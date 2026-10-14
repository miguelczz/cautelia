"""Pruebas de las herramientas del workspace.

Viven bajo `tests/unit/server/` porque son las herramientas de la base del
repositorio, que es lo que esta unidad llama `workspace`: la cobertura agregada,
la plantilla de variables, las aserciones de esquema y el modulo generado de
claves. El comando de pruebas de U1 recorre este directorio.

Ninguna necesita red, base de datos ni credenciales.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from untangle.copy_catalog.keys_module import render_keys_module
from untangle.copy_catalog.models import CopyEntry, Surface
from untangle.workspace import coverage_gate, env_check, schema_check

COBERTURA = """<?xml version="1.0" ?>
<coverage>
  <packages><package><classes><class><lines>
{lineas}
  </lines></class></classes></package></packages>
</coverage>
"""


def escribir_cobertura(path: Path, *, cubiertas: int, totales: int) -> None:
    lineas = "\n".join(
        f'    <line number="{n}" hits="{1 if n <= cubiertas else 0}"/>'
        for n in range(1, totales + 1)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(COBERTURA.format(lineas=lineas), encoding="utf-8")


# --- Cobertura agregada (NFR18.1) --------------------------------------------


def test_el_agregado_pondera_por_lineas_y_no_promedia_porcentajes() -> None:
    grande = coverage_gate.ProjectCoverage(name="backend", covered=7000, total=10000)
    pequeno = coverage_gate.ProjectCoverage(name="frontend", covered=200, total=200)

    total = coverage_gate.aggregate([grande, pequeno])

    # El promedio de porcentajes daria 85 % y el piso pasaria. El ponderado da
    # 70,6 % y no pasa: un proyecto de 200 lineas no puede pesar lo mismo que uno
    # de 10.000.
    assert round(total.percent, 1) == 70.6
    assert round((grande.percent + pequeno.percent) / 2, 1) == 85.0


def test_un_reporte_que_falta_dice_cual_y_como_producirlo(tmp_path: Path) -> None:
    escribir_cobertura(
        tmp_path / "app" / "backend" / "coverage" / "coverage.xml", cubiertas=8, totales=10
    )

    with pytest.raises(coverage_gate.CoverageInputMissingError) as excinfo:
        coverage_gate.collect(tmp_path)

    mensaje = str(excinfo.value)
    assert "cobertura-coverage.xml" in mensaje
    assert "mise run cov" in mensaje


def test_el_umbral_se_lee_del_manifiesto_y_no_de_una_bandera() -> None:
    from untangle import paths

    assert coverage_gate.read_floor(paths.repo_root()) == 80.0


# --- Plantilla de variables (SEC-U1.2) ---------------------------------------


def test_la_plantilla_y_lo_que_se_lee_se_comparan_en_las_dos_direcciones(
    tmp_path: Path,
) -> None:
    (tmp_path / "docker-compose.yml").write_text(
        "services:\n  db:\n    ports: ['${UNTANGLE_POSTGRES_PORT:-5432}:5432']\n",
        encoding="utf-8",
    )
    # Le falta la del puerto y le sobra una que nadie lee.
    (tmp_path / ".env.example").write_text(
        "UNTANGLE_ENV=\nUNTANGLE_EVALS_MODEL_API_KEY=\nUNTANGLE_TRACES_ENDPOINT=\n"
        "UNTANGLE_VARIABLE_MUERTA=\n",
        encoding="utf-8",
    )

    problemas = env_check.run_all(tmp_path)

    assert any("UNTANGLE_POSTGRES_PORT" in p and "no la lista" in p for p in problemas)
    assert any("UNTANGLE_VARIABLE_MUERTA" in p and "nadie la lee" in p for p in problemas)


def test_sin_plantilla_el_chequeo_falla_nombrando_el_archivo(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError) as excinfo:
        env_check.run_all(tmp_path)

    assert ".env.example" in str(excinfo.value)


# --- Aserciones de esquema ----------------------------------------------------


def test_el_arbol_real_valida_sus_archivos_versionados() -> None:
    from untangle import paths

    assert schema_check.run_all(paths.repo_root()) == []


def test_un_caso_invalido_se_reporta_nombrando_su_archivo(tmp_path: Path) -> None:
    casos = tmp_path / "app" / "evals" / "cases"
    casos.mkdir(parents=True)
    (tmp_path / "app" / "evals" / "subsets").mkdir(parents=True)
    (casos / "roto.yaml").write_text("case_key: DS-2/es/001\ndataset: DS-99\n", encoding="utf-8")

    problemas = schema_check.run_all(tmp_path)

    assert any("roto.yaml" in p for p in problemas)


# --- Modulo tipado de claves (C-28) -------------------------------------------


def test_el_modulo_generado_es_determinista_y_ordena_sus_claves() -> None:
    def entrada(clave: str) -> CopyEntry:
        return CopyEntry(key=clave, locale="es", text="x", surface=Surface.INBOX)

    entradas = {
        ("inbox.z", "es"): entrada("inbox.z"),
        ("inbox.a", "es"): entrada("inbox.a"),
    }

    primero = render_keys_module(entradas)
    segundo = render_keys_module(dict(reversed(list(entradas.items()))))

    # El orden sale de la clave, no del orden de insercion: si saliera del
    # diccionario, el chequeo de deriva fallaria sin que nadie cambiara nada.
    assert primero == segundo
    assert primero.index('"inbox.a"') < primero.index('"inbox.z"')


def test_un_catalogo_vacio_produce_un_tipo_que_no_admite_ninguna_clave() -> None:
    generado = render_keys_module({})

    assert "never" in generado
    assert "COPY_KEYS = [\n] as const" in generado


# --- Contratos generados (C-28) -----------------------------------------------


def test_generar_dos_veces_no_cambia_nada_y_una_edicion_a_mano_se_detecta(
    tmp_path: Path,
) -> None:
    from untangle.workspace import generate_contracts

    esquemas = tmp_path / "schemas"
    frontend = tmp_path / "frontend"

    primera = generate_contracts.generate(esquemas, frontend)
    segunda = generate_contracts.generate(esquemas, frontend)

    # Generar es idempotente: si no lo fuera, el chequeo de deriva fallaria en
    # cada corrida sin que nadie hubiera cambiado nada.
    assert primera
    assert segunda == []
    assert (esquemas / "golden-case.schema.json").is_file()
    assert (frontend / "copy-keys.ts").is_file()

    # Y un artefacto editado a mano vuelve a su sitio, que es como la compuerta
    # lo detecta: un generado nunca se arregla editandolo.
    (esquemas / "golden-case.schema.json").write_text("{}\n", encoding="utf-8")
    tercera = generate_contracts.generate(esquemas, frontend)
    assert [p.name for p in tercera] == ["golden-case.schema.json"]
