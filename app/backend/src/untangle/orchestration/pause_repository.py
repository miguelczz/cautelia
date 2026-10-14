"""`DatabaseHumanReviewRequestStore`: el `HumanReviewRequestStore` real (paso 6, BR4.1, BR4.4, BR6.1).

Mismo patron que `node_run_repository.py` y `checkpoint.py` en esta misma
unidad: toda conexion sale del punto unico de sesion, con la aseguradora ya
fijada. `insert_open` es una sola sentencia `INSERT ... ON CONFLICT ... DO
UPDATE`: la base decide si ya habia una pausa viva a traves del indice unico
parcial de la migracion, no una lectura previa de este modulo (BR6.1, aviso de
esta etapa).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from untangle.orchestration.pause import HumanReviewRequestRecord, PauseReason, PauseStatus
from untangle.tenancy import session
from untangle.tenancy.models import TenantId

_COLUMNAS = "request_id, tenant_id, case_id, reason, status, created_at, resolved_at, withdrawn_at"

_INSERTAR_O_ACTUALIZAR_MOTIVO = f"""
    INSERT INTO human_review_request
        (request_id, tenant_id, case_id, reason, status, created_at)
    VALUES
        (:request_id, :tenant_id, :case_id, :reason, 'open', :created_at)
    ON CONFLICT (tenant_id, case_id) WHERE status = 'open'
        DO UPDATE SET reason = excluded.reason
    RETURNING {_COLUMNAS}
"""  # noqa: S608 -- `_COLUMNAS` es una constante del modulo, no una entrada; los valores van ligados

_BUSCAR_ABIERTA = f"""
    SELECT {_COLUMNAS}
    FROM human_review_request
    WHERE tenant_id = :tenant_id AND case_id = :case_id AND status = 'open'
"""  # noqa: S608 -- misma constante, mismo motivo

_RETIRAR = f"""
    UPDATE human_review_request
    SET status = 'withdrawn', withdrawn_at = :withdrawn_at
    WHERE tenant_id = :tenant_id AND case_id = :case_id AND status = 'open'
    RETURNING {_COLUMNAS}
"""  # noqa: S608 -- misma constante, mismo motivo


def _from_row(fila: Mapping[str, Any]) -> HumanReviewRequestRecord:
    return HumanReviewRequestRecord(
        request_id=fila["request_id"],
        tenant_id=fila["tenant_id"],
        case_id=fila["case_id"],
        reason=PauseReason(fila["reason"]),
        status=PauseStatus(fila["status"]),
        created_at=fila["created_at"],
        resolved_at=fila["resolved_at"],
        withdrawn_at=fila["withdrawn_at"],
    )


class DatabaseHumanReviewRequestStore:
    """El `HumanReviewRequestStore` real, sobre `human_review_request`."""

    async def insert_open(self, record: HumanReviewRequestRecord) -> HumanReviewRequestRecord:
        async with session.session_for(record.tenant_id) as sesion:
            fila = await session.fetch_one(
                sesion,
                _INSERTAR_O_ACTUALIZAR_MOTIVO,
                request_id=record.request_id,
                tenant_id=record.tenant_id,
                case_id=record.case_id,
                reason=record.reason.value,
                created_at=record.created_at,
            )
        # `RETURNING` siempre trae fila con `DO UPDATE` (a diferencia de
        # `DO NOTHING`): o se inserto la nueva, o se actualizo la que habia.
        assert fila is not None  # noqa: S101 -- invariante de la sentencia, no una entrada de usuario
        return _from_row(fila)

    async def find_open(
        self, *, tenant_id: TenantId, case_id: str
    ) -> HumanReviewRequestRecord | None:
        async with session.session_for(tenant_id) as sesion:
            fila = await session.fetch_one(
                sesion, _BUSCAR_ABIERTA, tenant_id=tenant_id, case_id=case_id
            )
        return _from_row(fila) if fila is not None else None

    async def withdraw(
        self, *, tenant_id: TenantId, case_id: str, now: datetime
    ) -> HumanReviewRequestRecord | None:
        async with session.session_for(tenant_id) as sesion:
            fila = await session.fetch_one(
                sesion, _RETIRAR, tenant_id=tenant_id, case_id=case_id, withdrawn_at=now
            )
        return _from_row(fila) if fila is not None else None


__all__ = ["DatabaseHumanReviewRequestStore"]
