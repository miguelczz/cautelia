"""El mundo de las pruebas del proceso del ajustador: dobles en memoria y escenarios.

Nada de aqui toca una base ni un proveedor. Lo que se sustituye es lo que **toca el exterior**
--el repositorio de `adjuster_run`, el cupo, la lectura del caso y de la poliza, la recuperacion
del corpus, el modelo, la busqueda y el registro del cierre--; todo lo demas es el codigo de
verdad: la lectura de los hechos de la poliza, el verificador exacto de citas, la guardia de
salida con sus patrones, el catalogo de textos, los prompts versionados y el detector de idioma.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import pytest
from pydantic import BaseModel

from untangle.adjuster import repository
from untangle.adjuster.config import AdjusterConfig
from untangle.adjuster.models import AdjusterRun, OpenedRun, RunStatus, RunStep
from untangle.adjuster.ports import AdjusterPorts, DecisionToRecord
from untangle.adjuster.schema import AdjusterDecision, DecisionReason
from untangle.base import Locale, ProviderName, SpendSource, Use
from untangle.case_record.crypto import Cipher
from untangle.case_record.models import (
    CaseField,
    CaseState,
    Channel,
    FieldStatus,
    Priority,
    RecordType,
    Sealed,
    Speaker,
    TranscriptTurn,
)
from untangle.inbox.actions import InboxAction
from untangle.inbox.case_view import CaseDetail
from untangle.policy_rag.corpus.models import (
    Clause,
    ClauseRelation,
    DeclaredDriver,
    IssuedPolicy,
)
from untangle.policy_rag.corpus.retrieval import RetrievalProbe, RetrievalResult
from untangle.providers.ports import (
    GenerationResult,
    Prompt,
    ResearchResult,
    ResearchSource,
    UsageReport,
    Vector,
)
from untangle.rules.models import FiredRule, RuleEvaluation
from untangle.telemetry.spend.models import QuotaDecision

AHORA = datetime(2026, 11, 3, 15, 0, tzinfo=UTC)

CONFIGURACION = AdjusterConfig.model_validate(
    {
        "config_version": 1,
        "max_searches": 3,
        "allowed_domains": ["fasecolda.com", "tucarro.com.co"],
        "daily_case_cap": 20,
        "attempts": 3,
        "vehicle_value_range_cop": [8_000_000, 800_000_000],
    }
)

#: Una aseguradora que decide y una agencia que solo envia (de la configuracion de verdad).
ASEGURADORA = "sunmeadow"
AGENCIA = "knotwell"

CLAUSULA_CHOQUE = "SM-PAP-2026-D.INS.COLLISION"
CLAUSULA_PLATAFORMA = "SM-PAP-2026-D.EXCL.PLATFORM"
RELATO = "Choqué contra un poste en la Avenida 80 y el carro quedó con el capó abierto."


def clausula(clause_id: str, *, tenant_id: str = ASEGURADORA, idioma: Locale = "es") -> Clause:
    return Clause(
        tenant_id=tenant_id,
        clause_id=clause_id,
        clause_key=clause_id,
        form_id="SM-PAP-2026",
        form_version="2026.1",
        part="Daños al vehículo asegurado",
        language=idioma,
        text=f"Texto de la cláusula {clause_id}.",
        is_distractor=False,
        issuer_label="Autos Poblado",
    )


def poliza(
    *, tenant_id: str = ASEGURADORA, hasta: date = date(2027, 6, 1), vehiculos: bool = True
) -> IssuedPolicy:
    return IssuedPolicy(
        tenant_id=tenant_id,
        policy_number="POL-11",
        issuer_tenant=ASEGURADORA,
        form_id="SM-PAP-2026",
        form_version="2026.1",
        endorsement_ids=(),
        named_insured={"full_name": "Daniela Castaño"},
        drivers=(DeclaredDriver(full_name="Daniela Castaño"),),
        vehicles=({"make_model_year": "Mazda CX-5 2022"},) if vehiculos else (),
        limits_and_deductibles={"d.damage_deductible": 1500, "a.property_damage": 40000},
        period_start=date(2026, 6, 1),
        period_end=hasta,
    )


def decision_del_modelo(
    action: InboxAction = InboxAction.APPROVE,
    *,
    cita: tuple[str, ...] = (CLAUSULA_CHOQUE,),
    idioma: Locale = "es",
    **cambios: Any,
) -> AdjusterDecision:
    """La salida estructurada del modelo para el camino feliz, con lo que se quiera cambiar."""
    es = idioma == "es"
    base: dict[str, Any] = {
        "action": action,
        "headline": ("Tu reporte quedó aprobado." if es else "Your report has been approved."),
        "explanation": (
            "Tu póliza estaba vigente el día del choque y cubre los daños de tu carro por un "
            "golpe contra un objeto fijo. Tienes un deducible de $ 1.500.000."
            if es
            else "Your policy was in force on the day of the crash and it covers damage to "
            "your car from hitting a fixed object. You have a deductible of COP 1,500,000."
        ),
        "reasons": (
            DecisionReason(
                text=(
                    "La póliza estaba vigente cuando ocurrió el choque."
                    if es
                    else "The policy was in force when the crash happened."
                ),
                clause_ids=(),
            ),
            DecisionReason(
                text=(
                    "Los daños por un choque están dentro de lo que la póliza protege."
                    if es
                    else "Crash damage is within what the policy protects."
                ),
                clause_ids=cita,
            ),
        ),
        "cited_clause_ids": cita,
        "uncertainties": (),
    }
    return AdjusterDecision.model_validate(base | cambios)


# --- El repositorio de la corrida, en memoria ------------------------------------------------


@dataclass
class RepositorioEnMemoria:
    """Las mismas transiciones que `adjuster.repository`, sin base de datos."""

    filas: dict[tuple[str, str], AdjusterRun] = field(default_factory=dict)
    cierres: list[str] = field(default_factory=list)
    pasos_anexados: list[tuple[str, str]] = field(default_factory=list)

    def instalar(self, mp: pytest.MonkeyPatch) -> None:
        for nombre in ("read", "open_run", "append_step", "close_decided", "close_capped"):
            mp.setattr(repository, nombre, getattr(self, nombre))
        mp.setattr(repository, "close_failed", self.close_failed)

    async def read(self, tenant_id: str, case_id: str) -> AdjusterRun | None:
        return self.filas.get((tenant_id, case_id))

    async def open_run(
        self, tenant_id: str, case_id: str, *, model: str, max_attempts: int, now: datetime
    ) -> OpenedRun:
        clave = (tenant_id, case_id)
        actual = self.filas.get(clave)
        if actual is None:
            nueva = AdjusterRun(
                tenant_id=tenant_id,
                case_id=case_id,
                status=RunStatus.RUNNING,
                attempt=1,
                model=model,
                created_at=now,
                updated_at=now,
            )
            self.filas[clave] = nueva
            return OpenedRun(run=nueva, started=True)
        if actual.status in {RunStatus.DECIDED, RunStatus.RUNNING}:
            return OpenedRun(run=actual, started=False)
        if actual.status is RunStatus.FAILED and actual.attempt >= max_attempts:
            return OpenedRun(run=actual, started=False)
        intento = actual.attempt + 1 if actual.status is RunStatus.FAILED else actual.attempt
        reabierta = AdjusterRun(
            tenant_id=tenant_id,
            case_id=case_id,
            status=RunStatus.RUNNING,
            attempt=intento,
            model=model,
            created_at=actual.created_at,
            updated_at=now,
        )
        self.filas[clave] = reabierta
        return OpenedRun(run=reabierta, started=True)

    async def append_step(
        self,
        tenant_id: str,
        case_id: str,
        step: RunStep,
        *,
        now: datetime,
        searches_used: int | None = None,
    ) -> AdjusterRun:
        clave = (tenant_id, case_id)
        actual = self.filas[clave]
        assert actual.status is RunStatus.RUNNING
        self.pasos_anexados.append((case_id, step.id.value))
        if any(p.id is step.id for p in actual.steps):
            return actual
        nueva = actual.model_copy(
            update={
                "steps": (*actual.steps, step),
                "searches_used": actual.searches_used if searches_used is None else searches_used,
                "updated_at": now,
            }
        )
        self.filas[clave] = nueva
        return nueva

    def _cerrar(self, tenant_id: str, case_id: str, **cambios: Any) -> AdjusterRun:
        clave = (tenant_id, case_id)
        actual = self.filas[clave]
        assert actual.status is RunStatus.RUNNING
        cerrada = AdjusterRun.model_validate({**actual.model_dump(), **cambios})
        self.filas[clave] = cerrada
        self.cierres.append(cerrada.status.value)
        return cerrada

    async def close_decided(  # noqa: PLR0913 -- misma firma que `repository.close_decided`
        self,
        tenant_id: str,
        case_id: str,
        *,
        decision: InboxAction,
        summary: str,
        now: datetime,
        searches_used: int | None = None,
    ) -> AdjusterRun:
        return self._cerrar(
            tenant_id,
            case_id,
            status=RunStatus.DECIDED,
            decision=decision,
            summary=summary,
            updated_at=now,
            **({} if searches_used is None else {"searches_used": searches_used}),
        )

    async def close_capped(
        self, tenant_id: str, case_id: str, *, now: datetime, searches_used: int | None = None
    ) -> AdjusterRun:
        return self._cerrar(
            tenant_id,
            case_id,
            status=RunStatus.CAPPED,
            updated_at=now,
            **({} if searches_used is None else {"searches_used": searches_used}),
        )

    async def close_failed(
        self,
        tenant_id: str,
        case_id: str,
        *,
        error_kind: str,
        now: datetime,
        searches_used: int | None = None,
    ) -> AdjusterRun:
        return self._cerrar(
            tenant_id,
            case_id,
            status=RunStatus.FAILED,
            error_kind=error_kind,
            updated_at=now,
            **({} if searches_used is None else {"searches_used": searches_used}),
        )


# --- Los puertos, con dobles que anotan lo que se les pidio ------------------------------------


@dataclass
class ModeloFalso:
    """El puerto `TextGenerator`: responde lo que el escenario diga y anota cada llamada."""

    respuesta: BaseModel | Exception | Callable[[], BaseModel | Exception] | None = None
    llamadas: list[tuple[Prompt, type[BaseModel] | None, Use]] = field(default_factory=list)
    esperar: bool = False

    async def generate(
        self, prompt: Prompt, *, schema: type[BaseModel] | None, use: Use
    ) -> GenerationResult:
        self.llamadas.append((prompt, schema, use))
        if self.esperar:
            await asyncio.sleep(0)
        salida = self.respuesta() if callable(self.respuesta) else self.respuesta
        if isinstance(salida, Exception):
            raise salida
        return GenerationResult(
            text=None,
            parsed=salida,
            usage=UsageReport(
                provider=ProviderName.ANTHROPIC,
                model="claude-test",
                use=use,
                units=(),
                source=SpendSource.COUNTED_LOCALLY,
            ),
            prompt=prompt.instruction.ref,
        )


@dataclass
class InvestigadorFalso:
    """El puerto `WebResearcher`."""

    respuesta: ResearchResult | Exception | None = None
    llamadas: list[dict[str, Any]] = field(default_factory=list)

    async def research(
        self,
        prompt: Prompt,
        *,
        use: Use,
        max_searches: int,
        allowed_domains: Sequence[str],
    ) -> ResearchResult:
        self.llamadas.append(
            {
                "prompt": prompt,
                "use": use,
                "max_searches": max_searches,
                "allowed_domains": tuple(allowed_domains),
            }
        )
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        assert self.respuesta is not None
        return self.respuesta


def investigacion(
    *,
    valor: str = "85000000",
    firmeza: str = "medium",
    url: str = "https://www.fasecolda.com/guia-de-valores/mazda-cx5-2022",
    busquedas: int = 2,
) -> ResearchResult:
    return ResearchResult(
        text=f"Encontré el valor en la guía.\nVALUE_COP: {valor}\nCONFIDENCE: {firmeza}",
        sources=(ResearchSource(url=url, title="Guía de Valores Fasecolda"),),
        searches_used=busquedas,
    )


@dataclass
class Registro:
    """Quien registra el cierre del caso (el puerto `record_decision`)."""

    llamadas: list[DecisionToRecord] = field(default_factory=list)
    falla: Exception | None = None

    async def __call__(self, pedido: DecisionToRecord) -> None:
        self.llamadas.append(pedido)
        if self.falla is not None:
            raise self.falla


async def _vector(textos: Sequence[str]) -> list[Vector]:
    return [(0.1, 0.2) for _ in textos]


@dataclass
class Mundo:
    """Todo lo que una prueba del proceso configura y mira."""

    repo: RepositorioEnMemoria
    modelo: ModeloFalso
    investigador: InvestigadorFalso
    registro: Registro
    puertos: AdjusterPorts
    cupos: list[Any]
    # Escenario: lo que dicen la lectura del caso y de la poliza.
    tenant_id: str = ASEGURADORA
    idioma: Locale = "es"
    estado: CaseState = CaseState.DERIVED
    policy_ref: str | None = "POL-11"
    la_poliza: IssuedPolicy | None = None
    recuperadas: tuple[Clause, ...] = ()
    cupo: QuotaDecision = field(default_factory=lambda: QuotaDecision(allowed=True))
    recuperaciones: list[str] = field(default_factory=list)
    relato: str = RELATO
    campos_extra: dict[str, str] = field(default_factory=dict)

    @property
    def case_id(self) -> str:
        return "caso-1"


def _detalle(mundo: Mundo) -> CaseDetail | None:
    campos = {
        "description": mundo.relato,
        "location": "Avenida 80 con calle 30, Medellín",
        "incident_datetime": "ayer a las 7 de la noche",
        "vehicle_and_driver": "Mazda CX-5, lo manejaba yo",
        **mundo.campos_extra,
    }
    return CaseDetail(
        case_id=mundo.case_id,
        case_number="AP-12",
        record_type=RecordType.CLAIM,
        state=mundo.estado,
        resolution=None,
        channel=Channel.CHAT,
        language=mundo.idioma,
        priority=Priority.NORMAL,
        derivation_reason="rule",
        completeness_complete=len(campos),
        completeness_total=7,
        completeness_per_field=dict.fromkeys(campos, True),
        completeness_optional=frozenset(),
        fields=tuple(
            CaseField(
                case_id=mundo.case_id,
                field_key=clave,
                value=Sealed(b"sellado"),
                status=FieldStatus.STATED,
                evidence_turn_id="t-1",
                updated_at=AHORA,
            )
            for clave in campos
        ),
        transcript=(
            TranscriptTurn(
                turn_id="t-1",
                case_id=mundo.case_id,
                speaker=Speaker.INSURED,
                channel=Channel.CHAT,
                language=mundo.idioma,
                text_redacted=mundo.relato,
                started_at=AHORA,
            ),
        ),
        history=(),
        coverage_answers=(),
        rule_evaluation=RuleEvaluation(
            evaluation_id="ev-1",
            tenant_id=mundo.tenant_id,
            case_id=mundo.case_id,
            ruleset_version="v1",
            category="referral",
            fired_rules=(FiredRule(id="SUN-R-02", version=1, touches_money=True),),
            inputs_snapshot={},
            explanation_key="rules.explain.coverage_review",
            evaluated_at=AHORA,
        ),
        compliance=None,
        trace=None,
        updated_at=AHORA,
    )


def armar_mundo(mp: pytest.MonkeyPatch) -> Mundo:  # noqa: C901 -- instala todos los dobles en un solo sitio
    """Instala los dobles y devuelve el mundo para que la prueba lo configure."""
    repo = RepositorioEnMemoria()
    repo.instalar(mp)
    modelo = ModeloFalso(respuesta=decision_del_modelo())
    investigador = InvestigadorFalso(respuesta=investigacion())
    registro = Registro()
    puertos = AdjusterPorts(
        generate=modelo,
        research=investigador,
        embed=_vector,
        embedding_model="embedding-test",
        model="claude-test",
        cipher=Cipher.__new__(Cipher),
        now=lambda: AHORA,
        record_decision=registro,
    )
    mundo = Mundo(
        repo=repo,
        modelo=modelo,
        investigador=investigador,
        registro=registro,
        puertos=puertos,
        cupos=[],
    )

    async def reservar(config: AdjusterConfig, *, now: datetime | None = None) -> QuotaDecision:
        mundo.cupos.append(config.daily_case_cap)
        return mundo.cupo

    mp.setattr("untangle.adjuster.quota.reserve_case", reservar)

    async def detalle(tenant_id: str, case_id: str) -> CaseDetail | None:
        return _detalle(mundo)

    class _Vista:
        def __init__(self) -> None:
            self.policy_ref = mundo.policy_ref
            self.state = mundo.estado

    async def get_case(tenant_id: str, case_id: str) -> Any:
        return _Vista()

    async def abrir(tenant_id: str, case_id: str, keys: Any, *, cipher: Cipher) -> dict[str, str]:
        valores = {
            "description": mundo.relato,
            "location": "Avenida 80 con calle 30, Medellín",
            "incident_datetime": "ayer a las 7 de la noche",
            "vehicle_and_driver": "Mazda CX-5, lo manejaba yo",
            **mundo.campos_extra,
        }
        return {k: valores[k] for k in keys if k in valores}

    mp.setattr("untangle.adjuster.gather.case_view.detail_for", detalle)
    mp.setattr("untangle.adjuster.gather.casos.get_case", get_case)
    mp.setattr("untangle.adjuster.gather.casos.open_field_values", abrir)

    async def buscar_poliza(tenant_id: str, *, policy_number: str) -> IssuedPolicy | None:
        if mundo.la_poliza is None or policy_number != mundo.la_poliza.policy_number:
            return None
        return mundo.la_poliza

    async def claves_de_endosos(tenant_id: str, *, form_ids: Any) -> dict[str, tuple[str, ...]]:
        return {}

    mp.setattr("untangle.policy_rag.corpus.repository.find_policy", buscar_poliza)
    mp.setattr("untangle.policy_rag.corpus.repository.clause_keys_of_forms", claves_de_endosos)
    mp.setattr("untangle.adjuster.clauses.corpus.find_policy", buscar_poliza)

    async def recuperar(tenant_id: str, **kwargs: Any) -> RetrievalResult:
        mundo.recuperaciones.append(kwargs["query_text"])
        return RetrievalResult(
            clauses=mundo.recuperadas,
            probe=RetrievalProbe(
                clause_ids=tuple(c.clause_id for c in mundo.recuperadas),
                sources={},
                filtered_by={},
            ),
        )

    mp.setattr("untangle.adjuster.clauses.corpus.retrieve", recuperar)

    async def sin_relaciones(*args: Any, **kwargs: Any) -> tuple[ClauseRelation, ...]:
        return ()

    mp.setattr("untangle.policy_rag.citations.verifier.corpus.relations_into", sin_relaciones)
    return mundo


def con_poliza_vigente(mundo: Mundo) -> None:
    mundo.la_poliza = poliza(tenant_id=mundo.tenant_id)
    mundo.recuperadas = (
        clausula(CLAUSULA_CHOQUE, tenant_id=mundo.tenant_id, idioma=mundo.idioma),
        clausula(CLAUSULA_PLATAFORMA, tenant_id=mundo.tenant_id, idioma=mundo.idioma),
    )


Corrida = Callable[[], Awaitable[Any]]
