"""El repositorio de U9: guardar por identificador, sin duplicar (BR3.1, ADR-003).

Mismo patron que `compliance/controls/repository.py` (U10): la escritura es
idempotente por identificador, y quien reintenta con el mismo recibe la fila
que quedo guardada la primera vez.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from untangle.rules.models import FiredRule, RuleEvaluation
from untangle.rules.repository import evaluations_for, save_evaluation

from .conftest import AHORA, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u9")


def _evaluacion(
    *, tenant_id: str, case_id: str, evaluation_id: str, **cambios: object
) -> RuleEvaluation:
    base = {
        "evaluation_id": evaluation_id,
        "tenant_id": tenant_id,
        "case_id": case_id,
        "ruleset_version": "v1",
        "category": "referral",
        "fired_rules": (FiredRule(id="R-INJURY", version=1, touches_money=False),),
        "inputs_snapshot": {"injuries_present": "True"},
        "explanation_key": "rules.explain.injury",
        "evaluated_at": AHORA,
    }
    return RuleEvaluation.model_validate(base | cambios)


async def test_guardar_una_evaluacion_la_deja_leible(dos_aseguradoras: tuple[str, str]) -> None:
    primera, _ = dos_aseguradoras
    caso = await nuevo_caso(primera)
    evaluacion = _evaluacion(tenant_id=primera, case_id=caso.case_id, evaluation_id="ev-1")

    guardada = await save_evaluation(evaluacion)
    leidas = await evaluations_for(primera, caso.case_id)

    assert guardada == evaluacion
    assert leidas == (evaluacion,)


async def test_guardar_dos_veces_el_mismo_identificador_no_duplica(
    dos_aseguradoras: tuple[str, str],
) -> None:
    primera, _ = dos_aseguradoras
    caso = await nuevo_caso(primera)
    evaluacion = _evaluacion(tenant_id=primera, case_id=caso.case_id, evaluation_id="ev-1")

    primer_guardado = await save_evaluation(evaluacion)
    segundo_guardado = await save_evaluation(evaluacion)
    leidas = await evaluations_for(primera, caso.case_id)

    assert primer_guardado == segundo_guardado == evaluacion
    assert len(leidas) == 1


async def test_cada_aseguradora_solo_lee_sus_propias_evaluaciones(
    dos_aseguradoras: tuple[str, str],
) -> None:
    primera, segunda = dos_aseguradoras
    caso_primera = await nuevo_caso(primera)
    caso_segunda = await nuevo_caso(segunda)
    await save_evaluation(
        _evaluacion(tenant_id=primera, case_id=caso_primera.case_id, evaluation_id="ev-a")
    )
    await save_evaluation(
        _evaluacion(tenant_id=segunda, case_id=caso_segunda.case_id, evaluation_id="ev-b")
    )

    leidas_primera = await evaluations_for(primera, caso_primera.case_id)
    leidas_segunda = await evaluations_for(segunda, caso_segunda.case_id)

    assert [e.tenant_id for e in leidas_primera] == [primera]
    assert [e.tenant_id for e in leidas_segunda] == [segunda]


async def test_las_evaluaciones_de_un_caso_se_leen_en_el_orden_en_que_se_hicieron(
    dos_aseguradoras: tuple[str, str],
) -> None:
    primera, _ = dos_aseguradoras
    caso = await nuevo_caso(primera)
    primera_evaluacion = _evaluacion(
        tenant_id=primera, case_id=caso.case_id, evaluation_id="ev-1", evaluated_at=AHORA
    )
    segunda_evaluacion = _evaluacion(
        tenant_id=primera,
        case_id=caso.case_id,
        evaluation_id="ev-2",
        evaluated_at=AHORA + timedelta(minutes=5),
    )
    await save_evaluation(segunda_evaluacion)
    await save_evaluation(primera_evaluacion)

    leidas = await evaluations_for(primera, caso.case_id)

    assert [e.evaluation_id for e in leidas] == ["ev-1", "ev-2"]
