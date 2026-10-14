"""Que se lleva el reinicio nocturno de la llamada (C-11, BR7.3, NFR19, UG-3).

**Se borra la fila entera.** Su sujeto es el resumen de la clave de un navegador
y su tabla lleva la marca de dato de visitante. No hay nada que conservar: los
recuentos que el panel publico de U22 necesita se calculan de la traza y del
caso, no de aqui, asi que `kept` es cero y lo dice a proposito.

**Por que hace falta un purgador si la cascada ya existe.** `call_session` cuelga
del caso con `ON DELETE CASCADE`, asi que borrar el caso se lleva la llamada. Lo
que la cascada **no** alcanza es la llamada que nunca llego a tener caso: el
microfono concedido, el socket abierto y la persona que colgo antes de decir
nada. Esas filas llevan el resumen de un navegador y se quedarian para siempre.

Recorre las aseguradoras una por una por la misma razon que los demas
purgadores: la politica de fila no deja de aplicarse para borrar, y un `DELETE`
sin aseguradora fijada borraria exactamente cero filas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from untangle import observability
from untangle.tenancy import api as tenancy

BORRAR_LLAMADAS = "DELETE FROM call_session WHERE started_at < :older_than"
CONTAR_LLAMADAS = "SELECT count(*) AS total FROM call_session WHERE started_at < :older_than"


@dataclass(frozen=True)
class _CallPurger:
    """El purgador de U16, con la forma de `VisitorDataPurger` (C-11)."""

    name: str = "call_session"
    tables: tuple[str, ...] = ("call_session",)

    async def purge(self, *, older_than: datetime, dry_run: bool = False) -> tenancy.PurgeResult:
        borradas = 0
        for tenant_id in tenancy.available_ids():
            async with tenancy.session_for(tenant_id) as sesion:
                if dry_run:
                    fila = await tenancy.fetch_one(sesion, CONTAR_LLAMADAS, older_than=older_than)
                    borradas += int(fila["total"]) if fila is not None else 0
                else:
                    borradas += await tenancy.execute_sql(
                        sesion, BORRAR_LLAMADAS, older_than=older_than
                    )

        observability.emit("voice.call_session_purged", deleted=borradas, dry_run=dry_run)
        return tenancy.PurgeResult(name=self.name, deleted=borradas, kept=0)


#: El unico purgador de la voz. La raiz de composicion lo apunta en su registro,
#: y la comprobacion de U2 falla si `call_session` queda sin el.
CALL_SESSION_PURGER = _CallPurger()

__all__ = ["CALL_SESSION_PURGER"]
