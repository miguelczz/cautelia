"""La superficie publica del motor de reglas (C-19, BR2.1 a BR2.4, BR3.1).

Lo que U11 (captura), U12 (nodo `decision`), U14 (mostrar la regla) y U19
(elegibilidad) consumen de U9, y nada mas.

**Enmienda de esta generacion de codigo.** El boceto de C-19 recibia
`evaluate(case: CaseView, ...)`; lo construido recibe `tenant_id` y `inputs`
sueltos. La razon es de capas y no de preferencia: `rules` esta **por debajo**
de `case_record` en `.importlinter` (convencion de direccion de dependencias
del equipo), asi que este paquete no puede importar `CaseView` sin invertir esa
direccion. Quien traduce el estado del caso a `inputs` es quien esta por
encima de los dos -- el nodo `decision`, paso 7 de esta unidad -- y ese es
exactamente el lugar correcto: la captura (U11) ya sabe, por
`required_inputs()`, que campos tiene que dejar escritos (C-19).

| C-19 | Aqui | Por que difiere |
| --- | --- | --- |
| `evaluate(case: CaseView, *, ruleset_version=None)` | `evaluate(tenant_id, inputs: Mapping[str, RuleValue], *, ruleset_version=None)` | `rules` no puede importar `case_record`; el llamador traduce el estado tipado a insumos |
| (no declaradas) | `save_evaluation`, `evaluations_for` | El paso 3 de esta unidad construye la persistencia (BR4.1, CG-U9-4); el nodo `decision` del paso 7 las necesita para guardar y para no duplicar al reanudar (ADR-003) |

Ningun cliente de modelo aparece en la cadena de llamadas (BR2.1, SEC-U9.1): el
contrato `forbidden` `reglas-sin-proveedores` de `.importlinter` lo comprueba.
"""

from __future__ import annotations

from collections.abc import Mapping

from untangle.rules import loading
from untangle.rules.conditions import fields_read
from untangle.rules.evaluation import amount_steps_for, evaluate_ruleset, required_inputs_for
from untangle.rules.fields import KNOWN_FIELDS, RuleValue
from untangle.rules.models import (
    Category,
    FiredRule,
    RuleEngineError,
    RuleEvaluation,
    RuleEvaluationView,
    RuleNotConfiguredError,
    RuleValidationError,
    ValidatedRuleSet,
)
from untangle.rules.repository import evaluations_for, save_evaluation
from untangle.tenancy.models import TenantId


class RulesetVersionMismatchError(LookupError):
    """Se pidio una version de conjunto que no es la cargada.

    Este paquete no guarda todavia historia de versiones anteriores; pedir una
    version distinta a la cargada falla en el acto en vez de evaluar en
    silencio contra la version equivocada.
    """


def _ruleset_for(tenant_id: TenantId, ruleset_version: str | None) -> ValidatedRuleSet:
    ruleset = loading.require(tenant_id)
    if ruleset_version is not None and ruleset_version != ruleset.ruleset_version:
        msg = (
            f"se pidio la version '{ruleset_version}' del conjunto de '{tenant_id}' y la "
            f"cargada es '{ruleset.ruleset_version}'; no hay historia de versiones anteriores"
        )
        raise RulesetVersionMismatchError(msg)
    return ruleset


async def evaluate(
    tenant_id: TenantId,
    inputs: Mapping[str, RuleValue],
    *,
    ruleset_version: str | None = None,
) -> RuleEvaluationView:
    """Determinista y sin modelo (C-19, BR2.1). Async por la convencion del nodo que la llama."""
    ruleset = _ruleset_for(tenant_id, ruleset_version)
    return evaluate_ruleset(ruleset, inputs)


def required_inputs(*, tenant_id: TenantId, ruleset_version: str | None = None) -> frozenset[str]:
    """Los campos que el conjunto de esa aseguradora lee (C-19); U11 los captura."""
    ruleset = _ruleset_for(tenant_id, ruleset_version)
    return required_inputs_for(ruleset)


def amount_steps(*, tenant_id: TenantId) -> tuple[int, ...]:
    """Los montos desde los que cambian las reglas de esa aseguradora, de menor a mayor.

    En la cifra interna del motor (miles de pesos), igual que el campo que las reglas
    comparan; quien lo muestra lo convierte. Vacio si ninguna regla lee el monto. Levanta
    `RuleNotConfiguredError` si la aseguradora no tiene un conjunto cargado.
    """
    return amount_steps_for(_ruleset_for(tenant_id, None))


def rule_ids_reading(*, tenant_id: TenantId, fields: frozenset[str]) -> frozenset[str]:
    """Los identificadores de las reglas de esa aseguradora que leen alguno de esos campos.

    Lo pide la bandeja para no mostrarle al asegurado que regla dispararon los datos que
    anoto un ajustador: el identificador de una regla de fraude, escrito en su pantalla,
    cuenta lo que la anotacion no debe contar. (Los que anoto el mismo, haciendo de ajustador
    en la demostracion, si los ve: la bandeja decide cuando pedir esta lista.) Levanta `RuleNotConfiguredError` si la
    aseguradora no tiene un conjunto cargado.
    """
    ruleset = _ruleset_for(tenant_id, None)
    return frozenset(regla.id for regla in ruleset.rules if fields_read(regla.condition) & fields)


__all__ = [
    "KNOWN_FIELDS",
    "Category",
    "FiredRule",
    "RuleEngineError",
    "RuleEvaluation",
    "RuleEvaluationView",
    "RuleNotConfiguredError",
    "RuleValidationError",
    "RulesetVersionMismatchError",
    "amount_steps",
    "evaluate",
    "evaluations_for",
    "required_inputs",
    "rule_ids_reading",
    "save_evaluation",
]
