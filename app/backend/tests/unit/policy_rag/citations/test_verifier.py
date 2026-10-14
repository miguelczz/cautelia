"""Pruebas de `policy_rag.citations.verifier`, sin base de datos (CG-U8-4).

Solo `relations_into` toca la base (para BR3.5); se sustituye por un doble en
cada prueba, así que ninguna necesita PostgreSQL. Cada regla de precedencia
lleva su propia prueba, aislada (unit-test-instructions.md): BR3.1 (solo se
verifica lo recuperado), BR3.4 (no_clause_found nunca se confunde con nada
más), BR3.5 (el endoso que rechaza), BR3.8 (una sola cita rechazada tumba la
respuesta entera).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from typing import Any

import pytest

from untangle.policy_rag.citations.models import CitationReason, CoverageOutcome
from untangle.policy_rag.citations.verifier import Citation, verify
from untangle.policy_rag.corpus.models import Clause, ClauseRelation, IssuedPolicy, RelationKind

TENANT_ID = "testco"
AHORA = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def _poliza(**cambios: Any) -> IssuedPolicy:
    base: dict[str, Any] = {
        "tenant_id": TENANT_ID,
        "policy_number": "POL-TEST-001",
        "issuer_tenant": TENANT_ID,
        "form_id": "TCO-PAP-2026",
        "form_version": "2026.1",
        "endorsement_ids": ("TCO-PAP-2026-END-1",),
        "named_insured": {},
        "vehicles": (),
        "limits_and_deductibles": {},
        "period_start": date(2026, 1, 1),
        "period_end": date(2027, 1, 1),
    }
    return IssuedPolicy.model_validate(base | cambios)


def _clausula(clause_id: str, *, form_id: str = "TCO-PAP-2026") -> Clause:
    return Clause(
        tenant_id=TENANT_ID,
        clause_id=clause_id,
        clause_key=clause_id,
        form_id=form_id,
        form_version="2026.1",
        part="Parte A",
        language="es",
        text=f"Texto de {clause_id}.",
        is_distractor=False,
        issuer_label="Testco Mutual",
    )


def _correr(coro: Any) -> Any:
    return asyncio.run(coro)


async def _sin_relaciones(*args: Any, **kwargs: Any) -> tuple[ClauseRelation, ...]:
    return ()


def test_sin_citas_el_resultado_es_no_clause_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """BR3.4, BR5.6: no había nada que citar; es un resultado verificado, no un fallo."""
    monkeypatch.setattr(
        "untangle.policy_rag.citations.verifier.corpus.relations_into", _sin_relaciones
    )

    resultado = _correr(
        verify(TENANT_ID, policy=_poliza(), retrieved_clauses=(), citations=(), now=AHORA)
    )

    assert resultado.outcome is CoverageOutcome.NO_CLAUSE_FOUND
    assert resultado.citations == ()
    assert resultado.clause_language is None


def test_una_cita_que_no_se_recupero_se_rechaza_aunque_exista_la_clausula(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BR3.1: se rechaza aunque exista en el corpus -- aqui ni se retrieved_clauses la trae."""
    monkeypatch.setattr(
        "untangle.policy_rag.citations.verifier.corpus.relations_into", _sin_relaciones
    )
    citas = (Citation(clause_id="TCO-PAP-2026-A.LIMIT", claim="El limite es alto."),)

    resultado = _correr(
        verify(TENANT_ID, policy=_poliza(), retrieved_clauses=(), citations=citas, now=AHORA)
    )

    assert resultado.outcome is CoverageOutcome.REJECTED
    (veredicto,) = resultado.citations
    assert veredicto.reasons == (CitationReason.NOT_IN_RETRIEVED_SET,)


def test_todas_las_citas_verificadas_el_resultado_es_verified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "untangle.policy_rag.citations.verifier.corpus.relations_into", _sin_relaciones
    )
    clausula = _clausula("TCO-PAP-2026-A.LIMIT")
    citas = (
        Citation(clause_id=clausula.clause_id, claim="El limite es el que muestra la caratula."),
    )

    resultado = _correr(
        verify(
            TENANT_ID, policy=_poliza(), retrieved_clauses=(clausula,), citations=citas, now=AHORA
        )
    )

    assert resultado.outcome is CoverageOutcome.VERIFIED
    assert resultado.citations[0].outcome is CoverageOutcome.VERIFIED
    assert resultado.citations[0].reasons == ()
    assert resultado.clause_language == "es"


def test_una_cita_rechazada_tumba_la_respuesta_entera(monkeypatch: pytest.MonkeyPatch) -> None:
    """BR3.8: una sola cita sin `verified` rechaza la respuesta completa."""
    monkeypatch.setattr(
        "untangle.policy_rag.citations.verifier.corpus.relations_into", _sin_relaciones
    )
    buena = _clausula("TCO-PAP-2026-A.LIMIT")
    citas = (
        Citation(clause_id=buena.clause_id, claim="El limite es el que muestra la caratula."),
        Citation(clause_id="TCO-PAP-2026-INVENTADA", claim="Esto tambien esta cubierto."),
    )

    resultado = _correr(
        verify(TENANT_ID, policy=_poliza(), retrieved_clauses=(buena,), citations=citas, now=AHORA)
    )

    assert resultado.outcome is CoverageOutcome.REJECTED
    estados = {v.clause_id: v.outcome for v in resultado.citations}
    assert estados[buena.clause_id] is CoverageOutcome.VERIFIED
    assert estados["TCO-PAP-2026-INVENTADA"] is CoverageOutcome.REJECTED


def test_poliza_fuera_de_vigencia_rechaza_toda_cita(monkeypatch: pytest.MonkeyPatch) -> None:
    """BR3.2: la vigencia se vuelve a comprobar aqui, con independencia de la recuperacion."""
    monkeypatch.setattr(
        "untangle.policy_rag.citations.verifier.corpus.relations_into", _sin_relaciones
    )
    clausula = _clausula("TCO-PAP-2026-A.LIMIT")
    poliza_vencida = _poliza(period_start=date(2020, 1, 1), period_end=date(2021, 1, 1))
    citas = (Citation(clause_id=clausula.clause_id, claim="El limite es alto."),)

    resultado = _correr(
        verify(
            TENANT_ID,
            policy=poliza_vencida,
            retrieved_clauses=(clausula,),
            citations=citas,
            now=AHORA,
        )
    )

    assert resultado.outcome is CoverageOutcome.REJECTED
    assert CitationReason.POLICY_NOT_IN_FORCE in resultado.citations[0].reasons


async def _con_endorsement_modifies(
    tenant_id: str, *, clause_ids: Any
) -> tuple[ClauseRelation, ...]:
    return (
        ClauseRelation(
            tenant_id=TENANT_ID,
            from_clause="TCO-PAP-2026-END-1-A.LIMIT",
            relation=RelationKind.ENDORSEMENT_MODIFIES,
            to_clause="TCO-PAP-2026-A.LIMIT",
        ),
    )


def test_endoso_vigente_rechaza_la_cita_si_no_se_cita_tambien(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BR3.5, ADR-011: la cita se rechaza si la respuesta no cita tambien el endoso."""
    monkeypatch.setattr(
        "untangle.policy_rag.citations.verifier.corpus.relations_into", _con_endorsement_modifies
    )
    clausula = _clausula("TCO-PAP-2026-A.LIMIT")
    # El endoso vigente llega entre las recuperadas (asi lo deja el cierre de
    # la recuperacion, BR2.4) aunque la respuesta no lo cite: es justo lo que
    # permite reconocerlo como "vigente" y no solo como un identificador suelto.
    endoso = _clausula("TCO-PAP-2026-END-1-A.LIMIT", form_id="TCO-PAP-2026-END-1")
    citas = (Citation(clause_id=clausula.clause_id, claim="El limite es el original."),)

    resultado = _correr(
        verify(
            TENANT_ID,
            policy=_poliza(),
            retrieved_clauses=(clausula, endoso),
            citations=citas,
            now=AHORA,
        )
    )

    assert resultado.outcome is CoverageOutcome.REJECTED
    veredicto = resultado.citations[0]
    assert veredicto.amended_by == ("TCO-PAP-2026-END-1-A.LIMIT",)
    assert CitationReason.ENDORSEMENT_NOT_CITED in veredicto.reasons


def test_endoso_vigente_no_rechaza_si_la_respuesta_lo_cita_tambien(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El mismo endoso, esta vez citado tambien: la cita base pasa."""
    monkeypatch.setattr(
        "untangle.policy_rag.citations.verifier.corpus.relations_into", _con_endorsement_modifies
    )
    base = _clausula("TCO-PAP-2026-A.LIMIT")
    endoso = _clausula("TCO-PAP-2026-END-1-A.LIMIT", form_id="TCO-PAP-2026-END-1")
    citas = (
        Citation(clause_id=base.clause_id, claim="El limite es el original."),
        Citation(clause_id=endoso.clause_id, claim="El endoso sube el limite."),
    )

    resultado = _correr(
        verify(
            TENANT_ID,
            policy=_poliza(),
            retrieved_clauses=(base, endoso),
            citations=citas,
            now=AHORA,
        )
    )

    assert resultado.outcome is CoverageOutcome.VERIFIED
    veredicto_base = next(v for v in resultado.citations if v.clause_id == base.clause_id)
    assert veredicto_base.amended_by == ("TCO-PAP-2026-END-1-A.LIMIT",)
    assert veredicto_base.reasons == ()


def test_una_clausula_que_no_pertenece_a_la_poliza_se_rechaza(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BR3.2: ni el formulario base ni un endoso vigente la reconocen."""
    monkeypatch.setattr(
        "untangle.policy_rag.citations.verifier.corpus.relations_into", _sin_relaciones
    )
    ajena = _clausula("OTRA-ASEGURADORA-A.LIMIT", form_id="OTRO-FORM-2026")
    citas = (Citation(clause_id=ajena.clause_id, claim="El limite es alto."),)

    resultado = _correr(
        verify(TENANT_ID, policy=_poliza(), retrieved_clauses=(ajena,), citations=citas, now=AHORA)
    )

    assert resultado.outcome is CoverageOutcome.REJECTED
    assert CitationReason.NOT_IN_POLICY in resultado.citations[0].reasons
