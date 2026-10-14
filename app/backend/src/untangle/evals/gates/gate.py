"""La compuerta completa: compara, termina el reporte y decide el codigo de
salida (F1, F4).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from untangle.evals.gates import audit, loading
from untangle.evals.gates.calibration import calibrated_criteria as _calibrated_criteria
from untangle.evals.gates.compare import GateRules, GateVerdict, evaluate
from untangle.evals.gates.models import JudgeCalibration, RegressionExplanation
from untangle.evals.models import RootCause
from untangle.evals.report import EvalReport
from untangle.evals.runner import api as runner_api


@dataclass(frozen=True)
class GateSources:
    """Donde leer la memoria entre corridas: `None` es el archivo por defecto.

    Agrupadas en un solo parametro para no pasar de cinco argumentos en
    `run_gate` (PLR0913); las pruebas siguen pudiendo apuntar cada una a su
    propio directorio temporal.
    """

    baselines_dir: Path | None = None
    unstable_path: Path | None = None
    regressions_path: Path | None = None


@dataclass(frozen=True)
class GateOutcome:
    """El reporte ya terminado y el veredicto que decide si bloquea."""

    report: EvalReport
    verdict: GateVerdict

    @property
    def exit_code(self) -> int:
        return 1 if self.verdict.blocked else 0


def finalize_report(
    report: EvalReport,
    *,
    baseline_id: str | None,
    explanations: tuple[RegressionExplanation, ...],
) -> EvalReport:
    """Le da al reporte lo que le faltaba (F1 paso 5, `entities.md`).

    Adjunta la causa raiz de la explicacion que nombra a cada caso -- un caso
    fallido sin explicacion se queda sin causa en vez de que el codigo invente
    una -- y deja la cabecera diciendo contra que linea base se comparo, o que
    no hubo ninguna (FD-U21-5).
    """
    causa_por_caso: dict[str, RootCause] = {
        clave: explicacion.root_cause
        for explicacion in explanations
        for clave in explicacion.case_keys
    }

    filas = tuple(
        fila.evolve(root_cause=causa_por_caso[fila.case_key])
        if fila.case_key in causa_por_caso
        else fila
        for fila in report.cases
    )

    return report.evolve(header=report.header.evolve(baseline_id=baseline_id), cases=filas)


def blocking_criteria_from_registry() -> frozenset[str]:
    """Los criterios que algun `EvalTarget` registrado declaro `blocking=True`.

    Lee el registro vivo de C-22 (`runner.api`): las unidades marcan sus
    compuertas duras al registrar sus objetivos, y aqui se leen tal cual, sin
    una segunda lista que se pueda desincronizar de la primera.
    """
    return frozenset(
        target.criterion
        for targets in runner_api.registered_targets().values()
        for target in targets
        if target.blocking
    )


def _with_audit_findings(
    verdict: GateVerdict, findings: tuple[audit.AuditFinding, ...]
) -> GateVerdict:
    """Adjunta los hallazgos del segundo detector: un solo hallazgo bloquea
    siempre, sin pasar por ninguna de las reglas de `evaluate` (BR4.2)."""
    if not findings:
        return verdict
    razones_nuevas = tuple(
        f"segundo detector: '{h.source}' ({h.language}, {h.entity_type.value})" for h in findings
    )
    return dataclasses.replace(
        verdict,
        blocked=True,
        pii_findings=findings,
        reasons=(*verdict.reasons, *razones_nuevas),
    )


def run_gate(
    report: EvalReport,
    *,
    sources: GateSources | None = None,
    blocking_criteria: frozenset[str] | None = None,
    audit_paths: Sequence[Path] = (),
    calibration: JudgeCalibration | None = None,
) -> GateOutcome:
    """El veredicto completo sobre un reporte ya corrido (F1, F3, F2).

    `audit_paths` son las trazas exportadas, los logs y las exportaciones de
    esta corrida, cuando existen; el propio reporte se revisa siempre.
    `calibration` es la calibracion vigente del juez para el modelo y la
    rubrica de esta corrida; `None` hace que todo criterio del juez salga "no
    medida" (BR3.2), como si nunca se hubiera calibrado.
    """
    fuentes = sources if sources is not None else GateSources()
    baseline = loading.load_current_baseline(fuentes.baselines_dir)
    unstable = loading.load_unstable_cases(fuentes.unstable_path)
    explanations = loading.load_regression_explanations(fuentes.regressions_path)
    bloqueantes = (
        blocking_criteria if blocking_criteria is not None else blocking_criteria_from_registry()
    )
    calibrados = _calibrated_criteria(calibration)

    verdict = evaluate(
        report,
        baseline=baseline,
        unstable=unstable,
        explanations=explanations,
        rules=GateRules(blocking_criteria=bloqueantes, calibrated_criteria=calibrados),
    )
    hallazgos = audit.scan_report(report) + audit.scan_paths(audit_paths)
    verdict = _with_audit_findings(verdict, hallazgos)

    reporte_final = finalize_report(
        report,
        baseline_id=baseline.baseline_id if baseline is not None else None,
        explanations=explanations,
    )
    return GateOutcome(report=reporte_final, verdict=verdict)
