"""Reproduce una respuesta grabada como si el proveedor contestara (BR6.1).

Es el transporte de `test:u15`: en lugar de abrir un WebSocket o una peticion
HTTP, sirve lo que dice el archivo grabado. Lo que se dobla es **lo que contesta
el proveedor**, no el adaptador: el adaptador corre entero --techo, protocolo,
traduccion de errores, gasto-- sobre los mismos marcos que mando el proveedor el
dia de la captura.

Dos cosas que el reproductor hace para ser fiel, y que conviene saber al leer
una prueba:

- **Respeta el orden del contrato de Deepgram**: el resultado marcado
  `from_finalize` no se entrega hasta que el adaptador mando `Finalize`, que es
  cuando el proveedor de verdad lo manda.
- **Devuelve el `context_id` de la peticion en curso**: Cartesia repite en cada
  marco el identificador que el adaptador genero, y el de la captura no es el de
  la prueba. Solo se sustituye el de la captura: un marco con otro identificador
  llega tal cual, que es como se prueba un marco de otra peticion.

Y una que no hace: **no espera de verdad**. Cuando no queda nada que entregar
devuelve `None`, que es "no llego nada a tiempo", y el adaptador decide si eso ya
es un tiempo agotado.
"""

from __future__ import annotations

import asyncio
import base64
import copy
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from untangle.base import Use
from untangle.providers.speech_wire import (
    ByteStream,
    DuplexChannel,
    SpeechRequest,
    SpeechTransport,
    WireClosedError,
    WireMessage,
    WireRejectedError,
)
from untangle.providers.transport import TransportError

RECORDED = Path(__file__).parent / "recorded"


def load(name: str) -> dict[str, Any]:
    """Un archivo grabado, por su nombre sin extension."""
    datos = json.loads((RECORDED / f"{name}.json").read_text(encoding="utf-8"))
    assert isinstance(datos, dict)
    return datos


def _es_final_forzado(marco: Mapping[str, Any]) -> bool:
    texto = marco.get("text")
    return isinstance(texto, Mapping) and texto.get("from_finalize") is True


class ReplayChannel(DuplexChannel):
    """Un canal que entrega los marcos grabados, en su orden."""

    def __init__(self, fixture: Mapping[str, Any]) -> None:
        self._pendientes = list(fixture.get("received", []))
        self._cierre = fixture.get("closed")
        self.sent_texts: list[dict[str, Any]] = []
        self.sent_bytes = 0
        self._contexto: str | None = None
        self._finalizado = False
        # El identificador que llevaba la peticion el dia de la captura: solo los
        # marcos que traen **ese** pasan a llevar el de la peticion en curso.
        enviados = fixture.get("sent") or []
        primero = enviados[0].get("text", {}) if enviados else {}
        self._contexto_grabado: object = primero.get("context_id")

    async def send_bytes(self, data: bytes) -> None:
        await asyncio.sleep(0)
        self.sent_bytes += len(data)

    async def send_text(self, text: str) -> None:
        await asyncio.sleep(0)
        mensaje = json.loads(text)
        self.sent_texts.append(mensaje)
        if mensaje.get("type") == "Finalize":
            self._finalizado = True
        if isinstance(mensaje.get("context_id"), str):
            self._contexto = mensaje["context_id"]

    async def receive(self, *, timeout_s: float) -> WireMessage | None:
        # Cede el turno: la tarea que sube el audio tiene que poder avanzar
        # mientras el adaptador espera resultados, como con un canal de verdad.
        await asyncio.sleep(0)
        if not self._pendientes:
            if self._cierre is not None:
                raise WireClosedError(self._cierre.get("code"))
            return None
        if _es_final_forzado(self._pendientes[0]) and not self._finalizado:
            return None
        marco = self._pendientes.pop(0)
        if "binary_b64" in marco:
            return WireMessage(data=base64.b64decode(marco["binary_b64"]))
        if "text_raw" in marco:
            return WireMessage(text=str(marco["text_raw"]))
        texto = copy.deepcopy(marco["text"])
        if (
            self._contexto is not None
            and isinstance(texto, dict)
            and texto.get("context_id") == self._contexto_grabado
        ):
            texto["context_id"] = self._contexto
        return WireMessage(text=json.dumps(texto))


class ReplayStream(ByteStream):
    """Una respuesta HTTP que entrega los trozos grabados."""

    def __init__(self, fixture: Mapping[str, Any]) -> None:
        respuesta = fixture.get("response") or {}
        self._cabeceras: dict[str, str] = dict(respuesta.get("headers", {}))
        self._trozos = [
            base64.b64decode(m["binary_b64"])
            for m in fixture.get("received", [])
            if "binary_b64" in m
        ]
        self._cortar_en: int | None = fixture.get("fail_after_chunks")

    @property
    def content_type(self) -> str:
        return self._cabeceras.get("content-type", "")

    def header(self, name: str) -> str | None:
        return self._cabeceras.get(name)

    async def chunks(self) -> AsyncIterator[bytes]:
        for numero, trozo in enumerate(self._trozos):
            if self._cortar_en is not None and numero >= self._cortar_en:
                raise TransportError("ReadTimeout", timed_out=True)
            await asyncio.sleep(0)
            yield trozo


class ReplayTransport(SpeechTransport):
    """El transporte que sirve un archivo grabado. Una peticion por archivo."""

    def __init__(self, fixture: Mapping[str, Any]) -> None:
        self.fixture = fixture
        self.requests: list[SpeechRequest] = []
        self.channels: list[ReplayChannel] = []

    def _rechazar_si_toca(self) -> None:
        rechazo = self.fixture.get("rejected")
        if rechazo is not None:
            raise WireRejectedError(int(rechazo["status_code"]), dict(rechazo.get("body") or {}))

    @asynccontextmanager
    async def open_duplex(self, request: SpeechRequest) -> AsyncIterator[DuplexChannel]:
        self.requests.append(request)
        self._rechazar_si_toca()
        canal = ReplayChannel(self.fixture)
        self.channels.append(canal)
        yield canal

    @asynccontextmanager
    async def stream_post(self, request: SpeechRequest) -> AsyncIterator[ByteStream]:
        self.requests.append(request)
        self._rechazar_si_toca()
        yield ReplayStream(self.fixture)

    async def get_json(self, request: SpeechRequest) -> tuple[int, Mapping[str, object]]:
        """La respuesta de catalogo que declara la prueba, por ruta.

        Solo la consulta el comando a mano, y ninguna respuesta grabada la trae:
        la prueba que la necesita escribe en `catalog` que contesta cada ruta, y
        una ruta que no escribio es un fallo de la prueba, no un 404.
        """
        self.requests.append(request)
        catalogo = self.fixture.get("catalog")
        if not isinstance(catalogo, Mapping) or request.path not in catalogo:
            msg = f"la prueba no declara que contesta el catalogo en '{request.path}'"
            raise AssertionError(msg)
        respuesta = catalogo[request.path]
        if isinstance(respuesta, BaseException):
            raise respuesta
        return int(respuesta["status"]), dict(respuesta.get("body") or {})


class ReplayFactory:
    """La fabrica de transportes de prueba. Anota con que clave y uso la construyeron."""

    def __init__(self, transport: SpeechTransport) -> None:
        self.transport = transport
        self.created: list[tuple[str, Use]] = []

    def create(self, *, api_key: str, use: Use) -> SpeechTransport:
        self.created.append((api_key, use))
        return self.transport
