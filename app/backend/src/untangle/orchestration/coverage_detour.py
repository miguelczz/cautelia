"""El desvío de cobertura (paso 7 de U12, BR4.2, BR4.3, FD-U12-6): detectarlo sin descarrilar la captura.

**No es un nodo ni una rama del grafo** (FD-U12-6): es el turno leyendo lo que
el ritmo de fondo ya dejó en el estado. Por eso el desvío no escribe ningún
campo de la captura, y volver al bloque pendiente no necesita recordar nada --
se deduce del caso, no de un contador (ADR-003).

**La detección es un reconocedor propio de esta unidad**, no una cuarta señal
del contrato de U10 (C-20 declara tres, y ninguna es esta): U10 no sabe nada de
pólizas ni de cobertura, y `orchestration.rhythm` tiene prohibido -- por su
propio contrato de importación -- llegar a `policy_rag`. Es exactamente el
mismo patrón que los reconocedores propios de PII del proyecto: una expresión
bilingüe, determinista, sin ninguna llamada a un modelo, acotada a lo que esta
unidad necesita reconocer y nada más.
"""

from __future__ import annotations

import re

from untangle.base import Locale

#: Heurística determinista y bilingüe. No es NLU: es lo bastante amplia para
#: los guiones de DS-2 que esta unidad declara, y se amplía el día que un caso
#: nuevo la necesite más ancha -- nunca adivinando, siempre con su propio caso
#: de prueba delante (misma disciplina que el resto de los reconocedores del
#: proyecto).
_PATTERNS: dict[Locale, re.Pattern[str]] = {
    # Tres raíces y ninguna frase: `cubr\w*` ya subsume "qué cubre", y `cubiert\w*`
    # reconoce "cubierto" sin exigir el "está" delante --"¿el parabrisas cubierto
    # entra?" es la misma pregunta--. Se simplificó al arreglar la asimetría del
    # inglés, porque dos patrones que dicen ser el mismo son más fáciles de comparar
    # cuando los dos se leen de un vistazo.
    "es": re.compile(r"\b(cobertur\w*|cubr\w*|cubiert\w*)\b", re.IGNORECASE),
    # `cover\w*` y no la lista `coverage|covered`: el lado español acepta `cubr\w*`,
    # que incluye el verbo ("¿mi póliza **cubre** esto?"), y el inglés se quedaba sin
    # su equivalente -- "does my policy **cover** hail?" no lo reconocía--. Lo
    # encontró la prueba de paridad del tipo de caso que abre el chat, y es lo que la
    # regla P12 existe para cazar: dos patrones que dicen ser el mismo en dos idiomas
    # y no lo son. Las frases de más de una palabra quedan subsumidas y se borran: una
    # alternativa que nunca puede ganar es una que hay que mantener para nada.
    "en": re.compile(r"\b(cover\w*)\b", re.IGNORECASE),
}


def is_coverage_question(text: str, *, language: Locale) -> bool:
    """El turno pregunta por su cobertura, con el reconocedor propio de esta unidad (BR4.2)."""
    return _PATTERNS[language].search(text) is not None


#: Con que empieza una pregunta que no trae su signo: "me pagan la grua", "puedo
#: prestar mi carro". Plegado a minusculas; las tildes se aceptan con y sin ellas.
_ARRANQUE_DE_PREGUNTA = re.compile(
    r"^\W*("
    r"qu[eé]|c[oó]mo|cu[aá]nto|cu[aá]ndo|cu[aá]l|d[oó]nde|qui[eé]n|puedo|pued[eo]n?|"
    r"me (pagan|responde|sirve|aplica|ampara)|mi p[oó]liza|la p[oó]liza|tengo|hay|aplica|"
    r"what|how|when|where|which|who|does|do|can|could|is|are|am|will|would|should"
    r")\b",
    re.IGNORECASE,
)


def is_question_for_comparison(text: str, *, language: Locale) -> bool:
    """Si el texto es una pregunta que la vista de comparacion puede responder.

    La vista responde **toda** pregunta contra la poliza de ejemplo de cada
    aseguradora; lo unico que no admite es un relato --"ayer me chocaron en la
    80"--, que es para el chat. Asi que basta con que sea una pregunta: trae su
    signo, arranca como una, o nombra la cobertura.

    Antes se exigia la palabra "cubre" o "cobertura", y la vista rechazaba sus
    propias preguntas de ejemplo: "¿Me pagan un carro de alquiler mientras reparan
    el mio?" no la trae (visto el 2026-10-10).
    """
    return (
        "?" in text
        or "¿" in text
        or _ARRANQUE_DE_PREGUNTA.search(text) is not None
        or is_coverage_question(text, language=language)
    )


__all__ = ["is_coverage_question", "is_question_for_comparison"]
