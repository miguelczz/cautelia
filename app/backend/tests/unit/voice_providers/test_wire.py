"""El transporte de voz traduce la red a los tres tipos de la frontera, y nada mas.

Sin red: la respuesta HTTP la da el transporte de prueba del propio cliente, y
el WebSocket, un conector que contesta en memoria. Lo que se comprueba es la
traduccion --que ningun tipo de `websockets` ni de `httpx2` cruza hacia fuera--
y que la credencial viaja en cabecera y nunca en la URL.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosedError, InvalidStatus
from websockets.frames import Close
from websockets.http11 import Response

from untangle.base import Use
from untangle.providers.adapters import wire
from untangle.providers.adapters.deepgram import ENDPOINT as DEEPGRAM
from untangle.providers.speech_wire import SpeechRequest, WireClosedError, WireRejectedError
from untangle.providers.transport import TransportError

PETICION = SpeechRequest(
    path="v1/speak",
    query={"model": "aura-2-celeste-es"},
    body={"text": "hola"},
    connect_timeout_ms=1000,
    read_timeout_ms=1000,
)


def _http(handler: Callable[[httpx2.Request], httpx2.Response]) -> tuple[Any, str]:
    clave = secrets.token_urlsafe(24)
    fabrica = wire.WireTransportFactory(DEEPGRAM, network=httpx2.MockTransport(handler))
    return fabrica.create(api_key=clave, use=Use.VOICE), clave


async def test_la_respuesta_a_trozos_llega_con_la_clave_en_cabecera_y_no_en_la_url() -> None:
    vistas: list[httpx2.Request] = []

    def contestar(peticion: httpx2.Request) -> httpx2.Response:
        vistas.append(peticion)
        return httpx2.Response(
            200,
            headers={"content-type": "audio/l16;rate=24000", "dg-char-count": "4"},
            content=bytes(960),
        )

    transporte, clave = _http(contestar)
    async with transporte.stream_post(PETICION) as flujo:
        audio = b"".join([t async for t in flujo.chunks()])
        assert flujo.content_type == "audio/l16;rate=24000"
        assert flujo.header("dg-char-count") == "4"

    assert audio == bytes(960)
    (vista,) = vistas
    assert vista.headers["authorization"] == f"Token {clave}"
    assert clave not in str(vista.url)
    assert vista.url.params["model"] == "aura-2-celeste-es"
    assert clave not in repr(transporte)


async def test_un_rechazo_lleva_el_codigo_y_el_cuerpo_pero_no_lo_imprime() -> None:
    def contestar(_: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(403, json={"err_code": "INSUFFICIENT_PERMISSIONS", "err_msg": "x"})

    transporte, _ = _http(contestar)
    with pytest.raises(WireRejectedError) as capturado:
        async with transporte.stream_post(PETICION):
            pass
    assert capturado.value.status_code == 403
    assert capturado.value.body["err_code"] == "INSUFFICIENT_PERMISSIONS"
    assert "INSUFFICIENT" not in str(capturado.value)


@pytest.mark.parametrize(
    ("fallo", "agotado"),
    [(httpx2.ReadTimeout("lento"), True), (httpx2.ConnectError("sin red"), False)],
)
async def test_sin_respuesta_es_un_fallo_de_transporte(fallo: Exception, agotado: bool) -> None:
    def contestar(_: httpx2.Request) -> httpx2.Response:
        raise fallo

    transporte, _ = _http(contestar)
    with pytest.raises(TransportError) as capturado:
        async with transporte.stream_post(PETICION):
            pass
    assert capturado.value.timed_out is agotado
    with pytest.raises(TransportError):
        await transporte.get_json(PETICION)


async def test_la_consulta_de_catalogo_devuelve_el_mapa_o_nada() -> None:
    respuestas = iter([httpx2.Response(200, json={"tts": []}), httpx2.Response(200, text="no")])
    transporte, _ = _http(lambda _: next(respuestas))
    assert await transporte.get_json(PETICION) == (200, {"tts": []})
    assert await transporte.get_json(PETICION) == (200, {})


class _Conexion:
    """Un WebSocket en memoria: entrega lo que se le dio y anota lo que recibe."""

    def __init__(self, entrantes: list[str | bytes | Exception]) -> None:
        self._entrantes = entrantes
        self.salientes: list[str | bytes] = []
        self.cerrada = False

    async def send(self, mensaje: str | bytes) -> None:
        if self.cerrada:
            raise ConnectionClosedError(Close(1011, ""), None)
        self.salientes.append(mensaje)

    async def recv(self) -> str | bytes:
        if not self._entrantes:
            await asyncio.sleep(1)
        siguiente = self._entrantes.pop(0)
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente

    async def close(self) -> None:
        self.cerrada = True


def _ws(conector: Any) -> Any:
    fabrica = wire.WireTransportFactory(DEEPGRAM, connector=conector)
    return fabrica.create(api_key=secrets.token_urlsafe(24), use=Use.VOICE)


async def test_el_canal_traduce_mensajes_cierres_y_esperas() -> None:
    conexion = _Conexion(
        ['{"type": "Results"}', b"\x00\x01", ConnectionClosedError(Close(1011, ""), None)]
    )
    recibidos: dict[str, Any] = {}

    async def conectar(url: str, **opciones: Any) -> _Conexion:
        recibidos.update(opciones, url=url)
        return conexion

    transporte = _ws(conectar)
    async with transporte.open_duplex(PETICION) as canal:
        await canal.send_text('{"type": "Finalize"}')
        await canal.send_bytes(b"\x00\x00")
        texto = await canal.receive(timeout_s=0.5)
        binario = await canal.receive(timeout_s=0.5)
        with pytest.raises(WireClosedError) as cierre:
            await canal.receive(timeout_s=0.5)
        assert await canal.receive(timeout_s=0.01) is None

    assert texto is not None and texto.text == '{"type": "Results"}'
    assert binario is not None and binario.data == b"\x00\x01"
    assert cierre.value.code == 1011
    assert conexion.cerrada
    assert conexion.salientes == ['{"type": "Finalize"}', b"\x00\x00"]
    assert "Token " not in recibidos["url"]
    # El registro que recibe la biblioteca no escribe nada, a ningun nivel.
    silencio: logging.Logger = recibidos["logger"]
    assert not silencio.propagate
    assert not silencio.isEnabledFor(logging.CRITICAL)
    with pytest.raises(WireClosedError):
        await canal.send_text("{}")


@pytest.mark.parametrize(
    ("fallo", "esperado"),
    [
        (
            InvalidStatus(Response(402, "Payment Required", Headers(), b'{"err_code": "X"}')),
            "rechazo",
        ),
        (TimeoutError(), "agotado"),
        (OSError("sin red"), "caido"),
    ],
)
async def test_la_apertura_del_canal_traduce_su_fallo(fallo: Exception, esperado: str) -> None:
    async def conectar(url: str, **_: Any) -> _Conexion:
        raise fallo

    transporte = _ws(conectar)
    if esperado == "rechazo":
        with pytest.raises(WireRejectedError) as rechazo:
            async with transporte.open_duplex(PETICION):
                pass
        assert (rechazo.value.status_code, rechazo.value.body) == (402, {"err_code": "X"})
        return
    with pytest.raises(TransportError) as capturado:
        async with transporte.open_duplex(PETICION):
            pass
    assert capturado.value.timed_out is (esperado == "agotado")
