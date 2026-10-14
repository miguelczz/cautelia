"""La marca y el caracter de una aseguradora en su configuracion (CG-U6-4, BR1.6).

Llegan **opcionales** (C-25: una clave nueva llega opcional y sin subir
`config_version`), y cuando llegan, con su forma impuesta al cargar: un color mal
escrito apaga la carpeta nombrando el archivo y la clave, en vez de llegar como
un estilo que el navegador ignora en silencio.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from untangle.copy_catalog.models import COPY_KEY_PATTERN
from untangle.tenancy import api as tenancy
from untangle.tenancy import models as tenancy_models


@pytest.fixture
def carpeta() -> dict[str, Any]:
    """La configuracion real de una aseguradora, como mapa, para variarla."""
    return tenancy.load().available[0].model_dump(mode="json")


def test_sin_marca_ni_caracter_la_configuracion_sigue_valiendo(carpeta: dict[str, Any]) -> None:
    carpeta.pop("brand")
    carpeta.pop("character_key", None)

    tenant = tenancy.TenantConfig.model_validate(carpeta)

    assert tenant.brand is None
    assert tenant.character_key is None
    assert tenant.config_version == 1


@pytest.mark.parametrize("color", ["2C5F68", "#2C5F6", "#2C5F68FF", "teal", "#GG5F68"])
def test_un_color_de_marca_sin_la_forma_hexadecimal_se_rechaza(
    carpeta: dict[str, Any], color: str
) -> None:
    carpeta["brand"]["accent"] = color

    with pytest.raises(ValidationError, match=r"brand\.accent"):
        tenancy.TenantConfig.model_validate(carpeta)


def test_un_monograma_fuera_de_los_tres_se_rechaza(carpeta: dict[str, Any]) -> None:
    carpeta["brand"]["monogram"] = "star"

    with pytest.raises(ValidationError, match=r"brand\.monogram"):
        tenancy.TenantConfig.model_validate(carpeta)


def test_la_clave_de_caracter_tiene_la_forma_de_una_clave_del_catalogo(
    carpeta: dict[str, Any],
) -> None:
    carpeta["character_key"] = "home.tenant.character"
    assert tenancy.TenantConfig.model_validate(carpeta).character_key == "home.tenant.character"

    carpeta["character_key"] = "Caracter conservador"
    with pytest.raises(ValidationError, match="character_key"):
        tenancy.TenantConfig.model_validate(carpeta)


def test_la_forma_de_la_clave_de_caracter_es_la_misma_que_la_del_catalogo() -> None:
    """La forma esta escrita dos veces porque `tenancy` no puede importar el catalogo.

    Esta prueba es lo que impide que una cambie sin la otra.
    """
    assert tenancy_models.CHARACTER_KEY_PATTERN == COPY_KEY_PATTERN.pattern


def test_las_tres_aseguradoras_traen_su_marca_y_ningun_monograma_se_repite() -> None:
    """Las tres de la configuracion real se distinguen por su marca en los dos modos."""
    cargadas = tenancy.load().available
    marcas = [t.brand for t in cargadas]

    assert all(marca is not None for marca in marcas)
    monogramas = [marca.monogram for marca in marcas if marca is not None]
    assert len(set(monogramas)) == len(cargadas)
