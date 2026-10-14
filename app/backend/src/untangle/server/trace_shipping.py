"""La exportacion de trazas del proceso servido: cada 15 segundos, fuera de la respuesta.

Los tramos se acumulan en memoria (`BufferedRecorder`) y hasta ahora nadie los sacaba
del proceso. Esta pieza es quien los saca, y vive en `untangle.server` por dos razones
que son la misma regla: es la unica que puede construir el adaptador de Langfuse
(contrato `raiz-de-composicion`) y es la que tiene derecho a tardar, porque cerrar un
tramo no puede llamar al backend (`api.py` no importa `export.py`).

## Que hace, en orden

1. **Al arrancar** (`start`): pide a Langfuse el identificador del proyecto, una vez,
   para armar el enlace a una traza (`telemetry.traces.links`). Se hace dentro de la
   tarea de fondo y no en el arranque: un Langfuse que no contesta no retrasa la
   disponibilidad del proceso. Si falla, no hay enlace, se registra un evento y se
   vuelve a intentar en el ciclo siguiente --ver mas abajo-- hasta que conteste.
2. **Cada `EXPORT_INTERVAL_SECONDS`**: vacia el registrador y lo entrega con
   `export_pending`, que serializa, redacta y entrega, y que no levanta por un fallo
   del destino (BR4.8). La entrega corre en un hilo, asi que ni siquiera un destino
   que tarda sus cinco segundos detiene el bucle de eventos.
3. **Al apagar** (`stop`): una exportacion mas, con un tope de tiempo, para no perder
   lo ultimo que el proceso vio.

## Lo que no puede pasar

La tarea de fondo **no muere por una excepcion**: lo que `export_pending` no atrapa
--un registrador que no acumula, un fallo inesperado-- se registra como evento y el
ciclo sigue. Una exportacion que se para en silencio es exactamente el fallo que esta
pieza existe para cerrar.
"""

from __future__ import annotations

import asyncio
import contextlib

from untangle import observability
from untangle.providers.adapters import langfuse
from untangle.settings import Settings
from untangle.telemetry.traces import export, links

__all__ = [
    "EXPORT_INTERVAL_SECONDS",
    "SHUTDOWN_EXPORT_SECONDS",
    "TraceShipping",
    "build",
    "install_transport",
    "release_transport",
]

#: Cada cuanto se vacia el registrador. Quince segundos: una traza esta en Langfuse
#: casi enseguida, y el registrador acotado (2048 tramos) no se llena entre dos vueltas.
EXPORT_INTERVAL_SECONDS = 15.0

#: Lo que se espera, como mucho, a la ultima exportacion al apagar.
SHUTDOWN_EXPORT_SECONDS = 8.0


class TraceShipping:
    """El transporte de Langfuse instalado, y la tarea que lo alimenta."""

    def __init__(
        self,
        *,
        transport: langfuse.LangfuseTransport,
        settings: Settings,
        interval_seconds: float = EXPORT_INTERVAL_SECONDS,
    ) -> None:
        self._transport = transport
        self._settings = settings
        self._interval = interval_seconds
        self._parar: asyncio.Event | None = None
        self._tarea: asyncio.Task[None] | None = None
        self._enlace_avisado = False

    async def start(self) -> None:
        """Arranca la tarea de fondo. El arranque del proceso no espera a Langfuse."""
        if self._tarea is not None:
            return
        self._parar = asyncio.Event()
        self._tarea = asyncio.create_task(self._ciclo(self._parar), name="traces-export")

    async def stop(self) -> None:
        """Detiene la tarea, exporta lo ultimo y suelta el cliente."""
        if self._tarea is not None and self._parar is not None:
            self._parar.set()
            # Se le da el mismo tiempo que a la ultima exportacion: si esta a mitad de
            # una entrega a un destino que no contesta, `wait_for` la cancela al vencer.
            with contextlib.suppress(TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(self._tarea, timeout=SHUTDOWN_EXPORT_SECONDS)
            self._tarea = None
        try:
            await asyncio.wait_for(self._exportar(), timeout=SHUTDOWN_EXPORT_SECONDS)
        except TimeoutError:
            observability.emit("traces.shutdown_export_timeout")
        self._transport.close()
        links.install(None)

    async def _ciclo(self, parar: asyncio.Event) -> None:
        while not parar.is_set():
            await self._resolver_enlace()
            try:
                await asyncio.wait_for(parar.wait(), timeout=self._interval)
            except TimeoutError:
                await self._exportar()
            else:
                return

    async def _resolver_enlace(self) -> None:
        """Pide el identificador del proyecto hasta tenerlo. Un fallo no tumba nada."""
        if links.available():
            return
        try:
            proyecto = await asyncio.to_thread(self._transport.project_id)
        except Exception as error:  # noqa: BLE001 -- el enlace es un extra: ningun fallo suyo tumba el arranque ni el ciclo
            if not self._enlace_avisado:
                self._enlace_avisado = True
                observability.emit(
                    "traces.langfuse_project_unavailable", error=type(error).__name__
                )
            return
        host = self._settings.langfuse_host
        if host is None:  # pragma: no cover - sin host no se construye el transporte
            return
        links.install(links.TraceLinks(host=host, project_id=proyecto))
        observability.emit("traces.langfuse_link_ready")

    async def _exportar(self) -> None:
        try:
            await export.export_pending(settings=self._settings)
        except Exception as error:  # noqa: BLE001 -- la tarea de fondo no muere: se registra y el ciclo sigue
            observability.emit("traces.export_cycle_failed", error=type(error).__name__)


def install_transport(settings: Settings) -> langfuse.LangfuseTransport | None:
    """Instala el transporte de Langfuse si las tres variables estan, y lo devuelve.

    Lo usan los dos procesos que hablan con Langfuse: el que sirve (por `build`, que ademas
    arranca la tarea) y el del reinicio nocturno (`demo_reset`), que solo necesita el
    transporte para que el purgador de las trazas sepa borrar. Sin las tres variables no
    instala nada y todo queda como estaba: el archivo de la corrida para la tuberia.
    """
    transporte = langfuse.build_transport(settings)
    if transporte is not None:
        export.install_transport(transporte)
    return transporte


def release_transport(transport: langfuse.LangfuseTransport | None) -> None:
    """Quita el transporte instalado y cierra su cliente. `None` es no haber instalado nada."""
    if transport is None:
        return
    export.install_transport(None)
    transport.close()


def build(settings: Settings) -> TraceShipping | None:
    """Instala el transporte de Langfuse y devuelve quien lo alimenta, o `None` sin las tres variables.

    Sin ellas no se instala nada y todo queda como estaba: el archivo de la corrida
    para la tuberia, y ninguna tarea de fondo.
    """
    transporte = install_transport(settings)
    if transporte is None:
        return None
    return TraceShipping(transport=transporte, settings=settings)
