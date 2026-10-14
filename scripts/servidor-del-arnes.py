#!/usr/bin/env python3
"""El proceso contra el que corre el arnes de accesibilidad (`mise run a11y`, F9).

Levanta **el proceso real** --la misma raiz de composicion que sirve la demo, con
los estaticos recien compilados, la politica de contenido y las cabeceras de
verdad-- sobre una base efimera, igual que la suite de pruebas: la misma imagen
anclada por huella y el **rol del aplicativo**, nunca el superusuario.

Por que con base: sin ella la salud de "listo" responde 503 (BR5.1) y la
interfaz se quedaria en "la demo esta despertando". El arnes necesita las dos
cosas, y las dos de verdad: el inicio con el proceso listo, y la pagina de
espera, que obtiene interceptando la ruta de listo desde Playwright
(`unit-test-instructions.md`, dobles de prueba).

**No es codigo del aplicativo**: es el andamio de una prueba, por eso vive en
`scripts/` y no bajo `app/`. Sin motor de contenedores falla nombrandolo, igual
que la suite: un arnes que se salta en silencio es un arnes que no existe.

Uso (lo invoca `app/frontend/e2e/playwright.config.ts`):

    uv run --project app/backend python scripts/servidor-del-arnes.py --port 8765
"""

from __future__ import annotations

import argparse
import sys

import uvicorn

from untangle.server.composition import build_app
from untangle.settings import Settings
from untangle.tenancy import ephemeral


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, required=True)
    argumentos = parser.parse_args()

    with ephemeral.ephemeral_database() as base:
        ephemeral.upgrade_to_head(base.app_url)
        aplicacion = build_app(Settings(database_url=base.app_url))
        # Uvicorn atiende SIGTERM y SIGINT: al detenerse devuelve el control, y el
        # contexto de arriba apaga la base. Si el proceso muere de golpe, el
        # recolector de testcontainers se lleva el contenedor igual.
        uvicorn.run(aplicacion, host="127.0.0.1", port=argumentos.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
