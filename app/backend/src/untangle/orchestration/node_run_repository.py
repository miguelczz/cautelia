"""`DatabaseNodeRunStore`: el `NodeRunStore` real sobre la tabla `node_run` (paso 1 de esta unidad).

Mismo patron que `checkpoint.py` en esta misma unidad: toda conexion sale del
punto unico de sesion (C-10), con la aseguradora ya fijada, y el `UPSERT` apunta
a la restriccion de unicidad de la migracion (`node_run_trabajo_unico`) como su
objetivo de conflicto -- es la base, no este modulo, quien impide dos filas para
el mismo trabajo (BR5.4). `node_run_id` se llena con la propia clave de
idempotencia: es unica por aseguradora igual que la fila que identifica, y asi no
hace falta generar ni guardar un segundo identificador.

**Paso 5 (BR5.5):** el `UPSERT` suma las tres columnas del arrendamiento, ya
declaradas en la migracion de paso 1 y sin usar hasta ahora, y `find_stale_running`
es la consulta que el barrido de `sweep.py` necesita -- filtrada por aseguradora,
como toda consulta de este modulo (C-10).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Literal, cast

from untangle.base import ProviderErrorKind
from untangle.orchestration.node_run import NodeRunOutcome, NodeRunRecord
from untangle.telemetry.traces.models import NodeName
from untangle.tenancy import session
from untangle.tenancy.models import TenantId

_COLUMNAS = (
    "case_id, node, rhythm, attempt, max_attempts, outcome, error_type, "
    "latency_ms, idempotency_key, started_at, finished_at, "
    "lease_owner, lease_expires_at, heartbeat_at"
)

_BUSCAR = f"""
    SELECT {_COLUMNAS}
    FROM node_run
    WHERE tenant_id = :tenant_id AND idempotency_key = :idempotency_key
"""  # noqa: S608 -- `_COLUMNAS` es una constante del modulo, no una entrada; los valores van ligados

_BUSCAR_VENCIDAS = f"""
    SELECT {_COLUMNAS}
    FROM node_run
    WHERE tenant_id = :tenant_id AND outcome = 'running'
      AND lease_expires_at IS NOT NULL AND lease_expires_at < :before
"""  # noqa: S608 -- misma constante, mismo motivo

_UPSERT = """
    INSERT INTO node_run
        (node_run_id, tenant_id, case_id, node, rhythm, attempt, max_attempts,
         outcome, error_type, latency_ms, idempotency_key, started_at, finished_at,
         lease_owner, lease_expires_at, heartbeat_at)
    VALUES
        (:node_run_id, :tenant_id, :case_id, :node, :rhythm, :attempt, :max_attempts,
         :outcome, :error_type, :latency_ms, :idempotency_key, :started_at, :finished_at,
         :lease_owner, :lease_expires_at, :heartbeat_at)
    ON CONFLICT ON CONSTRAINT node_run_trabajo_unico DO UPDATE SET
        attempt = excluded.attempt,
        outcome = excluded.outcome,
        error_type = excluded.error_type,
        latency_ms = excluded.latency_ms,
        finished_at = excluded.finished_at,
        lease_owner = excluded.lease_owner,
        lease_expires_at = excluded.lease_expires_at,
        heartbeat_at = excluded.heartbeat_at
"""


def _from_row(tenant_id: TenantId, fila: Mapping[str, Any]) -> NodeRunRecord:
    error_type = fila["error_type"]
    return NodeRunRecord(
        tenant_id=tenant_id,
        case_id=fila["case_id"],
        node=NodeName(fila["node"]),
        rhythm=cast(Literal["turn", "background"], fila["rhythm"]),
        attempt=fila["attempt"],
        max_attempts=fila["max_attempts"],
        outcome=NodeRunOutcome(fila["outcome"]),
        idempotency_key=fila["idempotency_key"],
        started_at=fila["started_at"],
        finished_at=fila["finished_at"],
        error_type=ProviderErrorKind(error_type) if error_type is not None else None,
        latency_ms=fila["latency_ms"],
        lease_owner=fila["lease_owner"],
        lease_expires_at=fila["lease_expires_at"],
        heartbeat_at=fila["heartbeat_at"],
    )


class DatabaseNodeRunStore:
    """El `NodeRunStore` real (paso 4, con el arrendamiento del paso 5): una fila por `(tenant_id, idempotency_key)`."""

    async def find(self, *, tenant_id: TenantId, idempotency_key: str) -> NodeRunRecord | None:
        async with session.session_for(tenant_id) as sesion:
            fila = await session.fetch_one(
                sesion, _BUSCAR, tenant_id=tenant_id, idempotency_key=idempotency_key
            )
        if fila is None:
            return None
        return _from_row(tenant_id, fila)

    async def find_stale_running(
        self, *, tenant_id: TenantId, before: datetime
    ) -> Sequence[NodeRunRecord]:
        """BR5.5: lo que sigue `running` con el arrendamiento vencido antes de `before`."""
        async with session.session_for(tenant_id) as sesion:
            filas = await session.fetch_all(
                sesion, _BUSCAR_VENCIDAS, tenant_id=tenant_id, before=before
            )
        return tuple(_from_row(tenant_id, fila) for fila in filas)

    async def upsert(self, record: NodeRunRecord) -> None:
        ahora_finished_at: datetime | None = record.finished_at
        async with session.session_for(record.tenant_id) as sesion:
            await session.execute_sql(
                sesion,
                _UPSERT,
                node_run_id=record.idempotency_key,
                tenant_id=record.tenant_id,
                case_id=record.case_id,
                node=record.node.value,
                rhythm=record.rhythm,
                attempt=record.attempt,
                max_attempts=record.max_attempts,
                outcome=record.outcome.value,
                error_type=record.error_type.value if record.error_type is not None else None,
                latency_ms=record.latency_ms,
                idempotency_key=record.idempotency_key,
                started_at=record.started_at,
                finished_at=ahora_finished_at,
                lease_owner=record.lease_owner,
                lease_expires_at=record.lease_expires_at,
                heartbeat_at=record.heartbeat_at,
            )


__all__ = ["DatabaseNodeRunStore"]
