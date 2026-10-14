"""El resumen de la latencia de un canal en una corrida: p50 y p95 por idioma, con su recuento.

Es lo que viaja del conductor a la linea base y de ahi al panel y al README. **Nunca hay un
promedio de los dos idiomas**: el tipo tiene un campo por idioma y ninguno mas, igual que
`report.ByLanguage`, asi que publicar uno combinado seria escribir un campo que no existe.

**Percentil por rango mas proximo, sin interpolar.** El p95 de la corrida es un tiempo que
un turno de verdad tardo, no un valor entre dos. Con interpolacion la cifra publicada podria
ser una latencia que nadie vivio, y para un tiempo de espera eso no tiene sentido.

**Con pocos turnos un p95 engana.** Por rango mas proximo el p95 de `n` turnos es el que ocupa
la posicion `ceil(0.95 * n)`: con 19 turnos o menos esa posicion es la ultima, o sea que el
«p95» seria el peor turno y se publicaria como «95 de cada 100». Con 20 es el 19 de 20 y por
fin deja uno por encima. De ahi `MIN_TURNS_PER_LANGUAGE`. No es un umbral de calidad --la
latencia no es una compuerta-- sino la cantidad bajo la cual la cifra dice otra cosa de la que
afirma.

El resumen guarda lo que se midio aunque sea poco (`turns`, `p50_ms`, `p95_ms`); **quien decide
si se publica es `LatencySummary.publishable`**, y es el unico sitio donde se decide: el panel
y el README lo leen por ahi. Subir el minimo mas adelante no invalida una linea base ya
publicada: sus idiomas con pocos turnos pasan a «no medida» al leerla.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Self

from pydantic import Field, model_validator

from untangle.base import Frozen
from untangle.evals.models import ChatTurnLatency

#: Turnos que hacen falta, por idioma, para publicar una latencia. Ver el docstring del modulo:
#: es el primer `n` en que el p95 por rango mas proximo deja de ser el maximo.
MIN_TURNS_PER_LANGUAGE = 20

#: Los percentiles que se publican (`LatencyMeasure.percentiles` los nombra).
_P50 = 50
_P95 = 95


class LatencySummary(Frozen):
    """La latencia de un canal en un idioma: cuantos turnos y que percentiles."""

    #: Turnos de la persona que el canal acepto y a los que la agente contesto con texto.
    turns: int = Field(default=0, ge=0)
    p50_ms: int | None = Field(default=None, ge=0)
    p95_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _los_percentiles_existen_si_y_solo_si_hay_turnos(self) -> Self:
        hay_valores = self.p50_ms is not None and self.p95_ms is not None
        faltan_todos = self.p50_ms is None and self.p95_ms is None
        if self.turns > 0 and not hay_valores:
            msg = f"{self.turns} turno(s) medidos sin sus dos percentiles"
            raise ValueError(msg)
        if self.turns == 0 and not faltan_todos:
            msg = "un percentil sin ningun turno medido es un valor inventado"
            raise ValueError(msg)
        if self.p50_ms is not None and self.p95_ms is not None and self.p50_ms > self.p95_ms:
            msg = f"el p50 ({self.p50_ms} ms) no puede superar al p95 ({self.p95_ms} ms)"
            raise ValueError(msg)
        return self

    @property
    def publishable(self) -> bool:
        """Si hay turnos suficientes para decir «95 de cada 100» sin que sea el peor turno."""
        return self.turns >= MIN_TURNS_PER_LANGUAGE


class ChannelLatency(Frozen):
    """La latencia de un canal en una corrida, por idioma, con los conjuntos que la dieron.

    Sin tercer campo: no hay donde escribir un promedio de los dos idiomas.
    """

    #: Los conjuntos de datos de los casos que aportaron turnos, ordenados. Lo que se publica
    #: junto a la cifra para que diga sobre que conversaciones se midio.
    datasets: tuple[str, ...] = ()
    es: LatencySummary = LatencySummary()
    en: LatencySummary = LatencySummary()


def _rango_mas_proximo(ordenados: list[int], porcentaje: int) -> int:
    """El valor que ocupa la posicion `ceil(porcentaje * n / 100)`, con aritmetica entera."""
    posicion = -(-porcentaje * len(ordenados) // 100)
    return ordenados[posicion - 1]


def summarize(valores_ms: Iterable[int]) -> LatencySummary:
    """p50 y p95 por rango mas proximo de unos tiempos, con su recuento."""
    ordenados = sorted(valores_ms)
    if not ordenados:
        return LatencySummary()
    return LatencySummary(
        turns=len(ordenados),
        p50_ms=_rango_mas_proximo(ordenados, _P50),
        p95_ms=_rango_mas_proximo(ordenados, _P95),
    )


def channel_latency(*, turns: Iterable[ChatTurnLatency], datasets: Iterable[str]) -> ChannelLatency:
    """Los turnos de una corrida, separados por el idioma en que se atendieron."""
    medidos = list(turns)
    return ChannelLatency(
        datasets=tuple(sorted(set(datasets))),
        es=summarize(t.first_word_ms for t in medidos if t.language == "es"),
        en=summarize(t.first_word_ms for t in medidos if t.language == "en"),
    )
