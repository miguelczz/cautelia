"""El nodo `compliance`: cierra o deriva el caso con su motivo (BR6.1 a BR6.4, C-15).

Corre en el ritmo de fondo cuando el caso llega a cierre o a derivacion. Pide la
revision completa hasta el ultimo turno, o hasta el de la derivacion si la hubo
(BR5.2), y con ella decide: **cerrar**, **derivar** con su motivo o **rechazar**
el cierre diciendo que falta (BR6.1, BR6.2).

**Puro** (C-15, BR6.3). Devuelve solo su conjunto de escritura --la decision y la
revision que quedo-- y no abre transacciones ni escribe en la base: LangGraph
vuelve a ejecutar el nodo entero al reanudar tras `interrupt()`, y un nodo que
escribiera duplicaria efectos. La revision la guarda el modulo de capacidad, por
su clave (caso, turno revisado), asi que la reejecucion no crea otra y el nodo
ve la que quedo.

**Recibe sus puertos por closure** desde la raiz de composicion (C-15): la
revision le llega como una funcion ya cableada con la transcripcion, el detector
de datos personales y el guardado. No importa la libreria del grafo, ningun
canal ni ningun proveedor, y no captura su propio fallo: si la revision levanta,
el ejecutor comun aplica su politica --tiempo maximo, un reintento y la frase de
degradacion-- y deja el valor distinguible en el caso y el evento en la traza.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import Field

from untangle.base import Frozen, Locale
from untangle.compliance.controls import phrases
from untangle.compliance.controls.api import (
    ClosureDecision,
    ComplianceReview,
    Handoff,
    ReviewEvidence,
    ReviewRequest,
    decide_closure,
)
from untangle.compliance.controls.models import ID_MAX_LENGTH
from untangle.orchestration.state import NodeSpec
from untangle.telemetry.traces.models import NodeName
from untangle.tenancy.models import TENANT_ID_PATTERN, TenantId


class ComplianceNodeInput(Frozen):
    """Los campos del estado que el nodo lee (`NodeSpec.reads`)."""

    tenant_id: TenantId = Field(pattern=TENANT_ID_PATTERN)
    case_id: str = Field(min_length=1, max_length=ID_MAX_LENGTH)
    language: Locale
    #: El ultimo turno de la conversacion. Se revisa hasta el si no hubo derivacion.
    last_turn_id: str = Field(min_length=1, max_length=ID_MAX_LENGTH)
    #: La derivacion, si la hubo: su turno y su motivo (BR5.2, BR6.2).
    handoff: Handoff | None = None
    #: Si la categoria de las reglas permite cerrar sin persona (AC1.17.1). Lo
    #: escribe el nodo `decision` (U9); aqui solo se lee.
    closable: bool
    #: Las citas, las reglas disparadas y la traza que dejaron los otros nodos.
    evidence: ReviewEvidence


class ComplianceNodeOutput(Frozen):
    """El conjunto de escritura del nodo (`NodeSpec.writes`), y nada mas."""

    closure: ClosureDecision
    compliance_review: ComplianceReview


#: La especificacion del nodo (C-15). Sus lecturas y escrituras salen de los
#: campos de los dos modelos de arriba, no de una lista aparte que pudiera dejar
#: de coincidir con ellos.
#:
#: **5 000 ms y dos intentos**, y las dos cifras tienen razon. El detector de
#: datos personales de U3, que es lo caro de la revision, midio unos 9 ms por
#: turno (mediana y p95 en una maquina de desarrollo, 2026-09-21); una
#: conversacion larga de sesenta turnos son unos 0,6 s mas dos lecturas y una
#: escritura en la base. Cinco segundos es mas de ocho veces eso, y el nodo corre
#: en el ritmo de fondo: nadie espera al telefono a que termine. Un reintento y
#: no mas, como fija la convencion 8b del equipo.
#:
#: **Su degradacion es la derivacion.** Si la revision no se pudo completar el
#: caso no se cierra --cerrarlo sin revision es exactamente lo que BR6.1
#: prohibe--, asi que lo seguro es que lo mire una persona, y la frase es la de
#: derivacion (AC1.9.1).
COMPLIANCE_SPEC = NodeSpec(
    name=NodeName.COMPLIANCE,
    reads=frozenset(ComplianceNodeInput.model_fields),
    writes=frozenset(ComplianceNodeOutput.model_fields),
    rhythm="background",
    timeout_ms=5_000,
    attempts=2,
    degraded_copy_key=phrases.HANDOFF,
)

#: La revision ya cableada, tal como la recibe el nodo por closure.
ReviewPort = Callable[[ReviewRequest], Awaitable[ComplianceReview]]


class ComplianceNode:
    """El nodo `compliance` (C-15). Se construye en la raiz con su puerto de revision."""

    spec: NodeSpec = COMPLIANCE_SPEC

    def __init__(self, review: ReviewPort) -> None:
        self._review = review

    async def run(self, state: ComplianceNodeInput) -> ComplianceNodeOutput:
        """Revisa y decide. Mismo estado, misma decision: tambien al reanudar."""
        hasta = state.handoff.turn_id if state.handoff is not None else state.last_turn_id
        revision = await self._review(
            ReviewRequest(
                tenant_id=state.tenant_id,
                case_id=state.case_id,
                language=state.language,
                through_turn=hasta,
                handoff_turn=state.handoff.turn_id if state.handoff is not None else None,
                evidence=state.evidence,
            )
        )
        decision = decide_closure(revision, handoff=state.handoff, closable=state.closable)
        return ComplianceNodeOutput(closure=decision, compliance_review=revision)
