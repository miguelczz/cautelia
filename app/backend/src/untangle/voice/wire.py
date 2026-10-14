"""El protocolo del socket de voz (C-29, que esta unidad cierra).

Dos vocabularios **cerrados**, uno por sentido. Cerrarlos es lo que permite que
el comprobador de tipos obligue a cubrir todas las ramas al serializar, igual que
`TurnEvent` en C-14: un cuadro nuevo no puede entrar sin que su serializador se
entere.

**El audio no es un tipo de aqui.** Viaja en cuadros binarios, PCM de 16 bits,
mono, a 24 kHz --`SPEECH_AUDIO`, el unico formato del aplicativo-- y no lleva
cabecera: un cuadro binario es audio y un cuadro de texto es control. Mezclar los
dos en un sobre JSON obligaria a codificar en base64 y a pagar un tercio mas de
ancho de banda por cada trozo de 20 ms.

**Ningun cuadro lleva texto de interfaz.** `Notice` manda su clave del catalogo y
la consola la resuelve, igual que hace el chat en C-04. Una frase resuelta en los
dos lados acaba diciendose de dos maneras.

**Lo que si lleva texto es la transcripcion, y sale tal como la persona la dijo y la
oyo** (decision de Miguel del 2026-10-09 para lo que ella dice y del 2026-10-13 para lo
que dice la agente, que cambian BR7.2): el cable va por el socket de quien habla, y esa
es su propia pantalla. Este modulo no redacta ni destapa: traduce. Lo **guardado** en el
caso sigue tapado, y nada de esto llega a un evento ni a una traza.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from untangle.copy_catalog.api import CopyKey
from untangle.voice.models import CallState, EndReason

# --- Del navegador al servidor ------------------------------------------------


class UnknownFrameError(ValueError):
    """Llego un cuadro que este protocolo no conoce.

    Falla en el acto y **no nombra lo que llego**: el mensaje va a la traza del
    servidor y lo que se cierra es el socket. Aceptar un cuadro desconocido
    saltandoselo dejaria la puerta abierta a que una version futura del navegador
    creyera estar diciendo algo que nadie escucha.
    """


@dataclass(frozen=True)
class Auth:
    """El primer cuadro, siempre (BR1.4). El token va aqui y nunca en la URL."""

    token: str


@dataclass(frozen=True)
class Hangup:
    """La persona colgo."""


#: Lo que el navegador puede decir. Cerrado: el audio va en binario, no aqui.
ClientFrame = Auth | Hangup

AUTH = "auth"
HANGUP = "hangup"


def from_client(payload: object) -> ClientFrame:
    """Un cuadro de texto del navegador, tipado. Cualquier otra cosa se rechaza."""
    if not isinstance(payload, dict):
        raise UnknownFrameError
    tipo = payload.get("type")
    if tipo == AUTH:
        token = payload.get("token")
        if not isinstance(token, str) or not token:
            raise UnknownFrameError
        return Auth(token=token)
    if tipo == HANGUP:
        return Hangup()
    raise UnknownFrameError


# --- Del servidor al navegador ------------------------------------------------


@dataclass(frozen=True)
class State:
    """En que esta la llamada, para que la consola lo dibuje.

    Lleva los dos estados de conversacion que `CallSession` **no** persiste
    --escuchando y hablando-- porque la consola los necesita y la base no.
    """

    value: CallState | Literal["listening", "speaking"]


@dataclass(frozen=True)
class Transcript:
    """Un trozo de transcripcion, sin tapar, para la pantalla de quien habla (BR7.2 enmendado).

    Es el texto de la persona y el de la agente tal como los leyo y los oyo quien esta en
    la llamada: ninguna etiqueta de la redaccion llega aqui. Lo que se guarda en el caso
    se tapa antes de persistir, y eso no pasa por este cuadro.
    """

    speaker: Literal["insured", "agent"]
    text: str
    final: bool


@dataclass(frozen=True)
class StopAudio:
    """Vacia la cola de reproduccion **ya** (BR4.3).

    Es lo que pone la parada por debajo de 300 ms: el servidor no puede retirar el
    audio que ya mando, asi que quien lo tira es el navegador.
    """


@dataclass(frozen=True)
class Case:
    """La llamada quedo atada a un caso: su identificador y su numero."""

    case_id: str
    case_number: str


#: Lo que la consola oye cuando la llamada se acerca a su duracion maxima.
#:
#: **Vive junto al cuadro que la lleva** y no en el ciclo que la manda: el
#: vocabulario de `Notice` es parte del protocolo, y el chequeo que comprueba que
#: la consola sabe decir todo lo que el servidor manda tiene que poder leerlo sin
#: importar la raiz de composicion, que esta por encima de esta unidad.
TIME_RUNNING_OUT = CopyKey("voice.notice.time_running_out")


@dataclass(frozen=True)
class Notice:
    """Algo que la consola tiene que decir. **Una clave, nunca un texto.**"""

    copy_key: CopyKey


@dataclass(frozen=True)
class Latency:
    """Lo que tardo la respuesta de ese turno, en milisegundos (BR3.3).

    **Es el mismo numero que el evento de la traza**, no otro medido aqui: lo
    calcula una sola funcion y lo consumen los dos. Dos numeros con el mismo
    nombre que no coinciden convierten la consola en una pantalla que no se puede
    creer, y esta es la cifra que quien evalua va a comprobar.

    Lleva el turno al que pertenece para que la consola no tenga que suponer que el
    ultimo cuadro es del ultimo turno.
    """

    turn_id: str
    elapsed_ms: int
    #: La misma respuesta contada desde la **ultima palabra** que la persona dijo
    #: (2026-10-12), que es lo que vive: el reconocedor y la tolerancia de fin de habla
    #: pasan antes de que llegue el final. Aditivo y opcional: nulo si no se pudo calcular,
    #: y entonces el cuadro viaja como siempre. Sale de la misma funcion que `elapsed_ms`,
    #: con el mismo valor que quedo en la traza.
    from_last_word_ms: int | None = None


@dataclass(frozen=True)
class Ended:
    """La llamada termino, con su motivo del conjunto cerrado (BR1.6)."""

    reason: EndReason


#: Lo que el servidor puede decir. Cerrado, como `TurnEvent`.
ServerFrame = State | Transcript | StopAudio | Case | Notice | Latency | Ended

STATE = "state"
TRANSCRIPT = "transcript"
STOP_AUDIO = "stop_audio"
CASE = "case"
NOTICE = "notice"
LATENCY = "latency"
ENDED = "ended"


def to_client(frame: ServerFrame) -> dict[str, Any]:  # noqa: PLR0911 -- siete cuadros, siete ramas: la tabla indexada por tipo que el limite sugiere es justo lo que este modulo decidio no hacer, y la razon esta abajo
    """Un cuadro del servidor en la forma que viaja por el socket.

    Cada rama nombra su literal y sus campos. Una tabla indexada por tipo leeria
    igual de bien y dejaria el contrato con el navegador sin un sitio donde
    buscarlo con un grep.
    """
    if isinstance(frame, State):
        return {"type": STATE, "value": str(frame.value)}
    if isinstance(frame, Transcript):
        return {
            "type": TRANSCRIPT,
            "speaker": frame.speaker,
            "text": frame.text,
            "final": frame.final,
        }
    if isinstance(frame, StopAudio):
        return {"type": STOP_AUDIO}
    if isinstance(frame, Latency):
        cuadro: dict[str, Any] = {
            "type": LATENCY,
            "turn_id": frame.turn_id,
            "elapsed_ms": frame.elapsed_ms,
        }
        if frame.from_last_word_ms is not None:
            cuadro["from_last_word_ms"] = frame.from_last_word_ms
        return cuadro
    if isinstance(frame, Case):
        return {"type": CASE, "case_id": frame.case_id, "case_number": frame.case_number}
    if isinstance(frame, Notice):
        return {"type": NOTICE, "copy_key": frame.copy_key}
    if isinstance(frame, Ended):
        return {"type": ENDED, "reason": str(frame.reason)}
    raise UnknownFrameError


__all__ = [
    "AUTH",
    "CASE",
    "ENDED",
    "HANGUP",
    "LATENCY",
    "NOTICE",
    "STATE",
    "STOP_AUDIO",
    "TIME_RUNNING_OUT",
    "TRANSCRIPT",
    "Auth",
    "Case",
    "ClientFrame",
    "Ended",
    "Hangup",
    "Latency",
    "Notice",
    "ServerFrame",
    "State",
    "StopAudio",
    "Transcript",
    "UnknownFrameError",
    "from_client",
    "to_client",
]
