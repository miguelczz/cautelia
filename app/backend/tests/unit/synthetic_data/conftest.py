"""Instala la guardia de red en **toda** prueba de `test:u7` (ver `red.py`)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from .red import NetworkGuard, install_network_guard


@pytest.fixture(autouse=True)
def network_guard(monkeypatch: pytest.MonkeyPatch) -> Iterator[NetworkGuard]:
    """Instalada en cada prueba de la carpeta, sin que la pida.

    Falla la prueba al cerrarla si hubo **algun** intento de conexion, aunque el
    adaptador lo haya convertido en un error y la prueba lo esperara.
    """
    guardia = install_network_guard(monkeypatch)
    yield guardia
    assert not guardia.attempts, (
        "la prueba intento salir a la red, aunque el adaptador haya convertido el "
        f"fallo en un error: {guardia.attempts}"
    )
