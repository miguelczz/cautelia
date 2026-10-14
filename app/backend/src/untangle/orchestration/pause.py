"""La pausa hacia la bandeja (paso 6 de U12, BR4.1, BR4.4): `HumanReviewRequest`.

**Por que una tabla propia y no solo un campo del caso.** BR4.4 exige poder
decir que una pausa se **retiro** (la persona volvio a tiempo, nadie decidio
nada) y distinguirlo de que se **resolvio** (alguien la decidio desde la
bandeja). Un estado sin historia no puede decir cual de las dos paso; una fila
si, porque nace, y despues se cierra de una forma o de la otra, con su hora.

**Una sola pausa viva por caso, y la base es quien lo decide (BR6.1).** La
migracion de paso 1 ya trae el indice unico parcial
`human_review_request_una_viva` sobre `(tenant_id, case_id) WHERE status = 'open'`.
Este modulo no hace una lectura previa para evitar el choque -- eso dejaria una
ventana entre leer y escribir, la misma carrera que el `INSERT ... ON CONFLICT`
de `activation/repository.py` (U6) ya evita de la misma forma -- sino que
inserta directo y deja que la base decida con `ON CONFLICT ... DO UPDATE`.

**Por que `DO UPDATE` y no `DO NOTHING`.** Un nodo que se reintenta (BR5.2)
puede volver a llamar a `open_pause` con un motivo **distinto** del primer
intento -- la revision del paso 2 encontro exactamente este defecto en el canal
especial `__interrupt__` del checkpointer: la sentencia elegida por lote en vez
de por escritura dejaba que un motivo nuevo se perdiera en silencio al
reintentarse el nodo. Aqui se evita la misma clase de defecto de otra forma: la
fila **se actualiza** con el motivo del intento mas reciente en vez de
conservar el del primero, y `request_id` y `created_at` no se tocan porque
sigue siendo la misma pausa, no una nueva.

**Lo que este modulo no hace.** No decide cuando abrir una pausa -- eso es de
quien deriva (`compliance`, el limite de la demostracion, un proveedor
agotado) o de `abandonment.py` (BR3.3) --, y no invoca el grafo compilado de
verdad: eso es del paso 7, que todavia no existe. `raise_interrupt` solo
envuelve `langgraph.types.interrupt` con la forma que la bandeja necesita, para
que un nodo real la llame sin importar LangGraph el mismo (convencion 5b: el
nucleo no importa proveedores, y aqui el framework del grafo se trata igual
--se envuelve en un solo sitio--).
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from langgraph.types import interrupt as _langgraph_interrupt

from untangle.tenancy.models import TenantId


class PauseReason(StrEnum):
    """El conjunto cerrado de `human_review_request.reason` (BR4.1).

    Los cuatro valores son literales en la migracion de paso 1
    (`node_run_motivo_valido`... no, `human_review_request_motivo_valido`) y se
    repiten aqui como en el resto del proyecto (convencion: los conjuntos
    cerrados de una migracion no se generan desde el enum vivo, y el enum vivo
    no se genera desde la migracion; los dos se escriben y una prueba de
    esquema los compara).
    """

    COMPLIANCE_REFERRAL = "compliance_referral"
    ABUSE = "abuse"
    PROVIDER_FAILURE = "provider_failure"
    INCOMPLETE_CAPTURE = "incomplete_capture"


class PauseStatus(StrEnum):
    """El conjunto cerrado de `human_review_request.status` (BR4.4)."""

    OPEN = "open"
    RESOLVED = "resolved"
    WITHDRAWN = "withdrawn"


@dataclass(frozen=True)
class HumanReviewRequestRecord:
    """Una fila de `human_review_request`, tal como la lee y la escribe este modulo."""

    request_id: str
    tenant_id: TenantId
    case_id: str
    reason: PauseReason
    status: PauseStatus
    created_at: datetime
    resolved_at: datetime | None = None
    withdrawn_at: datetime | None = None


class HumanReviewRequestStore(Protocol):
    """El puerto que `pause.py` y `resume.py` usan para leer y escribir la pausa.

    Mismo patron que `NodeRunStore` (`node_run.py`): la unica implementacion
    real (`pause_repository.DatabaseHumanReviewRequestStore`) toma su conexion
    del punto unico de sesion, con la aseguradora fijada.
    """

    async def insert_open(self, record: HumanReviewRequestRecord) -> HumanReviewRequestRecord:
        """Abre la pausa, o si ya habia una viva, le actualiza el motivo (BR4.1).

        **No comprueba antes de insertar**: el indice unico parcial de la base
        es quien decide, con `ON CONFLICT ... DO UPDATE`, y esta llamada
        siempre devuelve una fila -- la nueva, o la que ya estaba con su
        motivo puesto al dia.
        """
        ...

    async def find_open(
        self, *, tenant_id: TenantId, case_id: str
    ) -> HumanReviewRequestRecord | None: ...

    async def withdraw(
        self, *, tenant_id: TenantId, case_id: str, now: datetime
    ) -> HumanReviewRequestRecord | None:
        """Retira la pausa viva del caso, o `None` si no habia ninguna (BR4.4)."""
        ...


#: Como se genera el identificador de una pausa nueva. Inyectado, como
#: `ClockPort` en el ejecutor: una prueba puede fijarlo para comparar contra un
#: valor exacto en vez de solo "algo no vacio".
IdFactory = Callable[[], str]


def _default_id() -> str:
    return f"hrr-{secrets.token_hex(12)}"


async def open_pause(  # noqa: PLR0913 -- el puerto, las tres llaves de identidad, el motivo y la fabrica de identificadores, ninguno derivable de otro
    store: HumanReviewRequestStore,
    *,
    tenant_id: TenantId,
    case_id: str,
    reason: PauseReason,
    now: datetime,
    id_factory: IdFactory = _default_id,
) -> HumanReviewRequestRecord:
    """Abre la pausa hacia la bandeja con su motivo del conjunto cerrado (BR4.1).

    Es **idempotente por caso, no por llamada**: si el caso ya tenia una pausa
    viva, esta funcion no crea una segunda -- el indice unico de la base no lo
    permitiria -- sino que la deja con el motivo de este intento, el mas
    reciente. Dos llamadas seguidas con el mismo motivo no cambian nada visible;
    dos llamadas con motivos distintos dejan el segundo, nunca el primero.
    """
    candidata = HumanReviewRequestRecord(
        request_id=id_factory(),
        tenant_id=tenant_id,
        case_id=case_id,
        reason=reason,
        status=PauseStatus.OPEN,
        created_at=now,
    )
    return await store.insert_open(candidata)


async def withdraw_pause(
    store: HumanReviewRequestStore, *, tenant_id: TenantId, case_id: str, now: datetime
) -> HumanReviewRequestRecord | None:
    """Retira la pausa viva del caso: `withdrawn`, nunca `resolved` (BR4.4).

    La persona volvio dentro de su ventana y nadie decidio nada; por eso el
    estado no es el mismo que el de una pausa que si paso por la bandeja.
    Retirar un caso sin pausa viva es un no-op, no un error: dos avisos de que
    la persona volvio no son dos motivos de fallar.
    """
    return await store.withdraw(tenant_id=tenant_id, case_id=case_id, now=now)


async def find_pause(
    store: HumanReviewRequestStore, *, tenant_id: TenantId, case_id: str
) -> HumanReviewRequestRecord | None:
    """La pausa viva del caso, o nada."""
    return await store.find_open(tenant_id=tenant_id, case_id=case_id)


def raise_interrupt(reason: PauseReason, **extra: Any) -> Any:
    """El punto real donde un nodo suspende el grafo hacia la bandeja (BR4.1).

    Envuelve `langgraph.types.interrupt`: dentro de una ejecucion del grafo
    compilado con `TenantCheckpointSaver` (paso 2), esto detiene el nodo y deja
    su motivo en el canal especial `__interrupt__` de `graph_checkpoint_write` --
    el mismo canal cuya semantica de "gana el ultimo intento, no el primero" ya
    prueba `test_checkpointer.py` (paso 2). Devuelve lo que traiga
    `Command(resume=...)` cuando alguien retoma la ejecucion (BR4.4).

    Fuera de una ejecucion compilada -- fuera del grafo real, que es del paso 7 --
    LangGraph la rechaza con su propio error; las pruebas de `open_pause` y
    `withdraw_pause` de este archivo no la necesitan, y la prueba que si ejercita
    esta funcion de verdad compila un grafo minimo sobre nuestro checkpointer
    (`tests/integration/u12/test_pause.py`).
    """
    payload: dict[str, Any] = {"reason": reason.value, **extra}
    return _langgraph_interrupt(payload)


__all__ = [
    "HumanReviewRequestRecord",
    "HumanReviewRequestStore",
    "IdFactory",
    "PauseReason",
    "PauseStatus",
    "find_pause",
    "open_pause",
    "raise_interrupt",
    "withdraw_pause",
]
