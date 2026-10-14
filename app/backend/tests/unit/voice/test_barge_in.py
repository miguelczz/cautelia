"""Interrumpir a la agente, y lo que no es una interrupcion (BR4.1)."""

from __future__ import annotations

import pytest

from untangle.base import Locale
from untangle.voice import barge_in

from .dobles import VACIO, final

pytestmark = pytest.mark.usefixtures("catalogo_cargado")

IDIOMAS: tuple[Locale, ...] = ("en", "es")


def test_nada_no_interrumpe() -> None:
    assert not barge_in.interrupts(None)
    assert not barge_in.interrupts(VACIO)


def test_dos_palabras_interrumpen() -> None:
    assert barge_in.interrupts(final("no wait"))


def test_una_silaba_suelta_no_interrumpe() -> None:
    """El ruido de un carro se transcribe a veces asi, y una agente que se calla
    con cada bache es peor que una que no se calla nunca (AC1.24.3)."""
    assert not barge_in.interrupts(final("uh", confianza=0.3))


def test_una_palabra_clara_si_interrumpe() -> None:
    """Quien dice 'no' claro esta interrumpiendo; pedirle dos palabras la
    obligaria a repetirse."""
    assert barge_in.interrupts(final("no", confianza=0.95))


def test_una_palabra_sin_confianza_no_interrumpe_sola() -> None:
    """Sin confianza no hay senal clara, y el piso existe para eso."""
    assert not barge_in.interrupts(final("no", confianza=None))


def test_el_piso_de_palabras_es_configurable() -> None:
    assert barge_in.interrupts(final("no wait stop", confianza=0.3), min_words=3)
    assert not barge_in.interrupts(final("no wait", confianza=0.3), min_words=3)


def test_mira_la_mejor_palabra_y_no_la_peor() -> None:
    """Es la diferencia con la escalera de 'no le entendi', que mira la peor:
    aquella busca si se puede dar por bueno lo que se oyo entero, y esta busca
    una senal clara de que alguien hablo."""
    claro = final("no", confianza=0.99)
    dudoso = final("mmm", confianza=0.1)
    mezcla = type(claro)(text=claro.text, is_final=True, words=(*dudoso.words, *claro.words))
    assert barge_in.interrupts(mezcla)


@pytest.mark.parametrize("language", IDIOMAS)
def test_la_frase_de_ceder_el_turno_sale_del_catalogo(language: Locale) -> None:
    frase = barge_in.acknowledgement(language=language)
    assert frase.strip()
    esperado = "go ahead" if language == "en" else "dime"
    assert esperado in frase.lower()


# --- Un saludo no es una interrupcion (2026-10-11) -----------------------------


@pytest.mark.parametrize(
    "dicho",
    [
        "aló", "¿Aló?", "alo alo", "hola", "Hola, buenas tardes", "buenas", "Hola Catalina",
        "sí", "si, claro", "hello", "Hello?", "hi", "yes", "ok", "okay, yes",
    ],
)  # fmt: skip
def test_un_saludo_o_una_muletilla_sola_se_reconoce(dicho: str) -> None:
    """Quien contesta el telefono con "alo" no esta interrumpiendo: comprueba que
    hay alguien. Las listas son las que ya existian --saludos del chat y el si de la
    lectura de confirmacion--, mas las pocas palabras de contacto que ninguna traia."""
    assert barge_in.is_greeting(dicho, language="es")
    assert barge_in.is_greeting(dicho, language="en")


@pytest.mark.parametrize(
    "dicho",
    [
        "tuve un choque",
        "hola, tuve un choque",
        "quiero una cotización",
        "alo, quiero una cotizacion",
        "yes I had an accident",
        "no",
        "no, espera",
        "gracias",
        "adiós",
        "¿cuánto falta?",
        "wait I need to correct something",
        "",
    ],
)
def test_lo_que_tiene_contenido_no_es_un_saludo(dicho: str) -> None:
    """El saludo con una palabra de contenido pegada, el "no" y las despedidas sociales
    si interrumpen: sin este limite la apertura se tragaria lo que la persona de verdad
    quiere decir."""
    assert not barge_in.is_greeting(dicho, language="es")


def test_un_saludo_largo_deja_de_ser_un_saludo() -> None:
    """Seis palabras es el tope, igual que en el chat: por encima ya hay una frase."""
    assert barge_in.is_greeting("hola hola hola hola hola hola", language="es")
    assert not barge_in.is_greeting("hola hola hola hola hola hola hola", language="es")
