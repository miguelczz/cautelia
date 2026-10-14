"""Lo que las pruebas de integracion de U13 necesitan en la base efimera.

Mismo patron que U8, U9, U10 y U11: los casos se crean con la API de U4, ninguna
aseguradora se escribe a mano --son las que ya carga `tenancy.config` desde
`app/config/tenants/`-- y la base se vacia antes y despues de cada prueba.

**Se vacia borrando el caso y las conversaciones**: `chat_session` puede existir
**sin caso** --una conversacion nace en el primer mensaje y el caso solo cuando hay
algo que registrar-- asi que la cascada del caso no basta para dejarla limpia. Los
contadores se vacian igual, que es lo que hace el reinicio nocturno.
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

#: Un instante fijo para toda la suite de U13. El reloj entra por argumento: una
#: conducta que leyera el reloj del proceso solo se podria probar esperando.
AHORA = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


async def _vaciar() -> None:
    """Borra los casos de cada aseguradora; la cascada se lleva lo de U13.

    Sin aseguradora fijada, la politica no dejaria ver ninguna fila y el borrado
    borraria exactamente cero: de ahi el `session_for` por aseguradora.
    """
    for tenant_id in tenancy.available_ids():
        async with session.session_for(tenant_id) as sesion:
            await session.execute_sql(sesion, "DELETE FROM chat_rate_window")
            await session.execute_sql(sesion, "DELETE FROM chat_session")
            await session.execute_sql(sesion, "DELETE FROM case_record")
            # El corpus lo siembra la prueba de la cita expandible; sin borrarlo,
            # una clausula sembrada sobrevive a la prueba que la escribio.
            await session.execute_sql(sesion, "DELETE FROM issued_policies")
            await session.execute_sql(sesion, "DELETE FROM clause_relations")
            await session.execute_sql(sesion, "DELETE FROM clauses")
            await session.execute_sql(sesion, "DELETE FROM policy_forms")


@pytest.fixture
async def base_de_u13(sesiones: ephemeral.EphemeralDatabase) -> AsyncIterator[None]:
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
    tenant_id: str,
    *,
    record_type: RecordType = RecordType.CLAIM,
    policy_ref: str | None = None,
    continues_case_id: str | None = None,
    now: datetime = AHORA,
) -> CasoSembrado:
    """Un caso de chat publico, por la API de U4.

    `policy_ref` es opcional y por omision no se declara ninguna: solo lo
    necesita la prueba de BR6.2 (tanda 3), que siembra dos casos con **la misma**
    poliza de ejemplo para probar que compartirla no basta para ver el caso del
    otro. `continues_case_id` es el caso del que viene, como lo deja un cambio de
    tema en el chat (2026-10-13).
    """
    case_id = f"u13-caso-{uuid.uuid4().hex[:12]}"
    await casos.create_case(
        tenant_id,
        casos.NewCase(
            case_id=case_id,
            record_type=record_type,
            channel=Channel.CHAT,
            origin=Origin.PUBLIC_CHAT,
            language="es",
            policy_ref=policy_ref,
            continues_case_id=continues_case_id,
        ),
        now=now,
    )
    return CasoSembrado(tenant_id=tenant_id, case_id=case_id)
