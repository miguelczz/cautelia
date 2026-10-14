"""Lo que las pruebas de integracion de U6 necesitan en la base efimera.

La base la levanta `tests/conftest.py`, una sola para toda la corrida. Aqui solo
esta lo propio de esta unidad: dejar las dos tablas de la activacion vacias
antes y despues de cada prueba, y crear las claves de navegador con la funcion
de U2 (`unit-test-instructions.md`, Datos de prueba).

**Por que antes tambien.** Una prueba tiene que poder correr sola y en cualquier
orden, y entrar limpia es la mitad de esa promesa que se olvida mas a menudo.

**Por que se borra por aseguradora.** Las dos tablas llevan politica: sin
aseguradora fijada, un `DELETE` no ve ninguna fila y borraria exactamente cero.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from untangle.tenancy import api as tenancy
from untangle.tenancy import ephemeral, session

#: Un instante fijo para toda la suite de U6. El reloj entra por argumento: una
#: conducta que leyera el reloj del proceso solo se podria probar esperando.
AHORA = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class Sesion:
    """Una sesion de visitante tal como la ve la activacion: aseguradora y resumen."""

    tenant_id: str
    visitor_key_hash: str


async def _vaciar() -> None:
    """Las dos sentencias escritas enteras, por aseguradora.

    Sin componer el nombre de la tabla con una cadena: eso seria SQL armado por
    concatenacion, que BR1.6 prohibe.
    """
    for tenant_id in tenancy.available_ids():
        async with session.session_for(tenant_id) as sesion:
            await session.execute_sql(sesion, "DELETE FROM activation_progress")
            await session.execute_sql(sesion, "DELETE FROM activation_daily")


@pytest.fixture
async def activacion(sesiones: ephemeral.EphemeralDatabase) -> AsyncIterator[None]:
    """Las dos tablas de la activacion vacias antes y despues de cada prueba."""
    await _vaciar()
    yield
    await _vaciar()


@pytest.fixture
def dos_aseguradoras() -> tuple[str, str]:
    """Dos aseguradoras reales de la configuracion, sin escribir su nombre.

    Se toman de la configuracion cargada y no de una lista a mano: si una cuarta
    entra o una sale, la prueba sigue midiendo lo mismo.
    """
    disponibles = tenancy.available_ids()
    assert len(disponibles) >= 2, "la prueba de aislamiento necesita dos aseguradoras"
    return disponibles[0], disponibles[1]


async def nueva_sesion(tenant_id: str, *, visitor_key: str | None = None) -> Sesion:
    """Una sesion de visitante creada con la funcion de U2, no inventada.

    `visitor_key` permite usar **la misma** clave en dos aseguradoras, que es la
    colision que el aislamiento tiene que resistir.
    """
    clave = visitor_key if visitor_key is not None else tenancy.new_visitor_key()
    registro = await tenancy.resolve_visitor_key(
        tenant_id=tenant_id, visitor_key=clave, origin="public_chat", now=AHORA
    )
    return Sesion(tenant_id=tenant_id, visitor_key_hash=registro.visitor_key_hash)
