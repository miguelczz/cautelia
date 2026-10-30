"""Pruebas del respaldo de la afirmación, sin llamar al juez de verdad (paso 9, CG-U8-4).

Ninguna prueba llama al juez real: los veredictos están grabados, como ya hizo
U21. Lo que se comprueba aquí son dos cosas: que `check_citation_backing`
compone lo que el puerto devuelve, y que el criterio `citation_backing` se
apaga cuando el juez no está calibrado y sigue sin bloquear ni desbloquear
nada -- enchufándolo a la misma `evals.gates.judgment.criterion_counts` que ya
prueba U21, no a una copia (BR3.6, BR3.3, ADR-014).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from untangle.base import Locale
from untangle.evals.gates import calibration
from untangle.evals.gates import judgment as gates_judgment
from untangle.evals.gates.models import JudgeCalibration, JudgeCalibrationRate, Split
from untangle.evals.models import CaseStatus, JudgmentKind
from untangle.evals.report import CaseRow
from untangle.policy_rag.citations import backing

AHORA = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def _correr(coro: Any) -> Any:
    return asyncio.run(coro)


class _JuezGrabado:
    """Un `JudgePort` con veredictos ya decididos. Nunca llama a ningún proveedor."""

    def __init__(self, veredictos: dict[str, backing.BackingVerdict]) -> None:
        self._veredictos = veredictos
        self.llamadas: list[backing.BackingCheck] = []

    async def __call__(self, check: backing.BackingCheck) -> backing.BackingVerdict:
        self.llamadas.append(check)
        return self._veredictos[check.clause_id]


def test_check_citation_backing_pregunta_por_cada_comprobacion_en_orden() -> None:
    """AC2.2.2: una comprobación por cita, en el orden recibido."""
    comprobaciones = (
        backing.BackingCheck(
            clause_id="SA-PAP-2026-A.1",
            clause_text="Cubre danos a terceros hasta el limite de la caratula.",
            claim="La parte A cubre el siniestro.",
        ),
        backing.BackingCheck(
            clause_id="SA-PAP-2026-A.2",
            clause_text="No cubre danos intencionales.",
            claim="La parte A cubre el siniestro.",
        ),
    )
    juez = _JuezGrabado(
        {
            "SA-PAP-2026-A.1": backing.BackingVerdict(
                backed=True, rationale="El texto habla de danos a terceros."
            ),
            "SA-PAP-2026-A.2": backing.BackingVerdict(
                backed=False, rationale="El texto excluye justo lo que la afirmacion cubre."
            ),
        }
    )

    resultados = _correr(backing.check_citation_backing(comprobaciones, judge=juez))

    assert [r.clause_id for r in resultados] == ["SA-PAP-2026-A.1", "SA-PAP-2026-A.2"]
    assert resultados[0].verdict.backed is True
    assert resultados[1].verdict.backed is False
    assert [c.clause_id for c in juez.llamadas] == ["SA-PAP-2026-A.1", "SA-PAP-2026-A.2"]


def _fila(*, resultado: str, juicio: JudgmentKind) -> CaseRow:
    return CaseRow(
        case_key="DS-3/es/001",
        language="es",
        status=CaseStatus.FAILED if resultado == "fail" else CaseStatus.PASSED,
        criteria_results={backing.CRITERION: resultado},
        criteria_judgment={backing.CRITERION: juicio},
    )


def test_el_respaldo_no_cuenta_mientras_el_juez_no_este_calibrado() -> None:
    """BR3.6, ADR-014: sin calibración, el criterio sale "no medida" -- no bloquea
    ni desbloquea, simplemente no participa (`criterion_counts` de U21)."""
    fila = _fila(resultado="fail", juicio=JudgmentKind.JUDGE)

    assert gates_judgment.criterion_counts(fila, backing.CRITERION, frozenset()) is False
    assert gates_judgment.effective_failed_criteria(fila, calibrated=frozenset()) == ()


def test_el_respaldo_cuenta_una_vez_calibrado_para_ese_idioma() -> None:
    fila = _fila(resultado="fail", juicio=JudgmentKind.JUDGE)
    calibrado: frozenset[tuple[str, Locale]] = frozenset({(backing.CRITERION, "es")})

    assert gates_judgment.criterion_counts(fila, backing.CRITERION, calibrado) is True
    assert gates_judgment.effective_failed_criteria(fila, calibrated=calibrado) == (
        backing.CRITERION,
    )


def test_la_calibracion_de_otro_idioma_no_alcanza() -> None:
    """La calibración es por (criterio, idioma): calibrar en inglés no enciende el español."""
    fila = _fila(resultado="fail", juicio=JudgmentKind.JUDGE)
    calibrado_en_ingles: frozenset[tuple[str, Locale]] = frozenset({(backing.CRITERION, "en")})

    assert gates_judgment.criterion_counts(fila, backing.CRITERION, calibrado_en_ingles) is False


def test_una_compuerta_de_codigo_sigue_bloqueando_sin_depender_del_juez() -> None:
    """BR3.3: las cuatro comprobaciones exactas de `verifier.py` no dependen de esto."""
    fila = CaseRow(
        case_key="DS-3/es/002",
        language="es",
        status=CaseStatus.FAILED,
        criteria_results={"citation_exists": "fail"},
        criteria_judgment={"citation_exists": JudgmentKind.CODE},
    )

    assert gates_judgment.criterion_counts(fila, "citation_exists", frozenset()) is True
    assert gates_judgment.effective_failed_criteria(fila, calibrated=frozenset()) == (
        "citation_exists",
    )


def test_calibrated_criteria_de_u21_reconoce_el_respaldo_por_su_nombre() -> None:
    """De punta a punta: una calibración real de U21 hace contar a `citation_backing`
    por su nombre, sin que este modulo repita la aritmetica de TPR/TNR."""
    tasa = JudgeCalibrationRate(
        criterion=backing.CRITERION,
        language="es",
        n=40,
        tpr=0.95,
        tnr=0.92,
        ci_low_tpr=0.85,
        ci_low_tnr=0.83,
    )
    calibracion = JudgeCalibration(
        calibration_id="test-calibration",
        judge_model="gemini-3.1-flash-lite",
        rubric_version="1",
        measured_at=AHORA,
        split=Split.TEST,
        rates=(tasa,),
    )

    calibrados = calibration.calibrated_criteria(calibracion)

    assert (backing.CRITERION, "es") in calibrados
    fila = _fila(resultado="fail", juicio=JudgmentKind.JUDGE)
    assert gates_judgment.criterion_counts(fila, backing.CRITERION, calibrados) is True


def test_sin_calibracion_publicada_el_conjunto_calibrado_esta_vacio() -> None:
    assert calibration.calibrated_criteria(None) == frozenset()
