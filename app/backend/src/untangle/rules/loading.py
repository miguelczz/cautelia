"""Carga y valida el significado de un conjunto de reglas (BR1.1 a BR1.4, C-19).

`tenancy.config` ya valida la **forma** del archivo (`RuleSet.model_validate`,
U2); este modulo valida su **significado** (U9): los operadores cerrados, el
conteo, la regla por defecto y las pruebas de cada regla (`entities.md`: "la
forma es de U2, el significado es de U9").

Cada aseguradora se valida por separado, igual que `tenancy.config.load()`: una
carpeta rota apaga solo esa aseguradora, con el identificador de la regla que
fallo, y las demas siguen (BR1.1).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from untangle import observability, paths
from untangle.rules.conditions import (
    ALWAYS,
    Condition,
    ConditionError,
    evaluate_condition,
    parse_condition,
)
from untangle.rules.fields import TRIAGE_FIELDS
from untangle.rules.models import (
    CATEGORIES,
    EXPLANATION_KEY_LEN,
    EXPLANATION_KEY_PATTERN,
    RuleNotConfiguredError,
    RuleOutcome,
    RuleValidationError,
    ValidatedRule,
    ValidatedRuleSet,
)
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import RuleDefinition, RuleSet, TenantConfigError, TenantId

#: El nombre fijo del archivo de reglas de una aseguradora (`entities.md`).
RULESET_FILE = "triage.yaml"

#: El conteo cerrado de BR1.1.
MIN_RULES = 10
MAX_RULES = 20


@dataclass(frozen=True)
class UnavailableRuleset:
    """Una aseguradora cuyo conjunto de reglas no valido. Nombra por que."""

    tenant_id: TenantId
    detail: str


@dataclass(frozen=True)
class LoadedRulesets:
    """Lo que quedo tras validar cada aseguradora: lo que vale y lo que no."""

    available: Mapping[TenantId, ValidatedRuleSet]
    unavailable: tuple[UnavailableRuleset, ...]

    def get(self, tenant_id: TenantId) -> ValidatedRuleSet | None:
        return self.available.get(tenant_id)


def _parse_then(raw: Mapping[str, object], *, rule_id: str) -> RuleOutcome:
    """Valida `then`: la categoria cerrada, la marca de dinero y la clave (`entities.md`)."""
    categoria = raw.get("category")
    if categoria not in CATEGORIES:
        msg = (
            f"la regla '{rule_id}' declara 'then.category' como '{categoria}', fuera de "
            f"{CATEGORIES} (entities.md)"
        )
        raise RuleValidationError(msg)

    dinero = raw.get("touches_money", False)
    if not isinstance(dinero, bool):
        msg = (
            f"la regla '{rule_id}' declara 'then.touches_money' como "
            f"{type(dinero).__name__}, no booleano (entities.md)"
        )
        raise RuleValidationError(msg)

    clave = raw.get("explanation_key")
    if not isinstance(clave, str):
        msg = (
            f"la regla '{rule_id}' declara 'then.explanation_key' como {type(clave).__name__}, "
            "no texto (entities.md, BR2.5)"
        )
        raise RuleValidationError(msg)
    if len(clave) > EXPLANATION_KEY_LEN or re.fullmatch(EXPLANATION_KEY_PATTERN, clave) is None:
        msg = (
            f"la regla '{rule_id}' declara 'then.explanation_key' como '{clave}', sin la "
            "forma de una clave del catalogo (entities.md, BR2.5)"
        )
        raise RuleValidationError(msg)

    return RuleOutcome(category=categoria, touches_money=dinero, explanation_key=clave)


def _run_rule_tests(rule: RuleDefinition, condition: Condition) -> None:
    """Corre cada `{given, expect}` de la regla, sola, contra su propia condicion (BR1.4, M5)."""
    for posicion, prueba in enumerate(rule.tests):
        if "given" not in prueba or "expect" not in prueba:
            msg = (
                f"la regla '{rule.id}' trae un caso de prueba mal formado en la posicion "
                f"{posicion}: se espera un mapa con 'given' y 'expect' (BR1.4, M5)"
            )
            raise RuleValidationError(msg)

        dado = prueba["given"]
        esperado = prueba["expect"]
        if not isinstance(dado, Mapping):
            msg = f"la regla '{rule.id}': 'given' de la prueba {posicion} no es un mapa (BR1.4)"
            raise RuleValidationError(msg)
        if not isinstance(esperado, bool):
            msg = f"la regla '{rule.id}': 'expect' de la prueba {posicion} no es booleano (BR1.4)"
            raise RuleValidationError(msg)

        obtenido = evaluate_condition(condition, dado)
        if obtenido != esperado:
            msg = (
                f"la regla '{rule.id}' no pasa su caso de prueba en la posicion {posicion}: "
                f"se esperaba {esperado} y la condicion dio {obtenido} (BR1.4)"
            )
            raise RuleValidationError(msg)


def validate_ruleset(raw: RuleSet, *, tenant_id: TenantId) -> ValidatedRuleSet:
    """El significado de un conjunto ya validado en su forma (BR1.1 a BR1.4)."""
    total = len(raw.rules)
    if not (MIN_RULES <= total <= MAX_RULES):
        msg = (
            f"la aseguradora '{tenant_id}' tiene {total} reglas; se esperan entre "
            f"{MIN_RULES} y {MAX_RULES} (BR1.1)"
        )
        raise RuleValidationError(msg)

    validadas: list[ValidatedRule] = []
    por_defecto: list[ValidatedRule] = []
    for regla in raw.rules:
        condicion = parse_condition(regla.when, rule_id=regla.id, vocabulary=TRIAGE_FIELDS)
        resultado = _parse_then(regla.then, rule_id=regla.id)
        _run_rule_tests(regla, condicion)
        validada = ValidatedRule(definition=regla, condition=condicion, then=resultado)
        validadas.append(validada)
        if condicion.operator != ALWAYS:
            continue
        if resultado.category == "standard_review":
            por_defecto.append(validada)
        elif resultado.category != "referral":
            # Una regla que dispara siempre y no es la por defecto solo puede
            # derivar, como la de la agencia (BR2.6): siempre cerrar directo no
            # es una regla, es saltarse la revision.
            msg = (
                f"la regla '{regla.id}' de '{tenant_id}' usa 'when: {{always: true}}' con la "
                f"categoria '{resultado.category}'; fuera de la regla por defecto, una regla "
                "que dispara siempre solo puede derivar (BR1.3, BR2.6)"
            )
            raise RuleValidationError(msg)

    if len(por_defecto) != 1:
        msg = (
            f"la aseguradora '{tenant_id}' declara {len(por_defecto)} reglas por defecto "
            "('when: {always: true}' con revision estandar); se espera exactamente una (BR1.3)"
        )
        raise RuleValidationError(msg)
    (regla_por_defecto,) = por_defecto

    return ValidatedRuleSet(
        tenant_id=tenant_id,
        ruleset_version=raw.ruleset_version,
        rules=tuple(validadas),
        default_rule=regla_por_defecto,
    )


def load_rulesets(root: Path | None = None) -> LoadedRulesets:
    """Recorre las aseguradoras cargadas y valida el significado de cada una."""
    directorio = root if root is not None else paths.tenants_dir()
    disponibles: dict[TenantId, ValidatedRuleSet] = {}
    caidas: list[UnavailableRuleset] = []

    for tenant_id in tenancy_config.loaded().ids:
        archivo = directorio / tenant_id / tenancy_config.RULES_DIR / RULESET_FILE
        if not archivo.is_file():
            caidas.append(
                UnavailableRuleset(
                    tenant_id=tenant_id,
                    detail=f"no tiene '{archivo}' (BR1.1)",
                )
            )
            continue
        try:
            crudo = tenancy_config.load_ruleset(archivo)
            validado = validate_ruleset(crudo, tenant_id=tenant_id)
        except (TenantConfigError, ConditionError, RuleValidationError) as error:
            detalle = str(error)
            caidas.append(UnavailableRuleset(tenant_id=tenant_id, detail=detalle))
            observability.emit("rules.ruleset_unavailable", tenant_id=tenant_id, detail=detalle)
            continue
        disponibles[tenant_id] = validado

    return LoadedRulesets(available=disponibles, unavailable=tuple(caidas))


_loaded: LoadedRulesets | None = None


def install(rulesets: LoadedRulesets) -> None:
    """Fija los conjuntos de reglas del proceso. La llama la raiz de composicion."""
    global _loaded
    _loaded = rulesets


def loaded() -> LoadedRulesets:
    """Los conjuntos de reglas del proceso, cargandolos la primera vez si hace falta."""
    global _loaded
    if _loaded is None:
        _loaded = load_rulesets()
    return _loaded


def reset() -> None:
    """Olvida lo cargado. Lo usan las pruebas para no compartir estado."""
    global _loaded
    _loaded = None


def require(tenant_id: TenantId) -> ValidatedRuleSet:
    """El conjunto de una aseguradora, o un fallo que la nombra (BR1.5, igual que U2)."""
    ruleset = loaded().get(tenant_id)
    if ruleset is None:
        msg = (
            f"la aseguradora '{tenant_id}' no tiene un conjunto de reglas cargado y valido; "
            "revise 'rules/triage.yaml' y los detalles en 'rules.loading.loaded().unavailable'"
        )
        raise RuleNotConfiguredError(msg)
    return ruleset
