"""El comando a mano que ingiere el corpus de polizas en la base (FD-U8-5).

    mise run corpus:ingest -- [--tenant <id> ...]

**Nunca corre en GitHub Actions ni al arrancar** (FD-U8-5): llama al proveedor
de embeddings con la clave del uso `corpus`, y un arranque que indexa es
un arranque que llama al proveedor sin que nadie lo haya pedido (PERF-U8.4).
Vive aqui y no en `untangle.policy_rag` porque necesita el adaptador del
proveedor, y solo la raiz de composicion puede construirlo (contrato
`raiz-de-composicion`); el mismo camino de gasto que `synthetic:draft`
--techo antes de llamar, fila en el libro mayor despues-- (`manual_ledger.py`).

## El uso `corpus`, cerrado en el PASO 0 de la tanda 3

`GeminiEmbedder.embed()` resuelve el modelo por el `Use` que se le pasa
(`ProvidersConfig.for_use`). Los cuatro usos que declaraba `providers.yaml`
apuntaban todos al modelo de generacion (`gemini-3.1-flash-lite`): `Use.OPERATIONS`
ya lo usaba `synthetic:draft` para generar texto, asi que apuntarlo tambien al
modelo de embeddings habria roto esa otra llamada -- un `UseConfig` es un
modelo por uso, no dos. Por eso este comando llama ahora con el uso `corpus`,
declarado aparte en `providers.yaml` con su propia clave
(`UNTANGLE_CORPUS_MODEL_API_KEY`), que es el mismo que usa el nodo
`policy_verification` (tanda 3) para la consulta.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal

from untangle.base import ProviderName, Use
from untangle.policy_rag.corpus import api as corpus
from untangle.providers import config as provider_config
from untangle.providers import factory
from untangle.providers.adapters.gemini import api as gemini
from untangle.providers.adapters.gemini import breaker as circuitos
from untangle.providers.adapters.gemini import transport as gemini_transport
from untangle.providers.config import ModelKind
from untangle.providers.ports import BudgetExhausted, ProviderError, ProviderErrorKind
from untangle.providers.transport import CallTimeouts, TransportFactory
from untangle.server import manual_ledger, spend_wiring
from untangle.settings import Settings
from untangle.tenancy import config as tenancy_config

#: Cuantas clausulas caben en una llamada a `batchEmbedContents` de Gemini.
#:
#: Su tope duro documentado es **cien** --un lote de 104 se rechaza con
#: `400 ... at most 100 requests can be in one batch`-- y la cuota del plan
#: gratuito rechaza ya ese tamano con `429`. Diez pasa. Las dos cosas se
#: midieron el 2026-09-27, en la primera ingesta real de las 414 clausulas del
#: corpus; hasta ese dia la ingesta mandaba el corpus entero en una llamada y
#: no podia funcionar con ninguna clave.
LOTE_DE_EMBEDDINGS_GEMINI = 10

__all__ = [
    "EmbeddingModel",
    "EmbeddingPlatform",
    "build_embedding_platform",
    "embedding_model_for",
    "main",
]


@dataclass(frozen=True)
class EmbeddingModel:
    """El modelo de embeddings configurado, con su identificador exacto (BR1.6)."""

    provider: ProviderName
    model_id: str
    dimensions: int


@dataclass(frozen=True)
class EmbeddingPlatform:
    """Lo que la ingesta necesita, construido por el camino del aplicativo."""

    clients: factory.ProviderClients
    embedder: gemini.GeminiEmbedder


def embedding_model_for(config: provider_config.ProvidersConfig) -> EmbeddingModel:
    """El unico modelo de embeddings declarado (TECH-U8.5). Falla si no hay ninguno."""
    for proveedor in config.providers:
        for modelo in proveedor.models:
            if modelo.kind is ModelKind.EMBEDDING:
                if modelo.dimensions is None:  # pragma: no cover -- el esquema ya lo exige
                    msg = f"el modelo de embeddings '{modelo.id}' no declara dimensiones"
                    raise provider_config.ProviderConfigError(msg)
                return EmbeddingModel(
                    provider=proveedor.name, model_id=modelo.id, dimensions=modelo.dimensions
                )
    msg = "providers.yaml no declara ningun modelo de embeddings (TECH-U8.5)"
    raise provider_config.ProviderConfigError(msg)


def build_embedding_platform(
    settings: Settings,
    config: provider_config.ProviderPlatformConfig,
    *,
    transports: TransportFactory | None = None,
) -> EmbeddingPlatform:
    """La fabrica y el adaptador de verdad hacia Gemini. Las pruebas nunca pasan por aqui (CG-U8-4)."""
    transportes = (
        transports if transports is not None else gemini_transport.GeminiTransportFactory()
    )
    clientes = factory.ProviderClients(
        settings=settings, config=config.providers, transports=transportes
    )
    uso = config.providers.for_use(Use.CORPUS)
    embebedor = gemini.GeminiEmbedder(
        clientes,
        config=config.providers,
        breakers=circuitos.CircuitBreakerRegistry(config.providers.circuit_breaker),
        usage=spend_wiring.LedgerUsageSink(),
        timeouts={
            Use.CORPUS: CallTimeouts(
                connect_timeout_ms=uso.connect_timeout_ms, read_timeout_ms=uso.read_timeout_ms
            )
        },
    )
    return EmbeddingPlatform(clients=clientes, embedder=embebedor)


def _analizador() -> argparse.ArgumentParser:
    analizador = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    analizador.add_argument(
        "--tenant",
        action="append",
        default=None,
        help="la aseguradora a ingerir; se repite para pedir varias (por omision, todas)",
    )
    return analizador


async def _con_registro(
    config: provider_config.ProviderPlatformConfig,
    url: str,
    *,
    run: Callable[[], Awaitable[int]],
) -> int:
    await manual_ledger.open_ledger(config, url)
    gastado: Decimal | None = None
    try:
        codigo = await run()
    finally:
        gastado = await manual_ledger.close_ledger()
    print(
        f"acumulado de la ventana tras la corrida: {gastado if gastado is not None else 'no disponible'}"
    )
    return codigo


async def _ingerir(
    tenant_ids: tuple[str, ...], embedder: gemini.GeminiEmbedder, modelo: EmbeddingModel
) -> int:
    cliente = corpus.EmbeddingClient(
        embedder=embedder,
        embedding_model=modelo.model_id,
        use=Use.CORPUS,
        # El limite es de Gemini, asi que lo fija quien sabe con quien se habla.
        # Medido el 2026-09-27 en la primera ingesta real: cien es el tope duro
        # de `batchEmbedContents` y la cuota del plan gratuito rechaza ya ese
        # tamano; diez pasa. Cambiar de proveedor cambia este numero, no el
        # codigo de `policy_rag`.
        batch_size=LOTE_DE_EMBEDDINGS_GEMINI,
    )
    try:
        reportes = await corpus.ingest_all(tenant_ids, client=cliente)
    except BudgetExhausted as parada:
        print(
            f"SE DETUVO: {parada}. No se reintenta ni se recarga; decide Miguel.",
            file=sys.stderr,
        )
        return 2
    except ProviderError as error:
        print(f"la ingesta fallo: {error}. No se reintenta.", file=sys.stderr)
        if error.kind is ProviderErrorKind.RATE_LIMITED:
            print("Si es la cuota diaria del plan gratuito, se retoma otro dia.", file=sys.stderr)
        return 1
    except (corpus.ManifestMismatchError, corpus.CorpusValidationError) as error:
        print(str(error), file=sys.stderr)
        return 1

    for reporte in reportes:
        print(
            f"{reporte.tenant_id}: {reporte.forms} formularios, {reporte.clauses} clausulas, "
            f"{reporte.relations} relaciones, {reporte.policies} polizas, "
            f"{reporte.clauses_reindexed} reindexadas, {reporte.embedder_calls} llamada(s) al proveedor"
        )
    return 0


async def run(argv: list[str] | None = None) -> int:
    """La ingesta entera, para quien **ya tiene** un bucle de eventos corriendo.

    Existe aparte de `main` porque el aprovisionamiento de una aseguradora la
    invoca desde dentro de su propio bucle, y `asyncio.run` no se puede llamar
    ahi: levanta `RuntimeError`. La frontera no la cruzaba ninguna prueba porque
    el doble imitaba la **firma** de `main` --recibe texto, devuelve numero-- y
    no su naturaleza, que es arrancar un bucle. La forma que no miente es esta:
    un nucleo asincrono, y `main` como cascara sincrona para la linea de comandos.
    """
    argumentos = _analizador().parse_args(argv)
    ajustes = Settings()
    config = provider_config.load()
    modelo = embedding_model_for(config.providers)

    tenant_ids = tuple(argumentos.tenant) if argumentos.tenant else tenancy_config.load().ids
    if not tenant_ids:
        print("no hay ninguna aseguradora cargada: nada que ingerir", file=sys.stderr)
        return 1

    plataforma = build_embedding_platform(ajustes, config)
    try:
        # La clave se exige antes de levantar ninguna base.
        plataforma.clients.require(Use.CORPUS)
    except factory.MissingProviderKeyError as error:
        print(str(error), file=sys.stderr)
        return 2

    url = manual_ledger.project_ledger_url(ajustes, purpose="ingesta del corpus (FD-U8-5)")
    return await _con_registro(
        config, url, run=lambda: _ingerir(tenant_ids, plataforma.embedder, modelo)
    )


def main(argv: list[str] | None = None) -> int:
    """La misma ingesta desde la linea de comandos, donde no hay bucle todavia."""
    return asyncio.run(run(argv))


if __name__ == "__main__":
    raise SystemExit(main())
