"""Los cuatro `NodeSpec` reales se componen al importarse (BR1.5, FD-U12-1).

`test_state.py` ya prueba `compose_state_fields` con especificaciones
fabricadas: eso aisla la logica de composicion, pero no demuestra que el
proceso real la ejecute. Lo que este archivo cierra es lo segundo: que los
CUATRO NODOS REALES pasan por ella al importarse, y que si dos de verdad
chocaran, importar el paquete fallaria en vez de arrancar con el choque
adentro.
"""

from __future__ import annotations

import dataclasses
import importlib
import subprocess
import sys

import pytest

from untangle.orchestration import graph
from untangle.orchestration.nodes.intake import node as intake_node
from untangle.orchestration.state import GraphStateError, compose_state_fields


def test_los_cuatro_specs_reales_componen_sin_chocar() -> None:
    """El caso feliz: hoy son disjuntos, y este modulo es quien lo demuestra en producción."""
    assert len(graph.GRAPH_NODE_SPECS) == 4
    assert graph.GRAPH_STATE_FIELDS == compose_state_fields(graph.GRAPH_NODE_SPECS)


def test_la_particion_por_ritmo_cubre_los_cuatro_nodos_sin_solaparse() -> None:
    """Paso 5: `TURN_NODE_SPECS` y `BACKGROUND_NODE_SPECS` se calculan, no se escriben a mano.

    Hoy `intake` es el unico del ritmo del turno y los otros tres son de fondo
    (decision de PERF-U12.4); esta prueba lo comprueba sobre los `NodeSpec`
    reales, no sobre una lista copiada de la memoria de quien escribio esto.
    """
    assert {s.name for s in graph.TURN_NODE_SPECS} == {intake_node.INTAKE_SPEC.name}
    assert set(graph.TURN_NODE_SPECS) | set(graph.BACKGROUND_NODE_SPECS) == set(
        graph.GRAPH_NODE_SPECS
    )
    assert set(graph.TURN_NODE_SPECS).isdisjoint(graph.BACKGROUND_NODE_SPECS)


def test_importar_el_grafo_falla_si_dos_specs_reales_chocan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BR1.5 para los nodos reales, no para dobles.

    Si `intake` pisara un campo que ya escribe `policy_verification`
    (`outcome`), importar `untangle.orchestration.graph` tiene que fallar al
    arrancar -- no quedarse en verde con el choque adentro.
    """
    spec_con_choque = dataclasses.replace(intake_node.INTAKE_SPEC, writes=frozenset({"outcome"}))
    monkeypatch.setattr(intake_node, "INTAKE_SPEC", spec_con_choque)

    try:
        with pytest.raises(GraphStateError, match="outcome"):
            importlib.reload(graph)
    finally:
        # `graph` pudo quedar a medio recomponer con el parche adentro (el
        # modulo se re-ejecuto hasta la linea que fallo). `monkeypatch.undo()`
        # deshace el parche aqui mismo -- no al terminar la prueba, que seria
        # tarde para esta recomposicion -- y se recompone limpio antes de que
        # corra cualquier otra prueba.
        monkeypatch.undo()
        importlib.reload(graph)


def test_la_raiz_de_composicion_importa_el_grafo() -> None:
    """Lo que hace que BR1.5 sea cierto en produccion y no solo en estas pruebas.

    `graph.py` compone al importarse, asi que el choque de dos conjuntos de
    escritura solo detiene el proceso **servido** si algo del proceso servido lo
    importa. Esa linea vive en `server/composition.py` y no la usa nadie por su
    nombre, asi que sin esta prueba se puede borrar y todo seguiria en verde:
    la deuda se reabriria en silencio.

    Se comprueba en un interprete nuevo porque `sys.modules` es del proceso: en
    la suite entera el modulo ya esta importado por otras pruebas, y la
    asercion pasaria sin que la linea existiera.
    """
    guion = (
        "import importlib, sys; "
        "importlib.import_module('untangle.server.composition'); "
        "sys.exit(0 if 'untangle.orchestration.graph' in sys.modules else 1)"
    )
    resultado = subprocess.run(  # noqa: S603 -- el ejecutable es el de esta misma prueba (`sys.executable`) y el guion es una constante literal de arriba: no entra nada de fuera
        [sys.executable, "-c", guion], check=False, capture_output=True
    )

    assert resultado.returncode == 0, (
        "importar la raiz de composicion no carga untangle.orchestration.graph: "
        f"{resultado.stderr.decode()}"
    )
