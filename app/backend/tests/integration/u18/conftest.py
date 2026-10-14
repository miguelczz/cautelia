"""Lo que las pruebas de U18 necesitan en la base efimera.

**No se construye un segundo juego de dobles ni de fixtures.** Esta unidad habla
la llamada de U16 en el otro idioma, y la forma de defecto que mas ha costado en
este proyecto es un doble mas permisivo que la pieza real. Un doble propio aqui
seria exactamente eso: uno escrito con lo que hacia falta para que el cambio de
idioma se viera, que es como se aprueban pruebas que no prueban.

Asi que se reusan los de U16 tal cual, y lo unico que esta carpeta anade son las
fixtures que pytest no hereda entre carpetas hermanas.
"""

from __future__ import annotations

import pytest

from untangle.copy_catalog import api as copy_api
from untangle.tenancy import config as tenancy_config

from ..u16.conftest import base_de_u16, cifrador, dos_aseguradoras, nuevo_caso

__all__ = ["base_de_u16", "cifrador", "dos_aseguradoras", "nuevo_caso"]


@pytest.fixture
def catalogo() -> None:
    copy_api.install(copy_api.load())
    tenancy_config.install(tenancy_config.load())
