"""La llamada simulada (`voice:simular`), sin llamar a nadie (2026-10-12).

La herramienta gasta dinero y no corre en GitHub: lo que si corre en cada entrega es todo
lo que no necesita un proveedor. El guion y su validacion (que un guion roto se diga antes
de gastar nada), el transporte simulado, la espera a la agente, el cableado del comando y
que los guiones versionados sirvan. Las frases con datos (`decir_con_datos`): que el guion las
lea, que lleguen a la escucha de la llamada como texto ya transcrito sin tocar la sintesis, y
que lo que entregan lo entienda el detector de turno de verdad.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import tomllib
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from untangle import paths
from untangle.base import Locale
from untangle.compliance.redaction import api as redaccion
from untangle.compliance.redaction.api import Redacted
from untangle.providers.ports import (
    SPEECH_AUDIO,
    ExternalText,
    ListenEvent,
    SpeechStarted,
    Transcript,
)
from untangle.server import composition, voice_cli, voice_simulation
from untangle.server.voice_simulation import (
    Pause,
    Say,
    SayWithData,
    Script,
    ScriptError,
    SimulatedChannel,
    VoiceWithDetail,
    VoiceWithTranscripts,
    WaitForAgent,
    describe_event,
    load_script,
    parse_script,
    partials_of,
    typed_duration_s,
)
from untangle.settings import Settings
from untangle.voice import api as voz
from untangle.voice.turn_detection import Ending, TurnDetector, ending_of

from ..voice.dobles import senal

GUIONES = paths.app_dir() / "evals" / "fixtures" / "voice-sim"


def _guion(*pasos: object, **resto: object) -> dict[str, object]:
    return {"pasos": list(pasos), **resto}


# --- El guion -----------------------------------------------------------------


def test_un_guion_completo_se_lee_paso_a_paso() -> None:
    guion = parse_script(
        _guion(
            {"esperar_agente": True},
            {"decir": " Hola "},
            {"pausa": 1.3},
            {"decir": "adios"},
            {"esperar_agente": True, "y": 1, "hasta": 10},
            descripcion="un caso",
            cola=2,
        )
    )

    assert guion.description == "un caso"
    assert guion.tail_s == 2.0
    assert guion.steps == (
        WaitForAgent(extra_s=0.4, timeout_s=40.0),
        Say("Hola"),
        Pause(1.3),
        Say("adios"),
        WaitForAgent(extra_s=1.0, timeout_s=10.0),
    )
    assert guion.say_chars == len("Hola") + len("adios")


def test_una_frase_con_datos_se_lee_como_tal_y_no_cuenta_como_voz() -> None:
    guion = parse_script(
        _guion(
            {"esperar_agente": True},
            {"decir": "Hola"},
            {"decir_con_datos": " Mi póliza es la POL-422088. "},
        )
    )

    assert guion.steps == (
        WaitForAgent(extra_s=0.4, timeout_s=40.0),
        Say("Hola"),
        SayWithData("Mi póliza es la POL-422088."),
    )
    assert guion.say_chars == len("Hola"), "solo lo sintetizado cuesta voz"
    assert (guion.said_phrases, guion.typed_phrases) == (1, 1)


def test_un_guion_de_solo_frases_con_datos_tiene_persona_y_no_gasta_voz() -> None:
    guion = parse_script(_guion({"decir_con_datos": "Mi póliza es la POL-422088."}))

    assert guion.say_chars == 0
    assert guion.typed_phrases == 1


def test_las_frases_con_datos_no_cuentan_para_el_tope_de_caracteres_sintetizados() -> None:
    """El tope existe porque la voz cuesta; un texto que llega ya transcrito no la usa."""
    guion = parse_script(_guion(*[{"decir_con_datos": "x" * 399}] * 6))

    assert guion.typed_phrases == 6
    assert guion.say_chars == 0


def test_la_cola_por_omision_deja_la_linea_abierta_unos_segundos() -> None:
    assert parse_script(_guion({"decir": "hola"})).tail_s == voice_simulation.DEFAULT_TAIL_S


@pytest.mark.parametrize(
    ("datos", "dice"),
    [
        ([{"decir": "hola"}], "objeto"),
        ({"pasos": []}, "al menos un paso"),
        ({}, "al menos un paso"),
        (_guion({"decir": "hola"}, extra=1), "no conoce extra"),
        (_guion({"decir": "hola", "pausa": 1}), "exactamente una"),
        (_guion({}), "exactamente una"),
        (_guion({"decir": "hola", "y": 1}), "no conoce y"),
        (_guion({"pausa": 1, "hasta": 3}), "no conoce hasta"),
        (_guion("hola"), "tiene que ser un objeto"),
        (_guion({"decir": ""}), "lleva una frase"),
        (_guion({"decir": "   "}), "lleva una frase"),
        (_guion({"decir": 7}), "lleva una frase"),
        (_guion({"decir": "x" * 401}), "pasa de 400"),
        (_guion({"decir_con_datos": ""}), "paso 1: decir_con_datos lleva una frase"),
        (_guion({"decir_con_datos": "  "}), "decir_con_datos lleva una frase"),
        (_guion({"decir_con_datos": 7}), "decir_con_datos lleva una frase"),
        (_guion({"decir_con_datos": ["POL-422088"]}), "decir_con_datos lleva una frase"),
        (_guion({"decir": "hola"}, {"decir_con_datos": "x" * 401}), "paso 2: la frase pasa de 400"),
        (_guion({"decir_con_datos": "hola", "decir": "hola"}), "exactamente una"),
        (_guion({"decir_con_datos": "hola", "y": 1}), "no conoce y"),
        (_guion({"decir_con_datos": "hola", "pausa": 1}), "exactamente una"),
        (_guion({"decir_dato": "hola"}), "exactamente una"),
        (_guion({"decir": "hola"}, cola=-1), "cola"),
        (_guion({"decir": "hola"}, cola="mucho"), "cola"),
        (_guion({"decir": "hola"}, cola=True), "cola"),
        (_guion({"pausa": -1}, {"decir": "hola"}), "pausa"),
        (_guion({"pausa": 61}, {"decir": "hola"}), "pausa"),
        (_guion({"pausa": "1"}, {"decir": "hola"}), "pausa"),
        (_guion({"esperar_agente": False}, {"decir": "hola"}), "true"),
        (_guion({"esperar_agente": True, "hasta": 0.5}, {"decir": "hola"}), "hasta"),
        (_guion({"esperar_agente": True, "y": -2}, {"decir": "hola"}), "y"),
        (_guion({"pausa": 1}), "no dice nada"),
        (_guion(*[{"decir": "hola"}] * 41), "pasa de 40 pasos"),
        (_guion(*[{"decir": "x" * 399}] * 6), "en total"),
    ],
)
def test_un_guion_roto_se_dice_antes_de_gastar_nada(datos: object, dice: str) -> None:
    with pytest.raises(ScriptError, match=dice):
        parse_script(datos)


def test_un_archivo_que_no_existe_o_no_es_json_nombra_el_archivo(tmp_path: Path) -> None:
    roto = tmp_path / "roto.json"
    roto.write_text("{ no es json", encoding="utf-8")

    with pytest.raises(ScriptError, match=r"no existe\.json"):
        load_script(tmp_path / "no existe.json")
    with pytest.raises(ScriptError, match=r"roto\.json.*no es JSON valido"):
        load_script(roto)


def test_un_paso_roto_dentro_de_un_archivo_nombra_archivo_y_paso(tmp_path: Path) -> None:
    archivo = tmp_path / "g.json"
    archivo.write_text('{"pasos": [{"decir": "hola"}, {"pausa": -3}]}', encoding="utf-8")

    with pytest.raises(ScriptError, match=r"g\.json.*paso 2"):
        load_script(archivo)


def test_los_guiones_versionados_sirven() -> None:
    """Se leen en cada entrega: un guion que no se puede leer se descubriria con la plata
    ya gastada, o no se descubriria."""
    archivos = sorted(GUIONES.glob("*.json"))
    assert {a.name for a in archivos} >= {
        "cierre-directo.json",
        "pausa-a-media-frase.json",
        "reporte-corto.json",
    }

    for archivo in archivos:
        guion = load_script(archivo)
        assert guion.description, f"{archivo.name} no dice que reproduce"
        assert isinstance(guion.steps[0], WaitForAgent), "primero se espera la apertura"
        assert guion.say_chars <= 400, f"{archivo.name} gasta de mas para ser de unos centavos"


def test_el_guion_de_la_pausa_a_media_frase_es_el_caso_de_la_llamada_real() -> None:
    guion = load_script(GUIONES / "pausa-a-media-frase.json")

    dicho = [paso.text for paso in guion.steps if isinstance(paso, Say)]
    assert dicho == ["Hola, quería consultar sobre", "si mi póliza me cubre un choque con una moto"]
    primero, segundo = (i for i, paso in enumerate(guion.steps) if isinstance(paso, Say))
    assert guion.steps[primero + 1 : segundo] == (Pause(1.3),)


def test_el_guion_del_reporte_corto_tiene_cuatro_turnos_de_la_persona() -> None:
    guion = load_script(GUIONES / "reporte-corto.json")

    assert sum(isinstance(paso, Say) for paso in guion.steps) == 4
    # Espera a la agente despues de cada cosa que dice, y la ultima es lo que cierra.
    assert isinstance(guion.steps[-1], WaitForAgent)
    for i, paso in enumerate(guion.steps[:-1]):
        if isinstance(paso, Say):
            assert isinstance(guion.steps[i + 1], WaitForAgent)


def test_el_guion_del_cierre_directo_da_la_poliza_ya_transcrita() -> None:
    """El guion existe para oir como termina un reporte de un solo vehiculo: la persona no
    puede dar su poliza por la voz sintetizada --saldria tapada--, asi que la da ya transcrita,
    y es una poliza del corpus de Autos Poblado, con su titular."""
    guion = load_script(GUIONES / "cierre-directo.json")
    poliza = json.loads(
        (
            paths.app_dir()
            / "data"
            / "tenants"
            / "sunmeadow"
            / "issued_policies"
            / "POL-422088.json"
        ).read_text(encoding="utf-8")
    )

    con_datos = [paso for paso in guion.steps if isinstance(paso, SayWithData)]
    assert len(con_datos) == 1
    assert poliza["policy_number"] in con_datos[0].text
    assert poliza["named_insured"]["full_name"] in con_datos[0].text
    sintetizadas = [paso.text for paso in guion.steps if isinstance(paso, Say)]
    assert sintetizadas, "una llamada de verdad tambien pasa por la voz y el reconocedor"
    # Lo que se sintetiza no lleva ningun dato con forma de dato: la redaccion lo taparia.
    for frase in sintetizadas:
        assert str(redaccion.redact(frase, language="es")) == frase
    # Y por eso la frase con datos no puede ir por ahi: la redaccion la altera.
    assert str(redaccion.redact(con_datos[0].text, language="es")) != con_datos[0].text


def test_el_guion_del_cierre_directo_deja_tiempo_para_oir_el_resultado() -> None:
    guion = load_script(GUIONES / "cierre-directo.json")

    assert isinstance(guion.steps[-1], WaitForAgent)
    assert guion.steps[-1].timeout_s >= 30, "el cierre corre en el fondo y tarda"
    assert guion.tail_s >= 15, "la linea sigue abierta para oir la despedida"
    # Cada frase de la persona espera a la agente, tambien la que llega ya transcrita.
    for i, paso in enumerate(guion.steps[:-1]):
        if isinstance(paso, (Say, SayWithData)):
            assert isinstance(guion.steps[i + 1], WaitForAgent)


# --- El transporte simulado ---------------------------------------------------


class _Reloj:
    """Un reloj que solo avanza cuando la prueba lo dice."""

    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


def _canal(salida: list[str], reloj: _Reloj | None = None) -> SimulatedChannel:
    """Con un reloj que la prueba mueve; sin el, con el de verdad (lo que esperar necesita:
    un reloj parado no vence nunca el plazo)."""
    if reloj is None:
        return SimulatedChannel(echo=salida.append)
    return SimulatedChannel(echo=salida.append, clock=reloj, started_at=reloj())


async def test_los_cuadros_salen_con_el_tiempo_desde_que_empezo_la_llamada() -> None:
    salida: list[str] = []
    reloj = _Reloj()
    canal = _canal(salida, reloj)
    reloj.t += 12.98

    await canal.send(voz.Transcript(speaker="agent", text="Hola, te ayudo", final=True))

    assert salida == [
        '[ 12.98s] <- Transcript {"speaker": "agent", "text": "Hola, te ayudo", "final": true}'
    ]


async def test_un_parcial_no_se_imprime_ni_cuenta_como_frase_de_la_agente() -> None:
    salida: list[str] = []
    canal = _canal(salida)

    await canal.send(voz.Transcript(speaker="insured", text="hola que", final=False))
    await canal.send(voz.Transcript(speaker="insured", text="hola que tal", final=True))
    await canal.send(voz.Transcript(speaker="agent", text="Listo…", final=True))

    assert len(salida) == 2
    assert canal.agent_phrases == 1, "solo cuentan las de la agente"


async def test_el_estado_dice_si_la_agente_vuelve_a_escuchar() -> None:
    canal = _canal([])

    await canal.send(voz.State("speaking"))
    assert not canal.agent_is_listening
    await canal.send(voz.State("listening"))
    assert canal.agent_is_listening


async def test_el_audio_de_la_agente_avisa_una_vez_por_rafaga() -> None:
    salida: list[str] = []
    reloj = _Reloj()
    canal = _canal(salida, reloj)

    await canal.send_audio(b"\x00" * 960)
    reloj.t += 0.1
    await canal.send_audio(b"\x00" * 960)
    reloj.t += 2.0
    await canal.send_audio(b"\x00" * 960)

    assert len([linea for linea in salida if "empieza a sonar" in linea]) == 2
    assert canal.audio_bytes == 3 * 960


async def test_la_persona_entra_por_trozos_de_veinte_ms_y_calla_con_silencio() -> None:
    canal = _canal([])
    trozo = voice_simulation._FRAME_BYTES
    duracion = canal.say(b"\x01" * (2 * trozo + 80))
    assert duracion == pytest.approx((2 * trozo + 80) / SPEECH_AUDIO.bytes_per_second)

    llegados: list[bytes | voz.Hangup] = []
    async for pieza in canal.inbound():
        llegados.append(pieza)
        if len(llegados) == 4:
            canal.hung_up = True

    assert llegados[0] == b"\x01" * trozo
    assert llegados[1] == b"\x01" * trozo
    # El ultimo trozo de la frase se rellena con silencio: nada se corta.
    assert llegados[2] == (b"\x01" * 80).ljust(trozo, b"\x00")
    # Y cuando ya no hay nada que decir, el microfono abierto manda silencio.
    assert llegados[3] == voice_simulation._SILENCE
    assert isinstance(llegados[4], voz.Hangup)


async def test_sin_nada_que_decir_el_microfono_manda_silencio() -> None:
    canal = _canal([])
    vistos: list[bytes | voz.Hangup] = []
    async for pieza in canal.inbound():
        vistos.append(pieza)
        if len(vistos) == 2:
            canal.hung_up = True

    assert vistos[:2] == [voice_simulation._SILENCE, voice_simulation._SILENCE]


# --- Esperar a la agente ------------------------------------------------------


def _ciclo_sonando_hasta(hasta: datetime | None) -> Any:
    return SimpleNamespace(playback_ends_at=hasta)


async def test_esperar_a_la_agente_necesita_una_frase_nueva_y_que_vuelva_a_escuchar() -> None:
    canal = _canal([])
    canal.state = "listening"  # el estado de antes de que ella conteste
    canal.agent_phrases = 3
    ciclo = _ciclo_sonando_hasta(None)

    async def contesta() -> None:
        await asyncio.sleep(0.15)
        await canal.send(voz.State("speaking"))
        await canal.send(voz.Transcript(speaker="agent", text="Listo", final=True))
        await asyncio.sleep(0.15)
        await canal.send(voz.State("listening"))

    tarea = asyncio.create_task(contesta())
    visto = await asyncio.wait_for(
        voice_simulation._wait_for_agent(
            canal, ciclo, WaitForAgent(extra_s=0, timeout_s=5), frases_antes=3
        ),
        timeout=5,
    )
    await tarea

    assert visto is True
    assert canal.agent_phrases == 4, "no salio con el estado viejo de antes de que contestara"


async def test_esperar_a_la_agente_no_sale_mientras_el_audio_sigue_sonando() -> None:
    salida: list[str] = []
    canal = _canal(salida)
    canal.state = "listening"
    canal.agent_phrases = 1
    sonando = datetime.now(UTC) + timedelta(seconds=0.4)
    ciclo = _ciclo_sonando_hasta(sonando)

    visto = await voice_simulation._wait_for_agent(
        canal, ciclo, WaitForAgent(extra_s=0, timeout_s=5), frases_antes=0
    )

    assert visto is True
    assert datetime.now(UTC) >= sonando


async def test_si_la_agente_no_contesta_el_guion_sigue_y_lo_dice() -> None:
    salida: list[str] = []
    canal = _canal(salida)
    canal.state = "listening"
    ciclo = _ciclo_sonando_hasta(None)

    visto = await voice_simulation._wait_for_agent(
        canal, ciclo, WaitForAgent(extra_s=0, timeout_s=0.25), frases_antes=0
    )

    assert visto is False
    assert any("la agente no contesto en 0.25 s" in linea for linea in salida)


async def test_si_la_persona_ya_colgo_no_espera_nada() -> None:
    canal = _canal([])
    canal.hung_up = True

    visto = await voice_simulation._wait_for_agent(
        canal, _ciclo_sonando_hasta(None), WaitForAgent(extra_s=0, timeout_s=30), frases_antes=0
    )

    assert visto is False


# --- La persona del guion -----------------------------------------------------


async def test_la_persona_dice_calla_espera_y_al_final_cuelga() -> None:
    salida: list[str] = []
    canal = _canal(salida)
    ciclo = _ciclo_sonando_hasta(None)
    canal.state = "listening"
    guion = Script(
        description="",
        steps=(Say("hola"), Pause(0.05), Say("adios")),
        tail_s=0.05,
    )
    audios = {"hola": b"\x01" * 960, "adios": b"\x02" * 960}

    await asyncio.wait_for(voice_simulation._person(canal, ciclo, guion, audios), timeout=5)

    dicho = [linea.split("persona dice: ")[1] for linea in salida if "persona dice" in linea]
    assert [d.split(" (")[0] for d in dicho] == ["'hola'", "'adios'"]
    assert salida[-1].endswith("persona cuelga")
    assert canal.hung_up is True
    assert canal.queue.qsize() == 2, "el audio de las dos frases quedo en la cola"


# --- `--detalle`: los parciales y las senales de voz --------------------------------


def _parcial(texto: str) -> Transcript:
    return Transcript(text=ExternalText(texto), is_final=False)


def _final(texto: str) -> Transcript:
    return Transcript(text=ExternalText(texto), is_final=True)


def test_un_parcial_y_una_senal_se_describen_y_un_final_no() -> None:
    assert describe_event(senal(0.3)) == "senal de voz, a los 0.30 s del audio"
    assert describe_event(_parcial("si mi póliza")) == "parcial 'si mi póliza'"
    assert describe_event(_final("si mi póliza me cubre.")) is None, (
        "los finales ya salen como cuadros"
    )


class _CallVoiceDoble:
    """Un `CallVoice` que entrega lo que se le da, y deja ver que se le pidio."""

    def __init__(self, eventos: list[ListenEvent], reloj: _Reloj | None = None) -> None:
        self.eventos = eventos
        self.reloj = reloj
        self.cerrado = False
        self.pidio_hablar: list[tuple[str, str, voz.VoiceMode, Locale]] = []

    async def _escuchar(self) -> AsyncIterator[ListenEvent]:
        try:
            for evento in self.eventos:
                if self.reloj is not None:
                    self.reloj.t += 0.5
                yield evento
        finally:
            self.cerrado = True

    def listen(
        self, tenant_id: str, audio: AsyncIterator[bytes], *, language: Locale
    ) -> AsyncIterator[ListenEvent]:
        del tenant_id, audio, language
        return self._escuchar()

    def speak(
        self, tenant_id: str, text: Redacted, *, mode: voz.VoiceMode, language: Locale
    ) -> AsyncIterator[bytes]:
        self.pidio_hablar.append((tenant_id, str(text), mode, language))

        async def trozos() -> AsyncIterator[bytes]:
            yield b"\x00"

        return trozos()


async def test_el_detalle_imprime_parciales_y_senales_con_su_tiempo_y_no_toca_el_flujo() -> None:
    salida: list[str] = []
    reloj = _Reloj()
    canal = _canal(salida, reloj)
    eventos: list[ListenEvent] = [
        senal(0.3),
        _parcial("si mi póliza"),
        _parcial("si mi póliza me cubre"),
        _final("Si mi póliza me cubre un choque."),
    ]
    voz_doble = _CallVoiceDoble(eventos, reloj)

    entregados = [
        e
        async for e in VoiceWithDetail(voz_doble, canal).listen(
            "knotwell", _sin_audio(), language="es"
        )
    ]

    assert entregados == eventos, "el testigo no cambia, quita ni reordena nada"
    assert salida == [
        "[  0.50s] ~ reconocedor: senal de voz, a los 0.30 s del audio",
        "[  1.00s] ~ reconocedor: parcial 'si mi póliza'",
        "[  1.50s] ~ reconocedor: parcial 'si mi póliza me cubre'",
    ]


async def _sin_audio() -> AsyncIterator[bytes]:
    yield b"\x00"


async def test_el_detalle_cierra_el_flujo_del_reconocedor_si_el_ciclo_lo_deja() -> None:
    voz_doble = _CallVoiceDoble([senal(0.1), senal(0.2)])
    escucha = VoiceWithDetail(voz_doble, _canal([])).listen("knotwell", _sin_audio(), language="es")

    primero = await anext(escucha)
    await escucha.aclose()

    assert primero == senal(0.1)
    assert voz_doble.cerrado, "el testigo dejo abierto el flujo del reconocedor"


async def test_el_detalle_no_cambia_lo_que_se_le_pide_a_la_sintesis() -> None:
    voz_doble = _CallVoiceDoble([])
    testigo = VoiceWithDetail(voz_doble, _canal([]))
    frase = redaccion.from_catalog("Hola.", language="es")

    trozos = [
        t async for t in testigo.speak("knotwell", frase, mode=voz.VoiceMode.PRIMARY, language="es")
    ]

    assert trozos == [b"\x00"]
    assert voz_doble.pidio_hablar == [("knotwell", "Hola.", voz.VoiceMode.PRIMARY, "es")]


class _CallVoiceConSesion(_CallVoiceDoble):
    """Una voz que ofrece la sesion de la llamada y deja ver que se le pidio."""

    def __init__(self) -> None:
        super().__init__([])
        self.sesiones: list[tuple[str, voz.VoiceMode, Locale]] = []
        self.boca: list[str] = []

    @contextlib.asynccontextmanager
    async def speech_session(
        self, tenant_id: str, *, mode: voz.VoiceMode, language: Locale
    ) -> AsyncIterator[voz.CallSpeech]:
        self.sesiones.append((tenant_id, mode, language))
        yield self
        self.boca.append("cerrada")


async def test_el_detalle_deja_pasar_la_sesion_de_la_voz_para_medir_la_llamada_de_verdad() -> None:
    """La simulacion existe para medir la llamada como es: con su conexion unica de sintesis."""
    voz_doble = _CallVoiceConSesion()
    testigo = VoiceWithDetail(voz_doble, _canal([]))

    async with testigo.speech_session(
        "knotwell", mode=voz.VoiceMode.PRIMARY, language="es"
    ) as boca:
        assert boca is voz_doble

    assert voz_doble.sesiones == [("knotwell", voz.VoiceMode.PRIMARY, "es")]
    assert voz_doble.boca == ["cerrada"]


async def test_el_detalle_sobre_una_voz_sin_sesion_habla_por_la_voz_suelta() -> None:
    voz_doble = _CallVoiceDoble([])
    testigo = VoiceWithDetail(voz_doble, _canal([]))

    async with testigo.speech_session(
        "knotwell", mode=voz.VoiceMode.PRIMARY, language="es"
    ) as boca:
        assert boca is voz_doble


# --- `decir_con_datos`: frases que llegan ya transcritas ----------------------------

FRASE_CON_DATOS = "Me llamo Ana Torres y mi póliza es la POL-422088."


@pytest.fixture
def decir_sin_esperar(monkeypatch: pytest.MonkeyPatch) -> None:
    """Una frase con datos tarda en decirse lo que dice `typed_duration_s`: aqui, nada."""
    monkeypatch.setattr(voice_simulation, "TYPED_CHARS_PER_S", 1e9)
    monkeypatch.setattr(voice_simulation, "MIN_TYPED_S", 0.0)


class _ReconocedorALaMano:
    """Un reconocedor que entrega lo que la prueba le va dando y termina cuando ella dice.

    Deja ver si se cerro su flujo y si le pidieron sintetizar algo: una frase con datos no
    debe llegar nunca a la sintesis.
    """

    def __init__(self) -> None:
        self.dado: asyncio.Queue[ListenEvent | Exception | None] = asyncio.Queue()
        self.cerrado = False
        self.pidio_hablar: list[str] = []

    async def _escuchar(self) -> AsyncIterator[ListenEvent]:
        try:
            while True:
                evento = await self.dado.get()
                if evento is None:
                    return
                if isinstance(evento, Exception):
                    raise evento
                yield evento
        finally:
            self.cerrado = True

    def listen(
        self, tenant_id: str, audio: AsyncIterator[bytes], *, language: Locale
    ) -> AsyncIterator[ListenEvent]:
        del tenant_id, audio, language
        return self._escuchar()

    def speak(
        self, tenant_id: str, text: Redacted, *, mode: voz.VoiceMode, language: Locale
    ) -> AsyncIterator[bytes]:
        del tenant_id, mode, language
        self.pidio_hablar.append(str(text))

        async def trozos() -> AsyncIterator[bytes]:
            yield b"\x00"

        return trozos()


def _tareas_sueltas() -> set[asyncio.Task[Any]]:
    return {t for t in asyncio.all_tasks() if t is not asyncio.current_task()}


async def _siguiente(escucha: AsyncIterator[ListenEvent]) -> ListenEvent:
    return await asyncio.wait_for(anext(escucha), timeout=5)


def test_la_duracion_de_una_frase_con_datos_crece_con_su_largo_y_tiene_piso() -> None:
    assert typed_duration_s("Si.") == voice_simulation.MIN_TYPED_S
    assert typed_duration_s(FRASE_CON_DATOS) == pytest.approx(
        len(FRASE_CON_DATOS) / voice_simulation.TYPED_CHARS_PER_S
    )
    assert typed_duration_s(FRASE_CON_DATOS) > typed_duration_s("Mi póliza es la POL-422088.")


#: Una frase como la de la llamada simulada del 2026-10-13 (4,6 s a ritmo de `TYPED_CHARS_PER_S`):
#: la agente pregunto «¿sigues ahi?» a los 4 s porque entre la senal y el final no llego nada.
FRASE_LARGA = "Me llamo Ana Torres Gomez y mi póliza es la POL-422088, por favor."


def _momentos_oidos(frase: str) -> list[float]:
    """Cuando llega algo a la escucha de la llamada: la senal en 0, los parciales y el final."""
    return [0.0, *(llegada for llegada, _ in partials_of(frase)), typed_duration_s(frase)]


def test_la_frase_larga_no_deja_pasar_mas_de_un_parcial_de_silencio_entre_la_senal_y_el_final() -> (
    None
):
    """La escalera de silencios cuenta desde lo ultimo oido, parcial incluido. Con la frase de la
    llamada simulada --4,6 s--, sin parciales el silencio corria durante toda la frase."""
    assert typed_duration_s(FRASE_LARGA) > 4.0, (
        "mas larga que la tolerancia de silencio de la llamada"
    )

    momentos = _momentos_oidos(FRASE_LARGA)

    huecos = [b - a for a, b in pairwise(momentos)]
    assert len(momentos) > 3, "hay parciales entre la senal y el final"
    assert max(huecos) <= voice_simulation.PARTIAL_EVERY_S + 1e-9
    assert huecos[0] == pytest.approx(voice_simulation.FIRST_PARTIAL_S), "el primero llega pronto"


def test_los_parciales_son_las_primeras_palabras_y_van_creciendo_sin_llegar_a_la_frase() -> None:
    palabras = FRASE_LARGA.split()

    parciales = partials_of(FRASE_LARGA)

    assert parciales, "una frase larga tiene parciales"
    cuantas = [len(texto.split()) for _, texto in parciales]
    assert cuantas == sorted(cuantas) and len(set(cuantas)) > 1, "agregan palabras"
    assert cuantas[0] >= 1 and cuantas[-1] < len(palabras), "ninguno trae la frase entera"
    for _, texto in parciales:
        assert texto.split() == palabras[: len(texto.split())], "son las primeras palabras"
    llegadas = [llegada for llegada, _ in parciales]
    assert llegadas == sorted(llegadas) and llegadas[-1] < typed_duration_s(FRASE_LARGA)


@pytest.mark.parametrize("frase", ["Si.", "Sí, sí.", "Hola", "Anticonstitucionalmente"])
def test_una_frase_que_se_dice_antes_del_primer_parcial_o_de_una_palabra_no_lleva_parciales(
    frase: str,
) -> None:
    assert typed_duration_s(frase) <= voice_simulation.FIRST_PARTIAL_S or len(frase.split()) == 1
    assert partials_of(frase) == ()


def test_los_segundos_de_audio_son_los_de_la_llamada_y_nunca_negativos() -> None:
    reloj = _Reloj()
    canal = _canal([], reloj)

    assert canal.stream_seconds() == 0.0
    reloj.t += 3.25
    assert canal.stream_seconds() == pytest.approx(3.25)
    reloj.t -= 10
    assert canal.stream_seconds() == 0.0


async def test_la_persona_entrega_la_frase_con_datos_sin_sintetizarla(
    decir_sin_esperar: None,
) -> None:
    salida: list[str] = []
    canal = _canal(salida)
    canal.state = "listening"
    guion = Script(description="", steps=(SayWithData(FRASE_CON_DATOS), Pause(0.01)), tail_s=0.01)

    # Sin audios: el camino de las frases sintetizadas buscaria la frase ahi y no la hallaria.
    ciclo = _ciclo_sonando_hasta(None)
    await asyncio.wait_for(voice_simulation._person(canal, ciclo, guion, {}), timeout=5)

    assert canal.heard.qsize() == 2
    primero, segundo = canal.heard.get_nowait(), canal.heard.get_nowait()
    assert isinstance(primero, SpeechStarted)
    assert segundo == Transcript(text=ExternalText(FRASE_CON_DATOS), is_final=True)
    assert canal.queue.qsize() == 0, "no se puso audio en el microfono"
    dicho = [linea for linea in salida if "persona dice" in linea]
    assert len(dicho) == 1
    assert "texto ya transcrito" in dicho[0]
    assert FRASE_CON_DATOS in dicho[0]
    assert salida[-1].endswith("persona cuelga")


async def test_la_senal_de_voz_de_la_frase_con_datos_lleva_los_segundos_de_la_llamada(
    decir_sin_esperar: None,
) -> None:
    reloj = _Reloj()
    canal = _canal([], reloj)
    reloj.t += 7.5

    await voice_simulation._say_with_data(canal, SayWithData(FRASE_CON_DATOS))

    primero = canal.heard.get_nowait()
    assert isinstance(primero, SpeechStarted)
    assert primero.at_s == pytest.approx(7.5)


async def test_entre_la_senal_y_el_final_la_frase_con_datos_entrega_parciales_con_palabras(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Como el reconocedor de verdad: la senal, los parciales con las primeras palabras y, al
    terminar de decirse, el final con la frase entera. El tiempo va comprimido."""
    monkeypatch.setattr(voice_simulation, "TYPED_CHARS_PER_S", len(FRASE_CON_DATOS) / 0.4)
    monkeypatch.setattr(voice_simulation, "FIRST_PARTIAL_S", 0.05)
    monkeypatch.setattr(voice_simulation, "PARTIAL_EVERY_S", 0.12)
    canal = _canal([])

    await asyncio.wait_for(
        voice_simulation._say_with_data(canal, SayWithData(FRASE_CON_DATOS)), timeout=5
    )

    eventos = [canal.heard.get_nowait() for _ in range(canal.heard.qsize())]
    assert isinstance(eventos[0], SpeechStarted)
    assert eventos[-1] == Transcript(text=ExternalText(FRASE_CON_DATOS), is_final=True)
    parciales = eventos[1:-1]
    assert len(parciales) >= 2
    palabras = FRASE_CON_DATOS.split()
    previo = 0
    for parcial in parciales:
        assert isinstance(parcial, Transcript) and not parcial.is_final
        dichas = str(parcial.text).split()
        assert dichas == palabras[: len(dichas)], "las primeras palabras de la frase"
        assert previo < len(dichas) < len(palabras), "crece y no llega a la frase entera"
        previo = len(dichas)


async def test_tras_una_frase_con_datos_esperar_a_la_agente_pide_una_frase_nueva(
    decir_sin_esperar: None,
) -> None:
    """Como con una frase sintetizada: lo que la agente ya habia dicho no cuenta como respuesta."""
    salida: list[str] = []
    canal = _canal(salida)
    canal.state = "listening"
    canal.agent_phrases = 2
    guion = Script(
        description="",
        steps=(SayWithData(FRASE_CON_DATOS), WaitForAgent(extra_s=0, timeout_s=0.25)),
        tail_s=0.0,
    )

    ciclo = _ciclo_sonando_hasta(None)
    await asyncio.wait_for(voice_simulation._person(canal, ciclo, guion, {}), timeout=5)

    assert any("la agente no contesto en 0.25 s" in linea for linea in salida)


async def test_las_frases_con_datos_llegan_mezcladas_con_lo_que_entrega_el_reconocedor() -> None:
    canal = _canal([])
    reconocedor = _ReconocedorALaMano()
    escucha = VoiceWithTranscripts(reconocedor, canal).listen(
        "sunmeadow", _sin_audio(), language="es"
    )
    escrito: list[ListenEvent] = [senal(2.0), _final(FRASE_CON_DATOS)]

    reconocedor.dado.put_nowait(senal(0.1))
    assert await _siguiente(escucha) == senal(0.1)
    for evento in escrito:
        canal.hear(evento)
    assert [await _siguiente(escucha), await _siguiente(escucha)] == escrito
    reconocedor.dado.put_nowait(_final("Si, soy yo."))
    assert await _siguiente(escucha) == _final("Si, soy yo.")
    reconocedor.dado.put_nowait(None)

    with pytest.raises(StopAsyncIteration):
        await _siguiente(escucha)
    assert reconocedor.cerrado
    assert reconocedor.pidio_hablar == [], "nada de lo escrito paso por la sintesis"
    assert _tareas_sueltas() == set()


async def test_la_escucha_mezclada_entrega_lo_escrito_aunque_el_reconocedor_calle() -> None:
    """El microfono manda silencio mientras la persona 'habla' el texto: el reconocedor no
    dice nada, y la frase tiene que llegar igual."""
    canal = _canal([])
    reconocedor = _ReconocedorALaMano()
    escucha = VoiceWithTranscripts(reconocedor, canal).listen(
        "sunmeadow", _sin_audio(), language="es"
    )

    canal.hear(_final(FRASE_CON_DATOS))

    assert await _siguiente(escucha) == _final(FRASE_CON_DATOS)
    await escucha.aclose()


async def test_si_el_reconocedor_falla_el_fallo_sale_por_la_escucha_mezclada() -> None:
    canal = _canal([])
    reconocedor = _ReconocedorALaMano()
    escucha = VoiceWithTranscripts(reconocedor, canal).listen(
        "sunmeadow", _sin_audio(), language="es"
    )
    reconocedor.dado.put_nowait(senal(0.1))
    assert await _siguiente(escucha) == senal(0.1)
    reconocedor.dado.put_nowait(RuntimeError("el reconocedor se cayo"))

    with pytest.raises(RuntimeError, match="el reconocedor se cayo"):
        await _siguiente(escucha)
    assert reconocedor.cerrado
    assert _tareas_sueltas() == set()


async def test_la_escucha_mezclada_cierra_el_reconocedor_y_sus_tareas_si_el_ciclo_la_deja() -> None:
    canal = _canal([])
    reconocedor = _ReconocedorALaMano()
    escucha = VoiceWithTranscripts(reconocedor, canal).listen(
        "sunmeadow", _sin_audio(), language="es"
    )
    reconocedor.dado.put_nowait(senal(0.1))

    assert await _siguiente(escucha) == senal(0.1)
    await escucha.aclose()

    assert reconocedor.cerrado, "el testigo dejo abierto el flujo del reconocedor"
    assert _tareas_sueltas() == set(), "quedaron tareas leyendo despues de cerrar"


async def test_lo_que_entrega_una_frase_con_datos_lo_cierra_el_detector_de_turno(
    decir_sin_esperar: None,
) -> None:
    """El fin del turno no es un evento: es el silencio tras el final. Se prueba con el
    detector de verdad, el mismo que usa el ciclo, que la senal y el final bastan para cerrarlo."""
    canal = _canal([])
    reconocedor = _ReconocedorALaMano()
    escucha = VoiceWithTranscripts(reconocedor, canal).listen(
        "sunmeadow", _sin_audio(), language="es"
    )
    ahora = datetime.now(UTC)
    detector = TurnDetector(started_at=ahora)

    await voice_simulation._say_with_data(canal, SayWithData(FRASE_CON_DATOS))
    senal_de_voz, final = await _siguiente(escucha), await _siguiente(escucha)
    assert isinstance(senal_de_voz, SpeechStarted)
    detector.speech_started(ahora)
    abierto_con_la_senal = detector.speaking
    assert not abierto_con_la_senal, "una senal sin turno abierto no abre nada"
    assert isinstance(final, Transcript)
    detector.observe(final, at=ahora)

    assert detector.speaking
    assert ending_of(FRASE_CON_DATOS) is Ending.CLOSED, "termina en punto: se espera lo corto"
    assert not detector.expired(ahora)
    assert detector.expired(ahora + detector.end_of_speech + timedelta(milliseconds=1))
    assert detector.close().text == FRASE_CON_DATOS
    await escucha.aclose()


async def test_la_voz_con_frases_con_datos_deja_pasar_la_sintesis_y_la_sesion() -> None:
    voz_doble = _CallVoiceConSesion()
    testigo = VoiceWithTranscripts(voz_doble, _canal([]))
    frase = redaccion.from_catalog("Hola.", language="es")

    trozos = [
        t
        async for t in testigo.speak("sunmeadow", frase, mode=voz.VoiceMode.PRIMARY, language="es")
    ]
    async with testigo.speech_session(
        "sunmeadow", mode=voz.VoiceMode.PRIMARY, language="es"
    ) as boca:
        assert boca is voz_doble

    assert trozos == [b"\x00"]
    assert voz_doble.pidio_hablar == [("sunmeadow", "Hola.", voz.VoiceMode.PRIMARY, "es")]
    assert voz_doble.sesiones == [("sunmeadow", voz.VoiceMode.PRIMARY, "es")]


async def test_los_testigos_se_apilan_y_la_sesion_llega_hasta_la_voz_de_verdad() -> None:
    voz_doble = _CallVoiceConSesion()
    canal = _canal([])
    apilados = VoiceWithDetail(VoiceWithTranscripts(voz_doble, canal), canal)

    async with apilados.speech_session(
        "sunmeadow", mode=voz.VoiceMode.PRIMARY, language="es"
    ) as boca:
        assert boca is voz_doble

    assert voz_doble.sesiones == [("sunmeadow", voz.VoiceMode.PRIMARY, "es")]


@pytest.mark.parametrize(
    ("con_datos", "detalle"), [(False, False), (True, False), (False, True), (True, True)]
)
def test_la_escucha_solo_se_envuelve_si_el_guion_o_el_detalle_lo_piden(
    con_datos: bool, detalle: bool
) -> None:
    voz_doble = _CallVoiceDoble([])
    paso = SayWithData(FRASE_CON_DATOS) if con_datos else Say("Hola")

    escucha = voice_simulation._listening_voice(
        voz_doble, _canal([]), Script(description="", steps=(paso,), tail_s=0.0), detail=detalle
    )

    if detalle:
        assert isinstance(escucha, VoiceWithDetail), "el detalle va por fuera"
        interior = escucha.inner
    else:
        interior = escucha
    if con_datos:
        assert isinstance(interior, VoiceWithTranscripts)
        assert interior.inner is voz_doble
    else:
        assert interior is voz_doble, "sin nada que testificar, la voz del aplicativo va sola"


def test_el_comando_acepta_detalle_y_por_omision_no_lo_pide() -> None:
    sin = voice_cli._analizador().parse_args(["simular", "--tenant", "k", "--guion", "g.json"])
    con = voice_cli._analizador().parse_args(
        ["simular", "--tenant", "k", "--guion", "g.json", "--detalle"]
    )

    assert sin.detalle is False
    assert con.detalle is True


@pytest.mark.parametrize(
    ("argumentos", "esperado"),
    [
        ({}, False),
        ({"detalle": False}, False),
        ({"detalle": True}, True),
    ],
)
def test_run_pasa_el_detalle_a_la_llamada(
    monkeypatch: pytest.MonkeyPatch, argumentos: dict[str, bool], esperado: bool
) -> None:
    recibido: list[bool] = []

    async def sin_llamar(*_: object, **kwargs: Any) -> None:
        recibido.append(kwargs["detail"])

    monkeypatch.setattr(voice_simulation, "simulate", sin_llamar)

    voice_simulation.run(
        argparse.Namespace(
            guion=GUIONES / "reporte-corto.json", tenant="knotwell", language="es", **argumentos
        ),
        Settings(),
    )

    assert recibido == [esperado]


# --- Cuando la llamada falla --------------------------------------------------


def test_la_traza_completa_sale_a_la_consola(capsys: pytest.CaptureFixture[str]) -> None:
    salida: list[str] = []
    canal = _canal(salida)

    try:
        msg = "algo que dijo la persona"
        raise ValueError(msg)
    except ValueError as error:
        voice_simulation._print_failure(canal, error)

    visto = capsys.readouterr().out
    assert "LA LLAMADA FALLO: ValueError" in salida[0]
    assert "Traceback (most recent call last)" in visto
    assert "algo que dijo la persona" in visto, "esta herramienta si muestra el mensaje"


# --- El comando ---------------------------------------------------------------


def test_el_comando_se_llama_simular_y_pide_aseguradora_y_guion() -> None:
    argumentos = voice_cli._analizador().parse_args(
        ["simular", "--tenant", "knotwell", "--guion", "g.json"]
    )

    assert (argumentos.comando, argumentos.tenant, argumentos.language) == (
        "simular",
        "knotwell",
        "es",
    )
    assert argumentos.guion == Path("g.json")
    with pytest.raises(SystemExit):
        voice_cli._analizador().parse_args(["simular", "--tenant", "knotwell"])
    with pytest.raises(SystemExit):
        voice_cli._analizador().parse_args(["simular", "--guion", "g.json"])


def test_la_ayuda_funciona_sin_levantar_nada(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as salida:
        voice_cli.main(["simular", "--help"])

    assert salida.value.code == 0
    assert "--guion" in capsys.readouterr().out


def test_un_guion_roto_no_levanta_la_aplicacion_ni_gasta(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_debe_levantarse(*_: object, **__: object) -> None:
        msg = "levanto la aplicacion con un guion roto"
        raise AssertionError(msg)

    monkeypatch.setattr(composition, "build_app", no_debe_levantarse)

    codigo = voice_cli.main(
        ["simular", "--tenant", "knotwell", "--guion", str(tmp_path / "x.json")]
    )

    assert codigo == 1
    assert "guion invalido" in capsys.readouterr().err


def test_el_comando_dice_lo_que_cuesta_antes_de_llamar(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    llamadas: list[str] = []

    async def sin_llamar(*_: object, **kwargs: Any) -> None:
        llamadas.append(kwargs["tenant_id"])

    monkeypatch.setattr(voice_simulation, "simulate", sin_llamar)
    argumentos = argparse.Namespace(
        guion=GUIONES / "reporte-corto.json", tenant="knotwell", language="es"
    )

    codigo = voice_simulation.run(argumentos, Settings())

    salida = capsys.readouterr().out
    assert llamadas == ["knotwell"]
    assert codigo == 1, "sin llamada (simulate devolvio nada) no es un exito"
    assert "unos centavos" in salida
    assert "4 frases" in salida
    assert "ya transcritas" not in salida, "sin frases con datos el aviso no las menciona"


def test_el_comando_avisa_de_las_frases_con_datos_y_que_no_cuestan_voz(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def sin_llamar(*_: object, **__: object) -> None:
        return None

    monkeypatch.setattr(voice_simulation, "simulate", sin_llamar)
    argumentos = argparse.Namespace(
        guion=GUIONES / "cierre-directo.json", tenant="sunmeadow", language="es"
    )

    voice_simulation.run(argumentos, Settings())

    guion = load_script(GUIONES / "cierre-directo.json")
    salida = capsys.readouterr().out
    assert f"{guion.said_phrases} frases de la persona" in salida
    assert f"{guion.say_chars} caracteres por la voz del aplicativo" in salida
    assert "1 con datos que llegan ya transcritas, sin voz ni reconocedor" in salida


def test_la_tarea_de_mise_dice_que_cuesta_y_que_no_corre_en_github() -> None:
    mise = tomllib.loads((paths.repo_root() / "mise.toml").read_text(encoding="utf-8"))

    tarea = mise["tasks"]["voice:simular"]

    assert "centavos" in tarea["description"]
    assert "no corre en GitHub" in tarea["description"]
    assert tarea["run"].endswith("python -m untangle.server.voice_cli simular")
    assert "--env-file .env" in tarea["run"]
