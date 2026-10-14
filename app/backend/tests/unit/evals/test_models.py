"""Pruebas de los modelos de las seis entidades.

Cada una afirma una restriccion de `entities.md`, no una forma de codificarla:
lo que se prueba es que el modelo rechace un estado que el diseno declara
invalido, y que acepte el que declara valido.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from untangle.copy_catalog.models import CopyEntry, Surface
from untangle.evals.models import (
    CaseResult,
    CaseStatus,
    Dataset,
    EvalRun,
    GoldenCase,
    NonComparableCause,
    NotMeasuredCause,
    ScriptAnswer,
)

MOMENTO = datetime(2026, 9, 19, 10, 0, tzinfo=UTC)


def _resultado(**cambios: object) -> dict[str, object]:
    base: dict[str, object] = {
        "result_id": "r-1",
        "run_id": "run-1",
        "case_key": "DS-2/es/017",
        "status": CaseStatus.PASSED,
    }
    base.update(cambios)
    return base


# --- Camino feliz -------------------------------------------------------------


def test_un_caso_pasado_con_su_criterio_es_valido_y_congelado() -> None:
    resultado = CaseResult(**_resultado(criteria_results={"citation_precision": "pass"}))  # type: ignore[arg-type]

    assert resultado.status is CaseStatus.PASSED
    assert resultado.off_script_turns == 0
    with pytest.raises(ValidationError):
        # Congelado: el resultado de un caso no se edita despues de escribirlo.
        resultado.status = CaseStatus.FAILED  # type: ignore[misc]


# --- Casos de error y de borde ------------------------------------------------


def test_un_caso_no_medido_sin_causa_es_invalido() -> None:
    with pytest.raises(ValidationError) as excinfo:
        CaseResult(**_resultado(status=CaseStatus.NOT_MEASURED))  # type: ignore[arg-type]

    assert "DS-2/es/017" in str(excinfo.value)
    assert "causa" in str(excinfo.value)


def test_un_caso_fallido_sin_criterio_fallido_es_invalido() -> None:
    with pytest.raises(ValidationError) as excinfo:
        CaseResult(
            **_resultado(
                status=CaseStatus.FAILED,
                criteria_results={"citation_precision": "pass"},
            )  # type: ignore[arg-type]
        )

    assert "DS-2/es/017" in str(excinfo.value)


def test_dos_respuestas_del_mismo_campo_no_comparten_secuencia() -> None:
    with pytest.raises(ValidationError) as excinfo:
        GoldenCase(
            case_key="DS-2/es/017",
            dataset=Dataset.DS_2,
            language="es",
            script=(
                ScriptAnswer(field_key="incident.location", sequence=1, text="En la 80"),
                ScriptAnswer(field_key="incident.location", sequence=1, text="Perdon, la 30"),
            ),
        )

    assert "incident.location" in str(excinfo.value)


def test_una_corrida_con_un_caso_no_medido_no_puede_declararse_comparable() -> None:
    no_medido = CaseResult(
        **_resultado(
            status=CaseStatus.NOT_MEASURED,
            not_measured_cause=NotMeasuredCause.PROVIDER_KEY_MISSING,
        )  # type: ignore[arg-type]
    )

    with pytest.raises(ValidationError) as excinfo:
        EvalRun(
            run_id="run-1",
            commit_sha="abc123",
            started_at=MOMENTO,
            results=(no_medido,),
            comparable=True,
        )

    assert "run-1" in str(excinfo.value)

    # Y la misma corrida, declarada no comparable con su causa, si es valida.
    corrida = EvalRun(
        run_id="run-1",
        commit_sha="abc123",
        started_at=MOMENTO,
        results=(no_medido,),
        comparable=False,
        non_comparable_cause=NonComparableCause.NOT_MEASURED_CASES,
    )
    assert corrida.comparable is False


def test_una_frase_con_version_mayor_que_uno_declara_su_decision() -> None:
    with pytest.raises(ValidationError) as excinfo:
        CopyEntry(
            key="voice.opening.disclosure",
            locale="es",
            text="Soy una agente virtual.",
            version=2,
            surface=Surface.VOICE,
        )

    assert "voice.opening.disclosure" in str(excinfo.value)

    con_decision = CopyEntry(
        key="voice.opening.disclosure",
        locale="es",
        text="Soy una agente virtual.",
        version=2,
        decision="D26",
        surface=Surface.VOICE,
    )
    assert con_decision.decision == "D26"
