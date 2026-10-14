"""El adaptador de Anthropic (uso `chat_reply`, 2026-10-07).

Solo la raiz de composicion lo importa (contrato `raiz-de-composicion`), y el SDK
solo se importa en `api.py` (contrato `sdk-solo-en-su-adaptador`).
"""

from __future__ import annotations

from untangle.providers.adapters.anthropic.api import (
    PROVIDER,
    AnthropicTextGenerator,
    MessagesClient,
    build_client,
)

__all__ = ["PROVIDER", "AnthropicTextGenerator", "MessagesClient", "build_client"]
