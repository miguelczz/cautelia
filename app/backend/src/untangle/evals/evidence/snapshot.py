"""Construir las cinco cifras desde la linea base vigente (U22, BR1.1, BR1.2).

Las cinco salen de la linea base **versionada** y de nada mas: el reporte de una
corrida vive en `tmp/` y no tiene commit que citar. Este modulo no toca la base
de datos: el costo por caso y los casos por aseguradora los conecta la tanda 2,
y mientras tanto salen "no medidas" con su causa, nunca en cero.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from untangle.base import Locale
from untangle.evals.evidence.models import (
    Figure,
    FigureKey,
    FigureSource,
    FigureState,
    LatencyEvent,
    LatencyMeasure,
    LatencyReading,
    Measurement,
    MetricsSnapshot,
    NotMeasuredCause,
    latency_measured,
    latency_not_measured,
    measured,
    not_measured,
)
from untangle.evals.gates.loading import load_current_baseline
from untangle.evals.gates.models import Baseline
from untangle.evals.latency_summary import LatencySummary
from untangle.evals.models import Channel

#: Que criterio de la linea base produce cada cifra medible.
#:
#: **Hoy ninguno de los dos existe, y por eso los dos son nulos.** Se comprobo
#: sobre los casos de `app/evals/cases/`: ningun criterio mide hoy la completitud
#: del caso ni la precision de citacion. Los de citacion (DS-3) declaran
#: `expected_verdicts: {}` a proposito, porque el verificador de citas todavia no
#: tiene conductor de evaluaciones.
#:
#: La primera version de este modulo puso aqui dos nombres inventados,
#: `field_extraction` y `citation_precision`, y la consecuencia era silenciosa: las
#: dos cifras se quedaban "no medidas" con la causa equivocada --"la linea base no
#: trae el criterio"-- para siempre, y eso se lee como un problema de la linea base
#: y no como lo que es. Un nombre supuesto es peor que un nulo: el nulo dice la
#: verdad y obliga a volver aqui.
#:
#: **Cuando U21 cablee el conductor que mide cada una, se escribe su nombre aqui**,
#: y la cifra empieza a llenarse sin tocar nada mas.
CRITERIA: Mapping[FigureKey, str | None] = {
    FigureKey.COMPLETENESS: None,
    FigureKey.CITATION_PRECISION: None,
}

LANGUAGES: tuple[Locale, ...] = ("es", "en")

#: La voz se mide por hito contra proveedores de verdad (PRD 11.2): el golden set de audio.
#: Una decision y no un pendiente: gasta del tope, asi que no corre en cada entrega.
VOICE_LATENCY = LatencyMeasure(
    channel="voice",
    start=LatencyEvent.SPEECH_END,
    end=LatencyEvent.FIRST_AUDIO,
    dataset="DS-5",
    percentiles=("p50", "p95"),
    not_measured_cause=NotMeasuredCause.MEASURED_PER_MILESTONE,
)

#: El conjunto que el PRD nombra para la latencia del chat. **Solo se cita cuando no hay nada
#: medido**: una latencia medida cita los conjuntos de los casos que de verdad aportaron
#: turnos (`ChannelLatency.datasets`), que son los de las conversaciones del chat de la corrida
#: completa --hoy DS-2, DS-4 y DS-6, porque DS-3 no conversa-- y no necesariamente este.
NOMINAL_CHAT_DATASET = "DS-2"

RunUrl = Callable[[str], str | None]


def _source(baseline: Baseline, run_url: RunUrl | None) -> FigureSource:
    return FigureSource(
        baseline_id=baseline.baseline_id,
        published_at=baseline.published_at,
        commit_sha=baseline.commit_sha,
        run_id=baseline.run_id,
        run_url=run_url(baseline.run_id) if run_url is not None else None,
    )


def _all_unmeasured(key: FigureKey, cause: NotMeasuredCause, *, by_language: bool) -> Figure:
    celdas: dict[Locale, Measurement] = (
        {idioma: not_measured(cause) for idioma in LANGUAGES} if by_language else {}
    )
    return Figure(
        key=key,
        state=FigureState.NOT_MEASURED,
        not_measured_cause=cause,
        by_language=celdas,
    )


def _reading(resumen: LatencySummary) -> LatencyReading:
    """Una lectura publicable, o la explicacion de por que no, con el recuento al lado."""
    if resumen.publishable and resumen.p50_ms is not None and resumen.p95_ms is not None:
        return latency_measured(p50_ms=resumen.p50_ms, p95_ms=resumen.p95_ms, turns=resumen.turns)
    return latency_not_measured(NotMeasuredCause.TOO_FEW_TURNS, turns=resumen.turns)


def _chat_measure(
    *,
    dataset: str,
    not_measured_cause: NotMeasuredCause | None = None,
    by_language: dict[Locale, LatencyReading] | None = None,
    source: FigureSource | None = None,
) -> LatencyMeasure:
    """La medida del chat: siempre entre los mismos dos eventos y con los mismos percentiles."""
    return LatencyMeasure(
        channel="chat",
        start=LatencyEvent.MESSAGE_SENT,
        end=LatencyEvent.FIRST_WORD,
        dataset=dataset,
        percentiles=("p50", "p95"),
        not_measured_cause=not_measured_cause,
        by_language=by_language or {},
        source=source,
    )


def _chat_latency(baseline: Baseline | None, run_url: RunUrl | None) -> LatencyMeasure:
    """La latencia del chat que trae la linea base, o la causa verdadera de que no la trae.

    Sale de la seccion `latencies` de la linea base y de ninguna otra parte: ni de los eventos
    del registro tecnico ni de la base de produccion. Tres situaciones distintas, cada una con
    su causa porque se arreglan en sitios distintos:

    - sin linea base: se arregla publicando una;
    - con linea base que no trae la seccion (publicada antes de que la corrida las midiera): se
      arregla publicando otra, con una corrida que converse;
    - con la seccion: cada idioma esta medido, o dice que le faltaron turnos y cuantos.
    """
    if baseline is None:
        return _chat_measure(
            dataset=NOMINAL_CHAT_DATASET, not_measured_cause=NotMeasuredCause.NO_BASELINE
        )
    canal = baseline.latencies.get(Channel.CHAT)
    if canal is None:
        return _chat_measure(
            dataset=NOMINAL_CHAT_DATASET,
            not_measured_cause=NotMeasuredCause.LATENCY_NOT_IN_BASELINE,
        )
    return _chat_measure(
        dataset=", ".join(canal.datasets) or NOMINAL_CHAT_DATASET,
        by_language={"es": _reading(canal.es), "en": _reading(canal.en)},
        source=_source(baseline, run_url),
    )


def _latency_figure(baseline: Baseline | None, run_url: RunUrl | None) -> Figure:
    """La cifra de latencias: la de la voz y la del chat, cada una con lo suyo.

    **La cifra entera sigue sin medir mientras la voz lo este**, y su causa --por hito-- es la
    de la voz. Es el resumen de la cifra y no lo que dice el chat: la pantalla y el README leen
    la causa y las lecturas de cada canal, no la de la cifra, y por eso esta no manda a nadie a
    esperar un hito por algo que el chat ya midio.
    """
    return Figure(
        key=FigureKey.LATENCY,
        state=FigureState.NOT_MEASURED,
        not_measured_cause=NotMeasuredCause.MEASURED_PER_MILESTONE,
        latency=(VOICE_LATENCY, _chat_latency(baseline, run_url)),
    )


def _criterion_figure(
    key: FigureKey, criterion: str | None, baseline: Baseline | None, run_url: RunUrl | None
) -> Figure:
    if criterion is None:
        # Antes que la linea base: el que no exista el criterio no depende de que
        # haya linea base, y decir "no hay linea base" cuando tampoco hay criterio
        # manda a arreglar el sitio equivocado.
        return _all_unmeasured(key, NotMeasuredCause.CRITERION_NOT_BUILT, by_language=True)
    if baseline is None:
        return _all_unmeasured(key, NotMeasuredCause.NO_BASELINE, by_language=True)
    tasas = baseline.metrics.get(criterion, {})
    if not tasas:
        return _all_unmeasured(key, NotMeasuredCause.CRITERION_ABSENT, by_language=True)
    celdas = {
        idioma: measured(tasas[idioma])
        if idioma in tasas
        else not_measured(NotMeasuredCause.CRITERION_ABSENT)
        for idioma in LANGUAGES
    }
    todas = all(c.state is FigureState.MEASURED for c in celdas.values())
    return Figure(
        key=key,
        state=FigureState.MEASURED if todas else FigureState.NOT_MEASURED,
        not_measured_cause=None if todas else NotMeasuredCause.CRITERION_ABSENT,
        by_language=celdas,
        source=_source(baseline, run_url) if todas else None,
    )


def build_snapshot(
    baseline: Baseline | None,
    *,
    run_url: RunUrl | None = None,
    criteria: Mapping[FigureKey, str | None] | None = None,
) -> MetricsSnapshot:
    """Las cinco cifras de una linea base (o de ninguna). Pura: no lee archivos.

    `criteria` entra por argumento para que el camino "medida" se pueda probar hoy,
    que es cuando en produccion los dos criterios son nulos. Sin el, la unica forma
    de probarlo seria inventar un nombre en produccion, que es de donde vino el
    defecto que este argumento arregla.
    """
    mapa = criteria if criteria is not None else CRITERIA
    figuras = (
        _criterion_figure(
            FigureKey.COMPLETENESS, mapa.get(FigureKey.COMPLETENESS), baseline, run_url
        ),
        _criterion_figure(
            FigureKey.CITATION_PRECISION, mapa.get(FigureKey.CITATION_PRECISION), baseline, run_url
        ),
        _latency_figure(baseline, run_url),
        _all_unmeasured(FigureKey.COST_PER_CASE, NotMeasuredCause.NOT_CONNECTED, by_language=False),
        _all_unmeasured(
            FigureKey.CASES_BY_TENANT, NotMeasuredCause.NOT_CONNECTED, by_language=False
        ),
    )
    return MetricsSnapshot(
        baseline_id=baseline.baseline_id if baseline else None,
        commit_sha=baseline.commit_sha if baseline else None,
        published_at=baseline.published_at if baseline else None,
        run_id=baseline.run_id if baseline else None,
        figures=figuras,
    )


def current_snapshot(*, run_url: RunUrl | None = None) -> MetricsSnapshot:
    """Lee la linea base vigente versionada y arma las cinco cifras (BR1.1)."""
    return build_snapshot(load_current_baseline(), run_url=run_url)
