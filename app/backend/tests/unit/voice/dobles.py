"""Los dos dobles grandes de U16: el reconocedor y la sintesis.

**Se escriben con cuidado a proposito.** La forma de defecto que mas ha costado en
este proyecto es un doble mas permisivo que la pieza real: el chat estuvo sin
poder atender a nadie con 2.363 pruebas en verde porque sus dobles aceptaban un
turno sin caso donde la pieza real lo rechaza.

Tres reglas, de `unit-test-instructions.md`:

1. **Heredan de los `Protocol` de C-16**, para que el comprobador de tipos los
   compare con la pieza real y no con lo que la prueba necesitaba.
2. **El reconocedor entrega un guion de tiempos**, con parciales, finales y
   silencios. Uno que devolviera el transcrito completo de golpe no podria
   probar la deteccion de turno, que es media unidad.
3. **Imita lo incomodo del real**: confianza nula cuando el proveedor no la
   manda, parciales que se corrigen, y transcripcion vacia cuando no se entendio.
   Si el doble siempre trajera confianza, BR3.4 no se probaria nunca.

La sintesis entrega el audio **en trozos**, porque medir una parada contra una
sintesis instantanea no mide nada.
"""

from __future__ import annotations

import itertools
from collections.abc import AsyncIterator, Iterable, Sequence
from dataclasses import dataclass, field

from untangle.base import Locale, Use
from untangle.compliance.redaction.api import Redacted
from untangle.orchestration.contracts import InboundTurn, TurnEvent
from untangle.providers.ports import (
    ExternalText,
    ListenEvent,
    SpeechStarted,
    SpeechToText,
    TextToSpeech,
    Transcript,
    VoiceRef,
    WordHypothesis,
)
from untangle.telemetry.traces import api as traces
from untangle.voice.call import TurnHandler


def palabras(
    texto: str, *, desde: float = 0.0, confianza: float | None = 0.95
) -> tuple[WordHypothesis, ...]:
    """Las palabras de una frase, con tiempos crecientes.

    `confianza=None` es el caso real que mas se olvida: el proveedor no siempre
    la manda, y nula significa "no lo dijo", nunca "salio mal" (BR3.1 de U15).
    """
    salida = []
    t = desde
    for palabra in texto.split():
        salida.append(
            WordHypothesis(
                text=ExternalText(palabra), start_s=t, end_s=t + 0.3, confidence=confianza
            )
        )
        t += 0.35
    return tuple(salida)


def parcial(texto: str, *, confianza: float | None = 0.95) -> Transcript:
    return Transcript(
        text=ExternalText(texto), is_final=False, words=palabras(texto, confianza=confianza)
    )


def final(texto: str, *, desde: float = 0.0, confianza: float | None = 0.95) -> Transcript:
    return Transcript(
        text=ExternalText(texto),
        is_final=True,
        words=palabras(texto, desde=desde, confianza=confianza),
    )


def senal(at_s: float = 0.3) -> SpeechStarted:
    """La senal de voz del reconocedor: alguien empezo a hablar `at_s` segundos de audio
    despues de abrirse el canal. Llega entre los transcritos, en el orden en que ocurrio."""
    return SpeechStarted(at_s=at_s)


#: Lo que devuelve el reconocedor cuando no entendio nada. No es `None` ni una
#: excepcion: el proveedor manda un final vacio, y BR3.4 se apoya en eso.
VACIO = Transcript(text=ExternalText(""), is_final=True, words=())


@dataclass
class ReconocedorGuionado(SpeechToText):
    """Un reconocedor que entrega el guion que le dieron, en orden.

    No mira el audio que entra --lo consume y lo cuenta-- porque lo que esta
    unidad prueba es que hace con lo que llega, no que el proveedor transcriba.
    """

    guion: Sequence[ListenEvent] = ()
    trozos_recibidos: int = field(default=0, init=False)

    async def _emitir(self, audio: AsyncIterator[bytes]) -> AsyncIterator[ListenEvent]:
        async for trozo in audio:
            self.trozos_recibidos += len(trozo)
        for pieza in self.guion:
            yield pieza

    def stream(
        self, audio: AsyncIterator[bytes], *, language: Locale
    ) -> AsyncIterator[ListenEvent]:
        del language  # el guion ya viene en el idioma de la prueba
        return self._emitir(audio)


@dataclass
class SintesisInstrumentada(TextToSpeech):
    """Una sintesis que entrega el audio en trozos y deja ver que se le pidio.

    `trozos` es cuantos pedazos entrega por frase: mas de uno a proposito, para
    que haya algo que interrumpir a mitad.
    """

    trozos: int = 3
    dicho: list[str] = field(default_factory=list)
    interrumpida_en: int | None = None

    async def _emitir(self, text: Redacted) -> AsyncIterator[bytes]:
        self.dicho.append(str(text))
        for i in range(self.trozos):
            if self.interrumpida_en is not None and i >= self.interrumpida_en:
                return
            yield b"\x00\x01" * 240  # 20 ms de PCM16 a 24 kHz

    def synthesize(self, text: Redacted, *, voice: VoiceRef) -> AsyncIterator[bytes]:
        del voice  # la eleccion de voz es de U15 y de U17, no de la prueba
        return self._emitir(text)


_TURNOS_DEL_DOBLE = itertools.count(1)


def con_rastro(grafo: TurnHandler) -> TurnHandler:
    """Un grafo doble que abre y cierra el rastro del turno como el de verdad.

    El `handle_turn` real abre `traces.turn_span` antes de su primer evento y lo cierra
    en un `finally`: pone variables de contexto al entrar y las repone al salir, y una
    variable de contexto solo se repone en la tarea donde se puso. Un doble que no abre
    nada esconde esa clase de fallo: la primera version de la muletilla (2026-10-12)
    pedia la respuesta desde otra tarea y tiraba cada llamada al primer turno largo con
    las pruebas en verde. **Todo grafo doble del ciclo de la llamada pasa por aqui.**

    Tampoco es mas permisivo que la pieza real en lo otro que la pieza real exige: un
    turno sin caso levanta.
    """

    async def con_el_rastro(turn: InboundTurn) -> AsyncIterator[TurnEvent]:
        if turn.case_id is None:
            msg = "handle_turn necesita case_id"
            raise ValueError(msg)
        with traces.turn_span(
            tenant_id=turn.tenant_id,
            case_id=turn.case_id,
            use=Use.VOICE if turn.channel == "voice" else Use.CHAT,
            turn_id=f"turno-de-prueba-{next(_TURNOS_DEL_DOBLE)}",
        ):
            async for evento in grafo(turn):
                yield evento

    return con_el_rastro


async def audio(trozos: Iterable[bytes]) -> AsyncIterator[bytes]:
    """Un flujo de audio de prueba."""
    for trozo in trozos:
        yield trozo


__all__ = [
    "VACIO",
    "ReconocedorGuionado",
    "SintesisInstrumentada",
    "audio",
    "con_rastro",
    "final",
    "palabras",
    "parcial",
    "senal",
]
