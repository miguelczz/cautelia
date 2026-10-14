"""Las filas de DS-8 que pueblan la base efimera de U2.

La base efimera vive en `tests/conftest.py`, porque tambien la piden las pruebas
unitarias del modulo de aislamiento. Aqui solo estan las colisiones.

Las filas se siembran por el **mismo camino** que usa el aplicativo: el punto
unico de sesion. Sembrarlas por una via paralela probaria una via que nadie usa.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest

from untangle import paths
from untangle.tenancy import ephemeral, session

INSERTAR_ENLACE = """
    INSERT INTO case_access_link (
        link_id, tenant_id, case_id, token_digest, access,
        created_at, expires_at, revoked_at, redeemed_count
    ) VALUES (
        :link_id, :tenant_id, :case_id, :token_digest, :access,
        CAST(:created_at AS timestamptz), CAST(:expires_at AS timestamptz),
        CAST(:revoked_at AS timestamptz), :redeemed_count
    )
"""

INSERTAR_CLAVE = """
    INSERT INTO visitor_key (
        tenant_id, visitor_key_hash, origin, created_at, last_seen_at
    ) VALUES (
        :tenant_id, :visitor_key_hash, :origin,
        CAST(:created_at AS timestamptz), CAST(:last_seen_at AS timestamptz)
    )
"""


def load_ds8() -> dict[str, Any]:
    """Las colisiones a proposito de DS-8, desde su archivo versionado.

    No se generan en tiempo de corrida: dos corridas del mismo commit tienen que
    ver exactamente las mismas filas.
    """
    archivo = paths.fixtures_dir() / "ds8_isolation.json"
    datos: dict[str, Any] = json.loads(archivo.read_text(encoding="utf-8"))
    return datos


@pytest.fixture
async def ds8(sesiones: ephemeral.EphemeralDatabase) -> AsyncIterator[dict[str, Any]]:
    """Siembra las filas de DS-8 y deja las tablas vacias al terminar.

    Cada prueba entra con las mismas filas y sale sin dejar ninguna: asi ninguna
    depende del orden de ejecucion ni de lo que dejo otra.
    """
    datos = load_ds8()
    filas = datos["rows"]
    for fila in filas["case_access_links"]:
        async with session.session_for(fila["tenant_id"]) as sesion:
            await session.execute_sql(sesion, INSERTAR_ENLACE, **fila)

    for fila in filas["visitor_keys"]:
        async with session.session_for(fila["tenant_id"]) as sesion:
            await session.execute_sql(sesion, INSERTAR_CLAVE, **fila)

    # Quien vacia las tablas al terminar es la fixture `sesiones`, en el conftest
    # de la raiz: asi hay un solo sitio que lo hace y no dos que puedan divergir.
    yield datos
