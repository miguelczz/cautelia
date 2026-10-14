"""La superficie publica de `untangle.voice` (U16, C-08 por dentro).

Un solo modulo de entrada, como en el resto del proyecto: lo que la raiz de
composicion y las rutas consumen esta aqui, y las piezas de dentro no se importan
desde fuera de esta unidad. La regla del proyecto lo dice asi: en una frontera
dentro del mismo proceso, el contrato **es** la firma de este archivo.

**Aqui no hay ninguna ruta.** Las tres de C-08 y el socket de C-29 viven en
`untangle.server.voice_routes`, y no por gusto: para atender una llamada hace
falta la plataforma de voz de U15, que se construye con los adaptadores de
proveedor, y el contrato `raiz-de-composicion` dice que solo `untangle.server`
los importa. Esta unidad queda asi del lado limpio de BR3.3: no conoce el
framework del grafo, no conoce ningun SDK, y lo que sabe de la voz son los
puertos de C-16.

**Este archivo no tiene logica propia.** Si la tuviera, seria una pieza escondida
en la puerta de entrada, que es la forma de defecto que este proyecto ya conoce.
"""

from __future__ import annotations

from untangle.voice.admission import CallCounters, CutCall, PublicCallDecision
from untangle.voice.admission import decide as decide_admission
from untangle.voice.call import CallEngine, LanguageChange, SwitchReason, TurnHandler, Utterance
from untangle.voice.case_opening import open_for_call
from untangle.voice.early_understanding import TurnUnderstander
from untangle.voice.latency import first_audio, language_switched
from untangle.voice.loop import CallChannel, CallRunner, CallSpeech, CallVoice, SessionVoice
from untangle.voice.models import (
    ESTADOS_VIVOS,
    CallSession,
    CallState,
    EndReason,
    VoiceMode,
)
from untangle.voice.purge import CALL_SESSION_PURGER
from untangle.voice.resume import Resumable
from untangle.voice.session import (
    CallNotFoundError,
    attach_case,
    case_ids_of_visitor,
    end_call,
    find_live,
    find_of_visitor,
    find_resumable,
    mark_live,
    new_call_id,
    open_call,
    set_language,
    switch_case,
)
from untangle.voice.tokens import (
    AUTH_DEADLINE_SECONDS,
    TOKEN_LIFETIME,
    TokenRejection,
    TokenVerdict,
    issue,
    verify,
)
from untangle.voice.turn_detection import SpeechEnd, TurnDetector
from untangle.voice.wire import (
    TIME_RUNNING_OUT,
    Auth,
    Case,
    ClientFrame,
    Ended,
    Hangup,
    Latency,
    Notice,
    ServerFrame,
    State,
    StopAudio,
    Transcript,
    UnknownFrameError,
    from_client,
    to_client,
)

__all__ = [
    "AUTH_DEADLINE_SECONDS",
    "CALL_SESSION_PURGER",
    "ESTADOS_VIVOS",
    "TIME_RUNNING_OUT",
    "TOKEN_LIFETIME",
    "Auth",
    "CallChannel",
    "CallCounters",
    "CallEngine",
    "CallNotFoundError",
    "CallRunner",
    "CallSession",
    "CallSpeech",
    "CallState",
    "CallVoice",
    "Case",
    "ClientFrame",
    "CutCall",
    "EndReason",
    "Ended",
    "Hangup",
    "LanguageChange",
    "Latency",
    "Notice",
    "PublicCallDecision",
    "Resumable",
    "ServerFrame",
    "SessionVoice",
    "SpeechEnd",
    "State",
    "StopAudio",
    "SwitchReason",
    "TokenRejection",
    "TokenVerdict",
    "Transcript",
    "TurnDetector",
    "TurnHandler",
    "TurnUnderstander",
    "UnknownFrameError",
    "Utterance",
    "VoiceMode",
    "attach_case",
    "case_ids_of_visitor",
    "decide_admission",
    "end_call",
    "find_live",
    "find_of_visitor",
    "find_resumable",
    "first_audio",
    "from_client",
    "issue",
    "language_switched",
    "mark_live",
    "new_call_id",
    "open_call",
    "open_for_call",
    "set_language",
    "switch_case",
    "to_client",
    "verify",
]
