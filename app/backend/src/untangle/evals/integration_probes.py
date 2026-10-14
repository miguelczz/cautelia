"""Los tres criterios de U12 que mide una prueba de integracion (2026-10-09).

La pregunta de cobertura a mitad del reporte y la llamada cortada con reanudacion
(`DS-2/{es,en}/coverage-question-mid-report`, `DS-2/{es,en}/dropped-call-resumed`)
se escribieron como casos del set con su sonda en
`tests/integration/u12/test_turn.py`, porque necesitan el grafo con su base. Nunca se
registraron en el corredor, y la corrida completa se detenia en el primero de ellos
("nombra el criterio ..., que no esta registrado"): no habia linea base posible.

**La sonda corre esa prueba en otro proceso** y lee su resultado. En otro proceso y
no importandola, por el contrato `evals-sin-base-de-datos`: el corredor sigue sin
abrir ninguna conexion, y quien llega sin base ve el caso **no medido**, con la
causa `target_unavailable`, nunca en verde ni omitido (NFR10.3). Un fallo de la
prueba es un fallo del caso; un error de preparacion o un salto, no medido.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from functools import cache
from pathlib import Path

from untangle import paths
from untangle.base import Locale
from untangle.evals.runner.api import CheckOutcome, EvalCheck, register_check
from untangle.evals.runner.failures import TargetUnavailableError

_ARCHIVO = "tests/integration/u12/test_turn.py"

#: El criterio y la prueba que lo mide; la prueba esta parametrizada por idioma.
CRITERIOS: dict[str, str] = {
    "coverage_question_mid_report_does_not_derail_capture": "test_ds2_coverage_question_mid_report",
    "two_consecutive_coverage_questions_return_once": "test_ds2_coverage_question_mid_report",
    "resume_after_simulated_restart_does_not_reask_confirmed_fields": (
        "test_ds2_dropped_call_resumed"
    ),
}

#: Lo que tarda como maximo una de estas pruebas, con su base efimera.
_TOPE_SEGUNDOS = 300


@cache
def _correr(prueba: str, language: Locale) -> CheckOutcome:
    """Corre la prueba una vez por idioma; los dos criterios de un caso la comparten."""
    nodo = f"{_ARCHIVO}::{prueba}[{language}]"
    with tempfile.TemporaryDirectory() as carpeta:
        reporte = Path(carpeta) / "junit.xml"
        proceso = subprocess.run(  # noqa: S603 -- argumentos fijos, sin shell
            [
                sys.executable,
                "-m",
                "pytest",
                nodo,
                "-q",
                "-p",
                "no:cacheprovider",
                f"--junitxml={reporte}",
            ],
            cwd=paths.backend_dir(),
            capture_output=True,
            text=True,
            timeout=_TOPE_SEGUNDOS,
            check=False,
        )
        if not reporte.is_file():
            msg = f"{nodo}: pytest no produjo reporte (salida {proceso.returncode})"
            raise TargetUnavailableError(msg)
        caso = ET.parse(reporte).find(".//testcase")  # noqa: S314 -- archivo propio
    if caso is None:
        msg = f"{nodo}: la prueba no existe o no se recogio"
        raise TargetUnavailableError(msg)
    if caso.find("failure") is not None:
        return CheckOutcome(passed=False, detail=f"{nodo} fallo")
    if caso.find("error") is not None or caso.find("skipped") is not None:
        # Sin base efimera la preparacion falla: es una compuerta que no se pudo
        # ejecutar, no una conducta rota.
        msg = f"{nodo}: no se pudo preparar (sin base local?)"
        raise TargetUnavailableError(msg)
    return CheckOutcome(passed=True)


def _sonda(prueba: str) -> EvalCheck:
    def chequeo(*, language: Locale, root: Path) -> CheckOutcome:
        del root
        return _correr(prueba, language)

    return chequeo


def register_integration_probes() -> None:
    """Registra los tres criterios de U12 en el corredor."""
    for criterio, prueba in CRITERIOS.items():
        register_check(criterio, _sonda(prueba))
