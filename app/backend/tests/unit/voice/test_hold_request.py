"""Pedir que la agente espere: "un momento", "hold on" (2026-10-11)."""

from __future__ import annotations

import pytest

from untangle.voice import hold_request, silence


@pytest.mark.parametrize(
    "dicho",
    [
        "un momento",
        "Un momento, por favor.",
        "espera",
        "Espera un segundo",
        "dame un segundo",
        "ya lo busco",
        "ok, ya la encuentro",
        "hold on",
        "One moment.",
        "give me a second",
        "just a sec",
        "Wait, one second please",
        "sí, un momento",
        "hold on a second",
        "hang on a moment",
        "Give me a moment, please.",
        "dame un momentito",
        "espera un momento",
    ],
)
def test_los_pedidos_de_espera_se_reconocen_en_los_dos_idiomas(dicho: str) -> None:
    """Las ocho formas que pidio la auditoria y sus variantes naturales. Se miran los
    dos idiomas a la vez: una frase corta llega con el idioma que la llamada ya tenia."""
    assert hold_request.requested(dicho)


@pytest.mark.parametrize(
    "dicho",
    [
        "tuve un choque",
        # Una correccion no es una pausa: tratarla como pausa la tiraria entera.
        "espera, no, mi placa es ABC123",
        "un momento, tuve un choque ayer",
        "wait I need to correct something",
        "el momento del choque fue anoche",
        "no",
        "",
        "mi póliza es POL-200341",
        # Los verbos de cortesia solos no piden nada: hace falta una frase de la lista.
        "dame el número de caso",
        "give me the number",
        "just",
    ],
)
def test_lo_que_trae_contenido_no_es_un_pedido_de_espera(dicho: str) -> None:
    """Basta una palabra con contenido para que el turno sea del grafo, como siempre."""
    assert not hold_request.requested(dicho)


def test_la_espera_larga_es_mas_larga_que_la_de_siempre() -> None:
    """La cifra es un dato con nombre (`silence.HOLD_TOLERANCE`), no un literal suelto, y
    solo tiene sentido si supera a la tolerancia de partida."""
    assert silence.HOLD_TOLERANCE > silence.DEFAULT_TOLERANCE
    assert silence.HOLD_TOLERANCE.total_seconds() == 30
