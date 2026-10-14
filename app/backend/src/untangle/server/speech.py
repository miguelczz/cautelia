"""La voz, cableada: adaptadores, clientes, techo, gasto y disponibilidad (U15, C-24).

Vive en `untangle.server` porque el contrato `raiz-de-composicion` dice que solo
este paquete importa `untangle.providers.adapters`. Aqui se juntan cuatro cosas
que ninguna otra pieza puede juntar:

- **el registro de los dos adaptadores de voz** --con que modelos tiene cada uno
  prueba de contrato (BR2.3)-- y su transporte de verdad;
- **los clientes del uso `voice`**, construidos por la fabrica con las claves de
  ese uso y de ningun otro (BR1.3);
- **el techo y el registro de gasto** delante de cada llamada (BR5.1): el techo
  lee la foto del presupuesto de U5 y el registro escribe en su libro mayor;
- **la disponibilidad de la voz de cada aseguradora**, decidida una sola vez al
  construir y sin preguntarle a ningun proveedor (BR2.1, BR2.2).

El resultado es `SpeechPlatform`. La raiz del proceso servido la construye al
arrancar y la deja en `app.state.speech`, que es donde U16 pregunta si la voz de
una aseguradora puede atender y pide la sintesis y la transcripcion. Los
comandos a mano (`voice:say`, `voice:contract-live`) recorren **el mismo
camino**: no hay una segunda forma de construir una voz.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Mapping, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from untangle import observability
from untangle.base import Locale, ProviderName, Use
from untangle.providers import config as provider_config
from untangle.providers.adapters import cartesia, deepgram
from untangle.providers.adapters.wire import WireTransportFactory
from untangle.providers.ceiling import CeilingGate
from untangle.providers.factory import MissingProviderKeyError, SpeechClients
from untangle.providers.ports import (
    BudgetExhausted,
    ExhaustedResource,
    ListenEvent,
    ProviderError,
    SessionTextToSpeech,
    SpeechToText,
    SpendGate,
    TextToSpeech,
    UsageSink,
    VoiceRef,
)
from untangle.providers.speech_wire import SpeechCaller, SpeechTransportFactory
from untangle.providers.transport import CallTimeouts
from untangle.providers.voice_availability import (
    SpeechAdapterInfo,
    SpeechModel,
    VoiceAvailability,
    VoiceUnavailableError,
    availability_by_tenant,
    transcription_model,
    voice_ref,
)
from untangle.server import spend_wiring
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend import attribution as spend_attribution
from untangle.telemetry.spend.models import VoiceMode
from untangle.tenancy.models import TenantConfig, TenantId, VoiceConfig

if TYPE_CHECKING:
    from untangle.compliance.redaction.api import Redacted

__all__ = [
    "PRIMARY_FAILURE_RETRY_AFTER",
    "PRIMARY_RETRY_AFTER",
    "SPEECH_ADAPTERS",
    "SpeechPlatform",
    "SpeechSession",
    "UnknownSpeechProviderError",
    "build_speech_clients",
    "build_speech_platform",
    "speech_transports",
    "synthesizer_for",
    "transcriber_for",
    "unpublished_voices",
]

#: Lo que la raiz sabe de cada adaptador de voz: con que modelos tiene prueba de
#: contrato (BR2.3). Un proveedor que no esta aqui no tiene adaptador, y una
#: aseguradora que lo nombre queda con la voz apagada (BR2.2).
SPEECH_ADAPTERS: Mapping[ProviderName, SpeechAdapterInfo] = {
    ProviderName.DEEPGRAM: deepgram.ADAPTER_INFO,
    ProviderName.CARTESIA: cartesia.ADAPTER_INFO,
}

#: Como pregunta cada adaptador "cuales de estas voces no publicas". Una consulta
#: que no cuesta; la ruta y la forma de la respuesta son protocolo de cada
#: proveedor y se quedan dentro de su adaptador (BR1.1).
type _VoiceCatalog = Callable[[SpeechCaller, Sequence[str]], Awaitable[list[str]]]

_CATALOGOS: Mapping[ProviderName, _VoiceCatalog] = {
    ProviderName.DEEPGRAM: deepgram.missing_voices,
    ProviderName.CARTESIA: cartesia.missing_voices,
}


#: Quien sintetiza una voz: el adaptador suelto de la plataforma, o el de la sesion de una
#: llamada, que para el proveedor que mantiene un canal abierto es ese canal.
type _Sintetizador = Callable[[VoiceRef], TextToSpeech]

#: Cuanto se le cree a un "no hay cupo" antes de volver a preguntarle a esa voz.
#: Preguntar no cuesta --el proveedor rechaza antes de sintetizar-- pero cada
#: pregunta fallida es un rechazo mas delante de la primera frase.
PRIMARY_RETRY_AFTER = timedelta(hours=1)

#: Cuanto se aparta la voz principal tras **cualquier otro** fallo (tiempo agotado,
#: conexion caida, 5xx, respuesta rota). Mas que la llamada mas larga --`max_call_seconds`,
#: 240 s por omision--, para que lo que le queda a la llamada que lo vio suene con una sola
#: voz: volver a la principal a media llamada la cambiaria otra vez. Y menos que
#: `PRIMARY_RETRY_AFTER` porque un fallo que no es de cupo suele pasar solo.
PRIMARY_FAILURE_RETRY_AFTER = timedelta(minutes=5)


def _ahora() -> datetime:
    return datetime.now(UTC)


@dataclass
class _FueraDeServicio:
    """Los proveedores de voz que no se usan por ahora, y hasta cuando se les cree.

    Sirve a dos cosas con plazos distintos. El cupo agotado: no se lleva la cuenta de
    los caracteres de nadie, porque una cuenta propia que se desvie de la del proveedor
    es creer que queda cupo cuando no queda (decision de Miguel del 2026-10-03). Y
    cualquier otro fallo, que se le cree unos minutos. En memoria del proceso: al
    reiniciar se le vuelve a preguntar, que es lo correcto.
    """

    hasta: dict[ProviderName, datetime] = field(default_factory=dict)

    def marcar(self, proveedor: ProviderName, ahora: datetime, *, por: timedelta) -> None:
        # Manda el plazo mas largo: un fallo corriente no acorta el de "sin cupo".
        nuevo = ahora + por
        actual = self.hasta.get(proveedor)
        self.hasta[proveedor] = nuevo if actual is None else max(actual, nuevo)

    def sigue(self, proveedor: ProviderName, ahora: datetime) -> bool:
        limite = self.hasta.get(proveedor)
        return limite is not None and ahora < limite


class UnknownSpeechProviderError(LookupError):
    """Se pidio un adaptador de voz para un proveedor que no tiene ninguno."""


def speech_transports() -> dict[ProviderName, SpeechTransportFactory]:
    """El transporte de verdad de cada proveedor de voz."""
    return {
        ProviderName.DEEPGRAM: WireTransportFactory(deepgram.ENDPOINT),
        ProviderName.CARTESIA: WireTransportFactory(cartesia.ENDPOINT),
    }


def build_speech_clients(
    settings: Settings,
    transports: Mapping[ProviderName, SpeechTransportFactory] | None = None,
) -> SpeechClients:
    """Los clientes de voz, con las claves del uso `voice` y ninguna otra (BR1.3)."""
    return SpeechClients(
        settings=settings,
        transports=transports if transports is not None else speech_transports(),
    )


def synthesizer_for(
    voice: VoiceRef,
    *,
    caller: SpeechCaller,
    gate: SpendGate,
    usage: UsageSink,
    timeouts: CallTimeouts,
) -> TextToSpeech:
    """El adaptador que sabe sintetizar esa voz. Los dos cumplen la misma interfaz (BR1.2)."""
    if voice.provider is ProviderName.CARTESIA:
        return cartesia.CartesiaTextToSpeech(caller, gate=gate, usage=usage, timeouts=timeouts)
    if voice.provider is ProviderName.DEEPGRAM:
        return deepgram.DeepgramAuraTextToSpeech(caller, gate=gate, usage=usage, timeouts=timeouts)
    msg = f"no hay adaptador de sintesis para '{voice.provider.value}'"
    raise UnknownSpeechProviderError(msg)


def transcriber_for(
    model: SpeechModel,
    *,
    caller: SpeechCaller,
    gate: SpendGate,
    usage: UsageSink,
    timeouts: CallTimeouts,
) -> SpeechToText:
    """El adaptador de transcripcion de ese modelo."""
    if model.provider is ProviderName.DEEPGRAM:
        return deepgram.DeepgramSpeechToText(
            caller, model=model, gate=gate, usage=usage, timeouts=timeouts
        )
    msg = f"no hay adaptador de transcripcion para '{model.provider.value}'"
    raise UnknownSpeechProviderError(msg)


async def unpublished_voices(caller: SpeechCaller, voices: Iterable[VoiceRef]) -> list[str]:
    """Las voces declaradas que su proveedor no publica, como `proveedor:voz`.

    Pregunta al catalogo de cada adaptador, que es una consulta que no cuesta. Un
    proveedor sin catalogo registrado no tiene adaptador, asi que ninguna de sus
    voces cuenta como publicada.
    """
    por_proveedor: dict[ProviderName, list[str]] = {}
    for voz in voices:
        por_proveedor.setdefault(voz.provider, []).append(voz.voice_id)

    faltan: list[str] = []
    for proveedor in sorted(por_proveedor, key=lambda p: p.value):
        pedidas = por_proveedor[proveedor]
        catalogo = _CATALOGOS.get(proveedor)
        ausentes = await catalogo(caller, pedidas) if catalogo is not None else pedidas
        faltan.extend(f"{proveedor.value}:{voz}" for voz in dict.fromkeys(ausentes))
    return faltan


def _plazo_de_la_caida(fallo: ProviderError | BudgetExhausted) -> timedelta | None:
    """Cuanto se aparta la voz principal tras este fallo; nulo si no se cambia de voz.

    El techo del proyecto es nulo a proposito: lo que se acabo es el presupuesto, no la
    voz, y pasar a la de respaldo seria esquivarlo.
    """
    if isinstance(fallo, ProviderError):
        return PRIMARY_FAILURE_RETRY_AFTER
    if fallo.resource is ExhaustedResource.PROVIDER_QUOTA:
        return PRIMARY_RETRY_AFTER
    return None


def _avisar_de_la_caida(
    fallo: ProviderError | BudgetExhausted,
    *,
    principal: VoiceRef,
    respaldo: VoiceRef,
    a_mitad: bool,
) -> None:
    """El evento de que la llamada siguio con la voz de respaldo (AC2.10.4).

    Lleva proveedores, el tipo del fallo, si llego a salir audio de la principal y la
    llamada cuando hay una atribuida: nunca el texto de la frase, que es de la persona.
    """
    atribucion = spend_attribution.current()
    campos: dict[str, object] = {
        "provider": principal.provider.value,
        "fallback": respaldo.provider.value,
        "mid_phrase": a_mitad,
        "call_id": None if atribucion is None else atribucion.call_id,
    }
    if isinstance(fallo, ProviderError):
        observability.emit("voice.primary_failed", error_kind=fallo.kind.value, **campos)
    else:
        observability.emit("voice.primary_out_of_quota", **campos)


@dataclass(frozen=True)
class SpeechPlatform:
    """La voz del aplicativo ya cableada. Se construye una vez y no se recarga.

    Lo que U16 usa, en proceso:

    - `availability_for(tenant_id)`: si la voz de esa aseguradora puede atender
      y, si no, con que motivo y que frase del catalogo mostrar (BR2.2);
    - `speak(...)`: sintetizar un texto ya redactado con la voz de esa
      aseguradora, en su idioma y en su modo, principal o de respaldo;
    - `speech_session(...)`: lo mismo para una llamada entera, por una sola conexion
      con el proveedor de la voz principal en vez de una por frase;
    - `transcriber(tenant_id)`: el adaptador que transcribe su audio.

    **No decide entre la voz principal y la de respaldo** --eso es de U17 antes
    de cada llamada (C-17, `reserve_primary_voice`)-- ni abre la llamada: el
    modo llega decidido. Lo que si hace es negarse a construir una voz apagada:
    pedirla levanta `VoiceUnavailableError` nombrando el motivo, en vez de dejar
    que la llamada falle a medias contra un proveedor.

    **Una excepcion, decidida por Miguel el 2026-10-03:** cuando el proveedor de
    la voz principal contesta que se le acabo el cupo, la frase se dice con la de
    respaldo y esa voz principal queda fuera hasta `PRIMARY_RETRY_AFTER`. El plan
    gratuito de la principal alcanza para unas quince llamadas al mes, y sin esto
    la llamada dieciseis terminaba con "algo fallo". No es una recarga ni salta
    ningun techo: la de respaldo pasa por el mismo techo y deja su propio gasto.
    Solo vale para el cupo **del proveedor**; el techo del proyecto sigue parando.

    **Y lo mismo con cualquier otro fallo de la principal (2026-10-13, AC2.10.4):** un
    tiempo agotado, una conexion caida, un 5xx o una respuesta rota, tambien **a mitad de
    frase**. La llamada sigue con la de respaldo y la principal queda fuera
    `PRIMARY_FAILURE_RETRY_AFTER`. Si tambien falla la de respaldo, el fallo sale: la
    llamada termina como siempre.
    """

    clients: SpeechClients
    gate: SpendGate
    usage: UsageSink
    timeouts: CallTimeouts
    availability: Mapping[TenantId, VoiceAvailability]
    voices: Mapping[TenantId, VoiceConfig]
    now: Callable[[], datetime] = _ahora
    out_of_service: _FueraDeServicio = field(default_factory=_FueraDeServicio)

    def availability_for(self, tenant_id: TenantId) -> VoiceAvailability:
        """Si la voz de esa aseguradora puede atender. Decidido al arrancar."""
        estado = self.availability.get(tenant_id)
        if estado is None:
            msg = (
                f"la aseguradora '{tenant_id}' no esta cargada en este proceso: no hay "
                "voz que consultar"
            )
            raise VoiceUnavailableError(msg)
        return estado

    def _configuracion(self, tenant_id: TenantId) -> VoiceConfig:
        estado = self.availability_for(tenant_id)
        if not estado.available:
            motivo = estado.reason.value if estado.reason is not None else "sin motivo"
            msg = (
                f"la voz de '{tenant_id}' esta apagada ({motivo}, clave '{estado.field}'): "
                "mire su disponibilidad antes de pedirla (BR2.2)"
            )
            raise VoiceUnavailableError(msg)
        return self.voices[tenant_id]

    def voice_for(self, tenant_id: TenantId, *, mode: VoiceMode, language: Locale) -> VoiceRef:
        """La voz de esa aseguradora en ese modo y ese idioma (BR2.1)."""
        return voice_ref(self._configuracion(tenant_id), mode=mode, language=language)

    def synthesizer(self, voice: VoiceRef) -> TextToSpeech:
        """El adaptador de esa voz, con el techo, el gasto y los tiempos del uso `voice`."""
        return synthesizer_for(
            voice, caller=self.clients, gate=self.gate, usage=self.usage, timeouts=self.timeouts
        )

    def speak(
        self, tenant_id: TenantId, text: Redacted, *, mode: VoiceMode, language: Locale
    ) -> AsyncIterator[bytes]:
        """El audio de ese texto con la voz de esa aseguradora, en el formato unico (BR4.1).

        La voz se resuelve **al pedirla**, no al iterar: una voz apagada falla
        aqui, antes de que nadie espere audio. Una frase suelta: abre su conexion
        y la cierra. Una llamada habla por `speech_session`.
        """
        return self._hablar(
            tenant_id, text, mode=mode, language=language, sintetizador=self.synthesizer
        )

    def _hablar(
        self,
        tenant_id: TenantId,
        text: Redacted,
        *,
        mode: VoiceMode,
        language: Locale,
        sintetizador: _Sintetizador,
    ) -> AsyncIterator[bytes]:
        voz = self.voice_for(tenant_id, mode=mode, language=language)
        if mode is not VoiceMode.PRIMARY:
            return sintetizador(voz).synthesize(text, voice=voz)
        respaldo = self.voice_for(tenant_id, mode=VoiceMode.FALLBACK, language=language)
        return self._con_respaldo(text, principal=voz, respaldo=respaldo, sintetizador=sintetizador)

    async def _con_respaldo(
        self,
        text: Redacted,
        *,
        principal: VoiceRef,
        respaldo: VoiceRef,
        sintetizador: _Sintetizador,
    ) -> AsyncIterator[bytes]:
        """La voz principal, y la de respaldo si la principal falla por lo que sea.

        Lo que se atrapa es la taxonomia cerrada del adaptador --los cuatro tipos de
        `ProviderError` y el cupo agotado del proveedor-- y nada mas: un tipo que se
        escapara de ahi es un defecto del adaptador y tiene que verse, no taparse con otra
        voz. El techo del proyecto tampoco cambia de voz: lo que se acabo es el
        presupuesto y la de respaldo gasta del mismo.

        **Si ya salio audio de la principal, la frase se repite entera en la de respaldo.**
        El adaptador no dice a que palabra llego, y recortar el texto por una estimacion
        del tiempo seria decidir al azar entre repetir y comerse palabras; repetir es lo
        honesto. Si el fallo llega con la frase ya casi dicha (el cierre del flujo, no el
        audio), la persona la oye otra vez en la otra voz: es el precio de no tener el
        dato.

        **Cada flujo se cierra aqui, en esta tarea, cuando se deja de leer**: con la sesion de
        una llamada la frase tiene el canal en exclusiva hasta que su flujo se cierra, y
        dejarlo al recolector la haria esperar a que alguien lo recoja.
        """
        caida: ProviderError | BudgetExhausted | None = None
        if not self.out_of_service.sigue(principal.provider, self.now()):
            sono = False
            try:
                async with _cerrando(
                    sintetizador(principal).synthesize(text, voice=principal)
                ) as audio:
                    async for trozo in audio:
                        sono = True
                        yield trozo
            except (ProviderError, BudgetExhausted) as fallo:
                plazo = _plazo_de_la_caida(fallo)
                if plazo is None or respaldo.provider is principal.provider:
                    raise
                self.out_of_service.marcar(principal.provider, self.now(), por=plazo)
                _avisar_de_la_caida(fallo, principal=principal, respaldo=respaldo, a_mitad=sono)
                caida = fallo
            else:
                return
        try:
            async with _cerrando(sintetizador(respaldo).synthesize(text, voice=respaldo)) as audio:
                async for trozo in audio:
                    yield trozo
        except MissingProviderKeyError:
            # La de respaldo no esta enchufada --una maquina con una sola clave de voz--: lo
            # que hay que ver es por que fallo la principal, no que falta la otra clave.
            if caida is None:
                raise
            raise caida from None

    @asynccontextmanager
    async def speech_session(
        self, tenant_id: TenantId, *, mode: VoiceMode, language: Locale
    ) -> AsyncIterator[SpeechSession]:
        """La boca de una llamada: una conexion abierta mientras dura, y cerrada al salir.

        Conectar con Cartesia desde Colombia cuesta de 0,7 a 0,8 s y `speak` lo paga en
        cada frase. Aqui se abre **una** vez, antes de la apertura, y las frases de la
        voz principal salen por ella. La voz de respaldo, Deepgram por HTTP, sigue
        pidiendose por frase, y la logica de respaldo es la de `speak`: si el canal de la
        sesion falla o se cae a mitad de llamada, la frase sale con la de respaldo y la
        principal queda fuera como con cualquier otro fallo.

        Se cierra siempre al salir del contexto, tambien cuando la llamada termina con
        un error. **Abrirla nunca hace fallar la llamada**: una voz apagada, un techo
        cerrado o un canal que no abre dejan la llamada hablando frase por frase, y el
        motivo sale con la primera frase como antes.
        """
        async with AsyncExitStack() as pila:
            persistentes: dict[ProviderName, TextToSpeech] = {}
            for voz in self._voces_de_la_llamada(tenant_id, mode=mode, language=language):
                sintetizador = self.synthesizer(voz)
                if voz.provider in persistentes or not isinstance(
                    sintetizador, SessionTextToSpeech
                ):
                    continue
                try:
                    persistentes[voz.provider] = await pila.enter_async_context(
                        sintetizador.open_session()
                    )
                except Exception as fallo:  # noqa: BLE001 -- abrir la sesion es una mejora de latencia: lo que levante no es un conjunto que este lado conozca, y la llamada habla frase por frase sin ella
                    observability.emit(
                        "voice.speech_session_open_failed",
                        provider=voz.provider.value,
                        error_type=type(fallo).__name__,
                        where=observability.failure_location(fallo),
                    )
            yield SpeechSession(self, persistentes)

    def _voces_de_la_llamada(
        self, tenant_id: TenantId, *, mode: VoiceMode, language: Locale
    ) -> list[VoiceRef]:
        """Las voces con las que puede hablar una llamada de ese modo, sin la que esta fuera
        de servicio: abrirle un canal seria gastar una conexion que se sabe que falla."""
        try:
            voces = [self.voice_for(tenant_id, mode=mode, language=language)]
            if mode is VoiceMode.PRIMARY:
                voces.append(self.voice_for(tenant_id, mode=VoiceMode.FALLBACK, language=language))
        except VoiceUnavailableError:
            return []
        ahora = self.now()
        return [voz for voz in voces if not self.out_of_service.sigue(voz.provider, ahora)]

    def transcriber(self, tenant_id: TenantId) -> SpeechToText:
        """El adaptador que transcribe el audio de las llamadas de esa aseguradora."""
        modelo = transcription_model(self._configuracion(tenant_id))
        return transcriber_for(
            modelo, caller=self.clients, gate=self.gate, usage=self.usage, timeouts=self.timeouts
        )

    def listen(
        self, tenant_id: TenantId, audio: AsyncIterator[bytes], *, language: Locale
    ) -> AsyncIterator[ListenEvent]:
        """Los parciales y finales del audio de una llamada de esa aseguradora (BR3.1), y la
        senal de que alguien empezo a hablar."""
        return self.transcriber(tenant_id).stream(audio, language=language)


class SpeechSession:
    """La boca de una llamada. Lo devuelve `SpeechPlatform.speech_session`.

    Tiene el `speak` de la plataforma, con la misma firma y la misma logica de respaldo; lo
    unico que cambia es por donde sale la voz principal: el canal que la sesion mantiene
    abierto, en vez de una conexion nueva por frase.
    """

    def __init__(
        self, platform: SpeechPlatform, persistent: Mapping[ProviderName, TextToSpeech]
    ) -> None:
        self._platform = platform
        self._persistent = persistent

    def speak(
        self, tenant_id: TenantId, text: Redacted, *, mode: VoiceMode, language: Locale
    ) -> AsyncIterator[bytes]:
        return self._platform._hablar(
            tenant_id, text, mode=mode, language=language, sintetizador=self._sintetizador
        )

    def _sintetizador(self, voz: VoiceRef) -> TextToSpeech:
        persistente = self._persistent.get(voz.provider)
        return persistente if persistente is not None else self._platform.synthesizer(voz)


@asynccontextmanager
async def _cerrando(flujo: AsyncIterator[bytes]) -> AsyncIterator[AsyncIterator[bytes]]:
    """El flujo de una frase, cerrado al dejar de leerlo aunque no se haya agotado.

    `async for` no cierra el flujo que recorre si se sale antes del final, y lo que queda
    abierto hasta que el recolector lo recoja es, con una sesion, el canal de la llamada.
    """
    try:
        yield flujo
    finally:
        cerrar = getattr(flujo, "aclose", None)
        if cerrar is not None:
            await cerrar()


def build_speech_platform(  # noqa: PLR0913 -- las costuras de prueba y de grabacion van por nombre
    settings: Settings,
    config: provider_config.ProviderPlatformConfig,
    tenants: Iterable[TenantConfig],
    *,
    transports: Mapping[ProviderName, SpeechTransportFactory] | None = None,
    gate: SpendGate | None = None,
    usage: UsageSink | None = None,
) -> SpeechPlatform:
    """La voz del aplicativo, con los valores de verdad por omision.

    Por omision, el techo lee la foto del presupuesto de U5 y el gasto va a su
    libro mayor. Las tres costuras con nombre existen para lo que no es el
    proceso servido: las pruebas sustituyen el transporte por la respuesta
    grabada y el techo por uno forzado; los comandos a mano envuelven el registro
    para poder imprimir lo que gasto la corrida y el transporte para grabar.

    Los tiempos son los del uso `voice` de `providers.yaml`: la voz no espera lo
    que espera una corrida de evaluaciones.
    """
    lista = tuple(tenants)
    uso = config.providers.for_use(Use.VOICE)
    return SpeechPlatform(
        clients=build_speech_clients(settings, transports),
        gate=gate if gate is not None else CeilingGate(spend.budget_state),
        usage=usage if usage is not None else spend_wiring.LedgerUsageSink(),
        timeouts=CallTimeouts(
            connect_timeout_ms=uso.connect_timeout_ms, read_timeout_ms=uso.read_timeout_ms
        ),
        availability=availability_by_tenant(
            lista, providers=config.providers, adapters=SPEECH_ADAPTERS
        ),
        voices={tenant.tenant_id: tenant.voice for tenant in lista},
    )
