"""Lo que las pruebas de integracion de U22 necesitan en la base efimera.

**El gasto no es de ninguna aseguradora.** El registro de gasto es dato del
proyecto: no lleva politica de fila (BR7.1 de U5). Desde el 2026-10-09 el tablero
es publico; lo que se siembra son casos con marcas reconocibles para comprobar que
su identificador y su numero **no salen**.

Las tablas del dinero se vacian antes y despues de cada prueba, como en U5: una
prueba tiene que poder correr sola y en cualquier orden.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import httpx2
import pytest
from fastapi import FastAPI

from untangle.base import ProviderName, SpendSource, UnitKind, Use
from untangle.case_record import api as casos
from untangle.case_record.models import Channel, Origin, RecordType
from untangle.copy_catalog import api as copy_api
from untangle.inbox import api as inbox_api
from untangle.server import composition, spend_routes
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend import repository
from untangle.telemetry.spend.models import BudgetLane, CostStatus, SpendEntry
from untangle.telemetry.traces import api as trazas
from untangle.tenancy import api as tenancy
from untangle.tenancy import ephemeral, session

from ..u5.conftest import TABLAS_DEL_DINERO, sembrar_ventana

__all__ = ["sembrar_ventana"]

#: Marcas que no valen para nada mas que firmar en la prueba.
CLAVE_DE_BANDEJA = "marca-de-clave-de-bandeja-que-no-debe-salir-00002"
CLAVE_DE_ENLACES = "marca-de-clave-de-enlaces-que-no-debe-salir-000003"

COOKIE_DE_BANDEJA = inbox_api.COOKIE

#: Un instante dentro de la ventana que empezo el 2026-09-16.
SEPTIEMBRE = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
OCTUBRE = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)

PRECIO = Decimal("0.00000025")


def gasto(  # noqa: PLR0913 -- cada argumento mueve una columna que la prueba lee
    entry_id: str,
    *,
    costo: Decimal | None,
    proveedor: ProviderName = ProviderName.GEMINI,
    case_ref: str | None = None,
    tenant_ref: str | None = None,
    occurred_at: datetime = SEPTIEMBRE,
    billable: bool = True,
    use: Use | None = None,
    call_ref: str | None = None,
) -> SpendEntry:
    """Una fila de gasto. Con `costo=None` es una llamada que no se pudo valorar.

    Las cuatro columnas de precio van juntas o no va ninguna, y cual de las dos lo
    dice `cost_status`: el ayudante lo impone para que ninguna prueba escriba una
    fila a medias por descuido.
    """
    medido = costo is not None
    return SpendEntry(
        entry_id=entry_id,
        provider=proveedor,
        model="gemini-3.1-flash-lite" if proveedor is ProviderName.GEMINI else "aura-2",
        use=use or (Use.CHAT if proveedor is ProviderName.GEMINI else Use.VOICE),
        call_ref=call_ref,
        tenant_ref=tenant_ref,
        case_ref=case_ref,
        units=Decimal(200000),
        unit_kind=(
            UnitKind.INPUT_TOKENS if proveedor is ProviderName.GEMINI else UnitKind.CHARACTERS
        ),
        unit_price_usd=PRECIO if medido else None,
        price_list_version="1" if medido else None,
        price_list_effective_date=date(2026, 9, 21) if medido else None,
        cost_usd=costo,
        cost_status=CostStatus.MEASURED if medido else CostStatus.NOT_MEASURED,
        billable=billable,
        lane=BudgetLane.PUBLIC,
        source=SpendSource.PROVIDER_REPORTED,
        occurred_at=occurred_at,
    )


async def registrar(entrada: SpendEntry) -> None:
    """Escribe la fila por el camino que usa el aplicativo, segun facture o no."""
    if entrada.billable:
        await repository.record_billable(entrada, now=entrada.occurred_at)
    else:
        await repository.record_non_billable(entrada)


@pytest.fixture
async def dinero(sesiones: ephemeral.EphemeralDatabase) -> AsyncIterator[None]:
    await _vaciar()
    yield
    await _vaciar()


async def _vaciar() -> None:
    async with session.unscoped_session() as sesion:
        for tabla in TABLAS_DEL_DINERO:
            # El nombre sale de una lista cerrada de esta misma suite, no de fuera.
            await session.execute_sql(sesion, f"DELETE FROM {tabla}")  # noqa: S608
    # Los casos que nombran las filas de gasto, y las conversaciones que los
    # atan a un navegador. Por aseguradora, porque llevan politica de fila.
    for tenant_id in tenancy.available_ids():
        async with session.session_for(tenant_id) as sesion:
            await session.execute_sql(sesion, "DELETE FROM chat_session")
            await session.execute_sql(sesion, "DELETE FROM case_record")


async def crear_caso(
    tenant_id: str,
    case_id: str,
    *,
    record_type: RecordType = RecordType.CLAIM,
    channel: Channel = Channel.CHAT,
) -> None:
    """Un caso real, porque `spend_entry.case_ref` **nombra** uno (llave foranea).

    La fila de gasto sobrevive al caso --el reinicio nocturno la deja con la
    columna en nulo--, pero para escribirla con un caso, el caso existe.
    """
    await casos.create_case(
        tenant_id,
        casos.NewCase(
            case_id=case_id,
            record_type=record_type,
            channel=channel,
            origin=Origin.GENERATOR,
            language="es",
            policy_ref=None,
        ),
        now=SEPTIEMBRE,
    )


def construir(sesiones: ephemeral.EphemeralDatabase, tmp_path: Path) -> FastAPI:
    return composition.build_app(
        Settings(
            env="local",
            database_url=sesiones.app_url,
            commit_sha="abc1234",
            staff_credential_signing_key=CLAVE_DE_BANDEJA,
            case_link_signing_key=CLAVE_DE_ENLACES,
        ),
        dist_dir=tmp_path,
    )


async def _soltar(sesiones: ephemeral.EphemeralDatabase) -> None:
    await session.dispose()
    session.configure(sesiones.app_url)
    spend.reset()
    trazas.reset_summaries()
    copy_api.reset()
    spend_routes.reset_cache()
    inbox_api.reset_keys()


@pytest.fixture
async def app(
    sesiones: ephemeral.EphemeralDatabase, tmp_path: Path, dinero: None
) -> AsyncIterator[FastAPI]:
    """La aplicacion con el tablero de gasto montado, como en produccion."""
    del dinero
    spend_routes.reset_cache()
    construida = construir(sesiones, tmp_path)
    try:
        yield construida
    finally:
        await _soltar(sesiones)


async def conversacion_del_navegador(tenant_id: str, case_id: str, clave: str) -> None:
    """Una conversacion de chat de ese navegador, atada a ese caso."""
    async with session.session_for(tenant_id) as sesion:
        await session.execute_sql(
            sesion,
            """
            INSERT INTO chat_session
              (chat_session_id, tenant_id, visitor_key_digest, case_id, language,
               origin_digest, created_at)
            VALUES (:id, :tenant_id, :resumen, :case_id, 'es', 'origen', now())
            """,
            id=f"chat-{case_id}",
            tenant_id=tenant_id,
            resumen=tenancy.visitor_key_digest(clave),
            case_id=case_id,
        )


def cliente(app: FastAPI, cookies: dict[str, str] | None = None) -> httpx2.AsyncClient:
    """Un cliente contra la aplicacion, con las cookies que lleve la prueba.

    Las cookies van en el cliente y no en cada peticion: el cliente de pruebas
    considera ambiguo lo segundo, y una cookie por peticion es justo lo que el
    navegador **no** hace con una cookie de sesion.
    """
    transporte = httpx2.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx2.AsyncClient(transport=transporte, base_url="https://testserver", cookies=cookies)
