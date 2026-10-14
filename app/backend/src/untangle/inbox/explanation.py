"""La explicacion de un caso: sus cinco preguntas, ninguna en blanco (BR2.4).

Que se pregunto, que se cito, que regla se disparo, quien decidio y cuando. Las
cinco viajan **siempre**, y ahi esta la regla entera: un hueco se lee como un dato
que se perdio, y quien firma una decision sobre cobertura necesita saber la
diferencia entre "no habia" y "no se pudo saber".

**Tres respuestas y no dos.** Una pregunta puede estar respondida con contenido
(`present`), respondida con nada (`none`: se miro y no habia) o **pendiente**
(`pending`: todavia no ha pasado). El tercer valor existe solo para las dos de la
decision, y existe porque `none` alli seria falso: decir "nadie decidio" de un caso
que espera decision es distinto de decir "todavia no se ha decidido", y lo segundo
es lo que ocurre. Es la misma distincion que el proyecto ya sostiene entre "no hay
clausula" y "no pude verificar", aplicada a otra pregunta.

**Por que esta pieza recibe lo poco que necesita y no la vista entera.** Toma
recuentos y un enum, no un `CaseDetail`: asi se mide con escenarios estructurados
--su caso de golden set son recuentos, no frases-- y el dia que U4 le anada un
campo a su caso esta regla no se entera. Quien adapta la vista a esta entrada es
la ruta, en un solo sitio.

**La atribucion nunca se inventa.** Una decision tomada con el enlace de
demostracion se atribuye a un visitante y jamas a una persona de la aseguradora
(BR5.5): el tipo de actor viaja tal cual, y esta pieza no tiene forma de
cambiarlo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Answer(StrEnum):
    """Como quedo respondida una de las cinco preguntas."""

    PRESENT = "present"
    NONE = "none"
    PENDING = "pending"


class Question(StrEnum):
    """Las cinco preguntas que la explicacion responde (BR2.4). Conjunto cerrado."""

    ASKED = "asked"
    CITED = "cited"
    RULE = "rule"
    DECIDED_BY = "decided_by"
    DECIDED_AT = "decided_at"


@dataclass(frozen=True)
class Decider:
    """Quien firmo la decision y cuando.

    `actor_kind` es el valor de U4 tal cual --`staff` para quien entro con
    credencial, `insured` para quien entro con el enlace de demostracion--. No se
    traduce aqui: la etiqueta que lee una persona sale del catalogo, y convertir
    un enum en texto en este punto pondria una frase visible fuera del catalogo.
    """

    actor_kind: str
    actor_id: str | None
    at: datetime


@dataclass(frozen=True)
class Evidence:
    """Lo que la explicacion necesita saber del caso, y nada mas.

    Recuentos y no contenido: lo que decide si una pregunta quedo respondida es si
    habia algo, no lo que decia. Esa es tambien la razon por la que sus escenarios
    de prueba son iguales en los dos idiomas, valor por valor (P12).
    """

    questions: int
    cited_clauses: int
    fired_rules: int
    rule_category: str | None
    decider: Decider | None


@dataclass(frozen=True)
class CaseExplanation:
    """Las cinco preguntas con su respuesta, y quien decidio si ya lo hizo."""

    answers: dict[Question, Answer]
    decider: Decider | None

    def __post_init__(self) -> None:
        faltan = sorted(q.value for q in Question if q not in self.answers)
        if faltan:
            # Una explicacion a la que le falta una pregunta es exactamente lo que
            # BR2.4 prohibe, y se detiene aqui en vez de dibujar un hueco.
            msg = f"la explicacion no responde {faltan}: BR2.4 exige las cinco"
            raise ValueError(msg)


def _hay(cuantos: int) -> Answer:
    return Answer.PRESENT if cuantos > 0 else Answer.NONE


def summarize(evidence: Evidence, *, closed: bool) -> CaseExplanation:
    """Las cinco respuestas de un caso.

    `closed` y no "se puede decidir ahora", que es una pregunta distinta y da la
    respuesta equivocada: un caso que espera al asegurado no se decide **hoy** y
    sigue pendiente de decision, porque su decision llegara cuando el asegurado
    vuelva. Lo que separa `pending` de `none` es si el caso todavia puede recibir
    una decision alguna vez, y eso es exactamente "no esta cerrado".

    Un caso cerrado sin decisor no existe hoy --toda decision escribe el suyo-- y
    si apareciera se responderia `none`, que es la verdad: se miro y no habia.
    """
    quien = evidence.decider
    de_la_decision = (
        Answer.PRESENT if quien is not None else (Answer.NONE if closed else Answer.PENDING)
    )
    return CaseExplanation(
        answers={
            Question.ASKED: _hay(evidence.questions),
            Question.CITED: _hay(evidence.cited_clauses),
            # La regla se responde por la categoria y no por el recuento: un caso
            # con categoria y sin reglas listadas dispara la regla por defecto, que
            # es una respuesta; uno sin categoria no paso todavia por el motor.
            Question.RULE: Answer.PRESENT if evidence.rule_category else Answer.NONE,
            Question.DECIDED_BY: de_la_decision,
            Question.DECIDED_AT: de_la_decision,
        },
        decider=quien,
    )


__all__ = ["Answer", "CaseExplanation", "Decider", "Evidence", "Question", "summarize"]
