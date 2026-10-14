"""La entidad del catalogo de textos.

`CopyEntry` es del componente CopyCatalog, no de Evaluation: vivia en el modulo
de evaluaciones y el contrato de capas lo detecto -- el catalogo habria quedado
importando el corredor para hablar de sus propias frases, que es la direccion
contraria a la que declara ADR-001.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from untangle.base import Frozen, Locale

# Las claves del catalogo son jerarquicas con puntos y siempre literales
# (BR3.4): nunca se construyen concatenando en tiempo de ejecucion, porque eso
# impediria comprobar si tienen consumidor.
COPY_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")


class Surface(StrEnum):
    """Donde se muestra una frase. Agrupa el catalogo por consumidor."""

    VOICE = "voice"
    CHAT = "chat"
    INBOX = "inbox"
    PANEL = "panel"
    SYSTEM = "system"


class CopyEntry(Frozen):
    """Una frase que lee una persona, en un idioma.

    El catalogo es la unica fuente de texto visible del sistema; ningun modulo
    escribe texto en linea (BR3.3).
    """

    key: str = Field(pattern=COPY_KEY_PATTERN.pattern)
    locale: Locale
    text: str = Field(min_length=1)
    version: int = Field(default=1, ge=1)
    decision: str | None = None
    surface: Surface

    @model_validator(mode="after")
    def _version_mayor_que_uno_declara_su_decision(self) -> Self:
        # BR3.5: una frase cambiada sin su razon deja la guia de voz y el
        # producto contandose historias distintas.
        if self.version > 1 and not self.decision:
            msg = (
                f"la entrada '{self.key}' ({self.locale}) tiene version "
                f"{self.version} y no declara la decision que la cambio (BR3.5)"
            )
            raise ValueError(msg)
        return self
