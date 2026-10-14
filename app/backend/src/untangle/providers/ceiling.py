"""El techo de gasto antes de cada llamada de voz: la implementacion de `SpendGate` (BR5.1).

Lee la foto del presupuesto de U5 (C-17, `budget_state`) y deja pasar la llamada
**solo** si el acumulado de la ventana de 90 dias esta por debajo del techo y se
conoce entero. Tres cosas lo cierran, y las tres fallan del lado cerrado porque
lo que esta en juego es dinero:

1. **El techo alcanzado**: lo gastado llego a los 5 USD de la ventana (D11).
2. **Una llamada sin valorar**: con una sola, el acumulado ya no se conoce y no
   se puede afirmar que quede presupuesto (decision de Miguel del 2026-09-21,
   la misma que cierra el carril de pago en U5).
3. **La foto no se pudo leer**: base caida o lenta. Seguir seria gastar sin
   control.

## Lo que este techo no decide

**No decide entre la voz principal y la de respaldo**, ni aplica los carriles
publico y de grabacion con su reserva: eso es de U17 antes de abrir la llamada
(C-17, `reserve_primary_voice`, US5.11). Este es el techo del proyecto entero,
el que ninguna llamada de voz puede pasar sea cual sea su carril o su voz, y el
que hace verdadera la regla de `project.md`: ningun gasto fuera del tope de
5 USD en 90 dias.

La foto se recibe por una funcion inyectada y no importando la contabilidad: asi
este modulo no arrastra la base de datos, y las pruebas fuerzan el acumulado al
borde sin gastar un centavo del presupuesto que protege (regla de `project.md`).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from untangle import observability
from untangle.base import ProviderName, Use
from untangle.providers.ports import BudgetExhausted, ExhaustedResource, SpendGate
from untangle.telemetry.spend.models import BudgetState

__all__ = ["CeilingGate", "ceiling_closed"]


def ceiling_closed(state: BudgetState) -> bool:
    """Si el techo del proyecto esta cerrado. Una funcion de la foto, sin base de datos."""
    return state.spent.unmeasured_count > 0 or state.spent.measured_usd >= state.cap_usd


class CeilingGate(SpendGate):
    """El techo, consultado antes de cada llamada de voz."""

    def __init__(self, read_budget: Callable[[], Awaitable[BudgetState]]) -> None:
        self._leer = read_budget

    async def ensure_open(self, *, provider: ProviderName, use: Use) -> None:
        try:
            estado = await self._leer()
        except Exception as error:  # noqa: BLE001 -- cualquier fallo de lectura cierra: una lista de tipos dejaria escapar el siguiente, y aqui lo que esta en juego es dinero
            observability.emit(
                "providers.ceiling_unreadable",
                provider=provider.value,
                use=use.value,
                error=type(error).__name__,
            )
            raise BudgetExhausted(
                ExhaustedResource.PROJECT_CAP, provider=provider, use=use
            ) from None
        if ceiling_closed(estado):
            raise BudgetExhausted(ExhaustedResource.PROJECT_CAP, provider=provider, use=use)
