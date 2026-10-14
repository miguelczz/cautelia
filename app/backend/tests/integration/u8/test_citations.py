"""`citation_checks` y `coverage_answers` contra PostgreSQL de verdad (pasos 5 y 6, tanda 2).

De integracion porque lo que se prueba es conducta del motor: las politicas de
fila, la llave compuesta hacia el caso y el borrado en cascada -- el mismo
patron que `tests/integration/u9/test_rule_evaluation_table.py`, con dos
tablas en vez de una porque BR4.1 exige que la respuesta y sus comprobaciones
se escriban juntas.

**Se escribe aqui y se corre en la sesion local** (CG-U8-5): este contenedor
no tiene Docker.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from untangle.case_record import purge as case_purge
from untangle.policy_rag.citations import api as citations
from untangle.policy_rag.citations import repository
from untangle.policy_rag.citations.models import CoverageAnswer, CoverageOutcome
from untangle.policy_rag.citations.verifier import CitationVerdict, VerificationResult
from untangle.server import composition
from untangle.tenancy import purge, rls_assertion, session

from .conftest import AHORA, CasoSembrado, nuevo_caso, nuevo_turno

pytestmark = pytest.mark.usefixtures("base_de_u8")

TABLAS = ("citation_checks", "coverage_answers")


def _verificacion(clause_id: str = "TCO-PAP-2026-A.LIMIT") -> VerificationResult:
    return VerificationResult(
        outcome=CoverageOutcome.VERIFIED,
        citations=(
            CitationVerdict(
                clause_id=clause_id,
                claim="El limite es el que muestra la caratula.",
                outcome=CoverageOutcome.VERIFIED,
                reasons=(),
                amended_by=(),
                clause_version="2026.1",
            ),
        ),
        clause_language="es",
    )


async def _registrar(caso: CasoSembrado, turn_id: str) -> CoverageAnswer:
    return await citations.record_answer(
        caso.tenant_id,
        case_id=caso.case_id,
        turn_id=turn_id,
        question="¿Que cubre la parte A?",
        verification=_verificacion(),
        answer_language="es",
        now=AHORA,
    )


# --- Aislamiento (SEC-U8.1, SEC-U8.5) ------------------------------------------


async def test_las_dos_tablas_tienen_aislamiento_habilitado_forzado_y_con_politica() -> None:
    async with session.unscoped_session() as sesion:
        tablas = {t.table: t for t in await rls_assertion.read_tables(sesion)}

    for tabla in TABLAS:
        assert tabla in tablas
        assert tablas[tabla].row_security
        assert tablas[tabla].force_row_security
        assert tablas[tabla].tenant_policies >= 1


async def test_cada_aseguradora_ve_solo_su_respuesta(dos_aseguradoras: tuple[str, str]) -> None:
    primera, segunda = dos_aseguradoras
    caso_1 = await nuevo_caso(primera)
    turno_1 = await nuevo_turno(caso_1)
    caso_2 = await nuevo_caso(segunda)
    turno_2 = await nuevo_turno(caso_2)

    await _registrar(caso_1, turno_1)
    await _registrar(caso_2, turno_2)

    async with session.session_for(primera) as sesion:
        vistas_primera = await session.fetch_all(sesion, "SELECT tenant_id FROM coverage_answers")
    async with session.session_for(segunda) as sesion:
        vistas_segunda = await session.fetch_all(sesion, "SELECT tenant_id FROM coverage_answers")

    assert [str(f["tenant_id"]) for f in vistas_primera] == [primera]
    assert [str(f["tenant_id"]) for f in vistas_segunda] == [segunda]


# --- Llave compuesta hacia el caso (UG-3, la leccion de U10) -------------------


async def test_una_respuesta_no_puede_apuntar_al_caso_de_otra_aseguradora(
    dos_aseguradoras: tuple[str, str],
) -> None:
    ajena, propia = dos_aseguradoras
    caso_ajeno = await nuevo_caso(ajena)
    caso_propio = await nuevo_caso(propia)
    turno_propio = await nuevo_turno(caso_propio)

    respuesta_cruzada = CoverageAnswer(
        answer_id="ans-cruzada",
        tenant_id=propia,
        case_id=caso_ajeno.case_id,
        turn_id=turno_propio,
        idempotency_key="coverage-cruzada",
        question_redacted="¿Que cubre la parte A?",
        outcome=CoverageOutcome.NO_CLAUSE_FOUND,
        citation_check_ids=(),
        answer_language="es",
        clause_language=None,
        created_at=datetime.now(UTC),
    )

    with pytest.raises(IntegrityError) as rechazo:
        await repository.save_answer_with_checks(respuesta_cruzada, checks=())

    assert "coverage_answers_del_caso" in str(rechazo.value)


# --- Borrado con el caso (BR4.5, SEC-U8.6) -------------------------------------


async def test_borrar_el_caso_se_lleva_su_respuesta_y_sus_comprobaciones(
    dos_aseguradoras: tuple[str, str],
) -> None:
    primera, _ = dos_aseguradoras
    borrado = await nuevo_caso(primera)
    turno_borrado = await nuevo_turno(borrado)
    conservado = await nuevo_caso(primera)
    turno_conservado = await nuevo_turno(conservado)

    await _registrar(borrado, turno_borrado)
    await _registrar(conservado, turno_conservado)

    async with session.session_for(primera) as sesion:
        await session.execute_sql(
            sesion, "DELETE FROM case_record WHERE case_id = :case_id", case_id=borrado.case_id
        )

    async with session.session_for(primera) as sesion:
        respuestas = await session.fetch_all(sesion, "SELECT case_id FROM coverage_answers")
        comprobaciones = await session.fetch_all(sesion, "SELECT case_id FROM citation_checks")

    assert [str(f["case_id"]) for f in respuestas] == [conservado.case_id]
    assert [str(f["case_id"]) for f in comprobaciones] == [conservado.case_id]


async def test_las_dos_tablas_llevan_la_marca_y_las_cubre_el_purgador_del_caso() -> None:
    marcadas = await purge.visitor_data_tables()

    for tabla in TABLAS:
        assert tabla in marcadas
        assert tabla in case_purge.CASE_RECORD_PURGER.tables
    assert await purge.tables_without_purger(composition.PURGADORES) == frozenset()


# --- Idempotencia por caso y turno (BR4.2, REL-U8.5) ---------------------------


async def test_reanudar_con_el_mismo_caso_y_turno_no_duplica_en_la_base(
    dos_aseguradoras: tuple[str, str],
) -> None:
    primera, _ = dos_aseguradoras
    caso = await nuevo_caso(primera)
    turno = await nuevo_turno(caso)

    primera_respuesta = await _registrar(caso, turno)
    segunda_respuesta = await _registrar(caso, turno)

    assert primera_respuesta.answer_id == segunda_respuesta.answer_id
    async with session.session_for(primera) as sesion:
        filas = await session.fetch_all(
            sesion,
            "SELECT answer_id FROM coverage_answers WHERE case_id = :case_id",
            case_id=caso.case_id,
        )
    assert len(filas) == 1


async def test_las_comprobaciones_quedan_ligadas_a_la_respuesta_que_las_agrupa(
    dos_aseguradoras: tuple[str, str],
) -> None:
    primera, _ = dos_aseguradoras
    caso = await nuevo_caso(primera)
    turno = await nuevo_turno(caso)

    respuesta = await _registrar(caso, turno)

    async with session.session_for(primera) as sesion:
        filas = await session.fetch_all(
            sesion,
            "SELECT check_id, outcome FROM citation_checks WHERE case_id = :case_id",
            case_id=caso.case_id,
        )
    assert {str(f["check_id"]) for f in filas} == set(respuesta.citation_check_ids)
    assert all(f["outcome"] == "verified" for f in filas)
