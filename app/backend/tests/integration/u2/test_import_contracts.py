"""Los tres contratos de importacion de U2, probados con violaciones plantadas.

Un contrato que nunca se ha visto fallar es un contrato del que nadie sabe si
funciona. Estas pruebas construyen un arbol minimo con los mismos nombres de
modulo, plantan **la** violacion que cada contrato existe para atrapar, y exigen
que la herramienta la encuentre y la nombre.

Son de integracion porque invocan la herramienta de verdad, en otro proceso: es
lo unico que comprueba que el archivo de configuracion dice lo que creemos que
dice.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

#: El ejecutable de la herramienta, dentro del mismo entorno que corre la suite.
LINT_IMPORTS = Path(sys.executable).parent / "lint-imports"

CAPAS_DE_TENANCY = """
[importlinter]
root_packages =
    untangle

[importlinter:contract:capas-de-tenancy]
name = Las capas internas de tenancy
type = layers
layers =
    untangle.tenancy.api
    untangle.tenancy.staff_identity : untangle.tenancy.visitor_access : untangle.tenancy.purge : untangle.tenancy.rls_assertion
    untangle.tenancy.session
    untangle.tenancy.config
"""

CLIENTE_SOLO_EN_LA_SESION = """
[importlinter]
root_packages =
    untangle
include_external_packages = True

[importlinter:contract:cliente-de-base-solo-en-la-sesion]
name = Dentro de tenancy, solo la pieza de sesion importa el cliente de base
type = forbidden
source_modules =
    untangle.tenancy.api
    untangle.tenancy.config
    untangle.tenancy.staff_identity
    untangle.tenancy.visitor_access
    untangle.tenancy.purge
    untangle.tenancy.rls_assertion
forbidden_modules =
    sqlalchemy
allow_indirect_imports = true
unmatched_ignore_imports_alerting = none
"""

EVALS_SIN_BASE = """
[importlinter]
root_packages =
    untangle

[importlinter:contract:evals-sin-base-de-datos]
name = El corredor de evaluaciones no importa la raiz de composicion ni la sesion
type = forbidden
source_modules =
    untangle.evals
forbidden_modules =
    untangle.server.composition
    untangle.tenancy.session
"""

#: El arbol minimo, con la direccion **correcta** de dependencias. Cada prueba
#: planta encima la violacion que le toca.
ARBOL: dict[str, str] = {
    "untangle/__init__.py": "",
    "untangle/tenancy/__init__.py": "",
    "untangle/tenancy/config.py": "",
    "untangle/tenancy/session.py": "from untangle.tenancy import config\n",
    "untangle/tenancy/staff_identity.py": "from untangle.tenancy import session\n",
    "untangle/tenancy/visitor_access.py": "from untangle.tenancy import session\n",
    "untangle/tenancy/purge.py": "from untangle.tenancy import session\n",
    "untangle/tenancy/rls_assertion.py": "from untangle.tenancy import session\n",
    "untangle/tenancy/api.py": (
        "from untangle.tenancy import purge, rls_assertion, session, staff_identity, visitor_access\n"
    ),
    "untangle/server/__init__.py": "",
    "untangle/server/composition.py": "from untangle.tenancy import api\n",
    "untangle/evals/__init__.py": "",
    "untangle/evals/cli.py": "",
}


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


def test_el_arbol_correcto_cumple_los_tres_contratos(tmp_path: Path) -> None:
    """La linea base: sin violacion plantada, los tres pasan.

    Sin esta prueba, las tres de abajo podrian estar fallando por un error del
    andamiaje y pareceria que los contratos funcionan.
    """
    _sembrar(tmp_path)

    for configuracion in (CAPAS_DE_TENANCY, CLIENTE_SOLO_EN_LA_SESION, EVALS_SIN_BASE):
        resultado = _correr(tmp_path, configuracion)
        assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_el_contrato_de_capas_atrapa_al_cargador_que_sube_de_nivel(tmp_path: Path) -> None:
    """El cargador es la capa mas baja: si dependiera de la sesion, validar la
    configuracion exigiria base de datos y arrancar sin base dejaria de poder
    decir que carpeta esta rota."""
    _sembrar(tmp_path, {"untangle/tenancy/config.py": "from untangle.tenancy import session\n"})

    resultado = _correr(tmp_path, CAPAS_DE_TENANCY)

    assert resultado.returncode != 0
    assert "capas internas de tenancy" in resultado.stdout.lower()
    assert "config" in resultado.stdout


def test_el_contrato_del_cliente_atrapa_a_una_pieza_que_importa_el_mapeador(
    tmp_path: Path,
) -> None:
    """Sin el, "Acceso del visitante" podria construirse su propia conexion y
    nada lo diria: el aislamiento dejaria de tener un solo punto."""
    _sembrar(
        tmp_path,
        {
            "untangle/tenancy/visitor_access.py": (
                "import sqlalchemy\nfrom untangle.tenancy import session\n"
            )
        },
    )

    resultado = _correr(tmp_path, CLIENTE_SOLO_EN_LA_SESION)

    assert resultado.returncode != 0
    assert "visitor_access" in resultado.stdout
    assert "sqlalchemy" in resultado.stdout


def test_el_contrato_de_evals_atrapa_al_corredor_que_toca_la_sesion(tmp_path: Path) -> None:
    """Es lo que mantiene vivo el camino del clon al reporte sin base de datos, y
    con ello la cifra publicada de NFR21. Hasta U2 era cierto por accidente."""
    _sembrar(
        tmp_path,
        {"untangle/evals/cli.py": "from untangle.tenancy import session\n"},
    )

    resultado = _correr(tmp_path, EVALS_SIN_BASE)

    assert resultado.returncode != 0
    assert "evals" in resultado.stdout
    assert "session" in resultado.stdout


def test_el_contrato_de_evals_tambien_atrapa_el_camino_indirecto(tmp_path: Path) -> None:
    """Llegar a la sesion **a traves** de la raiz de composicion cuenta igual:
    lo que se protege es que el camino de arranque no necesite base, y da lo
    mismo por donde llegue."""
    _sembrar(
        tmp_path,
        {"untangle/evals/cli.py": "from untangle.server import composition\n"},
    )

    resultado = _correr(tmp_path, EVALS_SIN_BASE)

    assert resultado.returncode != 0
    assert "composition" in resultado.stdout
