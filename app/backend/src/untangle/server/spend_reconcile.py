"""El ajuste conciliado: anota en el libro lo que el proveedor cobro y el libro no tiene.

    mise run spend:reconcile -- --provider anthropic --use evals_chat --amount 0.24 \\
        --note "consola de Anthropic, 2026-10-13" [--date 2026-10-13] [--model <id>] [--dry-run]

Existe por una cifra que no cuadraba (2026-10-13): la consola de Anthropic mostraba
0,96 USD del mes y los libros sumaban unos 0,71. Lo que faltaba (unos 0,24 USD) eran 33
corridas de `evals:entender` que gastaron de verdad sobre una base desechable y se
llevaron su gasto al borrarse. Los comandos ya escriben directo en el libro del proyecto;
esto anota, una vez y a mano, lo que ya paso.

## Lo que escribe

**Una fila del libro mayor** con origen `reconciled_adjustment`: el proveedor, el uso, el
importe, la fecha y la nota de donde salio la cifra. No es una medicion y se distingue de
una: no lleva unidades ni precio de lista, porque no la valoro ninguna lista --la dijo la
consola del proveedor--. Cuenta contra el techo de la ventana como cuenta cualquier gasto
facturable, que es lo que el techo debio haber visto.

## Lo que `--amount` es

**Lo que falta en el libro, no el total de la consola.** Si la consola dice 0,96 y el libro
suma 0,71, el importe es 0,25. Es siempre un aumento: el libro no admite importes negativos,
y un ajuste no se borra. Por eso hay `--dry-run`, que ensena el asiento y no escribe nada, y
un limite de 5 USD que pide `--allow-large`: un importe mal puesto es lo unico que este
comando no sabe deshacer.

## Reintentar no duplica

El identificador del asiento se deriva de lo que dice (proveedor, uso, modelo, importe, fecha
y nota). Correr dos veces el mismo comando deja una sola fila y suma una sola vez al acumulado.
Dos ajustes distintos del mismo dia se distinguen por su nota.

Corre sobre la base del proyecto (`UNTANGLE_DATABASE_URL`) y, como todo lo que escribe en el
libro, se detiene antes de escribir si esa base no esta levantada o no tiene la ventana.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from untangle.base import ProviderName, Use
from untangle.providers import config as provider_config
from untangle.server import manual_ledger
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend.models import MAX_ADJUSTMENT_NOTE, SpendEntry

__all__ = ["LARGE_ADJUSTMENT_USD", "MAX_ADJUSTMENT_USD", "main"]

#: Desde aqui el importe pide `--allow-large`. Un ajuste es la diferencia entre la consola y
#: el libro: centavos. Uno mayor casi siempre es el total de la consola puesto por error.
LARGE_ADJUSTMENT_USD = Decimal(5)

#: Lo mas que acepta el comando, con `--allow-large` o sin el. Muy por encima de cualquier
#: tope del proyecto: existe para que un error de dedo no llegue a la base.
MAX_ADJUSTMENT_USD = Decimal(1000)

#: Cuantos decimales admite el importe. La consola del proveedor muestra centavos.
_DECIMALES = 6


def _importe(texto: str) -> Decimal:
    try:
        valor = Decimal(texto)
    except InvalidOperation:
        msg = f"'{texto}' no es un numero"
        raise argparse.ArgumentTypeError(msg) from None
    if not valor.is_finite() or valor <= 0:
        msg = "el importe es lo que falta en el libro: mayor que cero"
        raise argparse.ArgumentTypeError(msg)
    if valor > MAX_ADJUSTMENT_USD:
        msg = f"el importe no puede pasar de {MAX_ADJUSTMENT_USD} USD: es lo que falta, no el total"
        raise argparse.ArgumentTypeError(msg)
    exponente = valor.as_tuple().exponent
    if isinstance(exponente, int) and -exponente > _DECIMALES:
        msg = f"el importe admite hasta {_DECIMALES} decimales"
        raise argparse.ArgumentTypeError(msg)
    return valor


def _fecha(texto: str) -> date:
    try:
        return date.fromisoformat(texto)
    except ValueError:
        msg = f"'{texto}' no es una fecha AAAA-MM-DD"
        raise argparse.ArgumentTypeError(msg) from None


def _nota(texto: str) -> str:
    limpia = " ".join(texto.split())
    if not limpia:
        msg = "la nota dice de donde salio la cifra y no puede ir vacia"
        raise argparse.ArgumentTypeError(msg)
    if len(limpia) > MAX_ADJUSTMENT_NOTE:
        msg = f"la nota admite hasta {MAX_ADJUSTMENT_NOTE} caracteres y trae {len(limpia)}"
        raise argparse.ArgumentTypeError(msg)
    return limpia


def _analizador() -> argparse.ArgumentParser:
    analizador = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    analizador.add_argument(
        "--provider", required=True, choices=[p.value for p in ProviderName], help="quien cobro"
    )
    analizador.add_argument(
        "--use",
        required=True,
        choices=[u.value for u in Use],
        help="el uso al que se atribuye; debe ser del mismo proveedor",
    )
    analizador.add_argument(
        "--amount",
        required=True,
        type=_importe,
        help="USD que FALTAN en el libro (no el total de la consola)",
    )
    analizador.add_argument(
        "--note",
        required=True,
        type=_nota,
        help="de donde salio la cifra, por ejemplo 'consola de Anthropic, 2026-10-13'",
    )
    analizador.add_argument(
        "--date", type=_fecha, default=None, help="el dia de la cifra; por omision, hoy (UTC)"
    )
    analizador.add_argument(
        "--model",
        default=None,
        help="por omision, el modelo que providers.yaml declara para el uso",
    )
    analizador.add_argument("--dry-run", action="store_true", help="ensena el asiento y no escribe")
    analizador.add_argument(
        "--allow-large",
        action="store_true",
        help=f"permite un importe de {LARGE_ADJUSTMENT_USD} USD o mas",
    )
    return analizador


def _ensenar(asiento: SpendEntry) -> None:
    print("Asiento de ajuste conciliado:")
    print(f"  proveedor     {asiento.provider.value}")
    print(f"  modelo        {asiento.model}")
    print(
        f"  uso           {asiento.use.value}  ({'facturable' if asiento.billable else 'gratuito'})"
    )
    print(f"  importe       {asiento.cost_usd} USD")
    print(f"  fecha         {asiento.occurred_at.date()}")
    print(f"  nota          {asiento.note}")
    print(f"  identificador {asiento.entry_id}")


async def _anotar(
    config: provider_config.ProviderPlatformConfig, url: str, argumentos: argparse.Namespace
) -> int:
    await manual_ledger.open_ledger(config, url)
    try:
        try:
            asiento = spend.adjustment_entry(
                provider=ProviderName(argumentos.provider),
                use=Use(argumentos.use),
                amount_usd=argumentos.amount,
                note=argumentos.note,
                on=argumentos.date or datetime.now(UTC).date(),
                model=argumentos.model,
            )
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 2
        _ensenar(asiento)
        if argumentos.dry_run:
            print("\n--dry-run: no se escribio nada.")
            return 0
        resultado = await spend.record_adjustment(asiento)
    finally:
        acumulado = await manual_ledger.close_ledger()

    if not resultado.written:
        print("\nEse ajuste ya estaba en el libro (mismo identificador): no se duplico.")
    elif asiento.billable:
        print("\nAnotado. Cuenta contra el techo de la ventana.")
    else:
        print("\nAnotado. Es de un uso gratuito: no mueve el acumulado del techo.")
    cifra = f"{acumulado:.6f} USD" if acumulado is not None else "no se pudo leer"
    print(f"Acumulado de la ventana en el libro de la base del proyecto: {cifra}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argumentos = _analizador().parse_args(argv)
    if argumentos.amount >= LARGE_ADJUSTMENT_USD and not argumentos.allow_large:
        print(
            f"el importe es {argumentos.amount} USD, de {LARGE_ADJUSTMENT_USD} o mas. Un ajuste es "
            "lo que FALTA en el libro, no el total de la consola. Si es correcto, repita con "
            "--allow-large. No se escribio nada.",
            file=sys.stderr,
        )
        return 2
    ajustes = Settings()
    config = provider_config.load()
    url = manual_ledger.project_ledger_url(ajustes, purpose="el ajuste conciliado")
    return asyncio.run(_anotar(config, url, argumentos))


if __name__ == "__main__":
    raise SystemExit(main())
