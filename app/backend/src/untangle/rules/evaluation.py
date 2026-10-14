"""El motor de evaluacion: precedencia, marca de dinero y explicacion (BR2.1 a BR2.4, C-19).

**Puro y determinista** (BR2.1): ninguna llamada de red, ningun reloj, ninguna
aleatoriedad, y ningun cliente de modelo en la cadena de llamadas -- el
contrato de importacion `reglas-sin-proveedores` de `.importlinter` lo
comprueba (SEC-U9.1). La misma entrada sobre el mismo conjunto da siempre la
misma salida.

Vive separado de `api.py` porque es la unica pieza que necesitan las sondas de
evaluacion (Q3): miden el motor real sin arrastrar la superficie asincrona que
usara el nodo `decision`.
"""

from __future__ import annotations

from collections.abc import Mapping

from untangle.rules.conditions import evaluate_condition, fields_read, gte_thresholds
from untangle.rules.fields import CLAIM_AMOUNT, RuleValue
from untangle.rules.models import (
    CATEGORY_RANK,
    Category,
    FiredRule,
    RuleEngineError,
    RuleEvaluationView,
    ValidatedRuleSet,
)


def required_inputs_for(ruleset: ValidatedRuleSet) -> frozenset[str]:
    """Los campos que **todo** el conjunto lee, para que la captura sepa que pedir (C-19)."""
    return frozenset().union(*(fields_read(regla.condition) for regla in ruleset.rules))


def amount_steps_for(ruleset: ValidatedRuleSet) -> tuple[int, ...]:
    """Los montos desde los que las reglas de ese conjunto cambian lo que hacen, de menor a mayor.

    Los valores distintos de las condiciones `gte` sobre el monto, tal cual los declara el
    archivo de la aseguradora: la pantalla de quien anota los muestra para que sepa en que
    cifras importa lo que escribe, y no los repite escritos en su codigo (si las reglas
    cambian de umbral, la ayuda cambia con ellas). Vacio si ninguna regla lee el monto.
    """
    pasos = frozenset[int]().union(
        *(gte_thresholds(regla.condition, CLAIM_AMOUNT) for regla in ruleset.rules)
    )
    return tuple(sorted(pasos))


def evaluate_ruleset(
    ruleset: ValidatedRuleSet, inputs: Mapping[str, RuleValue]
) -> RuleEvaluationView:
    """Evalua un conjunto ya validado sobre los insumos de un caso (F2, BR2.1 a BR2.4)."""
    defecto = ruleset.default_rule
    disparadas = [
        regla
        for regla in ruleset.rules
        if regla is not defecto and evaluate_condition(regla.condition, inputs)
    ]
    if not disparadas:
        # La regla por defecto solo entra cuando nada mas disparo (BR2.2): si
        # compitiera siempre, su revision estandar le ganaria a todo cierre directo.
        if not evaluate_condition(defecto.condition, inputs):
            # Invariante de carga rota (BR1.3), no un resultado de negocio.
            msg = (
                f"ninguna regla de '{ruleset.tenant_id}' disparo, ni siquiera la regla por "
                "defecto; revise la carga de este conjunto (BR1.3)"
            )
            raise RuleEngineError(msg)
        disparadas = [defecto]

    con_dinero = [regla for regla in disparadas if regla.then.touches_money]
    categoria: Category
    if con_dinero:
        # Una regla de dinero o cobertura fuerza la derivacion, sin importar las
        # demas -- incluida su propia categoria declarada (BR2.3, compuerta dura
        # AC1.17.3). La explicacion es la de la primera, en el orden del archivo,
        # para que dos corridas del mismo conjunto elijan siempre la misma.
        decisiva = con_dinero[0]
        categoria = "referral"
    else:
        # Gana la categoria mas prudente; con empate, la primera en el orden del
        # archivo (BR2.2).
        decisiva = max(disparadas, key=lambda regla: CATEGORY_RANK[regla.then.category])
        categoria = decisiva.then.category

    # Solo los campos que leyeron las reglas disparadas (BR2.4), no todo el
    # conjunto: `required_inputs_for` es quien responde por el conjunto entero.
    campos_leidos = frozenset().union(*(fields_read(regla.condition) for regla in disparadas))
    insumos = {campo: str(inputs[campo]) for campo in sorted(campos_leidos) if campo in inputs}
    reglas_disparadas = tuple(
        FiredRule(id=regla.id, version=regla.version, touches_money=regla.then.touches_money)
        for regla in disparadas
    )

    return RuleEvaluationView(
        category=categoria,
        fired_rules=reglas_disparadas,
        inputs_snapshot=insumos,
        explanation_key=decisiva.then.explanation_key,
        ruleset_version=ruleset.ruleset_version,
    )
