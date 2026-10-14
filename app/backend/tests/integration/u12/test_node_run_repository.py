"""`DatabaseNodeRunStore`: la capa de datos de `node_run` (paso 4, BR5.4; paso 5, BR5.5).

`test_runtime_tables.py` (paso 1) ya prueba la tabla con SQL directo: su
aislamiento y sus restricciones. Lo que este archivo cierra es lo que ese paso
no podia mostrar todavia -- que la pieza que el ejecutor de verdad usa toma su
clave de idempotencia como identidad de la fila, y que **la base, no el
codigo**, es quien impide dos filas para el mismo trabajo (BR5.4): dos intentos
del mismo trabajo actualizan la misma fila en vez de duplicarla. El paso 5 suma
`find_stale_running`: la consulta del barrido, sobre datos y aislamiento reales.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from untangle.base import ProviderErrorKind
from untangle.orchestration.node_run import NodeRunOutcome, NodeRunRecord
from untangle.orchestration.node_run_repository import DatabaseNodeRunStore
from untangle.telemetry.traces.models import NodeName
from untangle.tenancy import session

from .conftest import nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u12")

_AHORA = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def _fila(  # noqa: PLR0913 -- las cinco llaves de la fila mas el error y el arrendamiento opcionales, ninguno derivable de otro
    *,
    tenant_id: str,
    case_id: str,
    idempotency_key: str,
    attempt: int,
    outcome: NodeRunOutcome,
    error_type: ProviderErrorKind | None = None,
    lease_owner: str | None = None,
    lease_expires_at: datetime | None = None,
    heartbeat_at: datetime | None = None,
) -> NodeRunRecord:
    return NodeRunRecord(
        tenant_id=tenant_id,
        case_id=case_id,
        node=NodeName.DECISION,
        rhythm="background",
        attempt=attempt,
        max_attempts=2,
        outcome=outcome,
        idempotency_key=idempotency_key,
        started_at=_AHORA,
        finished_at=_AHORA if outcome is not NodeRunOutcome.RUNNING else None,
        error_type=error_type,
        lease_owner=lease_owner,
        lease_expires_at=lease_expires_at,
        heartbeat_at=heartbeat_at,
    )


async def test_upsert_crea_una_fila_y_find_la_recupera(dos_aseguradoras: tuple[str, str]) -> None:
    tenant_id, _ = dos_aseguradoras
    caso = await nuevo_caso(tenant_id)
    store = DatabaseNodeRunStore()
    clave = f"noderun-{caso.case_id}-1"

    await store.upsert(
        _fila(
            tenant_id=tenant_id,
            case_id=caso.case_id,
            idempotency_key=clave,
            attempt=1,
            outcome=NodeRunOutcome.SUCCEEDED,
        )
    )

    encontrada = await store.find(tenant_id=tenant_id, idempotency_key=clave)
    assert encontrada is not None
    assert encontrada.outcome is NodeRunOutcome.SUCCEEDED
    assert encontrada.attempt == 1
    assert encontrada.case_id == caso.case_id
    assert encontrada.node is NodeName.DECISION


async def test_buscar_una_clave_que_no_existe_da_none(dos_aseguradoras: tuple[str, str]) -> None:
    tenant_id, _ = dos_aseguradoras
    store = DatabaseNodeRunStore()

    assert await store.find(tenant_id=tenant_id, idempotency_key="noderun-nunca-existio") is None


async def test_dos_intentos_del_mismo_trabajo_actualizan_la_misma_fila_no_duplican(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR5.4: la restriccion `node_run_trabajo_unico` es la que impide la segunda fila."""
    tenant_id, _ = dos_aseguradoras
    caso = await nuevo_caso(tenant_id)
    store = DatabaseNodeRunStore()
    clave = f"noderun-{caso.case_id}-reintento"

    await store.upsert(
        # Sin `error_type`: una fila `running` nunca lo lleva -- la restriccion
        # `node_run_error_con_su_desenlace` de la migracion (paso 1) solo lo
        # exige, y lo permite, en `failed`/`degraded`.
        _fila(
            tenant_id=tenant_id,
            case_id=caso.case_id,
            idempotency_key=clave,
            attempt=1,
            outcome=NodeRunOutcome.RUNNING,
        )
    )
    await store.upsert(
        _fila(
            tenant_id=tenant_id,
            case_id=caso.case_id,
            idempotency_key=clave,
            attempt=2,
            outcome=NodeRunOutcome.DEGRADED,
            error_type=ProviderErrorKind.UNAVAILABLE,
        )
    )

    async with session.session_for(tenant_id) as sesion:
        filas = await session.fetch_all(
            sesion,
            "SELECT attempt, outcome FROM node_run WHERE tenant_id = :tenant_id AND idempotency_key = :clave",
            tenant_id=tenant_id,
            clave=clave,
        )
    assert len(filas) == 1, (
        "un relanzamiento no gasta dos veces: una sola fila para el mismo trabajo"
    )
    assert filas[0]["attempt"] == 2
    assert filas[0]["outcome"] == "degraded"

    encontrada = await store.find(tenant_id=tenant_id, idempotency_key=clave)
    assert encontrada is not None
    assert encontrada.outcome is NodeRunOutcome.DEGRADED
    assert encontrada.attempt == 2


async def test_dos_trabajos_distintos_del_mismo_caso_no_se_pisan(
    dos_aseguradoras: tuple[str, str],
) -> None:
    tenant_id, _ = dos_aseguradoras
    caso = await nuevo_caso(tenant_id)
    store = DatabaseNodeRunStore()

    await store.upsert(
        _fila(
            tenant_id=tenant_id,
            case_id=caso.case_id,
            idempotency_key=f"noderun-{caso.case_id}-a",
            attempt=1,
            outcome=NodeRunOutcome.SUCCEEDED,
        )
    )
    await store.upsert(
        _fila(
            tenant_id=tenant_id,
            case_id=caso.case_id,
            idempotency_key=f"noderun-{caso.case_id}-b",
            attempt=1,
            outcome=NodeRunOutcome.DEGRADED,
            error_type=ProviderErrorKind.TIMEOUT,
        )
    )

    async with session.session_for(tenant_id) as sesion:
        filas = await session.fetch_all(
            sesion,
            "SELECT idempotency_key FROM node_run WHERE tenant_id = :tenant_id AND case_id = :case_id",
            tenant_id=tenant_id,
            case_id=caso.case_id,
        )
    assert {f["idempotency_key"] for f in filas} == {
        f"noderun-{caso.case_id}-a",
        f"noderun-{caso.case_id}-b",
    }


async def test_la_fila_de_una_aseguradora_no_se_le_entrega_a_otra(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR6.1 a traves de la pieza, no de una consulta escrita a mano.

    El control positivo va delante a proposito: sin el, la asercion negativa
    pasaria igual con un `find` que no devolviera nunca nada.
    """
    ajena, propia = dos_aseguradoras
    caso = await nuevo_caso(ajena)
    store = DatabaseNodeRunStore()
    clave = f"noderun-{caso.case_id}-ajena"

    await store.upsert(
        _fila(
            tenant_id=ajena,
            case_id=caso.case_id,
            idempotency_key=clave,
            attempt=1,
            outcome=NodeRunOutcome.SUCCEEDED,
        )
    )

    assert await store.find(tenant_id=ajena, idempotency_key=clave) is not None
    assert await store.find(tenant_id=propia, idempotency_key=clave) is None


# --- BR5.5: el arrendamiento con latido, sobre la base de verdad ----------------


async def test_upsert_guarda_el_arrendamiento_y_find_lo_devuelve(
    dos_aseguradoras: tuple[str, str],
) -> None:
    tenant_id, _ = dos_aseguradoras
    caso = await nuevo_caso(tenant_id)
    store = DatabaseNodeRunStore()
    clave = f"noderun-{caso.case_id}-arrendada"

    await store.upsert(
        _fila(
            tenant_id=tenant_id,
            case_id=caso.case_id,
            idempotency_key=clave,
            attempt=1,
            outcome=NodeRunOutcome.RUNNING,
            lease_owner="proceso-1",
            lease_expires_at=_AHORA + timedelta(seconds=30),
            heartbeat_at=_AHORA,
        )
    )

    encontrada = await store.find(tenant_id=tenant_id, idempotency_key=clave)
    assert encontrada is not None
    assert encontrada.lease_owner == "proceso-1"
    assert encontrada.lease_expires_at == _AHORA + timedelta(seconds=30)
    assert encontrada.heartbeat_at == _AHORA


async def test_find_stale_running_solo_devuelve_lo_running_con_el_arrendamiento_vencido(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR5.5: vencida y `running`, si; vigente, terminal o sin arrendamiento, no."""
    tenant_id, _ = dos_aseguradoras
    caso = await nuevo_caso(tenant_id)
    store = DatabaseNodeRunStore()
    ahora = _AHORA + timedelta(hours=1)

    await store.upsert(
        _fila(
            tenant_id=tenant_id,
            case_id=caso.case_id,
            idempotency_key=f"noderun-{caso.case_id}-vencida",
            attempt=1,
            outcome=NodeRunOutcome.RUNNING,
            lease_owner="proceso-muerto",
            lease_expires_at=ahora - timedelta(seconds=1),
            heartbeat_at=ahora - timedelta(seconds=10),
        )
    )
    await store.upsert(
        _fila(
            tenant_id=tenant_id,
            case_id=caso.case_id,
            idempotency_key=f"noderun-{caso.case_id}-vigente",
            attempt=1,
            outcome=NodeRunOutcome.RUNNING,
            lease_owner="proceso-vivo",
            lease_expires_at=ahora + timedelta(minutes=5),
            heartbeat_at=ahora,
        )
    )
    await store.upsert(
        _fila(
            tenant_id=tenant_id,
            case_id=caso.case_id,
            idempotency_key=f"noderun-{caso.case_id}-sin-arrendamiento",
            attempt=1,
            outcome=NodeRunOutcome.RUNNING,
        )
    )
    await store.upsert(
        _fila(
            tenant_id=tenant_id,
            case_id=caso.case_id,
            idempotency_key=f"noderun-{caso.case_id}-terminal-vieja",
            attempt=2,
            outcome=NodeRunOutcome.DEGRADED,
            error_type=ProviderErrorKind.UNAVAILABLE,
        )
    )

    vencidas = await store.find_stale_running(tenant_id=tenant_id, before=ahora)

    assert {f.idempotency_key for f in vencidas} == {f"noderun-{caso.case_id}-vencida"}


async def test_find_stale_running_no_cruza_aseguradoras(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR6.1 a traves de la pieza: el barrido de una aseguradora no ve lo vencido de otra."""
    ajena, propia = dos_aseguradoras
    caso = await nuevo_caso(ajena)
    store = DatabaseNodeRunStore()
    ahora = _AHORA + timedelta(hours=1)

    await store.upsert(
        _fila(
            tenant_id=ajena,
            case_id=caso.case_id,
            idempotency_key=f"noderun-{caso.case_id}-vencida",
            attempt=1,
            outcome=NodeRunOutcome.RUNNING,
            lease_owner="proceso-muerto",
            lease_expires_at=ahora - timedelta(seconds=1),
            heartbeat_at=ahora - timedelta(seconds=10),
        )
    )

    # Control positivo: para su propia aseguradora, el barrido si la encuentra.
    assert len(await store.find_stale_running(tenant_id=ajena, before=ahora)) == 1
    assert await store.find_stale_running(tenant_id=propia, before=ahora) == ()
