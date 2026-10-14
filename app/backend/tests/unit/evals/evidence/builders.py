"""Ayudantes de U22: una linea base sembrada en un arbol temporal.

Las pruebas de las cifras no necesitan base de datos: lo unico que leen es
`app/evals/baselines/current.json`, asi que se siembra escribiendo ese archivo.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from untangle import paths
from untangle.evals.gates.loading import publish_baseline
from untangle.evals.gates.models import Baseline
from untangle.evals.models import CaseStatus

PUBLICADA = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)

#: Identificadores reconocibles: si alguno aparece en una respuesta del panel, la
#: respuesta esta cargando casos (SEC-U22.1).
CASOS_SEMBRADOS = (
    "DS-2/es/sentinela-caso-7781",
    "DS-2/en/sentinela-caso-7782",
    "DS-3/es/sentinela-caso-7783",
)


def linea_base(
    *,
    metrics: dict[str, dict[str, float]] | None = None,
    casos: tuple[str, ...] = CASOS_SEMBRADOS,
    latencies: dict[str, Any] | None = None,
) -> Baseline:
    """Una linea base sembrada. Sin `latencies` es una publicada antes de que existieran."""
    return Baseline.model_validate(
        {
            "baseline_id": "base-0001",
            "run_id": "run-7",
            "commit_sha": "0123456789abcdef0123456789abcdef01234567",
            "published_at": PUBLICADA,
            "case_verdicts": dict.fromkeys(casos, CaseStatus.PASSED),
            "metrics": (
                metrics
                if metrics is not None
                else {
                    "field_extraction": {"es": 0.96, "en": 0.93},
                    "citation_precision": {"es": 1.0, "en": 0.95},
                }
            ),
            "model_ids": {"chat": "modelo-de-prueba"},
            **({} if latencies is None else {"latencies": latencies}),
        }
    )


def latencia_de_chat(
    *, es: tuple[int, int, int], en: tuple[int, int, int], datasets: tuple[str, ...] = ("DS-2",)
) -> dict[str, Any]:
    """La seccion `latencies` de una linea base, con (turnos, p50, p95) por idioma."""
    return {
        "chat": {
            "datasets": list(datasets),
            "es": {"turns": es[0], "p50_ms": es[1], "p95_ms": es[2]},
            "en": {"turns": en[0], "p50_ms": en[1], "p95_ms": en[2]},
        }
    }


@pytest.fixture
def raiz(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Un arbol temporal con la marca de raiz; `paths` apunta a el.

    La configuracion y los contratos versionados se enlazan desde el arbol real:
    levantar el aplicativo carga el catalogo de textos y las aseguradoras, y lo que
    se siembra en el arbol temporal es solo la linea base.
    """
    real = paths.config_dir()
    contratos = paths.openapi_path().parent
    (tmp_path / "mise.toml").write_text("", encoding="utf-8")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "config").symlink_to(real, target_is_directory=True)
    (tmp_path / "app" / "contracts").symlink_to(contratos, target_is_directory=True)
    monkeypatch.setenv("UNTANGLE_REPO_ROOT", str(tmp_path))
    return tmp_path


def sembrar(baseline: Baseline) -> None:
    publish_baseline(baseline, paths.baselines_dir())
