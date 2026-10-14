"""La cola de eventos de una conversacion, entre el mensaje y el flujo (C-04).

El navegador manda el mensaje por una peticion y **escucha por otra**: el flujo de
eventos vive abierto mientras la pestana lo esta, y una respuesta llega por el flujo
y no como cuerpo del mensaje que la provoco. Entre las dos hace falta algo que
guarde lo que hay que entregar, y eso es esto.

**Es del proceso y no hay broker** (ADR-004, igual que el ritmo de fondo de U12). No
sobrevive a un reinicio, y **eso esta bien**: lo que tiene que sobrevivir es el caso,
que vive en la base, no los eventos de una pestana que ya se cerro. Un reinicio deja
al navegador reconectando y volviendo a leer el caso, que es exactamente lo que hace
al abrirlo por primera vez.

**Una cola por navegador, no por conversacion ni por pestana.** C-04 admite como
mucho un flujo por pestana; si alguien abre dos, la segunda toma la cola y la
primera se cierra. Dos pestanas leyendo la misma cola se repartirian los eventos
y cada una veria media conversacion, que es peor que cerrar una.

La identidad es **el navegador** --el resumen de su clave-- y no la conversacion,
y eso lo decidio el reinicio nocturno (BR2.6 de U20). El flujo lo abre la pestana
y vive mientras este abierta; la conversacion, en cambio, desaparece esa noche. Con
la cola atada a la conversacion, el mensaje siguiente abria una conversacion nueva,
buscaba su cola, no la encontraba, y **el visitante no volvia a recibir nada** hasta
recargar la pagina: el `POST` respondia 202 y la respuesta se publicaba en una cola
que nadie escuchaba. Atada al navegador, la misma pestana sigue oyendo, y el aviso
de que la demostracion se reinicio le llega por ahi.

**El mensaje puede llegar antes que su flujo** (2026-10-13). La pagina abre el flujo al
cargar, pero quien escribe rapido --o la red que tarda en abrirlo-- manda el primer
mensaje antes de que la cola exista, y entonces no habia donde dejar la respuesta: el
`POST` decia `202` y el mensaje no se atendia. Ahora la ruta **reserva** la cola
(`reserve`), el turno se atiende y la respuesta espera ahi; el flujo, al abrirse, **se
queda con esa cola** en vez de cerrarla y empezar otra vacia. Solo se adopta una cola
que nadie leia: la de una pestana que se fue sigue cerrandose, porque sus eventos son
de un flujo que ya no existe y la pantalla que reconecta vuelve a leer el caso.

**La conexion huerfana se cierra sola** (SCALE-U13.2). Una pestana que se oculta deja
de leer sin avisar, y sin un limite de espera su cola se quedaria viva reteniendo un
turno que nadie va a leer. El latido es lo que lo descubre: cuando no se puede
entregar, la cola se cierra.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from typing import Any, Protocol

from untangle import observability

#: Cada cuantos segundos se manda un latido. C-04 fija quince: bastante por debajo
#: del minuto en que los intermediarios suelen cortar una conexion ociosa, y lo
#: bastante espaciado para no convertir una conversacion en trafico constante.
HEARTBEAT_SECONDS = 15.0

#: Cuantos eventos caben antes de considerar que nadie esta leyendo. Una pestana
#: viva consume en cuanto llegan; una oculta no consume ninguno. Diez es mas de lo
#: que un turno produce, asi que llenarla significa que del otro lado no hay nadie.
MAX_PENDING = 10


class Publisher(Protocol):
    """Lo unico que la entrega de un turno necesita de la cola: dejar un evento.

    Existe para que la entrega pueda recibir la cola **con el reloj de la latencia puesto**
    (`chat/latency.py`) sin que cada camino por el que un turno contesta repita la marca.
    """

    def publish(self, wire: dict[str, Any]) -> bool: ...


@dataclass
class EventQueue:
    """Los eventos pendientes de una conversacion, con su numeracion.

    `next_id` es lo que C-04 pone en el `id:` de cada evento: creciente dentro del
    flujo, para que el navegador sepa si se perdio alguno.
    """

    #: Quien escucha: el resumen de la clave del navegador. No la conversacion
    #: --esa se va con el reinicio nocturno-- y no la clave, que no sale de U2.
    stream_ref: str
    _events: asyncio.Queue[dict[str, Any] | None] = field(
        default_factory=lambda: asyncio.Queue(maxsize=MAX_PENDING)
    )
    _next_id: int = 0
    closed: bool = False
    #: Si un flujo la esta leyendo. Falso solo en la cola que `reserve` deja para un
    #: mensaje que llego antes que su flujo: `open` la adopta en vez de reemplazarla.
    attached: bool = True

    @property
    def drained(self) -> bool:
        """Cerrada **y** sin nada pendiente: no va a llegar ni queda por entregar.

        Cerrar no es descartar. Un turno que publica su respuesta final y cierra
        acto seguido --que es lo normal-- dejaria esa respuesta sin entregar si
        quien consume saliera al ver `closed`. Lo encontro su prueba.
        """
        return self.closed and self._events.empty()

    def next_id(self) -> int:
        self._next_id += 1
        return self._next_id

    def publish(self, wire: dict[str, Any]) -> bool:
        """Deja un evento para el navegador. `False` si no hay quien lo lea.

        No espera: si la cola esta llena, del otro lado no hay nadie consumiendo
        --una pestana viva consume en cuanto llegan-- y esperar retendria el turno
        que la produjo. Se cierra la cola y quien publica se entera por el retorno.
        """
        if self.closed:
            return False
        try:
            self._events.put_nowait(wire)
        except asyncio.QueueFull:
            observability.emit("chat.stream_abandoned", stream_ref=self.stream_ref)
            self.close()
            return False
        return True

    def close(self) -> None:
        """Cierra el flujo. El centinela despierta a quien este esperando."""
        if self.closed:
            return
        self.closed = True
        # Si la cola ya estaba llena, no hay quien lea el centinela y no hace
        # falta: cerrar una cola llena es el caso normal de una pestana que se fue.
        with contextlib.suppress(asyncio.QueueFull):
            self._events.put_nowait(None)

    async def next_event(
        self, *, heartbeat_after: float = HEARTBEAT_SECONDS
    ) -> dict[str, Any] | None:
        """El proximo evento, o `None` si toca latido o se cerro la cola.

        Quien consume no distingue las dos cosas y no le hace falta: manda un
        latido y vuelve a esperar, y si la cola esta cerrada la siguiente vuelta
        lo ve en `closed`.

        El plazo se llama `heartbeat_after` y no `timeout` porque no es del que
        llama: es la cadencia del latido que C-04 fija, propiedad de la cola.
        """
        try:
            return await asyncio.wait_for(self._events.get(), timeout=heartbeat_after)
        except TimeoutError:
            return None


@dataclass
class QueueRegistry:
    """Las colas vivas del proceso, una por navegador."""

    _queues: dict[str, EventQueue] = field(default_factory=dict)

    def open(self, stream_ref: str) -> EventQueue:
        """Abre la cola de un navegador, cerrando la anterior si la habia.

        Es lo que hace cumplir "como mucho un flujo por pestana": la segunda
        pestana toma la cola y la primera recibe su cierre.
        """
        previa = self._queues.get(stream_ref)
        if previa is not None and not previa.attached and not previa.closed:
            # Un mensaje llego antes que este flujo y su respuesta espera aqui: se
            # adopta la cola, no se pierde lo que lleva.
            previa.attached = True
            return previa
        if previa is not None:
            previa.close()
        cola = EventQueue(stream_ref=stream_ref)
        self._queues[stream_ref] = cola
        return cola

    def reserve(self, stream_ref: str) -> EventQueue:
        """La cola de un navegador cuyo flujo todavia no abrio, para no perder lo que llegue.

        Si ya hay una viva --leida o reservada-- es esa. Una cerrada no se reutiliza:
        se reserva otra, porque publicar en una cerrada es perderlo.
        """
        existente = self._queues.get(stream_ref)
        if existente is not None and not existente.closed:
            return existente
        cola = EventQueue(stream_ref=stream_ref, attached=False)
        self._queues[stream_ref] = cola
        return cola

    def get(self, stream_ref: str) -> EventQueue | None:
        return self._queues.get(stream_ref)

    def discard(self, stream_ref: str) -> None:
        cola = self._queues.pop(stream_ref, None)
        if cola is not None:
            cola.close()

    @property
    def live(self) -> int:
        return sum(1 for cola in self._queues.values() if not cola.closed)


__all__ = ["HEARTBEAT_SECONDS", "MAX_PENDING", "EventQueue", "Publisher", "QueueRegistry"]
