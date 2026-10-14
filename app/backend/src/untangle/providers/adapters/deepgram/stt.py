"""Transcribir en streaming con Deepgram `nova-3` (C-16 `SpeechToText`, ADR-007).

## El orden de una transcripcion

1. **El techo**, antes de abrir nada (BR5.1).
2. **El canal**, con la consulta del modelo de esa aseguradora.
3. **Dos cosas a la vez**: una tarea sube el audio que entrega U16 mientras el
   flujo principal baja los resultados y los entrega como `Transcript`, parciales
   y finales, con la senal de voz `SpeechStarted` entre ellos. Tienen que ir a la vez
   porque la persona sigue hablando mientras Deepgram ya contesta.
4. **El cierre documentado**: acabado el audio se manda `Finalize`, se espera la
   respuesta marcada `from_finalize` y se manda `CloseStream`.
5. **El gasto**: los segundos de audio que se subieron, siempre, tambien si fallo.

## Cuando una espera es un tiempo agotado

Mientras la persona habla puede no llegar nada durante un rato, y eso es normal:
el canal se consulta con una espera corta y el silencio no cuenta. El tiempo
maximo de lectura del uso `voice` empieza a contar **cuando se mando
`Finalize`**, porque a partir de ahi lo unico que falta es la respuesta, y es la
cola que la persona espera (168 ms de mediana en el experimento 1).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

from untangle.base import Locale, ProviderErrorKind, ProviderName, UnitKind, Use
from untangle.providers.adapters.deepgram import protocol
from untangle.providers.adapters.speech_common import (
    SpeechCall,
    SpeechMisconfiguredError,
    audio_seconds,
)
from untangle.providers.ports import ListenEvent, SpeechToText, SpendGate, Transcript, UsageSink
from untangle.providers.speech_wire import (
    DuplexChannel,
    SpeechCaller,
    SpeechRequest,
    WireClosedError,
    WireRejectedError,
)
from untangle.providers.transport import CallTimeouts, TransportError
from untangle.providers.voice_availability import SpeechModel

__all__ = ["DeepgramSpeechToText"]

PROVIDER = ProviderName.DEEPGRAM

#: Cada cuanto se mira el canal mientras llega el audio. Corto para que un
#: resultado no espere, y sin consecuencia sobre el tiempo maximo, que se mide
#: con el reloj y no contando esperas.
_ESPERA_S = 0.05


@dataclass
class _Enviado:
    """Cuanto audio subio, para el gasto. Lo escribe la tarea que sube."""

    bytes: int = 0


class DeepgramSpeechToText(SpeechToText):
    """Transcribir con Deepgram. Una instancia por modelo de transcripcion configurado."""

    def __init__(  # noqa: PLR0913 -- seis dependencias inyectadas, ninguna derivable de otra
        self,
        caller: SpeechCaller,
        *,
        model: SpeechModel,
        gate: SpendGate,
        usage: UsageSink,
        timeouts: CallTimeouts,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if model.provider is not PROVIDER:
            msg = (
                f"el modelo de transcripcion es de '{model.provider.value}' y este es el "
                f"adaptador de '{PROVIDER.value}': la raiz de composicion esta cableada al reves"
            )
            raise SpeechMisconfiguredError(msg)
        self._caller = caller
        self._model = model
        self._gate = gate
        self._usage = usage
        self._timeouts = timeouts
        self._reloj = clock

    async def stream(
        self, audio: AsyncIterator[bytes], *, language: Locale
    ) -> AsyncIterator[ListenEvent]:
        llamada = SpeechCall(
            provider=PROVIDER,
            model=self._model.model,
            use=Use.VOICE,
            unit_kind=UnitKind.AUDIO_SECONDS,
            gate=self._gate,
            usage=self._usage,
        )
        await llamada.open()

        peticion = SpeechRequest(
            path=protocol.LISTEN_PATH,
            query=protocol.listen_query(self._model, language),
            connect_timeout_ms=self._timeouts.connect_timeout_ms,
            read_timeout_ms=self._timeouts.read_timeout_ms,
        )
        enviado = _Enviado()
        try:
            async with self._caller.open_duplex(
                peticion, provider=PROVIDER, use=Use.VOICE
            ) as canal:
                emisor = asyncio.create_task(_subir(canal, audio, enviado))
                try:
                    async for trozo in self._bajar(canal, emisor, llamada):
                        yield trozo
                finally:
                    if not emisor.done():
                        emisor.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await emisor
        except WireRejectedError as rechazo:
            raise llamada.from_rejection(rechazo, says_exhausted=protocol.says_exhausted) from None
        except TransportError as fallo:
            raise llamada.from_transport(fallo) from None
        except WireClosedError as cierre:
            raise llamada.from_close(cierre) from None
        finally:
            # Siempre, tambien si fallo: el audio que subio es audio que Deepgram
            # cobra, y una fila que faltara dejaria el gasto por debajo del real.
            await llamada.report(audio_seconds(enviado.bytes))

    async def _bajar(
        self,
        canal: DuplexChannel,
        emisor: asyncio.Task[None],
        llamada: SpeechCall,
    ) -> AsyncIterator[ListenEvent]:
        """Los resultados y las senales de voz, hasta la respuesta forzada por `Finalize`."""
        limite: float | None = None
        while True:
            if limite is None and _termino_de_subir(emisor):
                limite = self._reloj() + self._timeouts.read_timeout_ms / 1000

            mensaje = await canal.receive(timeout_s=_ESPERA_S)
            if mensaje is None:
                if limite is not None and self._reloj() >= limite:
                    raise llamada.failure(ProviderErrorKind.TIMEOUT)
                continue

            datos = _decodificar(mensaje.text, llamada)
            tipo = datos.get("type")
            if tipo == "SpeechStarted":
                senal = protocol.parse_speech_started(datos)
                if senal is not None:
                    yield senal
                continue
            if tipo != "Results":
                # `Metadata`, `UtteranceEnd`: no son texto.
                continue
            transcripcion = _resultado(datos, llamada)
            if transcripcion is not None:
                yield transcripcion
            if datos.get("from_finalize") is True:
                await canal.send_text(protocol.CLOSE_STREAM)
                return


def _termino_de_subir(emisor: asyncio.Task[None]) -> bool:
    """Si la tarea que sube ya acabo. Si acabo fallando, su fallo sale aqui."""
    if not emisor.done():
        return False
    fallo = emisor.exception()
    if fallo is not None:
        raise fallo
    return True


def _resultado(datos: dict[str, object], llamada: SpeechCall) -> Transcript | None:
    try:
        return protocol.parse_results(datos)
    except protocol.InvalidMessageError:
        raise llamada.failure(ProviderErrorKind.INVALID_RESPONSE) from None


async def _subir(canal: DuplexChannel, audio: AsyncIterator[bytes], enviado: _Enviado) -> None:
    """Sube el audio tal como llega y, al acabarse, pide el resultado forzado."""
    async for trozo in audio:
        if trozo:
            await canal.send_bytes(trozo)
            enviado.bytes += len(trozo)
    await canal.send_text(protocol.FINALIZE)


def _decodificar(texto: str | None, llamada: SpeechCall) -> dict[str, object]:
    """Un mensaje del canal como objeto JSON. Deepgram no manda binario de vuelta."""
    if texto is None:
        raise llamada.failure(ProviderErrorKind.INVALID_RESPONSE)
    try:
        datos = json.loads(texto)
    except ValueError:
        raise llamada.failure(ProviderErrorKind.INVALID_RESPONSE) from None
    if not isinstance(datos, dict):
        raise llamada.failure(ProviderErrorKind.INVALID_RESPONSE)
    return datos
