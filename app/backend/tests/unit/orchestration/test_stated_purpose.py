"""Cuando una primera frase todavia no dice a que viene (2026-10-13).

El vocabulario vive en el nucleo porque lo usan la llamada y el respaldo por reglas del chat.
Estas pruebas fijan la frontera de la funcion y, sobre todo, que **los dos canales leen lo
mismo**: si uno de los dos volviera a llevar su propia lista, una frase vaga se atenderia en
uno y se abriria como reporte en el otro.
"""

from __future__ import annotations

import pytest

from untangle.base import Locale
from untangle.chat import case_opening
from untangle.orchestration.stated_purpose import says_nothing_about_purpose
from untangle.voice.first_turn import CallPurpose, purpose_of

VAGAS: list[tuple[str, Locale]] = [
    ("Quería consultar sobre", "es"),
    ("Hola, quería consultar sobre algo", "es"),
    ("Buenas tardes, tengo una pregunta", "es"),
    ("Tengo una duda", "es"),
    ("Necesito ayuda", "es"),
    ("Quisiera hacer una consulta", "es"),
    ("Hola, necesito información", "es"),
    ("I have a question", "en"),
    ("Hi, I wanted to ask about something", "en"),
    ("I need some help", "en"),
    ("I'd like to ask a quick question", "en"),
    ("Can you help me?", "en"),
]

CON_CONTENIDO: list[tuple[str, Locale]] = [
    ("Quería consultar sobre un choque", "es"),
    ("Tengo una pregunta sobre un accidente que tuve ayer", "es"),
    ("Necesito reportar un accidente", "es"),
    ("Necesito ayuda, me chocaron", "es"),
    ("Quiero hablar con un ajustador", "es"),
    ("Tengo una pregunta sobre mi póliza", "es"),
    ("I have a question about my claim", "en"),
    ("I need help, I was rear-ended", "en"),
    ("I have a question about my policy", "en"),
]


@pytest.mark.parametrize(("texto", "idioma"), VAGAS)
def test_anunciar_que_se_quiere_consultar_algo_no_dice_a_que_viene(
    texto: str, idioma: Locale
) -> None:
    assert says_nothing_about_purpose(texto, language=idioma)


@pytest.mark.parametrize(("texto", "idioma"), CON_CONTENIDO)
def test_una_palabra_de_contenido_basta_para_que_ya_no_sea_vaga(texto: str, idioma: Locale) -> None:
    assert not says_nothing_about_purpose(texto, language=idioma)


@pytest.mark.parametrize(
    ("texto", "idioma"),
    [
        ("", "es"),
        ("   ", "en"),
        # Un saludo a secas no anuncia nada: cada canal tiene su regla para el saludo.
        ("hola buenas tardes", "es"),
        ("hello there", "en"),
        # Nueve palabras es el tope: mas que eso ya esta contando algo.
        ("hola buenas tardes queria preguntar si tal vez algo de una cosa mas", "es"),
    ],
)
def test_lo_que_no_anuncia_nada_o_es_demasiado_largo_no_es_vago(texto: str, idioma: Locale) -> None:
    assert not says_nothing_about_purpose(texto, language=idioma)


def test_el_idioma_decide_el_vocabulario() -> None:
    """«Tengo una pregunta» es un anuncio en espanol y, leida como ingles, no dice nada de eso."""
    assert says_nothing_about_purpose("tengo una pregunta", language="es")
    assert not says_nothing_about_purpose("tengo una pregunta", language="en")


@pytest.mark.parametrize(("texto", "idioma"), VAGAS + CON_CONTENIDO)
def test_la_llamada_y_el_chat_leen_lo_mismo(texto: str, idioma: Locale) -> None:
    """Lo que la llamada deja sin decidir (`NOT_STATED`) es lo que el chat no abre como caso.

    Las frases de arriba no son un saludo suelto ni nombran la poliza como tema, que son las
    dos cosas en las que cada canal tiene su propia regla: en el resto tienen que coincidir.
    """
    de_la_llamada = (
        purpose_of(texto, language=idioma, quote_enabled=False) is CallPurpose.NOT_STATED
    )
    del_chat = case_opening.has_not_said_what_for(texto, language=idioma)

    assert del_chat == de_la_llamada
