"""El grafo real compilado del ritmo de fondo, y su punto único de instalación (paso 7 de U12).

**Qué compone este módulo, y qué no.** El ritmo del turno (`intake`, el único
`NodeSpec` con `rhythm="turn"`) **no** corre dentro de este grafo compilado:
`handle_turn` lo invoca directo con `NodeExecutor.run`, exactamente como
`orchestration.graph.TURN_NODE_SPECS` ya lo separaba de
`BACKGROUND_NODE_SPECS` desde el paso 5. Lo que este módulo compila es la
secuencia fija de fondo -- `policy_verification` → `decision` → `compliance`
(`functional-spec.md`) --, con `TenantCheckpointSaver` (paso 2) enchufado de
verdad y `transition()` (paso 3) como única función de enrutado: es la pieza
que hace cierto, y no solo dicho, que "el orquestador es código con contratos y
no un modelo decidiendo con texto libre".

**Por qué `policy_verification`, `decision` y `compliance` entran como
enlaces genéricos y no como las clases reales de U8, U9 y U10.** Las tres
necesitan puertos que este paso no construye -- el corpus de pólizas real, el
motor de reglas de la aseguradora, la revisión completa de cumplimiento -- y
cablearlos de verdad es integración de proveedor y de datos de la aseguradora
que ninguna `Fronteras` de `functional-spec.md` le pide a esta unidad (U12
"ejecuta" los cuatro nodos; no construye sus puertos). Lo que este módulo
garantiza es genérico y reutilizable el día que esos tres nodos reales entren
por aquí: cada uno es un `NodeExecutor.Node` (paso 4, C-15) más un
`build_input`, la única pieza que sí depende del nodo -- construir su entrada
tipada desde `GraphState` -- y que ya era, según el propio aviso de
`executor.py`, "de quien invoque el grafo real". `intake`, que si es la clase
real de U11, muestra la forma que tomará esa pieza el día que las otras tres
lleguen: `orchestration.case_context` construye su entrada real desde el caso
(BR3.2), sin ninguna rama por nombre de nodo en el ejecutor ni aquí.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from untangle.base import Frozen
from untangle.orchestration.checkpoint import TenantCheckpointSaver
from untangle.orchestration.executor import Node, NodeExecutor
from untangle.orchestration.graph import BACKGROUND_NODE_SPECS
from untangle.orchestration.node_run import NodeRunOutcome
from untangle.orchestration.state import GraphState
from untangle.orchestration.transition import transition
from untangle.telemetry.traces.models import NodeName


@dataclass(frozen=True)
class BackgroundBinding[NodeInputT: Frozen, NodeOutputT: Frozen]:
    """Un nodo de fondo real o doble, más cómo construir su entrada desde el estado.

    `build_input` es la única pieza que conoce la forma particular del nodo
    (C-15): lee de `GraphState.node_writes` los campos que su `NodeSpec.reads`
    necesita. Es exactamente lo que `executor.py` dejó sin construir a
    propósito ("de quien invoque el grafo real").
    """

    node: Node[NodeInputT, NodeOutputT]
    build_input: Callable[[GraphState], NodeInputT]


#: Lo que un desenlace `degraded` deja en el estado, cuando el nodo agotó sus
#: intentos: la clave de su frase y el tipo de error, para que un consumidor
#: (el punto único de salida, BR2.5) pueda componer el `TurnError`/`Handoff` sin
#: adivinar nada. Vive bajo una clave propia (`<nodo>_degraded`), nunca bajo el
#: nombre de un campo que el `NodeOutput` real declare: los dos nunca chocan
#: porque ningún `NodeSpec` de C-15 declara un campo terminado en `_degraded`.
def degraded_key(node: NodeName) -> str:
    return f"{node.value}_degraded"


def _node_output_fields(output: Frozen) -> dict[str, object]:
    """Los campos de la salida de un nodo, con sus valores **tal cual** (sin volcar a JSON).

    A propósito no se usa `model_dump()`: volcaría un valor anidado -- por
    ejemplo `ComplianceNodeOutput.closure` -- a un diccionario y perdería su
    tipo. `GraphState.written(campo)` tiene que devolver el mismo objeto
    tipado que el nodo produjo, para que quien lo lea (el punto único de
    salida) no tenga que reconstruirlo.
    """
    return {campo: getattr(output, campo) for campo in type(output).model_fields}


def _wrap[NodeInputT: Frozen, NodeOutputT: Frozen](
    name: NodeName,
    binding: BackgroundBinding[NodeInputT, NodeOutputT],
    executor: NodeExecutor,
) -> Callable[[GraphState], Awaitable[dict[str, object]]]:
    async def _run(state: GraphState) -> dict[str, object]:
        node_input = binding.build_input(state)
        resultado = await executor.run(
            binding.node, node_input, tenant_id=state.tenant_id, case_id=state.case_id
        )
        pendiente = state.pending_background - {name}
        escritura: dict[str, object]
        if resultado.outcome is NodeRunOutcome.SUCCEEDED and resultado.output is not None:
            escritura = _node_output_fields(resultado.output)
        elif resultado.outcome is NodeRunOutcome.SUCCEEDED:
            # Un relanzamiento sobre un trabajo ya `succeeded` no trae su salida
            # de vuelta (`executor.py`, `_resultado_cacheado`): lo que ya se
            # escribió sigue en `state.node_writes` de la corrida anterior, y
            # este nodo no tiene nada nuevo que añadir.
            escritura = {}
        else:
            escritura = {
                degraded_key(name): {
                    "copy_key": (
                        str(resultado.degraded_copy_key)
                        if resultado.degraded_copy_key is not None
                        else None
                    ),
                    "error_kind": (
                        resultado.error_kind.value if resultado.error_kind is not None else None
                    ),
                }
            }
        return {
            "node_writes": {**state.node_writes, **escritura},
            "pending_background": pendiente,
        }

    return _run


def _route(state: GraphState) -> str:
    """El enrutado del grafo compilado: `transition()` (paso 3), sin ninguna rama propia.

    `transition` nunca devuelve `POLICY_VERIFICATION` -- es el nodo de entrada
    fijo de este grafo, no un destino de la transición (`transition.py`,
    "cuándo arranca la verificación de póliza... es del ejecutor") --, así que
    el único valor que esta función traduce a `END` es `INTAKE`: en este grafo
    de fondo esa respuesta significa "la secuencia terminó", no "invoca el
    nodo intake", que ni siquiera es parte de este grafo.
    """
    siguiente = transition(state)
    if siguiente is NodeName.INTAKE:
        return END
    return siguiente.value


def compile_turn_graph(
    binding: BackgroundBinding[Frozen, Frozen],
    *,
    executor: NodeExecutor,
    checkpointer: TenantCheckpointSaver,
) -> CompiledStateGraph[GraphState, None, GraphState, GraphState]:
    """El grafo real del ritmo del turno: un solo nodo, `intake` (BR2.1 a BR2.4).

    No enruta a ningún otro nodo -- `intake` nunca lo hace, es el único
    `NodeSpec` de `rhythm="turn"` -- y por eso no comparte `_route` con el
    grafo de fondo. Comparte `TenantCheckpointSaver` con él (mismo `thread_id`,
    el `case_id`): los puntos de control de los dos ritmos son puntos del
    mismo hilo, uno por cada vez que cualquiera de los dos grafos corre.
    """
    grafo = StateGraph(GraphState)
    # mypy no resuelve el sobrecargado de `add_node` contra una funcion generica
    # de este modulo (misma friccion conocida de los stubs de LangGraph que ya
    # documenta `test_resume.py`, paso 6, no de este codigo).
    grafo.add_node(NodeName.INTAKE.value, _wrap(NodeName.INTAKE, binding, executor))  # type: ignore[call-overload]
    grafo.add_edge(START, NodeName.INTAKE.value)
    grafo.add_edge(NodeName.INTAKE.value, END)
    return grafo.compile(checkpointer=checkpointer)


def compile_background_graph(
    bindings: Mapping[NodeName, BackgroundBinding[Any, Any]],
    *,
    executor: NodeExecutor,
    checkpointer: TenantCheckpointSaver,
) -> CompiledStateGraph[GraphState, None, GraphState, GraphState]:
    """El grafo real de `policy_verification → decision → compliance`, con puntos de control.

    Falla al construirse si falta uno de los tres enlaces del ritmo de fondo:
    un grafo a medias no arranca en silencio, arranca con el nombre de lo que
    falta.
    """
    esperados = {spec.name for spec in BACKGROUND_NODE_SPECS}
    faltan = esperados - set(bindings)
    if faltan:
        nombres = ", ".join(sorted(n.value for n in faltan))
        msg = f"faltan enlaces del ritmo de fondo para: {nombres}"
        raise ValueError(msg)

    grafo = StateGraph(GraphState)
    for nombre, enlace in bindings.items():
        # Misma friccion de stubs que `compile_turn_graph`, arriba.
        grafo.add_node(nombre.value, _wrap(nombre, enlace, executor))  # type: ignore[call-overload]

    grafo.add_edge(START, NodeName.POLICY_VERIFICATION.value)
    for nombre in bindings:
        grafo.add_conditional_edges(nombre.value, _route)

    return grafo.compile(checkpointer=checkpointer)


__all__ = [
    "BackgroundBinding",
    "compile_background_graph",
    "compile_turn_graph",
    "degraded_key",
]
