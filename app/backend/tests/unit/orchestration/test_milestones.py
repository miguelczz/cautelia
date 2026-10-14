"""Que turnos son un hito: su frase la dice siempre el codigo, nunca el modelo (2026-10-12).

Son los turnos donde la frase **hace algo** que el modelo no puede saber ni prometer: la
emergencia, el cierre del reporte con su numero, una lectura o una oferta que espera un si o un
no, la poliza que el corpus encontro («¿eres tu?»), la espera de una revision que de verdad
arranco. Se reconocen por lo que el nodo escribio, y cada condicion se prueba sola: dos de ellas
suelen coincidir en el mismo turno, y una que sobrara sin que nadie lo notara no se veria.

Funcion pura, sin base y sin modelo.
"""

from __future__ import annotations

from typing import Any

import pytest

from untangle.compliance.controls.signals import TurnSignals
from untangle.orchestration import turn
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.orchestration.nodes.intake.composition import COVERAGE_CHECKING
from untangle.orchestration.nodes.intake.node import IntakeNodeOutput, SessionEnd
from untangle.orchestration.nodes.intake.policy import PolicyMatch

_SIN_SENALES = TurnSignals(human_request=False, identity_question=False, emergency=False)
_PREGUNTA = "intake.question.what_happened"


def _salida(**cambios: Any) -> IntakeNodeOutput:
    base: dict[str, Any] = {
        "intake_next_block": Block.WHAT_HAPPENED,
        "intake_extracted": (),
        "intake_awaiting_confirmation": None,
        "intake_readback_resolved": None,
        "intake_response_key": _PREGUNTA,
        "intake_response_text": "¿Qué pasó?",
        "intake_session_ended": None,
    }
    return IntakeNodeOutput(**{**base, **cambios})


def _es_hito(
    salida: IntakeNodeOutput,
    *,
    senales: TurnSignals = _SIN_SENALES,
    revision_lanzada: bool = False,
) -> bool:
    return turn._es_un_hito(senales, salida, revision_lanzada=revision_lanzada)


def test_una_pregunta_normal_no_es_un_hito() -> None:
    assert not _es_hito(_salida())


def test_la_emergencia_es_un_hito_por_la_senal_aunque_la_clave_sea_una_pregunta() -> None:
    emergencia = TurnSignals(human_request=False, identity_question=False, emergency=True)

    assert _es_hito(_salida(), senales=emergencia)


@pytest.mark.parametrize(
    "cambio",
    [
        {"intake_session_ended": SessionEnd.ABUSE},
        {"intake_capture_closed": True},
        {"intake_awaiting_confirmation": Block.FINAL_CONFIRMATION},
        {
            "intake_policy_match": PolicyMatch(
                policy_number="POL-000001", holder_name="Marcela Ríos", vehicle=None
            )
        },
    ],
    ids=["cierre-por-abuso", "reporte-cerrado", "espera-un-si-o-un-no", "poliza-encontrada"],
)
def test_lo_que_el_nodo_deja_a_la_espera_o_cerrado_es_un_hito_aunque_la_clave_sea_una_pregunta(
    cambio: dict[str, Any],
) -> None:
    assert _es_hito(_salida(**cambio))


def test_una_revision_de_poliza_que_de_verdad_arranco_es_un_hito() -> None:
    assert _es_hito(_salida(), revision_lanzada=True)


@pytest.mark.parametrize(
    "clave",
    [
        "intake.closing.fast_claim_done",
        "intake.closing.voice_fast_offer",
        "intake.closing.summary_quote",
        "intake.readback.quote_all",
        "intake.readback.what_happened",
        "intake.policy.found",
        "intake.policy.declined",
        "intake.tone.calm",
        "intake.tone.closing_abuse",
        "intake.emergency.continuation",
        str(COVERAGE_CHECKING),
    ],
)
def test_las_frases_que_cierran_leen_de_vuelta_o_calman_son_un_hito_por_su_clave(
    clave: str,
) -> None:
    assert _es_hito(_salida(intake_response_key=clave))


@pytest.mark.parametrize(
    "clave",
    [
        "intake.question.safety",
        "intake.question.quote_all",
        "intake.question.quote_vehicle_model",
        "intake.social.greeting",
        "intake.social.thanks",
        "intake.social.goodbye",
        "policy_rag.coverage.ask_question",
    ],
)
def test_preguntar_agradecer_o_despedirse_no_es_un_hito_y_lo_dice_el_modelo(clave: str) -> None:
    assert not _es_hito(_salida(intake_response_key=clave))
