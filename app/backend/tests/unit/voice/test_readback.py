"""La lectura de confirmacion de un codigo dictado (BR3.5, AC1.23.2)."""

from __future__ import annotations

import pytest

from untangle.base import Locale
from untangle.voice import readback

from .dobles import final

pytestmark = pytest.mark.usefixtures("catalogo_cargado")

IDIOMAS: tuple[Locale, ...] = ("en", "es")


@pytest.mark.parametrize("language", IDIOMAS)
def test_un_codigo_con_letra_confundible_se_lee_antes_de_anotar(language: Locale) -> None:
    """La B esta en la lista versionada de los dos idiomas."""
    assert readback.needs_readback("ABC123", language=language)


@pytest.mark.parametrize("language", IDIOMAS)
def test_un_codigo_sin_letras_confundibles_ni_dudas_no_se_lee(language: Locale) -> None:
    """Leer todo siempre convierte la confirmacion en ruido y la gente deja de
    escucharla."""
    assert not readback.needs_readback(
        "XKL789", language=language, transcript=final("XKL789", confianza=0.99)
    )


@pytest.mark.parametrize("language", IDIOMAS)
def test_la_confianza_baja_obliga_a_leer_aunque_no_haya_letra_confundible(
    language: Locale,
) -> None:
    assert readback.needs_readback(
        "XKL789", language=language, transcript=final("XKL789", confianza=0.2)
    )


def test_sin_confianza_del_proveedor_no_se_obliga_a_leer() -> None:
    """Nula significa 'no lo dijo', nunca 'salio mal'. Tratarla como duda haria
    leer de vuelta cada codigo."""
    assert not readback.needs_readback(
        "XKL789", language="en", transcript=final("XKL789", confianza=None)
    )


def test_se_lee_el_codigo_entero_y_no_el_caracter_dudoso() -> None:
    """Leer solo la letra sospechosa de una placa no ayuda a nadie a comprobarla."""
    leido = readback.build("ABC123", language="en")
    assert "alpha" in leido.spelled
    assert "bravo" in leido.spelled
    assert "charlie" in leido.spelled
    assert "one, two, three" in leido.spelled


@pytest.mark.parametrize("language", IDIOMAS)
def test_los_digitos_se_dicen_con_su_nombre(language: Locale) -> None:
    leido = readback.build("B7", language=language)
    esperado = "seven" if language == "en" else "siete"
    assert esperado in leido.spelled


@pytest.mark.parametrize("language", IDIOMAS)
def test_la_frase_sale_del_catalogo_con_el_codigo_dentro(language: Locale) -> None:
    leido = readback.build("ABC123", language=language)
    assert leido.copy_key == readback.CONFIRM
    assert leido.spelled in leido.text
    assert leido.text != leido.spelled


@pytest.mark.parametrize(
    ("respuesta", "language", "acepta"),
    [
        ("yes", "en", True),
        ("that's right", "en", True),
        ("no", "en", False),
        ("", "en", False),
        ("sí", "es", True),
        ("correcto", "es", True),
        ("no", "es", False),
    ],
)
def test_solo_un_si_explicito_confirma(respuesta: str, language: Locale, acepta: bool) -> None:
    """Es el reconocedor de U11: lo que no es un si es un no, y callar no
    confirma."""
    assert readback.accepted(respuesta, language=language) is acepta
