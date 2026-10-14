"""El motor de evaluacion: precedencia, dinero y explicacion (BR2.1 a BR2.4).

Cada prueba construye su propio conjunto pequeno con `loading.validate_ruleset`
--nunca `rules/triage.yaml` de verdad-- y llama al motor sin pasar por ninguna
base de datos ni por ninguna aseguradora cargada.
"""

from __future__ import annotations

import pytest

from untangle.rules.conditions import parse_condition
from untangle.rules.evaluation import evaluate_ruleset, required_inputs_for
from untangle.rules.loading import validate_ruleset
from untangle.rules.models import RuleEngineError, RuleOutcome, ValidatedRule, ValidatedRuleSet
from untangle.tenancy.models import RuleDefinition, RuleSet

_THEN_POR_DEFECTO: dict[str, object] = {
    "category": "standard_review",
    "touches_money": False,
    "explanation_key": "rules.explain.generic",
}


def _regla(
    rule_id: str,
    *,
    when: dict[str, object],
    then: dict[str, object] | None = None,
    tests: tuple[dict[str, object], ...] = ({"given": {}, "expect": False},),
) -> RuleDefinition:
    return RuleDefinition(
        id=rule_id,
        version=1,
        when=when,
        then=_THEN_POR_DEFECTO | (then or {}),
        tests=tests,
    )


#: Rellena hasta el piso de BR1.1 sin disparar nunca en las pruebas de este
#: archivo: ninguna de ellas fija `fraud_suspected` en sus insumos.
def _relleno(n: int) -> tuple[RuleDefinition, ...]:
    return tuple(
        _regla(
            f"FILLER-{indice:02d}",
            when={"operator": "present", "field": "fraud_suspected"},
            tests=({"given": {}, "expect": False},),
        )
        for indice in range(n)
    )


#: Cuatro reglas con contenido, mas relleno hasta el piso de BR1.1: la de
#: heridos (referral), la de dinero (BR2.3, con una categoria propia que el
#: motor tiene que ignorar), la de caso simple (direct_close) y la por defecto.
def _conjunto() -> ValidatedRuleSet:
    reglas = RuleSet(
        ruleset_version="v1",
        rules=(
            _regla(
                "R-INJURY",
                when={"operator": "equals", "field": "injuries_present", "value": True},
                then={"category": "referral", "explanation_key": "rules.explain.injury"},
                tests=({"given": {"injuries_present": True}, "expect": True},),
            ),
            _regla(
                "R-MONEY",
                # A proposito, su categoria declarada NO es referral: BR2.3
                # tiene que forzarla igual, por la marca de dinero.
                when={"operator": "gte", "field": "claim_amount", "value": 5000},
                then={"touches_money": True, "explanation_key": "rules.explain.money"},
                tests=({"given": {"claim_amount": 5000}, "expect": True},),
            ),
            _regla(
                "R-SIMPLE",
                when={
                    "operator": "all",
                    "conditions": [
                        {"operator": "equals", "field": "injuries_present", "value": False},
                        {
                            "operator": "equals",
                            "field": "other_parties_data_pending",
                            "value": False,
                        },
                    ],
                },
                then={"category": "direct_close", "explanation_key": "rules.explain.simple"},
                tests=(
                    {
                        "given": {"injuries_present": False, "other_parties_data_pending": False},
                        "expect": True,
                    },
                ),
            ),
            _regla(
                "R-DEFAULT",
                when={"always": True},
                then={"explanation_key": "rules.explain.default"},
                tests=({"given": {}, "expect": True},),
            ),
            *_relleno(6),
        ),
    )
    return validate_ruleset(reglas, tenant_id="stonecroft")


def test_solo_dispara_el_default_da_revision_estandar_sin_insumos() -> None:
    resultado = evaluate_ruleset(_conjunto(), {})

    assert resultado.category == "standard_review"
    assert [regla.id for regla in resultado.fired_rules] == ["R-DEFAULT"]
    assert resultado.inputs_snapshot == {}
    assert resultado.explanation_key == "rules.explain.default"


def test_una_regla_de_referral_gana_sobre_el_default() -> None:
    resultado = evaluate_ruleset(_conjunto(), {"injuries_present": True})

    assert resultado.category == "referral"
    assert [regla.id for regla in resultado.fired_rules] == ["R-INJURY"]
    assert resultado.inputs_snapshot == {"injuries_present": "True"}
    assert resultado.explanation_key == "rules.explain.injury"


def test_una_regla_de_dinero_fuerza_referral_pese_a_su_propia_categoria() -> None:
    """BR2.3, compuerta dura AC1.17.3: touches_money manda, sin importar las demas."""
    resultado = evaluate_ruleset(_conjunto(), {"claim_amount": 5000})

    assert resultado.category == "referral"
    assert any(regla.id == "R-MONEY" and regla.touches_money for regla in resultado.fired_rules)
    assert resultado.explanation_key == "rules.explain.money"


def test_un_caso_simple_cierra_directo_y_el_default_no_compite() -> None:
    """BR2.2: la regla por defecto solo entra cuando nada mas disparo."""
    insumos = {"injuries_present": False, "other_parties_data_pending": False}

    resultado = evaluate_ruleset(_conjunto(), insumos)

    assert resultado.category == "direct_close"
    assert [regla.id for regla in resultado.fired_rules] == ["R-SIMPLE"]
    assert resultado.explanation_key == "rules.explain.simple"


def test_sin_datos_un_caso_no_cierra_directo() -> None:
    """Un campo ausente no dispara: el caso vacio va a revision, no a cierre."""
    resultado = evaluate_ruleset(_conjunto(), {"injuries_present": False})

    assert resultado.category == "standard_review"


def test_dinero_gana_sobre_un_caso_simple() -> None:
    insumos = {"injuries_present": False, "other_parties_data_pending": False, "claim_amount": 9000}

    resultado = evaluate_ruleset(_conjunto(), insumos)

    assert resultado.category == "referral"
    assert resultado.explanation_key == "rules.explain.money"


def test_el_resultado_es_deterministico_sobre_los_mismos_insumos() -> None:
    conjunto = _conjunto()
    insumos = {"injuries_present": True, "claim_amount": 5000}

    primero = evaluate_ruleset(conjunto, insumos)
    segundo = evaluate_ruleset(conjunto, insumos)

    assert primero == segundo


def test_required_inputs_for_junta_los_campos_de_todo_el_conjunto() -> None:
    campos = required_inputs_for(_conjunto())

    assert campos == {
        "injuries_present",
        "claim_amount",
        "other_parties_data_pending",
        "fraud_suspected",
    }


def test_si_ninguna_regla_dispara_el_motor_declara_un_fallo_de_invariante() -> None:
    """Defensivo: con un conjunto valido esto no deberia poder pasar (BR1.3)."""
    condicion = parse_condition(
        {"operator": "equals", "field": "injuries_present", "value": True}, rule_id="R-IMPOSIBLE"
    )
    regla = ValidatedRule(
        definition=_regla(
            "R-IMPOSIBLE",
            when={"operator": "equals", "field": "injuries_present", "value": True},
            tests=({"given": {"injuries_present": True}, "expect": True},),
        ),
        condition=condicion,
        then=RuleOutcome(
            category="standard_review", touches_money=False, explanation_key="rules.explain.x"
        ),
    )
    conjunto = ValidatedRuleSet(
        tenant_id="stonecroft", ruleset_version="v1", rules=(regla,), default_rule=regla
    )

    with pytest.raises(RuleEngineError, match=r"BR1\.3"):
        evaluate_ruleset(conjunto, {})
