"""El contrato de borrado de datos de visitante (C-11, BR3.6).

U2 declara **que es** un dato de visitante, aporta el `Protocol` y los dos
purgadores de sus propias tablas. El reinicio nocturno que los llama es de U20.

El registro de purgadores es **explicito**, escrito a mano en la raiz de
composicion. Un descubrimiento automatico deja de encontrar lo que alguien nombro
distinto, y la retencion acotada deja de estar acotada sin que nadie lo note.

Que el registro este completo no se confia a la memoria: una prueba le pregunta
al **catalogo de la base** que tablas llevan la marca de dato de visitante --la
que cada revision escribe junto a su aislamiento-- y falla si alguna no tiene
purgador. Comparar dos listas escritas a mano no comprobaria nada, porque quien
olvida una olvida las dos.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from untangle import observability
from untangle.tenancy import config, session
from untangle.tenancy.models import (
    VISITOR_DATA_MARK,
    PurgeResult,
    VisitorDataPurger,
)

TABLAS_CON_MARCA = """
    SELECT c.relname AS table_name
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'r'
      AND n.nspname = :esquema
      AND coalesce(obj_description(c.oid, 'pg_class'), '') LIKE :marca
    ORDER BY c.relname
"""

BORRAR_ENLACES = "DELETE FROM case_access_link WHERE created_at < :older_than"
CONTAR_ENLACES = "SELECT count(*) AS total FROM case_access_link WHERE created_at < :older_than"

BORRAR_CLAVES = "DELETE FROM visitor_key WHERE created_at < :older_than"
CONTAR_CLAVES = "SELECT count(*) AS total FROM visitor_key WHERE created_at < :older_than"


@dataclass(frozen=True)
class _TablePurger:
    """Un purgador de una tabla, recorriendo **todas** las aseguradoras.

    Recorre una por una porque la politica de fila no deja de aplicarse para
    borrar: sin aseguradora fijada no se ve ninguna fila, asi que un `DELETE`
    global borraria exactamente cero. Que el borrado pase por el mismo punto
    unico que todo lo demas es lo que hace que no exista una segunda via.
    """

    name: str
    tables: tuple[str, ...]
    delete_sql: str
    count_sql: str

    async def purge(self, *, older_than: datetime, dry_run: bool = False) -> PurgeResult:
        total = 0
        for tenant_id in config.available_ids():
            async with session.session_for(tenant_id) as sesion:
                if dry_run:
                    fila = await session.fetch_one(sesion, self.count_sql, older_than=older_than)
                    total += int(fila["total"]) if fila is not None else 0
                else:
                    total += await session.execute_sql(
                        sesion, self.delete_sql, older_than=older_than
                    )

        observability.emit(
            "tenancy.visitor_data_purged",
            purger=self.name,
            deleted=total,
            dry_run=dry_run,
        )
        # `kept` es lo que se conserva a proposito. En las dos tablas de U2 no se
        # conserva nada: son dato de visitante entero, y su retencion la acota el
        # reinicio nocturno.
        return PurgeResult(name=self.name, deleted=total, kept=0)


#: Los dos purgadores de U2. Cada dueno de datos de visitante aporta el suyo.
CASE_ACCESS_LINK_PURGER = _TablePurger(
    name="case_access_link",
    tables=("case_access_link",),
    delete_sql=BORRAR_ENLACES,
    count_sql=CONTAR_ENLACES,
)

VISITOR_KEY_PURGER = _TablePurger(
    name="visitor_key",
    tables=("visitor_key",),
    delete_sql=BORRAR_CLAVES,
    count_sql=CONTAR_CLAVES,
)


def registered_tables(purgers: Sequence[VisitorDataPurger]) -> frozenset[str]:
    """Las tablas que el registro dice cubrir."""
    return frozenset(tabla for purgador in purgers for tabla in purgador.tables)


async def visitor_data_tables(schema: str = "public") -> frozenset[str]:
    """Las tablas que **la base** dice que guardan datos de visitante.

    La marca la escribe cada revision junto al aislamiento de su tabla, asi que
    una tabla nueva la trae desde el dia que nace o no la trae nunca.
    """
    async with session.unscoped_session() as sesion:
        filas = await session.fetch_all(
            sesion, TABLAS_CON_MARCA, esquema=schema, marca=f"{VISITOR_DATA_MARK}%"
        )
    return frozenset(str(fila["table_name"]) for fila in filas)


async def tables_without_purger(purgers: Sequence[VisitorDataPurger]) -> frozenset[str]:
    """Las tablas de datos de visitante que nadie se comprometio a borrar."""
    return await visitor_data_tables() - registered_tables(purgers)
