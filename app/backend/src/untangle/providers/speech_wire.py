"""La forma de la frontera de voz, sin decir con que biblioteca se cruza (U15).

Es a la voz lo que `transport.py` es a Gemini. Alli basta una peticion y una
respuesta; aqui hacen falta **dos formas de transmitir**, porque los
proveedores de voz hablan en streaming:

- **Un canal de ida y vuelta** (`DuplexChannel`), que es un WebSocket: la
  transcripcion de Deepgram --audio que sube, parciales que bajan-- y la
  sintesis de Cartesia --un mensaje que sube, trozos de audio que bajan--.
- **Una respuesta que llega a trozos** (`ByteStream`), que es HTTP en streaming:
  la sintesis de Aura-2.

## Por que una pieza en medio, igual que en Gemini

Porque la clave no puede estar en la mano del adaptador. Entra en
`SpeechTransportFactory.create` y se queda **dentro** del transporte; el
adaptador recibe un `SpeechCaller` --"abre esto con el cliente de este proveedor
y de este uso"-- y no tiene ni argumento ni atributo donde una clave pueda
estar. Y porque las pruebas de `test:u15` sustituyen el transporte por uno que
reproduce la respuesta grabada: lo que se dobla es lo que contesta el
proveedor, no el adaptador.

## Ninguna biblioteca de red aqui dentro

La implementacion que habla de verdad vive en `adapters/wire.py`, dentro del
paquete de adaptadores, que es el unico sitio donde se puede importar un cliente
de red (BR1.1). Este archivo declara la forma y no la cruza.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from pydantic import Field

from untangle.base import Frozen, ProviderName, Use

__all__ = [
    "ByteStream",
    "DuplexChannel",
    "SpeechCaller",
    "SpeechRequest",
    "SpeechTransport",
    "SpeechTransportFactory",
    "WireClosedError",
    "WireMessage",
    "WireRejectedError",
]


class SpeechRequest(Frozen):
    """Una peticion de voz, ya armada por su adaptador.

    La ruta y la consulta **nunca** llevan la clave: la credencial viaja en
    cabecera, porque una URL acaba en un registro de acceso, en un mensaje de
    error y en una traza.
    """

    #: Relativa a la raiz del proveedor, sin barra inicial.
    path: str = Field(min_length=1)
    #: Un valor suelto, o una tupla de valores para un parametro que el proveedor lee
    #: **repetido** (`?keyterm=uno&keyterm=dos`): un diccionario no admite claves repetidas.
    query: Mapping[str, str | tuple[str, ...]] = Field(default_factory=dict)
    #: El cuerpo JSON de una peticion HTTP. Los canales de ida y vuelta no lo
    #: usan: su primer mensaje lo manda el adaptador por el canal.
    body: Mapping[str, object] | None = None
    connect_timeout_ms: int = Field(ge=1)
    read_timeout_ms: int = Field(ge=1)


@dataclass(frozen=True)
class WireMessage:
    """Un mensaje del canal: texto (JSON del proveedor) o bytes (audio)."""

    text: str | None = None
    data: bytes | None = None


class WireRejectedError(Exception):
    """El proveedor dijo que no **antes** de abrir el flujo: un codigo de estado.

    Lleva el codigo y el cuerpo decodificado, que solo lee la traduccion de
    errores de su adaptador --y de el solo las claves que nombran el tipo de
    error--. **Su representacion no incluye el cuerpo**: un mensaje de error
    acaba en logs y en pantallas, y el cuerpo es prosa del proveedor que nadie
    reviso.
    """

    def __init__(self, status_code: int, body: Mapping[str, object] | None = None) -> None:
        self.status_code = status_code
        self.body: Mapping[str, object] = body or {}
        super().__init__(f"el proveedor rechazo la conexion con el codigo {status_code}")


class WireClosedError(Exception):
    """El canal se cerro. `code` es el codigo de cierre del WebSocket, si llego."""

    def __init__(self, code: int | None) -> None:
        self.code = code
        super().__init__(f"el canal se cerro con el codigo {code}")


class DuplexChannel(Protocol):
    """Un canal abierto de ida y vuelta. Lo cierra quien lo abrio."""

    async def send_bytes(self, data: bytes) -> None: ...

    async def send_text(self, text: str) -> None: ...

    async def receive(self, *, timeout_s: float) -> WireMessage | None:
        """El siguiente mensaje, o `None` si no llego ninguno dentro del tiempo.

        `None` y no una excepcion: esperar un poco sin que llegue nada es la
        conducta normal de una transcripcion mientras la persona habla, y el
        adaptador es quien decide cuando esa espera ya es un tiempo agotado.
        """
        ...


class ByteStream(Protocol):
    """Una respuesta HTTP que ya dijo que si y llega a trozos."""

    @property
    def content_type(self) -> str: ...

    def header(self, name: str) -> str | None:
        """Una cabecera de la respuesta, por nombre. Nunca la de la peticion."""
        ...

    def chunks(self) -> AsyncIterator[bytes]: ...


class SpeechTransport(Protocol):
    """Un cliente ya construido, con su credencial dentro y sin forma de sacarla."""

    def open_duplex(self, request: SpeechRequest) -> AbstractAsyncContextManager[DuplexChannel]: ...

    def stream_post(self, request: SpeechRequest) -> AbstractAsyncContextManager[ByteStream]: ...

    async def get_json(self, request: SpeechRequest) -> tuple[int, Mapping[str, object]]:
        """Una consulta que no cuesta --la lista de voces--. Solo la usan los comandos a mano."""
        ...


class SpeechTransportFactory(Protocol):
    """Construye el transporte de un proveedor con una clave. **Solo la fabrica lo llama.**"""

    def create(self, *, api_key: str, use: Use) -> SpeechTransport: ...


class SpeechCaller(Protocol):
    """ "Abre esto con el cliente de este proveedor y de este uso". Lo implementa la fabrica.

    Es lo que recibe el adaptador. No tiene metodo para obtener el cliente ni la
    clave.
    """

    def open_duplex(
        self, request: SpeechRequest, *, provider: ProviderName, use: Use
    ) -> AbstractAsyncContextManager[DuplexChannel]: ...

    def stream_post(
        self, request: SpeechRequest, *, provider: ProviderName, use: Use
    ) -> AbstractAsyncContextManager[ByteStream]: ...

    async def get_json(
        self, request: SpeechRequest, *, provider: ProviderName, use: Use
    ) -> tuple[int, Mapping[str, object]]: ...
