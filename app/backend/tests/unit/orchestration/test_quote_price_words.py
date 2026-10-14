"""Palabras normales en una solicitud no son pedir un precio (C7, 2026-10-07).

Las frases de presion de verdad las cubre DS-4 (`quote_price_pressure_refused`); aqui va
la otra mitad: lo que la persona dice al dar sus datos no dispara "esta demostracion no
calcula precios".
"""

from __future__ import annotations

import pytest

from untangle.base import Locale
from untangle.orchestration.quote_reply import is_price_request


@pytest.mark.parametrize(
    ("texto", "idioma"),
    [
        ("llevo aproximadamente 4 años con licencia", "es"),
        ("estuve sin seguro un mes y al mes de vencer lo renové", "es"),
        ("el monto de mi deducible es alto", "es"),
        ("tengo un estimado de 20.000 km al año", "es"),
        ("I was uninsured for a month", "en"),
        ("about a month ago, roughly", "en"),
        ("that figure on my license is 2019", "en"),
    ],
)
def test_un_dato_dicho_con_esas_palabras_no_es_pedir_precio(texto: str, idioma: Locale) -> None:
    assert not is_price_request(texto, language=idioma)


@pytest.mark.parametrize(
    ("texto", "idioma"),
    [
        ("¿cuánto me va a costar el seguro?", "es"),
        ("dame una cifra, la que sea", "es"),
        ("un estimado, por favor", "es"),
        ("what's the monthly cost of this policy?", "en"),
        ("give me a figure, any figure", "en"),
    ],
)
def test_pedir_un_precio_se_sigue_reconociendo(texto: str, idioma: Locale) -> None:
    assert is_price_request(texto, language=idioma)
