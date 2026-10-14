"""El enlace a la traza del caso: lo reciben las dos puertas con dueno y nunca el caso de ejemplo.

Las rutas de verdad, con lo que toca la base reemplazado por dobles: el caso que devuelve
`detail_for`, la nota, los campos y el presupuesto de anotaciones. Lo que se prueba es el cableado
de la vista --quien recibe `trace_url` y cuando--, no la base.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record.models import CaseState, Channel, Priority, RecordType
from untangle.inbox import annotation, case_view, examples, triage_notes
from untangle.inbox import api as inbox_api
from untangle.telemetry.spend.models import Money
from untangle.telemetry.traces import links
from untangle.telemetry.traces.models import (
    NodeName,
    NodeTiming,
    TraceSummary,
    TraceSummaryStatus,
)
from untangle.tenancy import config as tenancy_config

AHORA = datetime(2026, 10, 14, 15, 0, tzinfo=UTC)
TRAZA = "48215069371502846913720465183927"
HOST = "https://us.cloud.langfuse.com"
ENLACE = f"{HOST}/project/proyecto-local/traces/{TRAZA}"
CASO = "case-0123456789abcdef"


def _traza(estado: TraceSummaryStatus) -> TraceSummary:
    listo = estado is TraceSummaryStatus.READY
    return TraceSummary(
        trace_id=TRAZA,
        tenant_id="stonecroft",
        case_id=CASO,
        visitor_key_hash="hash",
        nodes=(
            (
                NodeTiming(
                    node=NodeName.INTAKE,
                    started_at=AHORA,
                    duration_ms=40,
                    cost=Money.not_measured(),
                ),
            )
            if listo
            else ()
        ),
        latency_ms=120 if listo else None,
        status=estado,
        created_at=AHORA,
    )


def _caso(traza: TraceSummary | None) -> case_view.CaseDetail:
    return case_view.CaseDetail(
        case_id=CASO,
        case_number="STO-000001",
        record_type=RecordType.CLAIM,
        state=CaseState.DERIVED,
        resolution=None,
        channel=Channel.CHAT,
        language="es",
        priority=Priority.NORMAL,
        derivation_reason=None,
        completeness_complete=0,
        completeness_total=0,
        completeness_per_field={},
        completeness_optional=frozenset(),
        fields=(),
        transcript=(),
        history=(),
        coverage_answers=(),
        rule_evaluation=None,
        compliance=None,
        trace=traza,
        updated_at=AHORA,
    )


@pytest.fixture(autouse=True)
def _enlace_instalado() -> Iterator[None]:
    links.install(links.TraceLinks(host=HOST, project_id="proyecto-local"))
    yield
    links.install(None)
    tenancy_config.reset()
    inbox_api.reset_keys()


def _cliente(
    monkeypatch: pytest.MonkeyPatch, *, caso: case_view.CaseDetail, entra: str | None
) -> TestClient:
    """La aplicacion con las dos rutas y la base reemplazada por dobles."""

    async def detalle(*_: Any, **__: Any) -> case_view.CaseDetail:
        return caso

    async def nada(*_: Any, **__: Any) -> None:
        return None

    async def sin_campos(*_: Any, **__: Any) -> dict[str, str]:
        return {}

    async def sin_presupuesto(*_: Any, **__: Any) -> bool:
        return False

    async def quien_entra(*_: Any, **__: Any) -> str | None:
        return entra

    monkeypatch.setattr(case_view, "detail_for", detalle)
    monkeypatch.setattr(examples, "detalle", detalle)
    monkeypatch.setattr(triage_notes, "read", nada)
    monkeypatch.setattr(casos, "open_field_values", sin_campos)
    monkeypatch.setattr(annotation, "visitor_has_budget", sin_presupuesto)
    monkeypatch.setattr(crypto, "active", lambda: None)
    monkeypatch.setattr(inbox_api, "_quien_entra", quien_entra)
    aplicacion = FastAPI()
    aplicacion.include_router(inbox_api.router())
    aplicacion.include_router(inbox_api.examples_router())
    return TestClient(aplicacion)


RUTA_DEL_CASO = f"/api/inbox/stonecroft/cases/{CASO}"
RUTA_DEL_EJEMPLO = f"/api/examples/stonecroft/cases/{CASO}"


def test_el_visitante_con_el_enlace_de_su_caso_recibe_la_direccion_de_su_traza(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cliente = _cliente(monkeypatch, caso=_caso(_traza(TraceSummaryStatus.READY)), entra=None)

    respuesta = cliente.get(RUTA_DEL_CASO)

    assert respuesta.status_code == 200
    assert respuesta.json()["trace_url"] == ENLACE


def test_el_personal_con_su_credencial_recibe_la_direccion_de_la_traza(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cliente = _cliente(monkeypatch, caso=_caso(_traza(TraceSummaryStatus.READY)), entra="diana")

    respuesta = cliente.get(RUTA_DEL_CASO)

    assert respuesta.status_code == 200
    assert respuesta.json()["trace_url"] == ENLACE


def test_el_caso_de_ejemplo_publico_nunca_la_recibe_aunque_haya_traza_y_enlace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Su pagina no pide credencial: una direccion ahi la veria cualquiera."""
    cliente = _cliente(monkeypatch, caso=_caso(_traza(TraceSummaryStatus.READY)), entra=None)

    respuesta = cliente.get(RUTA_DEL_EJEMPLO)

    assert respuesta.status_code == 200
    assert respuesta.json()["trace_url"] is None
    assert "traces/" not in respuesta.text


@pytest.mark.parametrize("estado", [TraceSummaryStatus.RECORDING, TraceSummaryStatus.LOST])
def test_una_traza_que_se_registra_o_se_perdio_no_tiene_direccion_que_ensenar(
    monkeypatch: pytest.MonkeyPatch, estado: TraceSummaryStatus
) -> None:
    """La direccion llevaria a una pagina que no existe."""
    cliente = _cliente(monkeypatch, caso=_caso(_traza(estado)), entra="diana")

    assert cliente.get(RUTA_DEL_CASO).json()["trace_url"] is None


def test_un_caso_sin_resumen_de_traza_no_tiene_direccion(monkeypatch: pytest.MonkeyPatch) -> None:
    cliente = _cliente(monkeypatch, caso=_caso(None), entra="diana")

    assert cliente.get(RUTA_DEL_CASO).json()["trace_url"] is None


def test_si_no_se_supo_el_proyecto_no_hay_direccion(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin Langfuse configurado, o con el proyecto sin averiguar, el campo viaja vacio."""
    links.install(None)
    cliente = _cliente(monkeypatch, caso=_caso(_traza(TraceSummaryStatus.READY)), entra="diana")

    respuesta = cliente.get(RUTA_DEL_CASO)

    assert respuesta.status_code == 200
    assert respuesta.json()["trace_url"] is None


def test_la_vista_del_caso_no_lleva_direccion_si_la_ruta_no_la_pide() -> None:
    """Por omision apagado: una ruta nueva que arme la vista no la recibe por descuido."""
    detalle = _caso(_traza(TraceSummaryStatus.READY))
    aseguradora = tenancy_config.require("stonecroft")

    sin_pedirla = inbox_api._al_cable(detalle, aseguradora, anotado={})
    pidiendola = inbox_api._al_cable(detalle, aseguradora, anotado={}, con_enlace_a_la_traza=True)

    assert sin_pedirla.trace_url is None
    assert pidiendola.trace_url == ENLACE
