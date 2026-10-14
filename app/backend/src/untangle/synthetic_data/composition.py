"""La composicion del corpus entero, en el orden de F3.2 (BR1.3).

Es **un solo compositor** y no ocho, a proposito: cada paso usa lo que dejo el
anterior --las polizas necesitan los formularios de su emisora, los casos necesitan
las polizas, la lista de valores personales necesita las dos-- y cada salida pide
su flujo de azar una sola vez (BR1.2). Ocho compositores independientes tendrian
que volver a componer lo anterior y pedirian dos veces el mismo flujo, que es
justo lo que el elegidor prohibe.

El orden es el de F3.2:

1. formularios base y endosos de cada emisora;
2. distractores y relaciones entre clausulas;
3. copias de la agencia desde el original;
4. personas y vehiculos ficticios;
5. polizas emitidas, con las `example_policy` de `tenant.yaml`;
6. casos sembrados;
6b. los conductores que declara cada poliza (despues de los casos, para no mover nada de
    lo ya sembrado: ver `policies.declare_drivers`);
7. DS-8;
8. la lista de valores personales.

Todo problema se junta y se devuelve: el nucleo no escribe nada si hay uno solo.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from pydantic import BaseModel

from untangle.synthetic_data import cases as casos
from untangle.synthetic_data import corpus as corpus_mod
from untangle.synthetic_data import ds8
from untangle.synthetic_data.generator import Composition, CompositionContext, CorpusOutput
from untangle.synthetic_data.manifest import ManifestRecords
from untangle.synthetic_data.models import (
    DATA_PREFIX,
    PERSONAL_VALUES_OUTPUT,
    PersonalValue,
    PersonalValueKind,
    PersonalValueList,
)
from untangle.synthetic_data.people import People, PeopleError, Pools, UsedValues
from untangle.synthetic_data.policies import (
    ComposedPolicy,
    PolicyError,
    compose_policies,
    declare_drivers,
    policy_path,
)

__all__ = ["compose_corpus", "personal_values"]

#: La lista de valores personales, como ruta dentro de `app/data/`.
_VALORES_PERSONALES = PERSONAL_VALUES_OUTPUT.removeprefix(DATA_PREFIX)


def personal_values(
    policies: Mapping[str, Iterable[ComposedPolicy]], others: Iterable[PersonalValue]
) -> PersonalValueList:
    """Cada valor personal ficticio sembrado, por tipo e idioma (BR7.2, FD-U7-8).

    El idioma es el de la persona que lo tiene: una cedula colombiana es de la
    persona en espanol aunque aparezca en un caso en ingles.
    """
    valores: set[tuple[str, str, str]] = set()
    for grupo in policies.values():
        for poliza in grupo:
            registro, idioma = poliza.record, poliza.language
            persona = registro.named_insured
            # Los conductores adicionales son personas ficticias como el titular, y su nombre
            # tambien se pone a prueba en la redaccion (el del titular ya esta abajo).
            valores |= {
                (PersonalValueKind.NAME.value, idioma, d.full_name) for d in registro.drivers
            }
            valores |= {
                (PersonalValueKind.NAME.value, idioma, persona.full_name),
                (PersonalValueKind.PHONE.value, idioma, persona.phone),
                (PersonalValueKind.NATIONAL_ID.value, idioma, persona.national_id),
                (PersonalValueKind.EMAIL.value, idioma, persona.email),
                (PersonalValueKind.POLICY_NUMBER.value, idioma, registro.policy_number),
            }
            for vehiculo in registro.vehicles:
                valores.add((PersonalValueKind.PLATE.value, idioma, vehiculo.plate))
                valores.add((PersonalValueKind.VIN.value, idioma, vehiculo.vin))
    valores |= {(v.kind.value, v.language, v.value) for v in others}
    return PersonalValueList(
        values=tuple(
            PersonalValue.model_validate({"kind": kind, "language": idioma, "value": valor})
            for kind, idioma, valor in sorted(valores)
        )
    )


def compose_corpus(context: CompositionContext) -> Composition:
    """El corpus entero, sus registros para el manifiesto y todo lo que no cuadro."""
    problemas: list[str] = []
    salidas: dict[str, BaseModel | Mapping[str, object]] = {}

    # 1 a 3: formularios, endosos, distractores, relaciones y copias de la agencia.
    compuesto = corpus_mod.compose_corpus_texts(context.sources, context.tenants)
    problemas.extend(compuesto.problems)
    salidas.update(compuesto.outputs)
    diferencias_fuente = context.sources.differences
    diferencias, problemas_de_diferencias = corpus_mod.check_differences(
        diferencias_fuente.content if diferencias_fuente is not None else None, compuesto.issuers
    )
    problemas.extend(problemas_de_diferencias)

    try:
        roles = ds8.roles_from(context.tenants)
    except ds8.DS8Error as error:
        return Composition(problems=(*problemas, str(error)))

    # 4 y 5: personas, vehiculos y polizas emitidas.
    people = People(pools=Pools.from_sources(context.sources.texts), used=UsedValues())
    siembra = (context.chooser, people)
    try:
        polizas = compose_policies(context.tenants, compuesto.issuers, roles, siembra)
    except (PeopleError, PolicyError) as error:
        return Composition(problems=(*problemas, str(error)))

    # 6: casos sembrados.
    sembrados = casos.compose_cases(context.sources.texts, polizas, context.tenants, siembra)
    problemas.extend(sembrados.problems)
    registros = [c.record for c in sembrados.cases]
    cierran_directo = casos.direct_close_tenants(context.tenants_dir, context.tenants)
    problemas.extend(casos.check_coverage(registros, context.tenants, cierran_directo))
    criterios = context.sources.criteria
    problemas.extend(
        casos.check_criteria(registros, criterios.content if criterios is not None else None)
    )
    for caso in sembrados.cases:
        salidas[caso.path] = caso.record

    # 6b: los conductores que declara cada poliza, y con ellos las polizas se escriben.
    try:
        polizas = declare_drivers(polizas, siembra)
    except PeopleError as error:
        return Composition(problems=(*problemas, str(error)))
    for tenant_id, grupo in polizas.items():
        for poliza in grupo:
            salidas[policy_path(tenant_id, poliza.record.policy_number)] = poliza.record

    # 7: DS-8, con las mismas filas que escribio U2.
    salidas[ds8.DS8_OUTPUT] = ds8.compose_ds8(roles)

    # 8: la lista de valores personales.
    salidas[_VALORES_PERSONALES] = personal_values(
        polizas, (v for c in sembrados.cases for v in c.others)
    )

    return Composition(
        outputs=tuple(
            CorpusOutput(relative=ruta, document=documento)
            for ruta, documento in sorted(salidas.items())
        ),
        records=ManifestRecords(
            declared_differences=diferencias, seeded_cases=sembrados.refs(DATA_PREFIX)
        ),
        problems=tuple(problemas),
    )
