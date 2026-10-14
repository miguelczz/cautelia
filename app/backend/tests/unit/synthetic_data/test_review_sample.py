"""La muestra de diez clausulas por emisora que revisa Miguel (BR5.4, AC5.4.5, AC5.5.6).

Lo que tiene que ser cierto: que las diez salgan de la semilla registrada y de la
ruta del archivo --y no de una eleccion a mano--, que ninguna sea distractora,
que el archivo lo lea el cargador de fuentes, y que el comando **nunca**
sobrescriba una muestra que puede llevar el veredicto de Miguel.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import date
from pathlib import Path

import pytest
import yaml

from untangle.synthetic_data import cli, review_sample
from untangle.synthetic_data.manifest import SEED
from untangle.synthetic_data.models import REVIEW_SAMPLE_SIZE, ReviewSample

from .apoyo import RAIZ_REAL

DATOS_REALES = RAIZ_REAL / "app" / "data"
HOY = date(2026, 9, 21)


def _clausulas(raiz: Path, tenant_id: str, cuantas: int, distractoras: int = 0) -> None:
    carpeta = raiz / "tenants" / tenant_id / "clauses"
    carpeta.mkdir(parents=True, exist_ok=True)
    clausulas = [
        {
            "clause_id": f"EMI-PAP-2026-A.EXCL.{i:02d}",
            "part": "Parte A",
            "is_distractor": i < distractoras,
        }
        for i in range(cuantas)
    ]
    (carpeta / "XXX.json").write_text(json.dumps({"clauses": clausulas}), encoding="utf-8")


def test_con_la_misma_semilla_y_la_misma_fecha_sale_la_misma_muestra(tmp_path: Path) -> None:
    _clausulas(tmp_path, "emisora", 40)
    elegibles = review_sample.candidates(tmp_path, "emisora")

    primera = review_sample.draw("emisora", HOY, elegibles, seed=SEED)
    segunda = review_sample.draw("emisora", HOY, elegibles, seed=SEED)
    otro_dia = review_sample.draw("emisora", date(2026, 9, 22), elegibles, seed=SEED)

    assert primera == segunda
    assert len(set(primera.clause_ids)) == REVIEW_SAMPLE_SIZE
    assert otro_dia.clause_ids != primera.clause_ids


def test_ninguna_distractora_entra_en_la_muestra(tmp_path: Path) -> None:
    """Un distractor es, por diseno, un calco de otra clausula del mismo corpus."""
    _clausulas(tmp_path, "emisora", 20, distractoras=10)

    elegibles = review_sample.candidates(tmp_path, "emisora")
    muestra = review_sample.draw("emisora", HOY, elegibles, seed=SEED)

    assert {c.clause_id for c in elegibles} == {
        f"EMI-PAP-2026-A.EXCL.{i:02d}" for i in range(10, 20)
    }
    assert set(muestra.clause_ids) == {c.clause_id for c in elegibles}


def test_con_menos_de_diez_candidatas_no_hay_muestra(tmp_path: Path) -> None:
    _clausulas(tmp_path, "emisora", 9)

    with pytest.raises(review_sample.ReviewSampleError, match="genere el corpus"):
        review_sample.draw("emisora", HOY, review_sample.candidates(tmp_path, "emisora"), seed=SEED)


def test_el_archivo_escrito_lo_lee_el_modelo_y_dice_donde_leer_cada_clausula(
    tmp_path: Path,
) -> None:
    _clausulas(tmp_path, "emisora", 30)
    elegibles = review_sample.candidates(tmp_path, "emisora")
    muestra = review_sample.draw("emisora", HOY, elegibles, seed=SEED)

    texto = review_sample.render(muestra, elegibles, HOY)

    assert ReviewSample.model_validate(yaml.safe_load(texto)) == muestra
    assert all(f"{clave}  # Parte A, en app/data/" in texto for clave in muestra.clause_ids)


@pytest.mark.parametrize("emisora", ["stonecroft", "sunmeadow"])
def test_las_muestras_versionadas_son_las_que_saca_el_comando(emisora: str) -> None:
    """Cualquiera puede comprobar que las diez no se escogieron a mano."""
    archivo = DATOS_REALES / "sources" / review_sample.review_path(emisora, HOY)
    elegibles = review_sample.candidates(DATOS_REALES, emisora)

    versionada = ReviewSample.model_validate(yaml.safe_load(archivo.read_text(encoding="utf-8")))

    assert versionada.sample_seed == SEED
    assert (
        versionada.clause_ids == review_sample.draw(emisora, HOY, elegibles, seed=SEED).clause_ids
    )
    # El veredicto es de Miguel (AC5.4.5, AC5.5.6): o la muestra espera su
    # revision, con los tres campos vacios, o la tiene completa, con fecha y el
    # commit del corpus que leyo. Un veredicto a medias no cuenta como revision.
    anotados = (versionada.verdict, versionada.reviewed_on, versionada.commit)
    if versionada.verdict is None:
        assert anotados == (None, None, None)
    else:
        assert versionada.reviewed_on is not None
        assert versionada.commit is not None
        assert re.fullmatch(r"[0-9a-f]{40}", versionada.commit)


def test_ninguna_agencia_tiene_muestra() -> None:
    """Una agencia no tiene texto propio: sus clausulas son copias (BR4.2)."""
    assert sorted(p.name for p in (DATOS_REALES / "sources" / "reviews").glob("*.yaml")) == [
        "stonecroft-2026-09-21.yaml",
        "sunmeadow-2026-09-21.yaml",
    ]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Un arbol con la configuracion real de aseguradoras y el corpus real de las emisoras."""
    shutil.copytree(
        RAIZ_REAL / "app" / "config" / "tenants", tmp_path / "app" / "config" / "tenants"
    )
    for emisora in ("stonecroft", "sunmeadow"):
        shutil.copytree(
            DATOS_REALES / "tenants" / emisora / "clauses",
            tmp_path / "app" / "data" / "tenants" / emisora / "clauses",
        )
    return tmp_path


def test_el_comando_escribe_una_muestra_por_emisora_y_repetirlo_no_cambia_nada(
    repo: Path,
) -> None:
    datos = repo / "app" / "data"

    assert cli.run_sample(repo, datos, HOY) == 0
    escritas = {p.name: p.read_bytes() for p in (datos / "sources" / "reviews").glob("*.yaml")}
    assert cli.run_sample(repo, datos, HOY) == 0

    assert sorted(escritas) == ["stonecroft-2026-09-21.yaml", "sunmeadow-2026-09-21.yaml"]
    assert {
        p.name: p.read_bytes() for p in (datos / "sources" / "reviews").glob("*.yaml")
    } == escritas


def test_el_comando_nunca_sobrescribe_una_muestra_con_el_veredicto_de_miguel(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    datos = repo / "app" / "data"
    assert cli.run_sample(repo, datos, HOY) == 0
    archivo = datos / "sources" / review_sample.review_path("sunmeadow", HOY)
    revisada = archivo.read_text(encoding="utf-8").replace(
        "verdict: null", "verdict: own_text_structure_ok"
    )
    archivo.write_text(revisada, encoding="utf-8")

    assert cli.run_sample(repo, datos, HOY) == 1

    assert "no se sobrescribe" in capsys.readouterr().err
    assert archivo.read_text(encoding="utf-8") == revisada


def test_sin_fecha_el_comando_no_arranca() -> None:
    """La fecha no se lee del reloj: el generador no lo lee nunca (BR1.1)."""
    with pytest.raises(SystemExit) as salida:
        cli.main(["sample"])

    assert salida.value.code == 2
