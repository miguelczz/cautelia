"""Cuando no se entendio lo que se dijo (BR3.4, AC1.23.3; BR4.4 de U18).

Tres peldanos y **nada se anota en ninguno**: una transcripcion vacia o por
debajo del umbral de confianza no es un dato incompleto, es un dato que no se
tiene, y anotarlo seria guardar algo que nadie dijo.

A la tercera se ofrece guardar el caso o pasarlo a un ajustador --la misma frase
aprobada de la decision D8 que usa el segundo silencio-- y **nunca** devolver la
llamada. Un turno bueno reinicia la cuenta.

Es la escalera hermana de la de silencios y no la misma: un silencio es que no
llego nada, y esto es que llego algo que no se entendio. La persona que se quedo
callada y la que hablo con ruido de fondo no estan en la misma situacion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from untangle.base import Locale
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.providers.ports import Transcript

NOT_UNDERSTOOD = CopyKey("voice.retry.not_understood")
#: El segundo peldano, anadido por U18 (BR4.4, AC1.31.4). Lleva las dos lenguas
#: dentro y dice que idiomas se atienden.
ONLY_TWO_LANGUAGES = CopyKey("voice.languages.only_two")
OFFER = CopyKey("voice.offer.save_or_adjuster")

#: Por debajo de esto, una palabra no se da por entendida. Es dato de la
#: aseguradora y entra por argumento; esto es el valor con el que se arranca.
DEFAULT_CONFIDENCE_FLOOR = 0.6

#: A la tercera se ofrece otra cosa en vez de pedirlo otra vez.
PELDANOS = 3

#: En el segundo se dice que idiomas se atienden (U18, BR4.4).
_PELDANO_DE_IDIOMAS = 2


class RetryStep(StrEnum):
    NONE = "none"
    #: "Sorry, I didn't catch that. Could you say it again?"
    ASK_AGAIN = "ask_again"
    #: Que idiomas se atienden y que la llamada sigue en el suyo, en los dos a la vez.
    LANGUAGES = "languages"
    #: La oferta de guardar el caso o pasarlo a un ajustador.
    OFFER = "offer"


@dataclass(frozen=True)
class RetryPrompt:
    step: RetryStep
    copy_key: CopyKey
    text: str


def understood(
    transcript: Transcript | None, *, confidence_floor: float = DEFAULT_CONFIDENCE_FLOOR
) -> bool:
    """Si lo que llego se puede dar por entendido.

    Se mira **la confianza de la transcripcion**, que es lo que dice AC1.23.3, y
    se calcula como el promedio de sus palabras. Antes se miraba la peor palabra,
    y eso tiraba frases claras: en una llamada real del 2026-10-07, «tuve un
    choque en la calle diez» llego con siete palabras seguras y una en 0,58, se
    descarto entera y la agente contesto «no le escuche bien». Con la voz de una
    persona y el microfono de un portatil eso pasa en casi cada turno. Lo que si
    tiene que ser exacto palabra por palabra --una placa, una poliza-- lo
    comprueba la lectura de confirmacion con su propio piso, no esta escalera.

    Una palabra sin confianza --el proveedor no siempre la manda-- no cuenta en
    contra (BR3.1 de U15): nula significa "no lo dijo", no "salio mal".
    """
    if transcript is None or not transcript.text.strip():
        return False
    confianzas = [p.confidence for p in transcript.words if p.confidence is not None]
    if not confianzas:
        return True
    return sum(confianzas) / len(confianzas) >= confidence_floor


def next_step(consecutive: int) -> RetryStep:
    """Que toca tras `consecutive` turnos seguidos sin entender.

    **El segundo peldano cambio con U18** (BR4.4). Decia otra vez "no le escuche
    bien" y ahora dice que idiomas se atienden y que la llamada sigue en el suyo; el
    otro se elige antes de llamar (2026-10-11: ya no se puede pedir a mitad de llamada).

    Dos criterios aprobados describen este mismo momento --el reconocedor
    devolviendo baja confianza dos turnos seguidos-- con respuestas distintas:
    AC1.29.3 pide repetir y AC1.31.4 pide la frase de los dos idiomas. Gana la
    segunda por lo que le sirve a quien esta al telefono: repetirle la misma frase
    dos veces no le ayuda, y decirle como usar el otro idioma si, ademas de
    incluir implicitamente que no se le entendio. Repetir lo mismo dos veces es lo
    que hace colgar a la gente.
    """
    if consecutive <= 0:
        return RetryStep.NONE
    if consecutive >= PELDANOS:
        return RetryStep.OFFER
    if consecutive == _PELDANO_DE_IDIOMAS:
        return RetryStep.LANGUAGES
    return RetryStep.ASK_AGAIN


def offer(*, language: Locale) -> str:
    """ "¿Lo dejamos guardado o se lo paso a un ajustador?": la oferta, sola.

    La usa quien la tiene que repetir sin pasar por la escalera --al cambiar de idioma con
    la oferta abierta, que sigue esperando su respuesta--.
    """
    return copy_api.t(OFFER, locale=language)


def prompt_for(consecutive: int, *, language: Locale) -> RetryPrompt | None:
    """La frase que toca, ya resuelta del catalogo. `None` si no toca ninguna.

    Cada clave se nombra en su propia rama, por lo mismo que en `silence.py`.
    """
    paso = next_step(consecutive)
    if paso is RetryStep.ASK_AGAIN:
        return RetryPrompt(
            step=paso, copy_key=NOT_UNDERSTOOD, text=copy_api.t(NOT_UNDERSTOOD, locale=language)
        )
    if paso is RetryStep.LANGUAGES:
        return RetryPrompt(
            step=paso,
            copy_key=ONLY_TWO_LANGUAGES,
            text=copy_api.t(ONLY_TWO_LANGUAGES, locale=language),
        )
    if paso is RetryStep.OFFER:
        return RetryPrompt(step=paso, copy_key=OFFER, text=copy_api.t(OFFER, locale=language))
    return None


__all__ = [
    "DEFAULT_CONFIDENCE_FLOOR",
    "NOT_UNDERSTOOD",
    "OFFER",
    "ONLY_TWO_LANGUAGES",
    "PELDANOS",
    "RetryPrompt",
    "RetryStep",
    "next_step",
    "offer",
    "prompt_for",
    "understood",
]
