"""El acceso a datos de `adjuster_run`: abrir, anexar un paso, cerrar y leer.

**Ninguna conexion propia.** Toda consulta pasa por el punto unico de sesion con la aseguradora
fijada; la politica de fila hace el resto, y la prueba de aislamiento lo comprueba contra la base.

**Abrir es idempotente y dice quien manda.** Dos arranques del mismo caso chocan en la llave
primaria: gana uno, y `OpenedRun.started` es verdadero solo para ese. Una corrida decidida no se
reabre nunca; una que esta corriendo tampoco (hay otro proceso en ello); una capada se reabre sin
gastar intento --nunca llego a intentar--; una fallida gasta uno, hasta el maximo que declara la
configuracion.

**Una corrida que corre y no avanza se reabre.** Si el proceso que la llevaba se cayo, su fila
sigue en `running` para siempre y nadie la tomaria. Pasado `stale_after` sin que anexe un paso
(`updated_at`), cuenta como un intento perdido: se reabre gastando uno y, si ya no quedan, se cierra
como fallida con `run_abandoned`. Dos arranques simultaneos siguen sin trabajar a la vez: la fila se
lee `FOR UPDATE` y el segundo ve la corrida ya renovada.

**Cerrar es de una sola vez.** Solo una corrida `running` se cierra. Cerrarla otra vez con lo mismo
devuelve lo que ya hay; cerrarla con otra cosa levanta `RunConflictError`, porque dos procesos que
creen haber decidido el mismo caso distinto es exactamente lo que la idempotencia del cierre
existe para no dejar pasar.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from untangle.adjuster.errors import ErrorKind
from untangle.adjuster.models import AdjusterRun, OpenedRun, RunStatus, RunStep
from untangle.inbox.actions import InboxAction
from untangle.tenancy import api as tenancy
from untangle.tenancy.models import TenantId


class RunNotRunningError(RuntimeError):
    """Se intento anexar o cerrar una corrida que no esta corriendo."""


class RunConflictError(RuntimeError):
    """La corrida ya se cerro, y de otra manera que la que se pide."""


class RunNotFoundError(LookupError):
    """No hay corrida para ese caso."""


_LEER = """
    SELECT tenant_id, case_id, status, attempt, steps, decision, summary, model, searches_used,
           error_kind, created_at, updated_at
      FROM adjuster_run
     WHERE tenant_id = :tenant_id AND case_id = :case_id
"""

# `FOR UPDATE`: quien decide si reabrir lee la fila "de antes" y nadie la cambia entre la lectura
# y la escritura. Sin fila no hay nada que bloquear y la llave primaria decide la carrera.
_LEER_PARA_CAMBIAR = _LEER + " FOR UPDATE"

_ABRIR = """
    INSERT INTO adjuster_run (tenant_id, case_id, status, attempt, steps, model, searches_used,
                              created_at, updated_at)
    VALUES (:tenant_id, :case_id, 'running', 1, CAST('[]' AS jsonb), :model, 0, :now, :now)
    ON CONFLICT (tenant_id, case_id) DO NOTHING
    RETURNING tenant_id, case_id, status, attempt, steps, decision, summary, model, searches_used,
           error_kind, created_at, updated_at
"""

_REABRIR = """
    UPDATE adjuster_run
       SET status = 'running', attempt = :attempt, steps = CAST('[]' AS jsonb), decision = NULL,
           summary = NULL, model = :model, searches_used = 0, error_kind = NULL, updated_at = :now
     WHERE tenant_id = :tenant_id AND case_id = :case_id
    RETURNING tenant_id, case_id, status, attempt, steps, decision, summary, model, searches_used,
           error_kind, created_at, updated_at
"""

_ABANDONAR = """
    UPDATE adjuster_run
       SET status = 'failed', error_kind = :error_kind, updated_at = :now
     WHERE tenant_id = :tenant_id AND case_id = :case_id AND status = 'running'
    RETURNING tenant_id, case_id, status, attempt, steps, decision, summary, model, searches_used,
           error_kind, created_at, updated_at
"""

# Un paso no se anexa dos veces: el segundo intento de anexar el mismo identificador es un
# reintento del mismo trabajo y no cambia nada.
_ANEXAR = """
    UPDATE adjuster_run
       SET steps = steps || jsonb_build_array(CAST(:step AS jsonb)),
           searches_used = COALESCE(:searches_used, searches_used),
           updated_at = :now
     WHERE tenant_id = :tenant_id AND case_id = :case_id AND status = 'running'
       AND NOT EXISTS (
           SELECT 1 FROM jsonb_array_elements(steps) AS paso WHERE paso->>'id' = :step_id)
    RETURNING tenant_id, case_id, status, attempt, steps, decision, summary, model, searches_used,
           error_kind, created_at, updated_at
"""

_CERRAR = """
    UPDATE adjuster_run
       SET status = :status, decision = :decision, summary = :summary,
           searches_used = COALESCE(:searches_used, searches_used), error_kind = :error_kind,
           updated_at = :now
     WHERE tenant_id = :tenant_id AND case_id = :case_id AND status = 'running'
    RETURNING tenant_id, case_id, status, attempt, steps, decision, summary, model, searches_used,
           error_kind, created_at, updated_at
"""


def _corrida(fila: Mapping[str, Any]) -> AdjusterRun:
    pasos = fila["steps"]
    # Segun el driver, `jsonb` llega ya interpretado o como texto.
    datos = json.loads(pasos) if isinstance(pasos, str) else pasos
    return AdjusterRun.model_validate({**fila, "steps": datos})


async def read(tenant_id: TenantId, case_id: str) -> AdjusterRun | None:
    """La corrida del caso, o nada si el ajustador no ha empezado."""
    async with tenancy.session_for(tenant_id) as sesion:
        fila = await tenancy.fetch_one(sesion, _LEER, tenant_id=tenant_id, case_id=case_id)
    return None if fila is None else _corrida(fila)


async def open_run(  # noqa: PLR0913 -- aseguradora, caso, modelo, intentos, caducidad y reloj
    tenant_id: TenantId,
    case_id: str,
    *,
    model: str,
    max_attempts: int,
    stale_after: timedelta,
    now: datetime,
) -> OpenedRun:
    """Crea la corrida del caso o la reabre, y dice si esta llamada es la duena del trabajo.

    Idempotente: abrirla dos veces seguidas deja una corrida y un solo `started`. Una que corre
    desde hace mas de `stale_after` sin avanzar es de un proceso caido y se reabre.
    """
    async with tenancy.session_for(tenant_id) as sesion:
        creada = await tenancy.fetch_one(
            sesion, _ABRIR, tenant_id=tenant_id, case_id=case_id, model=model, now=now
        )
        if creada is not None:
            return OpenedRun(run=_corrida(creada), started=True)

        fila = await tenancy.fetch_one(
            sesion, _LEER_PARA_CAMBIAR, tenant_id=tenant_id, case_id=case_id
        )
        if fila is None:  # pragma: no cover -- el conflicto de la insercion garantiza que existe
            msg = f"la corrida del caso '{case_id}' choco al abrirse y no se pudo releer"
            raise RunNotFoundError(msg)
        actual = _corrida(fila)

        if actual.status is RunStatus.DECIDED:
            return OpenedRun(run=actual, started=False)
        perdida = actual.status is RunStatus.RUNNING
        if perdida and now - actual.updated_at < stale_after:
            return OpenedRun(run=actual, started=False)
        if actual.attempt >= max_attempts and actual.status in {
            RunStatus.FAILED,
            RunStatus.RUNNING,
        }:
            if not perdida:
                return OpenedRun(run=actual, started=False)
            # Sin intentos que gastar, la corrida perdida deja de aparentar que sigue en curso.
            cerrada = await tenancy.fetch_one(
                sesion,
                _ABANDONAR,
                tenant_id=tenant_id,
                case_id=case_id,
                error_kind=ErrorKind.RUN_ABANDONED.value,
                now=now,
            )
            if cerrada is None:  # pragma: no cover -- la fila esta bloqueada por esta transaccion
                raise RunNotFoundError(case_id)
            return OpenedRun(run=_corrida(cerrada), started=False)

        # Una capada nunca llego a intentar: reabrirla no gasta intento. Una fallida o una
        # perdida si.
        intento = actual.attempt if actual.status is RunStatus.CAPPED else actual.attempt + 1
        reabierta = await tenancy.fetch_one(
            sesion,
            _REABRIR,
            tenant_id=tenant_id,
            case_id=case_id,
            attempt=intento,
            model=model,
            now=now,
        )
    if reabierta is None:  # pragma: no cover -- la fila esta bloqueada por esta transaccion
        raise RunNotFoundError(case_id)
    return OpenedRun(run=_corrida(reabierta), started=True)


async def append_step(
    tenant_id: TenantId,
    case_id: str,
    step: RunStep,
    *,
    now: datetime,
    searches_used: int | None = None,
) -> AdjusterRun:
    """Anexa un paso a la corrida que esta corriendo. Anexar el mismo paso otra vez no cambia nada.

    `searches_used` es el total de busquedas hasta ahora (no un incremento); sin el, no se toca.
    """
    async with tenancy.session_for(tenant_id) as sesion:
        fila = await tenancy.fetch_one(
            sesion,
            _ANEXAR,
            tenant_id=tenant_id,
            case_id=case_id,
            step=json.dumps(step.model_dump(mode="json")),
            step_id=step.id.value,
            searches_used=searches_used,
            now=now,
        )
        if fila is None:
            fila = await tenancy.fetch_one(sesion, _LEER, tenant_id=tenant_id, case_id=case_id)
            if fila is None:
                msg = f"no hay corrida para el caso '{case_id}'"
                raise RunNotFoundError(msg)
            if _corrida(fila).status is not RunStatus.RUNNING:
                msg = f"la corrida del caso '{case_id}' no esta corriendo: no admite mas pasos"
                raise RunNotRunningError(msg)
    return _corrida(fila)


async def close_decided(  # noqa: PLR0913 -- aseguradora, caso, decision, explicacion, busquedas y reloj
    tenant_id: TenantId,
    case_id: str,
    *,
    decision: InboxAction,
    summary: str,
    now: datetime,
    searches_used: int | None = None,
) -> AdjusterRun:
    """Cierra la corrida como decidida, con su decision y la explicacion que ve el visitante.

    Se llama **antes** de registrar el cierre del caso (A5): la explicacion queda fija y un
    reintento la reusa en vez de generarla otra vez.
    """
    return await _cerrar(
        tenant_id,
        case_id,
        status=RunStatus.DECIDED,
        decision=decision,
        summary=summary,
        error_kind=None,
        now=now,
        searches_used=searches_used,
    )


async def close_capped(
    tenant_id: TenantId, case_id: str, *, now: datetime, searches_used: int | None = None
) -> AdjusterRun:
    """Cierra la corrida como capada: el tope diario se alcanzo y el caso espera."""
    return await _cerrar(
        tenant_id,
        case_id,
        status=RunStatus.CAPPED,
        decision=None,
        summary=None,
        error_kind=None,
        now=now,
        searches_used=searches_used,
    )


async def close_failed(
    tenant_id: TenantId,
    case_id: str,
    *,
    error_kind: str,
    now: datetime,
    searches_used: int | None = None,
) -> AdjusterRun:
    """Cierra la corrida como fallida, con el tipo de su error. El caso sigue en revision."""
    return await _cerrar(
        tenant_id,
        case_id,
        status=RunStatus.FAILED,
        decision=None,
        summary=None,
        error_kind=error_kind,
        now=now,
        searches_used=searches_used,
    )


async def _cerrar(  # noqa: PLR0913 -- el cierre lleva todo lo que distingue un estado de otro
    tenant_id: TenantId,
    case_id: str,
    *,
    status: RunStatus,
    decision: InboxAction | None,
    summary: str | None,
    error_kind: str | None,
    now: datetime,
    searches_used: int | None,
) -> AdjusterRun:
    async with tenancy.session_for(tenant_id) as sesion:
        fila = await tenancy.fetch_one(
            sesion,
            _CERRAR,
            tenant_id=tenant_id,
            case_id=case_id,
            status=status.value,
            decision=None if decision is None else decision.value,
            summary=summary,
            error_kind=error_kind,
            searches_used=searches_used,
            now=now,
        )
        if fila is not None:
            return _corrida(fila)
        previa = await tenancy.fetch_one(sesion, _LEER, tenant_id=tenant_id, case_id=case_id)

    if previa is None:
        msg = f"no hay corrida para el caso '{case_id}'"
        raise RunNotFoundError(msg)
    actual = _corrida(previa)
    # Cerrar otra vez con lo mismo es un reintento y devuelve lo que ya hay.
    if (actual.status, actual.decision, actual.summary, actual.error_kind) == (
        status,
        decision,
        summary,
        error_kind,
    ):
        return actual
    if actual.status is RunStatus.RUNNING:  # pragma: no cover -- el UPDATE la habria cerrado
        raise RunNotRunningError(case_id)
    msg = (
        f"la corrida del caso '{case_id}' ya esta '{actual.status.value}' y se pidio cerrarla "
        f"como '{status.value}': un caso no se decide dos veces de maneras distintas"
    )
    raise RunConflictError(msg)
