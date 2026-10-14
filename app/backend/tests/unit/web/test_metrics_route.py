"""El panel de cifras servido: sin credencial, solo recuentos (U22, tanda 1).

SEC-U22.1 `[bloquea]`: la prueba mira **la respuesta del servidor**, no lo que
dibuja la pantalla. Devolver la lista de casos y contarla en el navegador pasaria
la cifra y filtraria la lista entera; aqui se siembran casos con identificadores
reconocibles y se exige que ninguno salga.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from untangle import paths
from untangle.copy_catalog import api as copy_api
from untangle.evals.evidence import api as evidence
from untangle.server import composition, evidence_routes
from untangle.settings import Settings
from untangle.surface_spec import MAX_PROBE_TIMEOUT_MS, SurfaceId, SurfaceSpec
from untangle.telemetry.spend import api as spend

from ..evals.evidence.builders import (
    CASOS_SEMBRADOS,
    latencia_de_chat,
    linea_base,
    sembrar,
)

MODULO = composition.ModuleSpec(
    module="untangle.server.evidence_routes", provides=frozenset({"router", "surfaces"})
)


@pytest.fixture(autouse=True)
def proceso_limpio() -> Any:
    yield
    copy_api.reset()
    spend.reset()


def _cliente() -> TestClient:
    app = composition.build_app(
        Settings(env="local", database_url=None),
        modules=(MODULO,),
        dist_dir=paths.frontend_dist_dir(),
    )
    return TestClient(app, raise_server_exceptions=False)


def test_el_panel_responde_sin_credencial_y_sin_linea_base(raiz: Path) -> None:
    with _cliente() as cliente:
        respuesta = cliente.get("/api/metrics")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["baseline_id"] is None
    assert [f["key"] for f in cuerpo["figures"]] == [
        "completeness",
        "citation_precision",
        "latency",
        "cost_per_case",
        "cases_by_tenant",
    ]
    assert all(f["state"] == "not_measured" for f in cuerpo["figures"])
    assert all(f["not_measured_cause"] for f in cuerpo["figures"])


def test_sin_linea_base_la_ruta_responde_exactamente_el_ejemplo_versionado(raiz: Path) -> None:
    """El ejemplo que usa la pantalla es la respuesta real, no una copia a mano."""
    with _cliente() as cliente:
        cuerpo = cliente.get("/api/metrics").json()

    ejemplo = json.loads(paths.metrics_example_path().read_text(encoding="utf-8"))
    assert cuerpo == ejemplo


def test_con_linea_base_sembrada_la_ruta_sirve_su_cabecera_y_ninguna_cifra_en_cero(
    raiz: Path,
) -> None:
    """**La premisa cambio el 2026-09-30 y la intencion no.**

    Esta prueba decia que con linea base sembrada dos cifras salen "medidas". Eso
    era cierto contra dos nombres de criterio inventados; hoy en produccion los dos
    son nulos, porque ningun criterio mide todavia estas dos cifras. Lo que la
    prueba sostiene sigue siendo lo mismo: que la ruta **leyo** la linea base y que
    ninguna cifra sale en cero.
    """
    sembrar(linea_base())
    with _cliente() as cliente:
        cuerpo = cliente.get("/api/metrics").json()

    # Leyo: la cabecera es de la linea base sembrada y no de la nada.
    assert cuerpo["baseline_id"] == "base-0001"
    assert cuerpo["commit_sha"] == linea_base().commit_sha

    estados = {f["key"]: f["state"] for f in cuerpo["figures"]}
    assert set(estados.values()) == {"not_measured"}
    causas = {f["key"]: f["not_measured_cause"] for f in cuerpo["figures"]}
    assert causas["completeness"] == "criterion_not_built"
    assert causas["citation_precision"] == "criterion_not_built"
    # Y ninguna celda con un cero donde lo cierto es "no medida" (BR1.2).
    for figura in cuerpo["figures"]:
        for celda in figura["by_language"].values():
            assert celda["value"] is None


def test_la_respuesta_no_trae_ningun_identificador_de_caso_sembrado(raiz: Path) -> None:
    sembrar(linea_base())
    with _cliente() as cliente:
        respuesta = cliente.get("/api/metrics")
    texto = respuesta.text

    # Control positivo: la ruta si leyo la linea base sembrada. Sin esto, una ruta
    # que no entregara nunca nada pasaria la ausencia igual.
    assert respuesta.json()["baseline_id"] == "base-0001"
    for caso in CASOS_SEMBRADOS:
        assert caso not in texto
    assert "sentinela" not in texto
    # La linea base trae los veredictos por caso; la respuesta no los copia.
    assert "case_verdicts" not in texto
    assert "DS-" not in texto.replace("DS-5", "").replace("DS-2", "")


def test_la_latencia_del_chat_de_la_linea_base_llega_por_idioma_y_sin_ningun_caso(
    raiz: Path,
) -> None:
    """La cifra publica de la latencia: p50, p95 y recuento por idioma, de la linea base
    versionada. Control positivo --los numeros llegan-- y control negativo --ningun
    identificador de caso, de conversacion ni de turno viaja con ellos--."""
    sembrar(
        linea_base(
            latencies=latencia_de_chat(es=(52, 1180, 2810), en=(9, 420, 3090), datasets=("DS-2",))
        )
    )
    with _cliente() as cliente:
        respuesta = cliente.get("/api/metrics")

    [latencia] = [f for f in respuesta.json()["figures"] if f["key"] == "latency"]
    [chat] = [m for m in latencia["latency"] if m["channel"] == "chat"]
    assert chat["not_measured_cause"] is None
    assert chat["by_language"]["es"] == {
        "state": "measured",
        "p50_ms": 1180,
        "p95_ms": 2810,
        "turns": 52,
        "not_measured_cause": None,
    }
    # Nueve turnos: no llegan al minimo, asi que no hay cifra y si el recuento.
    assert chat["by_language"]["en"] == {
        "state": "not_measured",
        "p50_ms": None,
        "p95_ms": None,
        "turns": 9,
        "not_measured_cause": "too_few_turns",
    }
    assert chat["source"]["run_id"] == "run-7"
    for caso in CASOS_SEMBRADOS:
        assert caso not in respuesta.text
    assert re.search(r"DS-\d/(es|en)/", respuesta.text) is None


def test_el_tipo_de_la_respuesta_no_puede_cargar_un_caso() -> None:
    """Ni hoy ni cuando la tanda 2 conecte los recuentos: ningun campo admite casos."""
    esquema = json.dumps(evidence.MetricsSnapshot.model_json_schema())
    prohibidos = ("case_id", "case_number", "case_key", "case_ids", "case_verdicts", "visitor")
    for nombre in prohibidos:
        assert nombre not in esquema, nombre


def test_una_linea_base_ilegible_es_un_error_interno_sin_detalle(raiz: Path) -> None:
    archivo = paths.current_baseline_path()
    archivo.parent.mkdir(parents=True)
    archivo.write_text("{no es json", encoding="utf-8")

    with _cliente() as cliente:
        respuesta = cliente.get("/api/metrics")

    assert respuesta.status_code == 500
    assert respuesta.json()["code"] == "internal"
    assert "current.json" not in respuesta.text


# --- La superficie (C-24) ------------------------------------------------------


def test_la_superficie_es_publica_unica_y_con_sonda_barata() -> None:
    [superficie] = evidence_routes.surfaces()

    assert superficie.surface_id is SurfaceId.METRICS_PANEL
    assert superficie.public is True
    assert superficie.per_tenant is False
    assert 1 <= superficie.probe.timeout_ms <= MAX_PROBE_TIMEOUT_MS


async def _sondear(superficie: SurfaceSpec) -> None:
    await superficie.probe.check()


def test_la_sonda_responde_con_y_sin_linea_base_y_cae_si_la_linea_base_no_se_lee(
    raiz: Path,
) -> None:
    [superficie] = evidence_routes.surfaces()
    asyncio.run(_sondear(superficie))  # sin linea base: responde
    sembrar(linea_base())
    asyncio.run(_sondear(superficie))  # con linea base: responde

    paths.current_baseline_path().write_text("{no es json", encoding="utf-8")
    with pytest.raises(Exception):  # noqa: B017 -- cualquier fallo marca la superficie caida
        asyncio.run(_sondear(superficie))


def test_la_raiz_de_composicion_monta_el_panel_por_defecto_y_el_inicio_lo_anuncia(
    raiz: Path,
) -> None:
    """Con la lista de modulos de verdad, no con una armada para la prueba."""
    assert MODULO in composition.MODULOS

    app = composition.build_app(Settings(env="local", database_url=None))
    with TestClient(app, raise_server_exceptions=False) as cliente:
        directorio = cliente.get("/api/site").json()
        respuesta = cliente.get("/api/metrics")

    assert "metrics_panel" in directorio["surfaces"]
    assert respuesta.status_code == 200


# --- PERF-U22.1: armar las cinco cifras, p95 <= 200 ms ---------------------------


def test_armar_las_cinco_cifras_cabe_en_el_presupuesto(raiz: Path) -> None:
    """Una linea base grande a proposito: 5 000 veredictos, no los tres de siempre.

    Si alguien pone una consulta a la base dentro del bucle de las cifras, este
    es el numero que lo delata (PERF-U22.1).
    """
    casos = tuple(f"DS-2/es/caso-{n:05d}" for n in range(5000))
    sembrar(linea_base(casos=casos))

    duraciones: list[float] = []
    for _ in range(100):
        inicio = time.perf_counter()
        evidence.current_snapshot()
        duraciones.append(time.perf_counter() - inicio)

    duraciones.sort()
    p95 = duraciones[int(len(duraciones) * 0.95) - 1]
    assert p95 <= 0.2, f"p95 = {p95 * 1000:.1f} ms; el presupuesto es 200 ms"
