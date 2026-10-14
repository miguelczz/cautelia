"""La apertura del chat: la divulgacion y lo que se ofrece (BR1.1, BR1.3).

La composicion es pura, asi que estas pruebas no necesitan base. Lo que **si**
necesitan es el catalogo real cargado: comprobar la apertura contra un catalogo
falso no diria nada sobre lo que una persona lee.
"""

from __future__ import annotations

import pytest

from untangle.chat import opening
from untangle.copy_catalog import api as copy_api
from untangle.tenancy import config as tenant_config
from untangle.tenancy.models import TenantConfig

pytestmark = pytest.mark.usefixtures("catalogo_cargado")

#: Lo que AC1.1.1 exige que diga el primer mensaje, cada cosa con algo que buscar
#: en el texto. Se comprueban por separado y no con una comparacion contra una
#: frase entera: una frase entera se rompe al corregir una coma y no dice **cual**
#: falto. Desde el 2026-10-07 son cuatro y no seis: Miguel recorto la apertura y
#: quito que la conversacion se guarda y se borra cada noche (enmienda a AC1.1.1).
EXIGIDO_ES = {
    "que es una inteligencia artificial": "inteligencia artificial",
    "que es una demostracion": "demostración",
    "con polizas de ejemplo": "pólizas de ejemplo",
    "que no escriba datos reales": "datos personales reales",
}
EXIGIDO_EN = {
    "that it is an artificial intelligence": "artificial intelligence",
    "that it is a demonstration": "demonstration",
    "with example policies": "example policies",
    "that they should not write real data": "real personal data",
}


def _aseguradora(tenant_id: str) -> TenantConfig:
    return tenant_config.require(tenant_id)


# --- BR1.1: lo exigido, en los dos idiomas ------------------------------------


@pytest.mark.parametrize(("idioma", "exigido"), [("es", EXIGIDO_ES), ("en", EXIGIDO_EN)])
def test_la_apertura_dice_lo_que_el_criterio_exige(
    idioma: str, exigido: dict[str, str], aseguradoras: tuple[TenantConfig, ...]
) -> None:
    """AC1.1.1, compuerta dura. Se comprueba en las tres aseguradoras: una que
    dijera tres de las cuatro pasaria si solo se mirara una."""
    for config in aseguradoras:
        apertura = opening.compose(config, language=idioma)  # type: ignore[arg-type]
        for que, buscado in exigido.items():
            assert buscado in apertura.text, f"{config.tenant_id} ({idioma}) no dice {que}"


def test_la_apertura_es_el_texto_de_miguel(aseguradoras: tuple[TenantConfig, ...]) -> None:
    """La frase aprobada se copia literal (decision de Miguel del 2026-10-07)."""
    poblado = next(c for c in aseguradoras if c.quote_enabled)

    assert opening.compose(poblado, language="es").text == (
        f"Hola, soy {poblado.agent_name}, la asistente de inteligencia artificial de "
        f"{poblado.display_name}. "
        "Esto es una demostración con pólizas de ejemplo, así que no escribas datos personales "
        "reales. Puedo ayudarte a reportar un siniestro, a resolver dudas sobre tu póliza o "
        "darte una cotización."
    )


def test_la_apertura_nombra_a_la_agente_y_a_su_aseguradora(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    """Quien habla y de quien es. Cada aseguradora tiene su agente (2026-10-11) y el
    nombre sale de su carpeta, no del codigo."""
    for config in aseguradoras:
        apertura = opening.compose(config, language="es")
        assert config.agent_name is not None
        assert config.agent_name in apertura.text
        assert config.display_name in apertura.text


def test_cada_aseguradora_tiene_una_agente_distinta(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    """Decision de Miguel del 2026-10-11: no en todas atiende la misma."""
    nombres = [config.agent_name for config in aseguradoras]

    assert None not in nombres
    assert len(set(nombres)) == len(nombres)


def test_sin_nombre_propio_la_agente_es_la_del_catalogo(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    sin_nombre = aseguradoras[0].model_copy(update={"agent_name": None})

    apertura = opening.compose(sin_nombre, language="es")

    assert copy_api.t(opening.AGENT_NAME, locale="es") in apertura.text


def test_la_apertura_no_deja_ninguna_variable_sin_sustituir(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    """Una llave sin sustituir es texto roto que llega a una persona, y las
    pruebas de arriba no lo verian: buscan lo que **si** esta."""
    for config in aseguradoras:
        for idioma in ("es", "en"):
            texto = opening.compose(config, language=idioma).text
            assert "{" not in texto and "}" not in texto, f"{config.tenant_id} ({idioma})"


# --- BR1.3: lo que se ofrece sale de la configuracion --------------------------


def test_las_dos_capacidades_de_siempre_estan_en_toda_aseguradora(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    for config in aseguradoras:
        texto = opening.compose(config, language="es").text
        assert "reportar un siniestro" in texto
        assert "dudas sobre tu póliza" in texto
        # Desde el 2026-10-07 no se ofrece pasar el caso a una persona en la
        # apertura: Miguel lo quito porque alarga el primer mensaje sin ayudar.
        assert "una persona" not in texto


def test_la_cotizacion_solo_se_ofrece_donde_esta_activa(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    """AC1.1.3. Las dos puntas con **la misma** aseguradora, cambiando solo el
    dato: asi lo que se comprueba es que el dato manda, y no que dos carpetas
    distintas digan cosas distintas por cualquier otra razon.
    """
    base = aseguradoras[0]
    sin_cotizacion = base.model_copy(update={"quote_enabled": False})
    con_cotizacion = base.model_copy(update={"quote_enabled": True})

    assert "cotización" not in opening.compose(sin_cotizacion, language="es").text
    assert "cotización" in opening.compose(con_cotizacion, language="es").text


def test_la_clave_que_se_registra_es_la_de_la_divulgacion(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    """Lo que U10 guarda es la clave y nunca el texto, asi que la clave viaja
    con la apertura en vez de recomponerse despues."""
    apertura = opening.compose(aseguradoras[0], language="es")

    assert apertura.copy_key == "chat.opening.disclosure"


# --- Sin caso todavia: el saludo y las opciones (decisiones del 2026-10-07) -----


@pytest.mark.parametrize(
    ("idioma", "esperado"),
    [
        ("es", "¡Hola! ¿Quieres reportar un accidente o resolver una duda sobre tu póliza?"),
        ("en", "Hi! Would you like to report an accident or ask about your policy?"),
    ],
)
def test_el_saludo_es_corto_y_ofrece_las_opciones_en_una_pregunta(
    aseguradoras: tuple[TenantConfig, ...], idioma: str, esperado: str
) -> None:
    """No repite la apertura, que ya dijo quien habla y que sabe hacer."""
    sin_cotizacion = aseguradoras[0].model_copy(update={"quote_enabled": False})
    respuesta = opening.greeting_reply(sin_cotizacion, language=idioma)  # type: ignore[arg-type]

    assert respuesta.text == esperado
    assert respuesta.copy_key == opening.GREETING


def test_el_saludo_y_las_opciones_ofrecen_cotizar_solo_donde_esta_activa(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    """Las mismas capacidades que la apertura: nunca promete lo que no hay."""
    base = aseguradoras[0]
    sin = base.model_copy(update={"quote_enabled": False})
    con = base.model_copy(update={"quote_enabled": True})

    assert "cotización" not in opening.greeting_reply(sin, language="es").text
    assert "cotización" in opening.greeting_reply(con, language="es").text
    assert "cotización" not in opening.options(sin, language="es").text
    assert "cotización" in opening.options(con, language="es").text
    assert opening.options(con, language="es").copy_key == opening.OPTIONS_WITH_QUOTE
