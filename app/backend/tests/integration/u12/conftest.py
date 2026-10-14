"""Lo que las pruebas de integracion de U12 necesitan en la base efimera.

Mismo patron que U8, U9, U10 y U11: los casos se crean con la API de U4, ninguna
aseguradora se escribe a mano --son las que ya carga `tenancy.config` desde
`app/config/tenants/`-- y la base se vacia antes y despues de cada prueba.

**Se vacia borrando el caso**, no tabla por tabla: las tres de U12 cuelgan del
caso con borrado en cascada, asi que borrar el caso es exactamente como el
reinicio nocturno las vacia, y la limpieza de la prueba no ejercita un camino
distinto del de produccion.
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

#: Un instante fijo para toda la suite de U12. El reloj entra por argumento: una
#: conducta que leyera el reloj del proceso solo se podria probar esperando.
AHORA = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


async def _vaciar() -> None:
    """Borra los casos de cada aseguradora; la cascada se lleva lo de U12.

    Sin aseguradora fijada, la politica no dejaria ver ninguna fila y el borrado
    borraria exactamente cero: de ahi el `session_for` por aseguradora.
    """
    for tenant_id in tenancy.available_ids():
        async with session.session_for(tenant_id) as sesion:
            await session.execute_sql(sesion, "DELETE FROM case_record")


@pytest.fixture
async def base_de_u12(sesiones: ephemeral.EphemeralDatabase) -> AsyncIterator[None]:
    """La base efimera, sin casos antes ni despues de cada prueba."""
    await _vaciar()
    yield
    await _vaciar()


@pytest.fixture
def dos_aseguradoras() -> tuple[str, str]:
    disponibles = tenancy.available_ids()
    assert len(disponibles) >= 2, "las pruebas de aislamiento necesitan dos aseguradoras"
    return disponibles[0], disponibles[1]


@pytest.fixture
def cifrador(monkeypatch: pytest.MonkeyPatch) -> crypto.Cipher:
    monkeypatch.setenv(crypto.KEY_ENV_VAR, crypto.generate_key())
    return crypto.Cipher.from_settings()


@dataclass(frozen=True)
class CasoSembrado:
    """Un caso de una aseguradora, creado con la API de U4."""

    tenant_id: str
    case_id: str


async def nuevo_caso(
    tenant_id: str, *, record_type: RecordType = RecordType.CLAIM, policy_ref: str | None = None
) -> CasoSembrado:
    """Un caso de chat publico, por la API de U4.

    `policy_ref` es opcional y por omision no se declara ninguna: solo lo
    necesita la prueba de BR3.4 (paso 6), que siembra dos casos con **la misma**
    poliza de ejemplo para probar que compartirla no basta para ver el caso del
    otro.
    """
    case_id = f"u12-caso-{uuid.uuid4().hex[:12]}"
    await casos.create_case(
        tenant_id,
        casos.NewCase(
            case_id=case_id,
            record_type=record_type,
            channel=Channel.CHAT,
            origin=Origin.PUBLIC_CHAT,
            language="es",
            policy_ref=policy_ref,
        ),
        now=AHORA,
    )
    return CasoSembrado(tenant_id=tenant_id, case_id=case_id)
