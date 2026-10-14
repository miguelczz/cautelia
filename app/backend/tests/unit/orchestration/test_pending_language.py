"""Tras la respuesta de cobertura, la pregunta pendiente sale en el idioma del turno.

RT-10 (2026-10-09): la persona paso a ingles a mitad del reporte y la agente contesto
"To check that, I first need your policy. ¿Hubo alguien herido?": la frase guardada
estaba en espanol y se pegaba tal cual.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from untangle.case_record import fields
from untangle.case_record.models import CaseState, Completeness, RecordType
from untangle.copy_catalog import api as copy_api
from untangle.orchestration import turn

copy_api.install(copy_api.load())


def _contexto(language: str) -> Any:
    claves = [d.key for d in fields.definitions_for(RecordType.CLAIM)]
    return SimpleNamespace(
        record_type=RecordType.CLAIM,
        state=CaseState.CAPTURING,
        language=language,
        completeness=Completeness(
            per_field={c: c == "identity_and_policy" for c in claves},
            complete=1,
            total=len(claves),
        ),
    )


def _previo(texto: str) -> Any:
    return SimpleNamespace(node_writes={"intake_response_text": texto})


def test_en_el_mismo_idioma_se_retoma_la_frase_guardada() -> None:
    pendiente = turn._lo_pendiente(
        cast(Any, _previo("¿Hubo alguien herido?")), _contexto("es"), language="es"
    )
    assert pendiente == "¿Hubo alguien herido?"


def test_si_la_persona_cambio_de_idioma_la_pregunta_sale_en_el_suyo() -> None:
    pendiente = turn._lo_pendiente(
        cast(Any, _previo("¿Hubo alguien herido?")), _contexto("es"), language="en"
    )
    assert pendiente is not None
    assert "¿" not in pendiente
    assert pendiente.endswith("?")
