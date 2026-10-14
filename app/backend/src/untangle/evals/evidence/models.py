"""Las cinco cifras del panel y su vista de lectura (U22, entities.md).

`MetricsSnapshot` no se guarda en ninguna parte: es como se lee la linea base
vigente. Si el panel guardara su propia copia habria dos verdades, y un dia
discreparian (FD-U22-1).

Los invariantes estan en el tipo y no en quien lo construye, porque son los que
protegen el principio: una cifra sin medir **no puede** construirse sin su causa
ni con un valor, asi que un cero donde lo cierto es "no medida" (BR1.2) es
imposible de escribir y no solo improbable.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from untangle.base import Frozen, Locale
from untangle.evals.latency_summary import MIN_TURNS_PER_LANGUAGE


class FigureKey(StrEnum):
    """Las cinco cifras (AC4.16.1). Lista cerrada."""

    COMPLETENESS = "completeness"
    CITATION_PRECISION = "citation_precision"
    LATENCY = "latency"
    COST_PER_CASE = "cost_per_case"
    CASES_BY_TENANT = "cases_by_tenant"


class FigureState(StrEnum):
    MEASURED = "measured"
    NOT_MEASURED = "not_measured"


class NotMeasuredCause(StrEnum):
    """Por que una cifra no se midio. Cerrada: cada valor tiene su frase en el catalogo."""

    #: Todavia no se ha publicado ninguna linea base.
    NO_BASELINE = "no_baseline"
    #: Hay linea base, pero no trae el criterio que produce esta cifra.
    CRITERION_ABSENT = "criterion_absent"
    #: **Todavia no existe ningun criterio que mida esto.** No es que la linea base
    #: no lo traiga: es que nadie lo ha construido, asi que ninguna linea base
    #: podria traerlo. Distinguirlas importa porque se arreglan en sitios
    #: distintos: una se arregla publicando una linea base y la otra cableando el
    #: conductor que mide el criterio.
    CRITERION_NOT_BUILT = "criterion_not_built"
    #: Se mide por hito contra proveedores de verdad, no en cada entrega.
    MEASURED_PER_MILESTONE = "measured_per_milestone"
    #: La fuente existe pero esta cifra todavia no esta conectada al panel.
    NOT_CONNECTED = "not_connected"
    #: La linea base publicada existe pero no trae la seccion de latencias: se publico antes de
    #: que la corrida las midiera. Se arregla publicando una linea base nueva, no construyendo
    #: nada.
    LATENCY_NOT_IN_BASELINE = "latency_not_in_baseline"
    #: Se midieron menos turnos que los que hacen falta para publicar una latencia
    #: (`latency_summary.MIN_TURNS_PER_LANGUAGE`): con pocos, el «p95» es el peor turno y
    #: decir «95 de cada 100» seria afirmar otra cosa. El recuento se publica al lado.
    TOO_FEW_TURNS = "too_few_turns"


class LatencyEvent(StrEnum):
    """Los extremos entre los que se mide una latencia (AC4.16.3)."""

    SPEECH_END = "speech_end"
    FIRST_AUDIO = "first_audio"
    MESSAGE_SENT = "message_sent"
    FIRST_WORD = "first_word"


class Measurement(Frozen):
    """Una celda: el valor de una cifra en un idioma, o su ausencia explicada."""

    state: FigureState
    value: float | None = None
    not_measured_cause: NotMeasuredCause | None = None

    @model_validator(mode="after")
    def _medida_lleva_valor_y_no_medida_lleva_causa(self) -> Self:
        if self.state is FigureState.MEASURED:
            if self.value is None or self.not_measured_cause is not None:
                msg = "una celda medida lleva su valor y ninguna causa de no medida (BR1.2)"
                raise ValueError(msg)
        elif self.value is not None or self.not_measured_cause is None:
            msg = (
                "una celda no medida lleva su causa y ningun valor: un cero "
                "afirmaria una medicion que no ocurrio (BR1.2)"
            )
            raise ValueError(msg)
        return self


def measured(value: float) -> Measurement:
    return Measurement(state=FigureState.MEASURED, value=value)


def not_measured(cause: NotMeasuredCause) -> Measurement:
    return Measurement(state=FigureState.NOT_MEASURED, not_measured_cause=cause)


class FigureSource(Frozen):
    """De donde sale una cifra medida: fecha, commit y corrida (BR1.3)."""

    baseline_id: str = Field(min_length=1)
    published_at: datetime
    commit_sha: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    #: Solo cuando hay adonde llevar: un enlace a algo que no existe es peor que
    #: ninguno (BR2.2). El repositorio es privado hasta la pasada de publicacion.
    run_url: str | None = None


class LatencyReading(Frozen):
    """La latencia de un canal en un idioma: p50 y p95 con su recuento, o su ausencia explicada.

    Lleva el recuento de turnos **aunque este medida y aunque no**: un p95 sin saber sobre
    cuantos turnos sale es una cifra que no se puede juzgar, y el recuento de una no medida
    dice cuanto falto. Los tiempos son milisegundos enteros, de turnos que de verdad ocurrieron
    (percentil por rango mas proximo, sin interpolar).
    """

    state: FigureState
    p50_ms: int | None = Field(default=None, ge=0)
    p95_ms: int | None = Field(default=None, ge=0)
    turns: int = Field(default=0, ge=0)
    not_measured_cause: NotMeasuredCause | None = None

    @model_validator(mode="after")
    def _medida_lleva_sus_dos_percentiles_y_no_medida_lleva_causa(self) -> Self:
        if self.state is FigureState.MEASURED:
            if self.p50_ms is None or self.p95_ms is None or self.not_measured_cause is not None:
                msg = "una latencia medida lleva su p50 y su p95 y ninguna causa de no medida"
                raise ValueError(msg)
            if self.p50_ms > self.p95_ms:
                msg = f"el p50 ({self.p50_ms} ms) no puede superar al p95 ({self.p95_ms} ms)"
                raise ValueError(msg)
            if self.turns < MIN_TURNS_PER_LANGUAGE:
                msg = (
                    f"una latencia sobre {self.turns} turno(s) no se publica como medida: con "
                    f"menos de {MIN_TURNS_PER_LANGUAGE} el p95 es el peor turno"
                )
                raise ValueError(msg)
        elif self.p50_ms is not None or self.p95_ms is not None or self.not_measured_cause is None:
            msg = (
                "una latencia no medida lleva su causa y ningun tiempo: un cero o un p95 con "
                "pocos turnos afirmaria una medicion que no ocurrio"
            )
            raise ValueError(msg)
        return self


def latency_measured(*, p50_ms: int, p95_ms: int, turns: int) -> LatencyReading:
    return LatencyReading(state=FigureState.MEASURED, p50_ms=p50_ms, p95_ms=p95_ms, turns=turns)


def latency_not_measured(cause: NotMeasuredCause, *, turns: int = 0) -> LatencyReading:
    return LatencyReading(state=FigureState.NOT_MEASURED, turns=turns, not_measured_cause=cause)


class LatencyMeasure(Frozen):
    """Entre que eventos, sobre que conjunto y con que percentiles se mide (BR1.5).

    **Lleva su propia causa de no medida**, y no es un adorno: las dos latencias no
    estan sin medir por lo mismo. La de la voz se mide por hito contra proveedores
    de verdad, que es una decision; la del chat sale de la corrida de evaluaciones con
    conversaciones y de ninguna otra parte, asi que sin esa corrida en la linea base --o
    sin linea base-- esta sin medir hasta que alguien publique una. Una sola causa para las
    dos diria "por hito" de algo que nadie ha corrido, y mandaria a esperar un hito en vez de
    a publicar una linea base.

    **O una causa para el canal entero o una lectura por idioma, nunca las dos.** Con
    `not_measured_cause` no hay lecturas (el canal no tiene nada que decir); con
    `by_language` cada idioma esta medido o explica por que no, y la medida cita la linea base
    de la que salio (`source`). No hay lectura combinada: el mapa es por idioma.
    """

    channel: str = Field(pattern=r"^(voice|chat)$")
    start: LatencyEvent
    end: LatencyEvent
    dataset: str = Field(min_length=1)
    percentiles: tuple[str, ...] = Field(min_length=2)
    not_measured_cause: NotMeasuredCause | None = None
    by_language: dict[Locale, LatencyReading] = Field(default_factory=dict)
    source: FigureSource | None = None

    @model_validator(mode="after")
    def _p50_y_p95(self) -> Self:
        if not {"p50", "p95"} <= set(self.percentiles):
            msg = "una latencia se publica con p50 y p95 (BR1.5)"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _una_causa_o_lecturas_con_su_origen(self) -> Self:
        if self.not_measured_cause is not None and (self.by_language or self.source is not None):
            msg = "una latencia sin medir en el canal entero no trae lecturas ni origen"
            raise ValueError(msg)
        if self.by_language and self.source is None:
            msg = "las lecturas de una latencia citan la linea base de la que salen (BR1.3)"
            raise ValueError(msg)
        return self


class Figure(Frozen):
    """Una de las cinco cifras.

    `state` es `measured` solo si **todas** sus celdas lo estan. `by_language`
    nunca lleva una entrada combinada (BR1.4): es un mapa por idioma, y una cifra
    sin idioma lo trae vacio.
    """

    key: FigureKey
    state: FigureState
    not_measured_cause: NotMeasuredCause | None = None
    by_language: dict[Locale, Measurement] = Field(default_factory=dict)
    latency: tuple[LatencyMeasure, ...] = ()
    source: FigureSource | None = None

    @model_validator(mode="after")
    def _coherente(self) -> Self:
        if self.state is FigureState.NOT_MEASURED:
            if self.not_measured_cause is None:
                msg = f"la cifra '{self.key}' no medida no trae su causa (BR1.2)"
                raise ValueError(msg)
            return self
        if self.not_measured_cause is not None or not self.by_language:
            msg = f"la cifra '{self.key}' medida trae causa o ningun valor"
            raise ValueError(msg)
        if any(m.state is not FigureState.MEASURED for m in self.by_language.values()):
            msg = f"la cifra '{self.key}' esta medida pero alguna celda no lo esta"
            raise ValueError(msg)
        if self.source is None:
            msg = f"la cifra '{self.key}' medida no trae fecha, commit y corrida (BR1.3)"
            raise ValueError(msg)
        return self


class MetricsSnapshot(Frozen):
    """La vista de lectura de la linea base vigente (entities.md)."""

    baseline_id: str | None = None
    commit_sha: str | None = None
    published_at: datetime | None = None
    run_id: str | None = None
    figures: tuple[Figure, ...]

    @model_validator(mode="after")
    def _las_cinco_y_solo_las_cinco(self) -> Self:
        claves = [f.key for f in self.figures]
        if sorted(claves) != sorted(FigureKey):
            msg = "el panel lleva exactamente las cinco cifras, una vez cada una (AC4.16.1)"
            raise ValueError(msg)
        return self
