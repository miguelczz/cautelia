"""A que caso y a que llamada queda cada gasto (2026-10-09).

El tablero de telemetria dice cuanto costo un caso y una llamada. Antes solo 3 de
casi 3 000 filas nombraban su caso: el modelo de Claude no lo pasaba y la voz corre
fuera del turno. Aqui se fija lo que decide cada fila, sin base: se sustituye la
escritura y se mira con que la llamaron.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest

from untangle.base import ProviderName, SpendSource, UnitKind, Use
from untangle.providers import ports
from untangle.server import spend_wiring
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend import attribution
from untangle.telemetry.traces import api as trazas

pytestmark = pytest.mark.anyio

CASO_DEL_TURNO = "case-del-turno"
CASO_DE_LA_LLAMADA = "case-de-la-llamada"


@pytest.fixture
def escritas(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, Any]]]:
    filas: list[dict[str, Any]] = []

    async def anotar(**kwargs: Any) -> None:
        filas.append(kwargs)

    monkeypatch.setattr(spend, "record_spend", anotar)
    yield filas
    trazas.reset()


def _uso(use: Use, *, case_ref: str | None = None) -> ports.UsageReport:
    return ports.UsageReport(
        provider=ProviderName.ANTHROPIC,
        model="claude-haiku-5-5",
        use=use,
        units=(ports.UsageUnits(unit_kind=UnitKind.INPUT_TOKENS, units=Decimal(100)),),
        source=SpendSource.PROVIDER_REPORTED,
        case_ref=case_ref,
    )


async def test_dentro_de_un_turno_el_gasto_nombra_el_caso_del_turno(
    escritas: list[dict[str, Any]],
) -> None:
    with trazas.turn_span(tenant_id="stonecroft", case_id=CASO_DEL_TURNO, use=Use.CHAT):
        await spend_wiring.LedgerUsageSink().report(_uso(Use.CHAT_REPLY))

    assert escritas[0]["case_id"] == CASO_DEL_TURNO
    assert escritas[0]["tenant_ref"] == "stonecroft"
    assert escritas[0]["call_ref"] is None


async def test_lo_que_corre_en_una_llamada_nombra_su_caso_y_su_llamada(
    escritas: list[dict[str, Any]],
) -> None:
    with attribution.attributed(
        tenant_id="sunmeadow", case_id=CASO_DE_LA_LLAMADA, call_id="call-1"
    ):
        await spend_wiring.LedgerUsageSink().report(_uso(Use.VOICE))

    assert escritas[0]["case_id"] == CASO_DE_LA_LLAMADA
    assert escritas[0]["tenant_ref"] == "sunmeadow"
    assert escritas[0]["call_ref"] == "call-1"


async def test_si_la_llamada_cambia_de_caso_lo_siguiente_va_al_nuevo(
    escritas: list[dict[str, Any]],
) -> None:
    with attribution.attributed(tenant_id="sunmeadow", case_id="case-viejo", call_id="call-2"):
        attribution.switch_case("case-nuevo")
        await spend_wiring.LedgerUsageSink().report(_uso(Use.VOICE))

    assert escritas[0]["case_id"] == "case-nuevo"


async def test_las_pruebas_de_calidad_no_se_atribuyen_a_ningun_caso(
    escritas: list[dict[str, Any]],
) -> None:
    # Sus casos son de la corrida y no existen en la base: la columna es una llave
    # foranea, y nombrarlos haria fallar la escritura.
    with trazas.turn_span(tenant_id="stonecroft", case_id="eval-caso-de-mentira", use=Use.CHAT):
        await spend_wiring.LedgerUsageSink().report(_uso(Use.EVALS_CHAT))

    assert escritas[0]["case_id"] is None
    assert escritas[0]["call_ref"] is None


async def test_fuera_de_turno_y_de_llamada_no_se_inventa_caso(
    escritas: list[dict[str, Any]],
) -> None:
    await spend_wiring.LedgerUsageSink().report(_uso(Use.CHAT_REPLY))

    assert escritas[0]["case_id"] is None
    assert escritas[0]["tenant_ref"] is None


async def test_al_salir_de_la_llamada_la_atribucion_se_suelta(
    escritas: list[dict[str, Any]],
) -> None:
    with attribution.attributed(tenant_id="sunmeadow", case_id=CASO_DE_LA_LLAMADA, call_id="c"):
        pass
    await spend_wiring.LedgerUsageSink().report(_uso(Use.VOICE))

    assert attribution.current() is None
    assert escritas[0]["case_id"] is None
