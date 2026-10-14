"""`CitationVerifier.verify`: las cuatro comprobaciones exactas, sin modelo (paso 5, tanda 2).

El recorrido, por cada cita que la respuesta propone:

1. **BR3.1 — ¿se recuperó?** Un identificador que no esté en `retrieved_clauses`
   se rechaza **aunque exista en el corpus**: no se vuelve a mirar el corpus
   para saber si existe, porque hacerlo filtraría --por el motivo del rechazo--
   cuáles identificadores son reales y cuáles no.
2. **BR3.2 — cuatro comprobaciones, sin modelo.** Con la cláusula ya en mano
   (era del conjunto recuperado, así que existe): pertenece a este inquilino,
   pertenece al formulario vigente de la póliza o a uno de sus endosos
   vigentes, y la póliza sigue vigente en `now`.
3. **BR3.5 — el endoso que rechaza.** Un endoso vigente que modifica la
   cláusula citada la rechaza si la respuesta no cita también ese endoso;
   queda en `amended_by` haya pasado o no (ADR-011).
4. **BR3.3, BR3.8 — el resultado.** `verified` si no hay ninguna cita sin
   cláusula ni rechazada; `rejected` si alguna cita falla; `no_clause_found`
   si no había nada que citar. `unverifiable` no lo produce esta función: es
   el fallo del nodo tras su reintento (BR5.2), que llega en la tanda 3.

Solo `relations_into` toca la base (para BR3.5); todo lo demás es comparación
sobre los objetos ya en memoria, así que la mayoría de las reglas se prueban
sin PostgreSQL, con dobles de esa única función (CG-U8-4).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from untangle.base import Locale
from untangle.policy_rag.citations.models import CitationReason, CoverageOutcome
from untangle.policy_rag.corpus import api as corpus
from untangle.policy_rag.corpus.models import Clause, ClauseRelation, IssuedPolicy, RelationKind
from untangle.tenancy.models import TenantId


@dataclass(frozen=True)
class Citation:
    """Lo que la respuesta propone: una cláusula y lo que afirma sobre ella.

    `claim` viaja sin redactar todavía: `record_answer` es el único punto de
    salida que la redacta, justo antes de persistir (BR4.3).
    """

    clause_id: str
    claim: str


@dataclass(frozen=True)
class CitationVerdict:
    """El veredicto de una cita, antes de que `record_answer` le asigne su `check_id`."""

    clause_id: str
    claim: str
    outcome: CoverageOutcome
    reasons: tuple[CitationReason, ...]
    amended_by: tuple[str, ...]
    #: `None` cuando la cita no se pudo emparejar con una cláusula recuperada
    #: (BR3.1): no hay version que reportar de algo que no se encontró.
    clause_version: str | None


@dataclass(frozen=True)
class VerificationResult:
    """Lo que `verify` devuelve: el resultado de la respuesta entera y cada cita."""

    outcome: CoverageOutcome
    citations: tuple[CitationVerdict, ...]
    #: El idioma en que están escritas las cláusulas citadas. Vacío cuando no
    #: hubo ninguna cita que verificar (`no_clause_found`, FD-U8-1).
    clause_language: Locale | None


def _vigente(policy: IssuedPolicy, *, now: datetime) -> bool:
    return policy.period_start <= now.date() <= policy.period_end


def _pertenece_a_la_poliza(clause: Clause, policy: IssuedPolicy) -> bool:
    return clause.form_id == policy.form_id or clause.form_id in policy.endorsement_ids


def _endosos_vigentes_que_modifican(
    clause_id: str,
    *,
    relations: Sequence[ClauseRelation],
    policy: IssuedPolicy,
    retrieved_by_id: Mapping[str, Clause],
) -> tuple[str, ...]:
    """Los endosos que modifican `clause_id`, y son vigentes para esta poliza.

    "Vigente" es una propiedad del *formulario* del endoso (`Clause.form_id`
    dentro de `policy.endorsement_ids`), no del identificador de la clausula
    del endoso: `from_clause` es la clausula del endoso (BR3.5), y solo se
    puede decir si su formulario esta vigente si esa clausula esta entre las
    recuperadas -- que es justo lo que el cierre de la recuperacion garantiza
    cuando el endoso de verdad es vigente (BR2.4).
    """
    return tuple(
        sorted(
            {
                relacion.from_clause
                for relacion in relations
                if relacion.relation is RelationKind.ENDORSEMENT_MODIFIES
                and relacion.to_clause == clause_id
                and (endoso := retrieved_by_id.get(relacion.from_clause)) is not None
                and endoso.form_id in policy.endorsement_ids
            }
        )
    )


def _verify_one(  # noqa: PLR0913 -- siete datos de una comprobacion, ninguno derivable de otro
    citation: Citation,
    *,
    tenant_id: TenantId,
    policy: IssuedPolicy,
    policy_vigente: bool,
    retrieved_by_id: Mapping[str, Clause],
    relations: Sequence[ClauseRelation],
    all_cited_ids: frozenset[str],
) -> CitationVerdict:
    clausula = retrieved_by_id.get(citation.clause_id)
    if clausula is None:
        # BR3.1: no se recuperó para esta respuesta. No se vuelve a mirar el
        # corpus -- ni para decir que tampoco existe -- porque eso filtraria
        # por el motivo del rechazo cuales identificadores son reales.
        return CitationVerdict(
            clause_id=citation.clause_id,
            claim=citation.claim,
            outcome=CoverageOutcome.REJECTED,
            reasons=(CitationReason.NOT_IN_RETRIEVED_SET,),
            amended_by=(),
            clause_version=None,
        )

    reasons: list[CitationReason] = []
    if clausula.tenant_id != tenant_id:  # pragma: no cover -- RLS ya lo impide
        reasons.append(CitationReason.WRONG_TENANT)
    if not _pertenece_a_la_poliza(clausula, policy):
        reasons.append(CitationReason.NOT_IN_POLICY)
    if not policy_vigente:
        reasons.append(CitationReason.POLICY_NOT_IN_FORCE)

    amended_by = _endosos_vigentes_que_modifican(
        clausula.clause_id, relations=relations, policy=policy, retrieved_by_id=retrieved_by_id
    )
    if amended_by and not (set(amended_by) & all_cited_ids):
        # BR3.5, ADR-011: el endoso vigente rechaza la cita si la respuesta no
        # lo cita tambien. Se registra en amended_by haya pasado o no.
        reasons.append(CitationReason.ENDORSEMENT_NOT_CITED)

    outcome = CoverageOutcome.REJECTED if reasons else CoverageOutcome.VERIFIED
    return CitationVerdict(
        clause_id=citation.clause_id,
        claim=citation.claim,
        outcome=outcome,
        reasons=tuple(reasons),
        amended_by=amended_by,
        clause_version=clausula.form_version,
    )


async def verify(
    tenant_id: TenantId,
    *,
    policy: IssuedPolicy,
    retrieved_clauses: Sequence[Clause],
    citations: Sequence[Citation],
    now: datetime,
) -> VerificationResult:
    """Verifica cada cita propuesta y decide el resultado de la respuesta entera."""
    if not citations:
        # BR3.4, BR5.6: no había nada que citar. Es un resultado verificado, no
        # un fallo, y no se cita una clausula general para disfrazarlo.
        return VerificationResult(
            outcome=CoverageOutcome.NO_CLAUSE_FOUND, citations=(), clause_language=None
        )

    retrieved_by_id = {clausula.clause_id: clausula for clausula in retrieved_clauses}
    todas_las_citadas = frozenset(citation.clause_id for citation in citations)
    relaciones = await corpus.relations_into(tenant_id, clause_ids=tuple(todas_las_citadas))
    policy_vigente = _vigente(policy, now=now)

    veredictos = tuple(
        _verify_one(
            citation,
            tenant_id=tenant_id,
            policy=policy,
            policy_vigente=policy_vigente,
            retrieved_by_id=retrieved_by_id,
            relations=relaciones,
            all_cited_ids=todas_las_citadas,
        )
        for citation in citations
    )

    outcome = (
        CoverageOutcome.VERIFIED
        if all(v.outcome is CoverageOutcome.VERIFIED for v in veredictos)
        else CoverageOutcome.REJECTED
    )
    idiomas = {
        retrieved_by_id[v.clause_id].language for v in veredictos if v.clause_id in retrieved_by_id
    }
    clause_language = next(iter(idiomas)) if len(idiomas) == 1 else None
    return VerificationResult(
        outcome=outcome, citations=veredictos, clause_language=clause_language
    )


__all__ = ["Citation", "CitationVerdict", "VerificationResult", "verify"]
