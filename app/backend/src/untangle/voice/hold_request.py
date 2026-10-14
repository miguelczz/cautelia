"""Pedir que la agente espere: "un momento", "dame un segundo", "hold on" (2026-10-11).

Quien va a buscar su poliza lo avisa, y hasta hoy ese aviso era un turno mas: el
grafo no sabia que hacer con "un momento", y a los cinco segundos de silencio la
agente preguntaba "¿sigues ahi?" y a los quince colgaba. Ahora se reconoce, la
agente dice que espera y la tolerancia de silencio es mas larga una vez
(`silence.HOLD_TOLERANCE`).

**Lo reconoce codigo y no un modelo**, por la misma razon que `language_request`:
cambia el ritmo de la llamada, y eso se decide con una lista que se lee en un diff.

**Solo cuenta si el turno no trae nada mas.** "Espera, no, mi placa es ABC123" es una
correccion, y tratarla como una pausa la tiraria entera. Se quitan del turno las
frases de la lista y, de lo que queda, solo se admiten palabras de cortesia: si
sobra una sola palabra con contenido, el turno es del grafo como siempre. Y hace falta
al menos una frase de la lista: "dame" a secas no pide nada. Es el
mismo criterio que usa `social.is_only_social` para no confundir un saludo con un
relato.

**Se miran los dos idiomas a la vez**, como las senales sociales: una frase corta
llega con el idioma que la llamada ya tenia aunque este dicha en el otro. La
respuesta sale en el idioma de la llamada.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from untangle.base import Locale
from untangle.compliance.controls.normalization import fold

#: Las formas de pedir que se espere, ya plegadas (sin tildes, en minusculas). Cada una
#: es un pedido por si sola: "un momento", "wait". "momento" o "segundo" a secas no
#: estan, porque aparecen en "el momento del choque".
#:
#: Combinan entre si sin enumerar cada mezcla: "hold on a second" son dos entradas y
#: "give me a moment" es una mas la cortesia "give me".
PETICIONES: Mapping[Locale, tuple[str, ...]] = {
    "es": (
        "un momento",
        "un momentito",
        "un segundo",
        "un segundito",
        "un minuto",
        "espera",
        "espere",
        "ya lo busco",
        "ya la busco",
        "ya lo encuentro",
        "ya la encuentro",
    ),
    "en": (
        "a moment",
        "a second",
        "a sec",
        "a minute",
        "one moment",
        "one second",
        "one sec",
        "hold on",
        "hold up",
        "hang on",
        "wait",
        "let me find it",
        "let me look for it",
        "i am looking for it",
    ),
}

#: Lo que puede acompanar al pedido sin ser contenido: cortesias, muletillas y los
#: verbos que lo piden ("dame", "give me", "just"), ya plegados. Cerrada a proposito:
#: una palabra de mas que no este aqui devuelve el turno al grafo, que es el lado
#: seguro. Por si solos no son un pedido: hace falta una entrada de `PETICIONES`.
RELLENOS: frozenset[str] = frozenset(
    {
        "por", "favor", "porfa", "perdon", "oye", "oiga", "ok", "okay", "si", "claro",
        "bueno", "pues", "ah", "eh", "mm", "mhm", "aja", "gracias", "dame", "deme",
        "please", "sorry", "hey", "yes", "yeah", "sure", "well", "um", "uh", "thanks",
        "give", "me", "just",
    }
)  # fmt: skip


def _patron() -> re.Pattern[str]:
    # Las mas largas primero: "espera un momento" tiene que quitarse entera y no
    # dejar "un momento" como si fuera otra frase.
    frases = sorted({f for lista in PETICIONES.values() for f in lista}, key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(re.escape(f) for f in frases) + r")\b")


_PATRON = _patron()
_PALABRAS = re.compile(r"[^\W_]+")


def requested(text: str) -> bool:
    """Si el turno es un pedido de espera y nada mas."""
    plegado = " ".join(_PALABRAS.findall(fold(text)))
    if not plegado:
        return False
    resto = _PATRON.sub(" ", plegado)
    if resto == plegado:
        return False
    return all(palabra in RELLENOS for palabra in resto.split())


__all__ = ["PETICIONES", "RELLENOS", "requested"]
