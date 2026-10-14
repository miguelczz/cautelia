"""Pruebas del veredicto de la compuerta (BR2.2, BR2.3, BR2.4, FD-U21-5).

Las tres primeras son las pruebas que aislan una regla de precedencia, escritas
antes del codigo que la implementa (ajuste heredado de U9, 2026-09-16): un caso
que pasaba y falla sin explicacion deja la compuerta en rojo; el mismo caso con
una explicacion que lo nombra la deja en verde; el mismo caso marcado inestable
no cuenta para la compuerta.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from untangle.evals.gates.compare import GateRules, evaluate
from untangle.evals.gates.models import Baseline, RegressionExplanation, UnstableCase
from untangle.evals.latency_summary import ChannelLatency, LatencySummary
from untangle.evals.models import CaseStatus, Channel, JudgmentKind, RootCause

from .builders import fila, reporte

CASE_KEY = "DS-2/es/017"


def _linea_base_con(case_key: str, status: CaseStatus) -> Baseline:
    return Baseline(
        baseline_id="2026-09-20-0000000",
        run_id="run-base",
        commit_sha="0000000abc",
        published_at=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
        case_verdicts={case_key: status},
    )


# --- Las tres pruebas que aislan una regla de precedencia (BR2.2, BR2.4) ------


def test_un_caso_que_pasaba_y_ahora_falla_sin_explicacion_deja_la_compuerta_en_rojo() -> None:
    base = _linea_base_con(CASE_KEY, CaseStatus.PASSED)
    actual = reporte((fila(CASE_KEY, status=CaseStatus.FAILED),))

    veredicto = evaluate(actual, baseline=base, unstable=(), explanations=())

    assert veredicto.blocked is True
    assert CASE_KEY in veredicto.newly_failed
    assert any(CASE_KEY in razon for razon in veredicto.reasons)


def test_el_mismo_caso_con_una_explicacion_que_lo_nombra_deja_la_compuerta_en_verde() -> None:
    base = _linea_base_con(CASE_KEY, CaseStatus.PASSED)
    actual = reporte((fila(CASE_KEY, status=CaseStatus.FAILED),))
    explicacion = RegressionExplanation(
        case_keys=(CASE_KEY,),
        root_cause=RootCause.RULES,
        explained_at=date(2026, 9, 24),
        commit_sha="abc1234def",
    )

    veredicto = evaluate(actual, baseline=base, unstable=(), explanations=(explicacion,))

    assert veredicto.blocked is False
    assert veredicto.newly_failed == ()
    assert CASE_KEY in veredicto.explained_regressions


def test_el_mismo_caso_marcado_inestable_no_cuenta_para_la_compuerta() -> None:
    base = _linea_base_con(CASE_KEY, CaseStatus.PASSED)
    actual = reporte((fila(CASE_KEY, status=CaseStatus.FAILED),))
    inestable = UnstableCase(
        case_key=CASE_KEY,
        reason="dos corridas del mismo commit dieron veredictos distintos",
        marked_at=date(2026, 9, 24),
        run_ids=("run-1", "run-2"),
        work_item="TICKET-42",
    )

    veredicto = evaluate(actual, baseline=base, unstable=(inestable,), explanations=())

    assert veredicto.blocked is False
    assert veredicto.newly_failed == ()
    assert CASE_KEY in veredicto.unstable_excluded


# --- Las tres pruebas de la correccion del 2026-09-25 (compuertas duras) -----
#
# Una explicacion en `regressions.yaml` solo puede excusar una REGRESION de un
# criterio no bloqueante; una compuerta dura es absoluta y ninguna explicacion
# la levanta (PRD 11.2, team.md "Compuertas duras").

BLOCKING_CRITERION = "money_rule_forces_referral"


def test_un_criterio_bloqueante_en_rojo_con_explicacion_deja_la_compuerta_en_rojo() -> None:
    base = _linea_base_con(CASE_KEY, CaseStatus.PASSED)
    actual = reporte((fila(CASE_KEY, status=CaseStatus.FAILED, criterion=BLOCKING_CRITERION),))
    explicacion = RegressionExplanation(
        case_keys=(CASE_KEY,),
        root_cause=RootCause.RULES,
        explained_at=date(2026, 9, 24),
        commit_sha="abc1234def",
    )

    veredicto = evaluate(
        actual,
        baseline=base,
        unstable=(),
        explanations=(explicacion,),
        rules=GateRules(blocking_criteria=frozenset({BLOCKING_CRITERION})),
    )

    assert veredicto.blocked is True
    assert CASE_KEY in veredicto.blocking_failures
    assert any(BLOCKING_CRITERION in razon or CASE_KEY in razon for razon in veredicto.reasons)
    # La explicacion no lo saca de la lista de bloqueantes ni lo mete a la de
    # regresiones excusadas: una compuerta dura no pasa por ese camino.
    assert CASE_KEY not in veredicto.explained_regressions


def test_regresion_no_bloqueante_con_explicacion_deja_la_compuerta_en_verde() -> None:
    base = _linea_base_con(CASE_KEY, CaseStatus.PASSED)
    actual = reporte((fila(CASE_KEY, status=CaseStatus.FAILED, criterion="citation_precision"),))
    explicacion = RegressionExplanation(
        case_keys=(CASE_KEY,),
        root_cause=RootCause.RULES,
        explained_at=date(2026, 9, 24),
        commit_sha="abc1234def",
    )

    veredicto = evaluate(
        actual,
        baseline=base,
        unstable=(),
        explanations=(explicacion,),
        rules=GateRules(blocking_criteria=frozenset({BLOCKING_CRITERION})),
    )

    assert veredicto.blocked is False
    assert veredicto.blocking_failures == ()
    assert CASE_KEY in veredicto.explained_regressions


def test_un_caso_inestable_con_fallo_bloqueante_no_cuenta_pero_sale_listado() -> None:
    base = _linea_base_con(CASE_KEY, CaseStatus.PASSED)
    actual = reporte((fila(CASE_KEY, status=CaseStatus.FAILED, criterion=BLOCKING_CRITERION),))
    inestable = UnstableCase(
        case_key=CASE_KEY,
        reason="dos corridas del mismo commit dieron veredictos distintos",
        marked_at=date(2026, 9, 24),
        run_ids=("run-1", "run-2"),
        work_item="TICKET-42",
    )

    veredicto = evaluate(
        actual,
        baseline=base,
        unstable=(inestable,),
        explanations=(),
        rules=GateRules(blocking_criteria=frozenset({BLOCKING_CRITERION})),
    )

    assert veredicto.blocked is False
    assert veredicto.blocking_failures == ()
    # No cuenta para la compuerta, pero nunca en silencio: sale en su propia
    # lista (item 4 de la correccion).
    assert CASE_KEY in veredicto.unstable_blocking_failures
    assert CASE_KEY in veredicto.unstable_excluded


# --- Cobertura adicional -------------------------------------------------------


def test_sin_linea_base_la_compuerta_corre_sin_comparar() -> None:
    actual = reporte((fila(CASE_KEY, status=CaseStatus.PASSED),))

    veredicto = evaluate(actual, baseline=None, unstable=(), explanations=())

    assert veredicto.compared is False
    assert veredicto.blocked is False


def test_sin_linea_base_un_fallo_sin_explicar_si_bloquea() -> None:
    actual = reporte((fila(CASE_KEY, status=CaseStatus.FAILED),))

    veredicto = evaluate(actual, baseline=None, unstable=(), explanations=())

    assert veredicto.compared is False
    assert veredicto.blocked is True
    assert CASE_KEY in veredicto.unexplained_failures


def test_un_caso_que_fallaba_y_ahora_pasa_se_reporta_aparte() -> None:
    base = _linea_base_con(CASE_KEY, CaseStatus.FAILED)
    actual = reporte((fila(CASE_KEY, status=CaseStatus.PASSED),))

    veredicto = evaluate(actual, baseline=base, unstable=(), explanations=())

    assert veredicto.blocked is False
    assert CASE_KEY in veredicto.newly_passed


def test_una_regresion_fuera_de_ds2_ds3_ds6_no_activa_br2_2() -> None:
    """DS-8 son chequeos de contenido, hard-gates por si mismos: la comparacion
    de BR2.2 esta escrita para los tres conjuntos pequenos que nombra."""
    case_key = "DS-8/es/copy-catalog-parity"
    base = Baseline(
        baseline_id="2026-09-20-0000000",
        run_id="run-base",
        commit_sha="0000000abc",
        published_at=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
        case_verdicts={case_key: CaseStatus.PASSED},
    )
    actual = reporte((fila(case_key, status=CaseStatus.FAILED),))

    veredicto = evaluate(actual, baseline=base, unstable=(), explanations=())

    # No entra a newly_failed (esa lista es de BR2.2, solo DS-2/DS-3/DS-6), pero
    # el caso sigue sin explicacion: bloquea igual, por la regla de fallos sin
    # explicar (no es un criterio bloqueante, asi que no pasa por esa via).
    assert case_key not in veredicto.newly_failed
    assert case_key in veredicto.unexplained_failures
    assert veredicto.blocked is True


def test_una_caida_de_metrica_sin_explicar_bloquea() -> None:
    case_key = "DS-8/es/extraction-field"
    base = Baseline(
        baseline_id="2026-09-20-0000000",
        run_id="run-base",
        commit_sha="0000000abc",
        published_at=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
        case_verdicts={case_key: CaseStatus.PASSED},
        metrics={"field_extraction": {"es": 1.0}},
    )
    actual = reporte((fila(case_key, status=CaseStatus.FAILED, criterion="field_extraction"),))

    veredicto = evaluate(actual, baseline=base, unstable=(), explanations=())

    assert veredicto.blocked is True
    assert any(drop.criterion == "field_extraction" for drop in veredicto.metric_drops)


def test_una_caida_de_metrica_explicada_no_bloquea() -> None:
    case_key = "DS-8/es/extraction-field"
    base = Baseline(
        baseline_id="2026-09-20-0000000",
        run_id="run-base",
        commit_sha="0000000abc",
        published_at=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
        case_verdicts={case_key: CaseStatus.PASSED},
        metrics={"field_extraction": {"es": 1.0}},
    )
    actual = reporte((fila(case_key, status=CaseStatus.FAILED, criterion="field_extraction"),))
    explicacion = RegressionExplanation(
        case_keys=(case_key,),
        root_cause=RootCause.EXTRACTION,
        explained_at=date(2026, 9, 24),
        commit_sha="abc1234def",
    )

    veredicto = evaluate(actual, baseline=base, unstable=(), explanations=(explicacion,))

    assert veredicto.blocked is False
    assert veredicto.metric_drops == ()


# --- BR3.1 a BR3.3: el juez sin calibrar no bloquea, y el codigo si ----------
#
# Cuarta regla de precedencia, aplazada de la unidad anterior a este paso 6
# (`unit-test-instructions.md`): un criterio con el juez descalibrado sale "no
# medida" y no apaga las compuertas juzgadas por codigo.


def test_un_criterio_del_juez_sin_calibrar_no_bloquea() -> None:
    base = _linea_base_con(CASE_KEY, CaseStatus.PASSED)
    actual = reporte(
        (
            fila(
                CASE_KEY,
                status=CaseStatus.FAILED,
                criterion="voice_guide",
                judgment=JudgmentKind.JUDGE,
            ),
        )
    )

    # Sin calibracion para ('voice_guide', 'es'): calibrated_criteria por defecto vacio.
    veredicto = evaluate(actual, baseline=base, unstable=(), explanations=())

    assert veredicto.blocked is False
    assert "voice_guide@es" in veredicto.judge_not_calibrated
    assert CASE_KEY not in veredicto.unexplained_failures
    assert CASE_KEY not in veredicto.blocking_failures


def test_un_criterio_del_juez_calibrado_si_cuenta_y_bloquea_si_falla() -> None:
    base = _linea_base_con(CASE_KEY, CaseStatus.PASSED)
    actual = reporte(
        (
            fila(
                CASE_KEY,
                status=CaseStatus.FAILED,
                criterion="voice_guide",
                judgment=JudgmentKind.JUDGE,
            ),
        )
    )

    veredicto = evaluate(
        actual,
        baseline=base,
        unstable=(),
        explanations=(),
        rules=GateRules(calibrated_criteria=frozenset({("voice_guide", "es")})),
    )

    assert veredicto.blocked is True
    assert CASE_KEY in veredicto.unexplained_failures
    assert veredicto.judge_not_calibrated == ()


def test_la_latencia_se_publica_pero_no_es_compuerta_ni_mueve_la_comparacion() -> None:
    """Una linea base con una latencia pesima y una corrida con una excelente --o al reves-- dan
    el mismo veredicto: la latencia del chat se publica y no bloquea (NFR4 no es compuerta aqui)."""

    def _con_latencia(p95_ms: int) -> Baseline:
        return _linea_base_con(CASE_KEY, CaseStatus.PASSED).evolve(
            latencies={
                Channel.CHAT: ChannelLatency(
                    datasets=("DS-2",),
                    es=LatencySummary(turns=40, p50_ms=500, p95_ms=p95_ms),
                    en=LatencySummary(turns=40, p50_ms=500, p95_ms=p95_ms),
                )
            }
        )

    actual = reporte((fila(CASE_KEY),)).evolve(
        latencies={
            Channel.CHAT: ChannelLatency(
                datasets=("DS-2",),
                es=LatencySummary(turns=40, p50_ms=9000, p95_ms=60000),
                en=LatencySummary(turns=40, p50_ms=9000, p95_ms=60000),
            )
        }
    )

    rapida = evaluate(actual, baseline=_con_latencia(800), unstable=(), explanations=())
    lenta = evaluate(actual, baseline=_con_latencia(90000), unstable=(), explanations=())

    assert rapida == lenta
    assert rapida.blocked is False


def test_una_compuerta_de_codigo_sigue_bloqueando_con_el_juez_descalibrado() -> None:
    """BR3.3: la descalibracion del juez apaga solo los criterios que el juzga."""
    base = _linea_base_con(CASE_KEY, CaseStatus.PASSED)
    actual = reporte(
        (fila(CASE_KEY, status=CaseStatus.FAILED, criterion="money_rule_forces_referral"),)
    )

    veredicto = evaluate(
        actual,
        baseline=base,
        unstable=(),
        explanations=(),
        rules=GateRules(blocking_criteria=frozenset({"money_rule_forces_referral"})),
    )

    assert veredicto.blocked is True
    assert CASE_KEY in veredicto.blocking_failures
