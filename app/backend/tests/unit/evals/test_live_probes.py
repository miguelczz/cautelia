"""La sonda del escenario RT-4 contra el despliegue vivo (NFR10.3, AC4.11.5).

La **medicion** de RT-4 corre por hito contra el despliegue publico, y mientras
no exista uno el caso queda "no medido" con su causa. Lo que si se puede probar
hoy, y hay que probar, es que **la sonda funciona**: que da verde ante un
despliegue que responde bien y rojo ante cada una de las tres formas de
responder mal. Una sonda que nunca se ha visto fallar no sirve de compuerta.

Se levanta un servidor minimo en el propio proceso de la prueba: no toca la red
externa, no gasta cuota y se apaga al terminar.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from untangle.evals import live_probes
from untangle.evals.runner.api import CheckOutcome
from untangle.evals.runner.failures import TargetUnavailableError

#: Lo que responde un despliegue correcto: `404` con la misma causa opaca para
#: cualquier token que no valga (C-07).
RECHAZO_CORRECTO = (404, b'{"code":"link_invalid"}')

#: Donde vive el canje en el despliegue. Se toma al cargar el modulo y no en cada
#: peticion: una prueba cambia la ruta de la sonda y el servidor no la sigue.
RUTA_DEL_CANJE = live_probes.REDEEM_PATH


@contextmanager
def _servidor(responder: Callable[[bytes], tuple[int, bytes]]) -> Iterator[str]:
    """Levanta un despliegue de mentira y devuelve su direccion."""

    class Manejador(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # el nombre del metodo lo fija la clase base
            largo = int(self.headers.get("Content-Length", "0"))
            pedido = self.rfile.read(largo)
            # Como el despliegue de verdad: el canje vive bajo `/api`, y cualquier otra
            # ruta la contesta lo que sirve las paginas, igual para todo el mundo.
            if self.path == RUTA_DEL_CANJE:
                codigo, cuerpo = responder(pedido)
            else:
                codigo, cuerpo = 404, b"<!doctype html><title>Cautelia</title>"
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def log_message(self, *_: object) -> None:
            """Silencio: el servidor de prueba no ensucia la salida de la suite."""

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        yield f"http://127.0.0.1:{servidor.server_port}"
    finally:
        servidor.shutdown()
        servidor.server_close()
        hilo.join(timeout=5)


def _sondear(url: str, monkeypatch: pytest.MonkeyPatch) -> CheckOutcome:
    monkeypatch.setenv("UNTANGLE_LIVE_TARGET_URL", url)
    return live_probes.rt4_foreign_case_denied(language="es", root=Path("."))


def test_sin_despliegue_el_caso_queda_no_medido_y_nunca_en_verde(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una compuerta que no se pudo ejecutar se declara asi, jamas se omite."""
    monkeypatch.delenv("UNTANGLE_LIVE_TARGET_URL", raising=False)

    with pytest.raises(TargetUnavailableError) as fallo:
        live_probes.rt4_foreign_case_denied(language="es", root=Path("."))

    assert "UNTANGLE_LIVE_TARGET_URL" in str(fallo.value)


def test_un_despliegue_que_rechaza_igual_los_dos_tokens_pasa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El verde: dos tokens ajenos, dos `404` identicos byte a byte."""
    with _servidor(lambda _: RECHAZO_CORRECTO) as url:
        resultado = _sondear(url, monkeypatch)

    assert resultado.passed, resultado.detail


def test_el_identificador_de_traza_no_cuenta_como_diferencia(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El despliegue de verdad pone un `trace_id` distinto en cada rechazo: no dice
    nada del token, y con el dos rechazos iguales nunca lo serian byte a byte."""
    vistos: list[int] = []

    def responder(_: bytes) -> tuple[int, bytes]:
        vistos.append(len(vistos))
        cuerpo = {"code": "not_found", "status": 404, "trace_id": f"traza-{len(vistos)}"}
        return 404, json.dumps(cuerpo).encode()

    with _servidor(responder) as url:
        resultado = _sondear(url, monkeypatch)

    assert len(vistos) == len(live_probes.TOKENS_AJENOS)
    assert resultado.passed, resultado.detail


def test_un_404_que_no_es_del_api_queda_no_medido(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si el canje no esta donde la sonda lo busca, quien contesta es lo que sirve las
    paginas: un 404 igual para todos que no prueba nada. No se da por verde."""
    monkeypatch.setattr(live_probes, "REDEEM_PATH", "/case-links/redeem")

    with (
        _servidor(lambda _: RECHAZO_CORRECTO) as url,
        pytest.raises(TargetUnavailableError) as fallo,
    ):
        _sondear(url, monkeypatch)

    assert "no con el rechazo del API" in str(fallo.value)


def test_un_despliegue_que_concede_acceso_con_un_token_ajeno_falla(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El fallo que RT-4 existe para atrapar: un caso ajeno que si se abre."""
    concede = (200, json.dumps({"case_id": "CASE-DE-OTRO", "tenant": "sunmeadow"}).encode())
    with _servidor(lambda _: concede) as url:
        resultado = _sondear(url, monkeypatch)

    assert not resultado.passed
    assert "concedio acceso" in resultado.detail


def test_un_despliegue_que_distingue_las_causas_falla(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dos rechazos distintos convierten el rechazo en un oraculo (BR3.3)."""

    def responder(cuerpo: bytes) -> tuple[int, bytes]:
        token = json.loads(cuerpo)["token"]
        causa = "malformed" if token == live_probes.TOKENS_AJENOS[0] else "bad_signature"
        return 404, json.dumps({"code": causa}).encode()

    with _servidor(responder) as url:
        resultado = _sondear(url, monkeypatch)

    assert not resultado.passed
    assert "oraculo" in resultado.detail


def test_un_despliegue_que_responde_otro_codigo_falla(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`401` o `403` dirian que el enlace existe y no es tuyo. Tiene que ser `404`."""
    with _servidor(lambda _: (403, b'{"code":"forbidden"}')) as url:
        resultado = _sondear(url, monkeypatch)

    assert not resultado.passed
    assert "404" in resultado.detail


def test_un_despliegue_inalcanzable_queda_no_medido_y_no_fallido(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una caida de red no es un fallo del producto y no se cuenta como tal."""
    monkeypatch.setenv("UNTANGLE_LIVE_TARGET_URL", "http://127.0.0.1:1")

    with pytest.raises(TargetUnavailableError):
        live_probes.rt4_foreign_case_denied(language="es", root=Path("."))


def test_una_direccion_que_no_es_http_no_se_abre(monkeypatch: pytest.MonkeyPatch) -> None:
    """La sonda no abre archivos ni otros esquemas, aunque se los pidan."""
    monkeypatch.setenv("UNTANGLE_LIVE_TARGET_URL", "file:///etc/passwd")

    with pytest.raises(TargetUnavailableError) as fallo:
        live_probes.rt4_foreign_case_denied(language="es", root=Path("."))

    assert "no es http" in str(fallo.value)


# --- La otra mitad de RT-4: la cola de otra aseguradora ------------------------


@contextmanager
def _bandeja(responder: Callable[[str, str], tuple[int, bytes]]) -> Iterator[str]:
    """Un despliegue de mentira que contesta la cola segun la ruta y la credencial."""

    class Manejador(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # el nombre del metodo lo fija la clase base
            credencial = self.headers.get("Cookie", "").partition("=")[2]
            codigo, cuerpo = responder(self.path, credencial)
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def log_message(self, *_: object) -> None:
            """Silencio: el servidor de prueba no ensucia la salida de la suite."""

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        yield f"http://127.0.0.1:{servidor.server_port}"
    finally:
        servidor.shutdown()
        servidor.server_close()
        hilo.join(timeout=5)


def _rechazo(numero: list[int]) -> tuple[int, bytes]:
    """El rechazo del despliegue de verdad: igual para todos, con su traza propia."""
    numero.append(1)
    cuerpo = {"code": "not_found", "status": 404, "trace_id": f"traza-{len(numero)}"}
    return 404, json.dumps(cuerpo).encode()


def _pedir_la_cola(url: str, monkeypatch: pytest.MonkeyPatch) -> CheckOutcome:
    monkeypatch.setenv("UNTANGLE_LIVE_TARGET_URL", url)
    monkeypatch.setenv("UNTANGLE_STAFF_CREDENTIAL_SIGNING_KEY", "clave-de-esta-prueba-" + "x" * 24)
    return live_probes.rt4_inbox_queue_isolated(language="es", root=Path("."))


def test_la_cola_propia_se_entrega_y_la_ajena_se_rechaza_igual_que_a_cualquiera(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El verde, con un despliegue que pone su traza en cada rechazo."""
    propia, _ajena = live_probes._dos_aseguradoras()
    rechazos: list[int] = []

    def responder(ruta: str, credencial: str) -> tuple[int, bytes]:
        if propia.tenant_id in ruta and credencial != live_probes.CREDENCIAL_ILEGIBLE:
            return 200, json.dumps({"items": [{"case_number": "X"}]}).encode()
        return _rechazo(rechazos)

    with _bandeja(responder) as url:
        resultado = _pedir_la_cola(url, monkeypatch)

    assert resultado.passed, resultado.detail
    assert len(rechazos) == 2, "la cola ajena y la credencial ilegible, una vez cada una"


def test_una_cola_ajena_entregada_es_una_fuga(monkeypatch: pytest.MonkeyPatch) -> None:
    """El fallo que esta mitad existe para atrapar."""

    def responder(_ruta: str, credencial: str) -> tuple[int, bytes]:
        if credencial == live_probes.CREDENCIAL_ILEGIBLE:
            return 404, b'{"code":"not_found"}'
        return 200, json.dumps({"items": [{"case_number": "X"}]}).encode()

    with _bandeja(responder) as url:
        resultado = _pedir_la_cola(url, monkeypatch)

    assert not resultado.passed
    assert "fuga entre aseguradoras" in resultado.detail


def test_si_el_despliegue_no_acepta_la_credencial_el_caso_queda_no_medido(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin la clave de firma del despliegue la sonda no entra: no midio, no fallo."""
    with (
        _bandeja(lambda _ruta, _credencial: (404, b'{"code":"not_found"}')) as url,
        pytest.raises(TargetUnavailableError) as fallo,
    ):
        _pedir_la_cola(url, monkeypatch)

    assert "clave de firma" in str(fallo.value)


def test_una_bandeja_que_se_cae_si_es_un_fallo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un 500 no es "no pude entrar": la bandeja esta rota y eso se dice."""
    with _bandeja(lambda _ruta, _credencial: (500, b"{}")) as url:
        resultado = _pedir_la_cola(url, monkeypatch)

    assert not resultado.passed
    assert "control positivo" in resultado.detail
