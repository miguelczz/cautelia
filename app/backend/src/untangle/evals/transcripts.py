"""Lo que la agente dijo en una corrida, guardado aparte y ya redactado.

El reporte de una corrida (`report.EvalReport`) guarda **veredictos por caso**, no los
turnos: una conversacion se media y lo dicho se perdia con la corrida. Para calibrar al
juez (DS-7) hacen falta justo esos turnos, porque el juez se calibra contra lo que va a
juzgar y no contra texto de ejemplo. Este archivo es lo que los conserva.

**Un archivo por corrida**, bajo `tmp/evals/transcripts/<run_id>.json`, que no se
versiona. Es el punto de salida `eval_case_report` del registro de la redaccion
(`compliance.redaction.sinks`): nada llega aqui sin pasar antes por `redact` (lo que dijo
la persona) o `redact_composed` (lo que dijo la agente). Esas llamadas las hace
`transcript_recorder`, que es el unico que construye estos modelos; este modulo solo los
define, los escribe y los lee, y por eso no importa la redaccion: leer una cola de
etiquetado no tiene por que cargar un detector de datos personales.

Lo que se guarda por turno no es solo el texto: son tambien las **senales del codigo**
sobre el turno (la guardia de salida, el registro prohibido, mas de una pregunta, mas de
25 palabras, y si venia detras de un mensaje con miedo o enojo). Son veredictos de
codigo, calculados con el texto en claro antes de tapar, y solo llevan identificadores,
nunca texto. Sirven para que la cola de etiquetado no se llene de turnos faciles.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError

from untangle import paths
from untangle.base import Frozen, Locale
from untangle.evals.models import CASE_KEY_PATTERN

Speaker = Literal["agent", "insured"]


class TranscriptsLoadError(Exception):
    """El archivo de transcripciones no se pudo leer o no tiene la forma esperada."""


class RecordedTurn(Frozen):
    """Un turno de la conversacion, con su texto ya redactado."""

    #: Posicion en `CaseTranscript.turns`, contando los dos hablantes: la misma que
    #: nombra la guardia en el detalle de un fallo ("turno 5") y la que ata una etiqueta
    #: de DS-7 a su turno.
    index: int = Field(ge=0)
    speaker: Speaker
    #: Ya redactado. El tipo `Redacted` no se puede declarar aqui sin cargar la
    #: redaccion; la garantia esta en quien construye el modelo (`transcript_recorder`).
    text: str = Field(min_length=1)
    #: El idioma del texto de este turno, no el del caso: una conversacion que cambia de
    #: idioma a mitad (RT-10) tiene turnos en los dos.
    language: Locale
    #: La apertura fija del catalogo (divulgacion), que juzga el codigo y no el juez.
    opening: bool = False
    #: Senales del codigo sobre el turno de la agente: `guard:<categoria>`,
    #: `register:<forma>`, `several_questions`, `long_turn`, `after_emotion:<emocion>`.
    signals: tuple[str, ...] = ()


class RecordedConversation(Frozen):
    """Una conversacion de un caso con canal, tal como la dijeron."""

    case_key: str = Field(pattern=CASE_KEY_PATTERN.pattern)
    language: Locale
    tenant: str | None = None
    turns: tuple[RecordedTurn, ...] = ()
    #: `False` cuando no se pudieron leer las senales del codigo: la conversacion se
    #: guarda igual (la corrida costo dinero) pero la cola no puede estratificarla.
    signals_read: bool = True


class NotSaved(Frozen):
    """Una conversacion que se midio y no se guardo, y por que. Nunca se omite en silencio."""

    case_key: str = Field(pattern=CASE_KEY_PATTERN.pattern)
    reason: Literal["redaction_failed", "recording_failed"]


class TranscriptsFile(Frozen):
    """La raiz de `tmp/evals/transcripts/<run_id>.json`."""

    run_id: str = Field(min_length=1)
    commit_sha: str = Field(min_length=1)
    recorded_at: datetime
    conversations: tuple[RecordedConversation, ...] = ()
    not_saved: tuple[NotSaved, ...] = ()


def path_for(run_id: str, directory: Path | None = None) -> Path:
    base = directory if directory is not None else paths.transcripts_dir()
    return base / f"{run_id}.json"


def write_transcripts(file: TranscriptsFile, directory: Path | None = None) -> Path:
    """Escribe el archivo de la corrida. Sobrescribe el de la misma corrida, no otro."""
    destino = path_for(file.run_id, directory)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(".json.tmp")
    temporal.write_text(file.model_dump_json(indent=2) + "\n", encoding="utf-8")
    os.replace(temporal, destino)
    return destino


def load_transcripts(path: Path) -> TranscriptsFile:
    """Un archivo de transcripciones, validado. Nombra el archivo si falla."""
    try:
        crudo = path.read_text(encoding="utf-8")
    except OSError as error:
        msg = f"no se pudo leer '{path}': {error}"
        raise TranscriptsLoadError(msg) from error
    try:
        return TranscriptsFile.model_validate_json(crudo)
    except ValidationError as error:
        msg = f"'{path}' no valida el esquema de transcripciones: {error}"
        raise TranscriptsLoadError(msg) from error


def latest_path(directory: Path | None = None) -> Path | None:
    """El archivo de transcripciones mas reciente, o `None` si no hay ninguno.

    "Mas reciente" es por fecha de escritura del archivo: es la ultima corrida con
    conversaciones **hecha en esta maquina**, que es lo que "la ultima" quiere decir
    para quien la acaba de correr.
    """
    base = directory if directory is not None else paths.transcripts_dir()
    if not base.is_dir():
        return None
    archivos = [archivo for archivo in base.glob("*.json") if archivo.is_file()]
    if not archivos:
        return None
    return max(archivos, key=lambda a: (a.stat().st_mtime_ns, a.name))
