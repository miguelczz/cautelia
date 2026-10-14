"""Las dos entidades que escribe `CitationVerifier`, y su vocabulario cerrado (BR3.3, BR4.4).

`CitationCheck` y `CoverageAnswer` son las dos únicas entidades de `entities.md`
que este paquete declara: las cinco del corpus (`PolicyForm`, `Clause`,
`IssuedPolicy`, `ClauseIndexEntry`, `ClauseRelation`) son de `policy_rag.corpus`
y este módulo las lee, nunca las redeclara.

**Sin clave foránea hacia `clauses`, a propósito.** `CitationCheck.clause_id`
no referencia `clauses.clause_id`: una cita inventada apunta a una cláusula que
no existe, y ese es justamente el caso que hay que poder registrar (AC2.2.1,
BR3.1). La migración de tanda 1 (`u8_policy_0001_corpus_tables`) ya declaró la
tabla así, sin esa llave.

**Sin `case_record` importado.** `policy_rag` está por debajo de `case_record`
en el contrato de capas de `import-linter` (convención 5 del equipo): `case_id`
y `turn_id` viajan como `str`, el mismo patrón que usa
`orchestration.nodes.decision.node.DecisionNodeInput` con el motor de reglas.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from untangle.base import Frozen, Locale
from untangle.tenancy.models import TENANT_ID_PATTERN, TenantId


class CoverageOutcome(StrEnum):
    """El conjunto cerrado de cuatro valores (BR3.3, C-18).

    `NO_CLAUSE_FOUND` es un resultado verificado: se buscó y la póliza no dice
    nada. `UNVERIFIABLE` es un fallo: no se pudo buscar o comprobar. Los dos se
    parecen en pantalla y son opuestos en el reporte (BR3.4); no se colapsan
    nunca. Esta unidad, en esta tanda, solo produce los tres primeros --
    `UNVERIFIABLE` lo declara el nodo (tanda 3) cuando la recuperación falla
    tras su reintento (BR5.2).
    """

    VERIFIED = "verified"
    REJECTED = "rejected"
    NO_CLAUSE_FOUND = "no_clause_found"
    UNVERIFIABLE = "unverifiable"


class CitationReason(StrEnum):
    """Los motivos de una comprobación, como claves de un conjunto cerrado (BR4.4).

    Prosa libre no se puede agrupar: el reporte por caso y el diff contra la
    línea base agrupan por esta clave, y una redacción distinta por caso
    rompería esa cuenta.
    """

    #: BR3.1: el identificador no está en el conjunto recuperado para esta
    #: respuesta -- exista o no en el corpus, que aquí no se llega a mirar.
    NOT_IN_RETRIEVED_SET = "not_in_retrieved_set"
    #: BR3.2, defensa: la cláusula encontrada no es de este inquilino.
    WRONG_TENANT = "wrong_tenant"
    #: BR3.2: no pertenece al formulario vigente de la póliza ni a uno de sus
    #: endosos vigentes.
    NOT_IN_POLICY = "not_in_policy"
    #: BR3.2: la póliza no está vigente en el momento de comprobar.
    POLICY_NOT_IN_FORCE = "policy_not_in_force"
    #: BR3.5, ADR-011: un endoso vigente modifica la cláusula citada y la
    #: respuesta no cita también ese endoso.
    ENDORSEMENT_NOT_CITED = "endorsement_not_cited"


class CitationCheck(Frozen):
    """La comprobación de una cita contra el corpus (tabla `citation_checks`)."""

    check_id: str = Field(min_length=1)
    tenant_id: TenantId = Field(pattern=TENANT_ID_PATTERN)
    case_id: str = Field(min_length=1)
    clause_id: str = Field(min_length=1)
    clause_version: str | None = None
    claim_redacted: str
    outcome: CoverageOutcome
    reasons: tuple[CitationReason, ...] = ()
    amended_by: tuple[str, ...] | None = None
    checked_at: datetime


class CoverageAnswer(Frozen):
    """La respuesta de cobertura de un turno (tabla `coverage_answers`, BR4.1, BR4.2)."""

    answer_id: str = Field(min_length=1)
    tenant_id: TenantId = Field(pattern=TENANT_ID_PATTERN)
    case_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    question_redacted: str
    outcome: CoverageOutcome
    citation_check_ids: tuple[str, ...] = ()
    answer_language: Locale
    #: El idioma de las cláusulas citadas. Vacío cuando `outcome` es
    #: `no_clause_found`: no hay ninguna cláusula de la que hablar (FD-U8-1).
    clause_language: Locale | None = None
    created_at: datetime
