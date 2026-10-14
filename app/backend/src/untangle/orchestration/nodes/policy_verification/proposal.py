"""Quien propone que clausulas responden la pregunta (fase 1, 2026-10-08).

Era el paso que faltaba: el nodo recuperaba las clausulas y el verificador sabia
comprobar citas, pero nadie proponia ninguna, asi que toda pregunta de cobertura
terminaba en "no encuentro una clausula" (A3 de `docs/propuesta-2026-10/02-hallazgos.md`).

**El modelo propone y el codigo decide.** El modelo lee solo las clausulas que el
nodo recupero de la poliza de esa persona y dice cuales responden la pregunta, con
una frase de por que. El verificador exacto de siempre comprueba cada cita --que se
haya recuperado, que sea de la aseguradora y de la poliza, que la poliza este
vigente, y que si un endoso la modifica tambien se cite--, y solo lo verificado sale.
El texto de las clausulas entra como contenido delimitado, nunca como instruccion.

Este modulo no llama a ningun proveedor: define el puerto y la forma de la salida.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from untangle.base import Locale
from untangle.tenancy.models import TenantId


class ProposedCitation(BaseModel):
    """Una clausula que el modelo propone citar, y por que responde la pregunta."""

    model_config = ConfigDict(frozen=True)

    clause_id: str
    claim: str


class CitationProposal(BaseModel):
    """La salida que se le pide al modelo. Vacia cuando ninguna clausula responde."""

    model_config = ConfigDict(frozen=True)

    citations: tuple[ProposedCitation, ...] = ()


@dataclass(frozen=True)
class ClauseForProposal:
    """Lo que el modelo ve de una clausula recuperada."""

    clause_id: str
    part: str
    text: str
    #: La clausula recuperada que arrastro a esta por relacion (un endoso que la
    #: modifica, una definicion), o `None`.
    related_to: str | None = None


@dataclass(frozen=True)
class ProposalRequest:
    tenant_id: TenantId
    language: Locale
    question: str
    clauses: tuple[ClauseForProposal, ...]


#: El puerto: lo construye la raiz de composicion con el cliente de Claude. Puede
#: levantar `ProviderError` o `BudgetExhausted`; el nodo lo trata como "no pude
#: verificar", que nunca se confunde con "no hay clausula".
ProposerPort = Callable[[ProposalRequest], Awaitable[CitationProposal]]


__all__ = [
    "CitationProposal",
    "ClauseForProposal",
    "ProposalRequest",
    "ProposedCitation",
    "ProposerPort",
]
