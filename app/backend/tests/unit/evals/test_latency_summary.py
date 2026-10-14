"""El resumen de la latencia de un canal: percentiles por rango mas proximo, por idioma.

Lo que importa aqui no es que la aritmetica sea correcta en el caso feliz sino los dos bordes
que hacen que una cifra mienta: el p95 de pocos turnos (que es el peor turno) y el promedio
de los dos idiomas (que esconde que uno va peor).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from untangle.evals.latency_summary import (
    MIN_TURNS_PER_LANGUAGE,
    ChannelLatency,
    LatencySummary,
    channel_latency,
    summarize,
)
from untangle.evals.models import ChatTurnLatency


def _turnos(idioma: str, tiempos: list[int]) -> list[ChatTurnLatency]:
    return [ChatTurnLatency(language=idioma, first_word_ms=t) for t in tiempos]  # type: ignore[arg-type]


# --- Los percentiles: por rango mas proximo, sin interpolar -----------------------------


def test_los_percentiles_son_tiempos_que_un_turno_de_verdad_tardo() -> None:
    # Cien turnos de 10 a 1000 ms: el p50 es el 50.o y el p95 el 95.o, sin valores entre dos.
    resumen = summarize(range(10, 1010, 10))

    assert (resumen.turns, resumen.p50_ms, resumen.p95_ms) == (100, 500, 950)


def test_el_orden_de_llegada_no_cambia_el_resumen() -> None:
    desordenados = [900, 100, 500, 300, 700]

    assert summarize(desordenados) == summarize(sorted(desordenados))
    assert summarize(desordenados).p50_ms == 500


def test_el_p95_de_veinte_turnos_deja_uno_por_encima_y_el_de_diecinueve_es_el_maximo() -> None:
    """El borde que fija `MIN_TURNS_PER_LANGUAGE`: por debajo de 20 el «p95» es el peor turno."""
    veinte = summarize(range(1, 21))
    diecinueve = summarize(range(1, 20))

    assert veinte.p95_ms == 19, "el 19 de 20: el peor turno (20) queda fuera"
    assert diecinueve.p95_ms == 19, "con 19 turnos el p95 coincide con el maximo"
    assert MIN_TURNS_PER_LANGUAGE == 20


def test_un_solo_turno_es_su_propio_p50_y_p95() -> None:
    assert summarize([1234]) == LatencySummary(turns=1, p50_ms=1234, p95_ms=1234)


def test_sin_turnos_no_hay_percentiles_y_no_un_cero() -> None:
    resumen = summarize([])

    assert (resumen.turns, resumen.p50_ms, resumen.p95_ms) == (0, None, None)
    assert resumen.publishable is False


@pytest.mark.parametrize(
    ("turnos", "publicable"),
    [(MIN_TURNS_PER_LANGUAGE - 1, False), (MIN_TURNS_PER_LANGUAGE, True)],
)
def test_solo_se_publica_desde_el_minimo_de_turnos(turnos: int, publicable: bool) -> None:
    assert summarize([800] * turnos).publishable is publicable


# --- Los invariantes estan en el tipo ---------------------------------------------------


@pytest.mark.parametrize(
    "campos",
    [
        {"turns": 5},
        {"turns": 5, "p50_ms": 100},
        {"turns": 0, "p50_ms": 100, "p95_ms": 200},
        {"turns": 5, "p50_ms": 900, "p95_ms": 100},
        {"turns": 5, "p50_ms": -1, "p95_ms": 100},
    ],
    ids=["turnos-sin-percentiles", "solo-p50", "percentil-sin-turnos", "p50-mayor", "negativo"],
)
def test_un_resumen_incoherente_no_se_puede_construir(campos: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        LatencySummary(**campos)


# --- Por idioma, nunca combinado --------------------------------------------------------


def test_los_turnos_se_separan_por_el_idioma_en_que_se_atendieron() -> None:
    turnos = _turnos("es", [100] * 25) + _turnos("en", [900] * 22) + _turnos("es", [300] * 5)

    canal = channel_latency(turns=turnos, datasets=["DS-2"])

    assert canal.es.turns == 30
    assert canal.en.turns == 22
    assert canal.en.p50_ms == 900
    assert canal.es.p95_ms == 300, "los cinco turnos lentos del español no pasan al ingles"


def test_el_tipo_no_tiene_donde_escribir_un_promedio_de_los_dos_idiomas() -> None:
    assert set(ChannelLatency.model_fields) == {"datasets", "es", "en"}


def test_los_conjuntos_salen_ordenados_y_sin_repetir() -> None:
    canal = channel_latency(turns=[], datasets=["DS-6", "DS-2", "DS-6", "DS-4"])

    assert canal.datasets == ("DS-2", "DS-4", "DS-6")
    assert (canal.es.turns, canal.en.turns) == (0, 0)
