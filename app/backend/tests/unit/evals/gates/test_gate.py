"""Pruebas de la compuerta completa: termina el reporte y decide el codigo de
salida (F1 paso 5, FD-U21-5).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from untangle.evals.gates.baseline import publish
from untangle.evals.gates.gate import (
    GateSources,
    blocking_criteria_from_registry,
    finalize_report,
    run_gate,
)
from untangle.evals.gates.models import RegressionExplanation
from untangle.evals.models import CaseStatus, Dataset, RootCause
from untangle.evals.runner import api as runner_api
from untangle.evals.runner.api import EvalTarget

from .builders import fila, reporte


def _fuentes(tmp_path: Path) -> GateSources:
    return GateSources(
        baselines_dir=tmp_path / "baselines",
        unstable_path=tmp_path / "unstable-cases.yaml",
        regressions_path=tmp_path / "regressions.yaml",
    )


def test_finalize_report_adjunta_la_causa_raiz_de_la_explicacion() -> None:
    rep = reporte((fila("DS-2/es/017", status=CaseStatus.FAILED),))
    explicacion = RegressionExplanation(
        case_keys=("DS-2/es/017",),
        root_cause=RootCause.RULES,
        explained_at=date(2026, 9, 24),
        commit_sha="abc1234def",
    )

    final = finalize_report(rep, baseline_id="2026-09-20-abc1234", explanations=(explicacion,))

    assert final.cases[0].root_cause is RootCause.RULES
    assert final.header.baseline_id == "2026-09-20-abc1234"


def test_finalize_report_sin_explicacion_no_inventa_una_causa() -> None:
    rep = reporte((fila("DS-2/es/017", status=CaseStatus.FAILED),))

    final = finalize_report(rep, baseline_id=None, explanations=())

    assert final.cases[0].root_cause is None
    assert final.header.baseline_id is None


def test_run_gate_sin_linea_base_dice_que_no_comparo(tmp_path: Path) -> None:
    rep = reporte((fila("DS-2/es/017", status=CaseStatus.PASSED),))

    outcome = run_gate(rep, sources=_fuentes(tmp_path), blocking_criteria=frozenset())

    assert outcome.verdict.compared is False
    assert outcome.exit_code == 0
    assert outcome.report.header.baseline_id is None


def test_run_gate_con_linea_base_publicada_compara_y_bloquea(tmp_path: Path) -> None:
    baselines_dir = tmp_path / "baselines"
    verde = reporte(
        (fila("DS-2/es/017", status=CaseStatus.PASSED),),
        subset=None,
    )
    baseline, _, _ = publish(verde, directory=baselines_dir)

    rojo = reporte((fila("DS-2/es/017", status=CaseStatus.FAILED),))
    outcome = run_gate(
        rojo,
        sources=GateSources(
            baselines_dir=baselines_dir,
            unstable_path=tmp_path / "unstable-cases.yaml",
            regressions_path=tmp_path / "regressions.yaml",
        ),
        blocking_criteria=frozenset(),
    )

    assert outcome.verdict.compared is True
    assert outcome.exit_code == 1
    assert outcome.report.header.baseline_id == baseline.baseline_id


def test_run_gate_bloquea_con_un_hallazgo_del_segundo_detector(tmp_path: Path) -> None:
    traza = tmp_path / "trace.jsonl"
    traza.write_text('{"turn": "mi telefono es 3001234567"}\n', encoding="utf-8")
    rep = reporte((fila("DS-2/es/017", status=CaseStatus.PASSED),))

    outcome = run_gate(
        rep,
        sources=_fuentes(tmp_path),
        blocking_criteria=frozenset(),
        audit_paths=(traza,),
    )

    assert outcome.exit_code == 1
    assert outcome.verdict.pii_findings
    assert any("trace.jsonl" in razon for razon in outcome.verdict.reasons)


def test_run_gate_sin_archivos_para_auditar_no_bloquea_por_el_segundo_detector(
    tmp_path: Path,
) -> None:
    rep = reporte((fila("DS-2/es/017", status=CaseStatus.PASSED),))

    outcome = run_gate(rep, sources=_fuentes(tmp_path), blocking_criteria=frozenset())

    assert outcome.exit_code == 0
    assert outcome.verdict.pii_findings == ()


def test_blocking_criteria_from_registry_lee_solo_los_marcados() -> None:
    runner_api.reset()
    try:
        runner_api.register_targets(
            "u-test",
            (
                EvalTarget("bloqueante", Dataset.DS_2, "criterio con [bloquea]", blocking=True),
                EvalTarget("normal", Dataset.DS_2, "criterio sin bloquea"),
            ),
        )
        assert blocking_criteria_from_registry() == frozenset({"bloqueante"})
    finally:
        runner_api.reset()


def test_las_compuertas_duras_del_proyecto_estan_registradas_como_bloqueantes() -> None:
    """Decision de Miguel del 2026-10-11. Hasta entonces un fallo en las citas, en
    el acceso a un caso ajeno o en las frases prohibidas contaba como un caso rojo
    mas, que una explicacion escrita podia levantar."""
    from untangle.evals import cli as evals_cli

    runner_api.reset()
    try:
        evals_cli.register_all_probes()
        bloqueantes = blocking_criteria_from_registry()
    finally:
        runner_api.reset()

    for criterio in (
        # Fuga entre aseguradoras, contra el despliegue vivo.
        "rt4_foreign_case_denied",
        "rt4_inbox_queue_isolated",
        # Lo que el proyecto tiene prohibido publicar.
        "content_forbidden_claims",
        "content_clause_text",
        # Cero citas inexistentes, por caso de DS-3.
        "citation_exists_coverage_agreement_period",
        # Las que ya lo estaban: adversarial y datos personales.
        "rt1_injected_coverage_claim_blocked",
        "rt2_untrusted_text_stays_data",
        "rt3_pressure_extracts_no_promise",
        "rt6_fault_and_legal_advice_blocked",
    ):
        assert criterio in bloqueantes, criterio
    # El registro de tu del espanol es de estilo: no detiene una entrega.
    assert "content_spanish_register" not in bloqueantes
