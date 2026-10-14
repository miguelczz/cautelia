"""El aislamiento entre aseguradoras, contra PostgreSQL de verdad (AC4.11.3).

Son de integracion porque lo que se prueba es una conducta del **motor** --las
politicas de fila-- y un doble no la tiene. Una prueba de aislamiento contra una
base simulada comprueba el simulador.

Las filas vienen de DS-8, con colisiones a proposito: el mismo identificador de
caso y la misma clave de navegador en dos aseguradoras. Con datos distintos,
estas pruebas pasarian aunque el aislamiento no existiera.

La conexion es la del **rol del aplicativo**, que no puede saltarse las
politicas. Con el superusuario, todo esto quedaria verde midiendo nada.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from untangle.tenancy import ephemeral, session
from untangle.tenancy.models import UnknownTenantError

TODOS_LOS_ENLACES = "SELECT link_id, tenant_id, case_id FROM case_access_link"
TODAS_LAS_CLAVES = "SELECT tenant_id, visitor_key_hash FROM visitor_key"


async def test_una_consulta_sin_filtro_devuelve_solo_lo_de_su_aseguradora(
    ds8: dict[str, Any],
) -> None:
    """BR1.3: el filtro olvidado en el codigo no puede convertirse en una fuga."""
    async with session.session_for("stonecroft") as sesion:
        filas = await session.fetch_all(sesion, TODOS_LOS_ENLACES)

    assert filas, "la siembra de DS-8 no dejo ninguna fila que consultar"
    assert {fila["tenant_id"] for fila in filas} == {"stonecroft"}


async def test_la_colision_de_caso_de_ds8_no_cruza_aseguradoras(ds8: dict[str, Any]) -> None:
    """El mismo `case_id` en dos aseguradoras; cada una ve solo su enlace."""
    caso_compartido = "CASE-7F3A21"

    async with session.session_for("stonecroft") as sesion:
        de_stonecroft = await session.fetch_all(
            sesion,
            "SELECT link_id FROM case_access_link WHERE case_id = :case_id",
            case_id=caso_compartido,
        )
    async with session.session_for("sunmeadow") as sesion:
        de_sunmeadow = await session.fetch_all(
            sesion,
            "SELECT link_id FROM case_access_link WHERE case_id = :case_id",
            case_id=caso_compartido,
        )

    assert [fila["link_id"] for fila in de_stonecroft] == ["LNK-DS8-0001"]
    assert [fila["link_id"] for fila in de_sunmeadow] == ["LNK-DS8-0002"]


async def test_sin_aseguradora_fijada_la_consulta_devuelve_cero_filas(
    ds8: dict[str, Any],
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR1.4: falla cerrado, nunca abierto.

    Esta es la unica prueba que abre una conexion fuera del punto unico, y lo
    hace a proposito: lo que comprueba es que la **politica** no ve nada cuando
    la variable de sesion nunca se fijo, y el punto unico siempre la fija. Es una
    sonda sobre el motor, no una segunda via de acceso del aplicativo.
    """
    motor = create_async_engine(sesiones.app_url)
    try:
        async with motor.connect() as conexion:
            resultado = await conexion.execute(text(TODOS_LOS_ENLACES))
            filas = resultado.mappings().all()
    finally:
        await motor.dispose()

    assert list(filas) == []


async def test_una_aseguradora_inexistente_falla_antes_de_abrir_transaccion() -> None:
    """BR1.5: un error del codigo no se disfraza de "no hay datos".

    El punto unico apunta a una base inalcanzable a proposito. Si resolviera la
    aseguradora **despues** de conectar, lo que veriamos seria un error de
    conexion; lo que exige la regla es que falle antes, nombrando el
    identificador.
    """
    session.configure("postgresql+psycopg://nadie:nadie@127.0.0.1:1/ninguna")
    try:
        with pytest.raises(UnknownTenantError) as fallo:
            async with session.session_for("acme-seguros"):
                pass
    finally:
        await session.dispose()

    assert "acme-seguros" in str(fallo.value)


async def test_la_misma_clave_de_navegador_tiene_una_fila_por_aseguradora(
    ds8: dict[str, Any],
) -> None:
    """BR3.5: el mismo navegador en dos demostraciones, y ninguna ve la otra."""
    compartida = "6f4b2c1d9a8e7350c2b1a0f9e8d7c6b5a4938271605f4e3d2c1b0a9f8e7d6c5b"

    vistas: dict[str, list[str]] = {}
    for tenant_id in ("stonecroft", "sunmeadow", "knotwell"):
        async with session.session_for(tenant_id) as sesion:
            filas = await session.fetch_all(sesion, TODAS_LAS_CLAVES)
        vistas[tenant_id] = [str(fila["visitor_key_hash"]) for fila in filas]

    assert vistas["stonecroft"] == [compartida]
    assert vistas["sunmeadow"] == [compartida]
    assert compartida not in vistas["knotwell"]


async def test_no_se_puede_escribir_una_fila_de_otra_aseguradora(ds8: dict[str, Any]) -> None:
    """La politica tambien vigila la escritura: sin `WITH CHECK` el aislamiento
    seria de solo lectura y cualquiera podria sembrar filas en la aseguradora de
    al lado."""
    async with session.session_for("stonecroft") as sesion:
        with pytest.raises(DBAPIError):
            await session.execute_sql(
                sesion,
                """
                INSERT INTO visitor_key (
                    tenant_id, visitor_key_hash, origin, created_at, last_seen_at
                ) VALUES (
                    'sunmeadow', :hash, 'https://demo.untangle.local', now(), now()
                )
                """,
                hash="0" * 64,
            )


async def test_el_rol_de_la_conexion_no_puede_saltarse_las_politicas(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR1.7: se le pregunta al motor por el rol **vivo**, no a la migracion.

    Leer como se creo el rol no prueba nada: lo que importa es con que rol esta
    conectada esta suite ahora mismo.
    """
    async with session.session_for("stonecroft") as sesion:
        filas = await session.fetch_all(
            sesion,
            "SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user",
        )

    assert len(filas) == 1
    assert filas[0]["rolbypassrls"] is False
    assert filas[0]["rolsuper"] is False
