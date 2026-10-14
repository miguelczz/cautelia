"""El flujo tal como sale por el cable (C-04).

Se prueba sobre el generador y no sobre la ruta: **un flujo abierto no termina**
--no tiene por que, hasta que la pestana se cierra-- y un cliente de prueba que
consume el cuerpo entero nunca devuelve el control. Que la ruta exista y con su verbo
lo comprueba `tests/integration/u13/test_api.py`; lo que sale por ella, esto.
"""

from __future__ import annotations

import asyncio

from untangle.chat.api import event_stream
from untangle.chat.wire import EventQueue


async def _leer(cola: EventQueue) -> list[bytes]:
    """Todo lo que el flujo emite hasta cerrarse. La cola se cierra antes."""
    return [trozo async for trozo in event_stream(cola)]


async def test_lo_primero_que_sale_es_el_intervalo_de_reconexion_y_un_latido() -> None:
    """Sin esto el flujo no dice nada hasta que pasan quince segundos, y en ese
    rato una conexion viva y una colgada se ven exactamente igual. Lo encontre
    porque la prueba de la ruta se quedaba esperando.
    """
    cola = EventQueue(stream_ref="chat-1")
    cola.close()

    trozos = await _leer(cola)

    assert trozos[0] == b"retry: 3000\n: open\n\n"


async def test_cada_evento_sale_con_su_identificador_creciente() -> None:
    """C-04: el navegador sabe si se perdio alguno porque son crecientes."""
    cola = EventQueue(stream_ref="chat-1")
    cola.publish({"kind": "turn.partial", "seq": 1, "text": "La"})
    cola.publish({"kind": "turn.final", "text": "La cláusula aplica."})
    cola.close()

    trozos = await _leer(cola)

    assert b"id: 1\n" in trozos[1]
    assert b"id: 2\n" in trozos[2]


async def test_el_evento_viaja_como_json_en_su_linea_de_datos() -> None:
    cola = EventQueue(stream_ref="chat-1")
    cola.publish({"kind": "turn.final", "text": "Anotado."})
    cola.close()

    trozos = await _leer(cola)

    assert b'data: {"kind":"turn.final","text":"Anotado."}\n\n' in trozos[1]


async def test_el_acento_viaja_intacto() -> None:
    """La mitad de las conversaciones son en espanol: un serializador que
    escapara los acentos dejaria la pantalla llena de barras invertidas."""
    cola = EventQueue(stream_ref="chat-1")
    cola.publish({"kind": "turn.final", "text": "La póliza sí lo cubre."})
    cola.close()

    trozos = await _leer(cola)

    assert "póliza sí".encode() in trozos[1]


async def test_el_flujo_sigue_abierto_despues_del_primer_evento() -> None:
    """No se cierra al entregar: una conversacion son varios turnos por la misma
    conexion, y un flujo que muriera con el primero obligaria a reconectar en cada
    respuesta."""
    cola = EventQueue(stream_ref="chat-1")
    cola.publish({"kind": "turn.partial", "seq": 1, "text": "x"})
    cola.publish({"kind": "turn.final", "text": "Anotado."})
    cola.close()

    trozos = await _leer(cola)

    assert trozos[0].startswith(b"retry:")
    assert sum(1 for t in trozos if t.startswith(b"id:")) == 2


async def test_el_flujo_termina_cuando_la_cola_se_cierra() -> None:
    """Y no antes: lo que lo cierra es la pestana, no un plazo del servidor."""
    cola = EventQueue(stream_ref="chat-1")
    cola.close()

    trozos = await asyncio.wait_for(_leer(cola), timeout=1)

    assert len(trozos) == 1, "solo el de apertura"
