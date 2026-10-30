"""La transcripcion del caso: la unica puerta por la que entra un turno.

**Se guarda tal como se dijo** (decision de Miguel del 2026-10-30: «nadie va a poner ningun
supuesto dato real, quita eso»). Antes se guardaba redactada y todas las pantallas
mostraban «[NOMBRE 1]» donde la persona habia escrito su nombre. La redaccion sigue
en los puntos de salida que miden las compuertas duras --logs, trazas, exportacion y
reporte de evaluaciones--; la transcripcion ya no es uno de ellos.

El campo del modelo se sigue llamando `text_redacted` porque renombrarlo toca la
base y cada lector; lo que guarda hoy es el texto escrito.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from untangle.base import Locale
from untangle.case_record.models import CaseId, Channel, Speaker, TranscriptTurn, TurnId


@dataclass(frozen=True)
class TurnDraft:
    """Todo lo de un turno menos su texto.

    El texto va aparte en la firma a proposito: es lo unico que necesita pasar
    por la redaccion, y separarlo hace que no se pueda colar dentro de un objeto
    con otras diez cosas sin que nadie mire su tipo.
    """

    turn_id: TurnId
    case_id: CaseId
    speaker: Speaker
    channel: Channel
    language: Locale
    started_at: datetime
    ended_at: datetime | None = None
    interrupted: bool = False


def append(draft: TurnDraft, text: str) -> TranscriptTurn:
    """Anexa un turno con su texto tal como se dijo."""
    return TranscriptTurn(
        turn_id=draft.turn_id,
        case_id=draft.case_id,
        speaker=draft.speaker,
        channel=draft.channel,
        language=draft.language,
        text_redacted=str(text),
        started_at=draft.started_at,
        ended_at=draft.ended_at,
        interrupted=draft.interrupted,
    )
