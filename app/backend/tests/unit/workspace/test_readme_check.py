"""`readme:gen` y `readme:check` sobre un arbol temporal y sobre el repositorio (U22, BR4.2).

La linea base se siembra escribiendo su archivo, como en las pruebas de las cifras:
no hace falta base de datos.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from untangle import paths
from untangle.evals.gates.loading import publish_baseline, save_last_run_digest
from untangle.evals.gates.models import Baseline, LastRunDigest
from untangle.evals.models import CaseStatus, RootCause
from untangle.workspace import readme_check

MARCAS = (
    "<!-- generated:how-it-fails:begin -->\n<!-- generated:how-it-fails:end -->",
    "<!-- generated:evaluation-report:begin -->\n<!-- generated:evaluation-report:end -->",
)


@pytest.fixture
def arbol(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "mise.toml").write_text("", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        f"# X\n\n## How it fails\n\n{MARCAS[0]}\n\n## Narrativa\n\nDe Miguel.\n\n"
        f"## Evaluation report\n\n{MARCAS[1]}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("UNTANGLE_REPO_ROOT", str(tmp_path))
    return tmp_path


def _sembrar(commit: str = "0123456789abcdef0123456789abcdef01234567") -> None:
    publish_baseline(
        Baseline.model_validate(
            {
                "baseline_id": "base-1",
                "run_id": "run-1",
                "commit_sha": commit,
                "published_at": datetime(2026, 10, 1, tzinfo=UTC),
                "case_verdicts": {"DS-2/es/017": CaseStatus.PASSED},
            }
        ),
        paths.baselines_dir(),
    )


def _sembrar_resumen(caso: str = "DS-2/es/017") -> None:
    # Un resumen con un caso en rojo: lo que una linea base publicada nunca trae.
    save_last_run_digest(
        LastRunDigest.model_validate(
            {
                "run_id": "run-2",
                "commit_sha": "fedcba9876543210fedcba9876543210fedcba98",
                "produced_at": datetime(2026, 10, 2, tzinfo=UTC),
                "case_verdicts": {caso: CaseStatus.FAILED},
                "root_causes": {caso: RootCause.EXTRACTION},
            }
        )
    )


def test_sin_linea_base_lo_generado_pasa_el_chequeo(arbol: Path) -> None:
    assert readme_check.generate() is True
    assert readme_check.check() == []
    assert readme_check.main(["check"]) == 0
    assert "Not measured" in (arbol / "README.md").read_text(encoding="utf-8")


def test_generar_sin_cambios_lo_dice_y_no_reescribe(arbol: Path) -> None:
    readme_check.generate()

    assert readme_check.generate() is False


def test_con_resumen_la_seccion_nombra_el_caso_en_rojo_y_el_chequeo_pasa(arbol: Path) -> None:
    _sembrar_resumen()
    readme_check.generate()

    assert "`DS-2/es/017`" in (arbol / "README.md").read_text(encoding="utf-8")
    assert readme_check.check() == []


def test_una_linea_base_sin_resumen_no_inventa_fallos(arbol: Path) -> None:
    # La linea base es verde por construccion: si "Como falla" la leyera, diria
    # siempre que nada fallo aunque el ultimo reporte tenga 42 casos en rojo.
    _sembrar()
    readme_check.generate()

    texto = (arbol / "README.md").read_text(encoding="utf-8")
    assert "no full evaluation run has been recorded" in texto
    assert "No case failed" not in texto
    assert readme_check.check() == []


def test_publicar_fuentes_sin_regenerar_pone_rojo_el_chequeo(
    arbol: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    readme_check.generate()
    _sembrar()
    _sembrar_resumen()

    assert readme_check.main(["check"]) == 1
    error = capsys.readouterr().err
    assert "section 'How it fails'" in error
    assert "section 'Evaluation report'" in error
    assert "readme:gen" in error


def test_un_resumen_roto_se_nombra_y_no_se_ignora(
    arbol: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths.last_run_digest_path().parent.mkdir(parents=True, exist_ok=True)
    paths.last_run_digest_path().write_text('{"run_id": "x"}', encoding="utf-8")

    assert readme_check.main(["check"]) == 1
    assert "last-run.json" in capsys.readouterr().err


def test_el_readme_manipulado_a_mano_falla_nombrando_la_seccion(arbol: Path) -> None:
    _sembrar_resumen()
    readme_check.generate()
    archivo = arbol / "README.md"
    archivo.write_text(
        archivo.read_text(encoding="utf-8").replace("DS-2/es/017", "DS-2/es/018"),
        encoding="utf-8",
    )

    [problema] = readme_check.check()

    assert problema.startswith("README.md, section 'How it fails'")


def test_un_readme_sin_marcas_falla_y_no_se_inventan(arbol: Path) -> None:
    (arbol / "README.md").write_text("# X\n\nSin marcas.\n", encoding="utf-8")

    assert len(readme_check.check()) == 2
    assert readme_check.main(["gen"]) == 1
    assert (arbol / "README.md").read_text(encoding="utf-8") == "# X\n\nSin marcas.\n"


def test_un_readme_que_no_existe_falla(arbol: Path) -> None:
    (arbol / "README.md").unlink()

    assert readme_check.main(["check"]) == 1


def test_un_argumento_que_no_es_un_modo_es_un_error_de_uso() -> None:
    assert readme_check.main(["otra-cosa"]) == 64


def test_el_readme_del_repositorio_coincide_con_sus_fuentes() -> None:
    # La misma comprobacion que corre el guion de verificacion, sobre el README real.
    assert readme_check.check() == []


#: Las ocho piezas que AC4.1.2 exige, con el encabezado que las lleva. Se
#: comprueba que **estan y en este orden**, no que sean las unicas: las seis
#: narrativas las escribe Miguel en la semana 11 (FD-U22-9), y un recuento exacto
#: pondria rojo el dia que anada una seccion suya, que es trabajo legitimo.
PIEZAS = (
    "What it does",
    "What it does not do",
    "How it fails",
    "Architecture",
    "Principles, controls and evidence",
    "Evaluation report",
    "Attributions",
    "Run it",
)


def test_el_readme_del_repositorio_tiene_la_estructura_que_fija_ac4_1() -> None:
    texto = paths.readme_path().read_text(encoding="utf-8")
    primero = texto.index("\n## ")
    encabezados = [linea[3:] for linea in texto.splitlines() if linea.startswith("## ")]

    assert texto[:primero].strip().splitlines()[0].startswith("# ")
    assert len(texto[:primero].split("\n\n")) >= 2  # el parrafo de arriba existe
    # Los tres primeros son esos tres y en ese orden (AC4.1.1).
    assert encabezados[:3] == list(PIEZAS[:3])
    # Y las ocho piezas estan, en orden, admitiendo secciones de Miguel entre ellas.
    assert [e for e in encabezados if e in PIEZAS] == list(PIEZAS)


def test_el_chequeo_esta_en_el_guion_de_verificacion_y_en_el_archivo_de_tareas() -> None:
    # Sin esto, quitar la linea del guion dejaria el chequeo existiendo y sin correr
    # en ninguna entrega: justo la forma de defecto que BR4.2 existe para impedir.
    raiz = paths.repo_root()
    guion = (raiz / "scripts" / "verify.sh").read_text(encoding="utf-8")
    tareas = (raiz / "mise.toml").read_text(encoding="utf-8")

    assert "mise run readme:check" in guion
    assert '[tasks."readme:check"]' in tareas
    assert '[tasks."readme:gen"]' in tareas
