"""El transporte de verdad: la clave, los tiempos maximos y lo que deja salir.

**Sin red y sin clave real.** Lo que contesta es el propio cliente HTTP con su
transporte de prueba, asi que estas pruebas ejercitan la peticion armada, las
cabeceras y la traduccion de fallos sin tocar la red y sin gastar un centavo del
presupuesto que esta unidad existe para proteger.

La clave de cada caso se **genera en el montaje**, nunca se escribe fija: una
clave fija en un archivo de prueba es una clave en el repositorio, aunque no
sirva para nada.

Cada prueba monta lo suyo y no comparte nada con las demas: ni cliente, ni
transporte, ni fabrica.
"""

from __future__ import annotations

import secrets

import httpx2
import pytest

from untangle.base import Use
from untangle.providers.adapters.gemini.transport import (
    GEMINI_BASE_URL,
    GeminiTransportFactory,
)
from untangle.providers.transport import ProviderRequest, TransportError

RESPUESTA_OK = {
    "candidates": [{"content": {"parts": [{"text": "listo"}]}}],
    "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 3},
}


def _peticion(**cambios: object) -> ProviderRequest:
    base: dict[str, object] = {
        "path": "models/gemini-3.1-flash-lite:generateContent",
        "body": {"contents": []},
        "connect_timeout_ms": 2000,
        "read_timeout_ms": 12000,
    }
    return ProviderRequest.model_validate({**base, **cambios})


def _fabrica(manejador: object) -> tuple[GeminiTransportFactory, str]:
    """Una fabrica que contesta con ese manejador, y la clave que se le dio."""
    clave = secrets.token_urlsafe(16)
    red = httpx2.MockTransport(manejador)  # type: ignore[arg-type]
    return GeminiTransportFactory(network=red), clave


async def test_la_clave_viaja_en_cabecera_y_nunca_en_la_url() -> None:
    """Una URL acaba en un registro de acceso, en un mensaje de error y en una
    traza; una cabecera no. Se comprueban las dos mitades: que la cabecera la
    lleva y que ni la ruta ni la consulta la contienen."""
    vistas: list[httpx2.Request] = []

    def manejador(peticion: httpx2.Request) -> httpx2.Response:
        vistas.append(peticion)
        return httpx2.Response(200, json=RESPUESTA_OK)

    fabrica, clave = _fabrica(manejador)
    transporte = fabrica.create(api_key=clave, use=Use.CHAT)

    await transporte.send(_peticion())

    assert vistas[0].headers["x-goog-api-key"] == clave
    assert clave not in str(vistas[0].url)
    assert str(vistas[0].url).startswith(GEMINI_BASE_URL)


async def test_ninguna_representacion_del_transporte_imprime_la_clave() -> None:
    """La capa 2 del diseno de seguridad. El objeto se nombra por su uso; lo que
    no existe como atributo no se puede imprimir por descuido."""

    def manejador(_: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=RESPUESTA_OK)

    fabrica, clave = _fabrica(manejador)
    transporte = fabrica.create(api_key=clave, use=Use.VOICE)

    assert clave not in repr(transporte)
    assert clave not in str(vars(transporte))
    assert "voice" in repr(transporte)


async def test_los_dos_tiempos_maximos_de_la_peticion_llegan_al_cliente() -> None:
    """Son **por uso** y por peticion: el turno de voz no puede esperar lo que
    una corrida de evaluaciones si. Se comprueban en segundos, que es la unidad
    del cliente, contra los milisegundos que declara la configuracion."""
    # El cliente pasa los tiempos a su capa de red como un **mapa**, no como el
    # objeto: es la forma que viaja de verdad, y comprobar la otra seria
    # comprobar una conversion que nadie hace.
    vistas: list[dict[str, float | None]] = []

    def manejador(peticion: httpx2.Request) -> httpx2.Response:
        vistas.append(dict(peticion.extensions["timeout"]))
        return httpx2.Response(200, json=RESPUESTA_OK)

    fabrica, clave = _fabrica(manejador)
    transporte = fabrica.create(api_key=clave, use=Use.VOICE)

    await transporte.send(_peticion(connect_timeout_ms=2000, read_timeout_ms=2000))

    assert vistas[0]["connect"] == pytest.approx(2.0)
    assert vistas[0]["read"] == pytest.approx(2.0)


async def test_un_tiempo_agotado_sale_marcado_como_tal_y_sin_el_tipo_del_cliente() -> None:
    """BR2.2: ningun tipo del proveedor ni de su cliente cruza la frontera. Lo
    que sale es `TransportError` con la marca que el adaptador traduce a
    `timeout`, y no la excepcion del cliente HTTP."""

    def manejador(_: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("tardo")

    fabrica, clave = _fabrica(manejador)
    transporte = fabrica.create(api_key=clave, use=Use.EVALS)

    with pytest.raises(TransportError) as error:
        await transporte.send(_peticion())

    assert error.value.timed_out is True


async def test_no_haber_con_quien_hablar_sale_sin_marca_de_tiempo_agotado() -> None:
    """Una conexion rechazada no es una espera agotada: el adaptador las traduce
    a tipos distintos --`unavailable` y `timeout`-- y de eso depende que la
    politica de fallo del nodo tenga sentido."""

    def manejador(_: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("no hay nadie")

    fabrica, clave = _fabrica(manejador)
    transporte = fabrica.create(api_key=clave, use=Use.CHAT)

    with pytest.raises(TransportError) as error:
        await transporte.send(_peticion())

    assert error.value.timed_out is False


async def test_un_codigo_de_error_no_es_un_fallo_de_transporte() -> None:
    """El proveedor contesto: eso no es un fallo de conexion. Sale como respuesta
    con su codigo, y quien lo convierte en uno de los cuatro tipos es
    `errors.raise_for_response`, que es el unico sitio que traduce respuestas."""

    def manejador(_: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(429, json={"error": {"status": "RESOURCE_EXHAUSTED"}})

    fabrica, clave = _fabrica(manejador)
    transporte = fabrica.create(api_key=clave, use=Use.CHAT)

    respuesta = await transporte.send(_peticion())

    assert respuesta.status_code == 429
    assert respuesta.body["error"] == {"status": "RESOURCE_EXHAUSTED"}


@pytest.mark.parametrize(
    "cuerpo",
    [
        pytest.param(b"no soy json", id="texto suelto"),
        pytest.param(b"[1, 2, 3]", id="json que no es un mapa"),
    ],
)
async def test_un_cuerpo_que_no_es_un_mapa_llega_vacio_y_no_levanta(cuerpo: bytes) -> None:
    """Sale vacio a proposito, para que el unico sitio que traduce respuestas lo
    lea como `invalid_response`. Abrir aqui un segundo camino de traduccion
    dejaria dos que un dia dirian cosas distintas.

    Y **no se registra que venia**: el cuerpo lleva la respuesta del modelo, y la
    respuesta del modelo lleva lo que el asegurado escribio.
    """

    def manejador(_: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=cuerpo)

    fabrica, clave = _fabrica(manejador)
    transporte = fabrica.create(api_key=clave, use=Use.CHAT)

    respuesta = await transporte.send(_peticion())

    assert respuesta.status_code == 200
    assert respuesta.body == {}


async def test_cada_uso_recibe_su_propio_cliente_con_su_propia_clave() -> None:
    """Gemini limita **por proyecto** y cada uso vive en el suyo (ADR-018): una
    cuota agotada en el chat no puede apagar la voz. Que los clientes sean dos
    objetos distintos con dos cabeceras distintas es lo que lo sostiene."""
    vistas: dict[str, str] = {}

    def manejador(peticion: httpx2.Request) -> httpx2.Response:
        vistas[str(peticion.url)] = peticion.headers["x-goog-api-key"]
        return httpx2.Response(200, json=RESPUESTA_OK)

    red = httpx2.MockTransport(manejador)
    fabrica = GeminiTransportFactory(network=red)
    clave_voz = secrets.token_urlsafe(16)
    clave_chat = secrets.token_urlsafe(16)

    voz = fabrica.create(api_key=clave_voz, use=Use.VOICE)
    chat = fabrica.create(api_key=clave_chat, use=Use.CHAT)

    assert voz is not chat
    await voz.send(_peticion(path="models/voz:generateContent"))
    await chat.send(_peticion(path="models/chat:generateContent"))

    assert vistas[f"{GEMINI_BASE_URL}models/voz:generateContent"] == clave_voz
    assert vistas[f"{GEMINI_BASE_URL}models/chat:generateContent"] == clave_chat
    assert clave_voz != clave_chat

    await fabrica.aclose()
