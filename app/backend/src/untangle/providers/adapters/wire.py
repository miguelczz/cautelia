"""El transporte de voz de verdad: WebSocket y HTTP en streaming (U15).

Implementa la frontera de `providers/speech_wire.py` para los dos proveedores de
voz. Vive dentro de `adapters/` porque es el unico sitio del aplicativo donde se
puede importar un cliente de red (BR1.1): `websockets` para los canales de ida y
vuelta y `httpx2` para la respuesta a trozos de Aura-2. **Sin SDK de proveedor**
(FD-U15-1): los dos documentan su API de WebSocket y HTTP como la principal, y
es el camino que midio el experimento 1.

Es un solo transporte para los dos proveedores y no uno por proveedor, porque lo
unico que cambia entre ellos son las raices y como se presenta la credencial.
Eso es un dato (`WireEndpoint`) que declara el paquete de cada adaptador.

## La clave entra y no sale

Entra en `create(api_key=..., use=...)` y se queda en las cabeceras de este
objeto, que ningun metodo devuelve y que `__repr__` no imprime. Viaja siempre en
cabecera y **nunca en la URL**: el 2026-09-21 una clave en la cadena de consulta
acabo impresa en una traza del experimento 1, y una clave que se imprime se rota.

## Lo que ningun registro puede ver

`websockets` registra cada marco a nivel de depuracion, con un resumen de su
contenido. En un canal de voz ese contenido es **audio de una persona o el texto
de lo que dijo** (BR3.2, SEC-U15.4), asi que la conexion se abre con un registro
propio que no escribe nada, sea cual sea el nivel que configure el proceso.

## Que traduce y que no

Traduce los fallos de la biblioteca a los tres tipos de la frontera
--`TransportError`, `WireRejectedError`, `WireClosedError`-- y **nada mas**:
cual de los cuatro tipos de error es cada uno lo decide la traduccion de cada
adaptador, que es la que conoce a su proveedor. Ningun tipo de `websockets` ni
de `httpx2` cruza hacia fuera.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote, urlencode

import httpx2
import websockets
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import ConnectionClosed, InvalidHandshake, InvalidStatus

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

__all__ = ["Connector", "WireEndpoint", "WireTransportFactory"]

#: Quien abre un WebSocket. Por omision, `websockets.connect`; las pruebas
#: inyectan otro que contesta sin tocar la red.
type Connector = Callable[..., Awaitable[ClientConnection]]

#: El registro que recibe `websockets`: no propaga y no escribe, a ningun nivel.
_SILENCIO = logging.getLogger("untangle.providers.adapters.wire.silenced")
_SILENCIO.propagate = False
_SILENCIO.addHandler(logging.NullHandler())
_SILENCIO.setLevel(logging.CRITICAL + 1)

#: El mensaje mas grande que se acepta del proveedor. Un trozo de audio de
#: Cartesia en base64 ronda los 20 KB; un mega deja margen sin permitir que un
#: proveedor averiado llene la memoria del proceso.
_MENSAJE_MAXIMO_BYTES = 1_048_576


@dataclass(frozen=True)
class WireEndpoint:
    """Donde vive un proveedor de voz y como se le presenta la credencial."""

    websocket_base: str
    http_base: str
    #: La cabecera que lleva la credencial, y lo que va delante del valor.
    auth_header: str
    auth_prefix: str = ""
    #: Cabeceras fijas que la API exige en cada peticion (la version, en Cartesia).
    fixed_headers: Mapping[str, str] = field(default_factory=dict)


def _url(base: str, request: SpeechRequest) -> str:
    # Un valor que es tupla va como el mismo parametro repetido. El espacio sale como %20 y
    # no como `+` (el valor por omision de `urlencode`): una frase de varias palabras es un
    # solo termino, y `%20` lo lee igual cualquier servidor.
    consulta = (
        f"?{urlencode(dict(request.query), doseq=True, quote_via=quote)}" if request.query else ""
    )
    return f"{base}{request.path}{consulta}"


def _decodificar(crudo: bytes | bytearray | str) -> Mapping[str, object]:
    """Un cuerpo de error como mapa, o vacio si no lo es. No se registra nunca."""
    try:
        cargado: Any = json.loads(crudo)
    except ValueError:
        return {}
    return cargado if isinstance(cargado, dict) else {}


class _Channel(DuplexChannel):
    """Un WebSocket abierto, con los fallos de la biblioteca ya traducidos."""

    def __init__(self, conexion: ClientConnection) -> None:
        self._conexion = conexion

    async def send_bytes(self, data: bytes) -> None:
        try:
            await self._conexion.send(data)
        except ConnectionClosed as cierre:
            raise WireClosedError(cierre.rcvd.code if cierre.rcvd else None) from None

    async def send_text(self, text: str) -> None:
        try:
            await self._conexion.send(text)
        except ConnectionClosed as cierre:
            raise WireClosedError(cierre.rcvd.code if cierre.rcvd else None) from None

    async def receive(self, *, timeout_s: float) -> WireMessage | None:
        try:
            mensaje = await asyncio.wait_for(self._conexion.recv(), timeout=timeout_s)
        except TimeoutError:
            return None
        except ConnectionClosed as cierre:
            raise WireClosedError(cierre.rcvd.code if cierre.rcvd else None) from None
        if isinstance(mensaje, str):
            return WireMessage(text=mensaje)
        return WireMessage(data=bytes(mensaje))


class _Stream(ByteStream):
    """Una respuesta HTTP que ya dijo que si, leida a trozos."""

    def __init__(self, respuesta: httpx2.Response) -> None:
        self._respuesta = respuesta

    @property
    def content_type(self) -> str:
        return self._respuesta.headers.get("content-type", "")

    def header(self, name: str) -> str | None:
        return self._respuesta.headers.get(name)

    async def chunks(self) -> AsyncIterator[bytes]:
        try:
            async for trozo in self._respuesta.aiter_bytes():
                if trozo:
                    yield trozo
        except httpx2.TimeoutException as fallo:
            raise TransportError(type(fallo).__name__, timed_out=True) from None
        except httpx2.HTTPError as fallo:
            raise TransportError(type(fallo).__name__, timed_out=False) from None


class _WireTransport(SpeechTransport):
    """Un cliente de voz ya construido, con su credencial dentro y sin forma de sacarla."""

    def __init__(
        self,
        *,
        api_key: str,
        use: Use,
        endpoint: WireEndpoint,
        network: httpx2.AsyncBaseTransport | None,
        connector: Connector,
    ) -> None:
        self._use = use
        self._endpoint = endpoint
        self._network = network
        self._connector = connector
        # La clave vive solo aqui dentro, en las cabeceras. No es un atributo
        # propio con nombre de clave: lo que no se nombra no se imprime por error.
        self._cabeceras: dict[str, str] = {
            **dict(endpoint.fixed_headers),
            endpoint.auth_header: f"{endpoint.auth_prefix}{api_key}",
        }

    def __repr__(self) -> str:
        """Nombra el uso y la raiz. Nunca la clave ni las cabeceras que la llevan."""
        return f"_WireTransport(use={self._use.value}, base={self._endpoint.http_base})"

    @asynccontextmanager
    async def open_duplex(self, request: SpeechRequest) -> AsyncIterator[DuplexChannel]:
        conexion = await self._conectar(request)
        try:
            yield _Channel(conexion)
        finally:
            await conexion.close()

    async def _conectar(self, request: SpeechRequest) -> ClientConnection:
        """Abre el WebSocket. Lo que falle **aqui** es de la conexion, no del flujo."""
        try:
            return await self._connector(
                _url(self._endpoint.websocket_base, request),
                additional_headers=self._cabeceras,
                open_timeout=request.connect_timeout_ms / 1000,
                max_size=_MENSAJE_MAXIMO_BYTES,
                logger=_SILENCIO,
                user_agent_header=None,
            )
        except InvalidStatus as rechazo:
            respuesta = rechazo.response
            raise WireRejectedError(respuesta.status_code, _decodificar(respuesta.body)) from None
        except TimeoutError as fallo:
            raise TransportError(type(fallo).__name__, timed_out=True) from None
        except (OSError, InvalidHandshake) as fallo:
            raise TransportError(type(fallo).__name__, timed_out=False) from None

    @asynccontextmanager
    async def stream_post(self, request: SpeechRequest) -> AsyncIterator[ByteStream]:
        tiempos = httpx2.Timeout(
            connect=request.connect_timeout_ms / 1000,
            read=request.read_timeout_ms / 1000,
            write=request.read_timeout_ms / 1000,
            pool=request.connect_timeout_ms / 1000,
        )
        async with httpx2.AsyncClient(
            headers=self._cabeceras, timeout=tiempos, transport=self._network
        ) as cliente:
            peticion = cliente.build_request(
                "POST",
                _url(self._endpoint.http_base, request),
                json=dict(request.body or {}),
            )
            respuesta = await self._enviar(cliente, peticion)
            try:
                if not respuesta.is_success:
                    cuerpo = await respuesta.aread()
                    raise WireRejectedError(respuesta.status_code, _decodificar(cuerpo))
                yield _Stream(respuesta)
            finally:
                await respuesta.aclose()

    @staticmethod
    async def _enviar(cliente: httpx2.AsyncClient, peticion: httpx2.Request) -> httpx2.Response:
        try:
            return await cliente.send(peticion, stream=True)
        except httpx2.TimeoutException as fallo:
            raise TransportError(type(fallo).__name__, timed_out=True) from None
        except httpx2.HTTPError as fallo:
            raise TransportError(type(fallo).__name__, timed_out=False) from None

    async def get_json(self, request: SpeechRequest) -> tuple[int, Mapping[str, object]]:
        tiempos = httpx2.Timeout(
            connect=request.connect_timeout_ms / 1000,
            read=request.read_timeout_ms / 1000,
            write=request.read_timeout_ms / 1000,
            pool=request.connect_timeout_ms / 1000,
        )
        async with httpx2.AsyncClient(
            headers=self._cabeceras, timeout=tiempos, transport=self._network
        ) as cliente:
            try:
                respuesta = await cliente.get(_url(self._endpoint.http_base, request))
            except httpx2.TimeoutException as fallo:
                raise TransportError(type(fallo).__name__, timed_out=True) from None
            except httpx2.HTTPError as fallo:
                raise TransportError(type(fallo).__name__, timed_out=False) from None
            return respuesta.status_code, _decodificar(respuesta.content)


class WireTransportFactory:
    """Construye el transporte de un proveedor de voz. **Solo `SpeechClients` la llama.**

    `network` y `connector` son **costuras de prueba declaradas**, las mismas que
    tiene el transporte de Gemini: por omision son la pila de red y
    `websockets.connect`, y las pruebas inyectan otras que contestan sin tocar la
    red y sin clave. Lo que cambia es quien contesta, no como se arma la peticion
    ni por donde viaja la credencial.
    """

    def __init__(
        self,
        endpoint: WireEndpoint,
        *,
        network: httpx2.AsyncBaseTransport | None = None,
        connector: Connector | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._network = network
        self._connector: Connector = connector if connector is not None else websockets.connect

    def create(self, *, api_key: str, use: Use) -> SpeechTransport:
        return _WireTransport(
            api_key=api_key,
            use=use,
            endpoint=self._endpoint,
            network=self._network,
            connector=self._connector,
        )
