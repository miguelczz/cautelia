"""La ruta de anotar para las reglas, por HTTP: quien entra, que se rechaza y que ve cada uno.

Todo por la puerta. Que la pantalla no ofrezca el formulario es cortesia; lo que de verdad
lo impide es que la peticion directa se rechace, y eso solo se ve entrando por la ruta.

Los controles positivos van delante de cada rechazo (el ajustador anota, el caso derivado
admite), porque un rechazo comprobado contra una ruta que rechazara siempre no significa nada.
Las reglas son las reales de cada aseguradora, por su identificador.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI

from untangle.case_record import api as casos
from untangle.case_record import crypto, history
from untangle.case_record.models import CaseState, ChangeKind
from untangle.inbox import correction, events, triage_notes
from untangle.inbox import visitor as enlace
from untangle.rules import api as reglas
from untangle.tenancy import staff_identity, visitor_access

from .conftest import (
    CLAVE_DE_BANDEJA,
    CLAVE_DE_ENLACES,
    cerrado_por_las_reglas,
    cliente,
    credencial_de,
    nuevo_caso,
)

pytestmark = pytest.mark.usefixtures("base_de_u14")

#: Las aseguradoras cuyas reglas se nombran aqui. Una agencia (`KNOTWELL`) y un suscriptor
#: (`NADIA`) sirven para el rechazo por rol: sus credenciales son las de la tabla versionada.
CON_REGLAS = "sunmeadow"
OTRA = "stonecroft"
AGENCIA = "knotwell"
SUSCRIPTOR = "nadia-ferris"

TODO_SIN_ANOTAR: dict[str, Any] = {
    "claim_amount": None,
    "coverage_disputed": None,
    "fraud_suspected": None,
}


def _ruta(tenant_id: str, case_id: str) -> str:
    return f"/api/inbox/{tenant_id}/cases/{case_id}/triage-note"


def _vista(tenant_id: str, case_id: str) -> str:
    return f"/api/inbox/{tenant_id}/cases/{case_id}"


def _credencial_de_la_persona(tenant_id: str, principal_id: str) -> str:
    return staff_identity.issue_credential(
        tenant_id=tenant_id,
        principal_id=principal_id,
        signing_key=CLAVE_DE_BANDEJA,
        now=datetime.now(UTC),
    )


async def _anotar(  # noqa: PLR0913 -- la ruta, el cuerpo, la clave y quien entra
    app: FastAPI,
    tenant_id: str,
    case_id: str,
    cuerpo: dict[str, Any],
    *,
    clave: str | None = "anota-1",
    credencial: str | None = None,
) -> Any:
    cabeceras = {"Idempotency-Key": clave} if clave is not None else {}
    async with cliente(app, credencial=credencial or credencial_de(tenant_id)) as http:
        return await http.put(_ruta(tenant_id, case_id), json=cuerpo, headers=cabeceras)


async def _ver(app: FastAPI, tenant_id: str, case_id: str, *, credencial: str | None = None) -> Any:
    async with cliente(app, credencial=credencial or credencial_de(tenant_id)) as http:
        return (await http.get(_vista(tenant_id, case_id))).json()


# --- El ajustador anota y la vista muestra la evaluacion nueva ------------------------


async def test_el_ajustador_anota_y_la_vista_muestra_la_evaluacion_nueva(app: FastAPI) -> None:
    caso = await nuevo_caso(CON_REGLAS)
    antes = await _ver(app, CON_REGLAS, caso)
    assert antes["rule_category"] is None
    assert antes["triage_note"] is None
    assert antes["can_annotate_triage"] is True

    respuesta = await _anotar(
        app, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"claim_amount": 1500, "fraud_suspected": True}
    )

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["receipt_id"]
    assert cuerpo["rule_category"] == "referral"
    assert set(cuerpo["fired_rules"]) == {"SUN-R-03", "SUN-R-07"}

    despues = await _ver(app, CON_REGLAS, caso)
    assert despues["rule_category"] == "referral"
    assert set(despues["fired_rules"]) == {"SUN-R-03", "SUN-R-07"}
    assert despues["triage_note"] == {
        "claim_amount": 1500,
        "coverage_disputed": None,
        "fraud_suspected": True,
    }
    assert despues["state"] == antes["state"], "anotar cambio el estado del caso"


async def test_la_vista_muestra_la_ultima_evaluacion_tambien_al_quitar_lo_anotado(
    app: FastAPI,
) -> None:
    caso = await nuevo_caso(CON_REGLAS)
    await _anotar(app, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"fraud_suspected": True}, clave="a")
    assert (await _ver(app, CON_REGLAS, caso))["rule_category"] == "referral"

    quitada = await _anotar(app, CON_REGLAS, caso, TODO_SIN_ANOTAR, clave="b")

    assert quitada.status_code == 200, quitada.text
    despues = await _ver(app, CON_REGLAS, caso)
    assert despues["fired_rules"] == ["SUN-R-10"]
    assert despues["rule_category"] == "standard_review"
    assert despues["triage_note"] is None, "quitar todo deja el caso como si nadie hubiera anotado"


async def test_sin_anotar_no_dispara_y_un_no_comprobado_tampoco(app: FastAPI) -> None:
    caso = await nuevo_caso(CON_REGLAS)

    sin_anotar = await _anotar(app, CON_REGLAS, caso, TODO_SIN_ANOTAR, clave="a")
    con_no = await _anotar(
        app,
        CON_REGLAS,
        caso,
        TODO_SIN_ANOTAR | {"coverage_disputed": False, "fraud_suspected": False},
        clave="b",
    )

    assert sin_anotar.json()["fired_rules"] == ["SUN-R-10"]
    assert con_no.json()["fired_rules"] == ["SUN-R-10"]
    nota = (await _ver(app, CON_REGLAS, caso))["triage_note"]
    assert nota == {"claim_amount": None, "coverage_disputed": False, "fraud_suspected": False}


async def test_el_monto_por_encima_del_umbral_dispara_la_regla_de_monto(app: FastAPI) -> None:
    caso = await nuevo_caso(CON_REGLAS)

    respuesta = await _anotar(app, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"claim_amount": 12000})

    assert set(respuesta.json()["fired_rules"]) == {"SUN-R-03", "SUN-R-04"}


async def test_anotar_deja_su_entrada_de_historial_y_su_aviso(app: FastAPI) -> None:
    caso = await nuevo_caso(CON_REGLAS)

    await _anotar(app, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"coverage_disputed": True})

    entradas = [
        e
        for e in await history.of_case(CON_REGLAS, caso)
        if e.change_kind is ChangeKind.TRIAGE_NOTED
    ]
    assert [(e.field_key, e.detail, e.actor.actor_type.value) for e in entradas] == [
        ("coverage_disputed", "unset -> true", "staff")
    ]
    assert entradas[0].actor.actor_id == "marcus-webb"
    avisos = [a for a in await events.since(CON_REGLAS, 0) if a.case_id == caso]
    assert [a.kind for a in avisos] == [events.EventKind.CASE_UPDATED]


# --- Quien puede ----------------------------------------------------------------------


async def test_sin_credencial_no_se_anota(app: FastAPI) -> None:
    caso = await nuevo_caso(CON_REGLAS)

    async with cliente(app) as http:
        respuesta = await http.put(
            _ruta(CON_REGLAS, caso),
            json=TODO_SIN_ANOTAR,
            headers={"Idempotency-Key": "k"},
        )

    assert respuesta.status_code == 404


async def test_la_agencia_y_el_suscriptor_no_anotan_y_no_se_les_ofrece(app: FastAPI) -> None:
    """Estimar un monto o dudar de una cobertura es del ajustador de la aseguradora."""
    de_la_agencia = await nuevo_caso(AGENCIA)
    del_suscriptor = await nuevo_caso(CON_REGLAS)
    agente = _credencial_de_la_persona(AGENCIA, "priya-raman")
    suscriptor = _credencial_de_la_persona(CON_REGLAS, SUSCRIPTOR)

    # Los controles: el ajustador de la misma aseguradora, sobre su caso, si se la ofrece.
    assert (await _ver(app, CON_REGLAS, del_suscriptor))["can_annotate_triage"] is True

    for tenant_id, caso, credencial in (
        (AGENCIA, de_la_agencia, agente),
        (CON_REGLAS, del_suscriptor, suscriptor),
    ):
        anota = await _anotar(
            app, tenant_id, caso, TODO_SIN_ANOTAR | {"fraud_suspected": True}, credencial=credencial
        )
        vista = await _ver(app, tenant_id, caso, credencial=credencial)

        assert anota.status_code == 404, (tenant_id, anota.text)
        assert vista["can_annotate_triage"] is False, tenant_id
        assert await triage_notes.read(tenant_id, caso) is None


async def test_el_ajustador_de_otra_aseguradora_no_anota_ni_ve_el_caso_ajeno(
    app: FastAPI,
) -> None:
    ajeno = await nuevo_caso(CON_REGLAS)
    de_otra = _credencial_de_la_persona(OTRA, "diana")

    # Por la direccion de la otra aseguradora, con la credencial de la otra...
    con_su_direccion = await _anotar(
        app, OTRA, ajeno, TODO_SIN_ANOTAR | {"fraud_suspected": True}, credencial=de_otra
    )
    # ...y por la direccion de la duena, con una credencial que no es suya.
    con_la_ajena = await _anotar(
        app, CON_REGLAS, ajeno, TODO_SIN_ANOTAR | {"fraud_suspected": True}, credencial=de_otra
    )

    assert con_su_direccion.status_code == 404
    assert con_la_ajena.status_code == 404
    assert await triage_notes.read(CON_REGLAS, ajeno) is None
    assert not await reglas.evaluations_for(CON_REGLAS, ajeno)


async def test_lo_anotado_por_una_aseguradora_no_lo_lee_la_otra(app: FastAPI) -> None:
    """Misma lectura, otra aseguradora: el caso ni siquiera abre."""
    caso = await nuevo_caso(CON_REGLAS)
    await _anotar(app, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"claim_amount": 4321})

    async with cliente(app, credencial=_credencial_de_la_persona(OTRA, "diana")) as http:
        respuesta = await http.get(_vista(OTRA, caso))

    assert respuesta.status_code == 404
    assert "4321" not in respuesta.text


# --- El estado del caso ---------------------------------------------------------------


@pytest.mark.parametrize(
    "estado",
    [CaseState.OPEN, CaseState.CAPTURING, CaseState.VERIFYING, CaseState.DECIDING],
)
async def test_un_caso_que_la_agente_aun_lleva_responde_conflicto_y_no_escribe(
    app: FastAPI, estado: CaseState
) -> None:
    caso = await nuevo_caso(CON_REGLAS, estado=estado)

    respuesta = await _anotar(app, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"fraud_suspected": True})
    vista = await _ver(app, CON_REGLAS, caso)

    assert respuesta.status_code == 409, respuesta.text
    assert vista["can_annotate_triage"] is False
    assert await triage_notes.read(CON_REGLAS, caso) is None
    assert not await reglas.evaluations_for(CON_REGLAS, caso)


async def test_un_caso_cerrado_responde_conflicto_y_no_se_ofrece(app: FastAPI) -> None:
    abierto = await nuevo_caso(CON_REGLAS)
    cerrado = await cerrado_por_las_reglas(CON_REGLAS)

    acepta = await _anotar(app, CON_REGLAS, abierto, TODO_SIN_ANOTAR, clave="a")
    rechaza = await _anotar(app, CON_REGLAS, cerrado, TODO_SIN_ANOTAR, clave="b")
    vista = await _ver(app, CON_REGLAS, cerrado)

    assert acepta.status_code == 200
    assert rechaza.status_code == 409
    assert vista["can_annotate_triage"] is False
    assert await triage_notes.read(CON_REGLAS, cerrado) is None


@pytest.mark.parametrize("estado", [CaseState.DERIVED, CaseState.AWAITING_INSURED])
async def test_un_caso_con_un_ajustador_o_esperando_al_asegurado_admite_y_ofrece(
    app: FastAPI, estado: CaseState
) -> None:
    caso = await nuevo_caso(CON_REGLAS, estado=estado)

    respuesta = await _anotar(app, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"fraud_suspected": True})
    vista = await _ver(app, CON_REGLAS, caso)

    assert respuesta.status_code == 200, respuesta.text
    assert vista["can_annotate_triage"] is True


async def test_un_caso_que_no_existe_responde_como_uno_ajeno(app: FastAPI) -> None:
    respuesta = await _anotar(app, CON_REGLAS, "caso-que-no-existe", TODO_SIN_ANOTAR)

    assert respuesta.status_code == 404


# --- Idempotencia y validacion --------------------------------------------------------


async def test_la_misma_clave_devuelve_la_primera_y_no_escribe_dos_veces(app: FastAPI) -> None:
    caso = await nuevo_caso(CON_REGLAS)
    cuerpo = TODO_SIN_ANOTAR | {"claim_amount": 2500, "fraud_suspected": True}

    primera = await _anotar(app, CON_REGLAS, caso, cuerpo, clave="la-misma")
    segunda = await _anotar(app, CON_REGLAS, caso, cuerpo, clave="la-misma")

    assert primera.status_code == 200
    assert segunda.status_code == 200
    assert segunda.json() == primera.json()
    assert len(await reglas.evaluations_for(CON_REGLAS, caso)) == 1
    entradas = [
        e
        for e in await history.of_case(CON_REGLAS, caso)
        if e.change_kind is ChangeKind.TRIAGE_NOTED
    ]
    assert len(entradas) == 2, "la repeticion escribio otra vez en el historial"


async def test_una_clave_reciclada_para_otra_anotacion_es_un_conflicto(app: FastAPI) -> None:
    caso = await nuevo_caso(CON_REGLAS)
    await _anotar(app, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"claim_amount": 100}, clave="r")

    otra = await _anotar(app, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"claim_amount": 200}, clave="r")

    assert otra.status_code == 409
    nota = await triage_notes.read(CON_REGLAS, caso)
    assert nota is not None
    assert nota.values.claim_amount == 100


async def test_sin_clave_de_idempotencia_no_se_anota(app: FastAPI) -> None:
    caso = await nuevo_caso(CON_REGLAS)

    respuesta = await _anotar(app, CON_REGLAS, caso, TODO_SIN_ANOTAR, clave=None)

    assert respuesta.status_code == 422
    assert await triage_notes.read(CON_REGLAS, caso) is None


@pytest.mark.parametrize(
    "cuerpo",
    [
        pytest.param(TODO_SIN_ANOTAR | {"claim_amount": -1}, id="monto-negativo"),
        pytest.param(TODO_SIN_ANOTAR | {"claim_amount": 10_000_001}, id="monto-descomunal"),
        pytest.param(TODO_SIN_ANOTAR | {"claim_amount": "1500"}, id="monto-en-texto"),
        pytest.param(TODO_SIN_ANOTAR | {"claim_amount": 15.5}, id="monto-con-decimales"),
        pytest.param(TODO_SIN_ANOTAR | {"claim_amount": True}, id="monto-booleano"),
        pytest.param(TODO_SIN_ANOTAR | {"coverage_disputed": "si"}, id="cobertura-en-texto"),
        pytest.param(TODO_SIN_ANOTAR | {"fraud_suspected": 1}, id="fraude-numerico"),
        pytest.param({"claim_amount": 100}, id="cuerpo-parcial"),
        pytest.param(TODO_SIN_ANOTAR | {"otro_dato": True}, id="dato-de-mas"),
    ],
)
async def test_un_cuerpo_invalido_se_rechaza_sin_escribir(
    app: FastAPI, cuerpo: dict[str, Any]
) -> None:
    caso = await nuevo_caso(CON_REGLAS)

    respuesta = await _anotar(app, CON_REGLAS, caso, cuerpo)

    assert respuesta.status_code == 422, respuesta.text
    assert await triage_notes.read(CON_REGLAS, caso) is None
    assert not await reglas.evaluations_for(CON_REGLAS, caso)


async def test_los_extremos_validos_se_aceptan(app: FastAPI) -> None:
    """El control de la prueba de arriba: cero y el tope entran."""
    cero = await nuevo_caso(CON_REGLAS)
    tope = await nuevo_caso(CON_REGLAS)

    en_cero = await _anotar(
        app, CON_REGLAS, cero, TODO_SIN_ANOTAR | {"claim_amount": 0}, clave="cero"
    )
    en_el_tope = await _anotar(
        app,
        CON_REGLAS,
        tope,
        TODO_SIN_ANOTAR | {"claim_amount": triage_notes.MAX_CLAIM_AMOUNT},
        clave="tope",
    )

    assert en_cero.status_code == 200
    assert en_cero.json()["fired_rules"] == ["SUN-R-09"]
    assert en_el_tope.status_code == 200


# --- Lo anotado no le llega al asegurado ----------------------------------------------


async def _con_heridos(tenant_id: str, case_id: str) -> None:
    """La persona conto que hubo heridos: una regla que se dispara con **sus** palabras."""
    await correction.apply(
        tenant_id,
        case_id=case_id,
        field_key="injuries",
        value="si, mi hijo se golpeo la cabeza",
        idempotency_key=f"heridos-{case_id}",
        principal_id="marcus-webb",
        cipher=crypto.active(),
        language="es",
        now=datetime.now(UTC),
    )


async def test_el_monto_y_lo_anotado_no_llegan_a_la_pantalla_del_visitante(app: FastAPI) -> None:
    """Lo que anota el personal: ni el valor, ni que una regla de fraude o de dinero dispararon,
    ni un hueco donde estaban. (Lo que el visitante anota haciendo de ajustador si lo ve el, y
    esta en `test_triage_note_visitor_route.py`.)

    Se compara la respuesta **entera** del visitante antes y despues de anotar: lo que se
    comprueba no es que un numero no aparezca, sino que lo anotado no cambie nada de lo que
    el asegurado ve. Con el control positivo delante: el ajustador si lo ve, y el visitante
    si ve la regla que disparo lo que el mismo conto.
    """
    caso = await nuevo_caso(CON_REGLAS)
    await _con_heridos(CON_REGLAS, caso)
    emitido = await visitor_access.issue_case_link(
        tenant_id=CON_REGLAS,
        case_id=caso,
        signing_key=CLAVE_DE_ENLACES,
        now=datetime.now(UTC),
    )
    # La primera evaluacion, sin nada anotado: heridos sale de lo que la persona dijo.
    await _anotar(app, CON_REGLAS, caso, TODO_SIN_ANOTAR, clave="base")

    async def _lo_que_ve_el_visitante() -> Any:
        async with cliente(app) as http:
            await http.post(f"/api{enlace.REDEEM_PATH}", json={"token": emitido.token})
            return await http.get(_vista(CON_REGLAS, caso))

    antes = await _lo_que_ve_el_visitante()
    assert antes.status_code == 200, antes.text
    assert antes.json()["fired_rules"] == ["SUN-R-05"], (
        "el control: sus propias palabras si cuentan"
    )

    await _anotar(
        app,
        CON_REGLAS,
        caso,
        TODO_SIN_ANOTAR
        | {"claim_amount": 7318, "coverage_disputed": True, "fraud_suspected": True},
        clave="anota",
    )
    despues = await _lo_que_ve_el_visitante()

    assert despues.status_code == 200, despues.text
    cuerpo = despues.json()
    assert cuerpo["triage_note"] is None
    assert cuerpo["can_annotate_triage"] is False
    assert cuerpo["triage_amount_steps"] == [], "la ayuda de quien anota llego a quien no puede"
    assert cuerpo["fired_rules"] == ["SUN-R-05"], "una regla de lo anotado llego al visitante"
    for rastro in ("7318", "7.318", "7,318", "SUN-R-02", "SUN-R-03", "SUN-R-04", "SUN-R-07"):
        assert rastro not in despues.text, f"'{rastro}' aparece en la pantalla del visitante"
    # El control del otro lado: el ajustador si ve todo lo anotado y todo lo que disparo.
    del_ajustador = await _ver(app, CON_REGLAS, caso)
    assert del_ajustador["triage_note"]["claim_amount"] == 7318
    assert {"SUN-R-02", "SUN-R-03", "SUN-R-07", "SUN-R-05"} <= set(del_ajustador["fired_rules"])
    # Y la transcripcion, que es lo que el chat le muestra, no se movio.
    assert cuerpo["transcript"] == antes.json()["transcript"]


async def test_el_caso_de_ejemplo_publico_tampoco_lo_ve(app: FastAPI) -> None:
    """La pagina publica de casos lee los del generador sin credencial: nada de lo anotado."""
    caso = await nuevo_caso(CON_REGLAS)
    await _con_heridos(CON_REGLAS, caso)
    await _anotar(app, CON_REGLAS, caso, TODO_SIN_ANOTAR, clave="base")
    await _anotar(
        app,
        CON_REGLAS,
        caso,
        TODO_SIN_ANOTAR | {"claim_amount": 7318, "fraud_suspected": True},
        clave="anota",
    )

    async with cliente(app) as http:
        publico = await http.get(f"/api/examples/{CON_REGLAS}/cases/{caso}")

    assert publico.status_code == 200, publico.text
    cuerpo = publico.json()
    assert cuerpo["triage_note"] is None
    assert cuerpo["can_annotate_triage"] is False
    assert cuerpo["triage_amount_steps"] == []
    assert cuerpo["fired_rules"] == ["SUN-R-05"]
    assert "7318" not in publico.text
    assert "SUN-R-07" not in publico.text


async def test_anotar_no_escribe_en_la_conversacion_del_chat(app: FastAPI) -> None:
    caso = await nuevo_caso(CON_REGLAS)
    antes = await casos.transcript_of(CON_REGLAS, caso)

    await _anotar(app, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"claim_amount": 7318})

    assert await casos.transcript_of(CON_REGLAS, caso) == antes
