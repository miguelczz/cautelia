"""Lo que se manda a sintetizar: los codigos dichos como se dictan (2026-10-11)."""

from __future__ import annotations

from pathlib import Path

import pytest

from untangle.base import Locale
from untangle.voice import speakable

pytestmark = pytest.mark.usefixtures("catalogo_cargado")


@pytest.mark.parametrize(
    ("language", "escrito", "suena"),
    [
        ("es", "POL-23", "póliza dos tres"),
        ("en", "POL-23", "policy two three"),
        ("es", "AP-29", "a pe, dos nueve"),
        ("en", "AP-29", "A P, two nine"),
        ("es", "SA-1", "ese a, uno"),
        ("es", "AC-123456", "a ce, uno dos tres, cuatro cinco seis"),
        ("es", "ABC123", "a be ce, uno dos tres"),
        ("en", "ABC123", "A B C, one two three"),
        # Las otras formas de placa que reconoce U11, por tramos de letras y de digitos.
        ("es", "ABC12D", "a be ce, uno dos, de"),
        ("en", "ABC1234", "A B C, one two three four"),
        ("es", "1ABC234", "uno, a be ce, dos tres cuatro"),
    ],
)
def test_los_codigos_se_dicen_como_se_dictan(language: Locale, escrito: str, suena: str) -> None:
    """Los ejemplos de la auditoria (V17), uno por uno, en los dos idiomas."""
    assert speakable.for_speech(escrito, language=language) == suena


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize(
    "texto",
    [
        "El vehículo es de 2015.",
        "Tu carro es un modelo 2015 y cuesta 20000.",
        "Llámame al 305 555 0147.",
        "Part D addresses this in 2024.",
        "Nada que cambiar aquí.",
        # Cinco digitos o un prefijo pegado no son una placa ni un numero de caso.
        "ABC12345",
        "pre-ABC123",
        "AP-029",
        "AP-1234567",
        "ZNX-9706",
        "SA-PAP-2026-D.LIMIT",
    ],
)
def test_un_ano_y_lo_que_no_es_un_codigo_se_quedan_como_estan(language: Locale, texto: str) -> None:
    """Un ano se queda como numero: el sintetizador lo lee bien como ano, y partirlo en
    digitos lo dejaria irreconocible. Solo la forma de un codigo lo reescribe."""
    assert speakable.for_speech(texto, language=language) == texto


def test_en_una_frase_solo_cambia_el_codigo() -> None:
    texto = "Encontré tu póliza POL-23; el vehículo es de 2015, placa ABC123."
    assert speakable.for_speech(texto, language="es") == (
        "Encontré tu póliza dos tres; el vehículo es de 2015, placa a be ce, uno dos tres."
    )


@pytest.mark.parametrize(
    ("language", "antes"),
    [
        ("es", "Tu póliza"),
        ("es", "Tu número de póliza:"),
        ("es", "Tu póliza es"),
        ("es", "La póliza de Marcus es"),
        ("en", "Your policy"),
        ("en", "Policy:"),
        ("en", "Your policy is"),
    ],
)
def test_la_palabra_poliza_no_se_dice_dos_veces(language: Locale, antes: str) -> None:
    """Si la frase ya dice "póliza", el prefijo del numero se queda mudo."""
    dicho = speakable.for_speech(f"{antes} POL-23.", language=language)

    palabra = "póliza" if language == "es" else "policy"
    assert dicho.lower().count(palabra) == 1, dicho
    assert "POL" not in dicho


def test_el_numero_de_caso_no_dice_poliza() -> None:
    """Solo el prefijo POL es de poliza; el de una aseguradora se deletrea."""
    assert "póliza" not in speakable.for_speech("Caso AC-29", language="es")


def test_el_texto_sin_codigos_no_se_toca_en_absoluto() -> None:
    """La misma cadena, no una copia reescrita: el motor devuelve el `Redacted` que
    entro cuando no hay nada que cambiar."""
    texto = "¿Hubo alguien herido?"
    assert speakable.for_speech(texto, language="es") is texto


def test_el_texto_solo_se_sintetiza_en_un_punto() -> None:
    """V17: la reescritura vive en un solo sitio porque el sintetizador se llama desde un
    solo sitio. Si alguien llama `speak(` desde otro, ese camino vuelve a decir "POL guion
    dos cero cero..." y esta prueba lo nombra."""
    raiz = Path(__file__).resolve().parents[3] / "src" / "untangle" / "voice"
    llamadas = [
        f"{archivo.name}:{numero}"
        for archivo in sorted(raiz.glob("*.py"))
        for numero, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), start=1)
        if ".speak(" in linea and not linea.strip().startswith("#")
    ]

    assert llamadas == [f"loop.py:{llamadas[0].split(':')[1]}"], llamadas
