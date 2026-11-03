"""Una poliza de ejemplo en memoria para probar los datos rigidos sin base ni docker.

Los valores son escritos a mano y distintos entre si a proposito: una prueba que lee un monto del
campo equivocado tiene que fallar, y eso solo pasa si cada monto es unico.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

import pytest

from untangle.policy_rag.corpus.models import Clause, DeclaredDriver, IssuedPolicy

LIMITES: dict[str, Any] = {
    "a.bodily_injury_per_person": 100000,
    "a.bodily_injury_per_accident": 200000,
    "a.property_damage": 50000,
    "b.medical_payments_per_person": 10000,
    "c.driver_personal_accident": 100000,
    "d.damage_deductible": 1500,
    "d.theft_deductible": 250,
}


def poliza(**cambios: Any) -> IssuedPolicy:
    """La poliza de ejemplo, con lo que la prueba quiera cambiar."""
    datos: dict[str, Any] = {
        "tenant_id": "stonecroft",
        "policy_number": "POL-99",
        "issuer_tenant": "stonecroft",
        "form_id": "SA-PAP-2026",
        "form_version": "2026.1",
        "endorsement_ids": ("SA-PAP-2026-END-1", "SA-PAP-2026-END-2"),
        "named_insured": {"full_name": "Daniela Castaño", "national_id": "61.567.060"},
        "drivers": (
            DeclaredDriver(full_name="Daniela Castaño"),
            DeclaredDriver(full_name="Hernán Castaño"),
        ),
        "vehicles": (
            {"make_model_year": "Kia Picanto 2013", "plate": "JUH431", "vin": "B0UMB1VW2WD449075"},
            {"make_model_year": "Mazda 3 2020", "plate": "ABC123", "vin": "X" * 17},
        ),
        "limits_and_deductibles": dict(LIMITES),
        "period_start": date(2026, 6, 14),
        "period_end": date(2027, 6, 14),
    }
    datos.update(cambios)
    return IssuedPolicy.model_validate(datos)


@pytest.fixture
def poliza_de_ejemplo() -> IssuedPolicy:
    return poliza()


# --- Un corpus en memoria -----------------------------------------------------
# La base se sustituye en el limite del repositorio (`find_policy`, `clause_keys_of_forms`,
# `clauses_by_ids`). Que la base filtre por aseguradora es la politica de fila, que prueban las
# pruebas de aislamiento con la base de verdad.


class CorpusEnMemoria:
    """Un corpus en memoria: una poliza, las clausulas de dos formularios y lo que se pregunto."""

    def __init__(self, policy: IssuedPolicy | None, clauses: tuple[Clause, ...] = ()) -> None:
        self.policy = policy
        self.clauses = clauses
        self.read_for: list[str] = []

    async def find_policy(self, tenant_id: str, *, policy_number: str) -> IssuedPolicy | None:
        self.read_for.append(tenant_id)
        if self.policy and (tenant_id, policy_number) == (
            self.policy.tenant_id,
            self.policy.policy_number,
        ):
            return self.policy
        return None

    async def clause_keys_of_forms(
        self, tenant_id: str, *, form_ids: Sequence[str]
    ) -> dict[str, tuple[str, ...]]:
        return {f: ("B.INS",) for f in form_ids if f == "SA-PAP-2026-END-1"}

    async def clauses_by_ids(
        self, tenant_id: str, *, clause_ids: Sequence[str]
    ) -> tuple[Clause, ...]:
        return tuple(c for c in self.clauses if c.clause_id in clause_ids)


def clausula(clause_id: str, form_id: str, *, distractor: bool = False) -> Clause:
    return Clause(
        tenant_id="stonecroft",
        clause_id=clause_id,
        clause_key="B.INS",
        form_id=form_id,
        form_version="2026.1",
        part="Gastos médicos de los ocupantes",
        language="es",
        text="Texto sintetico de la clausula.",
        is_distractor=distractor,
        issuer_label="Stonecroft",
    )


def instalar_corpus(monkeypatch: pytest.MonkeyPatch, corpus: CorpusEnMemoria) -> CorpusEnMemoria:
    """Enchufa el corpus en memoria en el lugar de las tres lecturas del repositorio."""
    from untangle.policy_rag.corpus import repository

    monkeypatch.setattr(repository, "find_policy", corpus.find_policy)
    monkeypatch.setattr(repository, "clause_keys_of_forms", corpus.clause_keys_of_forms)
    monkeypatch.setattr(repository, "clauses_by_ids", corpus.clauses_by_ids)
    return corpus


def corpus_de_ejemplo() -> CorpusEnMemoria:
    """Una poliza y las clausulas de dos formularios, un senuelo y una clausula ajena."""
    return CorpusEnMemoria(
        poliza(),
        (
            clausula("C-BASE", "SA-PAP-2026"),
            clausula("C-ENDOSO", "SA-PAP-2026-END-1"),
            clausula("C-AJENA", "OTRO-FORMULARIO"),
            clausula("C-SENUELO", "SA-PAP-2026", distractor=True),
        ),
    )
