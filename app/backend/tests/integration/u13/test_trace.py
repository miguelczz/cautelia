"""El resumen de traza que ve el visitante (BR4.3, BR4.4; AC2.3.2, AC2.3.3).

Dos conductas, y las dos son de seguridad aunque solo una lo parezca:

- **Lo ajeno y lo inexistente se responden igual.** Se comprueba comparando las dos
  respuestas campo por campo, no mirando que "no aparezca" el dato del otro: recibir
  algo *distinto* de lo que recibe un desconocido ya confirma que ese caso existe.
- **Una traza en curso no es "no encontrado".** Si lo fuera, el visitante legitimo
  veria lo mismo que el intruso y no sabria que esperar, que es la misma fuga por el
  otro lado.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from untangle.chat import trace
from untangle.telemetry.spend.models import CostStatus, Money
from untangle.telemetry.traces import api as traces
from untangle.telemetry.traces.models import NodeName, NodeTiming, TraceOutcome

AHORA = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)

MIA = "a" * 64
DE_OTRO = "b" * 64


@pytest.fixture(autouse=True)
def _almacen_limpio() -> None:
    """El almacen del proceso, vacio en cada prueba. Sin esto una traza sembrada
    sobrevive a la prueba que la escribio y la siguiente pasa por la de al lado."""
    traces.reset_summaries()


async def _sembrar(
    *, trace_id: str, tenant_id: str, case_id: str, visitor: str, lista: bool = False
) -> None:
    await traces.open_summary(
        trace_id=trace_id,
        tenant_id=tenant_id,
        case_id=case_id,
        visitor_key_hash=visitor,
    )
    if lista:
        await traces.record_trace(
            trace_id,
            TraceOutcome(
                nodes=(
                    NodeTiming(
                        node=NodeName.INTAKE,
                        started_at=AHORA,
                        duration_ms=120,
                        cost=Money(status=CostStatus.NOT_MEASURED),
                    ),
                ),
                latency_ms=840,
                cost=Money(status=CostStatus.NOT_MEASURED),
                clauses_retrieved=3,
                clauses_verified=2,
            ),
            tenant_id=tenant_id,
        )


async def test_el_resumen_propio_muestra_nodos_clausulas_latencia_y_costo(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """AC2.3.2, y el control positivo de todo lo de abajo: sin el, las pruebas de
    aislamiento pasarian con una implementacion que no devolviera nunca nada."""
    _, propia = dos_aseguradoras
    await _sembrar(trace_id="tr-1", tenant_id=propia, case_id="caso-1", visitor=MIA, lista=True)

    vista = await trace.by_trace("tr-1", tenant_id=propia, visitor_key_hash=MIA)

    assert vista is not None
    assert vista.status == "ready"
    assert [nodo.node for nodo in vista.nodes] == ["intake"]
    assert vista.clauses_retrieved == 3
    assert vista.clauses_verified == 2
    assert vista.latency_ms == 840
    assert vista.cost_status == "not_measured", "sin precio no se escribe cero"
    assert vista.cost_usd is None


async def test_la_traza_de_otro_navegador_responde_igual_que_una_inexistente(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR4.3. Por identidad y no por ausencia: las dos respuestas se comparan entre
    si, porque cualquier diferencia --un codigo, un campo, una frase-- ya confirma
    que esa traza existe."""
    _, propia = dos_aseguradoras
    await _sembrar(trace_id="tr-1", tenant_id=propia, case_id="caso-1", visitor=MIA, lista=True)

    ajena = await trace.by_trace("tr-1", tenant_id=propia, visitor_key_hash=DE_OTRO)
    inexistente = await trace.by_trace("tr-no-existe", tenant_id=propia, visitor_key_hash=DE_OTRO)

    assert ajena == inexistente
    assert ajena is None


async def test_la_traza_de_otra_aseguradora_responde_igual_que_una_inexistente(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR6.3 aplicado al resumen: el mismo navegador, la otra aseguradora."""
    ajena, propia = dos_aseguradoras
    await _sembrar(trace_id="tr-1", tenant_id=ajena, case_id="caso-1", visitor=MIA, lista=True)

    de_la_otra = await trace.by_trace("tr-1", tenant_id=propia, visitor_key_hash=MIA)
    inexistente = await trace.by_trace("tr-no-existe", tenant_id=propia, visitor_key_hash=MIA)

    assert de_la_otra == inexistente
    assert de_la_otra is None


async def test_sin_cookie_no_hay_resumen_que_ver(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Un navegador que nunca escribio no tiene resumen propio, y se le responde lo
    mismo que a cualquier otro que no es dueno."""
    _, propia = dos_aseguradoras
    await _sembrar(trace_id="tr-1", tenant_id=propia, case_id="caso-1", visitor=MIA, lista=True)

    assert await trace.by_trace("tr-1", tenant_id=propia, visitor_key_hash=None) is None


async def test_una_traza_en_curso_se_dice_en_curso_y_nunca_no_encontrada(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """AC2.3.3, BR4.4. Mientras el rastro no se une con su resumen, el visitante ve esto.
    Desde el 2026-10-15 lo une `settle_summary` al cerrar el turno del chat."""
    _, propia = dos_aseguradoras
    await _sembrar(trace_id="tr-1", tenant_id=propia, case_id="caso-1", visitor=MIA)

    vista = await trace.by_trace("tr-1", tenant_id=propia, visitor_key_hash=MIA)

    assert vista is not None, "existe: decir 'no encontrado' seria mentir"
    assert vista.status == "recording"
    assert vista.recording, "la pagina se actualiza sola mientras esto sea cierto"
    assert vista.nodes == (), "todavia no hay recorrido que mostrar"
    assert vista.latency_ms is None, "y no cero, que seria una latencia medida"
