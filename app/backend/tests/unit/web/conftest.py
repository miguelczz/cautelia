"""Lo que comparten las pruebas unitarias de la parte servida de U6."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ..evals.evidence.builders import raiz
from .eventos import Eventos, capturar

__all__ = ["eventos", "raiz"]


@pytest.fixture
def eventos() -> Iterator[Eventos]:
    """Los eventos que emite la prueba, parseados."""
    with capturar() as leer:
        yield leer
