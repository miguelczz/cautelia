"""Quien despierta al ajustador: al derivar, al leer el caso, y lo que muestra de su corrida."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import pytest

from untangle.adjuster import pipeline, quota
from untangle.adjuster.models import (
    AdjusterRun,
    RunStatus,
    RunStep,
    SourceKind,
    StepId,
    StepSource,
)
from untangle.adjuster.service import AdjusterService, needs_retry, view_of
from untangle.case_record.models import CaseState
from untangle.inbox.actions import InboxAction

from .support import AHORA, CONFIGURACION, Mundo


def _corrida(estado: RunStatus, *, intento: int = 1, hace: timedelta = timedelta(0)) -> AdjusterRun:
    decidida = estado is RunStatus.DECIDED
    return AdjusterRun(
        tenant_id="sunmeadow",
        case_id="caso-1",
        status=estado,
        attempt=intento,
        model="claude-test",
        decision=InboxAction.APPROVE if decidida else None,
        summary="Aprobado.\n\nCubre el choque." if decidida else None,
        error_kind="provider_timeout" if estado is RunStatus.FAILED else None,
        created_at=AHORA - hace,
        updated_at=AHORA - hace,
    )


def _servicio(mundo: Mundo) -> AdjusterService:
    return AdjusterService(ports=mundo.puertos, config=CONFIGURACION)


async def _necesita(mundo: Mundo, corrida: AdjusterRun | None, estado: CaseState) -> bool:
    return await needs_retry(corrida, state=estado, ports=mundo.puertos, config=CONFIGURACION)


@pytest.fixture
def con_cupo(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Cuantos casos lleva hoy el contador; la prueba lo cambia."""
    usados = [0]

    async def hoy(config: Any, *, now: Any = None) -> quota.CasesToday:
        return quota.CasesToday(used=usados[0], limit=config.daily_case_cap)

    monkeypatch.setattr(quota, "cases_today", hoy)
    return usados


# --- Cuando vale la pena reintentar ------------------------------------------------------------


@pytest.mark.parametrize(
    "estado", [CaseState.OPEN, CaseState.CAPTURING, CaseState.DECIDING, CaseState.CLOSED]
)
async def test_un_caso_que_no_esta_derivado_no_se_reintenta(
    mundo: Mundo, estado: CaseState
) -> None:
    assert not await _necesita(mundo, None, estado)


async def test_un_caso_derivado_sin_corrida_se_intenta(mundo: Mundo) -> None:
    assert await _necesita(mundo, None, CaseState.DERIVED)


async def test_una_corrida_que_va_bien_no_dispara_nada_aunque_la_pantalla_pregunte_cada_3_segundos(
    mundo: Mundo,
) -> None:
    assert not await _necesita(
        mundo, _corrida(RunStatus.RUNNING, hace=timedelta(seconds=3)), CaseState.DERIVED
    )


async def test_una_corrida_perdida_se_retoma(mundo: Mundo) -> None:
    perdida = _corrida(RunStatus.RUNNING, hace=CONFIGURACION.running_stale_after)

    assert await _necesita(mundo, perdida, CaseState.DERIVED)


async def test_una_corrida_fallida_se_reintenta_mientras_queden_intentos(mundo: Mundo) -> None:
    quedan = _corrida(RunStatus.FAILED, intento=CONFIGURACION.attempts - 1)
    agotada = _corrida(RunStatus.FAILED, intento=CONFIGURACION.attempts)

    assert await _necesita(mundo, quedan, CaseState.DERIVED)
    assert not await _necesita(mundo, agotada, CaseState.DERIVED)


async def test_una_corrida_capada_espera_a_que_haya_cupo(mundo: Mundo, con_cupo: list[int]) -> None:
    capada = _corrida(RunStatus.CAPPED)

    con_cupo[0] = CONFIGURACION.daily_case_cap
    assert not await _necesita(mundo, capada, CaseState.DERIVED)

    con_cupo[0] = CONFIGURACION.daily_case_cap - 1
    assert await _necesita(mundo, capada, CaseState.DERIVED)


async def test_una_corrida_decidida_con_el_caso_aun_derivado_repite_el_registro(
    mundo: Mundo,
) -> None:
    """Decidio y no alcanzo a registrar: el reintento no vuelve a llamar al modelo."""
    assert await _necesita(mundo, _corrida(RunStatus.DECIDED), CaseState.DERIVED)
    assert not await _necesita(mundo, _corrida(RunStatus.DECIDED), CaseState.CLOSED)


# --- Agendar, de fondo y una sola vez por caso -------------------------------------------------


@pytest.fixture
def corridas(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    llamadas: list[tuple[str, str]] = []
    soltar = asyncio.Event()

    async def run_case(tenant_id: str, case_id: str, **_kw: Any) -> None:
        llamadas.append((tenant_id, case_id))
        await soltar.wait()

    run_case.soltar = soltar  # type: ignore[attr-defined]
    monkeypatch.setattr(pipeline, "run_case", run_case)
    return llamadas


async def test_al_derivar_se_agenda_la_corrida_sin_esperarla(
    mundo: Mundo, corridas: list[tuple[str, str]]
) -> None:
    servicio = _servicio(mundo)

    await servicio.on_derived("sunmeadow", "caso-1")
    await asyncio.sleep(0)

    assert corridas == [("sunmeadow", "caso-1")]
    pipeline.run_case.soltar.set()  # type: ignore[attr-defined]
    await servicio.drain()


async def test_un_mismo_proceso_no_lleva_dos_veces_el_mismo_caso(
    mundo: Mundo, corridas: list[tuple[str, str]]
) -> None:
    servicio = _servicio(mundo)

    primera = servicio.schedule("sunmeadow", "caso-1")
    segunda = servicio.schedule("sunmeadow", "caso-1")
    otra = servicio.schedule("sunmeadow", "caso-2")
    await asyncio.sleep(0)

    assert (primera, segunda, otra) == (True, False, True)
    assert sorted(c for _, c in corridas) == ["caso-1", "caso-2"]
    pipeline.run_case.soltar.set()  # type: ignore[attr-defined]
    await servicio.drain()
    assert servicio.schedule("sunmeadow", "caso-1"), (
        "terminada la corrida, el caso se puede agendar"
    )
    pipeline.run_case.soltar.set()  # type: ignore[attr-defined]
    await servicio.drain()


async def test_leer_un_caso_derivado_sin_corrida_la_agenda(
    mundo: Mundo, corridas: list[tuple[str, str]]
) -> None:
    servicio = _servicio(mundo)

    await servicio.retry_if_needed(mundo.tenant_id, mundo.case_id, CaseState.DERIVED)
    await asyncio.sleep(0)

    assert corridas == [(mundo.tenant_id, mundo.case_id)]
    pipeline.run_case.soltar.set()  # type: ignore[attr-defined]
    await servicio.drain()


async def test_leer_un_caso_que_ya_lleva_este_proceso_no_lo_agenda_otra_vez(
    mundo: Mundo, corridas: list[tuple[str, str]]
) -> None:
    servicio = _servicio(mundo)
    servicio.schedule(mundo.tenant_id, mundo.case_id)
    await asyncio.sleep(0)

    await servicio.retry_if_needed(mundo.tenant_id, mundo.case_id, CaseState.DERIVED)
    await asyncio.sleep(0)

    assert len(corridas) == 1
    pipeline.run_case.soltar.set()  # type: ignore[attr-defined]
    await servicio.drain()


async def test_leer_un_caso_cerrado_no_agenda_nada(
    mundo: Mundo, corridas: list[tuple[str, str]]
) -> None:
    servicio = _servicio(mundo)

    await servicio.retry_if_needed(mundo.tenant_id, mundo.case_id, CaseState.CLOSED)
    await asyncio.sleep(0)

    assert corridas == []


async def test_una_corrida_que_se_cae_no_tumba_la_tarea_y_libera_el_caso(
    mundo: Mundo, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def roto(*_a: Any, **_k: Any) -> None:
        msg = "se cayo"
        raise OSError(msg)

    monkeypatch.setattr(pipeline, "run_case", roto)
    servicio = _servicio(mundo)

    servicio.schedule("sunmeadow", "caso-1")
    await servicio.drain()

    assert servicio.schedule("sunmeadow", "caso-1"), "el caso quedo libre para el reintento"
    await servicio.drain()


# --- Lo que muestra la corrida -----------------------------------------------------------------


async def test_la_corrida_decidida_se_muestra_con_su_titular_su_explicacion_y_sus_pasos(
    mundo: Mundo,
) -> None:
    paso = RunStep(
        id=StepId.CLAUSES,
        title_key="adjuster.step.clauses.title",
        text="Encontré la cláusula del choque.",
        sources=(
            StepSource(kind=SourceKind.CLAUSE, ref="SM-PAP-2026-D.INS.COLLISION", label="Choque"),
            StepSource(
                kind=SourceKind.WEB, ref="valor", label="Guía", url="https://fasecolda.com/x"
            ),
        ),
    )
    corrida = _corrida(RunStatus.DECIDED).model_copy(update={"steps": (paso,), "searches_used": 2})

    vista = view_of(corrida)

    assert vista.status == "decided"
    assert vista.decision is InboxAction.APPROVE
    assert (vista.headline, vista.explanation) == ("Aprobado.", "Cubre el choque.")
    assert vista.searches_used == 2
    (paso_visto,) = vista.steps
    assert paso_visto.id == "clauses"
    assert [f.kind for f in paso_visto.sources] == ["clause", "web"]
    assert paso_visto.sources[1].url == "https://fasecolda.com/x"


async def test_una_corrida_sin_decidir_no_trae_decision_ni_explicacion(mundo: Mundo) -> None:
    vista = view_of(_corrida(RunStatus.RUNNING))

    assert vista.status == "running"
    assert (vista.decision, vista.headline, vista.explanation) == (None, None, None)


async def test_leer_devuelve_la_corrida_guardada_o_nada(mundo: Mundo) -> None:
    servicio = _servicio(mundo)
    assert await servicio.read(mundo.tenant_id, mundo.case_id) is None

    mundo.repo.filas[(mundo.tenant_id, mundo.case_id)] = _corrida(RunStatus.CAPPED).model_copy(
        update={"tenant_id": mundo.tenant_id, "case_id": mundo.case_id}
    )

    vista = await servicio.read(mundo.tenant_id, mundo.case_id)
    assert vista is not None
    assert vista.status == "capped"
