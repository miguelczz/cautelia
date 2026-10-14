"""La superficie pública de `policy_rag.citations`: verificar y registrar (C-18).

Lo que el nodo `policy_verification` (tanda 3) consumirá de aquí, y lo que las
pruebas de esta tanda ejercitan ya: `verify` decide el resultado de una
respuesta de cobertura sin llamar a ningún modelo (BR3.1 a BR3.8); `record_answer`
lo persiste con clave idempotente, redactado antes de escribir (BR4.1 a BR4.3).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime

from untangle.base import Locale
from untangle.compliance.redaction.api import redact
from untangle.policy_rag.citations import repository
from untangle.policy_rag.citations.models import (
    CitationCheck,
    CitationReason,
    CoverageAnswer,
    CoverageOutcome,
)
from untangle.policy_rag.citations.verifier import (
    Citation,
    CitationVerdict,
    VerificationResult,
    verify,
)
from untangle.tenancy.models import TenantId

#: Cuantos caracteres hexadecimales de la huella entran en cada identificador
#: derivado, igual que `orchestration.nodes.decision.node._DIGEST_LENGTH`.
_DIGEST_LENGTH = 32


def _digest(*parts: str) -> str:
    huella = hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()
    return huella[:_DIGEST_LENGTH]


def _idempotency_key(*, case_id: str, turn_id: str) -> str:
    """Derivada del caso y del turno (BR4.2): reanudar el grafo da la misma clave."""
    return f"coverage-{_digest(case_id, turn_id)}"


def _check_id(*, idempotency_key: str, clause_id: str) -> str:
    """Determinista por respuesta y cláusula: la misma cita da el mismo identificador."""
    return f"citck-{_digest(idempotency_key, clause_id)}"


async def record_answer(  # noqa: PLR0913 -- siete datos de una respuesta, ninguno derivable de otro
    tenant_id: TenantId,
    *,
    case_id: str,
    turn_id: str,
    question: str,
    verification: VerificationResult,
    answer_language: Locale,
    now: datetime,
) -> CoverageAnswer:
    """Persiste la respuesta ya verificada, redactada, con clave idempotente (BR4.1 a BR4.3).

    Escribe el verificador, no el nodo: LangGraph reejecuta el nodo completo al
    reanudar tras `interrupt()`, así que el nodo no puede ser quien escribe
    (ADR-003). La segunda llamada con el mismo caso y turno devuelve la
    respuesta que ya quedó guardada, sin volver a redactar ni a insertar nada.
    """
    clave = _idempotency_key(case_id=case_id, turn_id=turn_id)
    existente = await repository.find_answer_by_idempotency_key(tenant_id, idempotency_key=clave)
    if existente is not None:
        return existente

    pregunta_redactada = str(redact(question, language=answer_language))
    checks: list[CitationCheck] = []
    for veredicto in verification.citations:
        checks.append(
            _build_check(
                veredicto,
                tenant_id=tenant_id,
                case_id=case_id,
                idempotency_key=clave,
                answer_language=answer_language,
                now=now,
            )
        )

    respuesta = CoverageAnswer(
        answer_id=f"ans-{_digest(case_id, turn_id)}",
        tenant_id=tenant_id,
        case_id=case_id,
        turn_id=turn_id,
        idempotency_key=clave,
        question_redacted=pregunta_redactada,
        outcome=verification.outcome,
        citation_check_ids=tuple(check.check_id for check in checks),
        answer_language=answer_language,
        clause_language=verification.clause_language,
        created_at=now,
    )
    return await repository.save_answer_with_checks(respuesta, checks=checks)


def _build_check(  # noqa: PLR0913 -- seis datos de una comprobacion, ninguno derivable de otro
    veredicto: CitationVerdict,
    *,
    tenant_id: TenantId,
    case_id: str,
    idempotency_key: str,
    answer_language: Locale,
    now: datetime,
) -> CitationCheck:
    return CitationCheck(
        check_id=_check_id(idempotency_key=idempotency_key, clause_id=veredicto.clause_id),
        tenant_id=tenant_id,
        case_id=case_id,
        clause_id=veredicto.clause_id,
        clause_version=veredicto.clause_version,
        claim_redacted=str(redact(veredicto.claim, language=answer_language)),
        outcome=veredicto.outcome,
        reasons=veredicto.reasons,
        amended_by=veredicto.amended_by,
        checked_at=now,
    )


async def answers_for(
    tenant_id: TenantId, case_id: str
) -> tuple[tuple[CoverageAnswer, tuple[CitationCheck, ...]], ...]:
    """Las respuestas de cobertura de un caso, con sus comprobaciones (C-18).

    Enmienda aditiva del 2026-09-28, pedida por U14: la bandeja muestra las
    clausulas citadas al abrir un caso, y esta unidad solo sabia buscar por clave
    de idempotencia --lo que el grafo necesita al reanudar-- y no por caso.

    El `outcome` viaja tal cual porque la bandeja tiene que distinguir "no
    encuentro una clausula que lo cubra" de "no pude verificar" con etiquetas
    distintas (BR2.5): son dos valores distintos en el estado, en la traza y en el
    reporte de evaluaciones, y colapsarlos en la pantalla contaminaria con fallos
    de infraestructura una respuesta que si se verifico.
    """
    return await repository.answers_for(tenant_id, case_id)


async def verified_citations_since(
    tenant_id: TenantId, *, clause_ids: Sequence[str], since: datetime
) -> dict[str, int]:
    """Cuantas veces se cito cada clausula, verificada, desde un instante (fase 2)."""
    return await repository.verified_citations_since(tenant_id, clause_ids=clause_ids, since=since)


__all__ = [
    "Citation",
    "CitationCheck",
    "CitationReason",
    "CitationVerdict",
    "CoverageAnswer",
    "CoverageOutcome",
    "VerificationResult",
    "answers_for",
    "record_answer",
    "verified_citations_since",
    "verify",
]
