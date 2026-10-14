"""Los tipos que el motor de reglas mueve, de la condicion ya cargada a la fila guardada.

Tres familias, en el orden en que una regla las atraviesa:

1. **Lo que se carga**: `RuleOutcome` (el `then` de una regla, ya validado) y
   `ValidatedRule` / `ValidatedRuleSet` (una regla y un conjunto, con su
   condicion ya parseada y sus pruebas ya corridas). Internos del paquete.
2. **Lo que devuelve `evaluate()`**: `FiredRule` y `RuleEvaluationView` (C-19),
   como `dataclass` congelado, igual que `CaseView` de U4: son vistas de solo
   lectura para codigo, no entidades con invariantes que validar desde datos
   externos.
3. **Lo que se guarda**: `RuleEvaluation`, un modelo `Frozen` con las mismas
   invariantes que `entities.md` declara, porque esta si nace de una fila de
   base de datos y de lo que devuelve `evaluate()`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from untangle.base import Frozen
from untangle.rules.conditions import Condition
from untangle.tenancy.models import TENANT_ID_PATTERN, RuleDefinition, TenantId

#: Tope de los identificadores opacos, igual que en U10 (`ID_MAX_LENGTH`).
ID_MAX_LENGTH = 64

#: Forma de la clave de explicacion del catalogo, igual que `CATALOG_KEY_PATTERN`
#: de U10: segmentos en minusculas separados por puntos.
EXPLANATION_KEY_PATTERN = r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$"
EXPLANATION_KEY_LEN = 96

#: Las tres categorias cerradas de una decision (BR2.2).
Category = Literal["direct_close", "standard_review", "referral"]
CATEGORIES: tuple[Category, ...] = ("direct_close", "standard_review", "referral")

#: El orden de prudencia: el indice mas alto gana (BR2.2).
CATEGORY_RANK: dict[Category, int] = {
    "direct_close": 0,
    "standard_review": 1,
    "referral": 2,
}


class RuleValidationError(ValueError):
    """Una regla o un conjunto no se pudo validar. El mensaje nombra la regla."""


class RuleEngineError(RuntimeError):
    """Un conjunto ya validado no se comporto como sus invariantes prometen.

    No es un error de datos de entrada: si `evaluate()` lo levanta, es que una
    invariante de carga (BR1.3) se rompio despues de validar, y eso es un fallo
    del motor, no del caso.
    """


class RuleNotConfiguredError(LookupError):
    """La aseguradora no tiene un conjunto de reglas cargado y valido."""


@dataclass(frozen=True)
class RuleOutcome:
    """El `then` de una regla, ya validado (BR1.2)."""

    category: Category
    touches_money: bool
    explanation_key: str


@dataclass(frozen=True)
class ValidatedRule:
    """Una regla con su condicion parseada y su `then` validado."""

    definition: RuleDefinition
    condition: Condition
    then: RuleOutcome

    @property
    def id(self) -> str:
        return self.definition.id

    @property
    def version(self) -> int:
        return self.definition.version


@dataclass(frozen=True)
class ValidatedRuleSet:
    """El conjunto de una aseguradora, listo para evaluar (BR1.1 a BR1.4)."""

    tenant_id: TenantId
    ruleset_version: str
    rules: tuple[ValidatedRule, ...]
    default_rule: ValidatedRule


@dataclass(frozen=True)
class FiredRule:
    """Una regla disparada: su identificador, su version y su marca de dinero (C-19)."""

    id: str
    version: int
    touches_money: bool


@dataclass(frozen=True)
class RuleEvaluationView:
    """Lo que devuelve `evaluate()`: la categoria, sus reglas y su explicacion (C-19).

    `ruleset_version` no esta en el boceto de C-19 y es una adicion de esta
    generacion de codigo (paso 7): el nodo `decision` necesita la version del
    conjunto que decidio para poder construir el `RuleEvaluation` que guarda, y
    `evaluate_ruleset` es quien la conoce.
    """

    category: Category
    fired_rules: tuple[FiredRule, ...]
    inputs_snapshot: dict[str, str]
    explanation_key: str
    ruleset_version: str


class RuleEvaluation(Frozen):
    """La fila guardada de una evaluacion (`entities.md`, BR2.4, BR4.1)."""

    evaluation_id: str = Field(min_length=1, max_length=ID_MAX_LENGTH)
    tenant_id: TenantId = Field(pattern=TENANT_ID_PATTERN)
    case_id: str = Field(min_length=1, max_length=ID_MAX_LENGTH)
    ruleset_version: str = Field(min_length=1)
    category: Category
    fired_rules: tuple[FiredRule, ...]
    inputs_snapshot: dict[str, str]
    explanation_key: str = Field(pattern=EXPLANATION_KEY_PATTERN, max_length=EXPLANATION_KEY_LEN)
    evaluated_at: AwareDatetime

    @model_validator(mode="after")
    def _las_reglas_disparadas_nunca_estan_vacias(self) -> Self:
        # Al menos la regla por defecto siempre dispara (BR1.3, BR2.4).
        if not self.fired_rules:
            msg = f"la evaluacion '{self.evaluation_id}' no trae ninguna regla disparada (BR2.4)"
            raise ValueError(msg)
        return self
