"""Lo que comparten las pruebas unitarias de la activacion."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ..web.eventos import Eventos, capturar


@pytest.fixture
def eventos() -> Iterator[Eventos]:
    """Los eventos que emite la prueba, parseados."""
    with capturar() as leer:
        yield leer
