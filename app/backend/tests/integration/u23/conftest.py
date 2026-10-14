"""Lo que las pruebas de integracion de U23 necesitan en la base efimera.

La vista de comparacion **no tiene ruta propia** (FD-U23-1): habla tres veces por
las rutas del chat que ya existen. Asi que lo que se prueba aqui es el chat con el
dato de superficie puesto, contra la base de verdad, por HTTP.

El grafo entra por un doble --lo que se comprueba es la puerta, no la respuesta-- y
las tres aseguradoras son las que `tenancy.config` ya carga: ninguna se nombra a
mano.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastapi import FastAPI, Request, Response

from untangle.case_record import crypto
from untangle.chat import api as chat_api
from untangle.chat.wire import EventQueue
from untangle.copy_catalog import api as copy_api
from untangle.orchestration import contracts as c14
from untangle.server import composition
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend
from untangle.telemetry.traces import api as trazas
from untangle.tenancy import api as tenancy
from untangle.tenancy import ephemeral, session

#: Cuanto se espera a una entrega en vuelo al desmontar. Generoso a proposito:
#: lo que se evita con el es un fallo que aparece en la prueba siguiente.
ESPERA_DE_ENTREGA = 5.0

#: La galleta del visitante. Se nombra desde la ruta: si divergieran, estas pruebas
#: dejarian de probar la ruta real.
COOKIE = chat_api.COOKIE

#: Un instante fijo para los datos sembrados. El reloj entra por argumento: una
#: conducta que leyera el del proceso solo se podria probar esperando.
AHORA = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)

CLAVE_DE_CHAT = "marca-de-clave-de-chat-que-no-debe-salir-00023"
CLAVE_DE_BANDEJA = "marca-de-clave-de-bandeja-que-no-debe-salir-00023"
CLAVE_DE_ENLACES = "marca-de-clave-de-enlaces-que-no-debe-salir-000023"


async def _vaciar() -> None:
    for tenant_id in tenancy.available_ids():
        async with session.session_for(tenant_id) as sesion:
            await session.execute_sql(sesion, "DELETE FROM chat_rate_window")
            await session.execute_sql(sesion, "DELETE FROM chat_session")
            await session.execute_sql(sesion, "DELETE FROM case_record")


@pytest.fixture
async def base_de_u23(sesiones: ephemeral.EphemeralDatabase) -> AsyncIterator[None]:
    del sesiones
    await _vaciar()
    yield
    await _vaciar()


async def _sin_grafo(turn: c14.InboundTurn) -> AsyncIterator[c14.TurnEvent]:
    """Un grafo que contesta una frase. Lo que se prueba aqui es la puerta."""
    yield c14.FinalText(message_id="m1", text="Anotado.", language=turn.language)


@pytest.fixture(autouse=True)
def cifrador(monkeypatch: pytest.MonkeyPatch) -> Iterator[crypto.Cipher]:
    monkeypatch.setenv(crypto.KEY_ENV_VAR, crypto.generate_key())
    cipher = crypto.Cipher.from_settings()
    crypto.install(cipher)
    yield cipher
    crypto.reset()


@pytest.fixture
async def app(
    sesiones: ephemeral.EphemeralDatabase, demo_abierta: None, tmp_path: Path
) -> AsyncIterator[FastAPI]:
    ajustes = Settings(
        env="local",
        database_url=sesiones.app_url,
        commit_sha="abc1234",
        chat_model_api_key=CLAVE_DE_CHAT,
        staff_credential_signing_key=CLAVE_DE_BANDEJA,
        case_link_signing_key=CLAVE_DE_ENLACES,
    )
    construida = composition.build_app(ajustes, dist_dir=tmp_path)
    # El puerto del turno, enchufado con un doble: la raiz enchufa el de U12 y aqui
    # se cambia por argumento, que es lo que la inversion de dependencia deja hacer.
    chat_api.install_turn_handler(_sin_grafo)
    try:
        yield construida
    finally:
        await _esperar_entregas()
        await session.dispose()
        session.configure(sesiones.app_url)
        spend.reset()
        trazas.reset_summaries()
        copy_api.reset()


async def _esperar_entregas() -> None:
    """Espera las entregas en vuelo antes de desmontar la base.

    La ruta responde `202` y entrega el turno en una tarea aparte. Una prueba que
    termine con una entrega a medias deja la base desmontandose debajo de ella, y el
    fallo no aparece en esa prueba: aparece en el montaje de la siguiente, que es el
    peor sitio donde puede aparecer.
    """
    pendientes = {tarea for tarea in chat_api._ENTREGAS if not tarea.done()}
    if pendientes:
        await asyncio.wait(pendientes, timeout=ESPERA_DE_ENTREGA)


def cliente(app: FastAPI) -> httpx2.AsyncClient:
    transporte = httpx2.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx2.AsyncClient(transport=transporte, base_url="http://testserver")


def tres_aseguradoras() -> tuple[str, ...]:
    """Las tres que la configuracion versionada carga, en orden de identificador."""
    return tuple(sorted(tenancy.available_ids()))


async def abrir_flujo(tenant_id: str) -> Response:
    """Abre el flujo de eventos llamando a la ruta, y devuelve su respuesta.

    **Por su funcion y no por HTTP**: el transporte ASGI de las pruebas consume el
    cuerpo entero antes de devolver la respuesta, y un flujo de eventos no termina.
    Es la misma razon que ya escribio U13 en su prueba de las dos puertas.

    Hace falta abrirlo para poder comprobar **que se publica**: sin flujo abierto no
    hay cola donde publicar, asi que una prueba sin esto no distinguiria "no se
    publico la apertura" de "no habia donde publicarla".
    """
    rutas = {ruta.name: ruta for ruta in chat_api.router().routes}  # type: ignore[attr-defined]
    manejador = rutas["stream_chat"].endpoint  # type: ignore[attr-defined]
    peticion = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 1234)})
    respuesta: Response = await manejador(tenant_id, peticion, Response(), None)
    return respuesta


def galleta_de(respuesta: Response) -> str:
    """La galleta del visitante que una respuesta entrega."""
    for nombre, valor in respuesta.raw_headers:
        if nombre.lower() == b"set-cookie" and chat_api.COOKIE.encode() in valor:
            crudo = valor.decode()
            return crudo.split(";", 1)[0].split("=", 1)[1]
    msg = "la respuesta no entrego la galleta del visitante"
    raise AssertionError(msg)


def cola_de(galleta: str) -> EventQueue:
    """La cola viva de **ese navegador**, la del registro del propio modulo.

    Se mira el registro de verdad --y no una copia-- porque lo que se comprueba es
    que la ruta publique o no publique en la cola que el navegador escucha.

    La referencia es el resumen de la clave del navegador y no la conversacion: la
    cola es del navegador desde que el reinicio nocturno obligo a que lo fuera
    --una conversacion desaparece esa noche y la pestana sigue abierta-- y por eso
    este ayudante recibe la galleta.
    """
    # La cola es de ese navegador **con una aseguradora** (2026-10-10): la que
    # termine en su resumen. Con mas de una abierta, la prueba tiene que decir cual.
    resumen = tenancy.visitor_key_digest(galleta)
    suyas = [
        cola
        for referencia, cola in chat_api._COLAS._queues.items()
        if referencia.endswith(f":{resumen}")
    ]
    if len(suyas) != 1:
        msg = f"se esperaba un flujo abierto para ese navegador y hay {len(suyas)}"
        raise AssertionError(msg)
    return suyas[0]


async def eventos_de(cola: EventQueue, *, durante: float = 0.3) -> list[dict[str, Any]]:
    """Lo que la cola publico en ese rato, sin latidos.

    El plazo corto es el que distingue "no se publico" de "todavia no llego": la
    entrega del turno corre en una tarea aparte, asi que se espera un rato y se
    recoge lo que haya.
    """
    recogidos: list[dict[str, Any]] = []
    while True:
        try:
            evento = await asyncio.wait_for(cola.next_event(heartbeat_after=10), durante)
        except TimeoutError:
            return recogidos
        if evento is None:
            return recogidos
        recogidos.append(evento)
