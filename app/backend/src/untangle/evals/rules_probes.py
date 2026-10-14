"""Las sondas de DS-2 que miden el motor de reglas (U9, CG-U9-3).

Doce comprobaciones, una por criterio. Llaman al **motor real**
(`rules.loading` + `rules.evaluation`, no `rules.api`): son sincronas, como
exige `EvalCheck`, y la superficie asincrona de `api.py` es solo la convencion
del nodo `decision`, que estas sondas no necesitan arrastrar.

Corren contra la **configuracion real** de las tres aseguradoras (C-25).

Las tres de heridos (2026-10-13) no dan los insumos hechos: dan el campo `injuries` del
caso y lo pasan por la misma derivacion que usa el aplicativo
(`orchestration.triage_inputs.injuries_present`) antes de evaluar. Miden el recorrido
del dato guardado a la categoria; la lectura del campo sellado en la base y el
cableado del nodo los cubre la prueba de integracion de la cadena de fondo.

Las tres del conductor (2026-10-13) hacen lo mismo con el campo `vehicle_and_driver` y los
conductores que declara la poliza del caso (`orchestration.triage_inputs.unlisted_driver`): figura,
no figura y no se sabe. La categoria sola no distingue "figura" de "no se sabe" --ninguna regla
pide el insumo en falso--, asi que cada fila declara tambien lo que la derivacion debe dar.

Las dos de cierre (2026-10-13) llegan hasta donde el corredor puede mirar: del campo de
heridos y el de terceros hasta **lo que el recorrido hace con el caso** --cerrarlo como
`registered` sin ajustador, o dejarlo con uno--, con la misma decision pura que usa el
aplicativo (`orchestration.closing_plan.plan`). Que el estado del caso cambie de
verdad en la base lo cubre la prueba de integracion de la cadena de fondo.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from untangle.base import Locale
from untangle.case_record.models import CaseState, DerivationReason, Resolution
from untangle.compliance.controls.closure import decide_closure
from untangle.compliance.controls.models import ComplianceReview
from untangle.evals import rules_fixtures as fx
from untangle.evals.models import Dataset
from untangle.evals.runner.api import CheckOutcome, EvalTarget, register_check, register_targets
from untangle.orchestration import closing_plan, triage_inputs
from untangle.orchestration.closing_plan import (
    DIRECT_CLOSE_PHRASE,
    HANDOFF_PHRASE,
    ClosingPlan,
    Step,
)
from untangle.rules import loading
from untangle.rules.evaluation import evaluate_ruleset
from untangle.rules.fields import RuleValue
from untangle.rules.models import RuleEvaluationView

#: La unidad a la que se le miden estas comprobaciones (C-22).
UNIT = "u9-rules-decision"


def _conductor_derivado(fila: fx.RulesFixtureRow) -> bool | None:
    """`unlisted_driver` derivado del campo del vehiculo y el conductor de la fila, o `None`."""
    capturado = fila.vehicle_and_driver
    if capturado is None:
        return None
    return triage_inputs.unlisted_driver(
        capturado.value, status=capturado.status, declared_drivers=capturado.declared_drivers
    )


#: Lo que cada valor derivado de `unlisted_driver` se llama en las filas.
_NOMBRE_DEL_CONDUCTOR: dict[bool | None, str] = {False: "listed", True: "unlisted", None: "unknown"}


def _problema_del_conductor(fila: fx.RulesFixtureRow) -> str | None:
    """Lo que la fila espera del insumo `unlisted_driver` ya derivado, o el problema."""
    if fila.expected_driver is None:
        return None
    derivado = _NOMBRE_DEL_CONDUCTOR[_conductor_derivado(fila)]
    if derivado == fila.expected_driver:
        return None
    return (
        f"el conductor debia derivarse como '{fila.expected_driver}' y se derivo como '{derivado}'"
    )


def _insumos_de_la_fila(fila: fx.RulesFixtureRow) -> dict[str, RuleValue]:
    """Los insumos de la fila, con lo derivable derivado de los campos del caso que trae.

    Una derivacion ausente deja el insumo fuera, igual que en produccion: no se escribe
    `False` por no saber.
    """
    insumos = dict(fila.inputs)
    if fila.injuries is not None:
        derivado = triage_inputs.injuries_present(fila.injuries.value, status=fila.injuries.status)
        if derivado is not None:
            insumos["injuries_present"] = derivado
    if fila.other_parties is not None:
        pendientes = triage_inputs.other_parties_data_pending(
            (), block_status=fila.other_parties.status, value=fila.other_parties.value
        )
        if pendientes is not None:
            insumos["other_parties_data_pending"] = pendientes
    no_figura = _conductor_derivado(fila)
    if no_figura is not None:
        insumos["unlisted_driver"] = no_figura
    return insumos


def _cierre_de_la_fila(fila: fx.RulesFixtureRow, resultado: RuleEvaluationView) -> str | None:
    """Lo que el recorrido hace con el caso de esta fila, o el problema si no es lo esperado.

    La revision de cumplimiento se da por aprobada: lo que esta fila mide es lo que las reglas
    deciden, no los cuatro controles. El estado del caso es `deciding`, del que sale el cierre
    o la derivacion.
    """
    revision = ComplianceReview(
        review_id="revision-de-la-sonda",
        tenant_id=fila.tenant_id,
        case_id="caso-de-la-sonda",
        disclosure_ok=True,
        human_route_ok=True,
        pii_ok=True,
        explainability_ok=True,
        findings=(),
        reviewed_through_turn="turno-de-la-sonda",
        reviewed_at=datetime(2026, 10, 13, tzinfo=UTC),
    )
    cierre = decide_closure(revision, handoff=None, closable=resultado.category == "direct_close")
    plan = closing_plan.plan(
        case_state=CaseState.DECIDING,
        offer_open=False,
        closure=cierre,
        fired_rules=resultado.fired_rules,
    )
    if fila.closure == "registered":
        return _problema_del_registro(plan)
    return _problema_de_la_derivacion(plan)


def _problema_del_registro(plan: ClosingPlan) -> str | None:
    if plan.step is not Step.REGISTER or plan.resolution is not Resolution.REGISTERED:
        return f"debia quedar cerrado como 'registered' y el recorrido hizo '{plan.step}'"
    if plan.announce != DIRECT_CLOSE_PHRASE:
        return f"el cierre directo debia anunciarse con '{DIRECT_CLOSE_PHRASE}'"
    return None


def _problema_de_la_derivacion(plan: ClosingPlan) -> str | None:
    if plan.step is not Step.REFER:
        return f"debia quedar con un ajustador y el recorrido hizo '{plan.step}'"
    if plan.derivation_reason is not DerivationReason.RULE:
        return "la derivacion debia llevar el motivo 'rule'"
    if plan.announce != HANDOFF_PHRASE:
        return f"la derivacion debia anunciarse con '{HANDOFF_PHRASE}'"
    return None


def _problemas_de_escenario(
    fixtures: fx.RulesFixtures, scenario: str, *, exige_dinero: bool
) -> list[str]:
    """Cada fila del escenario, contra el motor real de su aseguradora."""
    filas = fixtures.rows_for(scenario)
    if not filas:
        return [f"el escenario '{scenario}' no tiene filas: no se midio nada"]

    problemas: list[str] = []
    for fila in filas:
        try:
            ruleset = loading.require(fila.tenant_id)
            resultado = evaluate_ruleset(ruleset, _insumos_de_la_fila(fila))
        except Exception as error:  # noqa: BLE001 -- una compuerta que no se pudo ejecutar nunca es verde
            problemas.append(f"{fila.id}: el motor no pudo evaluar ({error})")
            continue
        if resultado.category != fila.expected_category:
            problemas.append(
                f"{fila.id}: se esperaba la categoria '{fila.expected_category}' y dio "
                f"'{resultado.category}'"
            )
        problema_del_conductor = _problema_del_conductor(fila)
        if problema_del_conductor is not None:
            problemas.append(f"{fila.id}: {problema_del_conductor}")
        if exige_dinero and not any(regla.touches_money for regla in resultado.fired_rules):
            # La compuerta mide que la regla de dinero fuerza la derivacion, no
            # que otra regla derive por casualidad (AC1.17.3).
            problemas.append(f"{fila.id}: derivo sin que disparara ninguna regla de dinero")
        if fila.closure is not None:
            try:
                problema = _cierre_de_la_fila(fila, resultado)
            except Exception as error:  # noqa: BLE001 -- una compuerta que no se pudo ejecutar nunca es verde
                problemas.append(f"{fila.id}: no se pudo decidir el cierre ({error})")
                continue
            if problema is not None:
                problemas.append(f"{fila.id}: {problema}")
    return problemas


def _sonda(scenario: str, *, exige_dinero: bool = False) -> Callable[..., CheckOutcome]:
    def comprobar(*, language: Locale, root: Path) -> CheckOutcome:
        try:
            fixtures = fx.load_rules_fixtures(language, root)
        except fx.RulesFixtureError as error:
            return CheckOutcome(passed=False, detail=str(error))
        problemas = _problemas_de_escenario(fixtures, scenario, exige_dinero=exige_dinero)
        return CheckOutcome(passed=not problemas, detail="; ".join(problemas))

    return comprobar


#: Las cuatro comprobaciones, por el criterio que resuelven (CG-U9-3). Un
#: escenario reune varias filas -- una por aseguradora -- bajo un solo
#: criterio cuando todas prueban la misma cosa generica: que la categoria
#: coincide con la esperada, incluida la regla por defecto.
SONDAS: dict[str, Callable[..., CheckOutcome]] = {
    "rules_category_expected": _sonda("category-expected"),
    "direct_close_without_money": _sonda("direct-close"),
    "money_rule_forces_referral": _sonda("money-forces-referral", exige_dinero=True),
    "agency_always_referral": _sonda("agency-always-referral"),
    "triage_from_injuries_denied": _sonda("injuries-denied"),
    "triage_from_injuries_reported": _sonda("injuries-reported"),
    "triage_from_injuries_unclear": _sonda("injuries-unclear"),
    "triage_from_driver_listed": _sonda("driver-listed"),
    "triage_from_driver_unlisted": _sonda("driver-unlisted"),
    "triage_from_driver_unknown": _sonda("driver-unknown"),
    "closure_registers_without_adjuster": _sonda("closure-registers"),
    "closure_refers_to_adjuster": _sonda("closure-refers"),
}

TARGETS: tuple[EvalTarget, ...] = (
    EvalTarget(
        "rules_category_expected",
        Dataset.DS_2,
        "La categoria de cada aseguradora coincide con la esperada, incluida la regla por "
        "defecto (AC1.15.2, AC1.17.1, BR1.3, BR2.2)",
    ),
    EvalTarget(
        "direct_close_without_money",
        Dataset.DS_2,
        "Un caso simple y sin dinero cierra directo, sin regla de dinero disparada (FR6.1)",
    ),
    EvalTarget(
        "money_rule_forces_referral",
        Dataset.DS_2,
        "Una regla de dinero o cobertura fuerza la derivacion (AC1.15.4, AC1.17.3 [bloquea])",
        blocking=True,
    ),
    EvalTarget(
        "agency_always_referral",
        Dataset.DS_2,
        "La agencia deriva siempre, por su regla y no por una rama de codigo (FR6.4, BR2.6)",
    ),
    EvalTarget(
        "triage_from_injuries_denied",
        Dataset.DS_2,
        "Un caso que dice con claridad que nadie salio herido llega al motor como "
        "`injuries_present: false` y Sunmeadow lo cierra directo (FR6.1)",
    ),
    EvalTarget(
        "triage_from_injuries_reported",
        Dataset.DS_2,
        "Un caso que menciona a alguien herido, aunque tambien diga que no, llega al motor "
        "como `injuries_present: true` y las tres aseguradoras derivan (AC1.15.2)",
    ),
    EvalTarget(
        "triage_from_injuries_unclear",
        Dataset.DS_2,
        "Un caso cuya respuesta sobre heridos es dudosa no produce `injuries_present` y queda "
        "en revision estandar: nunca cierra directo",
    ),
    EvalTarget(
        "triage_from_driver_listed",
        Dataset.DS_2,
        "Un caso donde conducia quien la poliza declara llega al motor como "
        "`unlisted_driver: false` y la regla del conductor no dispara",
    ),
    EvalTarget(
        "triage_from_driver_unlisted",
        Dataset.DS_2,
        "Un caso donde conducia alguien que la poliza no declara llega al motor como "
        "`unlisted_driver: true` y las tres aseguradoras derivan",
    ),
    EvalTarget(
        "triage_from_driver_unknown",
        Dataset.DS_2,
        "Un caso donde no se sabe con claridad quien conducia, o cuya poliza no declara "
        "conductores, no produce `unlisted_driver`: la regla del conductor no dispara",
    ),
    EvalTarget(
        "closure_registers_without_adjuster",
        Dataset.DS_2,
        "Un reporte sin heridos y que dice con claridad que no hubo otros involucrados termina "
        "cerrado como `registered`, sin pasar por la bandeja, y se anuncia el cierre directo "
        "(AC1.17.1, AC1.17.2)",
    ),
    EvalTarget(
        "closure_refers_to_adjuster",
        Dataset.DS_2,
        "Un reporte con un tercero nombrado, con heridos, con un dato dudoso o ausente, o de "
        "una aseguradora que no cierra directo termina con un ajustador y se anuncia la "
        "derivacion: nunca se cierra solo (AC1.17.3)",
    ),
)


def register_rules_probes() -> None:
    """Registra las cuatro sondas y los objetivos de U9 en el corredor."""
    for criterio, sonda in SONDAS.items():
        register_check(criterio, sonda)
    register_targets(UNIT, TARGETS)
