"""Las fixtures del proceso del ajustador."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from untangle.base import Use
from untangle.copy_catalog import api as copy_api
from untangle.telemetry.traces import api as traces

from .support import Mundo, armar_mundo, con_poliza_vigente


@pytest.fixture(autouse=True)
def _catalogo_limpio() -> None:
    copy_api.reset()


@pytest.fixture
def mundo(monkeypatch: pytest.MonkeyPatch) -> Mundo:
    """Un caso derivado de una aseguradora, con poliza vigente y la clausula del choque."""
    mundo = armar_mundo(monkeypatch)
    con_poliza_vigente(mundo)
    return mundo


@pytest.fixture
def turno_abierto() -> Iterator[None]:
    """El tramo de turno que `pipeline.run_case` abre y del que cuelgan las llamadas (BR6.1)."""
    with traces.turn_span(tenant_id="stonecroft", case_id="case-prueba", use=Use.ADJUSTER):
        yield
