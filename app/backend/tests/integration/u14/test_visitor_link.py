"""Las dos compuertas duras del enlace firmado (BR5.1, BR5.2) y su hora (BR5.3).

**BR5.1** — un enlace abre su caso y nunca la lista.
**BR5.2** — una firma alterada y un caso que no existe se responden igual.

Las dos se miden **comparando respuestas enteras**, no comprobando que un dato
ajeno no aparezca: la filtracion no es el dato, es la distincion. Y en las dos el
**control positivo va delante**: el enlace legitimo abre su caso antes de que se
compruebe que el ajeno no abre nada. Sin el, las dos aserciones pasan igual contra
una bandeja que no entregue nada nunca, que es el defecto que U13 encontro en su
propia prueba del resumen de traza.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI

from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record.models import (
    Actor,
    ActorType,
    CaseField,
    CaseState,
    Channel,
    FieldStatus,
)
from untangle.compliance.controls.api import HandoffReason
from untangle.inbox import decision, visitor
from untangle.orchestration import case_context, transcript_writer
from untangle.tenancy import api as tenancy
from untangle.tenancy import visitor_access
from untangle.tenancy.models import TenantKind

from .conftest import AHORA, CLAVE_DE_ENLACES, cliente, credencial_de, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u14")

#: Un token con la **forma** de uno bueno y una firma que no vale. Es lo que hay
#: que comparar contra el rechazo de un caso inexistente: si difirieran, probar
#: enlaces diria cual de los intentos acerto.
TOKEN_ALTERADO = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA." + "0" * 64


@pytest.fixture
def emisora() -> str:
    return next(
        t.tenant_id
        for t in sorted(tenancy.loaded().available, key=lambda c: c.tenant_id)
        if t.kind is TenantKind.CARRIER
    )


@pytest.fixture(autouse=True)
def reanudaciones(app: FastAPI) -> Any:
    """El puerto de reanudacion, enchufado despues de que la raiz construya."""
    del app
    llamadas: list[str] = []

    async def reanudar(case_id: str, resolucion: object, tenant_id: str) -> None:
        del resolucion, tenant_id
        llamadas.append(case_id)

    decision.install_resume_handler(reanudar)
    yield llamadas
    decision.reset_resume_handler()


def _reloj_real() -> datetime:
    """El instante de verdad.

    Las pruebas que entran **por la ruta** emiten con el reloj del proceso, porque
    la ruta usa el suyo: emitir con el instante fijo de la suite daria un enlace
    ya vencido y la prueba fallaria por la fecha y no por su conducta. Las que
    comprueban los dos bordes de la hora si pasan el reloj por argumento, que es
    para lo que existe.
    """
    return datetime.now(UTC)


async def _emitir(tenant_id: str, case_id: str, *, now: datetime | None = None) -> str:
    emitido = await visitor_access.issue_case_link(
        tenant_id=tenant_id,
        case_id=case_id,
        signing_key=CLAVE_DE_ENLACES,
        now=now if now is not None else _reloj_real(),
    )
    return emitido.token


async def _canjear(app: FastAPI, token: str) -> Any:
    async with cliente(app) as http:
        return await http.post(f"/api{visitor.REDEEM_PATH}", json={"token": token})


def _sin_rastro(respuesta: Any) -> dict[str, object]:
    cuerpo = dict(respuesta.json())
    assert cuerpo.pop("trace_id", None), "la respuesta de error no trae rastro (C-01)"
    return cuerpo


# --- El control positivo, delante ---------------------------------------------


async def test_un_enlace_legitimo_abre_su_caso(app: FastAPI, emisora: str) -> None:
    """Sin esto, las dos compuertas de abajo no significan nada."""
    caso = await nuevo_caso(emisora)
    token = await _emitir(emisora, caso)

    canje = await _canjear(app, token)

    assert canje.status_code == 200, canje.text
    cuerpo = canje.json()
    assert cuerpo["case_id"] == caso
    assert cuerpo["tenant"] == emisora
    assert cuerpo["access"] == "view_and_decide"
    assert visitor.CASE_COOKIE in canje.headers.get("set-cookie", "")


async def test_con_la_cookie_se_abre_el_caso_y_se_decide(app: FastAPI, emisora: str) -> None:
    """El recorrido entero del visitante, que es el otro control positivo."""
    caso = await nuevo_caso(emisora)
    token = await _emitir(emisora, caso)

    async with cliente(app) as http:
        canje = await http.post(f"/api{visitor.REDEEM_PATH}", json={"token": token})
        assert canje.status_code == 200
        vista = await http.get(f"/api/inbox/{emisora}/cases/{caso}")
        decidido = await http.post(
            f"/api/inbox/{emisora}/cases/{caso}/decision",
            json={"decision": "approve", "comment": "Lo apruebo yo mismo."},
            headers={"Idempotency-Key": "visitante-1"},
        )

    assert vista.status_code == 200, vista.text
    assert vista.json()["case_id"] == caso
    assert decidido.status_code == 202, decidido.text


async def test_una_credencial_de_personal_que_no_vale_no_le_quita_el_caso_al_visitante(
    app: FastAPI, emisora: str
) -> None:
    """2026-10-09: un navegador con una credencial vieja de la bandeja (vencida, o de
    otra aseguradora) no podia abrir su propio caso con el enlace: la credencial se
    miraba primero, se rechazaba y la cookie del caso ni se probaba."""
    caso = await nuevo_caso(emisora)
    token = await _emitir(emisora, caso)

    async with cliente(app) as http:
        canje = await http.post(f"/api{visitor.REDEEM_PATH}", json={"token": token})
        assert canje.status_code == 200
        http.cookies.set("untangle_staff", "una-credencial-que-no-vale")
        vista = await http.get(f"/api/inbox/{emisora}/cases/{caso}")
        cola = await http.get(f"/api/inbox/{emisora}/cases")

    assert vista.status_code == 200, vista.text
    # El enlace sigue sin abrir la cola: la credencial que no vale no suma nada.
    assert cola.status_code == 404


def _credencial_que_no_vale(tipo: str, emisora: str) -> str:
    """Las tres formas en que un navegador guarda una credencial de la bandeja que ya no sirve."""
    if tipo == "ilegible":
        return "una-credencial-que-no-vale"
    if tipo == "vencida":
        return credencial_de(emisora, now=_reloj_real() - timedelta(days=2))
    otra = next(t for t in sorted(tenancy.available_ids()) if t != emisora)
    return credencial_de(otra)


@pytest.mark.parametrize("tipo", ["ilegible", "vencida", "de_otra_aseguradora"])
async def test_una_credencial_que_no_vale_tampoco_le_quita_al_visitante_la_decision(
    app: FastAPI, emisora: str, tipo: str
) -> None:
    """2026-10-12: quien tenia una credencial vieja de la bandeja en el navegador abria su
    caso con el enlace, escribia su nota y al decidir leia «el enlace vencio mientras
    escribias». La ruta de decidir volvia a pedir la credencial aunque ya hubiera entrado
    por el enlace: arreglada para ver el caso el 2026-10-09, quedaba esta."""
    from untangle.case_record import history as historial

    caso = await nuevo_caso(emisora)
    token = await _emitir(emisora, caso)

    async with cliente(app, credencial=_credencial_que_no_vale(tipo, emisora)) as http:
        canje = await http.post(f"/api{visitor.REDEEM_PATH}", json={"token": token})
        assert canje.status_code == 200, "el control positivo: con el enlace vivo, entra"
        decidido = await http.post(
            f"/api/inbox/{emisora}/cases/{caso}/decision",
            json={"decision": "approve", "comment": "Lo apruebo yo mismo."},
            headers={"Idempotency-Key": f"visitante-vieja-{tipo}"},
        )

    assert decidido.status_code == 202, decidido.text
    # Y queda a nombre de un visitante: la credencial que no vale no suma nada, ni siquiera
    # un nombre en el registro.
    entradas = await historial.of_case(emisora, caso)
    assert any(e.actor.actor_id == decision.VISITOR_ACTOR_ID for e in entradas)


async def test_sin_el_enlace_una_credencial_que_no_vale_sigue_sin_dejar_decidir(
    app: FastAPI, emisora: str
) -> None:
    """El control contrario: la tolerancia es del enlace, no de la credencial rota.

    Sin cookie de caso, una credencial ilegible no decide nada; si la ruta la aceptara
    por haberse relajado, el arreglo de arriba seria un agujero y no una correccion."""
    caso = await nuevo_caso(emisora)

    async with cliente(app, credencial="una-credencial-que-no-vale") as http:
        decidido = await http.post(
            f"/api/inbox/{emisora}/cases/{caso}/decision",
            json={"decision": "approve", "comment": "Sin enlace."},
            headers={"Idempotency-Key": "sin-enlace-1"},
        )

    assert decidido.status_code == 404
    vista = await casos.get_case(emisora, caso)
    assert vista is not None
    assert vista.state is not CaseState.CLOSED


# --- BR5.1 [bloquea]: el enlace nunca abre la lista ---------------------------


async def test_una_sesion_de_enlace_no_abre_la_cola(app: FastAPI, emisora: str) -> None:
    """Con la cookie puesta, la cola responde igual que a quien no tiene nada.

    Mostrar la lista expondria casos de otros visitantes. Se comparan las dos
    respuestas enteras: comprobar solo que no hay filas dejaria pasar una cola
    vacia con un `200`, que ya dice que la aseguradora existe.
    """
    caso = await nuevo_caso(emisora)
    token = await _emitir(emisora, caso)

    async with cliente(app) as http:
        await http.post(f"/api{visitor.REDEEM_PATH}", json={"token": token})
        con_enlace = await http.get(f"/api/inbox/{emisora}/cases")
    async with cliente(app) as http:
        sin_nada = await http.get(f"/api/inbox/{emisora}/cases")

    assert con_enlace.status_code == 404
    assert con_enlace.status_code == sin_nada.status_code
    assert _sin_rastro(con_enlace) == _sin_rastro(sin_nada)


async def test_una_sesion_de_enlace_no_abre_otro_caso(app: FastAPI, emisora: str) -> None:
    """Autoriza **un** caso, no una aseguradora.

    El segundo caso existe de verdad y es de la misma aseguradora: con uno
    inventado, la prueba pasaria por no existir y no por estar cerrada.
    """
    suyo = await nuevo_caso(emisora)
    ajeno = await nuevo_caso(emisora)
    token = await _emitir(emisora, suyo)

    async with cliente(app) as http:
        await http.post(f"/api{visitor.REDEEM_PATH}", json={"token": token})
        el_suyo = await http.get(f"/api/inbox/{emisora}/cases/{suyo}")
        el_otro = await http.get(f"/api/inbox/{emisora}/cases/{ajeno}")

    assert el_suyo.status_code == 200
    assert el_otro.status_code == 404


# --- BR5.2 [bloquea]: una sola via de rechazo ---------------------------------


async def test_la_firma_alterada_y_el_caso_inexistente_responden_igual(
    app: FastAPI, emisora: str
) -> None:
    """Campo por campo, salvo el rastro de la peticion, que cambia por diseno.

    Un mensaje distinto por causa le dice a quien prueba enlaces cual de sus
    intentos acerto el identificador de un caso.
    """
    # El control positivo primero: con un enlace bueno esto entrega algo.
    caso = await nuevo_caso(emisora)
    bueno = await _canjear(app, await _emitir(emisora, caso))
    assert bueno.status_code == 200

    alterado = await _canjear(app, TOKEN_ALTERADO)
    inexistente = await _canjear(app, "no-es-un-token")

    assert alterado.status_code == 404
    assert alterado.status_code == inexistente.status_code
    assert _sin_rastro(alterado) == _sin_rastro(inexistente)
    assert visitor.CASE_COOKIE not in alterado.headers.get("set-cookie", "")


async def test_un_enlace_de_otra_aseguradora_no_abre_nada(
    app: FastAPI, dos_aseguradoras: tuple[str, str]
) -> None:
    """El enlace lleva su aseguradora dentro; pedir el caso desde otra no vale."""
    ajena, propia = dos_aseguradoras
    caso_ajeno = await nuevo_caso(ajena)
    token = await _emitir(ajena, caso_ajeno)

    async with cliente(app) as http:
        canje = await http.post(f"/api{visitor.REDEEM_PATH}", json={"token": token})
        desde_otra = await http.get(f"/api/inbox/{propia}/cases/{caso_ajeno}")

    assert canje.status_code == 200, "el canje deberia encontrar su aseguradora"
    assert canje.json()["tenant"] == ajena
    assert desde_otra.status_code == 404


# --- BR5.3: la hora, por los dos bordes ---------------------------------------


async def test_los_dos_bordes_de_la_hora(app: FastAPI, emisora: str) -> None:
    """A los 59:59 da acceso; a los 60:01 dice que caduco.

    El reloj entra por argumento, que es lo que permite probar los dos bordes sin
    esperar una hora. Los dos juntos: probar solo el de dentro no prueba el borde.
    """
    caso = await nuevo_caso(emisora)
    token = await _emitir(emisora, caso, now=AHORA)

    casi = await visitor.redeem(
        token,
        signing_key=CLAVE_DE_ENLACES,
        now=AHORA + timedelta(minutes=59, seconds=59),
    )
    assert casi.case_id == caso

    with pytest.raises(visitor.CaseSessionInvalidError):
        await visitor.redeem(
            token,
            signing_key=CLAVE_DE_ENLACES,
            now=AHORA + timedelta(minutes=60, seconds=1),
        )


async def test_la_cookie_no_vive_mas_que_el_enlace(app: FastAPI, emisora: str) -> None:
    """Si viviera mas, el vencimiento del enlace dejaria de significar nada."""
    caso = await nuevo_caso(emisora)
    token = await _emitir(emisora, caso, now=AHORA)
    sesion = await visitor.redeem(token, signing_key=CLAVE_DE_ENLACES, now=AHORA)

    restante = visitor.cookie_max_age(sesion, now=AHORA + timedelta(minutes=59))

    assert 0 < restante <= 60, f"la cookie pediria {restante} s y al enlace le queda un minuto"
    assert visitor.cookie_max_age(sesion, now=AHORA + timedelta(hours=2)) == 0


async def test_un_enlace_vencido_no_decide_aunque_la_cookie_siga_puesta(
    app: FastAPI, emisora: str
) -> None:
    """BR5.4: si vence mientras se escribe el comentario, la decision no se aplica.

    La cookie se obtiene con un enlace vivo y despues se usa cuando ya vencio: es
    exactamente lo que le pasa a quien tarda una hora escribiendo. Se comprueba en
    **cada** peticion y no solo al canjear; si solo se comprobara al canjear, la
    sesion duraria lo que dure la pestana abierta.
    """
    caso = await nuevo_caso(emisora)
    # Emitido hace 59 minutos: vivo para canjear, vencido un minuto despues.
    token = await _emitir(emisora, caso, now=_reloj_real() - timedelta(minutes=59, seconds=30))

    async with cliente(app) as http:
        canje = await http.post(f"/api{visitor.REDEEM_PATH}", json={"token": token})
        assert canje.status_code == 200, "el control positivo: con el enlace vivo, entra"
        vencido = await _con_el_enlace_vencido(http, emisora, caso)

    assert vencido.status_code == 404
    from untangle.case_record import api as casos

    vista = await casos.get_case(emisora, caso)
    assert vista is not None
    assert vista.state is not CaseState.CLOSED, "la decision se aplico con el enlace vencido"


async def _con_el_enlace_vencido(http: Any, tenant_id: str, case_id: str) -> Any:
    """Decide cuando el enlace ya vencio, moviendo el reloj del aplicativo.

    Se mueve el reloj y no se espera una hora: el enlace vive una hora exacta y
    esperarla convertiria esta prueba en un cronometro.
    """
    from datetime import timedelta as _td

    from untangle.inbox import api as inbox_api

    real = inbox_api._ahora
    inbox_api._ahora = lambda: real() + _td(hours=2)
    try:
        return await http.post(
            f"/api/inbox/{tenant_id}/cases/{case_id}/decision",
            json={"decision": "approve", "comment": "Tarde una hora escribiendo esto."},
            headers={"Idempotency-Key": "vencido-1"},
        )
    finally:
        inbox_api._ahora = real


# --- BR5.5: quien decidio con un enlace no es una persona de la aseguradora ----


async def test_la_decision_con_enlace_se_atribuye_a_un_visitante(
    app: FastAPI, emisora: str
) -> None:
    """Y nunca a quien tiene credencial.

    Falsificar esto falsificaria la respuesta a "quien decidio", que es justo lo
    que la explicacion del caso existe para contestar.
    """
    from untangle.case_record import history as historial
    from untangle.case_record.models import ActorType

    caso = await nuevo_caso(emisora)
    token = await _emitir(emisora, caso)

    async with cliente(app) as http:
        await http.post(f"/api{visitor.REDEEM_PATH}", json={"token": token})
        await http.post(
            f"/api/inbox/{emisora}/cases/{caso}/decision",
            json={"decision": "approve", "comment": "Lo apruebo yo mismo."},
            headers={"Idempotency-Key": "visitante-2"},
        )

    entradas = await historial.of_case(emisora, caso)
    cierre = [e for e in entradas if e.actor.actor_id == decision.VISITOR_ACTOR_ID]
    assert cierre, "la decision no quedo a nombre de un visitante"
    assert all(e.actor.actor_type is not ActorType.STAFF for e in cierre)


async def test_el_visitante_sabe_que_decidio_un_ajustador_pero_no_cual(
    app: FastAPI, emisora: str
) -> None:
    """El identificador del personal viaja a quien entra con credencial, no al del enlace."""
    caso = await nuevo_caso(emisora)
    token = await _emitir(emisora, caso)

    async with cliente(app, credencial=credencial_de(emisora)) as http:
        decidido = await http.post(
            f"/api/inbox/{emisora}/cases/{caso}/decision",
            json={"decision": "approve", "comment": "Aprobado por la ajustadora."},
            headers={"Idempotency-Key": "ajustadora-1"},
        )
        con_credencial = await http.get(f"/api/inbox/{emisora}/cases/{caso}")
    assert decidido.status_code == 202, decidido.text

    async with cliente(app) as http:
        await http.post(f"/api{visitor.REDEEM_PATH}", json={"token": token})
        con_enlace = await http.get(f"/api/inbox/{emisora}/cases/{caso}")

    assert con_enlace.status_code == 200, con_enlace.text
    para_el_visitante = con_enlace.json()["explanation"]
    assert para_el_visitante["decided_by"] == "present"
    assert para_el_visitante["decided_by_kind"] == "staff"
    assert para_el_visitante["decided_by_id"] is None
    # El control: la misma ruta, con credencial, si lo nombra.
    quien = con_credencial.json()["explanation"]["decided_by_id"]
    assert quien
    assert quien not in con_enlace.text


async def test_la_credencial_manda_sobre_la_cookie(app: FastAPI, emisora: str) -> None:
    """Con las dos puestas decide la persona, y el registro dice su nombre.

    Al reves, un ajustador con una pestana vieja abierta quedaria registrado como
    "un visitante", que es una mentira en el unico registro que no puede mentir.
    """
    from untangle.case_record import history as historial

    caso = await nuevo_caso(emisora)
    token = await _emitir(emisora, caso)

    async with cliente(app, credencial=credencial_de(emisora)) as http:
        await http.post(f"/api{visitor.REDEEM_PATH}", json={"token": token})
        await http.post(
            f"/api/inbox/{emisora}/cases/{caso}/decision",
            json={"decision": "approve", "comment": "Aprobado por la ajustadora."},
            headers={"Idempotency-Key": "ambas-1"},
        )

    entradas = await historial.of_case(emisora, caso)
    autores = {e.actor.actor_id for e in entradas}
    assert decision.VISITOR_ACTOR_ID not in autores


async def test_un_caso_derivado_en_una_conversacion_se_puede_decidir(
    app: FastAPI, emisora: str
) -> None:
    """El recorrido principal de la demo, tal como ocurre: el chat deriva el caso
    **con el turno en que lo dijo**, y despues alguien lo decide.

    Visto el 2026-10-11: respondia un error interno. Las pruebas de arriba derivan
    el caso sin turno, que es una derivacion que en produccion no existe, y por eso
    no lo veian.
    """
    caso = await nuevo_caso(emisora, estado=CaseState.CAPTURING)
    turno = await transcript_writer.record_agent_turn(
        transcript_writer.TranscriptScope(
            tenant_id=emisora, case_id=caso, channel=Channel.CHAT, language="es"
        ),
        text="Tu caso queda con un ajustador.",
        now=AHORA,
        from_catalog=True,
    )
    derivado = await case_context.derive_case(
        tenant_id=emisora, case_id=caso, reason=HandoffReason.RULE, turn_id=turno, now=AHORA
    )
    assert derivado is True
    token = await _emitir(emisora, caso)

    async with cliente(app) as http:
        await http.post(f"/api{visitor.REDEEM_PATH}", json={"token": token})
        decidido = await http.post(
            f"/api/inbox/{emisora}/cases/{caso}/decision",
            json={"decision": "approve", "comment": "Lo apruebo yo mismo."},
            headers={"Idempotency-Key": "visitante-derivado-1"},
        )
        vista = await http.get(f"/api/inbox/{emisora}/cases/{caso}")

    assert decidido.status_code == 202, decidido.text
    assert vista.json()["state"] == "closed"


# --- Lo anotado, a su dueno y a nadie mas (decision de Miguel del 2026-10-11) -------


async def _anotar_heridos(tenant_id: str, case_id: str, cifrador: crypto.Cipher) -> None:
    await casos.set_field(
        tenant_id,
        CaseField(
            case_id=case_id,
            field_key="injuries",
            value=cifrador.seal("nadie salió herido"),
            status=FieldStatus.CONFIRMED,
            evidence_turn_id="turno-heridos",
            confirmed_aloud_at=AHORA,
            updated_at=AHORA,
        ),
        cipher=cifrador,
        actor=Actor(actor_type=ActorType.INSURED),
    )


def _heridos(vista: Any) -> dict[str, Any]:
    return next(c for c in vista.json()["fields"] if c["field_key"] == "injuries")


async def test_quien_entra_con_su_enlace_ve_lo_que_quedo_anotado(
    app: FastAPI, emisora: str, cifrador: crypto.Cipher
) -> None:
    """La pantalla decia "Completo" y quien decidia el caso no veia que se anoto."""
    caso = await nuevo_caso(emisora)
    await _anotar_heridos(emisora, caso, cifrador)
    token = await _emitir(emisora, caso)

    async with cliente(app) as http:
        await http.post(f"/api{visitor.REDEEM_PATH}", json={"token": token})
        vista = await http.get(f"/api/inbox/{emisora}/cases/{caso}")

    assert vista.status_code == 200, vista.text
    assert _heridos(vista)["value"] == "nadie salió herido"
    # Sus propias palabras, en claro: no se guardan en ninguna cache intermedia.
    assert "no-store" in vista.headers["cache-control"]
    sin_anotar = [c for c in vista.json()["fields"] if c["field_key"] != "injuries"]
    assert sin_anotar
    assert all(c["value"] is None for c in sin_anotar)


async def test_una_credencial_de_la_bandeja_no_recibe_lo_anotado(
    app: FastAPI, emisora: str, cifrador: crypto.Cipher
) -> None:
    """El valor viaja solo al dueno del caso: lo que lee la bandeja es la
    transcripcion, ya redactada."""
    caso = await nuevo_caso(emisora)
    await _anotar_heridos(emisora, caso, cifrador)

    async with cliente(app, credencial=credencial_de(emisora)) as http:
        vista = await http.get(f"/api/inbox/{emisora}/cases/{caso}")

    assert vista.status_code == 200, vista.text
    assert _heridos(vista)["complete"] is True
    assert all(c["value"] is None for c in vista.json()["fields"])


async def test_los_datos_opcionales_se_dicen_opcionales(app: FastAPI, emisora: str) -> None:
    """El contador dice "5 de 5" y la lista trae mas filas: las de mas son las que
    se ofrecen al final y no cuentan."""
    caso = await nuevo_caso(emisora)

    async with cliente(app, credencial=credencial_de(emisora)) as http:
        vista = await http.get(f"/api/inbox/{emisora}/cases/{caso}")

    cuerpo = vista.json()
    obligatorios = [c for c in cuerpo["fields"] if not c["optional"]]
    assert len(obligatorios) == cuerpo["completeness_total"]
    assert len(cuerpo["fields"]) > len(obligatorios)
