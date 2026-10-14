"""Anotar para las reglas con el enlace del caso, por HTTP: quien entra, que ve y que se rechaza.

El visitante que hace de ajustador anota **su propio caso** y nada mas, ve lo que el anoto y
lo que las reglas hicieron con ello, y no ve ni pisa lo que anoto una persona de la
aseguradora. Todo por la puerta: que la pantalla no ofrezca el bloque es cortesia; lo que de
verdad lo impide es que la peticion directa se rechace.

Los controles positivos van delante de cada rechazo (el enlace bueno anota, el personal si pisa
la nota del visitante, el tope corta en el borde), porque un rechazo comprobado contra una ruta
que rechazara siempre no significa nada. Las reglas son las reales de cada aseguradora.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2
import pytest
from fastapi import FastAPI

from untangle.case_record import history
from untangle.case_record.models import Actor, ActorType, CaseChange, CaseState, ChangeKind
from untangle.inbox import annotation, decision, events, triage_notes
from untangle.inbox import visitor as enlace
from untangle.rules import api as reglas
from untangle.tenancy import staff_identity, visitor_access

from .conftest import (
    AHORA,
    CLAVE_DE_BANDEJA,
    CLAVE_DE_ENLACES,
    cerrado_por_las_reglas,
    cliente,
    credencial_de,
    nuevo_caso,
)

pytestmark = pytest.mark.usefixtures("base_de_u14")

CON_REGLAS = "sunmeadow"
OTRA = "stonecroft"
AGENCIA = "knotwell"

TODO_SIN_ANOTAR: dict[str, Any] = {
    "claim_amount": None,
    "coverage_disputed": None,
    "fraud_suspected": None,
}

VISITANTE = Actor(actor_type=ActorType.INSURED, actor_id=decision.VISITOR_ACTOR_ID)


def _ruta(tenant_id: str, case_id: str) -> str:
    return f"/api/inbox/{tenant_id}/cases/{case_id}/triage-note"


def _vista(tenant_id: str, case_id: str) -> str:
    return f"/api/inbox/{tenant_id}/cases/{case_id}"


async def _token(tenant_id: str, case_id: str, *, hace: timedelta = timedelta()) -> str:
    emitido = await visitor_access.issue_case_link(
        tenant_id=tenant_id,
        case_id=case_id,
        signing_key=CLAVE_DE_ENLACES,
        now=datetime.now(UTC) - hace,
    )
    return emitido.token


@asynccontextmanager
async def _entra_el_visitante(
    app: FastAPI, tenant_id: str, case_id: str
) -> AsyncIterator[httpx2.AsyncClient]:
    """Un cliente que canjeo el enlace de ese caso, como la pantalla del visitante."""
    async with cliente(app) as http:
        canje = await http.post(
            f"/api{enlace.REDEEM_PATH}", json={"token": await _token(tenant_id, case_id)}
        )
        assert canje.status_code == 200, "el control: con el enlace vivo, entra"
        yield http


async def _anota_el_visitante(
    http: httpx2.AsyncClient,
    tenant_id: str,
    case_id: str,
    cuerpo: dict[str, Any],
    *,
    clave: str | None = "visitante-1",
) -> Any:
    cabeceras = {"Idempotency-Key": clave} if clave is not None else {}
    return await http.put(_ruta(tenant_id, case_id), json=cuerpo, headers=cabeceras)


async def _anota_el_personal(
    app: FastAPI, tenant_id: str, case_id: str, cuerpo: dict[str, Any], *, clave: str = "personal-1"
) -> Any:
    async with cliente(app, credencial=credencial_de(tenant_id)) as http:
        return await http.put(
            _ruta(tenant_id, case_id), json=cuerpo, headers={"Idempotency-Key": clave}
        )


async def _ve_el_personal(app: FastAPI, tenant_id: str, case_id: str) -> Any:
    async with cliente(app, credencial=credencial_de(tenant_id)) as http:
        return (await http.get(_vista(tenant_id, case_id))).json()


async def _entradas(tenant_id: str, case_id: str) -> list[CaseChange]:
    return [
        e
        for e in await history.of_case(tenant_id, case_id)
        if e.change_kind is ChangeKind.TRIAGE_NOTED
    ]


async def _nada_escrito(tenant_id: str, case_id: str) -> None:
    assert await triage_notes.read(tenant_id, case_id) is None
    assert not await reglas.evaluations_for(tenant_id, case_id)
    assert not await _entradas(tenant_id, case_id)


async def _sembrar_entradas_del_visitante(tenant_id: str, case_id: str, cuantas: int) -> None:
    for _ in range(cuantas):
        await history.append(
            tenant_id,
            CaseChange(
                change_id=history.new_change_id(),
                case_id=case_id,
                change_kind=ChangeKind.TRIAGE_NOTED,
                field_key="fraud_suspected",
                actor=VISITANTE,
                detail="unset -> true",
                changed_at=AHORA,
            ),
        )


# --- El visitante anota su caso y ve lo que paso --------------------------------------


async def test_el_visitante_anota_su_caso_y_la_lectura_muestra_lo_anotado_y_las_reglas(
    app: FastAPI,
) -> None:
    caso = await nuevo_caso(CON_REGLAS)
    async with _entra_el_visitante(app, CON_REGLAS, caso) as http:
        antes = (await http.get(_vista(CON_REGLAS, caso))).json()
        respuesta = await _anota_el_visitante(
            http,
            CON_REGLAS,
            caso,
            TODO_SIN_ANOTAR | {"claim_amount": 2500, "fraud_suspected": True},
        )
        despues = (await http.get(_vista(CON_REGLAS, caso))).json()

    assert antes["can_annotate_triage"] is True
    assert antes["triage_note"] is None
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["receipt_id"]
    assert cuerpo["rule_category"] == "referral"
    assert set(cuerpo["fired_rules"]) == {"SUN-R-03", "SUN-R-07"}
    # La lectura siguiente: su nota, sus reglas y el mismo estado del caso.
    assert despues["triage_note"] == {
        "claim_amount": 2500,
        "coverage_disputed": None,
        "fraud_suspected": True,
    }
    assert despues["rule_category"] == "referral"
    assert set(despues["fired_rules"]) == {"SUN-R-03", "SUN-R-07"}
    assert despues["can_annotate_triage"] is True
    assert despues["state"] == antes["state"]


async def test_el_visitante_queda_como_visitante_y_el_personal_ve_lo_que_anoto(
    app: FastAPI,
) -> None:
    caso = await nuevo_caso(CON_REGLAS)
    async with _entra_el_visitante(app, CON_REGLAS, caso) as http:
        await _anota_el_visitante(http, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"claim_amount": 2500})

    entradas = await _entradas(CON_REGLAS, caso)
    assert [(e.field_key, e.detail) for e in entradas] == [("claim_amount", "unset -> 2500")]
    assert (entradas[0].actor.actor_type, entradas[0].actor.actor_id) == (
        ActorType.INSURED,
        decision.VISITOR_ACTOR_ID,
    )
    nota = await triage_notes.read(CON_REGLAS, caso)
    assert nota is not None
    assert nota.noted_by == decision.VISITOR_ACTOR_ID
    del_ajustador = await _ve_el_personal(app, CON_REGLAS, caso)
    assert del_ajustador["triage_note"]["claim_amount"] == 2500
    assert "SUN-R-03" in del_ajustador["fired_rules"]


async def test_la_lectura_trae_los_umbrales_del_archivo_de_reglas_cuando_se_puede_anotar(
    app: FastAPI,
) -> None:
    caso = await nuevo_caso(CON_REGLAS)
    esperados = list(reglas.amount_steps(tenant_id=CON_REGLAS))
    assert esperados, "el control: la aseguradora tiene reglas sobre el monto"

    async with _entra_el_visitante(app, CON_REGLAS, caso) as http:
        vista = (await http.get(_vista(CON_REGLAS, caso))).json()

    assert vista["can_annotate_triage"] is True
    assert vista["triage_amount_steps"] == esperados


async def test_el_personal_tambien_recibe_los_umbrales_cuando_puede_anotar(app: FastAPI) -> None:
    caso = await nuevo_caso(CON_REGLAS)

    vista = await _ve_el_personal(app, CON_REGLAS, caso)

    assert vista["can_annotate_triage"] is True
    assert vista["triage_amount_steps"] == list(reglas.amount_steps(tenant_id=CON_REGLAS))


async def test_sin_poder_anotar_no_viajan_los_umbrales(app: FastAPI) -> None:
    """La ayuda es de quien anota: una agencia, que no anota, no la recibe."""
    caso = await nuevo_caso(AGENCIA)
    agente = staff_identity.issue_credential(
        tenant_id=AGENCIA,
        principal_id="priya-raman",
        signing_key=CLAVE_DE_BANDEJA,
        now=datetime.now(UTC),
    )

    async with cliente(app, credencial=agente) as http:
        vista = (await http.get(_vista(AGENCIA, caso))).json()

    assert vista["can_annotate_triage"] is False
    assert vista["triage_amount_steps"] == []


async def test_una_credencial_vieja_en_el_navegador_no_le_quita_al_visitante_la_anotacion(
    app: FastAPI,
) -> None:
    caso = await nuevo_caso(CON_REGLAS)

    async with cliente(app, credencial="una-credencial-que-no-vale") as http:
        await http.post(f"/api{enlace.REDEEM_PATH}", json={"token": await _token(CON_REGLAS, caso)})
        respuesta = await _anota_el_visitante(
            http, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"fraud_suspected": True}
        )

    assert respuesta.status_code == 200, respuesta.text
    entradas = await _entradas(CON_REGLAS, caso)
    assert {e.actor.actor_id for e in entradas} == {decision.VISITOR_ACTOR_ID}


# --- Solo su caso ---------------------------------------------------------------------


async def test_el_enlace_de_un_caso_no_anota_otro_caso(app: FastAPI) -> None:
    suyo = await nuevo_caso(CON_REGLAS)
    ajeno = await nuevo_caso(CON_REGLAS)
    cuerpo = TODO_SIN_ANOTAR | {"fraud_suspected": True}

    async with _entra_el_visitante(app, CON_REGLAS, suyo) as http:
        en_el_suyo = await _anota_el_visitante(http, CON_REGLAS, suyo, cuerpo, clave="a")
        en_el_ajeno = await _anota_el_visitante(http, CON_REGLAS, ajeno, cuerpo, clave="b")
        leyendo_el_ajeno = await http.get(_vista(CON_REGLAS, ajeno))

    assert en_el_suyo.status_code == 200
    assert en_el_ajeno.status_code == 404
    assert leyendo_el_ajeno.status_code == 404
    await _nada_escrito(CON_REGLAS, ajeno)


async def test_el_enlace_de_otra_aseguradora_no_anota_este_caso(app: FastAPI) -> None:
    caso_de_la_otra = await nuevo_caso(OTRA)
    caso = await nuevo_caso(CON_REGLAS)

    async with _entra_el_visitante(app, OTRA, caso_de_la_otra) as http:
        # Con la direccion de la aseguradora del caso, y con la del enlace.
        a_la_ajena = await _anota_el_visitante(
            http, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"fraud_suspected": True}, clave="a"
        )
        con_su_direccion = await _anota_el_visitante(
            http, OTRA, caso, TODO_SIN_ANOTAR | {"fraud_suspected": True}, clave="b"
        )

    assert a_la_ajena.status_code == 404
    assert con_su_direccion.status_code == 404
    await _nada_escrito(CON_REGLAS, caso)


async def test_un_enlace_vencido_no_anota_y_uno_vivo_si(app: FastAPI) -> None:
    caso = await nuevo_caso(CON_REGLAS)
    cuerpo = TODO_SIN_ANOTAR | {"fraud_suspected": True}

    # Una cookie cuyo enlace se emitio hace dos horas: el vencimiento se mira en cada peticion.
    async with cliente(app) as http:
        http.cookies.set(
            enlace.CASE_COOKIE, await _token(CON_REGLAS, caso, hace=timedelta(hours=2)), path="/api"
        )
        vencido = await _anota_el_visitante(http, CON_REGLAS, caso, cuerpo, clave="a")
    await _nada_escrito(CON_REGLAS, caso)
    async with cliente(app) as http:
        http.cookies.set(enlace.CASE_COOKIE, await _token(CON_REGLAS, caso), path="/api")
        vivo = await _anota_el_visitante(http, CON_REGLAS, caso, cuerpo, clave="b")

    assert vencido.status_code == 404
    assert vivo.status_code == 200, vivo.text


async def test_una_cookie_alterada_no_anota(app: FastAPI) -> None:
    caso = await nuevo_caso(CON_REGLAS)
    alterado = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA." + "0" * 64

    async with cliente(app) as http:
        http.cookies.set(enlace.CASE_COOKIE, alterado, path="/api")
        respuesta = await _anota_el_visitante(
            http, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"fraud_suspected": True}
        )

    assert respuesta.status_code == 404
    await _nada_escrito(CON_REGLAS, caso)


async def test_un_rechazo_por_enlace_responde_igual_que_un_caso_que_no_existe(
    app: FastAPI,
) -> None:
    """Una sola via de rechazo: si difirieran, probar enlaces diria cual acerto."""
    suyo = await nuevo_caso(CON_REGLAS)
    ajeno = await nuevo_caso(CON_REGLAS)
    cuerpo = TODO_SIN_ANOTAR | {"fraud_suspected": True}

    async with _entra_el_visitante(app, CON_REGLAS, suyo) as http:
        de_otro = await _anota_el_visitante(http, CON_REGLAS, ajeno, cuerpo, clave="a")
        inexistente = await _anota_el_visitante(
            http, CON_REGLAS, "caso-que-no-existe", cuerpo, clave="b"
        )

    assert de_otro.status_code == inexistente.status_code == 404
    sin_rastro = [
        {k: v for k, v in r.json().items() if k != "trace_id"} for r in (de_otro, inexistente)
    ]
    assert sin_rastro[0] == sin_rastro[1]


# --- Lo que anoto el personal ni se ve ni se pisa -------------------------------------


async def test_la_nota_del_personal_no_se_lee_ni_se_pisa_con_el_enlace(app: FastAPI) -> None:
    caso = await nuevo_caso(CON_REGLAS)
    anotada = await _anota_el_personal(
        app, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"claim_amount": 7318, "fraud_suspected": True}
    )
    assert anotada.status_code == 200, "el control: el personal anota"
    antes = await triage_notes.read(CON_REGLAS, caso)
    entradas = len(await _entradas(CON_REGLAS, caso))

    async with _entra_el_visitante(app, CON_REGLAS, caso) as http:
        vista = await http.get(_vista(CON_REGLAS, caso))
        pisa = await _anota_el_visitante(
            http, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"claim_amount": 10}
        )
        igual = await _anota_el_visitante(
            http,
            CON_REGLAS,
            caso,
            TODO_SIN_ANOTAR | {"claim_amount": 7318, "fraud_suspected": True},
            clave="visitante-2",
        )

    cuerpo = vista.json()
    assert vista.status_code == 200
    assert cuerpo["triage_note"] is None
    assert cuerpo["can_annotate_triage"] is False
    assert cuerpo["triage_amount_steps"] == []
    for rastro in ("7318", "SUN-R-03", "SUN-R-04", "SUN-R-07"):
        assert rastro not in vista.text, f"'{rastro}' aparece en la pantalla del visitante"
    assert pisa.status_code == 409
    assert igual.status_code == 409, "guardar lo mismo no puede decirle que hay una nota igual"
    assert await triage_notes.read(CON_REGLAS, caso) == antes
    assert len(await _entradas(CON_REGLAS, caso)) == entradas


async def test_el_personal_si_pisa_la_nota_del_visitante_y_desde_entonces_no_la_ve(
    app: FastAPI,
) -> None:
    caso = await nuevo_caso(CON_REGLAS)
    async with _entra_el_visitante(app, CON_REGLAS, caso) as http:
        await _anota_el_visitante(http, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"claim_amount": 2500})
        suya = (await http.get(_vista(CON_REGLAS, caso))).json()

        pisada = await _anota_el_personal(
            app, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"claim_amount": 9000}, clave="personal-2"
        )
        despues = (await http.get(_vista(CON_REGLAS, caso))).json()

    assert suya["triage_note"]["claim_amount"] == 2500
    assert pisada.status_code == 200
    assert despues["triage_note"] is None
    assert despues["can_annotate_triage"] is False
    assert "SUN-R-03" not in despues["fired_rules"]


# --- Lo que no cambia nada, no escribe ------------------------------------------------


async def test_guardar_lo_mismo_no_escribe_y_responde_con_la_evaluacion_vigente(
    app: FastAPI,
) -> None:
    caso = await nuevo_caso(CON_REGLAS)
    cuerpo = TODO_SIN_ANOTAR | {"claim_amount": 2500, "fraud_suspected": True}

    async with _entra_el_visitante(app, CON_REGLAS, caso) as http:
        primera = await _anota_el_visitante(http, CON_REGLAS, caso, cuerpo, clave="a")
        evaluaciones = await reglas.evaluations_for(CON_REGLAS, caso)
        entradas = len(await _entradas(CON_REGLAS, caso))
        avisos = len(await events.since(CON_REGLAS, 0))

        otra = await _anota_el_visitante(http, CON_REGLAS, caso, cuerpo, clave="b")

    assert primera.status_code == otra.status_code == 200
    assert otra.json()["receipt_id"] is None
    assert otra.json()["rule_category"] == primera.json()["rule_category"]
    assert otra.json()["fired_rules"] == primera.json()["fired_rules"]
    assert await reglas.evaluations_for(CON_REGLAS, caso) == evaluaciones
    assert len(await _entradas(CON_REGLAS, caso)) == entradas
    assert len(await events.since(CON_REGLAS, 0)) == avisos


async def test_guardar_vacio_un_caso_sin_nada_anotado_responde_sin_evaluacion_ni_recibo(
    app: FastAPI,
) -> None:
    caso = await nuevo_caso(CON_REGLAS)

    async with _entra_el_visitante(app, CON_REGLAS, caso) as http:
        respuesta = await _anota_el_visitante(http, CON_REGLAS, caso, TODO_SIN_ANOTAR)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {"receipt_id": None, "rule_category": None, "fired_rules": []}
    await _nada_escrito(CON_REGLAS, caso)


async def test_la_misma_clave_devuelve_la_primera_y_una_reciclada_es_un_conflicto(
    app: FastAPI,
) -> None:
    caso = await nuevo_caso(CON_REGLAS)
    cuerpo = TODO_SIN_ANOTAR | {"claim_amount": 2500}

    async with _entra_el_visitante(app, CON_REGLAS, caso) as http:
        primera = await _anota_el_visitante(http, CON_REGLAS, caso, cuerpo, clave="la-misma")
        segunda = await _anota_el_visitante(http, CON_REGLAS, caso, cuerpo, clave="la-misma")
        reciclada = await _anota_el_visitante(
            http, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"claim_amount": 9}, clave="la-misma"
        )
        sin_clave = await _anota_el_visitante(http, CON_REGLAS, caso, cuerpo, clave=None)

    assert segunda.json() == primera.json()
    assert reciclada.status_code == 409
    assert sin_clave.status_code == 422
    assert len(await reglas.evaluations_for(CON_REGLAS, caso)) == 1
    nota = await triage_notes.read(CON_REGLAS, caso)
    assert nota is not None
    assert nota.values.claim_amount == 2500


# --- El techo -------------------------------------------------------------------------


async def test_con_el_tope_alcanzado_la_lectura_deja_de_ofrecer_y_la_ruta_rechaza(
    app: FastAPI,
) -> None:
    caso = await nuevo_caso(CON_REGLAS)
    await _sembrar_entradas_del_visitante(CON_REGLAS, caso, annotation.VISITOR_ANNOTATION_LIMIT - 1)

    async with _entra_el_visitante(app, CON_REGLAS, caso) as http:
        antes = (await http.get(_vista(CON_REGLAS, caso))).json()
        cabe = await _anota_el_visitante(
            http, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"fraud_suspected": True}, clave="a"
        )
        despues = (await http.get(_vista(CON_REGLAS, caso))).json()
        no_cabe = await _anota_el_visitante(
            http, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"fraud_suspected": False}, clave="b"
        )
        igual = await _anota_el_visitante(
            http, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"fraud_suspected": True}, clave="c"
        )

    assert antes["can_annotate_triage"] is True
    assert cabe.status_code == 200, "el control: una entrada menos que el tope, todavia cabe"
    assert despues["can_annotate_triage"] is False
    assert despues["triage_amount_steps"] == []
    # Lo que ya anoto lo sigue leyendo, aunque ya no pueda cambiarlo.
    assert despues["triage_note"] == {
        "claim_amount": None,
        "coverage_disputed": None,
        "fraud_suspected": True,
    }
    assert no_cabe.status_code == 409
    assert igual.status_code == 200, "guardar lo que ya estaba no es un cambio"
    nota = await triage_notes.read(CON_REGLAS, caso)
    assert nota is not None
    assert nota.values.fraud_suspected is True


async def test_el_tope_del_visitante_no_alcanza_al_personal(app: FastAPI) -> None:
    caso = await nuevo_caso(CON_REGLAS)
    await _sembrar_entradas_del_visitante(CON_REGLAS, caso, annotation.VISITOR_ANNOTATION_LIMIT)

    vista = await _ve_el_personal(app, CON_REGLAS, caso)
    anotada = await _anota_el_personal(app, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"claim_amount": 5})

    assert vista["can_annotate_triage"] is True
    assert anotada.status_code == 200


# --- El estado del caso ---------------------------------------------------------------


@pytest.mark.parametrize(
    "estado",
    [CaseState.OPEN, CaseState.CAPTURING, CaseState.VERIFYING, CaseState.DECIDING],
)
async def test_un_caso_que_la_agente_aun_lleva_ni_se_ofrece_ni_se_anota_con_el_enlace(
    app: FastAPI, estado: CaseState
) -> None:
    caso = await nuevo_caso(CON_REGLAS, estado=estado)

    async with _entra_el_visitante(app, CON_REGLAS, caso) as http:
        vista = (await http.get(_vista(CON_REGLAS, caso))).json()
        respuesta = await _anota_el_visitante(
            http, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"fraud_suspected": True}
        )

    assert vista["can_annotate_triage"] is False
    assert vista["triage_amount_steps"] == []
    assert respuesta.status_code == 409
    await _nada_escrito(CON_REGLAS, caso)


@pytest.mark.parametrize("estado", [CaseState.DERIVED, CaseState.AWAITING_INSURED])
async def test_un_caso_con_un_ajustador_o_esperando_al_asegurado_se_anota_con_el_enlace(
    app: FastAPI, estado: CaseState
) -> None:
    caso = await nuevo_caso(CON_REGLAS, estado=estado)

    async with _entra_el_visitante(app, CON_REGLAS, caso) as http:
        vista = (await http.get(_vista(CON_REGLAS, caso))).json()
        respuesta = await _anota_el_visitante(
            http, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"fraud_suspected": True}
        )

    assert vista["can_annotate_triage"] is True
    assert respuesta.status_code == 200, respuesta.text


async def test_un_caso_cerrado_ni_se_ofrece_ni_se_anota_con_el_enlace(app: FastAPI) -> None:
    cerrado = await cerrado_por_las_reglas(CON_REGLAS)

    async with _entra_el_visitante(app, CON_REGLAS, cerrado) as http:
        vista = (await http.get(_vista(CON_REGLAS, cerrado))).json()
        respuesta = await _anota_el_visitante(
            http, CON_REGLAS, cerrado, TODO_SIN_ANOTAR | {"fraud_suspected": True}
        )

    assert vista["can_annotate_triage"] is False
    assert respuesta.status_code == 409
    assert await triage_notes.read(CON_REGLAS, cerrado) is None


# --- La pagina publica de ejemplos no cambia ------------------------------------------


async def test_el_caso_de_ejemplo_no_ofrece_anotar_ni_muestra_lo_que_el_visitante_anoto(
    app: FastAPI,
) -> None:
    """Los casos de ejemplo se leen sin credencial: nada de la anotacion llega ahi."""
    caso = await nuevo_caso(CON_REGLAS)
    async with _entra_el_visitante(app, CON_REGLAS, caso) as http:
        anotada = await _anota_el_visitante(
            http,
            CON_REGLAS,
            caso,
            TODO_SIN_ANOTAR | {"claim_amount": 7318, "fraud_suspected": True},
        )
        suya = (await http.get(_vista(CON_REGLAS, caso))).json()
    assert anotada.status_code == 200, "el control: ese mismo caso, con el enlace, si se anota"
    assert suya["triage_note"]["claim_amount"] == 7318

    async with cliente(app) as publico:
        ejemplo = await publico.get(f"/api/examples/{CON_REGLAS}/cases/{caso}")

    assert ejemplo.status_code == 200, ejemplo.text
    cuerpo = ejemplo.json()
    assert cuerpo["triage_note"] is None
    assert cuerpo["can_annotate_triage"] is False
    assert cuerpo["triage_amount_steps"] == []
    assert "SUN-R-03" not in cuerpo["fired_rules"]
    assert "SUN-R-07" not in cuerpo["fired_rules"]
    assert "7318" not in ejemplo.text


# --- Lo que decidir ya hacia sigue igual ----------------------------------------------


async def test_el_visitante_anota_y_despues_decide_y_el_caso_cerrado_ya_no_se_anota(
    app: FastAPI,
) -> None:
    """El recorrido entero de la pantalla: anotar para ver las reglas y despues decidir."""
    caso = await nuevo_caso(CON_REGLAS)

    async def reanudar(case_id: str, resolucion: object, tenant_id: str) -> None:
        del case_id, resolucion, tenant_id

    decision.install_resume_handler(reanudar)
    try:
        async with _entra_el_visitante(app, CON_REGLAS, caso) as http:
            anotada = await _anota_el_visitante(
                http, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"fraud_suspected": True}, clave="a"
            )
            decidida = await http.post(
                f"/api/inbox/{CON_REGLAS}/cases/{caso}/decision",
                json={"decision": "approve", "comment": "Lo apruebo yo mismo."},
                headers={"Idempotency-Key": "decide-1"},
            )
            tarde = await _anota_el_visitante(
                http, CON_REGLAS, caso, TODO_SIN_ANOTAR | {"fraud_suspected": False}, clave="b"
            )
            vista = (await http.get(_vista(CON_REGLAS, caso))).json()
    finally:
        decision.reset_resume_handler()

    assert anotada.status_code == 200
    assert decidida.status_code == 202, decidida.text
    assert tarde.status_code == 409
    assert vista["can_annotate_triage"] is False
    assert vista["triage_note"]["fraud_suspected"] is True
