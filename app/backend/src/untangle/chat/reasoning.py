"""El pensamiento de la agente sobre el caso de esta conversacion (2026-10-09).

Miguel pidio un boton para "ver el pensamiento de Catalina". La traza tecnica del
turno no servia: solo tiene tiempos y costos de nodos, y en una consulta la
respuesta se arma en el ritmo de fondo, que no deja nodos en ella. Lo que si se
puede mostrar, y es lo que una persona entiende como pensamiento, es lo que el caso
ya guarda: que tipo de conversacion entendio, que poliza confirmo, que datos anoto,
y por cada pregunta de cobertura que clausulas cito, si las verifico y que dice cada
una segun la agente. Todo es del propio caso del navegador: la ruta lo busca por la
conversacion viva, como el estado del caso.
"""

from __future__ import annotations

from untangle.base import Frozen, Locale
from untangle.case_record import api as casos
from untangle.case_record.crypto import Cipher
from untangle.chat import case_status, citation
from untangle.chat import session as chat
from untangle.policy_rag.citations import api as citas
from untangle.policy_rag.citations.models import CoverageOutcome


class ReasoningClause(Frozen):
    """Una clausula que la agente cito, con la parte de la poliza donde esta."""

    clause_id: str
    part: str
    verified: bool
    #: Lo que la agente entendio que dice la clausula sobre la pregunta, ya redactado.
    claim: str


class ReasoningAnswer(Frozen):
    """Una pregunta de cobertura y como se respondio."""

    question: str
    #: `verified`, `no_clause_found`, `unverifiable` o `rejected`.
    outcome: str
    clauses: tuple[ReasoningClause, ...] = ()


class ChatReasoning(Frozen):
    """Lo que la pagina dibuja como el pensamiento de la agente."""

    case_number: str
    record_type: str
    state: str
    policy_ref: str | None
    derivation_reason: str | None
    fields: tuple[case_status.FieldProgress, ...]
    answers: tuple[ReasoningAnswer, ...]


async def for_session(
    session_: chat.ChatSession, *, language: Locale, cipher: Cipher
) -> ChatReasoning | None:
    """El pensamiento sobre el caso de esta conversacion, o `None` si no hay caso.

    Trae **lo que quedo anotado** en cada dato (decision de Miguel del 2026-10-11):
    es el caso de quien pregunta, resuelto por su galleta, y son sus propias
    palabras. Un valor que no se puede abrir no sale, y el dato se muestra como
    anotado sin mas.
    """
    if session_.case_id is None:
        return None
    vista = await casos.get_case(session_.tenant_id, session_.case_id)
    if vista is None:
        return None
    estado = case_status.view_of(vista, case_link=None)
    anotado = await casos.open_field_values(
        session_.tenant_id,
        session_.case_id,
        [campo.field_key for campo in estado.fields],
        cipher=cipher,
    )
    campos = tuple(
        campo.model_copy(update={"value": anotado.get(campo.field_key)}) for campo in estado.fields
    )
    respuestas: list[ReasoningAnswer] = []
    for respuesta, comprobaciones in await citas.answers_for(session_.tenant_id, session_.case_id):
        detalles = {
            d.clause_id: d
            for d in await citation.details_for(
                session_.tenant_id, comprobaciones, language=language
            )
        }
        clausulas = tuple(
            ReasoningClause(
                clause_id=c.clause_id,
                part=(detalles[c.clause_id].translated_part or detalles[c.clause_id].part)
                if c.clause_id in detalles
                else "",
                verified=c.outcome is CoverageOutcome.VERIFIED,
                claim=c.claim_redacted,
            )
            for c in comprobaciones
        )
        respuestas.append(
            ReasoningAnswer(
                question=respuesta.question_redacted,
                outcome=respuesta.outcome.value,
                clauses=clausulas,
            )
        )
    return ChatReasoning(
        case_number=estado.case_number,
        record_type=estado.record_type or vista.record_type.value,
        state=estado.state,
        policy_ref=vista.policy_ref,
        derivation_reason=None if vista.derivation_reason is None else str(vista.derivation_reason),
        fields=campos,
        answers=tuple(respuestas),
    )


__all__ = ["ChatReasoning", "ReasoningAnswer", "ReasoningClause", "for_session"]
