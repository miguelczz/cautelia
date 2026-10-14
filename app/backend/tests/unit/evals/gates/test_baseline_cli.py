"""`evals:baseline` escribe el resumen siempre y antes de decidir si publica (U22, BR4.3).

El corredor no corre: se sustituye por un reporte armado en la prueba.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from untangle import paths
from untangle.evals.gates import baseline_cli, loading
from untangle.evals.latency_summary import ChannelLatency, LatencySummary
from untangle.evals.models import CaseStatus, Channel, RootCause
from untangle.evals.report import EvalReport
from untangle.evals.runner import runner

from .builders import fila, reporte


@pytest.fixture
def arbol(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "mise.toml").write_text("", encoding="utf-8")
    monkeypatch.setenv("UNTANGLE_REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(baseline_cli, "register_all_probes", lambda: None)
    return tmp_path


def _correr(monkeypatch: pytest.MonkeyPatch, rep: EvalReport) -> int:
    subsets: list[str | None] = []

    async def falso(*, subset: str | None, settings: object) -> SimpleNamespace:
        subsets.append(subset)
        return SimpleNamespace(report=rep)

    monkeypatch.setattr(runner, "run_evaluation", falso)
    codigo = baseline_cli.main([])
    # El comando nunca acepta ni pasa un subconjunto (F5).
    assert subsets == [None]
    return codigo


def test_una_corrida_en_rojo_deja_el_resumen_y_sigue_devolviendo_uno(
    arbol: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rep = reporte(
        (
            fila("DS-2/es/1", status=CaseStatus.FAILED).evolve(root_cause=RootCause.NOT_BUILT),
            fila("DS-2/es/2", status=CaseStatus.PASSED),
        ),
        subset=None,
    )

    assert _correr(monkeypatch, rep) == 1

    digest = loading.load_last_run_digest()
    assert digest is not None
    assert digest.root_causes == {"DS-2/es/1": RootCause.NOT_BUILT}
    # Y la linea base no se publico: el resumen no la sustituye.
    assert not paths.current_baseline_path().exists()


def test_una_corrida_en_verde_deja_el_resumen_y_publica_la_linea_base(
    arbol: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rep = reporte((fila("DS-2/es/1", status=CaseStatus.PASSED),), subset=None)

    assert _correr(monkeypatch, rep) == 0

    assert loading.load_last_run_digest() is not None
    assert paths.current_baseline_path().is_file()


def _sin_correr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Con `--report` el corredor no puede correr: lo que se publica ya se gasto."""

    async def prohibido(*, subset: str | None, settings: object) -> SimpleNamespace:
        msg = "con --report no se corre nada"
        raise AssertionError(msg)

    monkeypatch.setattr(runner, "run_evaluation", prohibido)


def _guardar(rep: EvalReport, donde: Path) -> Path:
    archivo = donde / "reporte.json"
    archivo.write_text(rep.model_dump_json(), encoding="utf-8")
    return archivo


def test_con_report_publica_la_linea_base_del_reporte_con_sus_latencias_sin_correr_nada(
    arbol: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La forma de llevar a la linea base la latencia que solo mide la corrida con el modelo:
    se corre `evals:completa` una vez y se publica su reporte, sin volver a gastar."""
    _sin_correr(monkeypatch)
    rep = reporte((fila("DS-2/es/1", status=CaseStatus.PASSED),), subset=None).evolve(
        latencies={
            Channel.CHAT: ChannelLatency(
                datasets=("DS-2",),
                es=LatencySummary(turns=31, p50_ms=1180, p95_ms=2810),
                en=LatencySummary(turns=27, p50_ms=1420, p95_ms=3090),
            )
        }
    )

    assert baseline_cli.main(["--report", str(_guardar(rep, arbol))]) == 0

    publicada = loading.load_current_baseline()
    assert publicada is not None
    assert publicada.latencies == rep.latencies
    # No escribe un resumen nuevo: ese lo dejo la corrida que produjo el reporte.
    assert loading.load_last_run_digest() is None


def test_con_report_las_condiciones_de_publicacion_son_las_de_siempre(
    arbol: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _sin_correr(monkeypatch)
    en_rojo = reporte((fila("DS-2/es/1", status=CaseStatus.FAILED),), subset=None)

    assert baseline_cli.main(["--report", str(_guardar(en_rojo, arbol))]) == 1

    assert "DS-2/es/1" in capsys.readouterr().err
    assert not paths.current_baseline_path().exists()


def test_con_report_un_archivo_ilegible_no_publica_nada(
    arbol: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _sin_correr(monkeypatch)
    roto = arbol / "roto.json"
    roto.write_text("{no es un reporte", encoding="utf-8")

    assert baseline_cli.main(["--report", str(roto)]) == 2
    assert baseline_cli.main(["--report", str(arbol / "no-existe.json")]) == 2

    assert "no se pudo leer el reporte" in capsys.readouterr().err
    assert not paths.current_baseline_path().exists()


def test_el_resumen_vive_junto_a_las_lineas_base_y_no_en_tmp(arbol: Path) -> None:
    assert paths.last_run_digest_path() == arbol / "app" / "evals" / "last-run.json"
    assert paths.last_run_digest_path().parent == paths.baselines_dir().parent
