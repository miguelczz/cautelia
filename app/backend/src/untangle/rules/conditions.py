"""El lenguaje cerrado de condiciones de una regla (BR1.2, FD-U9-1, Q1).

Sin lenguaje de expresiones: un arbol pequeno de operadores fijos sobre el
vocabulario cerrado de `fields.py`. Se valida entero al cargar -- operador,
campo y forma del valor -- para que una regla con una condicion rota no arranque
en silencio (BR1.2).

`always` no es un operador de comparacion: marca una regla que dispara siempre.
La lleva la regla por defecto, con revision estandar (BR1.3, Q2), y la de la
agencia, que deriva siempre (BR2.6); `loading` impide cualquier otro uso.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from untangle.rules.fields import KNOWN_FIELDS, RuleValue

#: Los seis operadores de hoja: comparan un campo contra un valor (Q1).
LEAF_OPERATORS = ("equals", "in", "present", "absent", "gte", "lte")
#: Los tres combinadores: componen condiciones ya validadas.
COMBINATOR_OPERATORS = ("all", "any", "not")
#: La marca de una regla que dispara siempre (BR1.3, BR2.6).
ALWAYS = "always"


class ConditionError(ValueError):
    """Una condicion invalida. El mensaje nombra la regla y que se rompio."""


@dataclass(frozen=True)
class Condition:
    """Una condicion ya validada, hoja o combinador."""

    operator: str
    field: str | None = None
    value: RuleValue | tuple[RuleValue, ...] | None = None
    conditions: tuple[Condition, ...] = ()


def _parse_field(raw: object, *, rule_id: str, operator: str, vocabulary: frozenset[str]) -> str:
    if not isinstance(raw, str) or raw not in vocabulary:
        msg = (
            f"la regla '{rule_id}' usa el operador '{operator}' sobre el campo "
            f"'{raw}', que no existe en el esquema de campos del motor (BR1.2)"
        )
        raise ConditionError(msg)
    return raw


def _parse_leaf(
    raw: Mapping[str, object], *, rule_id: str, operator: str, vocabulary: frozenset[str]
) -> Condition:
    campo = _parse_field(
        raw.get("field"), rule_id=rule_id, operator=operator, vocabulary=vocabulary
    )

    if operator in ("present", "absent"):
        return Condition(operator=operator, field=campo)

    if "value" not in raw:
        msg = f"la regla '{rule_id}' usa '{operator}' sobre '{campo}' sin declarar 'value' (BR1.2)"
        raise ConditionError(msg)
    valor = raw["value"]

    if operator == "in":
        if not isinstance(valor, Sequence) or isinstance(valor, str) or not valor:
            msg = (
                f"la regla '{rule_id}' usa 'in' sobre '{campo}' con un valor que no es "
                "una lista no vacia (BR1.2)"
            )
            raise ConditionError(msg)
        return Condition(operator=operator, field=campo, value=tuple(valor))

    if operator in ("gte", "lte") and not isinstance(valor, int | float):
        msg = (
            f"la regla '{rule_id}' usa '{operator}' sobre '{campo}' con un valor no numerico "
            "(BR1.2)"
        )
        raise ConditionError(msg)
    if not isinstance(valor, bool | int | float | str):
        msg = (
            f"la regla '{rule_id}' usa '{operator}' sobre '{campo}' con un valor de tipo "
            f"{type(valor).__name__}, fuera de lo que un campo puede valer (BR1.2)"
        )
        raise ConditionError(msg)

    return Condition(operator=operator, field=campo, value=valor)


def _parse_combinator(
    raw: Mapping[str, object], *, rule_id: str, operator: str, vocabulary: frozenset[str]
) -> Condition:
    hijas_crudas = raw.get("conditions")
    if not isinstance(hijas_crudas, Sequence) or isinstance(hijas_crudas, str) or not hijas_crudas:
        msg = f"la regla '{rule_id}' usa '{operator}' sin una lista 'conditions' no vacia (BR1.2)"
        raise ConditionError(msg)
    if operator == "not" and len(hijas_crudas) != 1:
        msg = f"la regla '{rule_id}' usa 'not' con {len(hijas_crudas)} condiciones; se espera una"
        raise ConditionError(msg)

    hijas = tuple(
        parse_condition(hija, rule_id=rule_id, vocabulary=vocabulary) for hija in hijas_crudas
    )
    return Condition(operator=operator, conditions=hijas)


def parse_condition(
    raw: object, *, rule_id: str, vocabulary: frozenset[str] = KNOWN_FIELDS
) -> Condition:
    """Valida una condicion contra el conjunto cerrado de operadores (BR1.2).

    `vocabulary` es lo que esa familia de reglas puede leer: por omision el
    vocabulario entero, y cada cargador pasa el de la suya (triage o
    elegibilidad) para que un conjunto no lea campos de otra familia.
    """
    if not isinstance(raw, Mapping):
        msg = f"la regla '{rule_id}' declara 'when' como {type(raw).__name__}, no un mapa (BR1.2)"
        raise ConditionError(msg)

    if raw.get(ALWAYS) is True:
        if set(raw) != {ALWAYS}:
            msg = f"la regla '{rule_id}' mezcla '{ALWAYS}' con otras claves en 'when' (BR1.3)"
            raise ConditionError(msg)
        return Condition(operator=ALWAYS)

    operator = raw.get("operator")
    if operator in LEAF_OPERATORS:
        return _parse_leaf(raw, rule_id=rule_id, operator=operator, vocabulary=vocabulary)
    if operator in COMBINATOR_OPERATORS:
        return _parse_combinator(raw, rule_id=rule_id, operator=operator, vocabulary=vocabulary)

    msg = (
        f"la regla '{rule_id}' declara el operador '{operator}', fuera del conjunto cerrado "
        f"{LEAF_OPERATORS + COMBINATOR_OPERATORS} (BR1.2)"
    )
    raise ConditionError(msg)


def evaluate_condition(condition: Condition, inputs: Mapping[str, RuleValue]) -> bool:
    """Evalua una condicion ya validada. Un campo ausente nunca dispara (BR2.1).

    Determinista: sin reloj, sin red y sin aleatoriedad. La misma condicion
    sobre los mismos insumos da siempre el mismo resultado.
    """
    if condition.operator == ALWAYS:
        return True
    if condition.operator in COMBINATOR_OPERATORS:
        return _evaluate_combinator(condition, inputs)
    return _evaluate_leaf(condition, inputs)


def _evaluate_combinator(condition: Condition, inputs: Mapping[str, RuleValue]) -> bool:
    if condition.operator == "all":
        return all(evaluate_condition(hija, inputs) for hija in condition.conditions)
    if condition.operator == "any":
        return any(evaluate_condition(hija, inputs) for hija in condition.conditions)
    return not evaluate_condition(condition.conditions[0], inputs)  # "not"


def _evaluate_leaf(condition: Condition, inputs: Mapping[str, RuleValue]) -> bool:
    assert condition.field is not None  # noqa: S101 -- toda hoja se parseo con su campo
    presente = condition.field in inputs and inputs[condition.field] is not None

    if condition.operator == "present":
        return presente
    if condition.operator == "absent":
        return not presente
    if not presente:
        # Sin dato todavia: la condicion no dispara, no es un error (convencion
        # 8b). Es el estado normal mientras la captura sigue en curso.
        return False
    return _compare(condition, inputs[condition.field])


def _compare(condition: Condition, valor: RuleValue) -> bool:
    """Los cuatro operadores que necesitan el valor presente (equals, in, gte, lte)."""
    if condition.operator == "equals":
        return valor == condition.value
    if condition.operator == "in":
        assert isinstance(condition.value, tuple)  # noqa: S101 -- lo garantiza el parseo
        return valor in condition.value

    assert isinstance(valor, int | float) and isinstance(condition.value, int | float)  # noqa: S101 -- lo garantiza el parseo
    if condition.operator == "gte":
        return valor >= condition.value
    return valor <= condition.value  # "lte": el unico operador que queda


def fields_read(condition: Condition) -> frozenset[str]:
    """Los campos que una condicion, ya validada, lee (para `required_inputs`)."""
    if condition.field is not None:
        return frozenset({condition.field})
    return frozenset().union(*(fields_read(hija) for hija in condition.conditions))


def gte_thresholds(condition: Condition, field: str) -> frozenset[int]:
    """Los valores desde los que una condicion `gte` sobre ese campo empieza a cumplirse.

    El campo es de cifras enteras (el monto va en miles de pesos), asi que un umbral con
    decimales se redondea hacia arriba: `>= 1000.5` y `>= 1001` dicen lo mismo sobre un entero,
    y quien lo lee necesita el primer numero que cambia el resultado.

    Recorre `all` y `any`, donde el umbral sigue siendo un punto desde el que la regla puede
    cumplirse. **No entra en `not`**: ahi `gte` quiere decir "por debajo de", que es otro
    umbral y no el que se muestra. Un valor booleano no es un umbral (`True >= 1` seria cierto
    en Python, y nadie escribio una regla de monto con un si).
    """
    if condition.field is None:
        if condition.operator == "not":
            return frozenset()
        return frozenset().union(*(gte_thresholds(hija, field) for hija in condition.conditions))
    valor = condition.value
    if (
        condition.operator == "gte"
        and condition.field == field
        and isinstance(valor, int | float)
        and not isinstance(valor, bool)
    ):
        return frozenset({math.ceil(valor)})
    return frozenset()
