"""T1 bajo dos turnos en vuelo (`_ensure_capturing`).

Dos turnos del mismo caso leen `open` a la vez y los dos intentan `open ->
capturing`; el segundo recibe la transicion rechazada. Hasta el 2026-10-06 eso
tumbaba el turno entero y la persona leia la frase de error por haber escrito
mientras la agente aun respondia. La colision no es un fallo: el caso ya esta
donde tiene que estar.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest

from untangle.case_record import api as casos
from untangle.case_record.models import CaseState
from untangle.orchestration import case_context

pytestmark = pytest.mark.anyio

AHORA = datetime(2026, 10, 6, 20, 0, tzinfo=UTC)


def _rechaza(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _apply(*_args: object, **_kwargs: object) -> object:
        raise casos.InvalidTransitionError("open -> capturing: el caso ya esta en capturing")

    monkeypatch.setattr(casos, "apply_transition", _apply)


def _releido(monkeypatch: pytest.MonkeyPatch, estado: CaseState) -> None:
    async def _get(_tenant: str, _case: str) -> object:
        return SimpleNamespace(state=estado)

    monkeypatch.setattr(casos, "get_case", _get)


async def test_si_el_otro_turno_ya_hizo_t1_este_sigue_con_el_estado_real(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _rechaza(monkeypatch)
    _releido(monkeypatch, CaseState.CAPTURING)
    # Solo se lee `.state`; un objeto con ese campo basta y no obliga a armar un caso entero.
    abierto = cast("casos.CaseView", SimpleNamespace(state=CaseState.OPEN))

    estado = await case_context._ensure_capturing("stonecroft", "C-1", abierto, now=AHORA)

    assert estado is CaseState.CAPTURING


async def test_un_rechazo_de_verdad_sigue_siendo_un_rechazo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si al releer el caso sigue en `open`, nadie hizo T1 y el rechazo no era una colision."""
    _rechaza(monkeypatch)
    _releido(monkeypatch, CaseState.OPEN)
    # Solo se lee `.state`; un objeto con ese campo basta y no obliga a armar un caso entero.
    abierto = cast("casos.CaseView", SimpleNamespace(state=CaseState.OPEN))

    with pytest.raises(casos.InvalidTransitionError):
        await case_context._ensure_capturing("stonecroft", "C-1", abierto, now=AHORA)
