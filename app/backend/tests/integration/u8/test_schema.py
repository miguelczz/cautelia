"""RLS, aislamiento entre aseguradoras y borrado en cascada, de verdad (SEC-U8.1, SEC-U8.5).

De integracion: lo que se prueba es conducta del motor -- las siete tablas con
politica de fila, y que una fila de una aseguradora es invisible para otra --
y un doble no la tiene. Se escribe aqui y se corre en la sesion local
(CG-U8-5).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from untangle.case_record import api as casos
from untangle.case_record.models import Channel, Origin, RecordType
from untangle.policy_rag.corpus.models import Clause, IssuedPolicy, PolicyForm
from untangle.policy_rag.corpus.repository import upsert_reference_data
from untangle.tenancy import api as tenancy
from untangle.tenancy import rls_assertion
from untangle.tenancy import session as tenancy_session

pytestmark = pytest.mark.usefixtures("base_de_u8")

TABLAS = (
    "policy_forms",
    "clauses",
    "clause_relations",
    "issued_policies",
    "clause_index",
    "citation_checks",
    "coverage_answers",
)


async def test_las_siete_tablas_tienen_aislamiento_habilitado_forzado_y_con_politica() -> None:
    async with tenancy_session.unscoped_session() as sesion:
        vivas = {t.table: t for t in await rls_assertion.read_tables(sesion)}

    for tabla in TABLAS:
        assert tabla in vivas, f"'{tabla}' no aparece en el catalogo vivo"
        assert vivas[tabla].row_security, f"'{tabla}' no tiene aislamiento habilitado"
        assert vivas[tabla].force_row_security, f"'{tabla}' no lo tiene forzado"
        assert vivas[tabla].tenant_policies >= 1, f"'{tabla}' no tiene politica de aseguradora"


def _formulario(tenant_id: str) -> PolicyForm:
    return PolicyForm.model_validate(
        {
            "tenant_id": tenant_id,
            "form_id": "TCO-PAP-2026",
            "form_version": "2026.1",
            "form_kind": "base",
            "language": "es",
            "issuer_label": "Testco Mutual",
            "issuer_tenant": tenant_id,
        }
    )


def _clausula(tenant_id: str, *, texto: str) -> Clause:
    return Clause.model_validate(
        {
            "tenant_id": tenant_id,
            "clause_id": f"{tenant_id}-TCO-PAP-2026-A.1",
            "clause_key": "A.1",
            "form_id": "TCO-PAP-2026",
            "form_version": "2026.1",
            "part": "Parte A",
            "language": "es",
            "text": texto,
            "is_distractor": False,
            "issuer_label": "Testco Mutual",
        }
    )


def _poliza(tenant_id: str) -> IssuedPolicy:
    return IssuedPolicy.model_validate(
        {
            "tenant_id": tenant_id,
            "policy_number": f"POL-{tenant_id.upper()}-001",
            "issuer_tenant": tenant_id,
            "form_id": "TCO-PAP-2026",
            "form_version": "2026.1",
            "endorsement_ids": [],
            "named_insured": {"full_name": "Persona de Prueba"},
            "vehicles": [],
            "limits_and_deductibles": {},
            "period_start": date(2026, 1, 1),
            "period_end": date(2027, 1, 1),
        }
    )


async def test_cada_aseguradora_solo_ve_su_propio_corpus(dos_aseguradoras: tuple[str, str]) -> None:
    primera, segunda = dos_aseguradoras
    await upsert_reference_data(
        primera,
        forms=(_formulario(primera),),
        clauses=(_clausula(primera, texto="Texto de la primera aseguradora."),),
        relations=(),
        policies=(_poliza(primera),),
    )
    await upsert_reference_data(
        segunda,
        forms=(_formulario(segunda),),
        clauses=(_clausula(segunda, texto="Texto de la segunda aseguradora."),),
        relations=(),
        policies=(_poliza(segunda),),
    )

    async with tenancy.session_for(primera) as sesion:
        formularios = await tenancy.fetch_all(sesion, "SELECT tenant_id FROM policy_forms")
        clausulas = await tenancy.fetch_all(sesion, "SELECT tenant_id FROM clauses")
        polizas = await tenancy.fetch_all(sesion, "SELECT tenant_id FROM issued_policies")

    assert {f["tenant_id"] for f in formularios} == {primera}
    assert {c["tenant_id"] for c in clausulas} == {primera}
    assert {p["tenant_id"] for p in polizas} == {primera}


async def test_reingestar_la_misma_clausula_no_duplica_la_fila(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR1.3: `ON CONFLICT` deja una sola fila por `clause_id`, no dos."""
    primera, _ = dos_aseguradoras
    formulario = _formulario(primera)
    poliza = _poliza(primera)
    await upsert_reference_data(
        primera,
        forms=(formulario,),
        clauses=(_clausula(primera, texto="version 1"),),
        relations=(),
        policies=(poliza,),
    )
    await upsert_reference_data(
        primera,
        forms=(formulario,),
        clauses=(_clausula(primera, texto="version 2, editada"),),
        relations=(),
        policies=(poliza,),
    )

    async with tenancy.session_for(primera) as sesion:
        filas = await tenancy.fetch_all(
            sesion,
            "SELECT text FROM clauses WHERE clause_id = :id",
            id=f"{primera}-TCO-PAP-2026-A.1",
        )
    assert len(filas) == 1
    assert filas[0]["text"] == "version 2, editada"


async def _caso_de_visitante(tenant_id: str) -> str:
    case_id = f"u8-caso-{tenant_id}"
    await casos.create_case(
        tenant_id,
        casos.NewCase(
            case_id=case_id,
            record_type=RecordType.CLAIM,
            channel=Channel.CHAT,
            origin=Origin.PUBLIC_CHAT,
            language="es",
        ),
        now=datetime(2026, 9, 21, 12, 0, tzinfo=UTC),
    )
    return case_id


async def test_citation_checks_y_coverage_answers_cuelgan_del_caso_en_cascada(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR4.1: la fila de citas se va cuando se va el caso -- el borrado que llega en tanda 2."""
    primera, _ = dos_aseguradoras
    case_id = await _caso_de_visitante(primera)

    async with tenancy.session_for(primera) as sesion:
        await tenancy.execute_sql(
            sesion,
            """
            INSERT INTO citation_checks
                (check_id, tenant_id, case_id, clause_id, clause_version, claim_redacted,
                 outcome, reasons, checked_at)
            VALUES
                (:check_id, :tenant_id, :case_id, :clause_id, :clause_version, :claim_redacted,
                 :outcome, CAST(:reasons AS jsonb), :checked_at)
            """,
            check_id="chk-1",
            tenant_id=primera,
            case_id=case_id,
            clause_id="TCO-PAP-2026-A.1",
            clause_version="2026.1",
            claim_redacted="una afirmacion ya redactada",
            outcome="verified",
            reasons="[]",
            checked_at=datetime(2026, 9, 21, 12, 0, tzinfo=UTC),
        )
        await tenancy.execute_sql(sesion, "DELETE FROM case_record WHERE case_id = :id", id=case_id)
        filas = await tenancy.fetch_all(sesion, "SELECT check_id FROM citation_checks")

    assert filas == ()
