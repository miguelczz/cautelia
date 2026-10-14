"""El aviso de la decision al chat (fase 1, 2026-10-08): si falla, la decision ya
registrada no se deshace ni le devuelve un error a quien decidio."""

from __future__ import annotations

import io
import sys
from collections.abc import Iterator

import pytest

from untangle import observability
from untangle.inbox import decision

DECIDIDA = decision.DecisionMade(
    tenant_id="stonecroft",
    case_id="caso-1",
    case_number="STO-000001",
    resolution="approved",
    comment="Aprobado.",
    ref="recibo-1",
    language="es",
)


@pytest.fixture
def eventos() -> Iterator[io.StringIO]:
    destino = io.StringIO()
    observability.set_stream(destino)
    yield destino
    observability.set_stream(sys.stdout)
    decision.install_decision_listener(None)


async def test_el_aviso_recibe_la_decision_registrada(eventos: io.StringIO) -> None:
    del eventos
    recibidas: list[decision.DecisionMade] = []

    async def avisar(d: decision.DecisionMade) -> None:
        recibidas.append(d)

    decision.install_decision_listener(avisar)
    await decision._avisar_la_decision(DECIDIDA)

    assert recibidas == [DECIDIDA]


async def test_un_aviso_que_falla_deja_rastro_y_no_levanta(eventos: io.StringIO) -> None:
    async def avisar(_d: decision.DecisionMade) -> None:
        msg = "sin conversacion viva"
        raise RuntimeError(msg)

    decision.install_decision_listener(avisar)
    await decision._avisar_la_decision(DECIDIDA)

    assert '"event": "inbox.decision_notice_failed"' in eventos.getvalue()
