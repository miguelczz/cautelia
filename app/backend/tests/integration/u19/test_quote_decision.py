"""La decision del suscriptor: quien puede, en que orden y sobre que (BR4.1, BR4.3).

Todo entra **por HTTP**: lo que U19 anade es un permiso que se comprueba en el
servidor, y una prueba que llamara a la funcion no diria nada sobre lo que
responde la bandeja a una peticion directa, que es justo lo que AC6.3.3 describe.

Las dos mitades de BR4.1 van juntas en cada caso: que el suscriptor **si** decide
una solicitud y que los otros **no**. Con solo la segunda, una ruta que rechazara
a todo el mundo pasaria igual.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI

from untangle.case_record import api as casos
from untangle.case_record.models import CaseState, RecordType
from untangle.inbox import decision
from untangle.inbox import visitor as enlace
from untangle.tenancy import api as tenancy
from untangle.tenancy import visitor_access
from untangle.tenancy.models import Role, TenantKind

from .conftest import (
    CLAVE_DE_ENLACES,
    cliente,
    credencial_de_rol,
    nueva_solicitud,
)

pytestmark = pytest.mark.usefixtures("base_de_u19")


@pytest.fixture
def agencia() -> str:
    """Una agencia: su agente de cuenta no decide, ni cobertura ni cotizaciones."""
    return next(
        c.tenant_id
        for c in sorted(tenancy.loaded().available, key=lambda c: c.tenant_id)
        if c.kind is TenantKind.AGENCY
    )


@pytest.fixture(autouse=True)
def reanudaciones(app: FastAPI) -> Any:
    """Un doble de la reanudacion que anota **en que estado** estaba el caso.

    Depende de `app` a proposito: la raiz de composicion enchufa el puerto real al
    construir la aplicacion y el doble tiene que quedar despues.
    """
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


async def _decidir(  # noqa: PLR0913 -- el rol, la accion, el comentario y la clave
    app: FastAPI,
    tenant_id: str,
    case_id: str,
    *,
    rol: Role = Role.UNDERWRITER,
    accion: str = "approve",
    comentario: str = "Elegible: el vehiculo y el uso entran en la guia.",
    clave: str = "dec-u19-1",
) -> Any:
    async with cliente(app, credencial=credencial_de_rol(tenant_id, rol)) as http:
        return await http.post(
            f"/api/inbox/{tenant_id}/cases/{case_id}/decision",
            json={"decision": accion, "comment": comentario},
            headers={"Idempotency-Key": clave},
        )


# --- BR4.1: solo el suscriptor, y en la API ----------------------------------


async def test_el_suscriptor_decide_la_solicitud_y_queda_cerrada(
    app: FastAPI, aseguradora_que_cotiza: str
) -> None:
    """El control positivo. Sin el, los rechazos de abajo no significan nada."""
    caso = await nueva_solicitud(aseguradora_que_cotiza)

    respuesta = await _decidir(app, aseguradora_que_cotiza, caso)

    assert respuesta.status_code == 202, respuesta.text
    assert respuesta.json()["resolution"] == "approved"
    vista = await casos.get_case(aseguradora_que_cotiza, caso)
    assert vista is not None
    assert vista.state is CaseState.CLOSED


async def test_rechazarla_la_cierra_con_la_otra_resolucion(
    app: FastAPI, aseguradora_que_cotiza: str
) -> None:
    """Las dos salidas de la decision, no solo la que aprueba."""
    caso = await nueva_solicitud(aseguradora_que_cotiza)

    respuesta = await _decidir(app, aseguradora_que_cotiza, caso, accion="reject")

    assert respuesta.status_code == 202, respuesta.text
    assert respuesta.json()["resolution"] == "rejected"


async def test_el_ajustador_no_decide_una_solicitud_y_no_la_cambia(
    app: FastAPI, aseguradora_que_cotiza: str
) -> None:
    """AC6.3.3 por la API: la fila `adjuster` + `decide_quote` de la tabla.

    El ajustador **si** decide los siniestros de su aseguradora, asi que lo que
    esto comprueba no es que no pueda nada: es que decidir cobertura y decidir una
    cotizacion dejaron de ser el mismo permiso.
    """
    caso = await nueva_solicitud(aseguradora_que_cotiza)

    respuesta = await _decidir(app, aseguradora_que_cotiza, caso, rol=Role.ADJUSTER)

    assert respuesta.status_code == 404, respuesta.text
    vista = await casos.get_case(aseguradora_que_cotiza, caso)
    assert vista is not None
    assert vista.state is CaseState.DERIVED, "la solicitud cambio con una peticion rechazada"


async def test_el_agente_de_cuenta_no_decide_una_solicitud_y_no_la_cambia(
    app: FastAPI, agencia: str
) -> None:
    """La tercera credencial, contra la API y en su propia aseguradora.

    Se siembra la solicitud **en la agencia** a proposito: una credencial de otra
    aseguradora se rechazaria por no ser de esta, y eso no diria nada sobre su
    permiso. Que la agencia no tenga la cotizacion activa no cambia la regla: el
    permiso no depende de la configuracion de quien la pide.
    """
    caso = await nueva_solicitud(agencia)

    respuesta = await _decidir(app, agencia, caso, rol=Role.ACCOUNT_AGENT)

    assert respuesta.status_code == 404, respuesta.text
    vista = await casos.get_case(agencia, caso)
    assert vista is not None
    assert vista.state is CaseState.DERIVED


async def test_el_suscriptor_no_decide_un_siniestro(
    app: FastAPI, aseguradora_que_cotiza: str
) -> None:
    """La otra mitad de la separacion, y la que hace que el permiso nuevo sirva.

    Sin esta, `decide_quote` seria un permiso **adicional** y el suscriptor
    decidiria cobertura tambien.
    """
    caso = await nueva_solicitud(aseguradora_que_cotiza, tipo=RecordType.CLAIM)

    respuesta = await _decidir(app, aseguradora_que_cotiza, caso)

    assert respuesta.status_code == 404, respuesta.text
    vista = await casos.get_case(aseguradora_que_cotiza, caso)
    assert vista is not None
    assert vista.state is CaseState.DERIVED


async def test_un_visitante_con_su_enlace_no_decide_su_propia_solicitud(
    app: FastAPI, aseguradora_que_cotiza: str
) -> None:
    """El enlace deja ver el caso propio y, en un siniestro, decidirlo (BR5.5 de U14).

    Una solicitud de cotizacion no: quien la pidio aprobandose a si misma no es una
    decision, y el rol que la decide es el del suscriptor.
    """
    caso = await nueva_solicitud(aseguradora_que_cotiza)
    emitido = await visitor_access.issue_case_link(
        tenant_id=aseguradora_que_cotiza,
        case_id=caso,
        signing_key=CLAVE_DE_ENLACES,
    )

    async with cliente(app) as http:
        canje = await http.post(f"/api{enlace.REDEEM_PATH}", json={"token": emitido.token})
        assert canje.status_code == 200, canje.text
        # La vista si: es su caso.
        vista = await http.get(f"/api/inbox/{aseguradora_que_cotiza}/cases/{caso}")
        decidido = await http.post(
            f"/api/inbox/{aseguradora_que_cotiza}/cases/{caso}/decision",
            json={"decision": "approve", "comment": "Me la apruebo yo."},
            headers={"Idempotency-Key": "visitante-u19"},
        )

    assert vista.status_code == 200, vista.text
    assert decidido.status_code == 404, decidido.text
    actual = await casos.get_case(aseguradora_que_cotiza, caso)
    assert actual is not None
    assert actual.state is CaseState.DERIVED


async def test_el_suscriptor_no_decide_la_solicitud_de_otra_aseguradora(
    app: FastAPI, aseguradora_que_cotiza: str, otra_aseguradora: str
) -> None:
    """Su credencial no vale fuera de su aseguradora, ni para su propio permiso."""
    ajeno = await nueva_solicitud(otra_aseguradora)

    async with cliente(
        app, credencial=credencial_de_rol(aseguradora_que_cotiza, Role.UNDERWRITER)
    ) as http:
        respuesta = await http.post(
            f"/api/inbox/{otra_aseguradora}/cases/{ajeno}/decision",
            json={"decision": "approve", "comment": "No es mia."},
            headers={"Idempotency-Key": "ajena-u19"},
        )

    assert respuesta.status_code == 404, respuesta.text
    vista = await casos.get_case(otra_aseguradora, ajeno)
    assert vista is not None
    assert vista.state is CaseState.DERIVED


# --- BR4.3: se registra antes de reanudar ------------------------------------


async def test_se_registra_antes_de_reanudar(
    app: FastAPI, aseguradora_que_cotiza: str, reanudaciones: list[dict[str, Any]]
) -> None:
    """Cuando el grafo se entera, la solicitud ya esta cerrada.

    Si fuera al reves, el estado que anota el doble seria `derived`, y esta prueba
    es la unica forma de verlo desde fuera.
    """
    caso = await nueva_solicitud(aseguradora_que_cotiza)

    respuesta = await _decidir(app, aseguradora_que_cotiza, caso)

    assert respuesta.status_code == 202, respuesta.text
    assert len(reanudaciones) == 1
    assert reanudaciones[0]["case_id"] == caso
    assert reanudaciones[0]["estado_al_reanudar"] is CaseState.CLOSED


async def test_una_peticion_rechazada_no_reanuda_nada(
    app: FastAPI, aseguradora_que_cotiza: str, reanudaciones: list[dict[str, Any]]
) -> None:
    """Lo que no se decide no continua: el grafo no se enteraria de nada."""
    caso = await nueva_solicitud(aseguradora_que_cotiza)

    await _decidir(app, aseguradora_que_cotiza, caso, rol=Role.ADJUSTER)

    assert reanudaciones == []


async def test_sin_comentario_no_se_decide_ni_se_reanuda(
    app: FastAPI, aseguradora_que_cotiza: str, reanudaciones: list[dict[str, Any]]
) -> None:
    """El comentario es lo que hace auditable la decision (BR4.1 de U14)."""
    caso = await nueva_solicitud(aseguradora_que_cotiza)

    respuesta = await _decidir(app, aseguradora_que_cotiza, caso, comentario="   ")

    assert respuesta.status_code == 400, respuesta.text
    assert reanudaciones == []
    vista = await casos.get_case(aseguradora_que_cotiza, caso)
    assert vista is not None
    assert vista.state is CaseState.DERIVED
