"""BR3.4: hay **un solo** detector de idioma y es una hoja de verdad.

Un contrato que nunca se ha visto fallar es un contrato del que nadie sabe si
funciona. Esta prueba construye un árbol mínimo con los mismos nombres de módulo,
planta la importación que el contrato existe para atrapar, y exige que la
herramienta la encuentre y la nombre.

**Lee el archivo de configuración real**, como las de U3 y U16: si alguien borra o
afloja la sección, esta prueba falla nombrándola.
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

HOJA = "idioma-es-una-hoja"

ENCABEZADO = """\
[importlinter]
root_packages =
    untangle
include_external_packages = True
"""

#: El árbol mínimo con la dirección **correcta**: el detector solo ve `base`, y
#: los dos canales lo ven a él.
ARBOL: dict[str, str] = {
    "untangle/__init__.py": "",
    "untangle/base.py": "",
    "untangle/language.py": "from untangle.base import Locale\n",
    "untangle/chat/__init__.py": "",
    "untangle/chat/api.py": "from untangle import language\n",
    "untangle/voice/__init__.py": "",
    "untangle/voice/call.py": "from untangle import language\n",
    "untangle/tenancy/__init__.py": "",
    "untangle/server/__init__.py": "",
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
            f"'{CONFIGURACION_REAL}' no declara el contrato '{nombre}'. Sin él, lo "
            "único que quedaría es esta prueba pasando sobre una configuración "
            "inventada."
        )
    return encontrada.group(0)


def _correr(raiz: Path, extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    contenido = dict(ARBOL)
    contenido.update(extra or {})
    for ruta, texto in contenido.items():
        archivo = raiz / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(texto, encoding="utf-8")
    configuracion = raiz / ".importlinter"
    configuracion.write_text(ENCABEZADO + "\n" + _seccion(HOJA), encoding="utf-8")
    return subprocess.run(  # noqa: S603 -- ruta absoluta y argumentos fijos, sin shell
        [str(LINT_IMPORTS), "--config", str(configuracion)],
        cwd=raiz,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


@pytest.fixture(autouse=True)
def la_herramienta_existe() -> None:
    if not LINT_IMPORTS.is_file():
        pytest.fail(
            f"no se encontró '{LINT_IMPORTS}'. Corra `mise run deps:install`: sin la "
            "herramienta, este contrato no se comprueba y su ausencia pasaría por verde."
        )


def test_el_arbol_correcto_cumple_el_contrato(tmp_path: Path) -> None:
    """La línea base: los dos canales ven el detector y él solo ve `base`.

    Sin esta prueba, las de abajo podrían estar fallando por un error del
    andamiaje y parecería que el contrato funciona.
    """
    resultado = _correr(tmp_path)

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_el_detector_no_puede_mirar_hacia_arriba(tmp_path: Path) -> None:
    """Lo que el contrato existe para atrapar.

    Un detector que importara un canal dejaría de ser una hoja y volvería a estar
    atado a uno de los dos, que es exactamente el estado del que se le sacó.
    """
    resultado = _correr(tmp_path, {"untangle/language.py": "from untangle.chat import api\n"})

    assert resultado.returncode != 0
    assert "language" in resultado.stdout


def test_el_contrato_nombra_los_dos_canales(tmp_path: Path) -> None:
    """La mitad que se pierde en silencio.

    Sacar `untangle.chat` o `untangle.voice` de la lista de prohibidos no rompe
    nada visible: la prueba de arriba seguiría verde si quedara el otro. Y desde
    ese día el detector podría volver a colgarse de un canal sin que nadie se
    entere, que es el estado del que subió.
    """
    seccion = _seccion(HOJA)

    assert "untangle.chat" in seccion
    assert "untangle.voice" in seccion


def test_no_queda_ningun_segundo_detector_en_el_arbol_real() -> None:
    """BR3.4 sobre el repositorio de verdad, no sobre un árbol de mentira.

    Los dos umbrales del detector son **medidas** de U13, no elecciones: 0,75 para
    el de dos idiomas y 0,5 para el amplio. Un segundo módulo con umbrales propios
    son dos números que se separan el día que alguien afina uno, en un proyecto que
    publica adherencia de idioma por idioma.

    Se busca el constructor de la biblioteca, que es lo que no se puede escribir
    sin crear un detector.
    """
    fuente = paths.repo_root() / "app" / "backend" / "src" / "untangle"
    con_detector = sorted(
        archivo.relative_to(fuente).as_posix()
        for archivo in fuente.rglob("*.py")
        if "LanguageDetectorBuilder" in archivo.read_text(encoding="utf-8")
    )

    assert con_detector == ["language.py"], f"hay más de un detector: {con_detector}"
