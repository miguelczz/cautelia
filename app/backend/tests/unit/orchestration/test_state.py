"""`GraphState` se compone desde los `NodeSpec`, no se escribe a mano (BR1.5, FD-U12-1).

El caso feliz ya lo prueba `tests/unit/intake/test_node.py` con los cuatro nodos
reales, que son disjuntos. Lo que falta -- y lo que aisla esta prueba -- es la
mitad que ese caso feliz no puede mostrar: que dos especificaciones que SI
comparten un campo hacen fallar la composicion, en vez de componerse en
silencio.
"""

from __future__ import annotations

import pytest

from untangle.base import Use
from untangle.orchestration import turn
from untangle.orchestration.nodes.intake.node import INTAKE_SPEC
from untangle.orchestration.state import (
    TURN_INPUT_FIELDS,
    GraphState,
    GraphStateError,
    NodeSpec,
    compose_state_fields,
)
from untangle.providers import config as provider_config
from untangle.telemetry.traces.models import NodeName


def _spec(name: NodeName, writes: frozenset[str]) -> NodeSpec:
    return NodeSpec(
        name=name,
        reads=frozenset(),
        writes=writes,
        rhythm="background",
        timeout_ms=1_000,
        attempts=2,
        degraded_copy_key="tone.calm",
    )


def test_la_composicion_falla_si_dos_nodos_declaran_el_mismo_campo() -> None:
    """BR1.5: el proceso no arranca -- no devuelve un aviso -- si dos nodos chocan."""
    intake = _spec(NodeName.INTAKE, frozenset({"outcome"}))
    policy_verification = _spec(NodeName.POLICY_VERIFICATION, frozenset({"outcome"}))

    with pytest.raises(GraphStateError, match="outcome"):
        compose_state_fields((intake, policy_verification))


def test_la_composicion_falla_si_un_nodo_pisa_un_campo_del_turno() -> None:
    """Un nodo tampoco puede escribir un campo que el turno ya entrega (C-14)."""
    intruso = _spec(NodeName.DECISION, frozenset({"case_id"}))

    with pytest.raises(GraphStateError, match="case_id"):
        compose_state_fields((intruso,))


def test_la_composicion_es_la_union_de_los_conjuntos_de_escritura_mas_el_turno() -> None:
    """El caso feliz: dos nodos disjuntos componen sin chocar."""
    decision = _spec(NodeName.DECISION, frozenset({"category", "closable"}))
    compliance = _spec(NodeName.COMPLIANCE, frozenset({"compliance_review"}))

    campos = compose_state_fields((decision, compliance))

    assert campos == TURN_INPUT_FIELDS | {"category", "closable", "compliance_review"}


def test_el_estado_compuesto_devuelve_none_para_lo_que_ningun_nodo_escribio() -> None:
    """`written` distingue "no corrio todavia" de un valor real (BR5.1, contexto)."""
    estado = GraphState(
        tenant_id="acme",
        case_id="case-1",
        turn_id="turn-1",
        turn_text="hola",
    )

    assert estado.written("outcome") is None


def test_el_constructor_llano_no_valida_node_writes() -> None:
    """Documentado, no accidental: `GraphState(...)` acepta cualquier clave.

    Es lo que le permite a las pruebas de `transition` sembrar estados sin
    traer los cuatro `NodeSpec` cada vez. Quien si los tenga a mano usa
    `GraphState.compose`, que si valida (ver la prueba de abajo).
    """
    estado = GraphState(
        tenant_id="acme",
        case_id="case-1",
        turn_id="turn-1",
        turn_text="hola",
        node_writes={"un_campo_que_nadie_declara": "valor"},
    )

    assert estado.written("un_campo_que_nadie_declara") == "valor"


def test_graph_state_compose_rechaza_un_campo_que_ningun_spec_declara() -> None:
    """`GraphState.compose` si valida: compone `specs` y comprueba `node_writes` contra eso."""
    decision = _spec(NodeName.DECISION, frozenset({"category"}))
    estado = GraphState(
        tenant_id="acme",
        case_id="case-1",
        turn_id="turn-1",
        turn_text="hola",
        node_writes={"outcome": "verified"},
    )

    with pytest.raises(GraphStateError, match="outcome"):
        GraphState.compose((decision,), estado)


def test_graph_state_compose_acepta_lo_que_si_declaran_las_specs_y_devuelve_el_mismo_estado() -> (
    None
):
    decision = _spec(NodeName.DECISION, frozenset({"category"}))
    estado = GraphState(
        tenant_id="acme",
        case_id="case-1",
        turn_id="turn-1",
        turn_text="hola",
        node_writes={"category": "direct_close"},
    )

    assert GraphState.compose((decision,), estado) is estado


# --- El presupuesto del nodo de captura por canal ------------------------------


def test_el_plazo_de_captura_del_chat_no_es_el_de_la_voz() -> None:
    """El plazo de `INTAKE_SPEC` sale de doblar la meta p95 de la **voz**.

    El chat lo heredaba por compartir el `NodeSpec`, y con el proveedor de verdad
    --medido entre 2.892 y 5.300 ms-- eso degradaba casi todos los turnos: la
    persona leia una frase de degradacion en vez de la pregunta siguiente. Ahora el
    chat lleva el suyo y **la voz sigue con el de su especificacion**, que es el
    numero aprobado y no se toca.

    Se comprueban los dos canales, porque con uno solo esto pasa igual contra un
    codigo que le diera el presupuesto del chat a los dos -- que es exactamente el
    defecto al reves.
    """
    assert turn._intake_timeout_ms("chat") == turn.INTAKE_TIMEOUT_CHAT_MS
    assert turn._intake_timeout_ms("voice") is None, "la voz usa el de su especificacion"
    # Y el del chat es **mas ancho** que el de la voz: si fuera igual o menor, esta
    # unidad no habria cambiado nada.
    assert turn.INTAKE_TIMEOUT_CHAT_MS > INTAKE_SPEC.timeout_ms
    # Y cabe dentro del plazo de lectura del proveedor para este uso: por encima, el
    # que cortaria seria el transporte y esta cifra no diria nada.
    lectura_chat_ms = next(
        uso.read_timeout_ms for uso in provider_config.load().providers.uses if uso.use is Use.CHAT
    )
    assert turn.INTAKE_TIMEOUT_CHAT_MS < lectura_chat_ms


def test_cada_frase_de_degradacion_declarada_por_un_nodo_se_resuelve_a_la_suya() -> None:
    """La tabla cerrada de `_degraded_phrase` tiene que conocer la clave de cada
    `NodeSpec`: una que no conozca cae en la frase generica de la guardia, y la
    persona lee otra cosa que la que el nodo declaro. Paso el 2026-10-06 al cambiar
    la frase del nodo de captura: la pantalla la conocia y el servidor no."""
    from untangle.copy_catalog.api import CopyKey

    clave = CopyKey(INTAKE_SPEC.degraded_copy_key)
    resuelta, texto = turn._degraded_phrase(clave, language="es")

    assert resuelta == clave
    assert texto != turn._degraded_phrase(CopyKey("una.clave.que.no.existe"), language="es")[1]
