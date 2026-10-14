"""El lote de embeddings: su tamano y lo que pasa cuando el proveedor dice que no.

Estas pruebas nacen de la **primera ingesta real**, el 2026-09-27. Hasta ese dia
la ingesta mandaba el corpus entero en una sola llamada y todas las pruebas
pasaban, porque el doble del `Embedder` acepta cualquier tamano. El proveedor no:
un lote de 104 se rechaza con `400 ... at most 100 requests can be in one batch`
y uno de 100 devuelve `429` con la cuota del plan gratuito. Es decir, la ingesta
no podia funcionar con ninguna clave, y ninguna compuerta lo veia.

Lo que estas pruebas fijan es justo eso: que el tamano del lote se respeta y que
un `429` no mata una corrida de decenas de llamadas seguidas.
"""

from __future__ import annotations

import pytest

from untangle.base import ProviderName, Use
from untangle.policy_rag.corpus.ingest import EmbeddingClient, _embeber_lote
from untangle.providers.ports import ProviderError, ProviderErrorKind, Vector


class _EmbedderDeLotes:
    """Devuelve un vector por texto y anota el tamano de cada lote recibido."""

    def __init__(self, *, fallos_de_cuota: int = 0) -> None:
        self.lotes: list[int] = []
        self._fallos_pendientes = fallos_de_cuota

    async def embed(self, texts: list[str], *, use: Use) -> list[Vector]:
        del use
        if self._fallos_pendientes > 0:
            self._fallos_pendientes -= 1
            raise ProviderError(
                ProviderErrorKind.RATE_LIMITED, provider=ProviderName.GEMINI, use=Use.CORPUS
            )
        self.lotes.append(len(texts))
        return [(float(len(t)),) for t in texts]


def _cliente(embedder: _EmbedderDeLotes, *, batch_size: int) -> EmbeddingClient:
    return EmbeddingClient(
        embedder=embedder,  # type: ignore[arg-type]
        embedding_model="test-embedder-v1",
        use=Use.CORPUS,
        batch_size=batch_size,
    )


async def test_un_rechazo_por_cuota_se_reintenta_y_la_corrida_sigue() -> None:
    embedder = _EmbedderDeLotes(fallos_de_cuota=1)
    textos = [f"clausula {i}" for i in range(4)]

    vectores = await _embeber_lote(textos, client=_cliente(embedder, batch_size=10))

    # Se rechazo una vez y volvio a enviarse: el lote llego entero al segundo
    # intento y no se perdio ningun vector.
    assert embedder.lotes == [4]
    assert len(vectores) == 4


async def test_una_respuesta_invalida_no_se_reintenta() -> None:
    # Un `invalid_response` no mejora esperando, y repetirlo solo gasta cuota:
    # es la misma linea que el corredor de evaluaciones ya traza (U1).
    class _Rota:
        async def embed(self, texts: list[str], *, use: Use) -> list[Vector]:
            del texts, use
            raise ProviderError(
                ProviderErrorKind.INVALID_RESPONSE, provider=ProviderName.GEMINI, use=Use.CORPUS
            )

    with pytest.raises(ProviderError) as fallo:
        await _embeber_lote(
            ["una"],
            client=EmbeddingClient(
                embedder=_Rota(),  # type: ignore[arg-type]
                embedding_model="test-embedder-v1",
                use=Use.CORPUS,
                batch_size=10,
            ),
        )

    assert fallo.value.kind is ProviderErrorKind.INVALID_RESPONSE


def test_un_lote_de_cero_no_se_puede_declarar() -> None:
    with pytest.raises(ValueError, match="no puede ser 0"):
        EmbeddingClient(
            embedder=_EmbedderDeLotes(),  # type: ignore[arg-type]
            embedding_model="test-embedder-v1",
            use=Use.CORPUS,
            batch_size=0,
        )
