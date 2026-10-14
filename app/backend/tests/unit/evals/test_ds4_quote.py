"""DS-4, el golden set de la cotizacion (U19): que sus casos esten bien formados y en paridad.

Los seis casos que se resuelven sin modelo **se corren** (los corre el subconjunto de arranque, y
aqui se corren sus sondas). Los dos de canal piden la clave del proveedor y **solo se validan de
forma**: nada de esta unidad los ejecuta contra un modelo.
"""

from __future__ import annotations

import pytest

from untangle import paths
from untangle.base import Locale
from untangle.case_record import fields
from untangle.case_record.models import RecordType
from untangle.evals import loading, quote_fixtures, quote_probes
from untangle.evals.models import Channel, Dataset, GoldenCase
from untangle.evals.runner import api as runner_api
from untangle.orchestration.nodes.intake import blocks
from untangle.rules import eligibility

IDIOMAS: tuple[Locale, ...] = ("es", "en")


def _casos() -> tuple[GoldenCase, ...]:
    return tuple(c for c in loading.load_cases() if c.dataset is Dataset.DS_4)


def _slug(caso: GoldenCase) -> str:
    return caso.case_key.split("/", 2)[2]


def test_ds4_tiene_ocho_casos_por_idioma_y_el_manifiesto_lo_dice() -> None:
    casos = _casos()
    declaracion = loading.load_manifest().declaration_for(Dataset.DS_4)

    assert declaracion.built is True
    assert declaracion.count == len(casos) == 16
    assert sum(1 for c in casos if c.language == "es") == 8
    assert sum(1 for c in casos if c.language == "en") == 8
    assert loading.check_manifest_counts(loading.load_manifest(), loading.load_cases()) == ()


def test_cada_caso_tiene_su_pareja_en_el_otro_idioma() -> None:
    """P12: los mismos casos en los dos idiomas, nunca uno solo ni un promedio combinado."""
    por_idioma = {
        idioma: {_slug(c) for c in _casos() if c.language == idioma} for idioma in IDIOMAS
    }

    assert por_idioma["es"] == por_idioma["en"]


def test_las_dos_parejas_declaran_los_mismos_criterios_y_la_misma_estructura() -> None:
    es = {_slug(c): c for c in _casos() if c.language == "es"}
    en = {_slug(c): c for c in _casos() if c.language == "en"}

    for slug, caso_es in es.items():
        caso_en = en[slug]
        assert caso_es.expected_verdicts == caso_en.expected_verdicts, slug
        assert caso_es.axes == caso_en.axes, slug
        assert caso_es.channel == caso_en.channel, slug
        assert caso_es.requires_provider_key == caso_en.requires_provider_key, slug
        assert [a.field_key for a in caso_es.script] == [a.field_key for a in caso_en.script], slug
        assert [(a.sequence, a.kind) for a in caso_es.script] == [
            (a.sequence, a.kind) for a in caso_en.script
        ], slug
        assert caso_es.expected_record.keys() == caso_en.expected_record.keys(), slug


def test_los_casos_sin_canal_se_resuelven_sin_modelo_y_tienen_sonda() -> None:
    """Un criterio sin sonda registrada reventaria la corrida completa con un `LookupError`."""
    sin_canal = [c for c in _casos() if c.channel is None]
    assert len(sin_canal) == 12

    quote_probes.register_quote_probes()
    for caso in sin_canal:
        assert caso.requires_provider_key is False, caso.case_key
        assert caso.expected_verdicts, caso.case_key
        for criterio, esperado in caso.expected_verdicts.items():
            assert esperado == "pass"
            assert runner_api.check_for(criterio) is not None, (caso.case_key, criterio)
            assert criterio in quote_probes.SONDAS


def test_los_casos_de_canal_piden_la_clave_y_declaran_su_registro_esperado() -> None:
    """Se validan de forma. La corrida completa por hito es la que los ejecuta."""
    de_canal = [c for c in _casos() if c.channel is not None]
    assert sorted(_slug(c) for c in de_canal) == [
        "quote-end-to-end",
        "quote-end-to-end",
        "quote-price-pressure-conversation",
        "quote-price-pressure-conversation",
    ]
    for caso in de_canal:
        assert caso.channel is Channel.CHAT
        assert caso.requires_provider_key is True
        assert caso.tenant is not None
        assert caso.expected_record == {
            "record_type": "quote_request",
            "state": "capturing",
            "complete": 17,
            "total": 17,
            "language": caso.language,
        }


def test_el_guion_de_un_caso_de_canal_responde_cada_campo_y_la_lectura_final() -> None:
    """Quince campos que se preguntan y **una** confirmacion, la de toda la solicitud.

    Desde el 2026-10-08 la solicitud no se lee de vuelta por bloques: se lee entera al final y
    el nodo deja la lectura en espera del ultimo bloque. Un guion con la confirmacion de cada
    bloque --como el que se escribio antes-- le contesta "si, es correcto" a una agente que
    esta preguntando por el vehiculo.
    """
    esperadas = [
        d.key
        for d in fields.definitions_for(RecordType.QUOTE_REQUEST)
        if d.key not in {"vehicle_age_years", "lapse_months"}
    ] + [blocks.QUOTE_BLOCK_ORDER[-1].value]

    for caso in _casos():
        if caso.channel is None:
            continue
        claves = {a.field_key for a in caso.script}
        assert claves == set(esperadas), (caso.case_key, set(esperadas) ^ claves)
        confirmaciones = [a.field_key for a in caso.script if a.field_key.startswith("quote_")]
        assert confirmaciones == ["quote_history"], caso.case_key
        assert caso.script[-1].field_key == "quote_history", "la confirmacion va al final"


def test_el_primer_mensaje_pide_cotizar_para_que_el_caso_nazca_como_solicitud() -> None:
    from untangle.orchestration import quote_reply

    for caso in _casos():
        if caso.channel is None:
            continue
        primero = caso.script[0]
        assert primero.field_key == "driver_name"
        assert quote_reply.is_quote_request(primero.text, language=caso.language), caso.case_key


def test_la_presion_se_repite_antes_de_la_respuesta_y_la_respuesta_real_llega_al_final() -> None:
    """Insistir es presionar mas de una vez: dos presiones y despues la respuesta de verdad."""
    from untangle.orchestration import quote_reply

    for caso in _casos():
        if _slug(caso) != "quote-price-pressure-conversation":
            continue
        del_campo = caso.answers_for("use_type")
        assert [a.sequence for a in del_campo] == [1, 2, 3]
        assert all(
            quote_reply.is_price_request(a.text, language=caso.language) for a in del_campo[:2]
        )
        assert not quote_reply.is_price_request(del_campo[2].text, language=caso.language)


# --- Los escenarios --------------------------------------------------------------------------


def test_los_dos_idiomas_miden_la_misma_elegibilidad_valor_por_valor() -> None:
    """P12: el motor no depende del idioma, y un escenario que existe en uno solo no se compara."""
    raiz = paths.repo_root()
    es = quote_fixtures.load_quote_fixtures("es", raiz)
    en = quote_fixtures.load_quote_fixtures("en", raiz)

    assert [f.model_dump() for f in es.eligibility] == [f.model_dump() for f in en.eligibility]
    assert len(es.pressure) == len(en.pressure) >= 10
    assert [f.tenant_id for f in es.availability] == [f.tenant_id for f in en.availability]
    assert [(f.anything_captured, f.expect_unavailable) for f in es.availability] == [
        (f.anything_captured, f.expect_unavailable) for f in en.availability
    ]


def test_los_umbrales_se_prueban_por_sus_dos_lados() -> None:
    """Un umbral mal puesto por uno es el error que no rompe nada: hay que tener ambos lados."""
    filas = quote_fixtures.load_quote_fixtures("es", paths.repo_root()).eligibility
    por_regla: dict[str, set[str]] = {}
    for fila in filas:
        for regla in fila.expected_rules:
            por_regla.setdefault(regla, set()).add(fila.scenario)

    for regla in ("SUN-Q-03", "SUN-Q-04", "SUN-Q-05"):
        assert "referral" in por_regla[regla], regla
    # Justo por debajo de cada umbral hay una fila que NO deriva.
    sin_derivar = [f for f in filas if f.scenario == "no-referral"]
    assert all(f.expected_outcome == "eligible" for f in sin_derivar)
    assert {f.inputs.get("vehicle_age_years") for f in sin_derivar} >= {25}
    assert {f.inputs.get("license_years") for f in sin_derivar} >= {1}
    assert {f.inputs.get("at_fault_losses_3y") for f in sin_derivar} >= {1}


def test_toda_regla_de_sunmeadow_la_decide_algun_escenario() -> None:
    """Una regla que ningun escenario provoca es una regla que nadie esta midiendo."""
    filas = quote_fixtures.load_quote_fixtures("en", paths.repo_root()).eligibility
    decididas = {regla for fila in filas for regla in fila.expected_rules}
    todas = {regla.id for regla in eligibility.require("sunmeadow").rules}

    assert decididas == todas


def test_una_fila_con_banda_y_salida_desparejadas_no_se_carga() -> None:
    """Las filas hablan el mismo idioma cerrado que el motor: no pueden esperar una pareja invalida."""
    for fila in quote_fixtures.load_quote_fixtures("es", paths.repo_root()).eligibility:
        assert fila.expected_band in {
            banda.value
            for banda in eligibility.BANDS_OF[
                eligibility.EligibilityOutcomeKind(fila.expected_outcome)
            ]
        }, fila.id


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_las_seis_sondas_pasan_con_la_configuracion_real(idioma: Locale) -> None:
    for criterio, sonda in quote_probes.SONDAS.items():
        resultado = sonda(language=idioma, root=paths.repo_root())
        assert resultado.passed, (criterio, resultado.detail)


def test_las_dos_compuertas_duras_se_declaran_como_tales() -> None:
    quote_probes.register_quote_probes()
    objetivos = {t.criterion: t for t in runner_api.registered_targets()[quote_probes.UNIT]}

    assert {c for c, t in objetivos.items() if t.blocking} == {
        "quote_reply_without_amount",
        "quote_price_pressure_refused",
    }
    assert set(objetivos) == set(quote_probes.SONDAS)
