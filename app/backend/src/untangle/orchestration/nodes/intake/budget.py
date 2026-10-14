"""Guardia previa del presupuesto de 3.900 tokens de entrada por turno (PERF-U11.1, ADR-006).

**Lo que esto es, dicho sin adornos: una estimacion, no el conteo del
proveedor.** Cuenta palabras y signos de puntuacion con una regla propia y
versionada --aplicada siempre igual, para que dos corridas del mismo commit
midan lo mismo (FD-U11-2)-- porque ni Gemini ni ningun proveedor de este
proyecto publica un contador que corra sin red, y "ninguna prueba llama al
proveedor" (CG-U11-4) es una regla mas dura que este presupuesto.

**La direccion del error no es la que parece.** Contar palabras y puntuacion
**no** es un limite superior: un tokenizador de subpalabras parte las palabras
largas o raras en varias piezas --"POL-123456" son tres unidades para esta
regla y cinco o mas para el tokenizador-- y en espanol suele dar bastante mas
de un token por palabra. Esta cuenta, entonces, **puede quedar por debajo de la
real**, y un prompt que pase esta guardia todavia puede no caber. Por eso es
una guardia previa y no la medicion de PERF-U11.1.

**Donde esta el conteo de verdad, y quien lo publica.** En la respuesta del
proveedor: `usageMetadata.promptTokenCount`, que el adaptador de U5 ya lee y
registra por nodo en la traza. Ese es el numero que mide PERF-U11.1 por decision
de Miguel del 2026-09-27 (enmienda escrita en
`nfr-requirements/performance-requirements.md`), y se publica desde la primera
corrida con conductor de canal (U13) -- la misma forma que PERF-U11.2 y
PERF-U11.3. Hasta entonces el criterio se reporta como "no medida" con esa causa.

Esta guardia se queda por lo que si certifica: si un prompt ya no cabe aqui, no
cabe. Que devuelva verde no certifica lo contrario.
"""

from __future__ import annotations

import re

from untangle.providers.ports import Prompt

#: PERF-U11.1, ADR-006: el presupuesto de entrada de un turno de voz.
MAX_INPUT_TOKENS_PER_VOICE_TURN = 3_900

#: Palabras y signos de puntuacion, por separado: una coma o un punto son su
#: propio token para un tokenizador real. Aun asi la cuenta puede quedar por
#: debajo de la real, porque las palabras largas se parten en subpalabras.
_TOKEN = re.compile(r"[\wÀ-ÿ]+|[^\w\sÀ-ÿ]", re.UNICODE)


def count_tokens(text: str) -> int:
    """La cuenta propia y versionada de este modulo: una estimacion (ver el docstring)."""
    return len(_TOKEN.findall(text))


def count_prompt_tokens(prompt: Prompt) -> int:
    """El presupuesto de entrada de un prompt entero: instruccion mas turnos."""
    total = count_tokens(str(prompt.instruction.text))
    for parte in prompt.parts:
        total += count_tokens(str(parte.text))
    return total


def assert_within_voice_budget(prompt: Prompt) -> tuple[str, ...]:
    """PERF-U11.1: el problema, si el prompt ya no cabe ni en la cuenta estimada.

    Que devuelva `()` **no** certifica que el prompt cabe: la cuenta puede
    quedar por debajo de la del proveedor (ver el docstring del modulo). Lo que
    certifica es lo contrario, que es lo util de una guardia previa: si aqui ya
    no cabe, no cabe.
    """
    total = count_prompt_tokens(prompt)
    if total > MAX_INPUT_TOKENS_PER_VOICE_TURN:
        return (
            f"el prompt estima {total} tokens de entrada, mas de los "
            f"{MAX_INPUT_TOKENS_PER_VOICE_TURN} del presupuesto de un turno de voz "
            "(PERF-U11.1, ADR-006)",
        )
    return ()


__all__ = [
    "MAX_INPUT_TOKENS_PER_VOICE_TURN",
    "assert_within_voice_budget",
    "count_prompt_tokens",
    "count_tokens",
]
