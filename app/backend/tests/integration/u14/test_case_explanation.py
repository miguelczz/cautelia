"""Lo que la vista de caso manda resuelto para que la pantalla no vuelva a decidir.

Cuatro cosas, y las cuatro son reglas de esta unidad escritas **una sola vez**: las
acciones que ofrece el caso (BR4.5, BR4.3, BR4.4), si se puede corregir un campo
(BR3.4), la explicacion de sus cinco preguntas (BR2.4, BR5.5) y quien emitio cada
clausula citada (BR2.6).

**Por que van por el cable y no se deducen en la pantalla.** Una interfaz que
preguntara "es una agencia?" o "esta cerrado?" escribiria esas reglas por segunda vez,
en otro lenguaje, y el dia que una cambie la otra seguiria diciendo lo de antes. Estas
pruebas son las que sostienen que la respuesta las trae.

Por HTTP y no por la funcion, como el resto de la unidad: lo que se ofrece es una ruta.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI

from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record.models import CaseState, Channel, Speaker
from untangle.case_record.transcript import TurnDraft
from untangle.compliance.redaction.api import redact
from untangle.inbox import decision
from untangle.policy_rag.citations.models import CitationCheck, CoverageAnswer, CoverageOutcome
from untangle.policy_rag.citations.repository import save_answer_with_checks
from untangle.policy_rag.corpus.models import Clause, FormKind, PolicyForm
from untangle.policy_rag.corpus.repository import upsert_reference_data
from untangle.tenancy import api as tenancy
from untangle.tenancy.models import TenantKind

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


@pytest.fixture(autouse=True)
def reanudacion(app: FastAPI) -> Any:
    """Un doble de la reanudacion del grafo: sin el, decidir falla en alto.

    Depende de `app` a proposito, igual que en `test_decision.py`: la raiz de
    composicion enchufa el puerto real al construir la aplicacion, y el doble tiene que
    quedar **despues**. Lo que estas pruebas miden es lo que la vista manda resuelto,
    no la reanudacion, que tiene sus propias pruebas.
    """
    del app

    async def reanudar(case_id: str, resolucion: object, tenant_id: str) -> None:
        del case_id, resolucion, tenant_id

    decision.install_resume_handler(reanudar)
    yield
    decision.reset_resume_handler()


@pytest.fixture
def emisora() -> str:
    """Una aseguradora que emite: aprueba y rechaza."""
    return next(
        t.tenant_id
        for t in sorted(tenancy.loaded().available, key=lambda c: c.tenant_id)
        if t.kind is TenantKind.CARRIER
    )


@pytest.fixture
def agencia() -> str:
    """Una agencia: marca como enviado y no decide."""
    return next(
        t.tenant_id
        for t in sorted(tenancy.loaded().available, key=lambda c: c.tenant_id)
        if t.kind is TenantKind.AGENCY
    )


async def _ver(app: FastAPI, tenant_id: str, case_id: str) -> dict[str, Any]:
    async with cliente(app, credencial=credencial_de(tenant_id)) as http:
        respuesta = await http.get(f"/api/inbox/{tenant_id}/cases/{case_id}")
    assert respuesta.status_code == 200, respuesta.text
    cuerpo: dict[str, Any] = respuesta.json()
    return cuerpo


async def _decidir(app: FastAPI, tenant_id: str, case_id: str, accion: str) -> Any:
    async with cliente(app, credencial=credencial_de(tenant_id)) as http:
        return await http.post(
            f"/api/inbox/{tenant_id}/cases/{case_id}/decision",
            json={"decision": accion, "comment": "Cubierto."},
            headers={"Idempotency-Key": f"k-{uuid.uuid4().hex[:8]}"},
        )


# --- Las acciones que ofrece el caso (BR4.5, BR4.3, BR4.4) --------------------


async def test_una_emisora_ofrece_aprobar_y_rechazar(app: FastAPI, emisora: str) -> None:
    caso = await nuevo_caso(emisora)

    vista = await _ver(app, emisora, caso)

    assert sorted(vista["available_actions"]) == ["approve", "reject"]


async def test_una_agencia_ofrece_solo_marcar_como_enviado(app: FastAPI, agencia: str) -> None:
    """La otra mitad: sin ella, una lista vacia pasaria la prueba de arriba."""
    caso = await nuevo_caso(agencia)

    vista = await _ver(app, agencia, caso)

    assert vista["available_actions"] == ["mark_sent"]


async def test_un_caso_que_espera_al_asegurado_no_ofrece_ninguna(
    app: FastAPI, emisora: str
) -> None:
    """Y la pantalla dira por que, con el estado que viene al lado (BR4.3)."""
    caso = await nuevo_caso(emisora, estado=CaseState.AWAITING_INSURED)

    vista = await _ver(app, emisora, caso)

    assert vista["available_actions"] == []
    assert vista["state"] == "awaiting_insured"


async def test_un_caso_decidido_deja_de_ofrecer_acciones(app: FastAPI, emisora: str) -> None:
    """BR4.4 visto desde la pantalla: la segunda persona no ve el boton.

    Lo que de verdad impide la segunda decision es la ruta, y eso lo prueba
    `test_decision.py`. Esto es lo que evita dibujar un boton que va a ser rechazado.
    """
    caso = await nuevo_caso(emisora)
    respuesta = await _decidir(app, emisora, caso, "approve")
    assert respuesta.status_code == 202, respuesta.text

    vista = await _ver(app, emisora, caso)

    assert vista["available_actions"] == []
    assert vista["resolution"] == "approved"


@pytest.mark.parametrize("estado", [CaseState.VERIFYING, CaseState.DECIDING])
async def test_un_caso_que_la_agente_aun_evalua_se_ofrece_al_personal_y_no_al_visitante(
    app: FastAPI, emisora: str, estado: CaseState
) -> None:
    """El personal puede tomarlo (aprobar o rechazar) y el visitante ve que sigue en revision.

    Las dos mitades juntas, con la misma ruta: un `[]` fijo pasaria la del visitante y
    una lista fija pasaria la del personal. El visitante abre **su** caso con la cookie
    del enlace, que es la misma puerta por la que decide.
    """
    from untangle.inbox import visitor
    from untangle.tenancy import visitor_access

    caso = await nuevo_caso(emisora, estado=estado)
    token = (
        await visitor_access.issue_case_link(
            tenant_id=emisora,
            case_id=caso,
            signing_key=CLAVE_DE_ENLACES,
            now=datetime.now(UTC),
        )
    ).token

    personal = await _ver(app, emisora, caso)
    async with cliente(app) as http:
        await http.post(f"/api{visitor.REDEEM_PATH}", json={"token": token})
        respuesta = await http.get(f"/api/inbox/{emisora}/cases/{caso}")
    assert respuesta.status_code == 200, respuesta.text
    del_visitante = respuesta.json()

    assert sorted(personal["available_actions"]) == ["approve", "reject"]
    assert del_visitante["available_actions"] == []
    assert del_visitante["state"] == estado.value


# --- El cierre directo: lo cierran las reglas y nadie decide (US1.17) ---------


async def test_un_cierre_directo_no_nombra_a_nadie_y_no_ofrece_nada(
    app: FastAPI, emisora: str
) -> None:
    """La vista distingue al sistema de una persona y de un visitante.

    `decided_by_kind` viaja como `system` y sin identificador: la pantalla decide con
    eso decir "sin ajustador" en vez de nombrar un actor. Sin acciones ni correcciones,
    y con la categoria `direct_close` y la regla que lo permitio.
    """
    caso = await cerrado_por_las_reglas(emisora)

    vista = await _ver(app, emisora, caso)

    explicacion = vista["explanation"]
    assert vista["state"] == "closed"
    assert vista["resolution"] == "registered"
    assert explicacion["decided_by"] == "present"
    assert explicacion["decided_by_kind"] == "system"
    assert explicacion["decided_by_id"] is None
    assert explicacion["decided_at_iso"]
    assert vista["rule_category"] == "direct_close"
    assert vista["fired_rules"] == ["R-CIERRE-DIRECTO"]
    assert vista["available_actions"] == []
    assert vista["can_correct_fields"] is False


# --- Si se puede corregir (BR3.4) --------------------------------------------


async def test_un_caso_abierto_ofrece_corregir_y_uno_cerrado_no(app: FastAPI, emisora: str) -> None:
    """Las dos mitades juntas: con una sola, un `False` fijo pasaria la suya."""
    abierto = await nuevo_caso(emisora)
    cerrado = await nuevo_caso(emisora)
    assert (await _decidir(app, emisora, cerrado, "approve")).status_code == 202

    assert (await _ver(app, emisora, abierto))["can_correct_fields"] is True
    assert (await _ver(app, emisora, cerrado))["can_correct_fields"] is False


# --- La explicacion y sus cinco preguntas (BR2.4, BR5.5) ---------------------


async def test_un_caso_sin_decidir_esta_pendiente_y_no_en_blanco(
    app: FastAPI, emisora: str
) -> None:
    """`pending` y no `none`: un hueco se lee como un dato que se perdio."""
    caso = await nuevo_caso(emisora)

    explicacion = (await _ver(app, emisora, caso))["explanation"]

    assert explicacion["decided_by"] == "pending"
    assert explicacion["decided_at"] == "pending"
    assert explicacion["decided_by_kind"] is None
    assert explicacion["decided_at_iso"] is None


async def test_un_caso_que_espera_al_asegurado_tambien_esta_pendiente(
    app: FastAPI, emisora: str
) -> None:
    """Su decision llegara cuando el asegurado vuelva, asi que no es `none`.

    Es la fila que distingue "todavia no se ha decidido" de "se miro y no habia", y la
    que se cae si alguien ata el pendiente a "se puede decidir ahora".
    """
    caso = await nuevo_caso(emisora, estado=CaseState.AWAITING_INSURED)

    explicacion = (await _ver(app, emisora, caso))["explanation"]

    assert explicacion["decided_by"] == "pending"


async def test_una_decision_con_credencial_nombra_a_quien_la_firmo(
    app: FastAPI, emisora: str
) -> None:
    caso = await nuevo_caso(emisora)
    assert (await _decidir(app, emisora, caso, "approve")).status_code == 202

    explicacion = (await _ver(app, emisora, caso))["explanation"]

    assert explicacion["decided_by"] == "present"
    assert explicacion["decided_at"] == "present"
    assert explicacion["decided_by_kind"] == "staff"
    # El identificador de la tabla versionada, no el nombre de nadie real: es lo que
    # responde "quien decidio" y lo que BR5.5 prohibe poner cuando fue un visitante.
    assert explicacion["decided_by_id"]
    assert explicacion["decided_at_iso"]


async def test_las_tres_primeras_preguntas_distinguen_haber_y_no_haber(
    app: FastAPI, emisora: str
) -> None:
    """Un caso sin preguntas de cobertura responde `none`, que es una respuesta.

    Sin esta prueba, una explicacion que dijera `present` a todo pasaria la de arriba:
    lo que se mide es que sepa decir las dos cosas.
    """
    vacio = await nuevo_caso(emisora)
    con_pregunta = await nuevo_caso(emisora)
    await _sembrar_respuesta(emisora, con_pregunta, clause_id="CL-SIN-CORPUS")

    sin = (await _ver(app, emisora, vacio))["explanation"]
    con = (await _ver(app, emisora, con_pregunta))["explanation"]

    assert sin["asked"] == "none"
    assert con["asked"] == "present"


# --- Las etiquetas y el emisor (BR2.1, BR2.6) --------------------------------


async def test_cada_campo_viaja_con_la_clave_de_su_etiqueta(app: FastAPI, emisora: str) -> None:
    """La pantalla no imprime `vehicle_and_driver`: eso es el valor interno del campo."""
    caso = await nuevo_caso(emisora)

    campos = (await _ver(app, emisora, caso))["fields"]

    assert campos
    for campo in campos:
        assert campo["label_key"].startswith("case.field."), campo
        assert campo["label_key"] != campo["field_key"]


async def test_una_clausula_citada_dice_quien_la_emitio(app: FastAPI, emisora: str) -> None:
    """BR2.6: sin este dato al lado, las clausulas de una agencia parecen suyas.

    Hace falta sembrar el corpus: una cita cuya clausula no esta en el corpus **se cae
    con su evento** --es la regla de U13 y esta unidad reusa su pieza--, asi que sin
    esto la lista de citas llegaria vacia y la prueba pasaria sin comprobar nada.
    """
    caso = await nuevo_caso(emisora)
    await _sembrar_clausula(emisora, clause_id="FORM-A11Y-4.1", emisor="Quien Emitio S.A.")
    await _sembrar_respuesta(emisora, caso, clause_id="FORM-A11Y-4.1")

    respuestas = (await _ver(app, emisora, caso))["coverage_answers"]

    citas = [cita for respuesta in respuestas for cita in respuesta["citations"]]
    assert citas, "la cita no llego al cable"
    for cita in citas:
        assert cita["issuer_label"] == "Quien Emitio S.A."


@pytest.mark.parametrize(
    ("idioma", "parte", "en_el_otro"),
    [
        ("en", "Part D — Coverage for Damage to Your Auto", "Parte D — Daños a su vehículo"),
        ("es", "Parte D — Daños a su vehículo", "Part D — Coverage for Damage to Your Auto"),
        # Una parte que el corpus no traduce no inventa nada: la pantalla usa la original.
        ("es", "Una parte sin traduccion", None),
    ],
    ids=["poliza-en-ingles", "poliza-en-espanol", "parte-sin-traduccion"],
)
async def test_una_clausula_trae_el_nombre_de_su_parte_en_el_otro_idioma(
    app: FastAPI, emisora: str, idioma: Locale, parte: str, en_el_otro: str | None
) -> None:
    """C17: la bandeja, «Ver mi caso» y «Casos» no conversan, asi que no hay un «idioma pedido»
    como en el chat; la tarjeta lleva el nombre en el otro idioma y la pantalla lo usa cuando su
    idioma no es el de la poliza. El texto de la clausula y su nombre original no cambian."""
    caso = await nuevo_caso(emisora)
    await _sembrar_clausula(
        emisora, clause_id="FORM-A11Y-4.1", emisor="Quien Emitio S.A.", language=idioma, part=parte
    )
    await _sembrar_respuesta(emisora, caso, clause_id="FORM-A11Y-4.1")

    respuestas = (await _ver(app, emisora, caso))["coverage_answers"]

    [cita] = [cita for respuesta in respuestas for cita in respuesta["citations"]]
    assert cita["part"] == parte
    assert cita["clause_language"] == idioma
    assert cita["part_in_other_language"] == en_el_otro


# --- Sembrado -----------------------------------------------------------------


async def _sembrar_respuesta(tenant_id: str, case_id: str, *, clause_id: str) -> None:
    """Una respuesta de cobertura verificada, con su turno y su comprobacion de cita."""
    sufijo = uuid.uuid4().hex[:8]
    turno = await casos.append_turn(
        tenant_id,
        TurnDraft(
            turn_id=f"turn-{sufijo}",
            case_id=case_id,
            speaker=Speaker.INSURED,
            channel=Channel.CHAT,
            language="es",
            started_at=AHORA,
        ),
        redact("Cubre el vidrio?", language="es"),
    )
    comprobacion = CitationCheck(
        check_id=f"chk-{sufijo}",
        tenant_id=tenant_id,
        case_id=case_id,
        clause_id=clause_id,
        clause_version="v1",
        claim_redacted="lo que se afirmo",
        outcome=CoverageOutcome.VERIFIED,
        reasons=(),
        checked_at=AHORA,
    )
    await save_answer_with_checks(
        CoverageAnswer(
            answer_id=f"ans-{sufijo}",
            tenant_id=tenant_id,
            case_id=case_id,
            turn_id=turno,
            idempotency_key=f"idem-{sufijo}",
            question_redacted="¿Cubre el vidrio?",
            outcome=CoverageOutcome.VERIFIED,
            citation_check_ids=(comprobacion.check_id,),
            answer_language="es",
            clause_language="es",
            created_at=AHORA,
        ),
        checks=(comprobacion,),
    )


async def _sembrar_clausula(
    tenant_id: str,
    *,
    clause_id: str,
    emisor: str,
    language: Locale = "es",
    part: str = "Part D",
) -> None:
    """Un formulario con una clausula en el corpus de esa aseguradora."""
    await upsert_reference_data(
        tenant_id,
        forms=(
            PolicyForm(
                tenant_id=tenant_id,
                form_id="FORM-A11Y",
                form_version="v1",
                form_kind=FormKind.BASE,
                language=language,
                issuer_label=emisor,
                issuer_tenant=tenant_id,
                jurisdiction_ref=None,
                clause_ids=(clause_id,),
            ),
        ),
        clauses=(
            Clause(
                tenant_id=tenant_id,
                clause_id=clause_id,
                clause_key="4.1",
                form_id="FORM-A11Y",
                form_version="v1",
                part=part,
                language=language,
                text="La compania responde por los danos al vehiculo asegurado.",
                is_distractor=False,
                issuer_label=emisor,
            ),
        ),
        relations=(),
        policies=(),
    )


# --- Sin clave enchufada: el mismo rechazo, nunca un 500 ----------------------


async def test_sin_clave_de_personal_la_cola_responde_como_a_una_credencial_ilegible(
    app: FastAPI, emisora: str
) -> None:
    """Un despliegue sin clave es un despliegue **sin bandeja** (BR1.4).

    Con el control positivo delante: con la clave enchufada la cola responde, asi que
    el rechazo no se debe a que la ruta no funcione. Un `500` aqui distinguiria "no
    configurado" de "no valido", y eso le dice a quien prueba credenciales que ahi hay
    una bandeja. Lo encontro el arnes de accesibilidad, que corre el proceso real sin
    claves.
    """
    from untangle.inbox import api as bandeja

    credencial = credencial_de(emisora)
    async with cliente(app, credencial=credencial) as http:
        con_clave = await http.get(f"/api/inbox/{emisora}/cases")
    assert con_clave.status_code == 200, con_clave.text

    ilegible = await _cola_con(app, emisora, credencial="no-es-una-credencial")

    bandeja.install_keys(staff_credential=None, case_link=None)
    try:
        sin_clave = await _cola_con(app, emisora, credencial=credencial)
    finally:
        bandeja.install_keys(staff_credential=CLAVE_DE_BANDEJA, case_link=CLAVE_DE_ENLACES)

    assert sin_clave.status_code == 404
    assert _sin_rastro(sin_clave) == _sin_rastro(ilegible)


async def test_sin_clave_de_enlace_el_canje_responde_como_un_enlace_que_no_vale(
    app: FastAPI,
) -> None:
    """La misma decision y la misma razon, del otro lado (BR5.2 `[bloquea]`)."""
    from untangle.inbox import api as bandeja

    async with cliente(app) as http:
        con_clave = await http.post("/api/case-links/redeem", json={"token": "no-vale"})
    assert con_clave.status_code == 404

    bandeja.install_keys(staff_credential=None, case_link=None)
    try:
        async with cliente(app) as http:
            sin_clave = await http.post("/api/case-links/redeem", json={"token": "no-vale"})
    finally:
        bandeja.install_keys(staff_credential=CLAVE_DE_BANDEJA, case_link=CLAVE_DE_ENLACES)

    assert sin_clave.status_code == 404
    assert _sin_rastro(sin_clave) == _sin_rastro(con_clave)


async def _cola_con(app: FastAPI, tenant_id: str, *, credencial: str) -> Any:
    async with cliente(app, credencial=credencial) as http:
        return await http.get(f"/api/inbox/{tenant_id}/cases")


def _sin_rastro(respuesta: Any) -> dict[str, object]:
    """El cuerpo del error sin su rastro, que es distinto en cada peticion a proposito.

    Se comprueba que **este**: comparar las respuestas quitando un campo que a lo mejor
    no existe seria comparar dos cuerpos incompletos y darlos por iguales.
    """
    cuerpo = dict(respuesta.json())
    assert cuerpo.pop("trace_id", None), "la respuesta de error no trae rastro (C-01)"
    return cuerpo
