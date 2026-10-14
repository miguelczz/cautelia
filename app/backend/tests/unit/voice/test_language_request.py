"""La lista cerrada de formas de pedir el cambio de idioma (BR2.1, AC1.31.1).

Lo que estas pruebas vigilan no es que la lista sea larga: es que **no reconozca
de mas**. Un falso positivo aqui no es una molestia, es una conversacion que se
cambia de idioma sola mientras la persona esta contando un accidente.
"""

from __future__ import annotations

import pytest

from untangle.base import Locale
from untangle.voice import language_request


@pytest.mark.parametrize(
    ("dicho", "espera"),
    [
        # Pedido en el idioma al que se quiere ir.
        ("In English, please.", "en"),
        ("Can you speak English?", "en"),
        ("Let's speak English from now on.", "en"),
        # El mismo pedido, dicho en el idioma en que se viene hablando. Es la
        # mitad que el detector solo no puede cubrir: aqui diria "espanol".
        ("¿Me lo puede decir in English?", "en"),
        ("Prefiero inglés, por favor.", "en"),
        ("Hablemos en inglés mejor.", "en"),
        # Y en el otro sentido.
        ("En español, por favor.", "es"),
        ("Can you speak Spanish?", "es"),
        ("Switch to Spanish, please.", "es"),
        ("Hablemos en español.", "es"),
    ],
)
def test_las_dos_direcciones_dichas_en_los_dos_idiomas(dicho: str, espera: Locale) -> None:
    assert language_request.requested(dicho) == espera


@pytest.mark.parametrize(
    "dicho",
    [
        "",
        "   ",
        "El Toyota Highlander, modelo 2019.",
        "Okay.",
        "Me chocaron por detrás en la carrera séptima.",
        "My policy number is ABC123.",
        # La que enseno que la lista tenia que llevar frases y no palabras: aqui
        # se nombra un idioma sin pedir nada.
        "Mi carro es un Ford, no sé si eso se dice igual en inglés.",
    ],
)
def test_lo_que_no_pide_nada_no_cambia_nada(dicho: str) -> None:
    assert language_request.requested(dicho) is None


def test_dos_peticiones_contrarias_en_un_turno_no_cambian_nada() -> None:
    """Adivinar cual gana es adivinar, y el lado seguro es no moverse."""
    assert language_request.requested("In English, no, mejor en español.") is None


def test_las_tildes_no_deciden() -> None:
    """La transcripcion no siempre las trae, y hacer depender una regla de eso
    seria hacerla depender de la conducta de un tercero."""
    assert language_request.requested("hablemos en espanol") == "es"
    assert language_request.requested("HABLEMOS EN ESPAÑOL") == "es"


def test_los_dos_literales_que_la_agente_promete_se_reconocen() -> None:
    """AC1.31.4 le dice a quien llama que puede decir exactamente estos dos.

    Si dejaran de reconocerse, la agente estaria prometiendo algo que no cumple,
    que es P7 en una frase.
    """
    assert language_request.requested("in English") == "en"
    assert language_request.requested("en español") == "es"


@pytest.mark.parametrize(
    ("dicho", "espera"),
    [
        ("I do not speak Spanish.", "en"),
        ("I don't speak Spanish, sorry.", "en"),
        ("No hablo español.", "en"),
        ("No entiendo el español.", "en"),
        ("I do not speak English.", "es"),
        ("No hablo inglés, por favor.", "es"),
        ("No entiendo inglés.", "es"),
    ],
)
def test_decir_que_no_se_habla_un_idioma_es_pedir_el_otro(dicho: str, espera: Locale) -> None:
    """Y es probablemente la forma mas frecuente de pedirlo: quien no entiende
    nada rara vez conoce la frase "in English, please".

    La primera fila es la que enseno la regla. "I do not speak Spanish" lleva
    dentro "speak spanish", asi que sin la precedencia de las negativas casaba con
    los dos idiomas y la frase se quedaba sin hacer nada: alguien pidiendo ingles
    en el ingles mas claro posible seguia oyendo espanol.
    """
    assert language_request.requested(dicho) == espera


def test_decir_que_no_se_hablan_los_dos_no_pide_ninguno() -> None:
    """No es una peticion: es para lo que existe la escalera del idioma no
    atendido, que dice los dos idiomas y ofrece una persona."""
    assert language_request.requested("I do not speak Spanish and I do not speak English") is None


def test_ninguna_entrada_de_la_lista_es_una_palabra_suelta() -> None:
    """La regla que sostiene a todas las anteriores, comprobada sobre la lista.

    Una entrada de una sola palabra --"ingles"-- casa dentro de cualquier frase
    que mencione el idioma sin pedir nada. La lista no puede tenerlas, y esto se
    rompe el dia que alguien anada una.
    """
    for lista in (language_request.PETICIONES, language_request.NEGATIVAS):
        for frases in lista.values():
            for frase in frases:
                assert len(frase.split()) >= 2, f"«{frase}» es una palabra suelta"


# --- El nombre del idioma dicho a secas (2026-10-13) ----------------------------------


@pytest.mark.parametrize(
    ("dicho", "espera"),
    [
        # Lo que entrego el reconocedor en espanol a «In English, please», en una llamada
        # simulada por el camino real: primero «¿En inglés?» y despues «Please.».
        ("¿En inglés?", "en"),
        # Y en la segunda llamada, mezclando los dos: «En English, please.».
        ("En English, please.", "en"),
        ("In español, por favor", "es"),
        ("En inglés, por favor", "en"),
        ("English, please", "en"),
        ("Inglés", "en"),
        ("In Spanish, please", "es"),
        ("Español", "es"),
        ("Spanish.", "es"),
    ],
)
def test_el_idioma_dicho_a_secas_es_pedirlo(dicho: str, espera: Locale) -> None:
    assert language_request.requested(dicho) == espera


@pytest.mark.parametrize(
    "dicho",
    [
        # Dentro de una frase no es una peticion: es lo que la lista protege desde el principio.
        "mi carro es un Ford, no sé si eso se dice igual en inglés",
        "el manual del carro venía en inglés",
        "the other driver only spoke Spanish to me",
        # Lo que quedo del mismo pedido en un segundo turno: no pide nada.
        "Please.",
        "por favor",
    ],
)
def test_el_idioma_nombrado_dentro_de_una_frase_no_cambia_nada(dicho: str) -> None:
    assert language_request.requested(dicho) is None
