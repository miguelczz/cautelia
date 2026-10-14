"""Publica una linea base nueva (F5, BR2.1, AC4.5.4).

Solo por hito, y solo cuando la corrida lo permite: comparable, completa y en
verde. Las tres condiciones se comprueban aqui y no en `loading.publish_baseline`,
que solo escribe: la decision de si se puede publicar necesita el reporte
entero, y `loading` no lo conoce.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from untangle.evals.gates import loading
from untangle.evals.gates.metrics import criterion_pass_rates
from untangle.evals.gates.models import Baseline, LastRunDigest
from untangle.evals.models import CaseStatus
from untangle.evals.report import EvalReport


class BaselinePublicationError(Exception):
    """La corrida no cumple las condiciones de BR2.1: se niega a publicar."""


def build_baseline(report: EvalReport, *, published_at: datetime | None = None) -> Baseline:
    """La linea base de una corrida, sin comprobar si se puede publicar.

    Separado de `publish()` para poder probar la forma del objeto sin pasar por
    las reglas de BR2.1 (F5, paso 2).
    """
    cabecera = report.header
    momento = published_at if published_at is not None else datetime.now(UTC)
    baseline_id = f"{momento.date().isoformat()}-{cabecera.commit_sha[:7]}"
    return Baseline(
        baseline_id=baseline_id,
        run_id=cabecera.run_id,
        commit_sha=cabecera.commit_sha,
        published_at=momento,
        case_verdicts={fila.case_key: fila.status for fila in report.cases},
        metrics=criterion_pass_rates(report),
        model_ids=cabecera.model_ids,
        latencies=report.latencies,
    )


def build_digest(
    report: EvalReport,
    *,
    produced_at: datetime | None = None,
    blocking_criteria: frozenset[str] = frozenset(),
    dirty_tree: bool = False,
) -> LastRunDigest:
    """El resumen de la corrida tal como salio, en verde o en rojo (BR4.3).

    No decide nada: si la corrida fue de un subconjunto, el tipo lo rechaza.

    `blocking_criteria` son las compuertas duras registradas al correr; se guardan
    solo las que algun caso de esta corrida midio, para que el tablero no liste
    compuertas que nadie ejecuto.
    """
    cabecera = report.header
    medidos = {criterio for fila in report.cases for criterio in fila.criteria_results}
    return LastRunDigest(
        run_id=cabecera.run_id,
        commit_sha=cabecera.commit_sha,
        produced_at=produced_at if produced_at is not None else datetime.now(UTC),
        subset=cabecera.subset,
        case_verdicts={fila.case_key: fila.status for fila in report.cases},
        root_causes={
            fila.case_key: fila.root_cause for fila in report.cases if fila.root_cause is not None
        },
        not_measured_causes={
            fila.case_key: fila.not_measured_cause
            for fila in report.cases
            if fila.not_measured_cause is not None
        },
        criteria_results={
            fila.case_key: dict(fila.criteria_results)
            for fila in report.cases
            if fila.criteria_results
        },
        blocking_criteria=tuple(sorted(blocking_criteria & medidos)),
        model_ids=dict(cabecera.model_ids),
        prompt_hashes=dict(cabecera.prompt_hashes),
        duration_seconds=cabecera.duration_seconds,
        comparable=cabecera.comparable,
        dirty_tree=dirty_tree,
    )


def publish(
    report: EvalReport,
    *,
    directory: Path | None = None,
    published_at: datetime | None = None,
) -> tuple[Baseline, Path, Path]:
    """Publica la linea base si la corrida lo permite (BR2.1, F5).

    Tres condiciones:
    - la corrida es comparable (ningun caso no medido la invalida, BR1.5);
    - es la corrida completa, no un subconjunto (F5, "no un subconjunto");
    - ningun caso fallo (las compuertas duras en verde).

    Cualquiera que falle detiene la publicacion nombrando el caso o la causa,
    como exige BR2.1 ("El comando de publicacion falla nombrando el caso").
    """
    cabecera = report.header
    if not cabecera.comparable:
        causa = (
            cabecera.non_comparable_cause.value if cabecera.non_comparable_cause else "sin causa"
        )
        msg = (
            f"la corrida '{cabecera.run_id}' no es comparable ({causa}); no se "
            "publica como linea base (BR2.1)"
        )
        raise BaselinePublicationError(msg)

    if cabecera.subset_declared:
        msg = (
            f"la corrida '{cabecera.run_id}' es del subconjunto '{cabecera.subset}': "
            "solo la corrida completa se publica como linea base (F5, BR2.1)"
        )
        raise BaselinePublicationError(msg)

    fallidos = tuple(
        sorted(fila.case_key for fila in report.cases if fila.status is CaseStatus.FAILED)
    )
    if fallidos:
        msg = (
            f"la corrida '{cabecera.run_id}' tiene {len(fallidos)} caso(s) en rojo y no "
            f"se publica como linea base: {', '.join(fallidos)} (BR2.1)"
        )
        raise BaselinePublicationError(msg)

    baseline = build_baseline(report, published_at=published_at)
    propia, vigente = loading.publish_baseline(baseline, directory=directory)
    return baseline, propia, vigente
