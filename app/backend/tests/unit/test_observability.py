"""El sitio donde fallo algo, sin lo que decia el mensaje (2026-10-12)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from untangle import observability


def _definir(archivo: str, codigo: str) -> dict[str, Any]:
    """Ejecuta `codigo` como si viviera en `archivo`: sus marcos llevan esa ruta."""
    espacio: dict[str, Any] = {}
    exec(compile(codigo, archivo, "exec"), espacio)  # noqa: S102 -- codigo de la prueba, no de nadie
    return espacio


def _error_de(llamada: Callable[[], object]) -> BaseException:
    """El error que levanta `llamada`, sin el marco de esta prueba.

    El rastro empieza donde se atrapa. Si esta prueba viviera en una ruta con `/untangle/`
    (la del repositorio, cuando se llama asi), su propio marco contaria.
    """
    with pytest.raises(ValueError, match=r".") as capturado:
        llamada()
    return capturado.value.with_traceback(capturado.tb.tb_next)


def test_dice_el_archivo_y_la_linea_dentro_del_aplicativo() -> None:
    espacio = _definir(
        "/srv/app/src/untangle/voice/loop.py", "\n\ndef boom():\n    raise ValueError('x')\n"
    )

    assert observability.failure_location(_error_de(espacio["boom"])) == "voice/loop.py:4"


def test_nunca_lleva_el_mensaje_del_error() -> None:
    """El mensaje puede traer lo que dijo la persona; el archivo y la linea, no."""
    espacio = _definir(
        "/srv/app/src/untangle/voice/call.py", "def boom():\n    raise ValueError('placa ABC123')\n"
    )

    assert "ABC123" not in observability.failure_location(_error_de(espacio["boom"]))


def test_gana_el_marco_mas_interno_del_aplicativo() -> None:
    interna = _definir("/a/untangle/voice/b.py", "def interna():\n    raise ValueError('x')\n")
    externa = _definir("/a/untangle/orchestration/a.py", "def externa(f):\n    f()\n")

    error = _error_de(lambda: externa["externa"](interna["interna"]))

    assert observability.failure_location(error) == "voice/b.py:2"


def test_una_biblioteca_instalada_dentro_del_repositorio_no_cuenta() -> None:
    """El repositorio se llama `untangle`: su `.venv` tambien tiene `/untangle/` en la ruta."""
    ajeno = _definir(
        "/home/m/untangle/app/backend/.venv/lib/python3.13/site-packages/websockets/x.py",
        "def boom():\n    raise ValueError('x')\n",
    )
    propio = _definir(
        "/home/m/untangle/app/backend/src/untangle/voice/loop.py",
        "def llama(f):\n    f()\n",
    )

    solo_la_biblioteca = _error_de(ajeno["boom"])
    desde_el_aplicativo = _error_de(lambda: propio["llama"](ajeno["boom"]))

    assert observability.failure_location(solo_la_biblioteca) == "desconocido"
    # El aplicativo llamo a la biblioteca: el sitio es el de la llamada, no el de dentro.
    assert observability.failure_location(desde_el_aplicativo) == "voice/loop.py:2"


def test_sin_marco_del_aplicativo_dice_desconocido() -> None:
    assert observability.failure_location(ValueError("x")) == "desconocido"
