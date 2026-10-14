"""El nodo `decision`: evalua las reglas de la aseguradora y guarda el resultado (BR3.1, C-15).

Corre en el ritmo de fondo, igual que `compliance`: ninguna decision de reglas
ocurre dentro del turno de voz (`project.md`, prohibicion de trabajo de reglas
en el turno). Llama al motor real de U9 (`rules.api`), guarda la evaluacion por
su identificador determinista y devuelve `compliance` como siguiente nodo, por
una funcion pura.

**Puro** (C-15, BR3.1): devuelve solo su conjunto de escritura y no abre
transacciones. `rules.api.save_evaluation` ya es idempotente por identificador
(ADR-003), y aqui el identificador mismo es determinista -- se deriva del
caso, la version del conjunto y los insumos --, asi que la reejecucion del
nodo tras `interrupt()` guarda la misma fila una sola vez.

**Recibe sus puertos por closure** desde la raiz de composicion: el reloj de
`evaluated_at` y el guardado, los dos unicos puntos impuros que el nodo
necesita. `evaluate()` (C-19) es codigo puro en memoria y se llama directo, sin
puerto -- es la misma superficie publica que las pruebas de `rules/` ya
ejercitan --, pero el guardado toca la base por el punto unico de sesion de
U2, y una prueba de nodo no abre una base (team.md, rama determinista). Con el
guardado inyectado, la prueba dobla solo esa pieza y ejercita el motor de
reglas real para lo demas. No importa LangGraph, ningun canal ni ningun
proveedor: el contrato de importacion `reglas-sin-proveedores` de
`.importlinter` lo comprueba, con este nodo como su segundo `source_module`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime

from pydantic import Field

from untangle.base import Frozen
from untangle.compliance.controls import phrases
from untangle.orchestration.state import NodeSpec
from untangle.rules.api import Category, FiredRule, RuleEvaluation, evaluate
from untangle.rules.fields import RuleValue
from untangle.rules.models import ID_MAX_LENGTH
from untangle.telemetry.traces.models import NodeName
from untangle.tenancy.models import TENANT_ID_PATTERN, TenantId

#: Cuantos caracteres hexadecimales de la huella entran en el identificador.
#: Con el prefijo "reval-" (6 caracteres) sobra margen bajo ID_MAX_LENGTH (64).
_DIGEST_LENGTH = 32


def _evaluation_id(
    *, tenant_id: TenantId, case_id: str, ruleset_version: str, inputs: Mapping[str, RuleValue]
) -> str:
    """Determinista: el mismo caso, version de conjunto e insumos dan el mismo id (ADR-003)."""
    fingerprint = json.dumps(
        {
            "tenant_id": tenant_id,
            "case_id": case_id,
            "ruleset_version": ruleset_version,
            "inputs": dict(inputs),
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:_DIGEST_LENGTH]
    return f"reval-{digest}"


class DecisionNodeInput(Frozen):
    """Los campos del estado que el nodo lee (`NodeSpec.reads`)."""

    tenant_id: TenantId = Field(pattern=TENANT_ID_PATTERN)
    case_id: str = Field(min_length=1, max_length=ID_MAX_LENGTH)
    #: Los insumos que la captura (U11) ya dejo en el estado, por el
    #: vocabulario cerrado de `rules/fields.py` (C-19, `required_inputs`).
    inputs: dict[str, RuleValue] = Field(default_factory=dict)


class DecisionNodeOutput(Frozen):
    """El conjunto de escritura del nodo (`NodeSpec.writes`), y nada mas.

    `fired_rules` es la evidencia de reglas del caso que necesita la revision
    completa de `compliance` (BR3.1: "adjunta fired_rules al caso"); `closable`
    ya lo lee ese mismo nodo, segun su propio comentario en
    `orchestration/nodes/compliance/node.py` ("lo escribe el nodo decision").
    """

    category: Category
    #: Cierto solo cuando la categoria es `direct_close` (AC1.17.1).
    closable: bool
    fired_rules: tuple[FiredRule, ...]


#: **2 000 ms y dos intentos.** Evaluar el conjunto es codigo puro en memoria,
#: sin red; lo unico que cuesta es guardar `rule_evaluation`, una sola consulta
#: por el punto unico de sesion. Es una fraccion del presupuesto de
#: `compliance` (5 000 ms), que ademas relee la transcripcion completa del
#: caso. Un reintento y no mas, como la convencion 8b del equipo.
#:
#: **Su degradacion es la derivacion**, la misma frase que `compliance`: si la
#: categoria no se pudo decidir, lo seguro es que la mire una persona (P1).
DECISION_SPEC = NodeSpec(
    name=NodeName.DECISION,
    reads=frozenset(DecisionNodeInput.model_fields),
    writes=frozenset(DecisionNodeOutput.model_fields),
    rhythm="background",
    timeout_ms=2_000,
    attempts=2,
    degraded_copy_key=phrases.HANDOFF,
)

#: El reloj de `evaluated_at`, tal como lo recibe el nodo por closure.
ClockPort = Callable[[], datetime]

#: El guardado, con la misma firma que `rules.api.save_evaluation` (BR3.1,
#: ADR-003): la raiz de composicion cablea el puerto real con esa funcion
#: directamente, sin envoltorio.
SavePort = Callable[[RuleEvaluation], Awaitable[RuleEvaluation]]


def next_node(_output: DecisionNodeOutput) -> NodeName:
    """Siempre `compliance`: la revision completa sigue a toda decision (BR3.1, F3).

    Recibe el estado por la misma firma que cualquier transicion del grafo
    (convencion 5c: pura y cerrada), aunque esta no lo necesite para decidir.
    """
    return NodeName.COMPLIANCE


class DecisionNode:
    """El nodo `decision` (C-15). Se construye en la raiz de composicion con sus puertos."""

    spec: NodeSpec = DECISION_SPEC

    def __init__(self, *, clock: ClockPort, save: SavePort) -> None:
        self._clock = clock
        self._save = save

    async def run(self, state: DecisionNodeInput) -> DecisionNodeOutput:
        """Evalua, guarda y responde. Mismo estado, misma evaluacion: tambien al reanudar."""
        view = await evaluate(state.tenant_id, state.inputs)
        evaluation = RuleEvaluation(
            evaluation_id=_evaluation_id(
                tenant_id=state.tenant_id,
                case_id=state.case_id,
                ruleset_version=view.ruleset_version,
                inputs=state.inputs,
            ),
            tenant_id=state.tenant_id,
            case_id=state.case_id,
            ruleset_version=view.ruleset_version,
            category=view.category,
            fired_rules=view.fired_rules,
            inputs_snapshot=view.inputs_snapshot,
            explanation_key=view.explanation_key,
            evaluated_at=self._clock(),
        )
        saved = await self._save(evaluation)
        return DecisionNodeOutput(
            category=saved.category,
            closable=saved.category == "direct_close",
            fired_rules=saved.fired_rules,
        )
