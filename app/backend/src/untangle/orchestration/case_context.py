"""El contexto del caso que un turno necesita, y cómo se aplican sus efectos (paso 7 de U12).

**Lo que este módulo cierra.** `orchestration/executor.py` (paso 4) dejó escrito
que construir la entrada tipada de un nodo a partir del caso, y aplicar su
conjunto de escritura de vuelta, es "de quien invoque el grafo real, todavía sin
construir". Este es ese módulo: la mitad de C-12 que la frontera de
`functional-spec.md` le pide a U4 ("crear el caso y aplicarle las
transiciones") no cubre -- leer su estado y guardar lo que `intake` extrajo --,
y sin la cual `handle_turn` no podría dirigir una segunda vuelta de la
conversación sin volver a preguntar lo ya dicho (BR3.2).

**Lo que se queda fuera, a propósito.** La transcripción durable (`case_record.
api.append_turn`, con su redacción real) no la pide la tabla de fronteras de
esta unidad -- solo "crear el caso y aplicarle las transiciones" -- y su costo
(la maquinaria de redacción entera) es justo lo que `evals/intake_probes.py` ya
documentó que se evita fuera de lo que hace falta probar. Sin ella, el conteo
de insultos de BR5.4 usa una memoria de proceso, no la transcripción
persistida: sobrevive a una llamada, no a un reinicio del proceso. Es una
simplificación **con nombre**, no un olvido, y no afecta ninguna regla de este
paso: BR3.2 se apoya en la completitud del caso, que sí es durable (se lee y se
escribe aquí, por la API real de U4), y las dos compuertas duras de este paso
(BR3.4, BR2.5) no dependen de la transcripción.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from untangle import observability
from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record import crypto, rules
from untangle.case_record import fields as case_fields
from untangle.case_record.models import (
    Actor,
    ActorType,
    CaseField,
    CaseState,
    Channel,
    Completeness,
    DerivationReason,
    FieldStatus,
    RecordType,
)
from untangle.compliance.controls.api import HandoffReason
from untangle.orchestration.nodes.intake import blocks
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.orchestration.nodes.intake.extraction import ExtractedField
from untangle.orchestration.nodes.intake.node import IntakeNodeInput, ReadbackResolution
from untangle.orchestration.nodes.intake.policy import PolicyMatch
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import IntakeConfig, TenantId


class UnknownCaseError(LookupError):
    """El caso que un turno nombra no existe para esta aseguradora."""


@dataclass(frozen=True)
class CaseContext:
    """Lo que `handle_turn` necesita del caso, ya cargado por la API real de U4."""

    tenant_id: TenantId
    case_id: str
    case_number: str
    record_type: RecordType
    state: CaseState
    completeness: Completeness
    language: Locale
    policy_ref: str | None
    #: El motivo y el turno de su derivacion, cuando el caso esta derivado. Los dos
    #: salen de la misma lectura del caso que todo lo demas --no cuestan una
    #: consulta mas-- y los lee el ritmo de fondo para acotar la revision de
    #: cumplimiento hasta la derivacion (BR5.1 de U10).
    derivation_reason: str | None
    derived_turn_id: str | None
    person_turns: tuple[str, ...]
    intake_config: IntakeConfig
    #: Si esta aseguradora tiene la cotizacion activa (U19, BR1.5). Dato de su
    #: configuracion: el turno no ramifica por aseguradora, lee esto.
    quote_enabled: bool = False


#: La memoria de proceso de BR5.4 (ver el docstring del módulo): cuántos turnos
#: de la persona se han visto en este proceso, por caso. No es la transcripción
#: -- no sobrevive a un reinicio -- y por eso vive aquí, marcada, y no en
#: `GraphState` (que sí sobrevive uno, vía el punto de control, y cuyo
#: `node_writes` solo admite lo que un `NodeSpec` real declara; ver `state.py`,
#: BR1.5).
_lock = threading.Lock()
_person_turns: dict[tuple[str, str], list[str]] = {}


def _remember_person_turn(tenant_id: TenantId, case_id: str, text: str) -> tuple[str, ...]:
    with _lock:
        vistos = _person_turns.setdefault((tenant_id, case_id), [])
        vistos.append(text)
        return tuple(vistos)


def forget_case(tenant_id: TenantId, case_id: str) -> None:
    """Olvida los turnos en memoria de un caso. Lo usan las pruebas entre corridas."""
    with _lock:
        _person_turns.pop((tenant_id, case_id), None)


def _quote_enabled_for(tenant_id: TenantId) -> bool:
    for aseguradora in tenancy_config.loaded().available:
        if aseguradora.tenant_id == tenant_id:
            return aseguradora.quote_enabled
    return False


def _intake_config_for(tenant_id: TenantId) -> IntakeConfig:
    for aseguradora in tenancy_config.loaded().available:
        if aseguradora.tenant_id == tenant_id:
            return aseguradora.intake
    return IntakeConfig()


async def _ensure_capturing(
    tenant_id: TenantId, case_id: str, caso: casos.CaseView, *, now: datetime
) -> CaseState:
    """T1 de `transitions.yaml`: "llega el primer turno de la persona" (`open -> capturing`).

    Sin esto, `blocks.next_block` ve un caso que nunca salió de `open` y
    devuelve siempre `DONE` (su propia regla: "un caso que ya salió de
    `CAPTURING`... no tiene más bloque que preguntar" -- `open` tampoco es
    `CAPTURING`). Cualquier turno la dispara, no solo uno de captura: T1 no
    pone condición ninguna, y "llegó un turno" es cierto también para una
    pregunta de cobertura o una petición de persona.
    """
    if caso.state is not CaseState.OPEN:
        return caso.state
    try:
        actualizado = await casos.apply_transition(
            tenant_id,
            case_id,
            CaseState.CAPTURING,
            context=rules.TransitionContext(now=now, actor=Actor(actor_type=ActorType.INSURED)),
        )
    except casos.InvalidTransitionError:
        # Dos turnos en vuelo sobre el mismo caso: los dos leyeron `open` y el otro
        # ya hizo T1. La transicion rechazada no es un fallo de este turno --el caso
        # esta donde tiene que estar--, asi que se vuelve a leer y se sigue con el
        # estado real. Si sigue en `open`, el rechazo era de verdad y se propaga
        # (visto el 2026-10-06: la persona leia "tuve un problema para responder
        # eso" por escribir mientras la agente aun respondia).
        releido = await casos.get_case(tenant_id, case_id)
        if releido is None or releido.state is CaseState.OPEN:
            raise
        return releido.state
    return actualizado.state


#: Como se traduce el motivo de la derivacion del canal al del caso.
#:
#: Los dos conjuntos son cerrados y **no tienen el mismo tamanio**: el del canal
#: (C-04) tiene seis motivos y el del caso (BR3.7 de U4) tiene tres, porque el del
#: caso lo **lee una regla** --la de la vuelta atras-- y crecerlo es cambiar el
#: modelo y su revision de esquema.
#:
#: Esta tabla traduce solo los que tienen un equivalente exacto. Los que no lo
#: tienen no se mapean a uno parecido: derivar un caso con un motivo que no es el
#: suyo deja un dato falso en la bandeja y en la regla que lo lee. Hoy produccion
#: emite **uno** --la peticion de persona-- y los otros cinco no tienen emisor; el
#: dia que alguno lo tenga, entra aqui a proposito o se queda sin derivar con su
#: evento, que es lo que hace esta funcion.
MOTIVO_DEL_CASO: Mapping[HandoffReason, DerivationReason] = {
    HandoffReason.HUMAN_REQUEST: DerivationReason.PERSON_REQUESTED,
    HandoffReason.RULE: DerivationReason.RULE,
    HandoffReason.LIMIT: DerivationReason.DEMO_LIMIT,
}


#: El camino de la tabla de transiciones de la captura al desenlace: T2 y T4.
_PASO_A_REVISION: Mapping[CaseState, CaseState] = {
    CaseState.CAPTURING: CaseState.VERIFYING,
    CaseState.VERIFYING: CaseState.DECIDING,
}


async def begin_review(
    *,
    tenant_id: TenantId,
    case_id: str,
    now: datetime,
    channel: Channel = Channel.CHAT,
) -> bool:
    """La captura del reporte termino: el caso pasa a revision, no a un ajustador (US1.17).

    Aplica el recorrido de la tabla de transiciones --`capturing -> verifying` (T2) y
    `verifying -> deciding` (T4)-- que hasta el 2026-10-13 el camino vivo se saltaba con T3, que
    deriva siempre. Del estado `deciding` sale el desenlace de las reglas: cerrado por T6 si el
    caso es de cierre directo, o derivado por T7 si las reglas piden que lo mire un ajustador.

    **Idempotente y tolerante**, como `derive_case`: un caso que ya esta en revision devuelve
    `True` sin tocar nada --un turno que llega con la oferta contestada vuelve a pasar por
    aqui--, y un caso que ya no admite el paso (derivado, cerrado) devuelve `False` y lo dice en
    la traza, sin levantar en medio de un turno que para la persona ya termino. Un caso `open`
    pasa por T1 primero.

    Devuelve si el caso quedo en `deciding`.
    """
    actor = Actor(actor_type=ActorType.SYSTEM)
    try:
        caso = await casos.get_case(tenant_id, case_id)
        if caso is None:
            return False
        estado = await _ensure_capturing(tenant_id, case_id, caso, now=now)
        while estado in _PASO_A_REVISION:
            actualizado = await casos.apply_transition(
                tenant_id,
                case_id,
                _PASO_A_REVISION[estado],
                context=rules.TransitionContext(now=now, actor=actor, channel=channel),
            )
            estado = actualizado.state
    except (casos.CaseClosedError, casos.InvalidTransitionError) as error:
        observability.emit(
            "orchestration.review_transition_rejected",
            tenant_id=tenant_id,
            case_id=case_id,
            detail=str(error),
        )
        return False
    if estado is not CaseState.DECIDING:
        observability.emit(
            "orchestration.review_not_started",
            tenant_id=tenant_id,
            case_id=case_id,
            state=estado.value,
        )
        return False
    return True


async def derive_case(  # noqa: PLR0913 -- el caso, el motivo, el turno, el reloj y quien/por donde, ninguno derivable de otro
    *,
    tenant_id: TenantId,
    case_id: str,
    reason: HandoffReason,
    turn_id: str | None,
    now: datetime,
    actor: Actor | None = None,
    channel: Channel = Channel.CHAT,
) -> bool:
    """Deriva el caso con su motivo y **el turno en que salio la frase** (BR3.7).

    Es la otra mitad de una derivacion, y la que faltaba: hasta ahora el canal
    publicaba la frase de derivacion y abria la pausa, y **el caso se quedaba en
    captura**. Un caso en captura no esta en la cola del ajustador --la cola
    excluye ese estado a proposito-- asi que quien pedia hablar con una persona no
    llegaba a la bandeja de nadie, y el aviso de "alguien lo esta revisando" que el
    chat sabe decir no se podia decir nunca.

    El turno es lo que deja a la revision de cumplimiento acotarse hasta la
    derivacion en vez de adivinar (BR5.1 de U10). Puede faltar: la derivacion de
    respaldo de un reporte terminado --la cadena fallo o no hay turno de la persona al
    que acotarla-- no inventa uno.

    `actor` y `channel` son de quien deriva y por donde: por omision, la persona por el
    chat, que es lo que hacen la peticion de persona y el limite de la demostracion. Las
    reglas derivan como el sistema (US1.17), y una llamada lo hace por la voz.

    Devuelve si derivo. `False` no es un fallo: es un motivo que el conjunto
    cerrado del caso no tiene, o un caso que ya no admite la transicion --cerrado,
    o ya derivado-- y las dos cosas se dicen en la traza en vez de levantar en
    medio de un turno que para la persona ya termino.
    """
    motivo = MOTIVO_DEL_CASO.get(reason)
    if motivo is None:
        observability.emit(
            "orchestration.handoff_reason_without_case_reason",
            tenant_id=tenant_id,
            case_id=case_id,
            reason=reason.value,
        )
        return False
    try:
        # **T1 primero, si el caso todavia no salio de `open`.** Pasa de verdad: una
        # conversacion cuyo **primer** mensaje pide hablar con una persona nunca
        # llego a cargar el contexto del caso --esa rama del turno corta antes-- asi
        # que el caso sigue abierto y la tabla de transiciones no tiene la pareja
        # `open -> derived`. La regla de T1 es "llego el primer turno de la persona",
        # y `_ensure_capturing` ya lo dice con estas palabras: una peticion de
        # persona tambien es un turno.
        caso = await casos.get_case(tenant_id, case_id)
        if caso is not None:
            await _ensure_capturing(tenant_id, case_id, caso, now=now)
        await casos.apply_transition(
            tenant_id,
            case_id,
            CaseState.DERIVED,
            context=rules.TransitionContext(
                now=now,
                actor=actor or Actor(actor_type=ActorType.INSURED),
                channel=channel,
                derivation_reason=motivo,
                derivation_turn_id=turn_id,
            ),
        )
    except (casos.CaseClosedError, casos.InvalidTransitionError) as error:
        observability.emit(
            "orchestration.handoff_transition_rejected",
            tenant_id=tenant_id,
            case_id=case_id,
            reason=reason.value,
            detail=str(error),
        )
        return False
    return True


def _contexto_de(
    tenant_id: TenantId,
    case_id: str,
    caso: casos.CaseView,
    *,
    state: CaseState,
    person_turns: tuple[str, ...],
) -> CaseContext:
    return CaseContext(
        tenant_id=tenant_id,
        case_id=case_id,
        case_number=caso.case_number,
        record_type=caso.record_type,
        state=state,
        completeness=caso.completeness,
        language=caso.language,
        policy_ref=caso.policy_ref,
        derivation_reason=caso.derivation_reason,
        derived_turn_id=caso.derived_turn_id,
        person_turns=person_turns,
        intake_config=_intake_config_for(tenant_id),
        quote_enabled=_quote_enabled_for(tenant_id),
    )


async def load_case_context(
    tenant_id: TenantId, case_id: str, *, turn_text: str, now: datetime
) -> CaseContext:
    """El contexto del caso para este turno, con `turn_text` ya contado (BR5.4).

    Se llama **antes** de correr `intake` (paso 1 del recorrido de
    `functional-spec.md`): `person_turns` incluye el turno actual, porque el
    conteo de insultos se hace "sobre la transcripción completa" y este turno
    ya es parte de ella. También aquí, y no en un paso aparte, se dispara T1
    (ver `_ensure_capturing`): todo turno pasa por esta función primero.
    """
    caso = await casos.get_case(tenant_id, case_id)
    if caso is None:
        msg = f"el caso '{case_id}' no existe para esta aseguradora"
        raise UnknownCaseError(msg)
    estado = await _ensure_capturing(tenant_id, case_id, caso, now=now)
    turnos = _remember_person_turn(tenant_id, case_id, turn_text)
    return _contexto_de(tenant_id, case_id, caso, state=estado, person_turns=turnos)


async def read_case_context(tenant_id: TenantId, case_id: str) -> CaseContext:
    """El contexto del caso tal como esta, **sin contar ningun turno ni moverlo** (2026-10-12).

    Lo pide el canal para entender un mensaje antes de entregarlo: leer no puede contar el
    turno dos veces --`load_case_context` lo cuenta para el recuento de insultos (BR5.4) y
    el turno lo volvera a pedir--, ni disparar T1. `person_turns` va vacio.
    """
    caso = await casos.get_case(tenant_id, case_id)
    if caso is None:
        msg = f"el caso '{case_id}' no existe para esta aseguradora"
        raise UnknownCaseError(msg)
    return _contexto_de(tenant_id, case_id, caso, state=caso.state, person_turns=())


async def completeness_of(tenant_id: TenantId, case_id: str) -> Completeness:
    """La completitud real del caso, recién leída (BR3.2, BR2.1).

    A diferencia de `load_case_context`, no cuenta el turno en la memoria de
    proceso de BR5.4: se usa para comprobar, **después** de aplicar lo que
    `intake` acaba de extraer, si ya hay identidad y póliza confirmadas -- una
    lectura de control, no un turno nuevo.
    """
    caso = await casos.get_case(tenant_id, case_id)
    if caso is None:
        msg = f"el caso '{case_id}' no existe para esta aseguradora"
        raise UnknownCaseError(msg)
    return caso.completeness


def build_intake_input(  # noqa: PLR0913 -- el contexto y cinco datos del turno, ninguno derivable de otro
    context: CaseContext,
    *,
    turn_text: str,
    turn_id: str,
    emergency_raised: bool,
    emergency_instruction: str | None,
    awaiting_confirmation: Block | None = None,
    stated_values: dict[str, str] | None = None,
    awaiting_policy_confirmation: PolicyMatch | None = None,
) -> IntakeNodeInput:
    """La entrada real de `intake` (C-15), traducida desde `CaseContext`.

    `intake` calcula su propio bloque pendiente de `completeness`, `case_state`
    y `record_type` (`nodes/intake/node.py`, `blocks.next_block`); esta función
    no lo precalcula ni lo duplica. `confirmed_values` llega vacío -- afecta
    solo la frase del resumen de cierre (AC1.5.2), y reconstruirlo entre turnos
    exigiría descifrar cada campo guardado, que ninguna regla de este paso
    pide (ver el docstring del módulo).
    """
    return IntakeNodeInput(
        tenant_id=context.tenant_id,
        case_id=context.case_id,
        record_type=context.record_type,
        case_state=context.state,
        completeness=context.completeness,
        language=context.language,
        turn_text=turn_text,
        turn_id=turn_id,
        person_turns=context.person_turns,
        emergency_raised=emergency_raised,
        emergency_instruction=emergency_instruction,
        confirmed_values={},
        awaiting_confirmation=awaiting_confirmation,
        stated_values=stated_values or {},
        intake_config=context.intake_config,
        awaiting_policy_confirmation=awaiting_policy_confirmation,
        case_number=context.case_number,
    )


async def stated_values_for_readback(
    tenant_id: TenantId,
    case_id: str,
    record_type: RecordType,
    completeness: Completeness,
    *,
    cipher: crypto.Cipher,
) -> dict[str, str]:
    """Lo dicho y sin confirmar, en claro, para poder leerlo de vuelta.

    **Se descifra lo justo y se dice por qué.** El docstring de este módulo
    explicaba que reconstruir los valores entre turnos exigiría descifrar cada
    campo guardado y que ninguna regla lo pedía. Ahora una lo pide: FD-U11-8
    obliga a leer los campos **nombrándolos** --"anotado, sin heridos" cumple y
    "anotado, los datos del accidente" no-- y sin el valor no hay lectura que
    valga. Lo que se abre son solo los campos que esperan su lectura, nunca el
    caso entero.
    """
    if not completeness.awaiting_readback:
        return {}
    # Los campos **del bloque que se va a leer**, no solo los que esperan
    # confirmacion: la frase de un bloque nombra todo lo suyo --"el martes, en la
    # salida 12"-- y con la mitad de los valores diria una frase a medias.
    #
    # **Cual bloque se lee no es "el que ya esta listo".** Se elegia el primero cuya
    # lectura estaba debida, pero un bloque de varios campos se completa *en el turno que
    # trae el ultimo*, y en el turno anterior todavia no estaba debido: la funcion devolvia
    # nada y la lectura nombraba solo el campo de este turno, con el resto en blanco. Con
    # los dos campos de "cuando y donde" ya pasaba; con los cuatro o seis de un bloque de la
    # solicitud (U19), que se preguntan de a uno, pasaria siempre. El bloque que se lee es el
    # primero del orden que tiene algun campo dicho y sin confirmar.
    bloque = next(
        (
            candidato
            for candidato in blocks.order_for(record_type)
            if blocks.readback_fields_in_block(record_type, candidato, completeness)
        ),
        None,
    )
    if bloque is None:
        return {}
    if record_type is RecordType.QUOTE_REQUEST:
        # La solicitud se confirma de una vez (2026-10-08): la lectura nombra los
        # campos de todos sus bloques, no solo los del primero.
        claves = tuple(
            clave
            for candidato in blocks.order_for(record_type)
            for clave in _claves_del_bloque(record_type, candidato)
        )
    else:
        claves = _claves_del_bloque(record_type, bloque)
    return await casos.open_field_values(tenant_id, case_id, claves, cipher=cipher)


def _claves_del_bloque(record_type: RecordType, block: Block) -> tuple[str, ...]:
    """Las claves de campo que ese bloque agrupa, leidas del esquema de U4."""
    return tuple(
        definicion.key
        for definicion in case_fields.definitions_for(record_type)
        if blocks.block_of(definicion.source_block) is block
    )


async def apply_readback_resolution(  # noqa: PLR0913 -- el caso, la resolucion y las tres llaves de aplicacion
    tenant_id: TenantId,
    case_id: str,
    resolution: ReadbackResolution,
    *,
    cipher: crypto.Cipher,
    channel: Channel,
    now: datetime,
) -> None:
    """Lo que la persona contestó a una lectura, aplicado al caso (BR3.1).

    **Es el único camino que confirma un campo desde la conversación.** Hasta el
    2026-09-29 solo había dos sitios que escribían `CONFIRMED` --la corrección
    desde la bandeja y el generador de datos sembrados-- así que los tres campos
    que exigen lectura en voz alta no llegaban a contar nunca y su bloque no
    terminaba: la agente volvía a preguntar lo ya contestado.

    Un "no" devuelve el campo a **`NOT_STATED` y sin valor**. No es un borrado
    por si acaso: la persona acaba de decir que lo anotado no es lo que dijo, así
    que conservarlo sería guardar un dato que nadie dio. `NOT_STATED` no es
    "vacío", es "nadie lo dijo", que es exactamente lo que ha pasado.
    """
    resultado = await casos.summary_with_fields(tenant_id, case_id)
    if resultado is None:
        return
    _, campos = resultado
    por_clave = {campo.field_key: campo for campo in campos}
    actor = Actor(actor_type=ActorType.INSURED)
    for clave in resolution.fields:
        anterior = por_clave.get(clave)
        if anterior is None:
            continue
        nuevo = (
            CaseField(
                case_id=case_id,
                field_key=clave,
                value=anterior.value,
                status=FieldStatus.CONFIRMED,
                evidence_turn_id=anterior.evidence_turn_id,
                confirmed_aloud_at=now,
                updated_at=now,
            )
            if resolution.accepted
            else CaseField(
                case_id=case_id,
                field_key=clave,
                value=None,
                status=FieldStatus.NOT_STATED,
                updated_at=now,
            )
        )
        await casos.set_field(tenant_id, nuevo, cipher=cipher, actor=actor, channel=channel)


async def apply_extracted_fields(  # noqa: PLR0913 -- el caso, lo extraido y las tres llaves de aplicacion (cifrador, canal, reloj), ninguna derivable de otra
    tenant_id: TenantId,
    case_id: str,
    extracted: tuple[ExtractedField, ...],
    *,
    cipher: crypto.Cipher,
    channel: Channel,
    now: datetime,
) -> None:
    """Aplica lo que `intake` extrajo al caso real, por la API de U4 (BR3.2).

    Sin esto, `case_record.api.get_case` seguiría devolviendo completitud cero
    en el turno siguiente y `intake` volvería a pedir el mismo bloque -- lo
    contrario de lo que BR3.2 exige. Cada campo se guarda como `STATED`: los
    tres campos que exigen lectura en voz alta (`requires_readback`) no cuentan
    como completos hasta que ese turno de confirmación ocurra (`case_record.
    fields.counts_as_complete`), y este módulo no lo simula -- no es una regla
    de este paso.
    """
    actor = Actor(actor_type=ActorType.INSURED)
    for campo in extracted:
        await casos.set_field(
            tenant_id,
            CaseField(
                case_id=case_id,
                field_key=campo.field_key,
                value=cipher.seal(campo.value),
                status=FieldStatus.STATED,
                evidence_turn_id=campo.evidence_turn_id,
                updated_at=now,
            ),
            cipher=cipher,
            actor=actor,
            channel=channel,
        )


#: El campo que la persona ya dio y no tiene que repetir si cambia de tema.
_IDENTIDAD = "identity_and_policy"


async def carry_over_identity(  # noqa: PLR0913 -- los dos casos y las tres llaves de aplicacion (cifrador, canal, reloj), ninguna derivable de otra
    tenant_id: TenantId,
    from_case_id: str,
    to_case_id: str,
    *,
    cipher: crypto.Cipher,
    channel: Channel,
    now: datetime,
) -> tuple[str, ...]:
    """Lleva la identidad y la poliza del caso anterior al nuevo (cambio de tema, 2026-10-12).

    Una persona que consultaba su poliza y ahora quiere reportar un accidente ya dio su
    nombre y su numero: pedirselos otra vez es justo lo que el cambio de tema existe para
    no hacer. Lleva, **si el caso nuevo las declara**:

    - el campo `identity_and_policy`, con su valor y la misma evidencia que ya tenia (el
      turno en que la persona lo dijo), como dicho y no como confirmado;
    - la poliza resuelta (`policy_ref`), que el corpus devolvio y la persona confirmo.

    El caso anterior no se toca. Devuelve que se llevo (las claves), para dejarlo en la
    traza; nunca los valores.
    """
    origen = await casos.get_case(tenant_id, from_case_id)
    con_campos = await casos.summary_with_fields(tenant_id, from_case_id)
    destino = await casos.get_case(tenant_id, to_case_id)
    if origen is None or con_campos is None or destino is None:
        return ()
    _, campos = con_campos
    llevado: list[str] = []

    declarados = {d.key for d in case_fields.definitions_for(destino.record_type)}
    dicho = next(
        (
            c
            for c in campos
            if c.field_key == _IDENTIDAD
            and c.status is not FieldStatus.NOT_STATED
            and c.value is not None
        ),
        None,
    )
    if dicho is not None and _IDENTIDAD in declarados:
        valores = await casos.open_field_values(
            tenant_id, from_case_id, (_IDENTIDAD,), cipher=cipher
        )
        valor = valores.get(_IDENTIDAD)
        if valor is not None:
            await casos.set_field(
                tenant_id,
                CaseField(
                    case_id=to_case_id,
                    field_key=_IDENTIDAD,
                    value=cipher.seal(valor),
                    status=FieldStatus.STATED,
                    evidence_turn_id=dicho.evidence_turn_id,
                    evidence_change_id=dicho.evidence_change_id,
                    updated_at=now,
                ),
                cipher=cipher,
                actor=Actor(actor_type=ActorType.INSURED),
                channel=channel,
            )
            llevado.append(_IDENTIDAD)

    if origen.policy_ref is not None and destino.record_type is not RecordType.QUOTE_REQUEST:
        await casos.set_policy_ref(tenant_id, to_case_id, origen.policy_ref)
        llevado.append("policy_ref")
    return tuple(llevado)


__all__ = [
    "CaseContext",
    "UnknownCaseError",
    "apply_extracted_fields",
    "apply_readback_resolution",
    "build_intake_input",
    "carry_over_identity",
    "completeness_of",
    "forget_case",
    "load_case_context",
    "read_case_context",
    "stated_values_for_readback",
]
