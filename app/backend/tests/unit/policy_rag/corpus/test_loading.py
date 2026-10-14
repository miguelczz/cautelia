"""Manifiesto y validacion estructural del corpus, sin base de datos (BR1.1, BR1.2, BR1.3).

Cada regla de precedencia lleva su propia prueba, escrita antes del codigo
(ajuste de la evaluacion de U9, `unit-test-instructions.md`): un corpus que no
casa con su manifiesto no se lee ni un poco (BR1.1), y ninguna de las tres
formas de romper la validacion estructural deja pasar una fila (BR1.2).
"""

from __future__ import annotations

import json
import re

import pytest

from untangle.policy_rag.corpus.loading import (
    CorpusValidationError,
    ManifestMismatchError,
    load_corpus,
    verify_manifest,
)

from .conftest import TENANT_ID, SeededCorpus


def test_el_manifiesto_consistente_no_falla(seeded_corpus: SeededCorpus) -> None:
    verify_manifest(
        TENANT_ID, repo_root=seeded_corpus.repo_root, manifest_path=seeded_corpus.manifest_path
    )


def test_un_archivo_que_no_casa_con_el_manifiesto_detiene_la_ingesta(
    seeded_corpus: SeededCorpus,
) -> None:
    seeded_corpus.corrupt_manifest_hash("forms/TCO-PAP-2026.json")

    with pytest.raises(ManifestMismatchError, match=re.escape("forms/TCO-PAP-2026.json")):
        verify_manifest(
            TENANT_ID,
            repo_root=seeded_corpus.repo_root,
            manifest_path=seeded_corpus.manifest_path,
        )


def test_un_archivo_editado_despues_del_manifiesto_tambien_falla(
    seeded_corpus: SeededCorpus, rewrite_json: object
) -> None:
    """Un archivo que cambio y el manifiesto no vio: BR1.1 lo ataja antes que nada."""
    ruta = seeded_corpus.corpus_tenants_dir / TENANT_ID / "clauses/TCO-PAP-2026.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    datos["clauses"][0]["text"] = "Texto cambiado a mano, sin pasar por el generador."
    ruta.write_text(json.dumps(datos), encoding="utf-8")

    with pytest.raises(ManifestMismatchError):
        verify_manifest(
            TENANT_ID,
            repo_root=seeded_corpus.repo_root,
            manifest_path=seeded_corpus.manifest_path,
        )


def test_cargar_el_corpus_sembrado_devuelve_sus_cuatro_catalogos(
    seeded_corpus: SeededCorpus,
) -> None:
    corpus = load_corpus(TENANT_ID, corpus_tenants_dir=seeded_corpus.corpus_tenants_dir)

    assert corpus.tenant_id == TENANT_ID
    assert {f.form_id for f in corpus.forms} == {
        "TCO-PAP-2026",
        "TCO-PAP-2025",
        "TCO-PAP-2026-END-1",
        "TCO-PAP-2026-END-2",
    }
    assert {c.clause_id for c in corpus.clauses} == {
        "TCO-PAP-2026-AGREEMENT.1",
        "TCO-PAP-2026-A.LIMIT",
        "TCO-PAP-2025-AGREEMENT.1.ALT",
        "TCO-PAP-2026-END-1-A.LIMIT",
    }
    assert len(corpus.relations) == 1
    assert corpus.relations[0].relation.value == "endorsement_modifies"
    assert len(corpus.policies) == 1
    assert corpus.policies[0].policy_number == "POL-TEST-001"


def test_dos_clausulas_con_el_mismo_identificador_detiene_la_ingesta(
    seeded_corpus: SeededCorpus,
) -> None:
    """BR1.2: un `clause_id` repetido, aunque venga de dos archivos distintos."""
    contenido: dict[str, object] = {
        "form_id": "TCO-PAP-2026-END-2",
        "clauses": [
            {
                "clause_id": "TCO-PAP-2026-A.LIMIT",  # ya existe en TCO-PAP-2026.json
                "clause_key": "A.LIMIT",
                "form_id": "TCO-PAP-2026-END-2",
                "form_version": "2026.1",
                "part": "Endoso 2",
                "language": "es",
                "text": "Un duplicado a proposito.",
                "is_distractor": False,
                "issuer_label": "Testco Mutual",
            }
        ],
    }
    seeded_corpus.write_form_file("clauses/TCO-PAP-2026-END-2.json", contenido)

    with pytest.raises(CorpusValidationError, match=re.escape("TCO-PAP-2026-A.LIMIT")):
        load_corpus(TENANT_ID, corpus_tenants_dir=seeded_corpus.corpus_tenants_dir)


def test_una_relacion_hacia_una_clausula_inexistente_detiene_la_ingesta(
    seeded_corpus: SeededCorpus,
) -> None:
    """BR1.2: una relacion cuyo destino no existe en ningun archivo de clausulas."""
    seeded_corpus.write_form_file(
        "clause_relations.json",
        {
            "relations": [
                {
                    "from_clause": "TCO-PAP-2026-END-1-A.LIMIT",
                    "relation": "endorsement_modifies",
                    "to_clause": "TCO-PAP-2026-NO-EXISTE",
                }
            ]
        },
    )

    with pytest.raises(CorpusValidationError, match="TCO-PAP-2026-NO-EXISTE"):
        load_corpus(TENANT_ID, corpus_tenants_dir=seeded_corpus.corpus_tenants_dir)


def test_una_poliza_que_referencia_un_endoso_sin_version_detiene_la_ingesta(
    seeded_corpus: SeededCorpus,
) -> None:
    """BR1.2: la poliza nombra un endoso que ningun formulario de la aseguradora declara."""
    seeded_corpus.write_form_file(
        "issued_policies/POL-TEST-001.json",
        {
            "policy_number": "POL-TEST-001",
            "tenant_id": TENANT_ID,
            "issuer_tenant": TENANT_ID,
            "form_id": "TCO-PAP-2026",
            "form_version": "2026.1",
            "endorsement_ids": ["TCO-PAP-2026-END-NO-EXISTE"],
            "named_insured": {"full_name": "Persona de Prueba"},
            "vehicles": [],
            "limits_and_deductibles": {},
            "period_start": "2026-01-01",
            "period_end": "2027-01-01",
        },
    )

    with pytest.raises(CorpusValidationError, match="TCO-PAP-2026-END-NO-EXISTE"):
        load_corpus(TENANT_ID, corpus_tenants_dir=seeded_corpus.corpus_tenants_dir)


def test_una_clausula_sin_clave_estructural_no_valida(seeded_corpus: SeededCorpus) -> None:
    """BR1.2: una clausula sin `clause_key` (el modelo la rechaza; el mensaje la nombra)."""
    seeded_corpus.write_form_file(
        "clauses/TCO-PAP-2026-END-2.json",
        {
            "form_id": "TCO-PAP-2026-END-2",
            "clauses": [
                {
                    "clause_id": "TCO-PAP-2026-END-2-SIN-CLAVE",
                    "clause_key": "",
                    "form_id": "TCO-PAP-2026-END-2",
                    "form_version": "2026.1",
                    "part": "Endoso 2",
                    "language": "es",
                    "text": "Una clausula sin clave estructural.",
                    "is_distractor": False,
                    "issuer_label": "Testco Mutual",
                }
            ],
        },
    )

    with pytest.raises(CorpusValidationError):
        load_corpus(TENANT_ID, corpus_tenants_dir=seeded_corpus.corpus_tenants_dir)
