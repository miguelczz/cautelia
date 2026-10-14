"""La pausa hacia la bandeja (paso 6 de U12): la logica de negocio, con un doble.

`test_pause_repository.py` (integracion) prueba la semantica real de
`ON CONFLICT ... DO UPDATE` contra Postgres -- eso es del motor de base de
datos y no se duplica aqui. Lo que este archivo prueba es lo que `pause.py`
hace **el mismo**: que arma la fila candidata con los campos correctos y que
delega en el puerto sin decidir nada por su cuenta (BR4.1, BR4.4), y que
`mark_abandoned` (BR3.3) siempre usa el motivo `incomplete_capture` y no toca
nada mas.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from untangle.orchestration.abandonment import mark_abandoned
from untangle.orchestration.pause import (
    HumanReviewRequestRecord,
    PauseReason,
    PauseStatus,
    find_pause,
    open_pause,
    withdraw_pause,
)

_TENANT_ID = "acme"
_CASE_ID = "case-1"
_AHORA = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


@dataclass
class FakeHumanReviewRequestStore:
    """Un `HumanReviewRequestStore` en memoria, con la misma regla que la base.

    Una sola fila viva por caso: `insert_open` sobre un caso que ya tiene una
    viva **actualiza su motivo** en vez de crear una segunda, igual que
    `ON CONFLICT ... DO UPDATE` en la pieza real -- es la unica pieza de la
    semantica de la base que este doble reproduce, porque es la que
    `open_pause` necesita para que sus propias pruebas tengan sentido sin
    Postgres delante.
    """

    filas: dict[tuple[str, str], HumanReviewRequestRecord] = field(default_factory=dict)
    llamadas_insert: list[HumanReviewRequestRecord] = field(default_factory=list)

    async def insert_open(self, record: HumanReviewRequestRecord) -> HumanReviewRequestRecord:
        self.llamadas_insert.append(record)
        clave = (record.tenant_id, record.case_id)
        viva = self.filas.get(clave)
        if viva is not None and viva.status is PauseStatus.OPEN:
            actualizada = HumanReviewRequestRecord(
                request_id=viva.request_id,
                tenant_id=viva.tenant_id,
                case_id=viva.case_id,
                reason=record.reason,
                status=PauseStatus.OPEN,
                created_at=viva.created_at,
            )
            self.filas[clave] = actualizada
            return actualizada
        self.filas[clave] = record
        return record

    async def find_open(self, *, tenant_id: str, case_id: str) -> HumanReviewRequestRecord | None:
        fila = self.filas.get((tenant_id, case_id))
        return fila if fila is not None and fila.status is PauseStatus.OPEN else None

    async def withdraw(
        self, *, tenant_id: str, case_id: str, now: datetime
    ) -> HumanReviewRequestRecord | None:
        clave = (tenant_id, case_id)
        viva = self.filas.get(clave)
        if viva is None or viva.status is not PauseStatus.OPEN:
            return None
        retirada = HumanReviewRequestRecord(
            request_id=viva.request_id,
            tenant_id=viva.tenant_id,
            case_id=viva.case_id,
            reason=viva.reason,
            status=PauseStatus.WITHDRAWN,
            created_at=viva.created_at,
            withdrawn_at=now,
        )
        self.filas[clave] = retirada
        return retirada


def _ids() -> Callable[[], str]:
    """Una fabrica de identificadores fija, para comparar contra un valor exacto."""
    contador = {"n": 0}

    def siguiente() -> str:
        contador["n"] += 1
        return f"hrr-fijo-{contador['n']}"

    return siguiente


# --- 1. `open_pause` arma la fila y delega (BR4.1) -----------------------------


async def test_open_pause_arma_la_fila_con_los_campos_pedidos() -> None:
    store = FakeHumanReviewRequestStore()

    creada = await open_pause(
        store,
        tenant_id=_TENANT_ID,
        case_id=_CASE_ID,
        reason=PauseReason.COMPLIANCE_REFERRAL,
        now=_AHORA,
        id_factory=_ids(),
    )

    assert creada.request_id == "hrr-fijo-1"
    assert creada.tenant_id == _TENANT_ID
    assert creada.case_id == _CASE_ID
    assert creada.reason is PauseReason.COMPLIANCE_REFERRAL
    assert creada.status is PauseStatus.OPEN
    assert creada.created_at == _AHORA
    assert len(store.llamadas_insert) == 1


async def test_open_pause_no_duplica_una_pausa_viva_del_mismo_caso() -> None:
    """Control positivo antes de la negativa de abajo: la primera si abre una fila."""
    store = FakeHumanReviewRequestStore()
    primera = await open_pause(
        store,
        tenant_id=_TENANT_ID,
        case_id=_CASE_ID,
        reason=PauseReason.PROVIDER_FAILURE,
        now=_AHORA,
        id_factory=_ids(),
    )
    assert primera.reason is PauseReason.PROVIDER_FAILURE  # control positivo

    segunda = await open_pause(
        store,
        tenant_id=_TENANT_ID,
        case_id=_CASE_ID,
        reason=PauseReason.ABUSE,
        now=_AHORA + timedelta(seconds=1),
        id_factory=_ids(),
    )

    # Misma pausa (mismo identificador), motivo del intento mas reciente.
    assert segunda.request_id == primera.request_id
    assert segunda.reason is PauseReason.ABUSE
    viva = await find_pause(store, tenant_id=_TENANT_ID, case_id=_CASE_ID)
    assert viva is not None
    assert viva.reason is PauseReason.ABUSE


# --- 2. `withdraw_pause` (BR4.4) ------------------------------------------------


async def test_withdraw_pause_retira_la_viva_y_deja_nada_para_una_ausente() -> None:
    store = FakeHumanReviewRequestStore()
    await open_pause(
        store,
        tenant_id=_TENANT_ID,
        case_id=_CASE_ID,
        reason=PauseReason.INCOMPLETE_CAPTURE,
        now=_AHORA,
        id_factory=_ids(),
    )

    retirada = await withdraw_pause(
        store, tenant_id=_TENANT_ID, case_id=_CASE_ID, now=_AHORA + timedelta(minutes=1)
    )
    assert retirada is not None
    assert retirada.status is PauseStatus.WITHDRAWN

    sin_pausa = await withdraw_pause(store, tenant_id=_TENANT_ID, case_id="otro-caso", now=_AHORA)
    assert sin_pausa is None


# --- 3. `mark_abandoned` usa siempre `incomplete_capture` (BR3.3) --------------


async def test_mark_abandoned_usa_el_motivo_captura_incompleta() -> None:
    store = FakeHumanReviewRequestStore()

    pausa = await mark_abandoned(store, tenant_id=_TENANT_ID, case_id=_CASE_ID, now=_AHORA)

    assert pausa.reason is PauseReason.INCOMPLETE_CAPTURE
    assert pausa.status is PauseStatus.OPEN


@pytest.mark.parametrize("motivo", list(PauseReason))
async def test_mark_abandoned_sobreescribe_cualquier_pausa_previa_a_incompleta(
    motivo: PauseReason,
) -> None:
    """Una captura que se abandona a medias de una derivacion sigue siendo captura incompleta.

    Si otra causa ya habia abierto la pausa (por ejemplo, cumplimiento derivo y
    la persona se fue antes de que la bandeja la viera), el motivo que queda es
    el de la sesion abandonada: es el ultimo evento que paso, y BR3.3 exige que
    no se decida nada sobre una captura a medias -- conservar un motivo viejo
    seria decidir que ese sigue siendo el estado real.
    """
    store = FakeHumanReviewRequestStore()
    await open_pause(
        store, tenant_id=_TENANT_ID, case_id=_CASE_ID, reason=motivo, now=_AHORA, id_factory=_ids()
    )

    pausa = await mark_abandoned(
        store, tenant_id=_TENANT_ID, case_id=_CASE_ID, now=_AHORA + timedelta(minutes=1)
    )

    assert pausa.reason is PauseReason.INCOMPLETE_CAPTURE
