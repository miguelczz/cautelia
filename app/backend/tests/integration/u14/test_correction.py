"""Corregir un campo: su rastro, su recibo y lo que no cambia (BR3.1 a BR3.4).

Todo por HTTP. La pantalla que no ofrece la accion es cortesia; lo que de verdad
impide corregir un caso cerrado es que la peticion directa se rechace, y eso solo
se ve entrando por la puerta.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI

from untangle.case_record import api as casos
from untangle.case_record import history as historial
from untangle.case_record.models import (
    Actor,
    ActorType,
    AttachmentKind,
    AttachmentState,
    CaseState,
    Channel,
    ClosingEvidence,
    Resolution,
)
from untangle.case_record.rules import TransitionContext

from .conftest import AHORA, cliente, credencial_de, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u14")

CAMPO = "location"


@pytest.fixture
def aseguradora() -> str:
    from untangle.tenancy import api as tenancy

    return tenancy.available_ids()[0]


def _ruta(tenant_id: str, case_id: str, campo: str = CAMPO) -> str:
    return f"/api/inbox/{tenant_id}/cases/{case_id}/fields/{campo}"


async def _corregir(  # noqa: PLR0913 -- la ruta, el valor, la clave y el campo
    app: FastAPI,
    tenant_id: str,
    case_id: str,
    *,
    valor: str,
    clave: str | None = "idem-1",
    campo: str = CAMPO,
) -> Any:
    cabeceras = {"Idempotency-Key": clave} if clave is not None else {}
    async with cliente(app, credencial=credencial_de(tenant_id)) as http:
        return await http.patch(
            _ruta(tenant_id, case_id, campo), json={"value": valor}, headers=cabeceras
        )


# --- BR3.1: la correccion deja su rastro --------------------------------------


async def test_una_correccion_deja_quien_cuando_y_el_valor_anterior(
    app: FastAPI, aseguradora: str
) -> None:
    """El historial de U4 registra el cambio, con la persona que lo hizo.

    Lo escribe U4 --es su historial-- y lo que la bandeja aporta es el actor. Se
    comprueba sobre el historial y no sobre la respuesta: una respuesta que dijera
    "hecho" sin que nada se hubiera escrito la pasaria igual.
    """
    caso = await nuevo_caso(aseguradora)

    respuesta = await _corregir(app, aseguradora, caso, valor="Carrera 43 con calle 10")

    assert respuesta.status_code == 200, respuesta.text
    cambios = await historial.of_case(aseguradora, caso)
    correcciones = [c for c in cambios if c.field_key == CAMPO]
    assert len(correcciones) == 1
    assert correcciones[0].actor.actor_type is ActorType.STAFF
    assert correcciones[0].actor.actor_id, "la entrada no dice quien corrigio"


async def test_corregir_no_cambia_la_transcripcion(app: FastAPI, aseguradora: str) -> None:
    """Corregir arregla un error de captura; no reescribe lo que dijo una persona.

    Se compara la transcripcion entera antes y despues: comprobar solo que sigue
    teniendo el mismo numero de turnos dejaria pasar un texto reescrito.
    """
    caso = await nuevo_caso(aseguradora)
    antes = await casos.transcript_of(aseguradora, caso)

    await _corregir(app, aseguradora, caso, valor="Carrera 43 con calle 10")

    assert await casos.transcript_of(aseguradora, caso) == antes


# --- BR3.3: el valor invalido conserva el anterior ----------------------------


async def test_un_campo_que_no_existe_en_el_esquema_se_rechaza(
    app: FastAPI, aseguradora: str
) -> None:
    """La validacion es la de U4; la bandeja no escribe una segunda.

    Dos validaciones para el mismo campo se separan, y el dia que se separen la
    que manda es la que corre antes.
    """
    caso = await nuevo_caso(aseguradora)

    respuesta = await _corregir(app, aseguradora, caso, valor="lo que sea", campo="campo-inventado")

    assert respuesta.status_code == 422


async def test_un_intento_fallido_no_borra_el_valor_bueno(app: FastAPI, aseguradora: str) -> None:
    """Lo que impide que un error de validacion destruya un dato ya capturado."""
    caso = await nuevo_caso(aseguradora)
    await _corregir(app, aseguradora, caso, valor="Carrera 43 con calle 10", clave="ok")

    await _corregir(app, aseguradora, caso, valor="x", clave="malo", campo="no-existe")

    from untangle.case_record import repository as case_repo

    campos = await case_repo.load_fields(aseguradora, caso)
    guardado = next(c for c in campos if c.field_key == CAMPO)
    assert guardado.value is not None, "el intento fallido se llevo el valor anterior"


# --- BR3.4: un caso cerrado no admite correcciones ----------------------------


async def test_un_caso_cerrado_rechaza_la_correccion_por_la_api(
    app: FastAPI, aseguradora: str
) -> None:
    """Con el control positivo delante: abierto acepta, cerrado rechaza.

    Sin el primero, la prueba pasaria contra una ruta que rechazara siempre.
    """
    abierto = await nuevo_caso(aseguradora)
    cerrado = await nuevo_caso(aseguradora)
    await _cerrar(aseguradora, cerrado)

    acepta = await _corregir(app, aseguradora, abierto, valor="Calle 10", clave="a")
    rechaza = await _corregir(app, aseguradora, cerrado, valor="Calle 10", clave="b")

    assert acepta.status_code == 200
    assert rechaza.status_code == 409


async def _cerrar(tenant_id: str, case_id: str) -> None:
    """Cierra un caso por el camino declarado, con su resolucion y su evidencia."""
    await casos.close_case(
        tenant_id,
        case_id,
        resolution=Resolution.APPROVED,
        # La evidencia de cierre es lo que un caso cerrado expone: sin los cinco
        # adjuntos U4 no deja cerrar, y por eso aqui se pasan como los pasa quien
        # cierra de verdad.
        closing_evidence=ClosingEvidence(
            transcript=AttachmentState(kind=AttachmentKind.PRESENT, reference=case_id),
            cited_clauses=AttachmentState(kind=AttachmentKind.EMPTY),
            fired_rules=AttachmentState(kind=AttachmentKind.EMPTY),
            trace_id=AttachmentState(kind=AttachmentKind.EMPTY),
            control_results=AttachmentState(kind=AttachmentKind.EMPTY),
        ),
        context=TransitionContext(
            now=AHORA,
            actor=Actor(actor_type=ActorType.STAFF, actor_id="diana"),
            channel=Channel.CHAT,
        ),
    )


# --- C-05: la idempotencia ----------------------------------------------------


async def test_repetir_la_misma_clave_no_corrige_dos_veces(app: FastAPI, aseguradora: str) -> None:
    """Y devuelve el mismo recibo, que es lo que C-05 promete."""
    caso = await nuevo_caso(aseguradora)

    primera = await _corregir(app, aseguradora, caso, valor="Calle 10", clave="la-misma")
    segunda = await _corregir(app, aseguradora, caso, valor="Calle 10", clave="la-misma")

    assert primera.status_code == 200
    assert segunda.status_code == 200
    assert primera.json()["receipt_id"] == segunda.json()["receipt_id"]

    cambios = await historial.of_case(aseguradora, caso)
    assert len([c for c in cambios if c.field_key == CAMPO]) == 1, "se corrigio dos veces"


async def test_una_clave_reciclada_para_otra_peticion_es_un_conflicto(
    app: FastAPI, aseguradora: str
) -> None:
    """Y **no** devuelve el resultado guardado.

    Devolverle a alguien el resultado de una peticion que no hizo es peor que
    fallar: le dice que su correccion se aplico cuando lo que se aplico fue otra.
    """
    caso = await nuevo_caso(aseguradora)
    await _corregir(app, aseguradora, caso, valor="Calle 10", clave="reciclada")

    otra = await _corregir(app, aseguradora, caso, valor="Calle 99", clave="reciclada")

    assert otra.status_code == 409


async def test_sin_clave_de_idempotencia_no_se_corrige(app: FastAPI, aseguradora: str) -> None:
    """Sin ella, un segundo envio del formulario escribiria una segunda correccion."""
    caso = await nuevo_caso(aseguradora)

    respuesta = await _corregir(app, aseguradora, caso, valor="Calle 10", clave=None)

    assert respuesta.status_code == 422


# --- El aislamiento, tambien al corregir ---------------------------------------


async def test_no_se_corrige_el_caso_de_otra_aseguradora(
    app: FastAPI, dos_aseguradoras: tuple[str, str]
) -> None:
    ajena, propia = dos_aseguradoras
    caso_ajeno = await nuevo_caso(ajena)

    respuesta = await _corregir(app, propia, caso_ajeno, valor="Calle 10")

    assert respuesta.status_code == 404
    cambios = await historial.of_case(ajena, caso_ajeno)
    assert not [c for c in cambios if c.field_key == CAMPO], "se corrigio un caso ajeno"


async def test_un_caso_que_espera_al_asegurado_si_se_corrige(
    app: FastAPI, aseguradora: str
) -> None:
    """Es lo contrario de decidir: un caso a medias se corrige, pero no se decide.

    La tabla del diseno funcional lo dice estado por estado, y confundir las dos
    columnas dejaria sin arreglar justo los casos que mas lo necesitan.
    """
    caso = await nuevo_caso(aseguradora, estado=CaseState.AWAITING_INSURED)

    respuesta = await _corregir(app, aseguradora, caso, valor="Calle 10")

    assert respuesta.status_code == 200
