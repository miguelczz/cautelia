"""Lo que comparten las pruebas de integracion de todas las unidades.

Hoy una sola cosa, y es una que ninguna unidad puede dar por supuesta: **la
demostracion acepta casos nuevos**. Pasadas 24 horas sin un reinicio nocturno
exitoso, el chat y la voz publicos dejan de aceptarlos (BR3.2 de U20), asi que
una prueba que monta la aplicacion y no dice nada corre contra una demo
**cerrada**: sobre una base recien creada no hay ninguna corrida y la ventana, que
falla cerrado a proposito, no puede afirmar que lo que entre se borre esa noche.

La demo de todos los dias es la que se reinicio anoche, y eso hay que decirlo en
vez de heredarlo. Por eso esta fixture no es `autouse`: la pide quien la necesita,
y asi queda escrito en cada carpeta que su prueba corre con la demo abierta.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from untangle.tenancy import ephemeral, session

SEMBRAR_CORRIDA = """
    INSERT INTO reset_run (reset_run_id, started_at, finished_at, outcome)
    VALUES (:reset_run_id, :empezo, :termino, 'succeeded')
"""

#: Una fila por purgador es obligatoria --una corrida sin ellas diria que corrio
#: sin decir que hizo-- y con una basta para que la consulta la encuentre.
SEMBRAR_FILA = """
    INSERT INTO reset_run_purger (
        reset_run_id, purger, call_order, deleted, kept, duration_ms, error_type
    )
    VALUES (:reset_run_id, 'sembrado-por-la-prueba', 0, 0, 0, 1, NULL)
"""

BORRAR = "DELETE FROM reset_run WHERE reset_run_id = :reset_run_id"

ID_DE_LA_CORRIDA = "reset-sembrado-por-la-prueba"


@pytest.fixture
async def demo_abierta(sesiones: ephemeral.EphemeralDatabase) -> AsyncIterator[None]:
    """Un reinicio nocturno exitoso de hace una hora, como el de cualquier dia.

    De hace una hora y no de hace un instante: el instante exacto no cambia nada
    --la ventana es de 24 horas-- y una hora deja ver en el dato que la corrida es
    de antes de la prueba y no parte de ella.
    """
    del sesiones
    ahora = datetime.now(UTC)
    async with session.unscoped_session() as sesion:
        await session.execute_sql(
            sesion,
            SEMBRAR_CORRIDA,
            reset_run_id=ID_DE_LA_CORRIDA,
            empezo=ahora - timedelta(hours=1),
            termino=ahora - timedelta(hours=1),
        )
        await session.execute_sql(sesion, SEMBRAR_FILA, reset_run_id=ID_DE_LA_CORRIDA)
    yield
    async with session.unscoped_session() as sesion:
        await session.execute_sql(sesion, BORRAR, reset_run_id=ID_DE_LA_CORRIDA)
