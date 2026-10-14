"""El barrido al arrancar (paso 5, BR5.5): lo vencido pasa a `abandoned`.

Un doble en memoria basta -- lo que se prueba es la decision (que vencio, que
no, y que le pasa a cada una), no el motor de base de datos: eso lo prueba
`tests/integration/u12/test_node_run_repository.py` sobre `find_stale_running`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from untangle.base import Frozen, ProviderErrorKind, Use
from untangle.orchestration.executor import NodeExecutor
from untangle.orchestration.node_run import NodeRunOutcome, NodeRunRecord, idempotency_key
from untangle.orchestration.state import NodeSpec
from untangle.orchestration.sweep import sweep_abandoned
from untangle.telemetry.traces import api as traces
from untangle.telemetry.traces.models import NodeName

_TENANT_ID = "acme"
_AHORA = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


@dataclass
class InMemoryLeaseStore:
    """`NodeRunStore` con `find_stale_running`, para las pruebas de este archivo."""

    filas: dict[tuple[str, str], NodeRunRecord] = field(default_factory=dict)

    async def find(self, *, tenant_id: str, idempotency_key: str) -> NodeRunRecord | None:
        return self.filas.get((tenant_id, idempotency_key))

    async def upsert(self, record: NodeRunRecord) -> None:
        self.filas[(record.tenant_id, record.idempotency_key)] = record

    async def find_stale_running(
        self, *, tenant_id: str, before: datetime
    ) -> tuple[NodeRunRecord, ...]:
        return tuple(
            fila
            for (tid, _), fila in self.filas.items()
            if tid == tenant_id
            and fila.outcome is NodeRunOutcome.RUNNING
            and fila.lease_expires_at is not None
            and fila.lease_expires_at < before
        )


def _running(
    *, clave: str, lease_expires_at: datetime | None, attempt: int = 1, max_attempts: int = 2
) -> NodeRunRecord:
    return NodeRunRecord(
        tenant_id=_TENANT_ID,
        case_id="caso-1",
        node=NodeName.POLICY_VERIFICATION,
        rhythm="background",
        attempt=attempt,
        max_attempts=max_attempts,
        outcome=NodeRunOutcome.RUNNING,
        idempotency_key=clave,
        started_at=_AHORA,
        lease_owner="proceso-muerto" if lease_expires_at is not None else None,
        lease_expires_at=lease_expires_at,
        heartbeat_at=_AHORA if lease_expires_at is not None else None,
    )


async def test_el_barrido_marca_abandoned_solo_lo_vencido() -> None:
    """BR5.5: un arrendamiento sin latido -- vencido -- se considera muerto."""
    store = InMemoryLeaseStore(
        filas={
            (_TENANT_ID, "vencida"): _running(
                clave="vencida", lease_expires_at=_AHORA - timedelta(seconds=1)
            ),
            (_TENANT_ID, "vigente"): _running(
                clave="vigente", lease_expires_at=_AHORA + timedelta(minutes=5)
            ),
        }
    )

    marcadas = await sweep_abandoned(store, tenant_id=_TENANT_ID, now=_AHORA)

    assert {f.idempotency_key for f in marcadas} == {"vencida"}
    vencida = store.filas[(_TENANT_ID, "vencida")]
    assert vencida.outcome is NodeRunOutcome.ABANDONED
    assert vencida.lease_owner is None
    assert vencida.lease_expires_at is None
    # Control positivo: la vigente sigue exactamente como estaba, sin tocar.
    vigente = store.filas[(_TENANT_ID, "vigente")]
    assert vigente.outcome is NodeRunOutcome.RUNNING
    assert vigente.lease_owner == "proceso-muerto"


async def test_el_barrido_no_toca_un_desenlace_terminal_aunque_su_reloj_sea_viejo() -> None:
    """`abandoned` y `degraded` no se colapsan: un `degraded` ya respondio al asegurado."""
    terminal = NodeRunRecord(
        tenant_id=_TENANT_ID,
        case_id="caso-1",
        node=NodeName.POLICY_VERIFICATION,
        rhythm="background",
        attempt=2,
        max_attempts=2,
        outcome=NodeRunOutcome.DEGRADED,
        idempotency_key="ya-resuelta",
        started_at=_AHORA - timedelta(hours=1),
        finished_at=_AHORA - timedelta(hours=1),
        error_type=ProviderErrorKind.UNAVAILABLE,
    )
    store = InMemoryLeaseStore(filas={(_TENANT_ID, "ya-resuelta"): terminal})

    marcadas = await sweep_abandoned(store, tenant_id=_TENANT_ID, now=_AHORA)

    assert marcadas == ()
    assert store.filas[(_TENANT_ID, "ya-resuelta")] == terminal


class _FakeInputSweep(Frozen):
    dato: str


class _FakeOutputSweep(Frozen):
    resultado: str


class _NodoQueRespondeUnaVez:
    """Simula el proceso nuevo que retoma el trabajo tras el barrido: le queda un intento."""

    def __init__(self, spec: NodeSpec) -> None:
        self.spec = spec
        self.llamadas = 0

    async def run(self, state: _FakeInputSweep) -> _FakeOutputSweep:
        self.llamadas += 1
        return _FakeOutputSweep(resultado="listo")


async def test_el_barrido_retoma_lo_pendiente_sin_reiniciar_el_conteo_de_intentos() -> None:
    """BR5.5 + BR5.4: `abandoned` no es terminal, asi que el proximo relanzamiento sigue el conteo.

    Un `NodeSpec` con dos intentos, del que ya se gasto uno antes de que el
    proceso muriera: tras el barrido, al proceso nuevo solo le queda uno.
    """
    entrada = _FakeInputSweep(dato="x")
    spec = NodeSpec(
        name=NodeName.POLICY_VERIFICATION,
        reads=frozenset({"dato"}),
        writes=frozenset({"resultado"}),
        rhythm="background",
        timeout_ms=1_000,
        attempts=2,
        degraded_copy_key="policy_rag.coverage.unverifiable",
    )
    clave = idempotency_key(
        tenant_id=_TENANT_ID, case_id="caso-1", node=spec.name, node_input=entrada
    )
    store = InMemoryLeaseStore(
        filas={
            (_TENANT_ID, clave): _running(
                clave=clave, lease_expires_at=_AHORA - timedelta(seconds=1), attempt=1
            )
        }
    )

    await sweep_abandoned(store, tenant_id=_TENANT_ID, now=_AHORA)
    assert store.filas[(_TENANT_ID, clave)].outcome is NodeRunOutcome.ABANDONED

    nodo = _NodoQueRespondeUnaVez(spec)
    ejecutor = NodeExecutor(store=store, clock=lambda: _AHORA)
    with traces.turn_span(tenant_id=_TENANT_ID, case_id="caso-1", use=Use.OPERATIONS):
        resultado = await ejecutor.run(nodo, entrada, tenant_id=_TENANT_ID, case_id="caso-1")

    assert nodo.llamadas == 1, "solo le quedaba un intento: el conteo no se reinicio a cero"
    assert resultado.outcome is NodeRunOutcome.SUCCEEDED
    assert resultado.attempts == 2
