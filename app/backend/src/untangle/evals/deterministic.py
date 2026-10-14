"""Los chequeos deterministas del sistema, como casos de evaluacion (CG-2).

El diseno dejo el subconjunto de arranque como una lista vacia que cada unidad
rellenaria. Una lista vacia produce un reporte de cero casos, y el primer Bolt no
podria demostrar su propio criterio de terminado: "clonar y llegar al reporte".

Estos son los casos que U1 **si puede producir**: chequeos que se resuelven sin
llamar a ningun modelo. Son casos reales del sistema, con identificador estable,
no casos de adorno. La practica del equipo ya los pedia en el reporte: "chequeos
de contenido con identificador estable, para que aparezcan en el reporte por caso
y en el diff contra la linea base como cualquier otra prueba".

Cada uno se mide **por idioma**, y eso no es una formalidad: la paridad de un
producto bilingue es justamente lo que un promedio esconderia.
"""

from __future__ import annotations

from pathlib import Path

from untangle.base import Locale
from untangle.copy_catalog import checks as copy_checks
from untangle.copy_catalog.loading import load_raw_entries
from untangle.evals import loading
from untangle.evals.runner.api import CheckOutcome, register_check


def _copy_dir(root: Path) -> Path:
    return root / "app" / "config" / "copy"


def copy_catalog_parity(*, language: Locale, root: Path) -> CheckOutcome:
    """Toda clave del catalogo existe en este idioma (BR3.1)."""
    entradas = load_raw_entries(_copy_dir(root))
    todas = {clave for clave, _ in entradas}
    en_este_idioma = {clave for clave, locale in entradas if locale == language}
    faltan = sorted(todas - en_este_idioma)
    if faltan:
        return CheckOutcome(
            passed=False,
            detail=f"faltan en {language}: {', '.join(faltan)}",
        )
    return CheckOutcome(passed=True)


def copy_catalog_consumers(*, language: Locale, root: Path) -> CheckOutcome:
    """Toda clave de este idioma tiene consumidor literal en el codigo (BR3.2)."""
    entradas = {
        par: valor for par, valor in load_raw_entries(_copy_dir(root)).items() if par[1] == language
    }
    hallazgos = copy_checks.check_consumers(entradas, root)
    if hallazgos:
        return CheckOutcome(
            passed=False,
            detail=f"sin consumidor: {', '.join(h.where for h in hallazgos)}",
        )
    return CheckOutcome(passed=True)


def copy_forbidden_forms(*, language: Locale, root: Path) -> CheckOutcome:
    """Ninguna frase de este idioma usa una forma prohibida (BR3.6)."""
    entradas = {
        par: valor for par, valor in load_raw_entries(_copy_dir(root)).items() if par[1] == language
    }
    hallazgos = copy_checks.check_forbidden_forms(entradas, root)
    if hallazgos:
        return CheckOutcome(
            passed=False,
            detail="; ".join(f"{h.where} {h.detail}" for h in hallazgos),
        )
    return CheckOutcome(passed=True)


def golden_case_schema(*, language: Locale, root: Path) -> CheckOutcome:
    """Todo caso de este idioma valida su esquema (M1).

    Se valida archivo por archivo para poder nombrar el que falla. Cargar todo de
    golpe diria que algo esta mal sin decir que.
    """
    directorio = root / "app" / "evals" / "cases"
    problemas: list[str] = []
    for archivo in sorted(directorio.rglob("*.yaml"), key=lambda p: p.as_posix()):
        try:
            caso = loading.load_case(archivo)
        except loading.LoadError as error:
            problemas.append(str(error))
            continue
        if caso.language != language:
            continue
    if problemas:
        return CheckOutcome(passed=False, detail="; ".join(problemas))
    return CheckOutcome(passed=True)


#: Los chequeos que U1 aporta al corredor, por el criterio que resuelven.
CHEQUEOS = {
    "copy_catalog_parity": copy_catalog_parity,
    "copy_catalog_consumers": copy_catalog_consumers,
    "copy_forbidden_forms": copy_forbidden_forms,
    "golden_case_schema": golden_case_schema,
}


def register_builtin_checks() -> None:
    """Registra los chequeos deterministas de U1 en el corredor."""
    for criterio, chequeo in CHEQUEOS.items():
        register_check(criterio, chequeo)
