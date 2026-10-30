"""Cuando nace una solicitud de cotizacion y donde no (U19, BR1.5, AC6.1.1, AC6.1.3).

Pedir cotizar abre una solicitud **solo donde la aseguradora la tiene activa**. Es un dato de
su configuracion y no una rama por aseguradora, asi que las pruebas cambian solo ese dato.
"""

from __future__ import annotations

import pytest

from untangle.base import Locale
from untangle.chat import case_opening, opening
from untangle.orchestration.nodes.intake import identity
from untangle.tenancy import config as tenancy_config


@pytest.fixture(autouse=True)
def _estado_limpio() -> None:
    tenancy_config.reset()


@pytest.mark.parametrize(
    ("idioma", "texto"),
    [
        ("es", "quiero una cotización"),
        ("es", "necesito cotizar mi carro"),
        ("en", "I'd like a quote"),
        ("en", "can you quote my car?"),
    ],
)
def test_pedir_cotizar_abre_una_solicitud_donde_esta_activa(idioma: Locale, texto: str) -> None:
    assert (
        case_opening.intent_of(texto, language=idioma, quote_enabled=True)
        is identity.ReportIntent.QUOTE_REQUEST
    )


@pytest.mark.parametrize(
    ("idioma", "texto"),
    [("es", "quiero una cotización"), ("en", "I'd like a quote")],
)
def test_pedir_cotizar_donde_esta_apagada_no_abre_una_solicitud(idioma: Locale, texto: str) -> None:
    """El caso se abre como siniestro, y el turno responde con la frase de AC6.1.3."""
    assert (
        case_opening.intent_of(texto, language=idioma, quote_enabled=False)
        is identity.ReportIntent.CLAIM
    )


def test_por_omision_la_cotizacion_esta_apagada() -> None:
    """Un llamador que no dice nada no enciende una capacidad que nadie configuro."""
    assert case_opening.intent_of("I'd like a quote", language="en") is identity.ReportIntent.CLAIM


@pytest.mark.parametrize(
    ("idioma", "texto", "esperado"),
    [
        ("es", "¿mi póliza cubre el parabrisas?", identity.ReportIntent.COVERAGE_INQUIRY),
        ("es", "me chocaron en la autopista", identity.ReportIntent.CLAIM),
        ("en", "does my policy cover hail?", identity.ReportIntent.COVERAGE_INQUIRY),
        ("en", "someone hit my car", identity.ReportIntent.CLAIM),
    ],
)
def test_encender_la_cotizacion_no_cambia_los_otros_dos_tipos(
    idioma: Locale, texto: str, esperado: identity.ReportIntent
) -> None:
    assert case_opening.intent_of(texto, language=idioma, quote_enabled=True) is esperado


def test_la_intencion_de_cotizar_tiene_su_tipo_de_registro() -> None:
    from untangle.case_record.models import RecordType

    assert identity._RECORD_TYPE_OF[identity.ReportIntent.QUOTE_REQUEST] is RecordType.QUOTE_REQUEST
    assert set(identity._RECORD_TYPE_OF) == set(identity.ReportIntent)


def test_solo_sunmeadow_tiene_la_cotizacion_activa_y_su_apertura_la_ofrece() -> None:
    """AC6.1.2 y AC6.1.3: la apertura la ofrece donde esta activa y no la menciona donde no."""
    aseguradoras = {t.tenant_id: t for t in tenancy_config.loaded().available}

    assert {k for k, t in aseguradoras.items() if t.quote_enabled} == {"sunmeadow"}
    for tenant_id, config in aseguradoras.items():
        for idioma in ("es", "en"):
            texto = opening.compose(config, language=idioma).text
            ofrece = "cotización" in texto or "quote" in texto
            assert ofrece is (tenant_id == "sunmeadow"), (tenant_id, idioma, texto)


def test_la_configuracion_de_cada_aseguradora_se_lee_de_su_carpeta() -> None:
    assert case_opening._quote_enabled("sunmeadow") is True
    assert case_opening._quote_enabled("stonecroft") is False
    assert case_opening._quote_enabled("knotwell") is False
    assert case_opening._quote_enabled("no-existe") is False


# --- El saludo suelto no abre caso (2026-10-07) --------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "hola",
        "Hola!",
        "Buenas tardes",
        "hola, ¿cómo estás?",
        "Hola Catalina",
        "buenos días",
        "Hi there",
        "hello",
        "Good morning!",
    ],
)
def test_un_saludo_sin_pedido_es_solo_un_saludo(texto: str) -> None:
    assert case_opening.is_greeting_only(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "hola, tuve un choque",
        "Hola, ¿mi póliza cubre el granizo?",
        "buenas, quiero cotizar",
        "hi, someone hit my car",
        "POL-11",
        "",
        "   ",
        # Todas las palabras parecen de saludo, pero ya no es un saludo suelto.
        "hola hola hola hola hola hola hola",
    ],
)
def test_lo_que_dice_algo_no_es_un_saludo(texto: str) -> None:
    assert not case_opening.is_greeting_only(texto)


# --- Quien solo anuncia que quiere consultar algo tampoco abre caso (2026-10-13) --


@pytest.mark.parametrize(
    ("texto", "idioma"),
    [
        # Un saludo suelto sigue siendolo.
        ("hola", "es"),
        ("Good morning!", "en"),
        # Anunciar que se quiere consultar algo, sin decir que, tambien.
        ("Quería consultar algo", "es"),
        ("Tengo una pregunta", "es"),
        ("Hola, necesito ayuda", "es"),
        ("I have a question", "en"),
        ("Hi, I wanted to ask about something", "en"),
    ],
)
def test_el_primer_mensaje_que_no_dice_a_que_viene_no_abre_caso(texto: str, idioma: Locale) -> None:
    assert case_opening.has_not_said_what_for(texto, language=idioma)


@pytest.mark.parametrize(
    ("texto", "idioma"),
    [
        ("Tuve un choque", "es"),
        ("Quería consultar sobre un choque", "es"),
        ("Tengo una pregunta sobre mi póliza", "es"),
        ("Quiero cotizar", "es"),
        ("I have a question about my claim", "en"),
        ("I was rear-ended", "en"),
        ("", "es"),
    ],
)
def test_el_que_dice_algo_si_abre_su_caso(texto: str, idioma: Locale) -> None:
    assert not case_opening.has_not_said_what_for(texto, language=idioma)
