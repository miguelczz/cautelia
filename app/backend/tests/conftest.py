"""La base efimera que comparten las pruebas que necesitan PostgreSQL de verdad.

Vive aqui, en la raiz de las pruebas, porque la piden dos arboles: las de
integracion de U2 y las unitarias del modulo de aislamiento. **Una sola base por
corrida de la suite**, creada cuando la primera prueba la pide y destruida al
terminar; `migrate:check` levanta la suya aparte porque necesita una base virgen
para subir, bajar y volver a subir.

Dos decisiones que se pagan si no se toman:

1. **La conexion usa el rol del aplicativo, nunca el superusuario.** Un
   superusuario se salta las politicas de fila, y entonces toda la suite de
   aislamiento pasaria sin que exista aislamiento: el fallo que no avisa
   (BR1.7, C-10).
2. **Sin motor de contenedores la suite falla; no se salta.** Saltarla dejaria la
   compuerta de aislamiento en verde sin haberla ejecutado, y una compuerta que
   no se ejecuta es una compuerta que no existe.

La base no se simula: lo que se prueba es una conducta del motor --las politicas
de fila-- que un doble no tiene.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest

from untangle.tenancy import config, ephemeral, session

#: Las tres variables de Langfuse. Ninguna prueba las hereda del entorno de quien la corre.
_VARIABLES_DE_LANGFUSE = (
    "UNTANGLE_LANGFUSE_PUBLIC_KEY",
    "UNTANGLE_LANGFUSE_SECRET_KEY",
    "UNTANGLE_LANGFUSE_HOST",
)


@pytest.fixture(autouse=True)
def _sin_langfuse_del_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    """Una prueba que arma la aplicacion con `Settings()` no puede mandar trazas a Langfuse.

    Con las tres variables en el entorno de quien desarrolla, `build_app` instalaria el
    transporte de verdad y la suite gastaria el cupo del plan gratuito (y mandaria trazas de
    prueba al proyecto local). Las pruebas que quieren Langfuse lo piden por argumento, con
    un transporte falso.
    """
    for nombre in _VARIABLES_DE_LANGFUSE:
        monkeypatch.delenv(nombre, raising=False)


@pytest.fixture(scope="session")
def base_efimera() -> Iterator[ephemeral.EphemeralDatabase]:
    """Una sola base efimera para toda la corrida, ya migrada hasta la cabeza."""
    with ephemeral.ephemeral_database() as base:
        ephemeral.upgrade_to_head(base.app_url)
        yield base


@pytest.fixture
async def sesiones(
    base_efimera: ephemeral.EphemeralDatabase,
) -> AsyncIterator[ephemeral.EphemeralDatabase]:
    """Apunta el punto unico de sesion a la base efimera y lo suelta al salir.

    Deja las tablas vacias al terminar. No es cortesia: cada prueba tiene que
    poder correr sola y en cualquier orden, y una fila que sobrevive a su prueba
    es la forma mas comun de que eso deje de ser cierto.
    """
    session.configure(base_efimera.app_url)
    try:
        yield base_efimera
        # Se vuelve a apuntar antes de limpiar: hay pruebas que ejercitan
        # comandos que cierran el motor al terminar --es lo correcto en un
        # proceso suelto-- y sin esto la limpieza fallaria por su culpa.
        session.configure(base_efimera.app_url)
        for tenant_id in config.available_ids():
            async with session.session_for(tenant_id) as sesion:
                await session.execute_sql(sesion, "DELETE FROM case_access_link")
                await session.execute_sql(sesion, "DELETE FROM visitor_key")
                # Basta con el caso: sus campos, partes, turnos e historial se
                # van con el por la cascada que la revision de U4 dejo escrita.
                await session.execute_sql(sesion, "DELETE FROM case_record")
    finally:
        await session.dispose()
