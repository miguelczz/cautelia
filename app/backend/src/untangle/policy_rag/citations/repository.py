"""Donde se guardan las comprobaciones y la respuesta de cobertura (BR4.1, BR4.2).

**Ninguna conexión propia**, igual que `rules/repository.py`: toda consulta pasa
por el punto único de sesión de U2, con la aseguradora ya fijada.

**La escritura es idempotente por `idempotency_key`** (ADR-003): el nodo
`policy_verification` se puede volver a ejecutar entero al reanudar tras
`interrupt()`, y guardar dos veces la misma respuesta no puede dejar dos filas.
Las comprobaciones y la respuesta se escriben en **una sola transacción**: una
respuesta sin sus comprobaciones, o comprobaciones sin la respuesta que las
agrupa, son las dos mitades rotas del mismo fallo.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime

from untangle.policy_rag.citations.models import CitationCheck, CoverageAnswer
from untangle.tenancy import api as tenancy
from untangle.tenancy.models import TenantId

_INSERTAR_COMPROBACION = """
    INSERT INTO citation_checks
        (check_id, tenant_id, case_id, clause_id, clause_version, claim_redacted, outcome,
         reasons, amended_by, checked_at)
    VALUES
        (:check_id, :tenant_id, :case_id, :clause_id, :clause_version, :claim_redacted, :outcome,
         CAST(:reasons AS jsonb), CAST(:amended_by AS jsonb), :checked_at)
    ON CONFLICT (check_id) DO NOTHING
"""

_INSERTAR_RESPUESTA = """
    INSERT INTO coverage_answers
        (answer_id, tenant_id, case_id, turn_id, idempotency_key, question_redacted, outcome,
         citation_check_ids, answer_language, clause_language, created_at)
    VALUES
        (:answer_id, :tenant_id, :case_id, :turn_id, :idempotency_key, :question_redacted,
         :outcome, CAST(:citation_check_ids AS jsonb), :answer_language, :clause_language,
         :created_at)
    ON CONFLICT (idempotency_key) DO NOTHING
    RETURNING answer_id
"""

_LEER_RESPUESTA_POR_CLAVE = """
    SELECT answer_id, tenant_id, case_id, turn_id, idempotency_key, question_redacted, outcome,
           citation_check_ids, answer_language, clause_language, created_at
    FROM coverage_answers
    WHERE tenant_id = :tenant_id AND idempotency_key = :idempotency_key
"""


#: Las respuestas de cobertura de un caso, con sus comprobaciones, para la vista de
#: la bandeja (enmienda aditiva a C-18, 2026-09-28).
#:
#: **El `outcome` es lo que separa "no encuentro una clausula que lo cubra" de "no
#: pude verificar"**, que son dos valores distintos desde que esta tabla nacio y que
#: la bandeja tiene que mostrar con etiquetas distintas (BR2.5). Colapsarlos en la
#: pantalla contaminaria con fallos de infraestructura una respuesta que si se
#: verifico, que es justo lo que la convencion 8c del equipo prohibe.
_LEER_RESPUESTAS_DEL_CASO = """
    SELECT answer_id, tenant_id, case_id, turn_id, idempotency_key, question_redacted, outcome,
           citation_check_ids, answer_language, clause_language, created_at
    FROM coverage_answers
    WHERE tenant_id = :tenant_id AND case_id = :case_id
    ORDER BY created_at, answer_id
"""

#: Las comprobaciones de varias respuestas en **una** consulta. Una por respuesta
#: multiplicaria idas a la base en la vista que declara el conteo como objetivo.
_LEER_COMPROBACIONES = """
    SELECT check_id, tenant_id, case_id, clause_id, clause_version, claim_redacted, outcome,
           reasons, amended_by, checked_at
    FROM citation_checks
    WHERE tenant_id = :tenant_id AND check_id = ANY(:check_ids)
"""


def _amended_by_json(check: CitationCheck) -> str | None:
    return None if check.amended_by is None else json.dumps(list(check.amended_by))


async def find_answer_by_idempotency_key(
    tenant_id: TenantId, *, idempotency_key: str
) -> CoverageAnswer | None:
    """La respuesta ya guardada con esa clave, o nada (ADR-003)."""
    async with tenancy.session_for(tenant_id) as sesion:
        fila = await tenancy.fetch_one(
            sesion, _LEER_RESPUESTA_POR_CLAVE, tenant_id=tenant_id, idempotency_key=idempotency_key
        )
    return CoverageAnswer.model_validate(dict(fila)) if fila is not None else None


async def answers_for(
    tenant_id: TenantId, case_id: str
) -> tuple[tuple[CoverageAnswer, tuple[CitationCheck, ...]], ...]:
    """Las respuestas de cobertura de un caso, cada una con sus comprobaciones.

    Lectura anadida por U14: la bandeja muestra las clausulas citadas y la razon
    de la respuesta, y hasta hoy esta unidad solo sabia buscar por clave de
    idempotencia --que es lo que el grafo necesita al reanudar-- y no por caso,
    que es lo que necesita quien lo abre.

    Dos consultas y no una por respuesta: las comprobaciones de todas se leen
    juntas y se reparten en memoria.
    """
    async with tenancy.session_for(tenant_id) as sesion:
        filas = await tenancy.fetch_all(
            sesion, _LEER_RESPUESTAS_DEL_CASO, tenant_id=tenant_id, case_id=case_id
        )
        respuestas = [CoverageAnswer.model_validate(dict(fila)) for fila in filas]
        identificadores = [
            check_id for respuesta in respuestas for check_id in respuesta.citation_check_ids
        ]
        comprobaciones: dict[str, CitationCheck] = {}
        if identificadores:
            crudas = await tenancy.fetch_all(
                sesion,
                _LEER_COMPROBACIONES,
                tenant_id=tenant_id,
                check_ids=identificadores,
            )
            comprobaciones = {
                str(fila["check_id"]): CitationCheck.model_validate(dict(fila)) for fila in crudas
            }

    return tuple(
        (
            respuesta,
            tuple(
                comprobaciones[check_id]
                for check_id in respuesta.citation_check_ids
                if check_id in comprobaciones
            ),
        )
        for respuesta in respuestas
    )


async def save_answer_with_checks(
    answer: CoverageAnswer, *, checks: Sequence[CitationCheck]
) -> CoverageAnswer:
    """Guarda la respuesta y sus comprobaciones en una transacción, o devuelve la que ya había.

    `ON CONFLICT ... DO NOTHING` sobre `idempotency_key` es lo que hace que
    reanudar el grafo tras `interrupt()` no duplique: la segunda escritura con
    la misma clave no inserta nada, y este método relee y devuelve la primera
    (mismo patrón que `rules.repository.save_evaluation`, BR4.2).
    """
    async with tenancy.session_for(answer.tenant_id) as sesion:
        for check in checks:
            await tenancy.execute_sql(
                sesion,
                _INSERTAR_COMPROBACION,
                check_id=check.check_id,
                tenant_id=check.tenant_id,
                case_id=check.case_id,
                clause_id=check.clause_id,
                clause_version=check.clause_version,
                claim_redacted=check.claim_redacted,
                outcome=check.outcome.value,
                reasons=json.dumps([razon.value for razon in check.reasons]),
                amended_by=_amended_by_json(check),
                checked_at=check.checked_at,
            )
        nueva = await tenancy.fetch_one(
            sesion,
            _INSERTAR_RESPUESTA,
            answer_id=answer.answer_id,
            tenant_id=answer.tenant_id,
            case_id=answer.case_id,
            turn_id=answer.turn_id,
            idempotency_key=answer.idempotency_key,
            question_redacted=answer.question_redacted,
            outcome=answer.outcome.value,
            citation_check_ids=json.dumps(list(answer.citation_check_ids)),
            answer_language=answer.answer_language,
            clause_language=answer.clause_language,
            created_at=answer.created_at,
        )

    if nueva is not None:
        return answer

    guardada = await find_answer_by_idempotency_key(
        answer.tenant_id, idempotency_key=answer.idempotency_key
    )
    if guardada is None:  # pragma: no cover -- el conflicto de la insercion garantiza que existe
        msg = f"la respuesta '{answer.idempotency_key}' choco al guardarse y no se pudo releer"
        raise LookupError(msg)  # pragma: no cover
    return guardada


_CITAS_DESDE = """
    SELECT clause_id, COUNT(*) AS veces
    FROM citation_checks
    WHERE tenant_id = :tenant_id AND outcome = 'verified' AND checked_at >= :desde
      AND clause_id = ANY(:clause_ids)
    GROUP BY clause_id
"""


async def verified_citations_since(
    tenant_id: TenantId, *, clause_ids: Sequence[str], since: datetime
) -> dict[str, int]:
    """Cuantas veces se cito cada clausula, verificada, desde un instante.

    Es un recuento agregado: no dice de que caso ni de quien (fase 2, 2026-10-08).
    """
    if not clause_ids:
        return {}
    async with tenancy.session_for(tenant_id) as sesion:
        filas = await tenancy.fetch_all(
            sesion, _CITAS_DESDE, tenant_id=tenant_id, clause_ids=list(clause_ids), desde=since
        )
    return {str(fila["clause_id"]): int(fila["veces"]) for fila in filas}
