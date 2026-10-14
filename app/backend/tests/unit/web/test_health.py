"""La evaluacion de listo, sin HTTP (BR5.1 a BR5.3, NFR16.2, NFR16.6, OBS-U6.1).

Y el indicador del reinicio nocturno (2026-10-13): al dia, vencido y no se pudo
leer, y que ninguno de los tres vuelve no apto al proceso.

Lo que se prueba es la decision: cuando el proceso puede atender, que dice de
cada cosa que comprobo, y que nada de eso toca un proveedor. Las rutas y el 503
con la forma de C-01 se prueban aparte, contra el proceso entero.

La base se sustituye por comprobaciones que responden, levantan o tardan: lo que
aqui importa es que hace la salud con cada respuesta. La base de verdad se
comprueba en la prueba de integracion de la ruta.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from untangle.demo_operations import api as demo
from untangle.demo_operations.api import PurgerRow, ResetOutcome, ResetRun
from untangle.server import health, surfaces
from untangle.surface_spec import ProbeCheck, SurfaceId, SurfaceProbe, SurfaceSpec

from . import espias
from .eventos import Eventos

INDICADORES = health.ProviderIndicators(priced_units=4, uses_with_key=("chat",))

AHORA = datetime(2026, 10, 13, 12, 30, tzinfo=UTC)


async def _base_que_responde() -> None:
    return None


async def _base_caida() -> None:
    msg = "connection refused"
    raise OSError(msg)


async def _base_colgada() -> None:
    await asyncio.sleep(5)


async def _sonda_que_lanza() -> None:
    msg = "no responde"
    raise RuntimeError(msg)


async def _sonda_lenta() -> None:
    await asyncio.sleep(5)


async def _reinicio_al_dia() -> health.DemoResetCheck:
    return health.DemoResetCheck(
        status=health.DemoResetStatus.CURRENT, last_successful_at=AHORA - timedelta(hours=5)
    )


async def _reinicio_vencido() -> health.DemoResetCheck:
    return health.DemoResetCheck(
        status=health.DemoResetStatus.OVERDUE, last_successful_at=AHORA - timedelta(hours=30)
    )


async def _reinicio_ilegible() -> health.DemoResetCheck:
    msg = "la tabla de corridas no responde"
    raise OSError(msg)


async def _reinicio_colgado() -> health.DemoResetCheck:
    await asyncio.sleep(5)
    return await _reinicio_al_dia()


def _deps(
    *,
    database_check: health.DatabaseCheck | None = _base_que_responde,
    tenants: int = 3,
    registry: surfaces.SurfaceRegistry | None = None,
    demo_reset_check: health.DemoResetProbe | None = _reinicio_al_dia,
) -> health.HealthDeps:
    return health.HealthDeps(
        version="abc123",
        providers=INDICADORES,
        registry=registry if registry is not None else surfaces.SurfaceRegistry(),
        database_check=database_check,
        tenant_count=lambda: tenants,
        demo_reset_check=demo_reset_check,
    )


def _corrida(termino: datetime) -> ResetRun:
    """Una corrida exitosa que termino en `termino`."""
    return ResetRun(
        reset_run_id=f"corrida-{termino.isoformat()}",
        started_at=termino - timedelta(seconds=30),
        finished_at=termino,
        outcome=ResetOutcome.SUCCEEDED,
        purgers=(PurgerRow(name="chat", deleted=3, kept=0, duration_seconds=1.0),),
    )


def _superficie(surface_id: SurfaceId, check: ProbeCheck) -> SurfaceSpec:
    return SurfaceSpec(
        surface_id=surface_id,
        owning_unit="prueba",
        public=True,
        per_tenant=True,
        probe=SurfaceProbe(check=check, timeout_ms=100),
    )


async def test_con_base_y_configuracion_el_proceso_esta_listo_y_no_inventa_superficies() -> None:
    resultado = await health.evaluate(_deps())

    assert resultado.ready
    assert resultado.checks.database is health.DatabaseStatus.OK
    assert resultado.checks.tenants == 3
    # Sin nada montado, el reporte no lista nada: nunca `ok` por no saber (BR5.3).
    assert resultado.checks.surfaces == {}
    assert resultado.checks.providers == INDICADORES


@pytest.mark.parametrize(
    "comprobacion",
    [None, _base_caida],
    ids=["sin-base-configurada", "base-caida"],
)
async def test_sin_base_el_proceso_no_esta_listo(
    comprobacion: health.DatabaseCheck | None, eventos: Eventos
) -> None:
    """NFR16.2: sin base no hay proceso listo, y la salud lo dice sin caerse."""
    resultado = await health.evaluate(_deps(database_check=comprobacion))

    assert not resultado.ready
    assert resultado.checks.database is health.DatabaseStatus.DOWN
    if comprobacion is not None:
        [fallo] = [e for e in eventos() if e["event"] == "server.database_check_failed"]
        assert fallo["error_type"] == "OSError"


async def test_una_base_colgada_se_corta_en_su_tiempo_y_no_en_el_de_la_base() -> None:
    """La salud entera cabe en un segundo aunque la base no conteste (C-02)."""
    inicio = time.perf_counter()
    resultado = await health.evaluate(_deps(database_check=_base_colgada))
    transcurrido = time.perf_counter() - inicio

    assert resultado.checks.database is health.DatabaseStatus.DOWN
    assert transcurrido < 1.0


async def test_sin_configuracion_de_aseguradoras_el_proceso_no_esta_listo() -> None:
    """La otra condicion de 503: una base que responde no basta sin aseguradoras."""
    resultado = await health.evaluate(_deps(tenants=0))

    assert not resultado.ready
    assert resultado.checks.database is health.DatabaseStatus.OK


async def test_una_superficie_caida_no_vuelve_no_apto_al_proceso() -> None:
    """NFR16.2: el chat caido sale `down` y el proceso sigue listo."""
    registro = surfaces.SurfaceRegistry(
        [
            _superficie(SurfaceId.CHAT, _sonda_que_lanza),
            _superficie(SurfaceId.INBOX, _sonda_lenta),
            _superficie(SurfaceId.CASE_LINK, _base_que_responde),
        ]
    )

    inicio = time.perf_counter()
    resultado = await health.evaluate(_deps(registry=registro))
    transcurrido = time.perf_counter() - inicio

    assert resultado.ready
    estados = {s: c.status for s, c in resultado.checks.surfaces.items()}
    assert estados == {
        SurfaceId.CHAT: "down",
        SurfaceId.INBOX: "down",
        SurfaceId.CASE_LINK: "ok",
    }
    assert transcurrido < 1.0


async def test_la_evaluacion_no_llama_a_ningun_proveedor_ni_gasta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NFR16.6 y SEC-U6.9: con cada puerta de dinero espiada, nadie la cruza."""
    llamadas = espias.instalar(monkeypatch)
    registro = surfaces.SurfaceRegistry([_superficie(SurfaceId.CHAT, _base_que_responde)])

    resultado = await health.evaluate(_deps(registry=registro))

    assert resultado.ready
    assert llamadas == []


def test_los_indicadores_de_proveedor_son_nombres_y_conteos_nunca_claves() -> None:
    """SEC-U6.3: el reporte no tiene donde poner una clave."""
    campos = set(health.ProviderIndicators.model_fields)

    assert campos == {"priced_units", "uses_with_key"}
    with pytest.raises(ValueError, match="priced_units"):
        health.ProviderIndicators(priced_units=-1, uses_with_key=())


# --- El reinicio nocturno ------------------------------------------------------


async def test_un_reinicio_al_dia_sale_con_la_hora_del_ultimo_exitoso() -> None:
    resultado = await health.evaluate(_deps(demo_reset_check=_reinicio_al_dia))

    assert resultado.ready
    assert resultado.checks.demo_reset == health.DemoResetCheck(
        status=health.DemoResetStatus.CURRENT, last_successful_at=AHORA - timedelta(hours=5)
    )


async def test_un_reinicio_vencido_se_dice_y_no_vuelve_no_apto_al_proceso() -> None:
    """El chat de los casos abiertos y la lectura siguen: es un indicador, no una condicion."""
    resultado = await health.evaluate(_deps(demo_reset_check=_reinicio_vencido))

    assert resultado.ready
    assert resultado.checks.demo_reset.status is health.DemoResetStatus.OVERDUE
    assert resultado.checks.demo_reset.last_successful_at == AHORA - timedelta(hours=30)
    assert resultado.checks.database is health.DatabaseStatus.OK


@pytest.mark.parametrize(
    "lectura",
    [_reinicio_ilegible, _reinicio_colgado, None],
    ids=["la-lectura-levanta", "la-lectura-se-cuelga", "sin-base-no-hay-registro-que-leer"],
)
async def test_un_reinicio_que_no_se_pudo_leer_sale_ilegible_y_la_salud_sigue_en_pie(
    lectura: health.DemoResetProbe | None, eventos: Eventos
) -> None:
    inicio = time.perf_counter()
    resultado = await health.evaluate(_deps(demo_reset_check=lectura))
    transcurrido = time.perf_counter() - inicio

    assert resultado.ready
    assert resultado.checks.demo_reset == health.DemoResetCheck(
        status=health.DemoResetStatus.UNREADABLE
    )
    # Un registro colgado se corta en su tiempo y no alarga la salud mas del segundo de C-02.
    assert transcurrido < 1.0
    fallos = [e for e in eventos() if e["event"] == "server.demo_reset_unreadable"]
    assert len(fallos) == (0 if lectura is None else 1)


def test_la_ruta_responde_200_con_el_reinicio_vencido_y_con_el_ilegible() -> None:
    """Lo que ve quien llama: 200 y el estado en `checks.demo_reset`, no un 503."""
    for lectura, estado in (
        (_reinicio_vencido, "overdue"),
        (_reinicio_ilegible, "unreadable"),
        (_reinicio_al_dia, "current"),
    ):
        app = FastAPI()
        app.include_router(health.router(_deps(demo_reset_check=lectura)))

        respuesta = TestClient(app).get("/api/health/ready")

        assert respuesta.status_code == 200
        assert respuesta.json()["checks"]["demo_reset"]["status"] == estado


def test_la_ruta_publica_la_hora_del_ultimo_reinicio_y_ningun_otro_dato() -> None:
    app = FastAPI()
    app.include_router(health.router(_deps(demo_reset_check=_reinicio_vencido)))

    cuerpo = TestClient(app).get("/api/health/ready").json()["checks"]["demo_reset"]

    assert set(cuerpo) == {"status", "last_successful_at"}
    assert datetime.fromisoformat(cuerpo["last_successful_at"]) == AHORA - timedelta(hours=30)


def test_el_tipo_no_deja_construir_un_estado_que_se_contradice() -> None:
    with pytest.raises(ValueError, match="cuando fue el ultimo exitoso"):
        health.DemoResetCheck(status=health.DemoResetStatus.CURRENT)
    with pytest.raises(ValueError, match="no se pudo leer"):
        health.DemoResetCheck(status=health.DemoResetStatus.UNREADABLE, last_successful_at=AHORA)
    with pytest.raises(ValueError, match="zona horaria"):
        health.DemoResetCheck(
            status=health.DemoResetStatus.OVERDUE, last_successful_at=datetime(2026, 10, 13)
        )


def test_la_regla_de_las_24_horas_es_la_de_u20_en_sus_dos_lados_del_borde() -> None:
    """`judge_demo_reset` no escribe la ventana: la pregunta a `accepts_new_cases`."""
    justo_antes = _corrida(AHORA - demo.RESET_WINDOW + timedelta(seconds=1))
    justo_despues = _corrida(AHORA - demo.RESET_WINDOW)

    al_dia = health.judge_demo_reset((justo_antes,), now=AHORA)
    vencido = health.judge_demo_reset((justo_despues,), now=AHORA)

    assert al_dia.status is health.DemoResetStatus.CURRENT
    assert al_dia.last_successful_at == justo_antes.finished_at
    assert vencido.status is health.DemoResetStatus.OVERDUE
    assert vencido.last_successful_at == justo_despues.finished_at
    # Y coincide con lo que decide el cierre del chat, para las mismas corridas.
    assert demo.accepts_new_cases((justo_antes,), now=AHORA)
    assert not demo.accepts_new_cases((justo_despues,), now=AHORA)


def test_sin_ningun_reinicio_exitoso_conocido_esta_vencido_y_sin_hora() -> None:
    resultado = health.judge_demo_reset((), now=AHORA)

    assert resultado == health.DemoResetCheck(status=health.DemoResetStatus.OVERDUE)


def test_un_ultimo_reinicio_en_el_futuro_esta_vencido() -> None:
    """Relojes en desacuerdo: la regla de U20 cierra, y el indicador lo dice igual."""
    resultado = health.judge_demo_reset((_corrida(AHORA + timedelta(hours=2)),), now=AHORA)

    assert resultado.status is health.DemoResetStatus.OVERDUE


async def test_la_lectura_real_juzga_las_corridas_que_el_registro_devuelve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ultima = _corrida(datetime.now(UTC) - timedelta(hours=2))

    async def corridas() -> tuple[ResetRun, ...]:
        return (ultima,)

    monkeypatch.setattr(demo, "successful_runs", corridas)

    resultado = await health.demo_reset_check()

    assert resultado.status is health.DemoResetStatus.CURRENT
    assert resultado.last_successful_at == ultima.finished_at
