"""Lo que se hace con un reporte cuando la cadena de fondo termina: ejecutar el desenlace (US1.17).

La decision --cerrar, derivar o esperar-- la toma `closing_plan.plan`, pura. Este modulo la
**ejecuta**: cierra el caso como `registered` con su evidencia, o lo deriva con el motivo
`rule`, y se lo dice a la persona con una frase del catalogo y por la guardia de salida.

**Un cierre que no se pudo hacer deriva.** U4 rechaza un cierre con un adjunto sin evaluar o
con un caso que ya no lo admite; ese caso no se queda a medias en revision: se deriva. Y si lo
que levanta es una excepcion, quien llama deriva antes de dejarla salir (`refer_to_adjuster`).

**En el chat se guarda y se publica; en una llamada solo se guarda.** La despedida de la
llamada es la que dice el resultado, y publicarlo tambien por el aviso de fondo lo diria dos
veces.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from untangle import observability
from untangle.case_record import api as casos
from untangle.case_record.models import Actor, ActorType, Channel, Resolution
from untangle.case_record.rules import TransitionContext
from untangle.compliance.controls.api import HandoffReason
from untangle.orchestration import case_context, transcript_writer
from untangle.orchestration.closing_plan import (
    ClosingPlan,
    Step,
    announcement_key,
    announcement_text,
    closing_evidence,
    plan,
    refer,
)
from untangle.orchestration.contracts import CaseNotifier
from untangle.orchestration.output import ExitGate
from untangle.orchestration.state import GraphState
from untangle.tenancy.models import TenantId

__all__ = ["Delivery", "conclude", "refer_to_adjuster"]


# --- Ejecutar el desenlace --------------------------------------------------------------


@dataclass(frozen=True)
class Delivery:
    """Quien anuncia el desenlace y como: el aviso al chat, o solo la transcripcion en voz."""

    notifier: CaseNotifier | None
    clock: Callable[[], datetime]
    spoken: bool = False


def _canal(spoken: bool) -> Channel:
    return Channel.VOICE if spoken else Channel.CHAT


def _el_sistema() -> Actor:
    return Actor(actor_type=ActorType.SYSTEM)


async def conclude(  # noqa: PLR0913 -- el caso, el estado de la cadena y lo que decide que hacer, por nombre
    *,
    tenant_id: TenantId,
    case_id: str,
    context: case_context.CaseContext,
    state: GraphState,
    offer_open: bool,
    turn_id: str | None,
    trace_ref: str | None,
    delivery: Delivery,
) -> ClosingPlan:
    """Aplica el desenlace de una vuelta de la cadena de fondo y devuelve lo que hizo.

    Cierra, deriva o no hace nada (ver `plan`). Un cierre que U4 rechaza --un adjunto sin
    evaluar, un caso que ya no admite el cierre-- no se queda a medias: se deriva, que es la
    salida segura. Lo que levanta una excepcion aqui lo deja subir quien llama, que es quien
    sabe derivar antes de dejarla salir.
    """
    vista = await casos.get_case(tenant_id, case_id)
    decision = plan(
        case_state=None if vista is None else vista.state,
        offer_open=offer_open,
        closure=state.written("closure"),
        fired_rules=_reglas(state),
    )
    observability.emit(
        "orchestration.closing_planned",
        tenant_id=tenant_id,
        case_id=case_id,
        step=decision.step.value,
        reason=decision.reason,
    )
    if decision.step is Step.NOTHING:
        return decision

    if decision.step is Step.REGISTER and await _registrar(
        tenant_id,
        case_id,
        state=state,
        trace_ref=trace_ref,
        delivery=delivery,
    ):
        await _anunciar(decision, context, delivery)
        return decision

    if decision.step is Step.REGISTER:
        # U4 rechazo el cierre: el caso sigue en revision y se deriva.
        decision = refer("close_rejected")
    if not await _derivar_el_caso(decision, tenant_id, case_id, turn_id=turn_id, delivery=delivery):
        # Otro movio el caso entre que se leyo y ahora --un ajustador lo tomo, la persona
        # pidio hablar con alguien--: ya no es de este desenlace, y anunciar «lo revisa un
        # ajustador» seria decir algo que este codigo no hizo.
        observability.emit("orchestration.closing_superseded", tenant_id=tenant_id, case_id=case_id)
        return ClosingPlan(Step.NOTHING, "case_moved_meanwhile")
    await _anunciar(decision, context, delivery)
    return decision


async def refer_to_adjuster(  # noqa: PLR0913 -- el caso, su contexto, el turno, el motivo y como se entrega, por nombre
    *,
    tenant_id: TenantId,
    case_id: str,
    context: case_context.CaseContext,
    turn_id: str | None,
    reason: str,
    delivery: Delivery,
) -> bool:
    """La derivacion de respaldo: un reporte terminado nunca se queda en revision.

    La usa quien no pudo llegar al desenlace --la cadena o el efecto levantaron, o no hay un
    turno de la persona al que acotar la revision--. Devuelve si el caso quedo derivado. Nunca
    levanta: es lo ultimo que se hace con un caso que ya fallo una vez.
    """
    decision = refer(reason)
    try:
        derivado = await _derivar_el_caso(
            decision, tenant_id, case_id, turn_id=turn_id, delivery=delivery
        )
        if derivado:
            await _anunciar(decision, context, delivery)
    except Exception as error:  # noqa: BLE001 -- lo ultimo que se hace con un caso que ya fallo: no puede tapar el fallo de antes
        observability.emit(
            "orchestration.closing_fallback_failed",
            tenant_id=tenant_id,
            case_id=case_id,
            error_type=type(error).__name__,
            where=observability.failure_location(error),
        )
        return False
    return derivado


def _reglas(state: GraphState) -> Sequence[object]:
    reglas = state.written("fired_rules")
    return reglas if isinstance(reglas, tuple | list) else ()


async def _registrar(
    tenant_id: TenantId,
    case_id: str,
    *,
    state: GraphState,
    trace_ref: str | None,
    delivery: Delivery,
) -> bool:
    """Cierra el caso como `registered`, con sus cinco adjuntos. Devuelve si quedo cerrado."""
    turnos = await casos.transcript_of(tenant_id, case_id)
    evidencia = closing_evidence(
        state, case_id=case_id, has_transcript=bool(turnos), trace_ref=trace_ref
    )
    try:
        await casos.close_case(
            tenant_id,
            case_id,
            resolution=Resolution.REGISTERED,
            closing_evidence=evidencia,
            context=TransitionContext(
                now=delivery.clock(), actor=_el_sistema(), channel=_canal(delivery.spoken)
            ),
        )
    except (casos.ClosingRejectedError, casos.CaseClosedError, casos.CaseNotFoundError) as error:
        observability.emit(
            "orchestration.direct_closure_rejected",
            tenant_id=tenant_id,
            case_id=case_id,
            error_type=type(error).__name__,
            # El detalle nombra el adjunto que falto, nunca texto de la persona.
            detail=str(error),
        )
        return False
    return True


async def _derivar_el_caso(
    decision: ClosingPlan,
    tenant_id: TenantId,
    case_id: str,
    *,
    turn_id: str | None,
    delivery: Delivery,
) -> bool:
    return await case_context.derive_case(
        tenant_id=tenant_id,
        case_id=case_id,
        reason=HandoffReason.RULE,
        turn_id=turn_id,
        now=delivery.clock(),
        actor=_el_sistema(),
        channel=_canal(delivery.spoken),
    )


async def _anunciar(
    decision: ClosingPlan, context: case_context.CaseContext, delivery: Delivery
) -> None:
    """Le dice a la persona como quedo su reporte, con una frase del catalogo y por la guardia.

    **En el chat** se guarda y se publica (`say_without_turn`). **En una llamada** solo se
    guarda: quien lo dice es la despedida (`voice/closing.py`), que espera el resultado unos
    instantes y elige la frase. Publicarlo tambien por el aviso de fondo lo diria dos veces; lo
    que queda en la transcripcion es lo que la pantalla muestra a quien colgo antes de tiempo.
    """
    if announcement_key(decision, spoken=delivery.spoken) is None:
        return
    if not delivery.spoken and delivery.notifier is None:
        observability.emit(
            "orchestration.closing_not_announced",
            tenant_id=context.tenant_id,
            case_id=context.case_id,
            reason="no_notifier",
        )
        return
    puerta = ExitGate(
        tenant_id=context.tenant_id, language=context.language, case_id=context.case_id
    )
    puerta.case_number = context.case_number
    texto, _ = await puerta.send(
        announcement_text(decision, spoken=delivery.spoken, language=context.language)
    )
    ambito = transcript_writer.TranscriptScope(
        tenant_id=context.tenant_id,
        case_id=context.case_id,
        channel=_canal(delivery.spoken),
        language=context.language,
    )
    if delivery.notifier is None or delivery.spoken:
        await transcript_writer.record_agent_turn(
            ambito, text=texto, now=delivery.clock(), from_catalog=True
        )
        return
    await transcript_writer.say_without_turn(
        delivery.notifier, ambito, text=texto, now=delivery.clock(), from_catalog=True
    )
