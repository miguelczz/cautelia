"""La cola de eventos de una conversacion (C-04, SCALE-U13.2).

Lo que se comprueba aqui es la conducta que no se ve cuando todo va bien: dos
pestanas abiertas, una pestana que se fue sin avisar, y el latido que lo descubre.
"""

from __future__ import annotations

import asyncio

import pytest

from untangle.chat.wire import MAX_PENDING, EventQueue, QueueRegistry


def _evento(n: int) -> dict[str, object]:
    return {"kind": "turn.partial", "seq": n}


# --- La numeracion que C-04 exige ---------------------------------------------


def test_los_identificadores_crecen_dentro_de_la_conversacion() -> None:
    """C-04: el navegador sabe si se perdio alguno porque son crecientes."""
    cola = EventQueue(stream_ref="chat-1")

    assert [cola.next_id() for _ in range(3)] == [1, 2, 3]


def test_dos_conversaciones_numeran_por_su_cuenta() -> None:
    """Crecientes **dentro** de la conversacion, no del proceso: un contador
    global haria que el navegador viera huecos por culpa de otra pestana."""
    una, otra = EventQueue(stream_ref="a"), EventQueue(stream_ref="b")
    una.next_id()
    una.next_id()

    assert otra.next_id() == 1


# --- La pestana que se fue sin avisar (SCALE-U13.2) ---------------------------


def test_una_cola_que_nadie_consume_se_cierra_en_vez_de_retener_el_turno() -> None:
    """Una pestana viva consume en cuanto llegan; una oculta no consume ninguno.

    Llenarla significa que del otro lado no hay nadie, y esperar ahi retendria el
    turno que produjo el evento. Sin esto, una pestana oculta deja trabajo de
    fondo vivo que nadie va a leer.
    """
    cola = EventQueue(stream_ref="chat-1")

    for n in range(MAX_PENDING):
        assert cola.publish(_evento(n)), f"el evento {n} cabia"

    assert not cola.publish(_evento(MAX_PENDING)), "el que sobra descubre que no hay nadie"
    assert cola.closed


def test_publicar_en_una_cola_cerrada_no_levanta_ni_miente() -> None:
    """Devuelve `False` y ya. Levantar obligaria a cada llamador a envolverlo, y
    devolver `True` haria creer que el navegador lo recibio."""
    cola = EventQueue(stream_ref="chat-1")
    cola.close()

    assert not cola.publish(_evento(1))


# --- Una sola pestana por conversacion ----------------------------------------


def test_la_segunda_pestana_toma_la_cola_y_la_primera_se_cierra() -> None:
    """C-04: como mucho un flujo por pestana. Dos leyendo la misma cola se
    repartirian los eventos y cada una veria media conversacion."""
    registro = QueueRegistry()
    primera = registro.open("chat-1")
    segunda = registro.open("chat-1")

    assert primera.closed
    assert not segunda.closed
    assert registro.get("chat-1") is segunda


def test_dos_conversaciones_distintas_conviven() -> None:
    """El control positivo: si abrir una cerrara todas, el chat atenderia a una
    sola persona a la vez."""
    registro = QueueRegistry()
    una = registro.open("chat-1")
    otra = registro.open("chat-2")

    assert not una.closed
    assert not otra.closed
    assert registro.live == 2


# --- El mensaje que llega antes que su flujo (2026-10-13) ---------------------


def test_el_flujo_que_abre_despues_se_queda_con_lo_que_la_cola_reservada_guardo() -> None:
    """**El defecto**: el mensaje llegaba antes que el flujo, no habia cola y su respuesta
    no se publicaba en ninguna parte. Reservada la cola, la respuesta espera ahi y el
    flujo, al abrir, la recibe en vez de cerrarla y empezar otra vacia."""
    registro = QueueRegistry()
    reservada = registro.reserve("chat-1")
    assert reservada.publish({"kind": "turn.final", "message_id": "m1"})

    del_flujo = registro.open("chat-1")

    assert del_flujo is reservada
    assert not del_flujo.closed
    assert del_flujo.attached
    assert registro.get("chat-1") is del_flujo


async def test_lo_que_se_publico_antes_de_abrir_el_flujo_llega_en_orden() -> None:
    registro = QueueRegistry()
    registro.reserve("chat-1").publish({"kind": "turn.final", "message_id": "m1"})
    del_flujo = registro.open("chat-1")

    assert await del_flujo.next_event(heartbeat_after=0.05) == {
        "kind": "turn.final",
        "message_id": "m1",
    }


def test_una_cola_reservada_se_reutiliza_mientras_nadie_la_lea() -> None:
    """Dos mensajes seguidos antes de que abra el flujo van a la misma cola: si cada uno
    reservara la suya, el segundo cerraria al primero."""
    registro = QueueRegistry()

    primera = registro.reserve("chat-1")
    segunda = registro.reserve("chat-1")

    assert segunda is primera
    assert not primera.attached


def test_reservar_no_le_quita_la_cola_a_un_flujo_que_ya_la_lee() -> None:
    registro = QueueRegistry()
    leida = registro.open("chat-1")

    assert registro.reserve("chat-1") is leida
    assert not leida.closed


def test_una_cola_cerrada_no_se_reserva_de_nuevo_sino_que_se_reemplaza() -> None:
    """Publicar en una cerrada es perderlo: la pestana se fue y su flujo ya no existe."""
    registro = QueueRegistry()
    cerrada = registro.open("chat-1")
    cerrada.close()

    nueva = registro.reserve("chat-1")

    assert nueva is not cerrada
    assert not nueva.closed
    assert not nueva.attached


def test_la_cola_de_una_pestana_que_se_fue_no_se_adopta() -> None:
    """Solo se adopta una cola que nadie leia. La de un flujo que ya estuvo abierto es
    de una conexion muerta: sus eventos no son de la que reconecta, que vuelve a leer el
    caso, y heredarlos los repetiria en pantalla."""
    registro = QueueRegistry()
    vieja = registro.open("chat-1")
    vieja.publish({"kind": "turn.final", "message_id": "de-la-conexion-muerta"})

    nueva = registro.open("chat-1")

    assert nueva is not vieja
    assert vieja.closed
    assert nueva._events.empty()


def test_una_cola_reservada_que_se_llena_sin_flujo_se_cierra_como_cualquier_otra() -> None:
    """Un navegador que nunca abre su flujo no retiene turnos para siempre."""
    registro = QueueRegistry()
    reservada = registro.reserve("chat-1")

    for n in range(MAX_PENDING):
        assert reservada.publish(_evento(n))

    assert not reservada.publish(_evento(MAX_PENDING))
    assert reservada.closed
    # Y el flujo que llegue tarde ya no la adopta: abre la suya.
    assert registro.open("chat-1") is not reservada


# --- El latido ----------------------------------------------------------------


async def test_sin_eventos_la_espera_termina_para_mandar_un_latido() -> None:
    """Sin el, un intermediario corta una conversacion en silencio y el navegador
    se queda mirando una pantalla que nunca va a decir nada."""
    cola = EventQueue(stream_ref="chat-1")

    evento = await cola.next_event(heartbeat_after=0.01)

    assert evento is None


async def test_con_un_evento_esperando_se_entrega_sin_agotar_el_latido() -> None:
    """El control positivo: una cola que devolviera siempre `None` pasaria la de
    arriba y el chat no entregaria nunca nada."""
    cola = EventQueue(stream_ref="chat-1")
    cola.publish(_evento(1))

    evento = await asyncio.wait_for(cola.next_event(heartbeat_after=5), timeout=1)

    assert evento == {"kind": "turn.partial", "seq": 1}


async def test_cerrar_despierta_a_quien_estaba_esperando() -> None:
    """Sin el centinela, cerrar dejaria al flujo esperando su latido completo
    antes de enterarse, y la pestana veria la conversacion colgada ese rato."""
    cola = EventQueue(stream_ref="chat-1")

    async def cerrar_pronto() -> None:
        await asyncio.sleep(0.01)
        cola.close()

    async with asyncio.TaskGroup() as grupo:
        grupo.create_task(cerrar_pronto())
        evento = await asyncio.wait_for(cola.next_event(heartbeat_after=5), timeout=1)

    assert evento is None
    assert cola.closed


@pytest.mark.parametrize("veces", [1, 2, 3])
def test_cerrar_varias_veces_no_rompe(veces: int) -> None:
    """Lo cierra el flujo al terminar y tambien el registro al descartarlo: que
    las dos vias coincidan es normal, no un error."""
    cola = EventQueue(stream_ref="chat-1")
    for _ in range(veces):
        cola.close()

    assert cola.closed
