"""El tope diario de casos del ajustador de IA (A10 del diseno).

El gasto de busqueda es variable --un centavo por busqueda, tres por caso-- y la demo es
publica, asi que cuantos casos decide el ajustador en un dia es lo que acota ese gasto. Se
cuenta en el cupo que ya protege el chat y la voz (`quota_counter`): un contador del sitio
entero, que se abre de nuevo a medianoche de la zona configurada.

**El limite no se lee de `providers.yaml` sino de `adjuster.yaml`** y viaja por argumento hasta
la contabilidad: el patron de los otros cupos --el limite instalado con la contabilidad-- sirve
a quien lo declara alli, y el del ajustador es una decision del ajustador, que se lee junto a
sus dominios y sus intentos.

**Reservar es consumir.** `reserve_case` consulta y consume en un solo acto: entre una lectura y
un incremento, dos casos a la vez pasarian los dos (RT-13). Quien reintenta un caso que ya
reservo su cupo --su corrida existe en `adjuster_run`-- no vuelve a reservar: es del proceso que
decide, no de este archivo.

**Cerrado donde hay dinero.** Si el presupuesto esta agotado o no se pudo medir, o el contador no
se pudo leer, se niega: el ajustador gasta, y apagarlo es la direccion segura. El caso espera.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from untangle.adjuster.config import AdjusterConfig
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend.models import SITE_SUBJECT, QuotaDecision, QuotaScope

__all__ = ["CasesToday", "cases_today", "reserve_case"]

SCOPE = QuotaScope.ADJUSTER_CASES_SITE_DAY


async def reserve_case(config: AdjusterConfig, *, now: datetime | None = None) -> QuotaDecision:
    """Si el ajustador puede atender un caso mas hoy, **y lo cuenta si puede**.

    Una negacion es un valor, nunca una excepcion: `allowed` en falso con su motivo y los
    segundos que faltan para que el dia se abra de nuevo. El caso que no cupo no se pierde,
    espera en `derived` y lo recoge el reintento.
    """
    return await spend.check_quota(SCOPE, SITE_SUBJECT, now=now, limit=config.daily_case_cap)


@dataclass(frozen=True)
class CasesToday:
    """Cuantos casos lleva hoy el ajustador y cuantos admite."""

    used: int
    limit: int

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)


async def cases_today(config: AdjusterConfig, *, now: datetime | None = None) -> CasesToday:
    """Lo que dice el contador ahora, para una pantalla o una traza. No consume nada."""
    estado = await spend.quota_state(SCOPE, SITE_SUBJECT, now=now, limit=config.daily_case_cap)
    return CasesToday(used=estado.count, limit=estado.limit)
