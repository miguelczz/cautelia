"""El final de la llamada: donde quedo el caso y como salir de ahi (BR3.4).

Lo que la regla pide son tres cosas: el numero del caso, su estado, y el enlace
firmado **cuando hay algo que abrir con el**. Y una cuarta que es la que importa:
un caso que quedo esperando al asegurado no puede quedarse sin salida, asi que o
vuelve dentro de su ventana o lo pasa ya a un ajustador y se lleva su enlace.

Todo entra por HTTP. La llamada de otro navegador responde igual que una que no
existe, y eso se comprueba aqui y no en la funcion: el resumen de la galleta viaja
**dentro** de la consulta, asi que una fila ajena no se llega a leer.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx2
import pytest
from fastapi import FastAPI

from untangle.case_record import api as casos
from untangle.case_record import rules as case_rules
from untangle.case_record.models import (
    Actor,
    ActorType,
    CaseState,
    Channel,
    DerivationReason,
)
from untangle.inbox import visitor as enlace
from untangle.tenancy import config as tenancy_config
from untangle.voice import tokens as voz_token

from .conftest import CLAVE_DE_ENLACES, CLAVE_DEL_SOCKET, aseguradora, cliente

pytestmark = pytest.mark.usefixtures("base_de_u17")

COOKIE = "untangle_visitor"


async def _llamada(app: FastAPI) -> tuple[str, str, str]:
    """Una llamada abierta: su identificador, su caso y la galleta del navegador."""
    async with cliente(app) as http:
        abierta = await http.post(f"/api/voice/{aseguradora()}/sessions", json={})
        assert abierta.status_code == 201, abierta.text
        galleta = http.cookies.get(COOKIE)
    assert galleta is not None
    cuerpo = abierta.json()
    assert cuerpo["case_id"] is not None
    return str(cuerpo["call_id"]), str(cuerpo["case_id"]), galleta


async def _llevar_a(tenant_id: str, case_id: str, estado: CaseState) -> None:
    """Mueve el caso por el camino declarado, nunca escribiendo el estado a mano."""
    ahora = datetime.now(UTC)
    camino = {
        CaseState.CAPTURING: [CaseState.CAPTURING],
        CaseState.VERIFYING: [CaseState.CAPTURING, CaseState.VERIFYING],
        CaseState.DECIDING: [CaseState.CAPTURING, CaseState.VERIFYING, CaseState.DECIDING],
        CaseState.DERIVED: [CaseState.CAPTURING, CaseState.DERIVED],
        CaseState.AWAITING_INSURED: [
            CaseState.CAPTURING,
            CaseState.DERIVED,
            CaseState.AWAITING_INSURED,
        ],
    }[estado]
    for paso in camino:
        await casos.apply_transition(
            tenant_id,
            case_id,
            paso,
            context=case_rules.TransitionContext(
                now=ahora,
                actor=Actor(actor_type=ActorType.SYSTEM),
                channel=Channel.VOICE,
                derivation_reason=(DerivationReason.RULE if paso is CaseState.DERIVED else None),
            ),
        )


async def _desenlace(app: FastAPI, call_id: str, *, galleta: str | None) -> httpx2.Response:
    async with cliente(app) as http:
        if galleta is not None:
            http.cookies.set(COOKIE, galleta)
        return await http.get(f"/api/voice/{aseguradora()}/sessions/{call_id}/outcome")


# --- BR3.4: donde quedo el caso -----------------------------------------------


async def test_al_terminar_se_puede_saber_donde_quedo_el_caso(app: FastAPI) -> None:
    """El numero y el estado, que es lo que la persona puede apuntar y leer."""
    call_id, case_id, galleta = await _llamada(app)
    await _llevar_a(aseguradora(), case_id, CaseState.CAPTURING)

    respuesta = await _desenlace(app, call_id, galleta=galleta)

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["state"] == "capturing"
    assert cuerpo["case_number"], "el desenlace no dice el numero del caso"
    # Y **sin enlace**: no hay nada que abrir con el todavia.
    assert cuerpo["case_link"] is None


async def test_un_caso_derivado_trae_su_enlace_firmado(app: FastAPI) -> None:
    """El enlace solo cuando hay algo que leer, y con el token en el fragmento.

    En el fragmento y no en la ruta: es lo que el navegador no manda al servidor
    ni en la cabecera de procedencia, asi que no aparece en ningun registro.
    """
    call_id, case_id, galleta = await _llamada(app)
    await _llevar_a(aseguradora(), case_id, CaseState.DERIVED)

    respuesta = await _desenlace(app, call_id, galleta=galleta)

    assert respuesta.status_code == 200, respuesta.text
    enlace = respuesta.json()["case_link"]
    assert enlace is not None, "un caso derivado se quedo sin enlace"
    assert enlace.startswith("/c#"), enlace


@pytest.mark.parametrize("estado", [CaseState.VERIFYING, CaseState.DECIDING])
async def test_un_caso_en_revision_trae_su_enlace_y_no_ofrece_el_chat(
    app: FastAPI, estado: CaseState
) -> None:
    """US1.17: la llamada se despide a los pocos instantes de terminar el reporte, y si las
    reglas todavia no resolvieron la despedida dice que el resultado aparece en la pantalla.
    Sin enlace, quien cuelga no tendria donde verlo."""
    call_id, case_id, galleta = await _llamada(app)
    await _llevar_a(aseguradora(), case_id, estado)

    cuerpo = (await _desenlace(app, call_id, galleta=galleta)).json()

    assert cuerpo["state"] == estado.value
    assert str(cuerpo["case_link"]).startswith("/c#")
    assert cuerpo["chat_continuation"] is False


async def test_el_token_del_socket_lo_firma_la_clave_de_la_voz(app: FastAPI) -> None:
    """La mitad de PENDIENTES 1.16 que vive en la raiz de composicion.

    Lo que se comprueba es el token que **el navegador recibe** por HTTP, no lo que
    la raiz guardo en un campo: si la raiz volviera a pasarle a la voz la clave del
    enlace de caso, ese token seguiria siendo valido para alguien y la prueba del
    socket no lo veria, porque esa instala sus propias dependencias.
    """
    async with cliente(app) as http:
        abierta = await http.post(f"/api/voice/{aseguradora()}/sessions", json={})
    assert abierta.status_code == 201, abierta.text
    cuerpo = abierta.json()
    token = str(cuerpo["transport"]["token"])
    call_id = str(cuerpo["call_id"])
    ahora = datetime.now(UTC)

    con_la_de_la_voz = voz_token.verify(
        token, call_id=call_id, signing_key=CLAVE_DEL_SOCKET, now=ahora
    )
    con_la_del_enlace = voz_token.verify(
        token, call_id=call_id, signing_key=CLAVE_DE_ENLACES, now=ahora
    )

    assert con_la_de_la_voz.accepted is True
    assert con_la_del_enlace.accepted is False


async def test_el_enlace_de_la_voz_se_canjea_con_la_clave_del_enlace(app: FastAPI) -> None:
    """La otra mitad de PENDIENTES 1.16: la ruta de la voz firma **dos** cosas.

    Comprobar que el enlace empieza por `/c#` no distingue con que clave se firmo,
    y desde que el token de socket tiene la suya esa es justo la confusion posible:
    pasarle a `issue_case_link` la clave de la voz daria un enlace con la misma
    forma que la bandeja rechazaria al canjearlo. Asi que se canjea, y se comprueba
    ademas que la clave del token **no** lo abre.
    """
    call_id, case_id, galleta = await _llamada(app)
    await _llevar_a(aseguradora(), case_id, CaseState.DERIVED)

    cuerpo = (await _desenlace(app, call_id, galleta=galleta)).json()
    token = str(cuerpo["case_link"]).removeprefix("/c#")

    sesion = await enlace.redeem(token, signing_key=CLAVE_DE_ENLACES, now=datetime.now(UTC))
    assert sesion.case_id == case_id
    with pytest.raises(enlace.CaseSessionInvalidError):
        await enlace.redeem(token, signing_key=CLAVE_DEL_SOCKET, now=datetime.now(UTC))


async def test_un_caso_que_espera_al_asegurado_no_trae_enlace(app: FastAPI) -> None:
    """Lo que ese necesita son sus dos salidas, no un enlace a algo que no paso."""
    call_id, case_id, galleta = await _llamada(app)
    await _llevar_a(aseguradora(), case_id, CaseState.AWAITING_INSURED)

    cuerpo = (await _desenlace(app, call_id, galleta=galleta)).json()

    assert cuerpo["state"] == "awaiting_insured"
    assert cuerpo["case_link"] is None


async def test_la_llamada_de_otro_navegador_responde_como_una_que_no_existe(
    app: FastAPI,
) -> None:
    """Sin galleta no se resuelve ninguna clave, y con otra no se lee la fila."""
    call_id, _, _ = await _llamada(app)

    ajena = await _desenlace(app, call_id, galleta="clave-de-otro")
    sin_galleta = await _desenlace(app, call_id, galleta=None)
    inexistente = await _desenlace(app, "llamada-que-no-existe", galleta="clave-de-otro")

    assert ajena.status_code == sin_galleta.status_code == inexistente.status_code == 404
    assert ajena.json()["code"] == inexistente.json()["code"]


# --- US1.20: seguir por chat con el numero del caso -----------------------------


async def test_un_caso_que_sigue_en_captura_se_puede_seguir_por_chat(app: FastAPI) -> None:
    """La consola solo ofrece el chat cuando el chat va a poder retomarlo: lo decide el
    servidor, con la configuracion de la aseguradora y el estado del caso."""
    call_id, case_id, galleta = await _llamada(app)
    await _llevar_a(aseguradora(), case_id, CaseState.CAPTURING)

    cuerpo = (await _desenlace(app, call_id, galleta=galleta)).json()

    assert cuerpo["chat_continuation"] is True


@pytest.mark.parametrize("estado", [CaseState.DERIVED, CaseState.AWAITING_INSURED])
async def test_un_caso_que_ya_no_esta_en_captura_no_ofrece_el_chat(
    app: FastAPI, estado: CaseState
) -> None:
    call_id, case_id, galleta = await _llamada(app)
    await _llevar_a(aseguradora(), case_id, estado)

    cuerpo = (await _desenlace(app, call_id, galleta=galleta)).json()

    assert cuerpo["chat_continuation"] is False


async def test_sin_continuidad_voz_a_chat_la_consola_no_ofrece_el_chat(app: FastAPI) -> None:
    """AC1.19.5: con la continuidad apagada nada promete que el chat pueda retomarlo."""
    call_id, case_id, galleta = await _llamada(app)
    await _llevar_a(aseguradora(), case_id, CaseState.CAPTURING)
    original = tenancy_config.loaded()
    tenancy_config.install(
        tenancy_config.LoadedTenants(
            available=tuple(
                t.model_copy(update={"voice_to_chat_continuity": False}) for t in original.available
            ),
            unavailable=original.unavailable,
        )
    )
    try:
        cuerpo = (await _desenlace(app, call_id, galleta=galleta)).json()
    finally:
        tenancy_config.install(original)

    assert cuerpo["chat_continuation"] is False


# --- BR3.4: la salida del que espera ------------------------------------------


async def test_pasarlo_a_una_persona_lo_deriva_y_devuelve_su_enlace(app: FastAPI) -> None:
    """La salida del caso que quedo esperando: se pasa ya, y se lleva su enlace.

    Sin esto, ese caso se queda sin salida y quien llamo sin saber que hacer.
    """
    call_id, case_id, galleta = await _llamada(app)
    await _llevar_a(aseguradora(), case_id, CaseState.AWAITING_INSURED)

    async with cliente(app) as http:
        http.cookies.set(COOKIE, galleta)
        respuesta = await http.post(f"/api/voice/{aseguradora()}/sessions/{call_id}/handoff")

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["state"] == "derived"
    assert str(cuerpo["case_link"]).startswith("/c#")
    # Y el caso de verdad quedo derivado, no solo la respuesta.
    vista = await casos.get_case(aseguradora(), case_id)
    assert vista is not None
    assert vista.state is CaseState.DERIVED


async def test_pasarlo_dos_veces_dice_donde_esta_y_no_falla(app: FastAPI) -> None:
    """Un caso que ya no admite la derivacion no es un error de quien pide.

    Es que su salida ya esta tomada, y lo que se devuelve es donde quedo: un
    segundo clic desde una pestana vieja no puede dejar la pantalla con un error
    sobre algo que ya se hizo.
    """
    call_id, case_id, galleta = await _llamada(app)
    await _llevar_a(aseguradora(), case_id, CaseState.AWAITING_INSURED)

    async with cliente(app) as http:
        http.cookies.set(COOKIE, galleta)
        primera = await http.post(f"/api/voice/{aseguradora()}/sessions/{call_id}/handoff")
        segunda = await http.post(f"/api/voice/{aseguradora()}/sessions/{call_id}/handoff")

    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 200, segunda.text
    assert segunda.json()["state"] == "derived"


async def test_nadie_mas_puede_pasar_el_caso_de_otra_llamada(app: FastAPI) -> None:
    """La misma puerta que el desenlace: una llamada ajena no existe."""
    call_id, case_id, _ = await _llamada(app)
    await _llevar_a(aseguradora(), case_id, CaseState.AWAITING_INSURED)

    async with cliente(app) as http:
        http.cookies.set(COOKIE, "clave-de-otro")
        respuesta = await http.post(f"/api/voice/{aseguradora()}/sessions/{call_id}/handoff")

    assert respuesta.status_code == 404, respuesta.text
    vista = await casos.get_case(aseguradora(), case_id)
    assert vista is not None
    assert vista.state is CaseState.AWAITING_INSURED, "una peticion ajena movio el caso"
