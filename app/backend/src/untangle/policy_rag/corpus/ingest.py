"""Orquesta la ingesta de una aseguradora: manifiesto, validacion e indice (FD-U8-5).

El recorrido, en el orden de `code-generation-plan.md` (paso 3):

1. **Manifiesto** (BR1.1) -- se compara antes de leer nada mas.
2. **Carga y validacion** (BR1.2, BR1.3) -- el corpus entero o ningun cambio.
3. **Escritura de referencia** -- formularios, clausulas, relaciones y polizas,
   por `ON CONFLICT` (`repository.upsert_reference_data`).
4. **Diferencia contra el indice ya escrito** (BR1.5, BR1.6) -- solo las
   clausulas cuyo `content_hash` cambio, o que nunca se indexaron para este
   modelo, llegan al `Embedder`. Las demas no generan ninguna llamada.
5. **Escritura del indice** -- una sola vez, con el vector que devolvio el
   proveedor.

Esta funcion no construye el `Embedder`: lo recibe. Construir el adaptador de
verdad es trabajo de la raiz de composicion (`untangle.server.corpus_ingest`,
contrato `raiz-de-composicion`); aqui solo se **usa** el puerto, y por eso
ninguna prueba de este modulo necesita clave de proveedor (CG-U8-4).
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from untangle import observability
from untangle.base import Use
from untangle.policy_rag.corpus import repository
from untangle.policy_rag.corpus.loading import LoadedCorpus, load_corpus, verify_manifest
from untangle.policy_rag.corpus.models import Clause, ClauseIndexEntry
from untangle.providers.ports import Embedder, ProviderError, ProviderErrorKind, Vector
from untangle.tenancy.models import TenantId


@dataclass(frozen=True)
class EmbeddingClient:
    """El puerto y con que llamarlo: el modelo (BR1.6) y el uso (`Use`).

    Los tres viajan juntos porque el modelo es parte de la clave del indice y
    el uso decide la clave y el plan del proveedor (`base.Use`): separarlos en
    tres parametros sueltos en cada funcion de este modulo era ademas lo que
    disparaba `PLR0913`.
    """

    embedder: Embedder
    embedding_model: str
    use: Use
    #: Cuantas clausulas caben en una llamada al proveedor.
    #:
    #: **No es una preferencia, es un limite del proveedor**, y por eso lo fija
    #: la raiz de composicion --que es la que sabe con quien se habla-- y no
    #: este modulo. Medido contra Gemini el 2026-09-27, en la primera ingesta
    #: real: un lote de 104 se rechaza con `400 ... at most 100 requests can be
    #: in one batch`, y uno de 100 devuelve `429` por la cuota del plan
    #: gratuito. Diez pasa. Mandar el corpus entero en una llamada, que es lo
    #: que esta funcion hacia antes, no podia funcionar con ninguna clave.
    batch_size: int = 10

    def __post_init__(self) -> None:
        if self.batch_size < 1:
            msg = f"el lote de embeddings no puede ser {self.batch_size}"
            raise ValueError(msg)


@dataclass(frozen=True)
class IngestionSources:
    """Donde leer el corpus, cuando no es `app/data/` (las pruebas, CG-U8-4).

    Los tres juntos porque siempre viajan juntos: un corpus sembrado en un
    directorio temporal necesita las tres rutas apuntando a ese mismo arbol, o
    `verify_manifest` compararia contra el manifiesto real.
    """

    corpus_tenants_dir: Path | None = None
    repo_root: Path | None = None
    manifest_path: Path | None = None


@dataclass(frozen=True)
class IngestionReport:
    """Lo que costo ingerir una aseguradora: para publicarlo (PERF-U8.4)."""

    tenant_id: TenantId
    forms: int
    clauses: int
    relations: int
    policies: int
    #: Cuantas clausulas se enviaron al `Embedder` en esta corrida. Cero
    #: cuando nada cambio (BR1.5).
    clauses_reindexed: int
    #: Cuantas veces se llamo a `Embedder.embed()`. Una por lote: el proveedor
    #: no admite mas de cien por llamada y su cuota admite menos todavia
    #: (`EmbeddingClient.batch_size`).
    embedder_calls: int


def _content_hash(text: str) -> str:
    """El hash que decide si una clausula hay que reindexarla (BR1.5)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pendientes(corpus: LoadedCorpus, *, already_indexed: dict[str, str]) -> tuple[Clause, ...]:
    """Las clausulas cuyo contenido no coincide con lo ya indexado, o que faltan."""
    pendientes = []
    for clausula in corpus.clauses:
        hash_actual = _content_hash(clausula.text)
        if already_indexed.get(clausula.clause_id) != hash_actual:
            pendientes.append(clausula)
    return tuple(pendientes)


#: Cuantas veces se reintenta un lote que el proveedor rechazo por cuota, y
#: cuanto se espera entre intentos. Un lote que devuelve `429` no esta roto:
#: esta llegando demasiado rapido, y la ingesta de 414 clausulas son decenas de
#: llamadas seguidas. Es la unica clase de fallo que se reintenta aqui: un
#: `invalid_response` no mejora esperando, y repetirlo solo gasta cuota.
REINTENTOS_POR_CUOTA = 3
ESPERA_BASE_SEGUNDOS = 2.0


async def _embeber_lote(lote: list[str], *, client: EmbeddingClient) -> list[Vector]:
    """Los vectores de un lote, reintentando solo si el proveedor dijo que va muy rapido."""
    for intento in range(1, REINTENTOS_POR_CUOTA + 1):
        try:
            return await client.embedder.embed(lote, use=client.use)
        except ProviderError as error:
            if error.kind is not ProviderErrorKind.RATE_LIMITED:
                raise
            if intento == REINTENTOS_POR_CUOTA:
                raise
            observability.emit(
                "policy_rag.ingest_rate_limited", attempt=intento, batch_size=len(lote)
            )
            await asyncio.sleep(ESPERA_BASE_SEGUNDOS * intento)
    raise AssertionError  # pragma: no cover -- el bucle sale por return o por raise


async def ingest_tenant(
    tenant_id: TenantId,
    *,
    client: EmbeddingClient,
    sources: IngestionSources | None = None,
    now: datetime | None = None,
) -> IngestionReport:
    """Ingiere el corpus de una aseguradora, de punta a punta.

    `sources` existe para las pruebas, que siembran un corpus minimo en un
    directorio temporal (unit-test-instructions.md, "Sistema de archivos"); en
    produccion se omite y las tres rutas se resuelven contra `app/data/`.
    """
    rutas = sources if sources is not None else IngestionSources()
    verify_manifest(tenant_id, repo_root=rutas.repo_root, manifest_path=rutas.manifest_path)
    corpus = load_corpus(tenant_id, corpus_tenants_dir=rutas.corpus_tenants_dir)

    await repository.upsert_reference_data(
        tenant_id,
        forms=corpus.forms,
        clauses=corpus.clauses,
        relations=corpus.relations,
        policies=corpus.policies,
    )

    ya_indexado = await repository.existing_content_hashes(
        tenant_id, embedding_model=client.embedding_model
    )
    pendientes = _pendientes(corpus, already_indexed=ya_indexado)

    # **Cada lote se escribe en cuanto vuelve**, y no todos juntos al final.
    # Es lo que hace que una corrida interrumpida sirva de algo: con la cuota
    # diaria del plan gratuito, 414 clausulas no caben en una sola corrida, y
    # guardar los vectores en memoria hasta el final significaba que un `429` en
    # la clausula 200 tiraba a la basura los 199 anteriores -- y volver a
    # pedirlos gasta justo la cuota que se acabo. Escribiendo por lote, la
    # comparacion de `content_hash` de BR1.5 hace que la siguiente corrida pida
    # solo lo que falta: la ingesta se retoma sola.
    llamadas = 0
    momento = now if now is not None else datetime.now(UTC)
    for inicio in range(0, len(pendientes), client.batch_size):
        lote = pendientes[inicio : inicio + client.batch_size]
        vectores = await _embeber_lote([clausula.text for clausula in lote], client=client)
        llamadas += 1
        entradas = tuple(
            (
                ClauseIndexEntry(
                    tenant_id=tenant_id,
                    clause_id=clausula.clause_id,
                    embedding_model=client.embedding_model,
                    content_hash=_content_hash(clausula.text),
                ),
                clausula,
                vector,
            )
            for clausula, vector in zip(lote, vectores, strict=True)
        )
        await repository.upsert_index_entries(
            tenant_id,
            embedding_model=client.embedding_model,
            entries=entradas,
            indexed_at=momento,
        )

    return IngestionReport(
        tenant_id=tenant_id,
        forms=len(corpus.forms),
        clauses=len(corpus.clauses),
        relations=len(corpus.relations),
        policies=len(corpus.policies),
        clauses_reindexed=len(pendientes),
        embedder_calls=llamadas,
    )


async def ingest_all(
    tenant_ids: tuple[TenantId, ...],
    *,
    client: EmbeddingClient,
    sources: IngestionSources | None = None,
    now: datetime | None = None,
) -> tuple[IngestionReport, ...]:
    """Ingiere el corpus de varias aseguradoras, una tras otra.

    Una a la vez y no en paralelo: cada una pasa por su propia sesion con la
    aseguradora fijada (BR1.7), y una corrida en paralelo no ahorraria
    llamadas al proveedor -- el costo esta en las clausulas, no en el reloj.
    """
    reportes = []
    for tenant_id in tenant_ids:
        reportes.append(await ingest_tenant(tenant_id, client=client, sources=sources, now=now))
    return tuple(reportes)
