"""Quien despierta al ajustador: al derivarse un caso y al leerlo, y lo que muestra de su corrida.

El proceso (`pipeline.run_case`) decide un caso; este modulo decide **cuando** correrlo y lo hace
de fondo, sin que quien derivo o quien leyo espere (un caso tarda del orden de un minuto).

- **Al derivar** (`on_derived`): agenda la corrida.
- **Al leer el caso** (`retry_if_needed`, A1): si esta derivado y su corrida no existe, fallo con
  intentos pendientes, quedo esperando el cupo y hoy hay, se perdio (el proceso se cayo y su fila
  lleva demasiado `running`) o decidio pero no alcanzo a registrar el cierre, la agenda otra vez.
  La pantalla del visitante consulta cada pocos segundos: una corrida que va bien no dispara nada.

Un mismo proceso nunca lleva dos veces el mismo caso (`_en_curso`); entre procesos lo impide la
llave primaria de `adjuster_run` (`repository.open_run`). Las tareas de fondo se guardan: una tarea
sin referencia puede recogerla el recolector de basura a medio camino.
"""

from __future__ import annotations

import asyncio

from untangle import observability
from untangle.adjuster import pipeline, quota, repository
from untangle.adjuster.config import AdjusterConfig
from untangle.adjuster.models import AdjusterRun, RunStatus, RunStep, split_summary
from untangle.adjuster.ports import AdjusterPorts
from untangle.case_record.models import CaseState
from untangle.inbox.adjuster_view import (
    AdjusterRunOut,
    AdjusterSourceOut,
    AdjusterStepOut,
)
from untangle.tenancy.models import TenantId


def view_of(run: AdjusterRun) -> AdjusterRunOut:
    """La corrida con la forma con que la bandeja la muestra."""
    titular, explicacion = split_summary(run.summary)
    return AdjusterRunOut(
        status=run.status.value,
        attempt=run.attempt,
        steps=tuple(_paso(paso) for paso in run.steps),
        decision=run.decision,
        headline=titular or None,
        explanation=explicacion or None,
        searches_used=run.searches_used,
        updated_at=run.updated_at.isoformat(),
    )


def _paso(paso: RunStep) -> AdjusterStepOut:
    return AdjusterStepOut(
        id=paso.id.value,
        title_key=paso.title_key,
        text=paso.text,
        sources=tuple(
            AdjusterSourceOut(kind=f.kind.value, ref=f.ref, label=f.label, url=f.url)
            for f in paso.sources
        ),
    )


async def needs_retry(
    run: AdjusterRun | None, *, state: CaseState, ports: AdjusterPorts, config: AdjusterConfig
) -> bool:
    """Si un caso con esa corrida vale la pena volver a intentarlo ahora."""
    if state is not CaseState.DERIVED:
        return False
    if run is None:
        return True
    ahora = ports.now()
    if run.status is RunStatus.RUNNING:
        return ahora - run.updated_at >= config.running_stale_after
    if run.status is RunStatus.FAILED:
        return run.attempt < config.attempts
    if run.status is RunStatus.CAPPED:
        return (await quota.cases_today(config, now=ahora)).remaining > 0
    # Decidida y el caso sigue derivado: el cierre no se registro. Repetirlo no llama al modelo.
    return True


class AdjusterService:
    """El ajustador enchufado a la raiz de composicion: oyente de la derivacion y vigia del caso."""

    def __init__(self, *, ports: AdjusterPorts, config: AdjusterConfig) -> None:
        self._puertos = ports
        self._config = config
        self._en_curso: set[tuple[TenantId, str]] = set()
        self._tareas: set[asyncio.Task[None]] = set()

    async def on_derived(self, tenant_id: TenantId, case_id: str) -> None:
        """Un caso acaba de derivarse: lo agenda y devuelve sin esperarlo."""
        self.schedule(tenant_id, case_id)

    async def read(self, tenant_id: TenantId, case_id: str) -> AdjusterRunOut | None:
        corrida = await repository.read(tenant_id, case_id)
        return None if corrida is None else view_of(corrida)

    async def retry_if_needed(self, tenant_id: TenantId, case_id: str, state: CaseState) -> None:
        if (tenant_id, case_id) in self._en_curso:
            return
        corrida = await repository.read(tenant_id, case_id)
        if await needs_retry(corrida, state=state, ports=self._puertos, config=self._config):
            self.schedule(tenant_id, case_id)

    def schedule(self, tenant_id: TenantId, case_id: str) -> bool:
        """Agenda la corrida si este proceso no la lleva ya. Devuelve si la agendo."""
        clave = (tenant_id, case_id)
        if clave in self._en_curso:
            return False
        self._en_curso.add(clave)
        tarea = asyncio.get_running_loop().create_task(self._correr(clave))
        self._tareas.add(tarea)
        tarea.add_done_callback(self._tareas.discard)
        return True

    async def _correr(self, clave: tuple[TenantId, str]) -> None:
        tenant_id, case_id = clave
        try:
            await pipeline.run_case(tenant_id, case_id, ports=self._puertos, config=self._config)
        except Exception as error:  # noqa: BLE001 -- una tarea de fondo que se cae en silencio deja el caso sin atender; el reintento al leerlo lo recoge
            observability.emit(
                "adjuster.task_failed",
                tenant_id=tenant_id,
                case_id=case_id,
                error=type(error).__name__,
            )
        finally:
            self._en_curso.discard(clave)

    async def stop(self) -> None:
        """Cancela lo que corre al apagar el proceso. Una corrida cortada queda `running` y la
        reabre el siguiente arranque cuando caduca (`running_stale_seconds`)."""
        pendientes = list(self._tareas)
        for tarea in pendientes:
            tarea.cancel()
        await asyncio.gather(*pendientes, return_exceptions=True)

    async def drain(self) -> None:
        """Espera a que terminen las tareas agendadas. Para el cierre ordenado y las pruebas."""
        if self._tareas:
            await asyncio.gather(*self._tareas, return_exceptions=True)
