"""La transcripcion del caso: la unica puerta, y exige texto ya redactado.

**El tipo lo impide antes de ejecutar** (SEC-U4.6). `append` pide un valor del
tipo redactado de U3, y ese tipo solo lo fabrica `compliance/redaction/api.py`
--lo comprueba `mise run redaction:constructor`--, asi que no hay forma de pasar
por aqui un texto sin redactar sin que una de las dos herramientas lo diga.

Por que importa tanto: la transcripcion es lo que una persona real escribio en
una superficie publica. Es el unico sitio de U4 donde entra texto libre, y por
lo tanto el unico donde un dato personal puede llegar en una forma que el
esquema no previo --un numero de poliza dentro de una frase, una cedula dicha de
pasada--. Los campos del caso se cifran; la transcripcion se **redacta**, que es
distinto y no se sustituyen: lo cifrado se puede abrir con la clave, lo redactado
ya no esta.

`redact_and_append` es el camino que se usa de verdad. `append` existe para
quien ya redacto --la voz, que redacta el parcial mientras la persona habla-- y
no volvemos a redactar lo que ya paso por el mismo punto.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from untangle.base import Locale
from untangle.case_record.models import CaseId, Channel, Speaker, TranscriptTurn, TurnId
from untangle.compliance.redaction.api import Redacted, redact


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


def append(draft: TurnDraft, text: Redacted) -> TranscriptTurn:
    """Anexa un turno cuyo texto **ya** paso por la redaccion.

    No vuelve a redactar: redactar dos veces convertiria `[NOMBRE 1]` en un
    texto que el segundo detector podria volver a tapar, y la numeracion de
    etiquetas dejaria de ser comparable entre turnos.
    """
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


def redact_and_append(draft: TurnDraft, text: str) -> TranscriptTurn:
    """Redacta y anexa. Es el camino que usa el chat.

    La redaccion ocurre **antes de persistir** y no antes de exportar: desde el
    dia en que el chat publico existe entran datos de personas reales, aunque el
    corpus sea sintetico.

    El idioma sale del borrador y no se detecta aqui: los reconocedores de placa,
    cedula, telefono y numero de poliza son distintos en los dos idiomas, y
    adivinar el idioma sobre un turno de cuatro palabras es como una cedula se
    queda sin tapar.
    """
    return append(draft, redact(text, language=draft.language))
