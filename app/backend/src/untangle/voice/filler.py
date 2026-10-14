"""La muletilla: un acuse corto mientras la agente prepara la respuesta (2026-10-12).

Entre que la persona termina de hablar y suena la respuesta pasaban dos o tres segundos
en silencio: el reconocedor, la tolerancia de fin de habla, el modelo que entiende el
turno y el primer trozo de voz. Una muletilla --"Listo…"-- dicha a los pocos cientos de
milisegundos le dice a quien llama que se le oyo, sin cambiar lo que tarda la respuesta.

**No es contenido.** No se anota en la transcripcion del caso, no es un turno y no es el
primer audio de la respuesta: `voice.first_audio` sigue midiendo el primer trozo de la
respuesta de verdad. Si la muletilla contara como primer audio, la meta de latencia
mejoraria sin que la respuesta llegara antes, y eso esta prohibido en este proyecto.

**Tres, y rotan.** Una fija, repetida en cada turno, suena a contestadora; elegir al azar
puede repetir la misma dos veces seguidas. La rotacion es la mas simple que cumple las dos
cosas: la siguiente de la lista, y vuelta a la primera.

Cada clave se nombra en su propia rama y no sale de una tabla, por lo mismo que en
`silence.py`: el chequeo de claves sin consumidor busca literales.
"""

from __future__ import annotations

from untangle.base import Locale
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey

ONE = CopyKey("voice.filler.one")
TWO = CopyKey("voice.filler.two")
THREE = CopyKey("voice.filler.three")

#: Cuantas muletillas hay. La rotacion da la vuelta al llegar aqui.
COUNT = 3


def next_index(last: int | None) -> int:
    """La que toca despues de `last` (nula si todavia no se dijo ninguna). Nunca la misma."""
    return 0 if last is None else (last + 1) % COUNT


def phrase(index: int, *, language: Locale) -> tuple[CopyKey, str]:
    """La clave y la frase de la muletilla `index`, ya resueltas del catalogo."""
    if index == 0:
        return ONE, copy_api.t(ONE, locale=language)
    if index == 1:
        return TWO, copy_api.t(TWO, locale=language)
    if index == COUNT - 1:
        return THREE, copy_api.t(THREE, locale=language)
    msg = f"no hay muletilla {index}: son {COUNT}"
    raise ValueError(msg)


__all__ = ["COUNT", "ONE", "THREE", "TWO", "next_index", "phrase"]
