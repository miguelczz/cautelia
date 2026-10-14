"""Lo que las pruebas unitarias de U16 necesitan, sin base de datos.

Mismo patron que `tests/unit/chat/conftest.py`: el catalogo real cargado, porque
comprobar lo que una persona **oye** contra un catalogo falso no diria nada.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from untangle.copy_catalog import api as copy_api
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import TenantConfig


@pytest.fixture
def catalogo_cargado() -> Iterator[None]:
    """El catalogo versionado, instalado para la prueba que lo pida."""
    copy_api.install(copy_api.load())
    tenancy_config.install(tenancy_config.load())
    yield


@pytest.fixture
def aseguradoras() -> tuple[TenantConfig, ...]:
    """Las aseguradoras de la configuracion, en orden de identificador.

    Sin escribir ningun identificador: si una cuarta entra o una sale, las
    pruebas siguen midiendo lo mismo.
    """
    return tuple(sorted(tenancy_config.load().available, key=lambda t: t.tenant_id))
