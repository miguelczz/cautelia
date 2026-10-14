"""El protocolo de Deepgram, en un solo archivo: rutas, consultas, mensajes y errores.

Lo que Deepgram documenta y lo que el experimento 1 midio, escrito para que la
unica forma de cambiarlo sea tocar aqui (BR1.1):

- **Transcripcion** por WebSocket en `v1/listen`: el audio sube en binario, los
  resultados bajan como JSON `Results` con `is_final`, y al terminar se manda
  `Finalize`, que fuerza el resultado de lo que ya recibio y llega marcado
  `from_finalize`. **Esa es la marca de fin, no el primer resultado final**: la
  primera version del experimento paraba en el primer final y cortaba la frase
  a la mitad, porque Deepgram entrega una frase larga en varios segmentos.
  Despues se manda `CloseStream`.
- **La senal de voz** `SpeechStarted`, que Deepgram manda con `vad_events=true` en
  cuanto detecta que alguien empieza a hablar --decimas de segundo, mientras que los
  parciales llegan una vez por segundo de audio--. Es una ayuda para saber que la
  persona retomo la frase, no un resultado: un mensaje que no se entiende se descarta y
  la escucha sigue.
- **Sintesis de respaldo** por HTTP en `v1/speak`: el texto sube en JSON y el
  audio baja a trozos, en PCM crudo con `container=none`.
- **La lista de modelos** en `v1/models`, que no cuesta: es contra la que
  `voice:contract-live` comprueba que las voces declaradas existen.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any

from untangle.base import Locale
from untangle.providers.adapters.wire import WireEndpoint
from untangle.providers.ports import (
    SPEECH_AUDIO,
    ExternalText,
    SpeechStarted,
    Transcript,
    VoiceRef,
    WordHypothesis,
)
from untangle.providers.voice_availability import SpeechModel
from untangle.tenancy.models import TranscriptionMode

__all__ = [
    "CLOSE_STREAM",
    "ENDPOINT",
    "FINALIZE",
    "LISTEN_PATH",
    "MODELS_PATH",
    "SPEAK_PATH",
    "InvalidMessageError",
    "is_pcm_audio",
    "listen_query",
    "parse_results",
    "parse_speech_started",
    "says_exhausted",
    "speak_query",
    "tts_voice_names",
]

#: Donde vive Deepgram y como se presenta la credencial: `Token <clave>` en la
#: cabecera `Authorization`, nunca en la URL.
ENDPOINT = WireEndpoint(
    websocket_base="wss://api.deepgram.com/",
    http_base="https://api.deepgram.com/",
    auth_header="Authorization",
    auth_prefix="Token ",
)

LISTEN_PATH = "v1/listen"
SPEAK_PATH = "v1/speak"
MODELS_PATH = "v1/models"

#: Fuerza el resultado final de lo recibido. Su respuesta llega con `from_finalize`.
FINALIZE = json.dumps({"type": "Finalize"})
#: Cierra el flujo de forma ordenada, despues de la respuesta forzada.
CLOSE_STREAM = json.dumps({"type": "CloseStream"})

#: Los `err_code` que dicen "se acabo el saldo", versionados aqui. Deepgram
#: contesta 402 cuando al proyecto no le alcanza el credito, y ese codigo ya se
#: reconoce sin mirar el cuerpo; esta lista cubre el mismo hecho dicho con otro
#: codigo de estado. **Documentado, no capturado**: agotar el saldo de verdad
#: para grabarlo costaria el saldo que protege (regla de `project.md`).
_CODIGOS_DE_AGOTAMIENTO: frozenset[str] = frozenset(
    {"INSUFFICIENT_CREDITS", "ASR_PAYMENT_REQUIRED", "PAYMENT_REQUIRED"}
)


class InvalidMessageError(ValueError):
    """Un mensaje que no tiene la forma del contrato. Se traduce a `invalid_response`.

    Su texto nombra **la clave** que falta o sobra, nunca el valor: el valor de un
    resultado es lo que dijo una persona.
    """


def listen_query(model: SpeechModel, language: Locale) -> dict[str, str | tuple[str, ...]]:
    """La consulta de la transcripcion (ADR-007).

    En modo `multi` el idioma lo detecta el modelo en cada palabra; en modo de un
    solo idioma se le dice cual, con el codigo que la aseguradora configura para ese
    idioma de la llamada (`es-419` para `es`: espanol de Latinoamerica). El audio es el
    formato unico del aplicativo. `interim_results` pide los parciales, que U16 necesita
    para saber que la persona sigue hablando, y `vad_events` la senal de que **empezo** a
    hablar, que llega en decimas de segundo: un parcial tarda hasta un segundo de audio en
    salir.

    **`keyterm`** (2026-10-13): los terminos que el reconocedor debe esperar oir --la
    poliza, los lugares, los carros--, **un parametro por termino** y no una lista con
    separadores: Nova-3 no admite comas ni punto y coma, y los acepta sin error y sin
    hacer nada. Una frase de varias palabras es un solo termino. Sirve tambien en modo
    `multi`, con los del idioma de la llamada. Si la aseguradora no declara ninguno, el
    parametro no se manda.
    """
    consulta: dict[str, str | tuple[str, ...]] = {
        "model": model.model,
        "language": "multi"
        if model.mode is TranscriptionMode.MULTI
        else model.language_code(language),
        "encoding": "linear16",
        "sample_rate": str(SPEECH_AUDIO.sample_rate_hz),
        "channels": str(SPEECH_AUDIO.channels),
        "interim_results": "true",
        "vad_events": "true",
        # Los numeros en cifras (2026-10-09): «dos cero cero uno uno siete» llegaba en
        # palabras y la poliza no se reconocia.
        "smart_format": "true",
    }
    terminos = model.keyterms_for(language)
    if terminos:
        consulta["keyterm"] = terminos
    return consulta


def speak_query(voice: VoiceRef) -> dict[str, str]:
    """La consulta de la sintesis de respaldo, en el formato unico (BR4.1).

    En Aura-2 el identificador de la voz **es** el parametro `model`: la voz
    lleva el idioma dentro del nombre (`aura-2-celeste-es`).
    """
    return {
        "model": voice.voice_id,
        "encoding": "linear16",
        "sample_rate": str(SPEECH_AUDIO.sample_rate_hz),
        "container": "none",
    }


def is_pcm_audio(content_type: str) -> bool:
    """Si la respuesta de `v1/speak` trae audio y no un documento de error."""
    tipo = content_type.split(";", 1)[0].strip().lower()
    return tipo.startswith("audio/") or tipo == "application/octet-stream"


def says_exhausted(body: Mapping[str, object]) -> bool:
    """Si el cuerpo de un rechazo nombra un saldo agotado. Solo se lee `err_code`.

    El `err_msg` **no** se mira: es prosa del proveedor, puede cambiar sin aviso,
    y una coincidencia casual decidiria detener el trabajo.
    """
    codigo = body.get("err_code")
    return isinstance(codigo, str) and codigo.strip().upper() in _CODIGOS_DE_AGOTAMIENTO


def _idioma(valor: object) -> Locale | None:
    """`es`, `es-419` o `en-US` a uno de los dos idiomas del producto, o nada."""
    if not isinstance(valor, str):
        return None
    base = valor.split("-", 1)[0].strip().lower()
    if base == "es":
        return "es"
    if base == "en":
        return "en"
    return None


def _numero(palabra: Mapping[str, Any], clave: str, *, obligatorio: bool) -> float | None:
    valor = palabra.get(clave)
    if valor is None and not obligatorio:
        return None
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        msg = f"la palabra trae '{clave}' sin numero"
        raise InvalidMessageError(msg)
    return float(valor)


def _palabra(cruda: object) -> WordHypothesis:
    if not isinstance(cruda, Mapping):
        msg = "una palabra del resultado no es un objeto"
        raise InvalidMessageError(msg)
    texto = cruda.get("punctuated_word") or cruda.get("word")
    if not isinstance(texto, str):
        msg = "la palabra no trae 'word'"
        raise InvalidMessageError(msg)
    confianza = _numero(cruda, "confidence", obligatorio=False)
    if confianza is not None and not 0 <= confianza <= 1:
        msg = "la palabra trae 'confidence' fuera de [0, 1]"
        raise InvalidMessageError(msg)
    inicio = _numero(cruda, "start", obligatorio=True)
    fin = _numero(cruda, "end", obligatorio=True)
    return WordHypothesis(
        text=ExternalText(texto),
        start_s=inicio or 0.0,
        end_s=fin or 0.0,
        confidence=confianza,
    )


def _alternativa(message: Mapping[str, object]) -> Mapping[str, object]:
    canal = message.get("channel")
    alternativas = canal.get("alternatives") if isinstance(canal, Mapping) else None
    if not isinstance(alternativas, list) or not alternativas:
        msg = "el resultado no trae 'channel.alternatives'"
        raise InvalidMessageError(msg)
    primera = alternativas[0]
    if not isinstance(primera, Mapping) or not isinstance(primera.get("transcript"), str):
        msg = "la alternativa no trae 'transcript'"
        raise InvalidMessageError(msg)
    return primera


def parse_results(message: Mapping[str, object]) -> Transcript | None:
    """Un mensaje `Results`, como `Transcript`; `None` si no dijo nada.

    - La confianza de cada palabra **se conserva si viene y es nula si no**,
      nunca cero (BR3.1, PA-2).
    - El idioma es el que **detecto** el modelo: el de la alternativa, o el de
      sus palabras si la alternativa no lo trae. Nulo si ninguno lo dice.
    - Un resultado sin texto no se entrega: el silencio no es un parcial.
    """
    alternativa = _alternativa(message)
    texto = str(alternativa["transcript"]).strip()
    if not texto:
        return None

    palabras_crudas = alternativa.get("words", [])
    if not isinstance(palabras_crudas, list):
        msg = "la alternativa trae 'words' que no es una lista"
        raise InvalidMessageError(msg)
    palabras = tuple(_palabra(p) for p in palabras_crudas)

    idiomas = alternativa.get("languages")
    idioma = _idioma(idiomas[0]) if isinstance(idiomas, list) and idiomas else None
    if idioma is None:
        idioma = next(
            (
                _idioma(p.get("language"))
                for p in palabras_crudas
                if isinstance(p, Mapping) and _idioma(p.get("language"))
            ),
            None,
        )

    return Transcript(
        text=ExternalText(texto),
        is_final=message.get("is_final") is True,
        words=palabras,
        language=idioma,
    )


def parse_speech_started(message: Mapping[str, object]) -> SpeechStarted | None:
    """Un mensaje `SpeechStarted`, o `None` si no se entiende.

    Solo se lee `timestamp` (segundos de audio desde que abrio el canal). Un mensaje sin
    el, con algo que no es un numero finito y no negativo, **no rompe la escucha**: la
    senal es una ayuda, y perderla deja la llamada como estaba antes de pedirla. Distinto
    de `parse_results`, cuyo mensaje roto si es una respuesta invalida.
    """
    marca = message.get("timestamp")
    if isinstance(marca, bool) or not isinstance(marca, int | float):
        return None
    if not math.isfinite(marca) or marca < 0:
        return None
    return SpeechStarted(at_s=float(marca))


def tts_voice_names(models_body: Mapping[str, object]) -> frozenset[str]:
    """Los nombres de las voces de sintesis que publica `v1/models`."""
    tts = models_body.get("tts")
    if not isinstance(tts, list):
        return frozenset()
    return frozenset(
        str(m["canonical_name"])
        for m in tts
        if isinstance(m, Mapping) and isinstance(m.get("canonical_name"), str)
    )
