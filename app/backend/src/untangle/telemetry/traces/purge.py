"""Que se lleva el reinicio nocturno de lo que ya salio hacia las trazas (BR2.1 de U20).

**Este es el purgador que BR2.1 nombra aparte**, y la razon por la que lo nombra
aparte es exactamente la razon por la que no existia: el backend de trazas **no
esta en la base**, asi que la comprobacion que recorre el catalogo buscando la
marca de dato de visitante no lo ve, y un registro sin este purgador pasaba en
verde. Las cinco tablas de esta unidad si estan cubiertas --`trace_summary`
cuelga del caso en cascada y la borra el purgador de U4--; lo que faltaba era lo
que **salio** del proceso.

## A quien le pregunta que hay que borrar

Al transporte, no a un archivo escrito aqui. Hay tres casos y los tres estan
declarados, porque un purgador que no distinguiera "no habia nada" de "no se
pudo mirar" seria justo la confusion que el proyecto persigue:

- **Archivo de la corrida** (`FileTransport`, que es el caso sin destino
  declarado): se reescribe dejando solo los lotes posteriores al corte. `deleted`
  son los tramos que se fueron y `kept` los que se quedaron porque son
  posteriores al corte, no porque se conserven a proposito.
- **Destino declarado sin exportador instalado** (`UnavailableTransport`): no
  salio nada, y no es una suposicion: ese transporte **levanta** en cada envio,
  asi que ningun tramo llego nunca al backend. `deleted=0`, `kept=0`.
- **Un transporte que sabe borrar lo que entrego** (`PurgeableSpanTransport`, hoy el de
  Langfuse): se le pide `purge_before` y se hace lo que dice. `deleted` son las trazas
  que el backend **acepto borrar**; `kept` es cero, porque lo posterior al corte ni se
  lista. Si el backend no contesta, o rechaza un borrado, devuelve lo que alcanzo y por
  que paro (ver abajo).
- **Cualquier otro transporte**: levanta. Borrar del backend es trabajo del transporte
  --sabe su direccion y su credencial-- y el que no lo trae deja la corrida `partial`
  con su alerta, en vez de declarar limpia una retencion que nadie acoto.

## Un Langfuse que no responde no cierra la demo (2026-10-14)

Si Langfuse no termina el borrado, el purgador **no levanta**: devuelve lo que el
backend acepto borrar y deja el evento `traces.backend_purge_incomplete` con la razon.
Levantar dejaria la corrida `partial`, y una corrida `partial` no reinicia la ventana de
24 horas: un Langfuse caido a las tres de la manana cerraria el chat y la voz a casos
nuevos durante un dia entero. Eso es lo que BR4.8 prohibe --si el backend de trazas cae,
nada del producto se detiene--, y lo que se protege levantando no lo justifica:

- **Lo que llega a Langfuse no es dato de nadie.** Los tramos solo llevan la lista
  cerrada de `api.py` (enums, numeros e identificadores), pasan por la redaccion antes
  de salir y la prueba de canarios lo comprueba. La retencion acotada de BR3.2 es la de
  los datos del visitante, que viven en la base y si se borran.
- **Lo que no se borro hoy se borra manana**: el corte es el mismo criterio, y la
  corrida siguiente lista todo lo anterior a su propio corte. Y el plan gratuito de
  Langfuse deja ver como mucho 30 dias, asi que nada queda a la vista para siempre.

"No pude borrar" sigue siendo distinto de "borre todo": lo dice su evento, con el
conteo y la razon, y no solo la ausencia de un error.

## Lo que este purgador no alcanza, dicho

Los tramos que el registrador del proceso tiene acumulados y todavia no exporto.
Son del proceso que los acumulo, el reinicio corre en otro, y la cola es acotada
--un `deque` con tope-- asi que mueren con el proceso y no crecen. Lo que no se
puede es borrarlos desde aqui, y callarlo dejaria creer que si.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from untangle import observability
from untangle.settings import Settings
from untangle.telemetry.traces import export
from untangle.tenancy.models import PurgeResult


class TraceBackendNotPurgeableError(RuntimeError):
    """Hay un transporte instalado que esta unidad no sabe barrer.

    No se traga y no se finge limpia: la corrida queda `partial`, la alerta sale
    con su identificador, y la retencion del backend queda declarada como lo que
    es --no acotada-- hasta que su transporte traiga su propio borrado.
    """


def _nanosegundos(corte: datetime) -> int:
    """El corte en la unidad en la que OTLP escribe el tiempo."""
    return int(corte.timestamp() * 1_000_000_000)


def _tramos(lote: Any) -> list[dict[str, Any]]:
    """Los tramos de un lote OTLP/JSON, sin suponer que la forma esta completa.

    Un archivo a medio escribir --el proceso se cayo mientras anexaba-- no puede
    tumbar el reinicio: lo que no se reconoce se cuenta como tramo y se borra,
    que es la direccion segura de las dos.
    """
    if not isinstance(lote, dict):
        return []
    tramos: list[dict[str, Any]] = []
    for recurso in lote.get("resourceSpans") or []:
        if not isinstance(recurso, dict):
            continue
        for alcance in recurso.get("scopeSpans") or []:
            if not isinstance(alcance, dict):
                continue
            tramos.extend(t for t in alcance.get("spans") or [] if isinstance(t, dict))
    return tramos


def _es_posterior_al_corte(tramo: dict[str, Any], corte_ns: int) -> bool:
    """Si este tramo empezo en el corte o despues. Lo ilegible **no** lo es.

    Un tramo sin instante reconocible se borra: es la unica lectura que no deja
    dato de visitante detras por no haber sabido leer su reloj.
    """
    inicio = tramo.get("startTimeUnixNano")
    if isinstance(inicio, bool) or not isinstance(inicio, int | str):
        return False
    try:
        return int(inicio) >= corte_ns
    except ValueError:
        return False


@dataclass(frozen=True)
class _Barrido:
    """Lo que queda del archivo tras el corte, y cuanto se fue."""

    lineas: tuple[str, ...]
    deleted: int
    kept: int


def _barrer_archivo(destino: Path, corte_ns: int) -> _Barrido:
    """Separa los lotes del archivo por el corte, sin escribir nada todavia.

    Un lote se conserva **entero o nada**: los tramos de un mismo lote salieron
    juntos, y partirlo dejaria un archivo que no es OTLP valido. Si alguno de sus
    tramos es anterior al corte, el lote se va; sus tramos posteriores, si los
    hubiera, son los del mismo turno y tambien son de ese visitante.
    """
    if not destino.is_file():
        return _Barrido(lineas=(), deleted=0, kept=0)

    quedan: list[str] = []
    borrados = 0
    conservados = 0
    for linea in destino.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        try:
            lote = json.loads(linea)
        except json.JSONDecodeError:
            # Una linea que no es JSON no se conserva: no se puede afirmar que no
            # lleve nada de nadie.
            borrados += 1
            continue
        tramos = _tramos(lote)
        if tramos and all(_es_posterior_al_corte(t, corte_ns) for t in tramos):
            quedan.append(linea)
            conservados += len(tramos)
        else:
            borrados += max(len(tramos), 1)
    return _Barrido(lineas=tuple(quedan), deleted=borrados, kept=conservados)


@dataclass(frozen=True)
class _TracesBackendPurger:
    """El noveno purgador del registro: lo que salio hacia las trazas.

    `tables` va **vacio a proposito**, y no por descuido: este purgador no cubre
    ninguna tabla. Las cinco de esta unidad ya tienen dueno, y lo que este barre
    no esta en la base --que es justo por lo que hacia falta nombrarlo--.
    """

    name: str = "traces_backend"
    tables: tuple[str, ...] = ()
    #: De donde salen los ajustes. Es un campo y no una llamada dentro de
    #: `purge` para que una prueba pueda fijar el destino sin tocar el entorno.
    settings_factory: Callable[[], Settings] = Settings

    async def purge(self, *, older_than: datetime, dry_run: bool = False) -> PurgeResult:
        ajustes = self.settings_factory()
        transporte = export.transport_for(ajustes)

        if isinstance(transporte, export.UnavailableTransport):
            # No salio nada, y es comprobable: este transporte levanta en cada
            # envio. Declararlo con ceros es distinto de no haber mirado.
            observability.emit(
                "traces.backend_purged", purger=self.name, deleted=0, kept=0, dry_run=dry_run
            )
            return PurgeResult(name=self.name, deleted=0, kept=0)

        if isinstance(transporte, export.PurgeableSpanTransport):
            return await self._barrer_backend(transporte, older_than, dry_run=dry_run)

        if not isinstance(transporte, export.FileTransport):
            msg = (
                f"el transporte de trazas instalado ({type(transporte).__name__}) no "
                "sabe borrar lo que ya entrego, y esta unidad no conoce su direccion: "
                "la corrida queda parcial y la retencion del backend, sin acotar"
            )
            raise TraceBackendNotPurgeableError(msg)

        barrido = _barrer_archivo(transporte.path, _nanosegundos(older_than))
        if not dry_run and barrido.deleted:
            if barrido.lineas:
                transporte.path.write_text(
                    "".join(f"{linea}\n" for linea in barrido.lineas), encoding="utf-8"
                )
            else:
                transporte.path.unlink(missing_ok=True)

        observability.emit(
            "traces.backend_purged",
            purger=self.name,
            deleted=barrido.deleted,
            kept=barrido.kept,
            dry_run=dry_run,
        )
        return PurgeResult(name=self.name, deleted=barrido.deleted, kept=barrido.kept)

    async def _barrer_backend(
        self,
        transporte: export.PurgeableSpanTransport,
        older_than: datetime,
        *,
        dry_run: bool,
    ) -> PurgeResult:
        """Le pide al backend remoto que borre lo anterior al corte, fuera del bucle de eventos."""
        # En un hilo: el borrado es de red y bloqueante, y el reinicio corre en un
        # proceso que tambien atiende peticiones.
        resultado = await asyncio.to_thread(transporte.purge_before, older_than, dry_run=dry_run)
        observability.emit(
            "traces.backend_purged",
            purger=self.name,
            deleted=resultado.deleted,
            kept=0,
            dry_run=dry_run,
            failure=resultado.failure,
        )
        if not resultado.complete:
            # No levanta: ver "Un Langfuse que no responde no cierra la demo" arriba.
            observability.emit(
                "traces.backend_purge_incomplete",
                purger=self.name,
                deleted=resultado.deleted,
                failure=resultado.failure,
                dry_run=dry_run,
            )
        return PurgeResult(name=self.name, deleted=resultado.deleted, kept=0)


#: El purgador del backend de trazas. La raiz de composicion lo apunta en su
#: registro escrito a mano, como los otros ocho.
TRACES_BACKEND_PURGER = _TracesBackendPurger()

__all__ = ["TRACES_BACKEND_PURGER", "TraceBackendNotPurgeableError"]
