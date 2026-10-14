"""El piso de cobertura agregado de los dos proyectos (NFR18.1, NFR18.3).

**Un solo numero ponderado por lineas**, no un promedio de porcentajes: un
proyecto de 200 lineas no puede pesar lo mismo que uno de 20.000, y promediar
porcentajes es exactamente el error que hace que un piso se cumpla en el papel.

El umbral vive en el manifiesto (`app/backend/pyproject.toml`, seccion
`[tool.untangle.coverage]`) junto a su lista de exclusion versionada, y este
comando **devuelve distinto de cero** cuando no se alcanza. Ese es el punto: un
piso que no hace fallar un comando es prosa.

El umbral no se baja para que un paso pase. Si no se alcanza, se escriben mas
pruebas o se dice que no se alcanzo, con el numero real.
"""

from __future__ import annotations

import sys
import tomllib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from untangle import paths


class CoverageInputMissingError(FileNotFoundError):
    """Falta un reporte de cobertura. El mensaje dice cual y como producirlo."""


@dataclass(frozen=True)
class ProjectCoverage:
    """Lo que aporta un proyecto al agregado: lineas, no porcentajes."""

    name: str
    covered: int
    total: int

    @property
    def percent(self) -> float:
        return 100.0 * self.covered / self.total if self.total else 0.0


@dataclass(frozen=True)
class CriticalModule:
    """Un modulo critico con su piso propio (NFR18.2).

    Son cinco en el proyecto --motor de reglas, verificador de citas,
    aislamiento por aseguradora, esquema del caso y redaccion de datos
    personales--, y llegan con U2, U3, U4, U8 y U9. La redaccion entro a la
    lista el 2026-09-20 por decision de Miguel: su compuerta detiene la entrega
    con un solo hallazgo y su fallo es silencioso. El agregado puede cumplirse con la interfaz cubierta y el aislamiento a
    medias; por eso cada uno se mide **aparte**.
    """

    path: str
    floor: float
    reason: str


def _seccion_de_cobertura(root: Path) -> dict[str, Any]:
    """La seccion del manifiesto donde viven el piso y las exclusiones."""
    archivo = root / "app" / "backend" / "pyproject.toml"
    datos: dict[str, Any] = tomllib.loads(archivo.read_text(encoding="utf-8"))
    seccion: dict[str, Any] = datos["tool"]["untangle"]["coverage"]
    return seccion


def read_floor(root: Path) -> float:
    """El umbral, leido del manifiesto y no de una bandera de linea de comandos."""
    return float(_seccion_de_cobertura(root)["aggregate_floor"])


def read_critical_modules(root: Path) -> tuple[CriticalModule, ...]:
    """Los modulos criticos declarados, con su piso y su razon."""
    entradas: list[dict[str, Any]] = _seccion_de_cobertura(root).get("critical_modules", [])
    return tuple(
        CriticalModule(
            path=str(entrada["path"]),
            floor=float(entrada["floor"]),
            reason=str(entrada["reason"]),
        )
        for entrada in entradas
    )


#: Modulos que el comando **informa** y no compara contra ningun piso.
#:
#: No son modulos criticos y no se declaran como tales (INF-U5-8): la plataforma
#: de proveedores y la contabilidad son adaptadores y telemetria, y `team.md`
#: deja dicho que los adaptadores pueden quedar por debajo mientras el agregado
#: se cumpla. Estan aqui por una razon distinta del piso: su cifra se **cita**,
#: y una cifra citada tiene que salir del comando que la nombra. Lo que gobierna
#: un piso es la lista del manifiesto; esta solo gobierna la impresion, y por eso
#: vive aqui y no alli, donde se leeria como una quinta fila con piso.
REPORTED_MODULES: tuple[str, ...] = (
    "app/backend/src/untangle/providers",
    "app/backend/src/untangle/telemetry",
)


def module_coverage(path: Path, module_path: str) -> ProjectCoverage:
    """Las lineas de un modulo dentro del reporte del backend.

    Las rutas del reporte son relativas al alcance declarado, asi que se vuelven
    a componer con el: comparar contra la mitad de una ruta encontraria de mas o
    de menos segun donde se invoque el comando.
    """
    raiz = ET.parse(path).getroot()  # noqa: S314 -- archivo propio, generado por la herramienta
    prefijos = [(fuente.text or "").rstrip("/") for fuente in raiz.iter("source")] or [""]

    cubiertas = 0
    totales = 0
    for clase in raiz.iter("class"):
        archivo = clase.get("filename") or ""
        completas = [f"{prefijo}/{archivo}" if prefijo else archivo for prefijo in prefijos]
        if not any(completa.startswith(module_path) for completa in completas):
            continue
        for linea in clase.iter("line"):
            totales += 1
            if int(linea.get("hits", "0")) > 0:
                cubiertas += 1

    return ProjectCoverage(name=module_path, covered=cubiertas, total=totales)


def _read_cobertura_xml(path: Path, name: str) -> ProjectCoverage:
    """Lee un reporte en el formato comun que emiten las dos herramientas."""
    if not path.is_file():
        msg = (
            f"falta el reporte de cobertura de {name}: se esperaba '{path}'. "
            "Corra `mise run cov`, que produce los dos antes de agregarlos."
        )
        raise CoverageInputMissingError(msg)

    raiz = ET.parse(path).getroot()  # noqa: S314 -- archivo propio, generado por la herramienta
    cubiertas = 0
    totales = 0
    for linea in raiz.iter("line"):
        totales += 1
        if int(linea.get("hits", "0")) > 0:
            cubiertas += 1
    return ProjectCoverage(name=name, covered=cubiertas, total=totales)


def aggregate(projects: list[ProjectCoverage]) -> ProjectCoverage:
    """Suma lineas cubiertas sobre lineas totales. Nunca promedia porcentajes."""
    return ProjectCoverage(
        name="agregado",
        covered=sum(p.covered for p in projects),
        total=sum(p.total for p in projects),
    )


def collect(root: Path) -> list[ProjectCoverage]:
    return [
        _read_cobertura_xml(root / "app" / "backend" / "coverage" / "coverage.xml", "backend"),
        _read_cobertura_xml(
            root / "app" / "frontend" / "coverage" / "cobertura-coverage.xml", "frontend"
        ),
    ]


def _informar_modulos(root: Path) -> None:
    """Imprime los modulos informados. **No devuelve fallos y no puede fallar.**

    La firma lo dice: no hay lista de fallos que devolver, asi que anadir una
    ruta aqui no puede convertirse en una compuerta por descuido. Lo unico que
    hace es que la cifra que alguien cita salga del comando que la cita.
    """
    reporte = root / "app" / "backend" / "coverage" / "coverage.xml"

    for ruta in REPORTED_MODULES:
        medido = module_coverage(reporte, ruta)
        etiqueta = ruta.split("/")[-1]
        print(
            f"{etiqueta:<10} {medido.covered:>6}/{medido.total:<6} lineas  "
            f"{medido.percent:6.2f} %  (informado, sin piso propio)"
        )


def _revisar_modulos_criticos(root: Path) -> list[str]:
    """Cada modulo critico contra **su** piso, e imprime lo medido (NFR18.2).

    El agregado puede cumplirse con la interfaz bien cubierta y el aislamiento a
    medias; estas son las filas que lo impiden.
    """
    reporte = root / "app" / "backend" / "coverage" / "coverage.xml"
    fallos: list[str] = []

    for modulo in read_critical_modules(root):
        medido = module_coverage(reporte, modulo.path)
        etiqueta = modulo.path.split("/")[-1]
        print(
            f"{etiqueta:<10} {medido.covered:>6}/{medido.total:<6} lineas  "
            f"{medido.percent:6.2f} %  (piso {modulo.floor:.0f} %, modulo critico)"
        )
        if medido.total == 0:
            fallos.append(
                f"{medido.name}: no se midio ninguna linea. Un modulo critico sin "
                "medicion no es un piso cumplido, es un piso no medido"
            )
        elif medido.percent < modulo.floor:
            fallos.append(
                f"{medido.name}: {medido.percent:.2f} %, por debajo de su piso de "
                f"{modulo.floor:.0f} % ({modulo.reason})"
            )
    return fallos


def main() -> int:
    raiz = paths.repo_root()
    piso = read_floor(raiz)

    try:
        proyectos = collect(raiz)
    except CoverageInputMissingError as error:
        print(str(error), file=sys.stderr)
        return 2

    total = aggregate(proyectos)

    for proyecto in proyectos:
        print(
            f"{proyecto.name:<10} {proyecto.covered:>6}/{proyecto.total:<6} "
            f"lineas  {proyecto.percent:6.2f} %"
        )
    print(
        f"{'agregado':<10} {total.covered:>6}/{total.total:<6} lineas  {total.percent:6.2f} %  "
        f"(piso {piso:.0f} %)"
    )

    if total.total == 0:
        print(
            "no se midio ninguna linea: el reporte esta vacio y eso no es un "
            "piso cumplido, es un piso no medido",
            file=sys.stderr,
        )
        return 1

    _informar_modulos(raiz)
    fallos = _revisar_modulos_criticos(raiz)
    if total.percent < piso:
        fallos.insert(
            0,
            f"cobertura agregada {total.percent:.2f} %, por debajo del piso de "
            f"{piso:.0f} % ({piso - total.percent:.2f} puntos)",
        )

    if fallos:
        print("", file=sys.stderr)
        for fallo in fallos:
            print(fallo, file=sys.stderr)
        print(
            "\nEl umbral no se baja: se escriben mas pruebas, o se dice que no se "
            "alcanzo con el numero real.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
