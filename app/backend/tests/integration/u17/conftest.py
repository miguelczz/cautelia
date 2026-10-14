"""Lo que las pruebas de integracion de U17 necesitan en la base efimera.

Lo que esta unidad cablea son **los dos carriles diarios y el modo de voz**, y las
tres cosas viven en la contabilidad de U5: la cuota que se consume al abrir, el
contador que la disponibilidad lee sin tocar, y el presupuesto que decide con que
voz se abre. Asi que aqui se monta la aplicacion de verdad con una foto del
presupuesto gobernable desde la prueba.

**El presupuesto entra por argumento y los precios son los de verdad.** La tanda
arreglo lo que hacia falta para que lo fueran: la reserva por llamada se suma de sus
tres componentes --transcripcion, sintesis y modelo-- y la tabla versionada los
valora todos, asi que aqui no hay precios inventados. Lo que si se siembra es la
ventana del presupuesto, porque lo que cada prueba necesita es un restante concreto.

Con el techo de verdad (5 USD) el cupo del sitio es **una llamada al dia**: alcanza
para las pruebas de un carril agotado, y la de la retoma pide sitio para dos, asi que
siembra un techo mayor y lo dice.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx2
import pytest
from fastapi import FastAPI

from untangle.copy_catalog import api as copy_api
from untangle.server import composition, voice_routes
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend import budget
from untangle.telemetry.spend.models import BudgetWindow
from untangle.telemetry.traces import api as trazas
from untangle.tenancy import api as tenancy
from untangle.tenancy import ephemeral, session

CLAVE_DE_ENLACES = "marca-de-clave-de-enlaces-que-no-debe-salir-000017"
#: La del token de socket, **otra a proposito** (PENDIENTES 1.16). Si fueran la
#: misma, la prueba que canjea el enlace de la voz pasaria tambien el dia que la
#: raiz le pasara a la voz la clave equivocada.
CLAVE_DEL_SOCKET = "marca-de-clave-del-token-de-voz-que-no-sale-000017"

#: El dia de estas pruebas. El reloj de la cuota es el del proceso --la cuota diaria
#: se cierra a medianoche de la zona configurada-- asi que lo que se fija aqui es la
#: ventana del presupuesto y no el reloj.
INICIO_DE_LA_VENTANA = datetime(2026, 9, 16, tzinfo=UTC).date()


def foto(*, gastado: str = "0", techo: str = "40.00") -> object:
    """Una foto del presupuesto con lo gastado y el techo que se le pidan.

    El techo por omision es el vigente (40 USD desde el 2026-10-07): con el de 5 el
    cupo del sitio salia de una llamada al dia y agotaba el carril del sitio antes
    que el de la conexion, que es el que estas pruebas quieren agotar.

    Con su reserva de grabacion **convertida por la misma aritmetica que la
    aplicacion**: los cuarenta y cinco minutos declarados valen quince llamadas de
    duracion maxima a la voz principal. Sin reserva, el restante publico sale sin
    medir y un restante sin medir cierra el carril del sitio.
    """
    reserva = spend.recording_reserve_usd()
    return budget.state(
        BudgetWindow(
            window_start=INICIO_DE_LA_VENTANA,
            window_end=INICIO_DE_LA_VENTANA + timedelta(days=90),
            billable_spent_usd=Decimal(gastado),
            cap_usd=Decimal(techo),
            alert_usd=Decimal(techo) * Decimal("0.6"),
            unmeasured_billable_calls=0,
            recording_reserve_usd=reserva.amount_usd,
            recording_reserve_status=reserva.status,
            updated_at=datetime(2026, 10, 2, 12, 0, tzinfo=UTC),
        )
    )


async def _vaciar() -> None:
    for tenant_id in tenancy.available_ids():
        async with session.session_for(tenant_id) as sesion:
            await session.execute_sql(sesion, "DELETE FROM call_session")
            await session.execute_sql(sesion, "DELETE FROM case_record")
    # Los contadores de cuota no son de ninguna aseguradora: viven en el esquema
    # del proyecto, y son justo lo que esta unidad consume.
    async with session.unscoped_session() as sesion:
        await session.execute_sql(sesion, "DELETE FROM quota_counter")


@pytest.fixture
async def base_de_u17(sesiones: ephemeral.EphemeralDatabase) -> AsyncIterator[None]:
    del sesiones
    await _vaciar()
    yield
    await _vaciar()


@pytest.fixture
async def app(
    sesiones: ephemeral.EphemeralDatabase,
    demo_abierta: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[FastAPI]:
    ajustes = Settings(
        env="local",
        database_url=sesiones.app_url,
        commit_sha="abc1234",
        case_link_signing_key=CLAVE_DE_ENLACES,
        voice_token_signing_key=CLAVE_DEL_SOCKET,
    )
    construida = composition.build_app(ajustes, dist_dir=tmp_path)

    async def presupuesto(*, now: datetime | None = None) -> object:
        del now
        return foto()

    monkeypatch.setattr(spend, "budget_state", presupuesto)
    try:
        yield construida
    finally:
        await session.dispose()
        session.configure(sesiones.app_url)
        spend.reset()
        trazas.reset_summaries()
        copy_api.reset()
        voice_routes.reset()


def cliente(app: FastAPI) -> httpx2.AsyncClient:
    """Un navegador. **Sobre `https`**: la galleta del visitante se pone `Secure`,
    y un cliente en texto plano la descartaria en silencio."""
    transporte = httpx2.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx2.AsyncClient(transport=transporte, base_url="https://testserver")


def aseguradora() -> str:
    return tenancy.available_ids()[0]


async def llamadas_en(tenant_id: str) -> int:
    async with session.session_for(tenant_id) as sesion:
        fila = await session.fetch_one(sesion, "SELECT count(*) AS total FROM call_session")
    return int(fila["total"]) if fila is not None else 0
