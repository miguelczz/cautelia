"""Los contratos de importacion de la siembra y del corredor, con violaciones plantadas.

Como las de `test_import_contracts.py`, estas pruebas construyen un arbol minimo
con los mismos nombres de modulo, plantan **la** violacion que cada contrato
existe para atrapar y exigen que la herramienta la nombre. **Leen el archivo de
configuracion real**: si alguien borra o afloja una seccion, fallan nombrandola.

- `evals-sin-generador` (BR8.1): el corredor de evaluaciones no importa el
  generador; lee lo versionado y nunca lo produce.
- `generador-sin-base` (BR6.3): el generador no abre sesion ni llega al registro
  del caso, **tampoco por cadena**; la siembra va por la API de U4 desde la raiz
  de composicion (FD-U7-9).

La tercera frontera del paso 12 --la composicion no importa `providers`-- ya
tiene su violacion plantada en `test_import_contracts.py`.
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

EVALS_SIN_GENERADOR = "evals-sin-generador"
GENERADOR_SIN_BASE = "generador-sin-base"

ENCABEZADO = """\
[importlinter]
root_packages =
    untangle
include_external_packages = True
"""

#: El arbol minimo, con las dependencias **correctas**: la raiz siembra por la API
#: de U4, el registro del caso usa la sesion, y el corredor lee datos.
ARBOL: dict[str, str] = {
    "untangle/__init__.py": "",
    "untangle/text_fingerprints.py": "",
    "untangle/tenancy/__init__.py": "",
    "untangle/tenancy/config.py": "",
    "untangle/tenancy/session.py": "import sqlalchemy\nimport psycopg\nfrom untangle.tenancy import config\n",
    "untangle/tenancy/api.py": "from untangle.tenancy import session\n",
    "untangle/case_record/__init__.py": "",
    "untangle/case_record/api.py": "from untangle.tenancy import session\n",
    "untangle/synthetic_data/__init__.py": "",
    "untangle/synthetic_data/models.py": "from untangle.tenancy import config\n",
    "untangle/synthetic_data/cases.py": "from untangle.synthetic_data import models\n",
    "untangle/synthetic_data/fingerprints.py": "from untangle import text_fingerprints\n",
    "untangle/evals/__init__.py": "",
    "untangle/evals/content_checks.py": "from untangle import text_fingerprints\n",
    "untangle/server/__init__.py": "",
    "untangle/server/synthetic_seed.py": (
        "from untangle.case_record import api\nfrom untangle.synthetic_data import cases\n"
    ),
    "untangle/ayudante.py": "",
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
    for ruta, texto in {**ARBOL, **(extra or {})}.items():
        archivo = raiz / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(texto, encoding="utf-8")
    configuracion = raiz / ".importlinter"
    configuracion.write_text(
        ENCABEZADO + "\n" + _seccion(EVALS_SIN_GENERADOR) + "\n" + _seccion(GENERADOR_SIN_BASE),
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
    return " ".join((resultado.stdout + resultado.stderr).split())


@pytest.fixture(autouse=True)
def la_herramienta_existe() -> None:
    if not LINT_IMPORTS.is_file():
        pytest.fail(f"no se encontro '{LINT_IMPORTS}': corra `mise run deps:install`")


def test_el_arbol_correcto_cumple_los_dos_contratos(tmp_path: Path) -> None:
    resultado = _correr(tmp_path)

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_el_corredor_que_importa_el_generador_rompe_el_contrato(tmp_path: Path) -> None:
    resultado = _correr(
        tmp_path,
        {"untangle/evals/content_checks.py": "from untangle.synthetic_data import cases\n"},
    )

    assert resultado.returncode != 0
    assert "El corredor de evaluaciones no importa el generador sintetico BROKEN" in _salida(
        resultado
    )
    assert "untangle.evals.content_checks -> untangle.synthetic_data.cases" in _salida(resultado)


@pytest.mark.parametrize(
    ("plantado", "arista"),
    [
        pytest.param(
            "from untangle.tenancy import session\n",
            "untangle.synthetic_data.cases -> untangle.tenancy.session",
            id="la-sesion",
        ),
        pytest.param(
            "from untangle.case_record import api\n",
            "untangle.synthetic_data.cases -> untangle.case_record.api",
            id="la-api-de-u4",
        ),
        pytest.param(
            "import sqlalchemy\n", "untangle.synthetic_data.cases -> sqlalchemy", id="el-driver"
        ),
    ],
)
def test_el_generador_que_llega_a_la_base_rompe_el_contrato(
    tmp_path: Path, plantado: str, arista: str
) -> None:
    resultado = _correr(tmp_path, {"untangle/synthetic_data/cases.py": plantado})

    assert resultado.returncode != 0
    assert "El generador no abre sesion ni llega al registro del caso BROKEN" in _salida(resultado)
    assert arista in _salida(resultado)


def test_tambien_por_cadena(tmp_path: Path) -> None:
    """Un ayudante intermedio no es una puerta: la cadena tambien se nombra."""
    resultado = _correr(
        tmp_path,
        {
            "untangle/ayudante.py": "from untangle.tenancy import session\n",
            "untangle/synthetic_data/cases.py": "from untangle import ayudante\n",
        },
    )

    assert resultado.returncode != 0
    assert "El generador no abre sesion ni llega al registro del caso BROKEN" in _salida(resultado)
    assert "untangle.ayudante -> untangle.tenancy.session" in _salida(resultado)
