"""La capa de datos de U10, contra PostgreSQL de verdad (paso 6 del plan).

Son de integracion porque lo que se prueba es conducta del **motor**: las
politicas de fila, las restricciones y la cascada, y lo que el catalogo dice de
cada columna. Una base simulada comprobaria el simulador.

La conexion es la del rol del aplicativo, que no puede saltarse las politicas
(`tests/conftest.py`): con el superusuario, las pruebas de aislamiento quedarian
verdes midiendo nada.

Cubre NFR10.6 (aislamiento forzado, con politica y con su prueba por tabla),
NFR11.8 (ninguna columna de texto libre ni de dato personal), NFR19.4 (nada
sobrevive al borrado del caso), las dos unicidades de BR4.2 y BR6.3, y las
invariantes que la base impone por debajo de los tipos.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError

from untangle.case_record import purge as case_purge
from untangle.server import composition
from untangle.tenancy import purge, rls_assertion, session

from .conftest import AHORA, CasoSembrado, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u10")

TABLAS = ("disclosure_record", "guard_intervention", "compliance_review")

INSERTAR_DIVULGACION = """
    INSERT INTO disclosure_record (disclosure_id, tenant_id, case_id, channel, language,
                                   catalog_key, disclosed_at)
    VALUES (:disclosure_id, :tenant_id, :case_id, :channel, :language,
            :catalog_key, :disclosed_at)
"""

INSERTAR_INTERVENCION = """
    INSERT INTO guard_intervention (intervention_id, tenant_id, case_id, turn_id, category,
                                    pattern_id, action, catalog_key, occurred_at)
    VALUES (:intervention_id, :tenant_id, :case_id, :turn_id, :category,
            :pattern_id, :action, :catalog_key, :occurred_at)
"""

INSERTAR_REVISION = """
    INSERT INTO compliance_review (review_id, tenant_id, case_id, disclosure_ok,
                                   human_route_ok, pii_ok, explainability_ok, findings,
                                   reviewed_through_turn, reviewed_at)
    VALUES (:review_id, :tenant_id, :case_id, :disclosure_ok,
            :human_route_ok, :pii_ok, :explainability_ok, CAST(:findings AS varchar[]),
            :reviewed_through_turn, :reviewed_at)
"""

#: Las tres lecturas, escritas enteras: componer el nombre de la tabla con una
#: cadena seria SQL armado por concatenacion (BR1.6 de U2).
LEER = {
    "disclosure_record": "SELECT tenant_id, case_id FROM disclosure_record",
    "guard_intervention": "SELECT tenant_id, case_id FROM guard_intervention",
    "compliance_review": "SELECT tenant_id, case_id FROM compliance_review",
}


def _divulgacion(caso: CasoSembrado, **cambios: Any) -> dict[str, Any]:
    fila: dict[str, Any] = {
        "disclosure_id": f"{caso.case_id}-divulgacion",
        "tenant_id": caso.tenant_id,
        "case_id": caso.case_id,
        "channel": "chat",
        "language": "es",
        "catalog_key": "compliance.disclosure.opening",
        "disclosed_at": AHORA,
    }
    return fila | cambios


def _intervencion(caso: CasoSembrado, **cambios: Any) -> dict[str, Any]:
    fila: dict[str, Any] = {
        "intervention_id": f"{caso.case_id}-intervencion",
        "tenant_id": caso.tenant_id,
        "case_id": caso.case_id,
        "turn_id": caso.turn_ids[-1],
        "category": "coverage_promise",
        "pattern_id": "guard.es.coverage_promise.001",
        "action": "substituted",
        "catalog_key": "compliance.guard.coverage_promise",
        "occurred_at": AHORA,
    }
    return fila | cambios


def _revision(caso: CasoSembrado, **cambios: Any) -> dict[str, Any]:
    fila: dict[str, Any] = {
        "review_id": f"{caso.case_id}-revision",
        "tenant_id": caso.tenant_id,
        "case_id": caso.case_id,
        "disclosure_ok": True,
        "human_route_ok": True,
        "pii_ok": True,
        "explainability_ok": True,
        "findings": [],
        "reviewed_through_turn": caso.turn_ids[-1],
        "reviewed_at": AHORA,
    }
    return fila | cambios


async def _sembrar_las_tres(caso: CasoSembrado) -> None:
    async with session.session_for(caso.tenant_id) as sesion:
        await session.execute_sql(sesion, INSERTAR_DIVULGACION, **_divulgacion(caso))
        await session.execute_sql(sesion, INSERTAR_INTERVENCION, **_intervencion(caso))
        await session.execute_sql(sesion, INSERTAR_REVISION, **_revision(caso))


async def _contar(tenant_id: str) -> dict[str, list[str]]:
    """Que ve una aseguradora en cada tabla: la aseguradora de cada fila."""
    vistas: dict[str, list[str]] = {}
    async with session.session_for(tenant_id) as sesion:
        for tabla, consulta in LEER.items():
            filas = await session.fetch_all(sesion, consulta)
            vistas[tabla] = [str(fila["tenant_id"]) for fila in filas]
    return vistas


async def _rechazo(tenant_id: str, sentencia: str, fila: dict[str, Any]) -> str:
    """Intenta escribir una fila y devuelve el mensaje del rechazo de la base."""
    with pytest.raises(IntegrityError) as rechazo:
        async with session.session_for(tenant_id) as sesion:
            await session.execute_sql(sesion, sentencia, **fila)
    return str(rechazo.value)


# --- Aislamiento (NFR10.6) ----------------------------------------------------


async def test_las_tres_tablas_tienen_aislamiento_habilitado_forzado_y_con_politica() -> None:
    """Preguntado al catalogo vivo, no leido de la migracion."""
    async with session.unscoped_session() as sesion:
        tablas = {t.table: t for t in await rls_assertion.read_tables(sesion)}

    for nombre in TABLAS:
        assert nombre in tablas, f"la tabla {nombre} no existe en el esquema"
        tabla = tablas[nombre]
        assert tabla.row_security, f"{nombre}: aislamiento no habilitado"
        assert tabla.force_row_security, f"{nombre}: aislamiento no forzado"
        assert tabla.tenant_policies >= 1, f"{nombre}: sin politica de aseguradora"


async def test_cada_aseguradora_ve_solo_sus_filas_en_las_tres_tablas(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Las dos aseguradoras escriben en las tres tablas; cada una ve solo lo suyo.

    Con filas de las dos en cada tabla la prueba no pasa por casualidad: sin
    aislamiento, cada una veria dos filas por tabla y no una.
    """
    primera, segunda = dos_aseguradoras
    await _sembrar_las_tres(await nuevo_caso(primera))
    await _sembrar_las_tres(await nuevo_caso(segunda))

    vistas_por_la_primera = await _contar(primera)
    vistas_por_la_segunda = await _contar(segunda)

    assert vistas_por_la_primera == {tabla: [primera] for tabla in TABLAS}
    assert vistas_por_la_segunda == {tabla: [segunda] for tabla in TABLAS}


async def test_escribir_una_fila_de_otra_aseguradora_lo_rechaza_la_politica(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La mitad de escritura de la politica (`WITH CHECK`): no solo no se ve."""
    primera, segunda = dos_aseguradoras
    caso = await nuevo_caso(primera)

    with pytest.raises(DBAPIError):
        async with session.session_for(primera) as sesion:
            await session.execute_sql(
                sesion, INSERTAR_DIVULGACION, **_divulgacion(caso, tenant_id=segunda)
            )


# --- Sin texto libre (NFR11.8, BR8.2) -----------------------------------------


async def test_ninguna_columna_es_texto_libre_ni_nombra_un_dato_personal() -> None:
    """Contra el catalogo vivo, con la lista versionada que ya usan U5 y U6.

    Se comprueban las dos cosas que se miraron: que columnas hay --una consulta
    rota que no devolviera ninguna pasaria en verde-- y que ninguna falla.
    """
    nombres = rls_assertion.personal_data_names()
    assert nombres, "la lista versionada de nombres de dato personal esta vacia"

    async with session.unscoped_session() as sesion:
        columnas = await rls_assertion.read_columns(sesion, list(TABLAS))

    assert {(c.table, c.column) for c in columnas} == {
        ("disclosure_record", "disclosure_id"),
        ("disclosure_record", "tenant_id"),
        ("disclosure_record", "case_id"),
        ("disclosure_record", "channel"),
        ("disclosure_record", "language"),
        ("disclosure_record", "catalog_key"),
        ("disclosure_record", "disclosed_at"),
        ("guard_intervention", "intervention_id"),
        ("guard_intervention", "tenant_id"),
        ("guard_intervention", "case_id"),
        ("guard_intervention", "turn_id"),
        ("guard_intervention", "category"),
        ("guard_intervention", "pattern_id"),
        ("guard_intervention", "action"),
        ("guard_intervention", "catalog_key"),
        ("guard_intervention", "occurred_at"),
        ("compliance_review", "review_id"),
        ("compliance_review", "tenant_id"),
        ("compliance_review", "case_id"),
        ("compliance_review", "disclosure_ok"),
        ("compliance_review", "human_route_ok"),
        ("compliance_review", "pii_ok"),
        ("compliance_review", "explainability_ok"),
        ("compliance_review", "findings"),
        ("compliance_review", "reviewed_through_turn"),
        ("compliance_review", "reviewed_at"),
    }
    fallos = [f for c in columnas if (f := rls_assertion.check_column(c, nombres)) is not None]
    assert fallos == []


# --- Unicidad (BR4.2, BR6.3) --------------------------------------------------


async def test_la_divulgacion_es_una_por_caso_y_canal(dos_aseguradoras: tuple[str, str]) -> None:
    """El segundo registro del mismo canal choca; el otro canal si entra.

    Un caso de voz retomado por chat lleva dos divulgaciones, y eso no es un
    duplicado: la unicidad es por canal, no por caso.
    """
    primera, _ = dos_aseguradoras
    caso = await nuevo_caso(primera)
    async with session.session_for(primera) as sesion:
        await session.execute_sql(sesion, INSERTAR_DIVULGACION, **_divulgacion(caso))
        await session.execute_sql(
            sesion,
            INSERTAR_DIVULGACION,
            **_divulgacion(caso, disclosure_id=f"{caso.case_id}-voz", channel="voice"),
        )

    mensaje = await _rechazo(
        primera,
        INSERTAR_DIVULGACION,
        _divulgacion(caso, disclosure_id=f"{caso.case_id}-otra"),
    )

    assert "disclosure_record_una_por_canal" in mensaje


async def test_la_revision_es_una_por_caso_y_turno_revisado(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Repetir la revision del mismo punto choca; revisar un turno posterior no."""
    primera, _ = dos_aseguradoras
    caso = await nuevo_caso(primera, turnos=3)
    async with session.session_for(primera) as sesion:
        await session.execute_sql(
            sesion, INSERTAR_REVISION, **_revision(caso, reviewed_through_turn=caso.turn_ids[1])
        )
        await session.execute_sql(
            sesion,
            INSERTAR_REVISION,
            **_revision(
                caso, review_id=f"{caso.case_id}-final", reviewed_through_turn=caso.turn_ids[2]
            ),
        )

    mensaje = await _rechazo(
        primera,
        INSERTAR_REVISION,
        _revision(caso, review_id=f"{caso.case_id}-otra", reviewed_through_turn=caso.turn_ids[1]),
    )

    assert "compliance_review_una_por_turno" in mensaje


# --- Borrado con el caso (NFR19.4, BR8.1) -------------------------------------


async def test_borrar_el_caso_se_lleva_las_filas_de_las_tres_tablas(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Cero filas sobreviven a su caso, y las del otro caso siguen ahi.

    El segundo caso es la mitad que se olvida: una cascada mal escrita que
    borrara de mas tambien dejaria cero filas del primero.
    """
    primera, _ = dos_aseguradoras
    borrado = await nuevo_caso(primera)
    conservado = await nuevo_caso(primera)
    await _sembrar_las_tres(borrado)
    await _sembrar_las_tres(conservado)

    async with session.session_for(primera) as sesion:
        await session.execute_sql(
            sesion, "DELETE FROM case_record WHERE case_id = :case_id", case_id=borrado.case_id
        )
    async with session.session_for(primera) as sesion:
        restantes = {
            tabla: [str(f["case_id"]) for f in await session.fetch_all(sesion, consulta)]
            for tabla, consulta in LEER.items()
        }

    assert restantes == {tabla: [conservado.case_id] for tabla in TABLAS}


async def test_las_tres_llevan_la_marca_y_las_cubre_el_purgador_del_caso() -> None:
    """La marca decide que entra al borrado nocturno, y nadie queda sin dueno (C-11)."""
    marcadas = await purge.visitor_data_tables()

    assert set(TABLAS) <= marcadas
    assert set(TABLAS) <= set(case_purge.CASE_RECORD_PURGER.tables)
    assert await purge.tables_without_purger(composition.PURGADORES) == frozenset()


# --- Las invariantes, impuestas por la base -----------------------------------


@pytest.mark.parametrize(
    ("cambios", "restriccion"),
    [
        # BR1.4: la frase descartada no deja salir ninguna clave.
        ({"action": "dropped"}, "guard_intervention_clave_salvo_descartada"),
        # BR1.5: sin evaluacion no hay categoria.
        (
            {"action": "not_evaluable", "catalog_key": "compliance.guard.degraded"},
            "guard_intervention_categoria_si_se_evaluo",
        ),
        # BR1.6: el patron va con su categoria.
        ({"pattern_id": None}, "guard_intervention_patron_con_su_categoria"),
        # BR1.2: una categoria que no es de las siete.
        ({"category": "insult"}, "guard_intervention_categoria_valida"),
        # BR8.2: texto libre donde va una clave del catalogo.
        (
            {"catalog_key": "Si, esta cubierto por completo"},
            "guard_intervention_clave_con_forma",
        ),
    ],
)
async def test_la_base_rechaza_una_intervencion_que_rompe_una_invariante(
    dos_aseguradoras: tuple[str, str], cambios: dict[str, Any], restriccion: str
) -> None:
    primera, _ = dos_aseguradoras
    caso = await nuevo_caso(primera)

    mensaje = await _rechazo(primera, INSERTAR_INTERVENCION, _intervencion(caso, **cambios))

    assert restriccion in mensaje


@pytest.mark.parametrize(
    ("cambios", "restriccion"),
    [
        # BR5.1: un control en falso sin su codigo.
        ({"pii_ok": False}, "compliance_review_datos_personales_concuerda"),
        # BR5.1: un codigo con su control en verdadero.
        ({"findings": ["disclosure_missing"]}, "compliance_review_divulgacion_concuerda"),
        # BR8.2: un hallazgo fuera de la lista cerrada.
        (
            {"explainability_ok": False, "findings": ["attachment_missing", "otra_cosa"]},
            "compliance_review_hallazgos_validos",
        ),
    ],
)
async def test_la_base_rechaza_una_revision_cuyos_controles_no_concuerdan(
    dos_aseguradoras: tuple[str, str], cambios: dict[str, Any], restriccion: str
) -> None:
    primera, _ = dos_aseguradoras
    caso = await nuevo_caso(primera)

    mensaje = await _rechazo(primera, INSERTAR_REVISION, _revision(caso, **cambios))

    assert restriccion in mensaje
