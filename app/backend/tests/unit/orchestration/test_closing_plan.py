"""Que se hace con un reporte cuando la cadena de fondo termina (US1.17, 2026-10-13).

La decision es una funcion pura y es la que se rompe regla por regla: cerrar es la excepcion y
derivar es la salida segura, asi que cada prueba de aqui busca la forma de que un caso cierre
solo **sin** que deba, o de que se quede esperando **cuando** ya debia resolverse.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from untangle.case_record.models import (
    AttachmentKind,
    CaseState,
    DerivationReason,
    Resolution,
)
from untangle.compliance.controls import phrases
from untangle.compliance.controls.api import (
    ClosureDecision,
    ClosureOutcome,
    ComplianceFinding,
    HandoffReason,
)
from untangle.compliance.controls.models import FindingCode
from untangle.orchestration import closing_plan
from untangle.orchestration.closing_plan import Step
from untangle.orchestration.state import GraphState
from untangle.voice import closing as voice_closing


@dataclass(frozen=True)
class _Regla:
    """Una regla disparada, con la unica marca que esta decision mira."""

    touches_money: bool


CIERRA = ClosureDecision(outcome=ClosureOutcome.CLOSE, copy_key=phrases.DIRECT_CLOSE)
DERIVA = ClosureDecision(
    outcome=ClosureOutcome.REFER, reason_code=HandoffReason.RULE, copy_key=phrases.HANDOFF
)
RECHAZA = ClosureDecision(
    outcome=ClosureOutcome.REFUSED,
    missing=(ComplianceFinding.of(FindingCode.DISCLOSURE_MISSING),),
)

EN_REVISION = [CaseState.VERIFYING, CaseState.DECIDING]
FUERA_DE_REVISION = [
    CaseState.OPEN,
    CaseState.CAPTURING,
    CaseState.DERIVED,
    CaseState.AWAITING_INSURED,
    CaseState.CLOSED,
]


def _plan(
    *,
    estado: CaseState | None = CaseState.DECIDING,
    oferta: bool = False,
    cierre: object | None = CIERRA,
    reglas: tuple[object, ...] = (),
) -> closing_plan.ClosingPlan:
    return closing_plan.plan(
        case_state=estado, offer_open=oferta, closure=cierre, fired_rules=reglas
    )


# --- 1. Cierre directo solo con CLOSE y sin regla de dinero ----------------------------------


@pytest.mark.parametrize("estado", EN_REVISION)
def test_una_decision_de_cierre_sin_dinero_cierra_como_registrado(estado: CaseState) -> None:
    plan = _plan(estado=estado, reglas=(_Regla(touches_money=False),))

    assert plan.step is Step.REGISTER
    assert plan.resolution is Resolution.REGISTERED
    assert plan.announce == closing_plan.DIRECT_CLOSE_PHRASE


def test_sin_ninguna_regla_disparada_tambien_cierra() -> None:
    """Las reglas disparadas pueden ser ninguna: `direct_close` lo decide la categoria."""
    assert _plan(reglas=()).step is Step.REGISTER


def test_una_regla_de_dinero_o_cobertura_impide_cerrar_aunque_la_decision_diga_cerrar() -> None:
    """La segunda defensa de AC1.17.1 y AC1.17.3: la precedencia de categorias ya lo impide."""
    plan = _plan(reglas=(_Regla(touches_money=False), _Regla(touches_money=True)))

    assert plan.step is Step.REFER
    assert plan.reason == "money_rule_fired"
    assert plan.resolution is None


def test_una_regla_que_no_dice_si_toca_dinero_cuenta_como_que_si() -> None:
    """No se cierra por no saber: un diccionario de un punto de control no tiene la marca."""
    assert _plan(reglas=({"id": "SUN-R-01"},)).step is Step.REFER


@pytest.mark.parametrize(
    ("cierre", "motivo"),
    [
        pytest.param(DERIVA, "rules_refer", id="las-reglas-derivan"),
        pytest.param(RECHAZA, "closure_refused", id="cumplimiento-rechaza-el-cierre"),
        pytest.param(None, "no_closure_decision", id="un-nodo-fallo-y-no-hay-decision"),
        pytest.param(
            {"outcome": "close", "copy_key": "compliance.closure.direct"},
            "no_closure_decision",
            id="un-diccionario-de-un-punto-de-control-no-es-una-decision",
        ),
        pytest.param("close", "no_closure_decision", id="un-texto-tampoco"),
    ],
)
def test_todo_lo_que_no_es_un_cierre_decidido_deriva(cierre: object | None, motivo: str) -> None:
    plan = _plan(cierre=cierre)

    assert plan.step is Step.REFER
    assert plan.reason == motivo
    assert plan.derivation_reason is DerivationReason.RULE
    assert plan.announce == closing_plan.HANDOFF_PHRASE


# --- 3. Con la oferta abierta no se cierra ni se deriva --------------------------------------


@pytest.mark.parametrize("cierre", [CIERRA, DERIVA, RECHAZA, None])
def test_con_la_oferta_abierta_no_se_hace_nada(cierre: object | None) -> None:
    """La persona todavia esta agregando: ni un cierre ni una derivacion le caen encima."""
    plan = _plan(oferta=True, cierre=cierre)

    assert plan.step is Step.NOTHING
    assert plan.reason == "offer_open"
    assert plan.announce is None


def test_al_contestar_la_oferta_el_mismo_caso_si_se_resuelve() -> None:
    assert _plan(oferta=True).step is Step.NOTHING
    assert _plan(oferta=False).step is Step.REGISTER


# --- El caso ya no esta en revision ----------------------------------------------------------


@pytest.mark.parametrize("estado", [*FUERA_DE_REVISION, None])
@pytest.mark.parametrize("cierre", [CIERRA, DERIVA, None])
def test_un_caso_que_ya_no_esta_en_revision_no_se_toca(
    estado: CaseState | None, cierre: object | None
) -> None:
    """Lo derivo una peticion de persona, o ya se cerro, o ya no existe: nada que hacer."""
    plan = _plan(estado=estado, cierre=cierre)

    assert plan.step is Step.NOTHING
    assert plan.reason == "case_not_in_review"


# --- Lo que se le dice a quien llama ---------------------------------------------------------


def test_la_voz_dice_su_frase_y_no_la_del_chat() -> None:
    registrado = _plan()
    derivado = _plan(cierre=DERIVA)

    assert closing_plan.announcement_key(registrado, spoken=False) == phrases.DIRECT_CLOSE
    assert closing_plan.announcement_key(derivado, spoken=False) == phrases.HANDOFF
    assert (
        closing_plan.announcement_key(registrado, spoken=True)
        == closing_plan.VOICE_REGISTERED_PHRASE
    )
    assert closing_plan.announcement_key(derivado, spoken=True) == closing_plan.VOICE_HANDOFF_PHRASE
    assert closing_plan.announcement_key(_plan(oferta=True), spoken=False) is None


def test_las_claves_repetidas_son_las_del_resto_del_sistema() -> None:
    """El catalogo pide cada clave como literal en su consumidor, asi que hay copias: que
    coincidan con las de la decision de cierre y con la despedida de la llamada."""
    assert closing_plan.DIRECT_CLOSE_PHRASE == phrases.DIRECT_CLOSE
    assert closing_plan.HANDOFF_PHRASE == phrases.HANDOFF
    assert closing_plan.VOICE_REGISTERED_PHRASE == voice_closing.REGISTERED
    assert closing_plan.VOICE_HANDOFF_PHRASE == voice_closing.NEXT_STEP


# --- La evidencia del cierre -----------------------------------------------------------------


def _estado(**escrituras: object) -> GraphState:
    return GraphState(
        tenant_id="sunmeadow",
        case_id="caso-1",
        turn_id="t-1",
        turn_text="",
        node_writes={"intake_capture_closed": True, **escrituras},
    )


def test_un_reporte_cerrado_sin_preguntar_por_cobertura_tiene_las_citas_vacias_y_no_sin_evaluar() -> (
    None
):
    """«Se miro y no habia» no es «no se miro»: sin esta distincion U4 rechazaria el cierre."""
    evidencia = closing_plan.closing_evidence(
        _estado(fired_rules=(_Regla(False),), compliance_review=_Revision("revision-1")),
        case_id="caso-1",
        has_transcript=True,
        trace_ref="traza-1",
    )

    assert evidencia.cited_clauses.kind is AttachmentKind.EMPTY
    assert evidencia.fired_rules.kind is AttachmentKind.PRESENT
    assert evidencia.transcript.kind is AttachmentKind.PRESENT
    assert evidencia.trace_id.reference == "traza-1"
    assert evidencia.control_results.reference == "revision-1"
    assert evidencia.complete is True


@dataclass(frozen=True)
class _Revision:
    review_id: str


def test_sin_reglas_disparadas_el_adjunto_esta_vacio_y_no_sin_evaluar() -> None:
    evidencia = closing_plan.closing_evidence(
        _estado(fired_rules=(), compliance_review=_Revision("r")),
        case_id="caso-1",
        has_transcript=True,
        trace_ref="t",
    )

    assert evidencia.fired_rules.kind is AttachmentKind.EMPTY
    assert evidencia.complete is True


@pytest.mark.parametrize(
    ("escrituras", "trace", "faltante"),
    [
        pytest.param({"compliance_review": _Revision("r")}, "t", "fired_rules", id="sin-reglas"),
        pytest.param({"fired_rules": ()}, "t", "control_results", id="sin-revision"),
        pytest.param(
            {"fired_rules": (), "compliance_review": _Revision("r")},
            None,
            "trace_id",
            id="sin-traza",
        ),
    ],
)
def test_un_adjunto_que_no_se_miro_se_marca_sin_evaluar_para_que_u4_rechace_el_cierre(
    escrituras: dict[str, object], trace: str | None, faltante: str
) -> None:
    evidencia = closing_plan.closing_evidence(
        _estado(**escrituras), case_id="caso-1", has_transcript=True, trace_ref=trace
    )

    assert evidencia.missing() == (faltante,)
    assert evidencia.complete is False


def test_si_se_pregunto_por_cobertura_las_citas_se_leen_de_lo_que_dejo_la_verificacion() -> None:
    con_citas = closing_plan.closing_evidence(
        _estado(
            outcome="verified",
            citations=("cita",),
            fired_rules=(),
            compliance_review=_Revision("r"),
        ),
        case_id="caso-1",
        has_transcript=True,
        trace_ref="t",
    )
    sin_citas = closing_plan.closing_evidence(
        _estado(
            outcome="no_clause_found",
            citations=(),
            fired_rules=(),
            compliance_review=_Revision("r"),
        ),
        case_id="caso-1",
        has_transcript=True,
        trace_ref="t",
    )

    assert con_citas.cited_clauses.kind is AttachmentKind.PRESENT
    assert sin_citas.cited_clauses.kind is AttachmentKind.EMPTY


def test_una_respuesta_de_cobertura_sin_citas_escritas_no_se_da_por_vacia() -> None:
    """Con una pregunta de cobertura de por medio, citas ausentes es que no se evaluaron."""
    evidencia = closing_plan.closing_evidence(
        _estado(outcome="verified", fired_rules=(), compliance_review=_Revision("r")),
        case_id="caso-1",
        has_transcript=True,
        trace_ref="t",
    )

    assert evidencia.cited_clauses.kind is AttachmentKind.NOT_EVALUATED
