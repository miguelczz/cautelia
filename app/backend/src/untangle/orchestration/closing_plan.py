"""Que hacer con un reporte cuando la cadena de fondo termina: la decision, pura (US1.17).

**Lo que faltaba.** Al terminar la captura de un siniestro el caso se derivaba siempre a un
ajustador, y la cadena de fondo --las reglas y la revision de cumplimiento-- producia una
`ClosureDecision` (`close`, `refer` o `refused`) que nadie ejecutaba: la frase de cierre
directo (`compliance.closure.direct`) no se decia nunca y la historia US1.17, que pide que un
caso con categoria `direct_close` quede cerrado como `registered` sin pasar por la bandeja, no
existia. Este modulo es la mitad que decide; `closing_outcome` es la que ejecuta.

**Pura a proposito, y en su propio modulo.** `plan` recibe lo que el estado de verdad tiene y
devuelve que hacer: no lee la base, ni el reloj, ni escribe nada. Es la que las pruebas rompen
regla por regla y la que el corredor de evaluaciones llama, y el corredor no puede llegar a la
base de datos ni de rebote (contrato `evals-sin-base-de-datos`): por eso vive aparte de quien
cierra el caso, que si la toca.

**Cerrar es la excepcion, derivar es la salida segura.** El plan solo cierra cuando todo lo
siguiente es cierto a la vez, y cualquier otra cosa --incluido no saber-- deriva:

- el caso sigue en revision (`verifying`/`deciding`): si ya lo derivo una peticion de persona
  o ya esta cerrado, no se toca;
- no hay una oferta de datos opcionales sin contestar: la persona todavia esta agregando;
- la decision de cierre es `close` --los cuatro controles pasaron y la categoria de las reglas
  es `direct_close`-- y es una `ClosureDecision` de verdad, no un diccionario que volvio de un
  punto de control;
- ninguna regla disparada lleva la marca de dinero o cobertura (AC1.17.1, AC1.17.3): la
  precedencia de categorias ya lo impide, y esto es la segunda defensa, por si un dia no.

**Lo que se cierra se cierra con evidencia.** `closing_evidence` arma los cinco adjuntos con lo
que el estado tiene, sin colapsar "se miro y no habia" con "no se miro": un adjunto sin evaluar
hace que U4 rechace el cierre, y un cierre rechazado deriva.

**Por que las reglas disparadas entran por su forma.** El manejador del turno importa este
modulo, y un contrato de capas le prohibe llegar al motor de reglas, ni de rebote. Por eso se
lee su marca (`touches_money`) y no se importa su tipo.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from untangle.base import Locale
from untangle.case_record.models import (
    AttachmentKind,
    AttachmentState,
    CaseState,
    ClosingEvidence,
    DerivationReason,
    Resolution,
)
from untangle.compliance.controls.closure import ClosureDecision, ClosureOutcome
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration.state import GraphState

__all__ = [
    "DIRECT_CLOSE_PHRASE",
    "HANDOFF_PHRASE",
    "REVIEW_STATES",
    "VOICE_HANDOFF_PHRASE",
    "VOICE_REGISTERED_PHRASE",
    "ClosingPlan",
    "Step",
    "announcement_key",
    "announcement_text",
    "closing_evidence",
    "plan",
    "refer",
]

#: Los dos estados de un reporte cuya captura cerro y todavia no tiene desenlace.
REVIEW_STATES: frozenset[CaseState] = frozenset({CaseState.VERIFYING, CaseState.DECIDING})

#: Lo que se le dice a quien escribe, y a quien llama. La voz dice lo suyo en su despedida
#: (`voice/closing.py`): estas dos claves son las de esa despedida, para que lo que queda
#: escrito en la transcripcion sea lo que se dijo.
#:
#: Las dos del chat repiten el literal de `compliance.controls.phrases` --el catalogo exige que
#: cada clave se pueda encontrar con un grep en su consumidor (BR3.4)-- y una prueba comprueba
#: que son las mismas que escribe la decision de cierre.
DIRECT_CLOSE_PHRASE = CopyKey("compliance.closure.direct")
HANDOFF_PHRASE = CopyKey("compliance.handoff.adjuster_review")
VOICE_REGISTERED_PHRASE = CopyKey("voice.closing.registered")
VOICE_HANDOFF_PHRASE = CopyKey("voice.closing.next_step")


class Step(StrEnum):
    """Los tres desenlaces posibles de una vuelta de la cadena de fondo."""

    #: No se hace nada todavia: el caso ya no esta en revision, o falta una respuesta.
    NOTHING = "nothing"
    #: Se cierra como `registered`, sin pasar por la bandeja.
    REGISTER = "register"
    #: Se deriva a un ajustador con el motivo `rule`.
    REFER = "refer"


@dataclass(frozen=True)
class ClosingPlan:
    """Que hacer con el caso, por que, y que decirle a la persona."""

    step: Step
    #: Una palabra para la traza: por que se decidio esto. Nunca texto de la persona.
    reason: str
    resolution: Resolution | None = None
    derivation_reason: DerivationReason | None = None
    #: La frase del catalogo del chat. La voz resuelve la suya (`announcement_key`).
    announce: CopyKey | None = None


def plan(
    *,
    case_state: CaseState | None,
    offer_open: bool,
    closure: object | None,
    fired_rules: Sequence[object],
) -> ClosingPlan:
    """Que hacer con el caso cuando la cadena de fondo termino. Pura.

    `closure` es lo que escribio el nodo `compliance`; cualquier cosa que no sea una
    `ClosureDecision` --`None` porque un nodo fallo, o un diccionario que volvio de un punto de
    control-- cuenta como "no hay decision", y sin decision se deriva.
    """
    if case_state is None or case_state not in REVIEW_STATES:
        return ClosingPlan(Step.NOTHING, "case_not_in_review")
    if offer_open:
        return ClosingPlan(Step.NOTHING, "offer_open")
    return _desenlace(closure, fired_rules)


def _desenlace(closure: object | None, fired_rules: Sequence[object]) -> ClosingPlan:
    """El caso esta en revision y nadie espera nada: cerrar si todo lo permite, derivar si no."""
    if not isinstance(closure, ClosureDecision):
        return refer("no_closure_decision")
    if closure.outcome is ClosureOutcome.REFUSED:
        return refer("closure_refused")
    if closure.outcome is not ClosureOutcome.CLOSE:
        return refer("rules_refer")
    if any(_toca_dinero(regla) for regla in fired_rules):
        return refer("money_rule_fired")
    return ClosingPlan(
        Step.REGISTER,
        "direct_close",
        resolution=Resolution.REGISTERED,
        announce=DIRECT_CLOSE_PHRASE,
    )


def refer(reason: str) -> ClosingPlan:
    return ClosingPlan(
        Step.REFER,
        reason,
        derivation_reason=DerivationReason.RULE,
        announce=HANDOFF_PHRASE,
    )


def _toca_dinero(regla: object) -> bool:
    """Una regla que no dice si toca dinero cuenta como que si: no se cierra por no saber."""
    marca: bool | None = getattr(regla, "touches_money", None)
    return marca is not False


def announcement_key(step_plan: ClosingPlan, *, spoken: bool) -> CopyKey | None:
    """La frase del catalogo que anuncia el desenlace, segun el canal."""
    if step_plan.announce is None:
        return None
    if not spoken:
        return step_plan.announce
    if step_plan.step is Step.REGISTER:
        return VOICE_REGISTERED_PHRASE
    return VOICE_HANDOFF_PHRASE


def announcement_text(step_plan: ClosingPlan, *, spoken: bool, language: Locale) -> str:
    """El texto del anuncio, con cada clave del catalogo en su propia llamada (BR3.4)."""
    if step_plan.step is Step.REGISTER:
        if spoken:
            return copy_api.t(VOICE_REGISTERED_PHRASE, locale=language)
        return copy_api.t(DIRECT_CLOSE_PHRASE, locale=language)
    if spoken:
        return copy_api.t(VOICE_HANDOFF_PHRASE, locale=language)
    return copy_api.t(HANDOFF_PHRASE, locale=language)


# --- La evidencia del cierre ------------------------------------------------------------


def closing_evidence(
    state: GraphState, *, case_id: str, has_transcript: bool, trace_ref: str | None
) -> ClosingEvidence:
    """Los cinco adjuntos del cierre, con lo que el estado tiene (FR1.7, BR6.3).

    Cada uno con su estado propio y sin colapsar: `EMPTY` es "se miro y no habia" y
    `NOT_EVALUATED` es "no se miro". Es la misma lectura que hace la revision de cumplimiento
    de los tres adjuntos que comparten (`server.composition._evidencia`), y una prueba de la
    cadena de fondo comprueba que las dos coinciden.
    """
    revision = state.written("compliance_review")
    referencia_de_la_revision = getattr(revision, "review_id", None)
    return ClosingEvidence(
        transcript=_presente_o_vacio(has_transcript, case_id),
        cited_clauses=_de_las_citas(state, case_id),
        fired_rules=_de_un_adjunto(state.written("fired_rules"), case_id),
        trace_id=(
            AttachmentState(kind=AttachmentKind.PRESENT, reference=trace_ref)
            if trace_ref
            else AttachmentState(kind=AttachmentKind.NOT_EVALUATED)
        ),
        control_results=(
            AttachmentState(kind=AttachmentKind.PRESENT, reference=referencia_de_la_revision)
            if isinstance(referencia_de_la_revision, str) and referencia_de_la_revision
            else AttachmentState(kind=AttachmentKind.NOT_EVALUATED)
        ),
    )


def _presente_o_vacio(hay: bool, referencia: str) -> AttachmentState:
    if hay:
        return AttachmentState(kind=AttachmentKind.PRESENT, reference=referencia)
    return AttachmentState(kind=AttachmentKind.EMPTY)


def _de_un_adjunto(valor: object, referencia: str) -> AttachmentState:
    if valor is None:
        return AttachmentState(kind=AttachmentKind.NOT_EVALUATED)
    if isinstance(valor, tuple | list) and not valor:
        return AttachmentState(kind=AttachmentKind.EMPTY)
    return AttachmentState(kind=AttachmentKind.PRESENT, reference=referencia)


def _de_las_citas(state: GraphState, case_id: str) -> AttachmentState:
    citas = state.written("citations")
    if (
        citas is None
        and state.written("outcome") is None
        and state.written("intake_capture_closed") is True
    ):
        # El reporte cerro sin que nadie preguntara por cobertura: no hay nada que citar, y eso
        # se miro. Es la misma lectura que hace la bandeja al cerrar un caso sin citas.
        return AttachmentState(kind=AttachmentKind.EMPTY)
    return _de_un_adjunto(citas, case_id)
