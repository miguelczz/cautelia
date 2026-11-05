"""Lo que el codigo comprueba de la salida del modelo antes de aceptarla como decision (paso 6).

El modelo propone y el codigo decide. En este orden, y la primera que falla detiene el intento
con su motivo (`ErrorKind`); nunca se corrige un texto a mano para que pase:

1. **La accion** es de las que ofrece ese tipo de aseguradora (`actions.allowed_for`, A3).
2. **Hay razones**: una decision que no se explica no se firma.
3. **El idioma** del texto es el del caso.
4. **Las citas** pasan por el verificador exacto (existe, es de la aseguradora y de la poliza,
   esta vigente, se recupero). Una cita que no pasa **se quita** del texto y de las razones
   (A4); si la decision queda sin una sola cita verificada, una aprobacion o un rechazo no se
   sostiene y el intento falla. La excepcion es rechazar porque la poliza no esta vigente: ahi no
   hay clausula que citar, y el motivo es un hecho del registro.
5. **La guardia de salida** deja pasar el texto tal cual, con la clave `adjuster.decision` que
   exime solo las promesas de cobertura y los montos. Si interviene --culpa, consejo legal,
   revelacion de configuracion, afirmar ser una persona-- el intento falla: la frase generica que
   la guardia pondria en su lugar no es una decision.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from untangle import language as language_detection
from untangle import observability
from untangle.adjuster.errors import ErrorKind
from untangle.adjuster.schema import AdjusterDecision, DecisionReason
from untangle.base import Locale
from untangle.compliance.controls import api as controls
from untangle.inbox import actions
from untangle.policy_rag.citations import api as citations
from untangle.policy_rag.corpus.models import Clause, IssuedPolicy
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import TenantId

#: La clave con la que la decision pasa por la guardia de salida. Exime solo promesas de
#: cobertura y montos (A7): es la decision misma lo que puede decir «cubre» y nombrar cifras.
GUARD_SOURCE_KEY = "adjuster.decision"


class DecisionRejected(Exception):  # noqa: N818 -- no es un error: es la conclusion de la validacion
    """El intento no llego a ser una decision. Lleva solo su motivo, nunca el texto."""

    def __init__(self, kind: ErrorKind) -> None:
        self.kind = kind
        super().__init__(kind.value)


@dataclass(frozen=True)
class CaseFacts:
    """Lo del caso que la validacion necesita, y nada mas."""

    tenant_id: TenantId
    case_id: str
    case_number: str
    language: Locale
    policy: IssuedPolicy | None
    retrieved: tuple[Clause, ...]
    now: datetime


@dataclass(frozen=True)
class ValidatedDecision:
    action: actions.InboxAction
    headline: str
    explanation: str
    reasons: tuple[DecisionReason, ...]
    uncertainties: tuple[str, ...]
    #: Las clausulas que la decision cita **y** el verificador dio por buenas, en el orden citado.
    verified_clauses: tuple[Clause, ...]


_SEPARADOR_AL_ABRIR = re.compile(r"([(\[])[ \t]*[,;][ \t]*")
_SEPARADOR_AL_CERRAR = re.compile(r"[ \t]*[,;][ \t]*([)\]])")
_PARENTESIS_VACIOS = re.compile(r"\([ \t]*\)|\[[ \t]*\]")
_ESPACIOS = re.compile(r"[ \t]{2,}")
_ESPACIO_ANTES_DE_PUNTUACION = re.compile(r"[ \t]+([.,;:!?)\]])")
_ESPACIO_DESPUES_DE_ABRIR = re.compile(r"([(\[])[ \t]+")


def remove_clause_ids(text: str, ids: Iterable[str]) -> str:
    """El texto sin los identificadores dados, con sus parentesis y corchetes si quedan vacios.

    Un identificador es una palabra entera: `SM-X.A` no sale de dentro de `SM-X.AB`, y el punto
    que cierra la oracion no es parte de el. Si ninguno aparece, el texto vuelve intacto.
    """
    resultado = text
    for identificador in sorted(set(ids), key=len, reverse=True):
        resultado = re.sub(rf"(?<![\w.-]){re.escape(identificador)}(?![\w-]|\.\w)", "", resultado)
    if resultado == text:
        return text
    resultado = _SEPARADOR_AL_ABRIR.sub(r"\1", resultado)
    resultado = _SEPARADOR_AL_CERRAR.sub(r"\1", resultado)
    resultado = _PARENTESIS_VACIOS.sub("", resultado)
    resultado = _ESPACIOS.sub(" ", resultado)
    resultado = _ESPACIO_ANTES_DE_PUNTUACION.sub(r"\1", resultado)
    resultado = _ESPACIO_DESPUES_DE_ABRIR.sub(r"\1", resultado)
    return resultado.strip()


def _ordered_unique(ids: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(ids))


def _check_language(texts: Sequence[str], expected: Locale) -> None:
    for texto in texts:
        medido = language_detection.measured(texto)
        if medido is not None and medido != expected:
            raise DecisionRejected(ErrorKind.WRONG_LANGUAGE)


async def _verified_ids(decision: AdjusterDecision, facts: CaseFacts) -> tuple[str, ...]:
    """De las clausulas que cita la decision, las que el verificador exacto da por buenas."""
    citadas = _ordered_unique(
        (*decision.cited_clause_ids, *(i for r in decision.reasons for i in r.clause_ids))
    )
    if not citadas or facts.policy is None:
        return ()

    def _afirmacion(identificador: str) -> str:
        razon = next((r.text for r in decision.reasons if identificador in r.clause_ids), None)
        return razon or decision.headline

    resultado = await citations.verify(
        facts.tenant_id,
        policy=facts.policy,
        retrieved_clauses=facts.retrieved,
        citations=[citations.Citation(clause_id=i, claim=_afirmacion(i)) for i in citadas],
        now=facts.now,
    )
    buenas = {
        v.clause_id for v in resultado.citations if v.outcome is citations.CoverageOutcome.VERIFIED
    }
    return tuple(i for i in citadas if i in buenas)


def _policy_not_in_force(facts: CaseFacts) -> bool:
    poliza = facts.policy
    if poliza is None:
        return False
    hoy = facts.now.date()
    return not poliza.period_start <= hoy <= poliza.period_end


async def validate(decision: AdjusterDecision, facts: CaseFacts) -> ValidatedDecision:
    """La salida del modelo como decision, o `DecisionRejected` con su motivo."""
    permitidas = actions.allowed_for(tenancy_config.require(facts.tenant_id))
    if decision.action not in permitidas:
        raise DecisionRejected(ErrorKind.ACTION_NOT_ALLOWED)
    if not decision.reasons:
        raise DecisionRejected(ErrorKind.NO_REASONS)

    _check_language(
        [decision.headline, decision.explanation, *(r.text for r in decision.reasons)],
        facts.language,
    )

    verificadas = await _verified_ids(decision, facts)
    if (
        decision.action is not actions.InboxAction.MARK_SENT
        and not verificadas
        and not (decision.action is actions.InboxAction.REJECT and _policy_not_in_force(facts))
    ):
        raise DecisionRejected(ErrorKind.NO_VERIFIED_CITATION)

    citadas = _ordered_unique(
        (*decision.cited_clause_ids, *(i for r in decision.reasons for i in r.clause_ids))
    )
    quitar = [i for i in citadas if i not in verificadas]
    headline = " ".join(remove_clause_ids(decision.headline, quitar).split())
    explanation = remove_clause_ids(decision.explanation, quitar)
    reasons = tuple(
        DecisionReason(
            text=texto,
            clause_ids=tuple(i for i in razon.clause_ids if i in verificadas),
        )
        for razon in decision.reasons
        if (texto := remove_clause_ids(razon.text, quitar))
    )
    uncertainties = tuple(
        texto for u in decision.uncertainties if (texto := remove_clause_ids(u, quitar))
    )
    if not headline or not explanation or not reasons:
        raise DecisionRejected(ErrorKind.NO_REASONS)

    await _guard([headline, explanation, *(r.text for r in reasons), *uncertainties], facts=facts)

    por_id = {c.clause_id: c for c in facts.retrieved}
    return ValidatedDecision(
        action=decision.action,
        headline=headline,
        explanation=explanation,
        reasons=reasons,
        uncertainties=uncertainties,
        verified_clauses=tuple(por_id[i] for i in verificadas if i in por_id),
    )


async def _guard(texts: Sequence[str], *, facts: CaseFacts) -> None:
    for texto in texts:
        resultado = await controls.guard_output(
            texto,
            tenant_id=facts.tenant_id,
            language=facts.language,
            case_id=facts.case_id,
            case_number=facts.case_number,
            source_key=GUARD_SOURCE_KEY,
        )
        if not resultado.unchanged:
            observability.emit(
                "adjuster.guard_blocked",
                tenant_id=facts.tenant_id,
                case_id=facts.case_id,
                categories=[str(i.category) for i in resultado.interventions],
                patterns=[str(i.pattern_id) for i in resultado.interventions],
            )
            raise DecisionRejected(ErrorKind.GUARD_BLOCKED)
