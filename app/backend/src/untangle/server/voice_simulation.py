"""La llamada simulada: una persona que es un guion, por el camino real de la llamada.

    mise run voice:simular -- --tenant <id> --guion <archivo.json> [--language es|en] [--detalle]

Nacio el 2026-10-12, cuando una llamada real se cayo y la unica forma de verlo fue que
Miguel llamara: cada intento cuesta plata y tiempo suyo. Esto es lo mismo sin el
microfono. Cada frase del guion se sintetiza con la voz del aplicativo y entra como
audio en tiempo real, con las pausas que el guion diga, por el reconocedor, el ciclo de
la llamada (`CallRunner`), el grafo y la voz de verdad. Lo unico que sustituye es el
socket. Usa el reloj de verdad, enciende la muletilla igual que la ruta real
(`FILLER_AFTER`), imprime cada cuadro que el servidor manda con su tiempo y, si la
llamada falla, la traza completa.

**Gasta dinero** --unos centavos por guion corto: la voz de quien llama, la
transcripcion, el modelo y la voz de la agente, a nombre de la llamada simulada en el
registro de gasto-- y por eso **no es una compuerta y no corre en GitHub Actions**.
Pasa por el techo y el registro de gasto como cualquier llamada. Deja un caso y una
llamada en la base local, con origen de despliegue local, que el reinicio nocturno no
borra.

**El guion es un archivo JSON, con datos 100 % sinteticos:**

    {
      "descripcion": "que reproduce este guion",
      "cola": 3,
      "pasos": [
        {"esperar_agente": true},
        {"decir": "Hola, queria consultar sobre"},
        {"pausa": 1.3},
        {"decir": "si mi poliza me cubre un choque con una moto"},
        {"esperar_agente": true, "y": 1.0}
      ]
    }

- `{"decir": "..."}`: la persona dice la frase. Pasa por el punto unico de redaccion
  antes de sintetizarse, como todo texto que va hacia una voz: un dato con forma de dato
  (una placa, un nombre) se leeria como su etiqueta, asi que los guiones no los llevan.
- `{"decir_con_datos": "..."}`: la persona dice una frase **con datos** --una poliza, un
  nombre-- y la frase llega a la llamada **ya transcrita**: no se sintetiza, no pasa por la
  redaccion de la voz ni por el reconocedor, asi que ningun dato sale hacia un proveedor y la
  redaccion de la voz sintetizada ni se toca ni se rodea. Entra por el mismo punto que lo que
  el reconocedor entrega (`CallVoice.listen`, que el ciclo consume en `_pasar_lo_oido`) con
  los eventos de un turno de la persona: la senal de voz (`SpeechStarted`) al empezar, los
  parciales con las palabras que lleva dichas (`partials_of`: el primero poco despues de la
  senal, uno mas cada tanto), el transcrito final tras lo que tardaria en decirse
  (`TYPED_CHARS_PER_S`), y el fin de su turno lo cierra el silencio, como el de cualquier turno:
  el detector lo vence tras el final (`TurnDetector`), sin evento propio. Los parciales importan:
  la escalera de silencios cuenta desde lo ultimo oido, parcial incluido, asi que sin ellos una
  frase larga dejaba pasar los segundos de la tolerancia y la agente preguntaba «¿sigues ahi?»
  a quien estaba hablando (visto el 2026-10-13, a los 4 s de una frase de 4,6 s). Mientras
  tanto el microfono sigue mandando silencio al
  reconocedor de verdad. Los datos tienen que ser sinteticos, igual que todo el guion; no
  cuentan para el tope de caracteres sintetizados porque no cuestan voz. Conviene dejar al
  menos 1 s (`"y": 1.0`) tras la ultima frase de la agente: el ciclo descarta como eco la
  senal de voz que cae mientras ella suena o en los 0,8 s siguientes, tambien la de este paso.
- `{"pausa": segundos}`: la persona calla.
- `{"esperar_agente": true, "y": 0.4, "hasta": 40}`: la persona espera a que la agente
  conteste a lo ultimo que dijo y termine de sonar, y calla `y` segundos mas. Sin
  respuesta en `hasta` segundos sigue de largo y lo dice. Al principio espera la apertura.
- `cola`: cuantos segundos sigue la linea abierta tras el ultimo paso (3 por omision).

**`--detalle`** imprime ademas, con su tiempo, cada parcial y cada senal de voz (`SpeechStarted`)
que entrega el reconocedor, en el instante en que llegan. Es lo que deja ver la carrera entre
una pausa de la persona y el cierre de su turno: sin el, de los parciales solo se ve el final.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import traceback
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record.models import Origin
from untangle.compliance.redaction import api as redaccion
from untangle.orchestration import closing_plan
from untangle.providers.ports import (
    SPEECH_AUDIO,
    ExternalText,
    ListenEvent,
    SpeechStarted,
    Transcript,
)
from untangle.server import composition, voice_routes
from untangle.settings import Settings
from untangle.telemetry.spend import attribution as spend_attribution
from untangle.tenancy import api as tenancy
from untangle.voice import api as voz
from untangle.voice.loop import FILLER_AFTER, CallChannel, CallRunner

__all__ = [
    "Pause",
    "Say",
    "SayWithData",
    "Script",
    "ScriptError",
    "SimulatedChannel",
    "VoiceWithDetail",
    "VoiceWithTranscripts",
    "WaitForAgent",
    "load_script",
    "parse_script",
    "partials_of",
    "run",
    "typed_duration_s",
]

#: Cuanto dura cada trozo de audio que entra, como el que manda el navegador.
FRAME_MS = 20
_FRAME_BYTES = SPEECH_AUDIO.bytes_per_second * FRAME_MS // 1000
_SILENCE = b"\x00" * _FRAME_BYTES

#: Lo que un guion puede pedir. Un guion largo gasta de mas sin querer: son topes de
#: cordura, no de seguridad.
MAX_STEPS = 40
MAX_SAY_CHARS = 400
MAX_TOTAL_SAY_CHARS = 2000
MAX_PAUSE_S = 60.0
MAX_TAIL_S = 120.0
MAX_WAIT_S = 120.0

#: Cuanto tardaria en decirse una frase que llega ya transcrita (`decir_con_datos`): caracteres
#: por segundo de una persona hablando con calma. Pone el final del transcrito donde lo pondria
#: el reconocedor y no en el mismo instante en que empieza la frase.
TYPED_CHARS_PER_S = 15.0
MIN_TYPED_S = 0.5

#: Los parciales de una frase con datos: cuando llega el primero tras la senal de voz y cada
#: cuanto el siguiente, con las palabras que llevaria dichas. El reconocedor de verdad entrega
#: parciales mientras la persona habla; sin ellos, el silencio que cuenta la llamada corre
#: durante toda la frase. Una frase que se dice en menos que el primero no lleva ninguno.
FIRST_PARTIAL_S = 0.5
PARTIAL_EVERY_S = 0.8

DEFAULT_TAIL_S = 3.0
DEFAULT_EXTRA_S = 0.4
DEFAULT_WAIT_TIMEOUT_S = 40.0

#: Lo que se espera entre mirada y mirada mientras se aguarda a la agente.
_POLL_S = 0.1


class ScriptError(ValueError):
    """El guion no sirve. El mensaje dice cual paso y por que, antes de gastar nada."""


# --- El guion -----------------------------------------------------------------


@dataclass(frozen=True)
class Say:
    """La persona dice una frase."""

    text: str


@dataclass(frozen=True)
class Pause:
    """La persona calla."""

    seconds: float


@dataclass(frozen=True)
class WaitForAgent:
    """La persona espera a que la agente conteste y termine de sonar."""

    extra_s: float
    timeout_s: float


@dataclass(frozen=True)
class SayWithData:
    """La persona dice una frase con datos, y la llamada la recibe ya transcrita."""

    text: str


Step = Say | SayWithData | Pause | WaitForAgent


@dataclass(frozen=True)
class Script:
    description: str
    steps: tuple[Step, ...]
    #: Cuanto sigue abierta la linea tras el ultimo paso.
    tail_s: float

    @property
    def say_chars(self) -> int:
        """Los caracteres que se sintetizan con la voz del aplicativo para quien llama.

        Las frases con datos no cuentan: llegan como texto y no cuestan voz.
        """
        return sum(len(paso.text) for paso in self.steps if isinstance(paso, Say))

    @property
    def said_phrases(self) -> int:
        """Cuantas frases se sintetizan."""
        return sum(isinstance(paso, Say) for paso in self.steps)

    @property
    def typed_phrases(self) -> int:
        """Cuantas frases llegan ya transcritas (`decir_con_datos`)."""
        return sum(isinstance(paso, SayWithData) for paso in self.steps)


def _number(valor: object, *, donde: str, maximo: float, minimo: float = 0.0) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        msg = f"{donde} tiene que ser un numero de segundos"
        raise ScriptError(msg)
    if not minimo <= valor <= maximo:
        msg = f"{donde} tiene que estar entre {minimo:g} y {maximo:g} segundos"
        raise ScriptError(msg)
    return float(valor)


def typed_duration_s(texto: str) -> float:
    """Lo que tardaria una persona en decir esta frase: de ahi sale cuando llega su transcrito."""
    return max(MIN_TYPED_S, len(texto) / TYPED_CHARS_PER_S)


def partials_of(texto: str) -> tuple[tuple[float, str], ...]:
    """Los parciales de una frase dicha de corrido: cuando llega cada uno, contado desde la
    senal de voz, y las palabras que lleva dichas.

    El primero llega a los `FIRST_PARTIAL_S` y uno mas cada `PARTIAL_EVERY_S` mientras la frase
    no haya terminado (`typed_duration_s`). Cada uno repite lo anterior y agrega palabras, como
    los del reconocedor, en proporcion a lo que ha pasado, y ninguno trae la frase entera: esa
    es el final. Una frase de una palabra, o que se dice antes del primer parcial, no tiene.
    """
    palabras = texto.split()
    duracion = typed_duration_s(texto)
    parciales: list[tuple[float, str]] = []
    llegada = FIRST_PARTIAL_S
    while len(palabras) > 1 and llegada < duracion:
        dichas = min(len(palabras) - 1, max(1, round(len(palabras) * llegada / duracion)))
        parciales.append((llegada, " ".join(palabras[:dichas])))
        llegada += PARTIAL_EVERY_S
    return tuple(parciales)


_ACCIONES = ("decir", "decir_con_datos", "pausa", "esperar_agente")


def _phrase(donde: str, clave: str, crudo: dict[str, object]) -> str:
    texto = crudo[clave]
    if not isinstance(texto, str) or not texto.strip():
        msg = f"{donde}: {clave} lleva una frase"
        raise ScriptError(msg)
    if len(texto) > MAX_SAY_CHARS:
        msg = f"{donde}: la frase pasa de {MAX_SAY_CHARS} caracteres"
        raise ScriptError(msg)
    return texto.strip()


def _step(indice: int, crudo: object) -> Step:
    donde = f"paso {indice}"
    if not isinstance(crudo, dict):
        msg = f"{donde}: tiene que ser un objeto con {', '.join(_ACCIONES)}"
        raise ScriptError(msg)
    acciones = [clave for clave in _ACCIONES if clave in crudo]
    if len(acciones) != 1:
        msg = f"{donde}: lleva exactamente una de {', '.join(_ACCIONES)} (trae {acciones})"
        raise ScriptError(msg)
    accion = acciones[0]
    permitidas = {
        "decir": {"decir"},
        "decir_con_datos": {"decir_con_datos"},
        "pausa": {"pausa"},
        "esperar_agente": {"esperar_agente", "y", "hasta"},
    }
    sobran = sorted(set(crudo) - permitidas[accion])
    if sobran:
        msg = f"{donde}: no conoce {', '.join(sobran)}"
        raise ScriptError(msg)
    if accion == "decir":
        return Say(text=_phrase(donde, accion, crudo))
    if accion == "decir_con_datos":
        return SayWithData(text=_phrase(donde, accion, crudo))
    if accion == "pausa":
        return Pause(seconds=_number(crudo["pausa"], donde=f"{donde}: pausa", maximo=MAX_PAUSE_S))
    if crudo["esperar_agente"] is not True:
        msg = f"{donde}: esperar_agente se escribe true"
        raise ScriptError(msg)
    return WaitForAgent(
        extra_s=_number(crudo.get("y", DEFAULT_EXTRA_S), donde=f"{donde}: y", maximo=MAX_WAIT_S),
        timeout_s=_number(
            crudo.get("hasta", DEFAULT_WAIT_TIMEOUT_S),
            donde=f"{donde}: hasta",
            maximo=MAX_WAIT_S,
            minimo=1.0,
        ),
    )


def parse_script(datos: object) -> Script:
    """El guion ya leido del JSON, validado paso a paso."""
    if not isinstance(datos, dict):
        msg = 'el guion es un objeto con "pasos"'
        raise ScriptError(msg)
    desconocidas = sorted(set(datos) - {"descripcion", "cola", "pasos"})
    if desconocidas:
        msg = f"el guion no conoce {', '.join(desconocidas)}"
        raise ScriptError(msg)
    crudos = datos.get("pasos")
    if not isinstance(crudos, list) or not crudos:
        msg = 'el guion lleva una lista "pasos" con al menos un paso'
        raise ScriptError(msg)
    if len(crudos) > MAX_STEPS:
        msg = f"el guion pasa de {MAX_STEPS} pasos"
        raise ScriptError(msg)
    pasos = tuple(_step(i, crudo) for i, crudo in enumerate(crudos, start=1))
    guion = Script(
        description=str(datos.get("descripcion", "")),
        steps=pasos,
        tail_s=_number(datos.get("cola", DEFAULT_TAIL_S), donde="cola", maximo=MAX_TAIL_S),
    )
    if guion.said_phrases + guion.typed_phrases == 0:
        msg = "el guion no dice nada: sin un paso decir o decir_con_datos no hay persona"
        raise ScriptError(msg)
    if guion.say_chars > MAX_TOTAL_SAY_CHARS:
        msg = f"las frases del guion pasan de {MAX_TOTAL_SAY_CHARS} caracteres en total"
        raise ScriptError(msg)
    return guion


def load_script(path: Path) -> Script:
    """Lee y valida un guion. Cualquier fallo se dice como `ScriptError`, nombrando el archivo."""
    try:
        datos = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        msg = f"no se pudo leer '{path}': {error.strerror or type(error).__name__}"
        raise ScriptError(msg) from error
    except json.JSONDecodeError as error:
        msg = f"'{path}' no es JSON valido: {error.msg} (linea {error.lineno})"
        raise ScriptError(msg) from error
    try:
        return parse_script(datos)
    except ScriptError as error:
        msg = f"'{path}': {error}"
        raise ScriptError(msg) from error


# --- El transporte simulado ---------------------------------------------------


@dataclass
class SimulatedChannel(CallChannel):
    """El socket, sustituido: audio de la persona en tiempo real y cuadros a la consola.

    Es lo unico del camino real que no esta. Entrega un trozo de 20 ms cada 20 ms de
    reloj --silencio cuando la persona calla, como un microfono abierto-- y escribe cada
    cuadro que el servidor manda con el tiempo desde que empezo la llamada.
    """

    echo: Callable[[str], None] = print
    clock: Callable[[], float] = time.monotonic
    started_at: float = field(default_factory=time.monotonic)
    queue: asyncio.Queue[bytes] = field(default_factory=asyncio.Queue)
    #: Lo que el reconocedor habria entregado de las frases con datos (`decir_con_datos`):
    #: `VoiceWithTranscripts` lo mezcla con lo que el reconocedor de verdad entrega.
    heard: asyncio.Queue[ListenEvent] = field(default_factory=asyncio.Queue)
    hung_up: bool = False
    #: El ultimo estado que mando la llamada ("listening", "speaking"...).
    state: str = ""
    #: Cuantas frases de la agente se han visto: `esperar_agente` mira que haya una nueva.
    agent_phrases: int = 0
    audio_bytes: int = 0
    frames: int = 0
    _last_audio_at: float = 0.0

    def stamp(self) -> str:
        return f"[{self.clock() - self.started_at:6.2f}s]"

    async def _entrar(self) -> AsyncIterator[bytes | voz.Hangup]:
        siguiente = self.clock()
        while not self.hung_up:
            try:
                trozo = self.queue.get_nowait()
            except asyncio.QueueEmpty:
                trozo = _SILENCE
            yield trozo
            siguiente += FRAME_MS / 1000
            await asyncio.sleep(max(0.0, siguiente - self.clock()))
        yield voz.Hangup()

    def inbound(self) -> AsyncIterator[bytes | voz.Hangup]:
        return self._entrar()

    async def send(self, frame: voz.ServerFrame) -> None:
        nombre = type(frame).__name__
        datos: dict[str, Any] = {
            k: getattr(frame, k) for k in getattr(frame, "__dataclass_fields__", {})
        }
        if isinstance(frame, voz.State):
            self.state = str(frame.value)
        if isinstance(frame, voz.Transcript):
            if not frame.final:
                return
            if frame.speaker == "agent":
                self.agent_phrases += 1
        self.frames += 1
        detalle = json.dumps(datos, default=str, ensure_ascii=False)[:230]
        self.echo(f"{self.stamp()} <- {nombre} {detalle}")

    async def send_audio(self, chunk: bytes) -> None:
        ahora = self.clock()
        if self.audio_bytes == 0 or ahora - self._last_audio_at > 0.6:
            self.echo(f"{self.stamp()} <- (empieza a sonar audio)")
        self.audio_bytes += len(chunk)
        self._last_audio_at = ahora

    def say(self, audio: bytes) -> float:
        """Pone el audio de la persona en la cola y devuelve cuanto tarda en sonar."""
        for inicio in range(0, len(audio), _FRAME_BYTES):
            self.queue.put_nowait(
                audio[inicio : inicio + _FRAME_BYTES].ljust(_FRAME_BYTES, b"\x00")
            )
        return len(audio) / SPEECH_AUDIO.bytes_per_second

    def hear(self, evento: ListenEvent) -> None:
        """Entrega a la escucha de la llamada un evento como si el reconocedor lo hubiera oido."""
        self.heard.put_nowait(evento)

    def stream_seconds(self) -> float:
        """Los segundos de audio de la llamada hasta ahora: el eje de `SpeechStarted.at_s`.

        El primer trozo sale al abrirse la linea, y `started_at` se fija justo antes.
        """
        return max(0.0, self.clock() - self.started_at)

    @property
    def agent_is_listening(self) -> bool:
        return self.state.endswith("listening")


# --- La voz, vista desde fuera ------------------------------------------------

#: Lo que se imprime de un parcial: igual que un cuadro, para que una frase larga no
#: ocupe la consola.
_DETAIL_CHARS = 230


@dataclass
class _VoiceWrapper:
    """La voz de la llamada tal cual: sintesis, sesion y escucha pasan sin tocarse.

    Los testigos de abajo la heredan y cambian solo `listen`. La sintesis y la sesion no se
    tocan porque la simulacion mide la llamada de verdad, con su conexion unica de sintesis.
    """

    inner: voz.CallVoice
    canal: SimulatedChannel

    def listen(
        self, tenant_id: str, audio: AsyncIterator[bytes], *, language: Locale
    ) -> AsyncIterator[ListenEvent]:
        return self.inner.listen(tenant_id, audio, language=language)

    def speak(
        self, tenant_id: str, text: redaccion.Redacted, *, mode: voz.VoiceMode, language: Locale
    ) -> AsyncIterator[bytes]:
        return self.inner.speak(tenant_id, text, mode=mode, language=language)

    def speech_session(
        self, tenant_id: str, *, mode: voz.VoiceMode, language: Locale
    ) -> AbstractAsyncContextManager[voz.CallSpeech]:
        """La boca de la llamada, la misma que usaria sin el testigo."""
        if isinstance(self.inner, voz.SessionVoice):
            return self.inner.speech_session(tenant_id, mode=mode, language=language)
        return _sin_sesion(self.inner)


@dataclass
class VoiceWithDetail(_VoiceWrapper):
    """La voz de la llamada, con una linea por cada parcial y cada senal de voz (`--detalle`).

    Es la misma voz --sintesis y reconocedor pasan sin tocarse-- con un testigo en la
    escucha: imprime lo que el reconocedor entrega **cuando lo entrega**, que no es cuando
    lo consume el ciclo. Los finales no se repiten aqui: ya salen como cuadros.
    """

    def listen(
        self, tenant_id: str, audio: AsyncIterator[bytes], *, language: Locale
    ) -> AsyncGenerator[ListenEvent]:
        return self._listen(tenant_id, audio, language=language)

    async def _listen(
        self, tenant_id: str, audio: AsyncIterator[bytes], *, language: Locale
    ) -> AsyncGenerator[ListenEvent]:
        eventos = self.inner.listen(tenant_id, audio, language=language)
        try:
            async for evento in eventos:
                linea = describe_event(evento)
                if linea is not None:
                    self.canal.echo(f"{self.canal.stamp()} ~ reconocedor: {linea}")
                yield evento
        finally:
            await _close(eventos)


class _EndOfRecognizer:
    """Marca el fin de lo que entrega el reconocedor en la cola que junta las dos fuentes."""


_END_OF_RECOGNIZER = _EndOfRecognizer()

#: Lo que lleva la cola que junta las dos fuentes: eventos, el fallo del reconocedor o su fin.
type _Mixed = ListenEvent | Exception | _EndOfRecognizer


@dataclass
class VoiceWithTranscripts(_VoiceWrapper):
    """La voz de la llamada, con las frases con datos mezcladas en lo que la escucha entrega.

    `decir_con_datos` no pasa por la sintesis ni por el reconocedor: la persona simulada deja
    sus eventos en `canal.heard` y esta escucha los entrega al ciclo entre los del reconocedor
    de verdad, que sigue abierto y oyendo el silencio del microfono. Es el mismo punto por el
    que entra todo lo oido (`CallRunner._pasar_lo_oido`), asi que el eco de la agente, el
    detector de turno y el resto lo tratan como a cualquier otro transcrito.

    Si el reconocedor falla, el fallo sale por aqui igual que saldria sin el testigo.
    """

    def listen(
        self, tenant_id: str, audio: AsyncIterator[bytes], *, language: Locale
    ) -> AsyncGenerator[ListenEvent]:
        return self._listen(tenant_id, audio, language=language)

    async def _listen(
        self, tenant_id: str, audio: AsyncIterator[bytes], *, language: Locale
    ) -> AsyncGenerator[ListenEvent]:
        eventos = self.inner.listen(tenant_id, audio, language=language)
        juntos: asyncio.Queue[_Mixed] = asyncio.Queue()
        tareas = [
            asyncio.create_task(self._pasar_el_reconocedor(eventos, juntos)),
            asyncio.create_task(self._pasar_lo_escrito(juntos)),
        ]
        try:
            while True:
                evento = await juntos.get()
                if isinstance(evento, _EndOfRecognizer):
                    return
                if isinstance(evento, Exception):
                    raise evento
                yield evento
        finally:
            for tarea in tareas:
                tarea.cancel()
            # Las tareas leen el flujo del reconocedor: hasta que no terminan, cerrarlo falla.
            await asyncio.gather(*tareas, return_exceptions=True)
            await _close(eventos)

    @staticmethod
    async def _pasar_el_reconocedor(
        eventos: AsyncIterator[ListenEvent], juntos: asyncio.Queue[_Mixed]
    ) -> None:
        try:
            async for evento in eventos:
                juntos.put_nowait(evento)
        except Exception as error:  # noqa: BLE001 -- se vuelve a lanzar en quien consume `juntos`
            juntos.put_nowait(error)
        else:
            juntos.put_nowait(_END_OF_RECOGNIZER)

    async def _pasar_lo_escrito(self, juntos: asyncio.Queue[_Mixed]) -> None:
        while True:
            juntos.put_nowait(await self.canal.heard.get())


async def _close(flujo: object) -> None:
    """Cierra un flujo asincrono si sabe cerrarse: `async for` no lo hace al salir antes."""
    cerrar = getattr(flujo, "aclose", None)
    if cerrar is not None:
        await cerrar()


@asynccontextmanager
async def _sin_sesion(voz_suelta: voz.CallSpeech) -> AsyncIterator[voz.CallSpeech]:
    """Una voz que no ofrece sesion: cada frase por la voz suelta."""
    yield voz_suelta


def describe_event(evento: ListenEvent) -> str | None:
    """La linea de un evento del reconocedor, o nada si no se imprime (los finales)."""
    if isinstance(evento, SpeechStarted):
        return f"senal de voz, a los {evento.at_s:.2f} s del audio"
    if evento.is_final:
        return None
    return f"parcial {str(evento.text)[:_DETAIL_CHARS]!r}"


# --- La persona ---------------------------------------------------------------


async def _synthesize(speech: voz.CallVoice, tenant_id: str, texto: str, idioma: Locale) -> bytes:
    """La voz de quien llama: la del aplicativo, sintetizada de una vez."""
    trozos = [
        trozo
        async for trozo in speech.speak(
            tenant_id,
            redaccion.redact(texto, language=idioma),
            mode=voz.VoiceMode.PRIMARY,
            language=idioma,
        )
    ]
    return b"".join(trozos)


async def _wait_for_agent(
    canal: SimulatedChannel,
    ciclo: CallRunner,
    paso: WaitForAgent,
    *,
    frases_antes: int,
) -> bool:
    """Espera a que la agente diga algo nuevo, termine de sonar y vuelva a escuchar.

    Devuelve si lo vio. Sin respuesta en `hasta` segundos, o con la llamada ya acabada,
    sigue de largo: un guion que se queda esperando para siempre gasta sin decir nada.
    """
    limite = canal.clock() + paso.timeout_s
    while canal.clock() < limite and not canal.hung_up:
        fin = ciclo.playback_ends_at
        sonando = fin is not None and fin > datetime.now(UTC)
        if canal.agent_phrases > frases_antes and not sonando and canal.agent_is_listening:
            await asyncio.sleep(paso.extra_s)
            return True
        await asyncio.sleep(_POLL_S)
    if not canal.hung_up:
        canal.echo(
            f"{canal.stamp()} !! la agente no contesto en {paso.timeout_s:g} s; sigue el guion"
        )
    return False


async def _say_with_data(canal: SimulatedChannel, paso: SayWithData) -> None:
    """Una frase con datos, entregada a la escucha de la llamada como texto ya transcrito.

    Los mismos eventos que el reconocedor daria por un turno de la persona: la senal de voz al
    empezar, los parciales con las palabras que lleva dichas (`partials_of`) y, tras lo que
    tardaria en decirse, el transcrito final. El fin del turno no es un evento: lo cierra el
    silencio que sigue, como siempre.
    """
    duracion = typed_duration_s(paso.text)
    canal.echo(
        f"{canal.stamp()} -> persona dice (texto ya transcrito, sin voz ni reconocedor): "
        f"{paso.text!r} ({duracion:.1f} s)"
    )
    canal.hear(SpeechStarted(at_s=canal.stream_seconds()))
    transcurrido = 0.0
    for llegada, dichas in partials_of(paso.text):
        await asyncio.sleep(llegada - transcurrido)
        transcurrido = llegada
        canal.hear(Transcript(text=ExternalText(dichas), is_final=False))
    await asyncio.sleep(duracion - transcurrido)
    canal.hear(Transcript(text=ExternalText(paso.text), is_final=True))


async def _person(
    canal: SimulatedChannel, ciclo: CallRunner, guion: Script, audios: dict[str, bytes]
) -> None:
    """La persona del guion: dice, calla y espera, y al final cuelga."""
    frases_al_hablar = 0
    for paso in guion.steps:
        if isinstance(paso, WaitForAgent):
            await _wait_for_agent(canal, ciclo, paso, frases_antes=frases_al_hablar)
        elif isinstance(paso, Pause):
            await asyncio.sleep(paso.seconds)
        elif isinstance(paso, SayWithData):
            frases_al_hablar = canal.agent_phrases
            await _say_with_data(canal, paso)
        else:
            audio = audios[paso.text]
            frases_al_hablar = canal.agent_phrases
            canal.echo(
                f"{canal.stamp()} -> persona dice: {paso.text!r} "
                f"({len(audio) / SPEECH_AUDIO.bytes_per_second:.1f} s)"
            )
            await asyncio.sleep(canal.say(audio))
    await asyncio.sleep(guion.tail_s)
    canal.echo(f"{canal.stamp()} -> persona cuelga")
    canal.hung_up = True


# --- La llamada ---------------------------------------------------------------


def _now() -> datetime:
    """El reloj de verdad, que el ciclo de la llamada pide como funcion."""
    return datetime.now(UTC)


def _print_failure(canal: SimulatedChannel, error: Exception) -> None:
    canal.echo(f"{canal.stamp()} !! LA LLAMADA FALLO: {type(error).__name__}")
    # La traza entera, con el mensaje: esto es una herramienta de quien desarrolla y los
    # guiones son sinteticos. Al registro del servidor solo van el tipo y el sitio.
    traceback.print_exception(error, limit=20, file=sys.stdout)


def _listening_voice(
    speech: voz.CallVoice, canal: SimulatedChannel, guion: Script, *, detail: bool
) -> voz.CallVoice:
    """La voz por la que escucha el ciclo: la de verdad, con los testigos que el guion pida.

    Sin frases con datos ni `--detalle` es la voz del aplicativo sin envolver. Con ambos, el
    detalle va por fuera para que imprima tambien lo que entregan las frases con datos.
    """
    if guion.typed_phrases:
        speech = VoiceWithTranscripts(speech, canal)
    if detail:
        speech = VoiceWithDetail(speech, canal)
    return speech


async def simulate(
    ajustes: Settings, *, tenant_id: str, language: Locale, guion: Script, detail: bool = False
) -> voz.EndReason | None:
    """Corre el guion contra la aplicacion levantada. Nulo si no se llego a llamar.

    Con `detail`, el ciclo escucha por `VoiceWithDetail`; con frases con datos, por
    `VoiceWithTranscripts`; la sintesis de la voz de quien llama no pasa por ahi.
    """
    aplicacion = composition.build_app(ajustes)
    async with aplicacion.router.lifespan_context(aplicacion):
        deps = voice_routes.current_deps()
        try:
            config = tenancy.require(tenant_id)
        except tenancy.UnknownTenantError as error:
            print(str(error), file=sys.stderr)
            return None
        estado = deps.speech.availability_for(tenant_id)
        if not estado.available:
            motivo = estado.reason.value if estado.reason is not None else "sin motivo"
            print(f"la voz de '{tenant_id}' esta apagada ({motivo})", file=sys.stderr)
            return None

        registro = await tenancy.resolve_visitor_key(
            tenant_id=tenant_id,
            visitor_key=tenancy.new_visitor_key(),
            origin="llamada-simulada",
        )
        llamada = await voz.open_call(
            tenant_id=tenant_id,
            visitor_key_digest=registro.visitor_key_hash,
            language=language,
            voice_mode=voz.VoiceMode.PRIMARY,
            now=_now(),
        )
        case_id = await voz.open_for_call(
            tenant_id, language=language, origin=Origin.LOCAL_DEPLOYMENT, now=_now()
        )
        llamada = await voz.attach_case(llamada, case_id=case_id)
        llamada = await voz.mark_live(llamada)

        canal = SimulatedChannel()
        motor = voz.CallEngine(
            call=llamada,
            config=config,
            handle_turn=deps.handle_turn,
            understand=deps.understand_turn,
        )
        ciclo = CallRunner(
            engine=motor,
            channel=canal,
            speech=_listening_voice(deps.speech, canal, guion, detail=detail),
            now=_now,
            max_call=timedelta(seconds=config.call.max_call_seconds),
            warn_at=timedelta(seconds=config.call.warn_at_seconds),
            filler_after=FILLER_AFTER,
            on_failure=lambda error: _print_failure(canal, error),
        )
        with spend_attribution.attributed(
            tenant_id=tenant_id, case_id=case_id, call_id=llamada.call_id
        ):
            audios = {
                paso.text: await _synthesize(deps.speech, tenant_id, paso.text, language)
                for paso in guion.steps
                if isinstance(paso, Say)
            }
            # El reloj de la salida arranca aqui, con la llamada, y no con la sintesis.
            canal.started_at = canal.clock()
            persona = asyncio.create_task(_person(canal, ciclo, guion, audios))
            motivo = await ciclo.run()
            persona.cancel()
        canal.echo(
            f"{canal.stamp()} == termino: {motivo.value} "
            f"({canal.frames} cuadros, {canal.audio_bytes / SPEECH_AUDIO.bytes_per_second:.1f} s "
            "de audio de la agente)"
        )
        await voz.end_call(motor.call, reason=motivo, now=_now())
        canal.echo(f"{canal.stamp()} == el caso quedo: {await _resolved(deps, tenant_id, case_id)}")
        return motivo


#: Cuanto espera la simulacion a que el fondo resuelva el reporte antes de decir como quedo.
RESOLUTION_WAIT = 5.0


async def _resolved(deps: voice_routes.VoiceDeps, tenant_id: str, case_id: str) -> str:
    """Como quedo el caso al terminar la llamada, por el mismo camino que una llamada real.

    La ruta de la voz resuelve la revision al cerrarse el socket (`settle_review`); aqui no hay
    socket, asi que se llama igual. El cierre corre en el fondo: se espera un poco a que el
    caso salga de revision, para que la simulacion muestre el desenlace y no solo la despedida.
    """
    if deps.settle_review is not None:
        await deps.settle_review(case_id, tenant_id=tenant_id)
    limite = asyncio.get_running_loop().time() + RESOLUTION_WAIT
    while True:
        vista = await casos.get_case(tenant_id, case_id)
        if vista is None:
            return "sin caso"
        en_revision = vista.state in closing_plan.REVIEW_STATES
        if not en_revision or asyncio.get_running_loop().time() >= limite:
            resolucion = f", {vista.resolution.value}" if vista.resolution is not None else ""
            return f"{vista.state.value}{resolucion}"
        await asyncio.sleep(0.2)


def _typed_note(guion: Script) -> str:
    """Lo que se anade al aviso de gasto cuando hay frases con datos: no cuestan voz."""
    if not guion.typed_phrases:
        return ""
    return f" y {guion.typed_phrases} con datos que llegan ya transcritas, sin voz ni reconocedor"


def run(argumentos: argparse.Namespace, ajustes: Settings) -> int:
    """La entrada del comando. Devuelve el codigo de salida: 0 si la llamada no se cayo."""
    try:
        guion = load_script(argumentos.guion)
    except ScriptError as error:
        print(f"guion invalido: {error}", file=sys.stderr)
        return 1
    if guion.description:
        print(guion.description)
    print(
        f"Llamada simulada a '{argumentos.tenant}' en {argumentos.language}: "
        f"{guion.said_phrases} frases de la persona "
        f"({guion.say_chars} caracteres por la voz del aplicativo){_typed_note(guion)}. Gasta "
        "voz, transcripcion y modelo de verdad: unos centavos."
    )
    motivo = asyncio.run(
        simulate(
            ajustes,
            tenant_id=argumentos.tenant,
            language=argumentos.language,
            guion=guion,
            detail=bool(getattr(argumentos, "detalle", False)),
        )
    )
    if motivo is None:
        return 1
    return 1 if motivo is voz.EndReason.ERROR else 0
