"""Un comando a mano gasta sobre el libro del proyecto, no sobre uno que se borra (2026-10-13).

`evals:entender` corria sobre una base desechable con la ventana en cero: 33 corridas
gastaron unos 0,24 USD que no quedaron en ningun libro, y el techo decidio con un
acumulado de menos. Estas pruebas fijan las dos mitades de lo que cambio, contra la base
de verdad y con el mismo camino que recorre el comando:

1. El techo que consulta el comando es el **acumulado de la ventana del proyecto**.
2. Lo que el adaptador reporta queda como fila en **ese** libro y suma a **ese** acumulado.

**Ninguna prueba gasta un centavo**: el uso del adaptador se reporta a mano, sin llamar a
nadie, y el acumulado se siembra directo.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest

from untangle.base import ProviderName, SpendSource, UnitKind, Use
from untangle.providers import config as provider_config
from untangle.providers.ceiling import CeilingGate
from untangle.providers.ports import BudgetExhausted, UsageReport, UsageUnits
from untangle.server import manual_ledger, spend_wiring
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend import repository
from untangle.telemetry.spend.models import WINDOW_START
from untangle.tenancy import ephemeral, session

from .conftest import sembrar_ventana


@pytest.fixture(autouse=True)
def contabilidad(dinero: None) -> Iterator[None]:
    spend.reset()
    yield
    spend.reset()


def _reporte() -> UsageReport:
    """Lo que reporta el adaptador de Claude para las evaluaciones: mil tokens de entrada."""
    return UsageReport(
        provider=ProviderName.ANTHROPIC,
        model="claude-haiku-5-5",
        use=Use.EVALS_CHAT,
        units=(
            UsageUnits(unit_kind=UnitKind.INPUT_TOKENS, units=Decimal(1000)),
            UsageUnits(unit_kind=UnitKind.OUTPUT_TOKENS, units=Decimal(200)),
        ),
        source=SpendSource.PROVIDER_REPORTED,
    )


async def test_el_techo_del_comando_lee_el_acumulado_del_libro_del_proyecto(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Con la ventana al tope, la compuerta del comando cierra: ve lo gastado de verdad."""
    await sembrar_ventana(gastado=Decimal("40.00"), techo=Decimal("40.00"), alerta=Decimal("24.00"))
    await manual_ledger.open_ledger(provider_config.load(), sesiones.app_url)
    try:
        with pytest.raises(BudgetExhausted):
            await CeilingGate(spend.budget_state).ensure_open(
                provider=ProviderName.ANTHROPIC, use=Use.EVALS_CHAT
            )
    finally:
        await manual_ledger.close_ledger()


async def test_con_la_ventana_por_debajo_del_techo_la_compuerta_deja_pasar(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Y la contraparte: abrir el libro no cierra nada que el acumulado deje abierto."""
    await sembrar_ventana(gastado=Decimal("0.89"), techo=Decimal("40.00"), alerta=Decimal("24.00"))
    await manual_ledger.open_ledger(provider_config.load(), sesiones.app_url)
    try:
        await CeilingGate(spend.budget_state).ensure_open(
            provider=ProviderName.ANTHROPIC, use=Use.EVALS_CHAT
        )
    finally:
        await manual_ledger.close_ledger()


async def test_lo_que_reporta_el_adaptador_queda_en_el_libro_y_suma_al_acumulado(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """El gasto de la corrida llega al libro del proyecto, a precio de lista y con su origen."""
    await sembrar_ventana(gastado=Decimal("0.65"), techo=Decimal("40.00"), alerta=Decimal("24.00"))
    await manual_ledger.open_ledger(provider_config.load(), sesiones.app_url)
    await spend_wiring.LedgerUsageSink().report(_reporte())
    acumulado = await manual_ledger.close_ledger()

    # 1000 tokens a 0,0000001 y 200 a 0,0000005: 0,0001 + 0,0001.
    assert acumulado == Decimal("0.650200")
    async with session.unscoped_session() as sesion:
        filas = await session.fetch_all(
            sesion,
            "SELECT unit_kind, cost_usd, cost_status, billable, source, price_list_version "
            "FROM spend_entry ORDER BY unit_kind",
        )
    assert [(f["unit_kind"], f["cost_usd"]) for f in filas] == [
        ("input_tokens", Decimal("0.0001")),
        ("output_tokens", Decimal("0.0001")),
    ]
    assert {f["cost_status"] for f in filas} == {"measured"}
    assert {f["billable"] for f in filas} == {True}
    assert {f["source"] for f in filas} == {"provider_reported"}
    ventana = await repository.load_window(WINDOW_START)
    assert ventana is not None
    assert ventana.billable_spent_usd == Decimal("0.6502")


async def test_el_libro_ilegible_no_deja_gastar_ni_el_punto_de_sesion_movido(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Sin ventana sembrada el comando se detiene antes de la primera llamada."""
    with pytest.raises(SystemExit, match="No se llamo a ningun proveedor"):
        await manual_ledger.open_ledger(provider_config.load(), sesiones.app_url)

    assert session.configured_url() == sesiones.app_url
