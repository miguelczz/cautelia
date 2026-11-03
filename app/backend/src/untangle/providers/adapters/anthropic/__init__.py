"""El adaptador de Anthropic (usos `chat_reply` y `adjuster`, 2026-10-07 y 2026-11-03).

Solo la raiz de composicion lo importa (contrato `raiz-de-composicion`), y el SDK
solo se importa en `api.py` (contrato `sdk-solo-en-su-adaptador`).
"""

from __future__ import annotations

from untangle.providers.adapters.anthropic.api import (
    PROVIDER,
    AnthropicTextGenerator,
    AnthropicWebResearcher,
    MessagesClient,
    build_client,
)

__all__ = [
    "PROVIDER",
    "AnthropicTextGenerator",
    "AnthropicWebResearcher",
    "MessagesClient",
    "build_client",
]
