"""La tasa de aciertos por criterio y por idioma, usada por la linea base y por
la comparacion (P12): un solo calculo para que las dos partes comparen lo mismo.
"""

from __future__ import annotations

from untangle.base import Locale
from untangle.evals.report import EvalReport


def criterion_pass_rates(report: EvalReport) -> dict[str, dict[Locale, float]]:
    """Tasa de aciertos por criterio y por idioma.

    Solo entra un idioma cuando hubo al menos un caso medido en ese criterio y
    ese idioma: un denominador cero no es una tasa de cero, es "no medido"
    (BR1.3), y aqui se omite en vez de inventar un valor.
    """
    tasas: dict[str, dict[Locale, float]] = {}
    for criterio in report.criteria:
        por_idioma: dict[Locale, float] = {}
        idiomas: tuple[Locale, ...] = ("es", "en")
        for idioma in idiomas:
            recuento = criterio.by_language.es if idioma == "es" else criterio.by_language.en
            medidos = recuento.passed + recuento.failed
            if medidos:
                por_idioma[idioma] = recuento.passed / medidos
        if por_idioma:
            tasas[criterio.criterion] = por_idioma
    return tasas
