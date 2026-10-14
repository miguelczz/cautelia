"""Entender la frase en cuanto llega, mientras corre la tolerancia de fin de habla (2026-10-13).

El turno de una llamada se cierra cuando, despues del ultimo final del reconocedor, pasa la
tolerancia (0,7, 1,2 o 2,5 s segun como termino la frase). Solo entonces el turno llamaba al
modelo, y esa llamada (1,5 a 2 s) corria **en fila** detras de una espera que no se puede
acortar: es lo que evita cortar a quien hace una pausa. Aqui la llamada al modelo sale en
cuanto llega el final, en una tarea aparte, y el turno que cierra despues recoge su resultado.

**Lo adelantado solo vale si nada cambio entre medias.** La lectura se hizo para un caso, un
idioma y un texto; el turno la usa solo si los tres siguen siendo los suyos. Si la persona
siguio hablando --otro parcial con palabras, otro final, la senal de voz con el turno
abierto--, si llego una respuesta del fondo o si el turno toma otro camino, la lectura se
cancela y se descarta: costo un llamado y nada mas. Lo que hace la lectura es **solo leer** (el
caso, la conversacion y el modelo), de modo que tirarla no deja nada a medias.

**Cada lectura deja un evento sin texto** (`voice.early_understanding`): si se uso o por que se
descarto, cuanto tardo y cuanto del turno ahorro. Sin el, "la agente contesta mas rapido" no se
distingue de un modelo que ese dia anduvo rapido.

**La tarea nunca consume un generador ni abre el rastro del turno.** Es una corrutina simple
que devuelve un valor: el rastro de `handle_turn` --variables de contexto que solo se reponen
en la tarea donde se pusieron-- sigue abriendose y cerrandose en la tarea de la llamada
(2026-10-12, `ValueError: ... was created in a different Context`).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from untangle import observability
from untangle.base import Locale
from untangle.tenancy.models import TenantId
from untangle.voice import latency

if TYPE_CHECKING:
    from untangle.orchestration.contracts import InboundTurn
    from untangle.orchestration.nodes.intake.understanding import UnderstandingResponse


class TurnUnderstander(Protocol):
    """Quien lee un mensaje con el contexto de su caso, antes de que el turno corra.

    Es `understand_turn` del turno, la misma costura que usa el chat; aqui se escribe como puerto
    porque la voz no puede importar el modulo que la implementa (arrastraria LangGraph). Devuelve
    `None` si no hay modelo, si fallo o tardo, o si el turno lo resuelve una regla.
    """

    async def __call__(self, turn: InboundTurn) -> UnderstandingResponse | None: ...


class Discard(StrEnum):
    """Por que una lectura adelantada no se uso. Cerrado: es un campo del evento."""

    #: La persona siguio hablando despues del final que la disparo.
    KEPT_TALKING = "kept_talking"
    #: Cambio algo de lo que la lectura suponia: el texto, el idioma, el caso, o llego una
    #: respuesta del fondo.
    STATE_CHANGED = "state_changed"
    #: El turno se cerro y tomo un camino que no pasa por el modelo (una repregunta, una lectura
    #: de codigo, un pedido de espera...).
    NOT_NEEDED = "not_needed"
    #: La llamada termino con la lectura en vuelo.
    CALL_ENDED = "call_ended"


@dataclass(frozen=True)
class Taken:
    """Lo que el turno recoge de una lectura adelantada.

    `response` nulo es un resultado: el modelo fallo, tardo, o el turno lo resuelve una regla.
    El turno lo entrega igual que el chat (`understood_by_channel`) y **no vuelve a llamar al
    modelo**, que duplicaria la espera justo cuando el proveedor anda mal.
    """

    response: UnderstandingResponse | None


@dataclass(frozen=True)
class _Reading:
    """Sobre que se hizo la lectura: si algo de esto cambia, no vale."""

    case_id: str | None
    language: Locale
    text: str


@dataclass(frozen=True)
class _Result:
    response: UnderstandingResponse | None
    #: Cuando termino de leerse, en el reloj monotono de `EarlyUnderstanding`.
    finished_at: float


@dataclass
class _Flight:
    """Una lectura en vuelo."""

    reading: _Reading
    task: asyncio.Task[_Result]
    started_at: float


def _reading_of(turn: InboundTurn) -> _Reading:
    return _Reading(case_id=turn.case_id, language=turn.language, text=turn.text)


def _ms(seconds: float) -> int:
    return max(0, int(seconds * 1000))


class EarlyUnderstanding:
    """La lectura adelantada de una llamada: una a la vez, y siempre se sabe que fue de ella.

    Una instancia por llamada. Sincrona para quien la lanza o la suelta --el ciclo de escucha no
    puede esperar a que un llamado cancelado termine de deshacerse--, y asincrona solo para quien
    la recoge y para el cierre de la llamada.
    """

    def __init__(
        self,
        understand: TurnUnderstander,
        *,
        tenant_id: TenantId,
        call_id: str,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._understand = understand
        self._tenant_id = tenant_id
        self._call_id = call_id
        self._monotonic = monotonic
        self._flight: _Flight | None = None
        #: Las tareas ya canceladas que todavia se estan deshaciendo: se guardan para que nadie
        #: las recoja a medias y para esperarlas todas al cerrar la llamada.
        self._releasing: set[asyncio.Task[_Result]] = set()

    @property
    def in_flight(self) -> bool:
        return self._flight is not None

    def start(self, turn: InboundTurn) -> None:
        """Empieza a leer `turn`. Si ya hay una lectura de ese mismo texto la deja correr; si es
        de otro --la persona dijo mas--, la suelta y empieza esta."""
        lectura = _reading_of(turn)
        if self._flight is not None:
            if self._flight.reading == lectura:
                return
            self.drop(Discard.KEPT_TALKING)
        tarea = asyncio.create_task(self._read(turn), name="early-understanding")
        self._flight = _Flight(reading=lectura, task=tarea, started_at=self._monotonic())

    async def _read(self, turn: InboundTurn) -> _Result:
        respuesta = await self._understand(turn)
        return _Result(response=respuesta, finished_at=self._monotonic())

    def retire(self, text: str) -> None:
        """Suelta la lectura en vuelo porque el turno, tal como esta ahora, ya no la merece.

        Si el texto es otro, la persona dijo mas; si es el mismo, lo que cambio fue otra cosa
        (llego un final sin palabras y la frase ya no se entiende, por ejemplo).
        """
        if self._flight is None:
            return
        igual = self._flight.reading.text == text
        self.drop(Discard.STATE_CHANGED if igual else Discard.KEPT_TALKING)

    def drop(self, cause: Discard, *, turn_id: str | None = None) -> None:
        """Suelta la lectura en vuelo, si la hay: la cancela, deja su evento y sigue.

        No espera a que la tarea termine de deshacerse; eso lo hace `aclose`.
        """
        vuelo, self._flight = self._flight, None
        if vuelo is not None:
            self._release(vuelo, cause, turn_id=turn_id)

    async def take(self, turn: InboundTurn, *, turn_id: str) -> Taken | None:
        """La lectura de este turno, si la hay y sigue valiendo; nula si el turno lee por su cuenta.

        Si la lectura todavia corre se espera lo que falte: es la misma espera que el turno habria
        hecho llamando al modelo, menos lo que ya avanzo. Una lectura que fallo por un error
        inesperado no tumba el turno: deja su evento y el turno lee como siempre.
        """
        vuelo, self._flight = self._flight, None
        if vuelo is None:
            return None
        if vuelo.reading != _reading_of(turn):
            self._release(vuelo, Discard.STATE_CHANGED, turn_id=turn_id)
            return None
        llego = self._monotonic()
        try:
            resultado = await vuelo.task
        except Exception as error:  # noqa: BLE001 -- la lectura es un adelanto: lo que levante no es un conjunto que este lado conozca, y el turno puede leer por su cuenta
            self._failed(error, turn_id=turn_id, words=len(vuelo.reading.text.split()))
            return None
        except asyncio.CancelledError:
            # Cancelan al turno mientras espera: la lectura se va con el, y alguien debe esperarla.
            self._track(vuelo.task)
            raise
        espera = max(0.0, resultado.finished_at - llego)
        duracion = resultado.finished_at - vuelo.started_at
        latency.early_understanding(
            tenant_id=self._tenant_id,
            call_id=self._call_id,
            turn_id=turn_id,
            outcome="used",
            words=len(vuelo.reading.text.split()),
            ran_ms=_ms(duracion),
            finished=True,
            understood=resultado.response is not None,
            waited_ms=_ms(espera),
            saved_ms=_ms(duracion - espera),
        )
        return Taken(response=resultado.response)

    async def aclose(self) -> None:
        """La llamada termino: se suelta lo que vuela y se espera a que todo se deshaga."""
        self.drop(Discard.CALL_ENDED)
        if self._releasing:
            await asyncio.gather(*self._releasing, return_exceptions=True)

    # --- Soltar y contar -------------------------------------------------------

    def _release(self, vuelo: _Flight, cause: Discard, *, turn_id: str | None) -> None:
        terminada = vuelo.task.done()
        corrio = self._monotonic() - vuelo.started_at
        if not terminada:
            vuelo.task.cancel()
        latency.early_understanding(
            tenant_id=self._tenant_id,
            call_id=self._call_id,
            turn_id=turn_id,
            outcome="discarded",
            cause=cause.value,
            words=len(vuelo.reading.text.split()),
            ran_ms=_ms(corrio),
            finished=terminada,
        )
        # Despues del evento: si la lectura ya habia fallado, el fallo se cuenta a continuacion.
        self._track(vuelo.task)

    def _track(self, tarea: asyncio.Task[_Result]) -> None:
        """Guarda una tarea soltada hasta que termine de deshacerse; si ya termino, la cuenta ya."""
        if tarea.done():
            self._settled(tarea)
            return
        self._releasing.add(tarea)
        tarea.add_done_callback(self._settled)

    def _settled(self, tarea: asyncio.Task[_Result]) -> None:
        """Una tarea soltada termino: se olvida y, si fallo por algo inesperado, se dice."""
        self._releasing.discard(tarea)
        if tarea.cancelled():
            return
        error = tarea.exception()
        if error is not None:
            self._failed(error, turn_id=None, words=None)

    def _failed(self, error: BaseException, *, turn_id: str | None, words: int | None) -> None:
        """Un fallo inesperado de la lectura: tipo y sitio, nunca el mensaje (puede traer lo dicho)."""
        latency.early_understanding(
            tenant_id=self._tenant_id,
            call_id=self._call_id,
            turn_id=turn_id,
            outcome="failed",
            words=words,
            ran_ms=None,
            finished=True,
            error_type=type(error).__name__,
            where=observability.failure_location(error),
        )


__all__ = ["Discard", "EarlyUnderstanding", "Taken", "TurnUnderstander"]
