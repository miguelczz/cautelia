"""Que se lleva el reinicio nocturno de la bandeja (C-11, BR6.3, NFR19).

**Se borra el aviso.** `inbox_event` lleva la marca de dato de visitante porque su
resumen sale de lo que dijo una persona: redactado, si, pero suyo. Un evento
viejo no le sirve a nadie --la reanudacion por `Last-Event-ID` mira lo de la
sesion en curso-- y quedarse ahi seria guardar texto de visitante despues de que
sus datos se hayan ido.

**No se borra el recibo.** `decision_receipt` no lleva la marca: lo que guarda es
la huella de una peticion y la referencia de lo que se escribio, ningun texto de
nadie. Se va con su caso por la cascada de la base, que es lo correcto, y borrarlo
antes dejaria a una decision repetida creando una segunda cuando el recibo de la
primera ya no existiera. Aparece como `kept` para que quien lea el resultado vea
que se conservo a proposito y no por olvido.

Recorre las aseguradoras una por una por la misma razon que los purgadores de U2
y U13: la politica de fila no deja de aplicarse para borrar, y un `DELETE` sin
aseguradora fijada borraria exactamente cero filas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from untangle import observability
from untangle.tenancy import api as tenancy

BORRAR_AVISOS = "DELETE FROM inbox_event WHERE created_at < :older_than"
CONTAR_AVISOS = "SELECT count(*) AS total FROM inbox_event WHERE created_at < :older_than"
CONTAR_RECIBOS = "SELECT count(*) AS total FROM decision_receipt"


@dataclass(frozen=True)
class _InboxPurger:
    """El purgador de U14, con la forma de `VisitorDataPurger` (C-11)."""

    name: str = "inbox_event"
    tables: tuple[str, ...] = ("inbox_event",)

    async def purge(self, *, older_than: datetime, dry_run: bool = False) -> tenancy.PurgeResult:
        borrados = 0
        conservados = 0
        for tenant_id in tenancy.available_ids():
            async with tenancy.session_for(tenant_id) as sesion:
                if dry_run:
                    fila = await tenancy.fetch_one(sesion, CONTAR_AVISOS, older_than=older_than)
                    borrados += int(fila["total"]) if fila is not None else 0
                else:
                    borrados += await tenancy.execute_sql(
                        sesion, BORRAR_AVISOS, older_than=older_than
                    )
                fila = await tenancy.fetch_one(sesion, CONTAR_RECIBOS)
                conservados += int(fila["total"]) if fila is not None else 0

        observability.emit(
            "inbox.events_purged", deleted=borrados, kept=conservados, dry_run=dry_run
        )
        return tenancy.PurgeResult(name=self.name, deleted=borrados, kept=conservados)


#: El unico purgador de la bandeja. La raiz de composicion lo apunta en su
#: registro, y la comprobacion de U2 falla si `inbox_event` queda sin el.
INBOX_PURGER = _InboxPurger()

__all__ = ["INBOX_PURGER"]
