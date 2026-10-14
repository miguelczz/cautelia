"""`PolicyCorpus.retrieve` contra PostgreSQL de verdad (paso 4, tanda 2).

De integracion porque lo que se prueba es lo que la SQL real hace: el
aislamiento entre aseguradoras sobre `clauses`/`clause_index` (RLS, BR2.1,
SEC-U8.1), la busqueda vectorial exacta sin filtrar entre aseguradoras
(NFR10.1) y el evento de recuperacion completo (OBS-U8.1). La fusion por rango
reciproco y el cierre por relaciones, al ser funciones puras, ya se prueban sin
base en `tests/unit/policy_rag/corpus/test_retrieval.py`; aqui solo se
comprueba que la orquestacion sobre la base real produce el mismo resultado.

**Se escribe aqui y se corre en la sesion local** (CG-U8-5): este contenedor no
tiene Docker. El `Embedder` sigue siendo un doble determinista (CG-U8-4).
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from untangle import observability
from untangle.base import Use
from untangle.policy_rag.corpus import api as corpus
from untangle.policy_rag.corpus.ingest import EmbeddingClient, IngestionSources

from .conftest import EMBEDDING_MODEL, QUERY_VECTOR, FakeEmbedder

pytestmark = pytest.mark.usefixtures("base_de_u8")

AHORA = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def _escribir(path: Path, contenido: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contenido), encoding="utf-8")


def _seed_tenant(  # noqa: PLR0913 -- una perilla por dato variable entre escenarios de prueba
    root: Path,
    tenant_id: str,
    *,
    form_id: str = "TCO-PAP-2026",
    old_form_id: str = "TCO-PAP-2025",
    endorsement_form_id: str = "TCO-PAP-2026-END-1",
    policy_number: str,
    period_start: str = "2026-01-01",
    period_end: str = "2027-01-01",
    endorsement_ids: list[str] | None = None,
    language: str = "es",
    base_clause_text: str = "El limite por persona es el que muestra la caratula.",
) -> None:
    """Un formulario base, una version anterior (distractor) y un endoso vigente."""
    tenant_dir = root / "app" / "data" / "tenants" / tenant_id
    base_clause_id = f"{form_id}-A.LIMIT"
    old_clause_id = f"{old_form_id}-A.LIMIT.ALT"
    endorsement_clause_id = f"{endorsement_form_id}-A.LIMIT"

    _escribir(
        tenant_dir / "forms" / f"{form_id}.json",
        {
            "form_id": form_id,
            "form_kind": "base",
            "form_version": "2026.1",
            "issuer_label": f"{tenant_id} Mutual",
            "issuer_tenant": tenant_id,
            "jurisdiction_ref": None,
            "language": language,
            "clause_ids": [base_clause_id],
        },
    )
    _escribir(
        tenant_dir / "forms" / f"{old_form_id}.json",
        {
            "form_id": old_form_id,
            "form_kind": "base",
            "form_version": "2025.1",
            "issuer_label": f"{tenant_id} Mutual",
            "issuer_tenant": tenant_id,
            "jurisdiction_ref": None,
            "language": language,
            "clause_ids": [old_clause_id],
        },
    )
    _escribir(
        tenant_dir / "forms" / f"{endorsement_form_id}.json",
        {
            "form_id": endorsement_form_id,
            "form_kind": "endorsement",
            "form_version": "2026.1",
            "issuer_label": f"{tenant_id} Mutual",
            "issuer_tenant": tenant_id,
            "jurisdiction_ref": None,
            "language": language,
            "clause_ids": [endorsement_clause_id],
        },
    )
    _escribir(
        tenant_dir / "clauses" / f"{form_id}.json",
        {
            "form_id": form_id,
            "clauses": [
                {
                    "clause_id": base_clause_id,
                    "clause_key": "A.LIMIT",
                    "form_id": form_id,
                    "form_version": "2026.1",
                    "part": "Parte A",
                    "language": language,
                    "text": base_clause_text,
                    "is_distractor": False,
                    "issuer_label": f"{tenant_id} Mutual",
                }
            ],
        },
    )
    _escribir(
        tenant_dir / "clauses" / f"{old_form_id}.json",
        {
            "form_id": old_form_id,
            "clauses": [
                {
                    "clause_id": old_clause_id,
                    "clause_key": "A.LIMIT",
                    "form_id": old_form_id,
                    "form_version": "2025.1",
                    "part": "Parte A",
                    "language": language,
                    "text": "Version anterior del limite, que ya no aplica (distractor).",
                    "is_distractor": True,
                    "issuer_label": f"{tenant_id} Mutual",
                }
            ],
        },
    )
    _escribir(
        tenant_dir / "clauses" / f"{endorsement_form_id}.json",
        {
            "form_id": endorsement_form_id,
            "clauses": [
                {
                    "clause_id": endorsement_clause_id,
                    "clause_key": "A.LIMIT",
                    "form_id": endorsement_form_id,
                    "form_version": "2026.1",
                    "part": "Endoso 1",
                    "language": language,
                    "text": "El endoso 1 sube el limite de la parte A.",
                    "is_distractor": False,
                    "issuer_label": f"{tenant_id} Mutual",
                }
            ],
        },
    )
    _escribir(
        tenant_dir / "clause_relations.json",
        {
            "relations": [
                {
                    "from_clause": endorsement_clause_id,
                    "relation": "endorsement_modifies",
                    "to_clause": base_clause_id,
                }
            ]
        },
    )
    _escribir(
        tenant_dir / "issued_policies" / f"{policy_number}.json",
        {
            "policy_number": policy_number,
            "tenant_id": tenant_id,
            "issuer_tenant": tenant_id,
            "form_id": form_id,
            "form_version": "2026.1",
            "endorsement_ids": endorsement_ids if endorsement_ids is not None else [],
            "named_insured": {"full_name": "Persona de Prueba"},
            "vehicles": [],
            "limits_and_deductibles": {},
            "period_start": period_start,
            "period_end": period_end,
        },
    )


def _manifest(root: Path) -> None:
    outputs: dict[str, str] = {}
    for archivo in (root / "app" / "data" / "tenants").rglob("*"):
        if archivo.is_file():
            clave = archivo.relative_to(root).as_posix()
            outputs[clave] = hashlib.sha256(archivo.read_bytes()).hexdigest()
    _escribir(
        root / "app" / "data" / "manifest.json",
        {
            "manifest_version": 1,
            "generator_version": "test",
            "seed": 1,
            "declared_differences": [],
            "review_samples": [],
            "seeded_cases": [],
            "inputs": {},
            "outputs": outputs,
        },
    )


def _sources(root: Path) -> IngestionSources:
    return IngestionSources(
        corpus_tenants_dir=root / "app" / "data" / "tenants",
        repo_root=root,
        manifest_path=root / "app" / "data" / "manifest.json",
    )


async def _ingest(root: Path, tenant_id: str) -> None:
    cliente = EmbeddingClient(
        embedder=FakeEmbedder(), embedding_model=EMBEDDING_MODEL, use=Use.CORPUS
    )
    await corpus.ingest_tenant(tenant_id, client=cliente, sources=_sources(root))


async def test_filtra_antes_de_ordenar_una_clausula_de_otra_aseguradora_no_aparece(
    tmp_path: Path, dos_aseguradoras: tuple[str, str]
) -> None:
    """BR2.1, SEC-U8.1: el conjunto recuperado nunca lleva una clausula ajena."""
    propia, ajena = dos_aseguradoras
    _seed_tenant(tmp_path, propia, policy_number="POL-PROPIA")
    _seed_tenant(tmp_path, ajena, policy_number="POL-AJENA", base_clause_text="Limite ajeno.")
    _manifest(tmp_path)
    await _ingest(tmp_path, propia)
    await _ingest(tmp_path, ajena)

    resultado = await corpus.retrieve(
        propia,
        policy_number="POL-PROPIA",
        query_text="limite",
        query_vector=QUERY_VECTOR,
        embedding_model=EMBEDDING_MODEL,
        now=AHORA,
    )

    ids_recuperados = {clausula.clause_id for clausula in resultado.clauses}
    assert ids_recuperados, "la prueba no afirma nada si no se recupero ninguna clausula"
    assert all(clausula.tenant_id == propia for clausula in resultado.clauses)


async def test_poliza_fuera_de_vigencia_recupera_vacio(tmp_path: Path) -> None:
    """BR2.2: conjunto vacio, sin aproximarse a la version anterior."""
    _seed_tenant(
        tmp_path,
        "stonecroft",
        policy_number="POL-VENCIDA",
        period_start="2020-01-01",
        period_end="2021-01-01",
    )
    _manifest(tmp_path)
    await _ingest(tmp_path, "stonecroft")

    resultado = await corpus.retrieve(
        "stonecroft",
        policy_number="POL-VENCIDA",
        query_text="limite",
        query_vector=QUERY_VECTOR,
        embedding_model=EMBEDDING_MODEL,
        now=AHORA,
    )

    assert resultado.clauses == ()


async def test_poliza_de_otra_aseguradora_es_identica_a_inexistente(
    tmp_path: Path, dos_aseguradoras: tuple[str, str]
) -> None:
    """BR2.6, SEC-U8.4: mismo resultado para una poliza ajena y una inventada."""
    propia, ajena = dos_aseguradoras
    _seed_tenant(tmp_path, propia, policy_number="POL-PROPIA")
    _seed_tenant(tmp_path, ajena, policy_number="POL-AJENA")
    _manifest(tmp_path)
    await _ingest(tmp_path, propia)
    await _ingest(tmp_path, ajena)

    resultado_ajena = await corpus.retrieve(
        propia,
        policy_number="POL-AJENA",
        query_text="limite",
        query_vector=QUERY_VECTOR,
        embedding_model=EMBEDDING_MODEL,
        now=AHORA,
    )
    resultado_inventada = await corpus.retrieve(
        propia,
        policy_number="POL-NO-EXISTE-NUNCA",
        query_text="limite",
        query_vector=QUERY_VECTOR,
        embedding_model=EMBEDDING_MODEL,
        now=AHORA,
    )

    assert resultado_ajena.clauses == () == resultado_inventada.clauses
    assert resultado_ajena.probe.filtered_by == resultado_inventada.probe.filtered_by


async def test_un_endoso_vigente_trae_por_cierre_la_clausula_que_modifica(
    tmp_path: Path,
) -> None:
    """BR2.4: el endoso vigente que modifica la clausula recuperada entra por el cierre."""
    _seed_tenant(
        tmp_path,
        "stonecroft",
        policy_number="POL-CON-ENDOSO",
        endorsement_ids=["TCO-PAP-2026-END-1"],
    )
    _manifest(tmp_path)
    await _ingest(tmp_path, "stonecroft")

    # `limit=1` es lo que hace observable el cierre: con el corpus sembrado
    # entero cabiendo en el limite por defecto, la busqueda ya devuelve el
    # endoso y no habria forma de distinguir lo que encontro la busqueda de lo
    # que arrastro el cierre, que es justo lo que BR2.4 exige poder separar.
    resultado = await corpus.retrieve(
        "stonecroft",
        policy_number="POL-CON-ENDOSO",
        query_text="limite",
        query_vector=QUERY_VECTOR,
        embedding_model=EMBEDDING_MODEL,
        now=AHORA,
        limit=1,
    )

    ids = {c.clause_id for c in resultado.clauses}
    assert "TCO-PAP-2026-END-1-A.LIMIT" in ids
    fuente = resultado.probe.sources["TCO-PAP-2026-END-1-A.LIMIT"]
    assert fuente.closure_of == "TCO-PAP-2026-A.LIMIT"
    # El cierre no cuenta para la metrica de recuperacion (BR2.4).
    assert fuente.lexical_rank is None
    assert fuente.vector_rank is None


async def test_un_endoso_no_vigente_no_entra_por_el_cierre(tmp_path: Path) -> None:
    """BR2.1, BR2.4: sin el endoso en `endorsement_ids`, su clausula no aparece."""
    _seed_tenant(tmp_path, "stonecroft", policy_number="POL-SIN-ENDOSO", endorsement_ids=[])
    _manifest(tmp_path)
    await _ingest(tmp_path, "stonecroft")

    resultado = await corpus.retrieve(
        "stonecroft",
        policy_number="POL-SIN-ENDOSO",
        query_text="limite",
        query_vector=QUERY_VECTOR,
        embedding_model=EMBEDDING_MODEL,
        now=AHORA,
    )

    ids = {c.clause_id for c in resultado.clauses}
    assert "TCO-PAP-2026-END-1-A.LIMIT" not in ids
    assert "TCO-PAP-2025-A.LIMIT.ALT" not in ids  # el distractor tampoco: otra version


async def test_la_busqueda_vectorial_no_cruza_aseguradoras(
    tmp_path: Path, dos_aseguradoras: tuple[str, str]
) -> None:
    """NFR10.1: la busqueda vectorial, medida aparte de las tablas de texto, tambien aisla."""
    propia, ajena = dos_aseguradoras
    _seed_tenant(tmp_path, propia, policy_number="POL-PROPIA")
    _seed_tenant(tmp_path, ajena, policy_number="POL-AJENA")
    _manifest(tmp_path)
    await _ingest(tmp_path, propia)
    await _ingest(tmp_path, ajena)

    from untangle.policy_rag.corpus import repository

    vectoriales = await repository.vector_rank(
        propia,
        embedding_model=EMBEDDING_MODEL,
        candidate_ids=("TCO-PAP-2026-A.LIMIT",),
        query_vector=QUERY_VECTOR,
        limit=10,
    )
    assert set(vectoriales) <= {"TCO-PAP-2026-A.LIMIT"}


async def test_el_evento_de_recuperacion_declara_filtros_y_origen(tmp_path: Path) -> None:
    """OBS-U8.1: el evento lleva los filtros aplicados y de donde vino cada clausula."""
    _seed_tenant(tmp_path, "stonecroft", policy_number="POL-OBS")
    _manifest(tmp_path)
    await _ingest(tmp_path, "stonecroft")

    # `set_stream` y no `capsys`: el punto unico de salida se queda con la
    # referencia a `sys.stdout` al importarse, asi que `capsys`, que sustituye
    # `sys.stdout` despues, no ve nada. El propio modulo deja `set_stream` para
    # esto, y asi la prueba no toca estado compartido entre pruebas.
    capturado = io.StringIO()
    observability.set_stream(capturado)
    try:
        await corpus.retrieve(
            "stonecroft",
            policy_number="POL-OBS",
            query_text="limite",
            query_vector=QUERY_VECTOR,
            embedding_model=EMBEDDING_MODEL,
            now=AHORA,
        )
    finally:
        observability.set_stream(sys.stdout)

    eventos = [json.loads(linea) for linea in capturado.getvalue().splitlines() if linea.strip()]
    probe = next(e for e in eventos if e["event"] == "policy_rag.retrieval_probe")
    assert probe["filtered_by"]["form_id"] == "TCO-PAP-2026"
    assert probe["filtered_by"]["tenant_id"] == "stonecroft"
    assert "TCO-PAP-2026-A.LIMIT" in probe["clause_ids"]
    # Nunca la pregunta ni el texto de una clausula: solo identificadores.
    assert "limite" not in json.dumps(probe)
