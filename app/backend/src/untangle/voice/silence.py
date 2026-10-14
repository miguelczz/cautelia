"""La escalera de silencios (BR5.1, BR5.2, BR5.3).

Tres tiempos iguales, cada uno contado **desde que la agente termina de hablar**.
El reloj se detiene mientras habla: si corriera, su propia respuesta contaria como
silencio de la persona y la llamada se cerraria sola.

**Tampoco corre mientras a quien le toca hablar es a la agente** (2026-10-11): el turno
ya cerrado y sin contestar, o la respuesta del fondo que aguarda (`loop.ANSWER_WAIT`,
`loop.LATE_ANSWER_WAIT`). El silencio solo cuenta contra la persona cuando la agente ya
callo y es el turno de ella; y si ella misma pide esperar, `HOLD_TOLERANCE`.

**Ninguna de las tres frases ofrece devolver la llamada.** La devolucion es `C3`,
no existe, y P7 prohibe ofrecer lo que no esta construido. La oferta correcta es
la decision D8 y vive en una clave compartida con el camino de "no le entendi",
porque las dos ofrecen exactamente lo mismo y son la misma frase aprobada.

Este modulo **no tiene reloj propio**: recibe cuanto silencio lleva y dice que
toca. Un temporizador aqui haria falta dormir para probarlo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from untangle.base import Locale
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey

STILL_THERE = CopyKey("voice.silence.still_there")
FAREWELL = CopyKey("voice.silence.farewell")
OFFER = CopyKey("voice.offer.save_or_adjuster")

#: La tolerancia de partida (guia de voz, punto 9). Es dato de la aseguradora y
#: entra por argumento; esto es el valor con el que se arranca.
DEFAULT_TOLERANCE = timedelta(seconds=5)

#: Cuanto se espera, en vez de la tolerancia de arriba, tras pedir la persona que se
#: espere ("un momento", "hold on"). Solo vale para el silencio que sigue a ese
#: pedido: preguntar "¿sigues ahi?" a los cinco segundos a quien acaba de decir que va
#: a buscar su poliza es no haberle hecho caso. El tercer silencio sigue colgando.
HOLD_TOLERANCE = timedelta(seconds=30)

#: Cuantos silencios seguidos caben antes de despedirse.
PELDANOS = 3


class SilenceStep(StrEnum):
    """En que peldano de la escalera esta la llamada."""

    #: Todavia no vencio ninguna tolerancia.
    NONE = "none"
    #: "Are you still there?"
    ASK = "ask"
    #: La oferta de guardar el caso o pasarlo a un ajustador.
    OFFER = "offer"
    #: La despedida, que ademas **termina la llamada**.
    FAREWELL = "farewell"


_ORDEN = (SilenceStep.ASK, SilenceStep.OFFER, SilenceStep.FAREWELL)


@dataclass(frozen=True)
class SilencePrompt:
    """Lo que la agente dice ante un silencio, y si con eso termina la llamada."""

    step: SilenceStep
    copy_key: CopyKey
    text: str

    @property
    def ends_call(self) -> bool:
        """Solo el tercero cuelga, y no en seco: se despide antes (BR5.2)."""
        return self.step is SilenceStep.FAREWELL


def next_step(consecutive: int) -> SilenceStep:
    """Que peldano toca despues de `consecutive` silencios seguidos.

    Un turno de la persona reinicia la cuenta, y por eso esto es una funcion de
    un numero y no una maquina con memoria: quien lleva la cuenta es la llamada.
    """
    if consecutive <= 0:
        return SilenceStep.NONE
    return _ORDEN[min(consecutive, PELDANOS) - 1]


def prompt_for(consecutive: int, *, language: Locale) -> SilencePrompt | None:
    """La frase del peldano, ya resuelta del catalogo. `None` si no toca ninguna.

    Cada clave se nombra en su propia rama y no se saca de una tabla: el chequeo
    de claves sin consumidor busca literales, y una clave elegida en ejecucion lo
    dejaria sin poder afirmar que alguien la usa.
    """
    paso = next_step(consecutive)
    if paso is SilenceStep.ASK:
        return SilencePrompt(
            step=paso, copy_key=STILL_THERE, text=copy_api.t(STILL_THERE, locale=language)
        )
    if paso is SilenceStep.OFFER:
        return SilencePrompt(step=paso, copy_key=OFFER, text=copy_api.t(OFFER, locale=language))
    if paso is SilenceStep.FAREWELL:
        return SilencePrompt(
            step=paso, copy_key=FAREWELL, text=copy_api.t(FAREWELL, locale=language)
        )
    return None


__all__ = [
    "DEFAULT_TOLERANCE",
    "FAREWELL",
    "HOLD_TOLERANCE",
    "OFFER",
    "PELDANOS",
    "STILL_THERE",
    "SilencePrompt",
    "SilenceStep",
    "next_step",
    "prompt_for",
]
