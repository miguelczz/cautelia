"""El proceso del servidor MCP: sin base no arranca, y la salida estandar queda para el protocolo."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from typing import Any

import pytest

from untangle import observability
from untangle.policy_mcp import __main__ as proceso
from untangle.settings import Settings
from untangle.tenancy import api as tenancy


@pytest.fixture(autouse=True)
def _salida_de_eventos_restaurada() -> Iterator[None]:
    anterior = observability._destino
    yield
    observability.set_stream(anterior)


def test_sin_base_no_arranca_y_lo_dice_por_la_salida_de_errores(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(proceso, "Settings", lambda: Settings(database_url=None))

    assert proceso.main() == 1

    salida = capsys.readouterr()
    assert salida.out == ""
    assert "UNTANGLE_DATABASE_URL" in salida.err


def test_los_eventos_tecnicos_pasan_a_la_salida_de_errores_antes_que_nada(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """La salida estandar es el protocolo: un evento ahi rompe al cliente."""
    monkeypatch.setattr(proceso, "Settings", lambda: Settings(database_url=None))
    proceso.main()

    observability.emit("mcp.prueba")

    salida = capsys.readouterr()
    assert salida.out == ""
    assert "mcp.prueba" in salida.err


def test_con_base_configura_la_sesion_y_sirve_por_stdio(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    llamadas: list[Any] = []
    monkeypatch.setattr(
        proceso, "Settings", lambda: Settings(database_url="postgresql://app@localhost/app")
    )
    monkeypatch.setattr(tenancy, "install", lambda tenants: llamadas.append("install"))
    monkeypatch.setattr(tenancy, "configure", lambda url: llamadas.append(("url", url)))

    class _Servidor:
        def run(self, transporte: str) -> None:
            llamadas.append(("run", transporte))

    monkeypatch.setattr(proceso, "build_server", lambda **_: _Servidor())

    assert proceso.main() == 0
    assert llamadas == ["install", ("url", "postgresql://app@localhost/app"), ("run", "stdio")]
    assert capsys.readouterr().out == ""
    assert sys.stdout is not observability._destino
