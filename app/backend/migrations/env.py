"""El entorno de Alembic del aplicativo (C-30).

**Una sola historia lineal** de migraciones para las once unidades que crean
tablas. Cada unidad escribe sus propias revisiones dentro de esta historia, y la
revision que crea una tabla trae en el **mismo archivo** su columna de
aseguradora, el aislamiento habilitado, el aislamiento forzado y su politica: no
existe una revision posterior "que agrega el aislamiento", porque entre una y
otra habria una ventana con datos sin aislar (BR1.10).

No hay `alembic.ini`. La configuracion se construye en
`untangle.tenancy.ephemeral`, con rutas absolutas y la direccion de la base
pasada por quien invoca. Un archivo `.ini` seria un segundo sitio donde vive la
ruta del guion, y el dia que no coincidan el error aparece como "no hay
revisiones" en vez de como lo que es.

La conexion se hace **sincrona** a proposito: Alembic lo es, y el driver
--psycopg 3-- sirve para los dos modos, asi que no hay un segundo driver que
mantener (ADR-002).
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine, pool

# Las revisiones escriben SQL explicito, no se autogeneran desde modelos: el
# aislamiento a nivel de fila no es algo que Alembic modele, y comparar contra un
# metadata a medias produciria revisiones que borran lo que no entiende.
target_metadata = None


def _url() -> str:
    url = context.config.get_main_option("sqlalchemy.url")
    if not url:
        msg = (
            "Alembic no recibio la direccion de la base. Invoque las migraciones "
            "por `untangle.tenancy.ephemeral`, que la pasa explicitamente."
        )
        raise RuntimeError(msg)
    return url


def run_migrations_offline() -> None:
    """Emite el SQL sin conectarse. Util para revisar que hara una revision."""
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica las revisiones contra la base.

    En PostgreSQL el DDL es transaccional: una revision que falla a la mitad deja
    la base como estaba, con su error (C-30).
    """
    motor = create_engine(_url(), poolclass=pool.NullPool)
    try:
        with motor.connect() as conexion:
            context.configure(connection=conexion, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        motor.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
