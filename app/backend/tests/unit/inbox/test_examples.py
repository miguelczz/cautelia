"""Lo que se puede comprobar de los casos de ejemplo sin base de datos.

La compuerta entera --que un caso de visitante no salga por la pagina publica-- se
prueba por HTTP contra la base en `tests/integration/u14/test_examples.py`. Aqui va lo
que no la necesita: la constante que la sostiene, el orden de la lista y el rechazo de
un identificador que ni siquiera se puede preguntar.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from untangle.case_record import fields
from untangle.case_record.api import CaseSummary
from untangle.case_record.models import (
    VISITOR_ORIGINS,
    CaseState,
    Channel,
    Origin,
    Priority,
    RecordType,
)
from untangle.inbox import examples


def test_el_unico_origen_publico_es_el_del_generador() -> None:
    """Si esta constante cambiara, la pagina publica empezaria a mostrar otra cosa."""
    assert examples.ORIGEN_PUBLICO is Origin.GENERATOR
    assert examples.ORIGEN_PUBLICO not in VISITOR_ORIGINS


def test_la_lista_no_ofrece_los_casos_abiertos() -> None:
    assert examples.FUERA_DE_LA_LISTA == (CaseState.OPEN,)


def _fila(numero: str, estado: CaseState) -> CaseSummary:
    ahora = datetime(2026, 10, 11, tzinfo=UTC)
    return CaseSummary(
        case_id=f"id-{numero}",
        case_number=numero,
        record_type=RecordType.CLAIM,
        state=estado,
        resolution=None,
        channel=Channel.CHAT,
        language="es",
        priority=Priority.NORMAL,
        derivation_reason=None,
        completeness=fields.completeness_of(RecordType.CLAIM, ()),
        created_at=ahora,
        updated_at=ahora,
        priority_rank=1,
    )


def test_el_orden_es_el_camino_del_caso_y_luego_el_numero() -> None:
    desordenadas = (
        _fila("XXX-000003", CaseState.CLOSED),
        _fila("XXX-000002", CaseState.DERIVED),
        _fila("XXX-000001", CaseState.DERIVED),
        _fila("XXX-000009", CaseState.CAPTURING),
        _fila("XXX-000004", CaseState.VERIFYING),
    )

    assert [f.case_number for f in examples.ordenados(desordenadas)] == [
        "XXX-000009",
        "XXX-000004",
        "XXX-000001",
        "XXX-000002",
        "XXX-000003",
    ]


@pytest.mark.parametrize("identificador", ["", "x" * 129, "con\x00nul", "salto\nde linea"])
async def test_un_identificador_que_no_se_puede_preguntar_no_llega_a_la_base(
    identificador: str,
) -> None:
    """Sin base configurada, si llegara a consultar fallaria: devuelve `None` antes."""
    assert await examples.detalle("una-aseguradora", identificador) is None
