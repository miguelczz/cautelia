"""El puerto del ajustador en la bandeja: sin enchufe no hay bloque, y su fallo no tumba la lectura."""

from __future__ import annotations

import io
import sys
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from untangle import observability
from untangle.case_record.models import CaseState
from untangle.inbox import adjuster_view, decision
from untangle.inbox.actions import InboxAction
from untangle.tenancy import api as tenancy

CORRIDA = adjuster_view.AdjusterRunOut(
    status="running", attempt=1, updated_at="2026-11-04T15:00:00+00:00"
)


class _Vigia:
    def __init__(self, *, falla: bool = False) -> None:
        self.falla = falla
        self.lecturas: list[tuple[str, str]] = []
        self.reintentos: list[tuple[str, str, CaseState]] = []

    async def read(self, tenant_id: str, case_id: str) -> adjuster_view.AdjusterRunOut | None:
        if self.falla:
            msg = "la base no contesta"
            raise OSError(msg)
        self.lecturas.append((tenant_id, case_id))
        return CORRIDA

    async def retry_if_needed(self, tenant_id: str, case_id: str, state: CaseState) -> None:
        if self.falla:
            msg = "la base no contesta"
            raise OSError(msg)
        self.reintentos.append((tenant_id, case_id, state))


@pytest.fixture
def eventos() -> Iterator[io.StringIO]:
    destino = io.StringIO()
    observability.set_stream(destino)
    adjuster_view.install(None)
    yield destino
    observability.set_stream(sys.stdout)
    adjuster_view.install(None)


async def test_sin_ajustador_enchufado_el_caso_sale_sin_bloque_y_sin_reintento(
    eventos: io.StringIO,
) -> None:
    assert await adjuster_view.read("sunmeadow", "caso-1") is None
    await adjuster_view.retry_if_needed("sunmeadow", "caso-1", CaseState.DERIVED)

    assert eventos.getvalue() == ""


async def test_con_ajustador_enchufado_lee_y_despierta_el_reintento(eventos: io.StringIO) -> None:
    del eventos
    vigia = _Vigia()
    adjuster_view.install(vigia)

    assert await adjuster_view.read("sunmeadow", "caso-1") == CORRIDA
    await adjuster_view.retry_if_needed("sunmeadow", "caso-1", CaseState.DERIVED)

    assert vigia.lecturas == [("sunmeadow", "caso-1")]
    assert vigia.reintentos == [("sunmeadow", "caso-1", CaseState.DERIVED)]


async def test_un_fallo_del_ajustador_deja_rastro_y_no_tumba_la_lectura_del_caso(
    eventos: io.StringIO,
) -> None:
    adjuster_view.install(_Vigia(falla=True))

    assert await adjuster_view.read("sunmeadow", "caso-1") is None
    await adjuster_view.retry_if_needed("sunmeadow", "caso-1", CaseState.DERIVED)

    registro = eventos.getvalue()
    assert '"event": "inbox.adjuster_read_failed"' in registro
    assert '"event": "inbox.adjuster_retry_failed"' in registro


async def test_el_ajustador_de_ia_no_se_hace_pasar_por_personal() -> None:
    """Si se le da un identificador de persona, falla antes de tocar nada."""
    aseguradora = tenancy.load().available[0]

    with pytest.raises(ValueError, match="no es una persona"):
        await decision.decide(
            aseguradora,
            case_id="caso-1",
            action=InboxAction.APPROVE,
            comment="Aprobado.",
            idempotency_key="adjuster-caso-1",
            principal_id="alguien",
            adjuster_ai=True,
            now=datetime(2026, 11, 4, tzinfo=UTC),
        )


async def test_la_decision_sin_comentario_tampoco_pasa_por_el_ajustador_de_ia() -> None:
    aseguradora = tenancy.load().available[0]

    with pytest.raises(decision.CommentRequiredError):
        await decision.decide(
            aseguradora,
            case_id="caso-1",
            action=InboxAction.APPROVE,
            comment="  ",
            idempotency_key="adjuster-caso-1",
            principal_id=None,
            adjuster_ai=True,
            now=datetime(2026, 11, 4, tzinfo=UTC),
        )


def test_el_aviso_al_chat_firma_por_omision_como_personal() -> None:
    firmada_por_personal = decision.DecisionMade(
        tenant_id="sunmeadow",
        case_id="caso-1",
        case_number="AP-1",
        resolution="approved",
        comment="Aprobado.",
        ref="r-1",
        language="es",
    )

    assert firmada_por_personal.actor_type.value == "staff"
