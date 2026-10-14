"""`NodeSpec` (C-15) y el estado tipado que U12 compone a partir de el.

`NodeSpec` lo declaro U10, el primer nodo construido, en el sitio que el
contrato nombra (`orchestration/state.py`) para que U12 lo encontrara aqui sin
mudar nada. Lo que dice de su nodo es **dato**, no codigo: que lee, que escribe,
en que ritmo corre y su politica de fallo --tiempo maximo, intentos y texto de
degradacion-- (regla de `project.md`: la politica de fallo de cada nodo se
declara como dato y la aplica un ejecutor comun). Un nodo no captura su propio
fallo para seguir adelante.

**Una sola grafia para los cuatro nodos** (convencion 3 del equipo): el nombre es
el mismo `NodeName` que nombra el tramo en la traza, no una lista paralela.

U12 agrega aqui `GraphState`, que **se compone desde los `NodeSpec`, no se
escribe a mano** (BR1.5, FD-U12-1): una lista escrita a mano se desincroniza con
el primer nodo que cambie su conjunto de escritura, y nadie se enteraria hasta
que un campo dejara de escribirse a mitad de una conversacion. El ejecutor
comun que aplica la politica de fallo y escribe estos campos en el estado es de
paso 4 de esta unidad, todavia sin construir.

**Enmienda del 2026-09-27 (FD-U12-2, paso 4):** `NodeSpec` suma `retries_owned_by`,
quien cuenta los reintentos. Es aditivo -- `"executor"` por omision, asi que los
cuatro nodos ya construidos siguen validos sin tocarlos -- y hoy solo
`policy_verification` declara `"node"`: tras agotar sus propios intentos todavia
tiene que escribir su `unverifiable`, el valor distinguible que nadie mas sabe
escribir, y un ejecutor que volviera a aplicar `attempts` sobre el haria cuatro
llamadas al proveedor en vez de dos (`orchestration/executor.py`, paso 4).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from untangle.telemetry.traces.models import NodeName

#: La forma de una clave del catalogo (C-21). La de degradacion sale del
#: catalogo como cualquier otra frase hacia el asegurado.
_CLAVE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")


class NodeSpecError(ValueError):
    """Una especificacion de nodo que no se puede cumplir. Falla al declararla."""


@dataclass(frozen=True)
class NodeSpec:
    """Lo que un nodo declara de si mismo (C-15)."""

    name: NodeName
    #: Los campos del estado que lee.
    reads: frozenset[str]
    #: Su conjunto de escritura: dos nodos no comparten ninguno (convencion 6).
    writes: frozenset[str]
    rhythm: Literal["turn", "background"]
    timeout_ms: int
    #: Cuantas veces se intenta en total: 2 es uno y un reintento.
    attempts: int
    degraded_copy_key: str
    #: FD-U12-2: quien cuenta los reintentos de este nodo. `"executor"` (por
    #: omision) es la politica comun: el ejecutor de paso 4 aplica `attempts` el
    #: mismo para los cuatro. `"node"` es la unica excepcion hoy
    #: (`policy_verification`): el ejecutor lo llama una sola vez y no reintenta
    #: por su cuenta, porque el nodo ya agoto sus propios intentos por dentro.
    retries_owned_by: Literal["executor", "node"] = "executor"

    def __post_init__(self) -> None:
        problemas: list[str] = []
        if not self.writes:
            problemas.append("no declara ningun campo que escriba")
        if self.timeout_ms <= 0:
            problemas.append(f"su tiempo maximo es {self.timeout_ms} ms")
        if self.attempts < 1:
            problemas.append(f"se intentaria {self.attempts} veces")
        if not _CLAVE.match(self.degraded_copy_key):
            problemas.append(f"'{self.degraded_copy_key}' no tiene forma de clave del catalogo")
        if problemas:
            msg = f"el nodo '{self.name.value}' " + "; ".join(problemas) + " (C-15)"
            raise NodeSpecError(msg)


class GraphStateError(ValueError):
    """El estado tipado no se pudo componer. Falla al arrancar el proceso (BR1.5)."""


#: Los campos que el estado suma por su cuenta, ademas de lo que escriben los
#: nodos: los que entrega el turno (C-14). Se fijan a mano porque ningun
#: `NodeSpec` los declara -- no los escribe ningun nodo, los trae el canal.
TURN_INPUT_FIELDS: frozenset[str] = frozenset({"tenant_id", "case_id", "turn_id", "turn_text"})


def compose_state_fields(specs: Sequence[NodeSpec]) -> frozenset[str]:
    """El conjunto de campos del estado tipado (BR1.5, FD-U12-1).

    Se compone de los conjuntos de escritura de `specs` mas `TURN_INPUT_FIELDS`.
    **Falla al componerse** -- no devuelve un aviso -- si dos especificaciones
    declaran el mismo campo, o si una pisa un campo del turno: un choque
    descubierto en produccion es un nodo pisandole un campo a otro a mitad de
    una conversacion, y eso no deja rastro.
    """
    dueno: dict[str, NodeName] = {}
    for spec in specs:
        for campo in spec.writes:
            if campo in TURN_INPUT_FIELDS:
                msg = f"'{campo}' del nodo '{spec.name.value}' ya es un campo del turno"
                raise GraphStateError(msg)
            visto = dueno.get(campo)
            if visto is not None:
                msg = f"'{campo}' lo escriben '{visto.value}' y '{spec.name.value}'"
                raise GraphStateError(msg)
            dueno[campo] = spec.name
    return TURN_INPUT_FIELDS | frozenset(dueno)


@dataclass(frozen=True)
class GraphState:
    """El estado tipado del grafo (FD-U12-1).

    `node_writes` guarda lo que los nodos ya escribieron, con la clave siendo el
    nombre del campo. **El constructor llano no valida esas claves**: acepta
    cualquier `node_writes` que se le pase, y asi lo usan las pruebas para
    sembrar estados arbitrarios sin tener que traer los cuatro `NodeSpec` cada
    vez. Quien si tenga las especificaciones a mano valida con
    `GraphState.compose(specs, estado)`, que compone el conjunto con
    `compose_state_fields` y falla si `node_writes` trae una clave que ninguna
    declara (BR1.5). El texto de la persona viaja en `turn_text` como cualquier
    otro campo del turno y nunca se concatena a una instruccion de sistema
    (BR1.4).
    """

    tenant_id: str
    case_id: str
    turn_id: str
    turn_text: str
    node_writes: Mapping[str, object] = field(default_factory=dict)
    #: Que trabajo de fondo esta en vuelo (entities.md, "Lo que U12 compone y no
    #: persiste"). Lo llena el ejecutor de paso 4; aqui solo se declara el campo.
    pending_background: frozenset[NodeName] = frozenset()

    def written(self, campo: str) -> object | None:
        """Lo que un nodo ya escribio en `campo`, o `None` si aun no corrio."""
        return self.node_writes.get(campo)

    @classmethod
    def compose(cls, specs: Sequence[NodeSpec], state: GraphState) -> GraphState:
        """Valida `state.node_writes` contra lo que componen `specs`, y lo devuelve (BR1.5).

        A diferencia de construir `GraphState` a mano, este camino si valida: si
        `node_writes` trae una clave que ningun `NodeSpec` de `specs` declara --
        ni es un campo del turno -- falla en vez de aceptar en silencio un campo
        que ningun nodo sabe que existe.
        """
        campos = compose_state_fields(specs)
        desconocidos = set(state.node_writes) - campos
        if desconocidos:
            msg = f"{sorted(desconocidos)} no son campos que declare ningun NodeSpec de `specs`"
            raise GraphStateError(msg)
        return state
