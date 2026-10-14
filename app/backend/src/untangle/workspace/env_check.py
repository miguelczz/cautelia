"""Compara `.env.example` con las variables que se leen de verdad (SEC-U1.2).

**En las dos direcciones**, y esa es toda la gracia:

- una variable que el codigo exige y la plantilla no lista es un fallo, porque
  quien clona no tiene forma de saber que hace falta;
- una variable listada que nadie lee tambien lo es, porque una plantilla que
  acumula nombres muertos deja de ser una guia y pasa a ser folklore.

Es la misma comprobacion que hace el catalogo con sus claves sin consumidor.

Las variables salen de dos sitios y de ningun otro: el objeto de configuracion
--el unico punto que lee el entorno-- y `docker-compose.yml`, que las lee el
motor de contenedores y no Python.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from untangle import paths
from untangle.settings import variable_names

NOMBRE_EN_PLANTILLA = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]*)=", re.MULTILINE)
NOMBRE_EN_COMPOSE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)")


def template_names(root: Path) -> set[str]:
    archivo = root / ".env.example"
    if not archivo.is_file():
        msg = f"falta la plantilla de variables: se esperaba '{archivo}'"
        raise FileNotFoundError(msg)
    return set(NOMBRE_EN_PLANTILLA.findall(archivo.read_text(encoding="utf-8")))


def compose_names(root: Path) -> set[str]:
    archivo = root / "docker-compose.yml"
    if not archivo.is_file():
        return set()
    return set(NOMBRE_EN_COMPOSE.findall(archivo.read_text(encoding="utf-8")))


def run_all(root: Path | None = None) -> list[str]:
    base = root if root is not None else paths.repo_root()

    plantilla = template_names(base)
    leidas = set(variable_names()) | compose_names(base)

    problemas: list[str] = []
    for nombre in sorted(leidas - plantilla):
        problemas.append(
            f"{nombre}: el codigo o los servicios la leen y '.env.example' no la lista"
        )
    for nombre in sorted(plantilla - leidas):
        problemas.append(f"{nombre}: '.env.example' la lista y nadie la lee")
    return problemas


def main() -> int:
    problemas = run_all()
    for problema in problemas:
        print(problema, file=sys.stderr)
    if problemas:
        print(
            f"\n{len(problemas)} desajuste(s) entre '.env.example' y lo que se lee",
            file=sys.stderr,
        )
        return 1
    print("variables de entorno: la plantilla y el codigo coinciden")
    return 0


if __name__ == "__main__":
    sys.exit(main())
