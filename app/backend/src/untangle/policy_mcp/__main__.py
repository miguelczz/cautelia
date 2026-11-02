"""El proceso del servidor MCP: `mise run mcp` (transporte stdio).

    mise run mcp

Es la raiz de composicion de este proceso: carga las aseguradoras y el catalogo, abre el punto
unico de sesion contra `UNTANGLE_DATABASE_URL` y sirve las herramientas por la entrada y la salida
estandar. Necesita la base local con los datos de ejemplo sembrados (`mise run services:up` y
`mise run synthetic:seed`); sin ella el servidor no arranca y lo dice por la salida de errores.

**La salida estandar es el protocolo.** Un cliente MCP lee de ahi mensajes JSON-RPC, asi que nada mas
puede escribir en ella: los eventos tecnicos del aplicativo (`observability.emit`) se redirigen a la
salida de errores antes de cualquier otra cosa, y los avisos propios de este modulo tambien.
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

from mcp.server.mcpserver import MCPServer

from untangle import observability
from untangle.copy_catalog import api as copy_api
from untangle.policy_mcp.server import build_server
from untangle.settings import Settings
from untangle.tenancy import api as tenancy


@asynccontextmanager
async def _ciclo_de_vida(_servidor: MCPServer) -> AsyncIterator[None]:
    """Cierra el grupo de conexiones cuando el cliente se va."""
    try:
        yield
    finally:
        await tenancy.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    del argv  # no tiene opciones: el transporte es stdio y la base sale del entorno
    observability.set_stream(sys.stderr)
    opciones = Settings()
    if not opciones.database_url:
        print(
            "mcp: falta UNTANGLE_DATABASE_URL. Levante la base local con `mise run services:up` "
            "y siembre los datos de ejemplo con `mise run synthetic:seed`.",
            file=sys.stderr,
        )
        return 1
    copy_api.install(copy_api.load())
    tenancy.install(tenancy.load())
    tenancy.configure(opciones.database_url)
    build_server(lifespan=_ciclo_de_vida).run("stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
