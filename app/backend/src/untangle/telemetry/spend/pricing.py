"""Cuanto costo una llamada, o por que no se pudo saber.

Una busqueda por (proveedor, modelo, unidad) y una multiplicacion decimal. Es
todo, y la parte importante es la que **no** hace: cuando la tabla no declara
precio, esto devuelve "no medido" y nunca cero (BR3.3).

Esa distincion parece menor hasta que se mira lo que cuesta perderla. Un cero por
falta de precio se suma como si fuera cierto: el costo por caso publicado baja,
el acumulado de la ventana se queda corto y el techo corta mas tarde de lo que
debia. Nada falla, nada avisa, y la cifra que el proyecto publica deja de
describir lo que dice describir. Es el mismo error que el proyecto ya se prohibio
en otro sitio, cuando separo "no hay clausula" de "no pude verificar".

La tabla se carga **una vez al arrancar** y no se recarga en caliente: cambiar un
precio mueve una cifra publicada, asi que tiene que quedar en el historial y
disparar la compuerta de evaluaciones. Una recarga en caliente permitiria moverla
sin que nadie lo viera en un diff.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import model_validator

from untangle.base import Frozen, ProviderName, UnitKind
from untangle.telemetry.spend.models import Money, PriceEntry, UsdAmount


class PricedCost(Frozen):
    """El costo de una llamada con la constancia de como se calculo (BR3.2).

    Los tres campos de constancia son lo que permite reproducir la cifra meses
    despues, cuando el precio del proveedor ya cambio (AC4.8.4). Van los cuatro
    juntos o ninguno, que es la misma invariante que guarda la fila de gasto
    (BR3.4): aqui se impone en el valor que la produce, para que una fila no
    pueda nacer a medias.
    """

    cost: Money
    unit_price_usd: UsdAmount | None = None
    price_list_version: str | None = None
    price_list_effective_date: date | None = None

    @model_validator(mode="after")
    def _la_constancia_acompana_al_costo(self) -> Self:
        constancia = {
            "unit_price_usd": self.unit_price_usd,
            "price_list_version": self.price_list_version,
            "price_list_effective_date": self.price_list_effective_date,
        }
        faltan = sorted(nombre for nombre, valor in constancia.items() if valor is None)
        sobran = sorted(nombre for nombre, valor in constancia.items() if valor is not None)

        if self.cost.is_measured and faltan:
            msg = (
                f"un costo medido dice con que precio y de que lista se calculo, y "
                f"faltan: {', '.join(faltan)}"
            )
            raise ValueError(msg)
        if not self.cost.is_measured and sobran:
            msg = (
                f"un costo no medido no tiene con que respaldarse, y llegaron: {', '.join(sobran)}"
            )
            raise ValueError(msg)
        return self


@dataclass(frozen=True)
class PriceTable:
    """La tabla versionada de precios de lista, ya en memoria.

    Se recorre en vez de indexarse porque tiene un punado de filas --una por
    proveedor, modelo y unidad-- y se consulta una vez por llamada a un
    proveedor, que dura segundos. Un indice aqui seria una estructura de mas que
    esconderia lo unico que hay que entender: que la clave son tres cosas y no
    dos.
    """

    entries: tuple[PriceEntry, ...] = ()

    @classmethod
    def from_entries(cls, entries: Iterable[PriceEntry]) -> PriceTable:
        return cls(entries=tuple(entries))

    def find(self, provider: ProviderName, model: str, unit_kind: UnitKind) -> PriceEntry | None:
        """El precio de esa terna, o `None` si la tabla no lo declara."""
        for linea in self.entries:
            if linea.provider is provider and linea.model == model and linea.unit_kind is unit_kind:
                return linea
        return None


def price_call(
    table: PriceTable,
    *,
    provider: ProviderName,
    model: str,
    unit_kind: UnitKind,
    units: Decimal,
) -> PricedCost:
    """El costo de una llamada a precio de lista, medido o **no medido**.

    El producto no se redondea a centavos. Redondear convertiria en cero toda
    llamada que cueste menos de medio centavo --que son casi todas las de este
    proyecto-- y eso es justo la cifra prohibida: un cero que se suma como si
    fuera cierto. La suma de muchos importes exactos si da un total con sentido;
    la suma de muchos ceros redondeados, no.
    """
    linea = table.find(provider, model, unit_kind)
    if linea is None:
        return PricedCost(cost=Money.not_measured())

    return PricedCost(
        cost=Money.measured(units * linea.unit_price_usd),
        unit_price_usd=linea.unit_price_usd,
        price_list_version=linea.list_version,
        price_list_effective_date=linea.effective_date,
    )
