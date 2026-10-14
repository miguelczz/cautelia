"""La base efimera y el gobierno de las migraciones (BR1.7, BR1.11, C-30).

Dos cosas que van juntas porque se necesitan a la vez: levantar una PostgreSQL
de verdad, con **la misma imagen anclada por huella** que el entorno local y con
**el rol del aplicativo**, y aplicar contra ella la historia unica de
migraciones.

Por que una base de verdad y no un doble: lo que se prueba es una conducta del
motor --las politicas de fila-- y un doble no la tiene. Una suite de aislamiento
contra un simulador comprueba el simulador.

Por que el rol del aplicativo y no el superusuario: el superusuario se salta las
politicas, y entonces toda la suite pasa sin que exista aislamiento. Es el fallo
que no avisa.

`testcontainers` se importa **dentro de la funcion** a proposito: es dependencia
de desarrollo, y este modulo vive en el arbol del aplicativo para que las pruebas
y `migrate:check` compartan un solo camino. Importarlo arriba obligaria al
proceso servido a traerse una herramienta de pruebas.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from untangle import observability, paths

if TYPE_CHECKING:  # pragma: no cover -- solo para anotar el contenedor
    from testcontainers.community.postgres import PostgresContainer

#: La imagen de la base, **anclada por huella digital**. Es la misma que el
#: entorno local: una etiqueta se puede reescribir en el registro, y entonces el
#: mismo comando baja otra imagen sin que nadie tocara el proyecto. Una prueba
#: comprueba que este valor y el de `docker-compose.yml` no se separen.
POSTGRES_IMAGE = (
    "pgvector/pgvector@sha256:cf134a767f474095eeba57e0117be8e568e011a63f33fbf252f14c9b760f8e6f"
)

#: El rol con el que se conecta el aplicativo. Sin privilegio de salto.
APP_ROLE = "untangle_app"

#: El superusuario del contenedor efimero. El aplicativo **nunca** lo usa.
SUPERUSER = "untangle"
DATABASE = "untangle"


class ContainerRuntimeUnavailableError(RuntimeError):
    """No hay motor de contenedores y por lo tanto no hay base.

    Se falla, no se salta. Saltar la suite de aislamiento la dejaria en verde sin
    haberla ejecutado, y una compuerta que no se ejecuta es una compuerta que no
    existe.
    """


class MultipleHeadsError(RuntimeError):
    """La historia de migraciones tiene mas de una cabeza (BR1.11).

    Un conflicto de migraciones que llegue al despliegue se resuelve con la base
    de produccion delante, que es el peor momento posible.
    """


@dataclass(frozen=True)
class EphemeralDatabase:
    """Las dos direcciones de la base efimera. El aplicativo solo usa la segunda."""

    superuser_url: str
    app_url: str


def _import_testcontainers() -> type[PostgresContainer]:
    try:
        from testcontainers.community.postgres import PostgresContainer
    except ImportError as error:  # pragma: no cover -- solo sin dependencias de desarrollo
        msg = (
            "falta `testcontainers`, que es dependencia de desarrollo: corra "
            "`mise run deps:install`. Sin base efimera no hay prueba de "
            "aislamiento, y saltarla dejaria la compuerta verde sin ejecutarla."
        )
        raise ContainerRuntimeUnavailableError(msg) from error
    return PostgresContainer


@contextmanager
def ephemeral_database() -> Iterator[EphemeralDatabase]:
    """Una PostgreSQL efimera con el rol del aplicativo ya creado.

    El rol lo crea el **mismo** guion de arranque que usa el entorno local, no
    una copia: dos guiones que se parecen acaban divergiendo justo en la linea
    que importa.
    """
    contenedor_clase = _import_testcontainers()
    contrasena = secrets.token_hex(16)

    contenedor = (
        contenedor_clase(
            image=POSTGRES_IMAGE,
            username=SUPERUSER,
            password=secrets.token_hex(16),
            dbname=DATABASE,
        )
        .with_env("UNTANGLE_POSTGRES_APP_USER", APP_ROLE)
        .with_env("UNTANGLE_POSTGRES_APP_PASSWORD", contrasena)
        .with_volume_mapping(str(paths.db_init_dir()), "/docker-entrypoint-initdb.d", "ro")
    )

    try:
        contenedor.start()
    except Exception as error:
        msg = (
            "no se pudo levantar la base efimera: "
            f"{error}. Arranque el motor de contenedores y vuelva a correr. "
            "Esta comprobacion no se salta: sin base no hay aislamiento que medir."
        )
        raise ContainerRuntimeUnavailableError(msg) from error

    try:
        superusuario = contenedor.get_connection_url(driver="psycopg")
        anfitrion = contenedor.get_container_host_ip()
        puerto = contenedor.get_exposed_port(5432)
        app = f"postgresql+psycopg://{APP_ROLE}:{contrasena}@{anfitrion}:{puerto}/{DATABASE}"
        observability.emit("tenancy.ephemeral_database_started", role=APP_ROLE)
        yield EphemeralDatabase(superuser_url=superusuario, app_url=app)
    finally:
        contenedor.stop()
        observability.emit("tenancy.ephemeral_database_stopped")


# --- La historia de migraciones -----------------------------------------------


def alembic_config(database_url: str, script_location: Path | None = None) -> Config:
    """La configuracion de Alembic, construida con rutas absolutas.

    No hay `alembic.ini`: un archivo aparte seria un segundo sitio donde vive la
    ruta del guion, y el dia que no coincidan el error aparece como "no hay
    revisiones" en vez de como lo que es.
    """
    configuracion = Config()
    directorio = script_location if script_location is not None else paths.migrations_dir()
    configuracion.set_main_option("script_location", str(directorio))
    configuracion.set_main_option("sqlalchemy.url", database_url)
    return configuracion


def heads(script_location: Path | None = None) -> tuple[str, ...]:
    """Las cabezas de la historia. Mas de una es un conflicto (BR1.11)."""
    configuracion = alembic_config("postgresql+psycopg://sin-uso", script_location)
    return tuple(ScriptDirectory.from_config(configuracion).get_heads())


def require_single_head(script_location: Path | None = None) -> str:
    """La unica cabeza, o un fallo que nombra las que hay."""
    cabezas = heads(script_location)
    if len(cabezas) != 1:
        msg = (
            f"la historia de migraciones tiene {len(cabezas)} cabezas "
            f"({', '.join(cabezas) or 'ninguna'}); tiene que haber exactamente una (C-30)"
        )
        raise MultipleHeadsError(msg)
    return cabezas[0]


def upgrade_to_head(database_url: str, script_location: Path | None = None) -> None:
    """Sube hasta la cabeza, tras comprobar que hay una sola."""
    require_single_head(script_location)
    command.upgrade(alembic_config(database_url, script_location), "head")


def downgrade_to_base(database_url: str, script_location: Path | None = None) -> None:
    """Baja hasta dejar la base como estaba. Un `downgrade()` roto se descubre aqui."""
    command.downgrade(alembic_config(database_url, script_location), "base")
