"""El resumen de la traza de un turno queda listo con sus propios tramos (2026-10-15).

Hasta ese dia nadie pasaba un resumen de `recording` a `ready`: en produccion la
pantalla del caso y la de Telemetria nunca enlazaban la traza en Langfuse de una
conversacion de verdad, aunque la traza si llegaba. Se prueba sin base: con el almacen
en proceso y tramos armados a mano, como los deja un turno del chat.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from untangle.telemetry.spend.models import CostStatus, Money
from untangle.telemetry.traces import api
from untangle.telemetry.traces.models import NodeName, SpanLevel, TraceSummaryStatus

TRAZA = "48215069371502846913720465183927"
INICIO = datetime(2026, 10, 15, 19, 0, tzinfo=UTC)


def _tramo(  # noqa: PLR0913 -- un tramo es esto
    span_id: str,
    *,
    parent: str | None,
    level: SpanLevel,
    name: str,
    desde_ms: int,
    dura_ms: int,
    costo: str | None = None,
    medido: bool = True,
    traza: str = TRAZA,
) -> api.FinishedSpan:
    atributos: dict[str, str | int] = {}
    if level is SpanLevel.NODE:
        atributos["untangle.node"] = name
    if costo is not None:
        atributos["untangle.cost_usd"] = costo
    if level is SpanLevel.CALL:
        atributos["untangle.cost_status"] = (
            CostStatus.MEASURED.value if medido else CostStatus.NOT_MEASURED.value
        )
    empieza = INICIO + timedelta(milliseconds=desde_ms)
    return api.FinishedSpan(
        trace_id=traza,
        tenant_id="stonecroft",
        span_id=span_id,
        parent_span_id=parent,
        name=name,
        level=level,
        started_at=empieza,
        ended_at=empieza + timedelta(milliseconds=dura_ms),
        duration_ms=dura_ms,
        attributes=atributos,
    )


def _turno(*, medido: bool = True) -> list[api.FinishedSpan]:
    """Un turno con dos nodos: la toma con dos llamadas y la decision sin ninguna."""
    return [
        _tramo(
            "c1",
            parent="n1",
            level=SpanLevel.CALL,
            name="llm",
            desde_ms=10,
            dura_ms=300,
            costo="0.0004",
        ),
        _tramo(
            "c2",
            parent="n1",
            level=SpanLevel.CALL,
            name="llm",
            desde_ms=320,
            dura_ms=200,
            costo="0.0001" if medido else None,
            medido=medido,
        ),
        _tramo("n1", parent="t", level=SpanLevel.NODE, name="intake", desde_ms=5, dura_ms=600),
        _tramo("n2", parent="t", level=SpanLevel.NODE, name="decision", desde_ms=610, dura_ms=40),
        _tramo("t", parent=None, level=SpanLevel.TURN, name="turn", desde_ms=0, dura_ms=700),
    ]


@pytest.fixture(autouse=True)
def _limpio() -> Iterator[None]:
    api.reset()
    api.reset_summaries()
    api.install_clock(SimpleNamespace(now=lambda: INICIO + timedelta(seconds=1)))
    yield
    api.install_clock(None)
    api.reset()
    api.reset_summaries()


def test_el_resultado_trae_los_nodos_en_orden_la_latencia_del_turno_y_el_costo() -> None:
    resultado = api.outcome_from_spans(_turno())

    assert resultado is not None
    assert [n.node for n in resultado.nodes] == [NodeName.INTAKE, NodeName.DECISION]
    assert [n.duration_ms for n in resultado.nodes] == [600, 40]
    assert resultado.latency_ms == 700
    # Cada nodo, el costo de las llamadas que colgaron de el; la decision no llamo a nadie.
    assert resultado.nodes[0].cost == Money.measured(Decimal("0.0005"))
    assert resultado.nodes[1].cost == Money.measured(Decimal(0))
    assert resultado.cost == Money.measured(Decimal("0.0005"))


def test_una_llamada_sin_medir_no_se_suma_como_cero() -> None:
    resultado = api.outcome_from_spans(_turno(medido=False))

    assert resultado is not None
    assert resultado.nodes[0].cost == Money.not_measured()
    assert resultado.cost == Money.not_measured()


@pytest.mark.parametrize("falta", [SpanLevel.TURN, SpanLevel.NODE])
def test_sin_el_tramo_del_turno_o_sin_nodos_no_hay_resultado(falta: SpanLevel) -> None:
    tramos = [t for t in _turno() if t.level is not falta]

    assert api.outcome_from_spans(tramos) is None


async def test_al_cerrar_el_turno_el_resumen_queda_listo_aunque_el_lote_ya_haya_salido() -> None:
    registrador = api.BufferedRecorder()
    api.install_recorder(registrador)
    for tramo in _turno():
        registrador.record(tramo)
    registrador.record(
        _tramo(
            "x",
            parent=None,
            level=SpanLevel.TURN,
            name="turn",
            desde_ms=0,
            dura_ms=1,
            traza="9" * 32,
        )
    )
    # La exportacion se lleva el lote cada quince segundos; los tramos siguen a mano.
    registrador.drain()
    await api.open_summary(
        trace_id=TRAZA, tenant_id="stonecroft", case_id="case-1", visitor_key_hash="h"
    )

    listo = await api.settle_summary(TRAZA, tenant_id="stonecroft")

    assert listo is not None
    assert listo.status is TraceSummaryStatus.READY
    assert listo.latency_ms == 700
    assert [n.node for n in listo.nodes] == [NodeName.INTAKE, NodeName.DECISION]


async def test_un_turno_sin_nodos_deja_el_resumen_registrandose() -> None:
    registrador = api.BufferedRecorder()
    api.install_recorder(registrador)
    registrador.record(
        _tramo("t", parent=None, level=SpanLevel.TURN, name="turn", desde_ms=0, dura_ms=5)
    )
    await api.open_summary(
        trace_id=TRAZA, tenant_id="stonecroft", case_id="case-1", visitor_key_hash="h"
    )

    assert await api.settle_summary(TRAZA, tenant_id="stonecroft") is None
    resumen = await api.current_summary_store().get(TRAZA, tenant_id="stonecroft")
    assert resumen is not None
    assert resumen.status is TraceSummaryStatus.RECORDING


def test_el_registrador_recuerda_un_numero_acotado_de_trazas() -> None:
    registrador = api.BufferedRecorder()
    for i in range(api.RECENT_TRACES + 5):
        registrador.record(
            _tramo(
                "t",
                parent=None,
                level=SpanLevel.TURN,
                name="turn",
                desde_ms=0,
                dura_ms=1,
                traza=f"{i:032d}",
            )
        )

    assert registrador.finished(f"{0:032d}") == ()
    assert len(registrador.finished(f"{api.RECENT_TRACES + 4:032d}")) == 1
