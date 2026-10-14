"""Que voces de Aura-2 publica Deepgram: una consulta que no cuesta (U15, BR2.2).

La usa `mise run voice:contract-live` antes de sintetizar nada: si una voz
declarada en `providers.yaml` no esta en la lista del proveedor, la corrida se
detiene sin gastar. Vive **aqui** y no en el comando porque la ruta de la lista y
la forma de su respuesta son protocolo de Deepgram, y el protocolo de cada
proveedor solo se usa dentro de su adaptador (BR1.1, SEC-U15.1).
"""

from __future__ import annotations

from collections.abc import Sequence

from untangle.base import ProviderName
from untangle.providers.adapters.deepgram import protocol
from untangle.providers.adapters.speech_common import catalog_lookup, catalog_request
from untangle.providers.speech_wire import SpeechCaller

__all__ = ["missing_voices"]

_ESTADO_OK = 200


async def missing_voices(caller: SpeechCaller, voice_ids: Sequence[str]) -> list[str]:
    """Las voces pedidas que Deepgram no publica, sin repetir y en el orden pedido.

    Una sola consulta a la lista de modelos, que trae todas las voces. Si la
    consulta no devuelve 200, **ninguna** cuenta como publicada: no se puede
    afirmar que una voz existe sin haberla visto en la lista.
    """
    estado, cuerpo = await catalog_lookup(
        caller, catalog_request(protocol.MODELS_PATH), provider=ProviderName.DEEPGRAM
    )
    publicadas = protocol.tts_voice_names(cuerpo) if estado == _ESTADO_OK else frozenset()
    return [voz for voz in dict.fromkeys(voice_ids) if voz not in publicadas]
