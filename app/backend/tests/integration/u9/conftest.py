"""Lo que las pruebas de integracion de U9 necesitan en la base efimera.

Mismo patron que U10 (`tests/integration/u10/conftest.py`): los casos se crean
con la API de U4, la base se vacia antes y despues de cada prueba borrando el
caso -- `rule_evaluation` cuelga de el en cascada (CG-U9-4) -- y ninguna
aseguradora se escribe a mano.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from untangle.case_record import api as casos
from untangle.case_record.models import Channel, Origin, RecordType
from untangle.tenancy import api as tenancy
from untangle.tenancy import ephemeral, session

#: Un instante fijo para toda la suite de U9. El reloj entra por argumento.
AHORA = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class CasoSembrado:
    """Un caso de una aseguradora, creado con la API de U4."""

    tenant_id: str
    case_id: str


async def _vaciar() -> None:
    for tenant_id in tenancy.available_ids():
        async with session.session_for(tenant_id) as sesion:
            await session.execute_sql(sesion, "DELETE FROM case_record")


@pytest.fixture
async def base_de_u9(sesiones: ephemeral.EphemeralDatabase) -> AsyncIterator[None]:
    """La base efimera, sin casos antes ni despues de cada prueba."""
    await _vaciar()
    yield
    await _vaciar()


@pytest.fixture
def dos_aseguradoras() -> tuple[str, str]:
    disponibles = tenancy.available_ids()
    assert len(disponibles) >= 2, "la prueba de aislamiento necesita dos aseguradoras"
    return disponibles[0], disponibles[1]


async def nuevo_caso(tenant_id: str) -> CasoSembrado:
    """Un caso de chat publico, por la API de U4. `rule_evaluation` no necesita turnos."""
    case_id = f"u9-caso-{uuid.uuid4().hex[:12]}"
    await casos.create_case(
        tenant_id,
        casos.NewCase(
            case_id=case_id,
            record_type=RecordType.CLAIM,
            channel=Channel.CHAT,
            origin=Origin.PUBLIC_CHAT,
            language="es",
        ),
        now=AHORA,
    )
    return CasoSembrado(tenant_id=tenant_id, case_id=case_id)
