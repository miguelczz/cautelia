"""La apertura hablada: su texto y lo que ofrece (BR2.1 a BR2.4).

La composicion es pura, asi que estas pruebas no necesitan base. Lo que **si**
necesitan es el catalogo real: comprobar lo que una persona oye contra un
catalogo falso no diria nada.
"""

from __future__ import annotations

import pytest

from untangle.base import Locale
from untangle.compliance.redaction import api as redaccion
from untangle.tenancy.models import TenantConfig
from untangle.voice import opening

pytestmark = pytest.mark.usefixtures("catalogo_cargado")

IDIOMAS: tuple[Locale, ...] = ("en", "es")

#: Lo que AC1.22.1 exige que diga la apertura hablada, cada cosa con algo que
#: buscar. Por separado y no contra la frase entera: una frase entera se rompe al
#: corregir una coma y no dice **cual** de las cuatro falto.
#: Desde el 2026-10-07 son dos: Miguel quito la lista de capacidades y la oferta de
#: pasar a una persona, que alargaban la apertura sin decir nada necesario antes de
#: la primera pregunta. La divulgacion (BR2.1) sigue entera.
EXIGIDO_EN = {
    "que es una inteligencia artificial": "AI assistant",
    "que la llamada queda transcrita": "transcribed",
}
EXIGIDO_ES = {
    "que es una inteligencia artificial": "inteligencia artificial",
    "que la llamada queda transcrita": "queda transcrita",
}


@pytest.mark.parametrize(("language", "exigido"), [("en", EXIGIDO_EN), ("es", EXIGIDO_ES)])
def test_la_apertura_dice_las_dos_cosas_de_la_divulgacion(
    language: Locale, exigido: dict[str, str], aseguradoras: tuple[TenantConfig, ...]
) -> None:
    """Se comprueba en las tres aseguradoras: una que dijera una de las dos
    pasaria si solo se mirara una."""
    for config in aseguradoras:
        texto = opening.compose(config, language=language).text
        for que, buscado in exigido.items():
            assert buscado in texto, f"{config.tenant_id} ({language}) no dice {que}"


@pytest.mark.parametrize("language", IDIOMAS)
def test_la_apertura_termina_preguntando_en_que_puede_ayudar(
    language: Locale, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    """Abierta desde el 2026-10-11: antes preguntaba por heridos a toda llamada, y
    quien llama puede tener una duda de su poliza."""
    texto = opening.compose(aseguradoras[0], language=language).text
    assert texto.rstrip().endswith(("help you?", "ayudar?"))
    assert "herido" not in texto
    assert "injured" not in texto


@pytest.mark.parametrize("language", IDIOMAS)
def test_la_voz_no_ofrece_cotizar_aunque_la_aseguradora_lo_tenga_activo(
    language: Locale, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    """**`quote_enabled` dice que la aseguradora cotiza, no que lo haga por voz.**

    La solicitud se captura en el chat --`chat.case_opening` es quien abre un caso
    de tipo `quote_request`-- y la voz no abre ninguno. Ofrecerlo aqui seria
    prometer una capacidad que este canal no tiene (P7). El dia que la voz capture
    solicitudes, esta prueba cambia a proposito.
    """
    base = aseguradoras[0]
    palabra = "quote" if language == "en" else "cotiz"
    sin = opening.compose(base.model_copy(update={"quote_enabled": False}), language=language).text
    con = opening.compose(base.model_copy(update={"quote_enabled": True}), language=language).text

    assert palabra not in sin.lower()
    assert palabra not in con.lower()
    assert sin == con


@pytest.mark.parametrize("language", IDIOMAS)
def test_la_pregunta_sigue_siendo_lo_ultimo(
    language: Locale, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    """Si no lo fuera, la apertura terminaria ofreciendo algo en vez de
    preguntando, que no es lo que el criterio aprueba."""
    texto = opening.compose(
        aseguradoras[0].model_copy(update={"quote_enabled": True}), language=language
    ).text

    assert texto.rstrip().endswith("?")


@pytest.mark.parametrize("language", IDIOMAS)
def test_la_apertura_nombra_a_la_aseguradora_y_a_la_agente(
    language: Locale, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    for config in aseguradoras:
        assert config.display_name in opening.compose(config, language=language).text


def test_la_clave_registrada_es_la_de_la_divulgacion(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    """Lo que se registra es la clave y nunca el texto (U10)."""
    assert opening.compose(aseguradoras[0], language="en").copy_key == opening.DISCLOSURE


@pytest.mark.parametrize("language", IDIOMAS)
def test_la_apertura_de_voz_no_es_la_del_chat(
    language: Locale, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    """Un mismo texto para los dos canales obligaria a que uno de los dos dijera
    algo que su criterio no aprobo: el chat no dice que la llamada queda
    transcrita, y la voz no dice que se borra cada noche."""
    from untangle.chat import opening as chat_opening

    config = aseguradoras[0]
    de_voz = opening.compose(config, language=language).text
    de_chat = chat_opening.compose(config, language=language).text
    assert de_voz != de_chat
    assert opening.DISCLOSURE != chat_opening.DISCLOSURE


# --- La apertura no sale mutilada por la redaccion (U18) -----------------------


@pytest.mark.parametrize("language", IDIOMAS)
def test_la_apertura_sale_entera_por_el_camino_del_catalogo(
    aseguradoras: tuple[TenantConfig, ...], language: Locale
) -> None:
    """Lo que la agente dice de si misma no se toca (U18).

    La apertura es una frase que escribimos nosotros, y el camino por el que sale
    --`from_catalog`-- no le pasa el detector de datos personales. Sin esta prueba,
    devolver ese camino a `redact` no rompería nada visible en el arnés y la agente
    volvería a presentarse con una palabra tachada en medio de la frase.
    """
    for config in aseguradoras:
        compuesta = opening.compose(config, language=language)

        salida = str(redaccion.from_catalog(compuesta.text, language=language))

        assert salida == compuesta.text
        assert "[" not in salida, salida


def test_en_espanol_el_detector_si_la_mutilaba_y_por_eso_existe_el_camino(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    """La otra mitad, y la que hace que la de arriba signifique algo.

    Si el detector dejara de equivocarse con el español, esta prueba se cae y el
    camino del catálogo dejaría de estar justificado por este motivo --seguiría
    estándolo por el principio, pero el motivo medido habría cambiado y conviene
    enterarse--. Medido el 2026-09-30: siete frases del catálogo en español y
    ninguna en inglés.
    """
    config = aseguradoras[0]
    en_espanol = opening.compose(config, language="es")
    en_ingles = opening.compose(config, language="en")
    assert str(redaccion.redact(en_espanol.text, language="es")) != en_espanol.text
    # El ingles, como en el proceso servido: la raiz instala los nombres de las
    # aseguradoras y de sus agentes como publicos. Sin eso tapa "Agencia Castilla's".
    redaccion.allow_public_terms(
        [*(c.display_name for c in aseguradoras), *(c.agent_name or "" for c in aseguradoras)]
    )
    try:
        assert str(redaccion.redact(en_ingles.text, language="en")) == en_ingles.text
    finally:
        redaccion.allow_public_terms([])


@pytest.mark.parametrize("language", IDIOMAS)
def test_al_retomar_la_apertura_sigue_siendo_la_divulgacion_pero_sin_pregunta(
    language: Locale, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    """Dos preguntas seguidas --"¿en que te puedo ayudar?" y "¿seguimos con ese?"-- dejaban
    a la persona sin saber a cual contestar (2026-10-11). La divulgacion (BR2.1) va entera
    y lo que se registra es ella, no la pregunta."""
    config = aseguradoras[0]
    completa = opening.compose(config, language=language)
    al_retomar = opening.compose(config, language=language, ask_how_to_help=False)

    assert "?" not in al_retomar.text
    assert "?" in completa.text
    assert completa.text.startswith(al_retomar.text)
    assert al_retomar.copy_key == completa.copy_key
