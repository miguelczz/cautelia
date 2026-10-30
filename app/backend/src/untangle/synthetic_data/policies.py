"""Las polizas emitidas, con sus personas y sus vehiculos (F3.2, pasos 4 y 5; BR3.6, BR4.3).

Cada aseguradora recibe `POLICIES_PER_TENANT` polizas **de su decena**, en este orden:

1. **Su `example_policy`**, la que muestra el chat publico (C-25), con todos los
   endosos de su emisora para que la demostracion los tenga a mano. Es la primera de
   su decena: `POL-11` para Seguros Aburra, `POL-21` para Autos Poblado, `POL-31` para
   Agencia Castilla. Decision de Miguel del 2026-10-30: un numero que se dice en dos
   cifras y que dice de quien es la poliza.
2. **Las polizas de DS-8** que sean suyas, con el numero, el asegurado y la
   vigencia que DS-8 declara: la colision de numero entre dos emisoras existe
   tambien en el corpus, que es donde U8 la ingiere. Una de DS-8 que cae fuera de la
   decena (la compartida, `POL-50`) se suma a las de la decena; una que cae dentro
   ocupa uno de sus numeros.
3. Las demas, con los numeros libres que siguen al de ejemplo dentro de la decena,
   en orden, y datos sembrados. Si la decena no alcanza, falla diciendolo.

**En una agencia, cada poliza dice quien la emitio** (BR4.3): `issuer_tenant` es
una emisora y el formulario es el de esa emisora, que la agencia tiene copiado.
La de ejemplo la emite la emisora que escribe en el idioma de la agencia; la de
DS-8, la primera emisora de otro idioma; las demas se reparten por turnos entre
las emisoras. Nada de esto nombra a ninguna: sale del tipo y del idioma de cada
una en su configuracion.

La persona asegurada escribe en el idioma de la emisora, que es el de sus
documentos: un cliente de la agencia con poliza de una emisora en espanol tiene
cedula y movil colombianos.

**Los limites** salen de tablas iguales para todas: la diferencia entre
aseguradoras esta en sus formularios y sus endosos, no aqui (BR4.2 de U2). Los
minimos respetan los del documento de jurisdiccion de Corvane.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Final

from untangle.base import Locale
from untangle.synthetic_data.chooser import ChooserFactory
from untangle.synthetic_data.corpus import IssuerCorpus
from untangle.synthetic_data.ds8 import DS8Roles, FixedPolicy, fixed_policies
from untangle.synthetic_data.models import DriverRef, IssuedPolicyRecord
from untangle.synthetic_data.people import (
    People,
    compose_persona,
    compose_relative_name,
    compose_vehicle,
)
from untangle.tenancy.config import LoadedTenants
from untangle.tenancy.models import TenantConfig, TenantKind

__all__ = [
    "POLICIES_PER_TENANT",
    "ComposedPolicy",
    "PolicyError",
    "compose_policies",
    "declare_drivers",
    "policy_path",
]

#: Cuantas polizas de su decena tiene cada aseguradora: suficientes para que los casos
#: sembrados no compartan todos al mismo asegurado. Una decena tiene diez numeros y la de
#: ejemplo es la primera de seis, asi que el limite natural es el final de la decena.
POLICIES_PER_TENANT: Final = 6

#: El inicio mas temprano de una vigencia sembrada, y cuantos dias despues puede
#: empezar. Con vigencias de un ano, toda poliza esta vigente durante la ventana de
#: la demostracion, que empieza el 2026-09-16.
_PRIMER_INICIO: Final = date(2026, 1, 1)
_DIAS_DE_INICIO: Final = 240

#: Opciones de limites y deducibles. Los de responsabilidad empiezan en los
#: minimos de Corvane: $25.000 por persona, $50.000 por accidente, $20.000 en bienes.
_POR_PERSONA: Final = (25_000, 50_000, 100_000)
_BIENES: Final = (20_000, 50_000, 100_000)
_GASTOS_MEDICOS: Final = (2_000, 5_000, 10_000)
_DEDUCIBLE_COLISION: Final = (250, 500, 1_000)
_DEDUCIBLE_OTROS: Final = (100, 250, 500)

#: Cuantos conductores adicionales declara una poliza, ademas del titular: de ninguno a dos. La
#: de ejemplo declara al menos uno, para que la demostracion tenga un conductor declarado que
#: no sea el titular.
_MAXIMO_DE_ADICIONALES: Final = 2


class PolicyError(ValueError):
    """Una poliza no se puede componer: se dice cual y por que."""


@dataclass(frozen=True)
class ComposedPolicy:
    """Una poliza emitida y lo que el resto de la composicion necesita saber de ella."""

    record: IssuedPolicyRecord
    #: El idioma de la persona asegurada.
    language: Locale
    is_example: bool


def policy_path(tenant_id: str, policy_number: str) -> str:
    return f"tenants/{tenant_id}/issued_policies/{policy_number}.json"


def _emisoras(tenants: LoadedTenants) -> list[TenantConfig]:
    return sorted(
        (t for t in tenants.available if t.kind is TenantKind.CARRIER), key=lambda t: t.tenant_id
    )


def _emisora_por_idioma(
    emisoras: list[TenantConfig], idioma: Locale, *, igual: bool
) -> TenantConfig:
    """La primera emisora que escribe (o que no escribe) en ese idioma, o la primera."""
    for emisora in emisoras:
        if (emisora.default_language == idioma) == igual:
            return emisora
    return emisoras[0]


def _limites(chooser: ChooserFactory, ruta: str) -> dict[str, int]:
    """Los limites y deducibles de una poliza, de su propio flujo."""
    elegidor = chooser.for_output(ruta, purpose="limits")
    por_persona = elegidor.choice(_POR_PERSONA)
    return {
        "a.bodily_injury_per_person": por_persona,
        "a.bodily_injury_per_accident": por_persona * 2,
        "a.property_damage": elegidor.choice(_BIENES),
        "b.medical_payments_per_person": elegidor.choice(_GASTOS_MEDICOS),
        "c.uninsured_per_person": por_persona,
        "c.uninsured_per_accident": por_persona * 2,
        "d.collision_deductible": elegidor.choice(_DEDUCIBLE_COLISION),
        "d.other_than_collision_deductible": elegidor.choice(_DEDUCIBLE_OTROS),
    }


@dataclass(frozen=True)
class _Plan:
    """Una poliza por componer: su numero, su emisora y lo que viene impuesto."""

    number: str
    issuer: TenantConfig
    is_example: bool
    fixed: FixedPolicy | None


def _decena(numero: str) -> int:
    """La decena de un numero de poliza: `POL-23` y `POL-21` son de la 2, `POL-50` de la 5."""
    return int(numero.removeprefix("POL-")) // 10


def _planes(
    tenant: TenantConfig,
    emisoras: list[TenantConfig],
    fijas: tuple[FixedPolicy, ...],
    numeros_tomados: set[str],
) -> list[_Plan]:
    """Las polizas de una aseguradora: la de ejemplo, las de DS-8 y las generadas."""
    agencia = tenant.kind is TenantKind.AGENCY
    if agencia:
        de_ejemplo = _emisora_por_idioma(emisoras, tenant.default_language, igual=True)
        de_ds8 = _emisora_por_idioma(emisoras, tenant.default_language, igual=False)
    else:
        de_ejemplo = de_ds8 = tenant
    planes = [_Plan(tenant.example_policy, de_ejemplo, is_example=True, fixed=None)]
    planes.extend(
        _Plan(fija.policy_number, de_ds8, is_example=False, fixed=fija)
        for fija in fijas
        if fija.tenant_id == tenant.tenant_id
    )
    decena = _decena(tenant.example_policy)
    turno = 0
    siguiente = int(tenant.example_policy.removeprefix("POL-")) + 1
    while sum(1 for p in planes if _decena(p.number) == decena) < POLICIES_PER_TENANT:
        numero = f"POL-{siguiente}"
        if _decena(numero) != decena:
            msg = (
                f"la decena de '{tenant.tenant_id}' ({tenant.example_policy}) no alcanza para "
                f"{POLICIES_PER_TENANT} polizas: se acabo en {numero}"
            )
            raise PolicyError(msg)
        siguiente += 1
        # Un numero generado no repite ninguno del corpus: la unica colision de
        # numeros es la que DS-8 declara, y una segunda no la declararia nadie.
        if numero in numeros_tomados:
            continue
        numeros_tomados.add(numero)
        emisora = emisoras[turno % len(emisoras)] if agencia else tenant
        turno += 1
        planes.append(_Plan(numero, emisora, is_example=False, fixed=None))
    return planes


def compose_policies(
    tenants: LoadedTenants,
    issuers: dict[str, IssuerCorpus],
    roles: DS8Roles,
    seeding: tuple[ChooserFactory, People],
) -> dict[str, tuple[ComposedPolicy, ...]]:
    """Las polizas de cada aseguradora, por su identificador, en orden de numero."""
    chooser, people = seeding
    emisoras = _emisoras(tenants)
    fijas = fixed_policies(roles)
    ordenadas = sorted(tenants.available, key=lambda t: t.tenant_id)
    # Los numeros impuestos se reservan antes de generar ninguno: asi ningun numero
    # generado de una aseguradora cae, por azar, sobre el de ejemplo de otra.
    tomados = {t.example_policy for t in ordenadas} | {f.policy_number for f in fijas}
    resultado: dict[str, tuple[ComposedPolicy, ...]] = {}
    for tenant in ordenadas:
        compuestas: list[ComposedPolicy] = []
        for plan in _planes(tenant, emisoras, fijas, tomados):
            corpus = issuers.get(plan.issuer.tenant_id)
            base = corpus.current_base if corpus is not None else None
            if corpus is None or base is None:
                msg = (
                    f"'{plan.number}' de '{tenant.tenant_id}': su emisora "
                    f"'{plan.issuer.tenant_id}' no tiene formulario base vigente"
                )
                raise PolicyError(msg)
            ruta = policy_path(tenant.tenant_id, plan.number)
            elegidor = chooser.for_output(ruta)
            idioma = plan.issuer.default_language
            persona = compose_persona(
                elegidor,
                people,
                idioma,
                persona_id=f"{tenant.case_number_prefix.lower()}-per-{plan.number[4:]}",
                full_name=plan.fixed.insured_name if plan.fixed is not None else None,
            )
            vehiculos = tuple(
                compose_vehicle(elegidor, people, idioma) for _ in range(elegidor.between(1, 2))
            )
            endosos = corpus.endorsement_ids
            if not plan.is_example:
                elegidos = set(elegidor.sample(endosos, elegidor.between(0, len(endosos))))
                endosos = tuple(e for e in endosos if e in elegidos)
            if plan.fixed is not None:
                inicio, fin = plan.fixed.effective_from, plan.fixed.effective_to
            else:
                inicio = _PRIMER_INICIO + timedelta(days=elegidor.between(0, _DIAS_DE_INICIO))
                fin = inicio.replace(year=inicio.year + 1)
            registro = IssuedPolicyRecord(
                policy_number=plan.number,
                tenant_id=tenant.tenant_id,
                issuer_tenant=plan.issuer.tenant_id,
                form_id=base.form_id,
                form_version=base.form_version,
                endorsement_ids=endosos,
                period_start=inicio,
                period_end=fin,
                named_insured=persona,
                vehicles=vehiculos,
                limits_and_deductibles=_limites(chooser, ruta),
            )
            compuestas.append(ComposedPolicy(registro, language=idioma, is_example=plan.is_example))
        resultado[tenant.tenant_id] = tuple(
            sorted(compuestas, key=lambda p: p.record.policy_number)
        )
    return resultado


def declare_drivers(
    policies: dict[str, tuple[ComposedPolicy, ...]], seeding: tuple[ChooserFactory, People]
) -> dict[str, tuple[ComposedPolicy, ...]]:
    """Los conductores que declara cada poliza: el titular y de ninguno a dos familiares.

    **Se compone aparte de `compose_policies` y despues de los casos, y no es una comodidad.**
    Dos razones, las dos de no mover nada de lo ya sembrado:

    - Cada poliza saca sus conductores de **su propio flujo** (`purpose="drivers"`), asi que
      ninguna eleccion de la poliza --numero, vehiculos, endosos, vigencia, limites-- cambia
      por declarar conductores. Anadirlos al flujo principal habria corrido todo lo que sigue.
    - Los nombres se reservan en `UsedValues` para que nadie mas los lleve. Reservarlos antes
      de los casos habria podido desplazar a un nombre ya sembrado; despues, nada que se
      componga a continuacion los usa.

    El titular va primero y es el nombre de la persona asegurada, tal cual. Los demas son
    familiares: llevan los apellidos de la casa y un nombre de pila que ningun conductor de la
    poliza lleva, que es lo que la comparacion de nombres de `orchestration.triage_inputs`
    necesita para distinguir a un familiar del titular.
    """
    chooser, people = seeding
    resultado: dict[str, tuple[ComposedPolicy, ...]] = {}
    for tenant_id in sorted(policies):
        declaradas: list[ComposedPolicy] = []
        for poliza in policies[tenant_id]:
            registro = poliza.record
            ruta = policy_path(tenant_id, registro.policy_number)
            elegidor = chooser.for_output(ruta, purpose="drivers")
            nombres = [registro.named_insured.full_name]
            de_pila = {nombres[0].split()[0].casefold()}
            minimo = 1 if poliza.is_example else 0
            for _ in range(elegidor.between(minimo, _MAXIMO_DE_ADICIONALES)):
                familiar = compose_relative_name(
                    elegidor,
                    people,
                    poliza.language,
                    holder_name=nombres[0],
                    taken_given_names=frozenset(de_pila),
                )
                nombres.append(familiar)
                de_pila.add(familiar.split()[0].casefold())
            declaradas.append(
                replace(
                    poliza,
                    record=registro.evolve(drivers=tuple(DriverRef(full_name=n) for n in nombres)),
                )
            )
        resultado[tenant_id] = tuple(declaradas)
    return resultado
