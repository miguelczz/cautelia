"""El protocolo de Cartesia, en un solo archivo: el mensaje que sube y los que bajan.

La sintesis va por WebSocket en `tts/websocket` (ADR-008): sube **un** mensaje
JSON con el texto, la voz, el idioma y el formato de salida, y bajan mensajes
JSON de tres tipos --`chunk` con un trozo de audio en base64, `done` cuando
termino y `error` si fallo--, todos con el `context_id` de la peticion.

La credencial viaja en la cabecera `X-API-Key` del apreton y **nunca en la URL**:
se comprobo el 2026-09-21 que el WebSocket la acepta asi (apreton 101), que es
lo que permite no usar la forma con la clave en la cadena de consulta.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Collection, Mapping

from untangle.providers.adapters.wire import WireEndpoint
from untangle.providers.ports import SPEECH_AUDIO, VoiceRef

__all__ = [
    "API_VERSION",
    "ENDPOINT",
    "TTS_PATH",
    "Frame",
    "InvalidMessageError",
    "generation_message",
    "parse_frame",
    "voice_path",
]

#: La version de la API con la que se midio en el experimento 1. Anclada como un
#: modelo: una version nueva puede cambiar la forma de los mensajes, y eso tiene
#: que verse en un diff y pasar por la prueba de contrato.
API_VERSION = "2024-06-10"

ENDPOINT = WireEndpoint(
    websocket_base="wss://api.cartesia.ai/",
    http_base="https://api.cartesia.ai/",
    auth_header="X-API-Key",
    fixed_headers={"Cartesia-Version": API_VERSION},
)

TTS_PATH = "tts/websocket"


def voice_path(voice_id: str) -> str:
    """La ficha publica de una voz. Consultarla no cuesta."""
    return f"voices/{voice_id}"


class InvalidMessageError(ValueError):
    """Un mensaje sin la forma del contrato. Se traduce a `invalid_response`."""


def generation_message(text: str, *, voice: VoiceRef, context_id: str) -> str:
    """El unico mensaje que sube: todo el texto de una vez, sin continuacion.

    El formato de salida es el unico del aplicativo (BR4.1). `continue: false`
    porque el adaptador sintetiza frases completas: U16 le entrega cada frase ya
    armada por el catalogo y la guardia de salida.
    """
    return json.dumps(
        {
            "model_id": voice.model,
            "transcript": text,
            "voice": {"mode": "id", "id": voice.voice_id},
            "language": voice.language,
            "context_id": context_id,
            "output_format": {
                "container": "raw",
                "encoding": SPEECH_AUDIO.encoding.value,
                "sample_rate": SPEECH_AUDIO.sample_rate_hz,
            },
            "continue": False,
        }
    )


class Frame:
    """Un mensaje que bajo, ya leido. `audio` solo en `chunk`; `status_code` en `error`."""

    __slots__ = ("audio", "kind", "status_code")

    def __init__(self, kind: str, *, audio: bytes = b"", status_code: int | None = None) -> None:
        self.kind = kind
        self.audio = audio
        self.status_code = status_code


def _estado(message: Mapping[str, object]) -> int | None:
    valor = message.get("status_code")
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def parse_frame(text: str, *, context_id: str, earlier: Collection[str] = ()) -> Frame:
    """Un mensaje de Cartesia. Lo que no es de esta peticion es un mensaje invalido.

    `earlier` son los `context_id` de frases ya terminadas **por el mismo canal**:
    en una conexion que sigue abierta, Cartesia puede mandar tarde algo de una
    frase anterior (un `flush_done`, un `timestamps`) y eso no es de la frase en
    curso ni un fallo suyo; se ignora. Un identificador que no es ni el de ahora
    ni uno de estos sigue siendo un mensaje invalido.

    El campo `error` **no se lee**: es prosa del proveedor. El tipo del error sale
    de `status_code`, que es un numero.
    """
    try:
        datos = json.loads(text)
    except ValueError:
        msg = "el mensaje no es JSON"
        raise InvalidMessageError(msg) from None
    if not isinstance(datos, dict):
        msg = "el mensaje no es un objeto"
        raise InvalidMessageError(msg)

    tipo = datos.get("type")
    ajeno = datos.get("context_id")
    if isinstance(ajeno, str) and ajeno != context_id and ajeno in earlier:
        return Frame("other")
    if ajeno not in (None, context_id):
        msg = "el mensaje trae el 'context_id' de otra peticion"
        raise InvalidMessageError(msg)
    if tipo == "error":
        return Frame("error", status_code=_estado(datos))
    if tipo == "done":
        return Frame("done")
    if tipo == "chunk":
        crudo = datos.get("data")
        if not isinstance(crudo, str):
            msg = "el trozo no trae 'data'"
            raise InvalidMessageError(msg)
        try:
            return Frame("chunk", audio=base64.b64decode(crudo, validate=True))
        except (binascii.Error, ValueError):
            msg = "el trozo trae 'data' que no es base64"
            raise InvalidMessageError(msg) from None
    # `timestamps`, `flush_done` y los que Cartesia agregue: no son audio.
    return Frame("other")
