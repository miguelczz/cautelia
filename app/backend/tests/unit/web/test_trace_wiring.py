"""La raiz de composicion cablea las trazas hacia Langfuse: solo con las tres variables, y en el ciclo de vida.

Se monta la aplicacion entera, como `test_served_process`, pero el transporte de Langfuse es
uno de `httpx2` falso: ninguna prueba sale a la red. Con las tres variables el arranque pide
el proyecto y deja el enlace, y el apagado exporta lo ultimo; sin ellas no se instala nada.
"""

from __future__ import annotations

import asyncio
import hashlib
import itertools
import json
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient

from untangle.base import ProviderName, Use
from untangle.compliance.redaction import detector as deteccion
from untangle.copy_catalog import api as copy_api
from untangle.providers.adapters import langfuse
from untangle.providers.adapters.langfuse import LangfuseTransport
from untangle.server import composition
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend
from untangle.telemetry.traces import api, export, links
from untangle.telemetry.traces.models import NodeName

HOST = "https://us.cloud.langfuse.com"
CLAVE_PUBLICA = "pk-lf-x"
CLAVE_SECRETA = "sk-lf-x"


@pytest.fixture(autouse=True)
def proceso_limpio() -> Iterator[None]:
    """La raiz instala catalogo, contabilidad, enlaces y transporte en variables de modulo."""
    yield
    copy_api.reset()
    spend.reset()
    links.install(None)
    export.install_transport(None)
    api.reset()
    deteccion.reset()
    deteccion.install_public_terms(())


@pytest.fixture(autouse=True)
def ids_deterministas(monkeypatch: pytest.MonkeyPatch) -> None:
    """Identificadores de traza y de tramo fijos: el modelo de nombres de la redaccion toma por
    persona, cada tanto y por cadena concreta, alguna cadena de cifras, y esta prueba no debe
    depender de ese azar. Sin `random` (prohibido en el proyecto): una semilla fija y SHA-256."""
    contador = itertools.count(1)

    def uuid_fijo() -> Any:
        resumen = hashlib.sha256(f"cableado-{next(contador)}".encode()).digest()
        return SimpleNamespace(int=int.from_bytes(resumen[:16], "big") >> 6)

    monkeypatch.setattr(api, "uuid4", uuid_fijo)


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    carpeta = tmp_path / "dist"
    carpeta.mkdir()
    (carpeta / "index.html").write_text("<!doctype html><title>x</title>", encoding="utf-8")
    return carpeta


def _langfuse_falso(recibidos: list[httpx2.Request]) -> httpx2.MockTransport:
    def manejador(peticion: httpx2.Request) -> httpx2.Response:
        recibidos.append(peticion)
        if peticion.url.path == "/api/public/projects":
            return httpx2.Response(200, json={"data": [{"id": "proyecto-local"}]})
        return httpx2.Response(200, json={})

    return httpx2.MockTransport(manejador)


def test_con_las_tres_variables_el_arranque_deja_el_enlace_y_el_apagado_exporta(
    dist: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recibidos: list[httpx2.Request] = []

    def transporte_de_prueba(ajustes: Settings) -> LangfuseTransport:
        return LangfuseTransport(
            public_key=CLAVE_PUBLICA,
            secret_key=CLAVE_SECRETA,
            host=ajustes.langfuse_host or HOST,
            network=_langfuse_falso(recibidos),
        )

    monkeypatch.setattr(langfuse, "build_transport", transporte_de_prueba)
    ajustes = Settings(
        env="ci",
        database_url=None,
        langfuse_public_key=CLAVE_PUBLICA,
        langfuse_secret_key=CLAVE_SECRETA,
        langfuse_host=HOST,
    )
    app = composition.build_app(ajustes, modules=(), dist_dir=dist)

    with TestClient(app, raise_server_exceptions=False):
        # El arranque no espera a Langfuse: el enlace aparece cuando la tarea de fondo
        # contesta. Se espera por la condicion y no por un reloj.
        asyncio.run(_hasta(lambda: links.available()))
        assert links.trace_url("48215069371502846913720465183927") == (
            f"{HOST}/project/proyecto-local/traces/48215069371502846913720465183927"
        )
        with (
            api.turn_span(tenant_id="stonecroft", case_id="case-1", use=Use.CHAT),
            api.node_span(NodeName.INTAKE),
            api.call_span(provider=ProviderName.GEMINI, model="gemini-2.5-flash-001", use=Use.CHAT),
        ):
            pass

    # Al salir del ciclo de vida, `stop` exporto lo que habia: una entrega OTLP.
    entregas = [p for p in recibidos if p.url.path == "/api/public/otel/v1/traces"]
    assert len(entregas) == 1
    lote: dict[str, Any] = json.loads(entregas[0].content)
    nombres = {t["name"] for t in lote["resourceSpans"][0]["scopeSpans"][0]["spans"]}
    assert nombres == {"turn", "intake", "call.gemini"}
    # Y el enlace se retiro con el transporte.
    assert not links.available()


def test_los_nombres_de_atributo_de_las_trazas_son_nombres_publicos_de_la_redaccion(
    dist: Path,
) -> None:
    """Sin esto, `langfuse.observation.type` salia como `[NAME 1]` (2026-10-14).

    La redaccion descarta un hallazgo hecho solo de nombres publicos; el arranque tiene que
    haber dejado ahi todos los que el exportador escribe, los de OpenTelemetry y los de Langfuse.
    """
    app = composition.build_app(Settings(env="ci", database_url=None), modules=(), dist_dir=dist)

    with TestClient(app, raise_server_exceptions=False):
        publicos = deteccion._TERMINOS_PUBLICOS

    assert set(export.wire_vocabulary()) <= publicos
    assert "langfuse.observation.type" in publicos


def test_sin_las_tres_variables_no_se_instala_ni_corre_nada(dist: Path) -> None:
    app = composition.build_app(Settings(env="ci", database_url=None), modules=(), dist_dir=dist)

    with TestClient(app, raise_server_exceptions=False):
        assert not links.available()
        assert isinstance(
            export.transport_for(Settings(env="ci", database_url=None)), export.FileTransport
        )


async def _hasta(condicion: Callable[[], bool], *, intentos: int = 1000) -> None:
    for _ in range(intentos):
        if condicion():
            return
        await asyncio.sleep(0.01)
    msg = "la condicion no se cumplio a tiempo"
    raise AssertionError(msg)
