"""La guardia de red funciona: si no, "sin red" seria una promesa y no un hecho."""

from __future__ import annotations

import socket

import pytest

from .red import NetworkBlockedError, NetworkGuard


def test_la_guardia_bloquea_resolver_un_nombre(network_guard: NetworkGuard) -> None:
    with pytest.raises(NetworkBlockedError, match="test:u7 no abre conexiones"):
        socket.getaddrinfo("generativelanguage.googleapis.com", 443)
    assert network_guard.attempts == ["getaddrinfo -> 'generativelanguage.googleapis.com'"]
    network_guard.forget()


def test_la_guardia_bloquea_conectar_un_socket(network_guard: NetworkGuard) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conexion:
        with pytest.raises(NetworkBlockedError):
            conexion.connect(("192.0.2.1", 443))
    with pytest.raises(NetworkBlockedError):
        socket.create_connection(("192.0.2.1", 443))
    assert len(network_guard.attempts) == 2
    network_guard.forget()
