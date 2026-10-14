"""Los resumenes de varios casos en una lectura, y la regla de "hay enlace" (2026-10-14).

El tablero de gasto muestra varios casos a la vez y no puede pagar una consulta por fila:
`latest_for_cases` es `latest_for_case` para una lista. Lo que se prueba aqui, sin base:

- el almacen del proceso da el ultimo resumen de **cada** caso, solo de su aseguradora;
- `trace_summaries_for_visitor` deja pasar **solo los del dueno** --los de otro navegador
  no aparecen, igual que si no existieran-- y lee una sola vez;
- el almacen de base arma esa lectura con una sola sentencia y devuelve lo que la fila dice
  (la sentencia contra Postgres de verdad es de `tests/integration/u5`);
- `links.summary_url`, la regla que comparten la bandeja y el tablero: solo `ready`.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from untangle.telemetry.spend.models import Money
from untangle.telemetry.traces import api, links, repository
from untangle.telemetry.traces.models import (
    NodeName,
    NodeTiming,
    TraceSummary,
    TraceSummaryStatus,
)
from untangle.tenancy import session

AHORA = datetime(2026, 10, 14, 15, 0, tzinfo=UTC)
HOST = "https://us.cloud.langfuse.com"
DUENO = "resumen-del-dueno"
OTRO = "resumen-de-otro-navegador"


@pytest.fixture(autouse=True)
def _almacen_y_enlaces_limpios() -> Iterator[None]:
    api.reset_summaries()
    links.install(None)
    yield
    api.reset_summaries()
    links.install(None)


def _resumen(  # noqa: PLR0913 -- cada prueba cambia solo lo suyo: dueno, aseguradora, estado u hora
    trace_id: str,
    case_id: str,
    *,
    dueno: str = DUENO,
    tenant_id: str = "stonecroft",
    estado: TraceSummaryStatus = TraceSummaryStatus.READY,
    minutos: int = 0,
) -> TraceSummary:
    listo = estado is TraceSummaryStatus.READY
    return TraceSummary(
        trace_id=trace_id,
        tenant_id=tenant_id,
        case_id=case_id,
        visitor_key_hash=dueno,
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
        created_at=AHORA + timedelta(minutes=minutos),
    )


async def _guardar(*resumenes: TraceSummary) -> None:
    for resumen in resumenes:
        await api.current_summary_store().put(resumen)


class _AlmacenQueCuenta:
    """El almacen del proceso, anotando que lecturas se pidieron."""

    def __init__(self) -> None:
        self._dentro = api.InProcessSummaryStore()
        self.por_caso = 0
        self.por_lista: list[tuple[str, ...]] = []

    async def put(self, summary: TraceSummary) -> None:
        await self._dentro.put(summary)

    async def get(self, trace_id: str, *, tenant_id: str) -> TraceSummary | None:
        return await self._dentro.get(trace_id, tenant_id=tenant_id)

    async def latest_for_case(self, case_id: str, *, tenant_id: str) -> TraceSummary | None:
        self.por_caso += 1
        return await self._dentro.latest_for_case(case_id, tenant_id=tenant_id)

    async def latest_for_cases(
        self, case_ids: Sequence[str], *, tenant_id: str
    ) -> dict[str, TraceSummary]:
        self.por_lista.append(tuple(case_ids))
        return await self._dentro.latest_for_cases(case_ids, tenant_id=tenant_id)


# --- El almacen del proceso ---------------------------------------------------


async def test_da_el_ultimo_resumen_de_cada_caso_y_solo_los_de_esa_aseguradora() -> None:
    await _guardar(
        _resumen("T-A-VIEJA", "caso-a", minutos=1),
        _resumen("T-A-NUEVA", "caso-a", minutos=5),
        _resumen("T-B", "caso-b", minutos=2),
        # Mismo identificador de caso en otra aseguradora: no es de esta lectura.
        _resumen("T-OTRA-ASEGURADORA", "caso-a", tenant_id="otra", minutos=9),
        _resumen("T-NO-PEDIDO", "caso-c", minutos=3),
    )

    ultimos = await api.current_summary_store().latest_for_cases(
        ["caso-a", "caso-b", "caso-sin-resumen"], tenant_id="stonecroft"
    )

    assert {caso: resumen.trace_id for caso, resumen in ultimos.items()} == {
        "caso-a": "T-A-NUEVA",
        "caso-b": "T-B",
    }
    assert await api.current_summary_store().latest_for_cases(["caso-a"], tenant_id="nadie") == {}


async def test_dos_resumenes_del_mismo_instante_desempatan_como_la_lectura_de_un_caso() -> None:
    await _guardar(_resumen("T-1", "caso-a", minutos=5), _resumen("T-2", "caso-a", minutos=5))
    almacen = api.current_summary_store()

    en_lista = await almacen.latest_for_cases(["caso-a"], tenant_id="stonecroft")
    de_un_caso = await almacen.latest_for_case("caso-a", tenant_id="stonecroft")

    assert de_un_caso is not None
    assert en_lista["caso-a"].trace_id == de_un_caso.trace_id == "T-2"


# --- La lectura con dueno -----------------------------------------------------


async def test_solo_salen_los_resumenes_del_navegador_que_los_produjo() -> None:
    await _guardar(
        _resumen("T-MIO", "caso-mio", dueno=DUENO),
        _resumen("T-AJENO", "caso-ajeno", dueno=OTRO),
    )

    suyos = await api.trace_summaries_for_visitor(
        ["caso-mio", "caso-ajeno"], tenant_id="stonecroft", visitor_key_hash=DUENO
    )
    de_otro = await api.trace_summaries_for_visitor(
        ["caso-mio", "caso-ajeno"], tenant_id="stonecroft", visitor_key_hash=OTRO
    )
    de_nadie = await api.trace_summaries_for_visitor(
        ["caso-mio", "caso-ajeno"], tenant_id="stonecroft", visitor_key_hash="desconocido"
    )

    assert set(suyos) == {"caso-mio"}
    assert set(de_otro) == {"caso-ajeno"}
    # Quien no es dueno de ninguno recibe lo mismo que si no existieran: nada.
    assert de_nadie == {}


async def test_una_lista_vacia_no_lee_y_una_lista_larga_lee_una_sola_vez() -> None:
    almacen = _AlmacenQueCuenta()
    api.install_summary_store(almacen)
    ids = [f"caso-{n}" for n in range(12)]
    await _guardar(*(_resumen(f"T-{n}", caso) for n, caso in enumerate(ids)))

    vacio = await api.trace_summaries_for_visitor(
        [], tenant_id="stonecroft", visitor_key_hash=DUENO
    )
    todos = await api.trace_summaries_for_visitor(
        ids, tenant_id="stonecroft", visitor_key_hash=DUENO
    )

    assert vacio == {}
    assert set(todos) == set(ids)
    # Una lectura para los doce, ninguna por caso, y la lista vacia ni se pide.
    assert almacen.por_lista == [tuple(ids)]
    assert almacen.por_caso == 0


# --- El almacen de base, sin base ---------------------------------------------


class _BaseFalsa:
    """El punto unico de sesion, sustituido: anota que se abrio y que se pregunto."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, filas: Sequence[dict[str, Any]]) -> None:
        self.sesiones: list[str] = []
        self.consultas: list[tuple[str, dict[str, Any]]] = []
        self._filas = filas
        monkeypatch.setattr(session, "session_for", self._abrir)
        monkeypatch.setattr(session, "fetch_all", self._fetch_all)

    @asynccontextmanager
    async def _abrir(self, tenant_id: str) -> AsyncIterator[object]:
        self.sesiones.append(tenant_id)
        yield object()

    async def _fetch_all(
        self, _sesion: object, sentencia: str, **parametros: Any
    ) -> tuple[dict[str, Any], ...]:
        self.consultas.append((sentencia, parametros))
        return tuple(self._filas)


def _fila(resumen: TraceSummary) -> dict[str, Any]:
    """La fila como la devuelve el motor: los nodos ya son una lista, no un texto JSON."""
    fila = repository._de_resumen(resumen)
    fila["nodes"] = json.loads(fila["nodes"])
    return fila


async def test_el_almacen_de_base_pide_todos_los_casos_en_una_sola_sentencia_de_su_aseguradora(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _BaseFalsa(
        monkeypatch,
        [
            _fila(_resumen("T-A", "caso-a", minutos=5)),
            _fila(_resumen("T-B", "caso-b", estado=TraceSummaryStatus.RECORDING)),
        ],
    )

    ultimos = await repository.DatabaseSummaryStore().latest_for_cases(
        ("caso-a", "caso-b", "caso-c"), tenant_id="stonecroft"
    )

    # Una sesion de esa aseguradora y una sentencia, con la lista ligada y no concatenada.
    assert base.sesiones == ["stonecroft"]
    assert base.consultas == [
        (repository.LEER_ULTIMOS_DE_VARIOS_CASOS, {"case_ids": ["caso-a", "caso-b", "caso-c"]})
    ]
    assert "ANY(:case_ids)" in repository.LEER_ULTIMOS_DE_VARIOS_CASOS
    assert {caso: r.trace_id for caso, r in ultimos.items()} == {"caso-a": "T-A", "caso-b": "T-B"}
    assert ultimos["caso-a"].status is TraceSummaryStatus.READY
    assert ultimos["caso-b"].status is TraceSummaryStatus.RECORDING


async def test_el_almacen_de_base_con_una_lista_vacia_ni_abre_sesion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _BaseFalsa(monkeypatch, [])

    assert (
        await repository.DatabaseSummaryStore().latest_for_cases([], tenant_id="stonecroft") == {}
    )
    assert base.sesiones == []
    assert base.consultas == []


# --- La regla de "hay enlace" -------------------------------------------------


@pytest.mark.parametrize(
    ("estado", "hay_enlace"),
    [
        (TraceSummaryStatus.READY, True),
        (TraceSummaryStatus.RECORDING, False),
        (TraceSummaryStatus.LOST, False),
    ],
)
def test_solo_un_resumen_listo_lleva_a_una_traza(
    estado: TraceSummaryStatus, hay_enlace: bool
) -> None:
    links.install(links.TraceLinks(host=HOST, project_id="proyecto-local"))

    direccion = links.summary_url(_resumen("T-1", "caso-a", estado=estado))

    assert direccion == (f"{HOST}/project/proyecto-local/traces/T-1" if hay_enlace else None)


def test_sin_resumen_o_sin_langfuse_configurado_no_hay_enlace() -> None:
    assert links.summary_url(None) is None

    # Un resumen listo, pero el backend de trazas no esta configurado.
    assert links.summary_url(_resumen("T-1", "caso-a")) is None
