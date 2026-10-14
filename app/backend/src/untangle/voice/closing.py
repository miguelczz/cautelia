"""La cola del cierre por voz: que sigue, el numero de caso y la despedida.

AC1.23.4 pide tres cosas al cerrar un reporte completo: un resumen en tres
frases, que sigue, y el numero de caso digito a digito.

**El resumen no esta aqui, y esa fue una correccion al cablearlo.** Lo arma el
nodo de captura de U11 con los valores del caso, que en el grafo estan en claro;
en la base estan **sellados**, asi que armarlo aqui habria obligado al canal de
voz a descifrar campos del caso solo para leerlos en voz alta. Un segundo sitio
que descifra es un segundo sitio que puede dejar de redactar.

Lo que si es de la voz son las otras dos frases y la despedida, porque las tres
dependen de como suena un numero y de que el enlace publico admite una llamada al
dia.

**La despedida no invita a volver a llamar.** La guia de voz tiene dos variantes
y esta es la que vale aqui: ofrecer otra llamada seria prometer lo que no se
puede cumplir.
"""

from __future__ import annotations

from datetime import timedelta

from untangle.base import Locale
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.voice import case_number

NEXT_STEP = CopyKey("voice.closing.next_step")
#: Las reglas cerraron el caso solas (US1.17): no necesita ajustador, y el enlace aparece en la
#: pantalla. Es la misma clave que `orchestration.closing_plan.VOICE_REGISTERED_PHRASE`: lo que
#: queda escrito en la transcripcion es lo que se dijo.
REGISTERED = CopyKey("voice.closing.registered")
#: La despedida llego antes que el resultado de las reglas: no promete ni un cierre ni un
#: ajustador, y dice donde se vera.
PENDING = CopyKey("voice.closing.pending")
FAREWELL = CopyKey("voice.closing.farewell")
#: Cuanto espera la despedida el resultado de las reglas, y cada cuanto lo mira (US1.17).
#:
#: **Es el paso de despedida, no el turno.** El turno de voz no hace trabajo de reglas ni de
#: cumplimiento --corre en el fondo, como en el chat-- y su presupuesto de latencia no cuenta
#: esto: la persona ya oyo "listo, ya tengo lo necesario" y la despedida va despues, con la
#: llamada a punto de terminar. Es una **lectura** del estado del caso, no una espera de la
#: cadena. Si las reglas no terminaron en este tiempo, la despedida es la neutral (`PENDING`) y
#: el resultado aparece en la pantalla; mas espera que esto es silencio al telefono.
RESULT_WAIT = timedelta(milliseconds=1500)
RESULT_POLL_SECONDS = 0.1

#: Se acabo el tiempo de la llamada y el reporte no quedo completo (2026-10-11).
TIME_IS_UP = CopyKey("voice.closing.time_is_up")
#: La persona pidio dejarlo guardado: dice hasta cuando puede retomarlo (2026-10-11).
SAVED = CopyKey("voice.closing.saved")
#: La ventana de retoma, dicha: "un minuto" o "quince minutos". Dos claves y no una con
#: plural dentro, porque la ventana minima que admite la configuracion es de un minuto.
DURATION_MINUTE = CopyKey("voice.duration.minute")
DURATION_MINUTES = CopyKey("voice.duration.minutes")


def build(*, number: str, insurer: str, language: Locale) -> str:
    """Lo que la agente dice despues del resumen del grafo, en orden."""
    return " ".join(
        [
            copy_api.t(NEXT_STEP, locale=language),
            case_number.say(number, insurer=insurer, language=language),
            copy_api.t(FAREWELL, locale=language),
        ]
    )


def build_registered(*, number: str, insurer: str, language: Locale) -> str:
    """La despedida de un reporte que las reglas cerraron solas: registrado, numero y adios."""
    return " ".join(
        [
            copy_api.t(REGISTERED, locale=language),
            case_number.say(number, insurer=insurer, language=language),
            copy_api.t(FAREWELL, locale=language),
        ]
    )


def build_pending(*, number: str, insurer: str, language: Locale) -> str:
    """La despedida cuando el resultado todavia no esta: guardado, numero y adios."""
    return " ".join(
        [
            copy_api.t(PENDING, locale=language),
            case_number.say(number, insurer=insurer, language=language),
            copy_api.t(FAREWELL, locale=language),
        ]
    )


def _con_numero(partes: list[str], *, number: str | None, insurer: str, language: Locale) -> str:
    """Las frases, el numero de caso si lo hay, y la despedida."""
    if number is not None:
        partes.append(case_number.say(number, insurer=insurer, language=language))
    partes.append(copy_api.t(FAREWELL, locale=language))
    return " ".join(partes)


def build_after_handoff(*, number: str | None, insurer: str, language: Locale) -> str:
    """Lo que sigue a "le paso tu caso a un ajustador": el numero y la despedida.

    La frase de derivacion ya dijo que sigue, y no se repite.
    """
    return _con_numero([], number=number, insurer=insurer, language=language)


def build_time_is_up(*, number: str | None, insurer: str, language: Locale) -> str:
    """El cierre cuando la llamada llega a su limite: no corta en seco."""
    return _con_numero(
        [copy_api.t(TIME_IS_UP, locale=language)],
        number=number,
        insurer=insurer,
        language=language,
    )


def _ventana_dicha(window: timedelta, *, language: Locale) -> str:
    """La ventana en minutos enteros, hacia abajo: nunca se promete mas de lo que hay.

    La configuracion no admite menos de un minuto (`resume_window_seconds >= 60`), asi
    que el resultado nunca es cero.
    """
    minutos = int(window.total_seconds() // 60)
    if minutos == 1:
        return copy_api.t(DURATION_MINUTE, locale=language)
    return copy_api.t(DURATION_MINUTES, locale=language, minutes=str(minutos))


def build_saved(*, window: timedelta, language: Locale) -> str:
    """Lo que se dice al dejar el caso guardado: que queda, hasta cuando, y adios.

    La ventana es la de retoma que la llamada deja abierta al terminar con este motivo
    (`resume_window_seconds` de la aseguradora), no un plazo escrito aqui.
    """
    return " ".join(
        [
            copy_api.t(SAVED, locale=language, window=_ventana_dicha(window, language=language)),
            copy_api.t(FAREWELL, locale=language),
        ]
    )


__all__ = [
    "DURATION_MINUTE",
    "DURATION_MINUTES",
    "FAREWELL",
    "NEXT_STEP",
    "PENDING",
    "REGISTERED",
    "RESULT_POLL_SECONDS",
    "RESULT_WAIT",
    "SAVED",
    "TIME_IS_UP",
    "build",
    "build_after_handoff",
    "build_pending",
    "build_registered",
    "build_saved",
    "build_time_is_up",
]
