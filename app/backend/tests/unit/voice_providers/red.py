"""La guardia de red de `test:u15`: **ninguna prueba de esta carpeta sale a la red**.

`mise run test:u15` corre en cada entrega contra las respuestas grabadas, y su
promesa es que no gasta saldo ni depende de que un proveedor conteste (BR6.1).
Esa promesa no se confia a la disciplina de quien escribe la prueba: esta
guardia se instala sola en cada prueba de la carpeta y bloquea las tres puertas
por las que sale una conexion --resolver un nombre, conectar un socket y abrir
una conexion con la biblioteca estandar--.

## Por que anota el intento ademas de bloquearlo

Porque bloquearlo no basta para que la prueba falle. Un adaptador bien escrito
**convierte** el fallo de conexion en `ProviderError(unavailable)`, que es su
trabajo; una prueba que esperara justo ese error pasaria en verde habiendo
intentado llamar al proveedor. Asi que cada intento queda anotado y la guardia
hace fallar la prueba al cerrarla si hubo alguno, se haya tragado o no.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from typing import Any

import pytest

__all__ = ["NetworkBlockedError", "NetworkGuard", "install_network_guard"]


class NetworkBlockedError(OSError):
    """Una prueba de `test:u15` intento salir a la red."""


@dataclass
class NetworkGuard:
    """Lo que la guardia vio. Solo la prueba de la propia guardia lo vacia."""

    attempts: list[str] = field(default_factory=list)

    def block(self, puerta: str, destino: object) -> NetworkBlockedError:
        self.attempts.append(f"{puerta} -> {destino!r}")
        return NetworkBlockedError(
            f"test:u15 no abre conexiones de red ({puerta} hacia {destino!r}): las "
            "pruebas corren contra las respuestas grabadas (BR6.1)"
        )

    def forget(self) -> None:
        self.attempts.clear()


def install_network_guard(monkeypatch: pytest.MonkeyPatch) -> NetworkGuard:
    """Cierra las tres puertas por las que sale una conexion y devuelve lo que ve."""
    guardia = NetworkGuard()

    def _resolver(host: object, *args: Any, **kwargs: Any) -> Any:
        raise guardia.block("getaddrinfo", host)

    def _conectar(self: socket.socket, direccion: object) -> Any:
        raise guardia.block("socket.connect", direccion)

    def _crear(direccion: object, *args: Any, **kwargs: Any) -> Any:
        raise guardia.block("create_connection", direccion)

    monkeypatch.setattr(socket, "getaddrinfo", _resolver)
    monkeypatch.setattr(socket.socket, "connect", _conectar)
    monkeypatch.setattr(socket.socket, "connect_ex", _conectar)
    monkeypatch.setattr(socket, "create_connection", _crear)
    return guardia
