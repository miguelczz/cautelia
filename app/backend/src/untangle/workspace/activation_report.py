"""`mise run activation:report`: cuantas sesiones llegan a cada hito, por dia.

**No es una compuerta y no entra en el guion de verificacion**, igual que
`spend:report`: es el productor de la cifra de OBS-U6.3. Lee la base, asi que
necesita `UNTANGLE_DATABASE_URL`; sin ella falla nombrandola en vez de reportar
ceros, que se leerian como "nadie entro".

## Lo que este reporte muestra, y lo que no

Una tabla por dia (UTC), con una fila por aseguradora y una columna por hito
(OBS-U6.3). **Solo conteos**: lee el conteo diario y nunca el avance por sesion,
que no tiene ruta de lectura (BR8.5). Ninguna linea nombra una sesion, una clave
de navegador ni un caso.

Una aseguradora sin fila un dia sale con ceros en ese dia: la fila del conteo
nace con la primera sesion que llega al hito, asi que su ausencia es exactamente
"ninguna sesion llego". Lo que este reporte **no puede** saber es si un registro
fallo --el turno siguio y el conteo quedo corto (BR8.3)--; eso lo dicen los
eventos `activation.milestone_failed` de ese dia.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Sequence
from datetime import date

from untangle.settings import Settings
from untangle.telemetry.activation import api as activation
from untangle.tenancy import api as tenancy

#: Las columnas, en el orden del recorrido de una visita.
HITOS: tuple[activation.ActivationMilestone, ...] = tuple(activation.ActivationMilestone)

ANCHO_ASEGURADORA = 16
ANCHO_HITO = 15


def render_counts(
    counts: Sequence[activation.ActivationDailyCount], tenants: Sequence[str]
) -> list[str]:
    """Las lineas del reporte. Pura: se prueba sin base ni salida estandar."""
    lineas = ["Activacion por dia, aseguradora e hito (OBS-U6.3, dias en UTC)", ""]
    if not counts:
        lineas.append("  (ninguna sesion registrada todavia)")
        return lineas

    por_dia: dict[date, dict[tuple[str, str], int]] = {}
    for fila in counts:
        por_dia.setdefault(fila.day, {})[(fila.tenant_id, fila.milestone.value)] = fila.count

    cabecera = f"  {'aseguradora':<{ANCHO_ASEGURADORA}}" + "".join(
        f"{hito.value:>{ANCHO_HITO}}" for hito in HITOS
    )
    for dia in sorted(por_dia):
        conteo = por_dia[dia]
        lineas.extend([dia.isoformat(), cabecera])
        for tenant_id in tenants:
            celdas = "".join(
                f"{conteo.get((tenant_id, hito.value), 0):>{ANCHO_HITO}}" for hito in HITOS
            )
            lineas.append(f"  {tenant_id:<{ANCHO_ASEGURADORA}}{celdas}")
        lineas.append("")
    return lineas


async def render() -> list[str]:
    """Lee el conteo de todas las aseguradoras y lo compone en lineas."""
    return render_counts(await activation.daily_counts(), tenancy.available_ids())


def main() -> int:
    opciones = Settings()
    if not opciones.database_url:
        print(
            "falta UNTANGLE_DATABASE_URL: la activacion vive en la base y este reporte la lee",
            file=sys.stderr,
        )
        return 1

    async def correr() -> list[str]:
        tenancy.configure(opciones.database_url or "")
        try:
            return await render()
        finally:
            await tenancy.dispose()

    for linea in asyncio.run(correr()):
        print(linea)
    return 0


if __name__ == "__main__":
    sys.exit(main())
