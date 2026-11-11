"""La salida estructurada de la decision: lo unico que se le pide al modelo (paso 6).

El modelo propone y el codigo decide: lo que sale de aqui pasa por `validation` antes de ser una
decision --la accion contra el tipo de aseguradora, las citas contra el verificador exacto, el
texto contra la guardia--. Ninguna transicion ni accion sobre el caso sale de texto libre: `action`
es un valor del conjunto cerrado de la bandeja.
"""

from __future__ import annotations

from pydantic import Field

from untangle.base import Frozen
from untangle.inbox.actions import InboxAction


class DecisionReason(Frozen):
    """Una razon de la decision, con las clausulas que la respaldan si las hay."""

    text: str = Field(
        min_length=1, max_length=600, description="One sentence, in the language of the case."
    )
    clause_ids: tuple[str, ...] = Field(
        default=(),
        description="Clause ids copied exactly from the clauses data; empty when the reason is a fact.",
    )


class AdjusterDecision(Frozen):
    """La decision que el modelo propone para el caso."""

    action: InboxAction = Field(
        description="One of the allowed actions given in the data, and no other."
    )
    headline: str = Field(
        min_length=1,
        max_length=200,
        description="The decision in one short sentence without figures; the chat notice quotes it.",
    )
    explanation: str = Field(
        min_length=1,
        max_length=900,
        description="The explanation for the person, in the language of the case.",
    )
    reasons: tuple[DecisionReason, ...] = Field(
        description="The reasons for the decision, most important first."
    )
    cited_clause_ids: tuple[str, ...] = Field(
        default=(), description="Every clause the decision cites, without repeating."
    )
    uncertainties: tuple[str, ...] = Field(
        default=(), description="What could not be confirmed and the person should know."
    )
