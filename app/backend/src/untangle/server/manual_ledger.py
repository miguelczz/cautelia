"""El libro de gasto de los comandos a mano que llaman a un proveedor.

Lo usan `voice:contract-live`, `voice:say`, `voice:call-live` (voz), `synthetic:draft`,
`evals:entender`, `evals:citas`, `evals:conversaciones`, `evals:completa` y
`corpus:ingest`. Todos recorren **el mismo camino de gasto** que una llamada del
proceso servido --techo antes de llamar, fila en el libro mayor despues--, y ninguno
puede llamar sin libro.

## Un solo libro: el de la base del proyecto

Es la base que nombra `UNTANGLE_DATABASE_URL`, la misma que usa `mise run dev`. Sin
ella, o con ella apagada, el comando **no llama a nadie**: se detiene con una frase que
dice que falta. Se comprueba antes de la primera llamada, no cuando algo ya se gasto.

Hasta el 2026-10-13 cinco tareas corrian con `--ledger ephemeral`: una base
desechable con la ventana sembrada en cero, que se destruia al terminar. Era un
parche de cuando la base del proyecto no existia, y tenia dos defectos que se
pagaron: el techo corria contra un acumulado que empezaba en cero, no contra el real,
y el gasto de la corrida **desaparecia con la base**. Las 33 corridas de
`evals:entender` del 7 al 13 de octubre (unos 0,24 USD) gastaron de verdad y no
quedaron en ningun libro. La base desechable no existe ya para esto: no hay un
segundo libro que alguien tenga que acordarse de pasar al primero, porque no hay un
segundo libro. Lo gastado que ya paso se anota con `mise run spend:reconcile`.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from untangle.base import ProviderName, UnitKind
from untangle.providers import config as provider_config
from untangle.providers.ports import UsageReport, UsageSink
from untangle.server import spend_wiring
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend import pricing
from untangle.telemetry.spend.models import WINDOW_DAYS, WINDOW_START
from untangle.tenancy import api as tenancy
from untangle.tenancy import session as tenancy_session

__all__ = [
    "AnnotatingUsageSink",
    "close_ledger",
    "open_ledger",
    "print_spend",
    "project_ledger_url",
    "spend_lines",
]


class AnnotatingUsageSink(UsageSink):
    """Pasa el uso al registro de gasto y se queda con una copia para el resumen."""

    def __init__(self, inner: UsageSink) -> None:
        self._inner = inner
        self.reports: list[UsageReport] = []

    async def report(self, usage: UsageReport) -> None:
        self.reports.append(usage)
        await self._inner.report(usage)


_SEMBRAR_VENTANA = """
    INSERT INTO budget_window (
        window_start, window_end, billable_spent_usd, cap_usd, alert_usd,
        recording_reserve_usd, recording_reserve_status, recording_spent_usd,
        unmeasured_billable_calls, unmeasured_recording_calls, updated_at
    ) VALUES (
        :inicio, :fin, 0, :techo, :alerta, :reserva, :estado_de_reserva, 0, 0, 0, :ahora
    )
"""


async def _sembrar_ventana() -> None:
    """La ventana de D11 en una base nueva: 40 USD en 90 dias desde el 2026-09-16,
    con alerta en 24 USD y **la reserva de grabacion convertida** (tope de Miguel del
    2026-10-07; el de 5 USD dejaba una llamada publica al dia con 0,09 USD gastados).

    Ningun comando la llama desde que el registro desechable se retiro (2026-10-13): se
    conserva para sembrar a mano, con el punto de sesion ya apuntado a la base, la ventana
    de una base nueva que no la tiene, sin escribir SQL suelto. Y `open_ledger` se detiene
    ante una base sin ventana, asi que esa siembra es lo que falta cuando lo dice.
    Una reserva en nulo deja el restante publico sin medir, y un restante sin medir
    cierra todo lo que cuesta dinero.
    """
    reserva = spend.recording_reserve_usd()
    async with tenancy_session.unscoped_session() as sesion:
        await tenancy_session.execute_sql(
            sesion,
            _SEMBRAR_VENTANA,
            inicio=WINDOW_START,
            fin=WINDOW_START + timedelta(days=WINDOW_DAYS),
            techo=Decimal("40.00"),
            alerta=Decimal("24.00"),
            reserva=reserva.amount_usd,
            estado_de_reserva=reserva.status.value,
            ahora=datetime.now(UTC),
        )


def project_ledger_url(settings: Settings, *, purpose: str) -> str:
    """La base del libro de gasto: la del proyecto, y si no esta, el comando se detiene.

    `purpose` nombra lo que no ocurre sin libro, para que el mensaje diga que se
    detuvo y por que. Se llama **antes** de construir nada que pueda gastar.
    """
    if not settings.database_url:
        msg = (
            f"falta UNTANGLE_DATABASE_URL: sin el libro de gasto de la base del proyecto no hay "
            f"{purpose}, y un gasto fuera de ese libro no cuenta contra el techo. Levante la "
            "base (mise run services:up) y ponga su direccion en .env. No se llamo a ningun "
            "proveedor."
        )
        raise SystemExit(msg)
    return settings.database_url


#: A que base apuntaba el proceso **antes** de que la contabilidad lo moviera.
#:
#: La contabilidad apunta el punto unico de sesion a su registro y al cerrar lo
#: soltaba siempre. Mientras solo la usaban tareas que corrian solas, daba igual:
#: no habia nadie mas. Desde que el alta de una aseguradora invoca la ingesta
#: dentro de su propio bucle, soltarlo cierra el motor que su dueno sigue usando,
#: y el alta moria al sembrar con "el punto unico de sesion no sabe a que base
#: conectarse". Lo que corresponde es devolver las cosas como estaban.
_url_anterior: str | None = None


async def open_ledger(config: provider_config.ProviderPlatformConfig, url: str) -> None:
    """Apunta la contabilidad al libro y **comprueba que se puede leer antes de gastar**.

    Si la base esta apagada, o no tiene la ventana de presupuesto, el comando se
    detiene aqui con la frase de lo que falta y deja el punto de sesion como estaba.
    Sin esta lectura, un libro ilegible se descubria en la primera llamada como "el
    techo esta cerrado", que es otra cosa: aqui el techo esta bien y lo que falta es
    la base.
    """
    global _url_anterior
    _url_anterior = tenancy.configured_url()
    tenancy.configure(url)
    spend.install(spend_wiring.spend_runtime(config))
    try:
        await _comprobar_el_libro()
    except SystemExit:
        await close_ledger()
        raise


async def _comprobar_el_libro() -> None:
    """Lee la foto del presupuesto; si no se puede, dice cual de las dos cosas falta."""
    try:
        await spend.budget_state()
    except spend.SpendUnavailableError as error:
        if error.__cause__ is None:
            falta = (
                f"la base del proyecto no tiene la ventana de presupuesto que empieza el "
                f"{WINDOW_START}: sin acumulado no hay techo que comprobar"
            )
        else:
            falta = (
                "no se pudo leer el libro de gasto de la base del proyecto: compruebe que "
                "este levantada (mise run services:up) y que UNTANGLE_DATABASE_URL apunte a ella"
            )
        msg = f"{falta}. No se llamo a ningun proveedor."
        raise SystemExit(msg) from error


async def _acumulado() -> Decimal | None:
    """El acumulado de la ventana tras la corrida, o nada si ya no se puede leer.

    Nada y no un error: se lee al cerrar, tambien cuando la corrida se detuvo, y un
    fallo aqui no puede tapar el motivo de la parada.
    """
    try:
        estado = await spend.budget_state()
    except spend.SpendUnavailableError:
        return None
    return estado.spent.measured_usd


async def close_ledger() -> Decimal | None:
    """Lee el acumulado y **devuelve el punto de sesion como estaba**.

    Corre siempre, tambien tras una parada. Las tres salidas:

    - La contabilidad uso la base que ya habia: no se suelta nada, porque el motor
      es de quien lo configuro y cerrarlo lo dejaria sin base a media tarea.
    - No habia ninguna: la contabilidad la puso, asi que la contabilidad la suelta.
    - Habia otra: se suelta la del registro --para no dejar su pozo de conexiones
      abierto-- y se vuelve a apuntar a la de antes.
    """
    global _url_anterior
    anterior, _url_anterior = _url_anterior, None
    try:
        gastado = await _acumulado()
        _avisar_de_filas_sin_escribir()
        return gastado
    finally:
        if anterior != tenancy.configured_url():
            await tenancy.dispose()
            if anterior is not None:
                tenancy.configure(anterior)


def _avisar_de_filas_sin_escribir() -> None:
    """Dice, en voz alta, cuantas filas de gasto no llegaron al libro.

    Las llamadas de un uso gratuito se escriben aparte del acumulado y su fallo se
    cuenta en vez de levantarse (`spend.deferred_failures`): no rompen el turno del
    chat, y esa es la razon de que existan. Un comando a mano no tiene turno que
    proteger, y una cifra a la que le faltan filas es justo lo que este libro no debe
    callar.
    """
    perdidas = spend.deferred_failures()
    if perdidas:
        print(
            f"AVISO: {perdidas} fila(s) de gasto no se pudieron escribir en el libro. "
            "Lo gastado en esta corrida esta por encima de lo anotado: use `mise run "
            "spend:reconcile` con la cifra de la consola del proveedor.",
            file=sys.stderr,
        )


def spend_lines(reports: Sequence[UsageReport], table: pricing.PriceTable) -> list[str]:
    """Lo que gasto la corrida: unidades por proveedor, modelo y clase, y su precio de lista.

    Se valora con la **misma** tabla y la misma aritmetica que el libro mayor
    (C-17), asi que la cifra impresa es la que se registro. Una linea sin precio
    se dice, y el total avisa de que se queda corto: nunca se suma como cero.
    """
    totales: dict[tuple[str, str, UnitKind], Decimal] = {}
    sin_recuento = 0
    for reporte in reports:
        if not reporte.units:
            sin_recuento += 1
        for unidad in reporte.units:
            clave = (reporte.provider.value, reporte.model, unidad.unit_kind)
            totales[clave] = totales.get(clave, Decimal(0)) + unidad.units

    lineas: list[str] = []
    total = Decimal(0)
    sin_precio = 0
    for (proveedor, modelo, clase), cantidad in sorted(
        totales.items(), key=lambda par: (par[0][0], par[0][1], par[0][2].value)
    ):
        costo = pricing.price_call(
            table,
            provider=ProviderName(proveedor),
            model=modelo,
            unit_kind=clase,
            units=cantidad,
        ).cost
        if costo.amount_usd is None:
            sin_precio += 1
            cifra = "sin precio de lista"
        else:
            total += costo.amount_usd
            cifra = f"{costo.amount_usd:.6f} USD"
        lineas.append(
            f"  {proveedor:<9} {modelo:<10} {clase.value:<14} {cantidad:>10.2f}   {cifra}"
        )

    if not totales:
        lineas.append("  ninguna llamada llego a contar unidades")
    if sin_recuento:
        lineas.append(
            f"  {sin_recuento} llamada(s) sin recuento: quedan en el registro como no medidas"
        )
    resumen = f"  Total a precio de lista: {total:.6f} USD"
    if sin_precio or sin_recuento:
        resumen += " (se queda corto: hay gasto sin valorar)"
    lineas.append(resumen)
    return lineas


def print_spend(
    reports: Sequence[UsageReport],
    config: provider_config.ProviderPlatformConfig,
    spent: Decimal | None,
) -> None:
    """El resumen de lo gastado y el acumulado de la ventana del libro del proyecto."""
    tabla = pricing.PriceTable.from_entries(config.prices.price_entries())
    print("\n--- Lo que gasto esta corrida, contado por el adaptador ---------------")
    for linea in spend_lines(reports, tabla):
        print(linea)
    cifra = f"{spent:.6f} USD" if spent is not None else "no se pudo leer"
    print(f"\nAcumulado de la ventana en el libro de gasto de la base del proyecto: {cifra}")
