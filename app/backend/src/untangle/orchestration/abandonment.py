"""La sesion abandonada (paso 6 de U12, BR3.3): esperar sin decidir nada.

**Por que esto es `open_pause` con un motivo, y no una transicion del caso.**
BR3.3 dice que el caso "queda esperando al asegurado, con su motivo, y sin
decidir nada" -- y "sin decidir nada" es la mitad que importa: no se le aplica
ninguna categoria ni revision de cierre a un reporte a medias, porque decidir
sobre datos incompletos produciria una decision con aspecto de completa, que es
peor que no decidir. Este modulo no llama a `case_record.api.apply_transition`
en ningun momento: no mueve el estado del caso, no le pone resolucion y no le
toca ningun campo. Lo unico que hace es abrir la pausa hacia la bandeja con el
motivo `incomplete_capture` -- que ya es, letra por letra, el motivo que BR4.1
declara para "cuando la captura queda incompleta" -- para que alguien la vea.

**El disparador (la conexion que se cierra, o los minutos de inactividad) no
es de este modulo.** Ese es el ritmo de fondo del canal (paso 7, con el
`handle_turn` real) o un barrido periodico, ninguno de los dos construido
todavia; lo que este paso deja listo es la unica accion que ese disparador
necesita poder llamar, ya probada con base de datos delante.
"""

from __future__ import annotations

from datetime import datetime

from untangle.orchestration.pause import (
    HumanReviewRequestRecord,
    HumanReviewRequestStore,
    PauseReason,
    open_pause,
)
from untangle.tenancy.models import TenantId


async def mark_abandoned(
    store: HumanReviewRequestStore, *, tenant_id: TenantId, case_id: str, now: datetime
) -> HumanReviewRequestRecord:
    """Abre la pausa de una sesion abandonada, con el motivo `incomplete_capture` (BR3.3).

    No lee ni escribe nada de `case_record`: la completitud real del caso la
    calcula ese modulo cuando alguien la pida, y esta funcion no necesita
    duplicarla para dejar la pausa abierta.
    """
    return await open_pause(
        store,
        tenant_id=tenant_id,
        case_id=case_id,
        reason=PauseReason.INCOMPLETE_CAPTURE,
        now=now,
    )


__all__ = ["mark_abandoned"]
