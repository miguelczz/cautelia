"""Lo que el fondo le lleva al chat va en el idioma en que se compuso (2026-10-11).

Una aseguradora que arranca en ingles y una persona que pregunta en espanol: el texto
llegaba en espanol y la tarjeta de la clausula rotulada en ingles, porque quien
entrega usaba el idioma de la conversacion y no el de la respuesta.
"""

from __future__ import annotations

from typing import Any

import pytest

from untangle.chat import api as chat_api
from untangle.chat import citation as chat_citation
from untangle.chat import session as chat_session


class _Escucha:
    language = "en"
    visitor_key_digest = "resumen-del-navegador"


class _Cola:
    def __init__(self) -> None:
        self.eventos: list[Any] = []

    def publish(self, evento: Any) -> bool:
        self.eventos.append(evento)
        return True


def _idioma_de(evento: Any) -> Any:
    """El idioma que lleva el evento, venga como diccionario o como objeto."""
    return evento["language"] if isinstance(evento, dict) else evento.language


def _armar(monkeypatch: pytest.MonkeyPatch) -> tuple[_Cola, list[str | None]]:
    cola = _Cola()
    pedidos: list[str | None] = []

    async def _listener_of(_tenant_id: str, _case_id: str) -> _Escucha:
        return _Escucha()

    async def _details_for(
        _tenant_id: str, _citations: Any, *, language: str | None = None
    ) -> tuple[()]:
        pedidos.append(language)
        return ()

    monkeypatch.setattr(chat_session, "listener_of", _listener_of)
    monkeypatch.setattr(chat_citation, "details_for", _details_for)
    monkeypatch.setattr(chat_api._COLAS, "get", lambda _flujo: cola)
    return cola, pedidos


async def test_la_respuesta_del_fondo_va_en_el_idioma_en_que_se_compuso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cola, pedidos = _armar(monkeypatch)

    entregado = await chat_api.CASE_NOTIFIER.notify(
        "una-aseguradora", "caso-1", text="En tu póliza…", citations=(object(),), language="es"
    )

    assert entregado is True
    # La tarjeta de la clausula se pide en el idioma de la respuesta, no en "en".
    assert pedidos == ["es"]
    [evento] = cola.eventos
    assert _idioma_de(evento) == "es"


async def test_sin_idioma_de_la_respuesta_se_usa_el_de_la_conversacion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _cola, pedidos = _armar(monkeypatch)

    await chat_api.CASE_NOTIFIER.notify(
        "una-aseguradora", "caso-1", text="Let me check.", citations=(object(),)
    )

    assert pedidos == ["en"]
