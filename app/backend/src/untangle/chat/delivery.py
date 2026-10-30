"""Entregar un turno del chat al grafo y poner de vuelta lo que salga (BR2.5, BR6.4).

Es la pieza que junta lo que las otras deciden: toma un mensaje ya admitido, se lo
da a `handle_turn` de U12 con la forma de C-14, serializa cada evento que vuelve
segun C-04 y lo deja en la cola del navegador.

**Todo evento se publica, tambien el de error.** El flujo de C-14 termina siempre en
texto final, derivacion o error, y esta funcion no elige cual: publica lo que le den.
Un camino que se tragara el error dejaria la conversacion colgada sin decir nada, que
es el modo de fallo que REL-U13.1 existe para impedir.

**El caso nace aqui, en el primer turno** (BR1.1 de U11, y el docstring de
`UnaddressedTurnError` de U12: "cablear cuando nace un caso es de U13/U16"). Antes
no nacia en ningun sitio: este archivo entregaba el turno con `case_id` en nulo y
el grafo levantaba, asi que **el chat nunca pudo atender a un visitante nuevo**.
Lo abre `chat.case_opening`, que elige el tipo con el reconocedor determinista de
U12 y se lo pide a `identity.open_case`, la funcion de U11 que existia sin
consumidor. Se ata a la conversacion antes de llamar al grafo: un turno que se
rompa a mitad deja el caso atado igual, y el mensaje siguiente sigue en el mismo.

**El texto que se persiste va redactado, y el tipo lo impone.** `append_turn` exige un
`Redacted`, asi que no hay forma de escribir la transcripcion sin haber pasado por la
redaccion de U3. Esta unidad no la aplica a mano: la llama, y el comprobador de tipos
es quien no deja saltarsela.

**El grafo entra por un puerto, no por un import.** Esta unidad no importa el
modulo que lo implementa: declara `TurnHandler` --lo que un canal necesita de
C-14, una funcion que recibe el turno y devuelve sus eventos-- y la raiz de
composicion enchufa el de U12. No es ceremonia: el contrato de importacion del
proyecto prohibe que un canal llegue a LangGraph **ni siquiera por transitividad**,
y llamar al modulo del runtime lo arrastraba entero. Invertir la dependencia es
lo que hace cierto que cambiar el framework del grafo no toque ningun canal, que
es lo que ADR-003 decide.

**El resumen de traza lo abre esta unidad, y no otra** (BR4.3, C-23). U5 dejo
construida toda la maquinaria --la tabla, el estado `recording`, la comparacion de
dueno-- y **nadie la estrenaba**: ni un solo `open_summary` en el codigo de
produccion, asi que la tabla estaba vacia y la pagina del resumen habria dicho "no
encontrado" siempre. Se midio antes de construir la pagina encima. La abre el canal
porque el resumen se ata al **resumen de la clave del navegador**, y esa clave no la
conoce nadie mas: ni el grafo, ni la telemetria.

**Y lo cierra en el mismo turno** (2026-10-15): `traces.settle_summary` lo completa
con los tramos del turno --nodos, latencia y costo, que son de U5 y U12; esta unidad
no los inventa-- y lo deja `ready`. Hasta ese dia nadie lo hacia y la pagina decia
"se esta registrando" para siempre, sin enlace a la traza en Langfuse. Un turno sin
nodos se queda en `recording`: un resumen listo sin nodos mentiria.

**Cada turno lleva su canal** (BR6.4). Un caso empezado por voz y seguido por chat es
un solo caso con una transcripcion en orden, y lo que distingue sus turnos es ese
campo. Escribirlo mal no rompe nada hoy y rompe la lectura del caso manana.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Protocol

from untangle import observability
from untangle.case_record import api as casos
from untangle.case_record.models import CaseState, Channel, Origin, RecordType, Resolution
from untangle.chat import (
    case_number,
    case_opening,
    citation,
    demo_window,
    latency,
    opening,
    resume,
    stream,
)
from untangle.chat import session as chat
from untangle.chat.wire import EventQueue, Publisher
from untangle.compliance.redaction import api as redaccion
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration import case_context, outcome_claim, quote_reply
from untangle.orchestration.contracts import (
    CaseTurnSupport,
    FinalText,
    Handoff,
    InboundTurn,
    TurnEvent,
)
from untangle.orchestration.model_reply import (
    FallbackReason,
    agent_name_of,
    record_outcome,
    usable_reply,
)
from untangle.orchestration.nodes.intake import composition as intake_composition
from untangle.orchestration.nodes.intake import identity, understanding
from untangle.orchestration.nodes.intake import suggestions as sugerencias
from untangle.orchestration.output import ExitGate, send_rewrite_or_base
from untangle.orchestration.transcript_writer import (
    TranscriptScope,
    closing_text,
    record_agent_turn,
    record_person_turn,
)
from untangle.telemetry.traces import api as traces
from untangle.tenancy import config as tenancy_config


class TurnHandler(Protocol):
    """Lo que un canal necesita del grafo (C-14), y nada mas.

    Es la firma de `orchestration.turn.handle_turn`, escrita aqui para que esta
    unidad no tenga que importar el modulo que la implementa.
    """

    def __call__(self, turn: InboundTurn) -> AsyncIterator[TurnEvent]: ...


#: El manejador de turnos del grafo, enchufado por la raiz de composicion. Vive
#: aqui y no en el modulo de rutas por una razon que un contrato de importacion
#: dijo antes que nadie: el conductor de evaluaciones tambien entrega turnos por
#: este canal, y pedirle el puerto al modulo de rutas le arrastraba el framework
#: web entero. El puerto es del canal, no de su superficie HTTP.
#:
#: Sin enchufar, el chat no atiende: prefiere decirlo al arrancar que descubrirlo
#: con una persona escribiendo.
_MANEJADOR: TurnHandler | None = None


class TurnHandlerNotInstalledError(RuntimeError):
    """Se pidio atender un turno sin haber enchufado el grafo.

    Es un error de composicion, no de la persona que escribio: la raiz lo enchufa
    al arrancar. Falla nombrando la funcion que lo instala.
    """


def install_turn_handler(handler: TurnHandler) -> None:
    """Enchufa el grafo. Lo llama la raiz de composicion (C-24)."""
    global _MANEJADOR
    _MANEJADOR = handler


#: Quien entiende el primer mensaje (fase 0, 2026-10-07) y, desde el 2026-10-12, lo que el nucleo
#: ofrece para los mensajes con caso: entenderlos antes de entregarlos y llevar la identidad al
#: caso nuevo cuando la persona cambia de tema. Los enchufa la raiz de composicion; sin ellos
#: el primer mensaje se clasifica por reglas y el turno entiende por su cuenta, como antes.
_ENTENDEDOR: understanding.Understander | None = None
_SOPORTE_DEL_CASO: CaseTurnSupport | None = None


def install_understanding(
    understander: understanding.Understander | None,
    case_turn: CaseTurnSupport | None = None,
) -> None:
    """Enchufa la comprension del primer mensaje y el cambio de tema. Lo llama la raiz."""
    global _ENTENDEDOR, _SOPORTE_DEL_CASO
    _ENTENDEDOR, _SOPORTE_DEL_CASO = understander, case_turn


def current_turn_handler() -> TurnHandler:
    """El grafo enchufado, para quien entrega turnos por este canal.

    Lo piden las rutas y el conductor de evaluaciones. Devolverlo en vez de dejar
    que cada uno lea la variable es lo que mantiene una sola forma de enchufarlo.
    """
    if _MANEJADOR is None:
        msg = (
            "el chat no tiene grafo enchufado: la raiz de composicion llama a "
            "'chat.install_turn_handler' al arrancar"
        )
        raise TurnHandlerNotInstalledError(msg)
    return _MANEJADOR


#: La frase con que el canal cierra un turno que se rompio en la entrega. Es la
#: misma que el grafo usa para su propio fallo (`turn.ERROR_CHAT`): para quien
#: escribio, "no pude responder" es lo mismo venga de donde venga, y el catalogo no
#: necesita una segunda frase para decir lo mismo. El literal se escribe aqui, en
#: el consumidor, porque de eso depende el chequeo de claves sin consumidor (BR3.4
#: del catalogo).
DELIVERY_ERROR = CopyKey("chat.turn.error")


class ConversationNotFoundError(RuntimeError):
    """Se pidio abrir el caso de una conversacion que no esta viva.

    Es un error de composicion, no del visitante: quien entrega un turno acaba de
    resolver la conversacion de ese navegador, asi que buscarla nunca deberia
    volver vacia. Se comprueba **antes** de abrir el caso, no despues: un caso
    abierto que ninguna conversacion reclama es un caso que el turno siguiente
    vuelve a abrir, y la demostracion acaba con un caso por mensaje.
    """


@dataclass(frozen=True)
class Delivered:
    """Lo que dejo un turno entregado: cuantos eventos y si se cerro de verdad."""

    events: int
    closed: bool
    #: El identificador del turno en la transcripcion. Sin valor por omision: el
    #: canal abre el caso en el primer turno y ahi escribe el turno. La unica
    #: entrega sin turno es la de un primer mensaje que solo saluda
    #: (`is_greeting_only`, 2026-10-07; y, sin modelo, el que solo anuncia que quiere
    #: consultar algo, `has_not_said_what_for`): no abre caso, y por eso no hay donde
    #: escribirlo.
    turn_id: str | None
    #: El caso de la conversacion tras esta entrega: el que ya tenia, o el que se
    #: abrio en este turno; ninguno tras un saludo suelto, por la misma razon.
    case_id: str | None
    #: Lo que tardo la primera palabra de la respuesta desde que el servidor recibio el mensaje
    #: (`chat/latency.py`), o `None` si el turno no llego a dar ninguna --fallo, o la pestana se
    #: fue--. Es el valor de `chat.first_word`: la corrida de evaluaciones lo toma de aqui para
    #: publicar la latencia sin definirla otra vez. Tiene valor por omision porque lo pone
    #: `deliver` al terminar, no cada camino que construye la entrega.
    #:
    #: **No entra en la comparacion.** Es una medida de cuanto tardo, no parte de lo que el
    #: turno dejo: dos entregas con el mismo resultado son la misma entrega aunque una tarde
    #: 1 ms y otra 4. Sin esto, la compuerta que exige que un numero de caso ajeno responda
    #: **identico** a uno inexistente fallaba segun el reloj.
    first_word_ms: int | None = field(default=None, compare=False)


async def deliver(  # noqa: PLR0913 -- el turno, el manejador, la galleta, el origen y la superficie
    queue: EventQueue,
    entrante: InboundTurn,
    *,
    handle_turn: TurnHandler,
    visitor_key_hash: str,
    origin: Origin,
    surface: opening.Surface = opening.Surface.CHAT,
    received_monotonic: float | None = None,
) -> Delivered:
    """Entrega el turno al grafo y publica lo que vuelva (C-14 -> C-04).

    Recibe **el turno de C-14 entero** y no sus siete campos sueltos: es lo que
    quien llama ya tiene que componer de todos modos, y desarmarlo aqui solo daria
    siete sitios donde equivocarse al volver a armarlo. Y recibe el manejador por
    argumento, no por import: ver el puerto de arriba.

    `origin` **no tiene valor por omision** y por eso se pide en cada llamada. Es
    lo que decide si el caso que se abra aqui es dato de visitante --y lo borra el
    reinicio nocturno-- o no lo es (BR4.6 de U4): el chat publico abre
    `PUBLIC_CHAT` y una corrida de evaluaciones no. Un valor por omision habria
    hecho que el equivocado fuera el mas facil de escribir, y el equivocado en esta
    eleccion es el que deja casos de una corrida en la base para siempre, o el que
    borra los de una persona que estaba escribiendo.

    **Ningun fallo sale de aqui sin decirse.** Si algo se rompe, el navegador
    recibe la frase de error del catalogo --que cierra el turno-- y la traza recibe
    su evento; despues se relanza, para que quien entrega no confunda un turno
    roto con uno atendido. Antes no se hacia nada de esto: el `POST` respondia 202,
    la excepcion moria en la tarea que nadie esperaba y la pantalla se quedaba
    muda.

    **Y mide su latencia** (`chat/latency.py`): `chat.message_sent` al empezar y
    `chat.first_word` cuando sale la primera palabra de la respuesta, por la cola de siempre
    pero mirada, de modo que lo midan todos los caminos por los que un turno contesta.
    `received_monotonic` es la marca de cuando el servidor recibio el mensaje, si quien llama
    la tomo antes de admitirlo --la ruta y el conductor de la corrida de evaluaciones--; sin
    ella se mide desde aqui. Lo medido vuelve en `Delivered.first_word_ms`.
    """
    medida = latency.measured(queue, entrante, since=received_monotonic)
    try:
        entregado = await _entregar(
            medida,
            entrante,
            handle_turn=handle_turn,
            visitor_key_hash=visitor_key_hash,
            origin=origin,
            surface=surface,
        )
        return replace(entregado, first_word_ms=medida.first_word_ms)
    except Exception as error:
        observability.emit(
            "chat.delivery_failed",
            tenant_id=entrante.tenant_id,
            session_ref=entrante.session_ref,
            case_id=entrante.case_id or "",
            error_type=type(error).__name__,
        )
        # La cola puede estar llena o cerrada; que la publicacion no se logre no
        # cambia nada de lo que sigue --el fallo ya quedo en la traza-- y tragarse
        # aqui el fallo original para contar otro seria perder el que importa.
        queue.publish(
            stream.delivery_error(
                copy_key=str(DELIVERY_ERROR),
                text=copy_api.t(DELIVERY_ERROR, locale=entrante.language),
            )
        )
        raise


async def _abrir_caso_si_falta(  # noqa: PLR0913 -- el turno, la galleta, el origen, la superficie y los dos de quien lo pide (tipo y caso de partida)
    entrante: InboundTurn,
    *,
    visitor_key_hash: str,
    origin: Origin,
    surface: opening.Surface,
    intent: identity.ReportIntent | None = None,
    switching_from: str | None = None,
) -> InboundTurn:
    """BR1.1: el caso nace en el primer turno, y la conversacion lo aprende en el acto.

    Tambien nace aqui el del **cambio de tema** (2026-10-12): `switching_from` es el caso
    del que la conversacion se va, y entonces la conversacion no se ata por primera vez sino
    que pasa de uno a otro (`chat.switch_case`, con ese caso como condicion).

    **Y nace con su divulgacion registrada** (BR1.4 de U23). Aqui y no en la ruta,
    porque hasta aqui no hay caso al que atarla: la ruta marca la conversacion como
    divulgada --que es lo que impide atender un mensaje antes de la apertura-- y el
    registro de U10 es por caso. Sin esta llamada la fila nunca se escribia, y el
    dia que el ritmo de fondo se cablee, `closure` rechazaria el cierre de todo caso
    del chat por una divulgacion que si se mostro.

    La clave que queda es la de **la superficie que la mostro**: la del chat cuando
    la mostro el chat, y la del bloque de la comparacion cuando la mostro la vista.

    Se busca la conversacion **antes** de abrir el caso: si no esta viva, no hay
    donde atarlo y abrirlo seria dejar un caso huerfano que el turno siguiente
    duplica. Atarlo despues del grafo --como se hacia, leyendolo del evento-- ya no
    tiene sentido: el grafo nunca abrio ninguno, y si el turno se rompe a mitad el
    caso tiene que quedar atado igual para que el mensaje siguiente siga en el
    mismo.
    """
    if entrante.case_id is not None:
        return entrante

    viva = await chat.find_live(tenant_id=entrante.tenant_id, visitor_key_digest=visitor_key_hash)
    if viva is None:
        msg = (
            "no hay conversacion viva para la sesion "
            f"'{entrante.session_ref}', y no se abre un caso que ninguna "
            "conversacion pueda reclamar"
        )
        raise ConversationNotFoundError(msg)
    if switching_from is not None and viva.case_id != switching_from:
        # Otro mensaje en vuelo ya movio la conversacion. Se dice antes de abrir nada: el enlace
        # del caso nuevo solo puede apuntar al caso **de esta conversacion**, y abrirlo para que
        # `switch_case` lo rechazara despues dejaria un caso suelto con su enlace.
        msg = f"la conversacion '{viva.chat_session_id}' ya no esta en el caso del que se parte"
        raise chat.ConversationMovedError(msg)

    case_id = await case_opening.open_for_first_turn(
        entrante.tenant_id,
        text=entrante.text,
        language=entrante.language,
        origin=origin,
        now=entrante.received_at,
        intent=intent,
        # El caso nuevo nace diciendo de cual viene, para que la conversacion se lea a traves
        # de los dos (2026-10-13). `switching_from` es el caso de **esta** conversacion.
        continues_case_id=switching_from,
    )
    if switching_from is None:
        await chat.attach_case(viva, case_id=case_id)
    else:
        await chat.switch_case(viva, case_id=case_id, from_case_id=switching_from)
    await opening.record(
        tenant_id=entrante.tenant_id,
        case_id=case_id,
        language=entrante.language,
        catalog_key=opening.disclosure_key_of(surface),
        now=entrante.received_at,
    )
    observability.emit(
        "chat.case_opened",
        tenant_id=entrante.tenant_id,
        session_ref=entrante.session_ref,
        case_id=case_id,
        origin=origin.value,
    )
    return replace(entrante, case_id=case_id)


async def _entender_el_primero(entrante: InboundTurn) -> understanding.UnderstandingResponse | None:
    """Un mensaje sin caso todavia, entendido: que quiere la persona.

    La historia que ve el modelo es la apertura y lo que se haya hablado antes de abrir caso
    (`_HISTORIA_SIN_CASO`): sin lo segundo, quien decia «tengo una duda de mi poliza» y
    despues su nombre recibia «¿quieres reportar un siniestro o tienes una duda?»."""
    config = tenancy_config.require(entrante.tenant_id)
    return await understanding.understand(
        _ENTENDEDOR,
        understanding.UnderstandingRequest(
            tenant_id=entrante.tenant_id,
            language=entrante.language,
            today=entrante.received_at.date(),
            record_type=None,
            quote_enabled=config.quote_enabled,
            noted=(),
            missing=(),
            person_text=entrante.text,
            channel="chat",
            history=(
                understanding.HistoryLine(
                    speaker="agent",
                    text=opening.compose(config, language=entrante.language).text,
                ),
                *_HISTORIA_SIN_CASO.get(entrante.session_ref, ()),
            ),
        ),
    )


#: Lo que se hablo antes de que hubiera caso (2026-10-13): un saludo, una duda general, «tengo
#: una pregunta de mi poliza». Sin caso no hay transcripcion donde guardarlo, y sin guardarlo la
#: agente contestaba cada mensaje como si fuera el primero. **Solo en memoria del proceso y por
#: sesion**, igual que `_DATOS_SIN_CASO` y con su mismo tope: lo de la persona entra ya tapado,
#: y si se pierde (otro proceso, reinicio) la agente vuelve a preguntar, como antes.
_HISTORIA_SIN_CASO: dict[str, tuple[understanding.HistoryLine, ...]] = {}
_MAXIMO_LINEAS_SIN_CASO = 8


def _recordar_sin_caso(entrante: InboundTurn, dicho_por_la_agente: str) -> None:
    """Anota el intercambio de un mensaje que no abrio caso."""
    if (
        entrante.session_ref not in _HISTORIA_SIN_CASO
        and len(_HISTORIA_SIN_CASO) >= _MAXIMO_SESIONES_SIN_CASO
    ):
        _HISTORIA_SIN_CASO.pop(next(iter(_HISTORIA_SIN_CASO)))
    previas = _HISTORIA_SIN_CASO.get(entrante.session_ref, ())
    nuevas = (
        understanding.HistoryLine(
            speaker="person", text=str(redaccion.redact(entrante.text, language=entrante.language))
        ),
        understanding.HistoryLine(speaker="agent", text=dicho_por_la_agente),
    )
    _HISTORIA_SIN_CASO[entrante.session_ref] = (*previas, *nuevas)[-_MAXIMO_LINEAS_SIN_CASO:]


def _frase_sin_caso(
    entrante: InboundTurn, entendido: understanding.UnderstandingResponse | None
) -> opening.Opening:
    """Que se contesta cuando el mensaje todavia no abre un caso.

    Un saludo, el saludo corto con las opciones; pedir cotizar donde no se cotiza, la
    frase de AC6.1.3, que ya ofrece lo demas; una duda general o algo que no es
    ninguna de las opciones, las opciones en una pregunta. Las tres son del catalogo.
    """
    config = tenancy_config.require(entrante.tenant_id)
    if entendido is None or entendido.wants is understanding.Want.GREETING:
        return opening.greeting_reply(config, language=entrante.language)
    if entendido.wants is understanding.Want.QUOTE:
        frase = quote_reply.compose_unavailable(language=entrante.language)
        return opening.Opening(copy_key=CopyKey(frase.key), text=frase.text)
    return opening.options(config, language=entrante.language)


def _lo_que_dice_el_modelo_sin_caso(
    entrante: InboundTurn,
    entendido: understanding.UnderstandingResponse | None,
    base: str,
) -> tuple[str | None, FallbackReason | None]:
    """Lo que el modelo contesta a un mensaje que no abre caso, o por que sale la frase base.

    Sin modelo, o una respuesta que no vale (`usable_reply`): la frase del catalogo. Sin caso
    no hay datos que el codigo pudiera rechazar ni hitos: la guardia de salida es lo que falta
    pasar, y la pasa `send_rewrite_or_base`. Tampoco hay reporte, asi que una respuesta que diga
    que quedo hecho o que lo revisa un ajustador (`outcome_claim`) es falsa de raiz.
    """
    if entendido is None:
        return None, FallbackReason.NO_MODEL
    reply = usable_reply(
        entendido.reply,
        base=base,
        agent_name=agent_name_of(entrante.tenant_id, entrante.language),
    )
    if reply is None:
        return None, FallbackReason.INVALID_REPLY
    if outcome_claim.claims_outcome(reply):
        return None, FallbackReason.REPORT_NOT_DONE
    return reply, None


async def _responder_sin_caso(
    queue: Publisher,
    entrante: InboundTurn,
    entendido: understanding.UnderstandingResponse | None,
) -> Delivered:
    """Un primer mensaje que todavia no abre caso: se contesta y se guia, sin abrir nada.

    Decision de Miguel del 2026-10-07: antes un "hola" o "¿que es un deducible?"
    abrian un reporte de accidente y la agente preguntaba si habia heridos. Desde el
    2026-10-12 contesta el modelo --un saludo, una duda general, lo que no es ninguna de
    las opciones--, con la misma llamada que entendio el mensaje. Lo que dice pasa la
    comprobacion de `usable_reply` y la guardia de salida, y si algo falla sale la frase del
    catalogo.
    """
    frase = _frase_sin_caso(entrante, entendido)
    del_modelo, motivo = _lo_que_dice_el_modelo_sin_caso(entrante, entendido, frase.text)
    texto, del_catalogo = await send_rewrite_or_base(
        ExitGate(tenant_id=entrante.tenant_id, language=entrante.language), del_modelo, frase.text
    )
    if del_modelo is not None and del_catalogo:
        motivo = FallbackReason.GUARD
    record_outcome(entrante.tenant_id, "chat", motivo)
    config = tenancy_config.require(entrante.tenant_id)
    evento = FinalText(
        message_id=uuid.uuid4().hex,
        text=texto,
        language=entrante.language,
        from_catalog=del_catalogo,
        # Sin caso, los botones son lo que la agente sabe hacer: escribir nunca es
        # obligatorio (fase 0, 2026-10-07).
        suggestions=sugerencias.options(
            language=entrante.language, quote_enabled=config.quote_enabled
        ),
    )
    publicado = queue.publish(stream.to_wire(evento))
    _recordar_sin_caso(entrante, texto)
    observability.emit(
        "chat.answered_without_case",
        tenant_id=entrante.tenant_id,
        session_ref=entrante.session_ref,
        wants=entendido.wants.value if entendido is not None else "greeting_by_rule",
    )
    return Delivered(events=int(publicado), closed=publicado, turn_id=None, case_id=None)


def _de_la_comparacion(
    entrante: InboundTurn,
) -> tuple[InboundTurn, identity.ReportIntent | None]:
    """La vista de comparacion solo admite preguntas de cobertura --la ruta ya lo
    comprobo--, asi que se entienden como tales sin modelo: abren o siguen una
    consulta, y la respuesta llega con su resultado explicito."""
    entendido = understanding.UnderstandingResponse(
        wants=understanding.Want.POLICY_QUESTION,
        asks_about_coverage=True,
        person_question=entrante.text,
    )
    intencion = identity.ReportIntent.COVERAGE_INQUIRY if entrante.case_id is None else None
    return replace(entrante, understood=entendido), intencion


async def _primer_mensaje(
    queue: Publisher, entrante: InboundTurn
) -> Delivered | tuple[InboundTurn, identity.ReportIntent | None]:
    """El primer mensaje: o se contesta sin caso, o dice que caso abrir.

    Fase 0 (2026-10-07): que quiere la persona se entiende por el sentido. Sin
    modelo, o si falla o tarda, por reglas como antes. Lo entendido viaja con el
    turno para no volver a entenderlo.
    """
    entendido = await _entender_el_primero(entrante)
    if entendido is None:
        # Sin el modelo, un saludo o un «queria consultar algo» tampoco abren un reporte: el
        # modelo los lee como `greeting` y el respaldo por reglas dice lo mismo (2026-10-13).
        if case_opening.has_not_said_what_for(entrante.text, language=entrante.language):
            return await _responder_sin_caso(queue, entrante, None)
        # Si habia modelo y no pudo, el turno no lo vuelve a llamar: duplicaria la espera.
        return replace(entrante, understood_by_channel=_ENTENDEDOR is not None), None
    tipo = understanding.opening_record_type(
        entendido,
        quote_enabled=tenancy_config.require(entrante.tenant_id).quote_enabled,
    )
    previos = _DATOS_SIN_CASO.pop(entrante.session_ref, ())
    if tipo is not None:
        _HISTORIA_SIN_CASO.pop(entrante.session_ref, None)
    if tipo is None and entendido.items and previos:
        # Segunda vez que da datos sin elegir: no responde la pregunta, sigue
        # contando. Es un reporte, que es lo que hacia la regla antes de la fase 0.
        tipo = RecordType.CLAIM
    if tipo is None:
        if entendido.items:
            _guardar_datos_sin_caso(entrante.session_ref, entendido.items)
        return await _responder_sin_caso(queue, entrante, entendido)
    return replace(
        entrante,
        understood=_con_lo_dicho_antes(entendido, previos),
        understood_by_channel=True,
        # La respuesta se escribio sin caso, sin saber que datos faltan: el turno que lo
        # abre dice la frase del catalogo.
        understood_without_case=True,
    ), case_opening.intent_for(tipo)


#: Lo que la persona dijo antes de elegir que quiere (2026-10-09). "Soy Marcela Rios,
#: mi poliza es POL-21" como primer mensaje no abria caso, y al elegir "reportar"
#: la agente volvia a pedir nombre y poliza: la corrida de evaluaciones lo mostro como
#: quince vueltas de la misma pregunta. **Solo en memoria del proceso y por sesion**,
#: nunca en la base --sin caso no hay donde redactarlo antes de persistir-- y acotado:
#: si se pierde (otro proceso, reinicio), la agente vuelve a pedirlo, como antes.
_DATOS_SIN_CASO: dict[str, tuple[understanding.UnderstoodItem, ...]] = {}
_MAXIMO_SESIONES_SIN_CASO = 512


def _guardar_datos_sin_caso(
    session_ref: str, items: tuple[understanding.UnderstoodItem, ...]
) -> None:
    if len(_DATOS_SIN_CASO) >= _MAXIMO_SESIONES_SIN_CASO:
        _DATOS_SIN_CASO.pop(next(iter(_DATOS_SIN_CASO)))
    _DATOS_SIN_CASO[session_ref] = items


def _con_lo_dicho_antes(
    entendido: understanding.UnderstandingResponse,
    previos: tuple[understanding.UnderstoodItem, ...],
) -> understanding.UnderstandingResponse:
    """Lo entendido en este mensaje, mas lo que dijo antes y no repite ahora."""
    ahora = {item.field_key for item in entendido.items}
    faltan = tuple(item for item in previos if item.field_key not in ahora)
    if not faltan:
        return entendido
    return entendido.model_copy(update={"items": (*entendido.items, *faltan)})


CLOSED_CASE = CopyKey("chat.closed_case.already_decided")


async def _si_ya_esta_decidido(
    queue: Publisher, entrante: InboundTurn, case_id: str
) -> Delivered | None:
    """Un caso ya decidido no se sigue capturando: se dice que tiene decision y donde
    verla, y como empezar otra cosa (B3, fase 1, 2026-10-08). Antes un reporte decia
    que seguia con el ajustador y una consulta o una cotizacion daban error."""
    vista = await casos.get_case(entrante.tenant_id, case_id)
    if vista is None or vista.state is not CaseState.CLOSED:
        return None
    # Con el caso y su numero: sin ellos la guardia toma el numero del propio caso
    # por un identificador ajeno y tapa la frase entera.
    numero = str(vista.case_number)
    # Un caso que las reglas cerraron solo (US1.17) no tiene "decision": quedo registrado, y asi
    # se dice. Uno que decidio un ajustador conserva la frase de siempre.
    if vista.resolution is Resolution.REGISTERED:
        _, base = intake_composition.compose_fast_closing(
            intake_composition.FastClosing.ALREADY,
            case_number=numero,
            language=entrante.language,
            phase=intake_composition.ClosingPhase.REGISTERED,
        )
    else:
        base = copy_api.t(CLOSED_CASE, locale=entrante.language, case_number=numero)
    texto, _ = await ExitGate(
        tenant_id=entrante.tenant_id,
        language=entrante.language,
        case_id=case_id,
        case_number=numero,
    ).send(base)
    publicado = queue.publish(
        stream.to_wire(
            FinalText(
                message_id=uuid.uuid4().hex,
                text=texto,
                language=entrante.language,
                case_id=case_id,
                from_catalog=True,
            )
        )
    )
    observability.emit(
        "chat.message_on_decided_case", tenant_id=entrante.tenant_id, case_id=case_id
    )
    return Delivered(events=int(publicado), closed=publicado, turn_id=None, case_id=case_id)


async def _con_el_tema_que_toca(
    entrante: InboundTurn,
    *,
    visitor_key_hash: str,
    origin: Origin,
    surface: opening.Surface,
) -> InboundTurn:
    """Un mensaje con caso, entendido antes de entregarlo para saber si cambio de tema (2026-10-12).

    Hasta ahora una conversacion quedaba atada al tipo de caso con que empezo: quien consultaba
    su poliza y decia «quiero reportar eso como un accidente» recibia «¿que quieres saber de tu
    poliza?» (C4, Miguel). Si la persona pide otra de las tres cosas que abren caso y su tipo
    no es el del caso, aqui se abre el caso nuevo, se ata a la conversacion, se le lleva la
    identidad y la poliza ya dadas, y el turno sigue en el con lo ya entendido. El caso anterior
    queda como estaba.

    La decision es del codigo sobre un valor cerrado del modelo (`understanding.
    switch_record_type`), y el modelo no se vuelve a llamar en el turno: lo entendido viaja en
    `InboundTurn.understood`, tambien cuando el modelo no pudo (entonces el turno sigue por
    reglas). **Un caso nuevo es un caso nuevo**: con la demostracion estrechada no se abre
    (BR3.2 de U20), y la persona sigue en el que tiene.
    """
    soporte, caso = _SOPORTE_DEL_CASO, entrante.case_id
    if soporte is None or caso is None:
        return entrante
    entendido = await soporte.understand(entrante)
    entrante = replace(entrante, understood=entendido, understood_by_channel=True)
    if entendido is None:
        return entrante
    vista = await casos.get_case(entrante.tenant_id, caso)
    if vista is None:
        return entrante
    tipo = understanding.switch_record_type(
        entendido,
        current=vista.record_type,
        quote_enabled=tenancy_config.require(entrante.tenant_id).quote_enabled,
    )
    if tipo is None:
        return entrante
    if not await demo_window.current_new_case_gate()():
        observability.emit(
            "chat.topic_change_refused",
            tenant_id=entrante.tenant_id,
            session_ref=entrante.session_ref,
            reason="demo_window_closed",
        )
        return entrante
    cambiado = await _abrir_caso_si_falta(
        replace(entrante, case_id=None),
        visitor_key_hash=visitor_key_hash,
        origin=origin,
        surface=surface,
        intent=case_opening.intent_for(tipo),
        switching_from=caso,
    )
    nuevo = cambiado.case_id
    assert nuevo is not None  # noqa: S101 -- lo acaba de garantizar `_abrir_caso_si_falta`
    # El modelo escribio su respuesta mirando el caso anterior --su estado, lo que le faltaba--
    # y en el nuevo no vale: en la conversacion de Miguel del 2026-10-12 dijo «como el caso ya
    # esta con el ajustador...» al abrir un reporte que acababa de nacer. El turno que abre el
    # caso nuevo dice la frase del catalogo, igual que el primer mensaje.
    cambiado = replace(cambiado, understood_without_case=True)
    await soporte.carry_over(tenant_id=entrante.tenant_id, from_case_id=caso, to_case_id=nuevo)
    observability.emit(
        "chat.topic_changed",
        tenant_id=entrante.tenant_id,
        session_ref=entrante.session_ref,
        case_id=nuevo,
        from_type=vista.record_type.value,
        to_type=tipo.value,
    )
    return cambiado


async def _decir_sin_turno(
    queue: Publisher, entrante: InboundTurn, texto: str, *, case_id: str | None, sugerir: bool
) -> bool:
    """Publica una frase del catalogo ya pasada por la guardia. Devuelve si se publico."""
    config = tenancy_config.require(entrante.tenant_id)
    sugerencias_de_inicio = (
        sugerencias.options(language=entrante.language, quote_enabled=config.quote_enabled)
        if sugerir
        else ()
    )
    return queue.publish(
        stream.to_wire(
            FinalText(
                message_id=uuid.uuid4().hex,
                text=texto,
                language=entrante.language,
                case_id=case_id,
                from_catalog=True,
                suggestions=sugerencias_de_inicio,
            )
        )
    )


async def _no_se_retoma(queue: Publisher, entrante: InboundTurn) -> Delivered:
    """La **unica** respuesta cuando un numero de caso no se retoma (AC1.20.2, AC1.20.3).

    No hay una rama por motivo: el numero que no existe, el de otro navegador, el de otra
    aseguradora y el de una voz que esta aseguradora no deja seguir por chat llegan todos aqui, y
    lo que cambia es la configuracion de la aseguradora y nada que dependa del numero. La frase no
    lleva el numero, no abre ningun caso, no escribe ningun turno y no toca la conversacion.
    """
    config = tenancy_config.require(entrante.tenant_id)
    base = case_number.not_resumed(
        continuity_enabled=config.voice_to_chat_continuity, language=entrante.language
    )
    texto, _ = await ExitGate(tenant_id=entrante.tenant_id, language=entrante.language).send(base)
    publicado = await _decir_sin_turno(
        queue, entrante, texto, case_id=None, sugerir=entrante.case_id is None
    )
    observability.emit(
        "chat.case_number_not_resumed",
        tenant_id=entrante.tenant_id,
        session_ref=entrante.session_ref,
    )
    return Delivered(
        events=int(publicado), closed=publicado, turn_id=None, case_id=entrante.case_id
    )


async def _atar_al_caso_retomado(
    entrante: InboundTurn, *, visitor_key_hash: str, case_id: str
) -> None:
    """Ata la conversacion al caso retomado, tenga o no ya un caso (AC1.20.4)."""
    viva = await chat.find_live(tenant_id=entrante.tenant_id, visitor_key_digest=visitor_key_hash)
    if viva is None:
        msg = (
            "no hay conversacion viva para la sesion "
            f"'{entrante.session_ref}', y no se ata un caso a una que no existe"
        )
        raise ConversationNotFoundError(msg)
    if viva.case_id is None:
        await chat.attach_case(viva, case_id=case_id)
    elif viva.case_id != case_id:
        await chat.switch_case(viva, case_id=case_id, from_case_id=viva.case_id)


async def _si_escribe_un_numero_de_caso(
    queue: Publisher, entrante: InboundTurn, *, visitor_key_hash: str
) -> Delivered | None:
    """Escribir el numero de un caso es retomarlo, y lo decide el codigo (US1.19, US1.20).

    Va **antes de entregarle el mensaje a nadie** --ni el modelo que entiende, ni el grafo--,
    igual que los demas controles baratos, y vale tanto si la conversacion no tiene caso como si
    ya tiene uno. Si el mensaje no trae un numero con el prefijo de alguna aseguradora, no hace
    nada y devuelve `None`.

    Lo que lo ata no es lo que diga la persona sino `chat.resume`: el numero tiene que ser de
    **este navegador** y de **esta aseguradora**, y cualquier otro caso recibe la misma respuesta
    que un numero inventado. Los casos que el navegador abrio por llamada cuentan solo si la
    aseguradora lo tiene encendido. El caso retomado es **el mismo caso**: sus turnos de voz y los
    de chat quedan en una transcripcion, cada uno con su canal.
    """
    numero = case_number.find(entrante.text)
    if numero is None:
        return None
    config = tenancy_config.require(entrante.tenant_id)
    retomado = await resume.by_case_number(
        tenant_id=entrante.tenant_id,
        case_number=numero,
        visitor_key_digest=visitor_key_hash,
        from_calls=config.voice_to_chat_continuity,
    )
    vista = None if retomado is None else await casos.get_case(entrante.tenant_id, retomado.case_id)
    if retomado is None or vista is None:
        return await _no_se_retoma(queue, entrante)

    # Desde aqui el caso es suyo. Uno decidido o en manos de un ajustador no se ata: se le dice
    # donde esta, y la conversacion sigue en el caso que tenia.
    if vista.state not in case_number.CONTINUABLE:
        if vista.state is CaseState.CLOSED:
            cerrado = await _si_ya_esta_decidido(queue, entrante, vista.case_id)
            if cerrado is not None:
                return cerrado
        texto, _ = await ExitGate(
            tenant_id=entrante.tenant_id,
            language=entrante.language,
            case_id=vista.case_id,
            case_number=str(vista.case_number),
        ).send(case_number.not_in_capture(vista, language=entrante.language))
        publicado = await _decir_sin_turno(
            queue, entrante, texto, case_id=entrante.case_id, sugerir=False
        )
        return Delivered(
            events=int(publicado), closed=publicado, turn_id=None, case_id=entrante.case_id
        )

    await _atar_al_caso_retomado(entrante, visitor_key_hash=visitor_key_hash, case_id=vista.case_id)
    # La divulgacion del chat tambien se dio en esta conversacion, y el registro es por canal:
    # el caso que nacio en la llamada ya tiene la de la voz.
    await opening.record(
        tenant_id=entrante.tenant_id,
        case_id=vista.case_id,
        language=entrante.language,
        catalog_key=opening.disclosure_key_of(opening.Surface.CHAT),
        now=entrante.received_at,
    )
    ambito = TranscriptScope(
        tenant_id=entrante.tenant_id,
        case_id=vista.case_id,
        channel=Channel.CHAT,
        language=entrante.language,
    )
    turn_id = await record_person_turn(ambito, text=entrante.text, now=entrante.received_at)
    texto, _ = await ExitGate(
        tenant_id=entrante.tenant_id,
        language=entrante.language,
        case_id=vista.case_id,
        case_number=str(vista.case_number),
    ).send(case_number.continued(vista, language=entrante.language))
    publicado = await _decir_sin_turno(queue, entrante, texto, case_id=vista.case_id, sugerir=False)
    await record_agent_turn(ambito, text=texto, now=datetime.now(UTC), from_catalog=True)
    observability.emit(
        "chat.case_resumed",
        tenant_id=entrante.tenant_id,
        session_ref=entrante.session_ref,
        case_id=vista.case_id,
        by="case_number",
        # El canal en el que empezo: dice a la traza cuantas retomas cruzan de la voz al chat.
        started_in=vista.channel.value,
    )
    return Delivered(
        events=int(publicado), closed=publicado, turn_id=turn_id, case_id=vista.case_id
    )


async def _con_su_caso(
    queue: Publisher,
    entrante: InboundTurn,
    *,
    visitor_key_hash: str,
    origin: Origin,
    surface: opening.Surface,
) -> Delivered | InboundTurn:
    """El turno con su caso abierto, o lo que ya se contesto sin abrir ninguno."""
    if surface is opening.Surface.CHAT:
        retomado = await _si_escribe_un_numero_de_caso(
            queue, entrante, visitor_key_hash=visitor_key_hash
        )
        if retomado is not None:
            return retomado
    intencion: identity.ReportIntent | None = None
    if surface is opening.Surface.COMPARISON:
        entrante, intencion = _de_la_comparacion(entrante)
    elif entrante.case_id is None:
        decidido = await _primer_mensaje(queue, entrante)
        if isinstance(decidido, Delivered):
            return decidido
        entrante, intencion = decidido
    nuevo = entrante.case_id is None
    entrante = await _abrir_caso_si_falta(
        entrante,
        visitor_key_hash=visitor_key_hash,
        origin=origin,
        surface=surface,
        intent=intencion,
    )
    caso = entrante.case_id
    assert caso is not None  # noqa: S101 -- lo acaba de garantizar `_abrir_caso_si_falta`
    if nuevo and surface is opening.Surface.COMPARISON:
        # La columna compara la poliza de ejemplo de esa aseguradora, la que nombra
        # su divulgacion: no se le pide a nadie (A8, fase 1, 2026-10-08).
        await casos.set_policy_ref(
            entrante.tenant_id, caso, tenancy_config.require(entrante.tenant_id).example_policy
        )
    cerrado = await _si_ya_esta_decidido(queue, entrante, caso)
    if cerrado is not None:
        return cerrado
    if surface is opening.Surface.CHAT and not nuevo:
        entrante = await _con_el_tema_que_toca(
            entrante, visitor_key_hash=visitor_key_hash, origin=origin, surface=surface
        )
    return entrante


async def _resumir_la_traza(
    trace_id: str, *, tenant_id: str, case_id: str, visitor_key_hash: str, turn_id: str
) -> None:
    """Abre el resumen de la traza del turno y lo cierra con sus tramos (2026-10-15)."""
    await traces.open_summary(
        trace_id=trace_id,
        tenant_id=tenant_id,
        case_id=case_id,
        visitor_key_hash=visitor_key_hash,
        turn_ref=turn_id,
    )
    try:
        await traces.settle_summary(trace_id, tenant_id=tenant_id)
    except Exception as error:  # noqa: BLE001 -- el resumen es diagnostico: su fallo no tumba un turno que ya se entrego
        observability.emit(
            "traces.summary_settle_failed", trace_id=trace_id, error=type(error).__name__
        )


async def _entregar(  # noqa: PLR0913 -- los mismos cinco que `deliver`; el primer mensaje ya va en `_primer_mensaje`
    queue: Publisher,
    entrante: InboundTurn,
    *,
    handle_turn: TurnHandler,
    visitor_key_hash: str,
    origin: Origin,
    surface: opening.Surface,
) -> Delivered:
    """La entrega en si. La envoltura de `deliver` es la que garantiza que se diga."""
    preparado = await _con_su_caso(
        queue, entrante, visitor_key_hash=visitor_key_hash, origin=origin, surface=surface
    )
    if isinstance(preparado, Delivered):
        return preparado
    entrante = preparado
    caso = entrante.case_id
    assert caso is not None  # noqa: S101 -- lo acaba de garantizar `_con_su_caso`

    ambito = TranscriptScope(
        tenant_id=entrante.tenant_id,
        case_id=caso,
        channel=Channel.CHAT,
        language=entrante.language,
    )
    turn_id = await record_person_turn(ambito, text=entrante.text, now=entrante.received_at)

    publicados = 0
    cerro = False
    trace_id: str | None = None
    async for evento in handle_turn(entrante):
        # El identificador de traza se lee **dentro** del ciclo: el generador de
        # C-14 sigue suspendido dentro de su propio tramo mientras entrega, asi que
        # el contexto esta vivo aqui y no despues de agotarlo.
        if trace_id is None:
            trace_id = traces.current_trace_id()
        if isinstance(evento, FinalText):
            detalles = await citation.details_for(
                entrante.tenant_id, evento.citations, language=entrante.language
            )
            cable = stream.to_wire(evento, citations=detalles, trace_ref=trace_id or "")
        else:
            cable = stream.to_wire(evento)
        if not queue.publish(cable):
            # La pestana se fue. No es un error del turno: el trabajo de fondo
            # sigue su curso y el caso queda igual; lo que se acabo es a quien
            # entregarselo.
            observability.emit(
                "chat.delivery_abandoned",
                session_ref=entrante.session_ref,
                delivered=publicados,
            )
            break
        publicados += 1
        if stream.closes_turn(cable):
            cerro = True
            dicho = closing_text(evento)
            if dicho is not None:
                # **Su instante es el de ahora y no el de la llegada del mensaje**, y
                # no es un detalle: la transcripcion se lee por `started_at` y los
                # dos turnos con el mismo instante quedarian en orden arbitrario. La
                # revision de cumplimiento busca "el turno de la agente **siguiente**
                # a la peticion de persona", asi que el orden es la regla.
                turno_de_la_agente = await record_agent_turn(
                    ambito,
                    text=dicho.text,
                    now=datetime.now(UTC),
                    from_catalog=dicho.from_catalog,
                )
                if isinstance(evento, Handoff):
                    # **Y aqui, con el turno ya escrito, se deriva el caso.** En
                    # este orden y no al reves: un caso derivado cuyo turno no
                    # estuviera en la transcripcion haria fallar la revision, que
                    # exige acotarse a un turno que exista. Al reves el fallo es
                    # benigno: el caso se queda en captura, que es lo que pasaba
                    # antes de esta tanda.
                    await case_context.derive_case(
                        tenant_id=entrante.tenant_id,
                        case_id=caso,
                        reason=evento.reason_code,
                        turn_id=turno_de_la_agente,
                        now=entrante.received_at,
                    )

    if trace_id is not None:
        await _resumir_la_traza(
            trace_id,
            tenant_id=entrante.tenant_id,
            case_id=caso,
            visitor_key_hash=visitor_key_hash,
            turn_id=turn_id,
        )

    return Delivered(events=publicados, closed=cerro, turn_id=turn_id, case_id=caso)


__all__ = [
    "DELIVERY_ERROR",
    "ConversationNotFoundError",
    "Delivered",
    "TurnHandler",
    "TurnHandlerNotInstalledError",
    "current_turn_handler",
    "deliver",
    "install_turn_handler",
    "install_understanding",
]
