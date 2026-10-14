"""Lo que la agente dice de una cotizacion (U19, BR1.5, BR2.3, BR3.1, BR3.2).

La compuerta dura de la unidad es que **ninguna respuesta de la cotizacion lleve un importe, un
simbolo o codigo de moneda, ni un porcentaje**. No se construye un detector (FD-U19-1): la
guardia de salida ya los caza en los dos idiomas, y estas pruebas pasan **cada frase** de la
cotizacion por esa guardia, con los patrones de verdad, para que una frase con una cifra en el
catalogo haga fallar una prueba y no llegue a una conversacion.
"""

from __future__ import annotations

import ast
import itertools
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from untangle import paths
from untangle.base import Locale
from untangle.case_record.models import RecordType
from untangle.compliance.controls import patterns
from untangle.compliance.controls.guard import GuardContext, GuardTurn, evaluate
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.loading import load_raw_entries
from untangle.orchestration import quote_reply
from untangle.orchestration.nodes.intake import composition, confirmation
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.rules import eligibility
from untangle.rules.fields import RuleValue
from untangle.tenancy import config as tenancy_config

IDIOMAS: tuple[Locale, ...] = ("es", "en")


@pytest.fixture(autouse=True)
def _estado_limpio() -> Iterator[None]:
    copy_api.reset()
    patterns.reset()
    tenancy_config.reset()
    eligibility.reset()
    yield
    copy_api.reset()
    patterns.reset()
    tenancy_config.reset()
    eligibility.reset()


@pytest.fixture(scope="module")
def biblioteca() -> patterns.PatternLibrary:
    return patterns.load_library()


def _sale_igual(frase: str, idioma: Locale, biblioteca: patterns.PatternLibrary) -> bool:
    """La guardia real, con las otras aseguradoras cargadas, deja pasar la frase sin tocarla."""
    contexto = GuardContext.for_tenant(
        "sunmeadow", language=idioma, tenants=tenancy_config.loaded().available
    )
    resultado = evaluate(frase, library=biblioteca, context=contexto, turn=GuardTurn())
    return resultado.unchanged and resultado.text_out == frase


# --- BR3.1: ninguna frase de la cotizacion lleva una cifra de dinero -------------------------


def _frases_de_la_cotizacion(idioma: Locale) -> dict[str, str]:
    """Todas las del catalogo que son de la cotizacion, con sus variables rellenas."""
    prefijos = (
        "quote.",
        "rules.explain.quote_",
        "intake.question.quote_",
        "intake.readback.quote_",
        "intake.closing.summary_quote",
    )
    relleno = {
        "band": "Su riesgo entra en lo habitual.",
        "name": "Marta Diaz",
        "birth_date": "12 de abril de 1990",
        "license_years": "8",
        "license_jurisdiction": "Corvane",
        "vehicle_year": "2014",
        "vehicle_make": "Mazda",
        "vehicle_model": "Tres",
        "vin": "JM1BL1SF7A1234567",
        "salvage_title": "nunca declarado pérdida total",
        "use_type": "personal",
        "annual_mileage_band": "normal",
        "garaging_jurisdiction": "Corvane",
        "at_fault_losses_3y": "0",
        "claims_3y": "1",
        "prior_coverage_active": "con seguro vigente",
        "lapse_months": "0",
        "summary": "Marta Diaz, 8 años con licencia; Mazda Tres 2014.",
    }
    frases: dict[str, str] = {}
    for (clave, locale), entrada in load_raw_entries(paths.copy_dir()).items():
        if locale == idioma and clave.startswith(prefijos):
            frases[clave] = entrada["text"].format(**relleno)
    return frases


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_ninguna_frase_de_la_cotizacion_la_toca_la_guardia(
    idioma: Locale, biblioteca: patterns.PatternLibrary
) -> None:
    """BR3.1 [bloquea]: ni importe, ni moneda, ni porcentaje, ni nada que la guardia vigile."""
    frases = _frases_de_la_cotizacion(idioma)
    assert len(frases) >= 40, "el inventario de frases de la cotizacion no puede quedar vacio"

    tocadas = {k: f for k, f in frases.items() if not _sale_igual(f, idioma, biblioteca)}
    assert tocadas == {}, tocadas


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_una_frase_con_un_importe_si_la_toca_la_guardia(
    idioma: Locale, biblioteca: patterns.PatternLibrary
) -> None:
    """La prueba de la prueba: con una cifra dentro, el inventario de arriba se pondria rojo."""
    con_cifra = {
        "es": [
            "Su prima seria de $450 al mes.",
            "Le costaria 120 dólares al mes.",
            "El descuento es del 15%.",
            "Pagaria unos 800 USD al año.",
        ],
        "en": [
            "Your premium would be $450 a month.",
            "It would cost you 120 dollars a month.",
            "The discount is 15%.",
            "You'd pay about 800 USD a year.",
        ],
    }[idioma]

    for frase in con_cifra:
        assert not _sale_igual(frase, idioma, biblioteca), frase


# --- Ninguna razon lleva un identificador de regla ni nombra una aseguradora (BR2.3) ---------


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_ninguna_frase_nombra_una_regla_ni_una_aseguradora(idioma: Locale) -> None:
    ids = {
        regla.id for conjunto in eligibility.loaded().available.values() for regla in conjunto.rules
    }
    nombres = {t.tenant_id for t in tenancy_config.loaded().available} | {
        t.display_name.lower() for t in tenancy_config.loaded().available
    }
    for clave, frase in _frases_de_la_cotizacion(idioma).items():
        assert not re.search(r"\b[A-Z]{3}-[A-Z]-\d{2}\b", frase), (clave, frase)
        assert not any(i.lower() in frase.lower() for i in ids), (clave, frase)
        assert not any(n in frase.lower() for n in nombres), (clave, frase)


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_la_respuesta_a_la_solicitud_no_lleva_el_identificador_de_la_regla_que_decidio(
    idioma: Locale, biblioteca: patterns.PatternLibrary
) -> None:
    """Todas las salidas posibles de Sunmeadow, compuestas de verdad, sin un `SUN-Q-0x`."""
    conjunto = eligibility.require("sunmeadow")
    entradas: list[dict[str, RuleValue]] = [
        {"use_type": "commercial"},
        {"salvage_title": True},
        {"at_fault_losses_3y": 2},
        {"license_years": 0},
        {"vehicle_age_years": 30},
        {},
        {"license_years": 2},
    ]
    base: dict[str, RuleValue] = {
        "use_type": "personal",
        "salvage_title": False,
        "at_fault_losses_3y": 0,
        "license_years": 10,
        "vehicle_age_years": 5,
    }
    for cambios in entradas:
        resultado = eligibility.evaluate_eligibility(conjunto, {**base, **cambios})
        texto = quote_reply.compose_eligibility_reply(
            resultado.outcome.value,
            resultado.band.value,
            resultado.explanation_key,
            language=idioma,
        )
        assert not any(regla in texto for regla in resultado.deciding_rules), texto
        assert "SUN-Q" not in texto
        assert _sale_igual(texto, idioma, biblioteca), texto
        assert texto.strip() and "rules.explain" not in texto and "quote." not in texto


# --- Las salidas y las bandas que las frases saben decir son las del motor, en los dos sentidos ---


def test_las_frases_cubren_exactamente_las_salidas_y_las_bandas_del_motor() -> None:
    assert quote_reply.KNOWN_OUTCOMES == {k.value for k in eligibility.EligibilityOutcomeKind}
    assert quote_reply.KNOWN_BANDS == {b.value for b in eligibility.RiskBand}


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_toda_salida_y_toda_banda_tiene_su_frase(idioma: Locale) -> None:
    for salida in eligibility.EligibilityOutcomeKind:
        assert quote_reply.outcome_sentence(salida.value, language=idioma).strip()
    for banda in eligibility.RiskBand:
        assert quote_reply.band_sentence(banda.value, language=idioma).strip()


def test_una_salida_o_una_banda_que_no_existe_no_se_dice() -> None:
    with pytest.raises(ValueError, match="no tiene frase"):
        quote_reply.band_sentence("cheap", language="es")
    with pytest.raises(ValueError, match="no tiene frase"):
        quote_reply.outcome_sentence("approved", language="es")
    with pytest.raises(ValueError, match="no tiene frase"):
        quote_reply.explanation_sentence("rules.explain.quote_inventada", language="es")


def test_las_razones_que_sabe_decir_son_las_de_cada_conjunto_de_elegibilidad() -> None:
    """Una clave que el YAML nombra y la tabla no conoce saldria vacia; una que sobra es codigo muerto."""
    usadas = {
        regla.explanation_key
        for conjunto in eligibility.loaded().available.values()
        for regla in conjunto.rules
    }

    assert usadas == quote_reply.KNOWN_EXPLANATION_KEYS


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_cada_razon_existe_en_el_catalogo_en_los_dos_idiomas(idioma: Locale) -> None:
    for clave in quote_reply.KNOWN_EXPLANATION_KEYS:
        assert copy_api.t(copy_api.CopyKey(clave), locale=idioma) != clave, clave


# --- BR3.2: ante la insistencia en un precio, una frase fija, sin cifra, que ofrece la banda ------


@pytest.mark.parametrize(
    ("idioma", "texto"),
    [
        ("es", "¿cuánto me cuesta?"),
        ("es", "ya, pero dime el precio"),
        ("es", "necesito la prima mensual"),
        ("es", "cuánto voy a pagar al mes?"),
        ("es", "dame una tarifa aproximada"),
        ("en", "how much would it cost?"),
        ("en", "just give me the price"),
        ("en", "what's my monthly premium"),
        ("en", "what would I pay per month?"),
    ],
)
def test_la_insistencia_en_un_precio_recibe_la_negativa_fija(idioma: Locale, texto: str) -> None:
    respuesta = quote_reply.reply_before_capture(
        record_type=RecordType.QUOTE_REQUEST,
        anything_captured=True,
        quote_enabled=True,
        text=texto,
        language=idioma,
    )

    assert respuesta is not None
    assert respuesta.key == "quote.reply.price_refusal"
    assert respuesta.text == copy_api.t(quote_reply.PRICE_REFUSAL, locale=idioma)
    assert not re.search(r"[$€%]|\d", respuesta.text)


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_la_negativa_ofrece_la_banda_cuando_ya_se_conoce(
    idioma: Locale, biblioteca: patterns.PatternLibrary
) -> None:
    for banda in eligibility.RiskBand:
        respuesta = quote_reply.compose_price_refusal(banda.value, language=idioma)

        assert respuesta.key == "quote.reply.price_refusal_with_band"
        assert quote_reply.band_sentence(banda.value, language=idioma) in respuesta.text
        assert not re.search(r"[$€%]|\d", respuesta.text)
        assert _sale_igual(respuesta.text, idioma, biblioteca)


@pytest.mark.parametrize(
    "texto", ["vivo en Corvane", "mi auto es un Mazda 2014", "no, es de uso personal", ""]
)
def test_lo_que_no_pregunta_por_el_precio_no_recibe_la_negativa(texto: str) -> None:
    for idioma in IDIOMAS:
        assert (
            quote_reply.reply_before_capture(
                record_type=RecordType.QUOTE_REQUEST,
                anything_captured=True,
                quote_enabled=True,
                text=texto,
                language=idioma,
            )
            is None
        )


def test_la_negativa_solo_aplica_dentro_de_una_solicitud() -> None:
    """En un siniestro, «cuanto cuesta» no es una peticion de precio de cotizacion."""
    assert (
        quote_reply.reply_before_capture(
            record_type=RecordType.CLAIM,
            anything_captured=True,
            quote_enabled=True,
            text="how much will the repair cost",
            language="en",
        )
        is None
    )


# --- BR1.5: donde la cotizacion esta apagada, una respuesta util --------------------------------


@pytest.mark.parametrize(
    ("idioma", "texto"),
    [
        ("es", "quiero una cotización"),
        ("es", "necesito cotizar mi carro"),
        ("es", "quiero sacar un seguro"),
        ("en", "I'd like a quote"),
        ("en", "can you quote my car?"),
        ("en", "I want to get a policy"),
    ],
)
def test_pedir_cotizar_donde_esta_apagada_recibe_la_respuesta_y_no_se_ofrece_lo_que_no_hay(
    idioma: Locale, texto: str
) -> None:
    respuesta = quote_reply.reply_before_capture(
        record_type=RecordType.CLAIM,
        anything_captured=False,
        quote_enabled=False,
        text=texto,
        language=idioma,
    )

    assert respuesta is not None
    assert respuesta.key == "quote.reply.unavailable"
    # Dice que no cotiza y ofrece lo que si puede: reportar un accidente o una duda de poliza.
    assert re.search(r"no ofrece|doesn't offer", respuesta.text)
    assert re.search(r"reportar|report", respuesta.text)
    assert re.search(r"póliza|policy", respuesta.text)


def test_donde_esta_activa_no_se_responde_que_no_cotiza() -> None:
    assert (
        quote_reply.reply_before_capture(
            record_type=RecordType.CLAIM,
            anything_captured=False,
            quote_enabled=True,
            text="quiero una cotización",
            language="es",
        )
        is None
    )


def test_a_mitad_de_un_reporte_mencionar_una_cotizacion_no_es_pedir_cotizar() -> None:
    """«El taller me dio una cotizacion» es parte del relato de un siniestro, no una peticion."""
    for texto in ("el taller me dio una cotización", "the shop gave me a quote"):
        idioma: Locale = "es" if "taller" in texto else "en"
        assert (
            quote_reply.reply_before_capture(
                record_type=RecordType.CLAIM,
                anything_captured=True,
                quote_enabled=False,
                text=texto,
                language=idioma,
            )
            is None
        )


def test_una_consulta_de_cobertura_tampoco_se_confunde_con_pedir_cotizar() -> None:
    assert (
        quote_reply.reply_before_capture(
            record_type=RecordType.COVERAGE_INQUIRY,
            anything_captured=False,
            quote_enabled=False,
            text="quiero una cotización",
            language="es",
        )
        is None
    )


# --- BR2.5: la elegibilidad no corre en el turno ---------------------------------------------


_RAIZ_DEL_PAQUETE = paths.repo_root() / "app" / "backend" / "src"


def _archivo_de(modulo: str) -> Path | None:
    """El archivo de un modulo del paquete, o `None` si no es del aplicativo."""
    base = _RAIZ_DEL_PAQUETE.joinpath(*modulo.split("."))
    if base.with_suffix(".py").is_file():
        return base.with_suffix(".py")
    if (base / "__init__.py").is_file():
        return base / "__init__.py"
    return None


def _importados_por(modulo: str) -> set[str]:
    """Los modulos del aplicativo que ese archivo importa, directamente."""
    archivo = _archivo_de(modulo)
    if archivo is None:
        return set()
    encontrados: set[str] = set()
    for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            nombres = [alias.name for alias in nodo.names]
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            # `from a import b` importa `a` y, si `a.b` es un modulo, tambien `a.b`.
            nombres = [nodo.module, *(f"{nodo.module}.{alias.name}" for alias in nodo.names)]
        else:
            continue
        encontrados |= {n for n in nombres if n.startswith("untangle") and _archivo_de(n)}
    return encontrados


def _alcanzables_desde(modulo: str) -> set[str]:
    """Todo lo que ese modulo llega a importar, de rebote tambien."""
    vistos: set[str] = set()
    pendientes = [modulo]
    while pendientes:
        actual = pendientes.pop()
        if actual in vistos:
            continue
        vistos.add(actual)
        pendientes.extend(_importados_por(actual))
    return vistos


@pytest.mark.parametrize(
    "modulo",
    [
        "untangle.orchestration.turn",
        "untangle.orchestration.rhythm",
        "untangle.orchestration.quote_reply",
        "untangle.orchestration.case_context",
    ],
)
def test_br2_5_el_camino_del_turno_no_llega_al_motor_de_reglas_ni_de_rebote(modulo: str) -> None:
    """Analiza el arbol de importaciones: ni directo, ni por un modulo puente.

    Lo mismo que vigila el contrato `ritmo-del-turno-sin-verificacion-ni-reglas` de
    `.importlinter`, pero desde una prueba: asi tambien falla con `pytest` y no solo con `lint`.
    Se recorre con el modulo `ast` y no con un grafo de terceros, para no depender de una
    herramienta que el proyecto no declara.
    """
    alcanzados = _alcanzables_desde(modulo)

    assert any(m.startswith("untangle.orchestration") for m in alcanzados), "el recorrido no anduvo"
    del_motor = sorted(
        m for m in alcanzados if m == "untangle.rules" or m.startswith("untangle.rules.")
    )
    assert del_motor == [], f"{modulo} llega al motor de reglas por {del_motor}"


def test_el_recorrido_de_importaciones_si_ve_el_motor_cuando_un_modulo_lo_importa() -> None:
    """La prueba de la prueba: un modulo que importa `rules.eligibility` lo alcanza."""
    assert "untangle.rules.eligibility" in _alcanzables_desde("untangle.rules.api") or (
        "untangle.rules.loading" in _alcanzables_desde("untangle.rules.api")
    )
    assert any(
        m.startswith("untangle.rules")
        for m in _alcanzables_desde("untangle.orchestration.nodes.decision.node")
    )


def test_el_manejador_del_turno_responde_con_frases_fijas_y_no_evalua_la_elegibilidad() -> None:
    """El turno **lee** lo que el fondo dejo; no evalua, y no puede (BR2.5).

    **La aserción cambió el 2026-10-03, y a una más fuerte.** Antes comprobaba que
    la palabra `eligibility` no apareciera en `turn.py`. Eso era un grep sobre la
    forma de una implementación, no sobre la regla: BR2.5 prohíbe **decidir** la
    elegibilidad dentro del turno y su propio texto dice qué hacer en su lugar --"el
    turno no hace ese trabajo, lee lo que el fondo dejó en el estado o emite una
    frase de espera"--, que es justo lo que ahora hace, por un puerto, igual que el
    desvío de cobertura.

    Lo que se comprueba es que el motor de reglas no sea **alcanzable** desde el
    turno, ni directamente ni por una cadena de imports. Eso sí es la regla, y es más
    estricto que el grep: un módulo intermedio que arrastrara `rules` pasaría el
    grep y cae aquí. Se comprobó: la primera versión de este cableado importaba
    `eligibility_run` directamente y esta comprobación --y su contrato de capas-- la
    rechazaron.
    """
    fuente = (paths.repo_root() / "app/backend/src/untangle/orchestration/turn.py").read_text(
        encoding="utf-8"
    )

    assert "quote_reply.reply_before_capture" in fuente
    # El símbolo del motor no se nombra: la evaluación no se llama desde aquí.
    assert "evaluate_eligibility" not in fuente
    alcanzables = _alcanzables_desde("untangle.orchestration.turn")
    arrastrados = sorted(m for m in alcanzables if m.startswith("untangle.rules"))
    assert not arrastrados, arrastrados


# --- Los caminos de cada bloque de la solicitud usan frases del catalogo ---------------------------


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_el_cierre_de_la_solicitud_es_una_frase_de_espera_y_no_un_resumen(
    idioma: Locale, biblioteca: patterns.PatternLibrary
) -> None:
    turno = composition.compose_turn(
        emergency_raised=False,
        block=Block.FINAL_CONFIRMATION,
        missing_field_keys=(),
        emotion=None,
        language=idioma,
        record_type=RecordType.QUOTE_REQUEST,
        confirmed_values={},
    )

    assert turno.key == "intake.closing.summary_quote"
    assert (
        confirmation.closing_summary_key(RecordType.QUOTE_REQUEST) == "intake.closing.summary_quote"
    )
    assert _sale_igual(turno.text, idioma, biblioteca)


def test_todas_las_combinaciones_de_cuatro_bloques_y_dos_idiomas_tienen_lectura() -> None:
    for bloque, idioma in itertools.product(
        (Block.QUOTE_DRIVER, Block.QUOTE_VEHICLE, Block.QUOTE_USAGE, Block.QUOTE_HISTORY), IDIOMAS
    ):
        assert confirmation.readback_key(bloque).startswith("intake.readback.quote_")
        assert confirmation.build_readback(bloque, {}, language=idioma).strip()
