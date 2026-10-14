"""Los controles del turno sobre lo que dijo la persona (BR2.1, BR2.4, BR3.1, BR3.2).

Tres senales, de reglas y en los dos idiomas: la peticion de persona, la pregunta
de identidad y la emergencia. Cada una mira el turno **ya redactado** por U3 y
normalizado, con los patrones de los dos idiomas a la vez (BR1.3): una peticion
dicha a medias en el otro idioma es una peticion (RT-15).

Este modulo solo **detecta**. Que hacer con cada senal es del runtime (U12):
emergencia, la indicacion antes de cualquier dato (BR3.1); pregunta de
identidad, la frase fija y la conversacion sigue (BR2.4); peticion de persona,
la derivacion en el turno siguiente con prioridad alta (BR2.2).

## La negacion de la emergencia apaga solo lo que toca (BR3.2)

Enmendada el 2026-09-21. Una negacion ("todos estamos bien", "fue un
golpecito") apaga una coincidencia de emergencia **solo si se solapan**: en
«nadie esta sangrando», «sangrando» esta dentro de la negacion y no cuenta. En
«todos estamos bien menos mi hija, que no reacciona» la negacion y el herido
grave estan en sitios distintos de la frase, el herido queda nombrado, y la
emergencia gana. Una falsa alarma cuesta una frase de mas; una emergencia
apagada puede costar una vida.

**Si la biblioteca no se puede cargar, esto levanta**, al reves que la guardia:
no hay una salida segura que inventar para una senal --ni "si" ni "no" lo son--
y el ejecutor comun del runtime es quien aplica la politica de fallo (convencion
8b del equipo). La biblioteca se valida al arrancar, asi que en el turno ese
fallo no deberia existir.
"""

from __future__ import annotations

from untangle.base import Frozen
from untangle.compliance.controls.normalization import normalize
from untangle.compliance.controls.patterns import CompiledPattern, PatternLibrary


class TurnSignals(Frozen):
    """Las tres senales de los controles del turno (`entities.md`, TurnSignals)."""

    human_request: bool
    identity_question: bool
    emergency: bool


def _primera(patrones: tuple[CompiledPattern, ...], texto: str) -> str | None:
    """El identificador del primer patron que coincide, o nada."""
    for patron in patrones:
        if patron.regex.search(texto):
            return patron.id
    return None


def _tramos(patrones: tuple[CompiledPattern, ...], texto: str) -> list[tuple[int, int]]:
    """Donde coincide cada patron, todas las veces."""
    return [m.span() for patron in patrones for m in patron.regex.finditer(texto)]


def _se_tocan(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def emergency_match(text: str, *, library: PatternLibrary) -> str | None:
    """El patron de emergencia que queda en pie tras las negaciones, o nada (BR3.2).

    Una coincidencia cuenta si **ninguna** negacion la toca. Devolver el patron y
    no solo si/no deja nombrar en la prueba que regla levanto la senal.
    """
    texto = normalize(text)
    negaciones = _tramos(library.emergency_negations, texto)
    for patron in library.emergency:
        for coincidencia in patron.regex.finditer(texto):
            tramo = coincidencia.span()
            if not any(_se_tocan(tramo, negacion) for negacion in negaciones):
                return patron.id
    return None


def human_request_match(text: str, *, library: PatternLibrary) -> str | None:
    """El patron de peticion de persona que coincide, o nada (BR2.1)."""
    return _primera(library.human_request, normalize(text))


def identity_question_match(text: str, *, library: PatternLibrary) -> str | None:
    """El patron de pregunta de identidad que coincide, o nada (BR2.4)."""
    return _primera(library.identity_question, normalize(text))


def read_signals(text: str, *, library: PatternLibrary) -> TurnSignals:
    """Las tres senales de un turno de la persona."""
    return TurnSignals(
        human_request=human_request_match(text, library=library) is not None,
        identity_question=identity_question_match(text, library=library) is not None,
        emergency=emergency_match(text, library=library) is not None,
    )
