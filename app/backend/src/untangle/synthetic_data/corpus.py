"""El corpus de cada emisora y las copias de la agencia (F3.2, pasos 1 a 3).

Compone, desde los textos fuente revisados, lo que ingiere U8 (C-26):

- **Formularios y clausulas** (BR3.1 a BR3.3): el formulario base de la edicion
  vigente con todas las partes de la referencia, un formulario por endoso, el
  documento de jurisdiccion y la **edicion anterior**, que solo guarda los
  distractores. Cada clausula se llama `<formulario>-<numeracion>` (BR3.2).
- **Distractores** (BR3.4): viven en la edicion anterior (`<prefijo>-PAP-2025`),
  que ninguna poliza emitida usa. Asi una version reemplazada y un casi-duplicado
  quedan indexables sin estar vigentes: citarlos es el error que DS-3 mide.
- **Relaciones** (BR3.5, ADR-010): `endorsement_modifies` sale de la numeracion
  del endoso, que es la del elemento que modifica; `defines`, de los terminos que
  declara cada definicion; `refers_to`, de las remisiones que declara la fuente.
- **Copias de la agencia** (BR4.1, BR4.2): cada formulario y cada archivo de
  clausulas de cada emisora se copia **byte a byte** al espacio de la agencia, con
  su emisora escrita en `issuer_tenant` e `issuer_label`.
- **Diferencias declaradas** (BR3.7): se comprueban contra lo compuesto.

Nada de esto nombra una aseguradora: las emisoras y las agencias salen de la
configuracion por su tipo, y cada formulario sabe de quien es por su prefijo.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Final

from pydantic import BaseModel

from untangle.synthetic_data.models import (
    JURISDICTION_FAMILY,
    ClauseFile,
    ClauseRecord,
    ClauseRelationFile,
    ClauseRelationRecord,
    DeclaredDifference,
    DifferenceFile,
    FormKind,
    FormRecord,
    PolicyPart,
    RelationKind,
    SourceKind,
)
from untangle.synthetic_data.sources import LoadedSourceFile, SourceBundle
from untangle.tenancy.config import LoadedTenants
from untangle.tenancy.models import TenantConfig, TenantKind

__all__ = [
    "BASE_PARTS",
    "MIN_ENDORSEMENTS",
    "CorpusResult",
    "IssuerCorpus",
    "check_differences",
    "clause_path",
    "compose_corpus_texts",
    "form_path",
    "relations_path",
]

#: Las partes que todo formulario base vigente tiene, con al menos una clausula
#: cada una (BR3.1): el acuerdo, las definiciones y las partes A a F.
BASE_PARTS: Final = (
    PolicyPart.AGREEMENT,
    PolicyPart.DEFINITIONS,
    PolicyPart.PART_A,
    PolicyPart.PART_B,
    PolicyPart.PART_C,
    PolicyPart.PART_D,
    PolicyPart.PART_E,
    PolicyPart.PART_F,
)

#: El minimo de endosos por emisora (BR3.3). Se construyen cinco.
MIN_ENDORSEMENTS: Final = 4

#: El orden en que las partes aparecen en un formulario: el de la referencia.
_ORDEN_DE_PARTES: Final = {parte.value: indice for indice, parte in enumerate(PolicyPart)}


def form_path(tenant_id: str, form_id: str) -> str:
    return f"tenants/{tenant_id}/forms/{form_id}.json"


def clause_path(tenant_id: str, form_id: str) -> str:
    return f"tenants/{tenant_id}/clauses/{form_id}.json"


def relations_path(tenant_id: str) -> str:
    return f"tenants/{tenant_id}/clause_relations.json"


@dataclass
class IssuerCorpus:
    """Lo que una emisora publica: sus formularios, sus clausulas y sus relaciones."""

    tenant: TenantConfig
    forms: dict[str, FormRecord] = field(default_factory=dict)
    clauses: dict[str, tuple[ClauseRecord, ...]] = field(default_factory=dict)
    relations: tuple[ClauseRelationRecord, ...] = ()
    #: La parte de la referencia de cada clausula, por su identificador.
    part_of: dict[str, str] = field(default_factory=dict)

    @property
    def current_base(self) -> FormRecord | None:
        """El formulario base de la edicion vigente: la mas reciente con clausulas propias."""
        vigentes = [
            f
            for f in self.forms.values()
            if f.form_kind is FormKind.BASE
            and any(not c.is_distractor for c in self.clauses[f.form_id])
        ]
        return max(vigentes, key=lambda f: f.form_id) if vigentes else None

    @property
    def endorsement_ids(self) -> tuple[str, ...]:
        base = self.current_base
        if base is None:
            return ()
        return tuple(
            sorted(
                (f for f in self.forms if f.startswith(f"{base.form_id}-END-")),
                key=lambda f: int(f.rsplit("-", 1)[1]),
            )
        )

    def all_clause_ids(self) -> set[str]:
        return {c.clause_id for grupo in self.clauses.values() for c in grupo}


@dataclass(frozen=True)
class CorpusResult:
    """El corpus compuesto: una entrada por emisora, las salidas y lo que no cuadro."""

    issuers: dict[str, IssuerCorpus]
    outputs: dict[str, BaseModel]
    problems: tuple[str, ...]


def _familia(form_id: str) -> str:
    return form_id.split("-")[1]


def _tipo_de_formulario(form_id: str) -> FormKind:
    if "-END-" in form_id:
        return FormKind.ENDORSEMENT
    if _familia(form_id) == JURISDICTION_FAMILY:
        return FormKind.JURISDICTION
    return FormKind.BASE


def _archivos_de(sources: SourceBundle, tenant_id: str) -> list[LoadedSourceFile]:
    """Los archivos de una emisora en el orden de la referencia: acuerdo, definiciones..."""
    return sorted(
        (f for f in sources.files if f.header.tenant_id == tenant_id),
        key=lambda f: (f.header.language, _ORDEN_DE_PARTES.get(str(f.header.part_key), 99)),
    )


def _clausulas(corpus: IssuerCorpus, sources: SourceBundle, problemas: list[str]) -> None:
    """Agrupa los textos de formulario de la emisora por su formulario, en orden."""
    por_formulario: dict[str, list[ClauseRecord]] = defaultdict(list)
    tipos_de_formulario = {
        SourceKind.CLAUSE,
        SourceKind.ENDORSEMENT,
        SourceKind.JURISDICTION,
        SourceKind.DISTRACTOR,
    }
    for archivo in _archivos_de(sources, corpus.tenant.tenant_id):
        for texto in archivo.texts:
            # El modelo ya exige numeracion y parte a todo texto de formulario; la
            # guarda solo se lo dice al comprobador de tipos.
            if (
                texto.kind not in tipos_de_formulario
                or texto.form_id is None
                or texto.clause_key is None
                or texto.part is None
            ):
                continue
            corpus.part_of[texto.source_id] = str(archivo.header.part_key)
            por_formulario[texto.form_id].append(
                ClauseRecord(
                    clause_id=texto.source_id,
                    form_id=texto.form_id,
                    form_version=texto.version,
                    clause_key=texto.clause_key,
                    part=texto.part,
                    language=texto.language,
                    text=texto.text,
                    is_distractor=texto.kind is SourceKind.DISTRACTOR,
                    issuer_label=corpus.tenant.display_name,
                )
            )
    for form_id, clausulas in sorted(por_formulario.items()):
        versiones = sorted({c.form_version for c in clausulas})
        if len(versiones) > 1:
            problemas.append(
                f"'{form_id}': sus clausulas traen versiones distintas ({', '.join(versiones)}); "
                "un formulario tiene una sola version (BR3.2)"
            )
        idiomas = sorted({c.language for c in clausulas})
        if len(idiomas) > 1:
            problemas.append(f"'{form_id}': sus clausulas estan en mas de un idioma")
        corpus.clauses[form_id] = tuple(clausulas)


def _formularios(corpus: IssuerCorpus, problemas: list[str]) -> None:
    """Un `FormRecord` por formulario, con la jurisdiccion en los base."""
    jurisdicciones = sorted(f for f in corpus.clauses if _familia(f) == JURISDICTION_FAMILY)
    for form_id, clausulas in corpus.clauses.items():
        tipo = _tipo_de_formulario(form_id)
        referencia = None
        if tipo is FormKind.BASE:
            if not jurisdicciones:
                problemas.append(
                    f"'{form_id}': la emisora '{corpus.tenant.tenant_id}' no tiene documento de "
                    "jurisdiccion, y todo formulario base lo referencia (BR3.1)"
                )
                continue
            referencia = jurisdicciones[-1]
        corpus.forms[form_id] = FormRecord(
            form_id=form_id,
            form_kind=tipo,
            form_version=clausulas[0].form_version,
            issuer_tenant=corpus.tenant.tenant_id,
            issuer_label=corpus.tenant.display_name,
            language=clausulas[0].language,
            jurisdiction_ref=referencia,
            clause_ids=tuple(c.clause_id for c in clausulas),
        )


def _estructura(corpus: IssuerCorpus, problemas: list[str]) -> None:
    """BR3.1, BR3.3 y BR3.4 sobre la emisora ya agrupada."""
    donde = corpus.tenant.tenant_id
    base = corpus.current_base
    if base is None:
        problemas.append(f"'{donde}': no tiene formulario base vigente (BR3.1)")
        return
    presentes = {
        corpus.part_of[c.clause_id] for c in corpus.clauses[base.form_id] if not c.is_distractor
    }
    faltan = [p.value for p in BASE_PARTS if p.value not in presentes]
    if faltan:
        problemas.append(
            f"'{base.form_id}': le faltan partes de la referencia: {', '.join(faltan)}"
        )
    if len(corpus.endorsement_ids) < MIN_ENDORSEMENTS:
        problemas.append(
            f"'{donde}': tiene {len(corpus.endorsement_ids)} endoso(s) y el minimo es "
            f"{MIN_ENDORSEMENTS} (BR3.3)"
        )
    for grupo in corpus.clauses.values():
        for clausula in grupo:
            if clausula.is_distractor and clausula.form_id == base.form_id:
                problemas.append(
                    f"'{clausula.clause_id}': un distractor vive en la edicion anterior, no en "
                    "el formulario vigente que usan las polizas (BR3.4)"
                )


def _destinos_de_distractores(
    corpus: IssuerCorpus, sources: SourceBundle, problemas: list[str]
) -> None:
    """BR3.4: cada distractor se confunde con una clausula vigente de su emisora."""
    base = corpus.current_base
    vigentes = {c.clause_id for c in corpus.clauses[base.form_id]} if base is not None else set()
    for texto in sources.texts:
        if texto.tenant_id != corpus.tenant.tenant_id or texto.kind is not SourceKind.DISTRACTOR:
            continue
        if texto.distractor_of not in vigentes:
            problemas.append(
                f"'{texto.source_id}': se confunde con '{texto.distractor_of}', que no es una "
                "clausula del formulario vigente de su emisora (BR3.4)"
            )


def _terminos(texto: str, terminos: Iterable[str]) -> bool:
    return any(
        re.search(rf"(?<!\w){re.escape(t)}(?!\w)", texto, flags=re.IGNORECASE) for t in terminos
    )


def _modificaciones(
    corpus: IssuerCorpus, base: FormRecord, problemas: list[str]
) -> set[tuple[str, RelationKind, str]]:
    """`endorsement_modifies`: la numeracion del endoso es la del elemento que modifica."""
    existentes = corpus.all_clause_ids()
    relaciones: set[tuple[str, RelationKind, str]] = set()
    for endoso in corpus.endorsement_ids:
        for clausula in corpus.clauses[endoso]:
            destino = f"{base.form_id}-{clausula.clause_key}"
            if destino not in existentes:
                problemas.append(
                    f"'{clausula.clause_id}': modifica '{clausula.clause_key}', que no esta en "
                    f"'{base.form_id}' (BR3.5)"
                )
                continue
            relaciones.add((clausula.clause_id, RelationKind.ENDORSEMENT_MODIFIES, destino))
    return relaciones


def _definiciones_y_remisiones(
    corpus: IssuerCorpus, base: FormRecord, sources: SourceBundle, problemas: list[str]
) -> set[tuple[str, RelationKind, str]]:
    """`defines` desde los terminos de cada definicion y `refers_to` desde la fuente."""
    vigentes = [
        c for form_id in (base.form_id, *corpus.endorsement_ids) for c in corpus.clauses[form_id]
    ]
    vigentes_ids = {c.clause_id for c in vigentes} | {
        c.clause_id
        for form_id, grupo in corpus.clauses.items()
        if corpus.forms[form_id].form_kind is FormKind.JURISDICTION
        for c in grupo
    }
    relaciones: set[tuple[str, RelationKind, str]] = set()
    for texto in sources.texts:
        if texto.tenant_id != corpus.tenant.tenant_id:
            continue
        relaciones |= {
            (texto.source_id, RelationKind.DEFINES, clausula.clause_id)
            for clausula in vigentes
            if texto.defines_terms
            and clausula.clause_id != texto.source_id
            and _terminos(clausula.text, texto.defines_terms)
        }
        for destino in texto.refers_to:
            if destino not in vigentes_ids:
                problemas.append(
                    f"'{texto.source_id}': remite a '{destino}', que no es una clausula vigente "
                    f"de '{corpus.tenant.tenant_id}' (BR3.5)"
                )
                continue
            relaciones.add((texto.source_id, RelationKind.REFERS_TO, destino))
    return relaciones


def _relaciones(corpus: IssuerCorpus, sources: SourceBundle, problemas: list[str]) -> None:
    """Las tres relaciones de ADR-010, con sus dos extremos en el espacio de la emisora."""
    base = corpus.current_base
    if base is None:
        return
    relaciones = _modificaciones(corpus, base, problemas)
    relaciones |= _definiciones_y_remisiones(corpus, base, sources, problemas)
    corpus.relations = tuple(
        ClauseRelationRecord(from_clause=origen, to_clause=destino, relation=tipo)
        for origen, tipo, destino in sorted(relaciones, key=lambda r: (r[0], r[1].value, r[2]))
    )


def _salidas_de(tenant_id: str, corpus: IssuerCorpus) -> dict[str, BaseModel]:
    salidas: dict[str, BaseModel] = {}
    for form_id, formulario in sorted(corpus.forms.items()):
        salidas[form_path(tenant_id, form_id)] = formulario
        salidas[clause_path(tenant_id, form_id)] = ClauseFile(
            form_id=form_id, clauses=corpus.clauses[form_id]
        )
    return salidas


def compose_corpus_texts(sources: SourceBundle, tenants: LoadedTenants) -> CorpusResult:
    """El corpus de las emisoras, las copias de las agencias y sus relaciones."""
    problemas: list[str] = []
    emisoras = sorted(
        (t for t in tenants.available if t.kind is TenantKind.CARRIER), key=lambda t: t.tenant_id
    )
    agencias = sorted(
        (t for t in tenants.available if t.kind is TenantKind.AGENCY), key=lambda t: t.tenant_id
    )
    corpus: dict[str, IssuerCorpus] = {}
    salidas: dict[str, BaseModel] = {}
    for emisora in emisoras:
        uno = IssuerCorpus(tenant=emisora)
        _clausulas(uno, sources, problemas)
        if not uno.clauses:
            problemas.append(f"'{emisora.tenant_id}': es una emisora y no tiene textos fuente")
            continue
        _formularios(uno, problemas)
        _estructura(uno, problemas)
        _destinos_de_distractores(uno, sources, problemas)
        _relaciones(uno, sources, problemas)
        corpus[emisora.tenant_id] = uno
        salidas.update(_salidas_de(emisora.tenant_id, uno))
        salidas[relations_path(emisora.tenant_id)] = ClauseRelationFile(
            tenant_id=emisora.tenant_id, relations=uno.relations
        )

    # Las copias de cada agencia salen de lo recien compuesto, en esta misma
    # generacion, y nunca de un texto propio (BR4.2).
    for agencia in agencias:
        relaciones: list[ClauseRelationRecord] = []
        for emisora_id, uno in sorted(corpus.items()):
            for ruta, documento in _salidas_de(emisora_id, uno).items():
                salidas[
                    ruta.replace(f"tenants/{emisora_id}/", f"tenants/{agencia.tenant_id}/", 1)
                ] = documento
            relaciones.extend(uno.relations)
        salidas[relations_path(agencia.tenant_id)] = ClauseRelationFile(
            tenant_id=agencia.tenant_id,
            relations=tuple(
                sorted(relaciones, key=lambda r: (r.from_clause, r.relation.value, r.to_clause))
            ),
        )
    return CorpusResult(issuers=corpus, outputs=salidas, problems=tuple(problemas))


def check_differences(
    differences: DifferenceFile | None, issuers: Mapping[str, IssuerCorpus]
) -> tuple[tuple[DeclaredDifference, ...], list[str]]:
    """Las diferencias declaradas, comprobadas contra el corpus (BR3.7).

    Cada formulario de `present_in` tiene una clausula con la numeracion de la
    diferencia, y ninguno de `absent_in` la tiene. Un formulario que no existe se
    nombra: una diferencia que habla de un formulario inventado no declara nada.
    """
    if differences is None:
        return (), [
            "falta app/data/sources/differences.yaml: las diferencias entre emisoras se declaran (BR3.7)"
        ]
    formularios = {
        form_id: uno.clauses[form_id] for uno in issuers.values() for form_id in uno.forms
    }
    problemas: list[str] = []
    for diferencia in differences.differences:
        for form_id, debe_estar in [
            *((f, True) for f in diferencia.present_in),
            *((f, False) for f in diferencia.absent_in),
        ]:
            clausulas = formularios.get(form_id)
            if clausulas is None:
                problemas.append(
                    f"diferencia '{diferencia.difference_id}': el formulario '{form_id}' no existe"
                )
                continue
            esta = any(
                c.clause_key == diferencia.clause_key and not c.is_distractor for c in clausulas
            )
            if esta != debe_estar:
                dice = "esta" if debe_estar else "falta"
                problemas.append(
                    f"diferencia '{diferencia.difference_id}': dice que '{diferencia.clause_key}' "
                    f"{dice} en '{form_id}', y el corpus dice lo contrario (BR3.7)"
                )
    return tuple(d.declared() for d in differences.differences), problemas
