"""Espias sobre todo lo que cuesta dinero o toca un proveedor (NFR16.6, SEC-U6.9).

La salud, las sondas y el directorio del sitio prometen **no llamar a ningun
proveedor, no gastar y no consumir limites de visitantes**. La forma de probar
una promesa de "nunca" es poner, en cada puerta por la que se podria romper, algo
que haga fallar la prueba si alguien la cruza:

- los dos adaptadores de Gemini (generar y calcular embeddings) y la fabrica de
  transportes, que es la frontera de red;
- las cinco funciones del gasto y la cuota que cobran, reservan o consumen;
- el registro de hitos de la activacion (BR8.4: el chequeo no es una sesion).

Cada espia **levanta y ademas anota** su nombre: levantar hace fallar la llamada
en el acto, y la lista permite afirmar al final que nadie la cruzo, aunque el
codigo bajo prueba hubiera atrapado la excepcion.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from untangle.providers.adapters.gemini import api as gemini
from untangle.providers.adapters.gemini import transport as gemini_transport
from untangle.telemetry.activation import repository as activation_repository
from untangle.telemetry.spend import api as spend

#: Cada puerta espiada: donde vive y como se llama.
PUERTAS: tuple[tuple[object, str], ...] = (
    (gemini.GeminiTextGenerator, "generate"),
    (gemini.GeminiEmbedder, "embed"),
    (gemini_transport.GeminiTransportFactory, "create"),
    (spend, "record_spend"),
    (spend, "check_quota"),
    (spend, "budget_state"),
    (spend, "reserve_primary_voice"),
    (spend, "release_call_quota"),
    (activation_repository, "record"),
)


def _espia(nombre: str, llamadas: list[str]) -> Callable[..., Any]:
    def espia(*_: object, **__: object) -> Any:
        llamadas.append(nombre)
        msg = f"se llamo a '{nombre}', que la salud y el directorio no pueden tocar"
        raise AssertionError(msg)

    return espia


def instalar(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Pone un espia en cada puerta y devuelve la lista de llamadas registradas."""
    llamadas: list[str] = []
    for duenio, nombre in PUERTAS:
        etiqueta = f"{getattr(duenio, '__name__', type(duenio).__name__)}.{nombre}"
        monkeypatch.setattr(duenio, nombre, _espia(etiqueta, llamadas))
    return llamadas
