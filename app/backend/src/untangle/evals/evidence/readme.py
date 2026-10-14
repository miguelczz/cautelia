"""Las dos secciones del README que se generan solas (U22, US4.1, BR4.1, BR4.2).

Las dos secciones tienen cada una su fuente, y son dos porque una no puede traer
el dato de la otra (FD-U22-10):

- "Evaluation report" sale de la **linea base vigente**, por el mismo camino que el
  panel de cifras: `build_snapshot`. Un segundo lector de la linea base seria un
  segundo esquema que un dia diverge.
- "Como falla" sale del **resumen de la ultima corrida completa**. No de la linea
  base: esa es una corrida verde, y leerla dejaria la seccion diciendo siempre
  "no case failed".

Este modulo es **puro**: recibe el texto del README, la linea base y el resumen, y
devuelve texto o problemas. Quien lee y escribe el archivo es `untangle.workspace.readme_check`.

**Que se compara.** Solo lo que hay entre las marcas de cada seccion. Las seis
secciones narrativas las escribe Miguel y un chequeo que las exigiera se pondria
rojo por trabajo que no es de esta unidad (FD-U22-9).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum

from untangle.evals.evidence.models import (
    Figure,
    FigureKey,
    FigureSource,
    FigureState,
    LatencyMeasure,
    LatencyReading,
    Measurement,
    MetricsSnapshot,
    NotMeasuredCause,
)
from untangle.evals.evidence.snapshot import LANGUAGES, build_snapshot
from untangle.evals.gates.models import Baseline, LastRunDigest
from untangle.evals.latency_summary import MIN_TURNS_PER_LANGUAGE
from untangle.evals.models import CaseStatus, RootCause
from untangle.evals.models import NotMeasuredCause as CaseNotMeasuredCause


class Section(StrEnum):
    """Las dos secciones generadas. Lista cerrada: el mensaje del chequeo las nombra."""

    HOW_IT_FAILS = "how-it-fails"
    EVALUATION_REPORT = "evaluation-report"


#: El encabezado de segundo nivel de cada una, tal como lo fija AC4.1.1 y AC4.1.2.
HEADINGS: dict[Section, str] = {
    Section.HOW_IT_FAILS: "How it fails",
    Section.EVALUATION_REPORT: "Evaluation report",
}

COMMAND = "mise run readme:gen"

_AVISO = (
    f"_Generated from the current baseline and the last full run by `{COMMAND}`. "
    "Do not edit by hand: `mise run readme:check` fails when this differs from what "
    "they produce._"
)

#: La frase de cada causa de "no medida". Cerrada: la prueba comprueba que no falta ninguna.
NOT_MEASURED_TEXT: dict[NotMeasuredCause, str] = {
    NotMeasuredCause.NO_BASELINE: "no baseline has been published yet",
    NotMeasuredCause.CRITERION_ABSENT: "the baseline does not carry the criterion that produces it",
    NotMeasuredCause.CRITERION_NOT_BUILT: "no criterion measures this yet",
    NotMeasuredCause.MEASURED_PER_MILESTONE: (
        "measured per milestone against real providers, not on every delivery"
    ),
    NotMeasuredCause.NOT_CONNECTED: "not recorded in the baseline; the live panel shows it",
    NotMeasuredCause.LATENCY_NOT_IN_BASELINE: "the published baseline carries no latencies",
    NotMeasuredCause.TOO_FEW_TURNS: "too few turns were measured to publish a reliable figure",
}

#: Por que no se midio un **caso**. Distinta de `NOT_MEASURED_TEXT`, que es la de una
#: cifra: son dos taxonomias cerradas con el mismo nombre en dos paquetes.
CASE_NOT_MEASURED_TEXT: dict[CaseNotMeasuredCause, str] = {
    CaseNotMeasuredCause.PROVIDER_UNAVAILABLE: "provider unavailable",
    CaseNotMeasuredCause.PROVIDER_TIMEOUT: "provider timeout",
    CaseNotMeasuredCause.QUOTA_EXHAUSTED: "quota exhausted",
    CaseNotMeasuredCause.BUDGET_EXHAUSTED: "budget exhausted",
    CaseNotMeasuredCause.RUNNER_TIMEOUT: "runner timeout",
    CaseNotMeasuredCause.PROVIDER_KEY_MISSING: "provider key missing",
    CaseNotMeasuredCause.TARGET_UNAVAILABLE: "no live deployment to run against",
}

ROOT_CAUSE_TEXT: dict[RootCause, str] = {
    RootCause.EXTRACTION: "extraction",
    RootCause.RETRIEVAL: "retrieval",
    RootCause.VERIFICATION: "verification",
    RootCause.RULES: "rules",
    RootCause.STYLE: "style",
    RootCause.LATENCY: "latency",
    RootCause.PROVIDER_ERROR: "provider error",
    RootCause.INFRASTRUCTURE: "infrastructure",
    RootCause.NOT_BUILT: "behavior not built yet",
}

FIGURE_TEXT: dict[FigureKey, str] = {
    FigureKey.COMPLETENESS: "Case completeness",
    FigureKey.CITATION_PRECISION: "Citation precision",
    FigureKey.LATENCY: "Latency",
    FigureKey.COST_PER_CASE: "Cost per case",
    FigureKey.CASES_BY_TENANT: "Cases per insurer",
}

_LANGUAGE_NAME = {"es": "Spanish", "en": "English"}


class MarkersError(ValueError):
    """Al README le faltan las marcas de una seccion generada, o las trae repetidas."""


def begin_marker(section: Section) -> str:
    return f"<!-- generated:{section.value}:begin -->"


def end_marker(section: Section) -> str:
    return f"<!-- generated:{section.value}:end -->"


def _case_list(keys: list[str]) -> str:
    return ", ".join(f"`{clave}`" for clave in sorted(keys))


def render_how_it_fails(digest: LastRunDigest | None) -> str:
    """Los casos que fallan, agrupados por la taxonomia cerrada de causa raiz (BR4.1).

    Nombra los identificadores y cita el commit **y la corrida del resumen**, no los
    de la linea base. Los casos **no medidos** van aparte, cada uno con su causa, y
    nunca se cuentan como fallos: uno dice "esto esta mal" y el otro "no lo se"
    (OBS-U1.3).
    """
    if digest is None:
        return (
            "Not measured: no full evaluation run has been recorded yet, so there is no run "
            "to read failures from. This section fills in when `mise run evals:baseline` "
            "writes the first summary."
        )

    cabecera = (
        f"Last full run `{digest.run_id}`, commit `{digest.commit_sha}`, "
        f"recorded {digest.produced_at.date().isoformat()}."
    )

    fallidos = sorted(c for c, e in digest.case_verdicts.items() if e is CaseStatus.FAILED)
    sin_medir = sorted(c for c, e in digest.case_verdicts.items() if e is CaseStatus.NOT_MEASURED)
    total = len(digest.case_verdicts)

    por_causa: dict[RootCause | None, list[str]] = defaultdict(list)
    for caso in fallidos:
        por_causa[digest.root_causes.get(caso)].append(caso)

    lineas = [cabecera, ""]
    if not fallidos:
        lineas.append(f"No case failed in this run ({total} cases recorded).")
    else:
        lineas.append(f"{len(fallidos)} of {total} cases failed, grouped by root cause:")
        lineas.append("")
        for causa in RootCause:
            if causa in por_causa:
                lineas.append(
                    f"- **{ROOT_CAUSE_TEXT[causa]}** ({len(por_causa[causa])}): "
                    f"{_case_list(por_causa[causa])}"
                )
        if None in por_causa:
            lineas.append(
                f"- **no root cause recorded** ({len(por_causa[None])}): "
                f"{_case_list(por_causa[None])}"
            )

    if sin_medir:
        lineas.extend(
            [
                "",
                f"{len(sin_medir)} cases were not measured, which is not the same as failing:",
                "",
            ]
        )
        lineas.extend(
            f"- `{caso}`: {CASE_NOT_MEASURED_TEXT[digest.not_measured_causes[caso]]}"
            for caso in sin_medir
        )
    return "\n".join(lineas)


def _cell(celda: Measurement) -> str:
    if celda.state is FigureState.MEASURED and celda.value is not None:
        return f"{celda.value * 100:.1f} %"
    # Nunca un cero ni una celda vacia donde lo cierto es "no medida" (BR1.2).
    causa = celda.not_measured_cause
    return f"not measured ({NOT_MEASURED_TEXT[causa]})" if causa else "not measured"


#: De donde sale la latencia del chat y que no incluye. Va en el README porque una cifra de
#: latencia sin decir que mide esta prohibida (P4): el reloj arranca cuando el servidor recibe el
#: mensaje, asi que la red de quien escribe no cuenta.
_CHAT_ENVIRONMENT = (
    "measured in the evaluation run, from the moment the server receives the message "
    "(the visitor's network is not included)"
)


def _duration(ms: int) -> str:
    """Un tiempo como lo dice el panel: milisegundos bajo el segundo, y decimas de segundo.

    En aritmetica entera y redondeando la mitad hacia arriba, igual que la pantalla: asi las dos
    superficies muestran el mismo texto para el mismo tiempo, tambien en los empates.
    """
    if ms < 1000:
        return f"{ms} ms"
    decimas = (ms + 50) // 100
    return f"{decimas // 10}.{decimas % 10} s"


def _reading(lectura: LatencyReading) -> str:
    if lectura.p50_ms is not None and lectura.p95_ms is not None:
        return (
            f"p50 {_duration(lectura.p50_ms)}, p95 {_duration(lectura.p95_ms)}, "
            f"over {lectura.turns} turns"
        )
    if lectura.not_measured_cause is NotMeasuredCause.TOO_FEW_TURNS:
        return (
            f"not measured (only {lectura.turns} turns measured; at least "
            f"{MIN_TURNS_PER_LANGUAGE} are needed)"
        )
    causa = lectura.not_measured_cause
    return f"not measured ({NOT_MEASURED_TEXT[causa]})" if causa else "not measured"


def _latency(medida: LatencyMeasure) -> list[str]:
    """La medida de un canal: una linea, y debajo una por idioma con la corrida de la que sale."""
    cabecera = (
        f"{medida.channel}: `{medida.start.value}` to `{medida.end.value}` on {medida.dataset}, "
        f"{' and '.join(medida.percentiles)}"
    )
    if medida.not_measured_cause is not None:
        return [f"{cabecera}: not measured ({NOT_MEASURED_TEXT[medida.not_measured_cause]})"]
    entorno = f": {_CHAT_ENVIRONMENT}" if medida.channel == "chat" else ""
    lineas = [f"{cabecera}{entorno}"]
    for idioma in LANGUAGES:
        if idioma in medida.by_language:
            lineas.append(f"  - {_LANGUAGE_NAME[idioma]}: {_reading(medida.by_language[idioma])}")
    if medida.source is not None:
        lineas.append(f"  - {_source_line(medida.source)}")
    return lineas


def _source_line(origen: FigureSource) -> str:
    return (
        f"source: baseline `{origen.baseline_id}`, commit `{origen.commit_sha[:7]}`, "
        f"run `{origen.run_id}`, {origen.published_at.date().isoformat()}"
    )


def _figure_lines(figura: Figure) -> list[str]:
    nombre = FIGURE_TEXT[figura.key]
    lineas = [f"- **{nombre}**"]
    if figura.by_language:
        for idioma in LANGUAGES:
            if idioma in figura.by_language:
                lineas.append(f"  - {_LANGUAGE_NAME[idioma]}: {_cell(figura.by_language[idioma])}")
    elif (
        figura.state is FigureState.NOT_MEASURED
        and figura.not_measured_cause
        and figura.key is not FigureKey.LATENCY
    ):
        # La latencia no: la causa de su cifra es la de la voz, y cada canal dice la suya.
        lineas.append(f"  - not measured ({NOT_MEASURED_TEXT[figura.not_measured_cause]})")
    for medida in figura.latency:
        primera, *resto = _latency(medida)
        lineas.append(f"  - {primera}")
        lineas.extend(f"  {linea}" for linea in resto)
    if figura.source is not None:
        lineas.append(f"  - {_source_line(figura.source)}")
    return lineas


def render_evaluation_report(snapshot: MetricsSnapshot) -> str:
    """Las cinco cifras, por idioma lado a lado, con su fecha y su commit (BR1.3, BR1.4)."""
    if snapshot.baseline_id is None or snapshot.commit_sha is None or snapshot.published_at is None:
        cabecera = (
            "Not measured: no baseline has been published yet, so none of the five figures "
            "has a date or a commit to cite."
        )
    else:
        cabecera = (
            f"Baseline `{snapshot.baseline_id}`, commit `{snapshot.commit_sha[:7]}`, "
            f"published {snapshot.published_at.date().isoformat()}."
        )
    orden = {clave: i for i, clave in enumerate(FigureKey)}
    lineas = [cabecera, ""]
    for figura in sorted(snapshot.figures, key=lambda f: orden[f.key]):
        lineas.extend(_figure_lines(figura))
    return "\n".join(lineas)


def render_sections(baseline: Baseline | None, digest: LastRunDigest | None) -> dict[Section, str]:
    """Lo que producen sus fuentes para cada seccion, sin marcas.

    Las cifras salen de la linea base y los fallos del resumen (FD-U22-10).
    """
    return {
        Section.HOW_IT_FAILS: render_how_it_fails(digest),
        Section.EVALUATION_REPORT: render_evaluation_report(build_snapshot(baseline)),
    }


def _block(section: Section, cuerpo: str) -> str:
    return f"{begin_marker(section)}\n{_AVISO}\n\n{cuerpo}\n{end_marker(section)}"


def _pattern(section: Section) -> re.Pattern[str]:
    return re.compile(
        f"{re.escape(begin_marker(section))}.*?{re.escape(end_marker(section))}", re.S
    )


@dataclass(frozen=True)
class Problem:
    """Un desacuerdo, con la seccion que lo tiene (BR4.2)."""

    section: Section
    detail: str

    def __str__(self) -> str:
        return f"README.md, section '{HEADINGS[self.section]}': {self.detail}"


def published(text: str, section: Section) -> str | None:
    """Lo que el README trae entre las marcas de la seccion, o `None` si faltan."""
    coincidencias = [m.group(0) for m in _pattern(section).finditer(text)]
    if len(coincidencias) != 1:
        return None
    return coincidencias[0]


def regenerate(text: str, baseline: Baseline | None, digest: LastRunDigest | None) -> str:
    """El README con las dos secciones reescritas. No toca nada fuera de las marcas."""
    resultado = text
    for seccion, cuerpo in render_sections(baseline, digest).items():
        bloque = _block(seccion, cuerpo)
        actual = published(resultado, seccion)
        if actual is None:
            msg = (
                f"la seccion '{HEADINGS[seccion]}' no tiene sus marcas "
                f"`{begin_marker(seccion)}` y `{end_marker(seccion)}` exactamente una vez; "
                "sin ellas no se sabe que reemplazar"
            )
            raise MarkersError(msg)
        resultado = resultado.replace(actual, bloque, 1)
    return resultado


def check(text: str, baseline: Baseline | None, digest: LastRunDigest | None) -> list[Problem]:
    """Lo publicado contra lo que producen sus fuentes. Vacio cuando coinciden (BR4.2)."""
    problemas: list[Problem] = []
    for seccion, cuerpo in render_sections(baseline, digest).items():
        esperado = _block(seccion, cuerpo)
        actual = published(text, seccion)
        if actual is None:
            problemas.append(
                Problem(
                    seccion,
                    f"missing its markers `{begin_marker(seccion)}` / `{end_marker(seccion)}` "
                    "(exactly one pair is required)",
                )
            )
        elif actual != esperado:
            problemas.append(
                Problem(
                    seccion,
                    "differs from what the current baseline and the last full run produce.\n"
                    f"--- they produce ---\n{esperado}\n"
                    f"--- the README says ---\n{actual}",
                )
            )
    return problemas
