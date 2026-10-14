"""La pestana de polizas: lo que viaja de cada poliza de ejemplo (fase 2, 2026-10-08)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx2
import pytest
from fastapi import FastAPI

from untangle.policy_rag.corpus.models import (
    Clause,
    ClauseRelation,
    FormKind,
    IssuedPolicy,
    PolicyForm,
    RelationKind,
)
from untangle.policy_rag.corpus.repository import upsert_reference_data
from untangle.server import policies, problems
from untangle.tenancy import api as tenancy

pytestmark = pytest.mark.usefixtures("base_de_u13")

DIFERENCIAS = """
differences:
- difference_id: tire-exclusion-reopened
  present_in: [form-u13-END-1]
- difference_id: ride-app-exclusion-reopened
  present_in: [otro-formulario]
"""


def _formulario(tenant_id: str, form_id: str, kind: FormKind, clause_id: str) -> PolicyForm:
    return PolicyForm(
        tenant_id=tenant_id,
        form_id=form_id,
        form_version="2026.1",
        form_kind=kind,
        language="es",
        issuer_label="Mutual",
        issuer_tenant=tenant_id,
        clause_ids=(clause_id,),
    )


def _clausula(tenant_id: str, form_id: str, clause_id: str, clave: str) -> Clause:
    return Clause(
        tenant_id=tenant_id,
        clause_id=clause_id,
        clause_key=clave,
        form_id=form_id,
        form_version="2026.1",
        part="Parte D",
        language="es",
        text="Texto de la clausula.",
        is_distractor=False,
        issuer_label="Mutual",
    )


async def _sembrar(tenant_id: str, numero: str) -> None:
    base = f"form-u13-{tenant_id}"
    await upsert_reference_data(
        tenant_id,
        forms=(
            _formulario(tenant_id, base, FormKind.BASE, f"{base}-D.1"),
            _formulario(tenant_id, "form-u13-END-1", FormKind.ENDORSEMENT, f"{tenant_id}-E-1"),
        ),
        clauses=(
            _clausula(tenant_id, base, f"{base}-D.1", "D.1"),
            _clausula(tenant_id, "form-u13-END-1", f"{tenant_id}-E-1", "D.EXCL.5"),
        ),
        relations=(),
        policies=(
            IssuedPolicy(
                tenant_id=tenant_id,
                policy_number=numero,
                issuer_tenant=tenant_id,
                form_id=base,
                form_version="2026.1",
                endorsement_ids=("form-u13-END-1",),
                named_insured={
                    "full_name": "Natalia Henao Rendón",
                    "national_id": "45.819.323",
                    "phone": "304 555 0160",
                    "email": "natalia.henao@example.org",
                },
                vehicles=({"make_model_year": "Renault Logan 2024", "plate": "WBR686"},),
                limits_and_deductibles={"d.collision_deductible": 250},
                period_start=date(2026, 1, 2),
                period_end=date(2027, 1, 2),
            ),
        ),
    )


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    ruta = tmp_path / "differences.yaml"
    ruta.write_text(DIFERENCIAS, encoding="utf-8")
    construida = FastAPI()
    problems.install_handlers(construida)
    construida.include_router(
        policies.router(
            policies.PoliciesDeps(tenants=lambda: tenancy.loaded().available, differences_path=ruta)
        )
    )
    return construida


def _cliente(app: FastAPI) -> httpx2.AsyncClient:
    transporte = httpx2.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx2.AsyncClient(transport=transporte, base_url="http://testserver")


async def test_la_poliza_viaja_con_lo_que_la_pestana_muestra_y_nada_mas(app: FastAPI) -> None:
    propia, ajena = tenancy.available_ids()[:2]
    await _sembrar(propia, "POL-913001")
    await _sembrar(ajena, "POL-913002")

    async with _cliente(app) as cliente:
        respuesta = await cliente.get(f"/api/policies/{propia}")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    numeros = [p["policy_number"] for p in cuerpo["policies"]]
    assert "POL-913001" in numeros
    assert "POL-913002" not in numeros, "la poliza de otra aseguradora no se lista"
    [poliza] = [p for p in cuerpo["policies"] if p["policy_number"] == "POL-913001"]
    assert poliza["holder_name"] == "Natalia Henao Rendón"
    assert poliza["vehicles"] == ["Renault Logan 2024"]
    assert poliza["limits"] == {"d.collision_deductible": 250}
    assert poliza["endorsements"] == [{"form_id": "form-u13-END-1", "clause_keys": ["D.EXCL.5"]}]
    assert poliza["questions"] == [*policies.GENERAL_QUESTIONS, "tire_exclusion_reopened"]
    for dato in ("45.819.323", "304 555 0160", "example.org", "WBR686"):
        assert dato not in respuesta.text, f"'{dato}' no tiene por que viajar"


async def test_una_aseguradora_que_no_existe_es_404(app: FastAPI) -> None:
    async with _cliente(app) as cliente:
        respuesta = await cliente.get("/api/policies/no-existe")

    assert respuesta.status_code == 404


async def test_los_documentos_dicen_cual_rige_y_que_endoso_modifica_cada_clausula(
    app: FastAPI,
) -> None:
    propia = tenancy.available_ids()[0]
    await _sembrar(propia, "POL-913001")
    base = f"form-u13-{propia}"
    viejo = _formulario(propia, "form-u13-2025", FormKind.BASE, "viejo-D.1")
    await upsert_reference_data(
        propia,
        forms=(viejo,),
        clauses=(_clausula(propia, "form-u13-2025", "viejo-D.1", "D.1"),),
        relations=(
            ClauseRelation(
                tenant_id=propia,
                from_clause=f"{propia}-E-1",
                to_clause=f"{base}-D.1",
                relation=RelationKind.ENDORSEMENT_MODIFIES,
            ),
        ),
        policies=(),
    )

    async with _cliente(app) as cliente:
        lista = await cliente.get(f"/api/policies/{propia}/documents")
        detalle = await cliente.get(f"/api/policies/{propia}/documents/{base}")
        ninguno = await cliente.get(f"/api/policies/{propia}/documents/no-existe")

    rigen = {d["form_id"]: d["in_force"] for d in lista.json()["documents"]}
    assert rigen[base] is True
    assert rigen["form-u13-END-1"] is True
    assert rigen["form-u13-2025"] is False, "ninguna poliza usa la version vieja"
    [clausula] = detalle.json()["clauses"]
    assert clausula["amended_by"] == ["form-u13-END-1"]
    assert clausula["cited_last_week"] == 0
    assert ninguno.status_code == 404
