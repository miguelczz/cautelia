"""El chat entiende un mensaje antes de entregarlo (2026-10-12): cuando no hay nada que entender.

Sin base y sin modelo. Lo que entiende de verdad, con el caso y la conversacion, esta probado de
punta a punta en `tests/integration/u13/test_topic_change.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, Literal

import pytest

from untangle.orchestration import contracts, turn


def _mensaje(
    *, case_id: str | None = "caso-1", texto: str = "hola", canal: Literal["chat", "voice"] = "chat"
) -> contracts.InboundTurn:
    return contracts.InboundTurn(
        tenant_id="sunmeadow",
        session_ref="chat-1",
        case_id=case_id,
        text=texto,
        language="es",
        channel=canal,
        received_at=datetime(2026, 10, 12, 12, 0, tzinfo=UTC),
    )


@pytest.fixture(autouse=True)
def _sin_runtime() -> Any:
    turn.reset_runtime()
    yield
    turn.reset_runtime()


async def test_sin_runtime_instalado_no_hay_nada_que_entender_y_no_levanta() -> None:
    """Si el turno de verdad se entrega, `handle_turn` es quien dice que falta el runtime."""
    assert await turn.understand_turn(_mensaje()) is None


async def test_sin_entendedor_en_el_runtime_no_se_entiende() -> None:
    turn._runtime = SimpleNamespace(understander=None)  # type: ignore[assignment]

    assert await turn.understand_turn(_mensaje()) is None


async def test_un_mensaje_sin_caso_no_se_entiende_aqui() -> None:
    """El primer mensaje lo entiende el canal sin caso, no por este camino."""

    async def entendedor(_peticion: object) -> object:
        raise AssertionError("no debia llamarse")

    turn._runtime = SimpleNamespace(understander=entendedor)  # type: ignore[assignment]

    assert await turn.understand_turn(_mensaje(case_id=None)) is None


@pytest.mark.parametrize(
    "texto",
    ["quiero hablar con un humano", "¿eres una persona o un robot?"],
    ids=["pide-un-ajustador", "pregunta-quien-es"],
)
async def test_lo_que_resuelve_una_senal_por_reglas_no_paga_una_llamada_al_modelo(
    texto: str,
) -> None:
    async def entendedor(_peticion: object) -> object:
        raise AssertionError("el turno resuelve estas senales sin modelo")

    turn._runtime = SimpleNamespace(understander=entendedor)  # type: ignore[assignment]

    assert await turn.understand_turn(_mensaje(texto=texto)) is None


@pytest.mark.parametrize("texto", ["si", "no, nadie", "si claro"])
async def test_una_respuesta_de_voz_de_una_o_dos_palabras_no_paga_una_llamada_al_modelo(
    texto: str,
) -> None:
    """Las resuelven las reglas del turno. La llamada adelanta esta lectura en cuanto llega el
    final, y adelantar un "si" seria pagar el modelo para tirar lo que devuelve."""

    async def entendedor(_peticion: object) -> object:
        raise AssertionError("una respuesta corta de voz la resuelven las reglas")

    turn._runtime = SimpleNamespace(understander=entendedor)  # type: ignore[assignment]

    assert await turn.understand_turn(_mensaje(texto=texto, canal="voice")) is None
    assert contracts.VOICE_RULES_MAX_WORDS == 2
