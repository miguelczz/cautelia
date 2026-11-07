"""El proceso que decide un caso derivado: seis pasos, uno por uno, guardados apenas terminan.

Los pasos tienen identificador estable (`StepId`) y se guardan en `adjuster_run` apenas
terminan, para que la pantalla los muestre llegando. Los cuatro primeros y la lectura de la
poliza son de codigo (`gather`); el quinto es una investigacion con busqueda web (`vehicle_value`);
el sexto es una sola llamada de salida estructurada cuyo resultado el codigo valida (`validation`).
Como mucho dos llamadas a Claude por caso (A2).

**Un fallo nunca inventa una decision (A12).** Un error del proveedor, una cita que no se
verifica, una accion que la aseguradora no ofrece o una frase que la guardia detiene dejan la
corrida en `failed` con su motivo y el caso en `derived`; el reintento lo vuelve a intentar hasta
`attempts` veces. Sin saldo, o sin cupo del dia, la corrida queda `capped` y el caso espera.

**La decision queda fija antes de registrarse (A5).** La corrida se cierra como `decided` con
su titular y su explicacion y solo despues se le pide al registro que cierre el caso con ese mismo
titular. Si el registro falla, la corrida ya decidio: el siguiente arranque lo repite con el texto
guardado, sin volver a llamar al modelo. Dos arranques del mismo caso nunca trabajan a la vez: lo
decide la llave primaria de `adjuster_run` (`open_run`).
"""

from __future__ import annotations

from dataclasses import dataclass

from untangle import observability
from untangle.adjuster import clauses as clause_search
from untangle.adjuster import gather, prompting, quota, repository, steps, validation, vehicle_value
from untangle.adjuster.config import AdjusterConfig
from untangle.adjuster.errors import ErrorKind
from untangle.adjuster.models import (
    SUMMARY_SEPARATOR,
    AdjusterRun,
    RunStatus,
    RunStep,
    split_summary,
)
from untangle.adjuster.ports import AdjusterPorts, DecisionToRecord
from untangle.adjuster.schema import AdjusterDecision
from untangle.base import Use
from untangle.case_record.models import CaseState
from untangle.inbox import actions
from untangle.inbox.actions import InboxAction
from untangle.policy_rag.corpus.models import Clause
from untangle.policy_rag.facts.models import PolicyStatus
from untangle.providers.ports import BudgetExhausted, ProviderError
from untangle.telemetry.traces import api as traces
from untangle.telemetry.traces.models import NodeName
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import TenantId


@dataclass(frozen=True)
class RunOutcome:
    """Lo que paso con este arranque."""

    status: RunStatus
    #: Si **este** arranque era el dueno del trabajo (la corrida era nueva o se reabrio).
    started: bool
    action: InboxAction | None = None
    #: Si este arranque registro el cierre del caso.
    recorded: bool = False
    #: El titular, que es el comentario con el que se registra el cierre (A5).
    comment: str | None = None
    headline: str | None = None
    explanation: str | None = None
    error_kind: str | None = None


async def run_case(
    tenant_id: TenantId, case_id: str, *, ports: AdjusterPorts, config: AdjusterConfig
) -> RunOutcome:
    """Decide el caso, o lo deja como estaba con el motivo. Idempotente."""
    vista = await gather.read_case_state(tenant_id, case_id)
    if vista is None:
        return _failed(ErrorKind.CASE_NOT_FOUND)

    previa = await repository.read(tenant_id, case_id)
    if previa is not None and previa.status is RunStatus.DECIDED:
        return await _settle_decided(previa, state=vista.state, ports=ports)
    if vista.state is not CaseState.DERIVED:
        return _failed(ErrorKind.CASE_NOT_DECIDABLE)

    abierta = await repository.open_run(
        tenant_id,
        case_id,
        model=ports.model,
        max_attempts=config.attempts,
        stale_after=config.running_stale_after,
        now=ports.now(),
    )
    if not abierta.started:
        corrida = abierta.run
        if corrida.status is RunStatus.DECIDED:
            return await _settle_decided(corrida, state=vista.state, ports=ports)
        return RunOutcome(status=corrida.status, started=False, error_kind=corrida.error_kind)

    # Solo un caso nuevo, o uno que quedo esperando el cupo, reserva el del dia: un reintento
    # tras un fallo ya lo pago.
    reservar = previa is None or previa.status is RunStatus.CAPPED
    try:
        # Un trabajo de fondo del caso: la llamada a un proveedor cuelga de un tramo de nodo y este
        # de uno de turno (BR6.1, BR6.3); sin ellos la primera llamada muere con
        # `SpanNestingError`. Es el trabajo del nodo de decision.
        with (
            traces.turn_span(
                tenant_id=tenant_id,
                case_id=case_id,
                use=Use.ADJUSTER,
                turn_id=f"adjuster-{case_id}",
            ),
            traces.node_span(NodeName.DECISION),
        ):
            resultado = await _decide(
                tenant_id,
                case_id,
                policy_ref=vista.policy_ref,
                reserve=reservar,
                ports=ports,
                config=config,
            )
    except BudgetExhausted:
        resultado = await _cap(tenant_id, case_id, ports=ports)
    except ProviderError as error:
        resultado = await _fail(
            tenant_id, case_id, ErrorKind.from_provider(error.kind), ports=ports
        )
    except validation.DecisionRejected as rechazo:
        resultado = await _fail(tenant_id, case_id, rechazo.kind, ports=ports)
    except Exception as error:  # noqa: BLE001 -- el proceso no puede dejar la corrida corriendo para siempre; se registra el tipo, nunca el texto
        observability.emit(
            "adjuster.run_error", tenant_id=tenant_id, case_id=case_id, error=type(error).__name__
        )
        resultado = await _fail(tenant_id, case_id, ErrorKind.INTERNAL_ERROR, ports=ports)
    observability.emit(
        "adjuster.run_finished",
        tenant_id=tenant_id,
        case_id=case_id,
        status=resultado.status.value,
        error_kind=resultado.error_kind,
    )
    return resultado


def _failed(kind: ErrorKind) -> RunOutcome:
    return RunOutcome(status=RunStatus.FAILED, started=False, error_kind=kind.value)


async def _fail(
    tenant_id: TenantId, case_id: str, kind: ErrorKind, *, ports: AdjusterPorts
) -> RunOutcome:
    await repository.close_failed(tenant_id, case_id, error_kind=kind.value, now=ports.now())
    return RunOutcome(status=RunStatus.FAILED, started=True, error_kind=kind.value)


async def _cap(tenant_id: TenantId, case_id: str, *, ports: AdjusterPorts) -> RunOutcome:
    await repository.close_capped(tenant_id, case_id, now=ports.now())
    return RunOutcome(status=RunStatus.CAPPED, started=True)


async def _append(
    tenant_id: TenantId,
    case_id: str,
    step: RunStep,
    *,
    ports: AdjusterPorts,
    searches_used: int | None = None,
) -> None:
    await repository.append_step(
        tenant_id, case_id, step, now=ports.now(), searches_used=searches_used
    )


async def _decide(  # noqa: PLR0913 -- el caso, su poliza, si reserva cupo y los dos enchufes
    tenant_id: TenantId,
    case_id: str,
    *,
    policy_ref: str | None,
    reserve: bool,
    ports: AdjusterPorts,
    config: AdjusterConfig,
) -> RunOutcome:
    if reserve:
        cupo = await quota.reserve_case(config, now=ports.now())
        if not cupo.allowed:
            return await _cap(tenant_id, case_id, ports=ports)

    leido = await gather.read_case(tenant_id, case_id, cipher=ports.cipher)
    if leido is None:
        raise validation.DecisionRejected(ErrorKind.CASE_NOT_FOUND)
    idioma = leido.detail.language
    hoy = ports.now().date()

    # 1. Lee el reporte.
    await _append(tenant_id, case_id, steps.case_read(leido, idioma), ports=ports)

    # 2. Lee la poliza.
    poliza = await gather.read_policy(tenant_id, policy_ref, language=idioma, on=hoy)
    paso_poliza = steps.policy_read(poliza, idioma)
    await _append(tenant_id, case_id, paso_poliza, ports=ports)

    # 3. Busca las clausulas. Con la poliza vencida no hay nada que se pueda citar.
    emitida = None
    recuperadas: tuple[Clause, ...] = ()
    if poliza.summary is not None and poliza.policy_number is not None:
        emitida = await clause_search.find_policy(tenant_id, poliza.policy_number)
        if poliza.summary.status is PolicyStatus.IN_FORCE:
            recuperadas = await clause_search.retrieve(
                tenant_id,
                policy_number=poliza.policy_number,
                narrative=leido.narrative,
                language=idioma,
                ports=ports,
            )
    paso_clausulas = steps.clauses(recuperadas, poliza, idioma)
    await _append(tenant_id, case_id, paso_clausulas, ports=ports)

    # 4. Mira las reglas.
    evaluacion = leido.detail.rule_evaluation
    paso_reglas = steps.rules(evaluacion, idioma)
    await _append(tenant_id, case_id, paso_reglas, ports=ports)

    # 5. El valor de referencia del vehiculo.
    vehiculo = vehicle_value.pick_vehicle([v.description for v in poliza.vehicles], leido.narrative)
    valor = await vehicle_value.look_up(
        vehiculo, ports=ports, config=config, language=idioma, today=hoy
    )
    paso_valor = steps.vehicle_value(valor, idioma, has_policy=poliza.summary is not None)
    await _append(tenant_id, case_id, paso_valor, ports=ports, searches_used=valor.searches_used)

    # 6. Decide.
    acciones = actions.allowed_for(tenancy_config.require(tenant_id))
    refs = steps.rule_refs(evaluacion)
    prompt = prompting.build_decision_prompt(
        language=idioma,
        today=hoy,
        narrative=leido.narrative,
        fields=leido.fields,
        policy_text=paso_poliza.text,
        clauses_text=paso_clausulas.text,
        clauses=recuperadas,
        rules_text=f"{paso_reglas.text} [{', '.join(refs)}]" if refs else paso_reglas.text,
        vehicle_value_text=paso_valor.text,
        allowed_actions=sorted(acciones),
    )
    generado = await ports.generate.generate(prompt, schema=AdjusterDecision, use=Use.ADJUSTER)
    propuesta = generado.parsed_as(AdjusterDecision)
    decision = await validation.validate(
        propuesta,
        validation.CaseFacts(
            tenant_id=tenant_id,
            case_id=case_id,
            case_number=leido.detail.case_number,
            language=idioma,
            policy=emitida,
            retrieved=recuperadas,
            now=ports.now(),
        ),
    )
    await _append(tenant_id, case_id, steps.decision(decision, idioma), ports=ports)

    # La decision queda fija en la corrida y solo despues se registra el cierre del caso (A5).
    await repository.close_decided(
        tenant_id,
        case_id,
        decision=decision.action,
        summary=f"{decision.headline}{SUMMARY_SEPARATOR}{decision.explanation}",
        now=ports.now(),
    )
    registrado = await _record(
        tenant_id, case_id, action=decision.action, headline=decision.headline, ports=ports
    )
    return RunOutcome(
        status=RunStatus.DECIDED,
        started=True,
        action=decision.action,
        recorded=registrado,
        comment=decision.headline,
        headline=decision.headline,
        explanation=decision.explanation,
    )


async def _record(
    tenant_id: TenantId,
    case_id: str,
    *,
    action: InboxAction,
    headline: str,
    ports: AdjusterPorts,
) -> bool:
    """Registra el cierre del caso con el titular ya guardado. Un fallo no deshace la decision."""
    try:
        await ports.record_decision(
            DecisionToRecord(
                tenant_id=tenant_id,
                case_id=case_id,
                action=action,
                comment=headline,
                idempotency_key=f"adjuster-{case_id}",
            )
        )
    except Exception as error:  # noqa: BLE001 -- la corrida ya decidio; el reintento repite el registro con el mismo texto
        observability.emit(
            "adjuster.record_failed",
            tenant_id=tenant_id,
            case_id=case_id,
            error=type(error).__name__,
        )
        return False
    return True


async def _settle_decided(
    corrida: AdjusterRun, *, state: CaseState, ports: AdjusterPorts
) -> RunOutcome:
    """Una corrida que ya decidio: si el caso sigue derivado, repite el registro; si no, nada."""
    titular, explicacion = split_summary(corrida.summary)
    registrado = False
    if state is CaseState.DERIVED and corrida.decision is not None:
        registrado = await _record(
            corrida.tenant_id,
            corrida.case_id,
            action=corrida.decision,
            headline=titular,
            ports=ports,
        )
    return RunOutcome(
        status=RunStatus.DECIDED,
        started=False,
        action=corrida.decision,
        recorded=registrado,
        comment=titular,
        headline=titular,
        explanation=explicacion,
    )
