"""Un Cartesia de mentira que **mantiene el canal abierto** entre una frase y la siguiente.

El reproductor de `replay.py` sirve una respuesta grabada por peticion: una peticion, un
canal. La sesion de una llamada hace lo contrario --muchas frases por el mismo canal--, y lo
que se prueba es justo eso: cuantas conexiones se abren, que el audio de una frase no se
mezcle con el de otra y que pasa cuando una frase se abandona o el canal se cae.

Se comporta como lo documenta Cartesia: cada mensaje de generacion trae su `context_id`, y
bajan `chunk` con ese identificador y un `done` al final. **Una generacion que ya empezo no
se detiene** (el `cancel` de Cartesia solo para las que aun no arrancan): lo que le quedaba
por mandar a una frase abandonada sigue llegando por el canal. Por eso el guion de cada
frase se pone entero en la cola al recibir el mensaje.

El audio de cada frase es el numero de la frase repetido (`bytes([n]) * 960`), para que una
prueba sepa de que frase es cada trozo que oye.
"""

from __future__ import annotations

import asyncio
import base64
import json
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from untangle.base import ProviderName, Use
from untangle.providers.factory import SpeechClients
from untangle.providers.speech_wire import (
    DuplexChannel,
    SpeechRequest,
    SpeechTransport,
    WireClosedError,
    WireMessage,
)
from untangle.settings import Settings

#: Lo que ocupa cada trozo de audio de prueba: 480 muestras de 16 bits, 20 ms.
BYTES_POR_TROZO = 960

_SE_CAE = object()


def audio_de_la_frase(numero: int) -> bytes:
    """El trozo de audio de la frase `numero` (la 1 es la primera que recibe el servidor)."""
    return bytes([numero]) * BYTES_POR_TROZO


@dataclass
class ServidorFalso:
    """Lo que el proveedor de mentira hace y lo que vio."""

    trozos_por_frase: int = 3
    #: Frase (numero global, desde 1) a la que el proveedor contesta un `error` con ese codigo.
    error_en: dict[int, int] = field(default_factory=dict)
    #: Frase a la que el canal se le cae despues de tantos trozos, con codigo 1011.
    cae_tras: dict[int, int] = field(default_factory=dict)
    aperturas: int = 0
    canales: list[CanalFalso] = field(default_factory=list)
    recibidos: list[dict[str, Any]] = field(default_factory=list)
    #: Si la apertura de un canal debe fallar con esta excepcion.
    falla_al_abrir: BaseException | None = None

    def clientes(self) -> SpeechClients:
        """Los clientes de voz de verdad, con este servidor como transporte de Cartesia."""
        ajustes = Settings(
            voice_deepgram_api_key=secrets.token_urlsafe(24),
            voice_cartesia_api_key=secrets.token_urlsafe(24),
        )
        return SpeechClients(
            settings=ajustes, transports={ProviderName.CARTESIA: FabricaFalsa(self)}
        )


class CanalFalso(DuplexChannel):
    def __init__(self, servidor: ServidorFalso) -> None:
        self._servidor = servidor
        self._cola: asyncio.Queue[object] = asyncio.Queue()
        self.cerrado = False
        self.cierres = 0
        self._codigo: int | None = None

    def cerrar_desde_el_servidor(self, codigo: int = 1001) -> None:
        """El proveedor cierra el canal (por ocio, por ejemplo): lo que siga lo ve cerrado."""
        self.cerrado = True
        self._codigo = codigo

    async def send_bytes(self, data: bytes) -> None:
        msg = "Cartesia no recibe audio de entrada"
        raise AssertionError(msg)

    async def send_text(self, text: str) -> None:
        await asyncio.sleep(0)
        if self.cerrado:
            raise WireClosedError(self._codigo)
        mensaje = json.loads(text)
        self._servidor.recibidos.append(mensaje)
        numero = len(self._servidor.recibidos)
        contexto = mensaje["context_id"]
        if numero in self._servidor.error_en:
            self._poner({"type": "error", "status_code": self._servidor.error_en[numero]}, contexto)
            return
        trozos = self._servidor.trozos_por_frase
        corte = self._servidor.cae_tras.get(numero)
        for i in range(trozos if corte is None else corte):
            audio = base64.b64encode(audio_de_la_frase(numero)).decode()
            self._poner({"type": "chunk", "data": audio, "i": i}, contexto)
        if corte is not None:
            self._cola.put_nowait(_SE_CAE)
            return
        self._poner({"type": "done", "done": True, "status_code": 206}, contexto)

    def _poner(self, marco: dict[str, Any], contexto: str) -> None:
        self._cola.put_nowait(json.dumps({**marco, "context_id": contexto}))

    async def receive(self, *, timeout_s: float) -> WireMessage | None:
        if self.cerrado and self._cola.empty():
            raise WireClosedError(self._codigo)
        try:
            item = await asyncio.wait_for(self._cola.get(), timeout=timeout_s)
        except TimeoutError:
            return None
        if item is _SE_CAE:
            self.cerrado = True
            self._codigo = 1011
            raise WireClosedError(1011)
        assert isinstance(item, str)
        return WireMessage(text=item)


class TransporteFalso(SpeechTransport):
    def __init__(self, servidor: ServidorFalso) -> None:
        self._servidor = servidor

    @asynccontextmanager
    async def open_duplex(self, request: SpeechRequest) -> AsyncIterator[DuplexChannel]:
        del request
        if self._servidor.falla_al_abrir is not None:
            raise self._servidor.falla_al_abrir
        self._servidor.aperturas += 1
        canal = CanalFalso(self._servidor)
        self._servidor.canales.append(canal)
        try:
            yield canal
        finally:
            canal.cerrado = True
            canal.cierres += 1

    def stream_post(self, request: SpeechRequest) -> Any:
        del request
        raise AssertionError("Cartesia habla por WebSocket")

    async def get_json(self, request: SpeechRequest) -> Any:
        del request
        raise AssertionError("la sesion no consulta el catalogo")


class FabricaFalsa:
    def __init__(self, servidor: ServidorFalso) -> None:
        self._servidor = servidor

    def create(self, *, api_key: str, use: Use) -> SpeechTransport:
        del api_key, use
        return TransporteFalso(self._servidor)


__all__ = [
    "BYTES_POR_TROZO",
    "CanalFalso",
    "FabricaFalsa",
    "ServidorFalso",
    "TransporteFalso",
    "audio_de_la_frase",
]
