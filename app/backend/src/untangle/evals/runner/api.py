"""Registro de objetivos y conductores de evaluacion (C-22).

El corredor **descubre** sus conductores por registro en vez de importarlos. No
es ceremonia: es lo que permite que una prueba registre un conductor que no llama
a ningun proveedor, y por lo tanto que el determinismo del corredor se pueda
probar sin gastar cuota. Una prueba que cuesta dinero es una prueba que se deja
de correr.

Los conductores viven en `untangle.evals.drivers` e importan la interfaz publica
del canal; **el codigo de produccion nunca importa `untangle.evals`**, y un
contrato `forbidden` de `import-linter` lo comprueba (UG-4).
"""

from __future__ import annotations

from collections.abc import Awaitable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from untangle.base import Locale
from untangle.evals.models import Channel, ChatTurnLatency, Dataset, GoldenCase


@dataclass(frozen=True)
class EvalTarget:
    """Lo que una unidad declara que se le mide.

    Sirve para que un criterio en rojo tenga dueno sin que nadie tenga que
    recordarlo: el reporte puede decir que unidad responde por el.
    """

    criterion: str
    dataset: Dataset
    description: str
    #: `True` cuando el criterio de aceptacion de este criterio lleva
    #: `[bloquea]` (PRD 11.2): pasa o falla por caso, un solo fallo detiene la
    #: entrega, y ninguna explicacion de regresion lo levanta (U21, correccion
    #: del 2026-09-25). Las explicaciones existen solo para las metricas que se
    #: miden contra el pasado; una compuerta dura es absoluta y no se mide
    #: contra el.
    blocking: bool = False


#: El criterio que el corredor le agrega a **todo** caso que corre por un canal, sin que
#: el caso lo declare: ningun turno de la agente dispara una categoria de la guardia de
#: salida. Vive aqui, junto al registro, porque lo comparten quien lo mide, quien lo
#: exige y quien lo marca como compuerta dura.
TRANSCRIPT_GUARD_CRITERION = "transcript_guard_clean"

#: El segundo criterio implicito (2026-10-12): ningun turno de la agente copia un fragmento
#: literal largo de los prompts versionados.
TRANSCRIPT_PROMPTS_CRITERION = "transcript_prompts_not_leaked"

#: Los criterios de transcripcion sin los cuales un caso con canal no puede correr: el
#: corredor los exige registrados, y si falta alguno el caso sale en rojo en vez de pasar
#: sin que nadie lea lo que la agente dijo.
REQUIRED_TRANSCRIPT_CHECKS = (TRANSCRIPT_GUARD_CRITERION, TRANSCRIPT_PROMPTS_CRITERION)


@dataclass(frozen=True)
class Turn:
    """Un turno de la conversacion de un caso."""

    speaker: Literal["agent", "insured"]
    text: str
    field_key: str | None = None


@dataclass(frozen=True)
class CaseTranscript:
    """Lo que un conductor devuelve tras ejecutar un caso."""

    case_key: str
    turns: tuple[Turn, ...] = ()
    #: El registro que el sistema produjo, para comparar con el esperado.
    record: dict[str, object] = field(default_factory=dict)
    #: Veredicto por criterio de evaluacion.
    verdicts: dict[str, str] = field(default_factory=dict)
    off_script_turns: int = 0
    trace_ref: str | None = None
    #: El numero legible del caso que la conversacion abrio, si abrio uno. La guardia lo
    #: necesita para no tomar por ajeno el numero del propio caso: sin el, la agente que
    #: lo dice en voz alta saldria en rojo aunque haya hecho lo correcto.
    case_number: str | None = None
    #: La latencia de cada turno de la persona al que la agente contesto, tal como la midio
    #: la entrega del canal (`chat/latency.py`). Solo la llena el conductor del chat.
    chat_latencies: tuple[ChatTurnLatency, ...] = ()


class TranscriptRecorder(Protocol):
    """Quien se queda con lo que dijo la agente en un caso, para guardarlo ya redactado.

    El corredor se lo ofrece a quien lo pida; no es parte del veredicto. **No debe
    levantar**: una corrida con modelo cuesta dinero y no se pierde porque no se pudo
    guardar una transcripcion. Lo que no pueda guardar lo declara el grabador mismo.
    """

    def record(self, case: GoldenCase, transcript: CaseTranscript, root: Path) -> None: ...


@runtime_checkable
class EvalDriver(Protocol):
    """Quien ejecuta un caso de conversacion por su canal (C-22)."""

    channel: Channel

    async def run_case(self, case: GoldenCase) -> CaseTranscript: ...


@dataclass(frozen=True)
class CheckOutcome:
    """El resultado de un chequeo determinista."""

    passed: bool
    #: Que se encontro. Nombra la clave o el archivo culpable.
    detail: str = ""


class EvalCheck(Protocol):
    """Un chequeo determinista, que se resuelve sin llamar a ningun modelo.

    No es parte de C-22: lo anade la decision CG-2 del plan, que llena el
    subconjunto de arranque con los chequeos deterministas del sistema en lugar
    de dejarlo vacio. Un subconjunto vacio produce un reporte de cero casos, y el
    primer Bolt no podria demostrar su propio criterio de terminado.
    """

    def __call__(self, *, language: Locale, root: Path) -> CheckOutcome: ...


class AsyncEvalCheck(Protocol):
    """Un chequeo que llama a un modelo y por eso es asincrono (2026-10-07).

    Lo usa la comprension de un mensaje: corre en el mismo bucle que el corredor
    y que su registro de gasto. Va en su propio registro para que los chequeos
    deterministas sigan teniendo su tipo sincrono.
    """

    def __call__(self, *, language: Locale, root: Path) -> Awaitable[CheckOutcome]: ...


class TranscriptCheck(Protocol):
    """Un criterio implicito de todo caso con canal, calculado sobre lo que se dijo.

    A diferencia de un `EvalCheck`, no lo nombra el caso: lo aplica el corredor a la
    transcripcion que devolvio el conductor, sea cual sea el canal. Que lo aplique el
    corredor y no el conductor es lo que impide que un conductor nuevo lo olvide en
    silencio.
    """

    def __call__(
        self, *, case: GoldenCase, transcript: CaseTranscript, root: Path
    ) -> CheckOutcome: ...


# --- Los cuatro registros -----------------------------------------------------

_targets: dict[str, tuple[EvalTarget, ...]] = {}
_drivers: dict[Channel, EvalDriver] = {}
_checks: dict[str, EvalCheck] = {}
_async_checks: dict[str, AsyncEvalCheck] = {}
_transcript_checks: dict[str, TranscriptCheck] = {}


def register_targets(unit: str, targets: Sequence[EvalTarget]) -> None:
    """Declara que se le mide a una unidad (C-22)."""
    _targets[unit] = tuple(targets)


def registered_targets() -> dict[str, tuple[EvalTarget, ...]]:
    return dict(_targets)


def register_driver(driver: EvalDriver) -> None:
    """Registra el conductor de un canal (C-22)."""
    _drivers[driver.channel] = driver


def driver_for(channel: Channel) -> EvalDriver | None:
    return _drivers.get(channel)


def register_check(criterion: str, check: EvalCheck) -> None:
    """Registra un chequeo determinista por el criterio que resuelve (CG-2)."""
    _checks[criterion] = check


def check_for(criterion: str) -> EvalCheck | None:
    return _checks.get(criterion)


def register_async_check(criterion: str, check: AsyncEvalCheck) -> None:
    """Registra un chequeo asincrono por el criterio que resuelve."""
    _async_checks[criterion] = check


def async_check_for(criterion: str) -> AsyncEvalCheck | None:
    return _async_checks.get(criterion)


def registered_checks() -> dict[str, EvalCheck]:
    return dict(_checks)


def register_transcript_check(criterion: str, check: TranscriptCheck) -> None:
    """Registra un criterio que el corredor aplica a la transcripcion de todo caso con canal."""
    _transcript_checks[criterion] = check


def registered_transcript_checks() -> dict[str, TranscriptCheck]:
    return dict(_transcript_checks)


def reset() -> None:
    """Vacia los registros. Lo usan las pruebas para no compartir estado."""
    _targets.clear()
    _drivers.clear()
    _checks.clear()
    _async_checks.clear()
    _transcript_checks.clear()
