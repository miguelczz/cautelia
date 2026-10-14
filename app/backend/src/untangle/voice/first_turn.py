"""A que llama la persona, dicho en su primer turno (2026-10-11).

La llamada abria siempre preguntando "¿hubo alguien herido?", como si toda llamada
fuera un accidente. Ahora abre con "¿en que te puedo ayudar?" y lo primero que la
persona dice decide: reportar un accidente, una duda sobre su poliza, o cotizar.

**Por reglas y sin modelo**, con los mismos reconocedores que usa el chat para su
primer mensaje (`coverage_detour` y `quote_reply`): este es el camino con el
presupuesto de latencia mas estricto, y dos reconocedores para la misma pregunta es
como uno de los dos se queda viejo.

**La voz no toma cotizaciones** --son diecisiete datos, y se piden por chat--: quien
llama a cotizar oye eso, dicho con honestidad, en vez de un reporte de accidente que
no pidio.

**Y una primera frase que no dice a que viene no decide nada** (2026-10-13). «Queria
consultar sobre...» o «tengo una pregunta» seguian por el reporte de un accidente, porque
lo que no era una duda de poliza ni una cotizacion caia en el reporte con que nacio la
llamada. Ahora esa frase se reconoce (`NOT_STATED`), la llamada pregunta a que viene y
espera la proxima. El vocabulario de esa frase vive en el nucleo (`orchestration/stated_purpose`)
porque el respaldo por reglas del chat usa el mismo.
"""

from __future__ import annotations

import re
from enum import StrEnum

from untangle.base import Locale
from untangle.orchestration import coverage_detour, quote_reply, stated_purpose


class CallPurpose(StrEnum):
    CLAIM = "claim"
    POLICY_QUESTION = "policy_question"
    QUOTE = "quote"
    #: Solo anuncia que quiere consultar o preguntar algo, sin decir que: no decide la llamada.
    NOT_STATED = "not_stated"


#: Nombrar la poliza como tema --"una duda de mi poliza", "about my policy"-- sin
#: estar dando su numero. Plegado; las tildes se aceptan con y sin ellas.
_SOBRE_LA_POLIZA = re.compile(
    r"\b(duda|dudas|pregunta|preguntas|consulta|consultar|preguntar|saber|informaci[oó]n|"
    r"referente|respecto|acerca|sobre|hablar\w*)\b.{0,40}\b(p[oó]liza|seguro)\b"
    r"|\b(question|questions|ask|asking|know|about|regarding)\b.{0,40}\b(policy|insurance)\b",
    re.IGNORECASE,
)


def purpose_of(text: str, *, language: Locale, quote_enabled: bool) -> CallPurpose:
    """A que llama, por lo que dijo.

    Cotizar y preguntar por la poliza se reconocen; una frase que solo anuncia que quiere
    consultar algo, sin decir que, **no decide nada**; el resto es un reporte, que es con lo que
    nacio la llamada.
    """
    if quote_enabled and quote_reply.is_quote_request(text, language=language):
        return CallPurpose.QUOTE
    if (
        coverage_detour.is_coverage_question(text, language=language)
        or _SOBRE_LA_POLIZA.search(text) is not None
    ):
        return CallPurpose.POLICY_QUESTION
    if stated_purpose.says_nothing_about_purpose(text, language=language):
        return CallPurpose.NOT_STATED
    return CallPurpose.CLAIM


__all__ = ["CallPurpose", "purpose_of"]
