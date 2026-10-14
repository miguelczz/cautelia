#!/usr/bin/env python3
"""El aplicativo corriendo contra la base local, para usarlo a mano (`mise run dev`).

Es **el proceso real** --la misma raiz de composicion que sirve la demo, con los
estaticos compilados, la politica de contenido y las cabeceras de verdad-- contra la
base del proyecto, la que levanta `mise run services:up`, y no contra una efimera:
lo que se quiere aqui es que los casos sembrados sigan ahi al recargar.

Es el hermano de `servidor-del-arnes.py`, que hace lo mismo sobre una base efimera
porque el arnes necesita una base virgen en cada corrida. Los dos son andamio y no
codigo del aplicativo, y por eso viven en `scripts/`.

**Sube las migraciones antes de servir.** Una base sin migrar responde 503 en la
salud de listo y la interfaz se queda en "la demo esta despertando", que es correcto y
no ayuda a nadie que solo queria mirar la bandeja.

Lee `UNTANGLE_DATABASE_URL` y `UNTANGLE_CASE_FIELD_ENCRYPTION_KEY` del entorno, que
es lo que `uv --env-file .env` le pasa. **Ninguna clave se escribe aqui ni se imprime.**

Uso (lo invoca `mise run dev`):

    uv run --env-file .env --project app/backend python scripts/servidor-local.py
"""

from __future__ import annotations

import argparse
import socket
import sys

import uvicorn

from untangle.server.composition import build_app
from untangle.settings import Settings
from untangle.tenancy import ephemeral

#: El puerto de la demo local. **No es 8000 a proposito**, aunque sea el que todo el
#: mundo espera: en esta maquina lo tiene otro proyecto --junto con el 8001, el 8002,
#: el 8003 y el 8080-- y con el 8000 por omision el servidor subia buscando uno libre
#: y aterrizaba cada vez en uno distinto. Lo que eso cuesta es concreto: hay que mirar
#: la salida para saber a que direccion ir, y la prueba de humo necesita que se le
#: diga el puerto de hoy en vez de tener uno por omision que sirva.
#:
#: **Lo que NO arregla, y se penso que si:** la conversacion del visitante no se
#: pierde al cambiar de puerto. Las galletas **no se aislan por puerto** (RFC 6265: el
#: puerto no forma parte de su alcance), asi que dos servidores en 8005 y 8050 se
#: reparten la misma galleta y la misma conversacion. Se comprobo: al mover la demo de
#: 8005 a 8050, el navegador siguio en su caso de antes sin abrir uno nuevo.
#:
#: La busqueda de un puerto libre sigue ahi como red: si tambien este se ocupa, se
#: toma el siguiente y se dice cual, en vez de no arrancar.
PUERTO_POR_OMISION = 8050


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--port",
        type=int,
        default=PUERTO_POR_OMISION,
        help=(
            f"El puerto. Por omision {PUERTO_POR_OMISION}; si esta ocupado se toma uno "
            "libre y se dice cual. Con --port explicito, ocupado es un error."
        ),
    )
    parser.add_argument(
        "--skip-migrate",
        action="store_true",
        help="No subir las migraciones (para cuando ya se subieron)",
    )
    parser.add_argument(
        "--migrate-only",
        action="store_true",
        help="Subir las migraciones y salir, sin servir (lo usa `mise run migrate`)",
    )
    argumentos = parser.parse_args()

    settings = Settings()
    if not settings.database_url:
        print(
            "falta UNTANGLE_DATABASE_URL: levanta la base con `mise run services:up` "
            "y declarala en `.env` (la plantilla es `.env.example`)",
            file=sys.stderr,
        )
        return 1

    if not argumentos.skip_migrate:
        ephemeral.upgrade_to_head(settings.database_url)
    if argumentos.migrate_only:
        return 0

    puerto = _puerto_libre(argumentos.port, pedido_a_mano="--port" in sys.argv)
    if puerto is None:
        print(
            f"el puerto {argumentos.port} esta ocupado. Mira quien lo tiene con\n\n"
            f"    lsof -nP -iTCP:{argumentos.port} -sTCP:LISTEN\n\n"
            "o pide otro con `mise run dev -- --port <otro>`. No se detiene nada por ti:\n"
            "lo que esta en ese puerto puede ser algo que estas usando.",
            file=sys.stderr,
        )
        return 1

    print(f"el aplicativo escucha en http://127.0.0.1:{puerto}", file=sys.stderr)
    uvicorn.run(build_app(settings), host="127.0.0.1", port=puerto, log_level="info")
    return 0


def _esta_libre(puerto: int) -> bool:
    """Si nadie escucha en ese puerto. Se pregunta al sistema, no se adivina."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as prueba:
        prueba.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            prueba.bind(("127.0.0.1", puerto))
        except OSError:
            return False
        return True


def _puerto_libre(pedido: int, *, pedido_a_mano: bool) -> int | None:
    """El puerto pedido, o el primero libre si el de omision esta ocupado.

    **Solo se busca otro cuando el puerto vino por omision.** Quien escribe `--port`
    quiere ese y no otro: servirle uno distinto en silencio deja la pantalla abierta en
    una direccion que no responde, y eso se busca durante un rato antes de mirar aqui.
    Con el de omision, en cambio, lo que se quiere es ver la demo, y el de omision ya se
    eligio para no chocar (ver `PUERTO_POR_OMISION`); esto es la red por si aun asi
    choca.

    Es lo mismo que hace el arnes de accesibilidad, y por el mismo motivo: chocar con un
    puerto fijo ya habia puesto `verify.sh` en rojo sin que nada del producto cambiara.
    """
    if _esta_libre(pedido):
        return pedido
    if pedido_a_mano:
        return None
    for siguiente in range(pedido + 1, pedido + 21):
        if _esta_libre(siguiente):
            return siguiente
    return None


if __name__ == "__main__":
    sys.exit(main())
