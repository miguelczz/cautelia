"""El adaptador de Cartesia: Catalina, la voz principal (U15, ADR-008).

**El unico sitio donde se habla el protocolo de Cartesia** (BR1.1). Solo la raiz
de composicion importa este paquete, y dentro de el nada mas que
`adapters/wire.py` abre conexiones.

- `protocol.py` --el mensaje que sube y los que bajan--.
- `tts.py` --sintetizar en streaming por WebSocket, una frase por canal o muchas
  por el mismo canal de una llamada--.
- `catalog.py` --que voces publica Cartesia, una consulta que no cuesta--.
- `ADAPTER_INFO` --lo que la raiz sabe de este adaptador (BR2.3)--.
"""

from __future__ import annotations

from untangle.base import ProviderName
from untangle.providers.adapters.cartesia.catalog import missing_voices
from untangle.providers.adapters.cartesia.protocol import ENDPOINT
from untangle.providers.adapters.cartesia.tts import CartesiaSpeechSession, CartesiaTextToSpeech
from untangle.providers.voice_availability import SpeechAdapterInfo

__all__ = [
    "ADAPTER_INFO",
    "ENDPOINT",
    "CartesiaSpeechSession",
    "CartesiaTextToSpeech",
    "missing_voices",
]

#: Los modelos de Cartesia con respuesta grabada y prueba de contrato en cada
#: entrega (BR2.3). Una prueba de `test:u15` comprueba que cada uno tiene su
#: archivo en `tests/unit/voice_providers/recorded/`.
ADAPTER_INFO = SpeechAdapterInfo(
    provider=ProviderName.CARTESIA,
    contract_models=frozenset({"sonic-3.6"}),
)
