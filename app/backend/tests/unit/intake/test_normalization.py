"""BR2.4, TECH-U11.2: reglas versionadas, en codigo, aplicadas despues del modelo."""

from __future__ import annotations

from datetime import date

import pytest

from untangle.base import Locale
from untangle.orchestration.nodes.intake import normalization

HOY = date(2026, 9, 27)


# --- El ejemplo del plan: "be de seis" -> "BD6" ------------------------------


def test_be_de_seis_decodifica_a_bd6() -> None:
    """El ejemplo exacto de `u11-tanda-1.md`: los separadores dictados pegados al codigo."""
    assert normalization.decode_spelled_code("be de seis", language="es") == "BD6"


def test_la_palabra_de_desambiguacion_no_se_confunde_con_la_letra_siguiente() -> None:
    """ "be de burro" es solo la letra B: "de" aqui es el conector, no la letra D."""
    assert normalization.decode_spelled_code("be de burro", language="es") == "B"


def test_ingles_reconoce_el_conector_as_in() -> None:
    assert normalization.decode_spelled_code("bee as in bravo", language="en") == "B"


def test_un_codigo_ya_compacto_se_reconoce_letra_por_letra() -> None:
    assert normalization.decode_spelled_code("b d 6", language="es") == "BD6"


def test_una_palabra_ajena_a_la_tabla_se_descarta_sin_romper_el_codigo() -> None:
    """ "mi placa es be de burro uno dos tres" descarta "mi", "placa" y "es"."""
    resultado = normalization.decode_spelled_code(
        "mi placa es be de burro uno dos tres", language="es"
    )
    assert resultado == "B123"


# --- Poliza, placa, cedula y telefono ----------------------------------------


def test_normaliza_poliza_dictada_letra_por_letra() -> None:
    dictado = "pe o ele guion cuatro ocho cero nueve uno cinco"
    assert normalization.normalize_policy_number(dictado, language="es") == "POL-480915"


def test_normaliza_poliza_ya_escrita() -> None:
    assert normalization.normalize_policy_number("POL-480915", language="es") == "POL-480915"


def test_poliza_incompleta_no_normaliza() -> None:
    """BR1.6: un numero incompleto no se completa adivinando -- ni aqui ni en `identity.py`."""
    assert normalization.normalize_policy_number("POL-4809", language="es") is None


@pytest.mark.parametrize(
    ("dictado", "esperado"),
    [
        ("a be ce uno dos tres", "ABC123"),
        ("a be ce uno dos de", "ABC12D"),
    ],
)
def test_normaliza_placa_colombiana_dictada(dictado: str, esperado: str) -> None:
    assert normalization.normalize_plate(dictado, language="es") == esperado


def test_placa_con_forma_invalida_no_normaliza() -> None:
    assert normalization.normalize_plate("uno dos tres", language="es") is None


def test_normaliza_cedula_con_puntos() -> None:
    assert normalization.normalize_national_id("43.218.907", language="es") == "43218907"


def test_normaliza_telefono_con_separadores() -> None:
    assert normalization.normalize_phone("300 123 4567", language="es") == "3001234567"


# --- Fechas relativas ---------------------------------------------------------


@pytest.mark.parametrize(
    ("language", "dicho", "desplazamiento"),
    [
        ("es", "ayer", -1),
        ("es", "anteayer", -2),
        ("es", "hoy", 0),
        ("en", "yesterday", -1),
        ("en", "today", 0),
    ],
)
def test_fecha_relativa_resuelve_contra_el_reloj_del_turno(
    language: Locale, dicho: str, desplazamiento: int
) -> None:
    from datetime import timedelta

    resultado = normalization.normalize_relative_date(dicho, language=language, now=HOY)
    assert resultado == HOY + timedelta(days=desplazamiento)


def test_hace_n_dias_se_resuelve_por_el_numero_dicho() -> None:
    from datetime import timedelta

    resultado = normalization.normalize_relative_date(
        "hace 3 dias tuve el accidente", language="es", now=HOY
    )
    assert resultado == HOY - timedelta(days=3)


def test_una_fecha_sin_forma_relativa_no_normaliza() -> None:
    assert normalization.normalize_relative_date("el martes pasado", language="es", now=HOY) is None


def test_dos_corridas_del_mismo_texto_dan_la_misma_fecha() -> None:
    """FD-U11-2: si normalizara el modelo, dos corridas podrian discrepar. Aqui no pueden."""
    primera = normalization.normalize_relative_date("ayer", language="es", now=HOY)
    segunda = normalization.normalize_relative_date("ayer", language="es", now=HOY)
    assert primera == segunda
