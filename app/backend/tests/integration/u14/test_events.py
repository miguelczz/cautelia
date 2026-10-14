"""El aviso en vivo: su numeracion, su reanudacion y su redaccion (BR6.1 a BR6.3).

Lo que aqui importa no es que el flujo emita algo: es que **una reconexion no
pierda nada**. Una cola que se actualiza sola pero se queda vieja al reconectar es
peor que una que no se actualiza, porque nadie se entera.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from untangle.inbox import api as inbox_api
from untangle.inbox import events
from untangle.tenancy import api as tenancy
from untangle.tenancy import session

from .conftest import AHORA, cliente, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u14")


@pytest.fixture
def aseguradora() -> str:
    return tenancy.available_ids()[0]


async def _avisar(tenant_id: str, case_id: str, resumen: str = "un caso cambio") -> int:
    evento = await events.append(
        tenant_id,
        case_id=case_id,
        kind=events.EventKind.CASE_UPDATED,
        summary=resumen,
        language="es",
        now=AHORA,
    )
    return evento.event_id


# --- BR6.1: el identificador crece por aseguradora ----------------------------


async def test_el_identificador_crece_desde_uno_en_cada_aseguradora(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Dos aseguradoras, dos secuencias que empiezan en uno.

    Con un contador global, la segunda empezaria en tres y su navegador veria
    huecos: pedir desde el ultimo hueco le traeria eventos de la otra o ninguno.
    Por eso se comprueban las dos, y no solo que una crezca.
    """
    primera, segunda = dos_aseguradoras
    caso_primera = await nuevo_caso(primera)
    caso_segunda = await nuevo_caso(segunda)

    uno = await _avisar(primera, caso_primera)
    dos = await _avisar(primera, caso_primera)
    otro = await _avisar(segunda, caso_segunda)

    assert (uno, dos) == (1, 2)
    assert otro == 1, "la segunda aseguradora no empezo su propia secuencia"


async def test_los_avisos_de_una_aseguradora_no_existen_para_otra(
    dos_aseguradoras: tuple[str, str],
) -> None:
    ajena, propia = dos_aseguradoras
    caso = await nuevo_caso(ajena)
    await _avisar(ajena, caso)

    assert await events.since(propia, 0) == ()


# --- BR6.2: la reanudacion no pierde lo ocurrido ------------------------------


async def test_una_reconexion_recibe_lo_que_se_perdio(aseguradora: str) -> None:
    """Y **solo** eso: ni repite lo que ya vio ni se salta lo de en medio."""
    caso = await nuevo_caso(aseguradora)
    visto = await _avisar(aseguradora, caso, "el primero")
    await _avisar(aseguradora, caso, "el segundo")
    await _avisar(aseguradora, caso, "el tercero")

    perdidos = await events.since(aseguradora, visto)

    assert [e.event_id for e in perdidos] == [visto + 1, visto + 2]


async def test_quien_abre_sin_cabecera_se_coloca_al_final(aseguradora: str) -> None:
    """No se le reproduce la demostracion entera.

    Quien abre la bandeja quiere lo que pase desde ahora; reproducirle todo le
    daria como novedad cosas que ocurrieron ayer.
    """
    caso = await nuevo_caso(aseguradora)
    await _avisar(aseguradora, caso)
    await _avisar(aseguradora, caso)

    ultimo = await events.last_event_id(aseguradora)

    assert ultimo == 2
    assert await events.since(aseguradora, ultimo) == ()


@pytest.mark.parametrize("cabecera", [None, "", "no-es-un-numero", "-3"])
def test_una_cabecera_ilegible_no_se_lee_como_desde_el_principio(cabecera: str | None) -> None:
    """Se trata como si no la hubiera mandado, que es colocarse al final.

    Reproducir todo a quien mando basura le daria eventos que ya vio, y hacerlo
    en silencio es lo que convierte un error del cliente en un error de la
    pantalla.
    """
    assert events.parse_last_event_id(cabecera) is None


def test_una_cabecera_con_numero_si_se_lee() -> None:
    """El control positivo de la de arriba: sin el, pasaria con un lector roto."""
    assert events.parse_last_event_id("7") == 7


# --- BR6.3: el resumen va redactado al escribirse ------------------------------


async def test_el_resumen_se_guarda_ya_redactado(aseguradora: str) -> None:
    """En la tabla, no al leerlo.

    Un evento guardado con texto sin redactar es un punto de salida sin redaccion
    aunque nadie lo lea todavia, y el reporte de redaccion lo encontraria ahi. Se
    comprueba **contra la fila de la base**, no contra lo que devuelve la funcion:
    lo segundo pasaria con una implementacion que redactara al leer.
    """
    caso = await nuevo_caso(aseguradora)
    await _avisar(aseguradora, caso, "llamar al 300 123 4567 del asegurado")

    async with session.session_for(aseguradora) as sesion:
        filas = await session.fetch_all(sesion, "SELECT summary_redacted FROM inbox_event")

    guardado = str(filas[0]["summary_redacted"])
    assert "3001234567" not in guardado
    assert "300 123 4567" not in guardado
    assert guardado, "el resumen se guardo vacio, que no es lo mismo que redactado"


# --- El flujo por HTTP ---------------------------------------------------------


async def test_el_cable_entrega_los_avisos_desde_donde_se_pidieron(aseguradora: str) -> None:
    """La forma exacta del cable, sobre el generador y no sobre la ruta.

    Un flujo abierto **no termina** hasta que la pestana cierra --que es justo lo
    que se quiere de el-- asi que no se puede consumir entero desde una prueba. Se
    consume lo que hace falta y se corta, igual que hizo U13 con el suyo.
    """
    caso = await nuevo_caso(aseguradora)
    visto = await _avisar(aseguradora, caso, "el primero")
    await _avisar(aseguradora, caso, "el segundo")

    trozos: list[bytes] = []
    flujo = inbox_api.inbox_stream(aseguradora, desde=visto)
    try:
        async for trozo in flujo:
            trozos.append(trozo)
            if b"el segundo" in b"".join(trozos):
                break
    finally:
        await flujo.aclose()

    cable = b"".join(trozos).decode("utf-8")
    assert "retry: 3000" in cable, "el flujo no dijo su intervalo de reconexion"
    assert f"id: {visto + 1}" in cable
    assert "el segundo" in cable
    assert "el primero" not in cable, "reprodujo un aviso que el navegador ya habia visto"


async def test_el_cable_late_cuando_no_hay_nada_que_decir(aseguradora: str) -> None:
    """Sin latido, un intermediario corta una conexion ociosa y nadie se entera.

    La pantalla se queda entonces mirando algo que ya no se va a actualizar, con el
    mismo aspecto que una viva.
    """
    trozos: list[bytes] = []
    flujo = inbox_api.inbox_stream(aseguradora, desde=0)
    try:
        async for trozo in flujo:
            trozos.append(trozo)
            if b"heartbeat" in b"".join(trozos):
                break
    finally:
        await flujo.aclose()

    assert b"heartbeat" in b"".join(trozos)


async def test_el_flujo_no_responde_sin_credencial(app: FastAPI, aseguradora: str) -> None:
    """La misma puerta que la cola: la aseguradora sale de la credencial.

    Se pide sin credencial a proposito, que es lo unico que se puede comprobar por
    la ruta sin dejar un flujo abierto: el rechazo ocurre **antes** de que el
    cuerpo empiece.
    """
    async with cliente(app) as http:
        respuesta = await http.get(f"/api/inbox/{aseguradora}/stream")

    assert respuesta.status_code == 404
