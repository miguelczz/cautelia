"""Las respuestas grabadas de la voz: como se capturan y que se guarda (BR6.1, CG-U15-3).

`mise run voice:contract-live -- --record` corre las pruebas de contrato contra
Deepgram y Cartesia de verdad, **por el camino del aplicativo**, con este
grabador envuelto alrededor del transporte real. Lo que el proveedor contesto
queda en `app/backend/tests/unit/voice_providers/recorded/`, un archivo por
prueba, y `test:u15` lo reproduce en cada entrega sin salir a la red.

## Que se guarda tal cual

**La estructura exacta de cada mensaje**: el JSON de cada marco, en su orden, con
sus claves y sus tipos; el codigo de estado y el cuerpo de un rechazo; el codigo
de cierre del canal; y las cabeceras de la respuesta que importan al contrato
(`_CABECERAS_DEL_CONTRATO`). Es lo que la prueba de contrato comprueba, asi que
no se toca.

## Que no se guarda, y que va en su lugar

- **Ningun audio.** Cada carga de audio --un trozo binario de Aura-2 o el `data`
  en base64 de un trozo de Cartesia-- se sustituye por **20 ms de silencio PCM**
  en el formato unico, en la misma codificacion que usa el proveedor. De los
  trozos de audio se guardan los tres primeros, y el archivo dice cuantos se
  omitieron. Lo que se oyo no vive en el repositorio: la voz de Catalina es de
  Cartesia, y el audio de entrada es sintetizado en memoria y se descarta.
- **Ninguna credencial ni identificador de cuenta.** El grabador envuelve el
  transporte **por dentro** de la fabrica: ve lo que el adaptador manda y lo que
  el proveedor contesta, nunca las cabeceras de la peticion, que es donde viaja
  la clave. Y las claves de los cuerpos que identifican la cuenta o la peticion
  (`_CLAVES_DE_CUENTA`) se sustituyen por una marca.
"""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from untangle import paths
from untangle.base import ProviderName, Use
from untangle.providers.ports import SPEECH_AUDIO
from untangle.providers.speech_wire import (
    ByteStream,
    DuplexChannel,
    SpeechRequest,
    SpeechTransport,
    SpeechTransportFactory,
    WireClosedError,
    WireMessage,
    WireRejectedError,
)

__all__ = [
    "PLACEHOLDER_AUDIO",
    "PLACEHOLDER_AUDIO_B64",
    "RECORDED_DIR",
    "Exchange",
    "Recorder",
    "RecordingTransportFactory",
    "about_lines",
    "sanitize",
]

#: Donde viven las respuestas grabadas, junto a las pruebas que las reproducen.
RECORDED_DIR = paths.repo_root() / "app/backend/tests/unit/voice_providers/recorded"

#: 20 ms de silencio en el formato unico: 24 kHz, 16 bits, mono.
PLACEHOLDER_AUDIO = bytes(SPEECH_AUDIO.bytes_per_second // 50)
PLACEHOLDER_AUDIO_B64 = base64.b64encode(PLACEHOLDER_AUDIO).decode("ascii")

#: Cuantos trozos de audio se guardan por prueba. Tres bastan para probar el
#: formato, el orden y la reunion en muestras enteras.
_TROZOS_GUARDADOS = 3

#: Las claves de un cuerpo que identifican la cuenta o la peticion. Se sustituyen
#: por `_MARCA`, en cualquier nivel del JSON.
_CLAVES_DE_CUENTA = frozenset(
    {"request_id", "project_id", "account_id", "organization_id", "sha256", "transaction_key"}
)
_MARCA = "retirado-al-grabar"

#: Las cabeceras de una respuesta HTTP que el contrato mira. Ninguna otra se
#: guarda: las demas identifican la peticion o la cuenta, o no dicen nada.
_CABECERAS_DEL_CONTRATO = ("content-type", "dg-char-count", "dg-model-name")


def sanitize(valor: Any) -> Any:
    """El JSON con las claves de cuenta sustituidas y el audio de Cartesia en silencio."""
    if isinstance(valor, Mapping):
        limpio = {
            clave: (_MARCA if clave in _CLAVES_DE_CUENTA else sanitize(dato))
            for clave, dato in valor.items()
        }
        if limpio.get("type") == "chunk" and isinstance(limpio.get("data"), str):
            limpio["data"] = PLACEHOLDER_AUDIO_B64
        return limpio
    if isinstance(valor, list):
        return [sanitize(dato) for dato in valor]
    return valor


def about_lines(provenance: str) -> list[str]:
    """La cabecera de cada archivo grabado: que es y que no contiene."""
    lineas = [
        "Respuesta grabada de un proveedor de voz, para la prueba de contrato de U15 (BR6.1).",
        "La estructura de cada mensaje es la exacta del proveedor: claves, tipos y orden.",
        "Todo audio es un marcador: 20 ms de silencio PCM de 16 bits, mono, a 24 kHz, en la",
        "misma codificacion que usa el proveedor (binario o base64). Ninguna voz vive aqui.",
        "No lleva clave, ni cabecera de autorizacion, ni identificador de cuenta.",
    ]
    if provenance == "captured":
        lineas.append(
            "Capturada una vez con `mise run voice:contract-live -- --record` (CG-U15-3)."
        )
    else:
        lineas.append(
            "DOCUMENTADA, NO CAPTURADA: armada a mano con la forma de error que documenta el "
            "proveedor, porque provocarla de verdad cuesta saldo o no se puede a voluntad."
        )
    return lineas


@dataclass
class Exchange:
    """Lo que una prueba intercambio con el proveedor, ya saneado."""

    probe: str
    provider: ProviderName
    model: str
    kind: str = ""
    request: dict[str, Any] = field(default_factory=dict)
    sent: list[dict[str, Any]] = field(default_factory=list)
    received: list[dict[str, Any]] = field(default_factory=list)
    rejected: dict[str, Any] | None = None
    closed: dict[str, Any] | None = None
    response: dict[str, Any] | None = None
    audio_frames_seen: int = 0
    audio_frames_omitted: int = 0

    def audio_frame(self) -> bool:
        """Cuenta un trozo de audio y dice si se guarda o se omite."""
        self.audio_frames_seen += 1
        if self.audio_frames_seen <= _TROZOS_GUARDADOS:
            return True
        self.audio_frames_omitted += 1
        return False

    def as_fixture(self) -> dict[str, Any]:
        return {
            "_about": about_lines("captured"),
            "provenance": "captured",
            "captured_on": date.today().isoformat(),
            "probe": self.probe,
            "provider": self.provider.value,
            "model": self.model,
            "kind": self.kind,
            "request": self.request,
            "sent": self.sent,
            "rejected": self.rejected,
            "response": self.response,
            "received": self.received,
            "closed": self.closed,
            "audio_frames_omitted": self.audio_frames_omitted,
        }


class Recorder:
    """El cuaderno de la captura: una entrada por prueba, en el orden en que corrieron."""

    def __init__(self) -> None:
        self.exchanges: list[Exchange] = []
        self._actual: Exchange | None = None

    def begin(self, probe: str, *, provider: ProviderName, model: str) -> Exchange:
        self._actual = Exchange(probe=probe, provider=provider, model=model)
        self.exchanges.append(self._actual)
        return self._actual

    @property
    def current(self) -> Exchange:
        if self._actual is None:
            msg = "el grabador recibio trafico sin una prueba abierta"
            raise RuntimeError(msg)
        return self._actual

    def write(self, folder: Path = RECORDED_DIR) -> list[Path]:
        folder.mkdir(parents=True, exist_ok=True)
        escritos: list[Path] = []
        for entrada in self.exchanges:
            destino = folder / f"{entrada.probe}.json"
            destino.write_text(
                json.dumps(entrada.as_fixture(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            escritos.append(destino)
        return escritos


def _texto(texto: str) -> dict[str, Any]:
    try:
        return {"text": sanitize(json.loads(texto))}
    except ValueError:
        return {"text_raw": texto}


class _RecordingChannel(DuplexChannel):
    def __init__(self, canal: DuplexChannel, entrada: Exchange) -> None:
        self._canal = canal
        self._entrada = entrada

    async def send_bytes(self, data: bytes) -> None:
        await self._canal.send_bytes(data)
        # El audio que sube no se guarda: se cuenta, junto al envio anterior.
        ultimo = self._entrada.sent[-1] if self._entrada.sent else None
        if ultimo is not None and "binary_bytes" in ultimo:
            ultimo["binary_bytes"] += len(data)
        else:
            self._entrada.sent.append({"binary_bytes": len(data)})

    async def send_text(self, text: str) -> None:
        await self._canal.send_text(text)
        self._entrada.sent.append(_texto(text))

    async def receive(self, *, timeout_s: float) -> WireMessage | None:
        try:
            mensaje = await self._canal.receive(timeout_s=timeout_s)
        except WireClosedError as cierre:
            self._entrada.closed = {"code": cierre.code}
            raise
        if mensaje is None:
            return None
        if mensaje.text is not None:
            registro = _texto(mensaje.text)
            es_audio = registro.get("text", {}).get("type") == "chunk"
            if not es_audio or self._entrada.audio_frame():
                self._entrada.received.append(registro)
        elif self._entrada.audio_frame():
            self._entrada.received.append({"binary_b64": PLACEHOLDER_AUDIO_B64})
        return mensaje


class _RecordingStream(ByteStream):
    def __init__(self, flujo: ByteStream, entrada: Exchange) -> None:
        self._flujo = flujo
        self._entrada = entrada

    @property
    def content_type(self) -> str:
        return self._flujo.content_type

    def header(self, name: str) -> str | None:
        return self._flujo.header(name)

    async def chunks(self) -> AsyncIterator[bytes]:
        async for trozo in self._flujo.chunks():
            if self._entrada.audio_frame():
                self._entrada.received.append({"binary_b64": PLACEHOLDER_AUDIO_B64})
            yield trozo


class _RecordingTransport(SpeechTransport):
    def __init__(self, inner: SpeechTransport, recorder: Recorder) -> None:
        self._inner = inner
        self._recorder = recorder

    @asynccontextmanager
    async def open_duplex(self, request: SpeechRequest) -> AsyncIterator[DuplexChannel]:
        entrada = self._recorder.current
        entrada.kind = "duplex"
        entrada.request = {"path": request.path, "query": dict(request.query)}
        try:
            async with self._inner.open_duplex(request) as canal:
                yield _RecordingChannel(canal, entrada)
        except WireRejectedError as rechazo:
            entrada.rejected = {"status_code": rechazo.status_code, "body": sanitize(rechazo.body)}
            raise

    @asynccontextmanager
    async def stream_post(self, request: SpeechRequest) -> AsyncIterator[ByteStream]:
        entrada = self._recorder.current
        entrada.kind = "stream_post"
        entrada.request = {
            "path": request.path,
            "query": dict(request.query),
            "body": sanitize(dict(request.body or {})),
        }
        try:
            async with self._inner.stream_post(request) as flujo:
                entrada.response = {
                    "headers": {
                        nombre: valor
                        for nombre in _CABECERAS_DEL_CONTRATO
                        if (valor := flujo.header(nombre)) is not None
                    }
                }
                yield _RecordingStream(flujo, entrada)
        except WireRejectedError as rechazo:
            entrada.rejected = {"status_code": rechazo.status_code, "body": sanitize(rechazo.body)}
            raise

    async def get_json(self, request: SpeechRequest) -> tuple[int, Mapping[str, object]]:
        # Las consultas de catalogo no son parte del contrato grabado.
        return await self._inner.get_json(request)


class RecordingTransportFactory(SpeechTransportFactory):
    """Envuelve la fabrica real. Ve lo que pasa por el transporte, nunca la clave."""

    def __init__(self, inner: SpeechTransportFactory, recorder: Recorder) -> None:
        self._inner = inner
        self._recorder = recorder

    def create(self, *, api_key: str, use: Use) -> SpeechTransport:
        return _RecordingTransport(self._inner.create(api_key=api_key, use=use), self._recorder)
