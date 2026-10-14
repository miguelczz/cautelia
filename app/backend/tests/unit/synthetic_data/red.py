"""La guardia de red de `test:u7`: **ninguna prueba de esta carpeta sale a la red**.

`mise run test:u7` no llama a ningun proveedor: la redaccion se prueba con el
doble de la fabrica de U5 (instrucciones de prueba de U7). La promesa no se
confia a la disciplina de quien escribe la prueba: la guardia se instala sola en
cada prueba de la carpeta y cierra las tres puertas por las que sale una
conexion --resolver un nombre, conectar un socket y abrir una conexion con la
biblioteca estandar--.

Anota cada intento ademas de bloquearlo, por la misma razon que la de U15: el
adaptador de Gemini **convierte** un fallo de conexion en
`ProviderError(unavailable)`, y una prueba que esperara ese error pasaria en
verde habiendo intentado llamar al proveedor. La guardia hace fallar la prueba
al cerrarla si hubo algun intento, se haya tragado o no.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from typing import Any

import pytest

__all__ = ["NetworkBlockedError", "NetworkGuard", "install_network_guard"]


class NetworkBlockedError(OSError):
    """Una prueba de `test:u7` intento salir a la red."""


@dataclass
class NetworkGuard:
    """Lo que la guardia vio. Solo la prueba de la propia guardia lo vacia."""

    attempts: list[str] = field(default_factory=list)

    def block(self, puerta: str, destino: object) -> NetworkBlockedError:
        self.attempts.append(f"{puerta} -> {destino!r}")
        return NetworkBlockedError(
            f"test:u7 no abre conexiones de red ({puerta} hacia {destino!r}): la "
            "redaccion se prueba con el doble de la fabrica de U5"
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
