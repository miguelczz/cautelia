"""El bloque del ajustador de IA en el caso, por un puerto que enchufa la raiz de composicion.

El ajustador (`untangle.adjuster`) esta por encima de la bandeja en el contrato de capas, asi que
la bandeja no lo importa: define aqui **la forma** en que lo muestra --los pasos con sus fuentes,
la decision, el resumen y el estado de la corrida-- y un puerto con dos preguntas, que la raiz de
composicion contesta con el ajustador. Sin nadie enchufado el caso sale sin el bloque.

Los vocabularios cerrados (estado, paso, clase de fuente) se repiten aqui como `Literal` porque
la bandeja no puede importar los del ajustador; una prueba de la raiz los compara.

**Leer el caso es lo que despierta el reintento** (A1): si el caso esta derivado y su corrida
fallo, quedo esperando el cupo o se perdio, la lectura vuelve a disparar el trabajo. Que un
fallo del ajustador no tumbe la lectura del caso es lo primero que se comprueba.
"""

from __future__ import annotations

from typing import Literal, Protocol

from untangle import observability
from untangle.base import Frozen
from untangle.case_record.models import CaseState
from untangle.inbox.actions import InboxAction
from untangle.tenancy.models import TenantId

RunStatusName = Literal["running", "decided", "capped", "failed"]
StepIdName = Literal["case_read", "policy_read", "clauses", "rules", "vehicle_value", "decision"]
SourceKindName = Literal["clause", "rule", "policy", "case", "web"]


class AdjusterSourceOut(Frozen):
    """Lo que respalda un paso: una clausula, una regla, un dato de la poliza o una pagina."""

    kind: SourceKindName
    ref: str
    label: str
    url: str | None = None


class AdjusterStepOut(Frozen):
    """Un paso del proceso, con su texto y sus fuentes."""

    id: StepIdName
    #: La clave del catalogo con el titulo del paso; la interfaz la resuelve en el idioma de quien mira.
    title_key: str | None = None
    text: str
    sources: tuple[AdjusterSourceOut, ...] = ()


class AdjusterRunOut(Frozen):
    """La corrida del ajustador sobre el caso, tal como la ve quien abre el caso."""

    status: RunStatusName
    attempt: int
    steps: tuple[AdjusterStepOut, ...] = ()
    #: Lo que decidio, solo con la corrida decidida.
    decision: InboxAction | None = None
    #: El titular de la decision y su explicacion, que el ajustador escribio en el idioma del caso.
    headline: str | None = None
    explanation: str | None = None
    searches_used: int = 0
    updated_at: str


class AdjusterWatcher(Protocol):
    """Lo que la raiz de composicion contesta con el ajustador."""

    async def read(self, tenant_id: TenantId, case_id: str) -> AdjusterRunOut | None: ...

    async def retry_if_needed(
        self, tenant_id: TenantId, case_id: str, state: CaseState
    ) -> None: ...


_VIGIA: AdjusterWatcher | None = None


def install(watcher: AdjusterWatcher | None) -> None:
    """La raiz de composicion enchufa el ajustador; `None` lo quita."""
    global _VIGIA
    _VIGIA = watcher


async def read(tenant_id: TenantId, case_id: str) -> AdjusterRunOut | None:
    """La corrida del caso, o nada si no hay ajustador enchufado, no ha empezado o fallo la lectura."""
    if _VIGIA is None:
        return None
    try:
        return await _VIGIA.read(tenant_id, case_id)
    except Exception as error:  # noqa: BLE001 -- leer el caso no puede depender de que el ajustador responda
        observability.emit(
            "inbox.adjuster_read_failed",
            tenant_id=tenant_id,
            case_id=case_id,
            error=type(error).__name__,
        )
        return None


async def retry_if_needed(tenant_id: TenantId, case_id: str, state: CaseState) -> None:
    """Despierta el reintento del ajustador al leer el caso. Un fallo se registra y no se propaga."""
    if _VIGIA is None:
        return
    try:
        await _VIGIA.retry_if_needed(tenant_id, case_id, state)
    except Exception as error:  # noqa: BLE001 -- el reintento es de fondo: leer el caso no depende de el
        observability.emit(
            "inbox.adjuster_retry_failed",
            tenant_id=tenant_id,
            case_id=case_id,
            error=type(error).__name__,
        )
