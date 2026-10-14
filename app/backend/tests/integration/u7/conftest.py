"""Sembrar dentro de la transaccion de la prueba, y revertirla al terminar (BR6.4).

**Cada prueba abre una conexion y una transaccion**, y el punto unico de sesion de
U2 queda atado a esa conexion mientras dura: cada `session_for` que abre la API de
U4 es un *savepoint* dentro de ella, y al terminar la prueba todo se revierte. Asi
dos pruebas que parten del mismo caso sembrado no se ven --ninguna confirma nada--
y ninguna deja filas para la siguiente.

La atadura **no cambia el codigo del punto unico**: sustituye, solo en estas
pruebas, de donde saca la conexion y como abre la sesion. La politica de fila, la
variable de aseguradora y el rol del aplicativo son los de siempre, y la base es
la efimera de la suite, con el rol del aplicativo y nunca el superusuario.

**Falla en alto si se abre una sesion fuera de la transaccion de una prueba.**
Volver a la conexion normal escribiria en la base sin revertir, y la siguiente
prueba veria filas que no son suyas: exactamente lo que esta fixture existe para
impedir.
"""

from __future__ import annotations

import functools
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine

from untangle import paths
from untangle.case_record import crypto
from untangle.server import synthetic_seed
from untangle.synthetic_data.cases import load_seeded_cases
from untangle.synthetic_data.models import SeededCaseRecord
from untangle.tenancy import ephemeral, session

#: El momento de la siembra en las pruebas: fijo, para que nada dependa del reloj.
AHORA = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)

_CONEXION: ContextVar[AsyncConnection | None] = ContextVar("conexion_de_la_prueba", default=None)


class SesionFueraDeLaTransaccionError(RuntimeError):
    """Una prueba de la siembra abrio sesion sin una transaccion de prueba abierta."""


def _conexion_de_la_prueba() -> AsyncConnection:
    conexion = _CONEXION.get()
    if conexion is None:
        msg = (
            "se abrio una sesion fuera de la transaccion de la prueba: escribiria en la "
            "base sin revertir. Abra `transaccion_de_prueba` antes de sembrar"
        )
        raise SesionFueraDeLaTransaccionError(msg)
    return conexion


@pytest.fixture
async def punto_unico_atado(
    base_efimera: ephemeral.EphemeralDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[str]:
    """Ata el punto unico de sesion a la transaccion de la prueba en curso.

    Al salir lo suelta: la siguiente prueba de la suite no hereda ni la direccion
    ni la atadura.
    """
    session.configure(base_efimera.app_url)
    monkeypatch.setattr(session, "_require_engine", _conexion_de_la_prueba)
    monkeypatch.setattr(
        session,
        "AsyncSession",
        functools.partial(AsyncSession, join_transaction_mode="create_savepoint"),
    )
    try:
        yield base_efimera.app_url
    finally:
        await session.dispose()


@asynccontextmanager
async def transaccion_de_prueba(url: str) -> AsyncIterator[AsyncConnection]:
    """Una conexion con su transaccion abierta, revertida siempre al salir."""
    motor = create_async_engine(url)
    try:
        async with motor.connect() as conexion:
            transaccion = await conexion.begin()
            marca = _CONEXION.set(conexion)
            try:
                yield conexion
            finally:
                _CONEXION.reset(marca)
                await transaccion.rollback()
    finally:
        await motor.dispose()


@pytest.fixture
def cifrador(monkeypatch: pytest.MonkeyPatch) -> crypto.Cipher:
    monkeypatch.setenv(crypto.KEY_ENV_VAR, crypto.generate_key())
    return crypto.Cipher.from_settings()


@pytest.fixture(scope="session")
def casos_sembrados() -> dict[str, SeededCaseRecord]:
    """Los casos que la generacion dejo escritos, por su clave."""
    return {caso.case_key: caso for caso in load_seeded_cases(paths.data_dir())}


type Sembrar = Callable[[str], Awaitable[synthetic_seed.SeedOutcome]]


@pytest.fixture
async def sembrar(
    punto_unico_atado: str,
    cifrador: crypto.Cipher,
    casos_sembrados: dict[str, SeededCaseRecord],
) -> AsyncIterator[Sembrar]:
    """Siembra un caso por su clave **dentro** de la transaccion de esta prueba.

    La transaccion se abre antes de la prueba y se revierte al terminar, pase lo
    que pase en ella (BR6.4).
    """
    async with transaccion_de_prueba(punto_unico_atado):

        async def _sembrar(case_key: str) -> synthetic_seed.SeedOutcome:
            return await synthetic_seed.seed_case(
                casos_sembrados[case_key], cipher=cifrador, now=AHORA
            )

        yield _sembrar
