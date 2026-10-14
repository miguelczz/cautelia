"""Pruebas de la tasa de aciertos por criterio y por idioma."""

from __future__ import annotations

from untangle.evals.gates.metrics import criterion_pass_rates
from untangle.evals.models import CaseStatus

from .builders import fila, reporte


def test_la_tasa_se_calcula_por_criterio_y_por_idioma() -> None:
    rep = reporte(
        (
            fila("DS-2/es/1", status=CaseStatus.PASSED),
            fila("DS-2/es/2", status=CaseStatus.FAILED),
            fila("DS-2/en/1", status=CaseStatus.PASSED, language="en"),
        )
    )
    tasas = criterion_pass_rates(rep)
    assert tasas["citation_precision"]["es"] == 0.5
    assert tasas["citation_precision"]["en"] == 1.0


def test_un_idioma_sin_casos_medidos_no_aparece() -> None:
    rep = reporte((fila("DS-2/es/1", status=CaseStatus.PASSED),))
    tasas = criterion_pass_rates(rep)
    assert "en" not in tasas["citation_precision"]
