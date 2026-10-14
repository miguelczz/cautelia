"""Lo que comparten las pruebas de U9: nada queda instalado de una a otra.

El motor de reglas y la configuracion de aseguradoras se olvidan antes y
despues de cada prueba, para que cada una se pueda correr sola y en cualquier
orden (mismo patron que `tests/unit/compliance/conftest.py`).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from untangle.rules import eligibility as rules_eligibility
from untangle.rules import loading as rules_loading
from untangle.tenancy import config as tenancy_config


@pytest.fixture(autouse=True)
def _estado_limpio() -> Iterator[None]:
    tenancy_config.reset()
    rules_loading.reset()
    rules_eligibility.reset()
    yield
    tenancy_config.reset()
    rules_loading.reset()
    rules_eligibility.reset()
