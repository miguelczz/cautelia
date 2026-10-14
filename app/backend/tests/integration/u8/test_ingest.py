"""La ingesta de punta a punta, contra PostgreSQL de verdad (BR1.5 a BR1.7, TECH-U8.4).

De integracion porque lo que se prueba es conducta del motor: el `UPSERT` con
`ON CONFLICT`, la columna generada... no, la columna `lexical_vector` calculada
por `to_tsvector` de verdad, y el aislamiento por aseguradora sobre las siete
tablas. El `Embedder` sigue siendo un doble (CG-U8-4): ninguna prueba de esta
unidad llama a un proveedor.

**Se escribe aqui y se corre en la sesion local** (CG-U8-5): el contenedor de
la tanda 1 no tiene Docker.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from untangle.base import ProviderName, Use
from untangle.policy_rag.corpus import api as corpus
from untangle.policy_rag.corpus.ingest import EmbeddingClient, IngestionSources
from untangle.providers.ports import ProviderError, ProviderErrorKind, Vector
from untangle.tenancy import api as tenancy

from .conftest import EMBEDDING_MODEL, FakeEmbedder

pytestmark = pytest.mark.usefixtures("base_de_u8")

TENANT_ID = "stonecroft"


def _seed_corpus(
    root: Path, *, clause_text: str = "Texto original de la clausula.", clauses: int = 1
) -> None:
    """Un corpus minimo en el arbol que `ingest_tenant` espera.

    `clauses` siembra varias cuando la prueba necesita mas de un lote; con una
    sola, el texto es exactamente `clause_text` y las pruebas de BR1.5 no
    cambian.
    """
    tenant_dir = root / "app" / "data" / "tenants" / TENANT_ID
    (tenant_dir / "forms").mkdir(parents=True, exist_ok=True)
    (tenant_dir / "clauses").mkdir(parents=True, exist_ok=True)
    (tenant_dir / "issued_policies").mkdir(parents=True, exist_ok=True)

    forma = tenant_dir / "forms" / "TCO-PAP-2026.json"
    forma.write_text(
        json.dumps(
            {
                "form_id": "TCO-PAP-2026",
                "form_kind": "base",
                "form_version": "2026.1",
                "issuer_label": "Testco Mutual",
                "issuer_tenant": TENANT_ID,
                "jurisdiction_ref": None,
                "language": "es",
                "clause_ids": [f"TCO-PAP-2026-A.{i}" for i in range(1, clauses + 1)],
            }
        ),
        encoding="utf-8",
    )
    clausulas = tenant_dir / "clauses" / "TCO-PAP-2026.json"
    clausulas.write_text(
        json.dumps(
            {
                "form_id": "TCO-PAP-2026",
                "clauses": [
                    {
                        "clause_id": f"TCO-PAP-2026-A.{i}",
                        "clause_key": f"A.{i}",
                        "form_id": "TCO-PAP-2026",
                        "form_version": "2026.1",
                        "part": "Parte A",
                        "language": "es",
                        "text": clause_text if clauses == 1 else f"{clause_text} ({i})",
                        "is_distractor": False,
                        "issuer_label": "Testco Mutual",
                    }
                    for i in range(1, clauses + 1)
                ],
            }
        ),
        encoding="utf-8",
    )
    poliza = tenant_dir / "issued_policies" / "POL-INT-001.json"
    poliza.write_text(
        json.dumps(
            {
                "policy_number": "POL-INT-001",
                "tenant_id": TENANT_ID,
                "issuer_tenant": TENANT_ID,
                "form_id": "TCO-PAP-2026",
                "form_version": "2026.1",
                "endorsement_ids": [],
                "named_insured": {"full_name": "Persona de Prueba"},
                "vehicles": [],
                "limits_and_deductibles": {},
                "period_start": "2026-01-01",
                "period_end": "2027-01-01",
            }
        ),
        encoding="utf-8",
    )

    outputs: dict[str, str] = {}
    for archivo in (forma, clausulas, poliza):
        clave = archivo.relative_to(root).as_posix()
        outputs[clave] = hashlib.sha256(archivo.read_bytes()).hexdigest()

    manifiesto: dict[str, object] = {
        "manifest_version": 1,
        "generator_version": "test",
        "seed": 1,
        "declared_differences": [],
        "review_samples": [],
        "seeded_cases": [],
        "inputs": {},
        "outputs": outputs,
    }

    (root / "app" / "data").mkdir(parents=True, exist_ok=True)
    (root / "app" / "data" / "manifest.json").write_text(json.dumps(manifiesto), encoding="utf-8")


def _sources(root: Path) -> IngestionSources:
    return IngestionSources(
        corpus_tenants_dir=root / "app" / "data" / "tenants",
        repo_root=root,
        manifest_path=root / "app" / "data" / "manifest.json",
    )


async def test_ingerir_sin_cambios_no_llama_al_proveedor(tmp_path: Path) -> None:
    """BR1.5: cero llamadas al `Embedder` cuando el `content_hash` no cambio."""
    _seed_corpus(tmp_path)
    embebedor = FakeEmbedder()
    cliente = EmbeddingClient(embedder=embebedor, embedding_model=EMBEDDING_MODEL, use=Use.CORPUS)

    primer_reporte = await corpus.ingest_tenant(
        TENANT_ID, client=cliente, sources=_sources(tmp_path)
    )
    assert primer_reporte.clauses_reindexed == 1
    assert primer_reporte.embedder_calls == 1
    assert len(embebedor.calls) == 1

    segundo_reporte = await corpus.ingest_tenant(
        TENANT_ID, client=cliente, sources=_sources(tmp_path)
    )
    assert segundo_reporte.clauses_reindexed == 0
    assert segundo_reporte.embedder_calls == 0
    assert len(embebedor.calls) == 1  # sigue en una: la segunda ingesta no llamo


async def test_una_clausula_cambiada_reindexa_solo_esa(tmp_path: Path) -> None:
    """BR1.5: con una clausula modificada, se reindexa exactamente una."""
    _seed_corpus(tmp_path)
    embebedor = FakeEmbedder()
    cliente = EmbeddingClient(embedder=embebedor, embedding_model=EMBEDDING_MODEL, use=Use.CORPUS)
    await corpus.ingest_tenant(TENANT_ID, client=cliente, sources=_sources(tmp_path))

    _seed_corpus(tmp_path, clause_text="Texto de la clausula, ya modificado.")
    reporte = await corpus.ingest_tenant(TENANT_ID, client=cliente, sources=_sources(tmp_path))

    assert reporte.clauses_reindexed == 1
    assert reporte.embedder_calls == 1
    assert len(embebedor.calls) == 2
    assert embebedor.calls[-1] == ("Texto de la clausula, ya modificado.",)


async def test_el_modelo_de_embeddings_es_parte_de_la_clave_del_indice(tmp_path: Path) -> None:
    """BR1.6: cambiar de modelo no encuentra nada indexado y reingesta todo."""
    _seed_corpus(tmp_path)
    embebedor = FakeEmbedder()
    cliente_v1 = EmbeddingClient(embedder=embebedor, embedding_model="modelo-v1", use=Use.CORPUS)
    await corpus.ingest_tenant(TENANT_ID, client=cliente_v1, sources=_sources(tmp_path))

    cliente_v2 = EmbeddingClient(embedder=embebedor, embedding_model="modelo-v2", use=Use.CORPUS)
    reporte = await corpus.ingest_tenant(TENANT_ID, client=cliente_v2, sources=_sources(tmp_path))

    assert reporte.clauses_reindexed == 1
    assert len(embebedor.calls) == 2

    async with tenancy.session_for(TENANT_ID) as sesion:
        filas = await tenancy.fetch_all(
            sesion,
            "SELECT embedding_model FROM clause_index WHERE clause_id = :id ORDER BY embedding_model",
            id="TCO-PAP-2026-A.1",
        )
    assert {f["embedding_model"] for f in filas} == {"modelo-v1", "modelo-v2"}


async def test_el_tsvector_usa_la_configuracion_del_idioma_de_la_clausula(tmp_path: Path) -> None:
    """TECH-U8.4: `spanish` para una clausula en espanol, no `english` ni `simple`."""
    _seed_corpus(tmp_path)
    embebedor = FakeEmbedder()
    cliente = EmbeddingClient(embedder=embebedor, embedding_model=EMBEDDING_MODEL, use=Use.CORPUS)
    await corpus.ingest_tenant(TENANT_ID, client=cliente, sources=_sources(tmp_path))

    async with tenancy.session_for(TENANT_ID) as sesion:
        fila = await tenancy.fetch_one(
            sesion,
            # 'proteccion' es la forma lematizada de 'protección' en espanol; solo
            # la coincide un tsvector calculado con la configuracion 'spanish'.
            "SELECT (lexical_vector @@ plainto_tsquery('spanish', 'clausula')) AS coincide "
            "FROM clause_index WHERE clause_id = :id",
            id="TCO-PAP-2026-A.1",
        )
    assert fila is not None
    assert fila["coincide"] is True


class _EmbedderQueSeQuedaSinCuota:
    """Responde `lotes_buenos` lotes y despues siempre dice que va muy rapido."""

    def __init__(self, *, lotes_buenos: int) -> None:
        self.calls: list[tuple[str, ...]] = []
        self._restantes = lotes_buenos

    async def embed(self, texts: Sequence[str], *, use: Use) -> list[Vector]:
        del use
        if self._restantes <= 0:
            raise ProviderError(
                ProviderErrorKind.RATE_LIMITED, provider=ProviderName.GEMINI, use=Use.CORPUS
            )
        self._restantes -= 1
        self.calls.append(tuple(texts))
        return [FakeEmbedder._vector(texto) for texto in texts]


async def test_una_corrida_interrumpida_conserva_lo_ya_indexado_y_la_siguiente_la_retoma(
    tmp_path: Path,
) -> None:
    """La ingesta se retoma sola: un lote ya escrito no se vuelve a pedir (BR1.5).

    Sale de la primera ingesta real, el 2026-09-27. Con la cuota diaria del plan
    gratuito las 414 clausulas del corpus no caben en una sola corrida, y hasta
    ese dia los vectores se guardaban en memoria hasta el final: un `429` en la
    clausula 200 tiraba a la basura los 199 anteriores, y volver a pedirlos gasta
    justo la cuota que se acabo.
    """
    _seed_corpus(tmp_path, clauses=10)
    sin_cuota = _EmbedderQueSeQuedaSinCuota(lotes_buenos=2)
    cliente_roto = EmbeddingClient(
        embedder=sin_cuota,
        embedding_model=EMBEDDING_MODEL,
        use=Use.CORPUS,
        batch_size=3,
    )

    with pytest.raises(ProviderError):
        await corpus.ingest_tenant(TENANT_ID, client=cliente_roto, sources=_sources(tmp_path))

    # Los dos lotes que si volvieron quedaron escritos, no en memoria.
    assert len(sin_cuota.calls) == 2

    bueno = FakeEmbedder()
    cliente = EmbeddingClient(
        embedder=bueno,
        embedding_model=EMBEDDING_MODEL,
        use=Use.CORPUS,
        batch_size=3,
    )
    reporte = await corpus.ingest_tenant(TENANT_ID, client=cliente, sources=_sources(tmp_path))

    # Quedaban cuatro de diez: la segunda corrida pide esas y ninguna mas.
    assert reporte.clauses_reindexed == 4
    assert sum(len(lote) for lote in bueno.calls) == 4
