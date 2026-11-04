"""Las fixtures del proceso del ajustador."""

from __future__ import annotations

import pytest

from untangle.copy_catalog import api as copy_api

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
