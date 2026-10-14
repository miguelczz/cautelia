"""La voz principal: Catalina en Cartesia `sonic-3.6` (C-16 `TextToSpeech`, ADR-008).

Por WebSocket, que es la API principal de Cartesia y la que da el primer audio
sin esperar a que se genere todo (281 ms de mediana en el experimento 1). Un
mensaje sube con el texto ya redactado; los trozos de audio bajan en base64 y se
entregan decodificados, en el formato unico y en muestras enteras (BR4.1).

El tiempo maximo de lectura del uso `voice` se aplica a **cada** espera: al
primer trozo y a cada uno de los siguientes. Si Cartesia deja de mandar a mitad
de una frase, el turno no puede quedarse callado esperando.

## Dos formas de usarlo

- `synthesize`: una frase, un canal. Abre el WebSocket, dice la frase y lo cierra.
  Es para quien dice una sola (`voice_cli say`, las pruebas de contrato).
- `open_session`: **un canal para toda la llamada.** Conectar desde Colombia
  (TCP, TLS y apertura del WebSocket) cuesta de 0,7 a 0,8 s, y pagado delante de
  cada frase --apertura, muletilla, respuesta-- es lo que mas se oia. El protocolo
  admite muchas generaciones por la misma conexion, cada una con su `context_id`,
  y la sesion las sintetiza una detras de otra.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Collection
from contextlib import AbstractAsyncContextManager, AsyncExitStack, aclosing, asynccontextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from untangle import observability
from untangle.base import ProviderErrorKind, ProviderName, UnitKind, Use
from untangle.providers.adapters.cartesia import protocol
from untangle.providers.adapters.speech_common import (
    CODIGO_DE_PAGO,
    SpeechCall,
    SpeechMisconfiguredError,
    WholeSamples,
    kind_for_status,
)
from untangle.providers.ports import (
    BudgetExhausted,
    SpendGate,
    TextToSpeech,
    UsageSink,
    VoiceRef,
)
from untangle.providers.speech_wire import (
    DuplexChannel,
    SpeechCaller,
    SpeechRequest,
    WireClosedError,
    WireMessage,
    WireRejectedError,
)
from untangle.providers.transport import CallTimeouts, TransportError

if TYPE_CHECKING:
    from untangle.compliance.redaction.api import Redacted

__all__ = ["CartesiaSpeechSession", "CartesiaTextToSpeech", "SpeechSessionClosedError"]

PROVIDER = ProviderName.CARTESIA

#: Cuantas veces se reabre el canal para una misma frase cuando el proveedor lo
#: cerro mientras estaba ocioso. Una: si tambien falla reabriendo, es el error de
#: siempre, no un bucle.
MAX_REOPENS_PER_PHRASE = 1

#: El evento por frase de la sesion: cuanto tardo el primer trozo de audio desde
#: que se pidio la frase, y si la conexion ya estaba abierta. Sin texto.
FIRST_CHUNK_EVENT = "voice.tts_first_chunk"
CONNECTION_REUSED = "reused"
CONNECTION_OPENED = "opened"

#: Un precalentamiento que no pudo abrir el canal. No es un fallo de la llamada:
#: la primera frase lo vuelve a intentar y, si falla, da su error de siempre.
WARMUP_FAILED_EVENT = "providers.speech_warmup_failed"
CLOSE_FAILED_EVENT = "providers.speech_channel_close_failed"
#: Cuanto se espera, como mucho, a que el proveedor conteste el cierre de un canal.
CLOSE_TIMEOUT_S = 3.0


def _nunca_agotado(_: object) -> bool:
    """Cartesia dice "se acabo el cupo" con el 402, que ya se reconoce sin cuerpo."""
    return False


class SpeechSessionClosedError(RuntimeError):
    """Se pidio una frase a una sesion que ya se cerro. Es un fallo de quien la usa."""


def _llamada(voice: VoiceRef, *, gate: SpendGate, usage: UsageSink) -> SpeechCall:
    """Una llamada de voz --techo, gasto y errores-- para una frase de esta voz."""
    if voice.provider is not PROVIDER:
        msg = (
            f"la voz es de '{voice.provider.value}' y este es el adaptador de "
            f"'{PROVIDER.value}': la raiz de composicion esta cableada al reves"
        )
        raise SpeechMisconfiguredError(msg)
    return SpeechCall(
        provider=PROVIDER,
        model=voice.model,
        use=Use.VOICE,
        unit_kind=UnitKind.CHARACTERS,
        gate=gate,
        usage=usage,
    )


def _peticion(timeouts: CallTimeouts) -> SpeechRequest:
    return SpeechRequest(
        path=protocol.TTS_PATH,
        connect_timeout_ms=timeouts.connect_timeout_ms,
        read_timeout_ms=timeouts.read_timeout_ms,
    )


class CartesiaTextToSpeech(TextToSpeech):
    """Sintetizar con una voz de Cartesia. Hoy, Catalina en los dos idiomas."""

    def __init__(
        self,
        caller: SpeechCaller,
        *,
        gate: SpendGate,
        usage: UsageSink,
        timeouts: CallTimeouts,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._caller = caller
        self._gate = gate
        self._usage = usage
        self._timeouts = timeouts
        self._clock = clock

    async def synthesize(self, text: Redacted, *, voice: VoiceRef) -> AsyncIterator[bytes]:
        llamada = _llamada(voice, gate=self._gate, usage=self._usage)
        await llamada.open()

        contexto = uuid.uuid4().hex
        enviada = False
        try:
            async with self._caller.open_duplex(
                _peticion(self._timeouts), provider=PROVIDER, use=Use.VOICE
            ) as canal:
                await canal.send_text(
                    protocol.generation_message(text, voice=voice, context_id=contexto)
                )
                enviada = True
                async for trozo in _audio(canal, contexto, llamada, self._timeouts):
                    yield trozo
        except WireRejectedError as rechazo:
            raise llamada.from_rejection(rechazo, says_exhausted=_nunca_agotado) from None
        except TransportError as fallo:
            raise llamada.from_transport(fallo) from None
        except WireClosedError as cierre:
            raise llamada.from_close(cierre) from None
        finally:
            # Salido el mensaje, se cuentan sus caracteres aunque Cartesia conteste
            # con un error: no hay forma de saber si llego a consumir, y el lado
            # conservador es contar de mas, porque el techo existe para no pasarse.
            # Si no llego a salir --el canal no abrio--, no consumio nada.
            await llamada.report(Decimal(len(text)) if enviada else Decimal(0))

    def open_session(self) -> AbstractAsyncContextManager[CartesiaSpeechSession]:
        """Un canal abierto para varias frases seguidas; se cierra al salir del contexto.

        Intenta abrir el canal **al entrar**, para que la primera frase tambien se
        ahorre la conexion. Si no puede, no falla: lo reintenta la primera frase.
        """
        return self._sesion()

    @asynccontextmanager
    async def _sesion(self) -> AsyncIterator[CartesiaSpeechSession]:
        sesion = CartesiaSpeechSession(
            self._caller,
            gate=self._gate,
            usage=self._usage,
            timeouts=self._timeouts,
            clock=self._clock,
        )
        try:
            await sesion.warm()
            yield sesion
        finally:
            await sesion.close()


@dataclass
class _Frase:
    """Lo que una frase de la sesion lleva consigo mientras se dice."""

    text: Redacted
    llamada: SpeechCall
    contexto: str
    mensaje: str
    pedida: float
    #: Cuantas veces salio el mensaje: cada una pudo consumir caracteres.
    enviadas: int = 0
    entregado: bool = False
    completa: bool = False
    #: Quien la leia dejo de leerla (la interrumpieron, o cancelaron la tarea): no fallo.
    abandonada: bool = False


class CartesiaSpeechSession(TextToSpeech):
    """Un canal de Cartesia que sintetiza una frase detras de otra, una a la vez.

    Cada frase conserva lo que garantiza `synthesize`: el techo de gasto se
    consulta antes de tocar el canal, los caracteres se reportan despues aunque la
    frase falle, los errores del proveedor salen en la taxonomia cerrada y el audio
    sale en muestras enteras. Lo que cambia es que el canal sobrevive a la frase.

    **Lo que pasa con una frase que no termina.** Hay dos maneras y no se tratan igual:

    - *La dejaron de leer* --la persona interrumpio a la agente, o cancelaron la tarea--: el
      canal **sigue abierto** para las frases que vienen. Cartesia no puede parar una
      generacion que ya empezo (su `cancel` solo detiene las que aun no arrancan), asi que
      lo que le quedaba por mandar de esa frase sigue llegando por el mismo canal; se
      recuerda su `context_id` y todo mensaje suyo se ignora. Cerrar el canal aqui costaria
      una conexion nueva (0,7 a 0,8 s) justo en la frase que sigue a una interrupcion.
    - *Fallo* --un error del proveedor, un tiempo agotado, un mensaje roto--: el canal queda
      en un estado que no se sabe, y se cierra; la frase siguiente abre otro.

    **Si el proveedor cierra el canal entre frases** (por ocio, por ejemplo), la
    frase que lo encuentra cerrado lo reabre una vez y sigue, sin que quien llama lo
    note. Solo si no habia entregado audio todavia: media frase repetida no se
    arregla reabriendo. Si falla al reabrir, es el mismo error que daria `synthesize`.

    **Una frase a la vez.** Quien pide dos juntas espera: la segunda empieza cuando
    la primera termina o se cierra. Quien deja de leer una frase a medias debe cerrar
    su iterador (`aclose`) antes de pedir otra, o esa espera no termina.
    """

    def __init__(
        self,
        caller: SpeechCaller,
        *,
        gate: SpendGate,
        usage: UsageSink,
        timeouts: CallTimeouts,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._caller = caller
        self._gate = gate
        self._usage = usage
        self._timeouts = timeouts
        self._clock = clock
        self._turno = asyncio.Lock()
        self._pila: AsyncExitStack | None = None
        self._canal: DuplexChannel | None = None
        #: Los `context_id` de las frases ya dichas o abandonadas en el canal abierto: lo que
        #: llegue con uno de ellos --un `flush_done` tardio, lo que quedaba de una frase
        #: interrumpida-- no es de la frase en curso y se ignora.
        self._ignorados: set[str] = set()
        self._cerrada = False

    async def warm(self) -> None:
        """Abre el canal antes de la primera frase, si el techo lo permite y se puede.

        El techo se consulta aqui tambien: tocar la red con el techo cerrado es
        justo lo que la regla prohibe. Nada de lo que falle aqui es un fallo de la
        llamada --el canal queda sin abrir y lo intenta la primera frase--.
        """
        async with self._turno:
            if self._canal is not None or self._cerrada:
                return
            try:
                await self._gate.ensure_open(provider=PROVIDER, use=Use.VOICE)
                await self._abrir_canal()
            except (BudgetExhausted, TransportError, WireRejectedError) as fallo:
                observability.emit(
                    WARMUP_FAILED_EVENT,
                    provider=PROVIDER.value,
                    use=Use.VOICE.value,
                    error_type=type(fallo).__name__,
                )

    async def close(self) -> None:
        """Cierra el canal. No espera a la frase en curso: si hay una, su lector lo nota."""
        self._cerrada = True
        await self._soltar_canal()

    def synthesize(self, text: Redacted, *, voice: VoiceRef) -> AsyncGenerator[bytes]:
        return self._decir(text, voice)

    async def _decir(self, text: Redacted, voice: VoiceRef) -> AsyncGenerator[bytes]:
        llamada = _llamada(voice, gate=self._gate, usage=self._usage)
        contexto = uuid.uuid4().hex
        frase = _Frase(
            text=text,
            llamada=llamada,
            contexto=contexto,
            mensaje=protocol.generation_message(text, voice=voice, context_id=contexto),
            pedida=self._clock(),
        )
        async with self._turno:
            await llamada.open()
            try:
                reabiertas = 0
                while True:
                    canal, reutilizado = await self._canal_para_la_frase()
                    try:
                        async with aclosing(
                            self._una_vez(canal, frase, reutilizado=reutilizado)
                        ) as trozos:
                            async for trozo in trozos:
                                yield trozo
                        break
                    except WireClosedError:
                        if (
                            frase.entregado
                            or not reutilizado
                            or reabiertas >= MAX_REOPENS_PER_PHRASE
                        ):
                            raise
                        reabiertas += 1
                        await self._soltar_canal()
            except WireRejectedError as rechazo:
                raise llamada.from_rejection(rechazo, says_exhausted=_nunca_agotado) from None
            except TransportError as fallo:
                raise llamada.from_transport(fallo) from None
            except WireClosedError as cierre:
                raise llamada.from_close(cierre) from None
            except (GeneratorExit, asyncio.CancelledError):
                frase.abandonada = True
                raise
            finally:
                await self._terminar(frase)

    async def _una_vez(
        self, canal: DuplexChannel, frase: _Frase, *, reutilizado: bool
    ) -> AsyncGenerator[bytes]:
        """El mensaje por este canal y su audio, hasta `done`."""
        await canal.send_text(frase.mensaje)
        frase.enviadas += 1
        audio = _audio(
            canal, frase.contexto, frase.llamada, self._timeouts, anteriores=self._ignorados
        )
        async with aclosing(audio):
            async for trozo in audio:
                if not frase.entregado:
                    observability.emit(
                        FIRST_CHUNK_EVENT,
                        provider=PROVIDER.value,
                        ms=round((self._clock() - frase.pedida) * 1000),
                        connection=CONNECTION_REUSED if reutilizado else CONNECTION_OPENED,
                    )
                    frase.entregado = True
                yield trozo
        frase.completa = True

    async def _terminar(self, frase: _Frase) -> None:
        """Lo que queda de la frase, termine como termine."""
        try:
            if frase.completa or frase.abandonada:
                # El canal sigue sano. Lo que Cartesia aun mande de esta frase se ignora.
                self._ignorados.add(frase.contexto)
            else:
                await self._soltar_canal()
        finally:
            # Igual que `synthesize`: lo que salio se cuenta aunque falle, del lado
            # conservador. Si la frase hubo de reenviarse tras un cierre cuentan los
            # dos envios: no se sabe si el primero consumio.
            await frase.llamada.report(Decimal(len(frase.text) * frase.enviadas))

    async def _canal_para_la_frase(self) -> tuple[DuplexChannel, bool]:
        """El canal abierto, o uno nuevo. Devuelve tambien si ya estaba abierto."""
        if self._canal is not None:
            return self._canal, True
        return await self._abrir_canal(), False

    async def _abrir_canal(self) -> DuplexChannel:
        if self._cerrada:
            msg = "la sesion de sintesis ya se cerro: la llamada termino"
            raise SpeechSessionClosedError(msg)
        pila = AsyncExitStack()
        canal = await pila.enter_async_context(
            self._caller.open_duplex(_peticion(self._timeouts), provider=PROVIDER, use=Use.VOICE)
        )
        self._pila, self._canal = pila, canal
        self._ignorados = set()
        return canal

    async def _soltar_canal(self) -> None:
        """Cierra el canal si hay uno. Un canal que ya fallo no tiene mas que decir."""
        pila, self._pila, self._canal = self._pila, None, None
        if pila is None:
            return
        try:
            # Con tope: el cierre del WebSocket espera la respuesta del proveedor, y la
            # llamada no puede quedarse sin terminar por un canal que ya no se usa.
            async with asyncio.timeout(CLOSE_TIMEOUT_S):
                await pila.aclose()
        except Exception as fallo:  # noqa: BLE001 -- cerrar un canal que ya se descarta no puede tapar el error de la frase que lo descarto
            observability.emit(
                CLOSE_FAILED_EVENT,
                provider=PROVIDER.value,
                use=Use.VOICE.value,
                error_type=type(fallo).__name__,
            )


async def _audio(
    canal: DuplexChannel,
    contexto: str,
    llamada: SpeechCall,
    timeouts: CallTimeouts,
    *,
    anteriores: Collection[str] = (),
) -> AsyncGenerator[bytes]:
    """Los trozos de audio hasta `done`, en muestras enteras."""
    muestras = WholeSamples()
    entregados = 0
    espera = timeouts.read_timeout_ms / 1000
    while True:
        marco = _leer(await canal.receive(timeout_s=espera), contexto, llamada, anteriores)
        if marco.kind == "chunk":
            completo = muestras.feed(marco.audio)
            if completo:
                entregados += len(completo)
                yield completo
        if marco.kind == "done":
            if entregados == 0 or muestras.pending:
                # Terminar sin audio, o con media muestra, no es el contrato.
                raise llamada.failure(ProviderErrorKind.INVALID_RESPONSE)
            return


def _leer(
    mensaje: WireMessage | None,
    contexto: str,
    llamada: SpeechCall,
    anteriores: Collection[str] = (),
) -> protocol.Frame:
    """El siguiente marco de esta peticion, o el error que corresponda.

    Nada que llegue a tiempo es un tiempo agotado; un binario, un JSON roto o un
    marco de otra peticion son `invalid_response`; y un marco `error` se traduce
    por su `status_code`, con el 402 como parada.
    """
    if mensaje is None:
        raise llamada.failure(ProviderErrorKind.TIMEOUT)
    if mensaje.text is None:
        raise llamada.failure(ProviderErrorKind.INVALID_RESPONSE)
    try:
        marco = protocol.parse_frame(mensaje.text, context_id=contexto, earlier=anteriores)
    except protocol.InvalidMessageError:
        raise llamada.failure(ProviderErrorKind.INVALID_RESPONSE) from None
    if marco.kind != "error":
        return marco
    if marco.status_code == CODIGO_DE_PAGO:
        raise llamada.exhausted()
    if marco.status_code is None:
        raise llamada.failure(ProviderErrorKind.INVALID_RESPONSE)
    raise llamada.failure(kind_for_status(marco.status_code))
