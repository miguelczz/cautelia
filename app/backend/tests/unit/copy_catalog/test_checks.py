"""Pruebas de los seis chequeos del catalogo (AC5.8.1 a AC5.8.4).

Una prueba por chequeo, cada una con un catalogo de prueba que lo rompe **a
proposito**, y una septima que comprueba que un catalogo sano pasa los seis.

Lo que cada prueba afirma no es que el chequeo falle: es que el mensaje **nombre
la clave o el archivo culpable**. Un chequeo que solo dice "fallo" obliga a
buscar a mano lo que la herramienta ya sabia.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from untangle import paths
from untangle.copy_catalog import checks

RAIZ_REAL = paths.repo_root()

CATALOGO_SANO_ES = """
inbox:
  card:
    title:
      text: Caso abierto
      surface: inbox
"""

CATALOGO_SANO_EN = """
inbox:
  card:
    title:
      text: Open case
      surface: inbox
"""

CONSUMIDOR = '''
"""Modulo de prueba que consume la clave."""

CLAVE = "inbox.card.title"
'''


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Un arbol minimo con la forma del repositorio real."""
    copy_dir = tmp_path / "app" / "config" / "copy"
    copy_dir.mkdir(parents=True)
    (copy_dir / "es.yaml").write_text(CATALOGO_SANO_ES, encoding="utf-8")
    (copy_dir / "en.yaml").write_text(CATALOGO_SANO_EN, encoding="utf-8")
    shutil.copy(
        RAIZ_REAL / "app" / "config" / "copy" / "forbidden-forms.yaml",
        copy_dir / "forbidden-forms.yaml",
    )
    (copy_dir / "inline-allowlist.yaml").write_text("allowed: []\n", encoding="utf-8")

    src = tmp_path / "app" / "backend" / "src" / "untangle" / "inbox"
    src.mkdir(parents=True)
    (src / "api.py").write_text(CONSUMIDOR, encoding="utf-8")
    return tmp_path


# --- Camino feliz -------------------------------------------------------------


def test_un_catalogo_sano_pasa_los_seis_chequeos(repo: Path) -> None:
    assert checks.run_all(repo) == []


# --- Uno por chequeo ----------------------------------------------------------


def test_br3_1_una_clave_sin_pareja_falla_nombrando_la_clave(repo: Path) -> None:
    (repo / "app" / "config" / "copy" / "en.yaml").write_text(
        "inbox:\n  card:\n    subtitle:\n      text: Other\n      surface: inbox\n",
        encoding="utf-8",
    )

    hallazgos = checks.run_all(repo)

    de_paridad = [h for h in hallazgos if h.rule == "BR3.1"]
    assert {h.where for h in de_paridad} == {"inbox.card.title", "inbox.card.subtitle"}


def test_br3_2_una_clave_sin_consumidor_falla_nombrando_la_clave(repo: Path) -> None:
    (repo / "app" / "backend" / "src" / "untangle" / "inbox" / "api.py").write_text(
        "CLAVE = 'otra.cosa'\n", encoding="utf-8"
    )

    hallazgos = [h for h in checks.run_all(repo) if h.rule == "BR3.2"]

    assert [h.where for h in hallazgos] == ["inbox.card.title"]


def test_br3_3_una_cadena_visible_en_linea_falla_nombrando_el_archivo(repo: Path) -> None:
    archivo = repo / "app" / "backend" / "src" / "untangle" / "inbox" / "api.py"
    archivo.write_text(
        'CLAVE = "inbox.card.title"\nMENSAJE = "Su caso ya fue enviado al ajustador."\n',
        encoding="utf-8",
    )

    hallazgos = [h for h in checks.run_all(repo) if h.rule == "BR3.3"]

    assert len(hallazgos) == 1
    assert hallazgos[0].where.endswith("inbox/api.py:2")


def test_br3_4_una_clave_construida_en_ejecucion_falla_nombrando_el_archivo(repo: Path) -> None:
    archivo = repo / "app" / "backend" / "src" / "untangle" / "inbox" / "api.py"
    archivo.write_text(
        'CLAVE = "inbox.card.title"\n\n\ndef render(estado: str) -> str:\n    return t(estado)\n',
        encoding="utf-8",
    )

    hallazgos = [h for h in checks.run_all(repo) if h.rule == "BR3.4"]

    assert len(hallazgos) == 1
    assert hallazgos[0].where.endswith("inbox/api.py:5")


def test_br3_5_una_version_mayor_que_uno_sin_decision_falla_nombrando_la_clave(
    repo: Path,
) -> None:
    (repo / "app" / "config" / "copy" / "es.yaml").write_text(
        "inbox:\n  card:\n    title:\n      text: Caso abierto\n"
        "      surface: inbox\n      version: 2\n",
        encoding="utf-8",
    )

    hallazgos = [h for h in checks.run_all(repo) if h.rule == "BR3.5"]

    assert [h.where for h in hallazgos] == ["inbox.card.title (es)"]


def test_br3_6_una_forma_prohibida_falla_nombrando_la_clave_y_la_forma(repo: Path) -> None:
    (repo / "app" / "config" / "copy" / "es.yaml").write_text(
        "inbox:\n  card:\n    title:\n      text: Lo llamamos en 24 horas\n      surface: inbox\n",
        encoding="utf-8",
    )

    hallazgos = [h for h in checks.run_all(repo) if h.rule == "BR3.6"]

    assert hallazgos
    assert hallazgos[0].where == "inbox.card.title (es)"
    assert "FF-2" in hallazgos[0].detail


# --- El septimo chequeo: que el catalogo valide su esquema --------------------


def test_un_catalogo_que_no_carga_ya_no_pasa_los_chequeos(tmp_path: Path) -> None:
    """Un comprobador que aprueba un catalogo que el aplicativo rechaza es peor
    que no tenerlo: el fallo aparece lejos de su causa --en la redaccion, que
    falla cerrado y deja de emitir texto-- y ahi no dice de donde viene.

    Los otros seis chequeos leen el YAML crudo, asi que un `surface` fuera del
    conjunto cerrado los pasaba todos. Detectado construyendo U4, anadiendo las
    etiquetas del caso.
    """
    destino = tmp_path / "app" / "config" / "copy"
    destino.parent.mkdir(parents=True)
    shutil.copytree(paths.repo_root() / "app" / "config" / "copy", destino)
    for nombre in ("es", "en"):
        archivo = destino / f"{nombre}.yaml"
        archivo.write_text(
            archivo.read_text(encoding="utf-8").replace(
                "surface: system", "surface: inexistente", 1
            ),
            encoding="utf-8",
        )

    hallazgos = checks.check_schema(checks.load_raw_entries(destino))

    assert len(hallazgos) == 2
    assert all("surface" in hallazgo.detail for hallazgo in hallazgos)


def test_el_catalogo_de_verdad_valida_su_esquema() -> None:
    """La linea base: sin ella, un fallo del andamiaje se leeria como exito."""
    entradas = checks.load_raw_entries(paths.repo_root() / "app" / "config" / "copy")

    assert checks.check_schema(entradas) == []
