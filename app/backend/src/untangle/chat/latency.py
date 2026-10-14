"""Los dos extremos de la latencia del chat: el mensaje que llega y la primera palabra que sale.

Son los eventos que el panel de cifras nombra para la latencia del chat (AC4.16.3,
`LatencyEvent.MESSAGE_SENT` y `FIRST_WORD`) y que, hasta aqui, el chat no emitia: la cifra
salia "no medida" porque no habia entre que medirla. Los de la voz viven en
`voice/latency.py`; estos son sus pares.

**Llevan tiempos e identificadores, nunca contenido** (ADR-013, igual que los de la voz): ni
el texto de la persona ni el de la agente. Por eso salen por `observability.emit`, el punto
unico de salida, y no necesitan redaccion.

**Que cuenta como cada extremo.**

- `chat.message_sent`: el instante en que el servidor recibe el mensaje. Es lo mas cerca del
  «enviar» de la persona que el servidor puede ver --no ve la red de ida--, y la ruta lo toma
  **al entrar**, antes de admitir y contar el mensaje, porque esa espera tambien la vive la
  persona. El conductor de la corrida de evaluaciones hace lo mismo: toma la marca antes de
  admitir y la pasa a la entrega. Sin una marca de entrada es el instante en que empieza la
  entrega.
- `chat.first_word`: la primera salida del turno que lleva texto de la respuesta --un
  parcial, el texto final o la derivacion--. **La frase de espera no cuenta** (`turn.waiting`),
  igual que la muletilla de la llamada no es el primer audio (`voice/latency.py`): si contara,
  la meta mejoraria sin que la respuesta llegara antes. Queda anotada en `after_waiting`.
  Un error tampoco: es el turno que fallo, no la primera palabra de una respuesta.

El tiempo se mide con el reloj monotono y no con la resta de dos horas de pared: un salto del
reloj del sistema no puede dar una latencia negativa. La hora de pared (`at`) va aparte, para
cruzar el evento con los de otros sistemas.

Un turno que nunca emite `first_word` --porque fallo o porque la persona se fue-- deja un
`message_sent` sin pareja, y quien junta las latencias lo cuenta como turno sin respuesta en
vez de descartarlo.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from untangle import observability
from untangle.base import Locale
from untangle.chat.wire import Publisher
from untangle.orchestration.contracts import InboundTurn
from untangle.tenancy.models import TenantId

MESSAGE_SENT = "chat.message_sent"
FIRST_WORD = "chat.first_word"

#: Los eventos del cable (C-04) que llevan texto de la respuesta. Literales y no importados de
#: `stream`: este modulo mide el cable, no lo traduce, y `stream` importa el contrato del
#: grafo que aqui no hace falta.
_LLEVAN_LA_RESPUESTA = frozenset({"turn.partial", "turn.final", "turn.handoff"})
_ESPERA = "turn.waiting"


class TurnClock:
    """El reloj de un turno: ya emitio `message_sent` y espera la primera palabra."""

    def __init__(self, entrante: InboundTurn, *, since: float, clock: Callable[[], float]) -> None:
        self._tenant_id: TenantId = entrante.tenant_id
        self._session_ref = entrante.session_ref
        self._language: Locale = entrante.language
        #: Une los dos eventos del mismo turno. Opaco: no es el del turno de la transcripcion,
        #: que no existe todavia cuando sale `message_sent`.
        self.turn_ref = uuid.uuid4().hex[:16]
        self._since = since
        self._clock = clock
        self._after_waiting = False
        self.first_word_ms: int | None = None

    def observe(self, wire: dict[str, Any]) -> None:
        """Mira una salida ya publicada. Emite `first_word` la primera vez que es respuesta."""
        if self.first_word_ms is not None:
            return
        tipo = wire.get("kind")
        if tipo == _ESPERA:
            self._after_waiting = True
            return
        if tipo not in _LLEVAN_LA_RESPUESTA or not wire.get("text"):
            return
        self.first_word_ms = round((self._clock() - self._since) * 1000)
        observability.emit(
            FIRST_WORD,
            tenant_id=self._tenant_id,
            session_ref=self._session_ref,
            turn_ref=self.turn_ref,
            language=self._language,
            output=tipo,
            at=datetime.now(UTC).isoformat(),
            elapsed_ms=self.first_word_ms,
            after_waiting=self._after_waiting,
        )


class MeasuredPublisher:
    """La cola de siempre, mirada: cada salida que se publica pasa por el reloj del turno.

    Es lo que deja medir **en un solo sitio** (`delivery.deliver`) cualquiera de los caminos
    por los que un turno contesta --el grafo, la respuesta sin caso, la decision ya tomada--, en
    vez de repetir la marca en cada `publish`. No cambia lo que se publica ni su resultado.
    """

    def __init__(self, inner: Publisher, clock: TurnClock) -> None:
        self._inner = inner
        self._clock = clock

    @property
    def first_word_ms(self) -> int | None:
        """Lo que tardo la primera palabra de la respuesta, o `None` si todavia no salio.

        Es el mismo numero que lleva `chat.first_word`: quien lo necesita en vez de leerlo del
        registro tecnico --la corrida de evaluaciones-- lo toma de aqui y no vuelve a medir.
        """
        return self._clock.first_word_ms

    def publish(self, wire: dict[str, Any]) -> bool:
        publicado = self._inner.publish(wire)
        # Solo lo que de verdad llego a la cola: una salida que no se pudo publicar --la
        # pestana se fue-- no es la primera palabra de nadie.
        if publicado:
            self._clock.observe(wire)
        return publicado


def start(
    entrante: InboundTurn,
    *,
    since: float | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> TurnClock:
    """Marca el envio del mensaje y devuelve el reloj que espera la primera palabra.

    `since` es la marca monotona de cuando el servidor recibio el mensaje, si quien llama la
    tomo antes (la ruta); sin ella, ahora.
    """
    ahora = clock()
    origen = ahora if since is None else since
    reloj = TurnClock(entrante, since=origen, clock=clock)
    observability.emit(
        MESSAGE_SENT,
        tenant_id=entrante.tenant_id,
        session_ref=entrante.session_ref,
        turn_ref=reloj.turn_ref,
        language=entrante.language,
        at=(datetime.now(UTC) - timedelta(seconds=ahora - origen)).isoformat(),
    )
    return reloj


def measured(
    publisher: Publisher,
    entrante: InboundTurn,
    *,
    since: float | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> MeasuredPublisher:
    """La cola con el reloj del turno puesto: emite `message_sent` ahora."""
    return MeasuredPublisher(publisher, start(entrante, since=since, clock=clock))


__all__ = [
    "FIRST_WORD",
    "MESSAGE_SENT",
    "MeasuredPublisher",
    "TurnClock",
    "measured",
    "start",
]
