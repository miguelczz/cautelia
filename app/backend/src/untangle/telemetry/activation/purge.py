"""Que se lleva el reinicio nocturno de la activacion, y que no (C-11, BR8.2).

**Se borra** el avance de cada sesion: es dato de visitante, porque su sujeto es
el resumen de la clave del navegador, y su tabla lleva la marca.

**No se borra** el conteo por dia, aseguradora e hito. Es la cifra que tiene que
sobrevivir, y no apunta a ninguna persona ni a ningun navegador. Aparece como
`kept`, nunca como `deleted`, para que quien lea el resultado del reinicio vea
que se conservo a proposito y no que se olvido.

Recorre las aseguradoras una por una por la misma razon que los purgadores de
U2: la politica de fila no deja de aplicarse para borrar, y un `DELETE` sin
aseguradora fijada borraria exactamente cero filas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from untangle import observability
from untangle.tenancy import api as tenancy

BORRAR_AVANCE = "DELETE FROM activation_progress WHERE reached_at < :older_than"
CONTAR_AVANCE = "SELECT count(*) AS total FROM activation_progress WHERE reached_at < :older_than"
CONTAR_CONTEO = "SELECT count(*) AS total FROM activation_daily"


@dataclass(frozen=True)
class _ActivationPurger:
    """El purgador de U6, con la forma de `VisitorDataPurger` (C-11)."""

    name: str = "activation_progress"
    tables: tuple[str, ...] = ("activation_progress",)

    async def purge(self, *, older_than: datetime, dry_run: bool = False) -> tenancy.PurgeResult:
        borradas = 0
        conservadas = 0
        for tenant_id in tenancy.available_ids():
            async with tenancy.session_for(tenant_id) as sesion:
                if dry_run:
                    fila = await tenancy.fetch_one(sesion, CONTAR_AVANCE, older_than=older_than)
                    borradas += int(fila["total"]) if fila is not None else 0
                else:
                    borradas += await tenancy.execute_sql(
                        sesion, BORRAR_AVANCE, older_than=older_than
                    )
                fila = await tenancy.fetch_one(sesion, CONTAR_CONTEO)
                conservadas += int(fila["total"]) if fila is not None else 0

        observability.emit(
            "activation.progress_purged",
            deleted=borradas,
            kept=conservadas,
            dry_run=dry_run,
        )
        return tenancy.PurgeResult(name=self.name, deleted=borradas, kept=conservadas)


#: El unico purgador de la activacion. La raiz de composicion lo apunta en su
#: registro escrito a mano, una linea por dueno (C-11).
ACTIVATION_PURGER = _ActivationPurger()
