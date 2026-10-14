"""La elegibilidad de una solicitud de cotizacion: reglas versionadas, salida y banda (U19).

Es el mismo motor de condiciones del triage --`when` con operadores cerrados,
`tests` dentro del propio YAML-- sobre **otro archivo** (`rules/eligibility.yaml`)
y otro vocabulario (`ELIGIBILITY_FIELDS`). No es una segunda implementacion: la
condicion se valida y se evalua con `conditions.py`, y lo unico propio de aqui es
lo que una regla de elegibilidad *decide* --una salida y una banda-- en lugar de
una categoria de siniestro.

**La salida y la banda son dos datos** (BR2.1, BR2.2). `outcome` dice que pasa con
la solicitud; `band` dice donde queda el riesgo. Solo hay cuatro parejas validas y
el tipo rechaza cualquier otra: en particular, una derivacion solo puede llevar
`pending_review`, porque afirmar una banda donde decide una persona es afirmar lo
que nadie ha decidido, y dejarla vacia diria por omision que es la peor.

**Ninguna cifra sale de aqui.** La razon es una clave del catalogo y la banda un
valor cerrado; el importe lo caza la guardia de salida, que ya existe (FD-U19-1).
Este modulo no construye un segundo detector.

**Puro y sin reloj** (BR2.5): evaluar es un calculo sobre datos ya cargados. No lo
llama el turno --`orchestration.rhythm` tiene prohibido llegar a `rules`--, lo
llama el ritmo de fondo.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator

from untangle import observability, paths
from untangle.base import Frozen
from untangle.rules.conditions import (
    ALWAYS,
    Condition,
    ConditionError,
    evaluate_condition,
    fields_read,
    parse_condition,
)
from untangle.rules.fields import ELIGIBILITY_FIELDS, RuleValue
from untangle.rules.models import (
    EXPLANATION_KEY_LEN,
    EXPLANATION_KEY_PATTERN,
    RuleNotConfiguredError,
    RuleValidationError,
)
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import RuleDefinition, RuleSet, TenantConfigError, TenantId

#: El nombre fijo del archivo de elegibilidad de una aseguradora, junto a su triage.
ELIGIBILITY_FILE = "eligibility.yaml"

#: Un anio del calendario no es una antiguedad (BR1.4). Ninguna condicion compara
#: contra un numero de esta magnitud: `vehicle_age_years gte 2001` envejece sola y
#: no falla nada. El tope es el primer anio que un formulario de seguros acepta.
CALENDAR_YEAR_FLOOR = 1900


class EligibilityOutcomeKind(StrEnum):
    """Las tres salidas cerradas de la elegibilidad (BR2.1)."""

    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    REFERRED = "referred"


class RiskBand(StrEnum):
    """La banda de riesgo: cuatro valores cerrados, ninguno habla de precio (BR2.2, Q1).

    Habla de **riesgo** y no de prima: "banda estandar" sin cifra insinuaria que hay
    un precio detras, y esta demostracion no calcula ninguno.
    """

    STANDARD_RISK = "standard_risk"
    ELEVATED_RISK = "elevated_risk"
    PENDING_REVIEW = "pending_review"
    OUTSIDE_APPETITE = "outside_appetite"


#: Que bandas admite cada salida (BR2.2). Es la unica tabla de parejas validas: el
#: tipo, el cargador y las pruebas la leen de aqui.
BANDS_OF: dict[EligibilityOutcomeKind, frozenset[RiskBand]] = {
    EligibilityOutcomeKind.ELIGIBLE: frozenset({RiskBand.STANDARD_RISK, RiskBand.ELEVATED_RISK}),
    EligibilityOutcomeKind.NOT_ELIGIBLE: frozenset({RiskBand.OUTSIDE_APPETITE}),
    EligibilityOutcomeKind.REFERRED: frozenset({RiskBand.PENDING_REVIEW}),
}

#: El orden de prudencia: la salida mas alta gana, igual que en el triage (BR2.2
#: del triage). Una solicitud que dispara una regla de no elegible y otra de
#: derivacion es no elegible.
OUTCOME_RANK: dict[EligibilityOutcomeKind, int] = {
    EligibilityOutcomeKind.ELIGIBLE: 0,
    EligibilityOutcomeKind.REFERRED: 1,
    EligibilityOutcomeKind.NOT_ELIGIBLE: 2,
}

#: El tipo de cada campo, para traducir el valor guardado --siempre texto-- a lo
#: que una condicion compara. Cerrado con el vocabulario: un campo nuevo sin tipo
#: hace fallar la prueba que compara los dos conjuntos.
FIELD_KINDS: dict[str, type[bool] | type[int] | type[str]] = {
    "use_type": str,
    "salvage_title": bool,
    "at_fault_losses_3y": int,
    "license_years": int,
    "vehicle_age_years": int,
}

#: Los valores que admite `use_type`. Es el conjunto cerrado del esquema de la
#: solicitud; la etiqueta que lee una persona sale del catalogo, nunca del valor.
USE_TYPES: frozenset[str] = frozenset({"personal", "commuting", "commercial"})


class EligibilityInputError(ValueError):
    """Un valor guardado no se puede leer como lo que su campo declara."""


class MissingEligibilityInputsError(LookupError):
    """Faltan campos de elegibilidad: no se evalua.

    Un campo ausente no dispara ninguna condicion (BR2.1 del triage), y en la
    elegibilidad eso es **peligroso**: sin datos, la regla por defecto diria
    "elegible". El triage cae en revision estandar, que es prudente; aqui no hay
    una salida prudente por omision, asi que se niega a evaluar y nombra lo que
    falta.
    """


class EligibilityOutcome(Frozen):
    """Lo que sale de las reglas: la salida, la banda, quien decidio y por que (BR2.1)."""

    outcome: EligibilityOutcomeKind
    band: RiskBand
    #: Los identificadores de las reglas que decidieron. **Para la traza y para la
    #: bandeja, nunca para quien pregunto** (BR2.3): el suscriptor necesita ver que
    #: decidio, el prospecto lee la condicion.
    deciding_rules: tuple[str, ...] = Field(min_length=1)
    explanation_key: str = Field(pattern=EXPLANATION_KEY_PATTERN, max_length=EXPLANATION_KEY_LEN)
    ruleset_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _la_banda_es_la_de_su_salida(self) -> Self:
        if self.band not in BANDS_OF[self.outcome]:
            validas = sorted(banda.value for banda in BANDS_OF[self.outcome])
            msg = (
                f"una solicitud '{self.outcome.value}' no puede llevar la banda "
                f"'{self.band.value}'; las validas son {validas} (BR2.2)"
            )
            raise ValueError(msg)
        return self


@dataclass(frozen=True)
class EligibilityRule:
    """Una regla de elegibilidad ya validada: su condicion y lo que decide."""

    definition: RuleDefinition
    condition: Condition
    outcome: EligibilityOutcomeKind
    band: RiskBand
    explanation_key: str

    @property
    def id(self) -> str:
        return self.definition.id


@dataclass(frozen=True)
class EligibilityRuleSet:
    """El conjunto de elegibilidad de una aseguradora, listo para evaluar."""

    tenant_id: TenantId
    ruleset_version: str
    rules: tuple[EligibilityRule, ...]
    default_rule: EligibilityRule

    @property
    def required_inputs(self) -> frozenset[str]:
        """Los campos que el conjunto lee: lo que la captura tiene que haber escrito."""
        return frozenset().union(*(fields_read(regla.condition) for regla in self.rules))


@dataclass(frozen=True)
class UnavailableEligibility:
    """Una aseguradora con la cotizacion activa cuyo conjunto no valido. Nombra por que."""

    tenant_id: TenantId
    detail: str


@dataclass(frozen=True)
class LoadedEligibility:
    """Lo que quedo tras validar la elegibilidad de cada aseguradora."""

    available: Mapping[TenantId, EligibilityRuleSet]
    unavailable: tuple[UnavailableEligibility, ...]

    def get(self, tenant_id: TenantId) -> EligibilityRuleSet | None:
        return self.available.get(tenant_id)


def _parse_then(
    raw: Mapping[str, object], *, rule_id: str
) -> tuple[EligibilityOutcomeKind, RiskBand, str]:
    """Valida `then`: la salida, la banda y la clave del catalogo, como pareja."""
    try:
        salida = EligibilityOutcomeKind(str(raw.get("outcome")))
    except ValueError as error:
        validas = [kind.value for kind in EligibilityOutcomeKind]
        msg = (
            f"la regla '{rule_id}' declara 'then.outcome' como '{raw.get('outcome')}', "
            f"fuera de {validas} (BR2.1)"
        )
        raise RuleValidationError(msg) from error
    try:
        banda = RiskBand(str(raw.get("band")))
    except ValueError as error:
        validas = [band.value for band in RiskBand]
        msg = (
            f"la regla '{rule_id}' declara 'then.band' como '{raw.get('band')}', "
            f"fuera de {validas} (BR2.2)"
        )
        raise RuleValidationError(msg) from error
    if banda not in BANDS_OF[salida]:
        msg = (
            f"la regla '{rule_id}' declara la salida '{salida.value}' con la banda "
            f"'{banda.value}', que esa salida no admite (BR2.2)"
        )
        raise RuleValidationError(msg)

    clave = raw.get("explanation_key")
    if (
        not isinstance(clave, str)
        or len(clave) > EXPLANATION_KEY_LEN
        or re.fullmatch(EXPLANATION_KEY_PATTERN, clave) is None
    ):
        msg = (
            f"la regla '{rule_id}' declara 'then.explanation_key' como {clave!r}, sin la "
            "forma de una clave del catalogo (BR2.3)"
        )
        raise RuleValidationError(msg)
    return salida, banda, clave


def _no_compara_contra_un_anio(condicion: Condition, *, rule_id: str) -> None:
    """BR1.4: ninguna hoja compara contra un numero que sea un anio del calendario."""
    if isinstance(condicion.value, int | float) and not isinstance(condicion.value, bool):
        if condicion.value >= CALENDAR_YEAR_FLOOR:
            msg = (
                f"la regla '{rule_id}' compara '{condicion.field}' contra {condicion.value}, "
                "que es un anio del calendario y no una cantidad: envejece sola y no falla "
                "nada; compare contra una antiguedad (BR1.4)"
            )
            raise RuleValidationError(msg)
    for hija in condicion.conditions:
        _no_compara_contra_un_anio(hija, rule_id=rule_id)


def _run_rule_tests(rule: RuleDefinition, condition: Condition) -> None:
    """Cada `{given, expect}` de la regla, sola, contra su propia condicion (BR2.4, M5)."""
    for posicion, prueba in enumerate(rule.tests):
        dado = prueba.get("given")
        esperado = prueba.get("expect")
        if not isinstance(dado, Mapping) or not isinstance(esperado, bool):
            msg = (
                f"la regla '{rule.id}' trae un caso de prueba mal formado en la posicion "
                f"{posicion}: se espera un mapa con 'given' y un 'expect' booleano (BR2.4)"
            )
            raise RuleValidationError(msg)
        obtenido = evaluate_condition(condition, dado)
        if obtenido != esperado:
            msg = (
                f"la regla '{rule.id}' no pasa su caso de prueba en la posicion {posicion}: "
                f"se esperaba {esperado} y la condicion dio {obtenido} (BR2.4)"
            )
            raise RuleValidationError(msg)


def validate_eligibility(raw: RuleSet, *, tenant_id: TenantId) -> EligibilityRuleSet:
    """El significado de un conjunto de elegibilidad ya validado en su forma (BR2.1 a BR2.4)."""
    validadas: list[EligibilityRule] = []
    por_defecto: list[EligibilityRule] = []
    for regla in raw.rules:
        try:
            condicion = parse_condition(regla.when, rule_id=regla.id, vocabulary=ELIGIBILITY_FIELDS)
        except ConditionError as error:
            raise RuleValidationError(str(error)) from error
        _no_compara_contra_un_anio(condicion, rule_id=regla.id)
        salida, banda, clave = _parse_then(regla.then, rule_id=regla.id)
        _run_rule_tests(regla, condicion)
        validada = EligibilityRule(
            definition=regla,
            condition=condicion,
            outcome=salida,
            band=banda,
            explanation_key=clave,
        )
        validadas.append(validada)
        if condicion.operator != ALWAYS:
            continue
        if salida is EligibilityOutcomeKind.ELIGIBLE:
            por_defecto.append(validada)
        elif salida is not EligibilityOutcomeKind.REFERRED:
            # Fuera de la regla por defecto, una regla que dispara siempre solo
            # puede derivar: que siempre dijera "no elegible" seria cerrar la
            # cotizacion, y eso se hace con `quote_enabled`, no con una regla.
            msg = (
                f"la regla '{regla.id}' de '{tenant_id}' usa 'when: {{always: true}}' con la "
                f"salida '{salida.value}'; fuera de la regla por defecto, una regla que "
                "dispara siempre solo puede derivar (BR2.1)"
            )
            raise RuleValidationError(msg)

    if len(por_defecto) != 1:
        msg = (
            f"la aseguradora '{tenant_id}' declara {len(por_defecto)} reglas por defecto "
            "('when: {always: true}' con salida elegible); se espera exactamente una (BR2.1)"
        )
        raise RuleValidationError(msg)
    (regla_por_defecto,) = por_defecto

    return EligibilityRuleSet(
        tenant_id=tenant_id,
        ruleset_version=raw.ruleset_version,
        rules=tuple(validadas),
        default_rule=regla_por_defecto,
    )


def load_eligibility(root: Path | None = None) -> LoadedEligibility:
    """Valida la elegibilidad de cada aseguradora que tiene la cotizacion activa.

    Una aseguradora con `quote_enabled: true` y sin un conjunto valido queda como
    no disponible **con su razon**, y las demas siguen. Una con la cotizacion
    apagada no necesita conjunto: no se le pide, y si trae uno se valida igual
    para que un archivo roto no espere a que alguien la encienda.
    """
    directorio = root if root is not None else paths.tenants_dir()
    disponibles: dict[TenantId, EligibilityRuleSet] = {}
    caidas: list[UnavailableEligibility] = []

    for tenant in tenancy_config.loaded().available:
        archivo = directorio / tenant.tenant_id / tenancy_config.RULES_DIR / ELIGIBILITY_FILE
        if not archivo.is_file():
            if tenant.quote_enabled:
                caidas.append(
                    UnavailableEligibility(
                        tenant_id=tenant.tenant_id,
                        detail=f"tiene la cotizacion activa y no tiene '{archivo}' (BR1.5)",
                    )
                )
            continue
        try:
            crudo = tenancy_config.load_ruleset(archivo)
            validado = validate_eligibility(crudo, tenant_id=tenant.tenant_id)
        except (TenantConfigError, RuleValidationError) as error:
            detalle = str(error)
            caidas.append(UnavailableEligibility(tenant_id=tenant.tenant_id, detail=detalle))
            observability.emit(
                "rules.eligibility_unavailable", tenant_id=tenant.tenant_id, detail=detalle
            )
            continue
        disponibles[tenant.tenant_id] = validado

    return LoadedEligibility(available=disponibles, unavailable=tuple(caidas))


_loaded: LoadedEligibility | None = None


def loaded() -> LoadedEligibility:
    """Los conjuntos de elegibilidad del proceso, cargandolos la primera vez si hace falta."""
    global _loaded
    if _loaded is None:
        _loaded = load_eligibility()
    return _loaded


def reset() -> None:
    """Olvida lo cargado. Lo usan las pruebas para no compartir estado."""
    global _loaded
    _loaded = None


def require(tenant_id: TenantId) -> EligibilityRuleSet:
    """El conjunto de una aseguradora, o un fallo que la nombra."""
    conjunto = loaded().get(tenant_id)
    if conjunto is None:
        msg = (
            f"la aseguradora '{tenant_id}' no tiene un conjunto de elegibilidad cargado y "
            f"valido; revise 'rules/{ELIGIBILITY_FILE}' y los detalles en "
            "'rules.eligibility.loaded().unavailable'"
        )
        raise RuleNotConfiguredError(msg)
    return conjunto


def eligibility_inputs(values: Mapping[str, str]) -> dict[str, RuleValue]:
    """Los valores guardados de la solicitud, leidos como lo que cada campo declara.

    Un valor que no se puede leer **levanta** en vez de omitirse: omitirlo lo
    convertiria en un campo ausente, y un campo ausente no dispara nada, que es
    justo como una solicitud mal capturada terminaria "elegible".
    """
    traducidos: dict[str, RuleValue] = {}
    for campo, tipo in FIELD_KINDS.items():
        if campo not in values:
            continue
        crudo = values[campo].strip()
        try:
            if tipo is bool:
                if crudo not in ("true", "false"):
                    raise ValueError(crudo)
                traducidos[campo] = crudo == "true"
            elif tipo is int:
                traducidos[campo] = int(crudo)
            else:
                if crudo not in USE_TYPES:
                    raise ValueError(crudo)
                traducidos[campo] = crudo
        except ValueError as error:
            msg = f"el valor guardado de '{campo}' ({crudo!r}) no es un {tipo.__name__} valido"
            raise EligibilityInputError(msg) from error
    return traducidos


def evaluate_eligibility(
    ruleset: EligibilityRuleSet, inputs: Mapping[str, RuleValue]
) -> EligibilityOutcome:
    """La salida y la banda de una solicitud completa (F2, BR2.1, BR2.2).

    **Se niega a evaluar si falta un campo que el conjunto lee** (ver
    `MissingEligibilityInputsError`). Con todos presentes es un calculo puro y
    determinista: sin red, sin reloj y sin modelo.
    """
    faltan = sorted(campo for campo in ruleset.required_inputs if inputs.get(campo) is None)
    if faltan:
        msg = (
            f"la elegibilidad de '{ruleset.tenant_id}' lee {faltan}, que la solicitud no "
            "trae; no se evalua con datos que faltan (BR1.3)"
        )
        raise MissingEligibilityInputsError(msg)

    defecto = ruleset.default_rule
    disparadas = [
        regla
        for regla in ruleset.rules
        if regla is not defecto and evaluate_condition(regla.condition, inputs)
    ]
    if not disparadas:
        # La regla por defecto solo entra cuando nada mas disparo: si compitiera
        # siempre, su "elegible con riesgo elevado" le ganaria a la banda estandar.
        disparadas = [defecto]

    # Gana la salida mas prudente; con empate, la primera en el orden del archivo.
    decisiva = max(disparadas, key=lambda regla: OUTCOME_RANK[regla.outcome])
    decisoras = tuple(regla.id for regla in disparadas if regla.outcome is decisiva.outcome)
    return EligibilityOutcome(
        outcome=decisiva.outcome,
        band=decisiva.band,
        deciding_rules=decisoras,
        explanation_key=decisiva.explanation_key,
        ruleset_version=ruleset.ruleset_version,
    )


__all__ = [
    "BANDS_OF",
    "CALENDAR_YEAR_FLOOR",
    "ELIGIBILITY_FILE",
    "FIELD_KINDS",
    "OUTCOME_RANK",
    "USE_TYPES",
    "EligibilityInputError",
    "EligibilityOutcome",
    "EligibilityOutcomeKind",
    "EligibilityRule",
    "EligibilityRuleSet",
    "LoadedEligibility",
    "MissingEligibilityInputsError",
    "RiskBand",
    "UnavailableEligibility",
    "eligibility_inputs",
    "evaluate_eligibility",
    "load_eligibility",
    "loaded",
    "require",
    "reset",
    "validate_eligibility",
]
