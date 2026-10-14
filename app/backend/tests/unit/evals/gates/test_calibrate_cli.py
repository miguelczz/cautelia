"""Pruebas de `evals:calibrate`: nunca llama al juez, solo lee lo grabado."""

from __future__ import annotations

from pathlib import Path

import pytest

from untangle import paths
from untangle.evals.gates import calibrate_cli, loading


@pytest.fixture(autouse=True)
def _directorios_en_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(paths, "labels_dir", lambda: tmp_path / "labels")
    monkeypatch.setattr(paths, "judge_verdicts_dir", lambda: tmp_path / "judge-verdicts")
    monkeypatch.setattr(paths, "calibrations_dir", lambda: tmp_path / "calibrations")
    return tmp_path


def test_sin_etiquetas_se_niega(tmp_path: Path) -> None:
    codigo = calibrate_cli.main(["--judge-model", "m", "--rubric-version", "v1"])
    assert codigo == 2


def test_sin_veredictos_grabados_se_niega(tmp_path: Path) -> None:
    from datetime import date

    from untangle.evals.gates.models import HumanLabel, LabelVerdict, Split

    loading.save_labels(
        "es",
        (
            HumanLabel(
                transcript_id="t1",
                turn_index=0,
                criterion="voice_guide",
                language="es",
                split=Split.TEST,
                verdict=LabelVerdict.PASS,
                labeled_at=date(2026, 9, 24),
            ),
        ),
    )

    codigo = calibrate_cli.main(["--judge-model", "m", "--rubric-version", "v1"])
    assert codigo == 2


def test_con_etiquetas_y_veredictos_publica_la_calibracion(tmp_path: Path) -> None:
    from datetime import date

    import yaml

    from untangle.evals.gates.models import HumanLabel, LabelVerdict, Split

    etiquetas = tuple(
        HumanLabel(
            transcript_id=f"t{i}",
            turn_index=0,
            criterion="voice_guide",
            language="es",
            split=Split.TEST,
            verdict=LabelVerdict.PASS if i < 16 else LabelVerdict.FAIL,
            labeled_at=date(2026, 9, 24),
        )
        for i in range(32)
    )
    loading.save_labels("es", etiquetas)

    veredictos_dir = paths.judge_verdicts_dir()
    veredictos_dir.mkdir(parents=True, exist_ok=True)
    contenido = {
        "judge_model": "m",
        "rubric_version": "v1",
        "verdicts": [
            {
                "transcript_id": f"t{i}",
                "turn_index": 0,
                "criterion": "voice_guide",
                "language": "es",
                "verdict": "pass" if i < 16 else "fail",
            }
            for i in range(32)
        ],
    }
    (veredictos_dir / "m-v1.yaml").write_text(yaml.safe_dump(contenido), encoding="utf-8")

    codigo = calibrate_cli.main(["--judge-model", "m", "--rubric-version", "v1"])

    assert codigo == 0
    calibracion = loading.load_calibration("m", "v1")
    assert calibracion is not None
    assert calibracion.rate_for("voice_guide", "es") is not None
