"""Las cinco entidades del corpus: forma y valores cerrados (capa Data model)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from untangle.policy_rag.corpus.models import (
    Clause,
    ClauseRelation,
    FormKind,
    IssuedPolicy,
    PolicyForm,
    RelationKind,
)

_FORM = {
    "tenant_id": "testco",
    "form_id": "TCO-PAP-2026",
    "form_version": "2026.1",
    "form_kind": "base",
    "language": "es",
    "issuer_label": "Testco Mutual",
    "issuer_tenant": "testco",
}


def test_un_formulario_valido_se_construye() -> None:
    formulario = PolicyForm.model_validate(_FORM)
    assert formulario.form_kind is FormKind.BASE
    assert formulario.jurisdiction_ref is None


def test_form_kind_no_admite_un_valor_fuera_del_conjunto_cerrado() -> None:
    with pytest.raises(ValidationError):
        PolicyForm.model_validate({**_FORM, "form_kind": "base_form"})


def test_una_clausula_sin_texto_no_valida() -> None:
    with pytest.raises(ValidationError):
        Clause.model_validate(
            {
                "tenant_id": "testco",
                "clause_id": "TCO-PAP-2026-A.1",
                "clause_key": "A.1",
                "form_id": "TCO-PAP-2026",
                "form_version": "2026.1",
                "part": "Parte A",
                "language": "es",
                "text": "",
                "is_distractor": False,
                "issuer_label": "Testco Mutual",
            }
        )


def test_el_identificador_de_una_relacion_es_deterministico() -> None:
    relacion = ClauseRelation(
        tenant_id="testco",
        from_clause="TCO-PAP-2026-END-1-A.LIMIT",
        to_clause="TCO-PAP-2026-A.LIMIT",
        relation=RelationKind.ENDORSEMENT_MODIFIES,
    )
    otra_vez = ClauseRelation(
        tenant_id="testco",
        from_clause="TCO-PAP-2026-END-1-A.LIMIT",
        to_clause="TCO-PAP-2026-A.LIMIT",
        relation=RelationKind.ENDORSEMENT_MODIFIES,
    )
    assert relacion.relation_id == otra_vez.relation_id
    assert (
        relacion.relation_id
        == "TCO-PAP-2026-END-1-A.LIMIT:endorsement_modifies:TCO-PAP-2026-A.LIMIT"
    )


def test_una_poliza_fuera_de_vigencia_se_construye_igual() -> None:
    """El modelo no impone `period_end > period_start`: eso es la migracion (BR2.2)."""
    poliza = IssuedPolicy.model_validate(
        {
            "tenant_id": "testco",
            "policy_number": "POL-TEST-001",
            "issuer_tenant": "testco",
            "form_id": "TCO-PAP-2026",
            "form_version": "2026.1",
            "endorsement_ids": [],
            "named_insured": {"full_name": "Persona de Prueba"},
            "vehicles": [],
            "limits_and_deductibles": {},
            "period_start": "2026-01-01",
            "period_end": "2025-01-01",
        }
    )
    assert poliza.period_end < poliza.period_start
