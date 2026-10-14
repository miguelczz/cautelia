"""Los cuatro contratos de importacion de U3, probados con violaciones plantadas.

Un contrato que nunca se ha visto fallar es un contrato del que nadie sabe si
funciona. Estas pruebas construyen un arbol minimo con los mismos nombres de
modulo, plantan **la** violacion que cada contrato existe para atrapar, y exigen
que la herramienta la encuentre y la nombre.

**Leen el archivo de configuracion real**, no una copia. Es la diferencia con las
pruebas equivalentes de U2: alli la configuracion esta transcrita dentro de la
prueba, asi que la prueba pasaria igual el dia que el archivo real dijera otra
cosa. Aqui, si alguien borra o afloja una seccion de `app/backend/.importlinter`,
estas pruebas fallan nombrandola.

Son de integracion porque invocan la herramienta de verdad, en otro proceso: es
lo unico que comprueba que el archivo de configuracion dice lo que creemos que
dice.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from untangle import paths

#: El ejecutable de la herramienta, dentro del mismo entorno que corre la suite.
LINT_IMPORTS = Path(sys.executable).parent / "lint-imports"

#: El archivo de configuracion real del proyecto. Lo que se prueba es este.
CONFIGURACION_REAL = paths.repo_root() / "app" / "backend" / ".importlinter"

CAPAS = "capas-de-redaction"
INDEPENDENCIA = "etiquetas-y-detector-independientes"
SINKS = "sinks-sin-dependencias"
SIN_RED = "redaccion-sin-red"

ENCABEZADO = """\
[importlinter]
root_packages =
    untangle
include_external_packages = True
"""

#: El arbol minimo, con la direccion **correcta** de dependencias. Cada prueba
#: planta encima la violacion que le toca.
ARBOL: dict[str, str] = {
    "untangle/__init__.py": "",
    "untangle/compliance/__init__.py": "",
    "untangle/compliance/redaction/__init__.py": "",
    "untangle/compliance/redaction/recognizers/__init__.py": "",
    "untangle/compliance/redaction/recognizers/models.py": "",
    "untangle/compliance/redaction/recognizers/loading.py": (
        "from untangle.compliance.redaction.recognizers import models\n"
    ),
    "untangle/compliance/redaction/detector.py": (
        "from untangle.compliance.redaction.recognizers import loading, models\n"
    ),
    "untangle/compliance/redaction/labels.py": (
        "from untangle.compliance.redaction.recognizers import models\n"
    ),
    "untangle/compliance/redaction/api.py": (
        "from untangle.compliance.redaction import detector, labels\n"
    ),
    "untangle/compliance/redaction/streaming.py": (
        "from untangle.compliance.redaction import api\n"
    ),
    "untangle/compliance/redaction/sinks.py": "",
}


def _seccion(nombre: str) -> str:
    """La seccion de un contrato, extraida del archivo real.

    Si la seccion no existe, la prueba falla **nombrandola**: es lo que hace de
    esto una prueba del contrato y no de una copia suya.
    """
    texto = CONFIGURACION_REAL.read_text(encoding="utf-8")
    patron = re.compile(
        rf"^\[importlinter:contract:{re.escape(nombre)}\]$.*?(?=^\[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    encontrada = patron.search(texto)
    if encontrada is None:
        pytest.fail(
            f"'{CONFIGURACION_REAL}' no declara el contrato '{nombre}'. Sin el, la "
            "regla que esta prueba comprueba no existe en el proyecto: lo unico "
            "que quedaria es esta prueba pasando sobre una configuracion inventada."
        )
    return encontrada.group(0)


def _config(*nombres: str) -> str:
    """El encabezado mas las secciones reales de los contratos pedidos."""
    return ENCABEZADO + "\n" + "\n".join(_seccion(nombre) for nombre in nombres)


def _sembrar(raiz: Path, extra: dict[str, str] | None = None) -> None:
    contenido = dict(ARBOL)
    contenido.update(extra or {})
    for ruta, texto in contenido.items():
        archivo = raiz / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(texto, encoding="utf-8")


def _correr(raiz: Path, configuracion: str) -> subprocess.CompletedProcess[str]:
    archivo = raiz / ".importlinter"
    archivo.write_text(configuracion, encoding="utf-8")
    # Ruta absoluta y argumentos fijos, sin shell: no entra nada de fuera.
    return subprocess.run(  # noqa: S603
        [str(LINT_IMPORTS), "--config", str(archivo)],
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
            f"no se encontro '{LINT_IMPORTS}'. Corra `mise run deps:install`: sin "
            "la herramienta, estos contratos no se comprueban y su ausencia no "
            "puede pasar por verde."
        )


def test_el_arbol_correcto_cumple_los_cuatro_contratos(tmp_path: Path) -> None:
    """La linea base: sin violacion plantada, los cuatro pasan.

    Sin esta prueba, las de abajo podrian estar fallando por un error del
    andamiaje y pareceria que los contratos funcionan.
    """
    _sembrar(tmp_path)

    resultado = _correr(tmp_path, _config(CAPAS, INDEPENDENCIA, SINKS, SIN_RED))

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_las_etiquetas_no_pueden_importar_el_detector(tmp_path: Path) -> None:
    """`labels` y `detector` estan en el mismo renglon y no pueden importarse.

    Escribir la etiqueta no puede depender de por que se detecto algo: es lo que
    impide que un dia la etiqueta lleve "una pista" del valor original para
    ayudar a depurar.

    Lo prohibe el contrato de **independencia** y no el de capas: en
    `import-linter` 2.6 el separador `:` dice que dos modulos estan al mismo
    nivel, no que no puedan importarse. Se comprobo plantando esta misma
    importacion y viendo el contrato de capas pasar en verde, que es justo la
    clase de control que parece existir y no existe.
    """
    _sembrar(
        tmp_path,
        {
            "untangle/compliance/redaction/labels.py": (
                "from untangle.compliance.redaction import detector\n"
            )
        },
    )

    resultado = _correr(tmp_path, _config(INDEPENDENCIA))

    assert resultado.returncode != 0
    assert "labels" in resultado.stdout
    assert "detector" in resultado.stdout


def test_las_capas_atrapan_a_la_superficie_que_importa_la_transcripcion(tmp_path: Path) -> None:
    """`streaming` esta **encima** de `api`, no debajo.

    El Flujo 2 exige que `streaming` llame a `redact()`. Si la superficie
    importara a `streaming`, el contrato bloquearia la unica llamada que el flujo
    obligatorio necesita, y se descubriria el dia de implementarlo.
    """
    _sembrar(
        tmp_path,
        {
            "untangle/compliance/redaction/api.py": (
                "from untangle.compliance.redaction import detector, labels, streaming\n"
            )
        },
    )

    resultado = _correr(tmp_path, _config(CAPAS))

    assert resultado.returncode != 0
    assert "streaming" in resultado.stdout


def test_el_registro_de_puntos_de_salida_no_puede_importar_la_redaccion(tmp_path: Path) -> None:
    """`sinks` solo declara; un registro que llamara a la redaccion seria un
    septimo punto de salida encubierto."""
    _sembrar(
        tmp_path,
        {
            "untangle/compliance/redaction/sinks.py": (
                "from untangle.compliance.redaction import api\n"
            )
        },
    )

    resultado = _correr(tmp_path, _config(SINKS))

    assert resultado.returncode != 0
    assert "sinks" in resultado.stdout


def test_el_contrato_sin_red_atrapa_a_un_cliente_http_dentro_del_modulo(tmp_path: Path) -> None:
    """SEC-U3.12: el texto no sale del proceso.

    La redaccion es lo unico que ve el dato en claro. Un cliente de red dentro de
    este modulo convertiria al control en el punto de fuga: no hay ninguna razon
    legitima para que aqui exista uno, y por eso se prohibe en vez de revisarse.
    """
    _sembrar(
        tmp_path,
        {
            "untangle/compliance/redaction/detector.py": (
                "import httpx\n"
                "from untangle.compliance.redaction.recognizers import loading, models\n"
            )
        },
    )

    resultado = _correr(tmp_path, _config(SIN_RED))

    assert resultado.returncode != 0
    assert "httpx" in resultado.stdout


def test_el_contrato_sin_red_atrapa_al_sdk_de_un_proveedor(tmp_path: Path) -> None:
    """ADR-013: la redaccion es determinista y no manda nada a un tercero.

    El contrato general de SDK ya cubre `untangle.compliance` entero; este lo
    repite acotado al modulo porque aqui la consecuencia es distinta: alli seria
    una capa saltada, y aqui seria el dato personal viajando fuera.
    """
    _sembrar(
        tmp_path,
        {
            "untangle/compliance/redaction/detector.py": (
                "import openai\n"
                "from untangle.compliance.redaction.recognizers import loading, models\n"
            )
        },
    )

    resultado = _correr(tmp_path, _config(SIN_RED))

    assert resultado.returncode != 0
    assert "openai" in resultado.stdout
