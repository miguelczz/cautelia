"""Los tipos de la corrida del ajustador: las invariantes que la tabla tambien impone."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from untangle.adjuster.models import (
    AdjusterRun,
    RunStatus,
    RunStep,
    SourceKind,
    StepId,
    StepSource,
)
from untangle.inbox.actions import InboxAction

AHORA = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


def _corrida(**cambios: Any) -> AdjusterRun:
    base: dict[str, Any] = {
        "tenant_id": "stonecroft",
        "case_id": "caso-1",
        "status": RunStatus.RUNNING,
        "attempt": 1,
        "model": "claude-haiku-5-5",
        "created_at": AHORA,
        "updated_at": AHORA,
    }
    return AdjusterRun.model_validate(base | cambios)


def test_son_los_seis_pasos_del_diseno() -> None:
    assert [paso.value for paso in StepId] == [
        "case_read",
        "policy_read",
        "clauses",
        "rules",
        "vehicle_value",
        "decision",
    ]


def test_una_fuente_web_sin_direccion_se_rechaza() -> None:
    with pytest.raises(ValidationError, match="direccion"):
        StepSource(kind=SourceKind.WEB, ref="fasecolda", label="Guia de valores")

    fuente = StepSource(
        kind=SourceKind.WEB,
        ref="fasecolda",
        label="Guia de valores",
        url="https://guiadevalores.fasecolda.com/x",
    )
    assert fuente.url is not None


def test_una_fuente_de_clausula_no_necesita_direccion() -> None:
    fuente = StepSource(kind=SourceKind.CLAUSE, ref="D.INS.COLLISION", label="Colision")
    assert fuente.url is None


def test_un_paso_sin_texto_o_con_un_identificador_inventado_se_rechaza() -> None:
    with pytest.raises(ValidationError):
        RunStep(id=StepId.RULES, text="")
    with pytest.raises(ValidationError):
        RunStep.model_validate({"id": "paso_inventado", "text": "algo"})


def test_una_corrida_decidida_lleva_decision_y_explicacion() -> None:
    decidida = _corrida(
        status=RunStatus.DECIDED, decision=InboxAction.APPROVE, summary="Cubierto por colision."
    )
    assert decidida.decision is InboxAction.APPROVE

    with pytest.raises(ValidationError):
        _corrida(status=RunStatus.DECIDED)
    with pytest.raises(ValidationError):
        _corrida(status=RunStatus.DECIDED, decision=InboxAction.APPROVE)
    with pytest.raises(ValidationError):
        _corrida(status=RunStatus.RUNNING, decision=InboxAction.REJECT, summary="x")


def test_solo_una_corrida_fallida_lleva_el_tipo_de_su_error() -> None:
    assert _corrida(status=RunStatus.FAILED, error_kind="timeout").error_kind == "timeout"
    with pytest.raises(ValidationError, match="fallida"):
        _corrida(status=RunStatus.RUNNING, error_kind="timeout")


def test_el_intento_empieza_en_uno_y_las_busquedas_no_son_negativas() -> None:
    with pytest.raises(ValidationError):
        _corrida(attempt=0)
    with pytest.raises(ValidationError):
        _corrida(searches_used=-1)
