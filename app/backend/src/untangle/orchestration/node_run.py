"""`NodeRun` (BR5.3, BR5.4, BR6.1): una fila por ejecucion de nodo, y su clave de idempotencia.

La tabla es de paso 1 de esta unidad (`migrations/versions/u12_graph_0001_runtime_tables.py`);
lo que este modulo agrega es el vocabulario tipado que la lee y la escribe, y la
funcion que deriva la clave de idempotencia que impide pagarle dos veces al
proveedor por el mismo trabajo (BR5.4): **del caso, el nodo y la entrada -- nunca
del reloj ni de un aleatorio**, igual que `orchestration.nodes.decision.node._evaluation_id`
deriva el identificador de su propia evaluacion.

`NodeRunStore` es el puerto que `executor.py` (paso 4) consume; su unica
implementacion real, `node_run_repository.DatabaseNodeRunStore`, toma su conexion
del punto unico de sesion (C-10), igual que `checkpoint.py` en esta misma unidad.
Las pruebas del ejecutor pasan un doble en memoria -- no una base -- porque lo
que ese paso prueba es la politica de fallo, no el motor de base de datos.

**Enmienda del paso 5 (BR5.5): el arrendamiento con latido.** Las tres columnas
--`lease_owner`, `lease_expires_at`, `heartbeat_at`-- ya existian en la migracion
de paso 1, sin usarlas todavia. El ejecutor las llena en cada intento (aditivo,
sin tocar la politica de reintentos del paso 4): un `node_run` en `running` sin
arrendamiento vigente es indistinguible de un proceso vivo que va lento, y
`find_stale_running` es lo que el barrido de `sweep.py` usa para encontrar los
que sí lo perdieron.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol

from untangle.base import Frozen, ProviderErrorKind
from untangle.telemetry.traces.models import NodeName
from untangle.tenancy.models import TenantId


class NodeRunOutcome(StrEnum):
    """El conjunto cerrado de `node_run.outcome` (restriccion `node_run_desenlace_valido`).

    `ABANDONED` -- el arrendamiento vencio y otro proceso lo tomo -- es del
    barrido de paso 5 de esta unidad; este modulo nunca lo escribe, solo lo
    declara para que el tipo cubra la columna entera. `FAILED` tampoco lo
    escribe el ejecutor de paso 4: aqui un intento agotado siempre es
    `DEGRADED` -- ya se resolvio la clave de su texto --, y `FAILED` queda
    disponible para un fallo que no sea de politica del proveedor (por ejemplo,
    un `NodeRunStore` que no pudo escribir), que no es de este paso.
    """

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEGRADED = "degraded"
    ABANDONED = "abandoned"


#: Los desenlaces que ya no vuelven a intentar el trabajo: BR5.4 se apoya en
#: esta lista para decidir si un relanzamiento puede devolver lo que ya hay sin
#: volver a llamar al proveedor.
TERMINAL_OUTCOMES: frozenset[NodeRunOutcome] = frozenset(
    {NodeRunOutcome.SUCCEEDED, NodeRunOutcome.DEGRADED}
)


@dataclass(frozen=True)
class NodeRunRecord:
    """Una fila de `node_run`, tal como la escribe y la lee el ejecutor de paso 4.

    No trae `node_run_id` como campo propio: la clave de idempotencia identifica
    la fila sola (la unicidad de `(tenant_id, idempotency_key)` es justo lo que
    la migracion de paso 1 ya impone), asi que no hace falta un segundo
    identificador que pudiera desincronizarse del primero.
    """

    tenant_id: TenantId
    case_id: str
    node: NodeName
    rhythm: Literal["turn", "background"]
    attempt: int
    max_attempts: int
    outcome: NodeRunOutcome
    idempotency_key: str
    started_at: datetime
    finished_at: datetime | None = None
    error_type: ProviderErrorKind | None = None
    latency_ms: int | None = None
    #: BR5.5: quien tiene el arrendamiento, y hasta cuando. `None` en las dos
    #: significa "sin arrendamiento vigente" -- el desenlace terminal
    #: (`succeeded`/`degraded`) lo suelta sin mas, y una fila que nunca corrio
    #: bajo esta enmienda tampoco lo trae. La restriccion de la migracion
    #: (`node_run_arrendamiento_completo`) exige que las dos vengan juntas.
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    #: El ultimo latido del proceso que lo ejecuta. Sin el, un arrendamiento
    #: vencido y uno que un proceso vivo esta a punto de renovar se ven igual.
    heartbeat_at: datetime | None = None


def idempotency_key[NodeInputT: Frozen](
    *, tenant_id: TenantId, case_id: str, node: NodeName, node_input: NodeInputT
) -> str:
    """BR5.4: derivada del caso, el nodo y la entrada -- nunca del reloj ni de un aleatorio.

    `node_input` es el modelo `Frozen` que el nodo declara como su entrada
    (`NodeSpec.reads`, C-15) y se vuelca con `model_dump(mode="json")`, igual
    que `decision.node._evaluation_id` vuelca sus insumos: asi dos corridas del
    mismo trabajo -- mismo caso, mismo nodo, misma entrada -- dan la misma clave
    sin importar cuantas veces se relance el proceso, y una entrada distinta (un
    turno nuevo, un dato corregido) da una clave distinta.
    """
    fingerprint = json.dumps(
        {
            "tenant_id": tenant_id,
            "case_id": case_id,
            "node": node.value,
            "input": node_input.model_dump(mode="json"),
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
    return f"noderun-{digest}"


class NodeRunStore(Protocol):
    """El puerto que el ejecutor usa para dejar el rastro de una ejecucion (BR5.3, BR5.4).

    Ni el puerto ni quien lo consume construyen una sesion de base: la unica
    implementacion real (`node_run_repository.DatabaseNodeRunStore`) toma la
    suya del punto unico de sesion (C-10). Las pruebas del ejecutor inyectan un
    doble en memoria.
    """

    async def find(self, *, tenant_id: TenantId, idempotency_key: str) -> NodeRunRecord | None: ...

    async def upsert(self, record: NodeRunRecord) -> None: ...

    async def find_stale_running(
        self, *, tenant_id: TenantId, before: datetime
    ) -> Sequence[NodeRunRecord]:
        """BR5.5: lo que sigue en `running` con `lease_expires_at` anterior a `before`.

        Una fila sin arrendamiento (`lease_expires_at is None`) nunca es
        candidata: significa que ningun proceso bajo esta enmienda la tomo
        todavia, no que la perdio.
        """
        ...


__all__ = [
    "TERMINAL_OUTCOMES",
    "NodeRunOutcome",
    "NodeRunRecord",
    "NodeRunStore",
    "idempotency_key",
]
