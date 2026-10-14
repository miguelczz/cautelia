"""Lo que comparten las pruebas unitarias de U13.

**El catalogo y las aseguradoras de verdad**, no unos de prueba: lo que se
comprueba es lo que una persona lee en la pantalla real. Una apertura medida
contra un catalogo inventado comprobaria el catalogo inventado.

**Nada queda instalado de una prueba a otra**: el catalogo y las aseguradoras del
proceso se olvidan antes y despues de cada una, para que cada prueba se pueda
correr sola y en cualquier orden.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from untangle.copy_catalog import api as copy_api
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import TenantConfig


@pytest.fixture(autouse=True)
def _estado_limpio() -> Iterator[None]:
    copy_api.reset()
    tenancy_config.reset()
    yield
    copy_api.reset()
    tenancy_config.reset()


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
