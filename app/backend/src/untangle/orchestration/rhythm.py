"""Los dos ritmos del grafo (paso 5 de U12, BR2.1 a BR2.4).

Tres piezas, cada una la mitad minima de una regla:

- `run_turn_controls` es **el manejador del turno** que BR2.3 nombra: dentro
  del turno corren solo los tres controles baratos -- la guardia de salida y
  las dos detecciones de `read_turn_signals` (peticion de persona y emergencia;
  la tercera senal que ese mismo modulo calcula, la pregunta de identidad, no
  es una de las tres de BR2.3, pero llega gratis en la misma pasada de
  patrones) --. Nunca la verificacion de poliza (`policy_rag`), las reglas
  (`rules`) ni la revision completa de cumplimiento
  (`compliance.controls.api.final_review`): este modulo no los importa, y por
  eso la prueba de BR2.3 puede analizar su arbol de importaciones -- no su
  texto -- y encontrar que no estan.
- `launch_background` es BR2.2: lanza el trabajo de fondo con `asyncio.create_task`
  (o el `task_factory` que le pasen, para las pruebas) y no lo espera. El turno
  que lo llama sigue de inmediato a lo que sea que haga despues.
- `waiting_response` es BR2.4: la frase de espera, si el ritmo de fondo
  todavia tiene algo pendiente. Decidir **cuando** llamarla -- que la persona
  este preguntando por su cobertura, no cualquier turno con algo pendiente -- es
  del desvio de cobertura del paso 7 (BR4.2, BR4.3); esta funcion solo sabe
  responder la pregunta "hay algo pendiente que justifique la frase", no cuando
  preguntarla.

Lo que este paso NO construye: `preload(case_id)`, `handle_turn` y `resume_case`
con la forma exacta de C-14 son del paso 7, que ya tiene el `GraphState` armado
y el grafo real para invocar. Aqui la precarga (BR2.1) es el mismo primitivo que
BR2.2 -- lanzar sin esperar -- aplicado a la cadena de fondo; el paso 7 lo
invoca con el nodo real en cuanto la captura confirma la identidad.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from untangle import observability
from untangle.base import Locale
from untangle.compliance.controls.api import (
    GuardResult,
    TurnSignals,
    guard_output,
    read_turn_signals,
)
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration import phrases
from untangle.telemetry.traces.models import NodeName
from untangle.tenancy.models import TenantId

#: Como se lanza el fondo. `asyncio.create_task` por omision; las pruebas pasan
#: una que registra la llamada en vez de programarla de verdad en el bucle de
#: eventos. Toma una corrutina (lo que `asyncio.create_task` exige) y devuelve
#: algo que se puede esperar despues -- quien lanzo puede esperarlo mas tarde,
#: y BR2.2 es justo que no lo espere ahora.
type TaskFactory[T] = Callable[[Coroutine[Any, Any, T]], Awaitable[T]]


@dataclass(frozen=True)
class TurnCheapControls:
    """Lo que corren los tres controles baratos del turno, y nada mas (BR2.3)."""

    signals: TurnSignals
    guard: GuardResult


async def run_turn_controls(
    text: str,
    *,
    tenant_id: TenantId,
    language: Locale,
    case_id: str | None = None,
) -> TurnCheapControls:
    """Los tres controles baratos del turno: las dos detecciones y la guardia (BR2.3).

    Nunca llama la verificacion de poliza, las reglas ni la revision completa de
    cumplimiento -- este modulo no las importa, y la prueba de BR2.3 analiza el
    arbol de importaciones de este archivo para comprobarlo.
    """
    signals = await read_turn_signals(text)
    guard = await guard_output(text, tenant_id=tenant_id, language=language, case_id=case_id)
    return TurnCheapControls(signals=signals, guard=guard)


def launch_background[T](
    work: Coroutine[Any, Any, T],
    *,
    task_factory: TaskFactory[T] | None = None,
) -> Awaitable[T]:
    """BR2.1, BR2.2: lanza `work` sin esperarlo. Quien llama sigue de inmediato.

    `work` es la corrutina que hace el trabajo de fondo (hoy, en esta unidad,
    invocar el ejecutor sobre un nodo de ritmo `background`; mas adelante, la
    cadena entera del grafo desde `policy_verification`). Esta funcion no sabe
    -- ni le hace falta saber -- que hace `work`: solo que no se espera **aqui**.
    Devuelve algo que se puede esperar mas tarde, si hace falta (una prueba que
    quiera comprobar que el fondo si termina, por ejemplo); BR2.2 es que nadie lo
    haga en el camino del turno.
    """
    if task_factory is None:
        task_factory = asyncio.create_task
    lanzada = task_factory(work)
    # **Lo que se lanza y no se espera tiene que dejar rastro si se rompe.** Sin
    # esto, un fallo del ritmo de fondo no dejaba ni un evento: la tarea moria,
    # `asyncio` escribia "Task exception was never retrieved" en la salida del
    # proceso --si alguien la estaba mirando-- y el caso se quedaba sin su valor
    # distinguible. La regla del proyecto lo pide al reves: todo fallo deja un
    # valor en el caso y un evento en la traza. El valor lo escribe el ejecutor
    # cuando el nodo falla; el evento es este, y cubre lo que se rompe **antes**
    # de que el ejecutor llegue a correr.
    #
    # Se registra solo sobre una `Task` de verdad: un `task_factory` de prueba
    # puede devolver cualquier `Awaitable`, y exigirle la interfaz de `Task` seria
    # obligar a cada prueba a imitarla para nada.
    if isinstance(lanzada, asyncio.Task):
        lanzada.add_done_callback(_reportar_fallo_de_fondo)
    return lanzada


def _reportar_fallo_de_fondo(tarea: asyncio.Task[Any]) -> None:
    """Recoge la excepcion de una tarea de fondo y la deja en la traza."""
    if tarea.cancelled():
        return
    error = tarea.exception()
    if error is not None:
        observability.emit(
            "orchestration.background_failed",
            error_type=type(error).__name__,
        )


def waiting_response(
    pending: frozenset[NodeName], *, language: Locale
) -> tuple[CopyKey, str] | None:
    """BR2.4: la frase de espera del catalogo, si `pending` no esta vacio.

    `pending` es lo que el ritmo de fondo todavia no devolvio
    (`GraphState.pending_background`). Que la pregunta que llego sea de
    cobertura -- y por tanto que esta frase corresponda -- lo decide el paso 7;
    aqui solo se resuelve la frase cuando alguien ya decidio que hace falta.
    """
    if not pending:
        return None
    return phrases.WAITING, phrases.waiting_text(locale=language)


__all__ = [
    "TaskFactory",
    "TurnCheapControls",
    "launch_background",
    "run_turn_controls",
    "waiting_response",
]
