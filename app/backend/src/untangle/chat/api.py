"""Las rutas del chat publico y su superficie (C-04, C-23, C-24).

**El mensaje y la respuesta van por rutas distintas**, porque el navegador manda por una y escucha por otra: el
mensaje entra por `POST` y se responde con `202` en cuanto se admite, y lo que la
agente dice sale por el flujo que la pestana ya tiene abierto. Responder en el cuerpo
del `POST` obligaria a esperar el turno entero con la conexion colgada, que es lo
contrario de lo que BR2.2 pide.

**La identidad es la cookie del navegador.** `EventSource` no manda cabeceras (C-04),
asi que no hay otra via, y tampoco hace falta: lo que ata una conversacion a alguien
es su clave de navegador, que U2 emite y de la que solo se guarda el resumen.

**Las respuestas de error no se documentan con el vocabulario de C-01**, y no por
descuido: ese vocabulario vive en `untangle.server`, que esta **por encima** de las
unidades en el contrato de capas, asi que esta unidad no puede importarlo. Es el mismo
problema que U6 ya resolvio para las superficies poniendo `surface_spec` en la raiz
del paquete; el vocabulario de problemas tiene la misma necesidad y hoy no vive ahi.
Queda anotado para su duena, U6: moverlo es su decision, no de esta unidad.

**Este es el primer modulo que se monta por C-24.** El contrato lo construyo U6 y
hasta ahora nadie lo habia estrenado: `router()` sin argumentos y `surfaces()` con su
sonda obligatoria. La sonda **no llama al modelo, no gasta y no consume el limite de
ningun visitante** (BR5.2): pregunta a la base si la tabla de conversaciones responde,
que es lo unico que distingue "el chat esta en pie" de "el chat esta caido".
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

import orjson
from fastapi import APIRouter, Cookie, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import Field

from untangle import language, observability
from untangle.base import Frozen, Locale
from untangle.case_record import crypto
from untangle.case_record.models import Origin
from untangle.chat import (
    case_status,
    citation,
    delivery,
    demo_window,
    history,
    opening,
    reasoning,
    stream,
    trace,
)
from untangle.chat import session as chat
from untangle.chat.delivery import (
    TurnHandlerNotInstalledError,
    current_turn_handler,
    install_turn_handler,
    install_understanding,
)
from untangle.chat.demo_window import (
    NewCaseGate,
    NewCaseGateNotInstalledError,
    install_new_case_gate,
)
from untangle.chat.limits import LIMIT_COPY_KEYS, LimitKind
from untangle.chat.wire import HEARTBEAT_SECONDS, EventQueue, QueueRegistry
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration import coverage_detour
from untangle.orchestration.contracts import FinalText, InboundTurn
from untangle.orchestration.nodes.intake import suggestions as sugerencias
from untangle.surface_spec import SurfaceId, SurfaceProbe, SurfaceSpec
from untangle.tenancy import api as tenancy
from untangle.tenancy import session as db
from untangle.tenancy.models import TenantConfig, TenantId

#: La cookie con la clave del navegador. `SameSite=Lax` y `HttpOnly`: nada del
#: lado del navegador necesita leerla, y lo que no se puede leer no se puede
#: robar con un script inyectado en la pagina.
COOKIE = "untangle_visitor"

#: Las colas vivas del proceso. Una por conversacion (ver `wire.py`).
_COLAS = QueueRegistry()


def _flujo_de(tenant_id: str, key_hash: str) -> str:
    """La referencia de la cola: **este navegador con esta aseguradora**.

    Era solo el navegador, y con dos aseguradoras abiertas a la vez --dos pestanas, o
    las tres columnas de la comparacion-- el segundo flujo cerraba el primero y las
    respuestas de una aseguradora salian por el flujo de otra (2026-10-10): en la
    comparacion, la respuesta de una columna aparecia bajo el nombre de otra y las
    demas decian "no se pudo revisar".
    """
    return f"{tenant_id}:{key_hash}"


#: La clave con la que se firma el enlace al caso que la pantalla muestra
#: (decision de Miguel, 2026-10-06). La enchufa la raiz de composicion, como las
#: de la bandeja: esta unidad no lee los ajustes del proceso. `None` es un
#: despliegue sin enlaces de caso, y entonces el estado del caso sale sin enlace.
_CLAVE_DE_ENLACE: str | None = None


def install_case_link_key(key: str | None) -> None:
    """La raiz de composicion enchufa la clave del enlace de caso."""
    global _CLAVE_DE_ENLACE
    _CLAVE_DE_ENLACE = key


#: Las entregas en curso. Se guardan solo para que el recolector de basura no se
#: lleve una tarea a medias: sin esta referencia, una entrega larga puede
#: desaparecer sin haber publicado su evento final.
_ENTREGAS: set[asyncio.Task[Any]] = set()


def _entrega_terminada(tarea: asyncio.Task[Any]) -> None:
    """Suelta la tarea y **recoge su excepcion si la hubo**.

    Lo segundo es la mitad que faltaba, y es la que convirtio un defecto en un
    misterio: una tarea que muere sin que nadie llame a su `exception()` deja
    `asyncio` escribiendo "Task exception was never retrieved" en la salida del
    proceso --si alguien la esta mirando-- y nada en la traza. Asi estuvo el chat
    desde que se construyo: el `POST` respondia 202, el turno reventaba y no habia
    ni un evento que lo dijera.

    `deliver` ya publica su frase de error y emite su propio evento con el contexto
    del turno; este es el respaldo para lo que se rompa fuera de ese alcance, y el
    unico sitio que garantiza que **ninguna** entrega muera en silencio.
    """
    _ENTREGAS.discard(tarea)
    if tarea.cancelled():
        return
    error = tarea.exception()
    if error is not None:
        observability.emit(
            "chat.delivery_task_failed",
            error_type=type(error).__name__,
        )


#: Lo que la sonda de la superficie tiene de plazo. Es una consulta que no toca
#: ninguna fila; con doscientos milisegundos, una base que responde nunca falla y
#: una caida no retiene la salud.
PROBE_TIMEOUT_MS = 200


class MessageIn(Frozen):
    """Lo que el navegador manda. El texto entra como dato, nunca como instruccion.

    Los dos campos de U23 son **aditivos y con valor por omision**, asi que el chat
    sigue mandando lo que mandaba (FD-U23-1: ninguna ruta nueva).
    """

    text: str = Field(min_length=1)
    #: De que pantalla viene (FD-U23-8). Decide que apertura se publica y con que
    #: clave queda registrada la divulgacion.
    surface: opening.Surface = opening.Surface.CHAT
    #: El idioma de la pantalla desde la que se pregunta, como **respaldo** cuando
    #: el texto no trae senal suficiente.
    #:
    #: Hace falta para BR2.1 de U23: el respaldo de siempre es el idioma de la
    #: conversacion, y las tres aseguradoras tienen idioma por omision distinto
    #: --`en`, `es`, `en`--, asi que la misma pregunta sin senal volveria contestada
    #: en dos idiomas y la comparacion compararia tambien el idioma. Quien decide
    #: sigue siendo el detector determinista; esto solo cambia con que empata.
    locale: Locale | None = None


class MessageAccepted(Frozen):
    """La respuesta del `POST`: se admitio y la respuesta sale por el flujo."""

    session_id: str
    language: Locale


class MessageRejected(Frozen):
    """Se alcanzo un limite. Lleva **cual** y la clave de la frase, nunca el texto.

    El navegador resuelve la frase de su catalogo, igual que con la de espera: una
    frase resuelta en dos sitios acaba diciendose de dos maneras.
    """

    limit: LimitKind
    copy_key: str
    retry_after: datetime | None = None


class DemoClosed(Frozen):
    """La demostracion no acepta casos nuevos ahora mismo (BR3.2 de U20).

    **Lleva `kind` y los otros dos rechazos no**, y no es adorno: el cliente
    generado no entrega el codigo de estado, asi que la pantalla distingue los
    rechazos **por su forma**. Un tercero con solo `copy_key` seria
    indistinguible del de fuera de proposito, y la pantalla diria "esa no es una
    pregunta de cobertura" cuando lo que pasa es que la demo se estrecho.
    """

    kind: Literal["demo_closed"] = "demo_closed"
    copy_key: str


class MessageOutOfScope(Frozen):
    """El texto no es una pregunta de cobertura y la superficie solo admite esas.

    Lleva la clave de la frase y nunca la frase, como el rechazo por limite: una
    frase resuelta en dos sitios acaba diciendose de dos maneras.
    """

    copy_key: str


#: La frase de "fuera de proposito" de la vista de comparacion (AC2.9.6).
OUT_OF_SCOPE = CopyKey("comparison.out_of_scope.explanation")

#: Lo que lee quien escribe con la demostracion estrechada (BR3.2 de U20). El
#: literal se escribe aqui, en el consumidor, porque de eso depende el chequeo de
#: claves sin consumidor; que coincida con la constante de U20 y con la tabla de la
#: voz lo comprueba una prueba de U20.
SURFACES_CLOSED = CopyKey("demo.reset.surfaces_closed")

#: El aviso que recibe una conversacion viva cuando el reinicio nocturno se llevo
#: su caso (BR2.6 de U20). Mismo trato que la de arriba: el literal se escribe en
#: el consumidor y una prueba de U20 comprueba que sigue siendo la misma clave que
#: declara aquella unidad, porque importarla no se puede --esta por encima en el
#: contrato de capas--.
RESET_NOTICE = CopyKey("demo.reset.conversation_notice")

#: Que superficies admiten **solo** preguntas de cobertura (Q3 de U23). Tabla
#: cerrada: el chat admite cualquier cosa --para eso existe-- y la comparacion no.
#:
#: Quien lo decide es el reconocedor determinista que ya existe, el mismo que usa
#: `case_opening` para elegir entre una consulta de dos campos y un siniestro de
#: siete. Fuera de proposito es, literalmente, "no es una pregunta de cobertura", y
#: una heuristica nueva en el cliente seria una tercera cosa: ni regla ni modelo.
SOLO_COBERTURA: frozenset[opening.Surface] = frozenset({opening.Surface.COMPARISON})


def _ahora() -> datetime:
    return datetime.now(UTC)


async def _entregar_la_apertura(
    conversacion: chat.ChatSession,
    *,
    config: TenantConfig,
    surface: opening.Surface,
    stream_ref: str,
    por_el_flujo: bool = True,
) -> chat.ChatSession:
    """La apertura con divulgacion, una sola vez por conversacion (BR1.1).

    **No se publica cuando otra pantalla ya mostro la suya** (FD-U23-8). La vista
    de comparacion muestra una divulgacion que dice mas que esta --nombra la
    poliza de ejemplo de cada columna-- y publicar las tres --una por columna--
    dejaria cuatro divulgaciones seguidas y tres ofertas de reportar un siniestro
    en una pantalla que compara coberturas. La conversacion queda marcada igual,
    que es lo que hace atendible el mensaje, y la clave que se registra es la de
    la superficie.

    **Tampoco se publica cuando la pide el historial** (`por_el_flujo` en falso):
    esa ruta la devuelve en su cuerpo, y publicarla ademas por el flujo la haria
    llegar dos veces a la misma pantalla. La conversacion queda marcada igual.
    """
    if conversacion.opening_delivered:
        return conversacion
    marcada = await chat.mark_opening_delivered(conversacion, now=_ahora())
    if surface is not opening.Surface.CHAT or not por_el_flujo:
        return marcada
    apertura = opening.compose(config, language=marcada.language)
    cola = _COLAS.get(stream_ref)
    if cola is not None:
        cola.publish(
            {
                "kind": "turn.final",
                "message_id": history.opening_message_id(marcada),
                "text": apertura.text,
                "language": marcada.language,
                "case_id": marcada.case_id,
                "citations": [],
                "suggestions": list(
                    sugerencias.options(
                        language=marcada.language, quote_enabled=config.quote_enabled
                    )
                ),
            }
        )
    return marcada


def _avisar_del_reinicio(visitante: Visitante) -> None:
    """Le dice a la pestana que sigue abierta que la demostracion se reinicio (BR2.6).

    Sin el aviso, quien estaba escribiendo ve que su conversacion dejo de tener
    sentido y no sabe por que: su caso ya no existe y su mensaje siguiente abre
    uno nuevo. El aviso sale por la cola **del navegador**, que es la que
    sobrevivio al borrado, y el mensaje siguiente se atiende normalmente.

    El texto se resuelve aqui, como el de la apertura, y no viaja como clave: es
    un mensaje de la conversacion y no un aviso transitorio del protocolo.
    """
    cola = _COLAS.get(_flujo_de(visitante.session.tenant_id, visitante.key_hash))
    if cola is None:  # pragma: no cover - solo se llama cuando habia cola
        return
    idioma = visitante.session.language
    cola.publish(
        {
            "kind": "turn.final",
            "message_id": f"demo-reset-{visitante.session.chat_session_id}",
            "text": copy_api.t(RESET_NOTICE, locale=idioma),
            "language": idioma,
            "case_id": None,
            "citations": [],
        }
    )


class _ChatNotifier:
    """Le lleva a un caso lo que el ritmo de fondo calculo, **sin turno siguiente**.

    Cumple `orchestration.contracts.CaseNotifier`. Vive aqui porque es aqui donde se
    sabe que existen colas, navegadores y pestanas abiertas: el nucleo solo dice que
    hay algo que decir de un caso.

    **La cola es del navegador y no de la conversacion**, como la del aviso del
    reinicio y por la misma razon (BR2.6 de U20): es la que sobrevive al borrado
    nocturno. Del caso se llega al navegador por la conversacion viva, que es la
    unica que ata los dos.

    Devolver si habia alguien escuchando no es cortesia: una respuesta calculada que
    no se entrego es un caso que al visitante le quedo a medias, y eso tiene que
    poder contarse en la traza. Lo que **no** se hace es guardarla para despues: ya
    esta guardada en su tabla, y el turno siguiente la lee si la persona vuelve.
    """

    async def notify(  # noqa: PLR0913 -- la firma del puerto CaseNotifier
        self,
        tenant_id: str,
        case_id: str,
        *,
        text: str,
        citations: tuple[object, ...] = (),
        suggestions: tuple[str, ...] = (),
        coverage_outcome: str | None = None,
        language: Locale | None = None,
    ) -> bool:
        escucha = await chat.listener_of(tenant_id, case_id)
        if escucha is None:
            observability.emit("chat.case_notice_unheard", tenant_id=tenant_id, case_id=case_id)
            return False
        # El idioma en que se compuso la respuesta manda sobre el de la conversacion:
        # quien abre una aseguradora que arranca en ingles y pregunta en espanol
        # recibia el texto en espanol y la tarjeta de la clausula rotulada en ingles.
        idioma = language if language is not None else escucha.language
        cola = _COLAS.get(_flujo_de(tenant_id, escucha.visitor_key_digest))
        if cola is None:
            observability.emit("chat.case_notice_unheard", tenant_id=tenant_id, case_id=case_id)
            return False
        # Las citas, completas como las de cualquier respuesta del turno: la pantalla
        # muestra la clausula exacta debajo del texto (fase 1, 2026-10-08).
        detalles = (
            await citation.details_for(tenant_id, citations, language=idioma) if citations else ()
        )
        entregado = cola.publish(
            stream.to_wire(
                FinalText(
                    message_id=f"background-{case_id}-{uuid.uuid4().hex[:8]}",
                    text=text,
                    language=idioma,
                    case_id=case_id,
                    citations=citations,
                    from_catalog=True,
                    suggestions=suggestions,
                    coverage_outcome=coverage_outcome,
                ),
                citations=detalles,
            )
        )
        observability.emit(
            "chat.case_notice_delivered" if entregado else "chat.case_notice_unheard",
            tenant_id=tenant_id,
            case_id=case_id,
        )
        return entregado


#: El puerto que la raiz enchufa en el ritmo de fondo (U19, tanda 2).
CASE_NOTIFIER = _ChatNotifier()


async def _la_demo_no_acepta_casos_nuevos(conversacion: chat.ChatSession) -> bool:
    """Si este mensaje abriria un caso nuevo con la demostracion estrechada.

    Las dos mitades juntas son la regla: una conversacion que **ya tiene caso**
    sigue entera aunque la ventana este cerrada (BR3.3), y la que no lo tiene no
    lo abre (BR3.2). Vive aqui y no en el cuerpo de la ruta para que la condicion
    tenga un nombre y un sitio donde leerse: en la ruta era la mitad de una linea
    con dos negaciones.
    """
    if conversacion.case_id is not None:
        return False
    return not await demo_window.current_new_case_gate()()


async def _recuperar_historial(
    tenant_id: str,
    visitor_key: str | None,
    request: Request,
    response: Response,
    *,
    locale: Locale | None = None,
) -> history.ChatHistory:
    """Lo que hace la ruta del historial, fuera del enrutador para que se lea solo.

    Entrega la apertura **sin publicarla** --va en el cuerpo-- y, si la
    conversacion anterior de este navegador desaparecio con el reinicio nocturno
    mientras su pestana seguia abierta, publica el aviso igual que lo haria el
    mensaje (BR2.6 de U20): es la misma situacion, vista desde la otra puerta.
    """
    config = tenancy.require(tenant_id)
    visitante = await _visitante(tenant_id, visitor_key, request, response)
    if visitante.resumed_after_reset:
        observability.emit("chat.reset_notice_published", tenant_id=tenant_id)
        _avisar_del_reinicio(visitante)
    conversacion = visitante.session
    if locale is not None:
        # El idioma de la pantalla, solo mientras la conversacion no haya dicho
        # nada (P2, decision de Miguel): la apertura sale en ese idioma.
        conversacion = await chat.set_language_if_fresh(conversacion, language=locale)
    conversacion = await _entregar_la_apertura(
        conversacion,
        config=config,
        surface=opening.Surface.CHAT,
        stream_ref=_flujo_de(tenant_id, visitante.key_hash),
        por_el_flujo=False,
    )
    return await history.load(conversacion, config=config)


async def _reiniciar(
    tenant_id: str,
    visitor_key: str | None,
    request: Request,
    response: Response,
    *,
    locale: Locale | None = None,
) -> history.ChatHistory:
    """Empezar de cero (decision de Miguel, 2026-10-06).

    Cierra la conversacion viva de este navegador --el caso queda guardado con su
    numero-- y abre una nueva con su apertura entregada, que es lo que devuelve.
    Se hace aqui entero y no dejando que la peticion siguiente abra la conversacion:
    esa peticion leeria "la pestana seguia abierta cuando la conversacion
    desaparecio" y publicaria el aviso del reinicio nocturno (BR2.6 de U20), que no
    es lo que paso.
    """
    config = tenancy.require(tenant_id)
    clave = visitor_key or tenancy.new_visitor_key()
    registro = await tenancy.resolve_visitor_key(
        tenant_id=tenant_id, visitor_key=clave, origin=_origen(request)
    )
    if visitor_key is None:
        response.set_cookie(COOKIE, clave, httponly=True, samesite="lax", secure=True)
    viva = await chat.find_live(tenant_id=tenant_id, visitor_key_digest=registro.visitor_key_hash)
    if viva is not None:
        await chat.close_session(viva, now=_ahora())
        observability.emit(
            "chat.conversation_reset",
            tenant_id=tenant_id,
            session_ref=viva.chat_session_id,
            had_case=viva.case_id is not None,
        )
    nueva = await chat.open_session(
        tenant_id=tenant_id,
        visitor_key_digest=registro.visitor_key_hash,
        origin_digest=registro.origin,
        # En el idioma de la pantalla, si lo dijo (P2): es la conversacion nueva.
        language=locale if locale is not None else config.default_language,
        now=_ahora(),
    )
    abierta = await _entregar_la_apertura(
        nueva,
        config=config,
        surface=opening.Surface.CHAT,
        stream_ref=_flujo_de(tenant_id, registro.visitor_key_hash),
        por_el_flujo=False,
    )
    return await history.load(abierta, config=config)


async def _resumen_de_traza(
    tenant_id: str, trace_id: str, visitor_key: str | None
) -> trace.TraceView | None:
    """Lo que hace la ruta del resumen de traza, fuera del enrutador.

    `200` con `null`, y **no** un 404: "no hay nada que mostrar" es una respuesta
    valida a una pregunta valida, no un error de quien pregunta. Con 404 el
    navegador escribe un error en la consola de una pagina que funciona --lo
    encontro el arnes de accesibilidad-- y el esquema ya declara `TraceView |
    null`. Que las tres causas respondan igual lo hace `by_trace`.
    """
    tenancy.require(tenant_id)
    resumen_clave = None if visitor_key is None else tenancy.visitor_key_digest(visitor_key)
    return await trace.by_trace(trace_id, tenant_id=tenant_id, visitor_key_hash=resumen_clave)


async def _estado_del_caso(
    tenant_id: str, visitor_key: str | None
) -> case_status.ChatCaseStatus | None:
    """Lo que hace la ruta del estado del caso, fuera del enrutador para que se lea solo."""
    tenancy.require(tenant_id)
    if visitor_key is None:
        return None
    viva = await chat.find_live(
        tenant_id=tenant_id, visitor_key_digest=tenancy.visitor_key_digest(visitor_key)
    )
    if viva is None:
        return None
    return await case_status.for_session(viva, signing_key=_CLAVE_DE_ENLACE, now=_ahora())


async def _pensamiento(
    tenant_id: str, visitor_key: str | None, *, language: Locale
) -> reasoning.ChatReasoning | None:
    """Lo que hace la ruta del pensamiento, fuera del enrutador, como el estado del caso."""
    tenancy.require(tenant_id)
    if visitor_key is None:
        return None
    viva = await chat.find_live(
        tenant_id=tenant_id, visitor_key_digest=tenancy.visitor_key_digest(visitor_key)
    )
    if viva is None:
        return None
    return await reasoning.for_session(viva, language=language, cipher=crypto.active())


def _origen(request: Request) -> str:
    """De donde llega, para el limite por origen. No se guarda: se resume."""
    return request.headers.get("origin") or (request.client.host if request.client else "unknown")


@dataclass(frozen=True)
class Visitante:
    """Quien escribe: su conversacion, su clave y el resumen de su clave.

    Las tres viajan juntas porque se obtienen de una sola resolucion y cada
    consumidor necesita una distinta: la cookie se pone con la clave, el turno se
    entrega con la conversacion, y el resumen de traza se ata al resumen de la
    clave --que es lo unico que sale de aqui hacia otra unidad, porque la clave
    misma no se comparte (BR7.3 de U5)--.
    """

    session: chat.ChatSession
    key: str
    key_hash: str
    #: La conversacion se abrio **en esta peticion** y este navegador ya tenia un
    #: flujo abierto. La unica forma de llegar a ese estado es que su conversacion
    #: anterior desapareciera mientras su pestana seguia abierta, y lo unico que
    #: borra una conversacion viva es el reinicio nocturno: ningun camino del
    #: aplicativo escribe `closed_at` (BR2.6 de U20).
    resumed_after_reset: bool = False


async def _visitante(
    tenant_id: TenantId, visitor_key: str | None, request: Request, response: Response
) -> Visitante:
    """La conversacion viva de este navegador, abriendola si es su primera vez."""
    clave = visitor_key or tenancy.new_visitor_key()
    registro = await tenancy.resolve_visitor_key(
        tenant_id=tenant_id, visitor_key=clave, origin=_origen(request)
    )
    if visitor_key is None:
        response.set_cookie(COOKIE, clave, httponly=True, samesite="lax", secure=True)

    viva = await chat.find_live(tenant_id=tenant_id, visitor_key_digest=registro.visitor_key_hash)
    if viva is not None:
        return Visitante(session=viva, key=clave, key_hash=registro.visitor_key_hash)

    config = tenancy.require(tenant_id)
    # Se mira **antes** de abrir la nueva: lo que distingue "se reinicio la
    # demostracion" de "es su primera vez" es que este navegador ya estuviera
    # escuchando.
    # Y escuchando de verdad: la cola que un mensaje reservo antes de que su flujo
    # abriera no la lee nadie, y no cuenta como una pestana abierta.
    cola_previa = _COLAS.get(_flujo_de(tenant_id, registro.visitor_key_hash))
    escuchaba = cola_previa is not None and cola_previa.attached
    nueva = await chat.open_session(
        tenant_id=tenant_id,
        visitor_key_digest=registro.visitor_key_hash,
        origin_digest=registro.origin,
        language=config.default_language,
        now=_ahora(),
    )
    return Visitante(
        session=nueva,
        key=clave,
        key_hash=registro.visitor_key_hash,
        resumed_after_reset=escuchaba,
    )


def _copiar_galleta(desde: Response, hacia: Response) -> None:
    """Pasa las cabeceras `set-cookie` de una respuesta a otra.

    Se copian **todas** las que haya y no una por nombre: `set-cookie` es la unica
    cabecera que puede repetirse, y quedarse con la primera es como una galleta nueva
    se pierde el dia que se anada otra.
    """
    for nombre, valor in desde.raw_headers:
        if nombre.lower() == b"set-cookie":
            hacia.raw_headers.append((nombre, valor))


def _sse(evento: dict[str, Any], *, event_id: int) -> bytes:
    """Un evento en el formato del cable. `id:` creciente, como C-04 pide."""
    return b"id: %d\ndata: %s\n\n" % (event_id, orjson.dumps(evento))


async def event_stream(cola: EventQueue) -> AsyncIterator[bytes]:
    """Los eventos de una conversacion, con su latido cada quince segundos.

    Publica y no privada a proposito: es la forma exacta del cable de C-04, y es
    donde vive la conducta que hay que comprobar. Un flujo abierto no se puede
    consumir entero desde una prueba --no termina hasta que la pestana se cierra,
    que es justo lo que se quiere-- asi que se prueba aqui, cerrando la cola.

    El latido no es adorno: sin el, un intermediario corta una conexion ociosa y
    el navegador se queda mirando una pantalla que no va a decir nada mas.
    """
    # Lo primero, en cuanto la conexion se abre: el intervalo de reconexion que
    # C-04 deja al navegador y un latido. Sin esto el flujo no dice nada hasta que
    # pasan quince segundos, y en ese rato una conexion viva y una colgada se ven
    # exactamente igual --tanto para quien mira la pantalla como para quien la
    # prueba--.
    yield b"retry: 3000\n: open\n\n"

    while True:
        evento = await cola.next_event(heartbeat_after=HEARTBEAT_SECONDS)
        if evento is None:
            # Ni evento ni nada pendiente: o toca latido, o la cola ya se drenó y
            # el flujo termina. Se mira `drained` y no `closed` porque cerrar no
            # es descartar: un turno que publica su respuesta final y cierra acto
            # seguido tiene que entregarla igual.
            if cola.drained:
                return
            yield b": heartbeat\n\n"
            continue
        yield _sse(evento, event_id=cola.next_id())


def router() -> APIRouter:  # noqa: C901 -- seis rutas cortas, cada una delegando en su funcion; partir el enrutador esconderia el contrato que existe para tener a la vista
    """Las seis rutas del chat publico (C-04, C-23, C-24)."""
    enrutador = APIRouter(prefix="/api/chat", tags=["chat"])

    @enrutador.get(
        "/{tenant_id}/stream",
        operation_id="streamChat",
    )
    async def stream_chat(
        tenant_id: str,
        request: Request,
        response: Response,
        untangle_visitor: Annotated[str | None, Cookie()] = None,
    ) -> StreamingResponse:
        visitante = await _visitante(tenant_id, untangle_visitor, request, response)
        # **La cola es del navegador y no de la conversacion** (ver `wire.py`): la
        # pestana sigue abierta cuando el reinicio nocturno se lleva la
        # conversacion, y es por ahi por donde se le avisa (BR2.6 de U20).
        cola = _COLAS.open(_flujo_de(tenant_id, visitante.key_hash))
        flujo = StreamingResponse(
            event_stream(cola),
            media_type="text/event-stream",
            headers={"cache-control": "no-store", "x-accel-buffering": "no"},
        )
        # **La galleta se copia a mano, y de eso dependia que el chat funcionara.**
        # FastAPI solo mezcla las cabeceras del `Response` inyectado cuando la ruta
        # devuelve un valor que el serializa; una `Response` devuelta tal cual --como
        # esta-- sale con las suyas y nada mas. El resultado era el tercer defecto de
        # esta costura, y el mas silencioso de los tres: el primer visitante abria su
        # flujo escuchando la conversacion A, se iba sin galleta, y su primer mensaje
        # --que si la recibia, porque esa ruta devuelve un valor serializado-- abria
        # la conversacion B. El flujo de A nunca oyo nada de B, y **ningun visitante
        # nuevo recibio una sola respuesta jamas**.
        _copiar_galleta(response, flujo)
        return flujo

    @enrutador.post(
        "/{tenant_id}/messages",
        status_code=202,
        operation_id="sendChatMessage",
        # El 429 se **declara**, no solo se devuelve: sin esta linea el esquema
        # dice que esta ruta solo responde 202, el cliente generado tipa el
        # rechazo como un error cualquiera y la pantalla no puede leer ni cual
        # limite fue ni su frase. Un contrato que no nombra una respuesta que
        # existe es un contrato que miente.
        responses={
            409: {
                "model": MessageOutOfScope,
                "description": "El texto no es una pregunta de cobertura (Q3 de U23)",
            },
            429: {"model": MessageRejected, "description": "Se alcanzo un limite (BR3.1)"},
            503: {
                "model": DemoClosed,
                "description": "La demostracion no acepta casos nuevos (BR3.2 de U20)",
            },
        },
    )
    async def send_message(
        tenant_id: str,
        body: MessageIn,
        request: Request,
        response: Response,
        untangle_visitor: Annotated[str | None, Cookie()] = None,
    ) -> MessageAccepted | MessageRejected | MessageOutOfScope | DemoClosed:
        # La marca de cuando el servidor recibe el mensaje: el extremo izquierdo de la latencia
        # del chat (`chat/latency.py`). **Al entrar**, antes de resolver al visitante, abrir la
        # apertura y contar el mensaje, porque esa espera tambien la vive quien escribe.
        recibido = time.monotonic()
        config = tenancy.require(tenant_id)
        visitante = await _visitante(tenant_id, untangle_visitor, request, response)
        conversacion = visitante.session

        # El aviso del reinicio, antes de cualquier otra cosa que se publique: su
        # conversacion anterior desaparecio anoche y su mensaje abre un caso nuevo
        # (BR2.6 de U20).
        if visitante.resumed_after_reset:
            observability.emit("chat.reset_notice_published", tenant_id=tenant_id)
            _avisar_del_reinicio(visitante)

        # **La ventana de la demostracion, antes que nada** (BR3.2, BR3.3 de U20).
        # Lo que se estrecha son los **casos nuevos**: una conversacion que ya
        # tiene caso sigue entera --quien esta a mitad de un reporte lo termina--
        # y la que no lo tiene no lo abre. Va antes de la apertura y antes de
        # contar: de este mensaje no se va a atender nada, asi que ni la
        # divulgacion sale ni el limite del visitante se gasta.
        if await _la_demo_no_acepta_casos_nuevos(conversacion):
            observability.emit("chat.demo_closed", tenant_id=tenant_id)
            response.status_code = 503
            return DemoClosed(copy_key=str(SURFACES_CLOSED))

        # BR1.1: la apertura sale --y queda anotada-- antes de mirar nada del
        # texto. `admit` levanta si no esta, asi que esto no es cortesia: es lo
        # que hace que el mensaje se pueda atender.
        conversacion = await _entregar_la_apertura(
            conversacion,
            config=config,
            surface=body.surface,
            stream_ref=_flujo_de(tenant_id, visitante.key_hash),
        )

        admision = await chat.admit(
            conversacion,
            config=config.chat,
            message_characters=len(body.text),
            now=_ahora(),
        )
        if not admision.admitted:
            limite = admision.limit
            observability.emit(
                "chat.message_rejected", tenant_id=tenant_id, limit=limite.value if limite else ""
            )
            response.status_code = 429
            cual = limite or LimitKind.SESSION
            return MessageRejected(
                limit=cual,
                # De la tabla cerrada que vive junto al enum, nunca compuesta con
                # una f-string: una clave compuesta no aparece en el chequeo de
                # claves sin consumidor, y por eso las cinco que se mandaban no
                # existian en el catalogo sin que nada avisara.
                copy_key=LIMIT_COPY_KEYS[cual],
                retry_after=admision.decision.retry_after,
            )

        idioma = language.for_turn(
            body.text, current=body.locale if body.locale is not None else conversacion.language
        )
        await chat.count_message(conversacion, now=_ahora())

        # Y **despues de contar**: tres mensajes se mandaron, asi que tres se
        # descuentan de los limites (BR2.3 de U23). Un corte antes de contar
        # convertiria la vista en la unica superficie donde preguntar sale gratis.
        if body.surface in SOLO_COBERTURA and not coverage_detour.is_question_for_comparison(
            body.text, language=idioma.language
        ):
            observability.emit(
                "chat.message_out_of_scope",
                tenant_id=tenant_id,
                surface=body.surface.value,
            )
            response.status_code = 409
            return MessageOutOfScope(copy_key=str(OUT_OF_SCOPE))

        flujo = _flujo_de(tenant_id, visitante.key_hash)
        cola = _COLAS.get(flujo)
        if cola is None or cola.closed:
            # **El mensaje llego antes que su flujo** (2026-10-13), o cuando el anterior
            # ya se cerro y el navegador todavia no reconecta. Antes no se entregaba:
            # el `POST` respondia `202` y la respuesta no se publicaba en ninguna parte,
            # que es exactamente un mensaje aceptado que nunca se atiende. Ahora se
            # reserva la cola, el turno se atiende y la respuesta espera ahi a que el
            # flujo abra, que lo hace al cargar la pagina: `open` se queda con esa cola.
            # Se sigue diciendo en la traza, porque la carrera existe aunque ya no pierda.
            cola = _COLAS.reserve(flujo)
            observability.emit(
                "chat.message_before_stream",
                tenant_id=tenant_id,
                session_ref=conversacion.chat_session_id,
            )
        entrante = InboundTurn(
            tenant_id=tenant_id,
            session_ref=conversacion.chat_session_id,
            case_id=conversacion.case_id,
            text=body.text,
            language=idioma.language,
            channel="chat",
            received_at=_ahora(),
        )
        tarea = asyncio.create_task(
            delivery.deliver(
                cola,
                entrante,
                handle_turn=current_turn_handler(),
                visitor_key_hash=visitante.key_hash,
                surface=body.surface,
                # El chat publico es dato de visitante: el reinicio nocturno
                # borra sus casos (BR4.6 de U4). Una corrida de evaluaciones
                # pasa otro origen, y por eso no hay valor por omision.
                origin=Origin.PUBLIC_CHAT,
                received_monotonic=recibido,
            )
        )
        _ENTREGAS.add(tarea)
        tarea.add_done_callback(_entrega_terminada)

        return MessageAccepted(session_id=conversacion.chat_session_id, language=idioma.language)

    @enrutador.get(
        "/{tenant_id}/history",
        operation_id="chatHistory",
    )
    async def chat_history(
        tenant_id: str,
        request: Request,
        response: Response,
        untangle_visitor: Annotated[str | None, Cookie()] = None,
        locale: Locale | None = None,
    ) -> history.ChatHistory:
        """La conversacion de este navegador como estaba, para dibujarla al abrir.

        `locale` es el idioma de la pantalla: una conversacion que todavia no dijo
        nada se abre en el, y la apertura sale en el (decision de Miguel,
        2026-10-06). Una en marcha no cambia por el selector.

        **La apertura sale aqui, al cargar la pagina, y no con el primer mensaje.**
        Es lo que el docstring de `OpeningNotDeliveredError` daba por hecho desde
        U13 --"la apertura sale al cargar la pagina, antes de que haya nada que
        escribir"-- y hasta el 2026-10-06 nadie lo hacia: la agente se presentaba
        **despues** de que la persona escribiera, y al volver a entrar no se
        presentaba nunca. La ruta del mensaje conserva su entrega para quien
        escribe sin haber pasado por aqui (un guion, una corrida de evaluaciones).

        **Esta ruta si resuelve la clave del navegador**, al contrario que la del
        resumen de traza: la pantalla la llama al abrirse, igual que abre el flujo,
        y las dos tienen que acabar en la misma conversacion. La pantalla la pide
        **despues** de que el flujo abrio, para que la galleta ya este puesta.
        """
        return await _recuperar_historial(
            tenant_id, untangle_visitor, request, response, locale=locale
        )

    @enrutador.post(
        "/{tenant_id}/reset",
        operation_id="resetChatConversation",
    )
    async def reset_conversation(
        tenant_id: str,
        request: Request,
        response: Response,
        untangle_visitor: Annotated[str | None, Cookie()] = None,
        locale: Locale | None = None,
    ) -> history.ChatHistory:
        """Empezar de cero: la conversacion nueva, con su apertura en el idioma de
        la pantalla, y el caso anterior guardado con su numero."""
        return await _reiniciar(tenant_id, untangle_visitor, request, response, locale=locale)

    @enrutador.get(
        "/{tenant_id}/case",
        operation_id="chatCaseStatus",
    )
    async def chat_case_status(
        tenant_id: str,
        untangle_visitor: Annotated[str | None, Cookie()] = None,
    ) -> case_status.ChatCaseStatus | None:
        """Donde va el caso de este navegador: numero, avance y enlace para abrirlo.

        Solo lee: sin galleta no hay conversacion y no se da de alta ninguna, como
        en el resumen de traza. `200` con `null` cuando no hay caso todavia: no es
        un error de quien pregunta, es que la conversacion acaba de empezar.
        """
        return await _estado_del_caso(tenant_id, untangle_visitor)

    @enrutador.get(
        "/{tenant_id}/reasoning",
        operation_id="chatReasoning",
    )
    async def chat_reasoning(
        tenant_id: str,
        language: Locale = "es",
        untangle_visitor: Annotated[str | None, Cookie()] = None,
    ) -> reasoning.ChatReasoning | None:
        """El pensamiento de la agente sobre el caso de este navegador (2026-10-09).

        Solo lee, como el estado del caso: sin galleta o sin caso, `200` con `null`.
        """
        return await _pensamiento(tenant_id, untangle_visitor, language=language)

    @enrutador.get(
        "/{tenant_id}/trace/{trace_id}",
        operation_id="chatTraceSummary",
    )
    async def trace_summary(
        tenant_id: str,
        trace_id: str,
        untangle_visitor: Annotated[str | None, Cookie()] = None,
    ) -> trace.TraceView | None:
        """El resumen de una respuesta, sin credencial y solo del propio navegador.

        **Sin cookie no se resuelve ninguna clave.** Un navegador que no ha escrito
        nunca no tiene resumen que ver, y resolverle una clave para responderle lo
        mismo solo dejaria una fila por cada visita a una direccion adivinada.

        El resumen de la clave se calcula, no se da de alta: esta ruta lee y no crea
        nada. Y las tres causas de que no haya nada --no existe, es de otra
        conversacion, es de otra aseguradora-- salen por esta misma puerta.
        """
        return await _resumen_de_traza(tenant_id, trace_id, untangle_visitor)

    return enrutador


async def _sonda() -> None:
    """Que el chat responde: una consulta que no toca ninguna fila (BR5.2).

    No llama al modelo, no gasta y no consume el limite de ningun visitante. Lo
    unico que distingue "el chat esta en pie" de "el chat esta caido" es que su
    tabla conteste.
    """
    tenant_id = tenancy.available_ids()[0]
    async with db.session_for(tenant_id) as sesion:
        await db.fetch_one(sesion, "SELECT 1 AS ok FROM chat_session LIMIT 1")


def surfaces() -> tuple[SurfaceSpec, ...]:
    """La superficie del chat, una por aseguradora (C-24, F8), y la de la comparacion."""
    return (
        SurfaceSpec(
            surface_id=SurfaceId.CHAT,
            owning_unit="u13-chat",
            public=True,
            per_tenant=True,
            probe=SurfaceProbe(check=_sonda, timeout_ms=PROBE_TIMEOUT_MS),
        ),
        # La comparacion entre aseguradoras (U23) habla por estas mismas rutas. Se
        # declara desde la fase 1 (2026-10-08): antes cada columna terminaba en "no
        # encuentro una clausula" porque nadie proponia citas, y enlazar lo que no
        # funciona es prometer una capacidad que no esta construida (BR4.1).
        SurfaceSpec(
            surface_id=SurfaceId.COMPARISON,
            owning_unit="u23-comparison",
            public=True,
            per_tenant=False,
            probe=SurfaceProbe(check=_sonda, timeout_ms=PROBE_TIMEOUT_MS),
        ),
    )


def purgers() -> tuple[Any, ...]:
    """El purgador del chat (C-11). Lo consume la raiz de composicion."""
    from untangle.chat.purge import CHAT_PURGER

    return (CHAT_PURGER,)


__all__ = [
    "CASE_NOTIFIER",
    "COOKIE",
    "SURFACES_CLOSED",
    "DemoClosed",
    "MessageAccepted",
    "MessageIn",
    "MessageRejected",
    "NewCaseGate",
    "NewCaseGateNotInstalledError",
    "TurnHandlerNotInstalledError",
    "current_turn_handler",
    "event_stream",
    "install_case_link_key",
    "install_new_case_gate",
    "install_turn_handler",
    "install_understanding",
    "router",
    "surfaces",
]
