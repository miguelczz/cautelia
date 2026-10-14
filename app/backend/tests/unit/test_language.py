"""El idioma de un turno, con frases reales (BR2.1, BR2.2, BR2.3).

Las frases son de la conversacion que este producto tiene de verdad --un aviso de
siniestro, una pregunta de cobertura-- y no lorem ipsum: un detector se comporta
distinto con texto natural que con relleno, y lo que hay que comprobar es el caso que
va a ocurrir.
"""

from __future__ import annotations

import pytest

from untangle.language import LanguageOutcome, for_turn, measured

#: Frases largas y naturales, las dos caras. Cada una se prueba **partiendo del
#: idioma contrario** a proposito: si el detector no hiciera nada y devolviera
#: siempre el idioma actual, estas pruebas lo dirian.
ESPANOL = "Me chocaron por detras en la autopista y necesito reportar el siniestro"
INGLES = "Someone hit my car from behind on the highway and I need to report it"
PORTUGUES = "Bom dia, preciso reportar um acidente com o meu carro esta manha"


# --- BR2.1: responde en el idioma del mensaje ---------------------------------


def test_un_mensaje_en_espanol_se_responde_en_espanol_aunque_la_pagina_abriera_en_ingles() -> None:
    """AC1.2.1, literal: el idioma del mensaje manda sobre el de la pagina."""
    resultado = for_turn(ESPANOL, current="en")

    assert resultado.language == "es"
    assert resultado.outcome is LanguageOutcome.DETECTED


def test_un_mensaje_en_ingles_se_responde_en_ingles_aunque_la_conversacion_fuera_en_espanol() -> (
    None
):
    resultado = for_turn(INGLES, current="es")

    assert resultado.language == "en"
    assert resultado.outcome is LanguageOutcome.DETECTED


# --- BR2.2: sin senal, no se cambia -------------------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "ok",
        "sí",
        "ABC123",
        # Un nombre propio de doce caracteres: pasaba cualquier filtro de
        # longitud y el detector le daba 0,92 a espanol. Es el caso que hizo
        # contar palabras en vez de caracteres.
        "Marcela Rios",
        "Placa ABC123",
        "  ",
        "42",
    ],
)
def test_un_mensaje_sin_senal_conserva_el_idioma_de_la_conversacion(texto: str) -> None:
    """AC1.2.3. Se prueba en las dos direcciones: un detector que devolviera
    siempre espanol pasaria la mitad de estos casos sin hacer nada."""
    assert for_turn(texto, current="en").language == "en"
    assert for_turn(texto, current="es").language == "es"
    assert for_turn(texto, current="en").outcome is LanguageOutcome.NO_SIGNAL


# --- BR2.3: un idioma que la demo no atiende ----------------------------------


def test_un_tercer_idioma_se_nombra_y_no_se_finge() -> None:
    """No se responde en portugues y no se ignora el turno: se conserva el idioma
    y quien llama sabe que tiene que decir que la demostracion atiende dos."""
    resultado = for_turn(PORTUGUES, current="es")

    assert resultado.unsupported
    assert resultado.language == "es", "la respuesta sale igual, en el idioma de la conversacion"


def test_un_tercer_idioma_no_se_confunde_con_falta_de_senal() -> None:
    """Son dos cosas distintas y llevan respuestas distintas: una calla y la otra
    dice que la demostracion atiende dos idiomas. Sin esta prueba, un detector
    que no distinguiera las dos pasaria las de arriba igual."""
    assert for_turn(PORTUGUES, current="es").outcome is LanguageOutcome.UNSUPPORTED
    assert for_turn("ok", current="es").outcome is LanguageOutcome.NO_SIGNAL


# --- El otro umbral: la metrica no adivina ------------------------------------


def test_la_medicion_devuelve_no_medido_en_vez_de_adivinar() -> None:
    """AC1.2.4. Es el otro uso y el otro umbral: aqui no hay conversacion de la
    que heredar, y contar una adivinanza como acierto contaminaria la cifra que
    el PRD publica por idioma."""
    assert measured("ok") is None
    assert measured("ABC123") is None


def test_la_medicion_si_reconoce_una_frase_de_verdad() -> None:
    """El control positivo del anterior: sin el, una medicion que devolviera
    siempre `None` pasaria la prueba de arriba y no mediria nada."""
    assert measured(ESPANOL) == "es"
    assert measured(INGLES) == "en"
