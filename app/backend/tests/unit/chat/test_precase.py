"""Lo hablado antes de abrir caso: lo que se guarda, lo que se reconstruye y lo que se ve.

Sin base: el punto unico de sesion se reemplaza por un doble que guarda las sentencias y sus
parametros. Lo que se comprueba es la conducta del modulo --que guarda tal como se escribio, en
orden, con el tope, ligando el texto como parametro-- y la del canal alrededor: que un fallo al
guardar o al leer no tumba el turno, y que la memoria del proceso manda sobre la base. El
aislamiento, la cascada y el tope contra PostgreSQL son de la prueba de integracion de U13.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from untangle import observability
from untangle.chat import delivery, precase
from untangle.compliance.redaction import api as redaccion
from untangle.orchestration.contracts import InboundTurn
from untangle.orchestration.nodes.intake import understanding

AHORA = datetime(2026, 11, 11, 15, 0, tzinfo=UTC)
ASEGURADORA = "aseguradora-a"


class _BaseDoble:
    """Un punto de sesion falso: registra lo ejecutado y responde las lecturas guardadas."""

    def __init__(self, filas: tuple[Mapping[str, Any], ...] = ()) -> None:
        self.filas = filas
        self.sesiones: list[str] = []
        self.ejecutadas: list[tuple[str, dict[str, Any]]] = []
        self.leidas: list[tuple[str, dict[str, Any]]] = []

    def namespace(self) -> SimpleNamespace:
        @asynccontextmanager
        async def session_for(tenant_id: str) -> AsyncIterator[object]:
            self.sesiones.append(tenant_id)
            yield object()

        async def execute_sql(_sesion: object, sentencia: str, **params: Any) -> int:
            self.ejecutadas.append((sentencia, params))
            return 1

        async def fetch_all(
            _sesion: object, sentencia: str, **params: Any
        ) -> tuple[Mapping[str, Any], ...]:
            self.leidas.append((sentencia, params))
            return self.filas

        return SimpleNamespace(
            session_for=session_for, execute_sql=execute_sql, fetch_all=fetch_all
        )


def _fila(n: int, hablante: str, texto: str) -> dict[str, Any]:
    return {
        "message_id": f"m{n}",
        "speaker": hablante,
        "text": texto,
        "language": "es",
        "created_at": AHORA.replace(second=n),
        "seq": n,
    }


@pytest.fixture
def base(monkeypatch: pytest.MonkeyPatch) -> _BaseDoble:
    doble = _BaseDoble()
    monkeypatch.setattr(precase, "db", doble.namespace())
    return doble


async def test_guarda_el_intercambio_en_orden_y_tal_como_se_escribio(base: _BaseDoble) -> None:
    """Persona primero, agente despues, en una sola sesion, con el texto sin tapar."""
    texto = "Mi póliza es POL-21 y me llamo Marcela Ríos"

    await precase.append_precase_exchange(
        tenant_id=ASEGURADORA,
        chat_session_id="chat-1",
        exchange=precase.Exchange(
            person_text=texto, agent_text="Claro, ¿en qué le ayudo?", language="es"
        ),
        now=AHORA,
    )

    assert base.sesiones == [ASEGURADORA], "las dos escrituras van en una sola transaccion"
    assert [p["speaker"] for _, p in base.ejecutadas] == ["person", "agent"]
    assert base.ejecutadas[0][1]["text"] == texto, "sin redactar (decision del 2026-10-30)"
    assert {p["tenant_id"] for _, p in base.ejecutadas} == {ASEGURADORA}
    assert {p["tope"] for _, p in base.ejecutadas} == {40}
    assert len({p["message_id"] for _, p in base.ejecutadas}) == 2


async def test_el_texto_viaja_como_parametro_y_nunca_dentro_de_la_sentencia(
    base: _BaseDoble,
) -> None:
    peligroso = "'); DROP TABLE chat_session; --"

    await precase.append_precase_exchange(
        tenant_id=ASEGURADORA,
        chat_session_id="chat-1",
        exchange=precase.Exchange(person_text=peligroso, agent_text="ok", language="es"),
        now=AHORA,
    )

    for sentencia, _ in base.ejecutadas:
        assert "DROP" not in sentencia
    assert base.ejecutadas[0][1]["text"] == peligroso


async def test_el_tope_es_de_cuarenta_mensajes_y_lo_aplica_la_sentencia() -> None:
    """El tope vive en la sentencia que inserta (una condicion sobre el conteo), de modo que ni
    la lectura previa ni el orden de llegada de dos turnos lo evitan."""
    assert precase.MAX_MESSAGES == 40
    assert "n.total < :tope" in precase._INSERTAR
    assert "ON CONFLICT DO NOTHING" in precase._INSERTAR


async def test_lee_los_mensajes_de_la_conversacion_en_su_forma(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doble = _BaseDoble((_fila(1, "person", "Hola"), _fila(2, "agent", "¿En qué le ayudo?")))
    monkeypatch.setattr(precase, "db", doble.namespace())

    cargados = await precase.load_precase_messages(tenant_id=ASEGURADORA, chat_session_id="chat-1")

    assert [(m.speaker, m.text) for m in cargados] == [
        ("person", "Hola"),
        ("agent", "¿En qué le ayudo?"),
    ]
    assert cargados[0].message_id == "m1"
    assert cargados[0].created_at == AHORA.replace(second=1)
    consulta, parametros = doble.leidas[0]
    assert "ORDER BY seq" in consulta
    assert parametros["tenant_id"] == ASEGURADORA
    assert parametros["chat_session_id"] == "chat-1"


async def test_con_last_pide_solo_los_ultimos(monkeypatch: pytest.MonkeyPatch) -> None:
    doble = _BaseDoble()
    monkeypatch.setattr(precase, "db", doble.namespace())

    await precase.load_precase_messages(tenant_id=ASEGURADORA, chat_session_id="chat-1", last=8)

    consulta, parametros = doble.leidas[0]
    assert "LIMIT :cantidad" in consulta
    assert parametros["cantidad"] == 8


# --- El canal alrededor ------------------------------------------------------


def _entrante(texto: str = "Hola, tengo una duda de mi póliza") -> InboundTurn:
    return InboundTurn(
        tenant_id=ASEGURADORA,
        session_ref="chat-1",
        case_id=None,
        text=texto,
        language="es",
        channel="chat",
        received_at=AHORA,
    )


class _Eventos:
    def __init__(self) -> None:
        self.emitidos: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, event: str, **fields: Any) -> None:
        self.emitidos.append((event, fields))


@pytest.fixture
def redactor(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Un redactor de juguete que tapa «@»: no depende de los modelos del detector real, que
    esta pieza no comprueba, y deja ver que el texto reconstruido pasa por el.

    Devuelve la lista de textos que recibio."""
    recibidos: list[str] = []

    def tapar(text: str, *, language: str) -> str:
        del language
        recibidos.append(text)
        return text.replace("@", "[ARROBA]")

    monkeypatch.setattr(redaccion, "redact", tapar)
    return recibidos


@pytest.fixture
def eventos(monkeypatch: pytest.MonkeyPatch) -> _Eventos:
    registro = _Eventos()
    monkeypatch.setattr(observability, "emit", registro)
    return registro


async def test_si_guardar_falla_el_turno_sigue_y_queda_registrado(
    monkeypatch: pytest.MonkeyPatch, eventos: _Eventos
) -> None:
    async def roto(**_: Any) -> None:
        raise ConnectionError("la base no contesta")

    monkeypatch.setattr(precase, "append_precase_exchange", roto)

    await delivery._guardar_sin_caso(_entrante(), "Claro, dígame.")  # no levanta

    assert [e for e, _ in eventos.emitidos] == ["chat.precase_save_failed"]
    assert eventos.emitidos[0][1]["error"] == "ConnectionError"
    assert "póliza" not in str(eventos.emitidos), "el texto de la persona no va al registro"


async def test_guardar_entrega_lo_dicho_sin_redactar(monkeypatch: pytest.MonkeyPatch) -> None:
    recibido: dict[str, Any] = {}

    async def captura(**kwargs: Any) -> None:
        recibido.update(kwargs)

    monkeypatch.setattr(precase, "append_precase_exchange", captura)

    await delivery._guardar_sin_caso(_entrante("Soy Marcela Ríos"), "Mucho gusto.")

    assert recibido["exchange"] == precase.Exchange(
        person_text="Soy Marcela Ríos", agent_text="Mucho gusto.", language="es"
    )
    assert recibido["chat_session_id"] == "chat-1"
    assert recibido["tenant_id"] == ASEGURADORA
    assert recibido["now"] == AHORA


@pytest.mark.usefixtures("catalogo_cargado")
async def test_la_memoria_del_proceso_manda_sobre_la_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    en_memoria = (understanding.HistoryLine(speaker="person", text="ya en memoria"),)
    monkeypatch.setattr(delivery, "_HISTORIA_SIN_CASO", {"chat-1": en_memoria})

    async def no_debe_leer(**_: Any) -> tuple[precase.PrecaseMessage, ...]:
        raise AssertionError("leyo la base teniendo la memoria")

    monkeypatch.setattr(precase, "load_precase_messages", no_debe_leer)

    assert await delivery._historia_previa(_entrante()) == en_memoria


@pytest.mark.usefixtures("redactor")
async def test_sin_memoria_reconstruye_las_ultimas_lineas_desde_la_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(delivery, "_HISTORIA_SIN_CASO", {})
    pedidos: list[dict[str, Any]] = []

    async def desde_la_base(**kwargs: Any) -> tuple[precase.PrecaseMessage, ...]:
        pedidos.append(kwargs)
        return (
            precase.PrecaseMessage("m1", "person", "Hola", "es", AHORA),
            precase.PrecaseMessage("m2", "agent", "¿En qué le ayudo?", "es", AHORA),
        )

    monkeypatch.setattr(precase, "load_precase_messages", desde_la_base)

    historia = await delivery._historia_previa(_entrante())

    assert [(linea.speaker, linea.text) for linea in historia] == [
        ("person", "Hola"),
        ("agent", "¿En qué le ayudo?"),
    ]
    assert pedidos[0]["last"] == delivery._MAXIMO_LINEAS_SIN_CASO
    assert pedidos[0]["chat_session_id"] == "chat-1"


async def test_lo_reconstruido_para_el_modelo_va_tapado_como_lo_de_memoria(
    monkeypatch: pytest.MonkeyPatch, redactor: list[str]
) -> None:
    """Lo guardado esta en claro, pero lo que ve el modelo se tapa como siempre."""
    monkeypatch.setattr(delivery, "_HISTORIA_SIN_CASO", {})

    async def desde_la_base(**_: Any) -> tuple[precase.PrecaseMessage, ...]:
        return (
            precase.PrecaseMessage("m1", "person", "Mi correo es ana@example.com", "es", AHORA),
        )

    monkeypatch.setattr(precase, "load_precase_messages", desde_la_base)

    historia = await delivery._historia_previa(_entrante())

    assert redactor == ["Mi correo es ana@example.com"]
    assert "@" not in historia[0].text


async def test_si_leer_falla_el_turno_sigue_sin_historia(
    monkeypatch: pytest.MonkeyPatch, eventos: _Eventos
) -> None:
    monkeypatch.setattr(delivery, "_HISTORIA_SIN_CASO", {})

    async def roto(**_: Any) -> tuple[precase.PrecaseMessage, ...]:
        raise ConnectionError("la base no contesta")

    monkeypatch.setattr(precase, "load_precase_messages", roto)

    assert await delivery._historia_previa(_entrante()) == ()
    assert [e for e, _ in eventos.emitidos] == ["chat.precase_load_failed"]
