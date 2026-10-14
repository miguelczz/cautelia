"""El conductor de voz: una grabación corrida por el transporte de la llamada (C-22).

Lo que aquí se comprueba no es que el conductor "funcione": es que lo que mide sea
**lo que una persona habría oído y dicho**, porque de eso depende lo único para lo
que existe --medir la voz contra DS-5 por hito--.

La grabación de estas pruebas es sintética: unas muestras de silencio en el
formato del aplicativo. No hace falta otra cosa, porque el reconocedor entra por
su puerto y aquí se sustituye por un doble con guion; lo que se mide es el camino,
no la transcripción. Las grabaciones de verdad son de personas reales, viven fuera
del repositorio y no entran aquí ni por asomo.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.compliance.redaction.api import Redacted
from untangle.copy_catalog import api as copy_api
from untangle.evals.drivers import voice as conductor
from untangle.evals.models import Channel as EvalChannel
from untangle.evals.models import Dataset, GoldenCase
from untangle.orchestration import contracts as u12
from untangle.providers.ports import ExternalText, Transcript, WordHypothesis
from untangle.telemetry.spend.models import VoiceMode
from untangle.tenancy import api as tenancy
from untangle.tenancy import config as tenancy_config
from untangle.voice import api as voz

from ...unit.voice.dobles import con_rastro

pytestmark = pytest.mark.usefixtures("base_de_u16")

#: Medio segundo de silencio en el formato del aplicativo. Lo que importa de la
#: grabación en estas pruebas es su tamaño, no lo que suena.
GRABACION = b"\x00\x00" * 12000


def _final(texto: str) -> Transcript:
    palabras = tuple(
        WordHypothesis(text=ExternalText(p), start_s=i * 0.3, end_s=i * 0.3 + 0.2, confidence=0.95)
        for i, p in enumerate(texto.split())
    )
    return Transcript(text=ExternalText(texto), is_final=True, words=palabras)


@dataclass
class VozDoble:
    """El reconocedor y la síntesis, con guion. Cumple el puerto `CallVoice`."""

    guion: Sequence[Transcript] = ()
    dicho: list[str] = field(default_factory=list)
    bytes_oidos: int = 0

    async def _oir(self, audio: AsyncIterator[bytes]) -> AsyncIterator[Transcript]:
        async for trozo in audio:
            self.bytes_oidos += len(trozo)
        for pieza in self.guion:
            yield pieza

    def listen(
        self, tenant_id: str, audio: AsyncIterator[bytes], *, language: Locale
    ) -> AsyncIterator[Transcript]:
        del tenant_id, language
        return self._oir(audio)

    async def _decir(self, text: Redacted) -> AsyncIterator[bytes]:
        self.dicho.append(str(text))
        yield b"\x00\x01" * 240

    def speak(
        self, tenant_id: str, text: Redacted, *, mode: VoiceMode, language: Locale
    ) -> AsyncIterator[bytes]:
        del tenant_id, mode, language
        return self._decir(text)


@con_rastro
async def _sin_grafo(turn: u12.InboundTurn) -> AsyncIterator[u12.TurnEvent]:
    yield u12.FinalText(message_id="m1", text="Noted.", language=turn.language)


@pytest.fixture
def catalogo() -> None:
    copy_api.install(copy_api.load())
    tenancy_config.install(tenancy_config.load())


def _caso(clave: str = "DS-5/en/003") -> GoldenCase:
    return GoldenCase(
        case_key=clave,
        dataset=Dataset.DS_5,
        language="en",
        tenant=tenancy.available_ids()[0],
        channel=EvalChannel.VOICE,
    )


def _con_grabacion(tmp_path: Path, caso: GoldenCase, muestras: bytes = GRABACION) -> Path:
    archivo = tmp_path / f"{caso.case_key.replace('/', '-')}.pcm"
    archivo.write_bytes(muestras)
    return tmp_path


async def test_la_grabacion_entra_entera_por_el_transporte(catalogo: None, tmp_path: Path) -> None:
    """Y en trozos de 20 ms, que es como la manda el navegador.

    Empujarla de golpe mediría otra cosa: el detector de fin de habla cuenta
    silencio, y un archivo entregado en un instante no tiene silencios que contar.
    """
    caso = _caso()
    doble = VozDoble(guion=[_final("someone hit me from behind")])
    driver = conductor.VoiceDriver(
        speech=doble, handle_turn=_sin_grafo, recordings=_con_grabacion(tmp_path, caso)
    )

    await driver.run_case(caso)

    assert doble.bytes_oidos == len(GRABACION)


async def test_la_transcripcion_que_devuelve_es_la_que_salio_por_el_cable(
    catalogo: None, tmp_path: Path
) -> None:
    """Lo que se compara con el veredicto esperado tiene que ser lo que la persona
    habría oído, no lo que el servidor creyó decir."""
    caso = _caso()
    doble = VozDoble(guion=[_final("someone hit me from behind")])
    driver = conductor.VoiceDriver(
        speech=doble, handle_turn=_sin_grafo, recordings=_con_grabacion(tmp_path, caso)
    )

    transcripcion = await driver.run_case(caso)

    dicho_por_la_agente = [t.text for t in transcripcion.turns if t.speaker == "agent"]
    assert dicho_por_la_agente, "la apertura no llego a la transcripcion del caso"
    assert "transcrib" in dicho_por_la_agente[0].lower()


async def test_el_registro_dice_por_que_termino_la_llamada(catalogo: None, tmp_path: Path) -> None:
    """Sin el motivo, un reporte completo y uno que se quedó esperando se leen
    igual en el reporte por caso."""
    caso = _caso()
    doble = VozDoble()
    driver = conductor.VoiceDriver(
        speech=doble, handle_turn=_sin_grafo, recordings=_con_grabacion(tmp_path, caso)
    )

    transcripcion = await driver.run_case(caso)

    # La grabación se acaba y la persona cuelga: no es un corte.
    assert transcripcion.record["end_reason"] == voz.EndReason.HANGUP.value


async def test_el_numero_del_caso_viaja_en_la_transcripcion(catalogo: None, tmp_path: Path) -> None:
    """La guardia que lee lo dicho lo necesita para no tomar por ajeno el propio caso."""
    caso = _caso()
    driver = conductor.VoiceDriver(
        speech=VozDoble(),
        handle_turn=_sin_grafo,
        recordings=_con_grabacion(tmp_path, caso),
    )

    transcripcion = await driver.run_case(caso)

    assert caso.tenant is not None
    assert transcripcion.case_number is not None, "la llamada abrio un caso y no lo dice"
    vista = await casos.get_case_by_number(caso.tenant, transcripcion.case_number)
    assert vista is not None, "el numero entregado es el de un caso de esta aseguradora"
    assert vista.state.value == transcripcion.record["state"]


async def test_una_grabacion_que_falta_no_es_un_caso_fallido(
    catalogo: None, tmp_path: Path
) -> None:
    """**No medida y fallida no son lo mismo**, y colapsarlas contamina una métrica
    publicada con fallos de infraestructura (P5).

    Por eso levanta un error propio que nombra el archivo, en vez de devolver una
    transcripción vacía que el reporte contaría como un caso que no pasó.
    """
    caso = _caso("DS-5/en/017")
    driver = conductor.VoiceDriver(speech=VozDoble(), handle_turn=_sin_grafo, recordings=tmp_path)

    with pytest.raises(conductor.VoiceRecordingNotFoundError, match="DS-5-en-017"):
        await driver.run_case(caso)


async def test_del_audio_que_salio_se_guarda_cuanto_fue_y_no_el_audio(
    catalogo: None, tmp_path: Path
) -> None:
    """BR7.1, también aquí.

    El conductor es el sitio más tentador para guardar el audio --"solo para poder
    volver a oírlo"-- y es exactamente el campo que no existe en ninguna parte de
    esta unidad. Lo que queda de la corrida es la transcripción redactada.
    """
    caso = _caso()
    canal = conductor.RecordingChannel(samples=GRABACION)

    await canal.send_audio(b"\x00\x01" * 240)

    assert canal.audio_out == 480
    assert not hasattr(canal, "audio_guardado")
    assert all(not isinstance(cuadro, bytes) for cuadro in canal.sent)
    del caso
