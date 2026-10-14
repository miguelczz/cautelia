"""La ventana de 24 horas, contra las dos superficies publicas (BR3.2, BR3.3).

La tanda 1 probo la regla como funcion pura: dado un historial y un reloj, dice si
se aceptan casos nuevos. Lo que aqui se comprueba es lo otro, que es lo que la
tanda 1 dejo escrito que faltaba: **que alguien la llame**, y que la llame donde
se decide --al abrir un caso-- y no donde cortaria una conversacion viva.

Son las dos mitades de la misma regla y las dos se prueban:

- lo **nuevo** no entra: el chat no abre un caso y la voz no abre una llamada;
- lo **abierto** termina: una conversacion que ya tiene caso sigue, y una llamada
  cortada se retoma, aunque la ventana este cerrada.

**El estado de partida es una base sin ninguna corrida**, que es el de un
despliegue nuevo. No es un caso raro: es la razon por la que `demo:reset` es el
ultimo paso del despliegue.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI

from untangle.chat import api as chat_api
from untangle.demo_operations import api as demo
from untangle.demo_operations.models import PurgerRow, ResetOutcome, ResetRun
from untangle.tenancy import api as tenancy
from untangle.voice import api as voz
from untangle.voice.availability import OFF_CODE_KEYS, VoiceOffCode

from .conftest import aseguradora, cliente

pytestmark = pytest.mark.usefixtures("base_de_u20")

CERRADA = "demo.reset.surfaces_closed"


def _corrida(*, hace: timedelta, outcome: ResetOutcome = ResetOutcome.SUCCEEDED) -> ResetRun:
    """Una corrida que termino hace tanto, con una sola fila de purgador."""
    momento = datetime.now(UTC) - hace
    fila = (
        PurgerRow(name="sembrado-por-la-prueba", deleted=0, kept=0, duration_seconds=0.001)
        if outcome is ResetOutcome.SUCCEEDED
        else PurgerRow(
            name="sembrado-por-la-prueba", duration_seconds=0.001, error_type="RuntimeError"
        )
    )
    return ResetRun(
        reset_run_id=f"reset-{int(hace.total_seconds())}-{outcome.value}",
        started_at=momento,
        finished_at=momento,
        outcome=outcome,
        purgers=(fila,),
    )


async def _sembrar(*corridas: ResetRun) -> None:
    for corrida in corridas:
        await demo.save_run(corrida)


# --- El chat ------------------------------------------------------------------


async def test_sin_ningun_reinicio_conocido_el_chat_no_abre_un_caso_nuevo(app: FastAPI) -> None:
    """La base recien creada: la ventana cierra y lo dice con la frase del catalogo.

    Y responde **503**, no 409: el servicio esta en pie y lo que falta es la
    garantia de que lo que entre se borre esa noche.
    """
    async with cliente(app) as http:
        respuesta = await http.post(
            f"/api/chat/{aseguradora()}/messages", json={"text": "me chocaron el carro"}
        )

    assert respuesta.status_code == 503, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["kind"] == "demo_closed"
    assert cuerpo["copy_key"] == CERRADA


async def test_con_un_reinicio_de_hace_una_hora_el_chat_acepta(app: FastAPI) -> None:
    """La demo de cualquier dia: se reinicio anoche y acepta casos nuevos."""
    await _sembrar(_corrida(hace=timedelta(hours=1)))

    async with cliente(app) as http:
        respuesta = await http.post(
            f"/api/chat/{aseguradora()}/messages", json={"text": "me chocaron el carro"}
        )

    assert respuesta.status_code == 202, respuesta.text


async def test_a_las_veinticinco_horas_el_chat_deja_de_aceptar(app: FastAPI) -> None:
    """El reloj es el del ultimo exito, y a las 24 horas ya se cerro."""
    await _sembrar(_corrida(hace=timedelta(hours=25)))

    async with cliente(app) as http:
        respuesta = await http.post(
            f"/api/chat/{aseguradora()}/messages", json={"text": "me chocaron el carro"}
        )

    assert respuesta.status_code == 503, respuesta.text


async def test_tres_intentos_fallidos_despues_del_ultimo_exito_no_abren_la_ventana(
    app: FastAPI,
) -> None:
    """La forma mas facil de implementar mal BR3.2, cerrada desde la superficie.

    Con el contador atado al **ultimo intento**, tres fallos recientes dejarian la
    demo aceptando datos indefinidamente y el tablero en verde. Aqui los tres
    fallos son de hace minutos y el ultimo exito de hace dos dias.
    """
    await _sembrar(
        _corrida(hace=timedelta(days=2)),
        _corrida(hace=timedelta(minutes=30), outcome=ResetOutcome.FAILED),
        _corrida(hace=timedelta(minutes=20), outcome=ResetOutcome.FAILED),
        _corrida(hace=timedelta(minutes=10), outcome=ResetOutcome.FAILED),
    )

    async with cliente(app) as http:
        respuesta = await http.post(
            f"/api/chat/{aseguradora()}/messages", json={"text": "me chocaron el carro"}
        )

    assert respuesta.status_code == 503, respuesta.text


async def test_una_conversacion_con_caso_sigue_entera_con_la_ventana_cerrada(
    app: FastAPI,
) -> None:
    """BR3.3: quien esta a mitad de un reporte lo termina.

    Se abre el caso con la ventana abierta --un mensaje, que es lo que lo crea-- y
    despues se cierra la ventana borrando la corrida. El mensaje siguiente de esa
    misma conversacion pasa, porque su caso ya existe: perder un reporte por un
    fallo de operacion que no es de quien lo escribe es el precio que esta regla
    existe para no cobrar.
    """
    await _sembrar(_corrida(hace=timedelta(hours=1)))

    async with cliente(app) as http:
        primero = await http.post(
            f"/api/chat/{aseguradora()}/messages", json={"text": "me chocaron el carro"}
        )
        assert primero.status_code == 202, primero.text
        galleta = http.cookies.get("untangle_visitor")
        assert galleta is not None
        await _atar_un_caso(aseguradora(), galleta=galleta)
        await _borrar_las_corridas()

        siguiente = await http.post(
            f"/api/chat/{aseguradora()}/messages", json={"text": "fue ayer por la tarde"}
        )

    # **Lo que para a este mensaje es el limite por minuto del chat, no la
    # ventana**, y la diferencia es exactamente lo que esta prueba comprueba: la
    # ventana se mira **antes** de contar, asi que si hubiera cerrado la respuesta
    # seria 503 con `demo_closed` y no un limite con su frase. Dos mensajes
    # seguidos del mismo navegador chocan con el limite de ritmo, que es otra
    # regla y de otra unidad; esperar su minuto no haria la prueba mas cierta.
    assert siguiente.status_code == 429, siguiente.text
    cuerpo = siguiente.json()
    assert cuerpo["limit"] == "rate"
    assert "kind" not in cuerpo


# --- La voz -------------------------------------------------------------------


async def test_la_consola_dice_la_demo_cerrada_y_no_ofrece_el_boton(app: FastAPI) -> None:
    """Ofrecer un boton que va a fallar es peor que no ofrecerlo (BR1.1 de U17)."""
    async with cliente(app) as http:
        respuesta = await http.get(f"/api/voice/{aseguradora()}/availability")

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["available"] is False
    assert cuerpo["reason_code"] == VoiceOffCode.DEMO_CLOSED.value
    assert cuerpo["reason_key"] == CERRADA


async def test_abrir_una_llamada_nueva_con_la_ventana_cerrada_responde_503(
    app: FastAPI,
) -> None:
    """Y con su codigo propio: ni cuota ni techo, que son otras dos cosas."""
    async with cliente(app) as http:
        respuesta = await http.post(f"/api/voice/{aseguradora()}/sessions", json={})

    assert respuesta.status_code == 503, respuesta.text
    assert respuesta.json()["code"] == "demo_closed"


async def test_una_llamada_cortada_se_retoma_con_la_ventana_cerrada(app: FastAPI) -> None:
    """BR3.3 en la voz: la retoma no es un caso nuevo, es el mismo.

    Se abre con la ventana abierta, se corta como la corta el socket --no
    colgando, que es un final a proposito y no deja nada retomable-- se cierra la
    ventana, y la retoma entra y vuelve al mismo caso.
    """
    await _sembrar(_corrida(hace=timedelta(hours=1)))

    async with cliente(app) as http:
        primera = await http.post(f"/api/voice/{aseguradora()}/sessions", json={})
        assert primera.status_code == 201, primera.text
        galleta = http.cookies.get("untangle_visitor")
        assert galleta is not None
        await _cortar(aseguradora(), galleta=galleta)
        await _borrar_las_corridas()

        retomada = await http.post(f"/api/voice/{aseguradora()}/sessions", json={})

    assert retomada.status_code == 201, retomada.text
    assert retomada.json()["case_id"] == primera.json()["case_id"]


async def test_la_consola_ofrece_la_retoma_aunque_la_ventana_este_cerrada(
    app: FastAPI,
) -> None:
    """La disponibilidad no puede discrepar de lo que la apertura hara de verdad.

    Si dijera "la demo esta cerrada" con una retoma viva, la consola esconderia un
    boton que el servidor si habria admitido, y quien dejo su reporte a medias no
    tendria forma de volver.
    """
    await _sembrar(_corrida(hace=timedelta(hours=1)))

    async with cliente(app) as http:
        primera = await http.post(f"/api/voice/{aseguradora()}/sessions", json={})
        assert primera.status_code == 201, primera.text
        galleta = http.cookies.get("untangle_visitor")
        assert galleta is not None
        await _cortar(aseguradora(), galleta=galleta)
        await _borrar_las_corridas()

        disponible = await http.get(f"/api/voice/{aseguradora()}/availability")

    assert disponible.json()["available"] is True, disponible.text


# --- La frase, una sola --------------------------------------------------------


def test_las_tres_tablas_nombran_la_misma_clave() -> None:
    """La frase de la demo cerrada se escribe en tres sitios y tiene que ser una.

    No se pueden importar entre si: `demo_operations` esta por encima de la voz y
    del chat en el contrato de capas, asi que cada uno escribe su literal y **esta
    prueba es lo que impide que divergan**. Sin ella, cambiar la clave en uno
    dejaria a los otros dos pidiendo una frase que el catalogo ya no tiene, y la
    pantalla diria un error generico.
    """
    assert str(demo.SURFACES_CLOSED) == CERRADA
    assert str(chat_api.SURFACES_CLOSED) == CERRADA
    assert str(OFF_CODE_KEYS[VoiceOffCode.DEMO_CLOSED]) == CERRADA


# --- Lo que las pruebas necesitan ---------------------------------------------


async def _atar_un_caso(tenant_id: str, *, galleta: str) -> None:
    """Le ata un caso a la conversacion de ese navegador, como el primer turno.

    Se hace aqui y no esperando al grafo porque lo que esta prueba necesita es el
    **estado** --una conversacion con caso-- y no el camino que lo produce, que es
    de U12 y ya tiene sus pruebas.
    """
    from untangle.chat import session as chat

    viva = await chat.find_live(
        tenant_id=tenant_id, visitor_key_digest=tenancy.visitor_key_digest(galleta)
    )
    assert viva is not None
    await chat.attach_case(viva, case_id=await _crear_un_caso(tenant_id))


async def _crear_un_caso(tenant_id: str) -> str:
    from untangle.case_record import api as casos
    from untangle.case_record.models import Channel, Origin, RecordType

    vista = await casos.create_case(
        tenant_id,
        casos.NewCase(
            case_id="case-de-la-conversacion-viva",
            record_type=RecordType.CLAIM,
            channel=Channel.CHAT,
            origin=Origin.PUBLIC_CHAT,
            language="es",
        ),
        now=datetime.now(UTC),
    )
    return vista.case_id


async def _cortar(tenant_id: str, *, galleta: str) -> None:
    """Deja la llamada viva de ese navegador cortada y retomable, como el socket."""
    viva = await voz.find_live(
        tenant_id=tenant_id, visitor_key_digest=tenancy.visitor_key_digest(galleta)
    )
    assert viva is not None, "no hay llamada viva que cortar"
    await voz.end_call(
        viva,
        reason=voz.EndReason.DROPPED,
        now=datetime.now(UTC),
        resume_window=timedelta(seconds=tenancy.require(tenant_id).call.resume_window_seconds),
    )


async def _borrar_las_corridas() -> None:
    """Cierra la ventana quitando el historial, que es lo que la regla mira."""
    from untangle.tenancy import session

    async with session.unscoped_session() as sesion:
        await session.execute_sql(sesion, "DELETE FROM reset_run")
