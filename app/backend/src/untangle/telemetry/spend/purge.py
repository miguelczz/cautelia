"""Que se lleva el reinicio nocturno de esta unidad, y que no (C-11, BR7.6).

Es el contrato de borrado mas corto del proyecto y el que mas conviene leer
entero, porque lo interesante esta en la columna de lo que **no** se borra.

**Se borran** los contadores de cuota de un visitante y de una sesion: su sujeto
es el resumen de la clave del navegador (BR7.3), asi que son dato de un
visitante aunque su tabla sea dato del proyecto. Y con ellos las marcas de cierre
de llamada (BR5.5): existen para que devolver el cupo dos veces no devuelva dos
cupos, y el contador al que protegen se va esa misma noche, asi que una marca que
sobreviviera no protegeria nada y solo creceria.

**No se borra**, y cada uno por su razon:

- **El contador del sitio.** Su sujeto es el literal `site` y no nombra a nadie.
  Borrarlo cada noche le regalaria al dia siguiente el cupo que ya se habia
  gastado, y ese cupo es lo que reparte el presupuesto entre los dias que faltan
  (BR5.6, BR7.6).
- **La ventana de presupuesto.** Es la unica cifra del proyecto que un criterio
  de aceptacion exige que sobreviva a todo, incluido el reinicio y el cambio de
  mes (AC5.14.4, BR4.7). No se toca.
- **El registro de gasto.** Sobrevive entero y aparece como `kept`, nunca como
  `deleted` (C-11). Las filas que nombraban un caso borrado quedan con esa
  columna en nulo --lo hace la base, con `ON DELETE SET NULL`-- y todo lo demas
  intacto (BR7.5). Con borrado en cascada, el reinicio vaciaria cada noche el
  historial de lo que el proyecto ya pago.

## Por que este purgador declara una tabla que no lleva la marca

El registro de la raiz se compara contra las tablas que **la base** marca como
dato de visitante, y `quota_counter` no la lleva: es dato del proyecto, esta en
la lista de exclusion del aislamiento y no tiene aseguradora que aislar (BR7.1).
Lo que si tiene son **filas** de visitante, y alguien tiene que comprometerse a
borrarlas. Declararla aqui deja ese compromiso escrito con un nombre; no
declararla la dejaria sin dueno sin que ninguna comprobacion lo dijera, porque
la comprobacion mira la marca y la marca no esta.

## Ninguna conexion propia

Toda consulta pasa por el punto unico de sesion de U2, **sin aseguradora
fijada**: estas tablas no tienen politica que fijar, y pedir una sesion con
aseguradora seria fingir una atribucion que no existe. Los parametros se ligan;
el conjunto de alcances que se borran viaja como parametro y no se compone en la
cadena.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from untangle import observability
from untangle.telemetry.spend.models import QuotaScope
from untangle.tenancy import session
from untangle.tenancy.models import PurgeResult

#: Los alcances cuyo sujeto es un visitante. Se declara como tupla derivada del
#: enum y no como lista escrita a mano: un alcance nuevo por visitante entraria
#: aqui solo, mientras que una lista suelta se olvidaria y sus filas
#: sobrevivirian a la noche sin que nada lo dijera.
ALCANCES_DE_VISITANTE: tuple[str, ...] = tuple(
    alcance.value for alcance in QuotaScope if alcance is not QuotaScope.VOICE_CALLS_SITE_DAY
)

BORRAR_CONTADORES = """
    DELETE FROM quota_counter
    WHERE updated_at < :older_than
      AND scope = ANY(:scopes)
"""

CONTAR_CONTADORES = """
    SELECT count(*) AS total FROM quota_counter
    WHERE updated_at < :older_than
      AND scope = ANY(:scopes)
"""

#: Las marcas de cierre de llamada. Se van con los contadores que protegen: una
#: marca sin su contador no impide nada y solo ocupa sitio (BR5.5, BR7.6).
BORRAR_CIERRES = """
    DELETE FROM voice_call_release
    WHERE decided_at < :older_than
"""

CONTAR_CIERRES = """
    SELECT count(*) AS total FROM voice_call_release
    WHERE decided_at < :older_than
"""

#: Lo que se conserva a proposito, y que viaja en `kept`: el contador del sitio y
#: las filas del libro mayor. Se cuenta en vez de callarse porque un purgador que
#: solo dijera cuanto borro no dejaria ver el dia que empezara a borrar de mas.
CONTAR_CONSERVADOS = """
    SELECT (SELECT count(*) FROM quota_counter WHERE scope = 'voice_calls_site_day')
         + (SELECT count(*) FROM spend_entry) AS total
"""


@dataclass(frozen=True)
class _SpendPurger:
    """El purgador de U5: los contadores de visitante y nada mas."""

    name: str = "spend_quota_counters"
    tables: tuple[str, ...] = ("quota_counter", "voice_call_release")

    async def purge(self, *, older_than: datetime, dry_run: bool = False) -> PurgeResult:
        alcances = list(ALCANCES_DE_VISITANTE)
        async with session.unscoped_session() as sesion:
            if dry_run:
                fila = await session.fetch_one(
                    sesion, CONTAR_CONTADORES, older_than=older_than, scopes=alcances
                )
                borrados = int(fila["total"]) if fila is not None else 0
                fila = await session.fetch_one(sesion, CONTAR_CIERRES, older_than=older_than)
                borrados += int(fila["total"]) if fila is not None else 0
            else:
                borrados = await session.execute_sql(
                    sesion, BORRAR_CONTADORES, older_than=older_than, scopes=alcances
                )
                borrados += await session.execute_sql(sesion, BORRAR_CIERRES, older_than=older_than)
            fila = await session.fetch_one(sesion, CONTAR_CONSERVADOS)
            conservados = int(fila["total"]) if fila is not None else 0

        observability.emit(
            "spend.visitor_data_purged",
            purger=self.name,
            deleted=borrados,
            kept=conservados,
            dry_run=dry_run,
        )
        return PurgeResult(name=self.name, deleted=borrados, kept=conservados)


#: El purgador de U5. La raiz de composicion lo apunta en su tupla explicita.
SPEND_PURGER = _SpendPurger()
