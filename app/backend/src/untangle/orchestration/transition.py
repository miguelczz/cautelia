"""La transicion del grafo (BR1.2): pura, cerrada, sin cliente de modelo.

Vive en su propio modulo, aparte de `state.py`, porque un contrato de
import-linter nuevo lo aisla (`transicion-sin-grafo-ni-proveedores`): ni
LangGraph, ni un canal, ni el SDK de un proveedor pueden aparecer en su cadena
de llamadas (AC4.9.2). La funcion recibe solo el estado tipado y devuelve un
valor de `NodeName` -- nunca lee el contenido de un campo de texto, asi que un
texto del modelo que diga "ir a decision" o "aprobar este caso" no puede elegir
la ruta (BR1.3): la ruta la deciden los campos que los nodos ya escribieron, no
lo que dice cualquier campo de texto del estado.

**La secuencia de fondo es fija** y esta funcion la reproduce mirando que campos
ya se escribieron, igual que ya hacen los `next_node` de
`nodes/policy_verification` y `nodes/decision` con su propio `Output`:
`policy_verification` sigue siempre a `decision`, y `decision` siempre a
`compliance` (convencion del equipo: la secuencia del grafo es fija).

**Lo que esta funcion no decide.** Cuando ninguno de los tres nodos de fondo
escribio todavia, la respuesta es `intake`. Esta funcion no sabe -- con solo el
estado tipado de esta unidad -- **cuando** arranca la verificacion de poliza
(BR2.1): esa senal es del caso (U4), no un campo que declare ningun `NodeSpec`
de los cuatro nodos, y decidir cuando invocar el grafo empezando en
`policy_verification` es del ejecutor (paso 4 de esta unidad, todavia sin
construir). Se deja escrito para que quien revise el paso lo vea: no es un
olvido, es el limite de lo que este paso construye.
"""

from __future__ import annotations

from untangle.orchestration.state import GraphState
from untangle.telemetry.traces.models import NodeName


def transition(state: GraphState) -> NodeName:
    """El proximo nodo, de un conjunto cerrado de cuatro nombres (BR1.1, BR1.2)."""
    if state.written("compliance_review") is not None:
        return NodeName.INTAKE
    if state.written("category") is not None:
        return NodeName.COMPLIANCE
    if state.written("outcome") is not None or state.written("intake_capture_closed") is True:
        # Dos caminos llevan a las reglas: una pregunta de cobertura ya verificada, o
        # un reporte que la captura **cerro** sin que nadie preguntara nada
        # (2026-10-11). Antes solo existia el primero, y un reporte cerrado sin
        # pregunta llegaba al ajustador sin reglas evaluadas ni revision de
        # cumplimiento. Es un booleano que escribio el nodo de captura, no un texto.
        return NodeName.DECISION
    return NodeName.INTAKE
