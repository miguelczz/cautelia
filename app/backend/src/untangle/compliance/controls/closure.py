"""Que decide el nodo `compliance` con la revision en la mano (BR6.1 a BR6.4).

Tres salidas y solo tres (`entities.md`, ClosureDecision):

- **refer**, con su motivo de la lista cerrada de C-04, cuando hay que derivar:
  la categoria de las reglas, una peticion de persona, una emergencia, un limite
  o una verificacion imposible (BR6.2). Un caso derivado va a una persona pase
  lo que pase con la revision, que se adjunta igual (BR5.2).
- **refused**, con lo que falta, cuando se intenta cerrar y algun control no
  paso (BR6.1): un caso sin la divulgacion registrada o sin sus adjuntos no se
  cierra, y el rechazo dice que falta para que la bandeja lo muestre.
- **close**, solo si los cuatro controles pasaron **y** la categoria de las
  reglas permite cerrar sin persona (AC1.17.1).

La decision es una funcion pura de sus entradas: la misma revision y el mismo
estado dan la misma decision, en la ejecucion y en la reejecucion al reanudar.

**Lo que el nodo dice al asegurado sale del catalogo** (BR6.4): la frase de
derivacion o la de cierre directo, que no afirman ni niegan cobertura y pasan por
la guardia como cualquier otra. El rechazo no dice nada al asegurado: es un
estado interno, y lo que falta se lee en la bandeja.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from untangle.base import Frozen
from untangle.compliance.controls import phrases
from untangle.compliance.controls.models import (
    CATALOG_KEY_MAX_LENGTH,
    CATALOG_KEY_PATTERN,
    ID_MAX_LENGTH,
    ComplianceReview,
    FindingCode,
)


class HandoffReason(StrEnum):
    """Los motivos de derivacion, la lista cerrada de C-04 (`TurnHandoff.reason_code`)."""

    RULE = "rule"
    COMPLIANCE = "compliance"
    HUMAN_REQUEST = "human_request"
    EMERGENCY = "emergency"
    LIMIT = "limit"
    UNVERIFIABLE = "unverifiable"


class ClosureOutcome(StrEnum):
    """Las tres salidas del nodo (BR6.1, BR6.2)."""

    CLOSE = "close"
    REFER = "refer"
    REFUSED = "refused"


class Handoff(Frozen):
    """Que la conversacion se derivo, en que turno y por que (BR5.2, BR6.2)."""

    #: El turno en que salio la frase de derivacion: la revision llega hasta el.
    turn_id: str = Field(min_length=1, max_length=ID_MAX_LENGTH)
    reason: HandoffReason


class ComplianceFinding(Frozen):
    """Un control que no paso, con su codigo cerrado (`entities.md`)."""

    code: FindingCode
    #: Que falta, dicho por el catalogo para la bandeja.
    detail_key: str = Field(pattern=CATALOG_KEY_PATTERN, max_length=CATALOG_KEY_MAX_LENGTH)

    @classmethod
    def of(cls, code: FindingCode) -> ComplianceFinding:
        """El hallazgo con la clave que le toca en el catalogo."""
        return cls(code=code, detail_key=phrases.FINDING_KEYS[code])


class ClosureDecision(Frozen):
    """Lo que el nodo `compliance` devuelve al runtime (`entities.md`)."""

    outcome: ClosureOutcome
    #: Obligatorio en `refer`, y solo ahi.
    reason_code: HandoffReason | None = None
    #: Obligatorio en `refused`, y solo ahi: que falta para cerrar (AC1.16.1).
    missing: tuple[ComplianceFinding, ...] = ()
    #: La frase del catalogo que dice la agente: la de derivacion en `refer` y la
    #: de cierre directo en `close`. Ninguna en `refused` (BR6.4).
    copy_key: str | None = Field(
        default=None, pattern=CATALOG_KEY_PATTERN, max_length=CATALOG_KEY_MAX_LENGTH
    )

    @model_validator(mode="after")
    def _cada_salida_con_lo_suyo(self) -> Self:
        derivada = self.outcome is ClosureOutcome.REFER
        rechazada = self.outcome is ClosureOutcome.REFUSED
        if derivada != (self.reason_code is not None):
            msg = f"una decision '{self.outcome.value}' lleva motivo si y solo si deriva (BR6.2)"
            raise ValueError(msg)
        if rechazada != bool(self.missing):
            msg = (
                f"una decision '{self.outcome.value}' dice que falta si y solo si "
                "rechaza el cierre (BR6.1)"
            )
            raise ValueError(msg)
        if rechazada == (self.copy_key is not None):
            msg = (
                f"una decision '{self.outcome.value}' lleva frase del catalogo si y "
                "solo si algo se le dice al asegurado (BR6.4)"
            )
            raise ValueError(msg)
        return self


def decide_closure(
    review: ComplianceReview, *, handoff: Handoff | None, closable: bool
) -> ClosureDecision:
    """La decision del nodo, pura (BR6.1, BR6.2, BR6.3).

    El orden es parte de la regla: una derivacion manda sobre todo lo demas,
    porque un caso que va a una persona no se esta intentando cerrar; despues,
    un cierre sin sus controles se rechaza diciendo que falta; y solo al final,
    con todo en orden, las reglas deciden si se cierra sin persona.
    """
    if handoff is not None:
        return ClosureDecision(
            outcome=ClosureOutcome.REFER, reason_code=handoff.reason, copy_key=phrases.HANDOFF
        )
    if not review.passed:
        return ClosureDecision(
            outcome=ClosureOutcome.REFUSED,
            missing=tuple(ComplianceFinding.of(code) for code in review.findings),
        )
    if not closable:
        return ClosureDecision(
            outcome=ClosureOutcome.REFER, reason_code=HandoffReason.RULE, copy_key=phrases.HANDOFF
        )
    return ClosureDecision(outcome=ClosureOutcome.CLOSE, copy_key=phrases.DIRECT_CLOSE)
