"""Que contesta la persona a "dejamos tu caso guardado, o se lo paso a un ajustador".

La oferta la dicen dos caminos --el segundo silencio y la tercera vez que no se
entiende-- y hasta hoy nadie leia la respuesta: "guardalo" y "pasalo" entraban al
grafo como un turno mas y la llamada seguia como si nada. Aqui se lee, con cuatro
desenlaces: pide el ajustador, pide dejarlo guardado, contesta un si o un no que no
dice cual de las dos, o dice otra cosa y la conversacion sigue.

**Reusa el reconocedor de peticion de persona de U10** (`detect_human_request`) para
"quiero hablar con un ajustador", y solo agrega las formas que existen por estar
contestando a esta pregunta: "pasalo", "al ajustador", "guardalo", "luego sigo". Por
si solas no significan nada, y por eso solo se miran con la oferta abierta.

**Cerrada a proposito**, como `hold_request`: una palabra que no este aqui devuelve el
turno al grafo, que es el lado seguro. Lo que no se hace es adivinar entre las dos: si
el turno nombra las dos --"guardalo, no lo pases"-- la negacion decide, y si nombra las
dos sin negar ninguna, no se elige nada.
"""

from __future__ import annotations

import re
from enum import StrEnum

from untangle.base import Locale
from untangle.compliance.controls import api as controls
from untangle.compliance.controls.normalization import fold
from untangle.orchestration.nodes.intake import confirmation


class OfferReply(StrEnum):
    #: Quiere que se lo pase a un ajustador.
    ADJUSTER = "adjuster"
    #: Quiere dejarlo guardado para seguir despues.
    SAVE = "save"
    #: Un si o un no a secas: no dice cual de las dos.
    CHOOSE = "choose"
    #: Dice otra cosa: la conversacion sigue.
    OTHER = "other"


#: Hasta cuantas palabras es un "si" o un "no" a secas. El mismo criterio que el de la
#: captura (`_es_asentimiento`): un si con mas palabras ya cuenta algo.
_PALABRAS_DE_UN_SI_O_UN_NO = 3

_NIEGA = r"\b(?:no|ni|sin|not|don't|dont)\b(?:\s+\w+){0,3}?\s+"

# Todo plegado (sin tildes, en minusculas): se busca sobre `fold(texto)`.
_ELIGE_AJUSTADOR = re.compile(
    r"\bpas(?:a|e|en|es)(?:lo|la|selo|sela|melo|mela)\b"
    r"|\bajustador(?:a|as|es)?\b|\badjusters?\b"
    r"|\b(?:pass|hand|send|forward)\s+it\b"
)
_RECHAZA_AJUSTADOR = re.compile(
    _NIEGA + r"(?:ajustador\w*|adjuster\w*|pas(?:a|e|en|es)\w*|pass\w*|hand\w*|send\w*)\b"
)

_SEGUIR = r"(?:sigo|seguimos|sigamos|continuo|continuamos|continuemos|termino|terminamos|retomo|retomamos|vuelvo|volvemos)"
_DESPUES = r"(?:luego|despues|mas tarde|otro dia|otro rato|otro momento)"
_ELIGE_GUARDAR = re.compile(
    r"\bguard(?:a|e|ar|ado|ada|alo|ala|ame|emoslo|emosla|elo|ela)\b"
    r"|\bdej(?:a|e)(?:lo|la|melo|mela|moslo|mosla)\b|\bdejamos\b"
    rf"|\b{_SEGUIR}\b.{{0,15}}\b{_DESPUES}\b|\b{_DESPUES}\b.{{0,15}}\b{_SEGUIR}\b"
    r"|\bsave\b|\b(?:keep|leave)\s+it\b"
    r"|\b(?:continue|finish|resume|pick\s+it\s+up|come\s+back)\b.{0,15}\blater\b"
    r"|\blater\b.{0,15}\b(?:continue|finish|resume)\b"
)
_RECHAZA_GUARDAR = re.compile(_NIEGA + r"(?:guard\w*|dej\w*|save\w*|keep|leave)\b")


async def classify(text: str, *, language: Locale) -> OfferReply:
    """Que eligio la persona. Se mira en los dos idiomas a la vez, como `confirmation`."""
    plegado = fold(text)
    pide_ajustador = (
        _ELIGE_AJUSTADOR.search(plegado) is not None or await controls.detect_human_request(text)
    ) and _RECHAZA_AJUSTADOR.search(plegado) is None
    pide_guardar = (
        _ELIGE_GUARDAR.search(plegado) is not None and _RECHAZA_GUARDAR.search(plegado) is None
    )
    if pide_ajustador and pide_guardar:
        return OfferReply.OTHER
    if pide_ajustador:
        return OfferReply.ADJUSTER
    if pide_guardar:
        return OfferReply.SAVE
    if len(text.split()) <= _PALABRAS_DE_UN_SI_O_UN_NO and (
        confirmation.is_affirmative(text, language=language)
        or confirmation.is_negative(text, language=language)
    ):
        return OfferReply.CHOOSE
    return OfferReply.OTHER


__all__ = ["OfferReply", "classify"]
