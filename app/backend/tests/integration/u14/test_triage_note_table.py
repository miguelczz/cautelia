"""La tabla de lo que el ajustador anota para las reglas: aislamiento, llaves y borrado.

Contra PostgreSQL de verdad, porque lo que se comprueba es lo que hace el motor: la
politica de fila, la llave compuesta hacia el caso y la cascada. Cubre el aislamiento por
aseguradora **en la base** (no solo en el codigo), el hueco de llave que U10 tuvo que
cerrar en una segunda revision y que esta tabla no abre (UG-3), y que "sin anotar" y
"no" son dos valores distintos.
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

TABLA = "case_triage_note"

INSERTAR = """
    INSERT INTO case_triage_note (tenant_id, case_id, claim_amount, coverage_disputed,
                                  fraud_suspected, noted_by, updated_at)
    VALUES (:tenant_id, :case_id, :claim_amount, :coverage_disputed, :fraud_suspected,
            :noted_by, :updated_at)
"""

LEER = "SELECT tenant_id, case_id FROM case_triage_note"


def _fila(tenant_id: str, case_id: str, **cambios: Any) -> dict[str, Any]:
    fila: dict[str, Any] = {
        "tenant_id": tenant_id,
        "case_id": case_id,
        "claim_amount": 1500,
        "coverage_disputed": True,
        "fraud_suspected": False,
        "noted_by": "ajustador-de-prueba",
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


async def test_cada_aseguradora_ve_solo_lo_que_anoto(dos_aseguradoras: tuple[str, str]) -> None:
    primera, segunda = dos_aseguradoras
    caso_primera = await nuevo_caso(primera)
    caso_segunda = await nuevo_caso(segunda)
    await _escribir(primera, _fila(primera, caso_primera, claim_amount=111))
    await _escribir(segunda, _fila(segunda, caso_segunda, claim_amount=222))

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


async def test_una_anotacion_no_puede_apuntar_al_caso_de_otra_aseguradora(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Dos escrituras con la misma forma, cambiando una sola cosa.

    La primera apunta a lo propio y entra --asi el rechazo de la segunda no se puede
    deber a otra restriccion--; la segunda apunta al caso de la otra y choca contra la
    llave, que el motor comprueba por encima de las politicas de fila.
    """
    ajena, propia = dos_aseguradoras
    caso_ajeno = await nuevo_caso(ajena)
    caso_propio = await nuevo_caso(propia)

    await _escribir(propia, _fila(propia, caso_propio))

    mensaje = await _rechazo(propia, _fila(propia, caso_ajeno))

    assert "case_triage_note_del_caso" in mensaje


async def test_un_caso_tiene_a_lo_sumo_una_anotacion(dos_aseguradoras: tuple[str, str]) -> None:
    """Una fila por caso: lo que vale es lo ultimo, y el historial vive en otro sitio."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _escribir(propia, _fila(propia, caso))

    with pytest.raises(IntegrityError):
        await _escribir(propia, _fila(propia, caso, claim_amount=9))


# --- Borrado con el caso ------------------------------------------------------


async def test_borrar_el_caso_se_lleva_su_anotacion_y_conserva_las_otras(
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


# --- Lo que la base impone ----------------------------------------------------


async def test_sin_anotar_y_no_son_dos_valores_distintos(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Nulo es "sin anotar" y falso es "se comprobo y no": una regla distingue las dos."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _escribir(
        propia,
        _fila(propia, caso, claim_amount=None, coverage_disputed=None, fraud_suspected=False),
    )

    async with session.session_for(propia) as sesion:
        fila = await session.fetch_one(
            sesion,
            "SELECT claim_amount, coverage_disputed, fraud_suspected FROM case_triage_note",
        )

    assert fila is not None
    assert fila["claim_amount"] is None
    assert fila["coverage_disputed"] is None
    assert fila["fraud_suspected"] is False


async def test_la_base_rechaza_un_monto_negativo(dos_aseguradoras: tuple[str, str]) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    mensaje = await _rechazo(propia, _fila(propia, caso, claim_amount=-1))

    assert "case_triage_note_monto_no_negativo" in mensaje


async def test_la_base_rechaza_una_anotacion_que_no_dice_quien_la_hizo(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    mensaje = await _rechazo(propia, _fila(propia, caso, noted_by=""))

    assert "case_triage_note_dice_quien" in mensaje
