"""A que caso y a que llamada se atribuye un gasto que no lleva turno (2026-10-09).

El turno ya deja su caso en el contexto de traza, y con eso se atribuye lo que
gasta el modelo. Pero en una llamada, la transcripcion y la voz corren **fuera**
del turno --escuchan y hablan todo el tiempo--, y su gasto quedaba sin caso, sin
aseguradora y sin llamada: el tablero de telemetria no podia decir cuanto costo
una llamada. Quien abre la llamada deja aqui su atribucion, y todo lo que se gaste
dentro de ella la hereda por el contexto, como el identificador de traza.

Es un objeto que cambia y no un valor fijo porque una llamada puede cambiar de
caso a mitad (decir "no" a retomar abre uno nuevo, BR6.4), y las tareas que
escuchan ya copiaron el contexto al nacer: si se reemplazara el valor, seguirian
viendo el caso viejo.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass
class Attribution:
    """La aseguradora, el caso y la llamada de lo que se gaste dentro."""

    tenant_id: str
    case_id: str | None
    call_id: str | None = None


_atribucion: ContextVar[Attribution | None] = ContextVar("untangle_spend_attribution", default=None)


@contextmanager
def attributed(
    *, tenant_id: str, case_id: str | None, call_id: str | None = None
) -> Iterator[Attribution]:
    """Todo lo que se gaste dentro de este bloque se atribuye a esto."""
    actual = Attribution(tenant_id=tenant_id, case_id=case_id, call_id=call_id)
    token = _atribucion.set(actual)
    try:
        yield actual
    finally:
        _atribucion.reset(token)


def current() -> Attribution | None:
    return _atribucion.get()


def switch_case(case_id: str) -> None:
    """La llamada sigue, con otro caso. Lo ven tambien las tareas ya lanzadas."""
    actual = _atribucion.get()
    if actual is not None:
        actual.case_id = case_id


__all__ = ["Attribution", "attributed", "current", "switch_case"]
