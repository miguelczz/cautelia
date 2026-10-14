"""Ninguna fila de una aseguradora puede apuntar al caso o al turno de otra (decision 4).

Compuerta dura, y es la que la politica de fila **no** cubre: las comprobaciones
de llave foranea las hace el motor por encima de las politicas, y con una llave
de una sola columna la aseguradora B podia escribir una fila suya que nombrara el
caso de la aseguradora A. La revision `u10_compliance_0002_tenant_fks` hizo que
toda llave entre tablas aisladas lleve tambien la aseguradora; estas pruebas lo
comprueban **llave por llave**, contra PostgreSQL de verdad y con el rol del
aplicativo.

Cada prueba hace dos inserciones con la misma fila y cambia una sola cosa:

1. la fila que apunta a lo **suyo** entra --asi el rechazo de la segunda no se
   puede deber a otra restriccion de la tabla--;
2. la misma fila apuntando al caso o al turno **de la otra aseguradora** choca, y
   el mensaje nombra la llave.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from untangle.tenancy import session

from .conftest import AHORA, CasoSembrado, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u10")

Fila = Callable[[str, CasoSembrado], dict[str, Any]]


def _id(prefijo: str) -> str:
    return f"{prefijo}-{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True)
class Llave:
    """Una llave foranea, la sentencia que la ejercita y la fila que la usa."""

    nombre: str
    sentencia: str
    #: La fila de la aseguradora `tenant_id`, apuntando al caso (y al turno) dado.
    fila: Fila
    #: Si la fila ademas **nombra un turno** (la intervencion y la revision). Su
    #: `turn_id` es una referencia, no su llave primaria como en el turno mismo.
    nombra_turno: bool = False


LLAVES = (
    Llave(
        "case_field_del_caso",
        "INSERT INTO case_field (case_id, tenant_id, field_key, updated_at) "
        "VALUES (:case_id, :tenant_id, :field_key, :updated_at)",
        lambda t, c: {
            "case_id": c.case_id,
            "tenant_id": t,
            "field_key": _id("campo"),
            "updated_at": AHORA,
        },
    ),
    Llave(
        "case_party_del_caso",
        "INSERT INTO case_party (party_id, tenant_id, case_id, role) "
        "VALUES (:party_id, :tenant_id, :case_id, 'witness')",
        lambda t, c: {"party_id": _id("parte"), "tenant_id": t, "case_id": c.case_id},
    ),
    Llave(
        "case_transcript_turn_del_caso",
        "INSERT INTO case_transcript_turn (turn_id, tenant_id, case_id, speaker, channel, "
        "language, text_redacted, started_at) VALUES (:turn_id, :tenant_id, :case_id, "
        "'insured', 'chat', 'es', 'Turno sembrado.', :started_at)",
        lambda t, c: {
            "turn_id": _id("turno"),
            "tenant_id": t,
            "case_id": c.case_id,
            "started_at": AHORA,
        },
    ),
    Llave(
        "case_change_del_caso",
        "INSERT INTO case_change (change_id, tenant_id, case_id, change_kind, actor_type, "
        "changed_at) VALUES (:change_id, :tenant_id, :case_id, 'transition_rejected', "
        "'system', :changed_at)",
        lambda t, c: {
            "change_id": _id("cambio"),
            "tenant_id": t,
            "case_id": c.case_id,
            "changed_at": AHORA,
        },
    ),
    Llave(
        "trace_summary_del_caso",
        "INSERT INTO trace_summary (trace_id, tenant_id, case_id, visitor_key_hash, created_at) "
        "VALUES (:trace_id, :tenant_id, :case_id, :hash, :created_at)",
        lambda t, c: {
            "trace_id": _id("traza"),
            "tenant_id": t,
            "case_id": c.case_id,
            "hash": "0" * 64,
            "created_at": AHORA,
        },
    ),
    Llave(
        "disclosure_record_del_caso",
        "INSERT INTO disclosure_record (disclosure_id, tenant_id, case_id, channel, language, "
        "catalog_key, disclosed_at) VALUES (:disclosure_id, :tenant_id, :case_id, 'chat', 'es', "
        "'compliance.disclosure.opening', :disclosed_at)",
        lambda t, c: {
            "disclosure_id": _id("divulgacion"),
            "tenant_id": t,
            "case_id": c.case_id,
            "disclosed_at": AHORA,
        },
    ),
    Llave(
        "guard_intervention_del_caso",
        "INSERT INTO guard_intervention (intervention_id, tenant_id, case_id, turn_id, category, "
        "pattern_id, action, catalog_key, occurred_at) VALUES (:intervention_id, :tenant_id, "
        ":case_id, :turn_id, 'amount', 'guard.es.amount.001', 'substituted', "
        "'compliance.guard.amount', :occurred_at)",
        lambda t, c: {
            "intervention_id": _id("intervencion"),
            "tenant_id": t,
            "case_id": c.case_id,
            "turn_id": c.turn_ids[-1],
            "occurred_at": AHORA,
        },
        nombra_turno=True,
    ),
    Llave(
        "compliance_review_del_caso",
        "INSERT INTO compliance_review (review_id, tenant_id, case_id, disclosure_ok, "
        "human_route_ok, pii_ok, explainability_ok, reviewed_through_turn, reviewed_at) "
        "VALUES (:review_id, :tenant_id, :case_id, true, true, true, true, :turn_id, :reviewed_at)",
        lambda t, c: {
            "review_id": _id("revision"),
            "tenant_id": t,
            "case_id": c.case_id,
            "turn_id": c.turn_ids[-1],
            "reviewed_at": AHORA,
        },
        nombra_turno=True,
    ),
)

#: Las dos llaves que apuntan a un turno: la fila es del caso propio y el turno,
#: de la otra aseguradora. Aislan la llave del turno de la del caso.
LLAVES_AL_TURNO = (
    ("guard_intervention_de_su_turno", LLAVES[6].sentencia),
    ("compliance_review_hasta_su_turno", LLAVES[7].sentencia),
)


async def _escribir(tenant_id: str, sentencia: str, fila: dict[str, Any]) -> None:
    async with session.session_for(tenant_id) as sesion:
        await session.execute_sql(sesion, sentencia, **fila)


async def _rechazo(tenant_id: str, sentencia: str, fila: dict[str, Any]) -> str:
    with pytest.raises(IntegrityError) as rechazo:
        await _escribir(tenant_id, sentencia, fila)
    return str(rechazo.value)


@pytest.mark.parametrize("llave", LLAVES, ids=[llave.nombre for llave in LLAVES])
async def test_una_fila_no_puede_apuntar_al_caso_de_otra_aseguradora(
    dos_aseguradoras: tuple[str, str], llave: Llave
) -> None:
    ajena, propia = dos_aseguradoras
    caso_ajeno = await nuevo_caso(ajena)
    caso_propio = await nuevo_caso(propia)

    # La misma fila, apuntando a lo suyo, entra.
    await _escribir(propia, llave.sentencia, llave.fila(propia, caso_propio))

    # Apuntando al caso de la otra aseguradora, choca con la llave. Para las filas
    # que ademas nombran un turno se usa el turno propio: lo que se prueba aqui es
    # la llave del caso, y la del turno tiene su propia prueba.
    cruzada = llave.fila(propia, caso_ajeno)
    if llave.nombra_turno:
        cruzada["turn_id"] = caso_propio.turn_ids[-1]
    mensaje = await _rechazo(propia, llave.sentencia, cruzada)

    assert llave.nombre in mensaje


@pytest.mark.parametrize(
    ("nombre", "sentencia"), LLAVES_AL_TURNO, ids=[n for n, _ in LLAVES_AL_TURNO]
)
async def test_una_fila_no_puede_apuntar_al_turno_de_otra_aseguradora(
    dos_aseguradoras: tuple[str, str], nombre: str, sentencia: str
) -> None:
    ajena, propia = dos_aseguradoras
    caso_ajeno = await nuevo_caso(ajena)
    caso_propio = await nuevo_caso(propia)
    llave = next(ll for ll in LLAVES if ll.sentencia == sentencia)

    await _escribir(propia, sentencia, llave.fila(propia, caso_propio))

    # El caso es el propio; el turno, el de la otra aseguradora.
    cruzada = llave.fila(propia, caso_propio) | {"turn_id": caso_ajeno.turn_ids[-1]}
    mensaje = await _rechazo(propia, sentencia, cruzada)

    assert nombre in mensaje


async def test_borrar_el_caso_se_lleva_sus_filas_con_la_llave_de_dos_columnas(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La cascada sigue viva con la llave nueva: NFR19.4 no se rompio al cerrar el hueco."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    for llave in LLAVES:
        await _escribir(propia, llave.sentencia, llave.fila(propia, caso))

    async with session.session_for(propia) as sesion:
        await session.execute_sql(
            sesion, "DELETE FROM case_record WHERE case_id = :case_id", case_id=caso.case_id
        )
        quedan = await session.fetch_one(
            sesion,
            "SELECT (SELECT count(*) FROM case_field) + (SELECT count(*) FROM case_party) "
            "+ (SELECT count(*) FROM case_transcript_turn) + (SELECT count(*) FROM case_change) "
            "+ (SELECT count(*) FROM trace_summary) + (SELECT count(*) FROM disclosure_record) "
            "+ (SELECT count(*) FROM guard_intervention) "
            "+ (SELECT count(*) FROM compliance_review) AS filas",
        )

    assert quedan is not None
    assert quedan["filas"] == 0
