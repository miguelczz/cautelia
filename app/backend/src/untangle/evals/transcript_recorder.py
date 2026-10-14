"""Quien guarda lo que la agente dijo en una corrida: redactado, y con las senales del codigo.

Es el unico que construye los modelos de `evals.transcripts`, y lo hace por **la misma
puerta que el aplicativo usa para guardar un turno** (`orchestration.transcript_writer`):
lo que dijo la persona pasa por `redact` y lo que dijo la agente por `redact_composed`.
Un punto de salida nuevo sin redaccion tiene que ser imposible por construccion, no
detectable por disciplina (`compliance.redaction.sinks`, `eval_case_report`); aqui lo es
porque el unico camino de un texto al archivo es una funcion que devuelve `Redacted`.

**Falla cerrado.** Si la redaccion no se puede ejecutar (los modelos no cargan, una llamada
falla), esa conversacion **no se guarda** y queda anotada en `not_saved`; nunca se escribe
con texto sin tapar. Una corrida con modelo cuesta dinero y por eso este grabador tampoco
levanta: lo que no puede guardar lo dice.

**Las senales se calculan con el texto en claro, antes de tapar**, por la misma razon que
`transcript_guard` mide sobre el texto tal como llego a la persona: tapar un nombre o una
placa cambia las palabras y podria ocultar lo que la guardia habria detenido. Las senales
solo llevan identificadores, nunca texto.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

from untangle import language as language_detector
from untangle import observability
from untangle.base import Locale
from untangle.compliance.redaction import api as redaction
from untangle.compliance.redaction.api import Redacted, RedactionFailedError
from untangle.evals import transcript_guard
from untangle.evals.models import GoldenCase
from untangle.evals.runner.api import CaseTranscript, Turn
from untangle.evals.transcripts import (
    NotSaved,
    RecordedConversation,
    RecordedTurn,
    TranscriptsFile,
    write_transcripts,
)
from untangle.orchestration.nodes.intake import tone

#: El PRD 11.2 (Relevancia: respuesta) pide turnos de 25 palabras o menos; el conteo es de
#: codigo y lo que lo pasa de ahi es un turno que el juez tiene que mirar con cuidado.
LONG_TURN_WORDS = 25

#: La guia de voz pide una pregunta por turno (PRD 11.2, Adherencia: guia de voz).
MAX_QUESTIONS_PER_TURN = 1

Redactor = Callable[[str, Locale], Redacted]
LanguageOf = Callable[[str, Locale], Locale]


def question_count(text: str) -> int:
    """Cuantas preguntas hace el turno, contadas por sus signos de cierre."""
    return text.count("?")


def word_count(text: str) -> int:
    return len(text.split())


def code_signals(
    *,
    case: GoldenCase,
    transcript: CaseTranscript,
    languages: Sequence[Locale],
    root: Path,
) -> dict[int, tuple[str, ...]]:
    """Las senales del codigo sobre cada turno de la agente, por indice de turno.

    Todas son veredictos de codigo que el proyecto ya aplica en otro sitio:

    - `guard:<categoria>`: la guardia de salida habria detenido el turno (la misma lectura
      que hace `transcript_guard_clean`, pero por turno y no por caso).
    - `register:<forma>`: el registro prohibido de la agente (BR5.3).
    - `several_questions`: mas de una pregunta en el turno (la guia de voz pide una).
    - `long_turn`: mas de 25 palabras (PRD 11.2).
    - `after_emotion:<emocion>`: el turno responde a un mensaje de la persona con miedo o
      enojo (BR5.2). No es un fallo: es el turno donde la guia de voz exige reconocerlo.
    """
    turnos = transcript.turns
    de_la_guardia: dict[int, list[str]] = {}
    if case.tenant is not None:
        for hallazgo in transcript_guard.find_violations(
            turnos,
            tenant_id=case.tenant,
            language=case.language,
            case_number=transcript.case_number,
            tenants=transcript_guard.tenants_for(root),
            library=transcript_guard.library_for(root),
        ):
            de_la_guardia[hallazgo.index] = [f"guard:{c.value}" for c, _ in hallazgo.hits]

    resultado: dict[int, tuple[str, ...]] = {}
    ultima_persona: int | None = None
    for indice, turno in enumerate(turnos):
        if turno.speaker == "insured":
            ultima_persona = indice
            continue
        senales: list[str] = list(de_la_guardia.get(indice, ()))
        forma = tone.forbidden_register_violation(turno.text, language=languages[indice])
        if forma is not None:
            senales.append(f"register:{forma}")
        if question_count(turno.text) > MAX_QUESTIONS_PER_TURN:
            senales.append("several_questions")
        if word_count(turno.text) > LONG_TURN_WORDS:
            senales.append("long_turn")
        if ultima_persona is not None:
            emocion = tone.detect_emotion(
                turnos[ultima_persona].text, language=languages[ultima_persona]
            )
            if emocion is not None:
                senales.append(f"after_emotion:{emocion.value}")
        resultado[indice] = tuple(senales)
    return resultado


SignalReader = Callable[..., dict[int, tuple[str, ...]]]


def _tapar_lo_de_la_agente(text: str, language: Locale) -> Redacted:
    return redaction.redact_composed(text, language=language)


def _tapar_lo_de_la_persona(text: str, language: Locale) -> Redacted:
    return redaction.redact(text, language=language)


def _idioma_del_texto(text: str, fallback: Locale) -> Locale:
    return language_detector.measured(text) or fallback


class TranscriptRecorder:
    """Se queda con las transcripciones de una corrida, ya redactadas.

    Una instancia por corrida. Cumple `runner.api.TranscriptRecorder`.
    """

    def __init__(
        self,
        *,
        redact_agent: Redactor = _tapar_lo_de_la_agente,
        redact_insured: Redactor = _tapar_lo_de_la_persona,
        read_signals: SignalReader = code_signals,
        language_of: LanguageOf = _idioma_del_texto,
    ) -> None:
        self._redact_agent = redact_agent
        self._redact_insured = redact_insured
        self._read_signals = read_signals
        self._language_of = language_of
        self._conversations: dict[str, RecordedConversation] = {}
        self._not_saved: dict[str, NotSaved] = {}

    def record(self, case: GoldenCase, transcript: CaseTranscript, root: Path) -> None:
        """Guarda la conversacion del caso, o anota por que no. Nunca levanta."""
        if not transcript.turns:
            return
        try:
            conversacion = self._build(case, transcript, root)
        except RedactionFailedError:
            self._not_saved[case.case_key] = NotSaved(
                case_key=case.case_key, reason="redaction_failed"
            )
            observability.emit(
                "evals.transcript_not_saved", case_key=case.case_key, reason="redaction_failed"
            )
            return
        except Exception as error:  # noqa: BLE001 -- el grabador no tumba una corrida que cuesta dinero: anota el tipo del fallo, jamas el texto
            self._not_saved[case.case_key] = NotSaved(
                case_key=case.case_key, reason="recording_failed"
            )
            observability.emit(
                "evals.transcript_not_saved",
                case_key=case.case_key,
                reason="recording_failed",
                error=type(error).__name__,
            )
            return
        self._conversations[case.case_key] = conversacion
        self._not_saved.pop(case.case_key, None)

    def _build(
        self, case: GoldenCase, transcript: CaseTranscript, root: Path
    ) -> RecordedConversation:
        turnos = transcript.turns
        idiomas = self._languages(case, turnos)

        signals_read = True
        senales: dict[int, tuple[str, ...]] = {}
        try:
            senales = self._read_signals(
                case=case, transcript=transcript, languages=idiomas, root=root
            )
        except Exception as error:  # noqa: BLE001 -- sin senales la conversacion se guarda igual (la corrida costo dinero) y la cola sabe que no la puede estratificar
            signals_read = False
            observability.emit(
                "evals.transcript_signals_unread",
                case_key=case.case_key,
                error=type(error).__name__,
            )

        guardados: list[RecordedTurn] = []
        for indice, turno in enumerate(turnos):
            es_agente = turno.speaker == "agent"
            tapado = (
                self._redact_agent(turno.text, idiomas[indice])
                if es_agente
                else self._redact_insured(turno.text, idiomas[indice])
            )
            guardados.append(
                RecordedTurn(
                    index=indice,
                    speaker=turno.speaker,
                    text=str(tapado),
                    language=idiomas[indice],
                    opening=es_agente and indice == 0,
                    signals=senales.get(indice, ()) if es_agente else (),
                )
            )

        return RecordedConversation(
            case_key=case.case_key,
            language=case.language,
            tenant=case.tenant,
            turns=tuple(guardados),
            signals_read=signals_read,
        )

    def _languages(self, case: GoldenCase, turnos: Sequence[Turn]) -> list[Locale]:
        """El idioma de cada turno: el que se mide, o el del turno anterior si no hay senal."""
        actual: Locale = case.language
        idiomas: list[Locale] = []
        for turno in turnos:
            actual = self._language_of(turno.text, actual)
            idiomas.append(actual)
        return idiomas

    def to_file(self, *, run_id: str, commit_sha: str, recorded_at: datetime) -> TranscriptsFile:
        """Lo recogido, en orden estable por caso, listo para `write_transcripts`."""
        return TranscriptsFile(
            run_id=run_id,
            commit_sha=commit_sha,
            recorded_at=recorded_at,
            conversations=tuple(self._conversations[k] for k in sorted(self._conversations)),
            not_saved=tuple(self._not_saved[k] for k in sorted(self._not_saved)),
        )

    @property
    def is_empty(self) -> bool:
        return not self._conversations and not self._not_saved

    def save(
        self, *, run_id: str, commit_sha: str, now: datetime, directory: Path | None = None
    ) -> Path | None:
        """Escribe lo recogido en `tmp/evals/transcripts/<run_id>.json`, o nada si no hubo nada.

        Una corrida sin conversaciones --`entender`, `citas`-- no deja archivo: un archivo
        vacio se leeria como "hubo conversaciones y no dijeron nada".
        """
        if self.is_empty:
            return None
        return write_transcripts(
            self.to_file(run_id=run_id, commit_sha=commit_sha, recorded_at=now), directory
        )


__all__ = [
    "LONG_TURN_WORDS",
    "MAX_QUESTIONS_PER_TURN",
    "TranscriptRecorder",
    "code_signals",
    "question_count",
    "word_count",
]
