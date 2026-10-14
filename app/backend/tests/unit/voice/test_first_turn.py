"""A que llama la persona, por lo primero que dice (2026-10-11)."""

from __future__ import annotations

import pytest

from untangle.voice.first_turn import CallPurpose, purpose_of


@pytest.mark.parametrize(
    ("dicho", "idioma"),
    [
        # De una llamada real: se atendia como reporte y se preguntaba por heridos.
        ("No, la verdad quiero hablarte referente a mi póliza.", "es"),
        ("Tengo una duda sobre mi póliza.", "es"),
        ("¿Mi póliza cubre el robo de una llanta?", "es"),
        ("Quiero saber qué cubre mi seguro.", "es"),
        ("I have a question about my policy.", "en"),
        ("Does my policy cover a rental car?", "en"),
    ],
)
def test_una_duda_de_la_poliza_no_es_un_reporte(dicho: str, idioma: str) -> None:
    assert purpose_of(dicho, language=idioma, quote_enabled=False) is CallPurpose.POLICY_QUESTION  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("dicho", "idioma"),
    [
        ("Iba por la autopista sur cuando una moto se me atravesó.", "es"),
        ("Tuve un choque esta mañana.", "es"),
        # Dar el numero de la poliza no es preguntar por ella.
        ("Soy Natalia Henao y mi póliza es POL-100042.", "es"),
        ("I was rear-ended on the highway.", "en"),
    ],
)
def test_lo_que_no_pregunta_por_la_poliza_es_un_reporte(dicho: str, idioma: str) -> None:
    assert purpose_of(dicho, language=idioma, quote_enabled=True) is CallPurpose.CLAIM  # type: ignore[arg-type]


def test_cotizar_solo_cuenta_donde_la_aseguradora_cotiza() -> None:
    """Donde no cotiza, el grafo ya tiene su frase: aqui no se desvia."""
    pide = "Quiero cotizar un seguro para mi carro."

    assert purpose_of(pide, language="es", quote_enabled=True) is CallPurpose.QUOTE
    assert purpose_of(pide, language="es", quote_enabled=False) is not CallPurpose.QUOTE


# --- Una primera frase que no dice a que viene no decide nada (2026-10-13) -------------


@pytest.mark.parametrize(
    ("dicho", "idioma"),
    [
        # La llamada real: «queria consultar sobre...» seguia como el reporte de un accidente.
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
    ],
)
def test_anunciar_que_se_quiere_consultar_algo_no_dice_a_que_viene(dicho: str, idioma: str) -> None:
    assert purpose_of(dicho, language=idioma, quote_enabled=True) is CallPurpose.NOT_STATED  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("dicho", "idioma", "esperado"),
    [
        # Una sola palabra de contenido y ya dice a que viene: sigue por donde iba.
        ("Quería consultar sobre un choque", "es", CallPurpose.CLAIM),
        ("Tengo una pregunta sobre un accidente que tuve ayer", "es", CallPurpose.CLAIM),
        ("Necesito reportar un accidente", "es", CallPurpose.CLAIM),
        ("Necesito ayuda, me chocaron", "es", CallPurpose.CLAIM),
        ("Quiero hablar con un ajustador", "es", CallPurpose.CLAIM),
        ("I have a question about my claim", "en", CallPurpose.CLAIM),
        ("I need help, I was rear-ended", "en", CallPurpose.CLAIM),
        # Y la poliza y la cotizacion se siguen reconociendo antes que lo vago.
        ("Tengo una pregunta sobre mi póliza", "es", CallPurpose.POLICY_QUESTION),
        ("I have a question about my policy", "en", CallPurpose.POLICY_QUESTION),
    ],
)
def test_una_palabra_de_contenido_basta_para_que_ya_no_sea_vaga(
    dicho: str, idioma: str, esperado: CallPurpose
) -> None:
    assert purpose_of(dicho, language=idioma, quote_enabled=True) is esperado  # type: ignore[arg-type]


def test_pedir_cotizar_se_reconoce_antes_que_lo_vago() -> None:
    assert purpose_of("Quiero cotizar", language="es", quote_enabled=True) is CallPurpose.QUOTE


def test_una_frase_larga_no_es_vaga_aunque_cada_palabra_sea_de_relleno() -> None:
    """Nueve palabras es el tope: mas que eso ya esta contando algo."""
    larga = "hola buenas tardes queria preguntar si tal vez algo de una cosa mas"

    assert purpose_of(larga, language="es", quote_enabled=False) is CallPurpose.CLAIM


def test_un_saludo_a_secas_no_es_vago_porque_no_anuncia_nada() -> None:
    """«Hola, buenas» no pide nada: la regla de las tres palabras de la llamada ya lo deja
    pasar, y esta funcion no lo toma por un anuncio."""
    assert purpose_of("hola buenas tardes", language="es", quote_enabled=False) is CallPurpose.CLAIM
