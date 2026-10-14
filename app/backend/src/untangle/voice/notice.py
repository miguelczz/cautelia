"""Lo que se decidio sobre un caso, dicho al volver a llamar (BR6.5, AC1.27.5).

Misma forma que `chat/notice.py` y con claves propias: aquella pantalla puede
enlazar a la traza y esta no, y lo que se lee no se dice igual que lo que se oye.

**Va antes de preguntar en que se puede ayudar.** La persona llama para saber que
paso con su caso; preguntarle primero en que se le ayuda es la forma mas segura
de que lo pregunte ella.

**Un caso sin decidir no inventa un resultado.** `pending` dice que sigue en
revision, sin plazo: la demo no lo garantiza y la guia de voz prohibe especular
sobre tiempos.
"""

from __future__ import annotations

from dataclasses import dataclass

from untangle.base import Locale
from untangle.case_record.models import Resolution
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey

#: Cada clave se nombra literal en su rama, que es lo que el chequeo de claves
#: sin consumidor necesita.
APPROVED = CopyKey("voice.decision.approved")
REJECTED = CopyKey("voice.decision.rejected")
SENT_TO_INSURER = CopyKey("voice.decision.sent_to_insurer")
PENDING = CopyKey("voice.decision.pending")
#: El comentario se dice **solo si lo hay**: dentro de las tres frases de arriba,
#: una decision sin nota diria "su comentario fue." y sonaria a frase cortada.
NOTE = CopyKey("voice.decision.note")


@dataclass(frozen=True)
class Spoken:
    """El aviso compuesto, con la clave con la que quedara registrado."""

    copy_key: CopyKey
    text: str


def pending(*, language: Locale) -> Spoken:
    """El caso sigue en revision. Sin plazo y sin inventar un resultado."""
    return Spoken(copy_key=PENDING, text=copy_api.t(PENDING, locale=language))


def resolved(resolution: Resolution, *, case_number: str, comment: str, language: Locale) -> Spoken:
    """Lo que una persona decidio, dicho en voz alta.

    Cada rama nombra su literal dentro: devolver la clave para resolverla despues
    romperia el chequeo de claves sin consumidor, que busca literales.

    `REGISTERED` no es una decision: es lo que el sistema pone al abrir el caso, y
    decirla seria decir que alguien decidio algo que nadie decidio. Se responde
    como pendiente, que es lo que de verdad pasa.
    """
    if resolution is Resolution.APPROVED:
        clave, texto = APPROVED, copy_api.t(APPROVED, locale=language, case_number=case_number)
    elif resolution is Resolution.REJECTED:
        clave, texto = REJECTED, copy_api.t(REJECTED, locale=language, case_number=case_number)
    elif resolution is Resolution.SENT_TO_INSURER:
        clave, texto = (
            SENT_TO_INSURER,
            copy_api.t(SENT_TO_INSURER, locale=language, case_number=case_number),
        )
    else:
        return pending(language=language)

    if comment.strip():
        texto = f"{texto} {copy_api.t(NOTE, locale=language, comment=comment)}"
    return Spoken(copy_key=clave, text=texto)


__all__ = [
    "APPROVED",
    "NOTE",
    "PENDING",
    "REJECTED",
    "SENT_TO_INSURER",
    "Spoken",
    "pending",
    "resolved",
]
