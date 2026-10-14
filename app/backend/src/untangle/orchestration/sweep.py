"""El barrido al arrancar (paso 5 de esta unidad, BR5.5): lo vencido pasa a `abandoned`.

**No relanza nada por si mismo.** Un `node_run` en `running` cuyo arrendamiento
vencio deja de parecer un trabajo en curso -- eso es todo lo que este modulo
hace --, y es la proxima vez que ese nodo se invoque la que lo retoma: `abandoned`
no esta en `TERMINAL_OUTCOMES` (`node_run.py`), asi que el ejecutor comun del
paso 4 lo trata igual que un `running` a medias y sigue el conteo de intentos
desde donde se quedo (BR5.4), sin que este barrido tenga que saber que entrada
tenia el nodo ni como volver a llamarlo.

**Por que `abandoned` y no `degraded`.** El resumen de BR5.5 lo dice: el primero
es una operacion (un proceso murio; el trabajo sigue pendiente), el segundo es
una respuesta ya emitida al asegurado (se agotaron los intentos y se emitio su
frase). Colapsarlos le haria decir al reporte que el sistema le respondio algo a
alguien cuando en realidad nadie lo escucho todavia.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from untangle import observability
from untangle.orchestration.node_run import NodeRunOutcome, NodeRunRecord, NodeRunStore
from untangle.tenancy.models import TenantId


async def sweep_abandoned(
    store: NodeRunStore, *, tenant_id: TenantId, now: datetime
) -> tuple[NodeRunRecord, ...]:
    """Marca como `abandoned` lo que sigue `running` con el arrendamiento vencido.

    Devuelve las filas que marco, para quien lo invoque al arrancar y quiera
    contar o registrar cuantas retomo (PERF-U12.8: la duracion y el conteo de
    este barrido se publican desde la primera corrida).
    """
    vencidas = await store.find_stale_running(tenant_id=tenant_id, before=now)
    marcadas: list[NodeRunRecord] = []
    for fila in vencidas:
        actualizada = replace(
            fila,
            outcome=NodeRunOutcome.ABANDONED,
            lease_owner=None,
            lease_expires_at=None,
        )
        await store.upsert(actualizada)
        observability.emit(
            "orchestration.node_run_abandoned",
            tenant_id=tenant_id,
            case_id=fila.case_id,
            node=fila.node.value,
            idempotency_key=fila.idempotency_key,
        )
        marcadas.append(actualizada)
    return tuple(marcadas)


__all__ = ["sweep_abandoned"]
