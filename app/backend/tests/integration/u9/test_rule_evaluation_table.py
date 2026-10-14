"""La capa de datos de U9, contra PostgreSQL de verdad (CG-U9-4, BR4.1).

De integracion porque lo que se prueba es conducta del **motor**: las
politicas de fila, la llave compuesta y la cascada. Cubre NFR10.8 (aislamiento
por aseguradora), el hueco de llave que U10 tuvo que cerrar en una segunda
revision y que esta tabla no abre (UG-3), y el borrado con el caso (BR4.1).
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError

from untangle.case_record import purge as case_purge
from untangle.server import composition
from untangle.tenancy import purge, rls_assertion, session

from .conftest import AHORA, CasoSembrado, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u9")

TABLA = "rule_evaluation"

INSERTAR = """
    INSERT INTO rule_evaluation (evaluation_id, tenant_id, case_id, ruleset_version, category,
                                 fired_rules, inputs_snapshot, explanation_key, evaluated_at)
    VALUES (:evaluation_id, :tenant_id, :case_id, :ruleset_version, :category,
            CAST(:fired_rules AS jsonb), CAST(:inputs_snapshot AS jsonb),
            :explanation_key, :evaluated_at)
"""

LEER = "SELECT tenant_id, case_id FROM rule_evaluation"


def _fila(caso: CasoSembrado, **cambios: Any) -> dict[str, Any]:
    fila: dict[str, Any] = {
        "evaluation_id": f"{caso.case_id}-evaluacion",
        "tenant_id": caso.tenant_id,
        "case_id": caso.case_id,
        "ruleset_version": "v1",
        "category": "standard_review",
        "fired_rules": '[{"id": "R-DEFAULT", "version": 1, "touches_money": false}]',
        "inputs_snapshot": "{}",
        "explanation_key": "rules.explain.default",
        "evaluated_at": AHORA,
    }
    return fila | cambios


async def _escribir(tenant_id: str, fila: dict[str, Any]) -> None:
    async with session.session_for(tenant_id) as sesion:
        await session.execute_sql(sesion, INSERTAR, **fila)


async def _rechazo(tenant_id: str, fila: dict[str, Any]) -> str:
    with pytest.raises(IntegrityError) as rechazo:
        await _escribir(tenant_id, fila)
    return str(rechazo.value)


# --- Aislamiento (NFR10.8) -----------------------------------------------------


async def test_la_tabla_tiene_aislamiento_habilitado_forzado_y_con_politica() -> None:
    async with session.unscoped_session() as sesion:
        tablas = {t.table: t for t in await rls_assertion.read_tables(sesion)}

    assert TABLA in tablas
    assert tablas[TABLA].row_security
    assert tablas[TABLA].force_row_security
    assert tablas[TABLA].tenant_policies >= 1


async def test_cada_aseguradora_ve_solo_su_fila(dos_aseguradoras: tuple[str, str]) -> None:
    primera, segunda = dos_aseguradoras
    await _escribir(primera, _fila(await nuevo_caso(primera)))
    await _escribir(segunda, _fila(await nuevo_caso(segunda)))

    async with session.session_for(primera) as sesion:
        vistas_primera = [str(f["tenant_id"]) for f in await session.fetch_all(sesion, LEER)]
    async with session.session_for(segunda) as sesion:
        vistas_segunda = [str(f["tenant_id"]) for f in await session.fetch_all(sesion, LEER)]

    assert vistas_primera == [primera]
    assert vistas_segunda == [segunda]


async def test_escribir_con_la_aseguradora_de_otra_lo_rechaza_la_politica(
    dos_aseguradoras: tuple[str, str],
) -> None:
    primera, segunda = dos_aseguradoras
    caso = await nuevo_caso(primera)

    with pytest.raises(DBAPIError):
        await _escribir(primera, _fila(caso, tenant_id=segunda))


# --- Llave compuesta hacia el caso (UG-3, la leccion de U10) -------------------


async def test_una_fila_no_puede_apuntar_al_caso_de_otra_aseguradora(
    dos_aseguradoras: tuple[str, str],
) -> None:
    ajena, propia = dos_aseguradoras
    caso_ajeno = await nuevo_caso(ajena)
    caso_propio = await nuevo_caso(propia)

    # A lo suyo entra: descarta que el rechazo de abajo sea por otra restriccion.
    await _escribir(propia, _fila(caso_propio))

    mensaje = await _rechazo(
        propia, _fila(caso_propio, evaluation_id="otra", case_id=caso_ajeno.case_id)
    )

    assert "rule_evaluation_del_caso" in mensaje


# --- Borrado con el caso (BR4.1) ------------------------------------------------


async def test_borrar_el_caso_se_lleva_su_evaluacion_y_conserva_las_otras(
    dos_aseguradoras: tuple[str, str],
) -> None:
    primera, _ = dos_aseguradoras
    borrado = await nuevo_caso(primera)
    conservado = await nuevo_caso(primera)
    await _escribir(primera, _fila(borrado))
    await _escribir(primera, _fila(conservado))

    async with session.session_for(primera) as sesion:
        await session.execute_sql(
            sesion, "DELETE FROM case_record WHERE case_id = :case_id", case_id=borrado.case_id
        )
    async with session.session_for(primera) as sesion:
        restantes = [str(f["case_id"]) for f in await session.fetch_all(sesion, LEER)]

    assert restantes == [conservado.case_id]


async def test_la_tabla_lleva_la_marca_y_la_cubre_el_purgador_del_caso() -> None:
    marcadas = await purge.visitor_data_tables()

    assert TABLA in marcadas
    assert TABLA in case_purge.CASE_RECORD_PURGER.tables
    assert await purge.tables_without_purger(composition.PURGADORES) == frozenset()


# --- Las invariantes que la base impone --------------------------------------


@pytest.mark.parametrize(
    ("cambios", "restriccion"),
    [
        # BR2.4: fired_rules nunca esta vacia.
        ({"fired_rules": "[]"}, "rule_evaluation_reglas_disparadas_no_vacias"),
        # Categoria fuera de las tres cerradas (BR2.2).
        ({"category": "closed"}, "rule_evaluation_categoria_valida"),
        # Texto libre donde va una clave del catalogo (BR2.5).
        ({"explanation_key": "esta cubierto"}, "rule_evaluation_clave_con_forma"),
    ],
)
async def test_la_base_rechaza_una_evaluacion_que_rompe_una_invariante(
    dos_aseguradoras: tuple[str, str], cambios: dict[str, Any], restriccion: str
) -> None:
    primera, _ = dos_aseguradoras
    caso = await nuevo_caso(primera)

    mensaje = await _rechazo(primera, _fila(caso, **cambios))

    assert restriccion in mensaje
