"""Quien corre el ajustador de IA para el subconjunto `ajustador` de DS-2 (plan 09, fase 5, tanda 2c).

Por cada caso del golden set: siembra un caso derivado en la base del proyecto por la API publica
del registro del caso, corre **el proceso entero** (`adjuster.pipeline.run_case`) con los puertos
de verdad --Claude para la decision y la busqueda web, el corpus de la base para las clausulas-- y
devuelve lo observado: hechos, ningun veredicto. Los veredictos son del corredor
(`untangle.evals.adjuster_probes`), por codigo.

Tres cosas distinguen esta corrida del proceso servido, y las tres tienen su razon:

- **El cierre del caso no se registra.** El caso sembrado se queda en `derived`: lo que se mide es
  la decision, y una bandeja que se llena de casos cerrados por una evaluacion no sirve a nadie.
- **El reloj es el dia declarado por el caso** (`evaluated_on`), para que dos corridas del mismo
  commit vean la misma vigencia y para poder medir una poliza vencida con el corpus de hoy.
- **El tope diario de casos no se consume.** Se sube para esta corrida: el contador del dia es el
  que protege el saldo de los visitantes, y una evaluacion no le gasta cupo a la demo. El saldo
  real lo sigue acotando el techo de gasto y el libro de `manual_ledger`.

Los casos sembrados llevan origen `public_chat`: el reinicio nocturno de la demostracion los
borra, y no se mezclan con los casos de ejemplo del generador.

No se monta en el proceso servido ni corre en ninguna compuerta: lo llama
`untangle.server.understanding_cli` desde `mise run evals:ajustador`.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, time

from untangle import language as language_detection
from untangle.adjuster import clauses as clause_search
from untangle.adjuster import pipeline, repository, validation
from untangle.adjuster.config import AdjusterConfig
from untangle.adjuster.models import AdjusterRun, SourceKind, StepId, split_summary
from untangle.adjuster.ports import AdjusterPorts, DecisionToRecord
from untangle.case_record import api as casos
from untangle.case_record.crypto import Cipher
from untangle.case_record.models import (
    Actor,
    ActorType,
    CaseField,
    CaseState,
    Channel,
    DerivationReason,
    FieldStatus,
    Origin,
    RecordType,
    Speaker,
)
from untangle.case_record.rules import TransitionContext
from untangle.case_record.transcript import TurnDraft
from untangle.compliance.controls import api as controls
from untangle.evals.adjuster_probes import AdjusterObservation, AdjusterRequest, Decider
from untangle.policy_rag.citations import api as citations
from untangle.policy_rag.corpus.models import Clause
from untangle.policy_rag.facts import api as facts
from untangle.policy_rag.facts.models import PolicyStatus
from untangle.providers import config as provider_config
from untangle.providers.ports import Vector
from untangle.server import adjuster_wiring
from untangle.settings import Settings

#: El tope diario con el que corre una evaluacion: tan alto que nunca es el que decide.
_TOPE_DIARIO_DE_EVALUACION = 1_000_000

#: Donde no hay nada que buscar: un dominio que no existe. Las busquedas del caso se restringen a el.
_DOMINIO_SIN_RESULTADOS = "sin-resultados.invalid"

#: El campo en que el caso guarda lo que la persona conto, el mismo que lee el ajustador.
_NARRATIVE_FIELD = "description"

_SISTEMA = Actor(actor_type=ActorType.SYSTEM)


async def _no_registrar(decision: DecisionToRecord) -> None:
    """El cierre del caso no se registra en una evaluacion: el caso sembrado sigue derivado."""
    del decision


@dataclass(frozen=True)
class _Mundo:
    ports: AdjusterPorts
    config: AdjusterConfig
    cipher: Cipher


async def _sembrar_caso(request: AdjusterRequest, case_id: str, *, cipher: Cipher) -> None:
    """Un caso derivado a peticion de la persona, con su relato y su poliza, por la API publica."""
    ahora = datetime.now(UTC)
    tenant = request.tenant_id
    await casos.create_case(
        tenant,
        casos.NewCase(
            case_id=case_id,
            record_type=RecordType.CLAIM,
            channel=Channel.CHAT,
            origin=Origin.PUBLIC_CHAT,
            language=request.language,
            policy_ref=request.policy_number,
        ),
        now=ahora,
    )
    contexto = TransitionContext(now=ahora, actor=_SISTEMA, channel=Channel.CHAT)
    await casos.apply_transition(tenant, case_id, CaseState.CAPTURING, context=contexto)
    turno = f"{case_id}-t01"
    await casos.append_turn(
        tenant,
        TurnDraft(
            turn_id=turno,
            case_id=case_id,
            speaker=Speaker.INSURED,
            channel=Channel.CHAT,
            language=request.language,
            started_at=ahora,
        ),
        request.narrative,
    )
    await casos.set_field(
        tenant,
        CaseField(
            case_id=case_id,
            field_key=_NARRATIVE_FIELD,
            value=cipher.seal(request.narrative),
            status=FieldStatus.STATED,
            evidence_turn_id=turno,
            updated_at=ahora,
        ),
        cipher=cipher,
        actor=_SISTEMA,
        channel=Channel.CHAT,
    )
    await casos.apply_transition(
        tenant,
        case_id,
        CaseState.DERIVED,
        context=replace(contexto, derivation_reason=DerivationReason.PERSON_REQUESTED),
    )


async def _verified_ids(
    request: AdjusterRequest,
    *,
    cited: Sequence[str],
    retrieved: Sequence[Clause],
    claim: str,
    now: datetime,
) -> tuple[str, ...]:
    """De las citadas, las que el verificador exacto da por buenas, medidas otra vez aparte."""
    if not cited:
        return ()
    poliza = await clause_search.find_policy(request.tenant_id, request.policy_number)
    if poliza is None:
        return ()
    resultado = await citations.verify(
        request.tenant_id,
        policy=poliza,
        retrieved_clauses=tuple(retrieved),
        citations=[citations.Citation(clause_id=i, claim=claim) for i in cited],
        now=now,
    )
    buenas = {
        v.clause_id for v in resultado.citations if v.outcome is citations.CoverageOutcome.VERIFIED
    }
    return tuple(i for i in cited if i in buenas)


async def _guard_clean(request: AdjusterRequest, case_id: str, texts: Sequence[str]) -> bool:
    """Si la guardia de salida deja pasar cada texto de la decision tal cual."""
    vista = await casos.get_case(request.tenant_id, case_id)
    for texto in texts:
        resultado = await controls.guard_output(
            texto,
            tenant_id=request.tenant_id,
            language=request.language,
            case_id=case_id,
            case_number=vista.case_number if vista is not None else None,
            source_key=validation.GUARD_SOURCE_KEY,
        )
        if not resultado.unchanged:
            return False
    return True


def _step(
    corrida: AdjusterRun | None, step: StepId
) -> tuple[str, tuple[tuple[SourceKind, str], ...]]:
    paso = next((p for p in (corrida.steps if corrida else ()) if p.id is step), None)
    if paso is None:
        return "", ()
    return paso.text, tuple((s.kind, s.ref) for s in paso.sources)


async def _observe(
    request: AdjusterRequest,
    case_id: str,
    outcome: pipeline.RunOutcome,
    *,
    mundo: _Mundo,
) -> AdjusterObservation:
    """Lo que quedo tras correr el proceso: la corrida guardada, y las comprobaciones aparte."""
    corrida = await repository.read(request.tenant_id, case_id)
    resumen = await facts.policy_summary(
        request.tenant_id, request.policy_number, on=request.evaluated_on
    )
    en_vigor = None if resumen is None else resumen.status is PolicyStatus.IN_FORCE
    estado = outcome.status.value
    if corrida is None or corrida.decision is None:
        return AdjusterObservation(
            status=estado,
            error_kind=outcome.error_kind,
            searches_used=corrida.searches_used if corrida else 0,
            policy_in_force=en_vigor,
        )

    titular, explicacion = split_summary(corrida.summary)
    razones, fuentes_decision = _step(corrida, StepId.DECISION)
    _, fuentes_clausulas = _step(corrida, StepId.CLAUSES)
    texto_valor, fuentes_valor = _step(corrida, StepId.VEHICLE_VALUE)
    citadas = tuple(ref for tipo, ref in fuentes_decision if tipo is SourceKind.CLAUSE)

    # Las recuperadas: lo que la propia corrida listo, y lo que da recuperar otra vez para el mismo
    # relato. Solo hace falta cuando hay algo que verificar.
    ahora = mundo.ports.now()
    otra_vez: tuple[Clause, ...] = ()
    if citadas and en_vigor:
        otra_vez = await clause_search.retrieve(
            request.tenant_id,
            policy_number=request.policy_number,
            narrative=request.narrative,
            language=request.language,
            ports=mundo.ports,
        )
    recuperadas_ids = tuple(
        dict.fromkeys(
            [ref for tipo, ref in fuentes_clausulas if tipo is SourceKind.CLAUSE]
            + [c.clause_id for c in otra_vez]
        )
    )
    verificadas = await _verified_ids(
        request, cited=citadas, retrieved=otra_vez, claim=titular, now=ahora
    )
    guardia = await _guard_clean(
        request, case_id, [titular, explicacion, *(r for r in razones.split("\n") if r)]
    )
    return AdjusterObservation(
        status=estado,
        error_kind=outcome.error_kind,
        action=corrida.decision.value,
        headline=titular,
        explanation=explicacion,
        reasons_text=razones,
        cited_clause_ids=citadas,
        retrieved_clause_ids=recuperadas_ids,
        verified_clause_ids=verificadas,
        searches_used=corrida.searches_used,
        explanation_language=language_detection.measured(explicacion),
        guard_clean=guardia,
        policy_in_force=en_vigor,
        vehicle_value_found=any(tipo is SourceKind.WEB for tipo, _ in fuentes_valor),
        vehicle_step_text=texto_valor,
    )


def _config_for(request: AdjusterRequest, base: AdjusterConfig) -> AdjusterConfig:
    cambios: dict[str, object] = {"daily_case_cap": _TOPE_DIARIO_DE_EVALUACION}
    if request.vehicle_value == "not_found":
        cambios["allowed_domains"] = (_DOMINIO_SIN_RESULTADOS,)
    return base.model_copy(update=cambios)


def _decider(mundo: _Mundo) -> Decider:
    async def decide(request: AdjusterRequest) -> AdjusterObservation:
        case_id = f"eval-adj-{uuid.uuid4().hex[:12]}"
        await _sembrar_caso(request, case_id, cipher=mundo.cipher)
        dia = datetime.combine(request.evaluated_on, time(12, 0), tzinfo=UTC)
        puertos = replace(mundo.ports, now=lambda: dia, record_decision=_no_registrar)
        salida = await pipeline.run_case(
            request.tenant_id,
            case_id,
            ports=puertos,
            config=_config_for(request, mundo.config),
        )
        return await _observe(request, case_id, salida, mundo=replace(mundo, ports=puertos))

    return decide


def build_decider(
    settings: Settings,
    config: provider_config.ProviderPlatformConfig,
    *,
    cipher: Cipher,
    embed: Callable[[Sequence[str]], Awaitable[list[Vector]]],
    adjuster_config: AdjusterConfig,
) -> Decider | None:
    """Quien corre el proceso de verdad, o nada si el uso `adjuster` no tiene clave.

    Los puertos son los del proceso servido (`adjuster_wiring.build_ports`): el mismo cliente de
    Claude, con el techo y el libro de gasto, atribuido al uso `adjuster`.
    """
    puertos = adjuster_wiring.build_ports(settings, config, cipher=cipher, embed=embed)
    if puertos is None:
        return None
    return _decider(_Mundo(ports=puertos, config=adjuster_config, cipher=cipher))
