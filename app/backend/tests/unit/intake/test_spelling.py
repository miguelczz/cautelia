"""BR2.5, TECH-U11.3: la tabla de deletreo, y que leer y reconocer sean el inverso exacto."""

from __future__ import annotations

import pytest

from untangle.base import Locale
from untangle.orchestration.nodes.intake import normalization, spelling


@pytest.mark.parametrize("language", ["es", "en"])
def test_deletrea_cada_letra_con_su_palabra_de_desambiguacion(language: Locale) -> None:
    leido = spelling.spell_for_readback("B", language=language)
    tabla = spelling.load()
    letra = tabla.letters["B"]
    assert letra.name[language] in leido
    assert letra.disambiguation[language] in leido


def test_los_digitos_se_leen_por_su_nombre_sin_palabra_de_desambiguacion() -> None:
    leido = spelling.spell_for_readback("6", language="es")
    assert leido == "seis"


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("code", ["BD6", "AB123", "XYZ"])
def test_deletrear_y_luego_reconocer_da_el_mismo_codigo(language: Locale, code: str) -> None:
    """El deletreo de BR2.5 y el reconocimiento de BR2.4 son el inverso exacto."""
    leido = spelling.spell_for_readback(code, language=language)
    reconocido = normalization.decode_spelled_code(leido, language=language)
    assert reconocido == code
