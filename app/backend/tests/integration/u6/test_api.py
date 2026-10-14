"""La salud y el directorio por HTTP, con la base efimera de verdad (paso 13 de U6).

Cubre lo que sin base no se puede ver: listo en 200 con su reporte completo
(OBS-U6.1), su tiempo en p95 (NFR16.4), una superficie montada que aparece en el
inicio y en la salud sin tocar U6 (SCALE-U6.1), que ninguna de las dos rutas
toca un proveedor (NFR16.6, SEC-U6.9) ni cuenta nada sensible (SEC-U6.3), y la
base caida de verdad (NFR16.2).

Se llama a la aplicacion con un cliente ASGI en el **mismo** bucle de eventos
que la base efimera de la suite: el cliente de prueba sincrono corre la
aplicacion en otro hilo con otro bucle, y el grupo de conexiones de la base no
se puede compartir entre bucles.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from urllib.parse import urlsplit

import httpx2
import pytest
from fastapi import FastAPI

from untangle import paths
from untangle.copy_catalog import api as copy_api
from untangle.server import composition
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend
from untangle.telemetry.traces import api as trazas
from untangle.tenancy import ephemeral, session

from ...unit.web import espias

SUPERFICIES = composition.ModuleSpec(
    module="tests.unit.web.superficies_con_sonda", provides=frozenset({"surfaces"})
)

#: Valores que **no** pueden aparecer en ninguna respuesta publica. No son claves
#: de ningun proveedor: son marcas para buscarlas en la respuesta.
CLAVE_DE_CHAT = "marca-de-clave-de-chat-que-no-debe-salir-0001"
CLAVE_DE_BANDEJA = "marca-de-clave-de-bandeja-que-no-debe-salir-00002"
CLAVE_DE_ENLACES = "marca-de-clave-de-enlaces-que-no-debe-salir-000003"

BASE_INALCANZABLE = "postgresql+psycopg://untangle_app:no-es-una-clave@127.0.0.1:1/untangle"

type Construir = Callable[..., FastAPI]


@pytest.fixture
async def construir(
    sesiones: ephemeral.EphemeralDatabase, tmp_path: Path
) -> AsyncIterator[Construir]:
    """Construye la aplicacion contra la base efimera, y deja el proceso como estaba."""

    def hacer(database_url: str | None = None) -> FastAPI:
        ajustes = Settings(
            env="local",
            database_url=database_url if database_url is not None else sesiones.app_url,
            commit_sha="abc1234",
            chat_model_api_key=CLAVE_DE_CHAT,
            staff_credential_signing_key=CLAVE_DE_BANDEJA,
            case_link_signing_key=CLAVE_DE_ENLACES,
        )
        return composition.build_app(ajustes, modules=(SUPERFICIES,), dist_dir=tmp_path)

    try:
        yield hacer
    finally:
        await session.dispose()
        session.configure(sesiones.app_url)
        spend.reset()
        trazas.reset_summaries()
        copy_api.reset()


def _cliente(app: FastAPI) -> httpx2.AsyncClient:
    transporte = httpx2.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx2.AsyncClient(transport=transporte, base_url="http://testserver")


async def test_listo_responde_200_con_el_reporte_de_c02(construir: Construir) -> None:
    """OBS-U6.1: version, base, aseguradoras, cada superficie montada y los indicadores."""
    async with _cliente(construir()) as cliente:
        respuesta = await cliente.get("/api/health/ready")

    assert respuesta.status_code == 200
    reporte = respuesta.json()
    assert reporte["status"] == "ready"
    assert reporte["version"] == "abc1234"
    assert reporte["checks"]["database"] == "ok"
    assert reporte["checks"]["tenants"] == 3
    assert set(reporte["checks"]["surfaces"]) == {"chat", "inbox"}
    assert {s["status"] for s in reporte["checks"]["surfaces"].values()} == {"ok"}
    # Los indicadores de U5 que vivian en el `/health` retirado (FD-U6-6).
    assert reporte["checks"]["providers"]["priced_units"] >= 1
    assert reporte["checks"]["providers"]["uses_with_key"] == ["chat"]


async def test_listo_responde_en_un_segundo_o_menos_en_p95(construir: Construir) -> None:
    """NFR16.4, medido: veinte consultas seguidas con la base y dos sondas."""
    duraciones: list[float] = []
    async with _cliente(construir()) as cliente:
        for _ in range(20):
            inicio = time.perf_counter()
            respuesta = await cliente.get("/api/health/ready")
            duraciones.append(time.perf_counter() - inicio)
            assert respuesta.status_code == 200

    p95 = sorted(duraciones)[int(0.95 * len(duraciones)) - 1]
    assert p95 <= 1.0, f"p95 de listo: {p95:.3f} s"


async def test_una_superficie_montada_aparece_en_el_inicio_y_en_la_salud(
    construir: Construir,
) -> None:
    """SCALE-U6.1: el modulo de prueba solo expone `surfaces()`; U6 no se toca.

    El chat es publico y aparece en el directorio; la bandeja no lo es: se sondea
    en la salud y no se ofrece en el inicio (BR4.1).
    """
    async with _cliente(construir()) as cliente:
        directorio = await cliente.get("/api/site")
        listo = await cliente.get("/api/health/ready")

    assert directorio.json()["surfaces"] == ["chat"]
    assert set(listo.json()["checks"]["surfaces"]) == {"chat", "inbox"}


async def test_ni_la_salud_ni_el_directorio_llaman_a_un_proveedor_ni_gastan(
    construir: Construir, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NFR16.6 y SEC-U6.9, con cada puerta de dinero espiada en la aplicacion entera.

    Los espias se ponen **despues** de construir: al arrancar, la raiz crea el
    transporte de cada uso que tiene clave --un objeto, sin red--, y eso no es lo
    que se prueba. Lo que se prueba es que atender la salud y el directorio no
    cruza ninguna de esas puertas.
    """
    aplicacion = construir()
    llamadas = espias.instalar(monkeypatch)

    async with _cliente(aplicacion) as cliente:
        listo = await cliente.get("/api/health/ready")
        directorio = await cliente.get("/api/site")
        vivo = await cliente.get("/api/health/live")

    assert (listo.status_code, directorio.status_code, vivo.status_code) == (200, 200, 200)
    assert llamadas == []


async def test_las_respuestas_publicas_no_cuentan_nada_sensible(
    construir: Construir, sesiones: ephemeral.EphemeralDatabase
) -> None:
    """SEC-U6.3: ni claves, ni la direccion de la base, ni rutas del disco, ni trazas de pila."""
    partes = urlsplit(sesiones.app_url)
    prohibidos = [
        CLAVE_DE_CHAT,
        CLAVE_DE_BANDEJA,
        CLAVE_DE_ENLACES,
        sesiones.app_url,
        str(paths.repo_root()),
        "Traceback",
    ]
    if partes.password:
        prohibidos.append(partes.password)
    if partes.port:
        prohibidos.append(f":{partes.port}")

    async with _cliente(construir()) as cliente:
        cuerpos = [
            (await cliente.get(ruta)).text
            for ruta in ("/api/health/ready", "/api/site", "/api/health/live")
        ]

    for cuerpo in cuerpos:
        for prohibido in prohibidos:
            assert prohibido not in cuerpo


async def test_con_la_base_caida_listo_responde_503_a_tiempo_y_vivo_sigue(
    construir: Construir,
) -> None:
    """NFR16.2 con una base que de verdad no contesta, y sin contar donde estaba."""
    async with _cliente(construir(database_url=BASE_INALCANZABLE)) as cliente:
        inicio = time.perf_counter()
        listo = await cliente.get("/api/health/ready")
        transcurrido = time.perf_counter() - inicio
        vivo = await cliente.get("/api/health/live")

    assert listo.status_code == 503
    assert listo.json()["code"] == "provider_unavailable"
    assert transcurrido <= 1.0
    assert "no-es-una-clave" not in listo.text
    assert "127.0.0.1" not in listo.text
    assert vivo.status_code == 200
