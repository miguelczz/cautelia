"""Las marcas de latencia de la llamada: lo que dicen y lo que no (2026-10-12)."""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from untangle import observability
from untangle.voice import latency

AHORA = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)


@pytest.fixture
def traza() -> Iterator[io.StringIO]:
    salida = io.StringIO()
    observability.set_stream(salida)
    yield salida
    observability.set_stream(sys.stdout)


def _eventos(salida: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(linea) for linea in salida.getvalue().splitlines() if linea.strip()]


def test_el_primer_audio_lleva_las_dos_medidas_y_conserva_la_de_siempre(
    traza: io.StringIO,
) -> None:
    """`elapsed_ms` es la definicion de la meta y no cambia; la otra se agrega al lado."""
    medida = latency.first_audio(
        tenant_id="t",
        call_id="c",
        turn_id="c-t1",
        speech_end_at=AHORA,
        at=AHORA + timedelta(milliseconds=900),
        last_audible_word_at=AHORA - timedelta(milliseconds=600),
    )

    assert (medida.elapsed_ms, medida.from_last_word_ms) == (900, 1500)
    (evento,) = _eventos(traza)
    assert evento["elapsed_ms"] == 900
    assert evento["elapsed_from_last_word_ms"] == 1500
    assert evento["after_filler"] is False


def test_sin_ultima_palabra_la_segunda_medida_es_nula_y_no_inventada(
    traza: io.StringIO,
) -> None:
    medida = latency.first_audio(
        tenant_id="t", call_id="c", turn_id="c-t1", speech_end_at=AHORA, at=AHORA
    )

    assert medida.from_last_word_ms is None
    assert _eventos(traza)[0]["elapsed_from_last_word_ms"] is None


def test_la_marca_dice_si_hubo_muletilla_antes(traza: io.StringIO) -> None:
    latency.first_audio(
        tenant_id="t", call_id="c", turn_id="c-t1", speech_end_at=AHORA, at=AHORA, filler_said=True
    )
    assert _eventos(traza)[0]["after_filler"] is True


def test_la_muletilla_deja_su_evento_sin_texto(traza: io.StringIO) -> None:
    latency.filler_said(
        tenant_id="t",
        call_id="c",
        turn_id="c-t1",
        speech_end_at=AHORA,
        at=AHORA + timedelta(milliseconds=1050),
    )

    (evento,) = _eventos(traza)
    assert evento["event"] == latency.FILLER_SAID == "voice.filler_said"
    assert evento["turn_id"] == "c-t1"
    assert evento["elapsed_ms"] == 1050
    assert set(evento) == {"event", "tenant_id", "call_id", "turn_id", "at", "elapsed_ms"}


def test_la_lectura_adelantada_deja_su_evento_con_recuentos_y_milisegundos_sin_texto(
    traza: io.StringIO,
) -> None:
    latency.early_understanding(
        tenant_id="t",
        call_id="c",
        turn_id="c-t1",
        outcome="used",
        words=9,
        ran_ms=1800,
        finished=True,
        understood=True,
        waited_ms=300,
        saved_ms=1500,
    )

    (evento,) = _eventos(traza)
    assert evento["event"] == latency.EARLY_UNDERSTANDING == "voice.early_understanding"
    assert (evento["outcome"], evento["saved_ms"], evento["waited_ms"]) == ("used", 1500, 300)
    assert evento["cause"] is None and evento["error_type"] is None
    assert "text" not in evento, "es ADR-013: ni el texto ni nada que lo diga"


def test_el_cambio_de_idioma_dice_de_donde_a_donde_y_por_que_sin_texto(
    traza: io.StringIO,
) -> None:
    latency.language_switched(tenant_id="t", call_id="c", frm="es", to="en", reason="requested")

    (evento,) = _eventos(traza)
    assert evento["event"] == latency.LANGUAGE_SWITCHED == "voice.language_switched"
    assert set(evento) == {"event", "tenant_id", "call_id", "from", "to", "reason"}
    assert (evento["from"], evento["to"], evento["reason"]) == ("es", "en", "requested")


def test_la_reapertura_del_reconocedor_dice_el_idioma_y_nada_mas(traza: io.StringIO) -> None:
    latency.listening_reopened(tenant_id="t", call_id="c", language="en")

    (evento,) = _eventos(traza)
    assert evento["event"] == latency.LISTENING_REOPENED == "voice.listening_reopened"
    assert set(evento) == {"event", "tenant_id", "call_id", "language"}


def test_un_detector_que_falla_deja_el_tipo_del_error_y_no_su_mensaje(
    traza: io.StringIO,
) -> None:
    latency.language_detection_failed(tenant_id="t", call_id="c", error_type="RuntimeError")

    (evento,) = _eventos(traza)
    assert evento["error_type"] == "RuntimeError"
    assert set(evento) == {"event", "tenant_id", "call_id", "error_type"}


def test_las_senales_de_voz_sin_palabras_dejan_su_evento_con_recuentos_y_sin_texto(
    traza: io.StringIO,
) -> None:
    latency.speech_signal_discarded(
        tenant_id="t", call_id="c", turn_id="c-t2", signals=3, held_ms=1500
    )

    (evento,) = _eventos(traza)
    assert evento["event"] == latency.SPEECH_SIGNAL_DISCARDED == "voice.speech_signal_discarded"
    assert set(evento) == {"event", "tenant_id", "call_id", "turn_id", "signals", "held_ms"}
    assert (evento["signals"], evento["held_ms"]) == (3, 1500)
