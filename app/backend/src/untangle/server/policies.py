"""La pestana de polizas: las polizas de ejemplo de cada aseguradora (fase 2, 2026-10-08).

`GET /api/policies/{tenant_id}`, sin credencial, como el directorio del sitio: son
las polizas sinteticas con las que el visitante puede probar el chat y la llamada, y
la pestana las muestra para que sepa que preguntar.

**Lo que viaja y lo que no.** El titular viaja por su nombre, que el chat ya dice al
confirmar la poliza; la cedula, el telefono, el correo, la placa y el VIN no viajan,
aunque sean sinteticos: la pestana no los necesita y una vista publica no muestra lo
que no usa.

**Las preguntas para probar no son texto**: son identificadores que la interfaz
resuelve en el catalogo. Dos generales para toda poliza, y una por cada diferencia
declarada entre aseguradoras (`app/data/sources/differences.yaml`) que esa poliza
trae, porque son las preguntas donde las respuestas de dos aseguradoras cambian.

No llama a ningun proveedor ni gasta: lee el corpus ya sembrado.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import cache
from pathlib import Path

import yaml
from fastapi import APIRouter

from untangle import paths
from untangle.base import Frozen, Locale
from untangle.policy_rag.citations import api as citas
from untangle.policy_rag.corpus import api as corpus
from untangle.policy_rag.corpus import translations as traducciones
from untangle.server.problems import ProblemCode, ProblemError, problem_responses
from untangle.tenancy import api as tenancy

#: Las preguntas que sirven para cualquier poliza. `towing` es a proposito una sin
#: clausula en el corpus: muestra que la agente dice "no la encuentro" en vez de
#: inventar (decision de Miguel del 2026-10-09: mas preguntas para probar).
GENERAL_QUESTIONS: tuple[str, ...] = (
    "hail",
    "rental_car",
    "theft",
    "uninsured_driver",
    "lend_car",
    "passengers_medical",
    "report_deadline",
    "abroad",
    "towing",
)


class EndorsementView(Frozen):
    """Un endoso de la poliza y que clausulas cambia, por su clave."""

    form_id: str
    clause_keys: tuple[str, ...]


class PolicyView(Frozen):
    """Una poliza de ejemplo, tal como la dibuja la pestana."""

    policy_number: str
    holder_name: str
    #: El nombre visible de quien la emitio: en una agencia no es ella.
    issuer_name: str
    vehicles: tuple[str, ...]
    period_start: date
    period_end: date
    #: Los limites y deducibles en las unidades del corpus. La interfaz los muestra en
    #: pesos multiplicando por mil (decision de Miguel del 2026-10-07).
    limits: dict[str, int]
    endorsements: tuple[EndorsementView, ...]
    #: Identificadores de pregunta, resueltos en el catalogo (`policies.question.*`).
    questions: tuple[str, ...]


class PolicyCatalog(Frozen):
    tenant_id: str
    example_policy: str
    policies: tuple[PolicyView, ...]


class DocumentView(Frozen):
    """Un documento del corpus de la aseguradora, para el panel de documentos."""

    form_id: str
    form_version: str
    #: `base`, `endorsement` o `jurisdiction`.
    kind: str
    language: str
    clause_count: int
    #: Si alguna poliza emitida lo usa. La version 2025 no: esta para comprobar que la
    #: agente no cita documentos viejos, y el panel lo dice.
    in_force: bool


class DocumentsCatalog(Frozen):
    tenant_id: str
    documents: tuple[DocumentView, ...]


class ClauseView(Frozen):
    clause_id: str
    clause_key: str
    part: str
    text: str
    #: Los endosos que la modifican, por su formulario.
    amended_by: tuple[str, ...]
    #: Cuantas veces salio citada y verificada en los ultimos siete dias. Un recuento
    #: agregado: no dice de que caso ni de quien.
    cited_last_week: int
    #: El idioma de la clausula y su traduccion de referencia al de la pantalla, si es
    #: otro (decision de Miguel del 2026-10-08). El texto que rige es `text`.
    language: str
    translated_text: str | None = None
    translated_part: str | None = None


class DocumentDetail(Frozen):
    tenant_id: str
    form_id: str
    clauses: tuple[ClauseView, ...]


#: La ventana del recuento de citas del panel.
CITATION_WINDOW = timedelta(days=7)


@dataclass(frozen=True)
class PoliciesDeps:
    tenants: Callable[[], Sequence[tenancy.TenantConfig]]
    differences_path: Path | None = None
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)


@cache
def _diferencias(ruta: Path) -> tuple[tuple[str, frozenset[str]], ...]:
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    return tuple(
        (str(d["difference_id"]).replace("-", "_"), frozenset(d["present_in"]))
        for d in datos["differences"]
    )


def questions_for(
    policy: corpus.IssuedPolicy, differences: Sequence[tuple[str, frozenset[str]]]
) -> tuple[str, ...]:
    """Las generales, y las de cada diferencia que esta poliza trae."""
    formularios = {policy.form_id, *policy.endorsement_ids}
    propias = tuple(ident for ident, presentes in differences if presentes & formularios)
    return (*GENERAL_QUESTIONS, *propias)


def router(deps: PoliciesDeps) -> APIRouter:
    enrutador = APIRouter(prefix="/api", tags=["policies"])

    @enrutador.get(
        "/policies/{tenant_id}",
        response_model=PolicyCatalog,
        operation_id="getPolicies",
        responses=problem_responses(404),
    )
    async def policies(tenant_id: str) -> PolicyCatalog:
        cargadas = {t.tenant_id: t for t in deps.tenants()}
        aseguradora = _cargada(cargadas, tenant_id)
        polizas = await corpus.list_policies(aseguradora.tenant_id)
        endosos = await corpus.clause_keys_of_forms(
            aseguradora.tenant_id,
            form_ids=sorted({e for p in polizas for e in p.endorsement_ids}),
        )
        diferencias = _diferencias(
            deps.differences_path or paths.synthetic_sources_dir() / "differences.yaml"
        )
        return PolicyCatalog(
            tenant_id=aseguradora.tenant_id,
            example_policy=aseguradora.example_policy,
            policies=tuple(
                PolicyView(
                    policy_number=p.policy_number,
                    holder_name=str(p.named_insured.get("full_name", "")),
                    issuer_name=(
                        cargadas[p.issuer_tenant].display_name
                        if p.issuer_tenant in cargadas
                        else aseguradora.display_name
                    ),
                    vehicles=tuple(str(v.get("make_model_year", "")) for v in p.vehicles),
                    period_start=p.period_start,
                    period_end=p.period_end,
                    limits={k: int(v) for k, v in p.limits_and_deductibles.items()},
                    endorsements=tuple(
                        EndorsementView(form_id=e, clause_keys=endosos.get(e, ()))
                        for e in p.endorsement_ids
                    ),
                    questions=questions_for(p, diferencias),
                )
                for p in polizas
            ),
        )

    @enrutador.get(
        "/policies/{tenant_id}/documents",
        response_model=DocumentsCatalog,
        operation_id="getPolicyDocuments",
        responses=problem_responses(404),
    )
    async def documents(tenant_id: str) -> DocumentsCatalog:
        aseguradora = _cargada({t.tenant_id: t for t in deps.tenants()}, tenant_id)
        formularios = await corpus.list_forms(aseguradora.tenant_id)
        polizas = await corpus.list_policies(aseguradora.tenant_id)
        usados = {p.form_id for p in polizas} | {e for p in polizas for e in p.endorsement_ids}
        return DocumentsCatalog(
            tenant_id=aseguradora.tenant_id,
            documents=tuple(
                DocumentView(
                    form_id=str(f["form_id"]),
                    form_version=str(f["form_version"]),
                    kind=str(f["form_kind"]),
                    language=str(f["language"]),
                    clause_count=int(str(f["clause_count"])),
                    # Un documento de jurisdiccion no lo emite ninguna poliza: rige
                    # para todas las de su territorio.
                    in_force=str(f["form_kind"]) == "jurisdiction" or str(f["form_id"]) in usados,
                )
                for f in formularios
            ),
        )

    @enrutador.get(
        "/policies/{tenant_id}/documents/{form_id}",
        response_model=DocumentDetail,
        operation_id="getPolicyDocument",
        responses=problem_responses(404),
    )
    async def document(
        tenant_id: str, form_id: str, language: Locale | None = None
    ) -> DocumentDetail:
        aseguradora = _cargada({t.tenant_id: t for t in deps.tenants()}, tenant_id)
        clausulas = await corpus.clauses_of_form(aseguradora.tenant_id, form_id=form_id)
        if not clausulas:
            raise ProblemError(status=404, code=ProblemCode.NOT_FOUND, title="Not found")
        ids = [c.clause_id for c in clausulas]
        endosos = await corpus.amending_forms(aseguradora.tenant_id, clause_ids=ids)
        veces = await citas.verified_citations_since(
            aseguradora.tenant_id, clause_ids=ids, since=deps.clock() - CITATION_WINDOW
        )
        return DocumentDetail(
            tenant_id=aseguradora.tenant_id,
            form_id=form_id,
            clauses=tuple(
                ClauseView(
                    clause_id=c.clause_id,
                    clause_key=c.clause_key,
                    part=c.part,
                    text=c.text,
                    amended_by=endosos.get(c.clause_id, ()),
                    cited_last_week=veces.get(c.clause_id, 0),
                    language=c.language,
                    translated_text=(
                        traducciones.clause_text(c.clause_id, language)
                        if language is not None and language != c.language
                        else None
                    ),
                    translated_part=(
                        traducciones.part_text(c.part, language)
                        if language is not None and language != c.language
                        else None
                    ),
                )
                for c in clausulas
            ),
        )

    return enrutador


def _cargada(cargadas: dict[str, tenancy.TenantConfig], tenant_id: str) -> tenancy.TenantConfig:
    aseguradora = cargadas.get(tenant_id)
    if aseguradora is None:
        raise ProblemError(status=404, code=ProblemCode.NOT_FOUND, title="Not found")
    return aseguradora


__all__ = [
    "CITATION_WINDOW",
    "GENERAL_QUESTIONS",
    "ClauseView",
    "DocumentDetail",
    "DocumentView",
    "DocumentsCatalog",
    "EndorsementView",
    "PoliciesDeps",
    "PolicyCatalog",
    "PolicyView",
    "questions_for",
    "router",
]
