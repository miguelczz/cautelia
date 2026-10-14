"""El tablero de la ultima corrida: lo que la pestana "Que tan bien funciona" dibuja."""

from __future__ import annotations

from datetime import UTC, datetime

from untangle.evals.evidence.board import GateFamily, build_board, family_of
from untangle.evals.gates.models import LastRunDigest
from untangle.evals.models import CaseStatus, NotMeasuredCause, RootCause

MOMENTO = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


def _resumen() -> LastRunDigest:
    return LastRunDigest(
        run_id="run-1",
        commit_sha="abc1234",
        produced_at=MOMENTO,
        case_verdicts={
            "DS-3/es/a": CaseStatus.PASSED,
            "DS-3/es/b": CaseStatus.FAILED,
            "DS-3/en/a": CaseStatus.FAILED,
            "DS-2/es/c": CaseStatus.PASSED,
            "DS-6/es/rt4": CaseStatus.NOT_MEASURED,
        },
        root_causes={"DS-3/es/b": RootCause.RETRIEVAL},
        not_measured_causes={"DS-6/es/rt4": NotMeasuredCause.TARGET_UNAVAILABLE},
        criteria_results={
            "DS-3/es/a": {"citation_a": "pass", "citation_exists_a": "pass"},
            # No encontro la clausula esperada, pero no invento ninguna.
            "DS-3/es/b": {"citation_b": "fail", "citation_exists_b": "pass"},
            # Cito algo que no existe: la compuerta dura.
            "DS-3/en/a": {"citation_a": "pass", "citation_exists_a": "fail"},
            "DS-2/es/c": {"intake_ordered_story": "pass"},
        },
        blocking_criteria=("citation_exists_a", "citation_exists_b"),
        model_ids={"anthropic:generation": "claude-haiku-5-5", "gemini:embedding": "e-1"},
        duration_seconds=300.0,
    )


def test_los_dos_idiomas_van_lado_a_lado_y_no_se_suman() -> None:
    tablero = build_board(_resumen())

    assert (tablero.totals.es.passed, tablero.totals.es.failed, tablero.totals.es.not_measured) == (
        2,
        1,
        1,
    )
    assert (tablero.totals.en.passed, tablero.totals.en.failed) == (0, 1)


def test_cada_tipo_de_prueba_trae_su_recuento() -> None:
    por_conjunto = {d.dataset: d for d in build_board(_resumen()).datasets}

    assert set(por_conjunto) == {"DS-2", "DS-3", "DS-6"}
    assert por_conjunto["DS-3"].by_language.es.failed == 1
    assert por_conjunto["DS-6"].by_language.es.not_measured == 1


def test_una_compuerta_dura_cuenta_solo_sus_criterios() -> None:
    """El caso que no encontro la clausula esperada **paso** la compuerta: no invento
    ninguna. El que cito algo inexistente la fallo."""
    citas = next(g for g in build_board(_resumen()).gates if g.family is GateFamily.CITATIONS)

    assert citas.measured is True
    assert (citas.by_language.es.passed, citas.by_language.es.failed) == (2, 0)
    assert (citas.by_language.en.passed, citas.by_language.en.failed) == (0, 1)


def test_una_compuerta_que_la_corrida_no_ejecuto_se_dice_no_medida() -> None:
    """Las seis familias salen siempre: la que nadie midio no se omite ni sale verde."""
    tablero = build_board(_resumen())
    aislamiento = next(g for g in tablero.gates if g.family is GateFamily.ISOLATION)

    assert {g.family for g in tablero.gates} == set(GateFamily)
    assert aislamiento.measured is False


def test_los_fallos_dicen_que_fallo_y_lo_que_detiene_una_entrega_va_primero() -> None:
    fallos = build_board(_resumen()).failures

    assert [f.case_key for f in fallos] == ["DS-3/en/a", "DS-3/es/b"]
    assert fallos[0].blocking is True
    assert fallos[0].criteria == ("citation_exists_a",)
    assert fallos[1].blocking is False
    assert fallos[1].root_cause == "retrieval"


def test_lo_no_medido_se_agrupa_por_su_causa_y_los_modelos_se_nombran() -> None:
    tablero = build_board(_resumen())

    assert [(g.cause, g.count) for g in tablero.not_measured] == [("target_unavailable", 1)]
    assert tablero.models == ("claude-haiku-5-5", "e-1")


def test_cada_compuerta_bloqueante_registrada_tiene_familia() -> None:
    """Una compuerta nueva sin familia no saldria en el tablero y nadie lo notaria."""
    from untangle.evals import cli as evals_cli
    from untangle.evals.gates.gate import blocking_criteria_from_registry
    from untangle.evals.runner import api as runner_api

    runner_api.reset()
    try:
        evals_cli.register_all_probes()
        sin_familia = sorted(c for c in blocking_criteria_from_registry() if family_of(c) is None)
    finally:
        runner_api.reset()

    assert sin_familia == []
