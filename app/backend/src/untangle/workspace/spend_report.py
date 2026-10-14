"""`mise run spend:report`: lo que el proyecto lleva gastado, con lo no medido.

**No es una compuerta y no entra en el guion de verificacion** (INF-U5-4). Es el
productor del valor real de NFR14.1, y una compuerta que fallara porque el costo
por caso subio seria una compuerta sobre una cifra que todavia no tiene linea
base. Compararla contra la linea base versionada es trabajo de U21.

## Lo que este reporte no hace, y por que

**No divide entre los casos que pasan todas las compuertas.** AC5.14.6 define el
costo por caso exitoso asi, y "que pasan todas las compuertas" lo sabe el
corredor de evaluaciones, que es de U21. Lo que esta unidad entrega es el gasto
por caso; el divisor lo pone quien conoce el resultado de las compuertas.
Inventar aqui un divisor --todos los casos, por ejemplo-- publicaria una cifra
mas baja que la real con el nombre de otra.

**Cada total viaja con su conteo de no medidas** (BR3.5). Publicar el total sin
decir cuantas llamadas no se pudieron valorar exige desarmar el tipo a
proposito, y este reporte no lo desarma: las dos cifras salen a la misma linea.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from decimal import Decimal

from untangle.settings import Settings
from untangle.telemetry.spend import budget, repository
from untangle.telemetry.spend.models import WINDOW_START, SpendTotal
from untangle.tenancy import session


def _linea(etiqueta: str, total: SpendTotal) -> str:
    """Una linea del reporte: el total medido **y** cuantas no se midieron."""
    sin_medir = (
        "todas medidas" if total.unmeasured_count == 0 else f"{total.unmeasured_count} sin medir"
    )
    return f"  {etiqueta:<24} {total.measured_usd:>18} USD   ({sin_medir})"


async def render(window_start: date = WINDOW_START) -> list[str]:
    """Las cuatro agregaciones y el estado de la ventana, ya en lineas.

    Se devuelve como lineas y no se imprime aqui para que una prueba pueda leer
    lo que diria sin capturar la salida estandar.
    """
    ventana = await repository.load_window(window_start)

    lineas: list[str] = ["Gasto del proyecto, a precio de lista (NFR14.1)", ""]

    if ventana is None:
        lineas.append(
            f"  No hay ventana de presupuesto que empiece el {window_start}: sin acumulado "
            "no hay techo que reportar."
        )
    else:
        estado = budget.state(ventana)
        lineas.extend(
            [
                f"Ventana {ventana.window_start} a {ventana.window_end}  [{estado.status.value}]",
                _linea("acumulado facturable", estado.spent),
                f"  {'techo':<24} {ventana.cap_usd:>18} USD",
                f"  {'alerta':<24} {ventana.alert_usd:>18} USD"
                + (
                    "" if ventana.alert_sent_at is None else f"   (enviada {ventana.alert_sent_at})"
                ),
                f"  {'restante publico':<24} "
                f"{_importe(estado.public_remaining_usd.amount_usd):>18} USD",
                # Las dos causas de un restante sin numero, a la vista y al lado
                # del restante que explican: la reserva --que solo puede quedarse
                # sin numero de una forma-- y el gasto del carril con su propio
                # conteo de llamadas sin valorar. Sin las dos lineas, "no medida"
                # seria un callejon sin salida para quien lee el reporte.
                f"  {'reserva de grabacion':<24} "
                f"{_importe(estado.recording_reserve_usd.amount_usd):>18} USD",
                _linea("gastado en grabacion", estado.recording_spent),
                f"  {'restante de grabacion':<24} "
                f"{_importe(estado.recording_remaining_usd.amount_usd):>18} USD",
                "",
            ]
        )

        del_historial = await repository.window_spend(ventana.window_start, ventana.window_end)
        lineas.extend(
            [
                "Conciliacion con el historial",
                _linea("recorriendo las filas", del_historial),
                "",
            ]
        )

    por_proveedor = await repository.spend_by_provider()
    lineas.append("Por proveedor")
    lineas.extend(_linea(nombre.value, total) for nombre, total in por_proveedor)
    if not por_proveedor:
        lineas.append("  (ninguna llamada registrada todavia)")
    lineas.append("")

    por_mes = await repository.spend_by_month()
    lineas.append("Por mes (UTC)")
    lineas.extend(_linea(mes, total) for mes, total in por_mes)
    if not por_mes:
        lineas.append("  (ninguna llamada registrada todavia)")
    lineas.append("")

    lineas.append(
        "El costo por caso exitoso (AC5.14.6) divide el gasto entre los casos que "
        "pasan todas las compuertas; ese divisor lo pone U21, que es quien conoce "
        "el resultado de las compuertas."
    )
    return lineas


def _importe(cantidad: Decimal | None) -> str:
    """Un importe, o **no medida**. Nunca cero por no saber (BR3.3)."""
    return "no medida" if cantidad is None else str(cantidad)


def main() -> int:
    opciones = Settings()
    if not opciones.database_url:
        print(
            "falta UNTANGLE_DATABASE_URL: el gasto vive en la base y este reporte la lee",
            file=sys.stderr,
        )
        return 1

    async def correr() -> list[str]:
        session.configure(opciones.database_url or "")
        try:
            return await render()
        finally:
            await session.dispose()

    for linea in asyncio.run(correr()):
        print(linea)
    return 0


if __name__ == "__main__":
    sys.exit(main())
