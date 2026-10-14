"""A donde va lo que el fondo calculo: primero a la llamada viva, si no al chat."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from untangle.chat import api as chat_api
from untangle.server import composition
from untangle.voice import answers as voice_answers

pytestmark = pytest.mark.anyio


@dataclass
class _Canal:
    hay_alguien: bool
    recibidos: list[str] = field(default_factory=list)

    async def notify(  # noqa: PLR0913 -- la firma del puerto CaseNotifier
        self,
        tenant_id: str,
        case_id: str,
        *,
        text: str,
        citations: tuple[object, ...] = (),
        suggestions: tuple[str, ...] = (),
        coverage_outcome: str | None = None,
        language: str | None = None,
    ) -> bool:
        del tenant_id, case_id, citations, suggestions, coverage_outcome
        self.recibidos.append(text)
        return self.hay_alguien


async def _avisar(
    monkeypatch: pytest.MonkeyPatch, *, en_llamada: bool, en_chat: bool
) -> tuple[bool, _Canal, _Canal]:
    llamada, chat = _Canal(en_llamada), _Canal(en_chat)
    monkeypatch.setattr(voice_answers, "CASE_NOTIFIER", llamada)
    monkeypatch.setattr(chat_api, "CASE_NOTIFIER", chat)
    entregado = await composition.CASE_NOTIFIER.notify("stonecroft", "case-1", text="hola")
    return entregado, llamada, chat


async def test_con_llamada_viva_se_dice_en_la_llamada_y_no_se_repite_en_el_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entregado, llamada, chat = await _avisar(monkeypatch, en_llamada=True, en_chat=True)

    assert entregado is True
    assert llamada.recibidos == ["hola"]
    assert chat.recibidos == []


async def test_sin_llamada_viva_llega_al_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    entregado, llamada, chat = await _avisar(monkeypatch, en_llamada=False, en_chat=True)

    assert entregado is True
    assert chat.recibidos == ["hola"]
    assert llamada.recibidos == ["hola"], "se le pregunto primero a la llamada"


async def test_si_nadie_escucha_se_dice_que_no_se_entrego(monkeypatch: pytest.MonkeyPatch) -> None:
    entregado, _, _ = await _avisar(monkeypatch, en_llamada=False, en_chat=False)

    assert entregado is False
