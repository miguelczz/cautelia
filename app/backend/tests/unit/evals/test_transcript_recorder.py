"""El grabador de transcripciones: lo que la agente dijo, redactado y con las senales del codigo.

Aqui no se usa un doble de la redaccion a proposito: `Redacted` no se puede fabricar fuera
del modulo de redaccion (`redaction:constructor` vigila tambien las pruebas), y lo que se
protege es justo que nada sin tapar llegue al archivo, que un doble no demostraria.
Sin modelo de lenguaje, sin base de datos y sin red; el detector de datos personales es
local.
"""

from __future__ import annotations

import io
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from untangle import observability, paths
from untangle.base import Locale
from untangle.compliance.controls.models import GuardCategory
from untangle.compliance.redaction import detector as deteccion
from untangle.evals import compliance_fixtures as fx
from untangle.evals.models import Channel, Dataset, GoldenCase
from untangle.evals.runner import api
from untangle.evals.transcript_recorder import (
    LONG_TURN_WORDS,
    TranscriptRecorder,
    question_count,
    word_count,
)
from untangle.evals.transcripts import NotSaved, load_transcripts, write_transcripts

RAIZ = paths.repo_root()
MOMENTO = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)

#: Lo que dice la persona y la agente, con los datos que la redaccion tiene que tapar.
DATOS_DE_LA_PERSONA = (
    "Me llamo Natalia Henao Rendón, mi teléfono es 3005551234 y la placa es ABC123."
)
DATOS_DE_LA_AGENTE = "Encontré la póliza POL-100042 a nombre de Natalia Henao Rendón. ¿Eres tú?"
DATOS = ("3005551234", "ABC123", "POL-100042", "Natalia", "Henao")


@pytest.fixture(autouse=True)
def _eventos_aparte() -> Iterator[io.StringIO]:
    """Los eventos tecnicos no van a la consola de la prueba, y se pueden leer."""
    salida = io.StringIO()
    observability.set_stream(salida)
    yield salida
    observability.set_stream(sys.stdout)


def _caso(*, language: Locale = "es", seq: str = "prueba") -> GoldenCase:
    return GoldenCase(
        case_key=f"DS-2/{language}/{seq}",
        dataset=Dataset.DS_2,
        language=language,
        tenant="stonecroft",
        channel=Channel.CHAT,
    )


def _agente(texto: str) -> api.Turn:
    return api.Turn(speaker="agent", text=texto)


def _persona(texto: str) -> api.Turn:
    return api.Turn(speaker="insured", text=texto)


def _transcripcion(caso: GoldenCase, *turnos: api.Turn) -> api.CaseTranscript:
    return api.CaseTranscript(case_key=caso.case_key, turns=turnos)


def _frase_que_la_guardia_detiene(idioma: Locale) -> str:
    escena = fx.load_scene(RAIZ)
    for fila in fx.load_fixtures(idioma, RAIZ).guard:
        if fila.expected_category is GuardCategory.COVERAGE_PROMISE:
            return fx.fill(fila.text, escena.markers())
    msg = f"las frases de prueba de '{idioma}' no traen ninguna de cobertura"
    raise AssertionError(msg)


def _grabar(*conversaciones: tuple[GoldenCase, api.CaseTranscript]) -> TranscriptRecorder:
    grabador = TranscriptRecorder()
    for caso, transcripcion in conversaciones:
        grabador.record(caso, transcripcion, RAIZ)
    return grabador


# --- Nada sin redactar llega al archivo -----------------------------------------


def test_nada_sin_tapar_llega_al_archivo(tmp_path: Path) -> None:
    caso = _caso()
    grabador = _grabar(
        (
            caso,
            _transcripcion(
                caso,
                _agente("Hola, soy la asistente de IA de la demostración."),
                _persona(DATOS_DE_LA_PERSONA),
                _agente(DATOS_DE_LA_AGENTE),
            ),
        )
    )

    destino = write_transcripts(
        grabador.to_file(run_id="run-x", commit_sha="abc", recorded_at=MOMENTO), tmp_path
    )

    crudo = destino.read_text(encoding="utf-8")
    for dato in DATOS:
        assert dato not in crudo, f"'{dato}' llego al archivo sin tapar"
    # Y no es que se haya borrado todo: lo que no es un dato sigue ahi.
    assert "asistente de IA" in crudo


def test_si_la_redaccion_falla_la_conversacion_no_se_guarda_y_la_corrida_sigue(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _eventos_aparte: io.StringIO
) -> None:
    """Fallar cerrado: sin redaccion no sale texto, y una corrida que cuesta dinero no muere."""

    def _romper(*_: object, **__: object) -> None:
        msg = "el detector esta roto a proposito"
        raise deteccion.DetectionError(msg)

    monkeypatch.setattr(deteccion.Detector, "detect", _romper)
    caso = _caso()
    grabador = TranscriptRecorder()

    grabador.record(
        caso,
        _transcripcion(caso, _agente("Hola."), _persona(DATOS_DE_LA_PERSONA)),
        RAIZ,
    )

    archivo = grabador.to_file(run_id="run-x", commit_sha="abc", recorded_at=MOMENTO)
    assert archivo.conversations == ()
    assert archivo.not_saved == (NotSaved(case_key=caso.case_key, reason="redaction_failed"),)
    # El evento dice cual no se guardo y por que, y nada de lo dicho.
    crudo = write_transcripts(archivo, tmp_path).read_text(encoding="utf-8")
    eventos = _eventos_aparte.getvalue()
    for dato in DATOS:
        assert dato not in crudo
        assert dato not in eventos
    assert "evals.transcript_not_saved" in eventos


def test_un_fallo_inesperado_del_grabador_no_levanta_y_se_anota() -> None:
    caso = _caso()

    def _romper(text: str, fallback: Locale) -> Locale:
        msg = "el detector de idioma esta roto a proposito"
        raise RuntimeError(msg)

    grabador = TranscriptRecorder(language_of=_romper)

    grabador.record(caso, _transcripcion(caso, _agente("Hola.")), RAIZ)

    archivo = grabador.to_file(run_id="run-x", commit_sha="abc", recorded_at=MOMENTO)
    assert archivo.conversations == ()
    assert archivo.not_saved == (NotSaved(case_key=caso.case_key, reason="recording_failed"),)


# --- Las senales del codigo ------------------------------------------------------


def test_las_senales_del_codigo_marcan_cada_turno_dudoso_y_dejan_limpio_el_resto() -> None:
    caso = _caso()
    larga = " ".join(["palabra"] * (LONG_TURN_WORDS + 1)) + "."
    grabador = _grabar(
        (
            caso,
            _transcripcion(
                caso,
                _agente("Hola, soy la asistente de IA de la demostración."),  # 0: apertura
                _persona("Choqué y estoy asustada."),  # 1
                _agente("Lamento lo ocurrido. ¿Cuál es su nombre? ¿Y su póliza?"),  # 2
                _persona("Natalia."),  # 3
                _agente(larga),  # 4
                _persona("Sí."),  # 5
                _agente("Estimado cliente, gracias."),  # 6
                _persona("Ok."),  # 7
                _agente(_frase_que_la_guardia_detiene("es")),  # 8
                _persona("Bien."),  # 9
                _agente("Gracias. ¿Hubo heridos?"),  # 10
            ),
        )
    )

    turnos = (
        grabador.to_file(run_id="run-x", commit_sha="abc", recorded_at=MOMENTO)
        .conversations[0]
        .turns
    )
    senales = {t.index: t.signals for t in turnos}

    assert senales[0] == ()
    # El turno que viene detras de un mensaje con miedo, y que ademas pregunta dos veces.
    assert "several_questions" in senales[2]
    assert "after_emotion:fear_or_crying" in senales[2]
    # La emocion es de la ultima frase de la persona: la siguiente ya no la hereda.
    assert not any(s.startswith("after_emotion") for s in senales[4])
    assert senales[4] == ("long_turn",)
    assert senales[6] == ("register:IR-2",)
    assert senales[8] == (f"guard:{GuardCategory.COVERAGE_PROMISE.value}",)
    assert senales[10] == ()
    # Las del asegurado no llevan senales: no se juzgan.
    assert all(t.signals == () for t in turnos if t.speaker == "insured")


def test_la_apertura_se_marca_y_solo_la_primera_frase_de_la_agente() -> None:
    caso = _caso()
    grabador = _grabar(
        (
            caso,
            _transcripcion(
                caso,
                _agente("Hola, soy la asistente de IA de la demostración."),
                _persona("Choqué."),
                _agente("Gracias. ¿Hubo heridos?"),
            ),
        )
    )

    turnos = (
        grabador.to_file(run_id="run-x", commit_sha="abc", recorded_at=MOMENTO)
        .conversations[0]
        .turns
    )

    assert [t.opening for t in turnos] == [True, False, False]


def test_si_las_senales_no_se_pueden_leer_la_conversacion_se_guarda_y_lo_declara() -> None:
    """La corrida costo dinero: se guarda, y la cola sabra que no la puede estratificar."""
    caso = _caso()

    def _sin_senales(**_: object) -> dict[int, tuple[str, ...]]:
        msg = "la configuracion no se pudo leer"
        raise OSError(msg)

    grabador = TranscriptRecorder(read_signals=_sin_senales)
    grabador.record(caso, _transcripcion(caso, _agente("Hola."), _persona("Choque.")), RAIZ)

    conversacion = grabador.to_file(
        run_id="run-x", commit_sha="abc", recorded_at=MOMENTO
    ).conversations[0]
    assert conversacion.signals_read is False
    assert len(conversacion.turns) == 2


# --- El idioma del turno ---------------------------------------------------------


def test_el_idioma_de_un_turno_es_el_de_su_texto_y_no_el_del_caso() -> None:
    """RT-10: una conversacion que empieza en espanol y sigue en ingles tiene turnos en los dos."""
    caso = _caso(language="es")
    grabador = _grabar(
        (
            caso,
            _transcripcion(
                caso,
                _agente("Hola, soy la asistente de IA de la demostración. ¿Qué pasó?"),
                _persona("Chocaron mi carro ayer por la tarde en la autopista."),
                _agente("Lo lamento mucho. ¿Hubo alguien herido en el choque?"),
                _persona("Sorry, can you answer me in English? The other driver left."),
                _agente("Of course, I can help you in English. Was anyone hurt in the accident?"),
            ),
        )
    )

    turnos = (
        grabador.to_file(run_id="run-x", commit_sha="abc", recorded_at=MOMENTO)
        .conversations[0]
        .turns
    )

    assert [t.language for t in turnos] == ["es", "es", "es", "en", "en"]


def test_un_turno_sin_senal_de_idioma_conserva_el_del_turno_anterior() -> None:
    caso = _caso(language="en")
    grabador = _grabar(
        (caso, _transcripcion(caso, _agente("Ok."), _persona("Yes."), _agente("Thanks.")))
    )

    turnos = (
        grabador.to_file(run_id="run-x", commit_sha="abc", recorded_at=MOMENTO)
        .conversations[0]
        .turns
    )

    assert {t.language for t in turnos} == {"en"}


# --- La forma del archivo ---------------------------------------------------------


def test_el_archivo_sale_en_orden_estable_por_caso() -> None:
    uno, otro = _caso(seq="b"), _caso(language="en", seq="a")
    grabador = _grabar(
        (uno, _transcripcion(uno, _agente("Hola."))),
        (otro, _transcripcion(otro, _agente("Hello."))),
    )

    archivo = grabador.to_file(run_id="run-x", commit_sha="abc", recorded_at=MOMENTO)

    assert [c.case_key for c in archivo.conversations] == ["DS-2/en/a", "DS-2/es/b"]


def test_un_caso_sin_turnos_no_deja_una_conversacion_vacia() -> None:
    caso = _caso()
    grabador = _grabar((caso, _transcripcion(caso)))

    assert grabador.is_empty


def test_grabar_dos_veces_el_mismo_caso_deja_la_ultima() -> None:
    """Un reintento del corredor no duplica la conversacion."""
    caso = _caso()
    grabador = _grabar(
        (caso, _transcripcion(caso, _agente("Primera."))),
        (caso, _transcripcion(caso, _agente("Segunda."))),
    )

    archivo = grabador.to_file(run_id="run-x", commit_sha="abc", recorded_at=MOMENTO)

    assert len(archivo.conversations) == 1
    assert archivo.conversations[0].turns[0].text == "Segunda."


def test_los_conteos_de_preguntas_y_palabras() -> None:
    assert question_count("¿Cómo se llama? ¿Y su póliza?") == 2
    assert question_count("Gracias.") == 0
    assert word_count("una dos  tres\ncuatro") == 4


# --- Guardar la corrida -------------------------------------------------------------------


def test_una_corrida_sin_conversaciones_no_deja_archivo(tmp_path: Path) -> None:
    """Un archivo vacio se leeria como "hubo conversaciones y no dijeron nada"."""
    assert (
        TranscriptRecorder().save(run_id="run-x", commit_sha="abc", now=MOMENTO, directory=tmp_path)
        is None
    )
    assert list(tmp_path.iterdir()) == []


def test_guardar_deja_el_archivo_de_la_corrida_y_se_lee_de_vuelta(tmp_path: Path) -> None:
    caso = _caso()
    grabador = _grabar(
        (caso, _transcripcion(caso, _agente("Hola."), _persona(DATOS_DE_LA_PERSONA)))
    )

    destino = grabador.save(run_id="run-x", commit_sha="abc", now=MOMENTO, directory=tmp_path)

    assert destino == tmp_path / "run-x.json"
    leida = load_transcripts(destino)
    assert leida.run_id == "run-x"
    assert [c.case_key for c in leida.conversations] == [caso.case_key]
