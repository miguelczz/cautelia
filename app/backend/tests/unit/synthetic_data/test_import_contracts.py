"""Los dos contratos de importacion de la redaccion de U7, con violaciones plantadas.

Un contrato que nunca se ha visto fallar es un contrato del que nadie sabe si
funciona. Como las de U2 y U3, estas pruebas construyen un arbol minimo con los
mismos nombres de modulo, plantan **la** violacion que cada contrato existe para
atrapar y exigen que la herramienta la nombre. **Leen el archivo de
configuracion real**: si alguien borra o afloja una seccion, fallan nombrandola.

- `composicion-sintetica-sin-proveedores` (BR1.5, SEC-U7.5): la composicion no
  importa `untangle.providers`; solo la redaccion, y solo por sus dos aristas.
- `redaccion-sintetica-solo-desde-la-raiz`: solo `untangle.server` importa la
  redaccion, que es lo que impide llegar a los proveedores a traves de ella.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from untangle import paths

LINT_IMPORTS = Path(sys.executable).parent / "lint-imports"
CONFIGURACION_REAL = paths.repo_root() / "app" / "backend" / ".importlinter"

SIN_PROVEEDORES = "composicion-sintetica-sin-proveedores"
SOLO_DESDE_LA_RAIZ = "redaccion-sintetica-solo-desde-la-raiz"

ENCABEZADO = """\
[importlinter]
root_packages =
    untangle
include_external_packages = True
"""

#: El arbol minimo, con las dependencias **correctas**.
ARBOL: dict[str, str] = {
    "untangle/__init__.py": "",
    "untangle/providers/__init__.py": "",
    "untangle/providers/ports.py": "",
    "untangle/providers/prompts.py": "from untangle.providers import ports\n",
    "untangle/synthetic_data/__init__.py": "",
    "untangle/synthetic_data/models.py": "",
    "untangle/synthetic_data/generator.py": "from untangle.synthetic_data import models\n",
    "untangle/synthetic_data/drafting.py": (
        "from untangle.providers import ports, prompts\n"
        "from untangle.synthetic_data import models\n"
    ),
    "untangle/server/__init__.py": "",
    "untangle/server/synthetic_draft.py": "from untangle.synthetic_data import drafting\n",
}


def _seccion(nombre: str) -> str:
    texto = CONFIGURACION_REAL.read_text(encoding="utf-8")
    patron = re.compile(
        rf"^\[importlinter:contract:{re.escape(nombre)}\]$.*?(?=^\[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    encontrada = patron.search(texto)
    if encontrada is None:
        pytest.fail(
            f"'{CONFIGURACION_REAL}' no declara el contrato '{nombre}': la regla que esta "
            "prueba comprueba no existe en el proyecto."
        )
    return encontrada.group(0)


def _correr(raiz: Path, extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    contenido = {**ARBOL, **(extra or {})}
    for ruta, texto in contenido.items():
        archivo = raiz / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(texto, encoding="utf-8")
    configuracion = raiz / ".importlinter"
    configuracion.write_text(
        ENCABEZADO + "\n" + _seccion(SIN_PROVEEDORES) + "\n" + _seccion(SOLO_DESDE_LA_RAIZ),
        encoding="utf-8",
    )
    # Ruta absoluta y argumentos fijos, sin shell: no entra nada de fuera.
    return subprocess.run(  # noqa: S603
        [str(LINT_IMPORTS), "--config", str(configuracion), "--no-cache"],
        cwd=raiz,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _salida(resultado: subprocess.CompletedProcess[str]) -> str:
    """La salida con los espacios normalizados: la herramienta parte las lineas largas."""
    return " ".join((resultado.stdout + resultado.stderr).split())


@pytest.fixture(autouse=True)
def la_herramienta_existe() -> None:
    if not LINT_IMPORTS.is_file():
        pytest.fail(f"no se encontro '{LINT_IMPORTS}': corra `mise run deps:install`")


def test_el_arbol_correcto_cumple_los_dos_contratos(tmp_path: Path) -> None:
    resultado = _correr(tmp_path)

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_la_composicion_que_importa_un_proveedor_rompe_el_contrato(tmp_path: Path) -> None:
    resultado = _correr(
        tmp_path,
        {"untangle/synthetic_data/generator.py": "from untangle.providers import ports\n"},
    )

    assert resultado.returncode != 0
    assert (
        "La composicion del generador no importa ningun proveedor; solo su redaccion BROKEN"
        in _salida(resultado)
    )
    assert "untangle.synthetic_data.generator -> untangle.providers.ports" in _salida(resultado)


def test_la_composicion_que_importa_la_redaccion_rompe_el_contrato(tmp_path: Path) -> None:
    resultado = _correr(
        tmp_path,
        {"untangle/synthetic_data/generator.py": "from untangle.synthetic_data import drafting\n"},
    )

    assert resultado.returncode != 0
    assert "Solo la raiz de composicion importa la redaccion del generador BROKEN" in _salida(
        resultado
    )
    assert "untangle.synthetic_data.generator -> untangle.synthetic_data.drafting" in _salida(
        resultado
    )


def test_una_excepcion_que_ya_no_excusa_nada_hace_fallar_el_contrato(tmp_path: Path) -> None:
    """Si la redaccion deja de importar el cargador de prompts, la arista exenta sobra."""
    resultado = _correr(
        tmp_path,
        {"untangle/synthetic_data/drafting.py": "from untangle.providers import ports\n"},
    )

    assert resultado.returncode != 0
    assert (
        "No matches for ignored import untangle.synthetic_data.drafting -> "
        "untangle.providers.prompts"
    ) in _salida(resultado)
