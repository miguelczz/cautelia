"""Las fronteras del generador que se comprueban leyendo el codigo, no corriendolo.

Tres promesas que una prueba de conducta no puede cerrar sola:

- **Sin azar ajeno a la semilla** (CG-U7-1, BR1.2): ningun modulo del paquete
  importa `random`, `secrets` ni `uuid`. El linter ya prohibe `random` en todo el
  aplicativo (TID251); esta prueba lo repite para el paquete y anade los otros dos,
  que el linter no vigila.
- **Sin reloj de pared** (BR1.1): ninguna llamada a `now`, `utcnow`, `today`,
  `time.time` y sus parientes. Medir cuanto tarda un comando con un reloj monotono
  si se permite: esa cifra se imprime y no entra en ninguna salida.
- **Sin modelo ni claves al componer** (BR1.5, SEC-U7.5): importar la composicion
  en un proceso limpio no carga ningun modulo de `untangle.providers` ni los
  ajustes que leen las claves del entorno.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

import untangle.synthetic_data as paquete

PAQUETE = Path(paquete.__file__).parent

#: Los modulos de la composicion: todo el paquete menos la redaccion, que es el
#: unico que habla con el modelo y el unico que puede conocer `tmp/`.
REDACCION = "drafting.py"

AZAR_PROHIBIDO = {"random", "secrets", "uuid"}
RELOJ_PROHIBIDO = {"now", "utcnow", "today", "time", "time_ns", "localtime", "gmtime", "ctime"}


def _modulos(*, incluir_redaccion: bool = True) -> list[Path]:
    archivos = sorted(PAQUETE.rglob("*.py"))
    if not incluir_redaccion:
        archivos = [a for a in archivos if a.name != REDACCION]
    assert archivos, f"no hay modulos en '{PAQUETE}'"
    return archivos


def _arbol(archivo: Path) -> ast.Module:
    return ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))


def _azar(archivo: Path) -> list[str]:
    """Las importaciones de una fuente de azar en un archivo."""
    hallazgos: list[str] = []
    for nodo in ast.walk(_arbol(archivo)):
        if isinstance(nodo, ast.Import):
            nombres = {alias.name.split(".")[0] for alias in nodo.names}
        elif isinstance(nodo, ast.ImportFrom):
            nombres = {(nodo.module or "").split(".")[0]}
        else:
            continue
        hallazgos.extend(
            f"{archivo.name}:{nodo.lineno} importa {n}" for n in sorted(nombres & AZAR_PROHIBIDO)
        )
    return hallazgos


def _reloj(archivo: Path) -> list[str]:
    """Las llamadas al reloj de pared en un archivo."""
    return [
        f"{archivo.name}:{nodo.lineno} llama a .{nodo.func.attr}()"
        for nodo in ast.walk(_arbol(archivo))
        if isinstance(nodo, ast.Call)
        and isinstance(nodo.func, ast.Attribute)
        and nodo.func.attr in RELOJ_PROHIBIDO
    ]


def test_ningun_modulo_del_paquete_importa_una_fuente_de_azar() -> None:
    assert [h for archivo in _modulos() for h in _azar(archivo)] == []


def test_ningun_modulo_del_paquete_lee_el_reloj_de_pared() -> None:
    assert [h for archivo in _modulos() for h in _reloj(archivo)] == []


@pytest.mark.parametrize(
    ("plantado", "busqueda"),
    [
        ("import random\n", _azar),
        ("from secrets import token_hex\n", _azar),
        ("import uuid\n", _azar),
        ("x = datetime.now(UTC)\n", _reloj),
        ("y = date.today()\n", _reloj),
        ("z = time.time()\n", _reloj),
    ],
)
def test_las_dos_busquedas_encuentran_lo_que_buscan(
    tmp_path: Path, plantado: str, busqueda: Callable[[Path], list[str]]
) -> None:
    """Una busqueda que nunca encuentra nada no demuestra nada: se planta y se ve."""
    archivo = tmp_path / "plantado.py"
    archivo.write_text(plantado, encoding="utf-8")

    assert busqueda(archivo) != []


def test_importar_la_composicion_no_carga_proveedores_ni_ajustes() -> None:
    codigo = (
        "import sys\n"
        "import untangle.synthetic_data.cli, untangle.synthetic_data.generator\n"
        "cargados = sorted(m for m in sys.modules if m.startswith('untangle.providers') "
        "or m == 'untangle.settings')\n"
        "print(cargados)\n"
    )
    # Ruta absoluta del interprete y argumentos fijos, sin shell: no entra nada de fuera.
    resultado = subprocess.run(  # noqa: S603
        [sys.executable, "-c", codigo],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )

    assert resultado.stdout.strip() == "[]"


# --- La composicion no conoce tmp/ (BR2.1, BR2.3) -----------------------------

#: Lo que delata que un modulo sabe llegar a los borradores o a los specimens.
_RUTAS_DE_TMP = ("synthetic_drafts_dir", "specimens_dir")
_TEXTOS_DE_TMP = ("tmp/", "synthetic-drafts", "specimens")


def _docstrings(arbol: ast.Module) -> set[int]:
    """Los nodos que son docstrings: prosa que explica, no rutas que se usan."""
    ids: set[int] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            cuerpo = nodo.body
            if (
                cuerpo
                and isinstance(cuerpo[0], ast.Expr)
                and isinstance(cuerpo[0].value, ast.Constant)
            ):
                ids.add(id(cuerpo[0].value))
    return ids


def _tmp(archivo: Path) -> list[str]:
    """Las referencias a `tmp/` en el codigo de un archivo, sin contar su documentacion."""
    arbol = _arbol(archivo)
    prosa = _docstrings(arbol)
    hallazgos: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom):
            hallazgos.extend(
                f"{archivo.name}:{nodo.lineno} importa {a.name}"
                for a in nodo.names
                if a.name in _RUTAS_DE_TMP
            )
        nombre = (
            nodo.attr
            if isinstance(nodo, ast.Attribute)
            else nodo.id
            if isinstance(nodo, ast.Name)
            else None
        )
        if nombre in _RUTAS_DE_TMP:
            hallazgos.append(f"{archivo.name}:{getattr(nodo, 'lineno', 0)} usa {nombre}")
        if (
            isinstance(nodo, ast.Constant)
            and isinstance(nodo.value, str)
            and id(nodo) not in prosa
            and any(t in nodo.value for t in _TEXTOS_DE_TMP)
        ):
            hallazgos.append(f"{archivo.name}:{nodo.lineno} nombra {nodo.value!r}")
    return hallazgos


def test_ningun_modulo_de_la_composicion_sabe_llegar_a_tmp() -> None:
    """Solo la redaccion escribe en tmp/; la composicion no tiene ninguna ruta hasta alli."""
    assert [h for archivo in _modulos(incluir_redaccion=False) for h in _tmp(archivo)] == []


@pytest.mark.parametrize(
    "plantado",
    [
        "from untangle import paths\nx = paths.synthetic_drafts_dir()\n",
        "from untangle.paths import specimens_dir\n",
        'RUTA = "tmp/synthetic-drafts/stonecroft"\n',
    ],
)
def test_la_busqueda_de_tmp_encuentra_lo_que_busca(tmp_path: Path, plantado: str) -> None:
    archivo = tmp_path / "plantado.py"
    archivo.write_text(
        '"""Un docstring que habla de tmp/ no cuenta."""\n' + plantado, encoding="utf-8"
    )

    assert _tmp(archivo) != []
