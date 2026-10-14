"""La conversacion que estaba viva cuando el reinicio se llevo su caso (BR2.6).

Es la regla con el modo de fallo mas silencioso de la unidad, y el cableado que
lo cerro no fue el aviso: fue **de quien es la cola**. Mientras la cola de eventos
era de la conversacion, pasaba esto:

1. la pestana queda abierta escuchando la cola de su conversacion;
2. el reinicio nocturno borra la conversacion;
3. el visitante escribe, el servidor abre una conversacion nueva, busca **su**
   cola, no la encuentra, y responde `202`;
4. la respuesta se publica en una cola que nadie escucha, y el visitante **no
   vuelve a recibir nada** hasta recargar la pagina.

Con la cola atada al navegador, la misma pestana sigue oyendo: le llega el aviso
de que la demostracion se reinicio y, detras, la respuesta de su mensaje nuevo.

Las pruebas abren el flujo **por su funcion** y no por HTTP, por la misma razon
que U13 y U23 ya escribieron: el transporte ASGI de las pruebas consume el cuerpo
entero antes de devolver la respuesta, y un flujo de eventos no termina.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI, Request, Response

from untangle.chat import api as chat_api
from untangle.copy_catalog import api as copy_api
from untangle.demo_operations import api as demo
from untangle.server import composition
from untangle.tenancy import api as tenancy

from .conftest import aseguradora, cliente
from .test_window import _corrida, _sembrar

pytestmark = pytest.mark.usefixtures("base_de_u20", "sin_transporte")


async def _abrir_flujo(tenant_id: str) -> Response:
    """Abre el flujo de eventos de un navegador nuevo y devuelve su respuesta."""
    rutas = {ruta.name: ruta for ruta in chat_api.router().routes}  # type: ignore[attr-defined]
    manejador = rutas["stream_chat"].endpoint  # type: ignore[attr-defined]
    peticion = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 1234)})
    respuesta: Response = await manejador(tenant_id, peticion, Response(), None)
    return respuesta


def _galleta_de(respuesta: Response) -> str:
    for nombre, valor in respuesta.raw_headers:
        if nombre.lower() == b"set-cookie" and chat_api.COOKIE.encode() in valor:
            return valor.decode().split(";", 1)[0].split("=", 1)[1]
    msg = "la respuesta no entrego la galleta del visitante"
    raise AssertionError(msg)


def _cola_de(galleta: str) -> Any:
    cola = chat_api._COLAS.get(
        chat_api._flujo_de(aseguradora(), tenancy.visitor_key_digest(galleta))
    )
    assert cola is not None, "no hay flujo abierto para ese navegador"
    return cola


async def _eventos(cola: Any, *, durante: float = 0.3) -> list[dict[str, Any]]:
    """Lo que la cola publico en ese rato, sin latidos."""
    recogidos: list[dict[str, Any]] = []
    while True:
        try:
            evento = await asyncio.wait_for(cola.next_event(heartbeat_after=10), durante)
        except TimeoutError:
            return recogidos
        if evento is None:
            return recogidos
        recogidos.append(evento)


async def test_la_conversacion_viva_recibe_el_aviso_y_su_mensaje_abre_un_caso_nuevo(
    app: FastAPI,
) -> None:
    """Las dos mitades de BR2.6, en una sola corrida y en este orden.

    El reinicio corre **de verdad** --los nueve purgadores-- en medio de la
    conversacion, que es la unica forma de llegar al estado que la regla describe.
    """
    await _sembrar(_corrida(hace=timedelta(hours=1)))
    tenant_id = aseguradora()

    flujo = await _abrir_flujo(tenant_id)
    galleta = _galleta_de(flujo)
    cola = _cola_de(galleta)

    # El reinicio se lleva la conversacion de este navegador, con la pestana
    # abierta. El corte es ahora, como en la corrida nocturna.
    corrida = await _reiniciar()
    assert corrida.outcome.value == "succeeded"

    async with cliente(app) as http:
        http.cookies.set(chat_api.COOKIE, galleta)
        respuesta = await http.post(
            f"/api/chat/{tenant_id}/messages", json={"text": "me chocaron el carro"}
        )

    assert respuesta.status_code == 202, respuesta.text
    eventos = await _eventos(cola)
    await _esperar_las_entregas()
    avisos = [e for e in eventos if str(e.get("message_id", "")).startswith("demo-reset-")]
    assert len(avisos) == 1, f"se esperaba un aviso del reinicio y llegaron {eventos}"
    # En **el idioma de la conversacion**, que es el de la aseguradora y no uno
    # fijo: las tres tienen idioma por omision distinto.
    idioma = tenancy.require(tenant_id).default_language
    assert avisos[0]["text"] == copy_api.t(chat_api.RESET_NOTICE, locale=idioma)


async def test_el_aviso_no_sale_en_la_primera_conversacion_de_un_navegador(
    app: FastAPI,
) -> None:
    """El control que impide que el aviso se diga siempre.

    Sin esta prueba, un aviso publicado en cada conversacion nueva pasaria la de
    arriba: a quien llega por primera vez se le estaria diciendo que la
    demostracion se reinicio y que su caso anterior ya no existe, y no habia
    ninguno.
    """
    await _sembrar(_corrida(hace=timedelta(hours=1)))
    tenant_id = aseguradora()

    flujo = await _abrir_flujo(tenant_id)
    galleta = _galleta_de(flujo)
    cola = _cola_de(galleta)

    async with cliente(app) as http:
        http.cookies.set(chat_api.COOKIE, galleta)
        respuesta = await http.post(
            f"/api/chat/{tenant_id}/messages", json={"text": "me chocaron el carro"}
        )

    assert respuesta.status_code == 202, respuesta.text
    eventos = await _eventos(cola)
    await _esperar_las_entregas()
    assert [e for e in eventos if str(e.get("message_id", "")).startswith("demo-reset-")] == []
    # Y la apertura si sale: es lo que distingue "no se publico el aviso" de "no
    # se publico nada".
    assert [e for e in eventos if str(e.get("message_id", "")).startswith("opening-")] != []


async def _esperar_las_entregas() -> None:
    """Deja que las entregas en curso terminen antes de que la prueba acabe.

    El `POST` responde 202 y atiende el turno en una tarea aparte. Una prueba que
    termina con esa tarea a medias deja su conexion a la base en el aire, y la
    siguiente la encuentra cuando el motor ya se cerro: el aviso que sale es un
    `PytestUnraisableExceptionWarning` **en otra prueba**, que es el peor sitio
    donde buscarlo.
    """
    for tarea in list(chat_api._ENTREGAS):
        with contextlib.suppress(Exception):
            await tarea


async def _reiniciar() -> Any:
    from untangle.server import demo_reset

    return await demo_reset.reset_now(composition.PURGADORES, now=datetime.now(UTC))


def test_la_clave_del_aviso_es_la_que_declara_u20() -> None:
    """Las dos tablas que no se pueden importar entre si, comprobadas (BR2.6).

    `demo_operations` esta por encima del chat en el contrato de capas, asi que
    cada uno escribe su literal; sin esta prueba, cambiar la clave en uno dejaria
    al otro pidiendo una frase que el catalogo ya no tiene.
    """
    assert str(chat_api.RESET_NOTICE) == str(demo.RESET_NOTICE)
