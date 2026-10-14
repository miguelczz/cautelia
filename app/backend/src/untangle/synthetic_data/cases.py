"""Los casos sembrados, uno por fuente de turnos (F3.2, paso 6; BR6.1, BR6.2).

Cada caso sale de una entrada `case_turns` escrita a mano (FD-U7-7): su estado,
sus campos, los criterios que parten de el y sus turnos. La composicion le asigna
una poliza emitida de su aseguradora --la de ejemplo si la fuente lo pide, una del
idioma pedido si lo pide, o cualquiera elegida con la semilla del caso-- y llena
los marcadores con la persona y el vehiculo de esa poliza.

## Los marcadores

Los datos personales de un caso nunca se escriben en la fuente: se escriben como
marcador y los llena la composicion, para que todos salgan del conjunto sembrado
y esten en la lista de valores personales (BR7.2):

- de la persona asegurada: `{insured_name}`, `{insured_first_name}`, `{phone}`,
  `{phone_spoken}`, `{national_id}`, `{national_id_spoken}`, `{email}`;
- de la poliza: `{policy_number}`, `{plate}`, `{vehicle}`, `{vin}`, `{insurer}`
  (la aseguradora del caso) e `{issuer}` (la que emitio la poliza);
- de otras personas del accidente: `{other_name_1}` a `{other_name_4}` y
  `{other_plate_1}`, `{other_plate_2}`, compuestos en el idioma del caso.

`*_spoken` dice los digitos uno a uno **en el idioma de la persona**, que es como
se dicta un documento por telefono y lo que RT-15 necesita. Un marcador que no
esta en esta lista detiene la generacion nombrando el caso.

## Lo que se valida sobre el conjunto

- **BR6.1**: hay al menos un caso en cada estado, en cada aseguradora y en cada
  idioma, y un cerrado con cada resolucion. `sent_to_insurer` solo en una agencia,
  y una agencia solo cierra asi, porque nunca decide cobertura (D18). `registered`
  solo donde las reglas de la aseguradora tienen alguna de cierre directo: en vivo
  es la unica forma de cerrar sin ajustador, y una aseguradora sin esa regla no
  puede tener un ejemplo asi (se lee de su configuracion, no de una lista).
- **BR6.2**: cada criterio de `seeded_criteria.yaml` tiene al menos un caso, y
  cada criterio que un caso nombra esta en esa lista. La lista crece con cada
  unidad, asi que esta validacion no fija cuantos criterios hay.
"""

from __future__ import annotations

import string
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from untangle.base import Locale
from untangle.synthetic_data.chooser import ChooserFactory, SeededChooser
from untangle.synthetic_data.models import (
    PersonalValue,
    PersonalValueKind,
    SeededCaseRecord,
    SeededCaseRef,
    SeededCaseSpec,
    SeededCriteriaFile,
    SeededField,
    SeededResolution,
    SeededState,
    SourceKind,
    SourceText,
    parse_turns,
)
from untangle.synthetic_data.people import (
    People,
    compose_plate,
    compose_unique_name,
    spoken_digits,
)
from untangle.synthetic_data.policies import ComposedPolicy
from untangle.tenancy.config import RULES_DIR, LoadedTenants, load_ruleset
from untangle.tenancy.models import TenantConfig, TenantKind

__all__ = [
    "DIRECT_CLOSE",
    "PLACEHOLDERS",
    "CaseComposition",
    "ComposedCase",
    "SeededCaseLoadError",
    "case_path",
    "check_coverage",
    "check_criteria",
    "compose_cases",
    "direct_close_tenants",
    "load_seeded_cases",
]

#: Los marcadores de la persona y de la poliza del caso.
_DE_LA_POLIZA: Final = frozenset(
    {
        "insured_name",
        "insured_first_name",
        "phone",
        "phone_spoken",
        "national_id",
        "national_id_spoken",
        "email",
        "policy_number",
        "plate",
        "vehicle",
        "vin",
        "insurer",
        "issuer",
    }
)
#: Los de otras personas del accidente, compuestos para cada caso.
_NOMBRES_DE_OTROS: Final = ("other_name_1", "other_name_2", "other_name_3", "other_name_4")
_PLACAS_DE_OTROS: Final = ("other_plate_1", "other_plate_2")

#: Todos los marcadores que puede llevar una fuente de turnos.
PLACEHOLDERS: Final = _DE_LA_POLIZA | set(_NOMBRES_DE_OTROS) | set(_PLACAS_DE_OTROS)

#: Las resoluciones que solo una agencia usa, y las que solo una emisora usa.
_SOLO_DE_AGENCIA: Final = frozenset({SeededResolution.SENT_TO_INSURER})

#: La categoria de una regla que cierra el caso sin ajustador (`rules.models.CATEGORIES`). Se copia
#: porque el generador no puede importar `untangle.rules` (mismo nivel en el contrato de capas);
#: una prueba compara las dos para que no se separen.
DIRECT_CLOSE: Final = "direct_close"


def case_path(tenant_id: str, language: Locale, name: str) -> str:
    """`tenants/<aseguradora>/cases/<idioma>/<nombre>.json`."""
    return f"tenants/{tenant_id}/cases/{language}/{name}.json"


class SeededCaseLoadError(ValueError):
    """Un caso sembrado escrito no se pudo leer. El mensaje nombra el archivo."""


def load_seeded_cases(data_dir: Path) -> tuple[SeededCaseRecord, ...]:
    """Los casos sembrados que la generacion dejo escritos, ordenados por su clave.

    Los lee la siembra (`untangle.server.synthetic_seed`), que los carga por la
    API de U4. Leen lo escrito y versionado, no lo que produciria una generacion
    nueva: lo que se siembra es lo que se reviso en el diff.
    """
    casos: list[SeededCaseRecord] = []
    # El mismo esquema de `case_path`, con comodines en sus tres partes.
    for archivo in sorted(data_dir.glob("tenants/*/cases/*/*.json")):
        try:
            casos.append(SeededCaseRecord.model_validate_json(archivo.read_bytes()))
        except (OSError, ValidationError) as error:
            msg = f"el caso sembrado '{archivo}' no se pudo leer: {error}"
            raise SeededCaseLoadError(msg) from error
    return tuple(sorted(casos, key=lambda caso: caso.case_key))


@dataclass(frozen=True)
class ComposedCase:
    """Un caso sembrado compuesto, con su ruta y los valores de terceros que sembro."""

    path: str
    record: SeededCaseRecord
    others: tuple[PersonalValue, ...]


@dataclass(frozen=True)
class CaseComposition:
    cases: tuple[ComposedCase, ...]
    problems: tuple[str, ...]

    def refs(self, prefix: str) -> tuple[SeededCaseRef, ...]:
        """Lo que el manifiesto lista de cada caso (BR6.2)."""
        return tuple(
            SeededCaseRef(
                case_key=c.record.case_key, path=f"{prefix}{c.path}", used_by=c.record.used_by
            )
            for c in self.cases
        )


def _marcadores(texto: str) -> set[str]:
    return {nombre for _, nombre, _, _ in string.Formatter().parse(texto) if nombre is not None}


def _poliza_del_caso(
    spec: SeededCaseSpec, polizas: Sequence[ComposedPolicy], elegidor: SeededChooser, donde: str
) -> ComposedPolicy:
    if spec.example_policy:
        candidatas = [p for p in polizas if p.is_example]
    elif spec.persona_language is not None:
        candidatas = [p for p in polizas if p.language == spec.persona_language]
    else:
        candidatas = list(polizas)
    if not candidatas:
        msg = f"'{donde}': su aseguradora no tiene ninguna poliza que cumpla lo que pide el caso"
        raise ValueError(msg)
    return elegidor.choice(candidatas)


def _valores(
    poliza: ComposedPolicy,
    tenant: TenantConfig,
    tenants: LoadedTenants,
    usados: set[str],
    contexto: tuple[SeededChooser, People, Locale],
) -> tuple[dict[str, str], list[PersonalValue]]:
    """Los valores de los marcadores que usa el caso, y los de terceros que sembro."""
    elegidor, people, idioma = contexto
    registro_poliza = poliza.record
    persona = registro_poliza.named_insured
    vehiculo = registro_poliza.vehicles[0]
    emisora = tenants.get(registro_poliza.issuer_tenant)
    valores = {
        "insured_name": persona.full_name,
        "insured_first_name": persona.full_name.split()[0],
        "phone": persona.phone,
        "phone_spoken": spoken_digits(persona.phone, poliza.language),
        "national_id": persona.national_id,
        "national_id_spoken": spoken_digits(persona.national_id, poliza.language),
        "email": persona.email,
        "policy_number": registro_poliza.policy_number,
        "plate": vehiculo.plate,
        "vehicle": vehiculo.make_model_year,
        "vin": vehiculo.vin,
        "insurer": tenant.display_name,
        "issuer": emisora.display_name if emisora is not None else tenant.display_name,
    }
    terceros: list[PersonalValue] = []
    for nombre in _NOMBRES_DE_OTROS:
        if nombre in usados:
            valor = compose_unique_name(elegidor, people, idioma)
            valores[nombre] = valor
            terceros.append(
                PersonalValue(kind=PersonalValueKind.NAME, language=idioma, value=valor)
            )
    for nombre in _PLACAS_DE_OTROS:
        if nombre in usados:
            valor = compose_plate(elegidor, idioma, used=people.used)
            valores[nombre] = valor
            terceros.append(
                PersonalValue(kind=PersonalValueKind.PLATE, language=idioma, value=valor)
            )
    return valores, terceros


def _componer_uno(
    texto: SourceText,
    polizas: Sequence[ComposedPolicy],
    tenants: LoadedTenants,
    seeding: tuple[ChooserFactory, People],
) -> ComposedCase:
    spec = texto.case
    if spec is None:  # el modelo ya lo exige a todo `case_turns`
        msg = f"'{texto.source_id}': los turnos de un caso llevan su caso"
        raise ValueError(msg)
    tenant = tenants.get(texto.tenant_id)
    if tenant is None:
        msg = f"'{texto.source_id}': la aseguradora '{texto.tenant_id}' no esta cargada"
        raise ValueError(msg)
    ruta = case_path(texto.tenant_id, texto.language, spec.name)
    usados = _marcadores(texto.text)
    for campo in spec.fields.values():
        usados |= _marcadores(campo.value)
    desconocidos = sorted(usados - PLACEHOLDERS)
    if desconocidos:
        msg = (
            f"'{texto.source_id}': marcadores desconocidos {', '.join(desconocidos)}; los validos "
            f"son {', '.join(sorted(PLACEHOLDERS))}"
        )
        raise ValueError(msg)
    chooser, people = seeding
    elegidor = chooser.for_output(ruta)
    poliza = _poliza_del_caso(spec, polizas, elegidor, texto.source_id)
    valores, terceros = _valores(
        poliza, tenant, tenants, usados, (elegidor, people, texto.language)
    )
    registro = SeededCaseRecord(
        case_key=f"SEED/{texto.tenant_id}/{texto.language}/{spec.name}",
        tenant_id=texto.tenant_id,
        language=texto.language,
        record_type=spec.record_type,
        channel=spec.channel,
        state=spec.state,
        resolution=spec.resolution,
        derivation_reason=spec.derivation_reason,
        policy_number=poliza.record.policy_number,
        fields={
            clave: SeededField(value=campo.value.format_map(valores), status=campo.status)
            for clave, campo in sorted(spec.fields.items())
        },
        transcript=parse_turns(texto.text.format_map(valores), where=texto.source_id),
        used_by=tuple(sorted(spec.used_by)),
    )
    return ComposedCase(path=ruta, record=registro, others=tuple(terceros))


def compose_cases(
    texts: Sequence[SourceText],
    policies: Mapping[str, tuple[ComposedPolicy, ...]],
    tenants: LoadedTenants,
    seeding: tuple[ChooserFactory, People],
) -> CaseComposition:
    """Un caso por fuente de turnos, en orden de clave, con lo que no cuadro."""
    casos: list[ComposedCase] = []
    problemas: list[str] = []
    fuentes = sorted(
        (t for t in texts if t.kind is SourceKind.CASE_TURNS),
        key=lambda t: (t.tenant_id, t.language, t.source_id),
    )
    claves: dict[str, str] = {}
    for texto in fuentes:
        nombre = texto.case.name if texto.case is not None else texto.source_id
        clave = f"{texto.tenant_id}/{texto.language}/{nombre}"
        if clave in claves:
            problemas.append(
                f"'{texto.source_id}': el caso '{nombre}' ya lo define '{claves[clave]}' en la "
                "misma aseguradora e idioma (BR6.2)"
            )
            continue
        claves[clave] = texto.source_id
        try:
            casos.append(_componer_uno(texto, policies.get(texto.tenant_id, ()), tenants, seeding))
        except (ValueError, KeyError) as error:
            problemas.append(str(error))
    return CaseComposition(
        cases=tuple(sorted(casos, key=lambda c: c.record.case_key)), problems=tuple(problemas)
    )


def direct_close_tenants(tenants_dir: Path, tenants: LoadedTenants) -> frozenset[str]:
    """Las aseguradoras cuyas reglas tienen alguna de cierre directo, leido de su configuracion.

    Sin lista y sin rama por aseguradora (convencion 9): lo dice la carpeta `rules/` de cada una.
    Los archivos ya los valido `tenancy.config.load` al cargar las aseguradoras, asi que aqui no
    puede fallar su forma.
    """
    cierran: set[str] = set()
    for tenant in tenants.available:
        for archivo in sorted((tenants_dir / tenant.tenant_id / RULES_DIR).glob("*.yaml")):
            if any(
                regla.then.get("category") == DIRECT_CLOSE for regla in load_ruleset(archivo).rules
            ):
                cierran.add(tenant.tenant_id)
    return frozenset(cierran)


def _resolucion_fuera_de_su_sitio(
    caso: SeededCaseRecord, tipos: Mapping[str, TenantKind], closes_directly: frozenset[str]
) -> str | None:
    """Por que la resolucion de un caso cerrado no cabe en su aseguradora, o nada si cabe."""
    if caso.resolution is None:
        return None
    de_agencia = tipos.get(caso.tenant_id) is TenantKind.AGENCY
    if de_agencia != (caso.resolution in _SOLO_DE_AGENCIA):
        quien = "una agencia" if de_agencia else "una emisora"
        return (
            f"'{caso.case_key}': {quien} no cierra un caso como '{caso.resolution.value}': "
            "la agencia solo envia a la aseguradora, y solo la agencia lo hace (D18)"
        )
    if caso.resolution is SeededResolution.REGISTERED and caso.tenant_id not in closes_directly:
        return (
            f"'{caso.case_key}': se cierra como 'registered', sin ajustador, y las reglas de "
            f"'{caso.tenant_id}' no tienen ninguna de cierre directo ('{DIRECT_CLOSE}'): en "
            "vivo un caso suyo nunca se cierra solo. Su ejemplo cerrado pasa por un ajustador "
            "(derivation_reason: rule y una resolucion de persona) (BR6.1)"
        )
    return None


def check_coverage(
    cases: Sequence[SeededCaseRecord], tenants: LoadedTenants, closes_directly: frozenset[str]
) -> list[str]:
    """BR6.1: cada estado en cada aseguradora e idioma, y cada resolucion en su sitio."""
    problemas: list[str] = []
    presentes = {(c.tenant_id, c.language, c.state) for c in cases}
    idiomas: tuple[Locale, ...] = ("es", "en")
    for tenant in sorted(tenants.available, key=lambda t: t.tenant_id):
        for idioma in idiomas:
            for estado in SeededState:
                if (tenant.tenant_id, idioma, estado) not in presentes:
                    problemas.append(
                        f"falta un caso sembrado en '{estado.value}' de '{tenant.tenant_id}' en "
                        f"'{idioma}' (BR6.1)"
                    )
    tipos = {t.tenant_id: t.kind for t in tenants.available}
    for caso in cases:
        fuera = _resolucion_fuera_de_su_sitio(caso, tipos, closes_directly)
        if fuera is not None:
            problemas.append(fuera)
    for resolucion in SeededResolution:
        if not any(c.resolution is resolucion for c in cases):
            problemas.append(f"falta un caso cerrado con resolucion '{resolucion.value}' (BR6.1)")
    return problemas


def check_criteria(
    cases: Sequence[SeededCaseRecord], criteria: SeededCriteriaFile | None
) -> list[str]:
    """BR6.2: cada criterio declarado tiene su caso, y cada caso nombra solo criterios declarados."""
    nombrados = {ac for c in cases for ac in c.used_by}
    if criteria is None:
        if nombrados:
            return [
                "los casos nombran criterios y falta app/data/sources/seeded_criteria.yaml, "
                "que dice cuales parten de un caso sembrado (BR6.2)"
            ]
        return []
    declarados = {c.ac_id for c in criteria.criteria}
    problemas = [
        f"el criterio {ac} parte de un caso sembrado y ningun caso lo nombra en used_by (BR6.2)"
        for ac in sorted(declarados - nombrados)
    ]
    problemas.extend(
        f"un caso nombra el criterio {ac}, que no esta en seeded_criteria.yaml (BR6.2)"
        for ac in sorted(nombrados - declarados)
    )
    return problemas
