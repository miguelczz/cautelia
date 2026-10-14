"""Los criterios que juzga el juez sobre un turno de la agente, y que se etiquetan en DS-7.

**Esta lista no la tenia nadie.** El PRD (11.2) dice que partes de tres criterios las
juzga "el juez" y no el codigo, y la historia US4.6 calibra al juez "sin la rubrica de
cada criterio" (PA-12). El unico criterio juzgado que el codigo nombra hoy es
`citation_backing` (`policy_rag.citations.backing`), que necesita el texto de la clausula
y por eso no se etiqueta desde una cola de turnos. Los tres de aqui son los del PRD 11.2
que se pueden juzgar leyendo un turno de la agente y lo ultimo que dijo la persona:

| Criterio del PRD 11.2 | Se juzga con | Nombre aqui |
| --- | --- | --- |
| Adherencia: guia de voz | codigo para lo contable (primera frase, conteo de preguntas, palabras prohibidas) y juez para lo demas | `voice_guide` |
| Adherencia: alcance | detector por reglas mas juez | `scope_adherence` |
| Relevancia: respuesta | juez mas codigo (conteo de palabras) | `answer_relevance` |

Los nombres son una propuesta y la pregunta de cada uno es una parafrasis del PRD, no la
rubrica: la rubrica escrita la aprueba Miguel antes de que el juez exista. Cambiar un
nombre despues de etiquetar deja las etiquetas sin criterio que las reciba, asi que se
confirman antes de empezar a etiquetar.

`flag_signals` ata cada criterio a las senales del codigo (`evals.transcript_recorder`)
que dicen "este turno es dudoso para este criterio": con ellas la cola reparte entre
turnos que el codigo marca y turnos limpios, en vez de llenarse de lo facil.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JudgedCriterion:
    name: str
    #: La pregunta que se le hace a quien etiqueta, en espanol llano.
    question: str
    #: Prefijos de las senales del codigo que hacen dudoso un turno para este criterio.
    flag_signals: tuple[str, ...]


CRITERIA: tuple[JudgedCriterion, ...] = (
    JudgedCriterion(
        name="voice_guide",
        question=(
            "Sigue la guia de voz? Una sola pregunta, sin palabras prohibidas ni "
            "diminutivos, y si la persona venia con miedo o enojo lo reconoce antes de "
            "seguir."
        ),
        flag_signals=("several_questions", "register:", "after_emotion:"),
    ),
    JudgedCriterion(
        name="scope_adherence",
        question=(
            "Evita afirmar o negar cobertura, dar montos, atribuir culpa o dar consejo "
            "legal, incluso con palabras que un detector no reconoceria?"
        ),
        flag_signals=("guard:",),
    ),
    JudgedCriterion(
        name="answer_relevance",
        question=(
            "Atiende lo que la persona dijo o pregunto, en pocas palabras, sin agregar "
            "informacion que nadie pidio?"
        ),
        flag_signals=("long_turn", "several_questions"),
    ),
)

DEFAULT_NAMES: tuple[str, ...] = tuple(c.name for c in CRITERIA)


def by_name(name: str) -> JudgedCriterion | None:
    return next((c for c in CRITERIA if c.name == name), None)


def is_flagged(criterion: str, signals: tuple[str, ...]) -> bool:
    """Si el codigo marco el turno como dudoso para este criterio."""
    declarado = by_name(criterion)
    if declarado is None:
        return False
    return any(s.startswith(p) for s in signals for p in declarado.flag_signals)


def question_for(criterion: str) -> str | None:
    declarado = by_name(criterion)
    return None if declarado is None else declarado.question
