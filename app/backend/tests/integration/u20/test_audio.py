"""El audio no se borra porque nunca se guardo (AC5.15.2, NFR19.5).

Es la unica promesa de esta unidad que **no se cumple borrando**, y por eso hay
que comprobarla de otra manera: si el aplicativo guardara audio en algun sitio,
el reinicio nocturno tendria que ir a buscarlo, y un archivo olvidado es un
archivo esperando a que alguien lo encuentre.

Se comprueba por los dos sitios donde podria estar:

- **En la base**, preguntandole al catalogo por sus columnas binarias. La lista
  de las que hay es cerrada y esta escrita aqui con su dueno: ninguna es de la
  voz, y una columna binaria nueva hace fallar esta prueba, que es exactamente
  donde el audio se colaria sin que nadie lo decidiera.
- **En el disco**, abriendo y cerrando una llamada de verdad por sus rutas y
  comprobando que el directorio de audio no cambia. Se compara antes y despues en
  vez de exigirlo vacio: ahi deja sus archivos `mise run voice:say`, que es un
  comando a mano, y una prueba que exigiera el directorio vacio fallaria en la
  maquina de quien lo haya corrido.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI

from untangle import paths
from untangle.server import composition, demo_reset
from untangle.tenancy import session

from .conftest import aseguradora, cliente
from .test_window import _corrida, _sembrar

pytestmark = pytest.mark.usefixtures("base_de_u20", "sin_transporte")

COLUMNAS_BINARIAS = """
    SELECT table_name, column_name
    FROM information_schema.columns
    WHERE table_schema = 'public' AND data_type = 'bytea'
    ORDER BY table_name, column_name
"""

#: Las columnas binarias del esquema, con su dueno y lo que guardan. **Ninguna es
#: de la voz.** Todas llevan texto cifrado: los campos del caso, los datos de un
#: tercero, lo que cambio en una correccion y el estado serializado del grafo.
#:
#: Escrita a mano a proposito: lo que la hace valer es que una columna binaria
#: nueva --que es la forma que tendria un audio guardado-- obligue a decidirlo
#: aqui en vez de aparecer sin que nadie lo viera.
DECLARADAS = {
    ("case_change", "new_value"),
    ("case_change", "previous_value"),
    ("case_field", "value"),
    ("case_party", "contact"),
    ("case_party", "name"),
    ("case_party", "plate"),
    ("graph_checkpoint", "metadata"),
    ("graph_checkpoint", "payload"),
    ("graph_checkpoint_write", "value"),
}


async def test_ninguna_columna_binaria_del_esquema_es_de_la_voz(app: FastAPI) -> None:
    """Se le pregunta al catalogo, no a una lista de tablas escrita aqui."""
    del app
    async with session.unscoped_session() as sesion:
        filas = await session.fetch_all(sesion, COLUMNAS_BINARIAS)

    encontradas = {(str(fila["table_name"]), str(fila["column_name"])) for fila in filas}
    assert encontradas == DECLARADAS, (
        "el esquema tiene columnas binarias que nadie declaro, y una columna binaria "
        f"es donde el audio se guardaria sin que nadie lo decidiera: {encontradas ^ DECLARADAS}"
    )
    assert not any(tabla.startswith("call_") for tabla, _ in encontradas)


async def test_una_llamada_no_deja_audio_en_el_disco_ni_antes_ni_despues(
    app: FastAPI,
) -> None:
    """Una llamada de verdad, por sus rutas, y el directorio de audio igual.

    Antes y despues del reinicio: lo primero es lo que demuestra que no hay nada
    que borrar, y lo segundo que el reinicio no tiene que ir a buscarlo.
    """
    await _sembrar(_corrida(hace=timedelta(hours=1)))
    antes = _archivos_de_audio()

    async with cliente(app) as http:
        abierta = await http.post(f"/api/voice/{aseguradora()}/sessions", json={})
    assert abierta.status_code == 201, abierta.text
    durante = _archivos_de_audio()

    await demo_reset.reset_now(composition.PURGADORES, now=datetime.now(UTC))

    assert durante == antes
    assert _archivos_de_audio() == antes


def _archivos_de_audio() -> frozenset[str]:
    """Lo que hay en el directorio de audio del comando a mano, si lo hay."""
    directorio = paths.voice_output_dir()
    if not directorio.is_dir():
        return frozenset()
    return frozenset(archivo.name for archivo in directorio.iterdir())
