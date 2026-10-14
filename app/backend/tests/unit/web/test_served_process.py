"""El proceso servido por HTTP, sin base de datos (BR6.1 a BR6.4, SEC-U6.1, SEC-U6.4, OBS-U6.2).

Se monta la aplicacion entera con la raiz de composicion --la misma que sirve la
demo-- y se la llama con el cliente de prueba. Los estaticos son una carpeta
`dist` propia de cada prueba, con una pagina de entrada, un archivo con huella,
uno sin huella y, **fuera** de `dist`, un archivo que ninguna ruta puede servir.

Sin base: listo responde 503, que es justo lo que algunas de estas pruebas
necesitan. Lo que exige base esta en `tests/integration/u6/test_api.py`.
"""

from __future__ import annotations

import gzip
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from untangle.copy_catalog import api as copy_api
from untangle.server import composition, security_headers
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend

from .eventos import Eventos
from .rutas_de_prueba import MENSAJE_INTERNO

ENTRADA = "<!doctype html><title>entrada de prueba</title>"
CON_HUELLA = "assets/index-AbCdEf12.js"
SIN_HUELLA = "theme-boot.js"
SECRETO = "contenido que vive fuera de dist y ninguna ruta puede servir"
PROBLEMA = "application/problem+json"
RUTAS_DE_PRUEBA = composition.ModuleSpec(
    module="tests.unit.web.rutas_de_prueba", provides=frozenset({"router"})
)


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    carpeta = tmp_path / "dist"
    (carpeta / "assets").mkdir(parents=True)
    (carpeta / "index.html").write_text(ENTRADA, encoding="utf-8")
    (carpeta / CON_HUELLA).write_text("console.log('huella')", encoding="utf-8")
    (carpeta / SIN_HUELLA).write_text("document.documentElement.dataset.mode='x'", "utf-8")
    (tmp_path / "secreto.txt").write_text(SECRETO, encoding="utf-8")
    return carpeta


@pytest.fixture(autouse=True)
def proceso_limpio() -> Iterator[None]:
    """La raiz instala el catalogo y la contabilidad en variables de modulo."""
    yield
    copy_api.reset()
    spend.reset()


def _cliente(dist: Path, *, https: bool = False) -> TestClient:
    app = composition.build_app(
        Settings(env="local", database_url=None), modules=(RUTAS_DE_PRUEBA,), dist_dir=dist
    )
    origen = "https://testserver" if https else "http://testserver"
    return TestClient(app, base_url=origen, raise_server_exceptions=False)


# --- Las cabeceras de seguridad ---------------------------------------------------


@pytest.mark.parametrize(
    ("metodo", "ruta", "estado"),
    [
        ("GET", "/api/site", 200),
        ("GET", f"/{CON_HUELLA}", 200),
        ("GET", "/una/pantalla/de/la/interfaz", 200),
        ("GET", "/api/no-existe", 404),
        ("GET", "/api/health/ready", 503),
        ("GET", "/api/_prueba/falla", 500),
        ("POST", "/", 405),
    ],
    ids=["api", "estatico", "aplicacion", "api-404", "listo-503", "no-previsto-500", "metodo-405"],
)
def test_toda_respuesta_lleva_el_conjunto_unico_de_cabeceras(
    dist: Path, metodo: str, ruta: str, estado: int
) -> None:
    """SEC-U6.1 y BR6.2: las tres ramas y los errores, incluido el no previsto."""
    with _cliente(dist) as cliente:
        respuesta = cliente.request(metodo, ruta)

    assert respuesta.status_code == estado
    for nombre, valor in security_headers.SECURITY_HEADERS:
        assert respuesta.headers.get(nombre) == valor, nombre
    # La politica exacta de CG-U6-2: sin excepciones para scripts.
    politica = respuesta.headers["content-security-policy"]
    assert "script-src 'self';" in politica
    assert "unsafe-inline" not in politica
    assert "unsafe-eval" not in politica
    assert "frame-ancestors 'none'" in politica
    # Por HTTP el transporte estricto no significa nada y no se manda.
    assert "strict-transport-security" not in respuesta.headers


def test_por_https_se_anade_el_transporte_estricto(dist: Path) -> None:
    with _cliente(dist, https=True) as cliente:
        respuesta = cliente.get("/api/health/live")

    assert respuesta.headers["strict-transport-security"] == (
        security_headers.STRICT_TRANSPORT_SECURITY
    )


# --- Los errores con la forma de C-01 -------------------------------------------


def test_un_error_no_previsto_sale_como_internal_sin_detalle(dist: Path, eventos: Eventos) -> None:
    """BR6.4 y SEC-U6.4: al cliente, `internal` y nada mas; al evento, lo que paso."""
    with _cliente(dist) as cliente:
        respuesta = cliente.get("/api/_prueba/falla")

    assert respuesta.status_code == 500
    assert respuesta.headers["content-type"].startswith(PROBLEMA)
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "internal"
    assert "detail" not in cuerpo
    assert MENSAJE_INTERNO not in respuesta.text
    assert "RuntimeError" not in respuesta.text
    assert "Traceback" not in respuesta.text
    assert cuerpo["trace_id"] == respuesta.headers["x-trace-id"]
    [evento] = [e for e in eventos() if e["event"] == "server.unhandled_error"]
    assert evento["error_type"] == "RuntimeError"
    assert evento["route"] == "/api/_prueba/falla"
    assert evento["trace_id"] == cuerpo["trace_id"]
    assert MENSAJE_INTERNO not in str(evento)


@pytest.mark.parametrize("metodo", ["GET", "POST", "DELETE"])
def test_una_ruta_desconocida_bajo_api_responde_json_y_nunca_la_aplicacion(
    dist: Path, metodo: str
) -> None:
    """BR6.1: un cliente que pide JSON no recibe HTML."""
    with _cliente(dist) as cliente:
        respuesta = cliente.request(metodo, "/api/esto/no/existe")

    assert respuesta.status_code == 404
    assert respuesta.headers["content-type"].startswith(PROBLEMA)
    assert respuesta.json()["code"] == "not_found"
    assert ENTRADA not in respuesta.text


def test_una_validacion_fallida_no_devuelve_lo_que_se_envio(dist: Path, eventos: Eventos) -> None:
    with _cliente(dist) as cliente:
        respuesta = cliente.get("/api/_prueba/numero", params={"n": "valor-enviado-por-alguien"})

    assert respuesta.status_code == 422
    assert respuesta.json()["code"] == "validation_failed"
    assert "valor-enviado-por-alguien" not in respuesta.text
    [evento] = [e for e in eventos() if e["event"] == "server.request_invalid"]
    assert evento["fields"] == ["query.n"]
    assert "valor-enviado-por-alguien" not in str(evento)


def test_sin_base_listo_responde_503_con_la_forma_de_c01_y_vivo_sigue_en_200(dist: Path) -> None:
    """NFR16.2: sin base el proceso no esta listo, pero esta vivo."""
    with _cliente(dist) as cliente:
        vivo = cliente.get("/api/health/live")
        listo = cliente.get("/api/health/ready")

    assert vivo.status_code == 200
    assert vivo.json() == {"status": "live"}
    assert listo.status_code == 503
    assert listo.headers["content-type"].startswith(PROBLEMA)
    assert listo.headers["retry-after"] == "5"
    assert listo.json()["code"] == "provider_unavailable"


# --- Los estaticos y el retorno a la aplicacion ---------------------------------


@pytest.mark.parametrize("ruta", ["/", "/status/waking", "/tenants/cualquiera/chat"])
def test_una_ruta_de_la_interfaz_devuelve_la_aplicacion_sin_cache(dist: Path, ruta: str) -> None:
    """BR6.1 y BR6.3: la pagina de entrada para el enrutador, y nunca guardada."""
    with _cliente(dist) as cliente:
        respuesta = cliente.get(ruta)

    assert respuesta.status_code == 200
    assert respuesta.text == ENTRADA
    assert respuesta.headers["cache-control"] == "no-store"


def test_con_huella_se_guarda_un_ano_y_sin_huella_se_revalida(dist: Path) -> None:
    """BR6.3: la huella en el nombre es lo que permite guardar sin riesgo."""
    with _cliente(dist) as cliente:
        con_huella = cliente.get(f"/{CON_HUELLA}")
        sin_huella = cliente.get(f"/{SIN_HUELLA}")
        entrada = cliente.get("/index.html")

    assert con_huella.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert sin_huella.headers["cache-control"] == "no-cache"
    assert entrada.headers["cache-control"] == "no-store"
    assert con_huella.text == "console.log('huella')"


def _con_variantes(dist: Path) -> None:
    """Las versiones que deja la compilacion junto al archivo con huella y la entrada."""
    for relativo, contenido in ((CON_HUELLA, "console.log('huella')"), ("index.html", ENTRADA)):
        original = dist / relativo
        (original.parent / f"{original.name}.gz").write_bytes(gzip.compress(contenido.encode()))
        (original.parent / f"{original.name}.br").write_bytes(b"brotli-de-prueba")


def test_con_gzip_aceptado_sirve_la_version_comprimida_con_el_tipo_del_original(
    dist: Path,
) -> None:
    """PERF-U6.1: lo que viaja antes de la pagina de espera va comprimido."""
    _con_variantes(dist)
    with _cliente(dist) as cliente:
        respuesta = cliente.get(f"/{CON_HUELLA}", headers={"Accept-Encoding": "gzip, deflate"})

    assert respuesta.headers["content-encoding"] == "gzip"
    assert respuesta.headers["content-type"].startswith("text/javascript")
    assert respuesta.headers["vary"] == "Accept-Encoding"
    assert respuesta.headers["cache-control"] == "public, max-age=31536000, immutable"
    # El cliente de prueba descomprime: lo que llega es el archivo de siempre.
    assert respuesta.text == "console.log('huella')"


def test_brotli_se_prefiere_si_el_navegador_lo_acepta(dist: Path) -> None:
    _con_variantes(dist)
    with _cliente(dist) as cliente:
        peticion = cliente.build_request("GET", "/", headers={"Accept-Encoding": "gzip, br"})
        # Sin descomprimir: lo que se mira es que codificacion eligio el proceso.
        respuesta = cliente.send(peticion, stream=True)
        cabeceras = dict(respuesta.headers)
        respuesta.close()

    assert cabeceras["content-encoding"] == "br"
    assert cabeceras["cache-control"] == "no-store"
    assert cabeceras["content-type"].startswith("text/html")


@pytest.mark.parametrize("aceptado", ["", "identity", "gzip;q=0", "br;q=0, gzip;q=0.0"])
def test_sin_codificacion_aceptada_sirve_el_original(dist: Path, aceptado: str) -> None:
    _con_variantes(dist)
    with _cliente(dist) as cliente:
        respuesta = cliente.get(f"/{CON_HUELLA}", headers={"Accept-Encoding": aceptado})

    assert "content-encoding" not in respuesta.headers
    assert respuesta.text == "console.log('huella')"


def test_sin_version_comprimida_sirve_el_original_aunque_se_acepte(dist: Path) -> None:
    with _cliente(dist) as cliente:
        respuesta = cliente.get(f"/{SIN_HUELLA}", headers={"Accept-Encoding": "gzip, br"})

    assert "content-encoding" not in respuesta.headers
    assert respuesta.headers["vary"] == "Accept-Encoding"


def test_la_api_no_se_comprime(dist: Path) -> None:
    """Un cuerpo de la API nunca va comprimido (ataque de compresion)."""
    with _cliente(dist) as cliente:
        respuesta = cliente.get("/api/site", headers={"Accept-Encoding": "gzip, br"})

    assert "content-encoding" not in respuesta.headers


@pytest.mark.parametrize(
    "ruta", ["/..%2fsecreto.txt", "/%2e%2e/secreto.txt", "/assets/..%2f..%2fsecreto.txt"]
)
def test_una_ruta_que_intenta_salir_de_dist_no_sirve_nada_de_fuera(dist: Path, ruta: str) -> None:
    with _cliente(dist) as cliente:
        respuesta = cliente.get(ruta)

    assert SECRETO not in respuesta.text


def test_sin_la_interfaz_compilada_sus_rutas_dicen_servicio_no_disponible(tmp_path: Path) -> None:
    """CG-U6-5: sin compilar, la API sigue atendiendo y la interfaz responde 503."""
    with _cliente(tmp_path / "sin-compilar") as cliente:
        interfaz = cliente.get("/")
        api = cliente.get("/api/health/live")

    assert interfaz.status_code == 503
    assert interfaz.headers["content-type"].startswith(PROBLEMA)
    assert interfaz.json()["code"] == "provider_unavailable"
    assert api.status_code == 200


# --- La traza en toda respuesta --------------------------------------------------


def test_cada_respuesta_lleva_su_propia_traza_y_el_error_la_repite(dist: Path) -> None:
    """OBS-U6.2 y C-01: la cabecera y el `trace_id` del error son el mismo valor."""
    with _cliente(dist) as cliente:
        una = cliente.get("/api/site")
        otra = cliente.get("/")
        error = cliente.get("/api/no-existe")

    trazas = [r.headers["x-trace-id"] for r in (una, otra, error)]
    assert all(re.fullmatch(r"[0-9a-f]{32}", traza) for traza in trazas)
    assert len(set(trazas)) == 3
    assert error.json()["trace_id"] == error.headers["x-trace-id"]


def test_la_documentacion_de_la_api_no_se_publica(dist: Path) -> None:
    """Sus paginas cargan scripts de un tercero que la politica bloquea (SEC-U6.2)."""
    with _cliente(dist) as cliente:
        documentacion = cliente.get("/docs")
        esquema = cliente.get("/openapi.json")

    # Caen en la aplicacion como cualquier otra ruta de la interfaz.
    assert documentacion.text == ENTRADA
    assert esquema.text == ENTRADA
