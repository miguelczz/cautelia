"""Que voces publica Cartesia: una consulta que no cuesta (U15, BR2.2).

La usa `mise run voice:contract-live` antes de sintetizar nada: si una voz
declarada en `providers.yaml` no tiene ficha en el proveedor, la corrida se
detiene sin gastar. Vive **aqui** y no en el comando porque la ruta de la ficha
es protocolo de Cartesia, y el protocolo de cada proveedor solo se usa dentro de
su adaptador (BR1.1, SEC-U15.1).
"""

from __future__ import annotations

from collections.abc import Sequence

from untangle.base import ProviderName
from untangle.providers.adapters.cartesia import protocol
from untangle.providers.adapters.speech_common import catalog_lookup, catalog_request
from untangle.providers.speech_wire import SpeechCaller

__all__ = ["missing_voices"]

_ESTADO_OK = 200


async def missing_voices(caller: SpeechCaller, voice_ids: Sequence[str]) -> list[str]:
    """Las voces pedidas que Cartesia no publica, sin repetir y en el orden pedido.

    Una consulta por voz: Cartesia no tiene una lista que se pueda leer entera
    sin paginar, y la ficha de una voz es la respuesta exacta a "existe esta".
    Cualquier codigo distinto de 200 cuenta como no publicada.
    """
    faltan: list[str] = []
    for voz in dict.fromkeys(voice_ids):
        estado, _ = await catalog_lookup(
            caller, catalog_request(protocol.voice_path(voz)), provider=ProviderName.CARTESIA
        )
        if estado != _ESTADO_OK:
            faltan.append(voz)
    return faltan
