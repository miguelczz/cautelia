"""La licencia de cada dependencia del arbol resuelto, contra una lista versionada.

El repositorio es candidato a publicarse (D-017), y la practica del equipo pide
registrar la licencia de cada dependencia y **rechazar la que impida
publicarlo**. Eso se reviso a mano el 2026-09-27 y la revision a mano encontro
lo que siempre encuentra: casi todo. Se le escaparon los dos modelos de spaCy,
que entran por un extra con su URL y no aparecen en el arbol de dependencias que
uno lee -- y uno de los dos, el espanol, es **GPL-3.0**.

De ahi la forma de este chequeo, que no es "una lista de licencias escrita hoy":

1. **Enumera el arbol resuelto**, los dos gestores, transitivas incluidas. Nadie
   escribe la lista de paquetes: se pregunta.
2. **Exige que lo instalado sea lo que fija el lockfile.** Si un paquete que el
   lockfile fija no esta instalado, el chequeo **falla** en vez de revisar un
   arbol incompleto. Esa es exactamente la grieta por la que el modelo espanol
   paso desapercibido: sin los modelos instalados, un chequeo silencioso habria
   dado verde.
3. **Compara contra la lista de `[tool.untangle.licenses]`**, donde cada licencia
   admitida lleva su razon. Una licencia que nadie decidio admitir detiene la
   entrega; no hay lista de bloqueadas que haya que mantener al dia, porque una
   lista de bloqueadas se queda corta con la primera licencia nueva y una de
   admitidas no.

Lo que **no** cubre: los recursos que no son paquetes --voces, tipografias
sueltas, corpus-- se registran a mano donde vive el recurso
(`site/PHOSPHOR-LICENSE.txt` es el precedente). Las tipografias que si entran
por npm (`@fontsource/*`, OFL-1.1) las ve este chequeo como cualquier otro
paquete.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from importlib import metadata as md
from pathlib import Path
from typing import Any, Protocol

from packaging.requirements import InvalidRequirement, Requirement

from untangle import paths

#: Los dos gestores. El nombre de un paquete solo es unico dentro del suyo, asi
#: que toda entrada escrita a mano dice a cual pertenece.
PYTHON = "python"
NPM = "npm"

#: Separadores de una expresion SPDX compuesta (`A AND B`, `A OR B`, `A WITH e`).
#: Se exige que **todas** las licencias nombradas esten admitidas, incluso en un
#: `OR` donde bastaria una: la regla "solo licencias que alguien decidio" es mas
#: simple de sostener que "alguna rama sirve", y hoy no cuesta nada --las dos
#: ramas de los dos `OR` del arbol estan admitidas.
_SEPARADORES = re.compile(r"\s+(?:AND|OR|WITH)\s+|[()]")

#: Texto libre que nombra **una** licencia. Se traduce sin preguntar porque no
#: hay dos lecturas posibles.
ALIAS: dict[str, str] = {
    "mit license": "MIT",
    "mit": "MIT",
    "mit-0": "MIT-0",
    "apache software license": "Apache-2.0",
    "apache license, version 2.0": "Apache-2.0",
    # "Modified BSD" es el sinonimo habitual de las tres clausulas, y no se
    # tradujo de memoria: se leyeron los dos archivos de licencia que lo usan
    # (`jsonpatch` y `jsonpointer`, 2026-09-27) y los dos traen la tercera
    # clausula, la del nombre del autor.
    "modified bsd license": "BSD-3-Clause",
    "apache license 2.0": "Apache-2.0",
    "apache 2.0": "Apache-2.0",
    "apache-2.0": "Apache-2.0",
    "bsd 2-clause license": "BSD-2-Clause",
    "bsd-2-clause": "BSD-2-Clause",
    "bsd 3-clause license": "BSD-3-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "mozilla public license 2.0 (mpl 2.0)": "MPL-2.0",
    "mpl-2.0": "MPL-2.0",
    "isc license (iscl)": "ISC",
    "isc license": "ISC",
    "isc": "ISC",
    "python software foundation license": "PSF-2.0",
    "psfl": "PSF-2.0",
    "psf-2.0": "PSF-2.0",
    # El metadato no dice "or later", asi que se lee la version fijada, que es la
    # lectura estricta. Si algun dia la diferencia importa, la resuelve la fuente
    # del paquete y no esta tabla.
    "gnu gpl 3.0": "GPL-3.0-only",
    "gpl-3.0-only": "GPL-3.0-only",
    "lgpl-3.0-only": "LGPL-3.0-only",
    "0bsd": "0BSD",
    "zlib": "Zlib",
    "cc0-1.0": "CC0-1.0",
    "cc-by-4.0": "CC-BY-4.0",
    "ofl-1.1": "OFL-1.1",
    "unlicense": "Unlicense",
    "blueoak-1.0.0": "BlueOak-1.0.0",
    "python-2.0": "Python-2.0",
    "cnri-python": "CNRI-Python",
}

#: Texto que nombra una **familia** y no una licencia: "BSD" no dice si son dos
#: clausulas o tres, y "GPL" no dice ni la version. No se adivina -- el paquete
#: pasa a necesitar su entrada en `declared`, con la fuente donde se leyo.
FAMILIAS = frozenset({"bsd", "bsd license", "gpl", "lgpl", "agpl", "gnu general public license"})


def _normalizar(nombre: str) -> str:
    """El nombre de un paquete de Python en su forma canonica (PEP 503)."""
    return re.sub(r"[-_.]+", "-", nombre).lower()


def _ids(expresion: str) -> tuple[str, ...]:
    """Las licencias que nombra una expresion, ya traducidas cuando hacia falta."""
    piezas = (pieza.strip() for pieza in _SEPARADORES.split(expresion))
    return tuple(ALIAS.get(pieza.lower(), pieza) for pieza in piezas if pieza)


@dataclass(frozen=True)
class Paquete:
    """Un paquete del arbol resuelto y lo que dice su propio metadato."""

    ecosystem: str
    name: str
    version: str
    #: Vacio cuando el metadato no dice nada utilizable: entonces hace falta su
    #: entrada en `declared`.
    licenses: tuple[str, ...]
    #: De donde salio la licencia, para que un fallo se pueda comprobar.
    source: str


class Metadato(Protocol):
    """Lo unico que se le pide al metadato de una distribucion: dos lecturas.

    Se declara la forma que se usa en vez de `importlib.metadata.PackageMetadata`
    para que una prueba pueda construir un metadato de mentira sin rellenar una
    interfaz que este modulo no toca.
    """

    def get(self, name: str, failobj: None = None) -> str | None: ...

    def get_all(self, name: str, failobj: None = None) -> list[str] | None: ...


def _licencias_de_metadato(metadato: Metadato) -> tuple[tuple[str, ...], str]:
    """Las licencias de una distribucion instalada, por orden de autoridad.

    PEP 639 (`License-Expression`) es SPDX y manda. Detras van el campo de texto
    libre y los clasificadores, que se traducen solo cuando nombran una licencia
    concreta.
    """
    expresion = (metadato.get("License-Expression") or "").strip()
    if expresion:
        return _ids(expresion), "License-Expression"

    libre = (metadato.get("License") or "").strip()
    # `pip-api` mete el texto completo de la licencia en este campo: lo que no
    # cabe en una linea no es un identificador.
    if libre and "\n" not in libre and len(libre) <= 60 and libre.lower() not in FAMILIAS:
        traducido = _ids(libre)
        if traducido:
            return traducido, "License"

    clasificadores = [
        c.split(" :: ")[-1].strip()
        for c in (metadato.get_all("Classifier") or [])
        if str(c).startswith("License ::")
    ]
    concretos = tuple(
        ALIAS[c.lower()] for c in clasificadores if c.lower() in ALIAS and c.lower() not in FAMILIAS
    )
    if concretos:
        return concretos, "Classifier"
    return (), "sin licencia en el metadato"


def _requisitos_del_lockfile(root: Path) -> tuple[set[str], list[str]]:
    """Los paquetes que el lockfile fija **y que aplican a esta maquina**.

    Se exporta el lockfile en vez de leer lo instalado porque lo que el proyecto
    promete es el lockfile; y se evaluan los marcadores porque el mismo lockfile
    fija `pywin32` o `colorama`, que en macOS no se instalan y no faltan.
    """
    salida = subprocess.run(
        [  # noqa: S607
            "uv",
            "export",
            "--project",
            "app/backend",
            "--format",
            "requirements-txt",
            "--all-groups",
            "--all-extras",
            "--no-emit-project",
            "--no-hashes",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if salida.returncode != 0:
        return set(), [
            f"no se pudo exportar el lockfile: {salida.stderr.strip().splitlines()[-1:]}"
        ]

    fijados: set[str] = set()
    for linea in salida.stdout.splitlines():
        limpia = linea.split("#", 1)[0].strip()
        if not limpia or limpia.startswith("-"):
            continue
        try:
            requisito = Requirement(limpia)
        except InvalidRequirement:
            continue
        if requisito.marker is not None and not requisito.marker.evaluate():
            continue
        fijados.add(_normalizar(requisito.name))
    return fijados, []


def python_packages(root: Path) -> tuple[list[Paquete], list[str]]:
    """El arbol de Python, con el lockfile como arbitro de que tiene que estar."""
    instalados = {_normalizar(d.metadata["Name"]): d for d in md.distributions()}
    fijados, problemas = _requisitos_del_lockfile(root)

    faltan = sorted(fijados - instalados.keys())
    if faltan:
        problemas.append(
            f"{len(faltan)} paquete(s) que el lockfile fija no estan instalados, asi que su "
            f"licencia no se puede leer: {', '.join(faltan)}. Corre `mise run deps:install` y, "
            "si falta alguno de los modelos de spaCy, `mise run models:install`"
        )

    paquetes: list[Paquete] = []
    for nombre in sorted(fijados & instalados.keys()):
        metadato = instalados[nombre].metadata
        licencias, origen = _licencias_de_metadato(metadato)
        paquetes.append(
            Paquete(
                ecosystem=PYTHON,
                name=nombre,
                version=metadato["Version"] or "?",
                licenses=licencias,
                source=origen,
            )
        )
    return paquetes, problemas


def npm_packages(root: Path) -> tuple[list[Paquete], list[str]]:
    """El arbol de la interfaz, tal como pnpm lo resolvio."""
    salida = subprocess.run(
        ["pnpm", "licenses", "list", "--json"],  # noqa: S607
        cwd=root / "app" / "frontend",
        capture_output=True,
        text=True,
        check=False,
    )
    if salida.returncode != 0 or not salida.stdout.strip():
        return [], [
            "no se pudo listar las licencias de la interfaz: "
            f"{(salida.stderr or salida.stdout).strip().splitlines()[-1:]}. "
            "Instala primero con `mise run deps:install`"
        ]

    agrupado: dict[str, Any] = json.loads(salida.stdout)
    paquetes: list[Paquete] = []
    for declarada, entradas in agrupado.items():
        for entrada in entradas:
            licencia = str(entrada.get("license") or declarada or "").strip()
            traducidas = _ids(licencia) if licencia and licencia.lower() not in FAMILIAS else ()
            paquetes.append(
                Paquete(
                    ecosystem=NPM,
                    name=str(entrada["name"]),
                    version=",".join(entrada.get("versions") or []) or "?",
                    licenses=traducidas,
                    source="pnpm licenses list",
                )
            )
    return sorted(paquetes, key=lambda p: p.name), []


@dataclass(frozen=True)
class Politica:
    """Lo que `[tool.untangle.licenses]` decide, con su razon por entrada."""

    allowed: dict[str, str] = field(default_factory=dict)
    #: Licencia leida a mano de la fuente, para el paquete cuyo metadato calla.
    declared: dict[tuple[str, str], tuple[str, ...]] = field(default_factory=dict)
    #: Licencia fuera de la lista admitida para un paquete nombrado, con fecha.
    exceptions: dict[tuple[str, str], tuple[tuple[str, ...], str, str]] = field(
        default_factory=dict
    )


def _clave(entrada: dict[str, Any]) -> tuple[str, str]:
    ecosistema = str(entrada["ecosystem"])
    nombre = str(entrada["package"])
    return (ecosistema, _normalizar(nombre) if ecosistema == PYTHON else nombre)


def load_policy(root: Path) -> tuple[Politica, list[str]]:
    manifiesto = root / "app" / "backend" / "pyproject.toml"
    if not manifiesto.is_file():
        return Politica(), [f"falta el manifiesto: se esperaba '{manifiesto}'"]
    with manifiesto.open("rb") as handle:
        datos = tomllib.load(handle)
    seccion = datos.get("tool", {}).get("untangle", {}).get("licenses", {})
    if not seccion:
        return Politica(), ["falta '[tool.untangle.licenses]' en app/backend/pyproject.toml"]

    problemas: list[str] = []
    admitidas: dict[str, str] = {}
    for entrada in seccion.get("allowed", []):
        razon = str(entrada.get("reason") or "").strip()
        if not razon:
            problemas.append(f"la licencia admitida '{entrada.get('id')}' no dice por que")
        admitidas[str(entrada["id"])] = razon

    declaradas = {_clave(e): tuple(e["licenses"]) for e in seccion.get("declared", [])}
    for entrada in seccion.get("declared", []):
        if not str(entrada.get("source") or "").strip():
            problemas.append(
                f"la licencia declarada a mano de '{entrada.get('package')}' no dice de "
                "donde se leyo"
            )

    excepciones: dict[tuple[str, str], tuple[tuple[str, ...], str, str]] = {}
    for entrada in seccion.get("exceptions", []):
        razon = str(entrada.get("reason") or "").strip()
        fecha = str(entrada.get("date") or "").strip()
        if not razon or not fecha:
            problemas.append(
                f"la excepcion de '{entrada.get('package')}' necesita razon y fecha escritas"
            )
        excepciones[_clave(entrada)] = (tuple(entrada["licenses"]), razon, fecha)

    return Politica(allowed=admitidas, declared=declaradas, exceptions=excepciones), problemas


@dataclass(frozen=True)
class Informe:
    problems: list[str]
    #: Las excepciones que se usaron, para imprimirlas en cada corrida: una
    #: excepcion que nadie vuelve a leer es una decision olvidada.
    used_exceptions: list[str]
    checked: int


def evaluate(paquetes: Iterable[Paquete], politica: Politica) -> Informe:
    """Compara el arbol contra la politica. Un paquete sin licencia decidida falla."""
    problemas: list[str] = []
    usadas: list[str] = []
    total = 0

    for paquete in paquetes:
        total += 1
        clave = (paquete.ecosystem, paquete.name)

        if clave in politica.exceptions:
            licencias, razon, fecha = politica.exceptions[clave]
            usadas.append(
                f"{paquete.name} {paquete.version} ({paquete.ecosystem}): "
                f"{', '.join(licencias)} -- admitida por excepcion del {fecha}. {razon}"
            )
            continue

        licencias = politica.declared.get(clave) or paquete.licenses
        if not licencias:
            problemas.append(
                f"{paquete.name} {paquete.version} ({paquete.ecosystem}): {paquete.source}. "
                "Lee la licencia en su fuente y declarala en "
                "'[tool.untangle.licenses] declared' con la URL donde la leiste"
            )
            continue

        for licencia in licencias:
            if licencia not in politica.allowed:
                problemas.append(
                    f"{paquete.name} {paquete.version} ({paquete.ecosystem}): licencia "
                    f"'{licencia}' ({paquete.source}) no esta en la lista admitida. "
                    "Si se puede publicar el repositorio con ella, anadela a "
                    "'[tool.untangle.licenses] allowed' con su razon; si no, hay que "
                    "sacar el paquete"
                )

    return Informe(problems=problemas, used_exceptions=usadas, checked=total)


def _arbol(root: Path) -> Iterator[tuple[list[Paquete], list[str]]]:
    yield python_packages(root)
    yield npm_packages(root)


def run_all(root: Path | None = None) -> Informe:
    base = root if root is not None else paths.repo_root()
    politica, problemas = load_policy(base)

    paquetes: list[Paquete] = []
    for encontrados, fallos in _arbol(base):
        paquetes.extend(encontrados)
        problemas.extend(fallos)

    informe = evaluate(paquetes, politica)
    return Informe(
        problems=[*problemas, *informe.problems],
        used_exceptions=informe.used_exceptions,
        checked=informe.checked,
    )


def main() -> int:
    informe = run_all()

    for admitida in informe.used_exceptions:
        print(f"excepcion: {admitida}")

    for problema in informe.problems:
        print(problema, file=sys.stderr)

    if informe.problems:
        print(
            f"\n{len(informe.problems)} problema(s) de licencias sobre {informe.checked} "
            "paquete(s) del arbol resuelto",
            file=sys.stderr,
        )
        return 1

    print(
        f"licencias: {informe.checked} paquetes del arbol resuelto, todos con licencia "
        f"admitida ({len(informe.used_exceptions)} por excepcion escrita)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
