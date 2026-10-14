"""Comprueba que los controles de cadena de suministro estan **vivos** (SEC-U1.4).

La razon de que este chequeo exista es un fallo real, encontrado el 2026-09-20:
los dos ajustes de pnpm estaban escritos en `app/frontend/.npmrc` y pnpm 12 no
los leia. No avisaba. El archivo se veia bien, el control no existia, y nada
habria dicho lo contrario hasta que alguien lo probara.

Desde pnpm 10 los ajustes propios de pnpm viven en `pnpm-workspace.yaml` y
`.npmrc` se queda con lo compatible con npm. Un ajuste de pnpm dejado en
`.npmrc` se ignora en silencio.

Por eso este chequeo **no lee archivos de configuracion**: le pregunta a cada
herramienta que valor tiene de verdad. Un control que solo se comprueba leyendo
el archivo donde se escribio no comprueba nada.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from untangle import paths

# Tres dias en minutos. El ataque tipico de cadena de suministro vive en las
# primeras horas de una version publicada, y la mayoria de los paquetes
# comprometidos se retiran dentro del primer dia.
ESPERA_MINIMA_MINUTOS = 4320
ESPERA_MINIMA_UV = "3 days ago"


def _pnpm_config(clave: str, directorio: Path) -> str:
    salida = subprocess.run(  # noqa: S603  -- binario fijo, argumentos literales
        ["pnpm", "config", "get", clave],  # noqa: S607
        cwd=directorio,
        capture_output=True,
        text=True,
        check=False,
    )
    return salida.stdout.strip()


#: Las secciones de `app/frontend/DEPENDENCIES.md` y lo que cada una registra.
SECCIONES_DE_DEPENDENCIAS = ("Ejecución", "Desarrollo y pruebas")
SECCION_DE_SUSTITUCIONES = "Sustituciones de versión"
SECCION_DE_AVISOS = "Avisos de seguridad aceptados"

#: Una fila de la tabla de avisos: el identificador **sin** comillas invertidas,
#: porque un aviso no es un paquete, y su ultima celda es la fecha de revision. Es
#: un `GHSA-` (pnpm) o un `CVE-` (`pip-audit --ignore-vuln`, que usa el que le dio
#: la base de avisos de Python).
FILA_DE_AVISO = re.compile(
    r"^\|\s*(?P<aviso>GHSA-[0-9a-z-]+|CVE-\d{4}-\d+)\s*\|(?P<resto>.*)\|\s*$"
)

#: Lo que la tarea `audit` de `mise.toml` le pasa a `pip-audit` para no bloquear un aviso.
IGNORAR_EN_PYTHON = re.compile(r"--ignore-vuln[ =]+(?P<aviso>\S+)")

#: Una fila de la tabla: el paquete entre comillas invertidas y sus celdas.
FILA = re.compile(r"^\|\s*`(?P<paquete>[^`]+)`\s*\|(?P<resto>.*)\|\s*$")


def _filas_por_seccion(texto: str) -> dict[str, dict[str, list[str]]]:
    """Las filas de cada seccion `##`, por paquete, con sus celdas."""
    secciones: dict[str, dict[str, list[str]]] = {}
    actual = ""
    for linea in texto.splitlines():
        if linea.startswith("## "):
            actual = linea[3:].strip()
            secciones.setdefault(actual, {})
            continue
        coincidencia = FILA.match(linea)
        if coincidencia is not None and actual:
            celdas = [celda.strip() for celda in coincidencia.group("resto").split("|")]
            secciones[actual][coincidencia.group("paquete")] = celdas
    return secciones


def _sustituidos(workspace: Path) -> list[str]:
    """Los paquetes cuya version fija `overrides` en `pnpm-workspace.yaml`."""
    if not workspace.is_file():
        return []
    cargado: Any = yaml.safe_load(workspace.read_text(encoding="utf-8")) or {}
    sustituciones = (cargado.get("overrides") or {}) if isinstance(cargado, dict) else {}
    return sorted(str(clave).rsplit(">", 1)[-1] for clave in sustituciones)


def _avisos_ignorados(workspace: Path) -> list[str]:
    """Los avisos que la auditoria no bloquea, tal como los lee pnpm."""
    if not workspace.is_file():
        return []
    cargado: Any = yaml.safe_load(workspace.read_text(encoding="utf-8")) or {}
    config = (cargado.get("auditConfig") or {}) if isinstance(cargado, dict) else {}
    return sorted(str(aviso) for aviso in (config.get("ignoreGhsas") or []))


def _avisos_ignorados_en_python(mise: Path) -> list[str]:
    """Los avisos que la auditoria de Python no bloquea: los `--ignore-vuln` de `audit`.

    Se leen de la tarea tal como `mise` la va a correr y no de una lista aparte: una
    segunda lista diria lo que se quiso ignorar y no lo que se ignora de verdad.
    """
    if not mise.is_file():
        return []
    datos: Any = tomllib.loads(mise.read_text(encoding="utf-8"))
    orden = datos.get("tasks", {}).get("audit", {}).get("run", [])
    comandos = [orden] if isinstance(orden, str) else [str(paso) for paso in orden]
    return sorted({m.group("aviso") for paso in comandos for m in IGNORAR_EN_PYTHON.finditer(paso)})


def _filas_de_avisos(texto: str) -> dict[str, list[str]]:
    """Las filas de la seccion de avisos aceptados, por aviso, con sus celdas."""
    filas: dict[str, list[str]] = {}
    actual = ""
    for linea in texto.splitlines():
        if linea.startswith("## "):
            actual = linea[3:].strip()
            continue
        coincidencia = FILA_DE_AVISO.match(linea)
        if coincidencia is not None and actual == SECCION_DE_AVISOS:
            celdas = [celda.strip() for celda in coincidencia.group("resto").split("|")]
            filas[coincidencia.group("aviso")] = celdas
    return filas


def check_accepted_advisories(root: Path, *, today: date | None = None) -> list[str]:
    """Cada aviso que la auditoria no bloquea tiene su fila y **su fecha por llegar**.

    Es lo que hace que una excepcion caduque. La auditoria de dependencias falla
    ante un aviso alto, y tanto pnpm (`ignoreGhsas`) como `pip-audit`
    (`--ignore-vuln` en la tarea `audit`) admiten ignorar uno por su identificador:
    sin este chequeo, ese identificador se escribe una vez y nadie vuelve a mirarlo
    --ni cuando sale el parche, ni cuando la dependencia cambia de sitio y el aviso
    ya no es de la cadena del linter sino del navegador--.

    Se comprueba en las dos direcciones, como la tabla de dependencias: un aviso
    ignorado sin fila no tiene razon escrita, y una fila sin aviso ignorado
    describe una excepcion que ya no existe.
    """
    hoy = today if today is not None else date.today()
    registro = root / "app" / "frontend" / "DEPENDENCIES.md"
    if not registro.is_file():
        return []  # la falta del registro ya la reporta el chequeo de dependencias
    # Los dos gestores comparten tabla: el aviso ignorado por pnpm y el que ignora
    # `pip-audit` caducan igual, y una excepcion de Python que solo viviera en un
    # comentario de `mise.toml` era la que nadie volvia a mirar.
    ignorados = sorted(
        {
            *_avisos_ignorados(root / "app" / "frontend" / "pnpm-workspace.yaml"),
            *_avisos_ignorados_en_python(root / "mise.toml"),
        }
    )
    filas = _filas_de_avisos(registro.read_text(encoding="utf-8"))

    problemas = [
        f"DEPENDENCIES.md: el aviso '{aviso}' se ignora en la auditoria y no tiene su "
        "fila en 'Avisos de seguridad aceptados' (por donde llega, por que no bloquea "
        "y cuando se revisa)"
        for aviso in ignorados
        if aviso not in filas
    ]
    problemas.extend(
        f"DEPENDENCIES.md: el aviso '{aviso}' tiene fila y la auditoria ya no lo ignora: "
        "si se cerro, la fila sobra"
        for aviso in sorted(filas.keys() - set(ignorados))
    )
    for aviso in ignorados:
        celdas = filas.get(aviso)
        if celdas is None:
            continue
        if len(celdas) < 4 or not all(celdas[:4]):
            problemas.append(
                f"DEPENDENCIES.md: la fila del aviso '{aviso}' tiene celdas vacias "
                "(paquete, por donde llega, por que no bloquea y cuando se revisa)"
            )
            continue
        problemas.extend(_fecha_de_revision(aviso, celdas[3], hoy=hoy))
    return problemas


def _fecha_de_revision(aviso: str, celda: str, *, hoy: date) -> list[str]:
    """La fecha de la ultima celda, si es una y si todavia no llego."""
    try:
        revision = date.fromisoformat(celda)
    except ValueError:
        return [
            f"DEPENDENCIES.md: la fecha de revision del aviso '{aviso}' no es una fecha "
            f"ISO-8601: '{celda}'"
        ]
    if revision < hoy:
        return [
            f"DEPENDENCIES.md: la excepcion del aviso '{aviso}' vencio el "
            f"{revision.isoformat()}: hay que mirar si ya tiene parche y renovarla con "
            "su razon o quitarla"
        ]
    return []


def check_frontend_dependencies(root: Path) -> list[str]:
    """TECH-U6.1: cada dependencia de la interfaz tiene su linea, y cada linea su dependencia.

    Una linea: que hace, por que no alcanza la plataforma y su licencia, con las
    tres celdas escritas. Se compara en las dos direcciones --una linea que ya no
    tiene dependencia describe algo que no se instala-- y cada falta sale
    nombrando el paquete. Las sustituciones de version de `pnpm-workspace.yaml`
    tambien necesitan la suya, con su razon.
    """
    frontend = root / "app" / "frontend"
    registro = frontend / "DEPENDENCIES.md"
    if not registro.is_file():
        return [f"falta el registro de dependencias de la interfaz: se esperaba '{registro}'"]

    manifiesto: dict[str, Any] = json.loads((frontend / "package.json").read_text(encoding="utf-8"))
    declaradas = {
        *manifiesto.get("dependencies", {}),
        *manifiesto.get("devDependencies", {}),
    }
    secciones = _filas_por_seccion(registro.read_text(encoding="utf-8"))
    # El titulo de la seccion puede llevar una aclaracion despues del nombre.
    filas: dict[str, list[str]] = {}
    sustituciones: dict[str, list[str]] = {}
    for titulo, contenido in secciones.items():
        if titulo.startswith(SECCIONES_DE_DEPENDENCIAS):
            filas.update(contenido)
        elif titulo.startswith(SECCION_DE_SUSTITUCIONES):
            sustituciones.update(contenido)

    problemas = [
        f"DEPENDENCIES.md: falta la linea de '{paquete}' (que hace, por que no alcanza "
        "la plataforma y su licencia)"
        for paquete in sorted(declaradas - filas.keys())
    ]
    problemas.extend(
        f"DEPENDENCIES.md: '{paquete}' tiene linea pero no esta en package.json"
        for paquete in sorted(filas.keys() - declaradas)
    )
    problemas.extend(
        f"DEPENDENCIES.md: la linea de '{paquete}' tiene celdas vacias"
        for paquete, celdas in sorted({**filas, **sustituciones}.items())
        if len(celdas) < 3 or not all(celdas[:3])
    )
    problemas.extend(
        f"DEPENDENCIES.md: la sustitucion de version de '{paquete}' no tiene su linea"
        for paquete in _sustituidos(frontend / "pnpm-workspace.yaml")
        if paquete not in sustituciones
    )
    return problemas


def run_all(root: Path | None = None) -> list[str]:
    base = root if root is not None else paths.repo_root()
    frontend = base / "app" / "frontend"
    problemas: list[str] = []

    # --- pnpm: se le pregunta a la herramienta, no al archivo -----------------
    espera = _pnpm_config("minimumReleaseAge", frontend)
    if espera != str(ESPERA_MINIMA_MINUTOS):
        problemas.append(
            f"pnpm minimumReleaseAge: pnpm responde '{espera or 'undefined'}' y se "
            f"esperaba '{ESPERA_MINIMA_MINUTOS}'. Si el valor esta en '.npmrc', "
            "muevelo a 'pnpm-workspace.yaml': desde pnpm 10 ahi se ignora en silencio"
        )

    scripts = _pnpm_config("ignoreScripts", frontend)
    if scripts != "true":
        problemas.append(
            f"pnpm ignoreScripts: pnpm responde '{scripts or 'undefined'}' y se "
            "esperaba 'true' (ADR-002). Mismo motivo: tiene que estar en "
            "'pnpm-workspace.yaml'"
        )

    # --- uv: el ajuste vive en el manifiesto y uv lo aplica al resolver -------
    manifiesto = base / "app" / "backend" / "pyproject.toml"
    if not manifiesto.is_file():
        problemas.append(f"falta el manifiesto de Python: se esperaba '{manifiesto}'")
    else:
        with manifiesto.open("rb") as handle:
            datos = tomllib.load(handle)
        valor = datos.get("tool", {}).get("uv", {}).get("exclude-newer")
        if valor != ESPERA_MINIMA_UV:
            problemas.append(
                f"uv exclude-newer: el manifiesto dice '{valor}' y se esperaba '{ESPERA_MINIMA_UV}'"
            )

    # --- La licencia y la razon de cada dependencia de la interfaz (U6) -------
    problemas.extend(check_frontend_dependencies(base))

    # --- Y cada aviso que la auditoria no bloquea, con su fecha por llegar ----
    problemas.extend(check_accepted_advisories(base))

    return problemas


def main() -> int:
    problemas = run_all()
    for problema in problemas:
        print(problema, file=sys.stderr)
    if problemas:
        print(
            f"\n{len(problemas)} control(es) de cadena de suministro sin efecto",
            file=sys.stderr,
        )
        return 1
    print(
        "cadena de suministro: la espera de tres dias esta activa en los dos gestores, "
        "cada dependencia de la interfaz tiene su linea y cada aviso aceptado su fecha"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
