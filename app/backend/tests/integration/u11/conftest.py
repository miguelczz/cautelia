"""Lo que las pruebas de integracion de U11 necesitan en la base efimera.

Mismo patron que U8, U9 y U10: los casos se crean con la API de U4, ninguna
aseguradora se escribe a mano -- son las que ya carga `tenancy.config` desde
`app/config/tenants/` -- y la base se vacia antes y despues de cada prueba.

**No corre en la nube.** El contenedor de esta tanda no tiene Docker
(`u11-tanda-1.md`, "Antes que nada: el entorno"): este archivo se escribe aqui
y se corre en la sesion local, con `mise run test:u11` y Docker levantado
(CG-U11-5).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest

from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record.models import Channel, Origin, RecordType
from untangle.policy_rag.corpus.models import FormKind, IssuedPolicy, PolicyForm
from untangle.policy_rag.corpus.repository import upsert_reference_data
from untangle.tenancy import api as tenancy
from untangle.tenancy import ephemeral, session

#: Un instante fijo para toda la suite de U11. El reloj entra por argumento.
AHORA = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)

_TABLAS_EN_ORDEN_DE_BORRADO = ("issued_policies", "policy_forms")


async def _vaciar() -> None:
    for tenant_id in tenancy.available_ids():
        async with session.session_for(tenant_id) as sesion:
            await session.execute_sql(sesion, "DELETE FROM case_record")
            for tabla in _TABLAS_EN_ORDEN_DE_BORRADO:
                await session.execute_sql(sesion, f"DELETE FROM {tabla}")  # noqa: S608


@pytest.fixture
async def base_de_u11(sesiones: ephemeral.EphemeralDatabase) -> AsyncIterator[None]:
    """La base efimera, sin casos ni polizas antes ni despues de cada prueba."""
    await _vaciar()
    yield
    await _vaciar()


@pytest.fixture
def dos_aseguradoras() -> tuple[str, str]:
    disponibles = tenancy.available_ids()
    assert len(disponibles) >= 2, "la prueba de BR1.2 necesita dos aseguradoras"
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


async def nuevo_caso(tenant_id: str, *, record_type: RecordType = RecordType.CLAIM) -> CasoSembrado:
    """Un caso de chat publico, por la API de U4."""
    case_id = f"u11-caso-{uuid.uuid4().hex[:12]}"
    await casos.create_case(
        tenant_id,
        casos.NewCase(
            case_id=case_id,
            record_type=record_type,
            channel=Channel.CHAT,
            origin=Origin.PUBLIC_CHAT,
            language="es",
        ),
        now=AHORA,
    )
    return CasoSembrado(tenant_id=tenant_id, case_id=case_id)


async def sembrar_poliza(
    tenant_id: str, *, policy_number: str, national_id: str | None = None
) -> IssuedPolicy:
    """Una poliza emitida minima, con su formulario, sin clausulas (BR1.2, BR1.5).

    Va por `upsert_reference_data` directo -- no por `ingest_tenant`, que exige
    un arbol de archivos completo con clausulas -- porque las pruebas de
    identidad de U11 no necesitan ninguna clausula: solo que la poliza exista.
    """
    formulario = PolicyForm(
        tenant_id=tenant_id,
        form_id="form-u11",
        form_version="2026.1",
        form_kind=FormKind.BASE,
        language="es",
        issuer_label=f"{tenant_id} Mutual",
        issuer_tenant=tenant_id,
    )
    poliza = IssuedPolicy(
        tenant_id=tenant_id,
        policy_number=policy_number,
        issuer_tenant=tenant_id,
        form_id=formulario.form_id,
        form_version=formulario.form_version,
        named_insured=(
            {"full_name": "Persona de Prueba", "national_id": national_id}
            if national_id is not None
            else {"full_name": "Persona de Prueba"}
        ),
        period_start=date(2026, 1, 1),
        period_end=date(2027, 1, 1),
    )
    await upsert_reference_data(
        tenant_id, forms=(formulario,), clauses=(), relations=(), policies=(poliza,)
    )
    return poliza
