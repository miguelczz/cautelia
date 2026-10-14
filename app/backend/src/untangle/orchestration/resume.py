"""Lo que hay para retomar un caso (paso 6 de U12: BR3.1, BR3.2, BR3.4, FD-U12-8).

**Se pide por `case_id`, nunca por poliza.** `resume_state` no tiene -- ni
puede tener, mirando su firma -- un parametro de numero de poliza: el origen
que abrio el caso es `case_id`, y ofrecer por poliza es exactamente lo que
BR3.4 prohibe, porque las tres polizas de ejemplo son publicas a proposito
(F8.7). Un caso a medias que otro navegador nunca conocio por su `case_id` no
tiene forma de aparecer aqui, sin importar cuantos otros casos compartan su
poliza.

**"Identico en texto y en estado" empieza aqui.** Un caso sin punto de control
y sin pausa produce exactamente `ResumeState(has_checkpoint=False,
open_pause_reason=None)` -- el mismo valor, campo por campo, que produce un
`case_id` que nunca existio. Esta funcion no distingue "esta poliza la usa
otra persona en otro caso" de "no hay nada que ofrecer" porque nunca se le dijo
cual poliza es: no tiene el dato con el que podria filtrar.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.runnables import RunnableConfig

from untangle.orchestration.checkpoint import TenantCheckpointSaver
from untangle.orchestration.pause import HumanReviewRequestStore, PauseReason
from untangle.tenancy.models import TenantId


@dataclass(frozen=True)
class ResumeState:
    """Lo que hay para reanudar un caso (BR3.1, BR3.2), y nada de ningun otro (BR3.4)."""

    has_checkpoint: bool
    open_pause_reason: PauseReason | None


async def resume_state(
    checkpointer: TenantCheckpointSaver,
    pause_store: HumanReviewRequestStore,
    *,
    tenant_id: TenantId,
    case_id: str,
) -> ResumeState:
    """El ultimo punto de control de `case_id` y su pausa viva, si las tiene.

    Las dos lecturas van cada una por su propia tabla, ya aisladas por
    aseguradora (BR6.1); esta funcion solo las junta. **No decide nada** sobre
    el caso -- eso lo prohibe BR3.3 -- y no toca ningun campo de `case_record`:
    es de solo lectura, siempre.
    """
    config: RunnableConfig = {"configurable": {"tenant_id": tenant_id, "thread_id": case_id}}
    tupla = await checkpointer.aget_tuple(config)
    pausa = await pause_store.find_open(tenant_id=tenant_id, case_id=case_id)
    return ResumeState(
        has_checkpoint=tupla is not None,
        open_pause_reason=pausa.reason if pausa is not None else None,
    )


__all__ = ["ResumeState", "resume_state"]
