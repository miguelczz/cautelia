"""Pruebas de `policy_rag.citations.api.record_answer`, sin base de datos.

`repository` se sustituye por un almacen en memoria (CG-U8-4): lo que se
prueba aqui es la redaccion antes de persistir (BR4.3) y la idempotencia por
clave (BR4.2), no la SQL real -- esa vive en
`tests/integration/u8/test_citations.py`, con PostgreSQL.

Necesita los modelos de spaCy instalados (`uv sync --extra models`): `redact()`
es el unico punto de salida y no hay doble que lo sustituya, por la misma razon
que ninguna prueba de U3 lo sustituye tampoco.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from untangle.policy_rag.citations import api as citations
from untangle.policy_rag.citations.models import CitationCheck, CoverageAnswer, CoverageOutcome
from untangle.policy_rag.citations.verifier import CitationVerdict, VerificationResult

TENANT_ID = "testco"
AHORA = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


class AlmacenDePrueba:
    """Un doble de `repository`: guarda en memoria, con la misma forma de conflicto por clave."""

    def __init__(self) -> None:
        self.respuestas: dict[str, CoverageAnswer] = {}
        self.comprobaciones: list[CitationCheck] = []
        self.llamadas_a_guardar = 0

    async def find_answer_by_idempotency_key(
        self, tenant_id: str, *, idempotency_key: str
    ) -> CoverageAnswer | None:
        return self.respuestas.get(idempotency_key)

    async def save_answer_with_checks(
        self, answer: CoverageAnswer, *, checks: list[CitationCheck]
    ) -> CoverageAnswer:
        self.llamadas_a_guardar += 1
        if answer.idempotency_key in self.respuestas:
            return self.respuestas[answer.idempotency_key]
        self.respuestas[answer.idempotency_key] = answer
        self.comprobaciones.extend(checks)
        return answer


def _correr(coro: Any) -> Any:
    return asyncio.run(coro)


def _verificacion(
    *, clause_id: str = "TCO-PAP-2026-A.LIMIT", claim: str = "El limite es alto."
) -> VerificationResult:
    return VerificationResult(
        outcome=CoverageOutcome.VERIFIED,
        citations=(
            CitationVerdict(
                clause_id=clause_id,
                claim=claim,
                outcome=CoverageOutcome.VERIFIED,
                reasons=(),
                amended_by=(),
                clause_version="2026.1",
            ),
        ),
        clause_language="es",
    )


def test_la_pregunta_y_la_afirmacion_se_guardan_redactadas(monkeypatch: pytest.MonkeyPatch) -> None:
    """BR4.3, SEC-U8.7: se persiste redactado, no solo se exporta redactado."""
    almacen = AlmacenDePrueba()
    monkeypatch.setattr(citations, "repository", almacen)

    respuesta = _correr(
        citations.record_answer(
            TENANT_ID,
            case_id="caso-1",
            turn_id="turno-1",
            question="Mi cedula es 1002003000, ¿que cubre la parte A?",
            verification=_verificacion(claim="Cubre a la persona 1002003000."),
            answer_language="es",
            now=AHORA,
        )
    )

    assert "1002003000" not in respuesta.question_redacted
    assert all("1002003000" not in c.claim_redacted for c in almacen.comprobaciones)


def test_reanudar_con_el_mismo_caso_y_turno_no_duplica(monkeypatch: pytest.MonkeyPatch) -> None:
    """BR4.2, REL-U8.5: la segunda escritura con la misma clave no inserta nada nuevo."""
    almacen = AlmacenDePrueba()
    monkeypatch.setattr(citations, "repository", almacen)

    primera = _correr(
        citations.record_answer(
            TENANT_ID,
            case_id="caso-1",
            turn_id="turno-1",
            question="¿Que cubre la parte A?",
            verification=_verificacion(),
            answer_language="es",
            now=AHORA,
        )
    )
    segunda = _correr(
        citations.record_answer(
            TENANT_ID,
            case_id="caso-1",
            turn_id="turno-1",
            question="¿Que cubre la parte A?",
            verification=_verificacion(),
            answer_language="es",
            now=AHORA,
        )
    )

    assert primera.answer_id == segunda.answer_id
    assert primera.idempotency_key == segunda.idempotency_key
    assert len(almacen.respuestas) == 1
    # `find_answer_by_idempotency_key` corta la segunda llamada antes de volver
    # a redactar y a intentar guardar (BR4.2): el almacen solo ve una escritura.
    assert almacen.llamadas_a_guardar == 1


def test_un_turno_distinto_produce_una_clave_distinta(monkeypatch: pytest.MonkeyPatch) -> None:
    almacen = AlmacenDePrueba()
    monkeypatch.setattr(citations, "repository", almacen)

    primera = _correr(
        citations.record_answer(
            TENANT_ID,
            case_id="caso-1",
            turn_id="turno-1",
            question="¿Que cubre la parte A?",
            verification=_verificacion(),
            answer_language="es",
            now=AHORA,
        )
    )
    segunda = _correr(
        citations.record_answer(
            TENANT_ID,
            case_id="caso-1",
            turn_id="turno-2",
            question="¿Y la parte B?",
            verification=_verificacion(),
            answer_language="es",
            now=AHORA,
        )
    )

    assert primera.idempotency_key != segunda.idempotency_key
    assert len(almacen.respuestas) == 2


def test_sin_citas_se_guarda_no_clause_found_sin_comprobaciones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    almacen = AlmacenDePrueba()
    monkeypatch.setattr(citations, "repository", almacen)
    verificacion = VerificationResult(
        outcome=CoverageOutcome.NO_CLAUSE_FOUND, citations=(), clause_language=None
    )

    respuesta = _correr(
        citations.record_answer(
            TENANT_ID,
            case_id="caso-1",
            turn_id="turno-1",
            question="¿Cubren terremotos?",
            verification=verificacion,
            answer_language="es",
            now=AHORA,
        )
    )

    assert respuesta.outcome is CoverageOutcome.NO_CLAUSE_FOUND
    assert respuesta.citation_check_ids == ()
    assert respuesta.clause_language is None
    assert almacen.comprobaciones == []
