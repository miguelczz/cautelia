"""Las cinco entidades del corpus, tal como U7 las escribe (`entities.md`).

Cinco de las siete entidades de U8: el formulario, la clausula, la relacion
entre clausulas, la poliza emitida y la entrada del indice. Las otras dos
--`CitationCheck` y `CoverageAnswer`-- las escribe `CitationVerifier` en
`policy_rag/citations/`, que llega en el paso 5 de esta unidad (tanda 2); este
modulo no las declara porque nada de lo que hay aqui las produce.

**El corpus real manda sobre el boceto de `entities.md`.** Tres nombres de
campo difieren de lo que ese documento sugiere, y la razon es la misma que ya
dejo escrita para `issuer_tenant` o `endorsement_ids`: gana el archivo que se
ingiere, no el boceto que se escribio antes de que U7 lo generara.

- `PolicyForm.kind` es `form_kind` aqui, con los valores que el archivo trae
  de verdad: `base`, `endorsement`, `jurisdiction` (nunca `base_form`).
- `PolicyForm` no tiene `superseded_by`: ningun formulario generado lo trae.
  Que version es vigente lo decide la poliza que la referencia (BR1.4), nunca
  el formulario, asi que la columna no existe (`FormLoadError` no la exige).
- `ClauseRelation` no tiene `form_version`: el archivo de relaciones es
  `{from_clause, relation, to_clause}` y nada mas. La version aplicable de una
  relacion es la de la clausula que senala (`to_clause`), y se resuelve
  contra `Clause.form_version`, no se duplica aqui.

Todos los modelos son `Frozen`: el corpus es dato de la aseguradora, sembrado
por U7, y no cambia una vez ingerido salvo por una nueva corrida de la
ingesta (BR1.5).
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import Field

from untangle.base import Frozen, Locale
from untangle.tenancy.models import TENANT_ID_PATTERN, TenantId


class FormKind(StrEnum):
    """Los tres tipos de formulario que trae el corpus (`form_kind` real)."""

    BASE = "base"
    ENDORSEMENT = "endorsement"
    JURISDICTION = "jurisdiction"


class RelationKind(StrEnum):
    """Los tres tipos de relacion entre clausulas (ADR-010)."""

    ENDORSEMENT_MODIFIES = "endorsement_modifies"
    DEFINES = "defines"
    REFERS_TO = "refers_to"


class PolicyForm(Frozen):
    """Un formulario del corpus de una aseguradora, tal como U7 lo escribe."""

    tenant_id: TenantId = Field(pattern=TENANT_ID_PATTERN)
    form_id: str = Field(min_length=1)
    form_version: str = Field(min_length=1)
    form_kind: FormKind
    language: Locale
    issuer_label: str = Field(min_length=1)
    #: Quien emitio el formulario. En una agencia decide de que corpus sale una
    #: cita para su cliente (BR2.5); en una aseguradora que emite directo
    #: coincide con `tenant_id`.
    issuer_tenant: TenantId = Field(pattern=TENANT_ID_PATTERN)
    jurisdiction_ref: str | None = None
    #: Los identificadores de cláusula que este formulario declara (BR1.2,
    #: BR1.3): la ingesta los usa para comprobar que cada clausula del archivo
    #: pertenece a un formulario que la nombra, y viceversa.
    clause_ids: tuple[str, ...] = ()


class Clause(Frozen):
    """Una clausula del corpus: la unidad de cita y de fragmento (BR1.3)."""

    tenant_id: TenantId = Field(pattern=TENANT_ID_PATTERN)
    clause_id: str = Field(min_length=1)
    clause_key: str = Field(min_length=1)
    form_id: str = Field(min_length=1)
    form_version: str = Field(min_length=1)
    part: str = Field(min_length=1)
    language: Locale
    text: str = Field(min_length=1)
    is_distractor: bool
    issuer_label: str = Field(min_length=1)


class ClauseRelation(Frozen):
    """Una arista entre dos clausulas del mismo corpus (ADR-010)."""

    tenant_id: TenantId = Field(pattern=TENANT_ID_PATTERN)
    from_clause: str = Field(min_length=1)
    to_clause: str = Field(min_length=1)
    relation: RelationKind

    @property
    def relation_id(self) -> str:
        """Un identificador deterministico y estable entre corridas (BR1.5).

        Nunca aleatorio (convencion del equipo): reingestar sin cambios tiene
        que producir la misma fila, y una arista la nombran sus tres campos
        por completo -- no hace falta nada mas para que sea unica dentro de la
        aseguradora.
        """
        return f"{self.from_clause}:{self.relation.value}:{self.to_clause}"


class DeclaredDriver(Frozen):
    """Un conductor que la poliza declara. Solo su nombre, que es lo que se compara."""

    full_name: str = Field(min_length=1)


class IssuedPolicy(Frozen):
    """Una poliza emitida: el filtro que hace que una respuesta salga de ahi y de ninguna otra."""

    tenant_id: TenantId = Field(pattern=TENANT_ID_PATTERN)
    policy_number: str = Field(min_length=1)
    issuer_tenant: TenantId = Field(pattern=TENANT_ID_PATTERN)
    form_id: str = Field(min_length=1)
    form_version: str = Field(min_length=1)
    endorsement_ids: tuple[str, ...] = ()
    #: Dato de persona sembrada por U7 (P8): sintetico, no dato de visitante.
    named_insured: dict[str, Any] = Field(default_factory=dict)
    #: Los conductores que la poliza declara, el titular primero. **Vacio es "no declara
    #: conductores"**, no "no tiene ninguno": es lo que traen las filas ingeridas antes de que
    #: existiera este campo, y quien compara a un conductor con la lista no puede decir que no
    #: figura cuando la lista no se sabe. Dato de persona sembrada, como el titular.
    drivers: tuple[DeclaredDriver, ...] = ()
    vehicles: tuple[dict[str, Any], ...] = ()
    limits_and_deductibles: dict[str, Any] = Field(default_factory=dict)
    period_start: date
    period_end: date


class ClauseIndexEntry(Frozen):
    """Lo que hace buscable una clausula: su hash de contenido y su modelo (BR1.5, BR1.6).

    No lleva el vector ni el `tsvector` -- los calcula la base, el segundo
    como columna generada y el primero al llamar al `Embedder` -- porque este
    modelo es lo que la ingesta compara para decidir **si** hace falta volver
    a calcular alguno de los dos, no lo que se guarda.
    """

    tenant_id: TenantId = Field(pattern=TENANT_ID_PATTERN)
    clause_id: str = Field(min_length=1)
    embedding_model: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
