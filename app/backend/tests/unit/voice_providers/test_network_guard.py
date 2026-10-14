"""La guardia de red de `test:u15` funciona de verdad (BR6.1).

Sin esta prueba, la guardia podria estar instalada sobre una puerta que ninguna
biblioteca usa y `test:u15` seguiria diciendo "sin red" sin comprobarlo.
"""

from __future__ import annotations

import asyncio
import socket

import pytest

from .red import NetworkBlockedError, NetworkGuard


def test_una_conexion_directa_se_bloquea_y_queda_anotada(network_guard: NetworkGuard) -> None:
    with pytest.raises(NetworkBlockedError):
        socket.create_connection(("127.0.0.1", 9))
    assert network_guard.attempts == ["create_connection -> ('127.0.0.1', 9)"]
    network_guard.forget()


async def test_la_red_asincrona_tambien_se_bloquea(network_guard: NetworkGuard) -> None:
    """Es la puerta que usan `websockets` y el cliente HTTP de los adaptadores."""
    with pytest.raises(OSError, match="test:u15 no abre conexiones"):
        await asyncio.open_connection("api.deepgram.com", 443)
    assert network_guard.attempts
    assert all("deepgram" in intento for intento in network_guard.attempts)
    network_guard.forget()
