"""El lenguaje cerrado de condiciones (BR1.2, Q1).

Ninguna prueba de aqui abre una base de datos ni toca la configuracion de
ninguna aseguradora: `parse_condition` y `evaluate_condition` son puras y se
prueban solas, con condiciones escritas para cada caso.
"""

from __future__ import annotations

import pytest

from untangle.rules.conditions import (
    Condition,
    ConditionError,
    evaluate_condition,
    fields_read,
    parse_condition,
)


def test_una_condicion_de_igualdad_valida_se_parsea_y_dispara_sobre_su_valor() -> None:
    condicion = parse_condition(
        {"operator": "equals", "field": "injuries_present", "value": True}, rule_id="R1"
    )

    assert evaluate_condition(condicion, {"injuries_present": True}) is True
    assert evaluate_condition(condicion, {"injuries_present": False}) is False


def test_un_campo_ausente_no_dispara_la_condicion_en_lugar_de_fallar() -> None:
    """Convencion 8b: sin dato todavia, la condicion no dispara; no es un error."""
    condicion = parse_condition(
        {"operator": "gte", "field": "claim_amount", "value": 5000}, rule_id="R1"
    )

    assert evaluate_condition(condicion, {}) is False


@pytest.mark.parametrize(
    ("cruda", "insumos", "esperado"),
    [
        ({"operator": "present", "field": "claim_amount"}, {"claim_amount": 100}, True),
        ({"operator": "absent", "field": "claim_amount"}, {}, True),
        (
            {"operator": "in", "field": "unlisted_driver", "value": [True]},
            {"unlisted_driver": True},
            True,
        ),
        ({"operator": "gte", "field": "claim_amount", "value": 5000}, {"claim_amount": 5000}, True),
        ({"operator": "lte", "field": "claim_amount", "value": 500}, {"claim_amount": 501}, False),
    ],
)
def test_cada_operador_de_hoja_se_evalua_segun_su_semantica(
    cruda: dict[str, object], insumos: dict[str, bool | int | float | str], esperado: bool
) -> None:
    condicion = parse_condition(cruda, rule_id="R1")

    assert evaluate_condition(condicion, insumos) is esperado


def test_los_combinadores_componen_condiciones_ya_validadas() -> None:
    condicion = parse_condition(
        {
            "operator": "all",
            "conditions": [
                {"operator": "equals", "field": "injuries_present", "value": True},
                {
                    "operator": "not",
                    "conditions": [{"operator": "present", "field": "fraud_suspected"}],
                },
            ],
        },
        rule_id="R1",
    )

    assert evaluate_condition(condicion, {"injuries_present": True}) is True
    assert (
        evaluate_condition(condicion, {"injuries_present": True, "fraud_suspected": True}) is False
    )


def test_always_dispara_siempre_sin_leer_campos() -> None:
    condicion = parse_condition({"always": True}, rule_id="R-default")

    assert condicion == Condition(operator="always")
    assert evaluate_condition(condicion, {}) is True
    assert fields_read(condicion) == frozenset()


def test_always_no_admite_otras_claves_a_su_lado() -> None:
    with pytest.raises(ConditionError, match="R-default"):
        parse_condition({"always": True, "field": "claim_amount"}, rule_id="R-default")


def test_un_operador_fuera_del_conjunto_cerrado_falla_nombrando_la_regla() -> None:
    with pytest.raises(ConditionError, match="R2"):
        parse_condition(
            {"operator": "matches", "field": "claim_amount", "value": "x"}, rule_id="R2"
        )


def test_un_campo_fuera_del_esquema_falla_nombrando_la_regla() -> None:
    with pytest.raises(ConditionError, match="R3"):
        parse_condition({"operator": "present", "field": "campo_inventado"}, rule_id="R3")


def test_not_exige_exactamente_una_condicion() -> None:
    with pytest.raises(ConditionError, match="R4"):
        parse_condition(
            {
                "operator": "not",
                "conditions": [
                    {"operator": "present", "field": "claim_amount"},
                    {"operator": "present", "field": "fraud_suspected"},
                ],
            },
            rule_id="R4",
        )


def test_fields_read_junta_los_campos_de_todas_las_hojas() -> None:
    condicion = parse_condition(
        {
            "operator": "any",
            "conditions": [
                {"operator": "present", "field": "injuries_present"},
                {"operator": "present", "field": "claim_amount"},
            ],
        },
        rule_id="R5",
    )

    assert fields_read(condicion) == frozenset({"injuries_present", "claim_amount"})
