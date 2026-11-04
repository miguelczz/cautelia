"""El texto de cada paso: frases del catalogo, en el idioma del caso, con los hechos dentro.

Lo que el visitante lee de cada paso lo escribe el codigo desde el catalogo --las frases--, con los
hechos exactos que acaba de leer --los numeros, las fechas, los identificadores--. El unico texto
libre del proceso es la explicacion de la decision, y esa pasa por la validacion y la guardia.

Cada paso lleva su `title_key`, que la interfaz resuelve en el idioma de quien mira, y sus fuentes:
las clausulas con su identificador, las reglas que se dispararon, la pagina de la que sale el valor.
"""

from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import urlparse

from untangle.adjuster.gather import CaseReading, PolicyReading
from untangle.adjuster.models import RunStep, SourceKind, StepId, StepSource
from untangle.adjuster.validation import ValidatedDecision
from untangle.adjuster.vehicle_value import Firmness, ValueStatus, VehicleValue
from untangle.base import Locale
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.policy_rag.corpus.models import Clause
from untangle.policy_rag.facts import formatting
from untangle.policy_rag.facts.models import PolicyStatus, PolicySummary
from untangle.rules.models import RuleEvaluation

#: Cuantas clausulas recuperadas se listan como fuente del paso que las busca.
_MAX_CLAUSE_SOURCES = 12


# Una constante por clave, como en el resto del aplicativo: asi cada clave tiene su consumidor
# literal y el chequeo de claves sin consumidor (BR3.2, BR3.4) sigue siendo exacto.
NOTHING = CopyKey("adjuster.step.nothing")
CASE_READ_TITLE = CopyKey("adjuster.step.case_read.title")
CASE_READ_BODY = CopyKey("adjuster.step.case_read.body")
POLICY_READ_TITLE = CopyKey("adjuster.step.policy_read.title")
POLICY_IN_FORCE = CopyKey("adjuster.step.policy_read.in_force")
POLICY_EXPIRED = CopyKey("adjuster.step.policy_read.expired")
POLICY_NOT_YET_IN_FORCE = CopyKey("adjuster.step.policy_read.not_yet_in_force")
POLICY_NONE = CopyKey("adjuster.step.policy_read.no_policy")
POLICY_NOT_FOUND = CopyKey("adjuster.step.policy_read.not_found")
POLICY_DETAILS = CopyKey("adjuster.step.policy_read.details")
POLICY_SOURCE = CopyKey("adjuster.step.policy_read.source")
CLAUSES_TITLE = CopyKey("adjuster.step.clauses.title")
CLAUSES_FOUND = CopyKey("adjuster.step.clauses.found")
CLAUSES_NONE_FOUND = CopyKey("adjuster.step.clauses.none_found")
CLAUSES_NOT_IN_FORCE = CopyKey("adjuster.step.clauses.not_in_force")
CLAUSES_NO_POLICY = CopyKey("adjuster.step.clauses.no_policy")
RULES_TITLE = CopyKey("adjuster.step.rules.title")
RULES_FIRED = CopyKey("adjuster.step.rules.fired")
RULES_NONE_FIRED = CopyKey("adjuster.step.rules.none_fired")
RULES_MISSING = CopyKey("adjuster.step.rules.missing")
VEHICLE_VALUE_TITLE = CopyKey("adjuster.step.vehicle_value.title")
VEHICLE_VALUE_FOUND = CopyKey("adjuster.step.vehicle_value.found")
VEHICLE_VALUE_NOT_VERIFIED = CopyKey("adjuster.step.vehicle_value.not_verified")
VEHICLE_VALUE_NO_VEHICLE = CopyKey("adjuster.step.vehicle_value.no_vehicle")
VEHICLE_VALUE_NO_POLICY = CopyKey("adjuster.step.vehicle_value.no_policy")
FIRMNESS_HIGH = CopyKey("adjuster.step.firmness.high")
FIRMNESS_MEDIUM = CopyKey("adjuster.step.firmness.medium")
FIRMNESS_LOW = CopyKey("adjuster.step.firmness.low")
DECISION_TITLE = CopyKey("adjuster.step.decision.title")
DECISION_UNCERTAINTIES = CopyKey("adjuster.step.decision.uncertainties")

#: La clave que cae cuando la regla que derivo el caso trae una razon que el catalogo no conoce.
RULE_REASON_DEFAULT = CopyKey("rules.explain.default")

_TITLES: dict[StepId, CopyKey] = {
    StepId.CASE_READ: CASE_READ_TITLE,
    StepId.POLICY_READ: POLICY_READ_TITLE,
    StepId.CLAUSES: CLAUSES_TITLE,
    StepId.RULES: RULES_TITLE,
    StepId.VEHICLE_VALUE: VEHICLE_VALUE_TITLE,
    StepId.DECISION: DECISION_TITLE,
}


def title_key(step: StepId) -> str:
    """La clave del titulo de cada paso, que la interfaz resuelve en el idioma de quien mira."""
    return _TITLES[step]


def format_cop(pesos: int, language: Locale) -> str:
    """Pesos colombianos escritos para el idioma, igual que los montos de la poliza."""
    if language == "es":
        return f"$\xa0{pesos:,}".replace(",", ".")
    return f"COP\xa0{pesos:,}"


def case_read(reading: CaseReading, language: Locale) -> RunStep:
    cuantos = len(reading.fields) + (1 if reading.narrative else 0)
    return RunStep(
        id=StepId.CASE_READ,
        title_key=title_key(StepId.CASE_READ),
        text=copy_api.t(
            CASE_READ_BODY,
            locale=language,
            case_number=reading.detail.case_number,
            fields=str(cuantos),
        ),
    )


def _listed(values: Sequence[str], language: Locale) -> str:
    return "; ".join(values) if values else copy_api.t(NOTHING, locale=language)


def _policy_sentence(resumen: PolicySummary, details: str, language: Locale) -> str:
    datos = {
        "policy_number": resumen.policy_number,
        "holder": resumen.holder_name,
        "start": formatting.format_date(resumen.period_start, language),
        "end": formatting.format_date(resumen.period_end, language),
        "details": details,
    }
    if resumen.status is PolicyStatus.IN_FORCE:
        return copy_api.t(POLICY_IN_FORCE, locale=language, **datos)
    if resumen.status is PolicyStatus.EXPIRED:
        return copy_api.t(POLICY_EXPIRED, locale=language, **datos)
    return copy_api.t(POLICY_NOT_YET_IN_FORCE, locale=language, **datos)


def policy_read(reading: PolicyReading, language: Locale) -> RunStep:
    resumen = reading.summary
    fuentes: tuple[StepSource, ...] = ()
    if reading.policy_number is None:
        texto = copy_api.t(POLICY_NONE, locale=language)
    elif resumen is None:
        texto = copy_api.t(POLICY_NOT_FOUND, locale=language, policy_number=reading.policy_number)
    else:
        detalle = copy_api.t(
            POLICY_DETAILS,
            locale=language,
            vehicles=_listed([v.description for v in reading.vehicles], language),
            drivers=_listed([d.full_name for d in reading.drivers], language),
            deductibles=_listed(
                [f"{d.label} {d.amount.formatted}" for d in reading.deductibles], language
            ),
            limits=_listed([f"{x.label} {x.amount.formatted}" for x in reading.limits], language),
            endorsements=_listed([s for e in reading.endorsements for s in e.summaries], language),
        )
        texto = _policy_sentence(resumen, detalle, language)
        fuentes = (
            StepSource(
                kind=SourceKind.POLICY,
                ref=resumen.policy_number,
                label=copy_api.t(
                    POLICY_SOURCE, locale=language, policy_number=resumen.policy_number
                ),
            ),
        )
    return RunStep(
        id=StepId.POLICY_READ,
        title_key=title_key(StepId.POLICY_READ),
        text=texto,
        sources=fuentes,
    )


def clauses(retrieved: Sequence[Clause], reading: PolicyReading, language: Locale) -> RunStep:
    resumen = reading.summary
    if resumen is None:
        texto = copy_api.t(CLAUSES_NO_POLICY, locale=language)
    elif resumen.status is not PolicyStatus.IN_FORCE:
        texto = copy_api.t(CLAUSES_NOT_IN_FORCE, locale=language)
    elif not retrieved:
        texto = copy_api.t(CLAUSES_NONE_FOUND, locale=language)
    else:
        texto = copy_api.t(CLAUSES_FOUND, locale=language, count=str(len(retrieved)))
    return RunStep(
        id=StepId.CLAUSES,
        title_key=title_key(StepId.CLAUSES),
        text=texto,
        sources=tuple(_clause_source(c) for c in retrieved[:_MAX_CLAUSE_SOURCES]),
    )


def _clause_source(clause: Clause) -> StepSource:
    return StepSource(kind=SourceKind.CLAUSE, ref=clause.clause_id, label=clause.part)


def rule_refs(evaluation: RuleEvaluation | None) -> tuple[str, ...]:
    """Los identificadores versionados de las reglas que se dispararon."""
    if evaluation is None:
        return ()
    return tuple(f"{r.id}@{r.version}" for r in evaluation.fired_rules)


def _rule_reason(explanation_key: str, language: Locale) -> str:
    """La razon por la que las reglas derivaron el caso, en el idioma del caso.

    La clave es un dato guardado con la evaluacion (el `then.explanation_key` de la regla): no se
    arma aqui, se lee del catalogo tal como esta. Una clave que el catalogo no trae cae a la razon
    por defecto en vez de mostrar la clave a una persona.
    """
    entrada = copy_api.get_catalog().entries.get((explanation_key, language))
    if entrada is None:
        return copy_api.t(RULE_REASON_DEFAULT, locale=language)
    return entrada.text


def rules(evaluation: RuleEvaluation | None, language: Locale) -> RunStep:
    fuentes: tuple[StepSource, ...] = ()
    if evaluation is None:
        texto = copy_api.t(RULES_MISSING, locale=language)
    else:
        motivo = _rule_reason(evaluation.explanation_key, language)
        if evaluation.fired_rules:
            texto = copy_api.t(RULES_FIRED, locale=language, reason=motivo)
        else:
            texto = copy_api.t(RULES_NONE_FIRED, locale=language, reason=motivo)
        fuentes = tuple(
            StepSource(kind=SourceKind.RULE, ref=f"{r.id}@{r.version}", label=r.id)
            for r in evaluation.fired_rules
        )
    return RunStep(id=StepId.RULES, title_key=title_key(StepId.RULES), text=texto, sources=fuentes)


def _firmness_phrase(firmness: Firmness | None, language: Locale) -> str:
    if firmness is Firmness.HIGH:
        return copy_api.t(FIRMNESS_HIGH, locale=language)
    if firmness is Firmness.MEDIUM:
        return copy_api.t(FIRMNESS_MEDIUM, locale=language)
    return copy_api.t(FIRMNESS_LOW, locale=language)


def vehicle_value(value: VehicleValue, language: Locale, *, has_policy: bool) -> RunStep:
    fuentes: tuple[StepSource, ...] = ()
    if value.status is ValueStatus.NO_VEHICLE:
        texto = copy_api.t(
            VEHICLE_VALUE_NO_VEHICLE if has_policy else VEHICLE_VALUE_NO_POLICY, locale=language
        )
    elif value.status is ValueStatus.FOUND and value.value_cop is not None and value.source:
        texto = copy_api.t(
            VEHICLE_VALUE_FOUND,
            locale=language,
            vehicle=value.vehicle or "",
            value=format_cop(value.value_cop, language),
            firmness=_firmness_phrase(value.firmness, language),
        )
        fuentes = (
            StepSource(
                kind=SourceKind.WEB,
                ref=value.source.url,
                label=value.source.title
                or (urlparse(value.source.url).hostname or value.source.url),
                url=value.source.url,
            ),
        )
    else:
        texto = copy_api.t(VEHICLE_VALUE_NOT_VERIFIED, locale=language, vehicle=value.vehicle or "")
    return RunStep(
        id=StepId.VEHICLE_VALUE,
        title_key=title_key(StepId.VEHICLE_VALUE),
        text=texto,
        sources=fuentes,
    )


def decision(validated: ValidatedDecision, language: Locale) -> RunStep:
    """Las razones de la decision, y lo que no se pudo confirmar, con las clausulas que cita."""
    lineas = [razon.text for razon in validated.reasons]
    if validated.uncertainties:
        lineas.append(
            copy_api.t(
                DECISION_UNCERTAINTIES,
                locale=language,
                items="; ".join(validated.uncertainties),
            )
        )
    return RunStep(
        id=StepId.DECISION,
        title_key=title_key(StepId.DECISION),
        text="\n".join(lineas),
        sources=tuple(_clause_source(c) for c in validated.verified_clauses),
    )
