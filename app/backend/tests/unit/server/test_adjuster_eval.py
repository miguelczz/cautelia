"""Quien corre el ajustador para `evals:ajustador`: que siembre el caso por la API publica, corra el
proceso con el reloj y el tope de la evaluacion, no registre el cierre y observe lo que quedo.

Sin base y sin red: lo que toca el exterior --el registro del caso, la corrida guardada, la poliza,
el corpus, el verificador y la guardia-- son dobles anotados; el modelo ni se llama."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from untangle.adjuster import clauses as clause_search
from untangle.adjuster import pipeline, repository
from untangle.adjuster.config import AdjusterConfig
from untangle.adjuster.models import (
    AdjusterRun,
    RunStatus,
    RunStep,
    SourceKind,
    StepId,
    StepSource,
)
from untangle.adjuster.ports import AdjusterPorts, DecisionToRecord
from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record.models import CaseState, FieldStatus, Origin
from untangle.compliance.controls import api as controls
from untangle.evals.adjuster_probes import AdjusterObservation, AdjusterRequest
from untangle.inbox.actions import InboxAction
from untangle.policy_rag.citations import api as citations
from untangle.policy_rag.corpus.models import Clause
from untangle.policy_rag.facts import api as facts
from untangle.policy_rag.facts.models import PolicyStatus
from untangle.providers import config as provider_config
from untangle.providers.ports import Vector
from untangle.server import adjuster_eval
from untangle.settings import Settings

CHOQUE = "AP-PAP-2026-D.INS.COLLISION"
OTRA = "AP-PAP-2026-D.EXCL.1"
HOY = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)

CONFIGURACION = AdjusterConfig.model_validate(
    {
        "config_version": 1,
        "max_searches": 3,
        "allowed_domains": ["fasecolda.com"],
        "daily_case_cap": 20,
        "attempts": 3,
        "running_stale_seconds": 300,
        "vehicle_value_range_cop": [8_000_000, 800_000_000],
    }
)


def _clausula(clause_id: str) -> Clause:
    return Clause(
        tenant_id="sunmeadow",
        clause_id=clause_id,
        clause_key=clause_id,
        form_id="AP-PAP-2026",
        form_version="2026.1",
        part="Daños al vehículo",
        language="es",
        text="x",
        is_distractor=False,
        issuer_label="Autos Poblado",
    )


def _pedido(**cambios: Any) -> AdjusterRequest:
    base: dict[str, Any] = {
        "tenant_id": "sunmeadow",
        "case_ref": "eval-collision-approved-es",
        "language": "es",
        "policy_number": "POL-21",
        "narrative": "Choqué contra un poste.",
        "evaluated_on": date(2026, 11, 15),
        "vehicle_value": "open",
    }
    return AdjusterRequest(**(base | cambios))


def _corrida(
    estado: RunStatus = RunStatus.DECIDED, *, con_valor_web: bool = False, **cambios: Any
) -> AdjusterRun:
    pasos = [
        RunStep(
            id=StepId.CLAUSES,
            text="Encontré 2 cláusulas.",
            sources=(
                StepSource(kind=SourceKind.CLAUSE, ref=CHOQUE, label="Daños"),
                StepSource(kind=SourceKind.CLAUSE, ref=OTRA, label="Daños"),
            ),
        ),
        RunStep(
            id=StepId.VEHICLE_VALUE,
            text="No pude verificar el valor.",
            sources=(
                (
                    StepSource(
                        kind=SourceKind.WEB,
                        ref="https://fasecolda.com/x",
                        label="Fasecolda",
                        url="https://fasecolda.com/x",
                    ),
                )
                if con_valor_web
                else ()
            ),
        ),
        RunStep(
            id=StepId.DECISION,
            text="La póliza estaba vigente.\nLos daños están cubiertos.",
            sources=(StepSource(kind=SourceKind.CLAUSE, ref=CHOQUE, label="Daños"),),
        ),
    ]
    base: dict[str, Any] = {
        "tenant_id": "sunmeadow",
        "case_id": "c",
        "status": estado,
        "attempt": 1,
        "steps": tuple(pasos),
        "decision": InboxAction.APPROVE,
        "summary": "Aprobado.\n\nTu póliza cubre el choque.",
        "model": "m",
        "searches_used": 2,
        "created_at": HOY,
        "updated_at": HOY,
    }
    return AdjusterRun.model_validate(base | cambios)


@dataclass
class Mundo:
    """Lo que el doble del exterior anoto y lo que contesta."""

    llamadas: list[tuple[str, Any]] = field(default_factory=list)
    corrida: AdjusterRun | None = None
    salida: pipeline.RunOutcome = field(
        default_factory=lambda: pipeline.RunOutcome(status=RunStatus.DECIDED, started=True)
    )
    resumen: Any = field(default_factory=lambda: SimpleNamespace(status=PolicyStatus.IN_FORCE))
    verificadas: tuple[str, ...] = (CHOQUE,)
    guardia_limpia: bool = True
    puertos_usados: list[AdjusterPorts] = field(default_factory=list)
    configuraciones: list[AdjusterConfig] = field(default_factory=list)


def _doble_del_registro(m: Mundo, monkeypatch: pytest.MonkeyPatch) -> None:
    async def crear(tenant: str, nuevo: Any, *, now: datetime) -> None:
        m.llamadas.append(("create_case", (tenant, nuevo)))

    async def transicion(tenant: str, case_id: str, hacia: CaseState, *, context: Any) -> None:
        m.llamadas.append(("transition", (hacia, context.derivation_reason)))

    async def turno(tenant: str, borrador: Any, texto: str) -> None:
        m.llamadas.append(("turn", (borrador.speaker, texto)))

    async def campo(tenant: str, campo: Any, **kw: Any) -> None:
        m.llamadas.append(("field", campo))

    async def ver_caso(tenant: str, case_id: str) -> Any:
        return SimpleNamespace(case_number="SM-0001")

    monkeypatch.setattr(casos, "create_case", crear)
    monkeypatch.setattr(casos, "apply_transition", transicion)
    monkeypatch.setattr(casos, "append_turn", turno)
    monkeypatch.setattr(casos, "set_field", campo)
    monkeypatch.setattr(casos, "get_case", ver_caso)


def _doble_del_resto(m: Mundo, monkeypatch: pytest.MonkeyPatch) -> None:
    async def correr(
        tenant: str, case_id: str, *, ports: AdjusterPorts, config: AdjusterConfig
    ) -> pipeline.RunOutcome:
        m.puertos_usados.append(ports)
        m.configuraciones.append(config)
        return m.salida

    async def leer(tenant: str, case_id: str) -> AdjusterRun | None:
        return m.corrida

    async def poliza(tenant: str, numero: str, *, on: date) -> Any:
        m.llamadas.append(("policy_summary", on))
        return m.resumen

    async def recuperar(tenant: str, **kw: Any) -> tuple[Clause, ...]:
        m.llamadas.append(("retrieve", kw["narrative"]))
        return (_clausula(CHOQUE),)

    async def emitida(tenant: str, numero: str) -> Any:
        return SimpleNamespace(policy_number=numero)

    async def verificar(tenant: str, **kw: Any) -> Any:
        return SimpleNamespace(
            citations=[
                SimpleNamespace(
                    clause_id=i,
                    outcome=(
                        citations.CoverageOutcome.VERIFIED
                        if i in m.verificadas
                        else citations.CoverageOutcome.UNVERIFIABLE
                    ),
                )
                for i in (c.clause_id for c in kw["citations"])
            ]
        )

    async def guardia(texto: str, **kw: Any) -> Any:
        m.llamadas.append(("guard", kw["source_key"]))
        return SimpleNamespace(unchanged=m.guardia_limpia)

    monkeypatch.setattr(pipeline, "run_case", correr)
    monkeypatch.setattr(repository, "read", leer)
    monkeypatch.setattr(facts, "policy_summary", poliza)
    monkeypatch.setattr(clause_search, "retrieve", recuperar)
    monkeypatch.setattr(clause_search, "find_policy", emitida)
    monkeypatch.setattr(citations, "verify", verificar)
    monkeypatch.setattr(controls, "guard_output", guardia)


@pytest.fixture
def mundo(monkeypatch: pytest.MonkeyPatch) -> Mundo:
    m = Mundo(corrida=_corrida())
    _doble_del_registro(m, monkeypatch)
    _doble_del_resto(m, monkeypatch)
    return m


async def _embed(textos: Sequence[str]) -> list[Vector]:
    return [(0.0,) for _ in textos]


@pytest.fixture
def cifrador(monkeypatch: pytest.MonkeyPatch) -> crypto.Cipher:
    monkeypatch.setenv(crypto.KEY_ENV_VAR, crypto.generate_key())
    return crypto.Cipher.from_settings()


def _decisor(
    cifrador: crypto.Cipher,
) -> Callable[[AdjusterRequest], Awaitable[AdjusterObservation]]:
    ajustes = Settings(anthropic_api_key_adjuster="sk-ant-api03-clave-de-prueba")
    decisor = adjuster_eval.build_decider(
        ajustes,
        provider_config.load(),
        cipher=cifrador,
        embed=_embed,
        adjuster_config=CONFIGURACION,
    )
    assert decisor is not None
    return decisor


def test_sin_la_clave_del_uso_no_se_arma_quien_decide(cifrador: crypto.Cipher) -> None:
    decisor = adjuster_eval.build_decider(
        Settings(anthropic_api_key_adjuster=None),
        provider_config.load(),
        cipher=cifrador,
        embed=_embed,
        adjuster_config=CONFIGURACION,
    )

    assert decisor is None


async def test_siembra_un_caso_derivado_a_peticion_y_corre_el_proceso_con_el_dia_del_caso(
    mundo: Mundo, cifrador: crypto.Cipher
) -> None:
    observado = await _decisor(cifrador)(_pedido())

    nombres = [n for n, _ in mundo.llamadas]
    assert nombres[:5] == ["create_case", "transition", "turn", "field", "transition"]
    (_, (_, nuevo)) = next(c for c in mundo.llamadas if c[0] == "create_case")
    assert nuevo.origin is Origin.PUBLIC_CHAT
    assert nuevo.policy_ref == "POL-21"
    assert nuevo.case_id.startswith("eval-adj-")
    transiciones = [d for n, d in mundo.llamadas if n == "transition"]
    assert [t[0] for t in transiciones] == [CaseState.CAPTURING, CaseState.DERIVED]
    assert transiciones[1][1].value == "person_requested"
    campo = next(d for n, d in mundo.llamadas if n == "field")
    assert campo.field_key == "description"
    assert campo.status is FieldStatus.STATED
    # El proceso corre con el reloj del caso, un tope que no es el de la demo, y sin registrar.
    (puertos,) = mundo.puertos_usados
    assert puertos.now() == datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
    await puertos.record_decision(
        DecisionToRecord(
            tenant_id="sunmeadow",
            case_id="c",
            action=InboxAction.APPROVE,
            comment="x",
            idempotency_key="k",
        )
    )
    assert not [c for c in mundo.llamadas if c[0] == "closed"]
    (config,) = mundo.configuraciones
    assert config.daily_case_cap > 1000
    assert config.allowed_domains == CONFIGURACION.allowed_domains
    assert observado.status == "decided"


async def test_observa_lo_que_quedo_guardado_y_lo_comprueba_aparte(
    mundo: Mundo, cifrador: crypto.Cipher
) -> None:
    observado = await _decisor(cifrador)(_pedido())

    assert observado.action == "approve"
    assert observado.headline == "Aprobado."
    assert observado.explanation == "Tu póliza cubre el choque."
    assert observado.cited_clause_ids == (CHOQUE,)
    assert observado.retrieved_clause_ids == (CHOQUE, OTRA)
    assert observado.verified_clause_ids == (CHOQUE,)
    assert observado.searches_used == 2
    assert observado.explanation_language == "es"
    assert observado.guard_clean is True
    assert observado.policy_in_force is True
    assert observado.vehicle_value_found is False
    assert observado.vehicle_step_text == "No pude verificar el valor."
    assert ("policy_summary", date(2026, 11, 15)) in mundo.llamadas
    assert ("guard", "adjuster.decision") in mundo.llamadas


async def test_una_cita_que_el_verificador_no_da_por_buena_no_queda_verificada(
    mundo: Mundo, cifrador: crypto.Cipher
) -> None:
    mundo.verificadas = ()

    observado = await _decisor(cifrador)(_pedido())

    assert observado.cited_clause_ids == (CHOQUE,)
    assert observado.verified_clause_ids == ()


async def test_si_la_guardia_cambiaria_un_texto_lo_dice(
    mundo: Mundo, cifrador: crypto.Cipher
) -> None:
    mundo.guardia_limpia = False

    assert (await _decisor(cifrador)(_pedido())).guard_clean is False


async def test_un_valor_con_fuente_web_se_ve_y_la_poliza_vencida_tambien(
    mundo: Mundo, cifrador: crypto.Cipher
) -> None:
    mundo.corrida = _corrida(con_valor_web=True)
    mundo.resumen = SimpleNamespace(status=PolicyStatus.EXPIRED)

    observado = await _decisor(cifrador)(_pedido())

    assert observado.vehicle_value_found is True
    assert observado.policy_in_force is False
    # Con la poliza vencida no hay clausulas que recuperar otra vez.
    assert not [c for c in mundo.llamadas if c[0] == "retrieve"]


async def test_si_el_valor_no_puede_encontrarse_la_busqueda_se_restringe_a_un_dominio_sin_resultados(
    mundo: Mundo, cifrador: crypto.Cipher
) -> None:
    await _decisor(cifrador)(_pedido(vehicle_value="not_found"))

    (config,) = mundo.configuraciones
    assert config.allowed_domains == ("sin-resultados.invalid",)
    assert CONFIGURACION.allowed_domains == ("fasecolda.com",)


async def test_un_intento_sin_decision_se_observa_sin_inventar_nada(
    mundo: Mundo, cifrador: crypto.Cipher
) -> None:
    mundo.corrida = _corrida(
        RunStatus.FAILED, decision=None, summary=None, error_kind="guard_blocked"
    )
    mundo.salida = pipeline.RunOutcome(
        status=RunStatus.FAILED, started=True, error_kind="guard_blocked"
    )

    observado = await _decisor(cifrador)(_pedido())

    assert observado.status == "failed"
    assert observado.error_kind == "guard_blocked"
    assert observado.action is None
    assert observado.cited_clause_ids == ()
    assert observado.policy_in_force is True
    assert not [c for c in mundo.llamadas if c[0] in ("retrieve", "guard")]


async def test_sin_corrida_guardada_ni_poliza_en_el_registro_lo_dice(
    mundo: Mundo, cifrador: crypto.Cipher
) -> None:
    mundo.corrida = None
    mundo.resumen = None
    mundo.salida = pipeline.RunOutcome(
        status=RunStatus.FAILED, started=False, error_kind="case_not_found"
    )

    observado = await _decisor(cifrador)(_pedido())

    assert observado.searches_used == 0
    assert observado.policy_in_force is None
    assert observado.error_kind == "case_not_found"


async def test_una_decision_sin_citas_no_recupera_otra_vez(
    mundo: Mundo, cifrador: crypto.Cipher
) -> None:
    sin_citas = _corrida(
        steps=(RunStep(id=StepId.DECISION, text="Es una agencia.", sources=()),),
        decision=InboxAction.MARK_SENT,
    )
    mundo.corrida = sin_citas

    observado = await _decisor(cifrador)(_pedido(tenant_id="knotwell"))

    assert observado.action == "mark_sent"
    assert observado.cited_clause_ids == ()
    assert observado.verified_clause_ids == ()
    assert observado.vehicle_step_text == ""
    assert not [c for c in mundo.llamadas if c[0] == "retrieve"]
