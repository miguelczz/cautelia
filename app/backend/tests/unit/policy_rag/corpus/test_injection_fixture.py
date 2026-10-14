"""El fixture de inyección de `app/evals/fixtures/injection-corpus/` (paso 7, CG-U8-6, FD-U8-3).

Sin base de datos: `verify_manifest` y `load_corpus` son lectura de archivos.
Lo que aquí se comprueba es que el fixture existe, casa con su propio
manifiesto y **nunca** convive con el corpus real de `app/data/` -- que es
justamente lo que FD-U8-3 pide: la cláusula con instrucciones no entra al
corpus que se publica.
"""

from __future__ import annotations

import pytest

from untangle import paths
from untangle.evals import loading as evals_loading
from untangle.evals.models import Dataset
from untangle.policy_rag.corpus.loading import load_corpus, verify_manifest

FIXTURE_ROOT = paths.repo_root() / "app" / "evals" / "fixtures" / "injection-corpus"
TENANT_ID = "injection-test"


def test_el_fixture_casa_con_su_propio_manifiesto() -> None:
    verify_manifest(
        TENANT_ID,
        repo_root=FIXTURE_ROOT,
        manifest_path=FIXTURE_ROOT / "app" / "data" / "manifest.json",
    )


def test_el_fixture_no_esta_dentro_del_corpus_real() -> None:
    """FD-U8-3: el corpus que se publica no contiene una trampa."""
    assert not FIXTURE_ROOT.is_relative_to(paths.corpus_tenants_dir())
    assert TENANT_ID not in {p.name for p in paths.corpus_tenants_dir().iterdir() if p.is_dir()}


def test_el_fixture_trae_una_clausula_por_idioma_recuperable_y_no_distractora() -> None:
    corpus = load_corpus(TENANT_ID, corpus_tenants_dir=FIXTURE_ROOT / "app" / "data" / "tenants")

    por_idioma = {clausula.language: clausula for clausula in corpus.clauses}
    assert set(por_idioma) == {"es", "en"}
    for clausula in por_idioma.values():
        # No distractora: un distractor que no se indexa no distrae, y esta
        # clausula tiene que poder recuperarse de verdad para que la
        # comprobacion de SEC-U8.3 sea real y no un adorno (CG-U8-6).
        assert clausula.is_distractor is False
        assert "ignora" in clausula.text.lower() or "ignore" in clausula.text.lower()

    assert len(corpus.policies) == 2
    assert {p.policy_number for p in corpus.policies} == {"POL-INJ-ES-001", "POL-INJ-EN-001"}


@pytest.mark.parametrize(
    "case_key", ["DS-6/es/rt2-policy-clause-injection", "DS-6/en/rt2-policy-clause-injection"]
)
def test_el_caso_de_ds6_entrega_una_clausula_real_del_fixture(case_key: str) -> None:
    """CG-U8-2, aplicado al caso de inyeccion (CG-U8-6): el mismo espejo que DS-3.

    Desde el 2026-10-12 el caso no corre por el canal: la sonda
    `rt2_poisoned_clause_not_obeyed` le entrega la clausula a mano al proponedor de citas
    (`poisoned_clause`). Esta prueba ata esa clausula y esa poliza al fixture real, para
    que el caso no nombre un identificador que nadie verifico.
    """
    casos = evals_loading.load_cases()
    caso = next(c for c in casos if c.case_key == case_key)
    assert caso.dataset is Dataset.DS_6
    assert caso.tenant == TENANT_ID
    assert caso.channel is None, "no es una conversacion: la clausula se entrega a mano"
    assert caso.expected_record == {}, "sin base no hay registro que comparar"
    assert caso.poisoned_clause is not None

    corpus = load_corpus(TENANT_ID, corpus_tenants_dir=FIXTURE_ROOT / "app" / "data" / "tenants")
    clausulas = {c.clause_id: c for c in corpus.clauses}
    polizas = {p.policy_number: p for p in corpus.policies}

    clause_id = caso.poisoned_clause.clause_id
    policy_number = caso.poisoned_clause.policy_number
    assert clause_id in clausulas
    assert policy_number in polizas
    assert clausulas[clause_id].is_distractor is False
    assert clausulas[clause_id].form_id == polizas[policy_number].form_id
    # La clausula es la envenenada: trae una orden, que es lo que la sonda pone a prueba.
    assert "ignor" in clausulas[clause_id].text.lower()
    assert clausulas[clause_id].language == caso.language
