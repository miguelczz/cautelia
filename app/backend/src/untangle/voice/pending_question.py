"""La pregunta que la agente dejo en el aire, para retomarla (2026-10-11).

Cuando la agente contesta otra cosa --lo que encontro en la poliza, que sigue
revisando-- la persona todavia debe una respuesta: "¿hubo alguien herido?". Sin
volver a decirla, lo que sigue es un silencio y despues "¿sigues ahi?".

Sale del texto que la agente dijo, y no del estado del grafo: lo que hay que
repetir es lo que la persona **oyo**, que en una llamada incluye la pregunta de la
apertura, que ningun nodo escribio.
"""

from __future__ import annotations

import re

_FIN_DE_FRASE = re.compile(r"(?<=[.!?…])\s+")


def last_question(text: str) -> str | None:
    """La ultima pregunta de lo dicho, sin el acuse que traia delante.

    En espanol empieza en su signo de apertura; en ingles es la ultima frase, si
    termina en signo de pregunta.
    """
    dicho = text.strip()
    if not dicho.endswith("?"):
        return None
    if "¿" in dicho:
        pregunta = dicho[dicho.rindex("¿") :]
    else:
        pregunta = _FIN_DE_FRASE.split(dicho)[-1]
    return pregunta.strip() or None


__all__ = ["last_question"]
