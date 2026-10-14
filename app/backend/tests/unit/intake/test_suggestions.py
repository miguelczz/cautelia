"""Los botones de respuesta rapida: que cada uno sea una respuesta que la captura ya
entiende por sus reglas, sin modelo (fase 0, 2026-10-07).

Si un boton dijera algo que las reglas no reconocen, tocarlo funcionaria solo
cuando el modelo esta, y el boton que existe para que nadie se pierda dejaria
perdido a quien lo toca justo cuando el modelo falla.
"""

from __future__ import annotations

import pytest

from untangle.base import Locale
from untangle.orchestration.nodes.intake import confirmation, normalization, policy, suggestions

IDIOMAS: tuple[Locale, ...] = ("es", "en")


@pytest.mark.parametrize("idioma", IDIOMAS)
@pytest.mark.parametrize(
    "pregunta",
    ["intake.readback.when_and_where", "intake.policy.found"],
)
def test_las_preguntas_de_si_o_no_llevan_un_si_y_un_no_que_las_reglas_leen(
    idioma: Locale, pregunta: str
) -> None:
    si, no = suggestions.for_question(pregunta, language=idioma, example_policy="POL-1")

    assert confirmation.is_affirmative(si, language=idioma)
    assert confirmation.is_negative(no, language=idioma)


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_la_poliza_de_ejemplo_se_reconoce_como_numero_de_poliza(idioma: Locale) -> None:
    [boton] = suggestions.for_question(
        "intake.question.identity_and_policy", language=idioma, example_policy="POL-100042"
    )

    assert policy.policy_number_in(boton)
    assert "POL-100042" in boton


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_los_usos_y_los_recorridos_se_convierten_en_su_valor(idioma: Locale) -> None:
    usos = suggestions.for_question(
        "intake.question.quote_use_type", language=idioma, example_policy="POL-1"
    )
    recorridos = suggestions.for_question(
        "intake.question.quote_annual_mileage_band", language=idioma, example_policy="POL-1"
    )

    assert [normalization.normalize_use_type(u, language=idioma) for u in usos] == [
        "personal",
        "commuting",
        "commercial",
    ]
    assert [normalization.normalize_mileage_band(r, language=idioma) for r in recorridos] == [
        "low",
        "medium",
        "high",
    ]


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_la_pregunta_de_seguridad_ofrece_las_dos_respuestas(idioma: Locale) -> None:
    nadie, alguien = suggestions.for_question(
        "intake.question.safety", language=idioma, example_policy="POL-1"
    )

    assert confirmation.is_negative(nadie, language=idioma)
    assert confirmation.is_affirmative(alguien, language=idioma)


def test_una_pregunta_abierta_no_lleva_botones() -> None:
    assert (
        suggestions.for_question(
            "intake.question.what_happened", language="es", example_policy="POL-1"
        )
        == ()
    )


def test_las_opciones_ofrecen_cotizar_solo_donde_esta_activa() -> None:
    assert len(suggestions.options(language="es", quote_enabled=False)) == 2
    assert suggestions.options(language="es", quote_enabled=True)[-1] == "Pedir una cotización"


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_la_oferta_del_cierre_ofrece_agregar_o_dejarlo_y_las_reglas_lo_leen(
    idioma: Locale,
) -> None:
    """«¿Quiere agregar X, o lo dejamos para el ajustador?» no se contesta con Si o No."""
    agregar, dejar = suggestions.for_question(
        "intake.closing.fast_claim_offer", language=idioma, example_policy="POL-1"
    )

    assert confirmation.accepts_offer(agregar, language=idioma)
    assert not confirmation.accepts_offer(dejar, language=idioma)


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_con_titular_el_boton_contesta_nombre_y_poliza(idioma: Locale) -> None:
    """La pregunta pide nombre y poliza; el boton contesta las dos (pedido de Miguel,
    2026-10-08: antes solo subia la poliza)."""
    [boton] = suggestions.for_question(
        "intake.question.identity_and_policy",
        language=idioma,
        example_policy="POL-100042",
        example_holder="Natalia Henao Rendón",
    )

    assert "Natalia Henao Rendón" in boton
    assert policy.policy_number_in(boton) == "POL-100042"


@pytest.mark.parametrize(
    "texto", ["Preguntar por mi póliza", "  reportar un accidente ", "Ask about my policy"]
)
def test_los_botones_de_opciones_se_reconocen_en_los_dos_idiomas(texto: str) -> None:
    """2026-10-09: el boton «Preguntar por mi poliza» se guardaba como la pregunta."""
    assert suggestions.is_option(texto)


def test_una_pregunta_de_verdad_no_es_un_boton_de_opciones() -> None:
    assert not suggestions.is_option("¿Me cubren si me roban el carro?")


@pytest.mark.parametrize("language", ["es", "en"])
def test_las_preguntas_de_ejemplo_son_cuatro_y_son_preguntas(language: str) -> None:
    preguntas = suggestions.sample_questions(language=language)  # type: ignore[arg-type]
    assert len(preguntas) == 4
    assert all(p.endswith("?") for p in preguntas)


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_la_pregunta_de_que_quiere_saber_ofrece_las_preguntas_de_ejemplo(idioma: Locale) -> None:
    """2026-10-12: la consulta que entra sin pregunta recibe la frase de «que quieres
    saber», y los ejemplos son los botones que orientan a quien no sabe que preguntar."""
    botones = suggestions.for_question(
        "policy_rag.coverage.ask_question", language=idioma, example_policy="POL-1"
    )

    assert botones == suggestions.sample_questions(language=idioma)
    assert len(botones) == 4
