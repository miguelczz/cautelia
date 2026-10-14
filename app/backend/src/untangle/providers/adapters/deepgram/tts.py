"""La voz de respaldo: Aura-2 de Deepgram por HTTP (C-16 `TextToSpeech`, ADR-008).

Por HTTP en streaming y no por WebSocket porque es **el camino que se midio**:
609 ms de mediana al primer audio en el experimento 1. El audio llega a trozos
en el formato unico (BR4.1), y se entrega en muestras enteras.

Recibe el texto **ya redactado** (`Redacted`): lo que se sintetiza va hacia una
persona y paso antes por el punto unico de salida. El adaptador no lo lee, no lo
registra y no lo guarda; lo manda y cuenta sus caracteres para el gasto.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from typing import TYPE_CHECKING

from untangle.base import ProviderErrorKind, ProviderName, UnitKind, Use
from untangle.providers.adapters.deepgram import protocol
from untangle.providers.adapters.speech_common import (
    SpeechCall,
    SpeechMisconfiguredError,
    WholeSamples,
)
from untangle.providers.ports import SpendGate, TextToSpeech, UsageSink, VoiceRef
from untangle.providers.speech_wire import SpeechCaller, SpeechRequest, WireRejectedError
from untangle.providers.transport import CallTimeouts, TransportError

if TYPE_CHECKING:
    from untangle.compliance.redaction.api import Redacted

__all__ = ["DeepgramAuraTextToSpeech"]

PROVIDER = ProviderName.DEEPGRAM


class DeepgramAuraTextToSpeech(TextToSpeech):
    """Sintetizar con una voz de Aura-2. Atiende cualquier voz de Deepgram configurada."""

    def __init__(
        self,
        caller: SpeechCaller,
        *,
        gate: SpendGate,
        usage: UsageSink,
        timeouts: CallTimeouts,
    ) -> None:
        self._caller = caller
        self._gate = gate
        self._usage = usage
        self._timeouts = timeouts

    async def synthesize(self, text: Redacted, *, voice: VoiceRef) -> AsyncIterator[bytes]:
        if voice.provider is not PROVIDER:
            msg = (
                f"la voz es de '{voice.provider.value}' y este es el adaptador de "
                f"'{PROVIDER.value}': la raiz de composicion esta cableada al reves"
            )
            raise SpeechMisconfiguredError(msg)

        llamada = SpeechCall(
            provider=PROVIDER,
            model=voice.model,
            use=Use.VOICE,
            unit_kind=UnitKind.CHARACTERS,
            gate=self._gate,
            usage=self._usage,
        )
        await llamada.open()

        peticion = SpeechRequest(
            path=protocol.SPEAK_PATH,
            query=protocol.speak_query(voice),
            body={"text": text},
            connect_timeout_ms=self._timeouts.connect_timeout_ms,
            read_timeout_ms=self._timeouts.read_timeout_ms,
        )
        aceptada = False
        muestras = WholeSamples()
        entregados = 0
        try:
            async with self._caller.stream_post(
                peticion, provider=PROVIDER, use=Use.VOICE
            ) as flujo:
                aceptada = True
                if not protocol.is_pcm_audio(flujo.content_type):
                    raise llamada.failure(ProviderErrorKind.INVALID_RESPONSE)
                async for trozo in flujo.chunks():
                    completo = muestras.feed(trozo)
                    if completo:
                        entregados += len(completo)
                        yield completo
            if entregados == 0 or muestras.pending:
                # Un 200 sin audio, o con media muestra al final, no es el contrato.
                raise llamada.failure(ProviderErrorKind.INVALID_RESPONSE)
        except WireRejectedError as rechazo:
            raise llamada.from_rejection(rechazo, says_exhausted=protocol.says_exhausted) from None
        except TransportError as fallo:
            raise llamada.from_transport(fallo) from None
        finally:
            # Aceptada, se cobran los caracteres que se mandaron, llegara o no todo
            # el audio. Rechazada antes de abrir, no consumio nada.
            await llamada.report(Decimal(len(text)) if aceptada else Decimal(0))
