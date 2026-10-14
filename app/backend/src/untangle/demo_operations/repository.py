"""Donde queda el registro de cada corrida del reinicio, y de donde se lee (TECH-U20.4).

**Ninguna conexion propia.** Toda consulta pasa por el punto unico de sesion de
U2 y los parametros se ligan. **Sin aseguradora fijada**: una corrida del
reinicio barre las tres y no es de ninguna, igual que el libro mayor del gasto.

**Las dos sentencias de la escritura son una transaccion.** Una corrida sin sus
filas de purgador no es media corrida: es un registro que dice que algo corrio
sin decir que hizo, y es justo el dato que la alerta necesita leer.

## Lo que esta funcion no hace, y es intencionado

No borra nada: el reinicio nocturno **no se purga a si mismo**. Si lo hiciera, el
contador de 24 horas de BR3.2 se quedaria sin memoria inmediatamente despues de
cada corrida, que es el estado en el que las superficies publicas cierran.
"""

from __future__ import annotations

from untangle.demo_operations.models import PurgerRow, ResetOutcome, ResetRun
from untangle.tenancy import session as db

GUARDAR_CORRIDA = """
    INSERT INTO reset_run (reset_run_id, started_at, finished_at, outcome)
    VALUES (:reset_run_id, :started_at, :finished_at, :outcome)
"""

GUARDAR_FILA = """
    INSERT INTO reset_run_purger (
        reset_run_id, purger, call_order, deleted, kept, duration_ms, error_type
    )
    VALUES (
        :reset_run_id, :purger, :call_order, :deleted, :kept, :duration_ms, :error_type
    )
"""

#: La unica consulta caliente, y pregunta **solo por las exitosas**.
#:
#: No es un atajo: el reloj de BR3.2 cuenta desde el ultimo reinicio exitoso, asi
#: que una consulta que devolviera "la ultima corrida" y se la pasara a la regla
#: seria la forma de implementar mal esa regla sin que la regla cambiara. Con
#: esta, atar el contador al ultimo intento no se puede escribir desde aqui.
ULTIMAS_EXITOSAS = """
    SELECT reset_run_id, started_at, finished_at, outcome
    FROM reset_run
    WHERE outcome = 'succeeded'
    ORDER BY finished_at DESC
    LIMIT :limite
"""

FILAS_DE = """
    SELECT reset_run_id, purger, call_order, deleted, kept, duration_ms, error_type
    FROM reset_run_purger
    WHERE reset_run_id = ANY(:corridas)
    ORDER BY reset_run_id, call_order
"""


def _milisegundos(segundos: float) -> int:
    """Los segundos del registro en la resolucion que la fila guarda.

    Se declara en vez de esconderse en la sentencia: el registro guarda
    milisegundos --es la resolucion que la alerta necesita-- asi que lo que se
    lee de vuelta es la duracion redondeada, no la que midio el reloj.
    """
    return max(round(segundos * 1000), 0)


async def save_run(run: ResetRun) -> None:
    """Deja la corrida y sus filas en la misma transaccion (BR3.1)."""
    async with db.unscoped_session() as sesion:
        await db.execute_sql(
            sesion,
            GUARDAR_CORRIDA,
            reset_run_id=run.reset_run_id,
            started_at=run.started_at,
            finished_at=run.finished_at,
            outcome=run.outcome.value,
        )
        for orden, fila in enumerate(run.purgers):
            await db.execute_sql(
                sesion,
                GUARDAR_FILA,
                reset_run_id=run.reset_run_id,
                purger=fila.name,
                call_order=orden,
                deleted=fila.deleted,
                kept=fila.kept,
                duration_ms=_milisegundos(fila.duration_seconds),
                error_type=fila.error_type,
            )


async def successful_runs(*, limit: int = 1) -> tuple[ResetRun, ...]:
    """Las ultimas corridas **exitosas**, las mas recientes primero.

    Es lo que se le da a `accepts_new_cases`, que elige entre lo que recibe: un
    intento fallido no puede llegar hasta ella por esta via, y por eso no puede
    reiniciar el contador por descuido (BR3.2).

    Las filas de purgador vienen con la corrida. Una corrida sin ellas no se
    puede construir --el tipo exige al menos una-- y leer una a medias seria
    decir que corrio sin decir que hizo.

    Lo que **no** vuelve es la lista de tablas de cada purgador: las declara el
    registro de la raiz de composicion, que es su unica fuente, y guardar una
    segunda copia por corrida dejaria dos listas que el dia que discrepen no se
    sabria cual manda.
    """
    async with db.unscoped_session() as sesion:
        corridas = await db.fetch_all(sesion, ULTIMAS_EXITOSAS, limite=limit)
        if not corridas:
            return ()
        identificadores = [str(fila["reset_run_id"]) for fila in corridas]
        filas = await db.fetch_all(sesion, FILAS_DE, corridas=identificadores)

    por_corrida: dict[str, list[PurgerRow]] = {clave: [] for clave in identificadores}
    for fila in filas:
        por_corrida[str(fila["reset_run_id"])].append(
            PurgerRow(
                name=str(fila["purger"]),
                deleted=None if fila["deleted"] is None else int(fila["deleted"]),
                kept=None if fila["kept"] is None else int(fila["kept"]),
                duration_seconds=int(fila["duration_ms"]) / 1000,
                error_type=None if fila["error_type"] is None else str(fila["error_type"]),
            )
        )
    # Las dos marcas vuelven con su zona porque las columnas son `timestamptz`.
    # Si alguna vez volvieran sin ella, `ResetRun` las rechaza antes de que el
    # contador de 24 horas compare un instante ambiguo.
    return tuple(
        ResetRun(
            reset_run_id=str(fila["reset_run_id"]),
            started_at=fila["started_at"],
            finished_at=fila["finished_at"],
            outcome=ResetOutcome(str(fila["outcome"])),
            purgers=tuple(por_corrida[str(fila["reset_run_id"])]),
        )
        for fila in corridas
    )


__all__ = ["save_run", "successful_runs"]
