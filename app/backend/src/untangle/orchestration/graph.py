"""Los cuatro `NodeSpec` reales, compuestos al importarse (BR1.5, FD-U12-1).

Vive aqui y no en `state.py` a proposito: los cuatro nodos importan
`state.py` (por `NodeSpec`), asi que si `state.py` importara aqui los cuatro
nodos para componerlos, formaria un ciclo. Este modulo esta por encima de los
cuatro -- es el sitio natural donde el paso 4 de esta unidad construira el
grafo de LangGraph -- y por ahora solo hace una cosa: componer el conjunto de
campos del estado con las especificaciones reales, no con dobles fabricados en
una prueba.

**Por que esto es lo que hace que BR1.5 se cumpla de verdad.** `compose_state_fields`
ya existia y ya tenia su prueba, pero nada la llamaba con los cuatro `NodeSpec`
reales: si dos llegaran a chocar, el unico sintoma habria sido una prueba en
rojo, y el proceso habria arrancado igual. Import-time es donde "el proceso no
arranca" deja de ser una frase y pasa a ser lo que pasa: importar este modulo
--y por tanto importar el paquete que lo requiera-- es lo que falla.
"""

from __future__ import annotations

from untangle.orchestration.nodes.compliance.node import COMPLIANCE_SPEC
from untangle.orchestration.nodes.decision.node import DECISION_SPEC
from untangle.orchestration.nodes.intake.node import INTAKE_SPEC
from untangle.orchestration.nodes.policy_verification.node import POLICY_VERIFICATION_SPEC
from untangle.orchestration.state import NodeSpec, compose_state_fields

#: Los cuatro nodos del grafo. El orden aqui es el de declaracion, no el de
#: ejecucion -- ese lo fija `transition` (BR1.1).
GRAPH_NODE_SPECS: tuple[NodeSpec, ...] = (
    INTAKE_SPEC,
    POLICY_VERIFICATION_SPEC,
    DECISION_SPEC,
    COMPLIANCE_SPEC,
)

#: Se calcula al importar el modulo. Si dos de los cuatro chocaran, esta linea
#: levanta `GraphStateError` y con ella la importacion entera del modulo.
GRAPH_STATE_FIELDS: frozenset[str] = compose_state_fields(GRAPH_NODE_SPECS)

#: Paso 5: la particion por ritmo (BR2.1 a BR2.4). Se calcula de `GRAPH_NODE_SPECS`
#: y no se declara aparte, por la misma razon que `GRAPH_STATE_FIELDS`: una lista
#: escrita a mano se desincroniza en cuanto un nodo cambie de ritmo, y nadie lo
#: notaria hasta que el turno esperara a un nodo que ya no deberia esperar.
TURN_NODE_SPECS: tuple[NodeSpec, ...] = tuple(s for s in GRAPH_NODE_SPECS if s.rhythm == "turn")
BACKGROUND_NODE_SPECS: tuple[NodeSpec, ...] = tuple(
    s for s in GRAPH_NODE_SPECS if s.rhythm == "background"
)
