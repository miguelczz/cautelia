"""Lo que las pruebas de U5 necesitan en la base efimera: la ventana y nada mas.

La base la levanta `tests/conftest.py`, una sola para toda la corrida. Aqui solo
esta lo propio de esta unidad: sembrar la ventana de presupuesto y dejar las
cuatro tablas del dinero vacias al terminar.

**Por que la limpieza vive aqui y no en la fixture de la raiz.** Aquella recorre
las aseguradoras y borra por sesion con aseguradora fijada, porque todo lo que
limpia lleva politica. Las cuatro tablas del dinero no llevan ninguna (BR7.1):
un borrado por aseguradora sobre ellas correria tres veces y borraria lo mismo
las tres, que funciona por accidente y se lee como si aislara algo.

**Ninguna de estas pruebas gasta un centavo.** El acumulado se **fuerza** en la
fila de la ventana, nunca se alcanza gastando de verdad: una suite que consumiera
el presupuesto dejaria al proyecto sin voz para demostrarlo, que es precisamente
lo que el techo existe para evitar (BR5.9, regla del proyecto).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from untangle.telemetry.spend.models import WINDOW_DAYS, WINDOW_START
from untangle.tenancy import ephemeral, session

#: Un instante fijo para toda la suite. El reloj entra por argumento en cada
#: llamada: una conducta que leyera el reloj del proceso solo se podria probar
#: esperando a que pase el dia (BR5.2).
AHORA = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)

VENTANA_FIN = WINDOW_START + timedelta(days=WINDOW_DAYS)

TABLAS_DEL_DINERO = ("spend_entry", "quota_counter", "budget_window", "voice_call_release")

SEMBRAR_VENTANA = """
    INSERT INTO budget_window (
        window_start, window_end, billable_spent_usd, cap_usd, alert_usd,
        alert_sent_at, recording_reserve_usd, recording_reserve_status,
        recording_spent_usd, unmeasured_billable_calls, unmeasured_recording_calls,
        updated_at
    ) VALUES (
        :inicio, :fin, :gastado, :techo, :alerta,
        :avisada, :reserva, :estado_reserva, :gastado_en_grabacion, :sin_valorar,
        :sin_valorar_en_grabacion, :ahora
    )
"""


async def sembrar_ventana(  # noqa: PLR0913 -- son las columnas de la fila, no una eleccion
    *,
    gastado: Decimal = Decimal(0),
    techo: Decimal = Decimal("5.00"),
    alerta: Decimal = Decimal("3.00"),
    reserva: Decimal | None = Decimal("0.225"),
    avisada: datetime | None = None,
    gastado_en_grabacion: Decimal = Decimal(0),
    sin_valorar: int = 0,
    sin_valorar_en_grabacion: int = 0,
) -> None:
    """La fila unica de la ventana, con el acumulado que pida la prueba.

    El acumulado se escribe directo a proposito: llegar a el gastando seria
    gastar el presupuesto que la prueba protege.

    `gastado_en_grabacion` es la parte del acumulado que salio del carril de
    grabacion, y esta aqui porque los dos carriles corren aparte (BR4.9, BR4.10):
    sin poder gastar uno sin el otro, no hay forma de sembrar el estado en el que
    los dos restantes discrepan, que es justo donde se ve cual de los dos lee
    cada carril.

    `sin_valorar` son las llamadas facturables que no se pudieron valorar. Se
    siembra igual que el acumulado y por la misma razon: provocarla de verdad
    exige una llamada a un proveedor sin precio de lista, y eso cuesta dinero.

    `sin_valorar_en_grabacion` es la parte de ese conteo que salio del carril de
    grabacion, y esta aqui por lo mismo que `gastado_en_grabacion`: sin poder
    sembrar uno sin el otro no hay forma de llegar al estado en el que los dos
    restantes discrepan, que es justo donde se ve que cada carril lee el suyo.
    Nunca puede ser mayor que `sin_valorar`: las de grabacion son un subconjunto
    de las facturables, y la base lo comprueba.
    """
    async with session.unscoped_session() as sesion:
        await session.execute_sql(
            sesion,
            SEMBRAR_VENTANA,
            inicio=WINDOW_START,
            fin=VENTANA_FIN,
            gastado=gastado,
            techo=techo,
            alerta=alerta,
            avisada=avisada,
            reserva=reserva,
            estado_reserva="measured" if reserva is not None else "not_measured",
            gastado_en_grabacion=gastado_en_grabacion,
            sin_valorar=sin_valorar,
            sin_valorar_en_grabacion=sin_valorar_en_grabacion,
            ahora=AHORA,
        )


@pytest.fixture
async def dinero(sesiones: ephemeral.EphemeralDatabase) -> AsyncIterator[None]:
    """Deja las cuatro tablas del dinero vacias antes y despues de cada prueba.

    Antes tambien, y no solo despues: una prueba tiene que poder correr sola y en
    cualquier orden, y entrar limpia es la mitad de esa promesa que se olvida
    mas a menudo.
    """
    await _vaciar()
    yield
    await _vaciar()


async def _vaciar() -> None:
    """Las cuatro sentencias escritas enteras, sin componer el nombre de la tabla.

    Componerlo con una cadena de Python seria SQL construido por concatenacion
    --lo que BR1.6 prohibe-- y obligaria a silenciar el hallazgo del linter. Se
    quita la forma que lo produce en vez de suprimirlo.
    """
    async with session.unscoped_session() as sesion:
        await session.execute_sql(sesion, "DELETE FROM spend_entry")
        await session.execute_sql(sesion, "DELETE FROM quota_counter")
        await session.execute_sql(sesion, "DELETE FROM budget_window")
        await session.execute_sql(sesion, "DELETE FROM voice_call_release")
