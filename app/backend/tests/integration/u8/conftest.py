"""Lo que las pruebas de integracion de U8 necesitan en la base efimera.

Mismo patron que U9 (`tests/integration/u9/conftest.py`): las siete tablas se
vacian antes y despues de cada prueba, en el orden que respeta sus llaves
foraneas, y ninguna aseguradora se escribe a mano -- son las que ya carga
`tenancy.config` desde `app/config/tenants/`.

**Nunca corre en la nube.** El contenedor de esta tanda no tiene Docker
(`u8-tanda-1.md`, "Antes que nada: el entorno"): este archivo se escribe aqui
y se corre en la sesion local, con `mise run test:u8` y Docker levantado
(CG-U8-5).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from untangle.base import Use
from untangle.case_record import api as casos
from untangle.case_record.models import Channel, Origin, RecordType, Speaker
from untangle.case_record.transcript import TurnDraft
from untangle.compliance.redaction.api import redact
from untangle.providers.ports import Vector
from untangle.tenancy import api as tenancy
from untangle.tenancy import ephemeral

#: Un instante fijo para las pruebas de U8 que crean un caso o un turno.
AHORA = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)

#: El modelo de embeddings de prueba: nunca el real, para que ninguna prueba
#: dependa de `providers.yaml` ni de una clave (CG-U8-4).
EMBEDDING_MODEL = "test-embedder-v1"
EMBEDDING_DIMENSIONS = 8

#: El vector de consulta de las pruebas de recuperacion. Tiene que traer las
#: mismas dimensiones que los indexados: pgvector compara por distancia y una
#: consulta de otra dimension no es una consulta mala, es un error de tipo.
#: Su contenido da igual --ninguna prueba de esta unidad afirma sobre la
#: distancia, sino sobre que se recupero y de quien-- pero es fijo para que dos
#: corridas del mismo commit ordenen igual.
QUERY_VECTOR: tuple[float, ...] = tuple(
    (i + 1) / (EMBEDDING_DIMENSIONS + 1) for i in range(EMBEDDING_DIMENSIONS)
)


class FakeEmbedder:
    """Un doble determinista del `Embedder` (CG-U8-4): cuenta llamadas y no llama a nadie.

    El vector de cada texto sale de su propio hash, sembrado y estable entre
    corridas -- nunca de `random` (convencion del equipo) -- para que la fusion
    y el orden de la busqueda vectorial, cuando lleguen en la tanda 2, sean
    deterministas y afirmables.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    async def embed(self, texts: Sequence[str], *, use: Use) -> list[Vector]:
        del use
        self.calls.append(tuple(texts))
        return [self._vector(texto) for texto in texts]

    @staticmethod
    def _vector(text: str) -> Vector:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return tuple((digest[i % len(digest)] / 255.0) for i in range(EMBEDDING_DIMENSIONS))


_TABLAS_EN_ORDEN_DE_BORRADO = (
    "clause_index",
    "clause_relations",
    "issued_policies",
    "clauses",
    "policy_forms",
    # `case_record` se lleva `citation_checks`, `coverage_answers` y
    # `case_transcript_turn` por cascada (BR4.5): no hace falta nombrarlas.
    "case_record",
)


async def _vaciar() -> None:
    for tenant_id in tenancy.available_ids():
        async with tenancy.session_for(tenant_id) as sesion:
            for tabla in _TABLAS_EN_ORDEN_DE_BORRADO:
                await tenancy.execute_sql(sesion, f"DELETE FROM {tabla}")  # noqa: S608


@pytest.fixture
async def base_de_u8(sesiones: ephemeral.EphemeralDatabase) -> AsyncIterator[None]:
    """La base efimera, sin corpus de U8 antes ni despues de cada prueba."""
    await _vaciar()
    yield
    await _vaciar()


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def dos_aseguradoras() -> tuple[str, str]:
    """Dos aseguradoras reales de la configuracion, para las pruebas de aislamiento."""
    disponibles = tenancy.available_ids()
    assert len(disponibles) >= 2, "la prueba de aislamiento necesita dos aseguradoras"
    return disponibles[0], disponibles[1]


@dataclass(frozen=True)
class CasoSembrado:
    """Un caso de una aseguradora, creado con la API de U4 (mismo patron que U9)."""

    tenant_id: str
    case_id: str


async def nuevo_caso(tenant_id: str) -> CasoSembrado:
    """Un caso de chat publico, por la API de U4."""
    case_id = f"u8-caso-{uuid.uuid4().hex[:12]}"
    await casos.create_case(
        tenant_id,
        casos.NewCase(
            case_id=case_id,
            record_type=RecordType.CLAIM,
            channel=Channel.CHAT,
            origin=Origin.PUBLIC_CHAT,
            language="es",
        ),
        now=AHORA,
    )
    return CasoSembrado(tenant_id=tenant_id, case_id=case_id)


async def nuevo_turno(caso: CasoSembrado, *, text: str = "¿Que cubre la parte A?") -> str:
    """Un turno del asegurado, ya redactado, para que `coverage_answers` tenga a que apuntar."""
    turn_id = f"u8-turno-{uuid.uuid4().hex[:12]}"
    await casos.append_turn(
        caso.tenant_id,
        TurnDraft(
            turn_id=turn_id,
            case_id=caso.case_id,
            speaker=Speaker.INSURED,
            channel=Channel.CHAT,
            language="es",
            started_at=AHORA,
        ),
        redact(text, language="es"),
    )
    return turn_id
