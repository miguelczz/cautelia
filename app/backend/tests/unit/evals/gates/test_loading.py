"""Pruebas de carga y escritura de la memoria entre corridas.

Todas escriben en un directorio temporal, nunca en `app/evals/`
(`unit-test-instructions.md`).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from untangle.evals.gates import loading
from untangle.evals.gates.models import (
    Baseline,
    HumanLabel,
    JudgeCalibration,
    JudgeCalibrationRate,
    JudgeVerdictRecord,
    LabelingQueueEntry,
    LabelVerdict,
    RegressionExplanation,
    Split,
)
from untangle.evals.loading import LoadError
from untangle.evals.models import CaseStatus, RootCause

MOMENTO = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


def _linea_base() -> Baseline:
    return Baseline(
        baseline_id="2026-09-24-abc1234",
        run_id="run-1",
        commit_sha="abc1234def",
        published_at=MOMENTO,
        case_verdicts={"DS-2/es/017": CaseStatus.PASSED},
    )


# --- Linea base -----------------------------------------------------------------


def test_sin_archivo_vigente_no_hay_linea_base(tmp_path: Path) -> None:
    assert loading.load_current_baseline(tmp_path) is None


def test_publicar_y_leer_la_linea_base_da_el_mismo_objeto(tmp_path: Path) -> None:
    original = _linea_base()
    propia, vigente = loading.publish_baseline(original, directory=tmp_path)

    assert propia.name == "2026-09-24-abc1234.json"
    assert vigente.name == "current.json"
    assert loading.load_current_baseline(tmp_path) == original
    assert loading.load_baseline(propia) == original


def test_una_linea_base_rota_nombra_el_archivo(tmp_path: Path) -> None:
    archivo = tmp_path / "current.json"
    archivo.write_text("{no es json valido", encoding="utf-8")

    with pytest.raises(LoadError, match=str(archivo)):
        loading.load_current_baseline(tmp_path)


# --- Inestables -------------------------------------------------------------


def test_sin_archivo_de_inestables_el_set_esta_vacio(tmp_path: Path) -> None:
    assert loading.load_unstable_cases(tmp_path / "unstable-cases.yaml") == ()


def test_un_archivo_de_inestables_valido_carga_sus_casos(tmp_path: Path) -> None:
    archivo = tmp_path / "unstable-cases.yaml"
    archivo.write_text(
        """
unstable_cases:
  - case_key: DS-2/es/017
    reason: dos corridas del mismo commit dieron veredictos distintos
    marked_at: 2026-09-24
    run_ids: [run-1, run-2]
    work_item: TICKET-42
""",
        encoding="utf-8",
    )
    casos = loading.load_unstable_cases(archivo)
    assert len(casos) == 1
    assert casos[0].case_key == "DS-2/es/017"


def test_un_archivo_de_inestables_roto_falla_nombrandolo(tmp_path: Path) -> None:
    archivo = tmp_path / "unstable-cases.yaml"
    archivo.write_text("unstable_cases: [1, 2, 3]", encoding="utf-8")

    with pytest.raises(LoadError, match=str(archivo)):
        loading.load_unstable_cases(archivo)


# --- Explicaciones de regresion -----------------------------------------------


def test_sin_archivo_de_explicaciones_no_hay_ninguna(tmp_path: Path) -> None:
    assert loading.load_regression_explanations(tmp_path / "regressions.yaml") == ()


def test_un_archivo_de_explicaciones_roto_se_trata_como_vacio(tmp_path: Path) -> None:
    """REL-U21.5: el fallo es hacia el lado seguro, nunca hacia detener la entrega
    por un problema de formato que no es del cambio que se esta revisando."""
    archivo = tmp_path / "regressions.yaml"
    archivo.write_text("esto: [no, es, la, forma, esperada", encoding="utf-8")

    assert loading.load_regression_explanations(archivo) == ()


def test_pero_schema_check_si_nombra_el_archivo_roto(tmp_path: Path) -> None:
    archivo = tmp_path / "regressions.yaml"
    archivo.write_text("esto: no es la forma esperada", encoding="utf-8")

    with pytest.raises(LoadError, match=str(archivo)):
        loading.validate_regression_explanations_file(archivo)


def test_un_archivo_de_explicaciones_valido_carga_sus_entradas(tmp_path: Path) -> None:
    archivo = tmp_path / "regressions.yaml"
    archivo.write_text(
        """
explanations:
  - case_keys: [DS-2/es/017]
    root_cause: rules
    explained_at: 2026-09-24
    commit_sha: abc1234def
""",
        encoding="utf-8",
    )
    explicaciones = loading.load_regression_explanations(archivo)
    assert explicaciones == (
        RegressionExplanation(
            case_keys=("DS-2/es/017",),
            root_cause=RootCause.RULES,
            explained_at=date(2026, 9, 24),
            commit_sha="abc1234def",
        ),
    )


# --- Etiquetas humanas (DS-7) ----------------------------------------------------


def test_sin_archivo_de_etiquetas_el_idioma_esta_vacio(tmp_path: Path) -> None:
    assert loading.load_labels("es", tmp_path) == ()


def test_guardar_y_leer_etiquetas_da_el_mismo_conjunto(tmp_path: Path) -> None:
    etiqueta = HumanLabel(
        transcript_id="t1",
        turn_index=0,
        criterion="voice_guide",
        language="es",
        split=Split.TEST,
        verdict=LabelVerdict.PASS,
        labeled_at=date(2026, 9, 24),
    )
    archivo = loading.save_labels("es", (etiqueta,), tmp_path)

    assert archivo.is_file()
    assert loading.load_labels("es", tmp_path) == (etiqueta,)


def test_un_archivo_de_etiquetas_roto_nombra_el_archivo(tmp_path: Path) -> None:
    archivo = tmp_path / "es.yaml"
    archivo.write_text("language: es\nlabels: [1, 2]", encoding="utf-8")

    with pytest.raises(LoadError, match=str(archivo)):
        loading.load_labels("es", tmp_path)


def test_sin_cola_de_etiquetado_esta_vacia(tmp_path: Path) -> None:
    assert loading.load_labeling_queue(tmp_path / "queue.yaml") == ()


def test_una_cola_de_etiquetado_valida_carga_sus_entradas(tmp_path: Path) -> None:
    archivo = tmp_path / "queue.yaml"
    archivo.write_text(
        """
entries:
  - transcript_id: t1
    turn_index: 0
    criterion: voice_guide
    language: es
    split: test
    agent_text: "Buenos dias, en que le puedo ayudar"
""",
        encoding="utf-8",
    )
    cola = loading.load_labeling_queue(archivo)
    assert len(cola) == 1
    assert cola[0].criterion == "voice_guide"


def test_la_cola_guardada_se_lee_igual_y_en_el_mismo_orden(tmp_path: Path) -> None:
    entradas = tuple(
        LabelingQueueEntry(
            transcript_id=f"t{n}",
            turn_index=n,
            criterion="voice_guide",
            language="es" if n % 2 else "en",
            split=Split.TEST,
            agent_text=f"Lamento lo ocurrido: ¿cuál es su póliza? ({n})",
            context=None if n == 0 else f"persona {n}",
        )
        for n in range(4)
    )
    archivo = tmp_path / "labels" / "queue.yaml"

    escrito = loading.save_labeling_queue(entradas, archivo)

    assert escrito == archivo
    assert loading.load_labeling_queue(archivo) == entradas
    # Sin contexto no se escribe un `context: null` que nadie pidio, y el texto no se escapa.
    contenido = archivo.read_text(encoding="utf-8")
    assert "null" not in contenido
    assert "¿cuál es su póliza?" in contenido
    # Y no queda el temporal a medias.
    assert [p.name for p in archivo.parent.iterdir()] == ["queue.yaml"]


def test_una_cola_vacia_guardada_se_puede_volver_a_leer(tmp_path: Path) -> None:
    archivo = tmp_path / "queue.yaml"

    loading.save_labeling_queue((), archivo)

    assert loading.load_labeling_queue(archivo) == ()


def test_una_cola_vieja_sin_contexto_se_sigue_leyendo(tmp_path: Path) -> None:
    """`context` es aditivo: una cola armada antes de que existiera no se rompe."""
    archivo = tmp_path / "queue.yaml"
    archivo.write_text(
        """
entries:
  - transcript_id: t1
    turn_index: 2
    criterion: voice_guide
    language: es
    split: test
    agent_text: "Cual es su placa"
    context: "Choque en la autopista"
""",
        encoding="utf-8",
    )
    cola = loading.load_labeling_queue(archivo)
    assert cola[0].context == "Choque en la autopista"


# --- Veredictos grabados del juez -------------------------------------------------


def test_sin_veredictos_grabados_esta_vacio(tmp_path: Path) -> None:
    assert loading.load_judge_verdicts("modelo-x", "v1", tmp_path) == ()


def test_veredictos_grabados_se_leen_por_modelo_y_rubrica_exactos(tmp_path: Path) -> None:
    archivo = tmp_path / "modelo-x-v1.yaml"
    archivo.write_text(
        """
judge_model: modelo-x
rubric_version: v1
verdicts:
  - transcript_id: t1
    turn_index: 0
    criterion: voice_guide
    language: es
    verdict: pass
""",
        encoding="utf-8",
    )
    veredictos = loading.load_judge_verdicts("modelo-x", "v1", tmp_path)
    assert veredictos == (
        JudgeVerdictRecord(
            transcript_id="t1",
            turn_index=0,
            criterion="voice_guide",
            language="es",
            verdict=LabelVerdict.PASS,
        ),
    )
    # Otra combinacion de modelo y rubrica no ve este archivo (BR3.2).
    assert loading.load_judge_verdicts("modelo-x", "v2", tmp_path) == ()


# --- Calibraciones -----------------------------------------------------------------


def test_sin_calibracion_para_esa_combinacion_da_none(tmp_path: Path) -> None:
    assert loading.load_calibration("modelo-x", "v1", tmp_path) is None


def test_guardar_y_leer_una_calibracion_da_el_mismo_objeto(tmp_path: Path) -> None:
    calibracion = JudgeCalibration(
        calibration_id="modelo-x-v1-2026-09-25",
        judge_model="modelo-x",
        rubric_version="v1",
        measured_at=MOMENTO,
        split=Split.TEST,
        rates=(
            JudgeCalibrationRate(
                criterion="voice_guide",
                language="es",
                n=20,
                tpr=1.0,
                tnr=1.0,
                ci_low_tpr=0.85,
                ci_low_tnr=0.85,
            ),
        ),
    )
    archivo = loading.save_calibration(calibracion, tmp_path)

    assert archivo.name == "modelo-x-v1.json"
    assert loading.load_calibration("modelo-x", "v1", tmp_path) == calibracion
