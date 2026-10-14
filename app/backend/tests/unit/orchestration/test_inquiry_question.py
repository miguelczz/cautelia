"""El boton «Preguntar por mi poliza» no es la pregunta de la consulta (2026-10-09).

Se guardaba como tal y la respuesta era «no encuentro una clausula que hable de eso». Desde
el 2026-10-14 tampoco lo es el mismo anuncio dicho con palabras («queria preguntar por mi
poliza»): en una llamada se reviso la poliza contra el y la consulta acabo con un ajustador.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from untangle.case_record.models import RecordType
from untangle.copy_catalog import api as copy_api
from untangle.orchestration import turn
from untangle.orchestration.nodes.intake import understanding

copy_api.install(copy_api.load())


def _contexto() -> Any:
    return SimpleNamespace(
        record_type=RecordType.COVERAGE_INQUIRY,
        completeness=SimpleNamespace(per_field={"question_asked": False}),
    )


def _turno(texto: str, idioma: str = "es") -> Any:
    return cast(Any, SimpleNamespace(text=texto, language=idioma))


def test_el_boton_de_opciones_no_queda_como_la_pregunta() -> None:
    entendido = understanding.UnderstandingResponse(
        wants=understanding.Want.POLICY_QUESTION,
        asks_about_coverage=True,
        person_question="Preguntar por mi póliza",
        items=(
            understanding.UnderstoodItem(
                field_key="question_asked", value="Preguntar por mi póliza"
            ),
        ),
    )

    limpio = turn._con_la_pregunta_de_la_consulta(
        entendido, _contexto(), _turno("Preguntar por mi póliza")
    )

    assert not any(i.field_key == "question_asked" for i in limpio.items)
    assert limpio.person_question is None


def test_una_pregunta_de_verdad_si_queda_guardada() -> None:
    entendido = understanding.UnderstandingResponse(
        wants=understanding.Want.POLICY_QUESTION,
        asks_about_coverage=True,
        person_question="¿Me cubren si me roban el carro?",
    )

    con_pregunta = turn._con_la_pregunta_de_la_consulta(
        entendido, _contexto(), _turno("¿Me cubren si me roban el carro?")
    )

    assert [i.value for i in con_pregunta.items if i.field_key == "question_asked"] == [
        "¿Me cubren si me roban el carro?"
    ]


@pytest.mark.parametrize(
    ("texto", "idioma"),
    [
        ("Hola, Valeria. Quería preguntar por mi póliza.", "es"),
        ("Tengo una duda sobre mi seguro", "es"),
        ("I have a question about my policy", "en"),
    ],
)
def test_anunciar_que_se_quiere_preguntar_por_la_poliza_no_es_la_pregunta(
    texto: str, idioma: str
) -> None:
    entendido = understanding.UnderstandingResponse(
        wants=understanding.Want.POLICY_QUESTION,
        asks_about_coverage=True,
        person_question=texto,
    )

    limpio = turn._con_la_pregunta_de_la_consulta(entendido, _contexto(), _turno(texto, idioma))

    assert not any(i.field_key == "question_asked" for i in limpio.items)
    assert limpio.person_question is None


def test_una_pregunta_de_verdad_sobre_la_poliza_si_queda_guardada() -> None:
    texto = "Quería preguntar si mi póliza cubre un carro de alquiler"
    entendido = understanding.UnderstandingResponse(
        wants=understanding.Want.POLICY_QUESTION,
        asks_about_coverage=True,
        person_question=texto,
    )

    con_pregunta = turn._con_la_pregunta_de_la_consulta(entendido, _contexto(), _turno(texto))

    assert [i.value for i in con_pregunta.items if i.field_key == "question_asked"] == [texto]
