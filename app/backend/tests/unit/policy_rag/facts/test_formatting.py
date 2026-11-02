"""Montos y fechas con el formato de la pestana de polizas (`Intl` en `es-CO` y `en-US`)."""

from __future__ import annotations

from datetime import date

import pytest

from untangle.base import Locale
from untangle.policy_rag.facts import formatting


@pytest.mark.parametrize(
    ("unidades", "idioma", "esperado"),
    [
        # Los textos que produce `Intl.NumberFormat(..., {currency: "COP"})` en la pestana.
        (1500, "es", "$\xa01.500.000"),
        (1500, "en", "COP\xa01,500,000"),
        (250, "es", "$\xa0250.000"),
        (250, "en", "COP\xa0250,000"),
        (0, "es", "$\xa00"),
    ],
)
def test_el_monto_escrito_es_el_de_la_pestana(unidades: int, idioma: Locale, esperado: str) -> None:
    assert formatting.format_pesos(unidades, idioma) == esperado


def test_el_corpus_guarda_miles_de_pesos() -> None:
    assert formatting.to_pesos(100000) == 100_000_000


@pytest.mark.parametrize(
    ("idioma", "esperado"),
    [("es", "1.500.000 pesos"), ("en", "1,500,000 Colombian pesos")],
)
def test_el_monto_hablado_lleva_la_palabra_y_no_el_simbolo(idioma: Locale, esperado: str) -> None:
    hablado = formatting.format_pesos(1500, idioma, spoken=True)
    assert hablado == esperado
    assert "$" not in hablado
    assert "COP" not in hablado


@pytest.mark.parametrize(
    ("dia", "idioma", "esperado"),
    [
        (date(2026, 6, 14), "es", "14 de junio de 2026"),
        (date(2026, 6, 14), "en", "June 14, 2026"),
        (date(2027, 3, 1), "es", "1 de marzo de 2027"),
        (date(2027, 12, 31), "en", "December 31, 2027"),
    ],
)
def test_la_fecha_larga_es_la_de_la_pestana(dia: date, idioma: Locale, esperado: str) -> None:
    assert formatting.format_date(dia, idioma) == esperado
