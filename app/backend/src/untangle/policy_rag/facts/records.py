"""De la poliza emitida a sus datos tipados: funciones puras, sin base ni reloj (plan 09, punto 6).

Cada funcion recibe la `IssuedPolicy` ya leida y devuelve un modelo de `models.py`. Los valores
salen **tal cual del registro**: ni se interpretan, ni se redondean, ni se completan. Lo unico que
se calcula es la vigencia, contra una fecha que entrega el llamador (`on`): el modulo no lee el
reloj, igual que `retrieval._vigente`, para que la vigencia se pruebe con fechas fijas.

La lectura de la base y la regla de aislamiento por aseguradora estan en `api.py`; aqui no hay
nada que consultar, y por eso estas funciones se prueban con una poliza de ejemplo en memoria.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

from untangle.base import Locale
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.policy_rag.corpus.models import IssuedPolicy
from untangle.policy_rag.facts import formatting
from untangle.policy_rag.facts.models import (
    Amount,
    DeductibleFact,
    DriverFact,
    EndorsementFact,
    LimitFact,
    PolicyStatus,
    PolicySummary,
    VehicleFact,
)

#: Las claves del corpus que son un deducible. Todo lo demas de `limits_and_deductibles` es un limite.
_DEDUCTIBLE_SUFFIX = "_deductible"


def status_on(policy: IssuedPolicy, on: date) -> PolicyStatus:
    """Si la poliza rige en esa fecha. Los dos extremos del periodo cuentan como vigentes."""
    if on < policy.period_start:
        return PolicyStatus.NOT_YET_IN_FORCE
    if on > policy.period_end:
        return PolicyStatus.EXPIRED
    return PolicyStatus.IN_FORCE


def summarize(policy: IssuedPolicy, *, on: date) -> PolicySummary:
    """Titular, emisora, periodo y vigencia en `on`, y cuantos vehiculos, conductores y endosos trae."""
    return PolicySummary(
        tenant_id=policy.tenant_id,
        policy_number=policy.policy_number,
        holder_name=str(policy.named_insured.get("full_name", "")),
        issuer_tenant=policy.issuer_tenant,
        form_id=policy.form_id,
        form_version=policy.form_version,
        period_start=policy.period_start,
        period_end=policy.period_end,
        as_of=on,
        status=status_on(policy, on),
        vehicle_count=len(policy.vehicles),
        driver_count=len(policy.drivers),
        endorsement_count=len(policy.endorsement_ids),
    )


def _amount(units: object, language: Locale) -> Amount:
    cifra = int(str(units))
    return Amount(
        units=cifra,
        pesos=formatting.to_pesos(cifra),
        formatted=formatting.format_pesos(cifra, language),
        language=language,
    )


def _limit_labels(language: Locale) -> dict[str, str]:
    """El rotulo de cada clave del corpus, del catalogo de la pestana de polizas.

    Una tabla de literales y no una clave armada con la del corpus: el chequeo de claves del
    catalogo busca el consumidor de cada una con un grep.
    """
    return {
        "a.bodily_injury_per_person": copy_api.t(
            CopyKey("policies.limit.a_bodily_injury_per_person"), locale=language
        ),
        "a.bodily_injury_per_accident": copy_api.t(
            CopyKey("policies.limit.a_bodily_injury_per_accident"), locale=language
        ),
        "a.property_damage": copy_api.t(
            CopyKey("policies.limit.a_property_damage"), locale=language
        ),
        "b.medical_payments_per_person": copy_api.t(
            CopyKey("policies.limit.b_medical_payments_per_person"), locale=language
        ),
        "c.driver_personal_accident": copy_api.t(
            CopyKey("policies.limit.c_driver_personal_accident"), locale=language
        ),
        "d.damage_deductible": copy_api.t(
            CopyKey("policies.limit.d_damage_deductible"), locale=language
        ),
        "d.theft_deductible": copy_api.t(
            CopyKey("policies.limit.d_theft_deductible"), locale=language
        ),
    }


def limits_of(policy: IssuedPolicy, *, language: Locale) -> tuple[LimitFact, ...]:
    """Los limites de la poliza, en el orden del corpus (de la responsabilidad civil a los deducibles)."""
    rotulos = _limit_labels(language)
    return tuple(
        LimitFact(key=clave, label=rotulos.get(clave, clave), amount=_amount(valor, language))
        for clave, valor in sorted(policy.limits_and_deductibles.items())
        if not clave.endswith(_DEDUCTIBLE_SUFFIX)
    )


def deductibles_of(policy: IssuedPolicy, *, language: Locale) -> tuple[DeductibleFact, ...]:
    """Los deducibles de la poliza."""
    rotulos = _limit_labels(language)
    return tuple(
        DeductibleFact(key=clave, label=rotulos.get(clave, clave), amount=_amount(valor, language))
        for clave, valor in sorted(policy.limits_and_deductibles.items())
        if clave.endswith(_DEDUCTIBLE_SUFFIX)
    )


def vehicles_of(policy: IssuedPolicy) -> tuple[VehicleFact, ...]:
    """Los vehiculos asegurados, por su descripcion. La placa y el VIN no salen de aqui."""
    return tuple(
        VehicleFact(description=str(v["make_model_year"]))
        for v in policy.vehicles
        if v.get("make_model_year")
    )


def drivers_of(policy: IssuedPolicy) -> tuple[DriverFact, ...]:
    """Los conductores que la poliza declara, el titular primero.

    **Vacio es «no declara conductores»**, no «no tiene ninguno» (`IssuedPolicy.drivers`): quien
    use el resultado no puede decir que alguien no figura cuando la lista no se sabe.
    """
    titular = str(policy.named_insured.get("full_name", "")).casefold()
    return tuple(
        DriverFact(full_name=d.full_name, is_holder=d.full_name.casefold() == titular)
        for d in policy.drivers
    )


def _endorsement_summaries(language: Locale) -> dict[str, str]:
    """Lo que cambia cada endoso conocido, por la clave de la clausula que modifica."""
    return {
        "DEF.FAMILY_MEMBER": copy_api.t(
            CopyKey("policies.endorsement.def_family_member"), locale=language
        ),
        "A.EXCL.A.5": copy_api.t(CopyKey("policies.endorsement.a_excl_a_5"), locale=language),
        "D.EXCL.3": copy_api.t(CopyKey("policies.endorsement.d_excl_3"), locale=language),
        "C.ARBITRATION": copy_api.t(CopyKey("policies.endorsement.c_arbitration"), locale=language),
        "F.PERIOD_TERRITORY": copy_api.t(
            CopyKey("policies.endorsement.f_period_territory"), locale=language
        ),
        "DEF.COVERED_AUTO": copy_api.t(
            CopyKey("policies.endorsement.def_covered_auto"), locale=language
        ),
        "D.EXCL.5": copy_api.t(CopyKey("policies.endorsement.d_excl_5"), locale=language),
        "D.TRANSPORT": copy_api.t(CopyKey("policies.endorsement.d_transport"), locale=language),
        "B.INS": copy_api.t(CopyKey("policies.endorsement.b_ins"), locale=language),
        "F.TERMINATION": copy_api.t(CopyKey("policies.endorsement.f_termination"), locale=language),
    }


def endorsements_of(
    policy: IssuedPolicy,
    *,
    clause_keys: Mapping[str, Sequence[str]],
    language: Locale,
) -> tuple[EndorsementFact, ...]:
    """Los endosos de la poliza y que clausulas cambia cada uno.

    `clause_keys` es lo que trae cada formulario de endoso (`corpus.clause_keys_of_forms`): un
    endoso sin entrada se devuelve igual, con la lista vacia, porque que la poliza lo trae es un
    dato del registro aunque no se sepa que cambia.
    """
    frases = _endorsement_summaries(language)
    hechos: list[EndorsementFact] = []
    for form_id in policy.endorsement_ids:
        claves = tuple(clause_keys.get(form_id, ()))
        hechos.append(
            EndorsementFact(
                form_id=form_id,
                clause_keys=claves,
                summaries=tuple(frases[c] for c in claves if c in frases),
            )
        )
    return tuple(hechos)


__all__ = [
    "deductibles_of",
    "drivers_of",
    "endorsements_of",
    "limits_of",
    "status_on",
    "summarize",
    "vehicles_of",
]
