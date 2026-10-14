"""El boton «Preguntar por mi poliza» no es la pregunta de la consulta (2026-10-09).

Se guardaba como tal y la respuesta era «no encuentro una clausula que hable de eso».
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

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


def _turno(texto: str) -> Any:
    return cast(Any, SimpleNamespace(text=texto))


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
