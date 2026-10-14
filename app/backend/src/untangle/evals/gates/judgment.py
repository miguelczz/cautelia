"""Que criterios de un caso cuentan de verdad (BR3.1 a BR3.3).

Compartido entre `compare.evaluate` y `baseline.publish`: los dos necesitan
saber si un caso "fallo de verdad" antes de decidir si bloquea o si se puede
publicar como linea base, y las dos preguntas usan la misma regla.
"""

from __future__ import annotations

from untangle.base import Locale
from untangle.evals.models import JudgmentKind
from untangle.evals.report import CaseRow


def criterion_counts(
    fila: CaseRow, criterion: str, calibrated: frozenset[tuple[str, Locale]]
) -> bool:
    """Si el veredicto de este criterio cuenta para la compuerta.

    Codigo y humano siempre cuentan: ninguno de los dos depende de la
    calibracion del juez (BR3.3, "las compuertas juzgadas por codigo siguen
    bloqueando"). Un criterio juzgado por el juez solo cuenta cuando su
    combinacion de idioma y criterio esta calibrada (BR3.1, BR3.2); sin
    calibracion, sale "no medida" y no bloquea, y **tampoco** desbloquea nada
    -- simplemente no participa.
    """
    juicio = fila.criteria_judgment.get(criterion)
    if juicio is not JudgmentKind.JUDGE:
        return True
    return (criterion, fila.language) in calibrated


def effective_failed_criteria(
    fila: CaseRow, *, calibrated: frozenset[tuple[str, Locale]]
) -> tuple[str, ...]:
    """Los criterios que fallaron de verdad, descontando el juez sin calibrar."""
    return tuple(
        sorted(
            criterio
            for criterio, veredicto in fila.criteria_results.items()
            if veredicto == "fail" and criterion_counts(fila, criterio, calibrated)
        )
    )
