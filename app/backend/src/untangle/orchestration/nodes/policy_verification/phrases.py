"""Las frases fijas del nodo `policy_verification` (BR5.6 a BR5.8, paso 8).

Cinco claves, todas bajo `policy_rag.coverage.*` porque este nodo es el unico
dueno de la respuesta de cobertura -- ninguna otra unidad las necesita todavia.
Cada una pasa por la guardia de salida como cualquier otro texto (BR5.7); eso
lo hace el nodo, no este modulo, que solo resuelve la clave del catalogo.
"""

from __future__ import annotations

import re

from untangle.base import Locale
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey

#: AC2.5.1: no habia ninguna clausula que citar (BR5.6).
NO_CLAUSE_FOUND = CopyKey("policy_rag.coverage.no_clause_found")

#: AC2.6.1, AC2.7.4: la recuperacion volvio a fallar tras su unico reintento
#: (BR5.2) y el caso queda derivado.
UNVERIFIABLE = CopyKey("policy_rag.coverage.unverifiable")

#: BR5.8, FD-U8-1: la clausula citada esta en un idioma distinto del de la
#: conversacion. Pide la variable `language`.
CROSS_LANGUAGE_NOTICE = CopyKey("policy_rag.coverage.cross_language_notice")

#: AC2.7.1: la forma de la cita por voz, una frase que nombra la parte y dice
#: que queda en el caso. Pide la variable `part`.
VOICE_SUMMARY = CopyKey("policy_rag.coverage.voice_summary")

#: AC2.7.2: un endoso vigente modifica la clausula citada (BR3.5); la
#: respuesta nunca dice el monto, en ningun canal. Sin variables.
AMOUNT_DEFERRED = CopyKey("policy_rag.coverage.amount_deferred")

#: Fase 1 (2026-10-08): la respuesta de cobertura en el chat, nombrando la parte de la
#: poliza; la cláusula exacta va debajo, como cita. Pide la variable `part`.
FOUND_CHAT = CopyKey("policy_rag.coverage.found_chat")
#: Lo que se dice mientras el fondo revisa la poliza; la respuesta llega sola.
CHECKING = CopyKey("policy_rag.coverage.checking")
#: Ya hay poliza y no hay pregunta: se pide, con un ejemplo.
ASK_QUESTION = CopyKey("policy_rag.coverage.ask_question")
#: La pregunta llego antes que la poliza.
NEED_POLICY = CopyKey("policy_rag.coverage.need_policy")
#: Lo que antecede a la pregunta del reporte que quedo pendiente.
BACK_TO_REPORT = CopyKey("policy_rag.coverage.back_to_report")

#: BR5.8: como se nombra cada idioma, en el idioma de quien pregunta. La
#: cursiva de la clave dice la conversacion, la de dentro dice la clausula.
_LANGUAGE_NAMES: dict[Locale, dict[Locale, str]] = {
    "es": {"es": "español", "en": "inglés"},
    "en": {"es": "Spanish", "en": "English"},
}


def no_clause_found_text(*, locale: Locale) -> str:
    return copy_api.t(NO_CLAUSE_FOUND, locale=locale)


def unverifiable_text(*, locale: Locale) -> str:
    return copy_api.t(UNVERIFIABLE, locale=locale)


def cross_language_notice_text(*, locale: Locale, clause_language: Locale) -> str:
    nombre = _LANGUAGE_NAMES[locale][clause_language]
    return copy_api.t(CROSS_LANGUAGE_NOTICE, locale=locale, language=nombre)


def voice_summary_text(*, locale: Locale, part: str) -> str:
    return copy_api.t(VOICE_SUMMARY, locale=locale, part=part)


def amount_deferred_text(*, locale: Locale) -> str:
    return copy_api.t(AMOUNT_DEFERRED, locale=locale)


__all__ = [
    "AMOUNT_DEFERRED",
    "CROSS_LANGUAGE_NOTICE",
    "NO_CLAUSE_FOUND",
    "UNVERIFIABLE",
    "VOICE_SUMMARY",
    "amount_deferred_text",
    "cross_language_notice_text",
    "found_chat_claim_text",
    "no_clause_found_text",
    "part_label",
    "unverifiable_text",
    "voice_summary_text",
]


def found_chat_text(*, locale: Locale, part: str) -> str:
    return copy_api.t(FOUND_CHAT, locale=locale, part=part)


FOUND_CHAT_CLAIM = CopyKey("policy_rag.coverage.found_chat_claim")


def found_chat_claim_text(*, locale: Locale, part: str, claim: str) -> str:
    """La respuesta con la explicacion de la IA sobre la clausula, terminada en punto."""
    frase = claim.strip()
    if frase and frase[-1] not in ".!?":
        frase += "."
    return copy_api.t(FOUND_CHAT_CLAIM, locale=locale, part=part, claim=frase)


#: La respuesta de cobertura **dicha** en una llamada (2026-10-11): no hay "abajo",
#: la clausula queda en el caso. Piden la variable `part`; la segunda, `claim`.
FOUND_VOICE = CopyKey("policy_rag.coverage.found_voice")
FOUND_VOICE_CLAIM = CopyKey("policy_rag.coverage.found_voice_claim")


def found_voice_text(*, locale: Locale, part: str) -> str:
    return copy_api.t(FOUND_VOICE, locale=locale, part=part)


def found_voice_claim_text(*, locale: Locale, part: str, claim: str) -> str:
    """La respuesta hablada con la explicacion de la IA, terminada en punto."""
    frase = claim.strip()
    if frase and frase[-1] not in ".!?":
        frase += "."
    return copy_api.t(FOUND_VOICE_CLAIM, locale=locale, part=part, claim=frase)


_PARTE = re.compile(r"-(A|B|C|D|E|F|DEF)\.")


def part_label(clause_id: str, *, locale: Locale) -> str:  # noqa: PLR0911 -- una rama por parte, cada una con su clave literal
    """La parte de la poliza en el idioma de la conversacion, por el identificador.

    Cada rama con su clave literal, para el chequeo de claves sin consumidor. Un
    identificador que no se reconoce dice "una de sus clausulas", nunca el nombre de
    la parte en el idioma del corpus (2026-10-08).
    """
    if "-END-" in clause_id:
        return copy_api.t(CopyKey("policy_rag.coverage.part.special"), locale=locale)
    if "-JUR-" in clause_id:
        return copy_api.t(CopyKey("policy_rag.coverage.part.territory"), locale=locale)
    parte = _PARTE.search(clause_id)
    letra = parte.group(1) if parte else ""
    if letra == "A":
        return copy_api.t(CopyKey("policy_rag.coverage.part.a"), locale=locale)
    if letra == "B":
        return copy_api.t(CopyKey("policy_rag.coverage.part.b"), locale=locale)
    if letra == "C":
        return copy_api.t(CopyKey("policy_rag.coverage.part.c"), locale=locale)
    if letra == "D":
        return copy_api.t(CopyKey("policy_rag.coverage.part.d"), locale=locale)
    if letra == "E":
        return copy_api.t(CopyKey("policy_rag.coverage.part.e"), locale=locale)
    if letra == "F":
        return copy_api.t(CopyKey("policy_rag.coverage.part.f"), locale=locale)
    if letra == "DEF":
        return copy_api.t(CopyKey("policy_rag.coverage.part.definitions"), locale=locale)
    return copy_api.t(CopyKey("policy_rag.coverage.part.other"), locale=locale)


def checking_text(*, locale: Locale) -> str:
    return copy_api.t(CHECKING, locale=locale)


def ask_question_text(*, locale: Locale) -> str:
    return copy_api.t(ASK_QUESTION, locale=locale)


def need_policy_text(*, locale: Locale) -> str:
    return copy_api.t(NEED_POLICY, locale=locale)


def back_to_report_text(*, locale: Locale) -> str:
    return copy_api.t(BACK_TO_REPORT, locale=locale)
