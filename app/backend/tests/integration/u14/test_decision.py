"""La decision: su comentario, su orden, quien la firma y quien puede (BR4.1 a BR4.6).

El orden es lo que mas cuidado pide aqui: **primero se registra y despues se
reanuda**. Al reves, una caida en medio deja el grafo contando al asegurado una
decision que el caso no tiene. Se comprueba con un doble que anota cuando lo
llamaron y en que estado estaba el caso en ese momento: sin eso, las dos versiones
se ven iguales desde fuera.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI

from untangle.case_record import api as casos
from untangle.case_record.models import CaseState
from untangle.inbox import decision
from untangle.tenancy import api as tenancy
from untangle.tenancy.models import TenantKind

from .conftest import (
    CLAVE_DE_ENLACES,
    cerrado_por_las_reglas,
    cliente,
    credencial_de,
    nuevo_caso,
)

pytestmark = pytest.mark.usefixtures("base_de_u14")


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


@pytest.fixture(autouse=True)
def reanudaciones(app: FastAPI) -> Any:
    """Un doble de la reanudacion que anota **cuando** lo llamaron.

    Anota el estado del caso en el momento de la llamada, no solo que la hubo: es
    lo unico que distingue "se registro y despues se reanudo" de lo contrario.
    """
    # Depende de `app` a proposito: la raiz de composicion enchufa el puerto real
    # --el de U12, que necesita el grafo levantado-- al construir la aplicacion, y
    # el doble tiene que quedar **despues**. Al reves, la raiz lo pisaria.
    del app
    llamadas: list[dict[str, Any]] = []

    async def reanudar(case_id: str, resolucion: object, tenant_id: str) -> None:
        vista = await casos.get_case(tenant_id, case_id)
        llamadas.append(
            {
                "case_id": case_id,
                "resolucion": resolucion,
                "estado_al_reanudar": vista.state if vista is not None else None,
            }
        )

    decision.install_resume_handler(reanudar)
    yield llamadas
    decision.reset_resume_handler()


async def _decidir(  # noqa: PLR0913 -- la ruta, la accion, el comentario y la clave
    app: FastAPI,
    tenant_id: str,
    case_id: str,
    *,
    accion: str = "approve",
    comentario: str = "Cubierto, la placa coincide.",
    clave: str | None = "dec-1",
) -> Any:
    cabeceras = {"Idempotency-Key": clave} if clave is not None else {}
    async with cliente(app, credencial=credencial_de(tenant_id)) as http:
        return await http.post(
            f"/api/inbox/{tenant_id}/cases/{case_id}/decision",
            json={"decision": accion, "comment": comentario},
            headers=cabeceras,
        )


# --- BR4.2: primero se registra, despues se reanuda ---------------------------


async def test_se_registra_antes_de_reanudar(
    app: FastAPI, emisora: str, reanudaciones: list[dict[str, Any]]
) -> None:
    """Cuando el grafo se entera, el caso ya esta cerrado.

    Si fuera al reves, el estado anotado por el doble seria `derived`, y esta
    prueba es la unica forma de verlo desde fuera.
    """
    caso = await nuevo_caso(emisora)

    respuesta = await _decidir(app, emisora, caso)

    assert respuesta.status_code == 202, respuesta.text
    assert len(reanudaciones) == 1
    assert reanudaciones[0]["estado_al_reanudar"] is CaseState.CLOSED


async def test_la_decision_no_espera_al_grafo(app: FastAPI, emisora: str) -> None:
    """`202` y no `200`: el trabajo sigue de fondo.

    Esperar la reanudacion colgaria la pantalla de quien decidio por lo que tarde
    una conversacion en continuar.
    """
    caso = await nuevo_caso(emisora)

    respuesta = await _decidir(app, emisora, caso)

    assert respuesta.status_code == 202
    assert respuesta.json()["case_state"] == "closed"


# --- BR4.1: el comentario es obligatorio --------------------------------------


@pytest.mark.parametrize("comentario", ["", "   ", "\n"])
async def test_sin_comentario_la_decision_se_rechaza(
    app: FastAPI, emisora: str, comentario: str
) -> None:
    """Y el caso no se toca: un comentario vacio no deja un caso medio cerrado."""
    caso = await nuevo_caso(emisora)

    respuesta = await _decidir(app, emisora, caso, comentario=comentario)

    assert respuesta.status_code in (400, 422)
    vista = await casos.get_case(emisora, caso)
    assert vista is not None
    assert vista.state is CaseState.DERIVED, "el caso se movio sin comentario"


async def test_el_comentario_queda_en_el_historial_como_se_escribio(
    app: FastAPI, emisora: str
) -> None:
    """Auditable, y tal como se escribio: desde el 2026-10-30 no se redacta al guardarse
    (decision de Miguel), porque lo lee el asegurado en su caso."""
    from untangle.case_record import history as historial

    caso = await nuevo_caso(emisora)

    await _decidir(app, emisora, caso, comentario="Aprobado, el telefono 300 123 4567 coincide.")

    entradas = await historial.of_case(emisora, caso)
    detalles = " ".join(e.detail or "" for e in entradas)
    assert "Aprobado, el telefono 300 123 4567 coincide." in detalles


# --- BR4.5: las acciones las decide la configuracion --------------------------


async def test_una_agencia_no_aprueba_ni_por_la_api(app: FastAPI, agencia: str) -> None:
    """La pantalla no ofrece la accion; esto es lo que de verdad la impide.

    Con el control positivo delante: su propia accion si se aplica, asi que el
    rechazo no se debe a que la agencia no pueda decidir nada.

    Responde `404` y no `409` porque quien la rechaza es la tabla de permisos, y
    todas sus causas comparten respuesta: una distinta por causa convertiria el
    rechazo en un oraculo sobre que roles existen.
    """
    suyo = await nuevo_caso(agencia)
    ajeno = await nuevo_caso(agencia)

    marca = await _decidir(app, agencia, suyo, accion="mark_sent", clave="a")
    aprueba = await _decidir(app, agencia, ajeno, accion="approve", clave="b")

    assert marca.status_code == 202, marca.text
    assert aprueba.status_code == 404
    vista = await casos.get_case(agencia, ajeno)
    assert vista is not None
    assert vista.state is CaseState.DERIVED, "el rechazo cambio el caso"


async def test_una_emisora_no_marca_como_enviado(app: FastAPI, emisora: str) -> None:
    """La otra mitad: sin ella, una lista de acciones vacia pasaria la de arriba."""
    caso = await nuevo_caso(emisora)

    respuesta = await _decidir(app, emisora, caso, accion="mark_sent")

    assert respuesta.status_code == 404


def test_la_configuracion_de_la_aseguradora_decide_sus_acciones(emisora: str, agencia: str) -> None:
    """La segunda capa, comprobada donde si se alcanza.

    Por la puerta manda la tabla de permisos, que hoy dice lo mismo y responde
    antes. Esta capa existe porque las dos preguntas son distintas --que puede
    **este rol** y que ofrece **esta aseguradora**-- y el dia que una aseguradora
    nueva no coincida con su rol, es la que lo dice. Comprobarla solo por la ruta
    seria comprobar la otra.
    """
    from untangle.inbox import actions

    ofrece_emisora = actions.allowed_for(tenancy.require(emisora))
    ofrece_agencia = actions.allowed_for(tenancy.require(agencia))

    assert ofrece_emisora == {actions.InboxAction.APPROVE, actions.InboxAction.REJECT}
    assert ofrece_agencia == {actions.InboxAction.MARK_SENT}


def test_ningun_identificador_de_aseguradora_vive_en_el_codigo_de_decision() -> None:
    """BR4.5: la diferencia sale de la configuracion, no de una condicion escrita.

    Se comprueba sobre el texto del modulo porque eso es lo que la regla nombra:
    "aparece un identificador de aseguradora literal en el codigo".
    """
    from pathlib import Path

    from untangle.inbox import actions

    fuente = Path(actions.__file__).read_text(encoding="utf-8")
    for tenant_id in tenancy.available_ids():
        assert tenant_id not in fuente, f"'{tenant_id}' escrito en el codigo de decision"


async def test_la_tercera_decision_del_contrato_no_existe(app: FastAPI, emisora: str) -> None:
    """`request_more` se dejo fuera con su razon escrita (BR4.7).

    La ruta ni siquiera la acepta como valor: el conjunto es cerrado, asi que un
    cliente que la mande recibe un error de forma y no una conducta inventada.
    """
    caso = await nuevo_caso(emisora)

    respuesta = await _decidir(app, emisora, caso, accion="request_more")

    assert respuesta.status_code == 422


# --- BR4.3 y BR4.4: que se puede decidir y cuando -----------------------------


async def test_un_caso_que_espera_al_asegurado_no_se_decide(app: FastAPI, emisora: str) -> None:
    """Ni por la API. La vista dira por que y que campos faltan; esto lo impide."""
    caso = await nuevo_caso(emisora, estado=CaseState.AWAITING_INSURED)

    respuesta = await _decidir(app, emisora, caso)

    assert respuesta.status_code == 409
    vista = await casos.get_case(emisora, caso)
    assert vista is not None
    assert vista.state is CaseState.AWAITING_INSURED


# --- Un caso que la agente aun evalua lo toma el personal (2026-10-13) ---------


@pytest.mark.parametrize(
    ("estado", "transicion"),
    [(CaseState.VERIFYING, "T5"), (CaseState.DECIDING, "T7")],
)
async def test_el_personal_toma_un_caso_que_la_agente_aun_evalua(
    app: FastAPI,
    emisora: str,
    reanudaciones: list[dict[str, Any]],
    estado: CaseState,
    transicion: str,
) -> None:
    """Se deriva a nombre de quien lo toma y sigue el camino de siempre, con su rastro.

    El rastro es lo que se mira: la derivacion lleva la pareja de la tabla (T5 desde
    `verifying`, T7 desde `deciding`) y el actor `staff` con su identificador, y el cierre
    lleva el mismo. Sin eso la toma seria un cierre sin explicar de donde salio.
    """
    from untangle.case_record import history as historial
    from untangle.case_record.models import ActorType, ChangeKind

    caso = await nuevo_caso(emisora, estado=estado)
    ajustador = tenancy.require(emisora).staff[0].principal_id

    respuesta = await _decidir(app, emisora, caso)

    assert respuesta.status_code == 202, respuesta.text
    assert respuesta.json()["case_state"] == "closed"
    vista = await casos.get_case(emisora, caso)
    assert vista is not None
    assert vista.state is CaseState.CLOSED
    assert vista.resolution is not None
    assert vista.resolution.value == "approved"

    aplicadas = [
        e
        for e in await historial.of_case(emisora, caso)
        if e.change_kind is ChangeKind.TRANSITION_APPLIED
    ]
    derivacion = [e for e in aplicadas if (e.detail or "").startswith(f"{transicion}:")]
    assert len(derivacion) == 1, f"no hay una sola derivacion {transicion} en el historial"
    assert derivacion[0].actor.actor_type is ActorType.STAFF
    assert derivacion[0].actor.actor_id == ajustador
    # Y la ultima transicion aplicada, la del cierre, es del mismo ajustador.
    cierre = max(aplicadas, key=lambda e: e.changed_at)
    assert cierre.actor.actor_type is ActorType.STAFF
    assert cierre.actor.actor_id == ajustador
    # El grafo nunca dejo este caso esperando a nadie: no hay nada que reanudar.
    assert reanudaciones == []


async def test_un_visitante_con_enlace_no_toma_un_caso_que_la_agente_aun_evalua(
    app: FastAPI, emisora: str
) -> None:
    """Le quitaria a su propio caso el cierre directo, y la ruta lo rechaza sin tocarlo.

    Con el control positivo al final: el mismo caso lo toma el personal, asi que el `409`
    de antes no se debe a que el caso no se pudiera decidir sino a **quien** lo pedia.
    """
    from untangle.case_record import history as historial
    from untangle.inbox import visitor
    from untangle.tenancy import visitor_access

    caso = await nuevo_caso(emisora, estado=CaseState.DECIDING)
    antes = await historial.of_case(emisora, caso)
    token = (
        await visitor_access.issue_case_link(
            tenant_id=emisora,
            case_id=caso,
            signing_key=CLAVE_DE_ENLACES,
            now=datetime.now(UTC),
        )
    ).token

    async with cliente(app) as http:
        await http.post(f"/api{visitor.REDEEM_PATH}", json={"token": token})
        rechazo = await http.post(
            f"/api/inbox/{emisora}/cases/{caso}/decision",
            json={"decision": "approve", "comment": "Lo apruebo yo mismo."},
            headers={"Idempotency-Key": "visitante-toma-1"},
        )

    assert rechazo.status_code == 409, rechazo.text
    vista = await casos.get_case(emisora, caso)
    assert vista is not None
    assert vista.state is CaseState.DECIDING, "el rechazo movio el caso"
    assert await historial.of_case(emisora, caso) == antes, "el rechazo dejo huella en el caso"

    toma = await _decidir(app, emisora, caso, clave="personal-toma-1")
    assert toma.status_code == 202, toma.text


async def test_un_caso_que_las_reglas_ya_cerraron_no_se_decide(app: FastAPI, emisora: str) -> None:
    """El cierre directo lo aplica el sistema y el personal que llega tarde no lo pisa."""
    caso = await cerrado_por_las_reglas(emisora)

    respuesta = await _decidir(app, emisora, caso, accion="reject")

    assert respuesta.status_code == 409
    vista = await casos.get_case(emisora, caso)
    assert vista is not None
    assert vista.resolution is not None
    assert vista.resolution.value == "registered", "la decision pisó el cierre directo"


def test_solo_el_personal_toma_los_estados_de_evaluacion(emisora: str) -> None:
    """La misma regla que dibuja los botones y la que rechaza la ruta, en una sola funcion."""
    from untangle.inbox import actions

    aseguradora = tenancy.require(emisora)
    for estado in (CaseState.VERIFYING, CaseState.DECIDING):
        assert actions.offered_for(aseguradora, state=estado) == frozenset()
        assert actions.offered_for(aseguradora, state=estado, by_staff=True) == {
            actions.InboxAction.APPROVE,
            actions.InboxAction.REJECT,
        }
        with pytest.raises(actions.ActionNotAllowedError):
            actions.require_allowed(aseguradora, action=actions.InboxAction.APPROVE, state=estado)
    # Los estados que la agente ya no trabaja siguen como estaban, con o sin credencial.
    for estado in (
        CaseState.OPEN,
        CaseState.CAPTURING,
        CaseState.AWAITING_INSURED,
        CaseState.CLOSED,
    ):
        assert actions.offered_for(aseguradora, state=estado, by_staff=True) == frozenset()


async def test_dos_personas_no_deciden_el_mismo_caso(app: FastAPI, emisora: str) -> None:
    """La segunda ve que ya hay decision y su accion no se aplica.

    Con **claves distintas**, que es el caso de dos personas: la misma clave es
    idempotencia y se prueba aparte.
    """
    caso = await nuevo_caso(emisora)

    primera = await _decidir(app, emisora, caso, accion="approve", clave="diana")
    segunda = await _decidir(app, emisora, caso, accion="reject", clave="otro")

    assert primera.status_code == 202
    assert segunda.status_code == 409
    vista = await casos.get_case(emisora, caso)
    assert vista is not None
    assert vista.resolution is not None
    assert vista.resolution.value == "approved", "la segunda decision piso a la primera"


async def test_repetir_la_misma_clave_devuelve_la_primera_y_no_reanuda_otra_vez(
    app: FastAPI, emisora: str, reanudaciones: list[dict[str, Any]]
) -> None:
    """Reanudar dos veces le contaria al asegurado la decision dos veces."""
    caso = await nuevo_caso(emisora)

    primera = await _decidir(app, emisora, caso, clave="la-misma")
    segunda = await _decidir(app, emisora, caso, clave="la-misma")

    assert primera.status_code == 202
    assert segunda.status_code == 202
    assert primera.json()["decision_id"] == segunda.json()["decision_id"]
    assert len(reanudaciones) == 1, "se reanudo dos veces"


async def test_sin_puerto_de_reanudacion_la_decision_falla_en_alto(
    app: FastAPI, emisora: str
) -> None:
    """Y no registra la decision en silencio.

    Un caso decidido cuya conversacion nunca continua se ve igual que uno bien
    cerrado, y el asegurado se queda esperando una respuesta que no llega.
    """
    decision.reset_resume_handler()
    caso = await nuevo_caso(emisora)

    respuesta = await _decidir(app, emisora, caso)

    assert respuesta.status_code >= 500
