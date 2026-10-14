"""Lo que las pruebas de integracion de U16 necesitan en la base efimera.

Mismo patron que U9 (`tests/integration/u9/conftest.py`): los casos se crean con
la API de U4, la base se vacia antes y despues de cada prueba borrando el caso
--`call_session` cuelga de el en cascada-- y ninguna aseguradora se escribe a
mano.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record.models import Channel, Origin, RecordType
from untangle.tenancy import api as tenancy
from untangle.tenancy import ephemeral, session

#: Un instante fijo para toda la suite de U16. El reloj entra por argumento.
AHORA = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class CasoSembrado:
    tenant_id: str
    case_id: str


async def _vaciar() -> None:
    for tenant_id in tenancy.available_ids():
        async with session.session_for(tenant_id) as sesion:
            await session.execute_sql(sesion, "DELETE FROM call_session")
            await session.execute_sql(sesion, "DELETE FROM case_record")
    # **Y los contadores de cuota**, que no son de ninguna aseguradora: viven en
    # el esquema del proyecto. Desde que U17 cablea los carriles, abrir una
    # llamada consume la del dia de ese navegador; sin borrarlos, la segunda
    # prueba que abre una llamada con la misma galleta recibe un 503 por un cupo
    # que gasto la prueba anterior.
    async with session.unscoped_session() as sesion:
        await session.execute_sql(sesion, "DELETE FROM quota_counter")


@pytest.fixture
async def base_de_u16(sesiones: ephemeral.EphemeralDatabase) -> AsyncIterator[None]:
    await _vaciar()
    yield
    await _vaciar()


@pytest.fixture
def dos_aseguradoras() -> tuple[str, str]:
    disponibles = tenancy.available_ids()
    assert len(disponibles) >= 2, "la prueba de aislamiento necesita dos aseguradoras"
    return disponibles[0], disponibles[1]


async def nuevo_caso(tenant_id: str) -> CasoSembrado:
    """Un caso de voz, por la API de U4."""
    case_id = f"u16-caso-{uuid.uuid4().hex[:12]}"
    await casos.create_case(
        tenant_id,
        casos.NewCase(
            case_id=case_id,
            record_type=RecordType.CLAIM,
            channel=Channel.VOICE,
            origin=Origin.PUBLIC_VOICE_CONSOLE,
            language="en",
        ),
        now=AHORA,
    )
    return CasoSembrado(tenant_id=tenant_id, case_id=case_id)


@pytest.fixture
def cifrador(monkeypatch: pytest.MonkeyPatch) -> crypto.Cipher:
    """Un cifrador de prueba, igual que en U13: la clave sale del entorno."""
    monkeypatch.setenv(crypto.KEY_ENV_VAR, crypto.generate_key())
    return crypto.Cipher.from_settings()
