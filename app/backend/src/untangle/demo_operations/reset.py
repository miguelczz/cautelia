"""La orquestacion del reinicio nocturno y la regla de las 24 horas (US5.15).

**Pura sobre el contrato.** Recibe los purgadores, el reloj y el corte como
argumentos, y devuelve que borro cada uno y cual fallo. No abre sesion, no mira el
reloj del proceso y no escribe ninguna sentencia de borrado (BR2.3, BR2.4): una
consulta escrita aqui seria el sitio donde la retencion deja de estar acotada sin
que nadie lo note, porque nadie la revisaria al anadir una tabla.

Que sea pura es lo que deja comprobar el camino del fallo con dobles, que es el
que importa: contra una base de verdad habria que romperla a proposito.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Final

from untangle import observability
from untangle.copy_catalog.api import CopyKey
from untangle.demo_operations.models import PurgerRow, ResetOutcome, ResetRun, outcome_of
from untangle.tenancy.models import VisitorDataPurger

#: El aviso que recibe una conversacion viva cuando el reinicio borra su caso
#: (BR2.6): su mensaje siguiente abre un caso nuevo, sin error.
RESET_NOTICE: Final = CopyKey("demo.reset.conversation_notice")

#: Lo que lee quien llega con las superficies estrechadas (BR3.2).
SURFACES_CLOSED: Final = CopyKey("demo.reset.surfaces_closed")

#: Cuanto puede pasar desde el ultimo reinicio exitoso antes de dejar de aceptar
#: casos nuevos (AC5.15.5).
RESET_WINDOW: Final = timedelta(hours=24)

#: El evento que sale cuando una corrida no termino limpia (BR3.1). Lleva el
#: identificador de la corrida, que es lo que permite encontrarla.
ALERT_EVENT: Final = "demo_operations.reset_alert"


class EmptyRegistryError(ValueError):
    """Se pidio un reinicio sin ningun purgador.

    No es una corrida que fallo: es un registro mal compuesto. Devolver un
    registro de corrida `succeeded` sobre cero purgadores diria que la demo
    esta limpia sin haber borrado nada.
    """


async def run_reset(
    purgers: Sequence[VisitorDataPurger],
    *,
    clock: Callable[[], datetime],
    older_than: datetime,
    reset_run_id: str,
    dry_run: bool = False,
) -> ResetRun:
    """Llama a cada purgador **en el orden del registro** y deja el registro de la corrida.

    Un purgador que levanta no detiene a los siguientes ni se traga: queda en su
    fila con el tipo de su error, y la corrida sigue. Detener a los demas dejaria
    sin borrar lo que si se podia borrar, y borrarlos sin dejar rastro del fallo
    dejaria una corrida que parece limpia (REL-U20.1, REL-U20.3).

    Un reinicio que no termino limpio sale como alerta con el identificador de la
    corrida (REL-U20.2). El reintento es volver a llamar a esta funcion: los
    purgadores borran lo anterior al corte, asi que repetir no empeora nada
    (REL-U20.4).
    """
    if not purgers:
        msg = "el reinicio recibio un registro de purgadores vacio"
        raise EmptyRegistryError(msg)

    empezo = clock()
    filas = [await _llamar(purgador, clock, older_than, dry_run) for purgador in purgers]
    corrida = ResetRun(
        reset_run_id=reset_run_id,
        started_at=empezo,
        finished_at=clock(),
        outcome=outcome_of(tuple(filas)),
        purgers=tuple(filas),
    )

    if corrida.outcome is not ResetOutcome.SUCCEEDED:
        observability.emit(
            ALERT_EVENT,
            reset_run_id=corrida.reset_run_id,
            outcome=corrida.outcome.value,
            failed=[
                {"purger": fila.name, "error_type": fila.error_type} for fila in corrida.failures
            ],
        )
    return corrida


async def _llamar(
    purgador: VisitorDataPurger,
    clock: Callable[[], datetime],
    older_than: datetime,
    dry_run: bool,
) -> PurgerRow:
    inicio = clock()
    try:
        resultado = await purgador.purge(older_than=older_than, dry_run=dry_run)
    except Exception as error:  # noqa: BLE001 -- el fallo de uno no detiene a los demas; queda en su fila
        return PurgerRow(
            name=purgador.name,
            tables=tuple(purgador.tables),
            duration_seconds=_duracion(inicio, clock()),
            error_type=type(error).__name__,
        )
    return PurgerRow(
        name=purgador.name,
        tables=tuple(purgador.tables),
        deleted=resultado.deleted,
        kept=resultado.kept,
        duration_seconds=_duracion(inicio, clock()),
    )


def _duracion(inicio: datetime, fin: datetime) -> float:
    return max((fin - inicio).total_seconds(), 0.0)


def last_successful_reset(runs: Sequence[ResetRun]) -> ResetRun | None:
    """La ultima corrida `succeeded`, por cuando **termino**. Nunca el ultimo intento."""
    exitosas = [corrida for corrida in runs if corrida.outcome is ResetOutcome.SUCCEEDED]
    return max(exitosas, key=lambda corrida: corrida.finished_at, default=None)


def accepts_new_cases(
    runs: Sequence[ResetRun],
    *,
    now: datetime,
    window: timedelta = RESET_WINDOW,
) -> bool:
    """Si el chat y la voz publicos aceptan **casos nuevos** (BR3.2).

    El reloj cuenta desde el ultimo reinicio **exitoso**, no desde el ultimo
    intento: tres intentos fallidos seguidos no reinician el contador, y es justo
    el caso en el que la retencion dejo de estar acotada. Por eso la funcion
    recibe el historial y elige ella la corrida: atarla a "la ultima" no se puede
    escribir desde fuera. `partial` tampoco cuenta: quedan datos sin borrar.

    Cierra en las tres situaciones en las que no puede afirmar que la retencion
    esta acotada: pasaron 24 horas o mas, no hay ningun reinicio exitoso conocido,
    o el ultimo exitoso es **posterior** a `now` (relojes en desacuerdo: un dato
    corrupto hacia el futuro mantendria la demo abierta para siempre).

    Solo decide sobre lo **nuevo**. Una conversacion o una llamada ya abierta no
    entra en esta decision y termina normalmente (BR3.3, respuesta Q1): quien
    cierra una conversacion abierta por esta funcion esta usandola mal.
    """
    if now.tzinfo is None:
        msg = "`now` no trae zona horaria: no se puede comparar con el ultimo reinicio"
        raise ValueError(msg)

    ultima = last_successful_reset(runs)
    if ultima is None:
        return False
    transcurrido = now - ultima.finished_at
    return timedelta(0) <= transcurrido < window
