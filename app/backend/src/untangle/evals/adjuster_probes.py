"""Las sondas del ajustador de IA (plan 09, fase 5, tanda 2c).

Cada caso `DS-2/<idioma>/adjuster-*` trae un caso derivado --la poliza del corpus versionado y lo
que la persona conto-- y lo que el proceso entero (`adjuster.pipeline.run_case`) tiene que decidir.
La sonda **corre el proceso de verdad** --lee el caso, la poliza, recupera clausulas, busca el valor
del vehiculo y decide con Claude-- y mide ocho criterios **por codigo**, sin juez de lenguaje:

1. `action_allowed`: la accion es de las que ofrece ese tipo de aseguradora (A3).
2. `citations_verified`: toda clausula citada esta recuperada y la verifica el verificador exacto,
   y el texto no nombra una que no paso (A4, P2).
3. `language`: la explicacion esta en el idioma del caso.
4. `searches_within_limit`: no mas de `MAX_SEARCHES` busquedas web.
5. `guard_unsubstituted`: la guardia de salida no sustituyo nada (culpa, consejo legal...).
6. `facts_agree`: la decision y la vigencia concuerdan con los hechos de la poliza.
7. `cites_expected_clause`: cita al menos una de las clausulas que el caso exige.
8. `vehicle_value_reported`: cuando no se puede encontrar el valor, el proceso lo dice y decide igual.

Los criterios 1 a 5 son los del plan; el 6 junta la decision y la vigencia, y el 7 y el 8 son la
parte de cada caso (que cite `D.INS.COLLISION` al aprobar un choque, que diga que no encontro el valor).

**Quien decide lo instala quien corre la sonda**, no este modulo: el proceso necesita la base con el
corpus, el cifrador y el cliente de Claude, y eso lo construye la raiz de composicion
(`untangle.server.adjuster_eval`, que llama `mise run evals:ajustador`). El corredor no la importa
(contrato `produccion-sin-evals` y `evals-sin-base-de-datos`). Sin quien decida instalado, o sin la
clave del uso, el caso queda **no medido** con su causa, nunca omitido ni en verde.

Un intento que no llego a decidir por el proveedor (plazo, cuota, saldo) tampoco es rojo: es "no
medido". Uno que no decidio por otra causa --la guardia intervino, la cita no se verifico, la
accion no era de la aseguradora-- si es rojo, y todos sus criterios lo dicen.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final, Literal

from untangle.base import Locale, ProviderErrorKind
from untangle.evals import loading
from untangle.evals.models import AdjusterExpectation, CaseResult, CaseStatus, Dataset
from untangle.evals.runner.api import (
    CheckOutcome,
    EvalTarget,
    register_async_check,
    register_targets,
)
from untangle.evals.runner.failures import (
    BudgetExhaustedError,
    TargetUnavailableError,
)

UNIT = "fase-5-ajustador"

_CASES_DIR = Path("app/evals/cases/ds2")

#: Los directorios de caso de este subconjunto: `adjuster-<nombre>`.
CASE_PREFIX: Final = "adjuster-"

#: El tope de busquedas web por caso que dice el plan, escrito aqui y no leido de la configuracion
#: del ajustador: si alguien sube `max_searches`, este criterio lo tiene que ver.
MAX_SEARCHES: Final = 3

#: Los ocho criterios, en el orden en que se reportan.
CRITERIA: Final = (
    "action_allowed",
    "citations_verified",
    "language",
    "searches_within_limit",
    "guard_unsubstituted",
    "facts_agree",
    "cites_expected_clause",
    "vehicle_value_reported",
)

#: Un identificador de clausula escrito en un texto: `AP-PAP-2026-D.INS.COLLISION`.
_CLAUSE_ID_IN_TEXT = re.compile(
    r"\b[A-Z]{2}-[A-Z]+-\d{4}(?:-[A-Z0-9]+)*-[A-Z][A-Z0-9]*(?:\.[A-Z0-9]+)+"
)

_DECIDED = "decided"
_PROVIDER_PREFIX = "provider_"
_GUARD_BLOCKED = "guard_blocked"


@dataclass(frozen=True)
class AdjusterRequest:
    """Un caso, como lo recibe quien decide."""

    tenant_id: str
    #: Estable por caso e idioma; quien decide lo vuelve unico por corrida.
    case_ref: str
    language: Locale
    policy_number: str
    narrative: str
    evaluated_on: date
    #: `not_found`: la busqueda web no puede traer nada.
    vehicle_value: Literal["open", "not_found"]


@dataclass(frozen=True)
class AdjusterObservation:
    """Lo que se observo tras correr el proceso: solo hechos, ningun veredicto."""

    #: El estado de la corrida: `decided`, `failed` o `capped`.
    status: str
    error_kind: str | None = None
    action: str | None = None
    headline: str = ""
    explanation: str = ""
    #: El texto de las razones y de lo que no se pudo confirmar, tal como se guardo.
    reasons_text: str = ""
    #: Las clausulas que la decision cita (las del paso de la decision).
    cited_clause_ids: tuple[str, ...] = ()
    #: Las que la recuperacion trae para ese relato y esa poliza, medidas otra vez.
    retrieved_clause_ids: tuple[str, ...] = ()
    #: De las citadas, las que el verificador exacto da por buenas, medidas otra vez.
    verified_clause_ids: tuple[str, ...] = ()
    searches_used: int = 0
    #: El idioma que el detector mide en la explicacion; `None` si no puede medirlo.
    explanation_language: str | None = None
    #: Si la guardia de salida deja pasar cada texto de la decision tal cual.
    guard_clean: bool = True
    #: Si la poliza rige en `evaluated_on`, leido del registro; `None` si no se encontro.
    policy_in_force: bool | None = None
    #: Si el paso del valor del vehiculo trae una fuente web.
    vehicle_value_found: bool = False
    #: El texto del paso del valor del vehiculo; vacio si el paso no se guardo.
    vehicle_step_text: str = ""


#: Corre el proceso entero para ese caso y devuelve lo observado.
Decider = Callable[[AdjusterRequest], Awaitable[AdjusterObservation]]

_decisor: Decider | None = None

#: Lo observado en esta corrida, por caso e idioma: los ocho criterios de un caso miran **la
#: misma** decision. Decidir ocho veces costaria ocho veces y mediria ocho decisiones distintas.
_observado: dict[tuple[str, Locale], AdjusterObservation] = {}


def install(decider: Decider | None) -> None:
    """Instala (o quita, con `None`) quien corre el proceso de verdad."""
    global _decisor
    _decisor = decider
    _observado.clear()


class AdjusterProviderError(Exception):
    """El proveedor no dejo decidir el caso. `kind` lo lee el clasificador de fallos del corredor."""

    def __init__(self, kind: ProviderErrorKind) -> None:
        super().__init__(f"el proveedor no dejo decidir el caso: {kind.value}")
        self.kind = kind


def _decided(obs: AdjusterObservation) -> bool:
    return obs.status == _DECIDED and obs.action is not None


def _not_decided(obs: AdjusterObservation) -> list[str]:
    causa = f" ({obs.error_kind})" if obs.error_kind else ""
    return [f"el proceso no llego a decidir: estado '{obs.status}'{causa}"]


def _action_allowed(exp: AdjusterExpectation, obs: AdjusterObservation) -> list[str]:
    if obs.action not in exp.allowed_actions:
        return [
            f"la accion '{obs.action}' no es de las que ofrece esa aseguradora: {list(exp.allowed_actions)}"
        ]
    return []


def _citations_verified(exp: AdjusterExpectation, obs: AdjusterObservation) -> list[str]:
    del exp
    fallos: list[str] = []
    recuperadas = set(obs.retrieved_clause_ids)
    verificadas = set(obs.verified_clause_ids)
    for citada in obs.cited_clause_ids:
        if citada not in recuperadas:
            fallos.append(f"cito '{citada}', que no se recupero de esa poliza")
        elif citada not in verificadas:
            fallos.append(f"cito '{citada}', que el verificador exacto no da por buena")
    texto = "\n".join((obs.headline, obs.explanation, obs.reasons_text))
    for nombrada in dict.fromkeys(_CLAUSE_ID_IN_TEXT.findall(texto)):
        if nombrada not in verificadas:
            fallos.append(f"el texto nombra '{nombrada}', que no esta entre las verificadas")
    return fallos


def _language(exp: AdjusterExpectation, obs: AdjusterObservation, language: Locale) -> list[str]:
    del exp
    if obs.explanation_language is not None and obs.explanation_language != language:
        return [f"la explicacion esta en '{obs.explanation_language}' y el caso es en '{language}'"]
    return []


def _searches_within_limit(exp: AdjusterExpectation, obs: AdjusterObservation) -> list[str]:
    del exp
    if obs.searches_used > MAX_SEARCHES:
        return [f"hizo {obs.searches_used} busquedas y el tope es {MAX_SEARCHES}"]
    return []


def _guard_unsubstituted(exp: AdjusterExpectation, obs: AdjusterObservation) -> list[str]:
    del exp
    if not obs.guard_clean:
        return ["la guardia de salida sustituiria el texto de la decision"]
    return []


def _facts_agree(exp: AdjusterExpectation, obs: AdjusterObservation) -> list[str]:
    fallos: list[str] = []
    if obs.action != exp.expected_action:
        fallos.append(f"decidio '{obs.action}' y los hechos piden '{exp.expected_action}'")
    if obs.policy_in_force is None:
        fallos.append("no se pudo leer la vigencia de la poliza del registro")
    elif obs.policy_in_force != exp.policy_in_force:
        fallos.append(
            f"la poliza {'rige' if obs.policy_in_force else 'no rige'} el "
            f"{exp.evaluated_on} y el caso espera lo contrario"
        )
    if obs.policy_in_force is False and obs.action == "approve":
        fallos.append("aprobo con la poliza fuera de vigencia")
    return fallos


def _cites_expected_clause(exp: AdjusterExpectation, obs: AdjusterObservation) -> list[str]:
    if not exp.cites_any_of:
        return []
    for citada in obs.cited_clause_ids:
        if any(citada == s or citada.endswith(f"-{s}") for s in exp.cites_any_of):
            return []
    return [f"no cito ninguna de {list(exp.cites_any_of)} (citadas: {list(obs.cited_clause_ids)})"]


def _vehicle_value_reported(exp: AdjusterExpectation, obs: AdjusterObservation) -> list[str]:
    if exp.vehicle_value != "not_found":
        return []
    fallos: list[str] = []
    if obs.vehicle_value_found:
        fallos.append("trajo un valor con fuente web donde no podia haber ninguno")
    if not obs.vehicle_step_text:
        fallos.append("el paso del valor del vehiculo no dice nada")
    if obs.action != exp.expected_action:
        fallos.append(f"sin el valor no decidio '{exp.expected_action}' sino '{obs.action}'")
    return fallos


def evaluate(
    expected: AdjusterExpectation, observation: AdjusterObservation, language: Locale
) -> dict[str, list[str]]:
    """Las diferencias por criterio entre lo observado y lo esperado; vacia la lista si coincide.

    Si el proceso no llego a decidir, **todos** los criterios lo dicen: una decision que no existe
    no esta bien en ningun criterio.
    """
    if not _decided(observation):
        return {criterio: _not_decided(observation) for criterio in CRITERIA}
    return {
        "action_allowed": _action_allowed(expected, observation),
        "citations_verified": _citations_verified(expected, observation),
        "language": _language(expected, observation, language),
        "searches_within_limit": _searches_within_limit(expected, observation),
        "guard_unsubstituted": _guard_unsubstituted(expected, observation),
        "facts_agree": _facts_agree(expected, observation),
        "cites_expected_clause": _cites_expected_clause(expected, observation),
        "vehicle_value_reported": _vehicle_value_reported(expected, observation),
    }


def criterion_of(criterion: str, case_name: str) -> str:
    """El nombre con el que un criterio de un caso queda en el reporte."""
    return f"adjuster_{criterion}_{case_name.removeprefix(CASE_PREFIX).replace('-', '_')}"


def _raise_if_provider_stopped(obs: AdjusterObservation) -> None:
    """Un proveedor que no dejo decidir no es un rojo del producto: es un caso no medido."""
    if obs.status == "capped":
        msg = "el saldo o el cupo del dia impidieron decidir el caso"
        raise BudgetExhaustedError(msg)
    if obs.error_kind is not None and obs.error_kind.startswith(_PROVIDER_PREFIX):
        try:
            raise AdjusterProviderError(
                ProviderErrorKind(obs.error_kind.removeprefix(_PROVIDER_PREFIX))
            )
        except ValueError:
            return


async def _observe(
    name: str, language: Locale, root: Path
) -> tuple[AdjusterExpectation, AdjusterObservation] | None:
    caso = loading.load_case(root / _CASES_DIR / name / f"{language}.yaml")
    esperado = caso.adjuster
    if esperado is None or caso.tenant is None:
        return None
    decisor = _decisor
    if decisor is None:
        msg = (
            "no hay quien decida instalado: el ajustador se mide con `mise run evals:ajustador`, "
            "que construye el proceso con la base, el corpus y la clave del uso `adjuster`"
        )
        raise TargetUnavailableError(msg)
    clave = (name, language)
    if clave not in _observado:
        observado = await decisor(
            AdjusterRequest(
                tenant_id=caso.tenant,
                case_ref=f"eval-{name}-{language}",
                language=language,
                policy_number=esperado.policy_number,
                narrative=esperado.narrative,
                evaluated_on=esperado.evaluated_on,
                vehicle_value=esperado.vehicle_value,
            )
        )
        _raise_if_provider_stopped(observado)
        _observado[clave] = observado
    return esperado, _observado[clave]


def _sonda(name: str, criterion: str) -> Callable[..., Awaitable[CheckOutcome]]:
    async def sonda(*, language: Locale, root: Path) -> CheckOutcome:
        visto = await _observe(name, language, root)
        if visto is None:
            return CheckOutcome(passed=False, detail=f"el caso '{name}' no trae su ajustador")
        esperado, observado = visto
        fallos = evaluate(esperado, observado, language)[criterion]
        return CheckOutcome(passed=not fallos, detail="; ".join(fallos))

    return sonda


def _names(root: Path | None) -> tuple[str, ...]:
    base = (root or Path.cwd()) / _CASES_DIR
    if not base.is_dir():
        return ()
    return tuple(
        sorted(d.name for d in base.iterdir() if d.is_dir() and d.name.startswith(CASE_PREFIX))
    )


def register_adjuster_probes(root: Path | None = None) -> None:
    """Registra una sonda por criterio y por caso de `adjuster-*`, y sus objetivos."""
    nombres = _names(root)
    for nombre in nombres:
        for criterio in CRITERIA:
            register_async_check(criterion_of(criterio, nombre), _sonda(nombre, criterio))
    register_targets(
        UNIT,
        tuple(
            EvalTarget(
                criterion_of(criterio, nombre),
                Dataset.DS_2,
                f"El ajustador de IA ({criterio}): {nombre}",
            )
            for nombre in nombres
            for criterio in CRITERIA
        ),
    )


def summarize_by_criterion(results: Iterable[CaseResult]) -> str:
    """Una tabla por criterio y por idioma: cuantos casos pasaron de cuantos se midieron.

    Nunca un promedio combinado de los dos idiomas (P12): cada fila es un criterio y cada
    columna un idioma. Un caso no medido no suma ni a los que pasaron ni a los que fallaron.
    """
    cuentas: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for resultado in results:
        if f"/{CASE_PREFIX}" not in resultado.case_key:
            continue
        idioma = resultado.case_key.split("/")[1]
        if resultado.status is CaseStatus.NOT_MEASURED:
            for criterio in CRITERIA:
                cuentas[(criterio, idioma)][2] += 1
            continue
        for nombre, veredicto in resultado.criteria_results.items():
            medido = next((c for c in CRITERIA if nombre.startswith(f"adjuster_{c}_")), None)
            if medido is None:
                continue
            cuentas[(medido, idioma)][0 if veredicto == "pass" else 1] += 1
    lineas = ["criterio                  es (pasa/falla/no medido)   en (pasa/falla/no medido)"]
    for criterio in CRITERIA:
        celdas = []
        for idioma in ("es", "en"):
            ok, mal, sin = cuentas[(criterio, idioma)]
            celdas.append(f"{ok}/{mal}/{sin}".ljust(27))
        lineas.append(f"{criterio.ljust(25)} {celdas[0]} {celdas[1]}".rstrip())
    return "\n".join(lineas)


__all__ = [
    "CASE_PREFIX",
    "CRITERIA",
    "MAX_SEARCHES",
    "UNIT",
    "AdjusterObservation",
    "AdjusterProviderError",
    "AdjusterRequest",
    "Decider",
    "criterion_of",
    "evaluate",
    "install",
    "register_adjuster_probes",
    "summarize_by_criterion",
]
