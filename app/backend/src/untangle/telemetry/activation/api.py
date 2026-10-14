"""La superficie publica de la telemetria de activacion (U6, US5.16).

**No es una ruta HTTP**: es una llamada en proceso. El hito lo decide el servidor
al procesar el turno --el chat informa el primer mensaje y el tercer turno (U13),
la vista por enlace el ciclo cerrado (U14)--, no el navegador, que podria
inventarlo (`frontend-components.md`, puntos de integracion).

Tres promesas, las tres comprobadas por pruebas:

1. **Cada hito cuenta una sola vez por sesion** (BR8.1). Lo cumple la
   transaccion del repositorio, no esta funcion.
2. **El chequeo periodico y el corredor de evaluaciones no cuentan** (BR8.4):
   quien informa dice de donde viene el trafico, y solo el de un visitante se
   registra.
3. **Registrar un hito nunca rompe ni demora el turno** (BR8.3). Cualquier fallo
   --base caida, base lenta, fila rechazada, error inesperado-- se convierte en
   un evento con el hito y el tipo de error, y la llamada devuelve `FAILED` sin
   lanzar. El conteo de ese dia queda por debajo, y el evento lo dice.

**Lo que el evento no lleva**: el resumen de la clave del navegador. Es el
identificador de una sesion, y ningun log, traza ni reporte de U6 apunta a una
(OBS-U6.6). La aseguradora si va: no es de nadie.

**Lo que se lee**: solo el conteo por dia (BR8.5). El avance por sesion no tiene
ruta de lectura.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from untangle import observability
from untangle.telemetry.activation import repository
from untangle.telemetry.activation.models import (
    ActivationDailyCount,
    ActivationMilestone,
    ActivationSource,
    MilestoneOutcome,
    RecordFailure,
)
from untangle.telemetry.traces import api as trazas

__all__ = [
    "RECORD_TIMEOUT_S",
    "ActivationDailyCount",
    "ActivationMilestone",
    "ActivationSource",
    "MilestoneOutcome",
    "RecordFailure",
    "classify_failure",
    "daily_counts",
    "record_milestone",
]

#: Cuanto puede esperar el turno a que el hito quede escrito, en segundos.
#:
#: Doscientos cincuenta milisegundos. Acota lo que una base lenta le puede costar
#: al turno que informa el hito --menos de una decima parte de los tres segundos
#: de NFR4-- y deja margen de sobra para las dos escrituras de fila unica, que en
#: condiciones normales tardan unos pocos milisegundos, incluida la primera
#: conexion del grupo. Pasado ese tiempo, el hito se da por perdido con su
#: evento: preferimos un conteo corto que un turno lento (BR8.3).
RECORD_TIMEOUT_S = 0.25

#: Los nombres de clase que dicen "la base no estaba". Se reconocen por nombre y
#: no importando el cliente de base: el contrato `sesion-unica-de-base-de-datos`
#: prohibe importarlo fuera del punto unico de sesion, y esta prohibicion importa
#: mas que la elegancia de un `isinstance`.
_INDISPONIBLE = frozenset(
    {"OperationalError", "InterfaceError", "SessionNotConfiguredError", "ConnectionError"}
)

#: Y los que dicen "la base rechazo la fila": una sesion que no es una clave de
#: esa aseguradora, o una aseguradora que no esta en la configuracion.
_RECHAZO = frozenset({"IntegrityError", "UnknownTenantError"})


def classify_failure(error: BaseException) -> RecordFailure:
    """El tipo de fallo, de la taxonomia cerrada (OBS-U6.4). Pura: se prueba sin base."""
    if isinstance(error, TimeoutError):
        return RecordFailure.TIMEOUT
    nombres = {clase.__name__ for clase in type(error).__mro__}
    if nombres & _RECHAZO:
        return RecordFailure.REJECTED
    if nombres & _INDISPONIBLE or isinstance(error, OSError):
        return RecordFailure.UNAVAILABLE
    return RecordFailure.UNEXPECTED


async def record_milestone(
    *,
    tenant_id: str,
    visitor_key_hash: str,
    milestone: ActivationMilestone,
    source: ActivationSource,
    now: datetime | None = None,
) -> MilestoneOutcome:
    """Informa un hito de una sesion. **Nunca lanza** (BR8.3).

    `source` no tiene valor por omision a proposito: quien informa tiene que
    decir si el trafico es de un visitante. Un valor por omision `VISITOR` haria
    que el corredor de evaluaciones contara como persona el dia que alguien
    olvidara pasarlo (BR8.4).
    """
    if source is not ActivationSource.VISITOR:
        return MilestoneOutcome.NOT_A_SESSION

    momento = now if now is not None else datetime.now(UTC)
    try:
        async with asyncio.timeout(RECORD_TIMEOUT_S):
            contado = await repository.record(
                tenant_id=tenant_id,
                visitor_key_hash=visitor_key_hash,
                milestone=milestone,
                reached_at=momento,
            )
    except Exception as error:  # noqa: BLE001 -- el turno no puede romperse por esto (BR8.3)
        # Se atrapa **cualquier** fallo a proposito: una lista de tipos conocidos
        # dejaria escapar el siguiente, y aqui la promesa es para todos. El fallo
        # no se traga: sale como evento con su tipo de la taxonomia cerrada, el
        # nombre de la clase para quien depura, y la traza del turno si la hay.
        observability.emit(
            "activation.milestone_failed",
            tenant_id=tenant_id,
            milestone=milestone.value,
            error_kind=classify_failure(error).value,
            error_type=type(error).__name__,
            trace_id=trazas.current_trace_id(),
        )
        return MilestoneOutcome.FAILED

    return MilestoneOutcome.COUNTED if contado else MilestoneOutcome.ALREADY_REACHED


async def daily_counts() -> tuple[ActivationDailyCount, ...]:
    """El conteo por dia, aseguradora e hito: lo unico que se publica (BR8.5)."""
    return await repository.daily_counts()
