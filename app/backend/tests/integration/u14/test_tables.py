"""Las dos tablas de la bandeja: su aislamiento, sus llaves y su purgador.

Estas pruebas no se pueden escribir sin base de datos, y por eso viven aqui: lo
que comprueban es lo que **PostgreSQL** hace, no lo que el codigo cree que hace.

Cuatro cosas, y cada una cierra un fallo distinto:

1. **La politica de fila**, que es la segunda capa del aislamiento: si la ruta se
   equivocara, la base seguiria sin entregar la fila.
2. **La llave compuesta hacia el caso.** Las comprobaciones de llave foranea las
   hace el motor **por encima** de las politicas, asi que una llave de una sola
   columna dejaria a una aseguradora escribir un aviso que nombrara el caso de
   otra.
3. **La unicidad de la clave de idempotencia**, que es donde vive de verdad la
   promesa de C-05: en la base y no en el codigo que escribe.
4. **El purgador**, que es lo que la marca de dato de visitante obliga a tener.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from untangle.inbox.purge import INBOX_PURGER
from untangle.server import composition
from untangle.tenancy import purge as tenancy_purge
from untangle.tenancy import session

from .conftest import AHORA, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u14")

INSERTAR_AVISO = (
    "INSERT INTO inbox_event "
    "(tenant_id, event_id, case_id, kind, summary_redacted, created_at) "
    "VALUES (:tenant_id, :event_id, :case_id, :kind, :summary_redacted, :created_at)"
)

INSERTAR_RECIBO = (
    "INSERT INTO decision_receipt "
    "(receipt_id, tenant_id, idempotency_key, operation, case_id, request_digest, "
    " result_ref, created_at) "
    "VALUES (:receipt_id, :tenant_id, :idempotency_key, :operation, :case_id, "
    " :request_digest, :result_ref, :created_at)"
)


def _aviso(tenant_id: str, case_id: str, *, event_id: int = 1) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "event_id": event_id,
        "case_id": case_id,
        "kind": "case_updated",
        "summary_redacted": "un caso cambio",
        "created_at": AHORA,
    }


def _recibo(tenant_id: str, case_id: str, *, clave: str = "k-1") -> dict[str, Any]:
    return {
        "receipt_id": f"rec-{uuid.uuid4().hex[:12]}",
        "tenant_id": tenant_id,
        "idempotency_key": clave,
        "operation": "decision",
        "case_id": case_id,
        "request_digest": "resumen-de-lo-que-se-pidio",
        "result_ref": "decision-1",
        "created_at": AHORA,
    }


async def _escribir(tenant_id: str, sentencia: str, fila: dict[str, Any]) -> None:
    async with session.session_for(tenant_id) as sesion:
        await session.execute_sql(sesion, sentencia, **fila)


async def _rechazo(tenant_id: str, sentencia: str, fila: dict[str, Any]) -> str:
    with pytest.raises(IntegrityError) as error:
        await _escribir(tenant_id, sentencia, fila)
    return str(error.value)


# --- 1. La politica de fila ---------------------------------------------------


async def test_el_aviso_de_una_aseguradora_no_existe_para_otra(
    dos_aseguradoras: tuple[str, str],
) -> None:
    ajena, propia = dos_aseguradoras
    caso = await nuevo_caso(ajena)
    await _escribir(ajena, INSERTAR_AVISO, _aviso(ajena, caso))

    async with session.session_for(propia) as sesion:
        filas = await session.fetch_all(sesion, "SELECT event_id FROM inbox_event")

    assert not filas


async def test_el_recibo_de_una_aseguradora_no_existe_para_otra(
    dos_aseguradoras: tuple[str, str],
) -> None:
    ajena, propia = dos_aseguradoras
    caso = await nuevo_caso(ajena)
    await _escribir(ajena, INSERTAR_RECIBO, _recibo(ajena, caso))

    async with session.session_for(propia) as sesion:
        filas = await session.fetch_all(sesion, "SELECT receipt_id FROM decision_receipt")

    assert not filas


# --- 2. La llave compuesta ----------------------------------------------------


async def test_un_aviso_no_puede_nombrar_el_caso_de_otra_aseguradora(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Dos escrituras con la misma forma, cambiando una sola cosa.

    La primera apunta a lo propio y entra --asi el rechazo de la segunda no se
    puede deber a otra restriccion--; la segunda apunta al caso de la otra y
    choca contra la llave.
    """
    ajena, propia = dos_aseguradoras
    caso_ajeno = await nuevo_caso(ajena)
    caso_propio = await nuevo_caso(propia)

    await _escribir(propia, INSERTAR_AVISO, _aviso(propia, caso_propio))

    mensaje = await _rechazo(propia, INSERTAR_AVISO, _aviso(propia, caso_ajeno, event_id=2))

    assert "inbox_event_del_caso" in mensaje


async def test_borrar_el_caso_se_lleva_sus_avisos_y_su_recibo(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La cascada: un caso borrado no deja avisos ni recibos huerfanos detras."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _escribir(propia, INSERTAR_AVISO, _aviso(propia, caso))
    await _escribir(propia, INSERTAR_RECIBO, _recibo(propia, caso))

    async with session.session_for(propia) as sesion:
        await session.execute_sql(
            sesion, "DELETE FROM case_record WHERE case_id = :case_id", case_id=caso
        )
        avisos = await session.fetch_all(sesion, "SELECT event_id FROM inbox_event")
        recibos = await session.fetch_all(sesion, "SELECT receipt_id FROM decision_receipt")

    assert not avisos
    assert not recibos


# --- 3. La promesa de idempotencia vive en la base ----------------------------


async def test_dos_recibos_con_la_misma_clave_no_caben(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Lo que impide una segunda decision es esta restriccion, no un `if`.

    Dos peticiones a la vez con la misma clave chocan aqui y una pierde. Con la
    comprobacion solo en el codigo, las dos leerian "no hay recibo" antes de que
    ninguna escribiera.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _escribir(propia, INSERTAR_RECIBO, _recibo(propia, caso, clave="la-misma"))

    mensaje = await _rechazo(propia, INSERTAR_RECIBO, _recibo(propia, caso, clave="la-misma"))

    assert "decision_receipt_clave_unica" in mensaje


async def test_la_misma_clave_en_otra_operacion_si_cabe(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La unicidad es por aseguradora **y operacion**: decidir y corregir no chocan.

    Sin esta prueba, una unicidad de mas --solo por clave-- pasaria la de arriba
    y romperia la correccion de un campo hecha con la clave de una decision.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _escribir(propia, INSERTAR_RECIBO, _recibo(propia, caso, clave="la-misma"))

    otra = _recibo(propia, caso, clave="la-misma")
    otra["operation"] = "field_correction"
    await _escribir(propia, INSERTAR_RECIBO, otra)

    async with session.session_for(propia) as sesion:
        filas = await session.fetch_all(sesion, "SELECT receipt_id FROM decision_receipt")

    assert len(filas) == 2


async def test_un_aviso_de_un_tipo_que_no_existe_se_rechaza(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """El conjunto cerrado de C-06, impuesto por la base y no por quien escribe."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    fila = _aviso(propia, caso)
    fila["kind"] = "case_renamed"
    mensaje = await _rechazo(propia, INSERTAR_AVISO, fila)

    assert "inbox_event_tipo_valido" in mensaje


# --- 4. El purgador -----------------------------------------------------------


async def test_la_tabla_de_avisos_tiene_purgador_registrado() -> None:
    """La marca de dato de visitante obliga a tenerlo, y esto lo comprueba.

    Le pregunta al catalogo de la base que tablas llevan la marca y falla si
    alguna no esta cubierta por el registro escrito a mano de la raiz.
    """
    sin_cubrir = await tenancy_purge.tables_without_purger(composition.PURGADORES)

    assert "inbox_event" not in sin_cubrir
    assert not sin_cubrir


async def test_el_purgador_borra_los_avisos_y_conserva_los_recibos(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Las dos mitades: lo que se va y lo que se queda, contadas por separado."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _escribir(propia, INSERTAR_AVISO, _aviso(propia, caso))
    await _escribir(propia, INSERTAR_RECIBO, _recibo(propia, caso))

    resultado = await INBOX_PURGER.purge(older_than=AHORA.replace(year=2027))

    assert resultado.deleted == 1
    assert resultado.kept == 1

    async with session.session_for(propia) as sesion:
        avisos = await session.fetch_all(sesion, "SELECT event_id FROM inbox_event")
        recibos = await session.fetch_all(sesion, "SELECT receipt_id FROM decision_receipt")

    assert not avisos
    assert len(recibos) == 1
