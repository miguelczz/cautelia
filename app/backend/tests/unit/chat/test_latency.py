"""La latencia del chat: los dos eventos que el panel de cifras nombra (AC4.16.3).

El panel dice que la latencia del chat se mide entre `message_sent` y `first_word`, y hasta
aqui el chat no emitia ninguno. Estas pruebas fijan **que cuenta como cada extremo**: lo que
se mide, y sobre todo lo que no --la frase de espera no es la primera palabra, y un error
tampoco--, porque una meta que mejora sin que la respuesta llegue antes es la que no sirve.
"""

from __future__ import annotations

import io
import json
import sys
import time
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest

from untangle import observability
from untangle.case_record.models import Origin
from untangle.chat import delivery, latency
from untangle.chat.wire import EventQueue
from untangle.orchestration.contracts import InboundTurn, TurnEvent

TEXTO_DE_LA_PERSONA = "Me chocaron por detras, mi placa es ABC123"
TEXTO_DE_LA_AGENTE = "Lamento lo ocurrido. Cuentame que paso."


class _Reloj:
    """Un reloj monotono que solo avanza cuando la prueba lo dice."""

    def __init__(self) -> None:
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora

    def pasar(self, segundos: float) -> None:
        self.ahora += segundos


class _Cola:
    """Una cola que recibe lo publicado y dice si lo acepto."""

    def __init__(self, *, acepta: bool = True) -> None:
        self.publicados: list[dict[str, Any]] = []
        self._acepta = acepta

    def publish(self, wire: dict[str, Any]) -> bool:
        if self._acepta:
            self.publicados.append(wire)
        return self._acepta


@pytest.fixture
def salida() -> Iterator[io.StringIO]:
    destino = io.StringIO()
    observability.set_stream(destino)
    yield destino
    observability.set_stream(sys.stdout)


def _eventos(salida: io.StringIO, nombre: str) -> list[dict[str, Any]]:
    lineas = (json.loads(linea) for linea in salida.getvalue().splitlines() if linea)
    return [e for e in lineas if e["event"] == nombre]


def _entrante(*, idioma: str = "es") -> InboundTurn:
    return InboundTurn(
        tenant_id="aseguradora-de-prueba",
        session_ref="chat-prueba",
        case_id=None,
        text=TEXTO_DE_LA_PERSONA,
        language=idioma,  # type: ignore[arg-type]
        channel="chat",
        received_at=datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
    )


def _final(texto: str = TEXTO_DE_LA_AGENTE) -> dict[str, Any]:
    return {"kind": "turn.final", "message_id": "m1", "text": texto}


# --- El extremo izquierdo: el mensaje que llega ---------------------------------


def test_al_empezar_el_turno_sale_message_sent_con_sus_identificadores(
    salida: io.StringIO,
) -> None:
    latency.start(_entrante(idioma="en"), clock=_Reloj())

    [evento] = _eventos(salida, latency.MESSAGE_SENT)
    assert evento["tenant_id"] == "aseguradora-de-prueba"
    assert evento["session_ref"] == "chat-prueba"
    assert evento["language"] == "en"
    assert evento["turn_ref"]
    assert datetime.fromisoformat(evento["at"]).tzinfo is not None


def test_message_sent_no_lleva_el_texto_de_la_persona(salida: io.StringIO) -> None:
    """ADR-013: tiempos e identificadores, nunca contenido. Es lo que cierra RT-14 para los
    eventos de latencia, igual que en la voz."""
    reloj = latency.start(_entrante(), clock=_Reloj())
    reloj.observe(_final())

    assert TEXTO_DE_LA_PERSONA not in salida.getvalue()
    assert "ABC123" not in salida.getvalue()
    assert TEXTO_DE_LA_AGENTE not in salida.getvalue()


def test_la_marca_de_llegada_de_la_ruta_cuenta_aunque_la_entrega_empiece_despues(
    salida: io.StringIO,
) -> None:
    """La ruta toma la hora **al entrar**, antes de admitir y contar el mensaje; esa espera
    tambien la vive quien escribe y entra en la latencia."""
    reloj = _Reloj()
    llego = reloj()
    reloj.pasar(0.4)  # la ruta admite y cuenta el mensaje

    medido = latency.start(_entrante(), since=llego, clock=reloj)
    reloj.pasar(0.3)
    medido.observe(_final())

    [primera] = _eventos(salida, latency.FIRST_WORD)
    assert primera["elapsed_ms"] == 700


# --- El extremo derecho: la primera palabra --------------------------------------


def test_first_word_mide_desde_el_envio_hasta_la_primera_respuesta(
    salida: io.StringIO,
) -> None:
    reloj = _Reloj()
    medido = latency.start(_entrante(), clock=reloj)
    reloj.pasar(1.25)

    medido.observe(_final())

    [evento] = _eventos(salida, latency.FIRST_WORD)
    assert evento["elapsed_ms"] == 1250
    assert evento["turn_ref"] == _eventos(salida, latency.MESSAGE_SENT)[0]["turn_ref"]
    assert evento["language"] == "es"
    assert evento["output"] == "turn.final"
    assert evento["after_waiting"] is False


def test_la_frase_de_espera_no_es_la_primera_palabra_y_queda_anotada(
    salida: io.StringIO,
) -> None:
    """Como la muletilla de la llamada: si la espera contara, la meta mejoraria sin que la
    respuesta llegara antes."""
    reloj = _Reloj()
    medido = latency.start(_entrante(), clock=reloj)
    reloj.pasar(0.2)
    medido.observe({"kind": "turn.waiting", "copy_key": "chat.waiting", "text": "Un momento"})
    assert _eventos(salida, latency.FIRST_WORD) == []

    reloj.pasar(2.0)
    medido.observe(_final())

    [evento] = _eventos(salida, latency.FIRST_WORD)
    assert evento["elapsed_ms"] == 2200
    assert evento["after_waiting"] is True


def test_un_error_no_es_la_primera_palabra_de_una_respuesta(salida: io.StringIO) -> None:
    medido = latency.start(_entrante(), clock=_Reloj())

    medido.observe({"kind": "turn.error", "code": "internal_error", "text": "Tuve un problema"})

    assert _eventos(salida, latency.FIRST_WORD) == []
    assert _eventos(salida, latency.MESSAGE_SENT) != [], "el turno sin pareja se ve, no se pierde"


@pytest.mark.parametrize("tipo", ["turn.partial", "turn.final", "turn.handoff"])
def test_un_parcial_el_texto_final_y_la_derivacion_llevan_la_respuesta(
    salida: io.StringIO, tipo: str
) -> None:
    medido = latency.start(_entrante(), clock=_Reloj())

    medido.observe({"kind": tipo, "text": TEXTO_DE_LA_AGENTE})

    [evento] = _eventos(salida, latency.FIRST_WORD)
    assert evento["output"] == tipo


def test_una_salida_sin_texto_no_es_una_palabra(salida: io.StringIO) -> None:
    medido = latency.start(_entrante(), clock=_Reloj())

    medido.observe(_final(""))

    assert _eventos(salida, latency.FIRST_WORD) == []


def test_solo_la_primera_respuesta_del_turno_se_mide(salida: io.StringIO) -> None:
    reloj = _Reloj()
    medido = latency.start(_entrante(), clock=reloj)
    reloj.pasar(0.5)
    medido.observe({"kind": "turn.partial", "text": "Lamento"})
    reloj.pasar(3.0)
    medido.observe(_final())

    [evento] = _eventos(salida, latency.FIRST_WORD)
    assert evento["elapsed_ms"] == 500


# --- La cola mirada: se mide lo que de verdad se publica -------------------------


def test_la_cola_mirada_publica_lo_mismo_y_mide_lo_publicado(salida: io.StringIO) -> None:
    cola = _Cola()
    medida = latency.measured(cola, _entrante(), clock=_Reloj())

    resultado = medida.publish(_final())

    assert resultado is True
    assert cola.publicados == [_final()]
    assert len(_eventos(salida, latency.FIRST_WORD)) == 1


def test_una_salida_que_la_cola_no_acepto_no_es_la_primera_palabra(
    salida: io.StringIO,
) -> None:
    """La pestana se fue: nadie leyo esa palabra."""
    medida = latency.measured(_Cola(acepta=False), _entrante(), clock=_Reloj())

    resultado = medida.publish(_final())

    assert resultado is False
    assert _eventos(salida, latency.FIRST_WORD) == []


# --- Cableado: lo mide la entrega, por cualquier camino por el que conteste ------


async def _sin_turno(turn: InboundTurn) -> AsyncIterator[TurnEvent]:
    """El grafo que no dice nada: estas pruebas sustituyen la entrega, no el grafo."""
    del turn
    eventos: tuple[TurnEvent, ...] = ()
    for evento in eventos:
        yield evento


async def test_la_entrega_mide_el_turno_aunque_conteste_por_cualquier_camino(
    monkeypatch: pytest.MonkeyPatch, salida: io.StringIO
) -> None:
    """`deliver` pone el reloj una sola vez; cada camino que contesta publica por la cola
    que recibe, sin repetir la marca. Aqui el camino es un doble que publica dos salidas."""

    async def camino(cola: Any, entrante: InboundTurn, **_: Any) -> delivery.Delivered:
        cola.publish({"kind": "turn.waiting", "copy_key": "chat.waiting", "text": "Un momento"})
        cola.publish(_final())
        cola.publish(_final("Otra cosa"))
        return delivery.Delivered(events=3, closed=True, turn_id=None, case_id=None)

    monkeypatch.setattr(delivery, "_entregar", camino)
    cola = EventQueue(stream_ref="navegador")

    await delivery.deliver(
        cola,
        _entrante(),
        handle_turn=_sin_turno,
        visitor_key_hash="clave",
        origin=Origin.PUBLIC_CHAT,
        received_monotonic=0.0,
    )

    [enviado] = _eventos(salida, latency.MESSAGE_SENT)
    [primera] = _eventos(salida, latency.FIRST_WORD)
    assert primera["turn_ref"] == enviado["turn_ref"]
    assert primera["after_waiting"] is True
    assert primera["output"] == "turn.final"


async def test_la_entrega_devuelve_la_latencia_que_midio_y_es_la_del_evento(
    monkeypatch: pytest.MonkeyPatch, salida: io.StringIO
) -> None:
    """Quien necesita la cifra --la corrida de evaluaciones-- la toma de la entrega y no la
    mide otra vez: es el mismo numero que `chat.first_word`, con el reloj monotono de verdad."""

    async def camino(cola: Any, entrante: InboundTurn, **_: Any) -> delivery.Delivered:
        cola.publish({"kind": "turn.waiting", "copy_key": "chat.waiting", "text": "Un momento"})
        cola.publish(_final())
        return delivery.Delivered(events=2, closed=True, turn_id=None, case_id=None)

    monkeypatch.setattr(delivery, "_entregar", camino)

    entregado = await delivery.deliver(
        EventQueue(stream_ref="navegador"),
        _entrante(),
        handle_turn=_sin_turno,
        visitor_key_hash="clave",
        origin=Origin.LOCAL_DEPLOYMENT,
        # El mensaje "llego" hace dos segundos: el reloj de verdad tiene que haberlo contado.
        received_monotonic=time.monotonic() - 2.0,
    )

    [primera] = _eventos(salida, latency.FIRST_WORD)
    assert entregado.first_word_ms == primera["elapsed_ms"]
    assert entregado.first_word_ms is not None
    assert entregado.first_word_ms >= 2000


@pytest.mark.parametrize(
    "salidas",
    [
        [{"kind": "turn.waiting", "copy_key": "chat.waiting", "text": "Un momento"}],
        [{"kind": "turn.error", "code": "internal_error", "text": "Tuve un problema"}],
        [_final("")],
        [],
    ],
    ids=["solo-espera", "solo-error", "sin-texto", "sin-nada"],
)
async def test_un_turno_sin_primera_palabra_no_deja_latencia(
    monkeypatch: pytest.MonkeyPatch, salidas: list[dict[str, Any]]
) -> None:
    """La frase de espera y el error no son la primera palabra: el turno no deja valor, y la
    cifra publicada no se mejora con turnos que no contestaron."""

    async def camino(cola: Any, entrante: InboundTurn, **_: Any) -> delivery.Delivered:
        for salida in salidas:
            cola.publish(salida)
        return delivery.Delivered(events=len(salidas), closed=True, turn_id=None, case_id=None)

    monkeypatch.setattr(delivery, "_entregar", camino)

    entregado = await delivery.deliver(
        EventQueue(stream_ref="navegador"),
        _entrante(),
        handle_turn=_sin_turno,
        visitor_key_hash="clave",
        origin=Origin.LOCAL_DEPLOYMENT,
    )

    assert entregado.first_word_ms is None


async def test_si_la_entrega_falla_el_turno_queda_sin_primera_palabra(
    monkeypatch: pytest.MonkeyPatch, salida: io.StringIO
) -> None:
    """Un turno roto deja `message_sent` sin pareja y el aviso de error del canal, que no es
    una palabra de la respuesta."""

    async def roto(cola: Any, entrante: InboundTurn, **_: Any) -> delivery.Delivered:
        raise RuntimeError("se rompio")

    monkeypatch.setattr(delivery, "_entregar", roto)
    cola = EventQueue(stream_ref="navegador")

    with pytest.raises(RuntimeError):
        await delivery.deliver(
            cola,
            _entrante(),
            handle_turn=_sin_turno,
            visitor_key_hash="clave",
            origin=Origin.PUBLIC_CHAT,
        )

    assert len(_eventos(salida, latency.MESSAGE_SENT)) == 1
    assert _eventos(salida, latency.FIRST_WORD) == []
