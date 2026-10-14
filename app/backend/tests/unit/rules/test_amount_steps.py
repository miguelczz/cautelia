"""Los montos desde los que cambian las reglas: lo que la pantalla de quien anota le muestra.

Dos cosas distintas. Con los conjuntos reales de las aseguradoras, que la pantalla recibe los
umbrales que de verdad estan en el archivo; con conjuntos pequenos escritos para cada caso, que
la lectura de las condiciones es la correcta (anidadas si, "por debajo de" no, duplicados una
sola vez, en orden aunque el archivo no lo este).
"""

from __future__ import annotations

import pytest

from untangle.rules import api as reglas
from untangle.rules.conditions import evaluate_condition, parse_condition
from untangle.rules.evaluation import amount_steps_for
from untangle.rules.loading import validate_ruleset
from untangle.rules.models import RuleNotConfiguredError, ValidatedRuleSet
from untangle.tenancy.models import RuleDefinition, RuleSet

_THEN: dict[str, object] = {
    "category": "referral",
    "touches_money": True,
    "explanation_key": "rules.explain.amount_review",
}

_POR_DEFECTO = RuleDefinition(
    id="R-DEFAULT",
    version=1,
    when={"always": True},
    then=_THEN | {"category": "standard_review", "touches_money": False},
    tests=({"given": {}, "expect": True},),
)


def _regla(rule_id: str, when: dict[str, object]) -> RuleDefinition:
    """Una regla de prueba, con el unico caso que el cargador le exige: el de sin insumos.

    Lo que la condicion da sobre un mapa vacio se calcula con el mismo motor, porque una
    negacion dispara cuando falta el dato y el cargador rechazaria un `expect` escrito a mano.
    """
    sin_insumos = evaluate_condition(parse_condition(when, rule_id=rule_id), {})
    return RuleDefinition(
        id=rule_id, version=1, when=when, then=_THEN, tests=({"given": {}, "expect": sin_insumos},)
    )


def _gte(valor: float | bool, campo: str = "claim_amount") -> dict[str, object]:
    return {"operator": "gte", "field": campo, "value": valor}


def _conjunto(*cuando: dict[str, object]) -> ValidatedRuleSet:
    """Las condiciones dadas, mas relleno que nunca dispara hasta el piso de diez reglas."""
    dadas = tuple(_regla(f"R-{i:02d}", c) for i, c in enumerate(cuando))
    relleno = tuple(
        _regla(f"FILLER-{i:02d}", {"operator": "present", "field": "unlisted_driver"})
        for i in range(9 - len(dadas))
    )
    return validate_ruleset(
        RuleSet(ruleset_version="v1", rules=(*dadas, *relleno, _POR_DEFECTO)),
        tenant_id="stonecroft",
    )


def _pasos(*cuando: dict[str, object]) -> tuple[int, ...]:
    return amount_steps_for(_conjunto(*cuando))


# --- Las aseguradoras reales ----------------------------------------------------------


@pytest.mark.parametrize("aseguradora", ["knotwell", "stonecroft", "sunmeadow"])
def test_cada_aseguradora_entrega_los_umbrales_de_su_archivo(aseguradora: str) -> None:
    # Los tres archivos miran el monto en dos umbrales `gte` y en un `lte` que no es umbral
    # de "desde": la ayuda del visitante tiene que listar los dos primeros y nada mas.
    assert reglas.amount_steps(tenant_id=aseguradora) == (1000, 10000)


def test_una_aseguradora_sin_reglas_cargadas_lo_dice() -> None:
    with pytest.raises(RuleNotConfiguredError):
        reglas.amount_steps(tenant_id="no-existe")


# --- La lectura de las condiciones ----------------------------------------------------


def test_los_umbrales_salen_de_menor_a_mayor_aunque_el_archivo_los_declare_al_reves() -> None:
    assert _pasos(_gte(10000), _gte(500), _gte(2500)) == (500, 2500, 10000)


def test_un_umbral_repetido_en_dos_reglas_aparece_una_vez() -> None:
    assert _pasos(_gte(1000), _gte(1000), _gte(4000)) == (1000, 4000)


def test_sin_ninguna_regla_sobre_el_monto_no_hay_umbrales() -> None:
    assert _pasos({"operator": "equals", "field": "fraud_suspected", "value": True}) == ()


def test_un_umbral_de_otro_campo_no_es_del_monto() -> None:
    assert _pasos(_gte(7, campo="injuries_present")) == ()


def test_un_por_debajo_de_no_es_un_desde() -> None:
    assert _pasos({"operator": "lte", "field": "claim_amount", "value": 999}, _gte(1000)) == (1000,)


def test_un_umbral_dentro_de_todas_y_de_alguna_se_encuentra() -> None:
    anidadas: dict[str, object] = {
        "operator": "any",
        "conditions": [
            {"operator": "equals", "field": "fraud_suspected", "value": True},
            {"operator": "all", "conditions": [_gte(3000), _gte(8000, campo="claim_amount")]},
        ],
    }

    assert _pasos(anidadas) == (3000, 8000)


def test_un_umbral_bajo_una_negacion_no_se_cuenta() -> None:
    """`not (monto >= 5000)` dispara por debajo de 5000: mostrar "desde 5000" seria mentir."""
    negada: dict[str, object] = {"operator": "not", "conditions": [_gte(5000)]}

    assert _pasos(negada, _gte(1000)) == (1000,)


def test_un_umbral_con_decimales_se_redondea_al_primer_entero_que_lo_cumple() -> None:
    assert _pasos(_gte(1000.5)) == (1001,)


def test_un_booleano_no_es_un_umbral() -> None:
    # `True >= 1` es cierto en Python; si alguien escribiera una regla asi, no es un monto.
    assert _pasos(_gte(True), _gte(2000)) == (2000,)
