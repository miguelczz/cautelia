"""El resumen de la ultima corrida completa (U22, FD-U22-10, BR4.3).

No es una linea base: se escribe tambien en rojo y nunca desde un subconjunto. Las
reglas de forma viven en el tipo, asi que aqui se prueba el tipo y no a quien lo
construye.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from untangle.evals.gates import loading
from untangle.evals.gates.baseline import build_digest
from untangle.evals.gates.models import LastRunDigest
from untangle.evals.loading import LoadError
from untangle.evals.models import CaseStatus, NotMeasuredCause, RootCause

from .builders import fila, reporte

MOMENTO = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def _datos(**cambios: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "run_id": "run-1",
        "commit_sha": "abc1234",
        "produced_at": MOMENTO,
        "case_verdicts": {
            "DS-2/es/1": CaseStatus.FAILED,
            "DS-2/es/2": CaseStatus.PASSED,
            "DS-5/es/1": CaseStatus.NOT_MEASURED,
        },
        "root_causes": {"DS-2/es/1": RootCause.EXTRACTION},
        "not_measured_causes": {"DS-5/es/1": NotMeasuredCause.TARGET_UNAVAILABLE},
    }
    return base | cambios


def test_un_resumen_bien_formado_valida() -> None:
    assert LastRunDigest.model_validate(_datos()).run_id == "run-1"


def test_una_causa_raiz_de_un_caso_que_el_resumen_no_trae_no_valida() -> None:
    with pytest.raises(ValueError, match=r"DS-2/es/9"):
        LastRunDigest.model_validate(_datos(root_causes={"DS-2/es/9": RootCause.RULES}))


def test_una_causa_de_no_medido_de_un_caso_que_el_resumen_no_trae_no_valida() -> None:
    causas = {
        "DS-5/es/1": NotMeasuredCause.TARGET_UNAVAILABLE,
        "DS-5/es/9": NotMeasuredCause.QUOTA_EXHAUSTED,
    }
    with pytest.raises(ValueError, match=r"DS-5/es/9"):
        LastRunDigest.model_validate(_datos(not_measured_causes=causas))


def test_una_causa_de_no_medido_de_un_caso_que_si_se_midio_no_valida() -> None:
    causas = {
        "DS-5/es/1": NotMeasuredCause.TARGET_UNAVAILABLE,
        "DS-2/es/2": NotMeasuredCause.QUOTA_EXHAUSTED,
    }
    with pytest.raises(ValueError, match=r"si se midieron: DS-2/es/2"):
        LastRunDigest.model_validate(_datos(not_measured_causes=causas))


def test_un_caso_no_medido_sin_su_causa_no_valida() -> None:
    with pytest.raises(ValueError, match=r"sin su causa: DS-5/es/1"):
        LastRunDigest.model_validate(_datos(not_measured_causes={}))


def test_un_resumen_que_declara_subconjunto_no_valida() -> None:
    with pytest.raises(ValueError, match=r"subconjunto 'smoke'"):
        LastRunDigest.model_validate(_datos(subset="smoke"))


def test_un_identificador_de_caso_con_forma_invalida_no_valida() -> None:
    with pytest.raises(ValueError, match="forma invalida"):
        LastRunDigest.model_validate(_datos(case_verdicts={"caso suelto": CaseStatus.PASSED}))


def test_construirlo_desde_un_subconjunto_se_rechaza() -> None:
    rep = reporte((fila("DS-2/es/1"),), subset="smoke")

    with pytest.raises(ValidationError, match="subconjunto"):
        build_digest(rep)


def test_se_construye_de_una_corrida_en_rojo_con_todo_lo_que_la_seccion_necesita() -> None:
    rep = reporte(
        (
            fila("DS-2/es/1", status=CaseStatus.FAILED).evolve(root_cause=RootCause.NOT_BUILT),
            fila("DS-2/es/2", status=CaseStatus.PASSED),
            fila("DS-5/es/1", status=CaseStatus.NOT_MEASURED).evolve(
                not_measured_cause=NotMeasuredCause.PROVIDER_KEY_MISSING
            ),
        ),
        run_id="run-rojo",
        commit_sha="fedcba9",
        subset=None,
        comparable=False,
    )

    digest = build_digest(rep, produced_at=MOMENTO)

    assert (digest.run_id, digest.commit_sha, digest.produced_at) == (
        "run-rojo",
        "fedcba9",
        MOMENTO,
    )
    assert digest.case_verdicts["DS-2/es/1"] is CaseStatus.FAILED
    assert digest.root_causes == {"DS-2/es/1": RootCause.NOT_BUILT}
    assert digest.not_measured_causes == {"DS-5/es/1": NotMeasuredCause.PROVIDER_KEY_MISSING}


def test_se_guarda_y_se_lee_igual(tmp_path: Path) -> None:
    digest = LastRunDigest.model_validate(_datos())
    destino = tmp_path / "evals" / "last-run.json"

    assert loading.save_last_run_digest(digest, destino) == destino
    assert loading.load_last_run_digest(destino) == digest


def test_guardar_uno_nuevo_reemplaza_al_anterior(tmp_path: Path) -> None:
    destino = tmp_path / "last-run.json"
    loading.save_last_run_digest(LastRunDigest.model_validate(_datos()), destino)
    loading.save_last_run_digest(LastRunDigest.model_validate(_datos(run_id="run-2")), destino)

    leido = loading.load_last_run_digest(destino)
    assert leido is not None
    assert leido.run_id == "run-2"


def test_sin_archivo_no_hay_resumen_y_no_es_un_error(tmp_path: Path) -> None:
    assert loading.load_last_run_digest(tmp_path / "last-run.json") is None


def test_un_archivo_roto_se_nombra(tmp_path: Path) -> None:
    roto = tmp_path / "last-run.json"
    roto.write_text('{"run_id": "run-1"}', encoding="utf-8")

    with pytest.raises(LoadError, match=r"last-run\.json"):
        loading.load_last_run_digest(roto)


# --- Lo que el tablero "Que tan bien funciona" lee del resumen (2026-10-11) ---------


def test_un_resumen_escrito_antes_de_los_campos_nuevos_se_sigue_leyendo() -> None:
    """Son aditivos: lo que un resumen viejo no trae se muestra como no registrado."""
    digest = LastRunDigest.model_validate(_datos())

    assert digest.criteria_results == {}
    assert digest.blocking_criteria == ()
    assert digest.model_ids == {}
    assert digest.duration_seconds is None
    assert digest.dirty_tree is False


def test_los_criterios_de_un_caso_que_el_resumen_no_trae_se_rechazan() -> None:
    with pytest.raises(ValidationError, match="criterios de casos"):
        LastRunDigest.model_validate(_datos(criteria_results={"DS-2/es/99": {"x": "pass"}}))


def test_guarda_como_le_fue_a_cada_caso_en_cada_criterio() -> None:
    """Es lo que deja decir por que fallo un caso, y no solo que fallo."""
    rep = reporte(
        (
            fila("DS-3/es/a", status=CaseStatus.FAILED, criterion="citation_a"),
            fila("DS-3/es/b", status=CaseStatus.PASSED, criterion="citation_exists_b"),
        ),
        subset=None,
    )

    digest = build_digest(rep, produced_at=MOMENTO)

    assert digest.criteria_results == {
        "DS-3/es/a": {"citation_a": "fail"},
        "DS-3/es/b": {"citation_exists_b": "pass"},
    }


def test_solo_lista_las_compuertas_duras_que_esta_corrida_midio() -> None:
    """Una compuerta registrada que ningun caso ejecuto no se presenta como si se
    hubiera medido."""
    rep = reporte((fila("DS-3/es/b", criterion="citation_exists_b"),), subset=None)

    digest = build_digest(
        rep,
        produced_at=MOMENTO,
        blocking_criteria=frozenset({"citation_exists_b", "rt4_foreign_case_denied"}),
    )

    assert digest.blocking_criteria == ("citation_exists_b",)


def test_lleva_las_condiciones_de_la_corrida() -> None:
    rep = reporte((fila("DS-2/es/1"),), subset=None)
    con_modelos = rep.evolve(
        header=rep.header.evolve(
            model_ids={"anthropic:generation": "claude-haiku-5-5"},
            prompt_hashes={"intake_understanding.es": "0123456789ab"},
            duration_seconds=412.5,
        )
    )

    digest = build_digest(con_modelos, produced_at=MOMENTO, dirty_tree=True)

    assert digest.model_ids == {"anthropic:generation": "claude-haiku-5-5"}
    assert digest.prompt_hashes == {"intake_understanding.es": "0123456789ab"}
    assert digest.duration_seconds == 412.5
    assert digest.comparable is True
    assert digest.dirty_tree is True
