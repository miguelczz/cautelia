"""La tabla de la corrida del ajustador: aislamiento, llaves, restricciones y borrado.

Contra PostgreSQL de verdad, porque lo que se comprueba es lo que hace el motor: la politica de
fila, la llave compuesta hacia el caso, la cascada y las restricciones que atan los campos al
estado. Cubre el aislamiento por aseguradora **en la base** (no solo en el codigo) y el hueco de
llave que U10 tuvo que cerrar en una segunda revision y que esta tabla no abre (UG-3).
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError

from untangle.case_record import purge as case_purge
from untangle.server import composition
from untangle.tenancy import purge, rls_assertion, session

from .conftest import AHORA, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u14")

TABLA = "adjuster_run"

INSERTAR = """
    INSERT INTO adjuster_run (tenant_id, case_id, status, attempt, steps, decision, summary,
                              model, searches_used, error_kind, created_at, updated_at)
    VALUES (:tenant_id, :case_id, :status, :attempt, CAST(:steps AS jsonb), :decision, :summary,
            :model, :searches_used, :error_kind, :created_at, :updated_at)
"""

LEER = "SELECT tenant_id, case_id FROM adjuster_run"


def _fila(tenant_id: str, case_id: str, **cambios: Any) -> dict[str, Any]:
    fila: dict[str, Any] = {
        "tenant_id": tenant_id,
        "case_id": case_id,
        "status": "running",
        "attempt": 1,
        "steps": "[]",
        "decision": None,
        "summary": None,
        "model": "claude-haiku-5-5",
        "searches_used": 0,
        "error_kind": None,
        "created_at": AHORA,
        "updated_at": AHORA,
    }
    return fila | cambios


async def _escribir(tenant_id: str, fila: dict[str, Any]) -> None:
    async with session.session_for(tenant_id) as sesion:
        await session.execute_sql(sesion, INSERTAR, **fila)


async def _rechazo(tenant_id: str, fila: dict[str, Any]) -> str:
    with pytest.raises(IntegrityError) as rechazo:
        await _escribir(tenant_id, fila)
    return str(rechazo.value)


# --- Aislamiento por aseguradora, en la base ----------------------------------


async def test_la_tabla_tiene_aislamiento_habilitado_forzado_y_con_politica() -> None:
    """La misma asercion que el arranque hace sobre todo el esquema, sobre esta tabla."""
    async with session.unscoped_session() as sesion:
        tablas = {t.table: t for t in await rls_assertion.read_tables(sesion)}

    assert TABLA in tablas
    assert tablas[TABLA].row_security
    assert tablas[TABLA].force_row_security
    assert tablas[TABLA].tenant_policies >= 1


async def test_cada_aseguradora_ve_solo_sus_corridas(dos_aseguradoras: tuple[str, str]) -> None:
    primera, segunda = dos_aseguradoras
    caso_primera = await nuevo_caso(primera)
    caso_segunda = await nuevo_caso(segunda)
    await _escribir(primera, _fila(primera, caso_primera))
    await _escribir(segunda, _fila(segunda, caso_segunda))

    async with session.session_for(primera) as sesion:
        vistas_primera = [
            (str(f["tenant_id"]), str(f["case_id"])) for f in await session.fetch_all(sesion, LEER)
        ]
    async with session.session_for(segunda) as sesion:
        vistas_segunda = [
            (str(f["tenant_id"]), str(f["case_id"])) for f in await session.fetch_all(sesion, LEER)
        ]

    assert vistas_primera == [(primera, caso_primera)]
    assert vistas_segunda == [(segunda, caso_segunda)]


async def test_escribir_con_la_aseguradora_de_otra_lo_rechaza_la_politica(
    dos_aseguradoras: tuple[str, str],
) -> None:
    primera, segunda = dos_aseguradoras
    caso = await nuevo_caso(primera)

    with pytest.raises(DBAPIError):
        await _escribir(primera, _fila(segunda, caso))


# --- Llave compuesta hacia el caso (UG-3, la leccion de U10) ------------------


async def test_una_corrida_no_puede_apuntar_al_caso_de_otra_aseguradora(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Dos escrituras con la misma forma, cambiando una sola cosa.

    La primera apunta a lo propio y entra --asi el rechazo de la segunda no se puede deber a
    otra restriccion--; la segunda apunta al caso de la otra y choca contra la llave, que el
    motor comprueba por encima de las politicas de fila.
    """
    ajena, propia = dos_aseguradoras
    caso_ajeno = await nuevo_caso(ajena)
    caso_propio = await nuevo_caso(propia)

    await _escribir(propia, _fila(propia, caso_propio))

    mensaje = await _rechazo(propia, _fila(propia, caso_ajeno))

    assert "adjuster_run_del_caso" in mensaje


async def test_un_caso_tiene_a_lo_sumo_una_corrida(dos_aseguradoras: tuple[str, str]) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _escribir(propia, _fila(propia, caso))

    with pytest.raises(IntegrityError):
        await _escribir(propia, _fila(propia, caso, attempt=2))


# --- Borrado con el caso ------------------------------------------------------


async def test_borrar_el_caso_se_lleva_su_corrida_y_conserva_las_otras(
    dos_aseguradoras: tuple[str, str],
) -> None:
    primera, _ = dos_aseguradoras
    borrado = await nuevo_caso(primera)
    conservado = await nuevo_caso(primera)
    await _escribir(primera, _fila(primera, borrado))
    await _escribir(primera, _fila(primera, conservado))

    async with session.session_for(primera) as sesion:
        await session.execute_sql(
            sesion, "DELETE FROM case_record WHERE case_id = :case_id", case_id=borrado
        )
    async with session.session_for(primera) as sesion:
        restantes = [str(f["case_id"]) for f in await session.fetch_all(sesion, LEER)]

    assert restantes == [conservado]


async def test_la_tabla_lleva_la_marca_y_la_cubre_el_purgador_del_caso() -> None:
    marcadas = await purge.visitor_data_tables()

    assert TABLA in marcadas
    assert TABLA in case_purge.CASE_RECORD_PURGER.tables
    assert await purge.tables_without_purger(composition.PURGADORES) == frozenset()


# --- Lo que la base impone: los campos atados al estado -----------------------


async def test_una_corrida_decidida_lleva_decision_y_explicacion(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    sin_decision = await _rechazo(
        propia, _fila(propia, caso, status="decided", summary="Cubierto por colision.")
    )
    assert "adjuster_run_decision_solo_si_decidida" in sin_decision

    sin_explicacion = await _rechazo(
        propia, _fila(propia, caso, status="decided", decision="approve")
    )
    assert "adjuster_run_resumen_solo_si_decidida" in sin_explicacion

    await _escribir(
        propia,
        _fila(propia, caso, status="decided", decision="approve", summary="Cubierto por colision."),
    )


async def test_una_decision_sin_estado_decidido_se_rechaza(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    mensaje = await _rechazo(propia, _fila(propia, caso, status="running", decision="reject"))

    assert "adjuster_run_decision_solo_si_decidida" in mensaje


async def test_el_tipo_de_error_solo_existe_en_una_corrida_fallida(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    mensaje = await _rechazo(propia, _fila(propia, caso, status="running", error_kind="timeout"))
    assert "adjuster_run_error_solo_si_fallida" in mensaje

    await _escribir(propia, _fila(propia, caso, status="failed", error_kind="timeout"))


@pytest.mark.parametrize(
    ("cambios", "restriccion"),
    [
        ({"status": "pensando"}, "adjuster_run_estado_valido"),
        ({"attempt": 0}, "adjuster_run_intento_positivo"),
        ({"searches_used": -1}, "adjuster_run_busquedas_no_negativas"),
        ({"steps": '{"no": "una lista"}'}, "adjuster_run_pasos_es_lista"),
        ({"model": ""}, "adjuster_run_dice_el_modelo"),
    ],
)
async def test_la_base_rechaza_lo_que_el_modelo_tampoco_admite(
    dos_aseguradoras: tuple[str, str], cambios: dict[str, Any], restriccion: str
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    mensaje = await _rechazo(propia, _fila(propia, caso, **cambios))

    assert restriccion in mensaje


async def test_una_decision_que_no_es_de_la_bandeja_se_rechaza(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    mensaje = await _rechazo(
        propia,
        _fila(propia, caso, status="decided", decision="request_more", summary="Faltan datos."),
    )

    assert "adjuster_run_decision_valida" in mensaje
