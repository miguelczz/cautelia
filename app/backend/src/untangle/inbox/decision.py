"""La decision de un caso: se registra primero y se reanuda despues (BR4.1 a BR4.6).

**El orden no es una preferencia.** Primero se cierra el caso con su resolucion y
su evidencia, y solo entonces se le dice al grafo que siga. Al reves --reanudar y
despues registrar-- una caida en medio deja el grafo contando al asegurado una
decision que el caso no tiene, y no hay forma de saber cual de las dos es la
verdad. En este orden, una caida en medio deja el caso decidido y el grafo sin
reanudar, que se ve, se arregla y no le miente a nadie.

**No se espera al grafo.** La ruta responde `202` en cuanto la decision esta
escrita; la reanudacion corre de fondo. Esperarla colgaria la pantalla de quien
decidio por el tiempo que tarde una conversacion en continuar.

**El comentario es obligatorio y es lo que hace auditable la decision** (BR4.1).
Sin el no se escribe nada, y lo que se rechaza se rechaza **antes** de tocar el
caso: un comentario vacio no puede dejar un caso medio cerrado.

**La evidencia de cierre sale de lo que la vista ya reune.** Los cinco adjuntos que
U4 exige al cerrar son exactamente los bloques que la bandeja muestra, asi que se
construyen de lo que hay: `present` donde hay algo, `empty` donde se miro y no
habia. Nunca `not_evaluated` por comodidad: eso diria que no se miro, y se miro.

**Quien decide sale de quien entro.** Una decision tomada con un enlace de
demostracion se atribuye a un visitante, nunca a una persona de la aseguradora
(BR5.5): falsificar eso seria falsificar la respuesta a "quien decidio", que es la
pregunta que la explicacion del caso existe para contestar.

**Un caso que la agente aun evalua lo toma solo el personal** (2026-10-13). Entre el
cierre de la captura y el resultado de las reglas el caso pasa unos segundos en
`verifying` y `deciding`, y un proceso que se reinicia lo deja atascado ahi. Quien
entra con credencial puede decidirlo igual: el caso se deriva a su nombre (T5 o T7,
motivo `rule`) y sigue el camino de siempre. Un visitante con enlace no: tomarlo le
quitaria a su propio caso el cierre directo. Un caso tomado no se reanuda, porque el
grafo nunca lo dejo esperando a nadie.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from untangle import observability
from untangle.case_record import api as casos
from untangle.case_record.models import (
    Actor,
    ActorType,
    AttachmentKind,
    AttachmentState,
    CaseState,
    ClosingEvidence,
    DerivationReason,
    Resolution,
)
from untangle.case_record.rules import TransitionContext
from untangle.compliance.redaction.api import redact
from untangle.inbox import actions, case_view, events, receipts
from untangle.tenancy.models import TenantConfig, TenantId

#: El actor de una decision tomada con un enlace de demostracion (BR5.5).
#:
#: **Tipo `insured` y no uno nuevo**: quien entra con el enlace es la persona que
#: reporto ese caso, asi que el conjunto cerrado de U4 ya tiene su valor y anadirle
#: uno seria cambiar el enum de otra unidad para decir lo que ya dice. Lo que la
#: regla prohibe es atribuirla a una persona de la aseguradora, y esto es
#: literalmente lo contrario.
#:
#: El identificador no lleva nombre de nadie: el visitante no tiene uno, y
#: inventarselo seria escribir en el registro una persona que no existe.
VISITOR_ACTOR_ID = "demo-visitor"


class CommentRequiredError(ValueError):
    """Se intento decidir sin comentario (BR4.1).

    Lo que ve quien decide es su decision y su texto **todavia en pantalla**:
    perder lo escrito por un error de validacion es la forma mas barata de que
    alguien decida sin comentario a la segunda. Esta excepcion no lleva el texto,
    porque el texto nunca salio del navegador.
    """


#: El puerto de reanudacion (C-14). La raiz de composicion enchufa el de U12.
#:
#: Por puerto y no por importacion directa, igual que U13 hizo con su manejador de
#: turno: asi la decision se puede probar sin levantar el grafo entero, y lo que se
#: comprueba --que se registra antes de reanudar-- se ve con un doble que anota
#: cuando lo llamaron.
ResumeHandler = Callable[[str, object, TenantId], Awaitable[None]]

_REANUDAR: ResumeHandler | None = None


class ResumeHandlerNotInstalledError(RuntimeError):
    """Nadie enchufo la reanudacion.

    Falla en el acto en vez de registrar la decision y no reanudar: un caso
    decidido cuya conversacion nunca continua se ve igual que uno bien cerrado, y
    el asegurado se queda esperando una respuesta que no va a llegar.
    """


@dataclass(frozen=True)
class DecisionMade:
    """Una decision recien registrada, para quien tiene que avisarla (fase 1)."""

    tenant_id: TenantId
    case_id: str
    case_number: str
    resolution: str
    #: El comentario del ajustador, ya redactado como quedo guardado.
    comment: str
    #: El recibo que la registro: es lo que autoriza al aviso a afirmar un resultado.
    ref: str
    language: str


#: Quien le avisa la decision a la conversacion del caso (fase 1, 2026-10-08). Antes
#: el aviso "le avisamos por aqui en cuanto haya una respuesta" existia y nadie lo
#: enviaba (B1).
DecisionListener = Callable[[DecisionMade], Awaitable[None]]

_AVISAR: DecisionListener | None = None


def install_decision_listener(listener: DecisionListener | None) -> None:
    """La raiz de composicion enchufa quien le avisa la decision al chat."""
    global _AVISAR
    _AVISAR = listener


async def _avisar_la_decision(decision: DecisionMade) -> None:
    """El aviso al chat, despues de registrar y reanudar. Si falla, la decision ya
    esta registrada y se ve en la bandeja y en el enlace del caso: se deja rastro y
    no se le devuelve un error a quien decidio."""
    if _AVISAR is None:
        return
    try:
        await _AVISAR(decision)
    except Exception as error:  # noqa: BLE001 -- avisar no puede deshacer una decision ya registrada
        observability.emit(
            "inbox.decision_notice_failed",
            tenant_id=decision.tenant_id,
            case_id=decision.case_id,
            error=type(error).__name__,
        )


def install_resume_handler(handler: ResumeHandler) -> None:
    """La raiz de composicion enchufa la reanudacion de U12."""
    global _REANUDAR
    _REANUDAR = handler


def current_resume_handler() -> ResumeHandler:
    if _REANUDAR is None:
        msg = (
            "no hay reanudacion enchufada: la raiz de composicion llama a "
            "`install_resume_handler` al montar la bandeja"
        )
        raise ResumeHandlerNotInstalledError(msg)
    return _REANUDAR


def reset_resume_handler() -> None:
    """Desenchufa. La usan las pruebas para no filtrar un doble entre casos."""
    global _REANUDAR
    _REANUDAR = None


@dataclass(frozen=True)
class DecisionRecorded:
    """Lo que devuelve una decision registrada, o la que ya estaba."""

    receipt_id: str
    case_state: CaseState
    resolution: Resolution
    replayed: bool


def _evidencia(detalle: case_view.CaseDetail) -> ClosingEvidence:
    """Los cinco adjuntos, construidos de lo que la vista reunio.

    `present` cuando hay algo y `empty` cuando se miro y no habia. Nunca
    `not_evaluated`: eso significa "no se miro", y aqui se miro todo --es lo que
    la vista acaba de hacer--.
    """

    def _estado(hay: bool, referencia: str) -> AttachmentState:
        if hay:
            return AttachmentState(kind=AttachmentKind.PRESENT, reference=referencia)
        return AttachmentState(kind=AttachmentKind.EMPTY)

    citadas = any(respuesta.citations for respuesta in detalle.coverage_answers)
    return ClosingEvidence(
        transcript=_estado(bool(detalle.transcript), detalle.case_id),
        cited_clauses=_estado(citadas, detalle.case_id),
        fired_rules=_estado(detalle.rule_evaluation is not None, detalle.case_id),
        trace_id=_estado(
            detalle.trace is not None,
            detalle.trace.trace_id if detalle.trace is not None else detalle.case_id,
        ),
        control_results=_estado(detalle.compliance is not None, detalle.case_id),
    )


def actor_of(*, principal_id: str | None) -> Actor:
    """Quien actua: el personal con su identificador, o con enlace un visitante (BR5.5).

    Publica porque la decision y las anotaciones para las reglas atribuyen igual a quien
    entra con el enlace de su caso: dos copias de esta tabla serian dos sitios donde el
    visitante podria quedar como alguien que no es.
    """
    if principal_id is None:
        return Actor(actor_type=ActorType.INSURED, actor_id=VISITOR_ACTOR_ID)
    return Actor(actor_type=ActorType.STAFF, actor_id=principal_id)


async def _tomar(
    tenant_id: TenantId, detalle: case_view.CaseDetail, *, actor: Actor, now: datetime
) -> None:
    """Deriva un caso que la agente aun evalua, a nombre de quien lo toma (T5 o T7).

    El motivo es `rule`: es el unico de los tres que no dice que la persona lo pidio ni
    que se acabo la demostracion, y el caso llega a la bandeja por la evaluacion que
    no termino. Quien lo tomo queda en la entrada del historial como `staff` con su
    identificador, igual que cualquier otro movimiento suyo.

    Si el caso se movio entre la lectura y este intento --la agente lo cerro o lo
    derivo en ese instante-- la tabla rechaza la pareja y se responde como cualquier
    otro caso que ya no admite la accion: `409`, sin cambiar nada.
    """
    try:
        await casos.apply_transition(
            tenant_id,
            detalle.case_id,
            CaseState.DERIVED,
            context=TransitionContext(
                now=now,
                actor=actor,
                channel=detalle.channel,
                derivation_reason=DerivationReason.RULE,
            ),
        )
    except casos.InvalidTransitionError as error:
        msg = (
            f"el caso '{detalle.case_id}' dejo de estar en '{detalle.state.value}' "
            "mientras se intentaba tomarlo"
        )
        raise actions.ActionNotAllowedError(msg) from error


async def decide(  # noqa: PLR0913 -- la accion, el comentario, la clave, quien y el reloj
    tenant: TenantConfig,
    *,
    case_id: str,
    action: actions.InboxAction,
    comment: str,
    idempotency_key: str,
    principal_id: str | None,
    now: datetime,
) -> DecisionRecorded:
    """Registra la decision, cierra el caso y reanuda el grafo, en ese orden."""
    if not comment.strip():
        msg = "toda decision exige comentario: es lo que la hace auditable (BR4.1)"
        raise CommentRequiredError(msg)

    tenant_id = tenant.tenant_id
    huella = receipts.digest_of(case_id, action.value, comment)
    anterior = await receipts.reuse_or_none(
        tenant_id,
        operation=receipts.Operation.DECISION,
        idempotency_key=idempotency_key,
        request_digest=huella,
    )

    detalle = await case_view.detail_for(tenant_id, case_id)
    if detalle is None:
        msg = f"el caso '{case_id}' no existe para '{tenant_id}'"
        raise LookupError(msg)

    if anterior is not None:
        # La misma clave otra vez: se devuelve la primera y **no se vuelve a
        # reanudar**. Reanudar dos veces le contaria al asegurado la decision dos
        # veces, que es un dano que el recibo existe para evitar.
        return DecisionRecorded(
            receipt_id=anterior.receipt_id,
            case_state=detalle.state,
            resolution=detalle.resolution or actions.RESOLUTION_OF[action],
            replayed=True,
        )

    # Que un caso ya decidido no se vuelva a decidir lo impone `require_allowed`:
    # `closed` no esta entre los estados decidibles. Aqui habia una comprobacion
    # propia que lo repetia, y al romperla no se cayo ninguna prueba --era una
    # tercera copia de la misma regla--. Se quito: dos guardias para lo mismo
    # significan que el dia que una cambie, la otra sigue diciendo lo de antes.
    resolucion = actions.require_allowed(
        tenant, action=action, state=detalle.state, by_staff=principal_id is not None
    )
    actor = actor_of(principal_id=principal_id)

    # 0. Un caso que la agente aun evalua se toma antes de decidirlo: se deriva a nombre
    #    de quien lo toma, con su rastro, y solo despues sigue el camino de siempre.
    tomado = actions.is_takeover(detalle.state)
    if tomado:
        await _tomar(tenant_id, detalle, actor=actor, now=now)

    # 1. Se registra. El caso queda cerrado con su resolucion, su hora, quien
    #    decidio y su comentario, en la transaccion de U4.
    # El comentario se redacta **antes** de persistirlo, como todo lo que escribe
    # una persona: la regla no tiene excepcion para quien lleva credencial, y por
    # el enlace firmado este texto llega desde una superficie publica. Lo que el
    # comentario aporta --el porque-- sobrevive a la redaccion; lo que no
    # sobrevive es el dato personal que alguien copie de la conversacion.
    comentario = str(redact(comment, language=detalle.language))
    vista = await casos.close_case(
        tenant_id,
        case_id,
        resolution=resolucion,
        closing_evidence=_evidencia(detalle),
        context=TransitionContext(now=now, actor=actor, channel=detalle.channel),
        comment=comentario,
    )
    recibo = await receipts.record(
        tenant_id,
        operation=receipts.Operation.DECISION,
        idempotency_key=idempotency_key,
        case_id=case_id,
        request_digest=huella,
        result_ref=resolucion.value,
        now=now,
    )
    await events.append(
        tenant_id,
        case_id=case_id,
        kind=events.EventKind.CASE_DECIDED,
        summary=f"decidido: {resolucion.value}",
        language=detalle.language,
        now=now,
    )

    # 2. Y solo ahora se reanuda, de fondo. Si esto falla, el caso ya esta
    #    decidido y se ve; al reves, el grafo habria contado una decision que el
    #    caso no tiene.
    observability.emit(
        "inbox.case_decided",
        tenant_id=tenant_id,
        case_id=case_id,
        resolution=resolucion.value,
        actor_type=actor.actor_type.value,
        taken_over=tomado,
    )
    # Un caso tomado no se reanuda: el grafo no lo tiene pausado esperando a nadie
    # porque nunca llego a pedir revision. Reanudarlo ademas de inutil es peligroso:
    # con un proceso reiniciado a media evaluacion, `resume` vuelve a correr los nodos
    # que le faltaban sobre un caso que ya esta cerrado.
    if not tomado:
        await current_resume_handler()(case_id, resolucion.value, tenant_id)
    await _avisar_la_decision(
        DecisionMade(
            tenant_id=tenant_id,
            case_id=case_id,
            case_number=str(vista.case_number),
            resolution=resolucion.value,
            comment=comentario,
            ref=recibo.receipt_id,
            language=detalle.language,
        )
    )

    return DecisionRecorded(
        receipt_id=recibo.receipt_id,
        case_state=vista.state,
        resolution=resolucion,
        replayed=False,
    )
