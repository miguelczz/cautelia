"""Derivar un caso avisa a quien lo atiende, por el puerto, sin que su fallo deshaga la derivacion."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from untangle.case_record import api as casos
from untangle.case_record.models import CaseState
from untangle.compliance.controls.api import HandoffReason
from untangle.orchestration import case_context, derivation_trigger

pytestmark = pytest.mark.anyio

AHORA = datetime(2026, 11, 4, 15, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _sin_oyente() -> Iterator[None]:
    derivation_trigger.install_derived_listener(None)
    yield
    derivation_trigger.install_derived_listener(None)


def _caso_en(monkeypatch: pytest.MonkeyPatch, *, deriva: bool) -> None:
    async def _get(_tenant: str, _case: str) -> object:
        return SimpleNamespace(state=CaseState.DECIDING)

    async def _apply(*_args: object, **_kwargs: object) -> object:
        if not deriva:
            raise casos.InvalidTransitionError("deciding -> derived: el caso ya esta cerrado")
        return object()

    monkeypatch.setattr(casos, "get_case", _get)
    monkeypatch.setattr(casos, "apply_transition", _apply)


async def _derivar() -> bool:
    return await case_context.derive_case(
        tenant_id="stonecroft",
        case_id="C-1",
        reason=HandoffReason.RULE,
        turn_id=None,
        now=AHORA,
    )


async def test_derivar_avisa_una_vez_con_el_caso(monkeypatch: pytest.MonkeyPatch) -> None:
    _caso_en(monkeypatch, deriva=True)
    avisos: list[tuple[str, str]] = []

    async def _oyente(tenant_id: str, case_id: str) -> None:
        avisos.append((tenant_id, case_id))

    derivation_trigger.install_derived_listener(_oyente)

    assert await _derivar() is True
    assert avisos == [("stonecroft", "C-1")]


async def test_si_la_transicion_se_rechaza_no_avisa(monkeypatch: pytest.MonkeyPatch) -> None:
    _caso_en(monkeypatch, deriva=False)
    avisos: list[str] = []

    async def _oyente(_tenant_id: str, case_id: str) -> None:
        avisos.append(case_id)

    derivation_trigger.install_derived_listener(_oyente)

    assert await _derivar() is False
    assert avisos == []


async def test_el_fallo_del_oyente_no_deshace_la_derivacion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _caso_en(monkeypatch, deriva=True)

    async def _oyente(_tenant_id: str, _case_id: str) -> None:
        raise RuntimeError("el oyente se cayo")

    derivation_trigger.install_derived_listener(_oyente)

    assert await _derivar() is True


async def test_sin_oyente_derivar_sigue_igual(monkeypatch: pytest.MonkeyPatch) -> None:
    _caso_en(monkeypatch, deriva=True)

    assert await _derivar() is True
