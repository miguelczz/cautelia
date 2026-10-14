"""Pruebas de las tres entidades nuevas de U21 (`entities.md`).

Lo que se prueba es que el modelo rechace un estado que el diseno declara
invalido, y que acepte el que declara valido -- el mismo criterio que
`test_models.py` de U1.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from untangle.evals.gates.models import (
    Baseline,
    RegressionExplanation,
    RegressionExplanationsFile,
    UnstableCase,
    UnstableCasesFile,
)
from untangle.evals.models import CaseStatus, RootCause

MOMENTO = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


# --- Camino feliz -------------------------------------------------------------


def test_una_linea_base_valida_es_congelada() -> None:
    linea = Baseline(
        baseline_id="2026-09-24-abc1234",
        run_id="run-1",
        commit_sha="abc1234def",
        published_at=MOMENTO,
        case_verdicts={"DS-2/es/017": CaseStatus.PASSED},
        metrics={"citation_precision": {"es": 0.95}},
    )
    assert linea.case_verdicts["DS-2/es/017"] is CaseStatus.PASSED
    with pytest.raises(ValidationError):
        linea.baseline_id = "otro"  # type: ignore[misc]


def test_un_caso_inestable_con_dos_corridas_es_valido() -> None:
    caso = UnstableCase(
        case_key="DS-2/es/017",
        reason="dos corridas del mismo commit dieron veredictos distintos",
        marked_at=date(2026, 9, 24),
        run_ids=("run-1", "run-2"),
        work_item="TICKET-42",
    )
    assert len(caso.run_ids) == 2


def test_una_explicacion_valida_declara_su_causa_raiz() -> None:
    explicacion = RegressionExplanation(
        case_keys=("DS-2/es/017",),
        root_cause=RootCause.RULES,
        explained_at=date(2026, 9, 24),
        commit_sha="abc1234def",
    )
    assert explicacion.root_cause is RootCause.RULES


# --- Casos de error y de borde --------------------------------------------------


def test_un_caso_inestable_con_una_sola_corrida_es_invalido() -> None:
    with pytest.raises(ValidationError):
        UnstableCase(
            case_key="DS-2/es/017",
            reason="solo una corrida",
            marked_at=date(2026, 9, 24),
            run_ids=("run-1",),
            work_item="TICKET-42",
        )


def test_una_explicacion_sin_identificadores_es_invalida() -> None:
    with pytest.raises(ValidationError):
        RegressionExplanation(
            case_keys=(),
            root_cause=RootCause.RULES,
            explained_at=date(2026, 9, 24),
            commit_sha="abc1234def",
        )


def test_una_linea_base_con_clave_de_caso_mal_formada_es_invalida() -> None:
    with pytest.raises(ValidationError):
        Baseline(
            baseline_id="2026-09-24-abc1234",
            run_id="run-1",
            commit_sha="abc1234def",
            published_at=MOMENTO,
            case_verdicts={"caso-suelto": CaseStatus.PASSED},
        )


def test_el_archivo_de_inestables_rechaza_un_caso_repetido() -> None:
    caso = UnstableCase(
        case_key="DS-2/es/017",
        reason="r",
        marked_at=date(2026, 9, 24),
        run_ids=("run-1", "run-2"),
        work_item="TICKET-42",
    )
    with pytest.raises(ValidationError):
        UnstableCasesFile(unstable_cases=(caso, caso))


def test_el_archivo_de_explicaciones_admite_varias_entradas() -> None:
    archivo = RegressionExplanationsFile(
        explanations=(
            RegressionExplanation(
                case_keys=("DS-2/es/017",),
                root_cause=RootCause.RULES,
                explained_at=date(2026, 9, 24),
                commit_sha="abc1234def",
            ),
        )
    )
    assert len(archivo.explanations) == 1
