"""Pruebas de TPR, TNR y el umbral que enciende o apaga al juez (BR3.1, BR3.2).

Sin juez de verdad: veredictos grabados y etiquetas sembradas, como exige
`unit-test-instructions.md`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from untangle.base import Locale
from untangle.evals.gates.calibration import (
    CALIBRATION_THRESHOLD,
    build_calibration,
    calibrated_criteria,
    compute_rates,
    is_calibrated,
)
from untangle.evals.gates.models import HumanLabel, JudgeVerdictRecord, LabelVerdict, Split


def _etiqueta(
    transcript_id: str,
    turn: int,
    criterio: str,
    verdicto: LabelVerdict,
    *,
    language: Locale = "es",
) -> HumanLabel:
    """Siempre de la particion de prueba; usar `.evolve(split=...)` para otra."""
    return HumanLabel(
        transcript_id=transcript_id,
        turn_index=turn,
        criterion=criterio,
        language=language,
        split=Split.TEST,
        verdict=verdicto,
        labeled_at=date(2026, 9, 24),
    )


def _veredicto(
    transcript_id: str, turn: int, criterio: str, verdicto: LabelVerdict, *, language: Locale = "es"
) -> JudgeVerdictRecord:
    return JudgeVerdictRecord(
        transcript_id=transcript_id,
        turn_index=turn,
        criterion=criterio,
        language=language,
        verdict=verdicto,
    )


def test_un_juez_perfecto_da_tpr_y_tnr_de_uno() -> None:
    etiquetas = tuple(
        _etiqueta(f"t{i}", 0, "voice_guide", LabelVerdict.PASS if i < 5 else LabelVerdict.FAIL)
        for i in range(10)
    )
    veredictos = tuple(
        _veredicto(f"t{i}", 0, "voice_guide", LabelVerdict.PASS if i < 5 else LabelVerdict.FAIL)
        for i in range(10)
    )

    tasas = compute_rates(etiquetas, veredictos)

    assert len(tasas) == 1
    tasa = tasas[0]
    assert tasa.tpr == 1.0
    assert tasa.tnr == 1.0
    assert tasa.n == 10


def test_solo_cuenta_la_particion_de_prueba() -> None:
    etiquetas = (
        _etiqueta("t1", 0, "voice_guide", LabelVerdict.PASS).evolve(split=Split.FIT),
        _etiqueta("t2", 0, "voice_guide", LabelVerdict.PASS),
        _etiqueta("t3", 0, "voice_guide", LabelVerdict.FAIL),
    )
    veredictos = (
        _veredicto("t1", 0, "voice_guide", LabelVerdict.FAIL),  # de fit, no deberia contar
        _veredicto("t2", 0, "voice_guide", LabelVerdict.PASS),
        _veredicto("t3", 0, "voice_guide", LabelVerdict.FAIL),
    )

    tasas = compute_rates(etiquetas, veredictos)

    assert len(tasas) == 1
    assert tasas[0].n == 2


def test_un_turno_sin_veredicto_grabado_no_cuenta() -> None:
    etiquetas = (
        _etiqueta("t1", 0, "voice_guide", LabelVerdict.PASS),
        _etiqueta("t2", 0, "voice_guide", LabelVerdict.FAIL),
    )
    veredictos = (_veredicto("t1", 0, "voice_guide", LabelVerdict.PASS),)

    # Falta el veredicto de t2 (el unico fallo real): sin el, no hay negativos
    # que medir, y la tasa no se calcula con un denominador vacio.
    assert compute_rates(etiquetas, veredictos) == ()


def test_sin_casos_de_las_dos_clases_no_se_calcula_la_tasa() -> None:
    etiquetas = tuple(_etiqueta(f"t{i}", 0, "voice_guide", LabelVerdict.PASS) for i in range(5))
    veredictos = tuple(_veredicto(f"t{i}", 0, "voice_guide", LabelVerdict.PASS) for i in range(5))

    assert compute_rates(etiquetas, veredictos) == ()


def test_is_calibrated_exige_los_dos_limites_por_encima_del_umbral() -> None:
    # n=16 por clase: con acierto perfecto, el limite inferior de Wilson pasa
    # 0.80 (1 / (1 + z^2/16) ~ 0.806); con n=10 (ver `test_wilson.py`) no llega.
    etiquetas = tuple(
        _etiqueta(f"t{i}", 0, "voice_guide", LabelVerdict.PASS if i < 16 else LabelVerdict.FAIL)
        for i in range(32)
    )
    veredictos = tuple(
        _veredicto(f"t{i}", 0, "voice_guide", LabelVerdict.PASS if i < 16 else LabelVerdict.FAIL)
        for i in range(32)
    )

    tasa = compute_rates(etiquetas, veredictos)[0]
    assert is_calibrated(tasa, threshold=CALIBRATION_THRESHOLD)


def test_calibrated_criteria_vacio_sin_calibracion() -> None:
    assert calibrated_criteria(None) == frozenset()


def test_build_calibration_guarda_el_modelo_y_la_rubrica_exactos() -> None:
    etiquetas = tuple(
        _etiqueta(f"t{i}", 0, "voice_guide", LabelVerdict.PASS if i < 16 else LabelVerdict.FAIL)
        for i in range(32)
    )
    veredictos = tuple(
        _veredicto(f"t{i}", 0, "voice_guide", LabelVerdict.PASS if i < 16 else LabelVerdict.FAIL)
        for i in range(32)
    )

    calibracion = build_calibration(
        judge_model="gemini-2.5-flash-exact-id",
        rubric_version="v1",
        labels=etiquetas,
        verdicts=veredictos,
        measured_at=datetime(2026, 9, 25, 10, 0, tzinfo=UTC),
    )

    assert calibracion.judge_model == "gemini-2.5-flash-exact-id"
    assert calibracion.rubric_version == "v1"
    assert calibrated_criteria(calibracion) == frozenset({("voice_guide", "es")})
