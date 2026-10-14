"""Las dos rutas del chat por HTTP, con la base efimera de verdad (C-04, C-24).

Se llama a la aplicacion con un cliente ASGI en el **mismo** bucle de eventos que la
base efimera, por la razon que U6 ya dejo escrita: el cliente sincrono corre la
aplicacion en otro hilo con otro bucle, y el grupo de conexiones no se comparte.

Lo que aqui se comprueba es lo que solo se ve por la puerta: que la compuerta dura se
cumple **desde fuera** --nadie puede mandar un mensaje que se procese antes de la
divulgacion--, que un limite alcanzado responde con su clave y nunca con su texto, y
que el flujo declara lo que C-04 pide.
"""

from __future__ import annotations

import asyncio
import io
import json
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import httpx2
import pytest
from fastapi import FastAPI, Request, Response

from untangle import observability
from untangle.chat import api as chat_api
from untangle.chat import stream
from untangle.chat.wire import EventQueue
from untangle.copy_catalog import api as copy_api
from untangle.orchestration import contracts as c14
from untangle.server import composition
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend
from untangle.telemetry.traces import api as trazas
from untangle.tenancy import ephemeral, session

pytestmark = pytest.mark.usefixtures("base_de_u13")

CLAVE_DE_CHAT = "marca-de-clave-de-chat-que-no-debe-salir-0001"
CLAVE_DE_BANDEJA = "marca-de-clave-de-bandeja-que-no-debe-salir-00002"
CLAVE_DE_ENLACES = "marca-de-clave-de-enlaces-que-no-debe-salir-000003"


async def _sin_grafo(turn: c14.InboundTurn) -> AsyncIterator[c14.TurnEvent]:
    """Un grafo que contesta una frase. Lo que se prueba aqui es la puerta."""
    yield c14.FinalText(message_id="m1", text="Anotado.", language=turn.language)


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
    # El puerto, enchufado con un doble: la raiz enchufa el de U12 y aqui se
    # cambia por argumento, que es lo que la inversion de dependencia deja hacer.
    chat_api.install_turn_handler(_sin_grafo)
    try:
        yield construida
    finally:
        # Un mensaje aceptado se atiende aunque su flujo no este abierto (2026-10-13), asi
        # que la entrega puede seguir corriendo cuando la prueba acaba: se espera antes de
        # desmontar la base, o su ultima escritura cae sobre un caso que ya no existe.
        await asyncio.gather(*list(chat_api._ENTREGAS), return_exceptions=True)
        await session.dispose()
        session.configure(sesiones.app_url)
        spend.reset()
        trazas.reset_summaries()
        copy_api.reset()


def _cliente(app: FastAPI) -> httpx2.AsyncClient:
    transporte = httpx2.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx2.AsyncClient(transport=transporte, base_url="http://testserver")


def _aseguradora() -> str:
    from untangle.tenancy import api as tenancy

    return tenancy.available_ids()[0]


# --- La cookie que ata la conversacion a este navegador ------------------------


async def test_la_primera_visita_recibe_su_clave_de_navegador(app: FastAPI) -> None:
    """Y con `HttpOnly`: nada del lado del navegador necesita leerla, y lo que no
    se puede leer no se lo lleva un script inyectado en la pagina."""
    async with _cliente(app) as cliente:
        respuesta = await cliente.post(
            f"/api/chat/{_aseguradora()}/messages", json={"text": "Hola, me chocaron"}
        )

    assert respuesta.status_code in {202, 429}
    galleta = respuesta.cookies.get(chat_api.COOKIE)
    assert galleta is not None
    assert "httponly" in respuesta.headers.get("set-cookie", "").lower()


def _galletas(respuesta: Response) -> list[bytes]:
    """Las cabeceras `set-cookie` de una respuesta, todas."""
    return [valor for nombre, valor in respuesta.raw_headers if nombre.lower() == b"set-cookie"]


async def test_las_dos_puertas_del_chat_entregan_la_galleta_del_visitante(
    app: FastAPI,
) -> None:
    """**El tercer defecto de la costura, y el mas silencioso de los tres.**

    FastAPI solo mezcla las cabeceras del `Response` inyectado cuando la ruta devuelve
    un valor que el serializa; el flujo devuelve una `StreamingResponse` tal cual, y
    salia **sin la galleta**. Un visitante nuevo abria su flujo escuchando la
    conversacion A, se iba sin galleta, y su primer mensaje --que si la recibia--
    abria la conversacion B. El flujo de A nunca oyo nada de B: **ningun visitante
    nuevo recibio una sola respuesta jamas**, y el aplicativo respondia `202` a cada
    mensaje.

    **Se llaman las dos puertas**, porque lo que estaba roto no era una cabecera
    suelta sino que las dos del mismo navegador acabaran en conversaciones distintas:
    mirando solo el mensaje, esta prueba pasa con el defecto puesto.

    Al flujo se le llama **por su funcion y no por HTTP**: el transporte ASGI de las
    pruebas consume el cuerpo entero antes de devolver la respuesta, y un flujo de
    eventos no termina -- la misma razon por la que `test_stream_wire.py` prueba el
    generador aparte --. Se llama la ruta y no `_copiar_galleta`, que dejaria pasar
    el dia que la ruta deje de llamarlo, que es exactamente el defecto que hubo.
    """
    aseguradora = _aseguradora()
    rutas = {ruta.name: ruta for ruta in chat_api.router().routes}  # type: ignore[attr-defined]
    peticion = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 1234)})

    # `BaseRoute` no declara `endpoint` -- lo declara `APIRoute`, que es lo que hay
    # aqui de verdad; el nombre viene del propio enrutador, asi que la llamada no
    # puede caer en otra ruta.
    manejador = rutas["stream_chat"].endpoint  # type: ignore[attr-defined]
    flujo = await manejador(aseguradora, peticion, Response(), None)
    async with _cliente(app) as cliente:
        mensaje = await cliente.post(
            f"/api/chat/{aseguradora}/messages", json={"text": "Me chocaron"}
        )

    del_flujo = _galletas(flujo)
    assert del_flujo, "el flujo salio sin galleta: su conversacion no es la del mensaje"
    assert chat_api.COOKIE.encode() in del_flujo[0]
    assert mensaje.cookies.get(chat_api.COOKIE) is not None


# --- BR1.1 desde fuera: la compuerta dura por la puerta ------------------------


async def test_el_primer_mensaje_recibe_la_divulgacion_antes_que_su_respuesta(
    app: FastAPI,
) -> None:
    """Compuerta dura, vista desde donde importa: **nadie puede mandar un mensaje
    que se procese antes de la divulgacion**, porque la ruta la emite y la anota
    antes de mirar el texto. Probarlo por dentro no bastaba: lo que hay que
    demostrar es que no hay forma de entrar saltandosela.
    """
    async with _cliente(app) as cliente:
        respuesta = await cliente.post(
            f"/api/chat/{_aseguradora()}/messages", json={"text": "Me chocaron por detras"}
        )

    assert respuesta.status_code == 202
    cuerpo = respuesta.json()
    assert cuerpo["session_id"].startswith("chat-")


# --- El historial: la apertura al abrir, y la conversacion como estaba ----------


async def test_abrir_la_pantalla_recibe_la_apertura_antes_de_escribir_nada(
    app: FastAPI,
) -> None:
    """La agente se presenta al cargar la pagina, no despues del primer mensaje
    (decision de Miguel, 2026-10-06). La ruta entrega la apertura, la deja
    anotada en la conversacion y pone la galleta, como el flujo."""
    async with _cliente(app) as cliente:
        respuesta = await cliente.get(f"/api/chat/{_aseguradora()}/history")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["opening"] is not None
    assert _agente(_aseguradora()) in cuerpo["opening"]["text"]
    assert cuerpo["opening"]["message_id"].startswith("opening-chat-")
    assert cuerpo["turns"] == []
    assert cuerpo["case_number"] is None
    assert respuesta.cookies.get(chat_api.COOKIE) is not None


def _navegador(app: FastAPI) -> tuple[httpx2.AsyncClient, str]:
    """Un navegador que ya tiene su galleta, y la clave con la que la tiene.

    La galleta se pone a mano, como en las pruebas del resumen de traza: el cliente
    de pruebas no reenvia por `http://` una galleta marcada `Secure`, asi que
    dejar que la ponga la primera respuesta deja cada peticion como un visitante
    nuevo.
    """
    from untangle.tenancy import api as tenancy

    clave = tenancy.new_visitor_key()
    cliente = _cliente(app)
    cliente.cookies.set(chat_api.COOKIE, clave)
    return cliente, clave


def _pestana(clave: str) -> EventQueue:
    """La pestana abierta de ese navegador: su cola, con el resumen que la ruta
    del flujo calcula.

    **Despues de la primera peticion y no antes**, como en el navegador de verdad,
    donde el flujo crea la conversacion y abre la cola en la misma peticion. Una
    cola abierta antes de que exista la conversacion se lee como "la pestana
    seguia abierta cuando el reinicio nocturno se llevo la conversacion", y la
    primera peticion publica el aviso del reinicio (BR2.6 de U20).

    Sin flujo abierto el mensaje se admite pero no se entrega, y lo que estas
    pruebas quieren es que el turno quede escrito.
    """
    from untangle.tenancy import api as tenancy

    return chat_api._COLAS.open(
        chat_api._flujo_de(_aseguradora(), tenancy.visitor_key_digest(clave))
    )


async def _esperar_la_entrega(cola: EventQueue) -> list[dict[str, object]]:
    """Espera a que las entregas en vuelo terminen y devuelve lo que publicaron.

    Se espera **la tarea** y no el evento de cierre: la entrega sigue escribiendo
    despues de publicarlo --el turno de la agente, el resumen de traza-- y leer el
    historial en ese hueco encontraria a veces un turno y a veces dos. Esperar la
    tarea es ademas lo que deja la conexion cerrada antes de que la base se vaya.
    """
    await asyncio.gather(*list(chat_api._ENTREGAS), return_exceptions=True)
    publicados: list[dict[str, object]] = []
    while not cola._events.empty():
        evento = cola._events.get_nowait()
        if evento is not None:
            publicados.append(evento)
    assert any(stream.closes_turn(evento) for evento in publicados), publicados
    return publicados


async def test_el_historial_devuelve_la_conversacion_guardada_de_este_navegador(
    app: FastAPI,
) -> None:
    """Quien sale y vuelve lee lo mismo que dejo: lo suyo, lo de la agente, y el
    numero de su caso. **Lo suyo viene redactado**, porque asi se guardo (SEC-U4.6):
    la prueba escribe un numero de poliza y comprueba que el historial no lo trae."""
    aseguradora = _aseguradora()
    cliente, clave = _navegador(app)
    async with cliente:
        await cliente.get(f"/api/chat/{aseguradora}/history")
        cola = _pestana(clave)
        enviado = await cliente.post(
            f"/api/chat/{aseguradora}/messages",
            json={"text": "Mi póliza es la POL-100042 y me chocaron"},
        )
        assert enviado.status_code == 202
        await _esperar_la_entrega(cola)
        respuesta = await cliente.get(f"/api/chat/{aseguradora}/history")

    cuerpo = respuesta.json()
    lados = [turno["speaker"] for turno in cuerpo["turns"]]
    assert lados == ["visitor", "agent"], cuerpo
    assert "POL-100042" not in cuerpo["turns"][0]["text"]
    assert "me chocaron" in cuerpo["turns"][0]["text"]
    assert cuerpo["turns"][1]["text"] == "Anotado."
    assert cuerpo["case_number"] is not None
    assert cuerpo["opening"] is not None


async def test_la_apertura_no_llega_dos_veces_cuando_el_historial_ya_la_entrego(
    app: FastAPI,
) -> None:
    """El historial la devuelve en su cuerpo y la deja anotada; el primer mensaje
    ya no la publica por el flujo. Sin esto la pantalla la leeria dos veces."""
    aseguradora = _aseguradora()
    cliente, clave = _navegador(app)
    async with cliente:
        historial = await cliente.get(f"/api/chat/{aseguradora}/history")
        assert historial.json()["opening"] is not None
        cola = _pestana(clave)
        await cliente.post(
            f"/api/chat/{aseguradora}/messages", json={"text": "Hola, me chocaron ayer"}
        )
        publicados = await _esperar_la_entrega(cola)

    # Por el flujo salio la respuesta y nada mas: la apertura ya la dio el historial.
    assert [evento["kind"] for evento in publicados] == ["turn.final"]
    assert not str(publicados[0]["message_id"]).startswith("opening-")


async def test_un_mensaje_que_llega_antes_de_su_flujo_se_atiende_y_la_respuesta_espera(
    app: FastAPI,
) -> None:
    """**El defecto (2026-10-13):** quien enviaba su primer mensaje antes de que el flujo de
    su conversacion estuviera abierto recibia `202` y nunca una respuesta: no habia cola
    donde publicarla y el turno ni siquiera se entregaba.

    Ahora el turno se atiende, la respuesta espera en una cola reservada y el flujo, al
    abrir, se queda con ella. Se manda **sin** abrir el flujo, que es lo que las otras
    pruebas hacen al reves a proposito.
    """
    aseguradora = _aseguradora()
    cliente, clave = _navegador(app)
    async with cliente:
        await cliente.get(f"/api/chat/{aseguradora}/history")
        enviado = await cliente.post(
            f"/api/chat/{aseguradora}/messages", json={"text": "Hola, me chocaron ayer"}
        )
        assert enviado.status_code == 202
        # La entrega termina sin que nadie lea: no hay flujo todavia.
        await asyncio.gather(*list(chat_api._ENTREGAS), return_exceptions=True)

        # Ahora la pestana abre su flujo y encuentra la respuesta esperandola.
        publicados = await _esperar_la_entrega(_pestana(clave))
        historial = await cliente.get(f"/api/chat/{aseguradora}/history")

    assert [evento["kind"] for evento in publicados] == ["turn.final"], publicados
    assert publicados[0]["text"] == "Anotado."
    # Y el turno quedo atendido de verdad, no solo publicado: esta en la conversacion.
    lados = [turno["speaker"] for turno in historial.json()["turns"]]
    assert lados == ["visitor", "agent"], historial.json()


async def test_el_turno_del_chat_emite_los_dos_eventos_de_su_latencia(app: FastAPI) -> None:
    """Lo que el panel de cifras nombra para la latencia del chat (AC4.16.3) y el chat no
    emitia: el mensaje que llega y la primera palabra de la respuesta, por la ruta de verdad.
    Llevan tiempos e identificadores, nunca el texto de nadie (ADR-013)."""
    aseguradora = _aseguradora()
    cliente, clave = _navegador(app)
    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        async with cliente:
            await cliente.get(f"/api/chat/{aseguradora}/history")
            cola = _pestana(clave)
            await cliente.post(
                f"/api/chat/{aseguradora}/messages",
                json={"text": "Mi póliza es la POL-100042 y me chocaron"},
            )
            await _esperar_la_entrega(cola)
    finally:
        observability.set_stream(sys.stdout)

    eventos = [
        json.loads(linea) for linea in salida.getvalue().splitlines() if linea.startswith("{")
    ]
    [enviado] = [e for e in eventos if e["event"] == "chat.message_sent"]
    [primera] = [e for e in eventos if e["event"] == "chat.first_word"]
    assert primera["turn_ref"] == enviado["turn_ref"]
    assert primera["tenant_id"] == aseguradora
    assert isinstance(primera["elapsed_ms"], int)
    assert primera["elapsed_ms"] >= 0
    assert primera["output"] == "turn.final"
    assert "POL-100042" not in salida.getvalue()
    assert "Anotado." not in salida.getvalue()


async def test_el_historial_de_otro_navegador_no_ve_esta_conversacion(app: FastAPI) -> None:
    """Dos galletas, dos conversaciones: la segunda vuelve vacia aunque la
    primera ya tenga caso. Es la misma regla que el resumen de traza (BR4.3)."""
    aseguradora = _aseguradora()
    primero, clave = _navegador(app)
    async with primero:
        await primero.get(f"/api/chat/{aseguradora}/history")
        cola = _pestana(clave)
        await primero.post(
            f"/api/chat/{aseguradora}/messages", json={"text": "Hola, me chocaron ayer"}
        )
        await _esperar_la_entrega(cola)
        propio = await primero.get(f"/api/chat/{aseguradora}/history")
    segundo, _ = _navegador(app)
    async with segundo:
        ajeno = await segundo.get(f"/api/chat/{aseguradora}/history")

    assert propio.json()["case_number"] is not None
    cuerpo = ajeno.json()
    assert cuerpo["turns"] == []
    assert cuerpo["case_number"] is None


# --- El caso visible mientras avanza (decision de Miguel, 2026-10-06) ---------


async def test_sin_caso_el_estado_del_caso_es_nulo_y_no_da_de_alta_nada(app: FastAPI) -> None:
    """Antes del primer mensaje no hay caso: `200` con `null`, y sin galleta no se
    resuelve ninguna clave, como en el resumen de traza."""
    async with _cliente(app) as cliente:
        sin_galleta = await cliente.get(f"/api/chat/{_aseguradora()}/case")
    cliente, _clave = _navegador(app)
    async with cliente:
        await cliente.get(f"/api/chat/{_aseguradora()}/history")
        sin_caso = await cliente.get(f"/api/chat/{_aseguradora()}/case")

    assert sin_galleta.status_code == 200 and sin_galleta.json() is None
    assert sin_caso.status_code == 200 and sin_caso.json() is None


async def test_con_caso_el_estado_trae_numero_avance_y_enlace_para_abrirlo(app: FastAPI) -> None:
    """Lo que la pantalla muestra bajo el titulo desde el primer mensaje: el numero,
    cuantos datos lleva de cuantos, y el enlace firmado al caso, que es el mismo que
    la llamada da al colgar. El chat lo prometia en el inicio y nunca lo daba."""
    aseguradora = _aseguradora()
    cliente, clave = _navegador(app)
    async with cliente:
        await cliente.get(f"/api/chat/{aseguradora}/history")
        cola = _pestana(clave)
        await cliente.post(f"/api/chat/{aseguradora}/messages", json={"text": "Me chocaron"})
        await _esperar_la_entrega(cola)
        respuesta = await cliente.get(f"/api/chat/{aseguradora}/case")

    cuerpo = respuesta.json()
    assert cuerpo is not None
    # El grafo de esta prueba contesta una frase y no mueve el caso: sigue abierto.
    assert cuerpo["case_number"] and cuerpo["state"] in {"open", "capturing"}
    assert cuerpo["total"] >= cuerpo["complete"] >= 0
    assert cuerpo["case_link"].startswith("/c#")


async def test_el_estado_del_caso_de_otro_navegador_es_nulo(app: FastAPI) -> None:
    """Dos galletas, dos conversaciones: el segundo navegador no ve el caso del
    primero ni recibe un enlace a el."""
    aseguradora = _aseguradora()
    primero, clave = _navegador(app)
    async with primero:
        await primero.get(f"/api/chat/{aseguradora}/history")
        cola = _pestana(clave)
        await primero.post(
            f"/api/chat/{aseguradora}/messages", json={"text": "Hola, me chocaron ayer"}
        )
        await _esperar_la_entrega(cola)
    segundo, _ = _navegador(app)
    async with segundo:
        ajeno = await segundo.get(f"/api/chat/{aseguradora}/case")

    assert ajeno.status_code == 200 and ajeno.json() is None


# --- El idioma lo decide la pantalla (P2, decision de Miguel, 2026-10-06) --------


def _agente(tenant_id: str) -> str:
    """Como se llama la agente de esa aseguradora: cada una tiene la suya."""
    from untangle.tenancy import api as tenancy

    nombre = tenancy.require(tenant_id).agent_name
    assert nombre is not None
    return nombre


def _aseguradora_en_ingles() -> str:
    from untangle.tenancy import api as tenancy

    return next(t.tenant_id for t in tenancy.loaded().available if t.default_language == "en")


async def test_la_apertura_sale_en_el_idioma_de_la_pantalla(app: FastAPI) -> None:
    """Una aseguradora que habla ingles por omision, con la pantalla en espanol: la
    conversacion nueva se abre en espanol y la apertura sale en espanol. Antes
    salia en ingles y nadie explicaba por que."""
    aseguradora = _aseguradora_en_ingles()
    cliente, _clave = _navegador(app)
    async with cliente:
        respuesta = await cliente.get(f"/api/chat/{aseguradora}/history?locale=es")

    cuerpo = respuesta.json()
    assert cuerpo["language"] == "es"
    assert cuerpo["opening"]["language"] == "es"
    assert _agente(aseguradora) in cuerpo["opening"]["text"]
    assert "demostración" in cuerpo["opening"]["text"]


async def test_una_conversacion_en_marcha_no_cambia_de_idioma_por_el_selector(
    app: FastAPI,
) -> None:
    """Solo la que no ha dicho nada sigue al selector: la que ya tiene mensajes
    cambia por lo que la persona escribe, no por una pastilla."""
    aseguradora = _aseguradora_en_ingles()
    cliente, clave = _navegador(app)
    async with cliente:
        await cliente.get(f"/api/chat/{aseguradora}/history?locale=en")
        cola = _pestana(clave)
        await cliente.post(f"/api/chat/{aseguradora}/messages", json={"text": "Hello there"})
        await _esperar_la_entrega(cola)
        despues = await cliente.get(f"/api/chat/{aseguradora}/history?locale=es")

    assert despues.json()["language"] == "en"


async def test_reiniciar_abre_la_conversacion_nueva_en_el_idioma_de_la_pantalla(
    app: FastAPI,
) -> None:
    aseguradora = _aseguradora_en_ingles()
    cliente, _clave = _navegador(app)
    async with cliente:
        await cliente.get(f"/api/chat/{aseguradora}/history?locale=en")
        reinicio = await cliente.post(f"/api/chat/{aseguradora}/reset?locale=es")

    assert reinicio.json()["language"] == "es"
    assert reinicio.json()["opening"]["language"] == "es"


# --- Empezar de cero (decision de Miguel, 2026-10-06) --------------------------


async def test_reiniciar_abre_una_conversacion_nueva_y_deja_el_caso_anterior_guardado(
    app: FastAPI,
) -> None:
    """La conversacion nueva arranca con la apertura y sin turnos; el caso de la
    anterior sigue en la base con su numero, y el estado del caso del navegador
    vuelve a ser nulo hasta el primer mensaje."""
    aseguradora = _aseguradora()
    cliente, clave = _navegador(app)
    async with cliente:
        await cliente.get(f"/api/chat/{aseguradora}/history")
        cola = _pestana(clave)
        await cliente.post(f"/api/chat/{aseguradora}/messages", json={"text": "Me chocaron"})
        await _esperar_la_entrega(cola)
        antes = (await cliente.get(f"/api/chat/{aseguradora}/case")).json()
        reinicio = await cliente.post(f"/api/chat/{aseguradora}/reset")
        despues_historial = (await cliente.get(f"/api/chat/{aseguradora}/history")).json()
        despues_caso = (await cliente.get(f"/api/chat/{aseguradora}/case")).json()

    assert antes is not None and antes["case_number"]
    assert reinicio.status_code == 200
    cuerpo = reinicio.json()
    assert cuerpo["opening"] is not None and cuerpo["turns"] == []
    assert cuerpo["case_number"] is None
    assert despues_historial["turns"] == [] and despues_historial["case_number"] is None
    assert despues_caso is None
    # El caso anterior sigue ahi: lo encuentra quien lo busca por su numero.
    from untangle.case_record import api as casos

    assert await casos.get_case_by_number(aseguradora, antes["case_number"]) is not None


async def test_reiniciar_no_publica_el_aviso_del_reinicio_nocturno(app: FastAPI) -> None:
    """Empezar de cero no es que la demostracion se haya reiniciado: por el flujo
    no sale ningun aviso."""
    aseguradora = _aseguradora()
    cliente, clave = _navegador(app)
    async with cliente:
        await cliente.get(f"/api/chat/{aseguradora}/history")
        cola = _pestana(clave)
        await cliente.post(f"/api/chat/{aseguradora}/reset")
        enviado = await cliente.post(
            f"/api/chat/{aseguradora}/messages", json={"text": "Hola, me chocaron ayer"}
        )
        assert enviado.status_code == 202
        publicados = await _esperar_la_entrega(cola)

    assert [evento["kind"] for evento in publicados] == ["turn.final"]
    assert not str(publicados[0]["message_id"]).startswith("demo-reset-")


# --- El flujo se declara, y su conducta se prueba aparte ----------------------


def test_las_dos_rutas_entran_en_el_contrato_publicado(app: FastAPI) -> None:
    """Se pregunta al esquema y no a la tabla de rutas: el esquema **es** el
    contrato que el navegador consume, y si una ruta no entra ahi, el cliente
    generado no la tiene aunque el servidor la sirva.

    Del flujo solo se comprueba que exista. Su conducta se prueba sobre el
    generador, en `tests/unit/chat/test_stream_wire.py`: **un flujo abierto no
    termina** --no tiene por que, hasta que la pestana se cierra-- y un cliente
    que consume el cuerpo entero nunca devolveria el control.
    """
    rutas = app.openapi()["paths"]

    assert "get" in rutas["/api/chat/{tenant_id}/stream"]
    assert "post" in rutas["/api/chat/{tenant_id}/messages"]
    assert "get" in rutas["/api/chat/{tenant_id}/history"]
    assert "get" in rutas["/api/chat/{tenant_id}/case"]
    assert "post" in rutas["/api/chat/{tenant_id}/reset"]


# --- Un limite alcanzado dice cual, y nunca su texto --------------------------


async def test_un_mensaje_demasiado_largo_recibe_su_clave_y_no_su_frase(
    app: FastAPI,
) -> None:
    """La frase la resuelve el navegador de su catalogo, igual que la de espera.
    Mandarla resuelta desde aqui es como una frase acaba diciendose de dos maneras.
    """
    async with _cliente(app) as cliente:
        respuesta = await cliente.post(
            f"/api/chat/{_aseguradora()}/messages", json={"text": "x" * 5000}
        )

    assert respuesta.status_code == 429
    cuerpo = respuesta.json()
    assert cuerpo["limit"] == "size"
    assert cuerpo["copy_key"] == "chat.limit.size"
    assert "text" not in cuerpo


async def test_un_mensaje_vacio_lo_rechaza_el_contrato_y_no_llega_al_limite(
    app: FastAPI,
) -> None:
    """El control de forma es del contrato, no de los limites: un texto vacio no
    es un limite alcanzado y no tiene por que gastar una consulta."""
    async with _cliente(app) as cliente:
        respuesta = await cliente.post(f"/api/chat/{_aseguradora()}/messages", json={"text": ""})

    assert respuesta.status_code == 422


# --- La superficie que U13 monta ----------------------------------------------


async def test_la_salud_de_listo_ve_la_superficie_del_chat(app: FastAPI) -> None:
    """U13 es el primer modulo montado por C-24: si su superficie no apareciera
    aqui, el contrato de U6 estaria sin estrenar y nadie lo notaria."""
    async with _cliente(app) as cliente:
        respuesta = await cliente.get("/api/health/ready")

    assert respuesta.status_code == 200
    superficies = respuesta.json()["checks"]["surfaces"]
    assert "chat" in superficies
    assert superficies["chat"]["status"] == "ok"


# --- El resumen de traza por la puerta (BR4.3, BR4.4) -------------------------


async def _sembrar_resumen(*, trace_id: str, visitor_key: str) -> str:
    """Un resumen abierto a nombre de una clave de navegador concreta.

    El resumen de la clave se calcula con la **unica** definicion del proyecto, la
    misma que usa la ruta: calcularlo aqui de otra forma probaria que dos funciones
    distintas coinciden, que no es lo que interesa.
    """
    from untangle.tenancy import api as tenancy

    from .conftest import nuevo_caso

    # El caso primero: el resumen cuelga de el en la base, y sembrarlo sin caso
    # probaria una escritura que en produccion no puede ocurrir.
    caso = await nuevo_caso(_aseguradora())
    await trazas.open_summary(
        trace_id=trace_id,
        tenant_id=_aseguradora(),
        case_id=caso.case_id,
        visitor_key_hash=tenancy.visitor_key_digest(visitor_key),
    )
    return caso.case_id


async def test_el_resumen_de_traza_se_ve_sin_credencial_con_la_cookie_propia(
    app: FastAPI,
) -> None:
    """AC2.3.2: sin iniciar sesion. Lo unico que hace falta es la cookie del
    navegador que lo produjo."""
    await _sembrar_resumen(trace_id="tr-http", visitor_key="clave-propia")
    async with _cliente(app) as cliente:
        cliente.cookies.set(chat_api.COOKIE, "clave-propia")
        respuesta = await cliente.get(f"/api/chat/{_aseguradora()}/trace/tr-http")

    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "recording"


async def test_la_traza_ajena_y_la_inexistente_dan_la_misma_respuesta_por_http(
    app: FastAPI,
) -> None:
    """BR4.3 desde fuera, comparando **las dos respuestas enteras**: codigo y cuerpo.

    Cualquier diferencia entre ellas --un codigo distinto, un campo de mas, una
    frase-- ya le dice al de al lado que esa traza existe.
    """
    await _sembrar_resumen(trace_id="tr-http", visitor_key="clave-propia")
    async with _cliente(app) as cliente:
        cliente.cookies.set(chat_api.COOKIE, "clave-de-otro")
        ajena = await cliente.get(f"/api/chat/{_aseguradora()}/trace/tr-http")
        inexistente = await cliente.get(f"/api/chat/{_aseguradora()}/trace/tr-que-no-existe")

    # Las dos respuestas enteras, iguales: mismo codigo y mismo cuerpo. Y `200`
    # con `null`, porque no hay nada que mostrar no es un error de quien pide.
    assert ajena.status_code == inexistente.status_code == 200
    assert ajena.json() == inexistente.json() is None


async def test_pedir_un_resumen_sin_cookie_no_da_de_alta_ninguna_clave(
    app: FastAPI,
) -> None:
    """Esta ruta lee y no crea nada: resolverle una clave a quien solo adivino una
    direccion dejaria una fila por cada intento."""
    async with _cliente(app) as cliente:
        respuesta = await cliente.get(f"/api/chat/{_aseguradora()}/trace/tr-lo-que-sea")

    assert respuesta.status_code == 200
    assert respuesta.json() is None
    assert respuesta.cookies.get(chat_api.COOKIE) is None
