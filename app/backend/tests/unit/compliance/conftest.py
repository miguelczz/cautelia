"""Lo que comparten las pruebas de la logica de U10.

**Los patrones de verdad**, no unos de prueba: lo que se prueba es que la guardia
y las senales hacen lo que las reglas piden con los archivos versionados que el
aplicativo carga. Una prueba contra patrones inventados comprobaria los patrones
inventados. Donde una prueba necesita un archivo roto, lo escribe en un
directorio temporal a partir de los de verdad.

**Las aseguradoras de la configuracion**, sin escribir ningun identificador: si
una cuarta entra o una sale, las pruebas siguen midiendo lo mismo.

**Nada queda instalado de una prueba a otra**: el catalogo, los patrones y las
aseguradoras del proceso se olvidan antes y despues de cada una, para que cada
prueba se pueda correr sola y en cualquier orden.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from untangle import paths
from untangle.compliance.controls import patterns
from untangle.compliance.controls.guard import GuardContext
from untangle.copy_catalog import api as copy_api
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import TenantConfig


@pytest.fixture(autouse=True)
def _estado_limpio() -> Iterator[None]:
    copy_api.reset()
    patterns.reset()
    tenancy_config.reset()
    yield
    copy_api.reset()
    patterns.reset()
    tenancy_config.reset()


@pytest.fixture(scope="session")
def biblioteca() -> patterns.PatternLibrary:
    """Los ocho archivos de patrones versionados, cargados una vez: son inmutables."""
    return patterns.load_library()


@pytest.fixture(scope="session")
def aseguradoras() -> tuple[TenantConfig, ...]:
    """Las aseguradoras de la configuracion, en orden de identificador."""
    return tuple(sorted(tenancy_config.load().available, key=lambda t: t.tenant_id))


def contexto_de(
    aseguradoras: tuple[TenantConfig, ...],
    idioma: str = "es",
    *,
    case_number: str | None = None,
    source_key: str | None = None,
) -> GuardContext:
    """El contexto de la primera aseguradora, con las demas leidas de la configuracion."""
    assert idioma in ("es", "en")
    return GuardContext.for_tenant(
        aseguradoras[0].tenant_id,
        language="es" if idioma == "es" else "en",
        tenants=aseguradoras,
        case_number=case_number,
        source_key=source_key,
    )


@pytest.fixture
def patrones_copiados(tmp_path: Path) -> Path:
    """Una copia de los patrones de verdad, para romper uno sin tocar el repositorio."""
    destino = tmp_path / "compliance"
    shutil.copytree(paths.compliance_dir(), destino)
    return destino
