"""Pruebas de la carga desde archivos versionados.

El sistema de archivos es real, sobre un directorio temporal: no se simula,
porque lo que se prueba es precisamente el comportamiento del listado y del
orden. Ninguna prueba necesita red, base de datos ni credenciales.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from untangle.evals.loading import (
    LoadError,
    check_language_parity,
    load_cases,
    load_manifest,
    load_subset,
    resolve_subset_cases,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture
def arbol_de_casos(tmp_path: Path) -> Path:
    """Dos casos validos, escritos en subdirectorios de nombre contrario al orden.

    El nombre del directorio va al reves del identificador a proposito: si el
    orden saliera del sistema de archivos, la prueba de orden pasaria por
    casualidad.
    """
    raiz = tmp_path / "cases"
    (raiz / "zz").mkdir(parents=True)
    (raiz / "aa").mkdir(parents=True)
    shutil.copy(FIXTURES / "case_ok_es.yaml", raiz / "zz" / "017.yaml")
    shutil.copy(FIXTURES / "case_ok_en.yaml", raiz / "aa" / "017.yaml")
    return raiz


# --- Camino feliz -------------------------------------------------------------


def test_el_orden_de_los_casos_es_el_mismo_en_dos_cargas(arbol_de_casos: Path) -> None:
    primera = [caso.case_key for caso in load_cases(arbol_de_casos)]
    segunda = [caso.case_key for caso in load_cases(arbol_de_casos)]

    assert primera == segunda
    # Y el orden sale del identificador, no del sistema de archivos: `en` va
    # antes que `es` aunque su archivo este en el directorio `aa`.
    assert primera == ["DS-2/en/017", "DS-2/es/017"]


# --- Casos de error y de borde ------------------------------------------------


def test_un_caso_que_no_valida_su_esquema_falla_nombrando_el_archivo_y_la_clave(
    tmp_path: Path,
) -> None:
    shutil.copy(FIXTURES / "case_bad_schema.yaml", tmp_path / "roto.yaml")

    with pytest.raises(LoadError) as excinfo:
        load_cases(tmp_path)

    mensaje = str(excinfo.value)
    assert "roto.yaml" in mensaje
    assert "dataset" in mensaje


def test_un_identificador_del_subconjunto_que_no_existe_detiene_la_carga_nombrandolo(
    arbol_de_casos: Path, tmp_path: Path
) -> None:
    subconjuntos = tmp_path / "subsets"
    subconjuntos.mkdir()
    shutil.copy(FIXTURES / "subset_unknown_case.yaml", subconjuntos / "roto.yaml")

    subconjunto = load_subset("roto", subconjuntos)
    with pytest.raises(LoadError) as excinfo:
        resolve_subset_cases(subconjunto, load_cases(arbol_de_casos))

    assert "DS-3/en/404" in str(excinfo.value)


def test_un_subconjunto_inexistente_nombra_el_archivo_que_se_esperaba(tmp_path: Path) -> None:
    with pytest.raises(LoadError) as excinfo:
        load_subset("no-existe", tmp_path)

    assert "no-existe.yaml" in str(excinfo.value)


def test_un_manifiesto_al_que_le_faltan_conjuntos_falla_nombrandolos(tmp_path: Path) -> None:
    archivo = tmp_path / "manifest.yaml"
    archivo.write_text(
        "datasets:\n  - dataset: DS-2\n    count: 0\n",
        encoding="utf-8",
    )

    with pytest.raises(LoadError) as excinfo:
        load_manifest(archivo)

    mensaje = str(excinfo.value)
    assert "DS-1" in mensaje
    assert "DS-8" in mensaje


def test_un_conjunto_no_construido_sin_razon_es_invalido(tmp_path: Path) -> None:
    archivo = tmp_path / "manifest.yaml"
    lineas = ["datasets:"]
    for numero in range(1, 9):
        lineas.append(f"  - dataset: DS-{numero}")
        lineas.append("    built: false" if numero == 5 else "    count: 0")
    archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    with pytest.raises(LoadError) as excinfo:
        load_manifest(archivo)

    assert "DS-5" in str(excinfo.value)


# --- Paridad por idioma (P12, NFR20.2) ----------------------------------------


def test_dos_casos_que_son_pareja_no_dan_ningun_problema_de_paridad(
    arbol_de_casos: Path,
) -> None:
    assert check_language_parity(load_cases(arbol_de_casos)) == ()


def test_un_caso_sin_pareja_en_el_otro_idioma_se_nombra_con_la_que_falta(
    tmp_path: Path,
) -> None:
    """El caso en espanol se queda solo: la comprobacion nombra la pareja que falta.

    Se comprueba tambien que el caso que si tiene idioma propio no se reporta
    dos veces: el problema es uno, y es del caso huerfano.
    """
    raiz = tmp_path / "cases"
    raiz.mkdir()
    shutil.copy(FIXTURES / "case_ok_es.yaml", raiz / "017.yaml")

    problemas = check_language_parity(load_cases(raiz))

    assert len(problemas) == 1
    assert "DS-2/es/017" in problemas[0]
    assert "DS-2/en/017" in problemas[0]


def test_la_pareja_se_busca_en_el_mismo_conjunto_y_no_en_otro(tmp_path: Path) -> None:
    """Mismo sufijo en otro conjunto no es pareja: DS-3 no completa a DS-2."""
    raiz = tmp_path / "cases"
    raiz.mkdir()
    shutil.copy(FIXTURES / "case_ok_es.yaml", raiz / "017.yaml")
    ajeno = (FIXTURES / "case_ok_en.yaml").read_text(encoding="utf-8")
    (raiz / "ajeno.yaml").write_text(ajeno.replace("DS-2", "DS-3"), encoding="utf-8")

    problemas = check_language_parity(load_cases(raiz))

    assert {p.split("'")[1] for p in problemas} == {"DS-2/es/017", "DS-3/en/017"}
