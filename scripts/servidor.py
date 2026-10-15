#!/usr/bin/env python3
"""El aplicativo servido dentro de un contenedor (intent `infra`).

**El tercer hermano**, y existe por una diferencia de una linea que importa:
`servidor-local.py` escucha en `127.0.0.1` --correcto en una maquina, inutil en un
contenedor, donde nadie de fuera llegaria-- y busca otro puerto si el suyo esta
ocupado, que en un contenedor es adivinar en vez de fallar. Aqui el puerto lo fija
el entorno y ocupado es un error: quien orquesta decide, no el proceso.

Lo demas es deliberadamente igual al hermano local: **la misma raiz de composicion**,
los mismos estaticos compilados, las mismas cabeceras. Un contenedor que sirviera
algo distinto de lo que se prueba en local no probaria nada.

**Sube las migraciones antes de servir**, por la misma razon: una base sin migrar
responde 503 en la salud de listo y la interfaz se queda en "la demo esta
despertando". Con `--skip-migrate` no las sube, para el dia que las migraciones
corran como un paso aparte del despliegue.

Ninguna clave se escribe aqui ni se imprime. Todo sale del entorno, que es lo unico
que un contenedor recibe.

    UNTANGLE_DATABASE_URL          obligatoria
    UNTANGLE_CASE_FIELD_ENCRYPTION_KEY  obligatoria
    PORT                           por omision 8080, que es lo que esperan
                                   Cloud Run, Render y la mayoria
"""

from __future__ import annotations

import argparse
import os
import sys

import uvicorn

from untangle.server.composition import build_app
from untangle.settings import Settings
from untangle.tenancy import ephemeral

#: El puerto por omision. 8080 y no 8050 --el del hermano local-- porque es el que
#: las plataformas de contenedores inyectan y esperan.
PUERTO_POR_OMISION = 8080


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-migrate",
        action="store_true",
        help="No subir las migraciones al arrancar (cuando corren como paso aparte)",
    )
    argumentos = parser.parse_args()

    settings = Settings()
    if not settings.database_url:
        print(
            "falta UNTANGLE_DATABASE_URL: el proceso no sirve sin base. Una base sin\n"
            "configurar deja la interfaz en 'la demo esta despertando' para siempre,\n"
            "que es peor que no arrancar, porque parece que arranco.",
            file=sys.stderr,
        )
        return 1

    if not argumentos.skip_migrate:
        try:
            ephemeral.upgrade_to_head(settings.database_url)
        except ephemeral.DatabaseAheadError as error:
            # Una vuelta atras (2026-10-15): la base la subio una version mas nueva. Las
            # migraciones son aditivas (docs/reference/operacion-de-produccion.md), asi que
            # este codigo funciona con ella; no arrancar dejaria el sitio en error.
            print(f"aviso: {error}; se arranca sin subir migraciones", file=sys.stderr)

    puerto = int(os.environ.get("PORT", PUERTO_POR_OMISION))
    # `0.0.0.0` y no `127.0.0.1`: dentro de un contenedor, escuchar solo en la
    # interfaz de loopback es no escuchar para nadie.
    uvicorn.run(build_app(settings), host="0.0.0.0", port=puerto, log_level="info")  # noqa: S104
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
