"""Lo que la persona dice de paso, reconocido sin modelo (decision de Miguel, 2026-10-06)."""

from __future__ import annotations

import pytest

from untangle.orchestration.nodes.intake import social
from untangle.orchestration.nodes.intake.social import SocialIntent

# --- Que senal trae el turno -------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "idioma", "senal"),
    [
        ("Hola", "es", SocialIntent.GREETING),
        ("Buenas tardes, Catalina", "es", SocialIntent.GREETING),
        ("Muchas gracias", "es", SocialIntent.THANKS),
        ("Hasta luego", "es", SocialIntent.GOODBYE),
        ("¿Cuánto falta?", "es", SocialIntent.PROGRESS),
        ("Hi there", "en", SocialIntent.GREETING),
        ("Thank you!", "en", SocialIntent.THANKS),
        ("Bye for now", "en", SocialIntent.GOODBYE),
        ("What else do you need?", "en", SocialIntent.PROGRESS),
    ],
)
def test_reconoce_cada_senal_en_los_dos_idiomas(
    texto: str, idioma: str, senal: SocialIntent
) -> None:
    assert social.detect(texto, language=idioma) is senal  # type: ignore[arg-type]


def test_un_relato_no_trae_ninguna_senal() -> None:
    """La prueba que aisla lo que importa: un turno con datos no es social."""
    assert social.detect("Me chocaron por detrás en la autopista.", language="es") is None
    assert social.detect("A truck hit me from behind at a light.", language="en") is None


def test_el_limite_de_palabra_evita_falsos_saludos() -> None:
    # "holanda" no es "hola", "hilo" no es "hi".
    assert social.detect("Vengo de Holanda.", language="es") is None
    assert social.detect("The thread was a hilo.", language="en") is None


def test_con_varias_senales_manda_la_despedida_y_luego_el_avance() -> None:
    assert social.detect("Gracias, hasta luego", language="es") is SocialIntent.GOODBYE
    assert social.detect("Hola, ¿cuánto falta?", language="es") is SocialIntent.PROGRESS
    assert social.detect("Hola, gracias", language="es") is SocialIntent.THANKS


# --- Si el turno trae algo mas que lo social --------------------------------


@pytest.mark.parametrize(
    ("texto", "idioma"),
    [
        ("Hola", "es"),
        ("Hola, Catalina.", "es"),
        ("Ok, gracias", "es"),
        ("Sí, gracias", "es"),
        ("¿Cuánto falta?", "es"),
        ("Thanks!", "en"),
        ("Hi, how much is left?", "en"),
    ],
)
def test_un_turno_solo_social_no_tiene_nada_que_extraer(texto: str, idioma: str) -> None:
    assert social.is_only_social(texto, language=idioma)  # type: ignore[arg-type]


def test_un_saludo_con_datos_si_tiene_que_extraer() -> None:
    texto = "Hola, soy Marcus Reed y mi póliza es la POL-01."
    assert social.detect(texto, language="es") is SocialIntent.GREETING
    assert not social.is_only_social(texto, language="es")
    assert "marcus" in social.leftover_words(texto, language="es")


def test_lo_que_no_es_social_nunca_es_solo_social() -> None:
    assert not social.is_only_social("Fue el jueves.", language="es")


# --- En el otro idioma: la conversacion no cambia de idioma por un turno corto --


def test_lo_social_se_reconoce_aunque_venga_en_el_otro_idioma() -> None:
    """BR2.2: "gracias" no mueve el idioma de una conversacion en ingles, asi que
    llega con `language="en"`; igual tiene que ser un agradecimiento. Visto en
    produccion con Sunmeadow el 2026-10-06."""
    assert social.detect("Gracias", language="en") is SocialIntent.THANKS
    assert social.is_only_social("Gracias", language="en")
    assert social.detect("Thanks!", language="es") is SocialIntent.THANKS
    assert social.detect("Hola", language="en") is SocialIntent.GREETING
    assert social.detect("Hasta luego", language="en") is SocialIntent.GOODBYE
