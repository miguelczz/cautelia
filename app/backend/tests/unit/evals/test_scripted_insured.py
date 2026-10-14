"""Pruebas del asegurado simulado (AC4.7.1 a AC4.7.5).

Ninguna llama a un modelo ni necesita credenciales: es justamente lo que se
prueba. El catalogo se monta sobre un directorio temporal para que la frase de
desconocimiento no dependa del contenido real, que cambia.
"""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from pathlib import Path

import pytest

from untangle.copy_catalog import api as copy_api
from untangle.evals import scripted_insured
from untangle.evals.models import AnswerKind, Dataset, GoldenCase, ScriptAnswer
from untangle.evals.scripted_insured import ScriptedInsured

DESCONOZCO_ES = "No sé, eso no lo tengo."
DESCONOZCO_EN = "I don't know, I don't have that."


@pytest.fixture(autouse=True)
def catalogo_de_prueba(tmp_path: Path) -> Iterator[None]:
    """Un catalogo propio, instalado y retirado: nada de estado compartido."""
    for locale, texto in (("es", DESCONOZCO_ES), ("en", DESCONOZCO_EN)):
        (tmp_path / f"{locale}.yaml").write_text(
            "evals:\n  scripted_insured:\n    unknown_field:\n"
            f'      text: "{texto}"\n      surface: system\n',
            encoding="utf-8",
        )
    copy_api.install(copy_api.load(tmp_path))
    yield
    copy_api.reset()


def caso(*respuestas: ScriptAnswer, language: str = "es") -> GoldenCase:
    return GoldenCase(
        case_key=f"DS-2/{language}/001",
        dataset=Dataset.DS_2,
        language=language,  # type: ignore[arg-type]
        script=respuestas,
    )


# --- Camino feliz -------------------------------------------------------------


def test_responde_el_campo_que_el_turno_declara_en_cualquier_orden() -> None:
    respondedor = ScriptedInsured(
        caso(
            ScriptAnswer(field_key="incident.location", text="En la 80 con la 33"),
            ScriptAnswer(field_key="incident.datetime", text="Ayer a las siete"),
        )
    )

    # La agente pregunta al reves del orden del guion, que es lo normal.
    assert respondedor.answer("incident.datetime").text == "Ayer a las siete"
    assert respondedor.answer("incident.location").text == "En la 80 con la 33"
    assert respondedor.off_script_turns == 0


def test_la_misma_secuencia_de_campos_da_la_misma_secuencia_de_respuestas() -> None:
    guion = (
        ScriptAnswer(field_key="incident.location", sequence=1, text="En la 80"),
        ScriptAnswer(
            field_key="incident.location",
            sequence=2,
            text="Perdón, en la 30",
            kind=AnswerKind.CORRECTION,
        ),
        ScriptAnswer(field_key="incident.datetime", text="Ayer a las siete"),
    )
    pedidos = ["incident.location", "incident.datetime", "incident.location", "incident.location"]

    primera = [ScriptedInsured(caso(*guion)).answer(c).text for c in pedidos]
    segunda = [ScriptedInsured(caso(*guion)).answer(c).text for c in pedidos]

    # Dos respondedores nuevos sobre el mismo guion: si hubiera una fuente de
    # azar, estas dos listas divergirian.
    assert primera == segunda


# --- Casos de error y de borde ------------------------------------------------


def test_una_correccion_se_entrega_una_sola_vez_y_despues_se_confirma() -> None:
    respondedor = ScriptedInsured(
        caso(
            ScriptAnswer(field_key="incident.datetime", sequence=1, text="A las seis"),
            ScriptAnswer(
                field_key="incident.datetime",
                sequence=2,
                text="No, perdón, a las siete",
                kind=AnswerKind.CORRECTION,
            ),
        )
    )

    primera = respondedor.answer("incident.datetime")
    correccion = respondedor.answer("incident.datetime")
    confirmacion = respondedor.answer("incident.datetime")

    assert primera.text == "A las seis"
    assert correccion.correction is True
    assert correccion.text == "No, perdón, a las siete"
    # Una correccion que se repite deja el caso en un bucle y nunca produce su
    # registro esperado.
    assert confirmacion.correction is False
    assert confirmacion.text == "No, perdón, a las siete"


def test_un_campo_fuera_del_guion_contesta_que_no_sabe_y_suma_un_desvio() -> None:
    respondedor = ScriptedInsured(
        caso(ScriptAnswer(field_key="incident.location", text="En la 80"))
    )

    respuesta = respondedor.answer("policy.deductible")

    assert respuesta.off_script is True
    assert respuesta.text == DESCONOZCO_ES
    assert respondedor.off_script_turns == 1


def test_la_frase_de_desconocimiento_sale_en_el_idioma_del_caso() -> None:
    en_ingles = ScriptedInsured(caso(language="en"))

    assert en_ingles.answer("policy.deductible").text == DESCONOZCO_EN


def test_ninguna_llamada_a_un_cliente_de_modelo_aparece_en_su_cadena() -> None:
    # El modulo no importa ningun proveedor ni nada con estado aleatorio. Se
    # comprueba sobre el codigo, no sobre una promesa del comentario.
    fuente = inspect.getsource(scripted_insured)

    for prohibido in ("random", "secrets", "openai", "google.genai", "anthropic", "providers"):
        assert prohibido not in fuente, f"el asegurado simulado menciona '{prohibido}'"

    importados = {
        nombre
        for nombre, valor in vars(scripted_insured).items()
        if inspect.ismodule(valor) or inspect.isclass(valor)
    }
    assert "random" not in importados
