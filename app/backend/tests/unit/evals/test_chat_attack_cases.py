"""Los ataques conversados de DS-6 (2026-10-12, auditoria E7): que carguen y que cuenten lo mismo.

Sin modelo. Lo que mide cada caso lo mide el corredor al correrlo contra Claude
(`mise run evals:conversaciones`); aqui se comprueba lo que se puede comprobar sin correrlo:
que el guion hable de campos que el esquema del siniestro tiene, que el registro esperado sea
coherente con el esquema y con lo que el guion contesta, y que las dos lenguas cuenten lo mismo.
"""

from __future__ import annotations

import pytest

from untangle import paths
from untangle.base import Locale
from untangle.case_record import fields
from untangle.case_record.models import RecordType
from untangle.evals import loading
from untangle.evals.models import Channel, GoldenCase

RAIZ = paths.repo_root()
CASOS = RAIZ / "app" / "evals" / "cases" / "ds6"
IDIOMAS: tuple[Locale, ...] = ("es", "en")

#: Cada ataque conversado y el original (el que prueba la guardia sobre frases escritas) del
#: que es la version conversada.
ATAQUES = {
    "rt1-direct-injection-chat": "rt1-direct-injection",
    "rt1-humanity-claim-chat": "rt1-humanity-claim",
    "rt3-pressure-chat": "rt3-pressure",
    "rt5-config-disclosure-chat": "rt5-config-disclosure",
    "rt6-fault-legal-advice-chat": "rt6-fault-legal-advice",
}

#: Los campos que el guion contesta con el ataque pegado al dato, y con su segunda respuesta
#: limpia por si la agente no anota la primera.
CAMPOS_CON_ATAQUE = ("injuries", "description", "incident_datetime")


def _cargar(slug: str, idioma: Locale) -> GoldenCase:
    return loading.load_case(CASOS / slug / f"{idioma}.yaml")


def _casos() -> list[tuple[str, Locale]]:
    return [(slug, idioma) for slug in ATAQUES for idioma in IDIOMAS]


@pytest.mark.parametrize(("slug", "idioma"), _casos())
def test_corre_por_el_canal_de_chat_con_la_aseguradora_y_la_poliza_de_rt10(
    slug: str, idioma: Locale
) -> None:
    caso = _cargar(slug, idioma)
    rt10 = _cargar("rt10-language-switch", idioma)

    assert caso.case_key == f"DS-6/{idioma}/{slug}"
    assert caso.channel is Channel.CHAT
    assert caso.tenant == rt10.tenant
    assert caso.language == idioma
    assert caso.requires_provider_key is True
    # Los criterios de la transcripcion son implicitos: el caso no los nombra.
    assert caso.expected_verdicts == {}
    # Y la misma persona y la misma poliza que RT-10.
    assert caso.script[0].field_key == "identity_and_policy"
    assert caso.script[0].text == rt10.script[0].text


@pytest.mark.parametrize(("slug", "idioma"), _casos())
def test_el_guion_solo_contesta_campos_que_el_siniestro_tiene(slug: str, idioma: Locale) -> None:
    """Un campo mal escrito no se pediria nunca: el guion lo trataria como desvio."""
    caso = _cargar(slug, idioma)
    del_siniestro = {d.key for d in fields.definitions_for(RecordType.CLAIM)}

    assert {r.field_key for r in caso.script} <= del_siniestro


@pytest.mark.parametrize(("slug", "idioma"), _casos())
def test_cada_campo_con_ataque_trae_su_segunda_respuesta_limpia(slug: str, idioma: Locale) -> None:
    caso = _cargar(slug, idioma)

    for campo in CAMPOS_CON_ATAQUE:
        respuestas = caso.answers_for(campo)
        assert [r.sequence for r in respuestas] == [1, 2], campo
        ataque, limpia = respuestas[0].text, respuestas[1].text
        # La limpia es el dato solo, y el ataque lo trae pegado: por eso es mas largo.
        assert len(ataque) > len(limpia), campo


@pytest.mark.parametrize(("slug", "idioma"), _casos())
def test_el_guion_contesta_los_cinco_datos_obligatorios_y_el_registro_lo_dice(
    slug: str, idioma: Locale
) -> None:
    """El registro esperado (5 de 5) sale de lo que el guion contesta y del esquema."""
    caso = _cargar(slug, idioma)
    obligatorios = {d.key for d in fields.definitions_for(RecordType.CLAIM) if not d.optional}

    assert obligatorios <= {r.field_key for r in caso.script}
    assert caso.expected_record == {
        "record_type": "claim",
        "state": "derived",
        "complete": len(obligatorios),
        "total": len(obligatorios),
        "language": idioma,
    }


@pytest.mark.parametrize("slug", ATAQUES)
def test_las_dos_lenguas_cuentan_lo_mismo(slug: str) -> None:
    es, en = _cargar(slug, "es"), _cargar(slug, "en")

    assert [(r.field_key, r.sequence) for r in es.script] == [
        (r.field_key, r.sequence) for r in en.script
    ]
    assert es.axes == en.axes
    assert {k: v for k, v in es.expected_record.items() if k != "language"} == {
        k: v for k, v in en.expected_record.items() if k != "language"
    }


@pytest.mark.parametrize(("slug", "original"), list(ATAQUES.items()))
def test_el_original_dice_cual_es_su_version_conversada(slug: str, original: str) -> None:
    """Sin esa linea, quien lee el original cree que la guardia sobre frases escritas es todo
    lo que se mide de ese ataque."""
    for idioma in IDIOMAS:
        texto = (CASOS / original / f"{idioma}.yaml").read_text(encoding="utf-8")

        assert f"`DS-6/{idioma}/{slug}`" in texto


def test_estan_en_el_subconjunto_de_conversaciones_y_no_en_el_de_arranque() -> None:
    """Necesitan el modelo: el subconjunto de arranque corre sin clave de ningun proveedor."""
    subsets = RAIZ / "app" / "evals" / "subsets"
    conversaciones = loading.load_subset("conversaciones", subsets)
    arranque = loading.load_subset("smoke", subsets)

    for slug in ATAQUES:
        for idioma in IDIOMAS:
            clave = f"DS-6/{idioma}/{slug}"
            assert clave in conversaciones.case_keys
            assert clave not in arranque.case_keys


def test_la_conversaciones_trae_todo_caso_de_chat_que_la_corrida_completa_mide() -> None:
    """El tope escrito del subconjunto es verdad: nada de chat se queda fuera. La
    cotizacion de DS-4 entro el 2026-10-12, cuando paso contra el modelo."""
    casos = loading.load_cases()
    conversaciones = set(
        loading.load_subset("conversaciones", RAIZ / "app" / "evals" / "subsets").case_keys
    )

    de_chat = {c.case_key for c in casos if c.channel is Channel.CHAT}

    assert de_chat == conversaciones
