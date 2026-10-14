"""TPR y TNR del juez contra las etiquetas humanas de DS-7 (F2, BR3.1 a BR3.4).

Positivo es "pasa" y negativo es "falla": TPR es la tasa de aciertos que el
juez confirma (de los turnos que de verdad pasan, cuantos dice que pasan) y
TNR es la tasa de fallos que detecta (de los que de verdad fallan, cuantos
dice que fallan). Las dos, con el limite inferior de Wilson, decian si el
juez cuenta (FD-U21-4).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from untangle.base import Locale
from untangle.evals.gates.models import (
    HumanLabel,
    JudgeCalibration,
    JudgeCalibrationRate,
    JudgeVerdictRecord,
    LabelVerdict,
    Split,
)
from untangle.evals.gates.wilson import wilson_lower_bound

#: FD-U21-4: el juez cuenta cuando el limite inferior de los dos intervalos
#: llega a este umbral. Vive aqui y en el codigo, nunca en una bandera de linea
#: de comandos (SEC-U21.5).
CALIBRATION_THRESHOLD = 0.80


def _key(label: HumanLabel) -> tuple[str, int, str]:
    return (label.transcript_id, label.turn_index, label.criterion)


def compute_rates(
    labels: tuple[HumanLabel, ...],
    verdicts: tuple[JudgeVerdictRecord, ...],
) -> tuple[JudgeCalibrationRate, ...]:
    """TPR y TNR por criterio e idioma, sobre la particion de prueba (BR3.1).

    Un turno etiquetado sin veredicto grabado del juez no cuenta ni suma ni
    resta: no es un desacuerdo, es un dato que falta, y sumarlo como fallo
    inflaria falsamente la tasa de fallos que el juez detecta.
    """
    por_veredicto = {(v.transcript_id, v.turn_index, v.criterion): v.verdict for v in verdicts}

    # (criterio, idioma) -> [(esperado, obtenido), ...]
    pares: dict[tuple[str, Locale], list[tuple[LabelVerdict, LabelVerdict]]] = defaultdict(list)

    for etiqueta in labels:
        if etiqueta.split is not Split.TEST:
            continue
        obtenido = por_veredicto.get(_key(etiqueta))
        if obtenido is None:
            continue
        pares[(etiqueta.criterion, etiqueta.language)].append((etiqueta.verdict, obtenido))

    tasas: list[JudgeCalibrationRate] = []
    for (criterio, idioma), observaciones in sorted(pares.items()):
        positivos = [
            obtenido for esperado, obtenido in observaciones if esperado is LabelVerdict.PASS
        ]
        negativos = [
            obtenido for esperado, obtenido in observaciones if esperado is LabelVerdict.FAIL
        ]

        if not positivos or not negativos:
            # Sin al menos un caso real de cada clase, ni TPR ni TNR se pueden
            # medir: una tasa calculada sobre cero fallos reales, por ejemplo,
            # no dice nada sobre si el juez los detecta.
            continue

        aciertos_positivos = sum(1 for o in positivos if o is LabelVerdict.PASS)
        aciertos_negativos = sum(1 for o in negativos if o is LabelVerdict.FAIL)

        tpr = aciertos_positivos / len(positivos)
        tnr = aciertos_negativos / len(negativos)

        tasas.append(
            JudgeCalibrationRate(
                criterion=criterio,
                language=idioma,
                n=len(observaciones),
                tpr=tpr,
                tnr=tnr,
                ci_low_tpr=wilson_lower_bound(aciertos_positivos, len(positivos)),
                ci_low_tnr=wilson_lower_bound(aciertos_negativos, len(negativos)),
            )
        )

    return tuple(tasas)


def build_calibration(
    *,
    judge_model: str,
    rubric_version: str,
    labels: tuple[HumanLabel, ...],
    verdicts: tuple[JudgeVerdictRecord, ...],
    measured_at: datetime,
) -> JudgeCalibration:
    """La calibracion completa, lista para publicar (F2, paso 3)."""
    tasas = compute_rates(labels, verdicts)
    return JudgeCalibration(
        calibration_id=f"{judge_model}-{rubric_version}-{measured_at.date().isoformat()}",
        judge_model=judge_model,
        rubric_version=rubric_version,
        measured_at=measured_at,
        split=Split.TEST,
        rates=tasas,
    )


def is_calibrated(rate: JudgeCalibrationRate, *, threshold: float = CALIBRATION_THRESHOLD) -> bool:
    """BR3.1: cuenta cuando el limite inferior de los dos intervalos llega al umbral."""
    return rate.ci_low_tpr >= threshold and rate.ci_low_tnr >= threshold


def calibrated_criteria(
    calibration: JudgeCalibration | None, *, threshold: float = CALIBRATION_THRESHOLD
) -> frozenset[tuple[str, Locale]]:
    """Los (criterio, idioma) cuyos veredictos del juez cuentan (BR3.1, BR3.2).

    `None` -- sin calibracion para esta combinacion exacta de modelo y rubrica
    -- da el conjunto vacio: todos sus criterios salen "no medida" con la causa
    "juez sin calibrar" (BR3.2).
    """
    if calibration is None:
        return frozenset()
    return frozenset(
        (tasa.criterion, tasa.language)
        for tasa in calibration.rates
        if is_calibrated(tasa, threshold=threshold)
    )
