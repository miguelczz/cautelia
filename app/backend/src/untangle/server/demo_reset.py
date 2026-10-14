"""`mise run demo:reset`: el reinicio nocturno de los datos de demostracion (US5.15).

Llama a **los nueve purgadores del registro escrito a mano** de la raiz de
composicion, en su orden, y deja el registro de la corrida en la base. No borra
ninguna tabla por su cuenta y no decide que se conserva: lo declara el purgador
de cada dueno, con su razon escrita al lado de su linea (BR2.3).

**Vive aqui y no en `untangle.demo_operations`** por la misma razon que la
siembra: el registro de purgadores es de la raiz de composicion, y la unidad que
orquesta no puede importarla --esta por debajo en el contrato de capas--. La
orquestacion es pura y recibe los purgadores; este archivo es quien los tiene.

**El corte es el instante en que la corrida empieza**, no una hora de ayer: lo
que el reinicio promete es que lo que dejo un visitante no sobrevive a la noche,
y un corte anterior dejaria vivo justo lo de las ultimas horas. Una conversacion
abierta a esa hora recibe su aviso y su mensaje siguiente abre un caso nuevo
(BR2.6); nadie pierde el trabajo hecho, porque lo que se corta son los datos y no
la conversacion.

**El ensayo no deja registro, y esa es la parte que importa.** Con `--dry-run`
cada purgador cuenta lo que borraria y no borra nada; guardar esa corrida como
exitosa reiniciaria el contador de 24 horas de BR3.2 **sin haber borrado nada**,
que es la unica forma de convertir esta herramienta en el fallo que vino a
evitar.

**El codigo de salida es lo unico que mira el disparador.** Una corrida que no
termina limpia sale distinta de cero, porque nadie esta mirando la salida a las
dos de la manana: la alerta ya salio por la traza, y el codigo es lo que el
disparador del intent `infra` puede ver.

**Y despues de barrer, deja la vitrina en su sitio** (AC5.6.4). Los casos del
generador no se borran --borrarlos cada noche vaciaria el corpus de
demostracion-- pero el que alguien movio se devuelve a su estado sembrado: una
decision tomada en la bandeja cierra un caso sembrado y no vuelve a derivado, asi
que sin este paso la bandeja de la demostracion se vacia un caso por dia y la
siembra no lo arregla --se detiene nombrandolo, porque es idempotente--.

**Es el ultimo paso del despliegue.** Sin ningun reinicio exitoso conocido las
superficies publicas cierran, y eso es correcto: tratar "ninguna corrida" como
abierto seria indistinguible de "el reinicio lleva tres dias sin correr". Sobre
una base recien creada no hay nada que borrar, la corrida sale `succeeded` en
milisegundos y deja el reloj en marcha.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from untangle import observability, paths
from untangle.case_record import api as casos
from untangle.case_record import purge as case_purge
from untangle.case_record.crypto import Cipher, EncryptionKeyMissingError
from untangle.case_record.models import CaseState
from untangle.demo_operations import repository
from untangle.demo_operations.api import ResetOutcome, ResetRun, run_reset
from untangle.demo_operations.reset import RESET_WINDOW, accepts_new_cases
from untangle.server import composition, synthetic_seed, trace_shipping
from untangle.settings import Settings
from untangle.synthetic_data.cases import SeededCaseLoadError, load_seeded_cases
from untangle.synthetic_data.models import SeededCaseRecord
from untangle.tenancy import session
from untangle.tenancy.models import VisitorDataPurger

__all__ = [
    "RestoreReport",
    "main",
    "nuevo_identificador",
    "reset_now",
    "restore_seeded_cases",
]


@dataclass(frozen=True)
class RestoreReport:
    """Que paso con los casos sembrados al final de la corrida (AC5.6.4)."""

    #: Los que estaban donde dice su archivo. No se tocan.
    kept: tuple[str, ...] = ()
    #: Los que no estaban y se sembraron.
    created: tuple[str, ...] = ()
    #: Los que estaban **en otro estado**: se borraron y se volvieron a sembrar.
    restored: tuple[str, ...] = ()
    #: Los de `kept` a los que esta corrida les completo la evaluacion de reglas porque no
    #: tenian ninguna (un caso sembrado antes de que la siembra evaluara). No se tocaron mas.
    completed: tuple[str, ...] = ()

    @property
    def total(self) -> int:
        return len(self.kept) + len(self.created) + len(self.restored)


async def restore_seeded_cases(
    records: Sequence[SeededCaseRecord],
    *,
    cipher: Cipher,
    now: datetime,
    refresh: bool = False,
) -> RestoreReport:
    """Devuelve cada caso sembrado a su estado, y deja como esta el que ya lo tiene.

    Tres caminos y ninguno mas: el que esta bien se deja, el que falta se siembra,
    y el que esta en otro estado se **borra y se vuelve a sembrar**. El tercero es
    el que hace falta y el que la siembra sola no puede: `seed_case` se detiene
    nombrando el caso que existe en otro estado, que es la conducta correcta para
    un comando a mano y no sirve para una corrida que nadie esta mirando.

    Borrar y volver a crear no pierde nada: lo que un caso sembrado contiene lo
    escribio el generador y esta versionado. Y el borrado arrastra la evaluacion de reglas
    del caso (cuelga de el en cascada), que `seed_case` vuelve a guardar al sembrarlo.

    Al que esta bien **solo se le completa la evaluacion de reglas si no tiene ninguna**: es
    lo que deja a una base poblada antes de que la siembra evaluara con sus casos de ejemplo
    explicados sin borrar nada y sin cambiarles el numero.

    Con `refresh` **todos** se borran y se vuelven a sembrar, aunque esten en su
    estado: es para cuando el generador cambio lo que dicen (los nombres de los
    titulares el 2026-10-09), porque comparar el estado no ve ese cambio.
    """
    quietos: list[str] = []
    creados: list[str] = []
    restaurados: list[str] = []
    completados: list[str] = []
    for registro in records:
        case_id = synthetic_seed.seeded_case_id(registro.case_key)
        vista = await casos.get_case(registro.tenant_id, case_id)
        if not refresh and vista is not None and vista.state is CaseState(registro.state.value):
            quietos.append(registro.case_key)
            # Idempotente: sobre un caso en su estado solo completa la evaluacion si falta.
            resultado = await synthetic_seed.seed_case(registro, cipher=cipher, now=now)
            if resultado.evaluated_now:
                completados.append(registro.case_key)
            continue
        if vista is not None:
            await case_purge.delete_seeded_case(registro.tenant_id, case_id)
            restaurados.append(registro.case_key)
        else:
            creados.append(registro.case_key)
        await synthetic_seed.seed_case(registro, cipher=cipher, now=now)

    observability.emit(
        "demo_operations.seeded_cases_restored",
        kept=len(quietos),
        created=len(creados),
        restored=len(restaurados),
        completed=len(completados),
    )
    return RestoreReport(
        kept=tuple(quietos),
        created=tuple(creados),
        restored=tuple(restaurados),
        completed=tuple(completados),
    )


def nuevo_identificador() -> str:
    """El identificador de la corrida. Lo acuna quien la dispara, como el de la llamada."""
    return f"reset-{uuid.uuid4().hex[:16]}"


async def reset_now(
    purgers: Sequence[VisitorDataPurger],
    *,
    now: datetime,
    dry_run: bool = False,
    reset_run_id: str | None = None,
) -> ResetRun:
    """Corre el reinicio con el corte en `now` y guarda su registro.

    El reloj se pasa como un valor fijo y no como `datetime.now`: las duraciones
    de la corrida salen de la misma funcion que el corte, y una corrida cuyo
    corte se moviera mientras corre borraria a cada purgador una cosa distinta.
    """
    corrida = await run_reset(
        purgers,
        clock=lambda: datetime.now(UTC),
        older_than=now,
        reset_run_id=reset_run_id or nuevo_identificador(),
        dry_run=dry_run,
    )
    if not dry_run:
        await repository.save_run(corrida)
    return corrida


def _imprimir(corrida: ResetRun, *, dry_run: bool) -> None:
    como = "contaria" if dry_run else "borro"
    for fila in corrida.purgers:
        if fila.error_type is not None:
            print(f"demo:reset: {fila.name} fallo con {fila.error_type}")
            continue
        print(
            f"demo:reset: {fila.name} {como} {fila.deleted} y conserva {fila.kept} "
            f"({fila.duration_seconds:.3f} s)"
        )
    registro = "ensayo, sin registro" if dry_run else f"registro {corrida.reset_run_id}"
    print(
        f"demo:reset: {corrida.outcome.value} con {len(corrida.purgers)} purgador(es), "
        f"{len(corrida.failures)} caido(s) ({registro})"
    )


async def _correr(
    purgers: Sequence[VisitorDataPurger],
    *,
    now: datetime,
    dry_run: bool,
    cipher: Cipher | None,
    refresh: bool = False,
) -> tuple[ResetRun, RestoreReport | None]:
    """Barre, guarda su registro, y despues devuelve los sembrados a su sitio.

    **En ese orden y no al reves.** Lo que no puede faltar es el barrido: si la
    clave de cifrado no esta, la vitrina se queda como estaba y el comando lo dice
    saliendo distinto de cero, pero los datos del visitante ya se fueron.
    """
    try:
        corrida = await reset_now(purgers, now=now, dry_run=dry_run)
        if dry_run or cipher is None:
            return corrida, None
        sembrados = load_seeded_cases(paths.data_dir())
        return corrida, await restore_seeded_cases(
            sembrados, cipher=cipher, now=now, refresh=refresh
        )
    finally:
        await session.dispose()


#: Con `--if-stale`, se barre si al ultimo exito le quedan menos de estas horas: asi
#: la demo local no se cierra a mitad de una prueba (en produccion lo hace el
#: disparador nocturno y en local no hay ninguno).
MARGEN_LOCAL: timedelta = timedelta(hours=4)


async def _esta_al_dia(now: datetime) -> bool:
    try:
        corridas = await repository.successful_runs(limit=1)
    finally:
        await session.dispose()
    return accepts_new_cases(corridas, now=now, window=RESET_WINDOW - MARGEN_LOCAL)


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    analizador.add_argument(
        "--dry-run",
        action="store_true",
        help="cuenta lo que borraria cada purgador y no borra nada; no deja registro",
    )
    analizador.add_argument(
        "--if-stale",
        action="store_true",
        help=(
            "barre solo si el ultimo reinicio exitoso esta por cumplir 24 horas; "
            "lo usa `mise run dev`, porque en local no hay disparador nocturno"
        ),
    )
    analizador.add_argument(
        "--refresh-seeded",
        action="store_true",
        help=(
            "vuelve a sembrar todos los casos sembrados aunque esten en su estado; "
            "para cuando el generador cambio su contenido"
        ),
    )
    argumentos = analizador.parse_args(argv)

    opciones = Settings()
    # **El proceso del reinicio no es el que sirve**: no pasa por `build_app`, asi que sin
    # esto el purgador de las trazas no veria a Langfuse y miraria el archivo de la corrida.
    # Con las tres variables puestas se instala su transporte, que es quien sabe borrar.
    transporte_de_trazas = trace_shipping.install_transport(opciones)
    try:
        return _reiniciar(argumentos, opciones)
    finally:
        trace_shipping.release_transport(transporte_de_trazas)


def _reiniciar(argumentos: argparse.Namespace, opciones: Settings) -> int:
    if not opciones.database_url:
        print(
            "demo:reset: falta UNTANGLE_DATABASE_URL: sin base no hay nada que barrer. "
            "Levante la local con `mise run services:up`",
            file=sys.stderr,
        )
        return 1

    # La clave de cifrado se resuelve **antes** de barrer para poder decirlo todo
    # junto, pero su ausencia no detiene el barrido: lo que no puede faltar es que
    # los datos del visitante se vayan.
    cipher: Cipher | None
    sin_clave: str | None = None
    try:
        cipher = Cipher.from_settings(opciones)
    except EncryptionKeyMissingError as error:
        cipher, sin_clave = None, str(error)

    session.configure(opciones.database_url)
    if argumentos.if_stale and asyncio.run(_esta_al_dia(datetime.now(UTC))):
        print("demo:reset: el ultimo reinicio esta al dia; no hace falta barrer")
        return 0
    if argumentos.if_stale:
        session.configure(opciones.database_url)
    try:
        corrida, vitrina = asyncio.run(
            _correr(
                composition.PURGADORES,
                now=datetime.now(UTC),
                dry_run=argumentos.dry_run,
                cipher=cipher,
                refresh=argumentos.refresh_seeded,
            )
        )
    except (SeededCaseLoadError, synthetic_seed.SeedError) as error:
        print(
            f"demo:reset: se barrio, y los casos sembrados no se pudieron devolver a su "
            f"estado: {error}",
            file=sys.stderr,
        )
        return 1

    _imprimir(corrida, dry_run=argumentos.dry_run)
    if vitrina is not None:
        print(
            f"demo:reset: casos sembrados: {len(vitrina.kept)} en su sitio, "
            f"{len(vitrina.created)} sembrado(s) y {len(vitrina.restored)} devuelto(s) "
            f"a su estado; {len(vitrina.completed)} con la evaluacion de reglas completada"
        )
    if sin_clave is not None and not argumentos.dry_run:
        print(
            f"demo:reset: se barrio, y los casos sembrados se quedaron como estaban: {sin_clave}",
            file=sys.stderr,
        )
        return 1
    if corrida.outcome is not ResetOutcome.SUCCEEDED:
        print(
            f"demo:reset: la corrida no termino limpia ({corrida.outcome.value}). "
            "Hay que reintentarla: a las 24 horas del ultimo exito las superficies "
            "publicas dejan de aceptar casos nuevos",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
