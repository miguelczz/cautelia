"""La capa de datos de la activacion, contra PostgreSQL de verdad (paso 4 de U6).

Son de integracion porque lo que se prueba es conducta del **motor**: las
politicas de fila, las restricciones de unicidad y lo que el catalogo dice de
cada columna. Una base simulada comprobaria el simulador.

La conexion es la del rol del aplicativo, que no puede saltarse las politicas
(`tests/conftest.py`). Con el superusuario, las pruebas de aislamiento quedarian
verdes midiendo nada.

Cubre NFR10.5 (aislamiento forzado, con politica y con su prueba por tabla),
NFR11.7 (ninguna columna de texto libre ni de dato personal, contra el catalogo
vivo y la lista versionada) y las dos restricciones de unicidad de BR8.1.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError

from untangle.tenancy import purge, rls_assertion, session

from .conftest import AHORA, nueva_sesion

pytestmark = pytest.mark.usefixtures("activacion")

TABLAS = ("activation_progress", "activation_daily")

INSERTAR_AVANCE = """
    INSERT INTO activation_progress (tenant_id, visitor_key_hash, milestone, reached_at)
    VALUES (:tenant_id, :visitor_key_hash, :milestone, :reached_at)
"""

INSERTAR_CONTEO = """
    INSERT INTO activation_daily (tenant_id, day, milestone, count)
    VALUES (:tenant_id, :day, :milestone, :count)
"""

TODO_EL_AVANCE = "SELECT tenant_id, visitor_key_hash, milestone FROM activation_progress"
TODO_EL_CONTEO = "SELECT tenant_id, day, milestone, count FROM activation_daily"

DIA = date(2026, 9, 21)


async def test_las_dos_tablas_tienen_aislamiento_habilitado_forzado_y_con_politica() -> None:
    """NFR10.5, preguntado al catalogo vivo y no leido de la migracion."""
    async with session.unscoped_session() as sesion:
        tablas = {t.table: t for t in await rls_assertion.read_tables(sesion)}

    for nombre in TABLAS:
        assert nombre in tablas, f"la tabla {nombre} no existe en el esquema"
        tabla = tablas[nombre]
        assert tabla.row_security, f"{nombre}: aislamiento no habilitado"
        assert tabla.force_row_security, f"{nombre}: aislamiento no forzado"
        assert tabla.tenant_policies >= 1, f"{nombre}: sin politica de aseguradora"


async def test_el_avance_de_una_aseguradora_no_se_ve_desde_otra_aunque_la_clave_coincida(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La misma clave de navegador en dos aseguradoras: cada una ve solo lo suyo.

    La colision es a proposito. Con claves distintas esta prueba pasaria aunque
    el aislamiento no existiera, porque ninguna consulta encontraria la fila
    ajena por otro camino.
    """
    primera, segunda = dos_aseguradoras
    clave_compartida = "clave-compartida-de-prueba-u6"
    de_la_primera = await nueva_sesion(primera, visitor_key=clave_compartida)
    de_la_segunda = await nueva_sesion(segunda, visitor_key=clave_compartida)
    assert de_la_primera.visitor_key_hash == de_la_segunda.visitor_key_hash

    async with session.session_for(primera) as sesion:
        await session.execute_sql(
            sesion,
            INSERTAR_AVANCE,
            tenant_id=primera,
            visitor_key_hash=de_la_primera.visitor_key_hash,
            milestone="first_message",
            reached_at=AHORA,
        )

    async with session.session_for(segunda) as sesion:
        vistas_por_la_segunda = await session.fetch_all(sesion, TODO_EL_AVANCE)
    async with session.session_for(primera) as sesion:
        vistas_por_la_primera = await session.fetch_all(sesion, TODO_EL_AVANCE)

    assert vistas_por_la_segunda == ()
    assert [fila["tenant_id"] for fila in vistas_por_la_primera] == [primera]


async def test_el_conteo_diario_de_una_aseguradora_no_se_ve_desde_otra(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """El mismo dia y el mismo hito en dos aseguradoras: dos filas que no se cruzan."""
    primera, segunda = dos_aseguradoras
    for tenant_id, conteo in ((primera, 3), (segunda, 7)):
        async with session.session_for(tenant_id) as sesion:
            await session.execute_sql(
                sesion,
                INSERTAR_CONTEO,
                tenant_id=tenant_id,
                day=DIA,
                milestone="third_turn",
                count=conteo,
            )

    async with session.session_for(primera) as sesion:
        de_la_primera = await session.fetch_all(sesion, TODO_EL_CONTEO)
    async with session.session_for(segunda) as sesion:
        de_la_segunda = await session.fetch_all(sesion, TODO_EL_CONTEO)

    assert [(f["tenant_id"], f["count"]) for f in de_la_primera] == [(primera, 3)]
    assert [(f["tenant_id"], f["count"]) for f in de_la_segunda] == [(segunda, 7)]


async def test_escribir_el_conteo_de_otra_aseguradora_lo_rechaza_la_politica(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La mitad de escritura de la politica (`WITH CHECK`): no solo no se ve, no se escribe."""
    primera, segunda = dos_aseguradoras

    with pytest.raises(DBAPIError):
        async with session.session_for(primera) as sesion:
            await session.execute_sql(
                sesion,
                INSERTAR_CONTEO,
                tenant_id=segunda,
                day=DIA,
                milestone="loop_closed",
                count=1,
            )


async def test_ninguna_columna_es_texto_libre_ni_nombra_un_dato_personal() -> None:
    """NFR11.7 contra el catalogo vivo, con la lista versionada que ya usa U5.

    Se comprueban **las dos** cosas que se miraron: que columnas hay --una
    consulta rota que no devolviera ninguna pasaria la comprobacion en verde-- y
    que ninguna falla.
    """
    nombres = rls_assertion.personal_data_names()
    assert nombres, "la lista versionada de nombres de dato personal esta vacia"

    async with session.unscoped_session() as sesion:
        columnas = await rls_assertion.read_columns(sesion, list(TABLAS))

    miradas = {(c.table, c.column) for c in columnas}
    assert miradas == {
        ("activation_progress", "tenant_id"),
        ("activation_progress", "visitor_key_hash"),
        ("activation_progress", "milestone"),
        ("activation_progress", "reached_at"),
        ("activation_daily", "tenant_id"),
        ("activation_daily", "day"),
        ("activation_daily", "milestone"),
        ("activation_daily", "count"),
    }
    fallos = [f for c in columnas if (f := rls_assertion.check_column(c, nombres)) is not None]
    assert fallos == []


async def test_el_mismo_hito_en_la_misma_sesion_choca_con_la_unicidad(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR8.1 empieza aqui: el segundo registro del mismo hito no puede entrar."""
    primera, _ = dos_aseguradoras
    visita = await nueva_sesion(primera)
    fila = {
        "tenant_id": primera,
        "visitor_key_hash": visita.visitor_key_hash,
        "milestone": "third_turn",
        "reached_at": AHORA,
    }
    async with session.session_for(primera) as sesion:
        await session.execute_sql(sesion, INSERTAR_AVANCE, **fila)

    with pytest.raises(IntegrityError):
        async with session.session_for(primera) as sesion:
            await session.execute_sql(sesion, INSERTAR_AVANCE, **fila)


async def test_el_conteo_es_unico_por_aseguradora_dia_e_hito(
    dos_aseguradoras: tuple[str, str],
) -> None:
    primera, _ = dos_aseguradoras
    fila = {"tenant_id": primera, "day": DIA, "milestone": "first_message", "count": 1}
    async with session.session_for(primera) as sesion:
        await session.execute_sql(sesion, INSERTAR_CONTEO, **fila)

    with pytest.raises(IntegrityError):
        async with session.session_for(primera) as sesion:
            await session.execute_sql(sesion, INSERTAR_CONTEO, **fila)


INSERTAR_CLAVE_A_MANO = """
    INSERT INTO visitor_key (tenant_id, visitor_key_hash, origin, created_at, last_seen_at)
    VALUES (:tenant_id, :visitor_key_hash, 'public_chat', :ahora, :ahora)
"""


async def _intentar_avance(tenant_id: str, visitor_key_hash: str, milestone: str) -> str:
    """Intenta escribir un avance y devuelve el mensaje del rechazo de la base."""
    with pytest.raises(IntegrityError) as rechazo:
        async with session.session_for(tenant_id) as sesion:
            await session.execute_sql(
                sesion,
                INSERTAR_AVANCE,
                tenant_id=tenant_id,
                visitor_key_hash=visitor_key_hash,
                milestone=milestone,
                reached_at=AHORA,
            )
    return str(rechazo.value)


async def test_un_hito_fuera_de_los_tres_lo_rechaza_la_base(
    dos_aseguradoras: tuple[str, str],
) -> None:
    primera, _ = dos_aseguradoras
    visita = await nueva_sesion(primera)

    mensaje = await _intentar_avance(primera, visita.visitor_key_hash, "second_turn")

    assert "activation_progress_hito_valido" in mensaje


async def test_una_clave_sin_resumir_se_rechaza_aunque_exista_como_clave(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La forma del resumen la impone la tabla, no la buena fe de quien escribe.

    La clave se siembra a mano en la tabla de U2 --que no restringe la forma--
    para que la referencia se cumpla y lo unico que falle sea la forma. Sin eso,
    la referencia rechazaria la fila antes y esta prueba no distinguiria cual de
    las dos restricciones existe.
    """
    primera, _ = dos_aseguradoras
    sin_resumir = "clave-en-claro"
    async with session.session_for(primera) as sesion:
        await session.execute_sql(
            sesion,
            INSERTAR_CLAVE_A_MANO,
            tenant_id=primera,
            visitor_key_hash=sin_resumir,
            ahora=AHORA,
        )

    mensaje = await _intentar_avance(primera, sin_resumir, "first_message")

    assert "activation_progress_resumen_de_clave" in mensaje


async def test_un_resumen_que_no_es_una_clave_de_esa_aseguradora_no_cuenta(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La sesion es una clave que U2 reconocio en **esa** aseguradora (FD-U6-3).

    Una clave de otra aseguradora tiene la forma correcta y aun asi no sirve: un
    resumen inventado, o uno ajeno, no puede contar como una sesion propia.
    """
    primera, segunda = dos_aseguradoras
    ajena = await nueva_sesion(segunda)

    mensaje = await _intentar_avance(primera, ajena.visitor_key_hash, "first_message")

    assert "activation_progress_de_su_clave" in mensaje


async def test_solo_el_avance_lleva_la_marca_de_dato_de_visitante() -> None:
    """BR8.2: la marca decide que entra al borrado nocturno; el conteo no la lleva."""
    marcadas = await purge.visitor_data_tables()

    assert "activation_progress" in marcadas
    assert "activation_daily" not in marcadas
