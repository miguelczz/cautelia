"""El punto unico de sesion de base de datos (C-10, BR1.1 a BR1.7).

**La unica via de acceso a la base.** Resuelve la aseguradora, abre la
transaccion, fija la variable de sesion dentro de esa misma transaccion y la
cierra. Ningun otro modulo construye un motor ni abre una conexion, y un
contrato de importacion lo comprueba: no es una convencion que alguien pueda
olvidar (SEC-U2.2).

Es ademas el **unico modulo de `tenancy` que importa el cliente de base de datos
y el mapeador**. Las demas piezas reciben su sesion y ejecutan por los ayudantes
de aqui, con los parametros ligados; asi "todo lo que toca la base pasa por la
sesion" es una regla de herramienta y no una frase de un documento.

Dos cosas que este modulo hace y que se notan solo cuando faltan:

1. **Resuelve la aseguradora antes de conectar.** Una que no existe falla en el
   acto nombrandola, sin abrir transaccion. Devolver una sesion sin aseguradora
   convertiria un error del codigo en "no hay datos" (BR1.5).
2. **La variable de sesion es local a la transaccion.** Al cerrar, se va con
   ella; no queda pegada a una conexion que despues reutilice otra aseguradora.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any

from sqlalchemy import CursorResult, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from untangle import observability
from untangle.tenancy import config
from untangle.tenancy.models import SessionNotConfiguredError, TenantId

#: El choque de una restriccion unica, con nombre propio de esta capa.
#:
#: **Existe para que nadie mas tenga que importar el cliente de base.** El contrato
#: `Ningun modulo abre una conexion fuera del punto unico de sesion` prohibe a todo lo
#: demas importar `sqlalchemy`, y con razon: el dia que cambie el cliente, lo que hoy
#: seria un `except` suelto en media docena de modulos se convierte en media docena de
#: sitios que arreglar. Quien necesite distinguir "esta fila ya existe" de cualquier
#: otro fallo lo cacha por este nombre.
#:
#: Es un alias y no una excepcion nueva envuelta a proposito: envolver obligaria a
#: este punto a atrapar y relanzar en cada sentencia, y eso si es una segunda puerta.
UniqueViolation = IntegrityError

#: El nombre de la variable de sesion que leen las politicas de cada tabla.
#: Vive escrito una sola vez: si cada migracion lo escribiera por su cuenta, un
#: error de tecleo daria una politica que no ve nada y una tabla vacia sin causa
#: visible.
TENANT_SETTING = "app.tenant_id"

#: Como se lee la variable desde una politica. `true` hace que una variable
#: ausente devuelva vacio en vez de lanzar, y `NULLIF` convierte ese vacio en
#: `NULL`, que no es igual a ningun `tenant_id`: sin aseguradora fijada, las
#: politicas no ven **nada**. Falla cerrado, nunca abierto (BR1.4).
TENANT_SETTING_SQL = f"NULLIF(current_setting('{TENANT_SETTING}', true), '')"

#: La sesion tipada que reciben las demas piezas. El alias existe para que
#: ninguna de ellas tenga que importar el mapeador solo para anotar un parametro.
type TenantSession = AsyncSession

_engine: AsyncEngine | None = None
_database_url: str | None = None
_current_tenant: ContextVar[TenantId | None] = ContextVar("untangle_current_tenant", default=None)


def configure(database_url: str) -> None:
    """Dice a que base conectarse. No conecta: el motor se crea al primer uso.

    La llaman la raiz de composicion, con la variable de entorno, y las pruebas,
    con su base efimera. Es el unico sitio donde entra una direccion de base.
    """
    global _engine, _database_url
    if _database_url == database_url and _engine is not None:
        return
    _engine = None
    _database_url = database_url


async def dispose() -> None:
    """Cierra el motor y olvida la direccion. Al apagar el proceso y entre pruebas."""
    global _engine, _database_url
    motor, _engine, _database_url = _engine, None, None
    if motor is not None:
        await motor.dispose()


def is_configured() -> bool:
    return _database_url is not None


def configured_url() -> str | None:
    """A que base apunta ahora, o nada si no se ha configurado.

    Existe para quien tiene que **devolver las cosas como estaban**: una tarea que
    apunta el proceso a otra base un rato y luego se lo devuelve a su dueno. No
    abre ninguna conexion ni es una segunda via para conseguir uno: el unico modo
    de hablar con la base sigue siendo `session_for`.
    """
    return _database_url


def _require_engine() -> AsyncEngine:
    global _engine
    if _database_url is None:
        msg = (
            "el punto unico de sesion no sabe a que base conectarse: llame a "
            "`configure(url)` al arrancar (la raiz de composicion lo hace con "
            "UNTANGLE_DATABASE_URL)"
        )
        raise SessionNotConfiguredError(msg)
    if _engine is None:
        _engine = create_async_engine(_database_url, pool_pre_ping=True)
    return _engine


@asynccontextmanager
async def session_for(tenant_id: TenantId) -> AsyncIterator[TenantSession]:
    """La unica via de acceso a la base, con la aseguradora ya fijada (C-10).

    Los cinco pasos del Flujo 1, en orden: resolver la aseguradora --y fallar en
    el acto si no existe--, abrir la transaccion con el rol del aplicativo, fijar
    la variable de sesion dentro de ella, entregar la sesion y cerrar.
    """
    # Paso 1. Antes de tocar el motor: una aseguradora que no existe es un error
    # del codigo, no una base vacia (BR1.5).
    tenant = config.require(tenant_id)

    motor = _require_engine()
    async with AsyncSession(motor, expire_on_commit=False) as sesion:
        # Paso 2 y 5. `begin()` confirma al salir bien y revierte ante un fallo.
        async with sesion.begin():
            # Paso 3. `true` = local a esta transaccion: al cerrarla se va con
            # ella y no queda pegada a la conexion.
            await sesion.execute(
                text("SELECT set_config(:nombre, :valor, true)"),
                {"nombre": TENANT_SETTING, "valor": tenant.tenant_id},
            )
            marca = _current_tenant.set(tenant.tenant_id)
            try:
                # Paso 4.
                yield sesion
            finally:
                _current_tenant.reset(marca)


def current_tenant() -> TenantId:
    """La aseguradora de la sesion en curso (C-10).

    Fuera de una sesion no hay respuesta razonable: devolver una cadena vacia
    dejaria que alguien la usara como filtro y creyera que consulto algo.
    """
    actual = _current_tenant.get()
    if actual is None:
        msg = "no hay ninguna sesion abierta: `current_tenant()` solo vale dentro de `session_for`"
        raise SessionNotConfiguredError(msg)
    return actual


async def fetch_all(
    session: TenantSession, statement: str, **params: Any
) -> tuple[Mapping[str, Any], ...]:
    """Ejecuta una consulta con **parametros ligados** y devuelve sus filas.

    Los parametros se ligan, nunca se concatenan: una consulta armada con texto
    es la via por la que un dato de entrada se vuelve instruccion (BR1.6).
    """
    resultado = await session.execute(text(statement), params)
    return tuple(dict(fila) for fila in resultado.mappings().all())


async def fetch_one(
    session: TenantSession, statement: str, **params: Any
) -> Mapping[str, Any] | None:
    """La primera fila de una consulta, o `None` si no hubo ninguna."""
    filas = await fetch_all(session, statement, **params)
    return filas[0] if filas else None


async def execute_sql(session: TenantSession, statement: str, **params: Any) -> int:
    """Ejecuta una sentencia con parametros ligados y devuelve las filas tocadas.

    El numero de filas solo existe en el resultado del cursor, y el mapeador
    declara el tipo mas general; la comprobacion en tiempo de ejecucion es lo
    que deja el tipo estrecho sin fingirlo.
    """
    resultado = await session.execute(text(statement), params)
    if not isinstance(resultado, CursorResult):  # pragma: no cover -- el motor siempre lo es
        msg = f"se esperaba un resultado de cursor y llego {type(resultado).__name__}"
        raise TypeError(msg)
    return int(resultado.rowcount)


@asynccontextmanager
async def unscoped_session() -> AsyncIterator[TenantSession]:
    """Una sesion **sin aseguradora fijada**. Dos usos legitimos y ningun otro.

    1. **Preguntarle al catalogo.** La asercion de aislamiento pregunta que
       tablas tiene el esquema, que privilegios tiene el rol vivo y que columnas
       tienen las tablas excluidas, y ninguna de las tres preguntas pertenece a
       una aseguradora.
    2. **Las tablas que son dato del proyecto y no de una aseguradora**: el
       libro mayor del gasto, los contadores de cuota y la ventana de
       presupuesto de U5. Estan en la lista de exclusion versionada, no llevan
       columna de aseguradora y no tienen politica que fijar, porque el techo es
       uno solo para el proyecto y el gasto de evaluaciones, generacion y
       operacion no tiene aseguradora ninguna (BR7.1).

    No sirve para leer una tabla **con** politica: sin la variable fijada, esas
    politicas no devuelven ninguna fila (BR1.4), que es justo lo que comprueba
    la suite de aislamiento. Sigue siendo el mismo punto unico: lo que cambia es
    que aqui no hay aseguradora que fijar, no que se abra una segunda via.
    """
    motor = _require_engine()
    async with AsyncSession(motor, expire_on_commit=False) as sesion:
        async with sesion.begin():
            observability.emit("tenancy.unscoped_session_opened")
            yield sesion
