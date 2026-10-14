"""Genera `app/contracts/openapi.json` desde la aplicacion misma (C-28, TECH-U6.2).

El esquema **sale de las rutas que existen**, no se escribe a mano: si una ruta
cambia y el esquema no se regenera en el mismo commit, el chequeo de deriva falla
nombrando el archivo. De este esquema sale el cliente de TypeScript de la
interfaz, que es la unica via por la que la interfaz habla con el servidor
(BR3.1).

**Por que vive en `server/` y no junto a los demas contratos generados.** Para
leer las rutas hay que construir la aplicacion, y eso es la raiz de composicion,
que esta en la capa de arriba del contrato de capas; `untangle.workspace`, donde
vive el generador de los JSON Schema, esta debajo y no puede importarla. El
archivo de tareas los corre uno detras de otro en `mise run contracts:gen`.

Construir la aplicacion **no la arranca**: no se conecta a la base, no llama a
ningun proveedor y no necesita ninguna clave. El esquema no depende del entorno:
la unica clave que se le pone es una marca, para que el panel de gasto --que no
se monta sin ella-- aparezca descrito.

## Los ejemplos de respuesta real

### El directorio del sitio (U6)

Junto al esquema se escribe `app/contracts/examples/site-directory.json`: la
respuesta de `GET /api/site` con la configuracion versionada de las
aseguradoras y las superficies que monta la raiz de composicion, **sin enlaces**
(los enlaces dependen del entorno, y un ejemplo que cambia segun la maquina no se
puede comparar). Las pruebas del inicio la usan en vez de filas escritas a mano,
que es lo que exige `unit-test-instructions.md`: si una aseguradora cambia, el
ejemplo cambia en el mismo commit y la comprobacion de deriva lo vigila.

### El panel de cifras sin linea base (U22)

`app/contracts/examples/metrics-snapshot.json` es la respuesta de `GET
/api/metrics` cuando todavia no hay ninguna linea base publicada. Las pruebas de
la pantalla lo usan para el estado "sin medir" en vez de una respuesta escrita a
mano, y una prueba del servidor exige que la ruta responda exactamente eso.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import FastAPI

from untangle import paths
from untangle.server import composition, evidence_routes, site
from untangle.settings import Settings
from untangle.tenancy import api as tenancy


def build_schema_app() -> FastAPI:
    """La aplicacion con todos sus modulos montados, sea cual sea el entorno."""
    return composition.build_app(Settings())


def render(app: FastAPI | None = None) -> str:
    """El esquema de la API, serializado de forma estable."""
    esquema = (app if app is not None else build_schema_app()).openapi()
    return json.dumps(esquema, indent=2, ensure_ascii=False) + "\n"


def render_site_example(app: FastAPI | None = None) -> str:
    """La respuesta de `GET /api/site` con la configuracion versionada, sin enlaces."""
    aplicacion = app if app is not None else build_schema_app()
    directorio = site.build_directory(
        tenancy.loaded().available,
        aplicacion.state.surfaces,
        site.SiteLinks(),
    )
    cuerpo = directorio.model_dump(mode="json", exclude_none=True)
    return json.dumps(cuerpo, indent=2, ensure_ascii=False) + "\n"


def render_metrics_example() -> str:
    """La respuesta de `GET /api/metrics` sin linea base publicada (U22).

    Es el estado con el que nace el panel, y no depende de ningun archivo del
    arbol: un ejemplo que cambiara cuando se publica la primera linea base se
    confundiria con deriva.
    """
    cuerpo = evidence_routes.empty_example().model_dump(mode="json")
    return json.dumps(cuerpo, indent=2, ensure_ascii=False) + "\n"


def _write_if_changed(archivo: Path, contenido: str) -> bool:
    anterior = archivo.read_text(encoding="utf-8") if archivo.is_file() else None
    if anterior == contenido:
        return False
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(contenido, encoding="utf-8")
    return True


def write(destino: Path | None = None, ejemplo: Path | None = None) -> list[Path]:
    """Escribe el esquema y el ejemplo del sitio si cambiaron; devuelve los cambiados."""
    aplicacion = build_schema_app()
    cambiados: list[Path] = []
    salidas = (
        (paths.metrics_example_path(), render_metrics_example()),
        (destino if destino is not None else paths.openapi_path(), render(aplicacion)),
        (
            ejemplo if ejemplo is not None else paths.site_example_path(),
            render_site_example(aplicacion),
        ),
    )
    for archivo, contenido in salidas:
        if _write_if_changed(archivo, contenido):
            cambiados.append(archivo)
    return cambiados


def main() -> int:
    cambiados = write()
    for archivo in cambiados:
        print(f"regenerado: {archivo}")
    if not cambiados:
        print("sin cambios: el esquema OpenAPI y el ejemplo del sitio ya estaban al dia")
    return 0


if __name__ == "__main__":
    sys.exit(main())
