"""Que se lleva el reinicio nocturno del chat, y que no (C-11, BR3.1, NFR19).

**Se borra** la conversacion entera: su sujeto es el resumen de la clave de un
navegador, y su tabla lleva la marca de dato de visitante. Con ella se va, por
cascada de la base, todo lo que cuelgue de su caso.

**Se borra tambien** el contador del ambito `origin`, que apunta a la red desde la
que alguien escribio. No lleva la marca --la tabla es aritmetica del sitio-- pero si
apunta a un visitante, y ese compromiso queda escrito aqui con un nombre, igual que
U5 y U6 escribieron el suyo.

**No se borra** el contador del ambito `site_day`: no apunta a nadie y es la cifra
que el panel publico de U22 necesita que sobreviva a la noche. Aparece como `kept`
para que quien lea el resultado vea que se conservo a proposito.

Recorre las aseguradoras una por una por la misma razon que los purgadores de U2: la
politica de fila no deja de aplicarse para borrar, y un `DELETE` sin aseguradora
fijada borraria exactamente cero filas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from untangle import observability
from untangle.tenancy import api as tenancy

BORRAR_SESIONES = "DELETE FROM chat_session WHERE created_at < :older_than"
CONTAR_SESIONES = "SELECT count(*) AS total FROM chat_session WHERE created_at < :older_than"

BORRAR_ORIGENES = (
    "DELETE FROM chat_rate_window WHERE scope = 'origin' AND window_start < :older_than"
)
CONTAR_ORIGENES = (
    "SELECT count(*) AS total FROM chat_rate_window "
    "WHERE scope = 'origin' AND window_start < :older_than"
)
CONTAR_DIAS = "SELECT count(*) AS total FROM chat_rate_window WHERE scope = 'site_day'"


@dataclass(frozen=True)
class _ChatPurger:
    """El purgador de U13, con la forma de `VisitorDataPurger` (C-11)."""

    name: str = "chat_session"
    tables: tuple[str, ...] = ("chat_session",)

    async def purge(self, *, older_than: datetime, dry_run: bool = False) -> tenancy.PurgeResult:
        borradas = 0
        conservadas = 0
        for tenant_id in tenancy.available_ids():
            async with tenancy.session_for(tenant_id) as sesion:
                if dry_run:
                    for consulta in (CONTAR_SESIONES, CONTAR_ORIGENES):
                        fila = await tenancy.fetch_one(sesion, consulta, older_than=older_than)
                        borradas += int(fila["total"]) if fila is not None else 0
                else:
                    for sentencia in (BORRAR_SESIONES, BORRAR_ORIGENES):
                        borradas += await tenancy.execute_sql(
                            sesion, sentencia, older_than=older_than
                        )
                fila = await tenancy.fetch_one(sesion, CONTAR_DIAS)
                conservadas += int(fila["total"]) if fila is not None else 0

        observability.emit(
            "chat.session_purged",
            deleted=borradas,
            kept=conservadas,
            dry_run=dry_run,
        )
        return tenancy.PurgeResult(name=self.name, deleted=borradas, kept=conservadas)


#: El unico purgador del chat. La raiz de composicion lo apunta en su registro, y
#: la comprobacion de U2 falla si `chat_session` queda sin el.
CHAT_PURGER = _ChatPurger()

__all__ = ["CHAT_PURGER"]
