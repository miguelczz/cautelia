"""Tramos literales compartidos entre dos textos.

Lo usan dos criterios que miran lo mismo desde lados distintos: que la agente no copie
sus propios prompts (`transcript_prompts`) y que un modelo no repita la orden de una
clausula envenenada (`injection_probes`). Es una comparacion de **texto**, sin modelo:
dos textos comparten un tramo cuando una cadena de caracteres seguidos aparece igual en
los dos, despues de plegarlos.

**Plegar es lo unico que se perdona.** Minusculas, sin tildes y espacios colapsados
(`compliance.controls.normalization.normalize`, la misma normalizacion de la guardia), y
sin las marcas de Markdown --las comillas inversas, los asteriscos, el numeral y el signo
`>`-- ni las vinetas al principio de una linea: copiar una regla de un prompt sin su vineta
sigue siendo copiarla. Cambiar una palabra la rompe, y esa es la medida: parafrasear no es
filtrar.
"""

from __future__ import annotations

import re

from untangle.compliance.controls.normalization import normalize

_MARCAS_DE_MARKDOWN = str.maketrans("", "", "`*#>")
_VINETA = re.compile(r"(?m)^\s*(?:[-*+]|\d+[.)])\s+")


def fold(text: str) -> str:
    """El texto plegado para compararlo: lo unico que se perdona de una copia."""
    return normalize(_VINETA.sub("", text).translate(_MARCAS_DE_MARKDOWN))


def longest_shared_run(text: str, reference: str, *, min_chars: int) -> int:
    """El tramo literal compartido mas largo, o 0 si ninguno llega a `min_chars`.

    Los dos textos ya vienen plegados (`fold`). Se busca cada ventana de `min_chars`
    caracteres del primero dentro del segundo, y la que aparece se extiende hacia la
    derecha mientras coincidan, para poder decir cuanto se copio.
    """
    if min_chars < 1:
        msg = "el tramo minimo tiene que ser de al menos un caracter"
        raise ValueError(msg)
    mejor = 0
    for inicio in range(len(text) - min_chars + 1):
        ventana = text[inicio : inicio + min_chars]
        for coincidencia in re.finditer(re.escape(ventana), reference):
            largo = min_chars
            while (
                inicio + largo < len(text)
                and coincidencia.start() + largo < len(reference)
                and text[inicio + largo] == reference[coincidencia.start() + largo]
            ):
                largo += 1
            mejor = max(mejor, largo)
    return mejor


__all__ = ["fold", "longest_shared_run"]
