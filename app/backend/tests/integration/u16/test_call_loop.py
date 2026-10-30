"""El ciclo de la llamada, con un canal de mentira y el reloj en la mano.

Aqui no hay WebSocket: `CallRunner` habla por `CallChannel`, y eso es
exactamente lo que permite mirar **cuando** hace cada cosa sin levantar un
servidor y sin esperar tiempo real. El apreton de manos y los motivos de final
se prueban por el socket, en `test_voice_socket.py`; lo de aqui es el ritmo.

**Ninguna prueba duerme.** El reloj entra por argumento y el detector de fin de
habla se construye con una tolerancia de cero, asi que un turno se cierra en
cuanto el guion deja de traer transcritos.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import sys
import time
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from itertools import pairwise

import pytest

from untangle import observability
from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record import rules
from untangle.case_record.models import Actor, ActorType, CaseState, Channel
from untangle.compliance.redaction.api import Redacted
from untangle.copy_catalog import api as copy_api
from untangle.orchestration import contracts as c14
from untangle.orchestration.nodes.intake import composition
from untangle.providers.ports import ExternalText, ListenEvent, Transcript, WordHypothesis
from untangle.telemetry.spend.models import VoiceMode
from untangle.tenancy import api as tenancy
from untangle.tenancy import config as tenancy_config
from untangle.tenancy import session as db
from untangle.tenancy.models import TranscriptionMode
from untangle.voice import answers, opening, resume, retry, silence
from untangle.voice import api as voz
from untangle.voice import loop as loop_voz
from untangle.voice.loop import (
    ANSWER_WAIT,
    FINAL_PLAYBACK_GRACE_S,
    LATE_ANSWER_WAIT,
    CallRunner,
)
from untangle.voice.turn_detection import MAX_WORD_TO_FINAL

from ...unit.voice.dobles import con_rastro, senal
from ...unit.voice.dobles import final as final_con_tiempos
from .conftest import AHORA, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u16")


#: PERF-U16.1: lo que esta unidad anade entre el fin del habla y el primer audio.
PRESUPUESTO_PROPIO_MS = 60

#: Veinte milisegundos de PCM16 a 24 kHz, en silencio.
SILENCIO = b"\x00\x00" * 240


def _final(texto: str, *, confianza: float | None = 0.95) -> Transcript:
    palabras = tuple(
        WordHypothesis(
            text=ExternalText(p), start_s=i * 0.3, end_s=i * 0.3 + 0.2, confidence=confianza
        )
        for i, p in enumerate(texto.split())
    )
    return Transcript(text=ExternalText(texto), is_final=True, words=palabras)


@dataclass
class CanalFalso:
    """El transporte, con lo que salio y por que puerta."""

    entrantes: list[bytes | voz.Hangup] = field(default_factory=list)
    cuadros: list[voz.ServerFrame] = field(default_factory=list)
    audio: list[bytes] = field(default_factory=list)
    #: Mientras devuelva cierto, el navegador sigue mandando silencio. Es como se
    #: mantiene la llamada viva sin esperar tiempo real: la condicion la escribe
    #: la prueba en terminos de lo que ya paso, no de un reloj.
    seguir: Callable[[], bool] | None = None

    async def _entrar(self) -> AsyncIterator[bytes | voz.Hangup]:
        for pieza in self.entrantes:
            yield pieza
        while self.seguir is not None and self.seguir():
            # Cede el turno entre trozos, como un navegador que manda uno cada
            # 20 ms. Sin esto el bucle llena la cola sin soltar nunca el hilo del
            # evento, y lo que se cuelga no es la llamada: es la prueba.
            await asyncio.sleep(0)
            yield SILENCIO

    def inbound(self) -> AsyncIterator[bytes | voz.Hangup]:
        return self._entrar()

    async def send(self, frame: voz.ServerFrame) -> None:
        # **Cede el turno**, como lo cede un socket de verdad. Un doble que no
        # suspende nunca es un doble mas rapido que la pieza real, y con el la
        # sintesis entera corre antes de que el reconocedor llegue a arrancar:
        # ninguna interrupcion seria posible y la prueba lo llamaria "no
        # interrumpio".
        await asyncio.sleep(0)
        self.cuadros.append(frame)

    async def send_audio(self, chunk: bytes) -> None:
        await asyncio.sleep(0)
        self.audio.append(chunk)

    def de_tipo[T](self, tipo: type[T]) -> list[T]:
        return [c for c in self.cuadros if isinstance(c, tipo)]


@dataclass
class VozDoble:
    """El oido y la boca, con guion. Cumple el puerto `CallVoice`."""

    guion: Sequence[ListenEvent] = ()
    trozos: int = 3
    #: El guion sale **antes** de consumir el audio: es alguien que ya esta
    #: hablando mientras la agente habla, que es lo unico que interrumpe.
    antes_del_audio: bool = False
    #: Si se da, el guion espera a que esto sea cierto antes de salir. Es como se
    #: coloca una frase **despues** de que la agente dijo algo, sin relojes.
    esperar_a: Callable[[], bool] | None = None
    dicho: list[str] = field(default_factory=list)
    #: El idioma de cada frase que se mando a sintetizar, en el mismo orden que `dicho`.
    idiomas_dichos: list[Locale] = field(default_factory=list)
    #: El idioma con que se abrio cada conexion del reconocedor, en orden. Mas de una cuando
    #: la llamada cambia de idioma y el ciclo reabre la escucha.
    escuchas: list[Locale] = field(default_factory=list)
    #: El guion sale **una sola vez**, aunque el ciclo reabra la escucha: una conexion nueva
    #: del reconocedor no repite lo que la persona ya dijo.
    _guion_dicho: bool = field(default=False, init=False)

    async def _oir(self, audio: AsyncIterator[bytes]) -> AsyncIterator[ListenEvent]:
        guion = () if self._guion_dicho else tuple(self.guion)
        self._guion_dicho = True
        if self.esperar_a is not None:
            while not self.esperar_a():  # noqa: ASYNC110 -- la condicion no es un evento sino algo que ya paso (cuantas veces hablo la agente): un `Event` obligaria al ciclo a avisar, y el ciclo no sabe que hay una prueba mirando
                await asyncio.sleep(0)
            for pieza in guion:
                yield pieza
            async for _ in audio:
                pass
            return
        if self.antes_del_audio:
            for pieza in guion:
                yield pieza
        async for _ in audio:
            pass
        if not self.antes_del_audio:
            for pieza in guion:
                yield pieza

    def listen(
        self, tenant_id: str, audio: AsyncIterator[bytes], *, language: Locale
    ) -> AsyncIterator[ListenEvent]:
        del tenant_id
        self.escuchas.append(language)
        return self._oir(audio)

    async def _decir(self, text: Redacted) -> AsyncIterator[bytes]:
        self.dicho.append(str(text))
        for _ in range(self.trozos):
            yield b"\x00\x01" * 240

    def speak(
        self, tenant_id: str, text: Redacted, *, mode: VoiceMode, language: Locale
    ) -> AsyncIterator[bytes]:
        del tenant_id, mode
        self.idiomas_dichos.append(language)
        return self._decir(text)


async def _sin_grafo(turn: c14.InboundTurn) -> AsyncIterator[c14.TurnEvent]:
    yield c14.FinalText(message_id="m1", text="Noted.", language=turn.language)


@pytest.fixture
def catalogo() -> None:
    copy_api.install(copy_api.load())
    tenancy_config.install(tenancy_config.load())


async def _motor(*, end_of_speech: timedelta = timedelta(0)) -> voz.CallEngine:
    """El motor sobre una llamada y un caso de verdad, con el reloj de la suite."""
    aseguradora = tenancy.available_ids()[0]
    caso = await nuevo_caso(aseguradora)
    llamada = await voz.open_call(
        tenant_id=aseguradora,
        visitor_key_digest="digest-de-prueba",
        language="en",
        voice_mode=VoiceMode.PRIMARY,
        now=AHORA,
    )
    llamada = await voz.attach_case(llamada, case_id=caso.case_id)
    return voz.CallEngine(
        call=llamada,
        config=tenancy.require(aseguradora),
        handle_turn=con_rastro(_sin_grafo),
        end_of_speech=end_of_speech,
        # Las frases de estos guiones llegan sin punto: sin esto, la espera de una
        # frase sin cierre o a medias dejaria el turno abierto con el reloj detenido.
        unpunctuated_end_of_speech=end_of_speech,
        incomplete_end_of_speech=end_of_speech,
    )


def _reloj() -> datetime:
    """El reloj de la llamada. Adelantado a `AHORA` para que la duracion maxima
    no venza antes de empezar: la llamada se siembra en esa fecha."""
    return AHORA + timedelta(seconds=1)


def _correr(motor: voz.CallEngine, canal: CanalFalso, voz_doble: VozDoble) -> CallRunner:
    return CallRunner(
        engine=motor,
        channel=canal,
        speech=voz_doble,
        now=_reloj,
        max_call=timedelta(seconds=180),
        warn_at=timedelta(seconds=30),
    )


# --- La apertura (BR2.1, BR2.3) -----------------------------------------------


async def test_lo_primero_que_suena_es_la_apertura(catalogo: None) -> None:
    """Y la divulgacion queda registrada con la hora del **fin** de la emision."""
    motor = await _motor()
    canal = CanalFalso(entrantes=[voz.Hangup()])
    doble = VozDoble()

    motivo = await _correr(motor, canal, doble).run()

    assert motivo is voz.EndReason.HANGUP
    assert doble.dicho, "la apertura no se sintetizo"
    assert "transcrib" in doble.dicho[0].lower()
    assert motor.disclosed_at is not None


async def test_sin_apertura_registrada_no_se_atiende_ningun_turno(catalogo: None) -> None:
    """BR2.1, mirada desde el motor: la compuerta es la hora de fin, no una
    bandera del ciclo, y por eso el ciclo no puede saltarsela."""
    motor = await _motor()
    assert motor.needs_opening_again is True
    with pytest.raises(ValueError, match=r"BR2\.1"):
        async for _ in motor.speak_turn(
            voz.SpeechEnd(text="hola", at=AHORA, last_audible_word_at=None, last=_final("hola")),
            turn_id="t1",
        ):
            pass


# --- El reloj arranca cuando termina de sonar, no cuando termina el envio -------


async def test_el_silencio_se_cuenta_desde_que_termina_de_sonar_la_frase(catalogo: None) -> None:
    """Lo vio Miguel en la primera llamada real (2026-10-06): la apertura dura
    unos veinte segundos en el navegador y el servidor la manda en uno; a los
    cinco segundos de empezar a sonar la agente preguntaba "¿sigue ahi?" y acababa
    colgando sola.

    Veinte segundos de audio son 960 000 bytes (PCM de 16 bits, 24 kHz, mono):
    el fin estimado de la reproduccion es veinte segundos despues de empezar a
    enviar, y la tolerancia de silencio cuenta desde ahi.
    """
    motor = await _motor()
    canal = CanalFalso()
    # 2 000 trozos de 480 bytes: veinte segundos de audio.
    doble = VozDoble(trozos=2000)
    ciclo = _correr(motor, canal, doble)

    interrumpida = await ciclo._decir(motor.opening())

    assert not interrumpida
    assert ciclo.playback_ends_at == _reloj() + timedelta(seconds=20)
    assert ciclo.silent_since() == _reloj() + timedelta(seconds=20)
    assert (
        motor.silence_deadline(since=ciclo.silent_since())
        == _reloj() + timedelta(seconds=20) + motor.silence_tolerance
    )


async def test_un_parcial_aplaza_el_sigue_ahi_aunque_no_cierre_el_turno(catalogo: None) -> None:
    """Visto en produccion el 2026-10-07: la persona hablaba, llegaban parciales y
    ningun final, y a los ocho segundos la agente preguntaba «¿sigue ahi?». El
    silencio se cuenta desde lo ultimo que se oyo, parcial incluido."""
    motor = await _motor()
    ciclo = _correr(motor, CanalFalso(), VozDoble())
    callo_a = _reloj()
    detector = motor.listening(since=callo_a)

    sin_oir = ciclo._proximo_limite(detector, callo_a)
    assert sin_oir == callo_a + motor.silence_tolerance

    detector.observe(
        Transcript(text=ExternalText("en la"), is_final=False, words=()),
        at=callo_a + timedelta(seconds=6),
    )

    con_parcial = ciclo._proximo_limite(detector, callo_a)
    assert con_parcial == callo_a + timedelta(seconds=6) + motor.silence_tolerance
    assert detector.deadline is None, "el parcial no cierra el turno"


async def test_la_consola_no_dice_escuchando_mientras_la_apertura_sigue_sonando(
    catalogo: None,
) -> None:
    """El estado "escuchando" se anuncia cuando termina de sonar. Antes salia en
    cuanto terminaba el envio, con la agente todavia hablando por el altavoz."""
    motor = await _motor()
    canal = CanalFalso(entrantes=[voz.Hangup()])
    doble = VozDoble(trozos=2000)

    motivo = await asyncio.wait_for(_correr(motor, canal, doble).run(), timeout=5)

    assert motivo is voz.EndReason.HANGUP
    estados = [c.value for c in canal.de_tipo(voz.State)]
    assert "speaking" in estados
    assert "listening" not in estados, estados
    # Y la divulgacion queda registrada con la hora en que termina de sonar.
    assert motor.disclosed_at == _reloj() + timedelta(seconds=20)


async def test_escuchando_sale_en_cuanto_termina_de_sonar(catalogo: None) -> None:
    """Con un reloj que avanza, "escuchando" se anuncia al pasar el fin estimado
    de la reproduccion. El reloj de la suite esta quieto a proposito y con el
    treinta milisegundos nunca pasan; aqui se usa uno que avanza un decimo de
    segundo por mirada, que es lo que hace cualquier reloj de verdad."""
    motor = await _motor()
    canal = CanalFalso(
        entrantes=[SILENCIO],
        seguir=lambda: not any(c.value == "listening" for c in canal.de_tipo(voz.State)),
    )
    doble = VozDoble()
    reloj = _RelojQueAvanza(AHORA + timedelta(seconds=1))
    ciclo = CallRunner(
        engine=motor,
        channel=canal,
        speech=doble,
        now=reloj,
        max_call=timedelta(seconds=180),
        warn_at=timedelta(seconds=30),
    )

    await asyncio.wait_for(ciclo.run(), timeout=5)

    estados = [c.value for c in canal.de_tipo(voz.State)]
    assert "listening" in estados, estados
    assert estados.index("speaking") < estados.index("listening")


@dataclass
class _RelojQueAvanza:
    """Un reloj que avanza cien milisegundos cada vez que alguien lo mira."""

    actual: datetime

    def __call__(self) -> datetime:
        self.actual += timedelta(milliseconds=100)
        return self.actual


# --- La interrupcion (BR4.1, BR4.3, BR4.5) ------------------------------------


async def test_lo_dicho_durante_la_apertura_ni_la_corta_ni_cuenta(catalogo: None) -> None:
    """Decision de Miguel del 2026-10-14: la apertura no se interrumpe y mientras suena no
    se escucha; la conversacion empieza cuando ella termina.

    Antes una frase con contenido la cortaba (`stop_audio`) y la apertura se repetia entera
    (BR4.5): quien hablaba al conectar la oia hasta tres veces. El evento del descarte es lo
    que distingue "se oyo y se descarto" de "no llego nada".
    """
    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        motor = await _motor()
        doble = VozDoble(guion=[_final("wait I need to correct something")], antes_del_audio=True)
        canal = CanalFalso(entrantes=[SILENCIO], seguir=lambda: motor.disclosed_at is None)

        await asyncio.wait_for(_correr(motor, canal, doble).run(), timeout=5)
    finally:
        observability.set_stream(sys.stdout)

    assert canal.de_tipo(voz.StopAudio) == [], "lo dicho encima corto la apertura"
    assert len(doble.dicho) == 1, "la apertura se repitio"
    assert motor.disclosed_at is not None, "la apertura nunca llego a registrarse"
    assert _lo_que_vio_la_persona(canal) == [], "lo dicho encima se trato como un turno"
    descartes = _eventos(salida, "voice.heard_during_opening_discarded")
    assert [e["words"] for e in descartes] == [6]


async def test_fuera_de_la_apertura_interrumpir_manda_stop_audio(catalogo: None) -> None:
    """BR4.3, en cualquier frase que no sea la apertura: el servidor no puede retirar el
    audio que ya mando, asi que manda `stop_audio` y quien vacia la cola es el navegador."""
    motor = await _motor()
    await _abierta(motor)
    canal = CanalFalso()
    ciclo = _correr(motor, canal, VozDoble())
    ciclo._oido.put_nowait(_final("wait I need to correct something"))

    frase = motor._hablar(c14.FinalText(message_id="m-1", text="Noted, thanks.", language="en"))
    interrumpida = await ciclo._decir(frase)

    assert interrumpida
    assert len(canal.de_tipo(voz.StopAudio)) == 1
    assert "wait I need to correct something" in _lo_que_vio_la_persona(canal)


async def test_el_ruido_de_una_palabra_no_interrumpe(catalogo: None) -> None:
    """BR4.2: el eco del altavoz y el ruido de carro no callan a la agente.

    Lo que los filtra es el piso de palabras, y sin esta prueba la interrupcion
    pasaria igual con el piso en uno --que es decir sin piso--. Sobre una frase que no es
    la apertura, porque lo dicho encima de la apertura no se escucha (2026-10-14).
    """
    motor = await _motor()
    await _abierta(motor)
    canal = CanalFalso()
    ciclo = _correr(motor, canal, VozDoble())
    ciclo._oido.put_nowait(_final("uh", confianza=0.4))

    frase = motor._hablar(c14.FinalText(message_id="m-1", text="Noted, thanks.", language="en"))
    interrumpida = await ciclo._decir(frase)

    assert not interrumpida
    assert canal.de_tipo(voz.StopAudio) == []


# --- La transcripcion que ve la consola (BR7.2, cambiada el 2026-10-09) ---------


async def test_la_persona_ve_en_su_consola_lo_que_dijo_tal_cual(catalogo: None) -> None:
    """Decision de Miguel del 2026-10-09: sus propias palabras no le salen tapadas.
    Lo que se guarda en el caso sigue redactado; eso lo prueba `transcript_writer`."""
    motor = await _motor()
    doble = VozDoble(guion=[_final("call me at 305 555 0147")])
    # Despues de la apertura: lo dicho encima no se escucha (2026-10-14).
    doble.esperar_a = lambda: motor.disclosed_at is not None
    canal = CanalFalso(entrantes=[SILENCIO], seguir=lambda: not _lo_que_vio_la_persona(canal))

    await asyncio.wait_for(_correr(motor, canal, doble).run(), timeout=5)

    del_asegurado = [c for c in canal.de_tipo(voz.Transcript) if c.speaker == "insured"]
    assert del_asegurado, "la consola no vio ninguna transcripcion de la persona"
    assert any("0147" in c.text for c in del_asegurado)
    assert all("[" not in c.text for c in del_asegurado)


async def test_la_agente_tambien_se_lee_sin_tapar_en_la_consola_y_suena_sin_etiquetas(
    catalogo: None,
) -> None:
    """2026-10-13, pedido cuatro veces: lo que la agente le dice a la persona se ve en su
    pantalla tal cual. Al sintetizador va tapado, y de ahi no sale ninguna etiqueta."""
    motor = await _motor()
    canal = CanalFalso()
    doble = VozDoble()
    ciclo = _correr(motor, canal, doble)
    escrito = "I have your plate as ABC123."

    dicha = motor._hablar(c14.FinalText(message_id="m-1", text=escrito, language="en"))
    await ciclo._decir(dicha)

    de_la_agente = [c.text for c in canal.de_tipo(voz.Transcript) if c.speaker == "agent"]
    assert de_la_agente == [escrito]
    assert len(doble.dicho) == 1
    assert "ABC123" not in doble.dicho[0]
    assert "[" not in doble.dicho[0]
    assert "that plate" in doble.dicho[0]


async def test_la_respuesta_del_fondo_llega_a_la_consola_en_dos_lineas_sin_tapar(
    catalogo: None,
) -> None:
    """La respuesta, y aparte "volviendo al reporte" con su pregunta: la primera es la que
    la base guarda, y la pantalla del caso la destapa solo si llega entera."""
    motor = await _motor()
    canal = CanalFalso()
    doble = VozDoble()
    ciclo = _correr(motor, canal, doble)
    motor._pregunta_pendiente = "What is your license plate?"
    respuesta = "Your policy covers towing for ABC123."

    await ciclo._decir(motor.background_answer(respuesta))

    de_la_agente = [c.text for c in canal.de_tipo(voz.Transcript) if c.speaker == "agent"]
    assert len(de_la_agente) == 2
    assert de_la_agente[0] == respuesta
    assert de_la_agente[1].endswith("What is your license plate?")
    # Y suena como una sola frase, sin la placa ni etiqueta alguna.
    assert len(doble.dicho) == 1
    assert "ABC123" not in doble.dicho[0]
    assert "[" not in doble.dicho[0]


# --- U17, BR3.3: la latencia de la consola es la de la traza ------------------


async def test_la_latencia_que_va_a_la_consola_es_la_que_quedo_en_la_traza(
    catalogo: None,
) -> None:
    """Un solo numero, dos consumidores (BR3.3 de U17).

    Dos cifras con el mismo nombre que no coinciden convierten la consola en una
    pantalla que no se puede creer, y esta es la que quien evalua va a comprobar.
    Asi que se comprueba lo unico que lo garantiza: que el milisegundo del cuadro
    sea **el mismo** que el del evento de la traza, no uno parecido.
    """
    del catalogo
    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        motor = await _motor()
        # El guion habla **despues** de la apertura, que es cuando hay un turno que
        # contestar; y la llamada se mantiene viva hasta que la latencia de ese
        # turno sale hacia la consola.
        doble = VozDoble(guion=[_final("does my policy cover a rental car?")])
        canal = CanalFalso(seguir=lambda: not canal.de_tipo(voz.Latency))
        doble.esperar_a = lambda: motor.disclosed_at is not None
        # Con un reloj que avanza: el turno se atiende cuando la apertura **termina de
        # sonar**; con el reloj quieto ese instante no llega nunca.
        ciclo = CallRunner(
            engine=motor,
            channel=canal,
            speech=doble,
            now=_RelojQueAvanza(AHORA + timedelta(seconds=1)),
            max_call=timedelta(seconds=180),
            warn_at=timedelta(seconds=30),
        )

        await asyncio.wait_for(ciclo.run(), timeout=10)
    finally:
        observability.set_stream(sys.stdout)

    de_la_traza = [
        json.loads(linea)
        for linea in salida.getvalue().splitlines()
        if linea and json.loads(linea).get("event") == "voice.first_audio"
    ]
    a_la_consola = canal.de_tipo(voz.Latency)

    assert de_la_traza, "la traza no registro el primer audio de ningun turno"
    assert len(a_la_consola) == len(de_la_traza), "la consola vio otra cantidad de turnos"
    for evento, cuadro in zip(de_la_traza, a_la_consola, strict=True):
        assert cuadro.elapsed_ms == evento["elapsed_ms"]
        assert cuadro.turn_id == evento["turn_id"]


# --- El corte (BR6.1) ---------------------------------------------------------


async def test_el_socket_que_muere_sin_colgar_es_un_corte(catalogo: None) -> None:
    """Un corte no es un final: es una pausa, y por eso lleva otro motivo."""
    motor = await _motor()
    canal = CanalFalso(entrantes=[SILENCIO])
    doble = VozDoble()

    motivo = await asyncio.wait_for(_correr(motor, canal, doble).run(), timeout=5)

    assert motivo is voz.EndReason.DROPPED


async def test_la_duracion_maxima_termina_la_llamada_con_su_motivo(catalogo: None) -> None:
    """Un conjunto cerrado que no pudiera decir esto dejaria la consola sin
    explicacion para el unico final que no decide nadie."""
    motor = await _motor()
    canal = CanalFalso(entrantes=[SILENCIO])
    doble = VozDoble()
    ciclo = CallRunner(
        engine=motor,
        channel=canal,
        speech=doble,
        now=lambda: AHORA + timedelta(hours=1),
        max_call=timedelta(seconds=180),
        warn_at=timedelta(seconds=30),
    )

    motivo = await asyncio.wait_for(ciclo.run(), timeout=5)

    assert motivo is voz.EndReason.MAX_DURATION


def test_el_reloj_de_la_prueba_no_es_el_del_sistema() -> None:
    """El ciclo mide la duracion contra el instante en que la llamada empezo.

    Con el reloj del sistema, una llamada sembrada en una fecha fija nace con sus
    tres minutos vencidos y termina antes de decir nada. Costo dos pruebas
    esperando `dropped` y recibiendo `max_duration`; queda escrito aqui.
    """
    assert _reloj() - AHORA < timedelta(seconds=180)
    assert _reloj() != datetime.now(UTC)


# --- Llamar por otro accidente (BR6.4) ----------------------------------------


async def test_decir_que_llama_por_otro_accidente_abre_un_caso_nuevo(
    catalogo: None,
) -> None:
    """Y el anterior queda intacto. Tres cosas se comprueban juntas a proposito.

    La primera: la llamada acaba trabajando sobre el caso nuevo, no sobre el que
    se le ofrecio.

    La segunda: la divulgacion queda registrada **tambien** contra el caso nuevo,
    con la hora en que se dijo. Sin eso, el caso con el que la llamada termina no
    tendria divulgacion registrada y BR2.1 se rompe por la puerta de atras: la
    compuerta seguiria verde porque mira el caso viejo.

    La tercera: la consola recibe el cuadro `case` con el numero, que es lo unico
    que le permite mostrarlo.
    """
    aseguradora = tenancy.available_ids()[0]
    anterior = await nuevo_caso(aseguradora)
    cortada = await voz.open_call(
        tenant_id=aseguradora,
        visitor_key_digest="digest-de-prueba",
        language="en",
        voice_mode=VoiceMode.PRIMARY,
        now=AHORA,
    )
    cortada = await voz.attach_case(cortada, case_id=anterior.case_id)
    cortada = await voz.end_call(
        cortada, reason=voz.EndReason.DROPPED, now=AHORA, resume_window=timedelta(minutes=15)
    )

    motor = await _motor()
    motor.call = await voz.switch_case(motor.call, case_id=anterior.case_id)
    await motor.look_for_resumable(cortada)

    doble = VozDoble(guion=[_final("no this is a different accident")])
    canal = CanalFalso(seguir=lambda: not canal.de_tipo(voz.Case))
    doble.esperar_a = lambda: len(doble.dicho) >= 2

    await asyncio.wait_for(_correr(motor, canal, doble).run(), timeout=10)

    cuadros = canal.de_tipo(voz.Case)
    assert cuadros, "la consola no recibio el caso nuevo"
    nuevo_id = cuadros[0].case_id
    assert nuevo_id != anterior.case_id
    assert motor.call.case_id == nuevo_id
    assert await casos.get_case(aseguradora, anterior.case_id) is not None
    assert await _divulgacion_registrada(aseguradora, nuevo_id), (
        "el caso con el que la llamada termina no tiene divulgacion registrada"
    )


async def _divulgacion_registrada(tenant_id: str, case_id: str) -> bool:
    """Si ese caso tiene su apertura de voz anotada.

    Se consulta la tabla de U10 directamente porque su superficie escribe y no
    lee: lo que se comprueba aqui es que la fila esta, que es lo unico que
    sostiene la compuerta BR2.1.
    """
    async with db.session_for(tenant_id) as sesion:
        fila = await db.fetch_one(
            sesion,
            "SELECT count(*) AS total FROM disclosure_record "
            "WHERE case_id = :case_id AND channel = 'voice'",
            case_id=case_id,
        )
    return fila is not None and int(fila["total"]) > 0


# --- Los presupuestos propios de la unidad (PERF-U16.1) -----------------------


async def test_lo_que_esta_unidad_anade_al_turno_cabe_en_su_presupuesto(
    catalogo: None,
) -> None:
    """PERF-U16.1: p95 ≤ 60 ms entre el fin del habla y el primer byte a la síntesis.

    **Es el número que se pone rojo cuando alguien mete trabajo en el camino del
    turno.** NFR1 es una meta de punta a punta y la mayor parte de su presupuesto
    se la comen el reconocedor, el modelo y la síntesis --U15 midió 697 ms al
    primer audio con Catalina--, así que esa meta se mide por hito. Lo que esta
    unidad vigila en cada entrega es lo suyo, y lo suyo es esto.

    Sin proveedores: el grafo y la síntesis entran por sus puertos, doblados. Lo
    que queda dentro del reloj es el detector, la decisión de si se entendió, la
    resolución del código dictado, la redacción y la lectura del caso.

    Se mide el p95 de veinte turnos y no un turno suelto: un turno solo mide la
    máquina de ese instante.
    """
    motor = await _motor()
    motor.disclosed_at = _reloj()

    muestras: list[float] = []
    for i in range(20):
        fin = voz.SpeechEnd(
            text="me chocaron por detras",
            at=_reloj(),
            last_audible_word_at=None,
            last=_final("me chocaron por detras"),
        )
        # Se cierra el generador al salir (`aclosing`): un `break` lo dejaria abierto, y con
        # el rastro del turno abierto el turno siguiente ya no cabe.
        async with contextlib.aclosing(motor.speak_turn(fin, turn_id=f"t{i}")) as frases:
            inicio = time.perf_counter()
            # El primero es el que cuenta: es el byte que sale hacia la sintesis.
            await anext(frases)
            muestras.append((time.perf_counter() - inicio) * 1000)

    muestras.sort()
    p95 = muestras[int(len(muestras) * 0.95) - 1]
    # Se imprime siempre, no solo al fallar: el numero es la cifra que la unidad
    # publica por entrega, y una cifra que solo se ve cuando esta mal no sirve
    # para notar que va subiendo.
    print(f"PERF-U16.1: p95 {p95:.1f} ms sobre {len(muestras)} turnos")
    assert p95 <= PRESUPUESTO_PROPIO_MS, f"p95 de {p95:.1f} ms, muestras {muestras}"


async def test_un_turno_abierto_nunca_se_lee_como_silencio(catalogo: None) -> None:
    """Medido en una llamada real el 2026-10-07: finales a los 17,3 y 17,8 s, plazo
    del turno a los 18,5 s, y la agente pregunto «¿sigue ahi?» a los 18,4 s. La
    espera volvio un instante antes del plazo y eso caia en la rama del silencio,
    que ademas tiraba la frase ya transcrita."""
    motor = await _motor(end_of_speech=timedelta(milliseconds=700))
    ciclo = _correr(motor, CanalFalso(), VozDoble())
    callo_a = _reloj()
    detector = motor.listening(since=callo_a)
    final_a = callo_a + timedelta(seconds=6)
    detector.observe(_final("tuve un choque en la calle diez"), at=final_a)
    plazo = final_a + timedelta(milliseconds=700)

    un_instante_antes = ciclo._que_toca(detector, callo_a, plazo - timedelta(microseconds=1))
    al_vencer = ciclo._que_toca(detector, callo_a, plazo)

    assert un_instante_antes == "esperar"
    assert al_vencer == "turno"


async def test_el_silencio_solo_cuenta_cuando_su_plazo_paso(catalogo: None) -> None:
    motor = await _motor()
    ciclo = _correr(motor, CanalFalso(), VozDoble())
    callo_a = _reloj()
    detector = motor.listening(since=callo_a)
    vence = callo_a + motor.silence_tolerance

    assert ciclo._que_toca(detector, callo_a, vence - timedelta(microseconds=1)) == "esperar"
    assert ciclo._que_toca(detector, callo_a, vence) == "silencio"


# --- El final: la llamada no termina hasta que suena lo ultimo (2026-10-10) --------


async def test_la_llamada_espera_a_que_termine_de_sonar_la_despedida(catalogo: None) -> None:
    """Enviar el audio no es que se haya oido.

    La despedida de un reporte completo lleva el numero de caso y tarda segundos en
    sonar. El servidor daba la llamada por terminada al acabar de **enviarla**, la
    pagina cerraba el audio y el numero se cortaba.
    """
    ciclo = _correr(await _motor(), CanalFalso(), VozDoble())
    ciclo._sonando_hasta = _reloj() + timedelta(seconds=0.3)

    inicio = time.perf_counter()
    await ciclo._dejar_sonar(voz.EndReason.COMPLETED)
    espero = time.perf_counter() - inicio

    assert espero >= 0.3 + FINAL_PLAYBACK_GRACE_S - 0.1, espero


@pytest.mark.parametrize(
    "motivo", [voz.EndReason.HANGUP, voz.EndReason.DROPPED, voz.EndReason.ERROR]
)
async def test_si_ya_no_hay_quien_oiga_no_se_espera(catalogo: None, motivo: voz.EndReason) -> None:
    ciclo = _correr(await _motor(), CanalFalso(), VozDoble())
    ciclo._sonando_hasta = _reloj() + timedelta(seconds=5)

    inicio = time.perf_counter()
    await ciclo._dejar_sonar(motivo)

    assert time.perf_counter() - inicio < 0.2


async def test_colgar_mientras_suena_la_despedida_suelta_la_espera(catalogo: None) -> None:
    ciclo = _correr(await _motor(), CanalFalso(), VozDoble())
    ciclo._sonando_hasta = _reloj() + timedelta(seconds=5)
    ciclo._colgo = True

    inicio = time.perf_counter()
    await ciclo._dejar_sonar(voz.EndReason.COMPLETED)

    assert time.perf_counter() - inicio < 0.2


async def test_la_espera_del_final_tiene_tope(
    catalogo: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un calculo de reproduccion disparatado no deja la llamada abierta para siempre."""
    monkeypatch.setattr(loop_voz, "FINAL_PLAYBACK_MAX_S", 0.2)
    ciclo = _correr(await _motor(), CanalFalso(), VozDoble())
    ciclo._sonando_hasta = _reloj() + timedelta(hours=1)

    inicio = time.perf_counter()
    await ciclo._dejar_sonar(voz.EndReason.COMPLETED)

    assert time.perf_counter() - inicio < 1.0


# --- La respuesta que trae el fondo, dicha en la llamada (2026-10-11) ---------------


async def _abierta(motor: voz.CallEngine) -> None:
    """La apertura dicha y registrada: deja en el aire su primera pregunta."""
    motor.opening()
    await motor.opening_finished(at=AHORA)


async def test_mientras_se_espera_la_respuesta_no_se_pregunta_si_sigue_ahi(
    catalogo: None,
) -> None:
    """La agente dijo "dejame revisar tu poliza": quien calla es ella. Antes, a los
    cinco segundos le preguntaba a la persona si seguia ahi."""
    motor = await _motor()
    ciclo = _correr(motor, CanalFalso(), VozDoble())
    callo_a = _reloj()
    detector = motor.listening(since=callo_a)
    ciclo._respuesta_hasta = callo_a + ANSWER_WAIT
    pasado_el_silencio = callo_a + motor.silence_tolerance + timedelta(seconds=1)

    assert ciclo._que_toca(detector, callo_a, pasado_el_silencio) == "esperar"
    assert ciclo._que_toca(detector, callo_a, callo_a + ANSWER_WAIT) == "sin_respuesta"


async def test_la_respuesta_de_cobertura_se_dice_en_la_llamada(catalogo: None) -> None:
    """Antes no llegaba nunca: quien la entregaba solo conocia el chat."""
    motor = await _motor()
    await _abierta(motor)
    doble = VozDoble()
    ciclo = _correr(motor, CanalFalso(), doble)
    callo_a = _reloj()
    detector = motor.listening(since=callo_a)
    ciclo._escuchar_al_fondo()
    ciclo._respuesta_hasta = callo_a + ANSWER_WAIT
    assert motor.call.case_id is not None

    entregada = await answers.CASE_NOTIFIER.notify(
        motor.call.tenant_id, motor.call.case_id, text="In your policy, Part D addresses this."
    )
    hubo, motivo = await ciclo._al_vencer(detector, callo_a, _reloj())

    assert entregada is True
    assert (hubo, motivo) == (True, None)
    assert doble.dicho[-1].startswith("In your policy, Part D addresses this.")
    # Y retoma la pregunta que la persona todavia debe.
    assert doble.dicho[-1].endswith("How can I help you?")
    ciclo._dejar_de_escuchar_al_fondo()
    assert ciclo._respuesta_hasta is None


async def test_la_respuesta_no_se_dice_encima_de_la_persona(catalogo: None) -> None:
    motor = await _motor(end_of_speech=timedelta(seconds=1))
    await _abierta(motor)
    doble = VozDoble()
    ciclo = _correr(motor, CanalFalso(), doble)
    detector = motor.listening(since=_reloj())
    detector.observe(_final("and another thing about"), at=_reloj())
    ciclo._llego_del_fondo(answers.BackgroundAnswer(text="In your policy, Part D."))

    dijo = await ciclo._decir_lo_del_fondo(detector)

    assert dijo is False
    assert doble.dicho == []
    assert len(ciclo._por_decir) == 1, "queda por decir, no se pierde"


async def test_si_la_respuesta_no_llega_a_tiempo_se_dice_que_sigue_revisando(
    catalogo: None,
) -> None:
    motor = await _motor()
    await _abierta(motor)
    doble = VozDoble()
    ciclo = _correr(motor, CanalFalso(), doble)
    callo_a = _reloj() - ANSWER_WAIT
    detector = motor.listening(since=callo_a)
    ciclo._respuesta_hasta = callo_a + ANSWER_WAIT

    hubo, motivo = await ciclo._al_vencer(detector, callo_a, _reloj())

    assert (hubo, motivo) == (True, None)
    assert "still checking" in doble.dicho[-1]
    assert doble.dicho[-1].endswith("How can I help you?")
    # Dicho que sigue revisando, **sigue esperando**: antes aqui quedaba `None` y a los
    # cinco segundos arrancaba el silencio contra la persona (2026-10-11).
    assert ciclo._respuesta_hasta == ciclo.silent_since() + LATE_ANSWER_WAIT


async def test_sin_llamada_viva_la_respuesta_no_es_para_la_voz(catalogo: None) -> None:
    """Devuelve que no habia nadie, y quien lo enchufa prueba entonces con el chat."""
    motor = await _motor()
    ciclo = _correr(motor, CanalFalso(), VozDoble())
    assert motor.call.case_id is not None
    destino = (motor.call.tenant_id, motor.call.case_id)

    antes = await answers.CASE_NOTIFIER.notify(*destino, text="x")
    ciclo._escuchar_al_fondo()
    durante = await answers.CASE_NOTIFIER.notify(*destino, text="x")
    ciclo._dejar_de_escuchar_al_fondo()
    despues = await answers.CASE_NOTIFIER.notify(*destino, text="x")

    assert (antes, durante, despues) == (False, True, False)


async def test_un_turno_que_cierra_con_la_frase_de_espera_abre_la_espera(
    catalogo: None,
) -> None:
    async def _revisando(turn: c14.InboundTurn) -> AsyncIterator[c14.TurnEvent]:
        del turn
        yield c14.Waiting(
            copy_key=copy_api.CopyKey("orchestration.turn.waiting"), text="One moment."
        )

    motor = await _motor()
    motor.handle_turn = con_rastro(_revisando)
    await _abierta(motor)
    ciclo = _correr(motor, CanalFalso(), VozDoble())
    habla = voz.SpeechEnd(
        text="does my policy cover this",
        at=_reloj(),
        last_audible_word_at=None,
        last=_final("does my policy cover this"),
    )

    motivo = await ciclo._atender(habla)

    assert motivo is None
    assert ciclo._respuesta_hasta == ciclo.silent_since() + ANSWER_WAIT


# --- El tiempo de la llamada: se avisa en voz alta y no corta en seco ---------------


async def test_el_aviso_de_que_queda_poco_tambien_se_dice(catalogo: None) -> None:
    """Antes solo salia en la pantalla, y quien habla por telefono no la mira."""
    motor = await _motor()
    canal, doble = CanalFalso(), VozDoble()
    ciclo = _correr(motor, canal, doble)
    a_la_hora = AHORA + timedelta(seconds=180 - 30)

    primero = await ciclo._avisar(a_la_hora, hablando=False)
    segundo = await ciclo._avisar(a_la_hora, hablando=False)

    assert (primero, segundo) == (True, False)
    assert len(canal.de_tipo(voz.Notice)) == 1
    assert doble.dicho == [copy_api.t(copy_api.CopyKey("voice.time.running_out"), locale="en")]


async def test_el_aviso_no_interrumpe_a_quien_habla_y_se_dice_antes_de_responderle(
    catalogo: None,
) -> None:
    motor = await _motor()
    await _abierta(motor)
    canal, doble = CanalFalso(), VozDoble()
    ciclo = _correr(motor, canal, doble)

    await ciclo._avisar(AHORA + timedelta(seconds=150), hablando=True)
    assert doble.dicho == []
    await ciclo._atender(
        voz.SpeechEnd(text="hello", at=_reloj(), last_audible_word_at=None, last=_final("hello"))
    )

    aviso = copy_api.t(copy_api.CopyKey("voice.time.running_out"), locale="en")
    assert doble.dicho == [aviso, "Noted."]


async def test_al_acabarse_el_tiempo_la_llamada_se_despide_con_el_numero(
    catalogo: None,
) -> None:
    """Antes cortaba en seco, sin numero de caso."""
    motor = await _motor()
    await _abierta(motor)
    assert motor.call.case_id is not None
    vista = await casos.get_case(motor.call.tenant_id, motor.call.case_id)
    assert vista is not None
    doble = VozDoble()
    ciclo = _correr(motor, CanalFalso(), doble)

    motivo = await ciclo._despedirse_por_tiempo()
    await asyncio.sleep(0.2)  # la derivacion va en el fondo

    assert motivo is voz.EndReason.MAX_DURATION
    assert "out of time" in doble.dicho[-1]
    assert voz_numero(str(vista.case_number)) in doble.dicho[-1]


def voz_numero(numero: str) -> str:
    from untangle.voice import case_number

    return case_number.spell(numero, language="en")


async def test_la_despedida_empieza_antes_del_limite_para_caber_en_el(catalogo: None) -> None:
    motor = await _motor()
    ciclo = _correr(motor, CanalFalso(), VozDoble())

    assert ciclo._momento_del_aviso < ciclo._hora_de_despedirse < ciclo._fin_de_llamada


# --- Interrumpir: no se habla encima, y la despedida se dice entera (2026-10-11) ----


def _turno_con(
    ciclo: CallRunner, frases: Sequence[voz.Utterance], *, interrumpe_la: int | None
) -> list[tuple[str, bool]]:
    """Sustituye lo que el motor dice y como suena, para mirar solo el orden.

    Devuelve lo dicho, con si cada frase se podia interrumpir.
    """
    dichas: list[tuple[str, bool]] = []

    async def hablar(speech: voz.SpeechEnd, *, turn_id: str) -> AsyncGenerator[voz.Utterance]:
        del speech, turn_id
        for frase in frases:
            yield frase

    async def decir(frase: voz.Utterance, **opciones: object) -> bool:
        dichas.append((str(frase.text), bool(opciones.get("interrumpible", True))))
        return interrumpe_la is not None and len(dichas) == interrumpe_la

    ciclo.engine.speak_turn = hablar  # type: ignore[method-assign]
    ciclo._decir = decir  # type: ignore[method-assign]
    return dichas


def _dicho(texto: str, motivo: voz.EndReason | None = None) -> voz.Utterance:
    from untangle.compliance.redaction import api as redaccion

    return voz.Utterance(text=redaccion.from_catalog(texto, language="en"), end_reason=motivo)


_HABLA = voz.SpeechEnd(text="hello", at=AHORA, last_audible_word_at=None, last=_final("hello"))


async def test_si_la_persona_interrumpe_no_se_le_dice_encima_el_resto_del_turno(
    catalogo: None,
) -> None:
    """Antes se cortaba la frase en curso y las siguientes del mismo turno sonaban
    igual, encima de quien acababa de interrumpir."""
    motor = await _motor()
    await _abierta(motor)
    ciclo = _correr(motor, CanalFalso(), VozDoble())
    dichas = _turno_con(ciclo, [_dicho("One."), _dicho("Two."), _dicho("Three.")], interrumpe_la=1)

    motivo = await ciclo._atender(_HABLA)

    assert motivo is None
    assert [texto for texto, _ in dichas] == ["One."]


async def test_el_cierre_de_un_reporte_se_aplaza_si_la_persona_seguia_hablando(
    catalogo: None,
) -> None:
    """Visto en una llamada: la persona iba a decir que carro manejaba, la agente la
    corto con "anotado" y enseguida se despidio. Ahora la oye primero."""
    motor = await _motor()
    await _abierta(motor)
    motor.closed = True  # el motor ya habia decidido cerrar
    ciclo = _correr(motor, CanalFalso(), VozDoble())
    dichas = _turno_con(
        ciclo,
        [_dicho("Noted."), _dicho("Your case number is one two three.", voz.EndReason.COMPLETED)],
        interrumpe_la=1,
    )

    motivo = await ciclo._atender(_HABLA)

    assert motivo is None, "la llamada sigue: falta oir a la persona"
    assert [texto for texto, _ in dichas] == ["Noted."]
    assert motor.closed is False, "el cierre se vuelve a decidir despues de su turno"


async def test_la_despedida_no_se_puede_cortar_a_la_mitad(catalogo: None) -> None:
    """Lleva el numero de caso, que es lo unico que la persona se lleva."""
    motor = await _motor()
    await _abierta(motor)
    ciclo = _correr(motor, CanalFalso(), VozDoble())
    dichas = _turno_con(
        ciclo,
        [_dicho("Noted."), _dicho("Your case number is one two three.", voz.EndReason.COMPLETED)],
        interrumpe_la=None,
    )

    motivo = await ciclo._atender(_HABLA)

    assert motivo is voz.EndReason.COMPLETED
    assert dichas == [("Noted.", True), ("Your case number is one two three.", False)]


# --- La llamada por una duda de la poliza abre una consulta (2026-10-11) ------------


async def test_llamar_por_una_duda_de_la_poliza_abre_una_consulta_y_no_un_reporte(
    catalogo: None,
) -> None:
    """Antes toda llamada era un reporte de accidente y empezaba por los heridos."""
    recibidos: list[c14.InboundTurn] = []

    async def grafo(turn: c14.InboundTurn) -> AsyncIterator[c14.TurnEvent]:
        recibidos.append(turn)
        yield c14.FinalText(message_id="m1", text="Noted.", language=turn.language)

    motor = await _motor()
    motor.handle_turn = con_rastro(grafo)
    await _abierta(motor)
    del_reporte = motor.call.case_id
    canal = CanalFalso()
    ciclo = _correr(motor, canal, VozDoble())
    dicho = "I have a question about my policy"

    await ciclo._atender(
        voz.SpeechEnd(text=dicho, at=_reloj(), last_audible_word_at=None, last=_final(dicho))
    )

    assert motor.call.case_id is not None
    assert motor.call.case_id != del_reporte
    consulta = await casos.get_case(motor.call.tenant_id, motor.call.case_id)
    assert consulta is not None
    assert consulta.record_type.value == "coverage_inquiry"
    # El turno se entrega ya sobre la consulta, y la pantalla recibe su numero.
    assert [t.case_id for t in recibidos] == [motor.call.case_id]
    assert [c.case_id for c in canal.de_tipo(voz.Case)] == [motor.call.case_id]


async def test_llamar_por_un_accidente_sigue_con_el_caso_de_la_llamada(catalogo: None) -> None:
    motor = await _motor()
    await _abierta(motor)
    del_reporte = motor.call.case_id
    ciclo = _correr(motor, CanalFalso(), VozDoble())
    dicho = "I was rear-ended on the highway this morning"

    await ciclo._atender(
        voz.SpeechEnd(text=dicho, at=_reloj(), last_audible_word_at=None, last=_final(dicho))
    )

    assert motor.call.case_id == del_reporte


# --- Un saludo encima de la apertura no la corta (2026-10-11) -------------------


def _lo_que_vio_la_persona(canal: CanalFalso) -> list[str]:
    return [c.text for c in canal.de_tipo(voz.Transcript) if c.speaker == "insured"]


async def test_un_alo_mientras_se_envia_la_apertura_no_la_interrumpe(catalogo: None) -> None:
    """V7. Antes cualquier cosa dicha encima de la apertura la cortaba, y una apertura
    cortada se repite entera (BR4.5): quien decia "¿alo?" oia el saludo dos veces."""
    motor = await _motor()
    doble = VozDoble(guion=[_final("¿Aló?")], antes_del_audio=True)
    canal = CanalFalso(entrantes=[SILENCIO], seguir=lambda: motor.disclosed_at is None)

    await asyncio.wait_for(_correr(motor, canal, doble).run(), timeout=5)

    assert canal.de_tipo(voz.StopAudio) == [], "el saludo corto la apertura"
    assert len(doble.dicho) == 1, "la apertura se repitio"
    assert motor.disclosed_at is not None, "la apertura nunca llego a registrarse"
    assert _lo_que_vio_la_persona(canal) == [], "el saludo se trato como un turno"


# --- La agente no se oye a si misma (2026-10-13) ---------------------------------


@dataclass
class _VozConEco(VozDoble):
    """Un reconocedor que oye a la propia agente: en cuanto empieza a sonar una frase,
    entrega sus primeras palabras como si las hubiera dicho alguien. Es lo que hace el
    microfono de un portatil sin audifonos cuando la cancelacion de eco no alcanza."""

    palabras: int = 6

    async def _oir(self, audio: AsyncIterator[bytes]) -> AsyncIterator[ListenEvent]:
        while not self.dicho:  # noqa: ASYNC110 -- igual que `VozDoble`: la condicion es algo que ya paso
            await asyncio.sleep(0)
        yield _final(" ".join(self.dicho[0].split()[: self.palabras]))
        async for _ in audio:
            pass


async def test_el_eco_de_la_apertura_no_la_corta_ni_cuenta_como_turno(catalogo: None) -> None:
    """Lo que pidio Miguel: que la agente no se escuche a si misma, con o sin audifonos.

    Seis palabras de la propia apertura, oidas mientras suena: antes pasaban de sobra el
    piso de dos palabras, la agente se cortaba, repetia la apertura (BR4.5) y tomaba su
    propia frase como lo primero que dijo la persona.
    """
    motor = await _motor()
    doble = _VozConEco()
    canal = CanalFalso(entrantes=[SILENCIO], seguir=lambda: motor.disclosed_at is None)

    await asyncio.wait_for(_correr(motor, canal, doble).run(), timeout=5)

    assert canal.de_tipo(voz.StopAudio) == [], "la agente se corto con su propia voz"
    assert len(doble.dicho) == 1, "la apertura se repitio"
    assert motor.disclosed_at is not None, "la apertura nunca llego a registrarse"
    assert _lo_que_vio_la_persona(canal) == [], "el eco se pinto como dicho por la persona"


async def test_durante_la_apertura_ni_el_eco_ni_la_persona_la_cortan(catalogo: None) -> None:
    """El eco de la apertura y, pegada, una frase de la persona: ninguna de las dos la corta
    ni se pinta como dicha, porque mientras suena la apertura no se escucha (2026-10-14)."""
    motor = await _motor()

    @dataclass
    class _EcoYLuegoLaPersona(_VozConEco):
        async def _oir(self, audio: AsyncIterator[bytes]) -> AsyncIterator[ListenEvent]:
            while not self.dicho:  # noqa: ASYNC110 -- igual que `VozDoble`
                await asyncio.sleep(0)
            yield _final(" ".join(self.dicho[0].split()[: self.palabras]))
            yield _final("wait I need to correct something")
            async for _ in audio:
                pass

    doble = _EcoYLuegoLaPersona()
    canal = CanalFalso(entrantes=[SILENCIO], seguir=lambda: motor.disclosed_at is None)

    await asyncio.wait_for(_correr(motor, canal, doble).run(), timeout=5)

    assert canal.de_tipo(voz.StopAudio) == [], "algo corto la apertura"
    assert len(doble.dicho) == 1, "la apertura se repitio"
    assert _lo_que_vio_la_persona(canal) == []


async def test_fuera_de_la_apertura_el_filtro_quita_el_eco_y_deja_pasar_a_la_persona(
    catalogo: None,
) -> None:
    """La otra mitad: el filtro quita el eco, no calla el microfono. Con la apertura ya
    dicha, el eco de una frase de la agente se quita y las palabras de la persona pasan
    enteras, que es lo que despues puede cortarla."""
    motor = await _motor()
    await _abierta(motor)
    ciclo = _correr(motor, CanalFalso(), VozDoble())
    ciclo._flujo_empezo_a = _reloj()
    frase = "Thanks. What is the license plate of your car?"
    ciclo._propia_voz.begin(frase, starts_at=_reloj())
    persona = _final("wait I need to correct something")

    assert ciclo._sin_la_voz_de_la_agente(_final(" ".join(frase.split()[:6]))) is None
    assert ciclo._sin_la_voz_de_la_agente(persona) is persona


@pytest.mark.parametrize("saludo", ["hola", "hello", "yes", "buenas tardes", "sí"])
async def test_los_saludos_y_muletillas_sobre_la_apertura_siguen_de_largo(
    catalogo: None, saludo: str
) -> None:
    motor = await _motor()
    doble = VozDoble(guion=[_final(saludo)], antes_del_audio=True)
    canal = CanalFalso(entrantes=[SILENCIO], seguir=lambda: motor.disclosed_at is None)

    await asyncio.wait_for(_correr(motor, canal, doble).run(), timeout=5)

    assert canal.de_tipo(voz.StopAudio) == []
    assert len(doble.dicho) == 1


async def test_lo_dicho_con_la_apertura_ya_enviada_pero_sonando_tampoco_cuenta(
    catalogo: None,
) -> None:
    """El caso que se oye en una llamada de verdad: el servidor manda la apertura en un
    segundo y el navegador la dice durante veinte. Lo dicho mientras suena llega con todo
    enviado, por el camino de `_oir` y no por el de `_decir`.

    Ni el "¿alo?" ni la frase con contenido la cortan ni cuentan (2026-10-14). Antes la
    frase con contenido si la cortaba. Los dos eventos de descarte son los que distinguen
    "se oyo y se descarto" de "no llego nada".
    """
    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        motor = await _motor()
        doble = VozDoble(
            guion=[_final("¿Aló?"), _final("tuve un choque en la calle diez")], trozos=2000
        )
        doble.esperar_a = lambda: motor.disclosed_at is not None
        canal = CanalFalso(
            entrantes=[SILENCIO],
            seguir=lambda: (
                salida.getvalue().count("voice.heard_during_opening_discarded") < 2
                and not canal.de_tipo(voz.StopAudio)
            ),
        )

        await asyncio.wait_for(_correr(motor, canal, doble).run(), timeout=5)
    finally:
        observability.set_stream(sys.stdout)

    assert _lo_que_vio_la_persona(canal) == []
    assert canal.de_tipo(voz.StopAudio) == []
    aperturas = [d for d in doble.dicho if "transcrib" in d.lower()]
    assert len(aperturas) == 1, "la apertura no tenia por que repetirse"
    descartes = _eventos(salida, "voice.heard_during_opening_discarded")
    assert [e["words"] for e in descartes] == [1, 7]


async def test_el_permiso_de_un_saludo_dura_lo_que_dura_la_apertura(catalogo: None) -> None:
    """El permiso es solo mientras la apertura suena. Pasada su hora de fin, "hola" es
    lo primero que la persona dice, y se atiende como cualquier turno."""
    motor = await _motor()
    await _abierta(motor)  # registra la apertura con la hora AHORA, su fin estimado
    saludo = _final("hola")

    assert motor.opening_is_sounding(now=AHORA - timedelta(seconds=1))
    assert motor.greeting_over_opening(saludo, now=AHORA - timedelta(seconds=1))
    assert not motor.opening_is_sounding(now=AHORA)
    assert not motor.greeting_over_opening(saludo, now=AHORA)
    # Y con contenido no lo es ni mientras suena.
    assert not motor.greeting_over_opening(
        _final("hola, tuve un choque"), now=AHORA - timedelta(seconds=1)
    )


# --- El silencio no corre contra la persona mientras habla la agente (2026-10-11) ----


@dataclass
class _RelojManual:
    """Un reloj que solo avanza cuando la prueba lo dice."""

    actual: datetime

    def __call__(self) -> datetime:
        return self.actual

    def avanzar(self, **tiempo: float) -> None:
        self.actual += timedelta(**tiempo)


def _ciclo_con(motor: voz.CallEngine, reloj: Callable[[], datetime], doble: VozDoble) -> CallRunner:
    return CallRunner(
        engine=motor,
        channel=CanalFalso(),
        speech=doble,
        now=reloj,
        max_call=timedelta(seconds=600),
        warn_at=timedelta(seconds=30),
    )


def _esperar_respuesta(ciclo: CallRunner, hasta: datetime) -> None:
    """Arma la espera de la respuesta del fondo, como la deja un turno con la frase de
    espera. Es una funcion y no una asignacion en la prueba para que el comprobador de
    tipos no estreche el campo y trate lo que viene como inalcanzable."""
    ciclo._respuesta_hasta = hasta


async def test_tras_decir_que_sigue_revisando_se_sigue_esperando_sin_preguntar_si_sigue_ahi(
    catalogo: None,
) -> None:
    """V11. "Sigo revisando" cerraba la espera, el silencio arrancaba contra la persona
    y a los cinco segundos la agente preguntaba si seguia ahi; a los quince colgaba,
    con la respuesta todavia en camino."""
    motor = await _motor()
    await _abierta(motor)
    doble = VozDoble()
    reloj = _RelojManual(_reloj())
    ciclo = _ciclo_con(motor, reloj, doble)
    callo_a = reloj()
    _esperar_respuesta(ciclo, callo_a + ANSWER_WAIT)
    detector = motor.listening(since=callo_a)

    reloj.avanzar(seconds=ANSWER_WAIT.total_seconds())
    hubo, motivo = await ciclo._al_vencer(detector, callo_a, reloj())

    assert (hubo, motivo) == (True, None)
    assert "still checking" in doble.dicho[-1]
    # La escucha vuelve a abrirse desde que la agente termina de decirlo.
    desde = ciclo.silent_since()
    nuevo = motor.listening(since=desde)
    # Pasada de sobra la tolerancia de silencio, quien debe hablar sigue siendo ella.
    despues = desde + motor.silence_tolerance * 3
    assert ciclo._que_toca(nuevo, desde, despues) == "esperar"
    assert ciclo._proximo_limite(nuevo, desde) == desde + LATE_ANSWER_WAIT


async def test_si_la_espera_larga_tambien_vence_deja_de_esperar_y_el_silencio_vuelve_a_contar(
    catalogo: None,
) -> None:
    motor = await _motor()
    await _abierta(motor)
    doble = VozDoble()
    reloj = _RelojManual(_reloj())
    ciclo = _correr(motor, CanalFalso(), doble)
    ciclo.now = reloj
    callo_a = reloj()
    _esperar_respuesta(ciclo, callo_a + ANSWER_WAIT)
    detector = motor.listening(since=callo_a)
    reloj.avanzar(seconds=ANSWER_WAIT.total_seconds())
    await ciclo._al_vencer(detector, callo_a, reloj())
    desde = ciclo.silent_since()
    nuevo = motor.listening(since=desde)
    dicho_antes = list(doble.dicho)

    reloj.actual = desde + LATE_ANSWER_WAIT
    assert ciclo._que_toca(nuevo, desde, reloj()) == "sin_respuesta"
    hubo, motivo = await ciclo._al_vencer(nuevo, desde, reloj())

    # No repite "sigo revisando": ya lo dijo una vez.
    assert (hubo, motivo) == (True, None)
    assert doble.dicho == dicho_antes
    assert ciclo._respuesta_hasta is None
    # Y desde ahora el silencio cuenta, con su tolerancia de siempre.
    tras = ciclo.silent_since()
    otro = motor.listening(since=tras)
    assert ciclo._que_toca(otro, tras, tras + motor.silence_tolerance) == "silencio"


async def test_la_respuesta_que_llega_despues_de_sigo_revisando_se_dice(catalogo: None) -> None:
    motor = await _motor()
    await _abierta(motor)
    doble = VozDoble()
    reloj = _RelojManual(_reloj())
    ciclo = _correr(motor, CanalFalso(), doble)
    ciclo.now = reloj
    callo_a = reloj()
    _esperar_respuesta(ciclo, callo_a + ANSWER_WAIT)
    ciclo._escuchar_al_fondo()
    detector = motor.listening(since=callo_a)
    reloj.avanzar(seconds=ANSWER_WAIT.total_seconds())
    await ciclo._al_vencer(detector, callo_a, reloj())
    desde = ciclo.silent_since()
    nuevo = motor.listening(since=desde)
    reloj.avanzar(seconds=20)
    assert motor.call.case_id is not None

    await answers.CASE_NOTIFIER.notify(
        motor.call.tenant_id, motor.call.case_id, text="In your policy, Part D addresses this."
    )
    hubo, motivo = await ciclo._al_vencer(nuevo, desde, reloj())
    ciclo._dejar_de_escuchar_al_fondo()

    assert (hubo, motivo) == (True, None)
    assert doble.dicho[-1].startswith("In your policy, Part D addresses this.")
    assert ciclo._respuesta_hasta is None
    assert ciclo._demora_dicha is False


async def test_mientras_el_grafo_prepara_la_respuesta_no_se_pregunta_si_sigue_ahi(
    catalogo: None,
) -> None:
    """V11, la otra mitad: el turno ya esta cerrado y quien debe hablar es la agente.
    Un grafo que tarda veinte segundos no deja a la persona con el reloj de silencio en
    marcha: el silencio cuenta desde que la agente termina de contestar."""
    reloj = _RelojManual(_reloj())
    motor = await _motor()

    async def lento(turn: c14.InboundTurn) -> AsyncIterator[c14.TurnEvent]:
        reloj.avanzar(seconds=20)
        yield c14.FinalText(message_id="m1", text="Noted.", language=turn.language)

    motor.handle_turn = con_rastro(lento)
    doble = VozDoble(guion=[_final("I was rear-ended on the highway this morning")])
    doble.esperar_a = lambda: motor.disclosed_at is not None
    canal = CanalFalso(entrantes=[SILENCIO], seguir=lambda: "Noted." not in doble.dicho)
    ciclo = _ciclo_con(motor, reloj, doble)

    await asyncio.wait_for(ciclo.run(), timeout=5)

    assert "Noted." in doble.dicho
    pregunta = copy_api.t(silence.STILL_THERE, locale="en")
    assert pregunta not in doble.dicho, "preguntó si seguia ahi mientras preparaba la respuesta"
    assert motor._silencios == 0
    del canal


# --- "Un momento": la agente espera mas antes de preguntar si sigue ahi (2026-10-11) ---


async def test_un_momento_no_va_al_grafo_y_la_agente_dice_que_espera(catalogo: None) -> None:
    """V11. Antes "un momento" era un turno mas: el grafo no sabia que hacer con el y a
    los cinco segundos la agente preguntaba si seguia ahi."""
    recibidos: list[c14.InboundTurn] = []

    async def grafo(turn: c14.InboundTurn) -> AsyncIterator[c14.TurnEvent]:
        recibidos.append(turn)
        yield c14.FinalText(message_id="m1", text="Noted.", language=turn.language)

    motor = await _motor()
    motor.handle_turn = con_rastro(grafo)
    await _abierta(motor)
    doble = VozDoble()
    ciclo = _correr(motor, CanalFalso(), doble)

    for dicho in ("Hold on, one moment please.", "give me a second"):
        motivo = await ciclo._atender(
            voz.SpeechEnd(text=dicho, at=_reloj(), last_audible_word_at=None, last=_final(dicho))
        )
        assert motivo is None
        assert doble.dicho[-1] == "Sure, take your time."

    assert recibidos == [], "un pedido de espera llego al grafo"


async def test_tras_un_momento_el_primer_silencio_espera_treinta_segundos(
    catalogo: None,
) -> None:
    motor = await _motor()
    await _abierta(motor)
    ciclo = _correr(motor, CanalFalso(), VozDoble())
    dicho = "one moment"
    antes = motor.listening(since=_reloj())

    await ciclo._atender(
        voz.SpeechEnd(text=dicho, at=_reloj(), last_audible_word_at=None, last=_final(dicho))
    )
    desde = ciclo.silent_since()
    detector = motor.listening(since=desde)

    # Sin el pedido, la tolerancia de siempre; con el, la espera larga.
    assert motor.silence_deadline(since=desde) == desde + silence.HOLD_TOLERANCE
    assert antes is not detector
    assert ciclo._que_toca(detector, desde, desde + silence.DEFAULT_TOLERANCE * 2) == "esperar"
    assert ciclo._que_toca(detector, desde, desde + silence.HOLD_TOLERANCE) == "silencio"

    # La espera larga se gasta con el primer silencio: el segundo vuelve a los cinco.
    assert motor.on_silence() is not None
    despues = motor.silence_deadline(since=desde)
    assert despues == desde + motor.silence_tolerance


async def test_hablar_de_nuevo_cancela_la_espera_larga(catalogo: None) -> None:
    motor = await _motor()
    await _abierta(motor)
    ciclo = _correr(motor, CanalFalso(), VozDoble())
    for dicho in ("one moment", "I was rear-ended on the highway this morning"):
        await ciclo._atender(
            voz.SpeechEnd(text=dicho, at=_reloj(), last_audible_word_at=None, last=_final(dicho))
        )

    desde = _reloj()
    assert motor.silence_deadline(since=desde) == desde + motor.silence_tolerance


async def test_un_momento_no_es_el_no_a_la_oferta_de_retomar(catalogo: None) -> None:
    """La oferta "¿seguimos con ese caso?" espera un si o un no. "Un momento" no es
    ninguno: antes se leia como un no y abria un caso nuevo."""
    motor = await _motor()
    await _abierta(motor)
    doble = VozDoble()
    ciclo = _correr(motor, CanalFalso(), doble)
    ciclo._oferta_abierta = True
    caso = motor.call.case_id
    dicho = "hold on a second"

    await ciclo._atender(
        voz.SpeechEnd(text=dicho, at=_reloj(), last_audible_word_at=None, last=_final(dicho))
    )

    assert doble.dicho[-1] == "Sure, take your time."
    assert ciclo._oferta_abierta is True, "la oferta sigue esperando su respuesta"
    assert motor.call.case_id == caso, "se abrio un caso nuevo"


# --- La llamada cambia de idioma a mitad (2026-10-13) ---------------------------------


async def test_pedir_el_otro_idioma_cambia_la_llamada_y_se_contesta_en_el_idioma_nuevo(
    catalogo: None,
) -> None:
    """AC1.31.1. Entre el 2026-10-11 y el 2026-10-13 la agente decia que la llamada seguia en
    el suyo: la transcripcion era de un idioma por llamada y mover solo la voz dejaba a la
    persona hablando con quien no la oia. Ahora el pedido cambia la llamada: el acuse y la
    pregunta que seguia salen ya en el idioma nuevo, con su voz, y el pedido no llega al grafo."""
    recibidos: list[c14.InboundTurn] = []

    async def grafo(turn: c14.InboundTurn) -> AsyncIterator[c14.TurnEvent]:
        recibidos.append(turn)
        yield c14.FinalText(message_id="m1", text="Noted.", language=turn.language)

    motor = await _motor()
    motor.handle_turn = con_rastro(grafo)
    await _abierta(motor)
    doble = VozDoble()
    ciclo = _correr(motor, CanalFalso(), doble)
    dicho = "En español, por favor"

    motivo = await ciclo._atender(
        voz.SpeechEnd(text=dicho, at=_reloj(), last_audible_word_at=None, last=_final(dicho))
    )

    assert motivo is None
    assert recibidos == [], "el pedido llego al grafo"
    assert motor.language == "es"
    acuse = copy_api.t(copy_api.CopyKey("voice.languages.switched"), locale="es")
    assert acuse == "Claro, seguimos en español."
    # El acuse y, en el mismo aliento, la pregunta de a que llama, ya en español.
    primera = copy_api.t(copy_api.CopyKey("voice.opening.first_question"), locale="es")
    assert doble.dicho[-1] == f"{acuse} {primera}"
    # Y suena con la voz del idioma nuevo.
    assert doble.idiomas_dichos[-1] == "es"


async def test_lo_que_sigue_a_un_cambio_de_idioma_se_entrega_al_grafo_en_el_idioma_nuevo(
    catalogo: None,
) -> None:
    """El turno siguiente ya es en el otro idioma (AC1.31.1) y la conversacion sigue sin
    reiniciarse: el grafo recibe el siguiente turno con el idioma nuevo."""
    recibidos: list[c14.InboundTurn] = []

    async def grafo(turn: c14.InboundTurn) -> AsyncIterator[c14.TurnEvent]:
        recibidos.append(turn)
        yield c14.FinalText(message_id="m1", text="Noted.", language=turn.language)

    motor = await _motor()
    motor.handle_turn = con_rastro(grafo)
    await _abierta(motor)
    ciclo = _correr(motor, CanalFalso(), VozDoble())
    for dicho in ("En español, por favor", "Tuve un choque en la calle diez"):
        await ciclo._atender(
            voz.SpeechEnd(text=dicho, at=_reloj(), last_audible_word_at=None, last=_final(dicho))
        )

    assert [t.language for t in recibidos] == ["es"]
    assert recibidos[0].text == "Tuve un choque en la calle diez"


async def test_ida_y_vuelta_la_llamada_vuelve_al_idioma_en_que_empezo(catalogo: None) -> None:
    """AC1.31.2: "en español" y despues "in English, please" dejan la llamada donde empezo."""
    motor = await _motor()
    await _abierta(motor)
    doble = VozDoble()
    ciclo = _correr(motor, CanalFalso(), doble)

    for dicho in ("En español, por favor", "In English, please"):
        await ciclo._atender(
            voz.SpeechEnd(text=dicho, at=_reloj(), last_audible_word_at=None, last=_final(dicho))
        )

    assert motor.language == "en"
    assert doble.idiomas_dichos[-2:] == ["es", "en"]
    assert doble.dicho[-1].startswith("Sure, we'll continue in English.")


async def test_el_reconocedor_se_reabre_en_el_idioma_nuevo(catalogo: None) -> None:
    """Lo que faltaba el 2026-10-11: la voz cambiaba y el oido no. El reconocedor de un solo
    idioma por conexion se cierra y se abre otra vez con el idioma nuevo, sobre el mismo
    audio, y lo que la persona diga despues se transcribe en ese idioma."""
    motor = await _motor()
    doble = VozDoble(guion=[_final("En español, por favor")])
    doble.esperar_a = lambda: motor.disclosed_at is not None
    canal = CanalFalso(seguir=lambda: len(doble.escuchas) < 2)

    await asyncio.wait_for(_correr(motor, canal, doble).run(), timeout=10)

    assert doble.escuchas == ["en", "es"]
    assert motor.language == "es"


async def test_con_el_reconocedor_multiidioma_no_se_reabre(catalogo: None) -> None:
    """En modo `multi` el modelo detecta el idioma de cada palabra y la conexion sirve para
    los dos: reabrirla de mas costaria un corte de audio sin ganar nada."""
    motor = await _motor()
    stt = motor.config.voice.stt
    assert stt is not None, "la aseguradora de la prueba no trae reconocedor"
    multi = stt.model_copy(update={"mode": TranscriptionMode.MULTI})
    motor.config = motor.config.model_copy(
        update={"voice": motor.config.voice.model_copy(update={"stt": multi})}
    )
    doble = VozDoble(guion=[_final("En español, por favor")])
    doble.esperar_a = lambda: motor.disclosed_at is not None
    # La llamada sigue viva un buen rato despues del acuse: si el ciclo fuera a reabrir la
    # escucha, ese rato es lo que le da para hacerlo.
    restan = [50]

    def seguir() -> bool:
        if any("seguimos en español" in frase for frase in doble.dicho):
            restan[0] -= 1
        return restan[0] > 0

    canal = CanalFalso(seguir=seguir)

    await asyncio.wait_for(_correr(motor, canal, doble).run(), timeout=10)

    assert motor.language == "es"
    assert doble.escuchas == ["en"]


async def test_lo_dicho_antes_de_reabrir_la_escucha_no_se_pierde_ni_se_repite(
    catalogo: None,
) -> None:
    """El audio que el navegador manda mientras el reconocedor se reabre espera en la misma
    cola: la nueva conexion lo recibe, y lo que la primera ya habia entregado no vuelve."""
    motor = await _motor()
    doble = VozDoble(guion=[_final("En español, por favor")])
    doble.esperar_a = lambda: motor.disclosed_at is not None
    canal = CanalFalso(seguir=lambda: len(doble.escuchas) < 2)
    ciclo = _correr(motor, canal, doble)

    await asyncio.wait_for(ciclo.run(), timeout=10)

    # Una sola vez el pedido llego al motor: el guion no se repitio en la conexion nueva.
    assert sum("seguimos en español" in frase for frase in doble.dicho) == 1


# --- Lo que suena no es lo que se ve: los codigos se dicen como se dictan (2026-10-11) ---


async def test_la_sintesis_recibe_los_codigos_dichos_y_la_pantalla_los_escritos(
    catalogo: None,
) -> None:
    """V17. "POL-31", las placas y los numeros de caso llegaban crudos al sintetizador.
    El texto que suena se reescribe en un solo punto, justo antes de sintetizar; el de la
    pantalla, que es el que tambien se guarda, sigue con el formato escrito."""
    from untangle.compliance.redaction import api as redaccion

    motor = await _motor()
    doble = VozDoble()
    canal = CanalFalso()
    ciclo = _correr(motor, canal, doble)
    escrito = "Found policy POL-31, plate ABC123, model year 2015, case SA-602938."

    await ciclo._decir(voz.Utterance(text=redaccion.from_catalog(escrito, language="en")))

    assert doble.dicho == [
        "Found policy three one, plate A B C, one two three, "
        "model year 2015, case S A, six zero two, nine three eight."
    ]
    en_pantalla = [c.text for c in canal.de_tipo(voz.Transcript) if c.speaker == "agent"]
    assert en_pantalla == [escrito]


async def test_una_frase_sin_codigos_suena_igual_que_se_ve(catalogo: None) -> None:
    from untangle.compliance.redaction import api as redaccion

    motor = await _motor()
    doble = VozDoble()
    ciclo = _correr(motor, CanalFalso(), doble)
    escrito = "Is anyone hurt? Your 2015 model is noted."

    await ciclo._decir(voz.Utterance(text=redaccion.from_catalog(escrito, language="en")))

    assert doble.dicho == [escrito]


async def test_el_texto_del_turno_que_se_guarda_no_es_el_que_suena(catalogo: None) -> None:
    """`spoken` devuelve otro `Redacted` y no toca el `Utterance`: lo que el motor anota en
    la transcripcion y lo que el ciclo manda a la consola es `text`, intacto."""
    from untangle.compliance.redaction import api as redaccion

    motor = await _motor()
    frase = voz.Utterance(text=redaccion.from_catalog("Your policy is POL-31.", language="en"))

    suena = motor.spoken(frase)

    assert str(suena) == "Your policy is three one."
    assert str(frase.text) == "Your policy is POL-31."
    # Y sin nada que reescribir, el mismo objeto.
    llana = voz.Utterance(text=redaccion.from_catalog("Is anyone hurt?", language="en"))
    assert motor.spoken(llana) is llana.text


# --- Retomar una llamada cortada: una sola pregunta, y nunca en silencio (2026-10-11) ---


async def _motor_con_un_caso_por_retomar(
    *, grafo: voz.TurnHandler | None = None
) -> tuple[voz.CallEngine, str]:
    """Un motor cuya llamada es la retoma de un reporte que se corto en plena captura."""
    aseguradora = tenancy.available_ids()[0]
    anterior = await nuevo_caso(aseguradora)
    await casos.apply_transition(
        aseguradora,
        anterior.case_id,
        CaseState.CAPTURING,
        context=rules.TransitionContext(
            now=AHORA, actor=Actor(actor_type=ActorType.INSURED), channel=Channel.VOICE
        ),
    )
    cortada = await voz.open_call(
        tenant_id=aseguradora,
        visitor_key_digest="digest-de-prueba",
        language="en",
        voice_mode=VoiceMode.PRIMARY,
        now=AHORA,
    )
    cortada = await voz.attach_case(cortada, case_id=anterior.case_id)
    cortada = await voz.end_call(
        cortada, reason=voz.EndReason.DROPPED, now=AHORA, resume_window=timedelta(minutes=15)
    )
    motor = await _motor()
    if grafo is not None:
        motor.handle_turn = con_rastro(grafo)
    motor.call = await voz.switch_case(motor.call, case_id=anterior.case_id)
    await motor.look_for_resumable(cortada)
    return motor, anterior.case_id


def _pregunta_del_caso() -> str:
    """Lo que la captura preguntaria ahora a un reporte recien empezado."""
    return copy_api.t(composition.QUESTION_SAFETY, locale="en")


async def _retoma_y_contesta(
    motor: voz.CallEngine, dicho: str, *, dichas: int
) -> tuple[VozDoble, CanalFalso]:
    """Corre la llamada: apertura, oferta, lo que la persona contesta, y `dichas` frases.

    La respuesta sale cuando la oferta ya termino de enviarse, y no cuando empieza: una
    palabra suelta dicha encima de la agente es ruido que no interrumpe (BR4.2) y se
    descarta, y un "si" a mitad de la oferta se perderia sin que nadie lo notara. Con el
    reloj quieto de la suite la apertura nunca termina de sonar, asi que un "si" a secas se
    leeria como el saludo sobre ella; por eso estas pruebas contestan con una frase corta.
    """
    doble = VozDoble(guion=[_final(dicho)])
    canal = CanalFalso(seguir=lambda: len(doble.dicho) < dichas)
    doble.esperar_a = lambda: len(canal.audio) >= 2 * doble.trozos
    await asyncio.wait_for(_correr(motor, canal, doble).run(), timeout=10)
    return doble, canal


async def test_al_retomar_suena_una_sola_pregunta_y_es_la_oferta(catalogo: None) -> None:
    """Antes sonaban dos seguidas: "¿en que te puedo ayudar?" de la apertura y "¿seguimos
    con ese?". La divulgacion va entera, sin la primera pregunta."""
    motor, _ = await _motor_con_un_caso_por_retomar()

    doble, _ = await _retoma_y_contesta(motor, "yes, that one", dichas=3)

    apertura, oferta = doble.dicho[0], doble.dicho[1]
    assert "transcrib" in apertura.lower()
    assert "?" not in apertura
    assert oferta.count("?") == 1
    assert copy_api.t(resume.OFFER, locale="en") in oferta


async def test_un_si_retoma_con_la_pregunta_que_habia_quedado_pendiente_una_vez(
    catalogo: None,
) -> None:
    motor, caso = await _motor_con_un_caso_por_retomar()

    doble, canal = await _retoma_y_contesta(motor, "yes, that one", dichas=3)

    esperado = f"{copy_api.t(resume.ACCEPTED, locale='en')} {_pregunta_del_caso()}"
    assert doble.dicho[2] == esperado
    assert len(doble.dicho) == 3, "la agente siguio hablando sin que la persona dijera nada"
    assert sum(frase.count(_pregunta_del_caso()) for frase in doble.dicho) == 1
    assert motor.call.case_id == caso, "seguir con el caso no abre otro"
    assert not canal.de_tipo(voz.Case), "seguir con el caso no anuncia uno nuevo"


@pytest.mark.parametrize("dicho", ["no", "no, it's something else", "I want to start over"])
async def test_un_no_abre_un_caso_nuevo_y_pregunta_en_que_puede_ayudar(
    catalogo: None, dicho: str
) -> None:
    """Antes se abria el caso nuevo y la llamada se quedaba callada hasta el "¿sigues
    ahi?". El caso anterior queda intacto."""
    motor, anterior = await _motor_con_un_caso_por_retomar()
    aseguradora = motor.call.tenant_id

    doble, canal = await _retoma_y_contesta(motor, dicho, dichas=3)

    esperado = (
        f"{copy_api.t(resume.NEW_CASE, locale='en')} "
        f"{copy_api.t(opening.FIRST_QUESTION, locale='en')}"
    )
    assert doble.dicho[2] == esperado
    nuevo = canal.de_tipo(voz.Case)
    assert nuevo and nuevo[0].case_id != anterior
    assert motor.call.case_id == nuevo[0].case_id
    intacto = await casos.get_case(aseguradora, anterior)
    assert intacto is not None
    assert intacto.state is CaseState.CAPTURING


async def test_contar_algo_del_accidente_es_seguir_con_el_caso_y_se_atiende_como_turno(
    catalogo: None,
) -> None:
    """Sin "si" ni "no": el turno llega al grafo con el caso retomado, sin acuse previo."""
    recibidos: list[c14.InboundTurn] = []

    async def grafo(turn: c14.InboundTurn) -> AsyncIterator[c14.TurnEvent]:
        recibidos.append(turn)
        yield c14.FinalText(message_id="m1", text="Thanks, noted.", language=turn.language)

    motor, caso = await _motor_con_un_caso_por_retomar(grafo=grafo)

    doble, canal = await _retoma_y_contesta(
        motor, "it happened yesterday on Tenth Street", dichas=3
    )

    assert [t.case_id for t in recibidos] == [caso]
    assert doble.dicho[2] == "Thanks, noted."
    assert not canal.de_tipo(voz.Case)


async def test_lo_que_no_se_oyo_no_es_un_no_y_la_oferta_sigue_abierta(catalogo: None) -> None:
    """Un "si" con confianza baja abria un caso nuevo; ahora lo atiende la escalera de
    reintentos y la persona puede contestar de nuevo."""
    motor, caso = await _motor_con_un_caso_por_retomar()
    await _abierta(motor)
    doble = VozDoble()
    ciclo = _correr(motor, CanalFalso(), doble)
    ciclo._oferta_abierta = True

    await ciclo._atender(
        voz.SpeechEnd(
            text="yes", at=_reloj(), last_audible_word_at=None, last=_final("yes", confianza=0.1)
        )
    )

    assert doble.dicho[-1] == copy_api.t(retry.NOT_UNDERSTOOD, locale="en")
    assert ciclo._oferta_abierta is True
    assert motor.call.case_id == caso


async def test_si_el_caso_no_tiene_pregunta_pendiente_se_pregunta_que_quiere_agregar(
    catalogo: None,
) -> None:
    """Un caso que ya no esta capturando no tiene una pregunta que retomar: en lugar de
    callar, la agente pregunta."""
    motor, _ = await _motor_con_un_caso_por_retomar()
    # El reporte ya no esta capturando: lo que se retoma no tiene pregunta propia.
    motor._retomable = replace(motor._retomable, pending_question=None)  # type: ignore[type-var]

    doble, _ = await _retoma_y_contesta(motor, "yes, that one", dichas=3)

    esperado = (
        f"{copy_api.t(resume.ACCEPTED, locale='en')} "
        f"{copy_api.t(resume.CONTINUE_OPEN, locale='en')}"
    )
    assert doble.dicho[2] == esperado


@pytest.mark.parametrize("dicho", ["yes", "sí", "okay"])
async def test_un_si_a_secas_retoma_con_la_pregunta_pendiente(catalogo: None, dicho: str) -> None:
    """El mismo camino, atendiendo el turno ya cerrado: con el reloj de la suite quieto no
    cabe una llamada entera en que un "si" suelto no sea el saludo sobre la apertura."""
    motor, caso = await _motor_con_un_caso_por_retomar()
    await _abierta(motor)
    doble = VozDoble()
    ciclo = _correr(motor, CanalFalso(), doble)
    ciclo._oferta_abierta = True

    motivo = await ciclo._atender(
        voz.SpeechEnd(text=dicho, at=_reloj(), last_audible_word_at=None, last=_final(dicho))
    )

    assert motivo is None
    assert doble.dicho == [
        f"{copy_api.t(resume.ACCEPTED, locale='en')} {_pregunta_del_caso()}",
    ]
    assert ciclo._oferta_abierta is False
    assert motor.call.case_id == caso


# --- La ultima palabra audible se ancla al flujo de la llamada (2026-10-12) -----------


@dataclass
class _CanalQueAvanzaElReloj(CanalFalso):
    """Un navegador que manda un trozo por segundo: el reloj avanza entre trozo y trozo."""

    reloj: _RelojManual | None = None

    async def _entrar(self) -> AsyncIterator[bytes | voz.Hangup]:
        assert self.reloj is not None
        for pieza in self.entrantes:
            yield pieza
            self.reloj.avanzar(seconds=1)


async def test_la_ultima_palabra_se_ancla_al_primer_trozo_de_la_llamada_y_no_al_turno(
    catalogo: None,
) -> None:
    """Hay un solo flujo de audio por llamada y el reconocedor numera sus palabras desde el
    primer trozo. El detector las pasaba a hora de pared desde el inicio del TURNO, y en
    cualquier turno que no fuera el primero la marca caia despues del final que la trajo:
    el reporte del hito (AC1.23.5) publicaria un dato falso."""
    motor = await _motor()
    reloj = _RelojManual(AHORA + timedelta(seconds=1))
    canal = _CanalQueAvanzaElReloj(entrantes=[SILENCIO, SILENCIO, SILENCIO], reloj=reloj)
    ciclo = CallRunner(
        engine=motor,
        channel=canal,
        speech=VozDoble(),
        now=reloj,
        max_call=timedelta(seconds=180),
        warn_at=timedelta(seconds=30),
    )
    abre_la_llamada = reloj()
    await ciclo._recibir()
    # El primer trozo, no el ultimo: el reloj siguio avanzando con los otros dos.
    assert ciclo._flujo_empezo_a == abre_la_llamada
    assert reloj() == abre_la_llamada + timedelta(seconds=3)

    # Un minuto despues empieza a escucharse otro turno; dice algo que termina en el
    # segundo 62 de la llamada y su final llega 0,8 s mas tarde.
    reloj.actual = abre_la_llamada + timedelta(seconds=60)
    detector = ciclo._escuchando(reloj())
    llegada = abre_la_llamada + timedelta(seconds=62.8)
    detector.observe(final_con_tiempos("highway exit twelve", desde=61.0), at=llegada)
    cerrado = detector.close()

    assert cerrado.last_audible_word_at is not None
    assert cerrado.last_audible_word_at < cerrado.at
    assert cerrado.last_audible_word_at == abre_la_llamada + timedelta(seconds=62.0)
    assert cerrado.at - cerrado.last_audible_word_at < MAX_WORD_TO_FINAL


# --- Una muletilla cuando la respuesta tarda (2026-10-12) ------------------------------

#: Cuanto se espera la primera frase en estas pruebas. Real, no del reloj de la suite: es
#: el plazo de un `asyncio.wait`. Lo bastante corto para no alargar la suite.
ESPERA_CORTA = timedelta(milliseconds=20)
#: Una respuesta que tarda varias veces `ESPERA_CORTA`.
RESPUESTA_LENTA = timedelta(milliseconds=120)


def _muletillas(idioma: Locale = "en") -> list[str]:
    """Las tres, en el orden en que rotan."""
    claves = ("voice.filler.one", "voice.filler.two", "voice.filler.three")
    return [copy_api.t(copy_api.CopyKey(clave), locale=idioma) for clave in claves]


def _turno_cerrado(
    texto: str = "does my policy cover a rental car?", *, con_palabra: bool = True
) -> voz.SpeechEnd:
    """Un turno ya cerrado: el final llego 400 ms antes de cerrarse y la ultima palabra, 1 s."""
    return voz.SpeechEnd(
        text=texto,
        at=_reloj() - timedelta(milliseconds=400),
        last_audible_word_at=_reloj() - timedelta(seconds=1) if con_palabra else None,
        last=_final(texto),
    )


@dataclass
class _VozQueEsperaAlMotor(VozDoble):
    """Una voz cuya primera frase no empieza a sonar hasta que el motor arranco.

    Si el motor esperara a que la muletilla terminara para empezar su trabajo, la
    muletilla esperaria al motor y el motor a la muletilla: la prueba cae por tiempo.
    """

    arranco: asyncio.Event = field(default_factory=asyncio.Event)
    empezo: asyncio.Event = field(default_factory=asyncio.Event)

    async def _decir(self, text: Redacted) -> AsyncIterator[bytes]:
        await asyncio.wait_for(self.arranco.wait(), timeout=2)
        self.empezo.set()
        async for trozo in super()._decir(text):
            yield trozo


async def _ciclo_de_muletilla(
    grafo: voz.TurnHandler,
    *,
    filler_after: timedelta | None = ESPERA_CORTA,
    doble: VozDoble | None = None,
) -> tuple[voz.CallEngine, CallRunner, VozDoble, CanalFalso]:
    motor = await _motor()
    motor.handle_turn = con_rastro(grafo)
    await _abierta(motor)
    doble = doble if doble is not None else VozDoble()
    canal = CanalFalso()
    ciclo = CallRunner(
        engine=motor,
        channel=canal,
        speech=doble,
        now=_reloj,
        max_call=timedelta(seconds=180),
        warn_at=timedelta(seconds=30),
        filler_after=filler_after,
    )
    return motor, ciclo, doble, canal


def _grafo_que_espera(
    hasta: Callable[[], bool],
    *,
    arranco: asyncio.Event | None = None,
    al_responder: Callable[[], None] | None = None,
    texto: str = "Noted.",
) -> voz.TurnHandler:
    """Un grafo que no contesta hasta que `hasta()` sea cierto, sin dormir: cede el turno."""

    async def grafo(turn: c14.InboundTurn) -> AsyncIterator[c14.TurnEvent]:
        if arranco is not None:
            arranco.set()
        while not hasta():  # noqa: ASYNC110 -- la condicion es algo que ya paso (la muletilla sono), no un evento que el ciclo pueda avisar
            await asyncio.sleep(0)
        if al_responder is not None:
            al_responder()
        yield c14.FinalText(message_id="m1", text=texto, language=turn.language)

    return grafo


def _grafo_lento(retraso: timedelta = RESPUESTA_LENTA) -> voz.TurnHandler:
    """Un grafo que de verdad tarda mas que `ESPERA_CORTA`: con una espera que no deja pasar
    el tiempo, una prueba de "no hay muletilla" pasaria igual con la muletilla rota."""

    async def grafo(turn: c14.InboundTurn) -> AsyncIterator[c14.TurnEvent]:
        await asyncio.sleep(retraso.total_seconds())
        yield c14.FinalText(message_id="m1", text="Noted.", language=turn.language)

    return grafo


def _eventos(salida: io.StringIO, nombre: str) -> list[dict[str, object]]:
    lineas = (json.loads(linea) for linea in salida.getvalue().splitlines() if linea.strip())
    return [e for e in lineas if e.get("event") == nombre]


async def _ceder(veces: int = 200) -> None:
    """Deja correr el ciclo de eventos sin que pase tiempo."""
    for _ in range(veces):
        await asyncio.sleep(0)


async def test_respuesta_lenta_muletilla_y_despues_la_respuesta_en_ese_orden(
    catalogo: None,
) -> None:
    contenedor: list[VozDoble] = []
    grafo = _grafo_que_espera(lambda: bool(contenedor[0].dicho))
    _, ciclo, doble, _ = await _ciclo_de_muletilla(grafo)
    contenedor.append(doble)

    motivo = await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)

    assert motivo is None
    assert doble.dicho == [_muletillas()[0], "Noted."]


async def test_respuesta_rapida_no_lleva_muletilla(catalogo: None) -> None:
    grafo = _grafo_que_espera(lambda: True)
    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        _, ciclo, doble, _ = await _ciclo_de_muletilla(grafo, filler_after=timedelta(seconds=5))

        await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)
    finally:
        observability.set_stream(sys.stdout)

    assert doble.dicho == ["Noted."]
    assert _eventos(salida, "voice.filler_said") == []
    assert [e["after_filler"] for e in _eventos(salida, "voice.first_audio")] == [False]


async def test_sin_filler_after_nunca_hay_muletilla_aunque_la_respuesta_tarde(
    catalogo: None,
) -> None:
    _, ciclo, doble, _ = await _ciclo_de_muletilla(_grafo_lento(), filler_after=None)

    await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)

    assert doble.dicho == ["Noted."]


async def test_las_muletillas_rotan_y_nunca_se_repite_la_misma_dos_veces_seguidas(
    catalogo: None,
) -> None:
    contenedor: list[VozDoble] = []
    # Cada turno espera a que ya se haya dicho una frase mas de las que llevaba.
    dichas_antes = [0]
    grafo = _grafo_que_espera(lambda: len(contenedor[0].dicho) > dichas_antes[0])
    _, ciclo, doble, _ = await _ciclo_de_muletilla(grafo)
    contenedor.append(doble)

    muletillas: list[str] = []
    for _ in range(4):
        dichas_antes[0] = len(doble.dicho)
        await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)
        muletillas.append(doble.dicho[-2])

    todas = _muletillas()
    assert muletillas == [todas[0], todas[1], todas[2], todas[0]]
    assert all(a != b for a, b in pairwise(muletillas))


async def test_la_muletilla_sale_en_el_idioma_de_la_llamada(catalogo: None) -> None:
    contenedor: list[VozDoble] = []
    grafo = _grafo_que_espera(lambda: bool(contenedor[0].dicho))
    motor, ciclo, doble, _ = await _ciclo_de_muletilla(grafo)
    contenedor.append(doble)
    motor.call = replace(motor.call, language="es")

    await asyncio.wait_for(ciclo._atender(_turno_cerrado("mi poliza cubre un carro?")), timeout=5)

    assert doble.dicho[0] == _muletillas("es")[0] == "Listo…"


async def test_el_motor_no_espera_a_que_termine_la_muletilla_para_empezar(
    catalogo: None,
) -> None:
    """La muletilla y la espera a la primera frase corren a la vez. La voz de esta prueba no
    deja sonar la muletilla hasta que el motor arranco, y el motor no contesta hasta que la
    muletilla empezo: si uno esperara al otro para empezar, la prueba cae por tiempo."""
    doble = _VozQueEsperaAlMotor()
    grafo = _grafo_que_espera(doble.empezo.is_set, arranco=doble.arranco)
    _, ciclo, _, _ = await _ciclo_de_muletilla(grafo, doble=doble)

    await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)

    assert doble.dicho == [_muletillas()[0], "Noted."]


async def test_el_primer_audio_se_mide_en_la_respuesta_y_no_en_la_muletilla(
    catalogo: None,
) -> None:
    """Si la muletilla contara como primer audio, la meta de latencia mejoraria sin que la
    respuesta llegara antes: la marca es la del primer trozo de la respuesta de verdad."""
    contenedor: list[VozDoble] = []
    grafo = _grafo_que_espera(lambda: bool(contenedor[0].dicho))
    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        _, ciclo, doble, canal = await _ciclo_de_muletilla(grafo)
        contenedor.append(doble)
        await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)
    finally:
        observability.set_stream(sys.stdout)

    primeros = _eventos(salida, "voice.first_audio")
    assert len(primeros) == 1, "la muletilla emitio su propio primer audio"
    assert primeros[0]["after_filler"] is True
    assert len(_eventos(salida, "voice.filler_said")) == 1
    # En la consola: una sola cifra, y llega despues del texto de la respuesta, no de la
    # muletilla.
    latencias = [i for i, c in enumerate(canal.cuadros) if isinstance(c, voz.Latency)]
    textos = [
        i
        for i, c in enumerate(canal.cuadros)
        if isinstance(c, voz.Transcript) and c.speaker == "agent"
    ]
    assert len(latencias) == 1
    assert len(textos) == 2
    assert latencias[0] > textos[1] > textos[0]


async def test_el_evento_de_la_muletilla_lleva_el_turno_y_los_milisegundos_sin_texto(
    catalogo: None,
) -> None:
    contenedor: list[VozDoble] = []
    grafo = _grafo_que_espera(lambda: bool(contenedor[0].dicho))
    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        motor, ciclo, doble, _ = await _ciclo_de_muletilla(grafo)
        contenedor.append(doble)
        await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)
    finally:
        observability.set_stream(sys.stdout)

    (evento,) = _eventos(salida, "voice.filler_said")
    assert evento["turn_id"] == f"{motor.call.call_id}-t1"
    assert evento["elapsed_ms"] == 400
    assert not any(texto in salida.getvalue() for texto in _muletillas())


async def test_la_muletilla_no_entra_a_la_transcripcion_del_caso(catalogo: None) -> None:
    contenedor: list[VozDoble] = []
    grafo = _grafo_que_espera(lambda: bool(contenedor[0].dicho))
    motor, ciclo, doble, _ = await _ciclo_de_muletilla(grafo)
    contenedor.append(doble)

    await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)
    pendientes = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if pendientes:
        await asyncio.wait(pendientes, timeout=5)

    assert doble.dicho[0] == _muletillas()[0], "la muletilla si sono"
    assert motor.call.case_id is not None
    turnos = await casos.transcript_of(motor.call.tenant_id, motor.call.case_id)
    escritos = [t.text_redacted for t in turnos]
    assert escritos, "la respuesta de verdad si queda escrita"
    assert not any(texto in escrito for texto in _muletillas() for escrito in escritos)
    assert ciclo._turnos == 1, "la muletilla no cuenta como un turno"


async def test_con_la_llamada_cerrando_no_hay_muletilla(catalogo: None) -> None:
    motor, ciclo, doble, _ = await _ciclo_de_muletilla(_grafo_lento())
    motor.closed = True

    await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)

    assert doble.dicho == ["Noted."]


async def test_pasada_la_hora_de_despedirse_no_hay_muletilla(catalogo: None) -> None:
    _, ciclo, doble, _ = await _ciclo_de_muletilla(_grafo_lento())
    # El aviso de tiempo ya se dio: lo que se prueba es la despedida, no el aviso.
    ciclo._aviso_dado = True
    ciclo.now = lambda: ciclo._hora_de_despedirse + timedelta(seconds=1)

    await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)

    assert doble.dicho == ["Noted."]


async def test_tras_el_aviso_de_tiempo_hablado_no_hay_muletilla(catalogo: None) -> None:
    """El aviso de que queda poco ya sono delante de la respuesta: otra frase corta antes
    de la respuesta no es un acuse, es ruido."""
    motor, ciclo, doble, _ = await _ciclo_de_muletilla(_grafo_lento())
    ciclo._aviso_por_decir = True

    await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)

    assert doble.dicho == [str(motor.time_warning().text), "Noted."]


async def test_si_la_persona_ya_colgo_no_hay_muletilla(catalogo: None) -> None:
    _, ciclo, doble, _ = await _ciclo_de_muletilla(_grafo_lento())
    ciclo._colgo = True

    await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)

    assert doble.dicho == ["Noted."]


async def test_lo_que_la_persona_dice_durante_la_muletilla_lo_recoge_el_detector(
    catalogo: None,
) -> None:
    """No es interrumpible: no consume lo que llega ni lo toma por una interrupcion."""
    visto: dict[str, int] = {}
    contenedor: list[tuple[CallRunner, CanalFalso]] = []

    def al_responder() -> None:
        ciclo, canal = contenedor[0]
        visto["en_cola"] = ciclo._oido.qsize()
        visto["paradas"] = len(canal.de_tipo(voz.StopAudio))

    doble_contenedor: list[VozDoble] = []
    grafo = _grafo_que_espera(lambda: bool(doble_contenedor[0].dicho), al_responder=al_responder)
    _, ciclo, doble, canal = await _ciclo_de_muletilla(grafo)
    doble_contenedor.append(doble)
    contenedor.append((ciclo, canal))
    ciclo._oido.put_nowait(_final("wait I have one more thing to say"))

    await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)

    assert doble.dicho[0] == _muletillas()[0]
    # Al terminar la muletilla, lo que dijo sigue en la cola y nadie paro el audio.
    assert visto == {"en_cola": 1, "paradas": 0}


async def test_una_respuesta_con_mas_de_una_frase_mide_solo_la_primera(catalogo: None) -> None:
    """El primer audio es el del turno (BR8.1): la segunda frase no es la espera de la
    persona, y contarla meteria en la meta lo que dura hablar la primera."""

    async def grafo(turn: c14.InboundTurn) -> AsyncIterator[c14.TurnEvent]:
        yield c14.FinalText(message_id="m1", text="First.", language=turn.language)
        yield c14.FinalText(message_id="m2", text="Second.", language=turn.language)

    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        _, ciclo, doble, canal = await _ciclo_de_muletilla(grafo, filler_after=None)
        await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)
    finally:
        observability.set_stream(sys.stdout)

    assert doble.dicho == ["First.", "Second."]
    assert len(_eventos(salida, "voice.first_audio")) == 1
    assert len(canal.de_tipo(voz.Latency)) == 1


async def test_la_consola_recibe_las_dos_medidas_las_mismas_de_la_traza(catalogo: None) -> None:
    """`elapsed_ms` desde el ultimo final, como siempre; la otra, desde la ultima palabra."""
    grafo = _grafo_que_espera(lambda: True)
    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        _, ciclo, _, canal = await _ciclo_de_muletilla(grafo, filler_after=None)
        await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)
    finally:
        observability.set_stream(sys.stdout)

    (evento,) = _eventos(salida, "voice.first_audio")
    (cuadro,) = canal.de_tipo(voz.Latency)
    assert evento["elapsed_ms"] == 400
    assert evento["elapsed_from_last_word_ms"] == 1000
    assert cuadro.elapsed_ms == evento["elapsed_ms"]
    assert cuadro.from_last_word_ms == evento["elapsed_from_last_word_ms"]


async def test_sin_ultima_palabra_la_consola_recibe_la_cifra_de_siempre(catalogo: None) -> None:
    grafo = _grafo_que_espera(lambda: True)
    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        _, ciclo, _, canal = await _ciclo_de_muletilla(grafo, filler_after=None)
        await asyncio.wait_for(ciclo._atender(_turno_cerrado(con_palabra=False)), timeout=5)
    finally:
        observability.set_stream(sys.stdout)

    (evento,) = _eventos(salida, "voice.first_audio")
    (cuadro,) = canal.de_tipo(voz.Latency)
    assert evento["elapsed_from_last_word_ms"] is None
    assert cuadro.from_last_word_ms is None
    assert cuadro.elapsed_ms == 400


# --- El rastro del turno se abre y se cierra en la tarea de la llamada (2026-10-12) -----
#
# El rastro real pone variables de contexto antes de su primer evento y las repone en un
# `finally`: una variable de contexto solo se repone en la tarea donde se puso. La primera
# muletilla pedia la primera frase desde otra tarea y cerraba el turno desde la de la
# llamada: `ValueError ... was created in a different Context`, y toda llamada con
# muletilla moria al primer turno largo. Las pruebas no lo vieron porque el grafo doble no
# abria nada; desde ahora todo grafo doble del ciclo pasa por `con_rastro`, y estas tres
# lo miran con una variable propia.

_RASTRO = ContextVar[str | None]("rastro_del_doble", default=None)


def _grafo_con_variable_de_contexto(
    textos: Sequence[str], *, retraso: timedelta = RESPUESTA_LENTA
) -> voz.TurnHandler:
    """Un grafo que pone una variable de contexto antes de su primer evento y la repone
    en un `finally`, con respuesta lenta para que suene la muletilla."""

    async def grafo(turn: c14.InboundTurn) -> AsyncIterator[c14.TurnEvent]:
        token = _RASTRO.set(turn.session_ref)
        try:
            await asyncio.sleep(retraso.total_seconds())
            for i, texto in enumerate(textos):
                yield c14.FinalText(message_id=f"m{i}", text=texto, language=turn.language)
        finally:
            _RASTRO.reset(token)

    return grafo


async def test_un_turno_con_muletilla_que_termina_normal_cierra_su_rastro_en_su_tarea(
    catalogo: None,
) -> None:
    _, ciclo, doble, _ = await _ciclo_de_muletilla(_grafo_con_variable_de_contexto(["Noted."]))

    motivo = await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)

    assert motivo is None
    assert doble.dicho == [_muletillas()[0], "Noted."]
    assert _RASTRO.get() is None


async def test_un_turno_con_muletilla_interrumpido_a_mitad_de_la_respuesta_cierra_su_rastro(
    catalogo: None,
) -> None:
    """La persona corta la respuesta; lo que quedaba del turno no se dice, pero el grafo
    se sigue consumiendo hasta cerrarlo en la tarea de la llamada."""
    grafo = _grafo_con_variable_de_contexto(["One.", "Two."])
    _, ciclo, doble, canal = await _ciclo_de_muletilla(grafo)
    # La muletilla no se interrumpe: lo que llega durante ella corta la respuesta que sigue.
    ciclo._oido.put_nowait(_final("wait I need to correct something"))

    motivo = await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)

    assert motivo is None
    assert doble.dicho == [_muletillas()[0], "One."]
    assert len(canal.de_tipo(voz.StopAudio)) == 1
    assert _RASTRO.get() is None


async def test_un_turno_que_termina_con_frases_sin_decir_cierra_su_rastro_al_salir(
    catalogo: None,
) -> None:
    """La despedida es la ultima que se dice y el generador queda a medias: se cierra aqui,
    en la tarea de la llamada, y no cuando el recolector de basura se acuerde."""

    async def hablar(speech: voz.SpeechEnd, *, turn_id: str) -> AsyncGenerator[voz.Utterance]:
        del speech, turn_id
        token = _RASTRO.set("turno")
        try:
            await asyncio.sleep(RESPUESTA_LENTA.total_seconds())
            yield _dicho("Noted.")
            yield _dicho("Goodbye.", voz.EndReason.SAVED)
            yield _dicho("Nunca se dice.")
        finally:
            _RASTRO.reset(token)

    _, ciclo, doble, _ = await _ciclo_de_muletilla(_sin_grafo)
    ciclo.engine.speak_turn = hablar  # type: ignore[method-assign]

    motivo = await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)

    assert motivo is voz.EndReason.SAVED
    assert doble.dicho == [_muletillas()[0], "Noted.", "Goodbye."]
    assert _RASTRO.get() is None


@dataclass
class _VozLenta(VozDoble):
    """Una voz cuyas frases tardan en sonar y dejan ver de quien es cada trozo.

    Cada trozo lleva por contenido el numero de la frase a la que pertenece; si dos frases
    suenan a la vez, sus trozos salen mezclados.
    """

    async def _decir(self, text: Redacted) -> AsyncIterator[bytes]:
        self.dicho.append(str(text))
        frase = len(self.dicho)
        for _ in range(self.trozos):
            await asyncio.sleep(0.01)
            yield bytes([frase]) * 480


async def test_si_la_muletilla_ya_esta_sonando_la_respuesta_espera_a_que_termine(
    catalogo: None,
) -> None:
    """La respuesta llega mientras la muletilla suena: no se mezclan, y la muletilla no se
    corta. El grafo contesta en cuanto la muletilla empieza."""
    contenedor: list[VozDoble] = []
    grafo = _grafo_que_espera(lambda: bool(contenedor[0].dicho))
    _, ciclo, doble, canal = await _ciclo_de_muletilla(grafo, doble=_VozLenta(trozos=4))
    contenedor.append(doble)

    await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)

    assert doble.dicho == [_muletillas()[0], "Noted."]
    assert [trozo[0] for trozo in canal.audio] == [1, 1, 1, 1, 2, 2, 2, 2]


async def test_si_la_respuesta_llega_antes_de_que_empiece_la_muletilla_esta_nunca_suena(
    catalogo: None,
) -> None:
    """La muletilla que esperaba su turno se cancela: ni suena despues de la respuesta ni
    deja su evento."""
    grafo = _grafo_que_espera(lambda: True)
    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        _, ciclo, doble, _ = await _ciclo_de_muletilla(grafo, filler_after=timedelta(seconds=5))
        await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)
        await _ceder()
    finally:
        observability.set_stream(sys.stdout)

    assert doble.dicho == ["Noted."]
    assert _eventos(salida, "voice.filler_said") == []
    assert [t for t in asyncio.all_tasks() if t is not asyncio.current_task()] == []


# --- Una llamada que falla dice donde, no con que (2026-10-12) ---------------------------


async def test_una_llamada_que_falla_deja_el_archivo_y_la_linea_y_no_el_mensaje(
    catalogo: None,
) -> None:
    """Hasta hoy el registro solo traia el tipo de error y hubo que reproducir la llamada
    para saber de donde venia. El fallo se provoca dentro del aplicativo: un turno sin caso
    abierto levanta desde `voice/call.py`."""
    motor = await _motor()
    await _abierta(motor)
    motor.call = replace(motor.call, case_id=None)
    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        canal = CanalFalso(seguir=lambda: not _eventos(salida, "voice.call_failed"))
        doble = VozDoble(
            guion=[_final("I was hit from behind on the highway")], antes_del_audio=True
        )

        ciclo = _correr(motor, canal, doble)
        # Quien quiera el error entero --la llamada simulada-- lo pide aqui; el registro no.
        fallos: list[Exception] = []
        ciclo.on_failure = fallos.append

        motivo = await asyncio.wait_for(ciclo.run(), timeout=5)
    finally:
        observability.set_stream(sys.stdout)

    assert motivo is voz.EndReason.ERROR
    (evento,) = _eventos(salida, "voice.call_failed")
    assert evento["error_type"] == "ValueError"
    assert str(evento["where"]).startswith("voice/call.py:")
    assert "caso abierto" not in salida.getvalue(), "el mensaje del error no sale al registro"
    assert [type(f) for f in fallos] == [ValueError]
    assert "caso abierto" in str(fallos[0])


# --- La senal de voz del reconocedor (2026-10-12) ----------------------------------------
#
# Llega en decimas de segundo, mucho antes que un parcial. Sirve para dos cosas con la agente
# callada --aplazar el cierre del turno y ahorrar la muletilla-- y para ninguna mientras
# habla: el microfono recoge su propia voz por el altavoz.


async def test_el_ciclo_lleva_la_senal_de_voz_al_detector_del_turno_abierto(
    catalogo: None,
) -> None:
    """«No.» deja el turno abierto con la espera corta; la senal lo aplaza `signal_grace`. Sin el
    enlace entre el ciclo y el detector, el plazo se queda en la corta."""
    motor = await _motor()
    motor.end_of_speech = timedelta(seconds=10)
    motor.unpunctuated_end_of_speech = timedelta(seconds=20)
    motor.incomplete_end_of_speech = timedelta(seconds=30)
    # La espera de la senal, mas larga que la de la frase cerrada, para ver que la mueve.
    motor.signal_grace = timedelta(seconds=30)
    motor.signal_only_extension = timedelta(seconds=30)
    await _abierta(motor)
    doble = VozDoble(guion=[_final("No."), senal(0.3)], antes_del_audio=True)
    # El guion sale ya y la llamada sigue viva hasta que el ciclo oyo la senal: que el guion
    # llegue antes de que el navegador cierre dependia de cuantas vueltas daba el ciclo.
    canal = CanalFalso(entrantes=[SILENCIO], seguir=lambda: ciclo._voces_oidas == 0)
    ciclo = _correr(motor, canal, doble)

    motivo = await asyncio.wait_for(ciclo.run(), timeout=5)

    assert motivo is voz.EndReason.DROPPED
    detector = motor._detector
    assert detector is not None
    assert detector.speaking, "el turno de «No.» sigue abierto: nada lo cerro"
    assert detector.deadline == _reloj() + timedelta(seconds=30)


async def test_la_senal_sin_turno_abierto_no_cierra_ni_abre_nada_en_el_ciclo(
    catalogo: None,
) -> None:
    motor = await _motor()
    await _abierta(motor)
    doble = VozDoble(guion=[senal(0.3)], antes_del_audio=True)
    # Viva hasta que la senal llego al ciclo: si no, esta prueba pasaria sin haberla visto.
    canal = CanalFalso(entrantes=[SILENCIO], seguir=lambda: ciclo._voces_oidas == 0)
    ciclo = _correr(motor, canal, doble)

    motivo = await asyncio.wait_for(ciclo.run(), timeout=5)

    assert motivo is voz.EndReason.DROPPED
    assert ciclo._voces_oidas == 1
    detector = motor._detector
    assert detector is not None
    assert not detector.speaking
    assert detector.deadline is None


async def test_una_senal_mientras_la_agente_habla_no_la_interrumpe(catalogo: None) -> None:
    """La apertura suena y el reconocedor avisa de voz: es el eco del altavoz o un ruido, y
    una senal no dice de quien es. La apertura llega entera y no se repite."""
    motor = await _motor()
    doble = VozDoble(guion=[senal(0.1), senal(0.2)], antes_del_audio=True)
    canal = CanalFalso(entrantes=[SILENCIO], seguir=lambda: len(doble.dicho) < 1)

    await asyncio.wait_for(_correr(motor, canal, doble).run(), timeout=5)

    assert canal.de_tipo(voz.StopAudio) == []
    assert len(doble.dicho) == 1, "la apertura se repitio: algo la interrumpio"
    assert motor.disclosed_at is not None, "la apertura nunca llego a registrarse"
    assert len(canal.audio) == doble.trozos, "la apertura no se envio entera"


async def test_la_senal_se_descarta_al_buscar_una_interrupcion_y_no_tapa_las_palabras(
    catalogo: None,
) -> None:
    """Lo que viene detras de una senal sigue contando: la interrupcion es de las palabras."""
    motor = await _motor()
    ciclo = _correr(motor, CanalFalso(), VozDoble())
    ciclo._oido.put_nowait(senal(0.1))
    assert ciclo._interrupcion() is None
    assert ciclo._oido.empty()

    hablo = _final("wait I need to correct something")
    ciclo._oido.put_nowait(senal(0.2))
    ciclo._oido.put_nowait(hablo)
    assert ciclo._interrupcion() == hablo


async def test_un_turno_con_senales_sin_palabras_deja_un_evento_sin_texto(
    catalogo: None,
) -> None:
    """Para contar en llamadas reales cuanto ruido hay: una vez por turno, con cuantas senales
    fueron y cuanto alargaron el plazo, y nunca lo que se dijo (ADR-013)."""
    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        _, ciclo, _, _ = await _ciclo_de_muletilla(_grafo_lento(timedelta(0)), filler_after=None)
        await asyncio.wait_for(
            ciclo._atender(
                voz.SpeechEnd(
                    text="does my policy cover a rental car?",
                    at=_reloj() - timedelta(milliseconds=400),
                    last_audible_word_at=None,
                    last=_final("does my policy cover a rental car?"),
                    unconfirmed_signals=2,
                    held_by_signals=timedelta(milliseconds=1350),
                )
            ),
            timeout=5,
        )
    finally:
        observability.set_stream(sys.stdout)

    (evento,) = _eventos(salida, "voice.speech_signal_discarded")
    assert evento["signals"] == 2
    assert evento["held_ms"] == 1350
    assert evento["call_id"]
    assert evento["turn_id"] == f"{evento['call_id']}-t1"
    (linea,) = [x for x in salida.getvalue().splitlines() if "speech_signal_discarded" in x]
    assert "rental" not in linea, "el evento no lleva lo que se dijo"


async def test_un_turno_sin_senales_sin_palabras_no_deja_ese_evento(catalogo: None) -> None:
    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        _, ciclo, _, _ = await _ciclo_de_muletilla(_grafo_lento(timedelta(0)), filler_after=None)
        await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)
    finally:
        observability.set_stream(sys.stdout)

    assert _eventos(salida, "voice.speech_signal_discarded") == []


def _silencio_con_senal_durante_el_turno(*, senal_a_tiempo: bool) -> tuple[VozDoble, asyncio.Event]:
    """Una escucha que avisa de voz cuando el grafo ya arranco --es decir, con el turno ya
    cerrado--, o sin avisar. Su flujo sigue abierto: una escucha que se acaba es una llamada
    que se corto, y esa no lleva muletilla."""
    arranco = asyncio.Event()
    guion = [senal(0.4)] if senal_a_tiempo else []
    return VozDoble(guion=guion, esperar_a=arranco.is_set), arranco


def _grafo_que_tarda_tras_arrancar(arranco: asyncio.Event) -> voz.TurnHandler:
    """Avisa que arranco y contesta despues de `RESPUESTA_LENTA`, mucho mas que `ESPERA_CORTA`."""

    async def grafo(turn: c14.InboundTurn) -> AsyncIterator[c14.TurnEvent]:
        arranco.set()
        await asyncio.sleep(RESPUESTA_LENTA.total_seconds())
        yield c14.FinalText(message_id="m1", text="Noted.", language=turn.language)

    return grafo


@pytest.mark.parametrize(
    ("senal_a_tiempo", "hay_muletilla"),
    [
        pytest.param(False, True, id="sin-senal-la-muletilla-suena"),
        pytest.param(True, False, id="con-senal-no-hay-muletilla"),
    ],
)
async def test_si_la_persona_empieza_a_hablar_tras_cerrarse_el_turno_no_hay_muletilla(
    catalogo: None, senal_a_tiempo: bool, hay_muletilla: bool
) -> None:
    """La muletilla espera 20 ms a la respuesta; en ese plazo el reconocedor avisa de voz.
    El turno ya se cerro y no se deshace --la respuesta sigue su camino--, pero un
    «Listo...» encima de quien retoma la palabra solo estorba. La prueba pareada sin senal
    deja ver que lo unico que cambia es la senal."""
    doble, arranco = _silencio_con_senal_durante_el_turno(senal_a_tiempo=senal_a_tiempo)
    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        _, ciclo, _, _ = await _ciclo_de_muletilla(
            _grafo_que_tarda_tras_arrancar(arranco), doble=doble
        )
        escucha = asyncio.create_task(ciclo._escuchar())
        try:
            await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)
        finally:
            escucha.cancel()
            await asyncio.gather(escucha, return_exceptions=True)
    finally:
        observability.set_stream(sys.stdout)

    if hay_muletilla:
        assert doble.dicho == [_muletillas()[0], "Noted."]
        assert len(_eventos(salida, "voice.filler_said")) == 1
    else:
        assert doble.dicho == ["Noted."]
        assert _eventos(salida, "voice.filler_said") == []


async def test_una_senal_anterior_al_cierre_del_turno_no_quita_la_muletilla(
    catalogo: None,
) -> None:
    """Lo que aplaza una senal es el cierre del turno, y eso ya paso (lo hace el detector).
    La muletilla solo mira lo que llega **despues** de cerrado: la voz de antes era de lo
    que ya se dijo."""
    doble = VozDoble(guion=[senal(0.1)], antes_del_audio=True)
    _, ciclo, _, _ = await _ciclo_de_muletilla(_grafo_lento(), doble=doble)
    escucha = asyncio.create_task(ciclo._escuchar())
    try:
        await _ceder()
        assert ciclo._voces_oidas == 1, "la senal no llego antes del cierre"

        await asyncio.wait_for(ciclo._atender(_turno_cerrado()), timeout=5)
    finally:
        escucha.cancel()
        await asyncio.gather(escucha, return_exceptions=True)

    assert doble.dicho == [_muletillas()[0], "Noted."]
