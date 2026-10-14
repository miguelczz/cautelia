"""El adaptador de Deepgram: transcripcion y voz de respaldo (U15, ADR-007, ADR-008).

**El unico sitio donde se habla el protocolo de Deepgram** (BR1.1). Un contrato
`protected` de importacion deja que solo la raiz de composicion importe este
paquete, y dentro de el nada mas que `adapters/wire.py` abre conexiones.

Cinco piezas:

- `protocol.py` --rutas, consultas, mensajes y errores de Deepgram--.
- `stt.py` --transcribir en streaming con `nova-3` en modo `multi`--.
- `tts.py` --la voz de respaldo con Aura-2--.
- `catalog.py` --que voces publica Deepgram, una consulta que no cuesta--.
- `ADAPTER_INFO` --lo que la raiz sabe de este adaptador para decidir si la voz
  de una aseguradora puede atender (BR2.3)--.
"""

from __future__ import annotations

from untangle.base import ProviderName
from untangle.providers.adapters.deepgram.catalog import missing_voices
from untangle.providers.adapters.deepgram.protocol import ENDPOINT
from untangle.providers.adapters.deepgram.stt import DeepgramSpeechToText
from untangle.providers.adapters.deepgram.tts import DeepgramAuraTextToSpeech
from untangle.providers.voice_availability import SpeechAdapterInfo

__all__ = [
    "ADAPTER_INFO",
    "ENDPOINT",
    "DeepgramAuraTextToSpeech",
    "DeepgramSpeechToText",
    "missing_voices",
]

#: Los modelos de Deepgram con respuesta grabada y prueba de contrato en cada
#: entrega. Un modelo que no esta aqui no se puede activar por configuracion
#: (BR2.3), y una prueba de `test:u15` comprueba que cada uno tiene su archivo en
#: `tests/unit/voice_providers/recorded/`.
ADAPTER_INFO = SpeechAdapterInfo(
    provider=ProviderName.DEEPGRAM,
    contract_models=frozenset({"nova-3", "aura-2"}),
)
