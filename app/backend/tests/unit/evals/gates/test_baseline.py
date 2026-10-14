"""Pruebas de la publicacion de la linea base (BR2.1, F5).

Se niega a publicar si la corrida no esta en verde o no es comparable, y el
comando nombra el caso al negarse.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from untangle.evals.gates.baseline import BaselinePublicationError, build_baseline, publish
from untangle.evals.gates.loading import load_baseline
from untangle.evals.gates.models import Baseline
from untangle.evals.latency_summary import ChannelLatency, LatencySummary
from untangle.evals.models import CaseStatus, Channel, NonComparableCause, RootCause

from .builders import fila, reporte


def test_una_corrida_no_comparable_no_se_publica(tmp_path: Path) -> None:
    rep = reporte((fila("DS-2/es/1"),), comparable=False)
    rep = rep.evolve(
        header=rep.header.evolve(non_comparable_cause=NonComparableCause.QUOTA_EXHAUSTED)
    )

    with pytest.raises(BaselinePublicationError, match="no es comparable"):
        publish(rep, directory=tmp_path)


def test_un_subconjunto_no_se_publica_como_linea_base(tmp_path: Path) -> None:
    rep = reporte((fila("DS-2/es/1"),), subset="smoke")

    with pytest.raises(BaselinePublicationError, match="subconjunto"):
        publish(rep, directory=tmp_path)


def test_una_corrida_con_un_caso_en_rojo_se_niega_nombrandolo(tmp_path: Path) -> None:
    rep = reporte(
        (fila("DS-2/es/1", status=CaseStatus.FAILED),),
        subset=None,
    )

    with pytest.raises(BaselinePublicationError, match="DS-2/es/1"):
        publish(rep, directory=tmp_path)


def test_una_corrida_completa_y_en_verde_se_publica(tmp_path: Path) -> None:
    rep = reporte(
        (fila("DS-2/es/1", status=CaseStatus.PASSED),),
        subset=None,
    )

    baseline, propia, vigente = publish(rep, directory=tmp_path)

    assert baseline.case_verdicts == {"DS-2/es/1": CaseStatus.PASSED}
    assert propia.is_file()
    assert vigente.is_file()


def test_el_identificador_de_la_linea_base_lleva_fecha_y_commit_corto() -> None:
    rep = reporte(
        (fila("DS-2/es/1", status=CaseStatus.PASSED),),
        commit_sha="ee8d21dabcdef",
        subset=None,
    )
    baseline = build_baseline(rep)
    assert baseline.baseline_id.endswith("-ee8d21d")


def test_una_linea_base_no_lleva_causas_raiz() -> None:
    # Una linea base es una corrida verde y `publish()` rechaza los casos fallidos,
    # que son los unicos que tienen causa raiz: un campo que ninguna ruta de
    # produccion puede llenar es una trampa (FD-U22-10). Las causas viven en el
    # resumen de la ultima corrida.
    rep = reporte(
        (fila("DS-2/es/1", status=CaseStatus.PASSED).evolve(root_cause=RootCause.EXTRACTION),),
        subset=None,
    )

    assert "root_causes" not in Baseline.model_fields
    assert "root_causes" not in build_baseline(rep).model_dump()


# --- Las latencias viajan con la linea base, aparte de las tasas ----------------------


def _latencias() -> dict[Channel, ChannelLatency]:
    return {
        Channel.CHAT: ChannelLatency(
            datasets=("DS-2", "DS-6"),
            es=LatencySummary(turns=31, p50_ms=1180, p95_ms=2810),
            en=LatencySummary(turns=27, p50_ms=1420, p95_ms=3090),
        )
    }


def test_la_linea_base_guarda_las_latencias_del_reporte_en_su_propia_seccion() -> None:
    rep = reporte((fila("DS-2/es/1"),), subset=None).evolve(latencies=_latencias())

    baseline = build_baseline(rep)

    assert baseline.latencies == _latencias()
    # Aparte de las tasas: `metrics` sigue siendo tasas por criterio y nada mas.
    assert set(baseline.metrics) == {"citation_precision"}


def test_las_latencias_sobreviven_a_publicar_y_a_leer_la_linea_base(tmp_path: Path) -> None:
    rep = reporte((fila("DS-2/es/1"),), subset=None).evolve(latencies=_latencias())

    baseline, _, vigente = publish(rep, directory=tmp_path)

    assert load_baseline(vigente).latencies == _latencias() == baseline.latencies
    assert '"latencies"' in vigente.read_text(encoding="utf-8")


def test_un_reporte_sin_latencias_publica_la_seccion_vacia() -> None:
    baseline = build_baseline(reporte((fila("DS-2/es/1"),), subset=None))

    assert baseline.latencies == {}
