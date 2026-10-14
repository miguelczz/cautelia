"""Las tres rutas de la llamada y el socket que la lleva (C-08, C-29, C-24).

Tres verbos y un socket. Los verbos deciden **si** se puede llamar, abren la
llamada y la cierran; el socket la sostiene. La conversacion en si esta en
`voice_loop.py`, que es lo que este archivo arranca cuando el token cuadra.

## Tres desviaciones de C-08, dichas

**La ruta.** C-08 dibuja `/tenants/{tenant}/voice/...` y aqui se monta
`/api/voice/{tenant_id}/...`. No es un descuido: es la forma que ya tienen las
nueve rutas construidas --el chat y la bandeja-- y una tercera convencion en la
misma API es peor que la que no se siguio.

**El cuerpo del `POST` no admite `case_id`.** C-08 lo declara para retomar una
llamada cortada, y aceptarlo seria dejar que quien llama **nombre un caso**. La
regla que lo impide es el criterio `[bloquea]` AC1.27.3: un caso retomable se
busca por el resumen de la clave del navegador y por nada mas (BR6.3). El campo
no se ignora --se quita--, porque un campo que se acepta y se descarta es el que
alguien reactiva un martes.

**Los carriles diarios salen nulos.** `calls_per_visitor_day` y
`calls_per_site_day` son de U17 y hoy no los aplica nadie. Servir un numero que
nada hace cumplir es exactamente la promesa que P7 prohibe; nulo dice la verdad,
que es que todavia no hay carril.

## Lo que este archivo no decide

**Ni el modo de voz ni los limites publicos.** El modo se fija al abrir y no
cambia a mitad de llamada (US5.11), y quien lo elige es U17 con su reserva; hasta
entonces se abre con la voz principal, que es la que la configuracion declara
primero. El techo de gasto del proyecto tampoco se decide aqui: se **lee** con la
misma funcion que usa la compuerta de U15, para que la respuesta de
disponibilidad y lo que el adaptador hara con la primera llamada no puedan
discrepar.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal, Protocol

import orjson
from fastapi import APIRouter, Cookie, Request, Response, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from untangle import observability
from untangle.base import Frozen, Locale
from untangle.case_record import api as casos
from untangle.case_record import rules as case_rules
from untangle.case_record.api import CaseClosedError
from untangle.case_record.models import (
    Actor,
    ActorType,
    CaseState,
    Channel,
    DerivationReason,
    InvalidTransitionError,
)
from untangle.chat import case_number as chat_case_number
from untangle.demo_operations import api as demo
from untangle.providers.ceiling import ceiling_closed
from untangle.providers.ports import SPEECH_AUDIO
from untangle.providers.voice_availability import VoiceAvailability
from untangle.server.problems import ProblemCode, ProblemError, problem_responses
from untangle.surface_spec import SurfaceId, SurfaceProbe, SurfaceSpec
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend import attribution as spend_attribution
from untangle.telemetry.spend.models import SITE_SUBJECT, QuotaScope, VoiceMode
from untangle.tenancy import api as tenancy
from untangle.tenancy import session as db
from untangle.tenancy.models import TenantId, UnknownTenantError
from untangle.voice import admission
from untangle.voice import api as voz
from untangle.voice.availability import OFF_CODE_KEYS, VoiceOffCode
from untangle.voice.loop import FILLER_AFTER, CallChannel, CallRunner, CallVoice

#: La galleta del visitante. Es **la misma** que la del chat: quien llama y quien
#: escribe son el mismo navegador, y dos galletas darian dos identidades a la
#: misma persona --y con ellas dos casos donde hay uno--.
COOKIE = "untangle_visitor"

#: El plazo de la sonda. Una consulta que no toca ninguna fila.
PROBE_TIMEOUT_MS = 200

#: Cuantos milisegundos de audio lleva cada cuadro binario (C-29).
FRAME_MS = 20

#: El codigo con el que se cierra un socket que no se autentico. Es el mismo para
#: las cuatro formas de token malo (BR1.5): distinguirlas le diria a quien esta
#: probando tokens cual acerto a medias.
CLOSE_UNAUTHENTICATED = 1008


class VoiceNotInstalledError(RuntimeError):
    """Se pidio una llamada y la raiz de composicion no enchufo la voz.

    Falla nombrandolo en vez de responder un error generico: sin plataforma de
    voz o sin manejador de turno, la llamada no puede existir, y eso es un fallo
    de arranque disfrazado de fallo de peticion.
    """


class Socket(Protocol):
    """Lo que el apreton de manos necesita de un WebSocket, y nada mas.

    `WebSocket` de Starlette lo cumple sin declararlo. Escribirlo como puerto es
    lo que permite comprobar que los cuatro tokens malos se cierran igual sin
    levantar un servidor, y deja a la vista que este archivo usa cinco cosas del
    transporte y no la clase entera.
    """

    client_state: WebSocketState

    async def accept(self) -> None: ...

    async def receive(self) -> Any: ...

    async def send_text(self, data: str) -> None: ...

    async def send_bytes(self, data: bytes) -> None: ...

    async def close(self, code: int = 1000) -> None: ...


class VoicePlatform(CallVoice, Protocol):
    """Lo que las rutas necesitan de la voz de U15: disponibilidad, oido y boca.

    `SpeechPlatform` lo cumple sin declararlo, que es la gracia de un `Protocol`
    estructural. Se escribe como puerto y no se toma la plataforma entera por lo
    mismo que en el ciclo: lo que estas rutas pueden pedirle a la voz cabe en
    tres lineas, y con eso la llamada entera se prueba con los dobles de esta
    unidad --que heredan de los `Protocol` de C-16-- sin construir un solo
    cliente ni tocar la red.
    """

    def availability_for(self, tenant_id: TenantId) -> VoiceAvailability: ...


class SettleReview(Protocol):
    """Lo que el fin de una llamada necesita de la orquestacion: resolver la revision."""

    def __call__(self, case_id: str, /, *, tenant_id: TenantId) -> Awaitable[None]: ...


@dataclass(frozen=True)
class VoiceDeps:
    """Lo que la raiz enchufa para que la voz atienda.

    El manejador de turno entra por aqui y no se importa, por el mismo contrato
    que obliga al chat: el modulo que lo implementa importa LangGraph.
    """

    speech: VoicePlatform
    handle_turn: voz.TurnHandler
    #: Firma el token de socket. **Propia de la voz** desde el 2026-10-03: antes
    #: era la del enlace de caso, y una sola clave ataba las dos superficies.
    token_signing_key: str | None
    #: Firma el enlace de caso que la ruta de desenlace entrega al colgar. Es la
    #: de U2 y tiene que seguir siendolo: lo que emite aqui lo canjea la bandeja,
    #: que verifica con esa. Esta separada de la de arriba para que se vea que
    #: esta ruta firma **dos cosas distintas**.
    case_link_signing_key: str | None
    #: Quien lee un mensaje con el contexto de su caso, para que la llamada empiece a entender
    #: la frase en cuanto llega su final y no cuando vence la tolerancia de fin de habla
    #: (2026-10-13). Entra enchufado como el manejador de turno, por la misma razon. Nulo
    #: deja el turno leyendo por su cuenta, como antes.
    understand_turn: voz.TurnUnderstander | None = None
    #: Quien resuelve un reporte que quedo en revision cuando la llamada termina (US1.17): la
    #: oferta de datos opcionales sin contestar se da por rechazada y se corre el cierre. Entra
    #: enchufado como el manejador de turno, por la misma razon. Nulo no resuelve nada.
    settle_review: SettleReview | None = None


_DEPS: VoiceDeps | None = None


def install(deps: VoiceDeps) -> None:
    global _DEPS
    _DEPS = deps


def reset() -> None:
    """Suelta lo instalado. Solo para las pruebas, que construyen varias veces."""
    global _DEPS
    _DEPS = None


def current_deps() -> VoiceDeps:
    if _DEPS is None:
        msg = "la voz no esta enchufada: la raiz de composicion no llamo a install()"
        raise VoiceNotInstalledError(msg)
    return _DEPS


# --- Lo que viaja por las tres rutas ------------------------------------------


class CallLimits(Frozen):
    """Los limites que la consola dibuja antes de ofrecer el boton (BR1.1)."""

    max_call_seconds: int
    warn_at_seconds: int
    resume_window_seconds: int
    #: Nulos hasta que U17 los aplique. Ver la cabecera del modulo.
    calls_per_visitor_day: int | None = None
    calls_per_site_day: int | None = None


class Availability(Frozen):
    """Si hay voz, con que motivo no, con que modo y con que limites (C-08)."""

    available: bool
    reason_code: VoiceOffCode | None = None
    #: La frase del catalogo que la consola resuelve. **Nunca el texto**: una
    #: frase resuelta en los dos lados acaba diciendose de dos maneras.
    reason_key: str | None = None
    voice_mode: VoiceMode
    limits: CallLimits
    #: Hasta cuando este navegador puede retomar un caso cortado. Nulo si no hay.
    resume_until: datetime | None = None


class Transport(Frozen):
    """El objeto que C-08 dejo abierto y que D1 cierra (C-29).

    Un WebSocket del mismo origen con PCM de 16 bits, mono, a 24 kHz --el unico
    formato del aplicativo-- y el token en el primer cuadro, nunca en esta URL.
    """

    kind: Literal["websocket"] = "websocket"
    url: str
    #: Vive un minuto y se manda **dentro** del socket (BR1.4).
    token: str
    encoding: str
    sample_rate_hz: int
    channels: int
    frame_ms: int


class CallOpened(Frozen):
    """La respuesta de abrir una llamada (C-08)."""

    call_id: str
    case_id: str | None
    voice_mode: VoiceMode
    max_call_seconds: int
    transport: Transport


class CallOutcome(Frozen):
    """Donde quedo el caso de esta llamada, al terminar (BR3.4).

    **El enlace solo viaja cuando hay algo que abrir con el**: un caso derivado o
    cerrado tiene una pagina que leer, y uno que todavia espera al asegurado no
    --lo que ese necesita es volver o pedir que lo revise una persona, y eso son
    las dos salidas que la consola ofrece--.

    El numero del caso y no su identificador: es lo que la persona puede apuntar y
    lo que la bandeja muestra.
    """

    case_number: str
    state: CaseState
    case_link: str | None = None
    #: Si este caso se puede seguir por chat escribiendo su numero (US1.20): la aseguradora tiene
    #: encendida la continuidad voz a chat y el caso todavia esta en captura. Lo decide el servidor
    #: y no la pantalla, para que la consola no prometa lo que el chat no va a hacer.
    chat_continuation: bool = False


class NewCall(Frozen):
    """Lo que la consola manda para abrir. **Sin `case_id`**: ver la cabecera.

    `language` es **opcional desde U18** (BR1.1, decision D5), y su ausencia no es
    un descuido: significa "nadie eligio", y entonces manda el idioma de la
    aseguradora. La diferencia entre "eligio espanol" y "asi vino la pestana" la
    sabe el selector del navegador y no el servidor, asi que el servidor no la
    puede adivinar: lo unico que puede hacer es distinguir el dato que llega del
    que no llega. Es aditivo, asi que la API no cambia de version (decision de
    Miguel del 2026-09-18).
    """

    language: Locale | None = None


def _ahora() -> datetime:
    return datetime.now(UTC)


def _origen(request: Request) -> str:
    return request.headers.get("origin") or (request.client.host if request.client else "unknown")


def _aseguradora(tenant_id: str) -> TenantId:
    """La aseguradora de la ruta, o la misma respuesta que una inexistente."""
    try:
        tenancy.require(tenant_id)
    except UnknownTenantError as error:
        raise ProblemError(
            status=404,
            code=ProblemCode.NOT_FOUND,
            title="Unknown tenant",
        ) from error
    return tenant_id


#: Que cuota de U5 es cada carril, y de quien se cuenta. Tabla cerrada: el carril
#: de la conexion cuenta por el resumen de la galleta y el del sitio por el sitio
#: entero, que es un sujeto con nombre propio en U5.
_ALCANCE_DE: dict[admission.Lane, QuotaScope] = {
    admission.Lane.VISITOR: QuotaScope.VOICE_CALLS_VISITOR_DAY,
    admission.Lane.SITE: QuotaScope.VOICE_CALLS_SITE_DAY,
}

#: Que problema responde cada carril cuando es el que para la llamada.
_PROBLEMA_DE: dict[admission.Lane, ProblemCode] = {
    admission.Lane.VISITOR: ProblemCode.RATE_LIMITED_DAILY,
    admission.Lane.SITE: ProblemCode.RATE_LIMITED_SITE,
}


async def _cobrar_los_carriles(*, resumen: str, resumes: bool, now: datetime) -> None:
    """Consume los carriles que esta llamada gasta, en el orden de la politica.

    **Consumir y no leer**: `check_quota` consulta y consume en un solo acto, y
    entre las dos cosas habria un hueco por el que dos peticiones del mismo
    visitante pasarian las dos (RT-13). La respuesta de disponibilidad si lee, y
    por eso no puede ser la que decide: es cortesia, no cerrojo.

    El orden sale de `lanes_for`, que es el unico sitio donde esta escrito.

    **Lo que no se compensa, y por que.** Si el carril del sitio se agota justo
    despues de que el de la conexion ya se cobro --una carrera por la ultima
    llamada del dia del sitio--, esa conexion pierde su llamada del dia sin haber
    hablado. No se devuelve: lo que U5 ofrece para devolver cupo esta atado a una
    llamada que se abrio y se cerro sin gastar, y aqui no hay llamada. Cobrar el
    sitio primero movería la misma injusticia al carril caro, que entregaria un
    hueco del sitio a quien no puede usarlo. Queda dicho en el rastro.
    """
    cobrados: list[admission.Lane] = []
    for carril in admission.lanes_for(resumes=resumes):
        sujeto = resumen if carril is admission.Lane.VISITOR else SITE_SUBJECT
        decision = await spend.check_quota(_ALCANCE_DE[carril], sujeto, now=now)
        if not decision.allowed:
            observability.emit(
                "voice.call_rejected",
                lane=carril.value,
                already_charged=",".join(c.value for c in cobrados),
            )
            raise ProblemError(
                status=503,
                code=_PROBLEMA_DE[carril],
                title=f"The {carril.value} daily lane is exhausted",
                retry_after_s=decision.retry_after_seconds,
            )
        cobrados.append(carril)


async def _carriles_y_contadores(
    tenant_id: TenantId,
    *,
    resumen: str | None,
    corte: admission.CutCall | None,
    now: datetime,
) -> tuple[admission.CallLanes, admission.CallCounters]:
    """Los carriles de hoy y lo que llevan contado, **leidos sin consumir**.

    Los dos carriles diarios se le preguntan a U5 y no se vuelven a leer de
    `providers.yaml`: alli estan declarados una vez, la raiz de composicion los
    instala en el tiempo de ejecucion del gasto, y el del sitio **no es el tope
    escrito** sino el cupo que U5 deriva hoy del presupuesto (BR5.6). Leerlos aqui
    por segunda vez daria dos numeros que un dia discrepan, y el que la apertura
    aplica es el de U5.

    La ventana de retoma si sale de la carpeta de la aseguradora: cuanto tiempo se
    puede volver a una conversacion es una decision de como conversa cada una, no un
    control de gasto.
    """
    del_visitante = await spend.quota_state(QuotaScope.VOICE_CALLS_VISITOR_DAY, resumen, now=now)
    del_sitio = await spend.quota_state(QuotaScope.VOICE_CALLS_SITE_DAY, SITE_SUBJECT, now=now)
    carriles = admission.CallLanes(
        calls_per_visitor_day=del_visitante.limit,
        calls_per_site_day=del_sitio.limit,
        resume_window_seconds=tenancy.require(tenant_id).call.resume_window_seconds,
    )
    contadores = admission.CallCounters(
        visitor_calls_today=del_visitante.count,
        site_calls_today=del_sitio.count,
        cut_call=corte,
    )
    return carriles, contadores


#: Los estados en los que el caso tiene una pagina que abrir con su enlace. Uno
#: que todavia espera al asegurado no la tiene: lo que necesita son sus dos
#: salidas, no un enlace a algo que no ha pasado.
#:
#: **Uno en revision si la tiene** (US1.17): la llamada se despide a los pocos instantes de
#: terminar el reporte, y si las reglas todavia no resolvieron, la despedida dice que el
#: resultado aparece en la pantalla. Sin enlace, quien cuelga no tendria donde verlo.
_ESTADOS_CON_ENLACE: frozenset[CaseState] = frozenset(
    {CaseState.VERIFYING, CaseState.DECIDING, CaseState.DERIVED, CaseState.CLOSED}
)

#: Quien pide el traspaso es quien llamo, y no una persona de la aseguradora: el
#: registro no puede decir que lo derivo alguien de la bandeja (BR5.5 de U14).
VISITOR_ACTOR = "demo-visitor"


def _sin_carriles(tenant_id: TenantId) -> CallLimits:
    """Los limites de la llamada **sin** los carriles diarios.

    Es lo que viaja cuando la voz esta apagada: prometer "una llamada al dia" a
    quien no va a poder llamar es decirle que podria. Los carriles se sirven solo
    cuando hay voz, que es cuando significan algo.
    """
    config = tenancy.require(tenant_id).call
    return CallLimits(
        max_call_seconds=config.max_call_seconds,
        warn_at_seconds=config.warn_at_seconds,
        resume_window_seconds=config.resume_window_seconds,
    )


def _limites(
    tenant_id: TenantId, *, carriles: admission.CallLanes, cupo_del_sitio: int
) -> CallLimits:
    """Lo que la consola dibuja antes de ofrecer el boton.

    El carril del sitio que viaja es el **cupo de hoy** y no el tope escrito: el
    cupo se deriva cada dia de lo que queda del presupuesto (BR5.6) y es el que la
    apertura va a aplicar. Servir el tope prometeria llamadas que no caben.
    """
    config = tenancy.require(tenant_id).call
    return CallLimits(
        max_call_seconds=config.max_call_seconds,
        warn_at_seconds=config.warn_at_seconds,
        resume_window_seconds=config.resume_window_seconds,
        calls_per_visitor_day=carriles.calls_per_visitor_day,
        calls_per_site_day=cupo_del_sitio,
    )


async def _techo_cerrado() -> bool:
    """Si el techo del proyecto no deja abrir una llamada mas.

    Es la **misma** funcion que consulta la compuerta de U15 antes de cada llamada
    al proveedor, y por eso la respuesta de disponibilidad no puede discrepar de
    lo que pasara de verdad. Un fallo de lectura cierra, igual que alli: seguir
    seria gastar sin control.
    """
    try:
        return ceiling_closed(await spend.budget_state())
    except Exception as error:  # noqa: BLE001 -- cualquier fallo de lectura cierra; aqui lo que esta en juego es dinero
        observability.emit("voice.budget_unreadable", error_type=type(error).__name__)
        return True


async def _la_demo_acepta_casos_nuevos() -> bool:
    """Si la ventana del reinicio nocturno deja abrir un caso nuevo (BR3.2 de U20).

    **Un fallo de lectura cierra**, igual que el del techo y por una razon
    hermana: si no se puede afirmar que la retencion esta acotada, seguir
    recibiendo datos de personas es peor que degradar a proposito.

    Pregunta solo por las corridas **exitosas**: el reloj cuenta desde la ultima
    que termino limpia, nunca desde el ultimo intento.
    """
    try:
        return demo.accepts_new_cases(await demo.successful_runs(), now=_ahora())
    except Exception as error:  # noqa: BLE001 -- cualquier fallo de lectura cierra; lo que esta en juego son datos de personas
        observability.emit("voice.demo_window_unreadable", error_type=type(error).__name__)
        return False


async def _clave_del_visitante(
    tenant_id: TenantId, visitor_key: str | None, request: Request, response: Response
) -> str:
    """El resumen de la clave de este navegador, dandole una si es su primera vez."""
    clave = visitor_key or tenancy.new_visitor_key()
    registro = await tenancy.resolve_visitor_key(
        tenant_id=tenant_id, visitor_key=clave, origin=_origen(request)
    )
    if visitor_key is None:
        response.set_cookie(COOKIE, clave, httponly=True, samesite="lax", secure=True)
    return registro.visitor_key_hash


async def _resolver_la_revision(
    deps: VoiceDeps, llamada: voz.CallSession, tenant_id: TenantId
) -> None:
    """La red de seguridad de la voz (US1.17): una llamada que termina no deja el caso en revision.

    Colgar, un corte, el limite de tiempo o los silencios pueden terminar la llamada con el
    reporte completo y la oferta de datos opcionales sin contestar. El caso quedaria en revision
    para siempre: nadie volveria a lanzar la decision. Se da la oferta por rechazada y se
    corre el cierre, que cierra el caso o lo deriva. Nunca rompe el final de la llamada.
    """
    if deps.settle_review is None or llamada.case_id is None:
        return
    try:
        await deps.settle_review(llamada.case_id, tenant_id=tenant_id)
    except Exception as error:  # noqa: BLE001 -- el fin de la llamada ya paso: un fallo aqui se dice en la traza, no la rompe
        observability.emit(
            "voice.settle_review_failed",
            tenant_id=tenant_id,
            call_id=llamada.call_id,
            error_type=type(error).__name__,
            where=observability.failure_location(error),
        )


async def _desenlace(tenant_id: TenantId, llamada: object, *, ahora: datetime) -> CallOutcome:
    """Donde quedo el caso, con su enlace si hay algo que abrir (BR3.4).

    El enlace se emite **aqui y ahora**, no al abrir la llamada: vive una hora,
    y uno emitido al principio de una llamada de tres minutos llega a la
    pantalla con la hora ya empezada.
    """
    case_id = getattr(llamada, "case_id", None)
    if case_id is None:
        raise ProblemError(status=404, code=ProblemCode.NOT_FOUND, title="Unknown call")
    vista = await casos.get_case(tenant_id, case_id)
    if vista is None:
        raise ProblemError(status=404, code=ProblemCode.NOT_FOUND, title="Unknown call")

    enlace = None
    if vista.state in _ESTADOS_CON_ENLACE:
        emitido = await tenancy.issue_case_link(
            tenant_id=tenant_id,
            case_id=case_id,
            # La clave del enlace de caso, **no** la del token de socket: lo que
            # se emite aqui lo canja la bandeja de U2, que verifica con esta.
            signing_key=current_deps().case_link_signing_key,
            now=ahora,
        )
        # El token viaja en el **fragmento**, que el navegador nunca manda al
        # servidor ni en la cabecera de procedencia (C-07).
        enlace = f"/c#{emitido.token}"
    return CallOutcome(
        case_number=vista.case_number,
        state=vista.state,
        case_link=enlace,
        chat_continuation=(
            tenancy.require(tenant_id).voice_to_chat_continuity
            and vista.state in chat_case_number.CONTINUABLE
        ),
    )


def router() -> APIRouter:  # noqa: C901, PLR0915 -- son seis rutas y el socket, cada una corta; partirlas esconderia el contrato, que es lo que este enrutador existe para tener a la vista
    """Las cinco rutas de C-08, las dos del final de la llamada y el socket de C-29."""
    enrutador = APIRouter(prefix="/api/voice", tags=["voice"])

    @enrutador.get(
        "/{tenant_id}/availability",
        operation_id="voiceAvailability",
        responses=problem_responses(404),
    )
    async def availability(
        tenant_id: str,
        untangle_visitor: Annotated[str | None, Cookie()] = None,
    ) -> Availability:
        """Lo que la consola pregunta **antes** de ofrecer el boton (BR1.1).

        Ofrecer un boton que va a fallar es peor que no ofrecerlo. Aqui no se
        crea nada: un navegador que solo mira no deja fila en ninguna tabla, y
        por eso la clave del visitante solo se **calcula** si ya la traia.
        """
        aseguradora = _aseguradora(tenant_id)
        ahora = _ahora()
        estado = current_deps().speech.availability_for(aseguradora)
        # Con que voz se abriria una llamada ahora. Es la **misma funcion** que la
        # de la apertura, no una copia: si difirieran, la consola avisaria de una
        # voz y sonaria la otra.
        modo = await spend.expected_voice_mode(now=ahora)

        if not estado.available:
            return Availability(
                available=False,
                reason_code=VoiceOffCode.PROVIDER_UNAVAILABLE,
                reason_key=estado.reason_key,
                voice_mode=modo,
                limits=_sin_carriles(aseguradora),
            )
        if await _techo_cerrado():
            return Availability(
                available=False,
                reason_code=VoiceOffCode.BUDGET_EXHAUSTED,
                reason_key=OFF_CODE_KEYS[VoiceOffCode.BUDGET_EXHAUSTED],
                voice_mode=modo,
                limits=_sin_carriles(aseguradora),
            )

        resumen = None if untangle_visitor is None else tenancy.visitor_key_digest(untangle_visitor)
        cortada = (
            None
            if resumen is None
            else await voz.find_resumable(
                tenant_id=aseguradora, visitor_key_digest=resumen, now=ahora
            )
        )
        # Sin caso o sin hora de fin no hay retoma que ofrecer: el corte es
        # exactamente "esta conversacion quedo a medias y hasta cuando".
        corte = (
            admission.CutCall(case_id=cortada.case_id, ended_at=cortada.ended_at)
            if cortada is not None and cortada.case_id is not None and cortada.ended_at is not None
            else None
        )
        # **La ventana del reinicio nocturno, y solo para lo nuevo** (BR3.2, BR3.3
        # de U20). Va despues de resolver la retoma a proposito: quien dejo una
        # llamada a medias puede terminarla aunque la demo este estrechada --su
        # caso ya existe-- y esconderle el boton seria cortarle el reporte por un
        # fallo de operacion que no es suyo.
        if corte is None and not await _la_demo_acepta_casos_nuevos():
            return Availability(
                available=False,
                reason_code=VoiceOffCode.DEMO_CLOSED,
                reason_key=OFF_CODE_KEYS[VoiceOffCode.DEMO_CLOSED],
                voice_mode=modo,
                limits=_sin_carriles(aseguradora),
            )

        carriles, contadores = await _carriles_y_contadores(
            aseguradora, resumen=resumen, corte=corte, now=ahora
        )
        limites = _limites(
            aseguradora, carriles=carriles, cupo_del_sitio=carriles.calls_per_site_day
        )

        # **La decision va aqui y no se repite**: es la misma de la apertura, con
        # los contadores leidos en vez de consumidos. Ofrecer un boton que va a
        # fallar es peor que no ofrecerlo (BR1.1).
        decision = admission.decide(lanes=carriles, counters=contadores, now=ahora)
        if not decision.admitted:
            codigo = decision.off_code or VoiceOffCode.RATE_LIMITED_DAILY
            return Availability(
                available=False,
                reason_code=codigo,
                reason_key=OFF_CODE_KEYS[codigo],
                voice_mode=modo,
                limits=limites,
            )

        return Availability(
            available=True,
            voice_mode=modo,
            limits=limites,
            resume_until=cortada.resume_until if cortada is not None else None,
        )

    @enrutador.post(
        "/{tenant_id}/sessions",
        status_code=201,
        operation_id="openVoiceCall",
        responses=problem_responses(404, 503),
    )
    async def open_call(
        tenant_id: str,
        body: NewCall,
        request: Request,
        response: Response,
        untangle_visitor: Annotated[str | None, Cookie()] = None,
    ) -> CallOpened:
        """Abre la llamada. El microfono ya se concedio: eso pasa antes (BR1.2)."""
        aseguradora = _aseguradora(tenant_id)
        deps = current_deps()
        estado = deps.speech.availability_for(aseguradora)
        if not estado.available:
            raise ProblemError(
                status=503,
                code=ProblemCode.PROVIDER_UNAVAILABLE,
                title="Voice is off for this tenant",
            )
        if await _techo_cerrado():
            raise ProblemError(
                status=503,
                code=ProblemCode.BUDGET_EXHAUSTED,
                title="The voice budget is exhausted",
            )

        resumen = await _clave_del_visitante(aseguradora, untangle_visitor, request, response)
        ahora = _ahora()
        idioma = body.language or tenancy.require(aseguradora).default_language

        # Lo retomable se mira **antes de cobrar**: una retoma no gasta el carril de
        # la conexion y si el del sitio (BR1.3), y quien lo dice es `lanes_for`.
        cortada = await voz.find_resumable(
            tenant_id=aseguradora, visitor_key_digest=resumen, now=ahora
        )
        corte = (
            admission.CutCall(case_id=cortada.case_id, ended_at=cortada.ended_at)
            if cortada is not None and cortada.case_id is not None and cortada.ended_at is not None
            else None
        )
        retoma = admission.resumable_case(
            corte,
            window_seconds=tenancy.require(aseguradora).call.resume_window_seconds,
            now=ahora,
        )
        # **La ventana del reinicio, y solo para lo nuevo** (BR3.2, BR3.3 de U20).
        # Se mira con la retoma ya resuelta y **antes de cobrar los carriles**:
        # una llamada que no se va a abrir no gasta el cupo de nadie, y la que
        # retoma un caso abierto se admite igual, que es lo que BR3.3 pide.
        if retoma is None and not await _la_demo_acepta_casos_nuevos():
            raise ProblemError(
                status=503,
                code=ProblemCode.DEMO_CLOSED,
                title="The demo is not accepting new cases",
            )
        await _cobrar_los_carriles(resumen=resumen, resumes=retoma is not None, now=ahora)

        # El modo se decide **antes** de abrir y para toda la llamada (BR5.7), con
        # el identificador a la vista para que su decision quede en el rastro a
        # nombre de esta llamada.
        call_id = voz.new_call_id()
        modo = await spend.reserve_primary_voice(call_id, now=ahora)
        llamada = await voz.open_call(
            tenant_id=aseguradora,
            visitor_key_digest=resumen,
            language=idioma,
            voice_mode=modo,
            now=ahora,
            call_id=call_id,
        )

        # El caso nace **antes** de la primera palabra, y esa es la diferencia con
        # el chat: la divulgacion se registra contra un caso y va antes de
        # cualquier pregunta (BR2.1, BR2.3). Si ya hay uno retomable, la llamada
        # arranca sobre el; decir que no se resuelve en el ciclo, con un caso
        # nuevo y el anterior intacto (BR6.4).
        case_id = (
            retoma
            if retoma is not None
            else await voz.open_for_call(aseguradora, language=idioma, now=ahora)
        )
        llamada = await voz.attach_case(llamada, case_id=case_id)

        return CallOpened(
            call_id=llamada.call_id,
            case_id=llamada.case_id,
            voice_mode=llamada.voice_mode,
            max_call_seconds=tenancy.require(aseguradora).call.max_call_seconds,
            transport=Transport(
                url=f"/api/voice/{aseguradora}/socket",
                token=voz.issue(llamada.call_id, signing_key=deps.token_signing_key, now=ahora),
                encoding=SPEECH_AUDIO.encoding.value,
                sample_rate_hz=SPEECH_AUDIO.sample_rate_hz,
                channels=SPEECH_AUDIO.channels,
                frame_ms=FRAME_MS,
            ),
        )

    @enrutador.delete(
        "/{tenant_id}/sessions/{call_id}",
        status_code=204,
        operation_id="endVoiceCall",
        responses=problem_responses(404),
    )
    async def end_call(
        tenant_id: str,
        call_id: str,
        untangle_visitor: Annotated[str | None, Cookie()] = None,
    ) -> Response:
        """Cierra la llamada desde fuera del socket.

        **Una llamada de otro navegador responde igual que una que no existe**
        (CD-10): sin cookie no se resuelve ninguna clave, y un identificador que
        no es de este navegador no dice que exista.
        """
        aseguradora = _aseguradora(tenant_id)
        viva = (
            None
            if untangle_visitor is None
            else await voz.find_live(
                tenant_id=aseguradora,
                visitor_key_digest=tenancy.visitor_key_digest(untangle_visitor),
            )
        )
        if viva is None or viva.call_id != call_id:
            raise ProblemError(status=404, code=ProblemCode.NOT_FOUND, title="Unknown call")
        await voz.end_call(viva, reason=voz.EndReason.HANGUP, now=_ahora())
        return Response(status_code=204)

    @enrutador.get(
        "/{tenant_id}/sessions/{call_id}/outcome",
        operation_id="voiceCallOutcome",
        responses=problem_responses(404),
    )
    async def call_outcome(
        tenant_id: str,
        call_id: str,
        untangle_visitor: Annotated[str | None, Cookie()] = None,
    ) -> CallOutcome:
        """Donde quedo el caso de esta llamada (BR3.4).

        **La llamada de otro navegador responde igual que una que no existe**: sin
        galleta no se resuelve ninguna clave, y la busqueda lleva el resumen dentro
        de la consulta.
        """
        aseguradora = _aseguradora(tenant_id)
        llamada = (
            None
            if untangle_visitor is None
            else await voz.find_of_visitor(
                tenant_id=aseguradora,
                call_id=call_id,
                visitor_key_digest=tenancy.visitor_key_digest(untangle_visitor),
            )
        )
        if llamada is None:
            raise ProblemError(status=404, code=ProblemCode.NOT_FOUND, title="Unknown call")
        return await _desenlace(aseguradora, llamada, ahora=_ahora())

    @enrutador.post(
        "/{tenant_id}/sessions/{call_id}/handoff",
        operation_id="handOffVoiceCase",
        responses=problem_responses(404, 409),
    )
    async def hand_off(
        tenant_id: str,
        call_id: str,
        untangle_visitor: Annotated[str | None, Cookie()] = None,
    ) -> CallOutcome:
        """Pasa el caso a una persona, a peticion de quien llamo (BR3.4).

        Es la salida del caso que quedo esperando al asegurado: o vuelve dentro de
        su ventana, o lo pasa ya a un ajustador y se lleva su enlace. Sin esto, ese
        caso se queda sin salida y quien llamo sin saber que hacer.

        **Derivar es una transicion del caso y la hace U4**, con su motivo del
        conjunto cerrado: aqui no se escribe ningun estado a mano.
        """
        aseguradora = _aseguradora(tenant_id)
        ahora = _ahora()
        llamada = (
            None
            if untangle_visitor is None
            else await voz.find_of_visitor(
                tenant_id=aseguradora,
                call_id=call_id,
                visitor_key_digest=tenancy.visitor_key_digest(untangle_visitor),
            )
        )
        if llamada is None or llamada.case_id is None:
            raise ProblemError(status=404, code=ProblemCode.NOT_FOUND, title="Unknown call")

        try:
            await casos.apply_transition(
                aseguradora,
                llamada.case_id,
                CaseState.DERIVED,
                context=case_rules.TransitionContext(
                    now=ahora,
                    actor=Actor(actor_type=ActorType.INSURED, actor_id=VISITOR_ACTOR),
                    channel=Channel.VOICE,
                    derivation_reason=DerivationReason.PERSON_REQUESTED,
                ),
            )
        except (CaseClosedError, InvalidTransitionError) as error:
            # Un caso que ya no admite la derivacion --cerrado, o ya derivado-- no
            # es un error de quien pide: es que su salida ya esta tomada, y lo que
            # se devuelve es donde quedo.
            observability.emit(
                "voice.handoff_not_applicable",
                tenant_id=aseguradora,
                error_type=type(error).__name__,
            )
        return await _desenlace(aseguradora, llamada, ahora=ahora)

    @enrutador.websocket("/{tenant_id}/socket")
    async def socket(
        websocket: WebSocket,
        tenant_id: str,
        untangle_visitor: Annotated[str | None, Cookie()] = None,
    ) -> None:
        await _atender_socket(websocket, tenant_id, untangle_visitor)

    return enrutador


# --- El socket ----------------------------------------------------------------


@dataclass
class _AudioRecibido:
    """Cuanto audio mando el navegador y con que pico, sin guardar el audio.

    Existe porque «la agente no me oye» tiene dos causas que desde fuera se ven
    igual: el navegador no mando nada, o mando silencio. El 2026-10-07 una llamada
    real no dejo ni una palabra transcrita y no habia forma de saber cual de las
    dos fue. Son dos numeros, nunca muestras: el audio es la voz de una persona.
    """

    trozos: int = 0
    recibidos: int = 0
    pico: int = 0

    def anotar(self, datos: bytes) -> None:
        self.trozos += 1
        self.recibidos += len(datos)
        # PCM de 16 bits con signo; un trozo impar no es del formato y no se mide.
        if len(datos) >= 2 and len(datos) % 2 == 0:
            muestras = memoryview(datos).cast("h")
            self.pico = max(self.pico, max(muestras), -min(muestras))

    def emitir(self, *, tenant_id: TenantId, call_id: str) -> None:
        observability.emit(
            "voice.audio_received",
            tenant_id=tenant_id,
            call_id=call_id,
            chunks=self.trozos,
            seconds=round(self.recibidos / SPEECH_AUDIO.bytes_per_second, 2),
            peak=round(self.pico / 32768, 4),
        )


@dataclass
class _SocketChannel(CallChannel):
    """El transporte de C-29 sobre un WebSocket. La unica conversion de formato.

    El audio cruza en binario y el control en texto: un cuadro binario es audio y
    uno de texto es control. Meter los dos en un sobre JSON obligaria a codificar
    en base64 y a pagar un tercio mas de ancho de banda por cada trozo de 20 ms.
    """

    websocket: Socket
    #: Lo que llego del microfono, para la traza al colgar (2026-10-07).
    audio: _AudioRecibido = field(default_factory=lambda: _AudioRecibido())

    async def inbound(self) -> AsyncIterator[bytes | voz.Hangup]:
        while True:
            try:
                mensaje = await self.websocket.receive()
            except (WebSocketDisconnect, RuntimeError):
                return
            if mensaje["type"] == "websocket.disconnect":
                return
            datos = mensaje.get("bytes")
            if datos is not None:
                self.audio.anotar(datos)
                yield datos
                continue
            texto = mensaje.get("text")
            if texto is None:
                continue
            try:
                cuadro = voz.from_client(orjson.loads(texto))
            except (orjson.JSONDecodeError, voz.UnknownFrameError):
                # Un cuadro que este protocolo no conoce cierra la llamada. No se
                # salta: aceptarlo dejaria la puerta abierta a que una version
                # futura del navegador creyera estar diciendo algo que nadie oye.
                observability.emit("voice.unknown_frame")
                return
            if isinstance(cuadro, voz.Hangup):
                yield cuadro
                return

    async def send(self, frame: voz.ServerFrame) -> None:
        """Un cuadro de control, **en texto**.

        Que sea texto y el audio binario es lo unico que distingue los dos en el
        cable: sin eso, la consola recibiria el JSON de un `stop_audio` y lo
        reproduciria como si fueran muestras.
        """
        with contextlib.suppress(WebSocketDisconnect, RuntimeError):
            await self.websocket.send_text(orjson.dumps(voz.to_client(frame)).decode("utf-8"))

    async def send_audio(self, chunk: bytes) -> None:
        with contextlib.suppress(WebSocketDisconnect, RuntimeError):
            await self.websocket.send_bytes(chunk)


async def _primer_cuadro(websocket: Socket) -> str | None:
    """El token del primer cuadro de texto, o nada (BR1.4).

    Un socket que se abre y calla se suelta: esperarlo indefinidamente deja
    conexiones colgadas que nadie cierra.
    """
    try:
        async with asyncio.timeout(voz.AUTH_DEADLINE_SECONDS):
            mensaje = await websocket.receive()
    except (TimeoutError, WebSocketDisconnect, RuntimeError):
        return None
    texto = mensaje.get("text")
    if texto is None:
        return None
    try:
        cuadro = voz.from_client(orjson.loads(texto))
    except (orjson.JSONDecodeError, voz.UnknownFrameError):
        return None
    return cuadro.token if isinstance(cuadro, voz.Auth) else None


async def _autenticar(
    websocket: Socket, tenant_id: TenantId, visitor_key: str | None
) -> voz.CallSession | None:
    """La llamada de este socket, si el token la abre ahora (BR1.4, BR1.5).

    Las cuatro formas de token malo --ausente, vencido, de otra llamada,
    alterado-- se cierran **igual** hacia afuera. El motivo exacto va a la traza
    del servidor, que es donde sirve: un token alterado y uno vencido son
    incidentes distintos para quien opera y la misma respuesta para quien prueba.
    """
    token = await _primer_cuadro(websocket)
    viva = (
        None
        if visitor_key is None
        else await voz.find_live(
            tenant_id=tenant_id, visitor_key_digest=tenancy.visitor_key_digest(visitor_key)
        )
    )
    if viva is None:
        observability.emit(
            "voice.socket_rejected", tenant_id=tenant_id, reason=voz.TokenRejection.MISSING.value
        )
        return None

    veredicto = voz.verify(
        token, call_id=viva.call_id, signing_key=current_deps().token_signing_key, now=_ahora()
    )
    if not veredicto.accepted:
        observability.emit(
            "voice.socket_rejected",
            tenant_id=tenant_id,
            reason=veredicto.rejection.value if veredicto.rejection else "",
        )
        return None
    return viva


async def _atender_socket(websocket: Socket, tenant_id: str, visitor_key: str | None) -> None:
    """El apreton de manos y, si cuadra, la llamada entera."""
    await websocket.accept()
    try:
        aseguradora = _aseguradora(tenant_id)
    except ProblemError:
        await websocket.close(code=CLOSE_UNAUTHENTICATED)
        return

    viva = await _autenticar(websocket, aseguradora, visitor_key)
    if viva is None:
        await websocket.close(code=CLOSE_UNAUTHENTICATED)
        return

    canal = _SocketChannel(websocket=websocket)
    llamada = await voz.mark_live(viva)
    await canal.send(voz.State(voz.CallState.LIVE))

    config = tenancy.require(aseguradora)
    deps = current_deps()
    motor = voz.CallEngine(
        call=llamada,
        config=config,
        handle_turn=deps.handle_turn,
        understand=deps.understand_turn,
    )
    if viva.case_id is not None:
        # El caso que la llamada trae puede ser uno cortado que este navegador
        # dejo a medias: si lo es, la oferta de continuar va **despues** de la
        # apertura completa (BR6.2), y quien la compone es el motor.
        cortada = await voz.find_resumable(
            tenant_id=aseguradora,
            visitor_key_digest=llamada.visitor_key_digest,
            now=llamada.started_at,
        )
        if cortada is not None:
            await motor.look_for_resumable(cortada)

    ciclo = CallRunner(
        engine=motor,
        channel=canal,
        speech=deps.speech,
        now=_ahora,
        max_call=timedelta(seconds=config.call.max_call_seconds),
        warn_at=timedelta(seconds=config.call.warn_at_seconds),
        # La muletilla es de la llamada de verdad: las evaluaciones no la quieren, porque
        # depende de cuanto tarda el modelo y haria que dos corridas del mismo commit
        # no dijeran lo mismo.
        filler_after=FILLER_AFTER,
    )
    # Todo lo que la llamada gaste --transcripcion, voz y modelo-- queda a nombre
    # de su caso y de esta llamada, para que la telemetria diga cuanto costo.
    with spend_attribution.attributed(
        tenant_id=aseguradora, case_id=llamada.case_id, call_id=llamada.call_id
    ):
        motivo = await ciclo.run()

    # Un corte deja el caso retomable; colgar, no. La ventana la decide la
    # configuracion y entra por argumento, porque quien la fija es U17 (BR6.1).
    # Un fallo tambien: quien perdio la llamada por una caida de la voz puede
    # volver a llamar y seguir donde iba (2026-10-11). Y dejar el caso guardado a
    # peticion de la persona: la despedida le dijo hasta cuando, y tiene que ser cierto.
    ventana = (
        timedelta(seconds=config.call.resume_window_seconds)
        if motivo in (voz.EndReason.DROPPED, voz.EndReason.ERROR, voz.EndReason.SAVED)
        else None
    )
    with contextlib.suppress(voz.CallNotFoundError):
        await voz.end_call(motor.call, reason=motivo, now=_ahora(), resume_window=ventana)
    await _resolver_la_revision(deps, motor.call, aseguradora)
    await canal.send(voz.Ended(reason=motivo))
    canal.audio.emitir(tenant_id=aseguradora, call_id=llamada.call_id)
    # Las dos puntas pueden haber cerrado ya: el navegador al colgar, o la
    # aplicacion si `send` cerro el canal. Cerrar otra vez levantaba una excepcion
    # sin atrapar en cada llamada colgada (traza del 2026-10-07).
    if websocket.client_state is WebSocketState.CONNECTED:
        with contextlib.suppress(RuntimeError, WebSocketDisconnect):
            await websocket.close()


# --- La superficie ------------------------------------------------------------


async def _sonda() -> None:
    """Que la voz responde: una consulta que no toca ninguna fila (BR5.2).

    No llama al reconocedor, no sintetiza nada, no gasta y no consume el limite de
    ningun visitante. Lo unico que distingue "la voz esta en pie" de "la voz esta
    caida" es que su tabla conteste.
    """
    tenant_id = tenancy.available_ids()[0]
    async with db.session_for(tenant_id) as sesion:
        await db.fetch_one(sesion, "SELECT 1 AS ok FROM call_session LIMIT 1")


def surfaces() -> tuple[SurfaceSpec, ...]:
    """La consola de llamada, una por aseguradora (C-24, F8).

    **Se monta ahora y no en la tanda 5**, aunque el servidor estuviera entero
    desde entonces: el inicio dibuja el boton de una superficie en cuanto esta
    montada, y hasta esta tanda ese boton llevaba a una pantalla que no existia.
    Ofrecer una capacidad que no esta construida es lo que prohibe la regla del
    proyecto, y la sonda nace con ella por la otra: una funcion sin llamador de
    produccion es la forma de defecto que mas ha costado aqui.
    """
    return (
        SurfaceSpec(
            surface_id=SurfaceId.VOICE_CONSOLE,
            owning_unit="u16-voice-call",
            public=True,
            per_tenant=True,
            probe=SurfaceProbe(check=_sonda, timeout_ms=PROBE_TIMEOUT_MS),
        ),
    )


__all__ = [
    "COOKIE",
    "Availability",
    "CallLimits",
    "CallOpened",
    "NewCall",
    "Socket",
    "Transport",
    "VoiceDeps",
    "VoiceNotInstalledError",
    "VoicePlatform",
    "current_deps",
    "install",
    "reset",
    "router",
    "surfaces",
]
