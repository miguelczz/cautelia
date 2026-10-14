"""Que transiciones permite el modelo, y que hace falta para cada una.

**Ninguna rama de codigo decide a donde va un caso.** El ejecutor busca la
pareja (estado actual, estado pedido) en la tabla versionada y evalua las
condiciones que esa fila nombra. Anadir una transicion es anadir una fila al
archivo, no un `if` aqui. Es lo que sostiene "ningun caso llega a cerrado por un
camino que nadie diseno" (BR3.2, SEC-U4.12).

**Todo intento deja entrada, incluido el rechazado** (BR5.4, SEC-U4.12). Por eso
el ejecutor no devuelve un caso: devuelve un resultado que **siempre** trae la
entrada del historial, y el que la persiste no puede obtener una respuesta sin
tener tambien lo que hay que escribir. Con una excepcion a secas, olvidar el
rastro seria cuestion de escribir un `except` en el sitio equivocado; asi no hay
sitio donde escribirlo.

**Las condiciones son datos con implementacion obligatoria.** Cada nombre que la
tabla menciona tiene que tener aqui su funcion, y cargar falla si alguno no la
tiene. Sin esa comprobacion, una condicion mal escrita en el archivo --una letra
de mas-- no se evaluaria nunca y la transicion pasaria siempre: el fallo mas
peligroso de todos, porque se parece a que todo funciona.

**El reloj entra por parametro.** T12 depende de cuanto tiempo paso, y un reloj
leido aqui dentro haria que sus dos bordes --el minuto 14:59 y el 15:01-- solo
se pudieran probar esperando.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from untangle.case_record import schema_loading
from untangle.case_record.models import (
    Actor,
    Case,
    CaseChange,
    CaseState,
    ChangeKind,
    Channel,
    ClosingEvidence,
    DerivationReason,
    Priority,
    Resolution,
    Transition,
)

#: Cuanto dura la ventana para retomar una llamada que el limite de la
#: demostracion corto (BR3.3). Quince minutos exactos cuentan como dentro: la
#: regla dice "no han pasado quince minutos", y un borde que excluyera el propio
#: minuto quince rechazaria a quien vuelve justo a tiempo.
VENTANA_PARA_RETOMAR = timedelta(minutes=15)


@dataclass(frozen=True)
class TransitionContext:
    """El contexto de un intento: quien, por donde, cuando, y lo que hace falta.

    Lleva junto todo lo que el caso no sabe de si mismo. Junto y no suelto por
    una razon practica: son los mismos datos que necesitan la evaluacion de las
    condiciones y la entrada del historial, y separarlos obligaba a arrastrar
    seis argumentos por cada firma.

    El reloj va aqui y no se lee dentro: es lo que permite probar los dos bordes
    de la ventana sin esperar quince minutos.
    """

    now: datetime
    actor: Actor
    channel: Channel | None = None
    #: Cuando el caso entro en derivado. Lo sabe el historial, no el caso.
    derived_at: datetime | None = None
    #: La clave del navegador que pide retomar, y la del que abrio el caso.
    browser_key: str | None = None
    case_browser_key: str | None = None
    #: Si un ajustador ya empezo a decidir. Un caso ya decidido no se retoma:
    #: la agente cuenta la decision en vez de volver a capturar.
    decision_started: bool = False
    #: El motivo, cuando el intento **deriva** el caso (BR3.7). Lo declara quien
    #: deriva --cumplimiento, las reglas, el limite de la demostracion o la
    #: siembra de U7--, y el caso no lo sabe de si mismo hasta ese momento.
    #:
    #: Anadido por U7 el 2026-09-21: T3, T5 y T7 piden un motivo declarado, y la
    #: superficie publica no ofrecia ninguna forma de declararlo, asi que ningun
    #: consumidor podia derivar un caso sin tocar el repositorio. Solo cuenta al
    #: pasar a `derived`; en cualquier otra transicion se ignora.
    derivation_reason: DerivationReason | None = None
    #: El turno en que salio la frase de derivacion, cuando la derivacion ocurre
    #: **en un turno** de la conversacion. Es lo que deja a la revision de
    #: cumplimiento acotarse hasta ahi (BR5.1 de U10) en vez de adivinar.
    #:
    #: **No es obligatorio y no lo sera**, al contrario que el motivo: el boton de
    #: pasar a una persona de la consola de voz y la decision de la bandeja derivan
    #: sin que haya ninguna frase en ningun turno, y exigirlo ahi obligaria a
    #: inventar uno. Solo cuenta al pasar a `derived`.
    derivation_turn_id: str | None = None


Condicion = Callable[[Case, TransitionContext], bool]


def _motivo_declarado(case: Case, contexto: TransitionContext) -> bool:
    """Derivar sin decir por que dejaria un caso en la bandeja sin explicacion."""
    return case.derivation_reason is not None or contexto.derivation_reason is not None


def _resolucion_declarada(case: Case, contexto: TransitionContext) -> bool:
    """Cerrar exige exactamente una resolucion del conjunto cerrado (BR3.4)."""
    return case.resolution is not None


def _evidencia_de_cierre_completa(case: Case, contexto: TransitionContext) -> bool:
    """Los cinco adjuntos, y un conjunto vacio cuenta como presente (BR6.3).

    Vacio dice que se miro y no habia; no evaluado dice que no se miro.
    Colapsarlos dejaria cerrar casos que nadie reviso.
    """
    return case.closing_evidence is not None and case.closing_evidence.complete


def _motivo_es_el_limite_de_la_demostracion(case: Case, contexto: TransitionContext) -> bool:
    """Solo se retoma lo que corto la demostracion, no lo que derivo una regla."""
    return case.derivation_reason is DerivationReason.DEMO_LIMIT


def _dentro_de_la_ventana(case: Case, contexto: TransitionContext) -> bool:
    """Quince minutos desde que el caso entro en derivado.

    Sin esa marca no hay ventana que medir, y la respuesta es que no: dar por
    buena una condicion que no se pudo comprobar es como una condicion deja de
    ser una condicion.
    """
    if contexto.derived_at is None:
        return False
    return contexto.now - contexto.derived_at <= VENTANA_PARA_RETOMAR


def _mismo_navegador(case: Case, contexto: TransitionContext) -> bool:
    """La misma persona, hasta donde una demostracion sin cuentas puede saberlo.

    Dos claves ausentes **no** son la misma: sin clave no se comprueba nada, y
    tratarlo como coincidencia dejaria a cualquiera retomar el caso de otro.
    """
    if contexto.browser_key is None or contexto.case_browser_key is None:
        return False
    return secrets.compare_digest(contexto.browser_key, contexto.case_browser_key)


def _sin_decision_iniciada(case: Case, contexto: TransitionContext) -> bool:
    """Un caso que ya se decidio no vuelve a captura."""
    return not contexto.decision_started


#: Cada nombre que la tabla de transiciones menciona, con su implementacion.
#: `_comprobar_implementaciones()` falla si la tabla nombra una que no este aqui.
CONDICIONES: Mapping[str, Condicion] = {
    "derivation_reason_declared": _motivo_declarado,
    "resolution_declared": _resolucion_declarada,
    "closing_evidence_complete": _evidencia_de_cierre_completa,
    "derivation_reason_is_demo_limit": _motivo_es_el_limite_de_la_demostracion,
    "within_resume_window": _dentro_de_la_ventana,
    "same_browser_key": _mismo_navegador,
    "no_decision_started": _sin_decision_iniciada,
}


class ConditionNotImplementedError(RuntimeError):
    """La tabla nombra una condicion que nadie implemento.

    Es condicion de arranque y no un aviso: una condicion sin implementacion no
    se evalua, la transicion pasa siempre, y el sintoma es que todo funciona.
    """


def assert_conditions_are_implemented(
    transiciones: tuple[Transition, ...] | None = None,
) -> None:
    """Toda condicion de la tabla tiene funcion. Lo llama la raiz de composicion."""
    filas = transiciones if transiciones is not None else schema_loading.transitions()
    nombradas = {condicion for fila in filas for condicion in fila.conditions}
    huerfanas = sorted(nombradas - set(CONDICIONES))
    if huerfanas:
        msg = (
            f"la tabla de transiciones nombra condiciones sin implementacion: "
            f"{huerfanas}. Una condicion que no se evalua deja pasar la "
            f"transicion siempre, y parece que todo funciona"
        )
        raise ConditionNotImplementedError(msg)

    # Y al reves: una implementacion que ninguna fila nombra es codigo que
    # nadie ejecuta, y en una regla de negocio eso casi siempre es un nombre
    # que se escribio distinto en los dos sitios.
    sin_uso = sorted(set(CONDICIONES) - nombradas)
    if sin_uso:
        msg = (
            f"estas condiciones estan implementadas y ninguna transicion las "
            f"nombra: {sin_uso}. O sobran, o el nombre no coincide con el del "
            f"archivo"
        )
        raise ConditionNotImplementedError(msg)


@dataclass(frozen=True)
class TransitionOutcome:
    """Lo que deja un intento de transicion: siempre una entrada, a veces un caso.

    `case` viene vacio cuando el intento se rechaza. `change` **nunca** viene
    vacio: es lo que hace que un rechazo no pueda pasar en silencio.
    """

    accepted: bool
    change: CaseChange
    case: Case | None = None
    #: Que fallo, cuando fallo. Vacio cuando se acepto.
    reason: str | None = None


def _transicion(desde: CaseState, hacia: CaseState) -> Transition | None:
    for fila in schema_loading.transitions():
        if fila.from_state is desde and fila.to_state is hacia:
            return fila
    return None


def _entrada(
    case: Case, *, kind: ChangeKind, detail: str, context: TransitionContext
) -> CaseChange:
    return CaseChange(
        change_id=f"chg-{secrets.token_hex(12)}",
        case_id=case.case_id,
        change_kind=kind,
        actor=context.actor,
        channel=context.channel,
        detail=detail,
        changed_at=context.now,
    )


def moved_meanwhile(
    case: Case, *, to: CaseState, context: TransitionContext, closing: bool = False
) -> CaseChange:
    """La entrada de un intento que llego tarde: otro movio el caso entre leerlo y escribirlo.

    El intento era legal sobre el caso que se leyo y por eso `attempt_transition` lo
    acepto; lo que lo rechaza es que la fila ya no esta en ese estado cuando se va a
    escribir. Es un rechazo como los demas y deja su entrada como los demas (BR5.4):
    sin ella, de las dos acciones simultaneas solo quedaria rastro de la que gano.
    """
    return _entrada(
        case,
        kind=ChangeKind.CLOSE_REJECTED if closing else ChangeKind.TRANSITION_REJECTED,
        detail=(
            f"el caso dejo de estar en {case.state} mientras se intentaba llevarlo a "
            f"{to}: otro cambio llego antes"
        ),
        context=context,
    )


def attempt_transition(
    case: Case, *, to: CaseState, context: TransitionContext
) -> TransitionOutcome:
    """Intenta llevar el caso al estado pedido. Siempre devuelve que anexar.

    No levanta: el rechazo es un resultado, no una interrupcion, porque quien
    llama tiene que escribir la entrada antes de decidir que hacer. Quien la
    convierte en error es la superficie del modulo, ya con el rastro guardado.
    """
    fila = _transicion(case.state, to)
    if fila is None:
        razon = (
            f"la tabla de transiciones no tiene la pareja "
            f"({case.state} -> {to}): ese camino no existe en el modelo"
        )
        return TransitionOutcome(
            accepted=False,
            change=_entrada(
                case, kind=ChangeKind.TRANSITION_REJECTED, detail=razon, context=context
            ),
            reason=razon,
        )

    faltan = [nombre for nombre in fila.conditions if not CONDICIONES[nombre](case, context)]
    if faltan:
        razon = f"{fila.id} ({case.state} -> {to}) pide {sorted(faltan)}, y no se cumplen"
        return TransitionOutcome(
            accepted=False,
            change=_entrada(
                case, kind=ChangeKind.TRANSITION_REJECTED, detail=razon, context=context
            ),
            reason=razon,
        )

    cerrado = to is CaseState.CLOSED
    # El motivo que trae el contexto se escribe en el caso **solo al derivar**, y
    # con el la prioridad que el tipo exige cuando la persona pidio hablar con
    # alguien (BR3.8): el tipo lo rechazaria de otro modo, y es la regla, no un
    # criterio de quien deriva.
    motivo = case.derivation_reason
    prioridad = case.priority
    turno_de_la_derivacion = case.derived_turn_id
    if to is CaseState.DERIVED and context.derivation_reason is not None:
        motivo = context.derivation_reason
        if motivo is DerivationReason.PERSON_REQUESTED:
            prioridad = Priority.HIGH
    if to is CaseState.DERIVED and context.derivation_turn_id is not None:
        # El turno se escribe **con la misma condicion que el motivo**: solo al
        # derivar. En cualquier otra transicion el contexto lo puede traer y aqui
        # se ignora, igual que el motivo, para que nadie pueda marcar un turno de
        # derivacion en un caso que no se esta derivando --el tipo lo rechazaria--.
        turno_de_la_derivacion = context.derivation_turn_id
    if to not in (CaseState.DERIVED, CaseState.CLOSED):
        # El caso sale de derivado sin cerrarse --la persona retomo la
        # conversacion--: el turno de aquella derivacion ya no describe su estado.
        turno_de_la_derivacion = None
    # `evolve` y no `model_copy`: el segundo no vuelve a validar, asi que un
    # caso movido a un estado nuevo saldria sin pasar por sus invariantes.
    movido = case.evolve(
        state=to,
        updated_at=context.now,
        closed_at=context.now if cerrado else case.closed_at,
        derivation_reason=motivo,
        derived_turn_id=turno_de_la_derivacion,
        priority=prioridad,
    )
    return TransitionOutcome(
        accepted=True,
        case=movido,
        change=_entrada(
            movido,
            kind=ChangeKind.TRANSITION_APPLIED,
            detail=f"{fila.id}: {case.state} -> {to}",
            context=context,
        ),
    )


def attempt_close(
    case: Case,
    *,
    resolution: Resolution,
    closing_evidence: ClosingEvidence,
    context: TransitionContext,
    comment: str | None = None,
) -> TransitionOutcome:
    """Intenta cerrar el caso con su resolucion y sus cinco adjuntos.

    Es un camino propio y no `attempt_transition(to=CLOSED)` por dos razones que
    se ven en el historial: la entrada de un cierre rechazado es de clase
    `close_rejected` --no se confunde con un camino inexistente-- y su detalle
    **nombra el adjunto que falto**, que es lo unico que el ajustador necesita
    saber para resolverlo.

    **No construye un caso a medias para comprobarlo.** Un caso con resolucion y
    sin cerrar viola BR3.5, asi que el candidato intermedio ni siquiera se puede
    construir: los adjuntos se comprueban antes, y el caso cerrado se arma de una
    sola vez con sus cuatro campos. Se descubrio cuando el tipo empezo a validar
    de verdad, y es la forma correcta: comprobar sobre un objeto que no podria
    existir es comprobar sobre algo que no va a pasar.
    """
    faltan = closing_evidence.missing()
    if faltan:
        razon = (
            f"no se puede cerrar: {sorted(faltan)} sin evaluar. Un conjunto "
            f"vacio cuenta como presente --se miro y no habia--; sin evaluar "
            f"dice que nadie lo miro (BR6.3)"
        )
        return _cierre_rechazado(case, razon, context)

    fila = _transicion(case.state, CaseState.CLOSED)
    if fila is None:
        razon = (
            f"la tabla de transiciones no tiene la pareja "
            f"({case.state} -> {CaseState.CLOSED}): desde ahi no se cierra"
        )
        return _cierre_rechazado(case, razon, context)

    cerrado = case.evolve(
        state=CaseState.CLOSED,
        resolution=resolution,
        closing_evidence=closing_evidence,
        closed_at=context.now,
        updated_at=context.now,
    )

    # Las condiciones de la fila se evaluan sobre el caso **ya cerrado**, que es
    # el que se guardaria. Evaluarlas sobre el de antes comprobaria si se podia
    # cerrar con lo que habia, no con lo que se esta cerrando.
    incumplidas = [
        nombre for nombre in fila.conditions if not CONDICIONES[nombre](cerrado, context)
    ]
    if incumplidas:
        razon = f"{fila.id} pide {sorted(incumplidas)}, y no se cumplen"
        return _cierre_rechazado(case, razon, context)

    return TransitionOutcome(
        accepted=True,
        case=cerrado,
        change=_entrada(
            cerrado,
            kind=ChangeKind.TRANSITION_APPLIED,
            # El comentario de quien decidio va **en la misma entrada** que el
            # cierre y no en una aparte: son un solo acto, y dos entradas serian
            # dos transacciones para algo indivisible. Anadido por U14 el
            # 2026-09-28, cuando la bandeja necesito registrar el porque.
            detail=(
                f"{fila.id}: {case.state} -> {CaseState.CLOSED}"
                + (f" | {comment}" if comment else "")
            ),
            context=context,
        ),
    )


def _cierre_rechazado(case: Case, razon: str, context: TransitionContext) -> TransitionOutcome:
    return TransitionOutcome(
        accepted=False,
        change=_entrada(case, kind=ChangeKind.CLOSE_REJECTED, detail=razon, context=context),
        reason=razon,
    )
