"""El registro de dependencias de la interfaz (TECH-U6.1, SEC-U6.7).

Cada dependencia de `app/frontend/package.json` tiene su linea en
`app/frontend/DEPENDENCIES.md` --que hace, por que no alcanza la plataforma y su
licencia-- y la comprobacion de `mise run supply:check` falla **nombrando** la
que falte. Cada prueba rompe un arbol de prueba a proposito.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from untangle.workspace import supply_chain_check

REGISTRO = """# Dependencias

## Ejecución (llegan al navegador)

| Paquete | Qué hace | Por qué no alcanza la plataforma | Licencia |
| --- | --- | --- | --- |
| `react` | Componentes | El DOM no los trae | MIT |

## Desarrollo y pruebas (no llegan al navegador)

| Paquete | Qué hace | Por qué no alcanza la plataforma | Licencia |
| --- | --- | --- | --- |
| `vitest` | Pruebas | Node no transforma JSX | MIT |

## Sustituciones de versión

| Paquete | Sustitución | Razón | Licencia |
| --- | --- | --- | --- |
| `js-yaml` | 4.3.2 | Avisos corregidos | MIT |
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    frontend = tmp_path / "app" / "frontend"
    frontend.mkdir(parents=True)
    (frontend / "package.json").write_text(
        json.dumps({"dependencies": {"react": "^19"}, "devDependencies": {"vitest": "^5"}}),
        encoding="utf-8",
    )
    (frontend / "DEPENDENCIES.md").write_text(REGISTRO, encoding="utf-8")
    (frontend / "pnpm-workspace.yaml").write_text(
        'overrides:\n  "parser>js-yaml": "4.3.2"\n', encoding="utf-8"
    )
    return tmp_path


def _manifiesto(repo: Path, **secciones: dict[str, str]) -> None:
    (repo / "app" / "frontend" / "package.json").write_text(json.dumps(secciones), encoding="utf-8")


def test_un_registro_completo_pasa(repo: Path) -> None:
    assert supply_chain_check.check_frontend_dependencies(repo) == []


def test_una_dependencia_sin_linea_falla_nombrandola(repo: Path) -> None:
    _manifiesto(
        repo,
        dependencies={"react": "^19", "clsx": "^2"},
        devDependencies={"vitest": "^5"},
    )

    problemas = supply_chain_check.check_frontend_dependencies(repo)

    assert len(problemas) == 1
    assert "'clsx'" in problemas[0]


def test_una_linea_sin_dependencia_tambien_es_un_hallazgo(repo: Path) -> None:
    _manifiesto(repo, dependencies={"react": "^19"})

    problemas = supply_chain_check.check_frontend_dependencies(repo)

    assert problemas == ["DEPENDENCIES.md: 'vitest' tiene linea pero no esta en package.json"]


def test_una_linea_con_celdas_vacias_falla(repo: Path) -> None:
    registro = repo / "app" / "frontend" / "DEPENDENCIES.md"
    registro.write_text(
        REGISTRO.replace(
            "| `react` | Componentes | El DOM no los trae | MIT |", "| `react` |  |  | MIT |"
        ),
        encoding="utf-8",
    )

    problemas = supply_chain_check.check_frontend_dependencies(repo)

    assert problemas == ["DEPENDENCIES.md: la linea de 'react' tiene celdas vacias"]


def test_una_sustitucion_de_version_sin_linea_falla(repo: Path) -> None:
    (repo / "app" / "frontend" / "pnpm-workspace.yaml").write_text(
        'overrides:\n  "parser>js-yaml": "4.3.2"\n  "otro>semver": "7.6.0"\n', encoding="utf-8"
    )

    problemas = supply_chain_check.check_frontend_dependencies(repo)

    assert problemas == ["DEPENDENCIES.md: la sustitucion de version de 'semver' no tiene su linea"]


def test_sin_registro_falla_nombrando_el_archivo(repo: Path) -> None:
    (repo / "app" / "frontend" / "DEPENDENCIES.md").unlink()

    [problema] = supply_chain_check.check_frontend_dependencies(repo)

    assert "DEPENDENCIES.md" in problema


def test_el_registro_real_cubre_el_manifiesto_real() -> None:
    assert supply_chain_check.check_frontend_dependencies(Path(__file__).parents[5]) == []


# --- Los avisos de seguridad aceptados, con su fecha por llegar ---------------
#
# La auditoria de dependencias bloquea ante un aviso alto, y pnpm admite ignorar
# uno por su identificador. Lo que estas pruebas protegen es que ese identificador
# **no se pueda escribir y olvidar**: sin fila con su razon, o con la fecha de
# revision ya pasada, la compuerta vuelve a ponerse roja.

AVISOS = """# Dependencias

## Avisos de seguridad aceptados

| Aviso | Paquete | Por dónde llega | Por qué no bloquea | Revisar |
| --- | --- | --- | --- | --- |
| GHSA-aaaa-bbbb-cccc | `glob-cosa` | el linter | No llega al navegador | 2026-11-03 |
"""


@pytest.fixture
def repo_con_aviso(repo: Path) -> Path:
    frontend = repo / "app" / "frontend"
    (frontend / "DEPENDENCIES.md").write_text(REGISTRO + AVISOS, encoding="utf-8")
    (frontend / "pnpm-workspace.yaml").write_text(
        "auditConfig:\n  ignoreGhsas:\n    - GHSA-aaaa-bbbb-cccc\n", encoding="utf-8"
    )
    return repo


def test_un_aviso_con_su_fila_y_su_fecha_por_llegar_pasa(repo_con_aviso: Path) -> None:
    problemas = supply_chain_check.check_accepted_advisories(
        repo_con_aviso, today=date(2026, 10, 3)
    )

    assert problemas == []


def test_un_aviso_ignorado_sin_su_fila_falla_nombrandolo(repo_con_aviso: Path) -> None:
    """Es el caso que importa: ignorar sin escribir por que."""
    (repo_con_aviso / "app" / "frontend" / "pnpm-workspace.yaml").write_text(
        "auditConfig:\n  ignoreGhsas:\n    - GHSA-zzzz-yyyy-xxxx\n", encoding="utf-8"
    )

    problemas = supply_chain_check.check_accepted_advisories(
        repo_con_aviso, today=date(2026, 10, 3)
    )

    assert len(problemas) == 2, problemas
    assert any("GHSA-zzzz-yyyy-xxxx" in p and "no tiene su fila" in p for p in problemas)
    # Y la fila que quedo sin aviso tambien se nombra: describe una excepcion que
    # ya no existe.
    assert any("GHSA-aaaa-bbbb-cccc" in p and "sobra" in p for p in problemas)


def test_una_excepcion_vencida_vuelve_a_poner_la_compuerta_en_rojo(
    repo_con_aviso: Path,
) -> None:
    """La mitad que hace que la excepcion caduque de verdad.

    Un dia despues de su fecha, el chequeo falla diciendo que hay que mirar si ya
    tiene parche. Sin esto, la fecha seria una nota que nadie vuelve a leer.
    """
    problemas = supply_chain_check.check_accepted_advisories(
        repo_con_aviso, today=date(2026, 11, 4)
    )

    assert len(problemas) == 1
    assert "vencio el 2026-11-03" in problemas[0]


def test_una_fecha_que_no_es_una_fecha_tambien_falla(repo_con_aviso: Path) -> None:
    """Para que "revisar: cuando salga el parche" no cuente como fecha."""
    registro = (repo_con_aviso / "app" / "frontend" / "DEPENDENCIES.md").read_text(encoding="utf-8")
    (repo_con_aviso / "app" / "frontend" / "DEPENDENCIES.md").write_text(
        registro.replace("2026-11-03", "cuando salga el parche"), encoding="utf-8"
    )

    problemas = supply_chain_check.check_accepted_advisories(
        repo_con_aviso, today=date(2026, 10, 3)
    )

    assert len(problemas) == 1
    assert "no es una fecha" in problemas[0]


def test_sin_avisos_ignorados_no_hay_nada_que_exigir(repo: Path) -> None:
    """El caso normal del proyecto: ninguna excepcion escrita."""
    assert supply_chain_check.check_accepted_advisories(repo, today=date(2026, 10, 3)) == []


# --- Y los de la auditoria de Python: `--ignore-vuln` en la tarea `audit` -----
#
# La excepcion de `langgraph-sdk` vivio semanas solo en un comentario de
# `mise.toml`: la compuerta la ignoraba para siempre y nadie volvia a preguntar.
# Ahora la fila con su fecha es obligatoria, igual que la de pnpm.

AVISO_DE_PYTHON = "| CVE-2026-100001 | `paquete-py` 1.0 | `otra-cosa > paquete-py` | No se ejecuta | 2026-11-13 |\n"

MISE_CON_IGNORADO = """
[tasks.audit]
run = [
  "uv export | pip-audit --strict --ignore-vuln CVE-2026-100001 -r /dev/stdin",
  "pnpm --dir app/frontend audit --audit-level high",
]
"""


@pytest.fixture
def repo_con_aviso_de_python(repo_con_aviso: Path) -> Path:
    """El de pnpm sigue ignorado y con su fila: los dos gestores conviven en la tabla."""
    registro = repo_con_aviso / "app" / "frontend" / "DEPENDENCIES.md"
    registro.write_text(registro.read_text(encoding="utf-8") + AVISO_DE_PYTHON, encoding="utf-8")
    (repo_con_aviso / "mise.toml").write_text(MISE_CON_IGNORADO, encoding="utf-8")
    return repo_con_aviso


def test_un_aviso_de_python_con_su_fila_y_su_fecha_por_llegar_pasa(
    repo_con_aviso_de_python: Path,
) -> None:
    problemas = supply_chain_check.check_accepted_advisories(
        repo_con_aviso_de_python, today=date(2026, 10, 13)
    )

    assert problemas == []


def test_un_ignore_vuln_sin_su_fila_falla_nombrandolo(repo_con_aviso_de_python: Path) -> None:
    """Escribir el `--ignore-vuln` sin la razon y la fecha pone la compuerta en rojo."""
    (repo_con_aviso_de_python / "mise.toml").write_text(
        MISE_CON_IGNORADO.replace("CVE-2026-100001", "CVE-2026-100002"), encoding="utf-8"
    )

    problemas = supply_chain_check.check_accepted_advisories(
        repo_con_aviso_de_python, today=date(2026, 10, 13)
    )

    assert any("CVE-2026-100002" in p and "no tiene su fila" in p for p in problemas), problemas
    # Y la fila que quedo sin aviso se nombra: describe una excepcion que ya no existe.
    assert any("CVE-2026-100001" in p and "sobra" in p for p in problemas), problemas


def test_un_aviso_de_python_vencido_vuelve_a_poner_la_compuerta_en_rojo(
    repo_con_aviso_de_python: Path,
) -> None:
    problemas = supply_chain_check.check_accepted_advisories(
        repo_con_aviso_de_python, today=date(2026, 11, 14)
    )

    # El de pnpm vence el 2026-11-03 y el de Python el 2026-11-13: los dos se nombran.
    assert len(problemas) == 2, problemas
    assert any("CVE-2026-100001" in p and "vencio el 2026-11-13" in p for p in problemas)


def test_la_excepcion_real_de_langgraph_sdk_tiene_su_fila_y_vence_el_13_de_noviembre() -> None:
    """La del repositorio de verdad, con la fecha puesta a mano para no depender del reloj."""
    raiz = Path(__file__).parents[5]

    assert supply_chain_check.check_accepted_advisories(raiz, today=date(2026, 10, 13)) == []

    vencida = supply_chain_check.check_accepted_advisories(raiz, today=date(2026, 11, 14))
    assert any("CVE-2026-104873" in p and "vencio el 2026-11-13" in p for p in vencida), vencida
