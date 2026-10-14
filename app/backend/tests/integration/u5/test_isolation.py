"""Lo que paga que tres tablas salgan del aislamiento (BR7.1, BR7.2).

Tres tablas de U5 no llevan aseguradora y no tienen politica que las filtre. A
cambio aceptan una prohibicion mas fuerte y **comprobable**: ahi dentro no hay
nada personal que aislar. Este archivo comprueba las dos mitades de esa decision
contra el catalogo vivo, no contra el archivo de migracion.

La cuarta tabla, el resumen de traza, si es dato de un visitante y se comporta
como cualquier otra: lleva su politica, y un navegador de otra aseguradora no la
ve.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from untangle.tenancy import ephemeral, purge, rls_assertion, session
from untangle.tenancy.models import ExcludedTable

AHORA = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)

#: Las cuatro tablas que salen del aislamiento porque son dato del proyecto, no
#: de una aseguradora. La cuarta --la marca de cierre de una llamada-- entro con
#: la devolucion del cupo (BR5.5) y faltaba aqui: la lista estaba escrita a mano
#: y una lista a mano se queda corta cada vez que nace una tabla, que es
#: exactamente el modo de fallo contra el que existe `rls:check`. Esa compuerta
#: si la cubria, porque le pregunta al catalogo vivo; esta prueba comprueba otra
#: cosa --los nombres de dato personal-- y por eso la omision no se veia.
DEL_DINERO = ("spend_entry", "quota_counter", "budget_window", "voice_call_release")

CREAR_CASO = """
    INSERT INTO case_record (case_id, tenant_id, case_number, record_type,
                             state, channel, origin, language, created_at, updated_at)
    VALUES (:case_id, :tenant_id, :numero, 'claim', 'capturing', 'chat',
            'public_chat', 'es', :ahora, :ahora)
"""

CREAR_RESUMEN = """
    INSERT INTO trace_summary (trace_id, tenant_id, case_id, visitor_key_hash,
                               nodes, created_at)
    VALUES (:trace_id, :tenant_id, :case_id, :navegador,
            CAST('[]' AS jsonb), :ahora)
"""


@pytest.fixture
async def tabla_excluida_con_dato_personal(
    sesiones: ephemeral.EphemeralDatabase,
) -> AsyncIterator[str]:
    """Una tabla de prueba excluida del aislamiento, con una columna que no puede.

    Se crea de verdad y se le pregunta al catalogo, en vez de inventar la
    respuesta: lo que esta prueba defiende es que la **consulta** encuentre la
    columna, y una lista escrita a mano pasaria igual con una consulta rota.

    Lleva **las dos violaciones de BR7.2** a la vez, porque son dos motivos
    independientes: `visitor_email` tiene longitud acotada y falla por su
    nombre; `nota` tiene un nombre inocente y falla por ser texto sin tope. Una
    tabla con una sola de las dos dejaria la otra comprobacion sin ejercer.
    """
    nombre = "prueba_excluida"
    async with session.unscoped_session() as sesion:
        await session.execute_sql(
            sesion,
            "CREATE TABLE prueba_excluida ("
            "  id varchar(32) PRIMARY KEY,"
            "  visitor_email varchar(120),"
            "  nota text"
            ")",
        )
    yield nombre
    async with session.unscoped_session() as sesion:
        await session.execute_sql(sesion, "DROP TABLE prueba_excluida")


# --- La mitad que se pierde: el aislamiento -----------------------------------


async def test_la_asercion_de_aislamiento_pasa_con_las_tres_exclusiones_escritas(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Las tres estan en la lista versionada, asi que la compuerta sigue verde.

    Si faltara una, la asercion la nombraria por no tener politica: es lo que
    hace que sacar una tabla del aislamiento tenga que decidirse a la vista, en
    el manifiesto, y no se pueda hacer por descuido.
    """
    informe = await rls_assertion.assert_rls_complete()

    assert informe.ok, informe.lines()
    excluidas = {entrada.table for entrada in informe.excluded_tables}
    assert set(DEL_DINERO) <= excluidas
    # Y la que si es dato de visitante esta del otro lado, revisada como todas.
    assert "trace_summary" in informe.checked_tables


async def test_cada_exclusion_del_dinero_trae_su_razon_escrita(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Una exclusion sin razon no se puede revisar: solo se puede heredar."""
    por_tabla = {entrada.table: entrada.reason for entrada in rls_assertion.excluded_tables()}

    for tabla in DEL_DINERO:
        assert tabla in por_tabla, f"'{tabla}' no esta en la lista de exclusion versionada"
        assert "proyecto" in por_tabla[tabla].lower()


# --- La mitad que se paga: las columnas ---------------------------------------


async def test_la_asercion_mira_de_verdad_las_columnas_de_las_tablas_excluidas(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Una tabla excluida de la que no se miro ninguna columna esta saltada.

    Sin este conteo, esa tabla y una comprobada entera se ven igual en verde, que
    es exactamente la forma en la que un control deja de existir sin que nadie lo
    note.
    """
    informe = await rls_assertion.assert_rls_complete()

    por_tabla = {columna.split(".", 1)[0] for columna in informe.checked_columns}
    assert set(DEL_DINERO) <= por_tabla
    # Diecisiete columnas del libro mayor, siete del contador y once de la
    # ventana, mas la del control de migraciones: la cifra exacta cambia con cada
    # unidad, asi que lo que se exige es que ninguna de las tres quede sin mirar.
    assert len(informe.checked_columns) > len(DEL_DINERO)


async def test_el_conteo_por_carril_de_la_ventana_paga_lo_que_su_exclusion_cobra(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """La columna nueva de `budget_window`, con su prueba de aislamiento.

    `unmeasured_recording_calls` nacio el 2026-09-21 en una tabla que **no**
    lleva politica de aseguradora, y una tabla excluida no paga su exclusion de
    una vez y para siempre: la paga columna a columna, cada vez que nace una. Lo
    que se comprueba es lo que BR7.2 cobra --ni nombre de dato personal ni texto
    sin tope-- y que la asercion **la mire de verdad**, porque una columna que
    ninguna comprobacion toca se ve igual de verde que una revisada entera.

    Se le pregunta al catalogo vivo y no al archivo de migracion: lo que importa
    es la columna que existe, no la que alguien escribio que crearia.
    """
    nombres = rls_assertion.personal_data_names()

    async with session.unscoped_session() as sesion:
        columnas = await rls_assertion.read_columns(sesion, ["budget_window"])

    por_nombre = {columna.column: columna for columna in columnas}
    assert "unmeasured_recording_calls" in por_nombre, (
        "la columna del conteo por carril no esta en el catalogo: la migracion no corrio"
    )
    assert rls_assertion.check_column(por_nombre["unmeasured_recording_calls"], nombres) is None

    informe = await rls_assertion.assert_rls_complete()

    assert informe.ok, informe.lines()
    assert "budget_window.unmeasured_recording_calls" in informe.checked_columns


async def test_falla_ante_una_tabla_excluida_con_una_columna_de_dato_personal(
    tabla_excluida_con_dato_personal: str,
) -> None:
    """El control que paga la exclusion, ejercido con una violacion de verdad.

    Se comprueba que falle **y que nombre las tres cosas**: la tabla, la columna
    y la entrada de la lista con la que coincidio. Un fallo que dijera solo "la
    tabla no pasa" obligaria a abrir la migracion y comparar catorce nombres a
    mano.
    """
    excluida = ExcludedTable(table=tabla_excluida_con_dato_personal, reason="tabla de prueba")

    async with session.unscoped_session() as sesion:
        tablas = await rls_assertion.read_tables(sesion)
        rol = await rls_assertion.read_role(sesion)
        columnas = await rls_assertion.read_columns(sesion, [excluida.table])

    informe = rls_assertion.evaluate(
        tablas, rol, [excluida], columnas, rls_assertion.personal_data_names()
    )

    assert not informe.ok
    fallo = next(f for f in informe.column_failures if f.column == "visitor_email")
    assert fallo.table == tabla_excluida_con_dato_personal
    assert "'email'" in fallo.reason
    assert any(
        "prueba_excluida.visitor_email" in linea and "email" in linea for linea in informe.lines()
    )


async def test_falla_ante_una_tabla_excluida_con_una_columna_de_texto_sin_tope(
    tabla_excluida_con_dato_personal: str,
) -> None:
    """La otra mitad de BR7.2, la que no depende de acertar el nombre.

    Una columna de texto sin tope es donde un dia cabe una frase del asegurado,
    y estaria en la unica parte del aplicativo que nadie filtra por aseguradora.
    La lista de nombres no la atrapa --`nota` no se parece a nada de las catorce
    entradas-- y por eso esta comprobacion es independiente y no un refuerzo de
    la otra.

    El mensaje nombra **el tipo**: sin el, quien lee la compuerta en rojo tiene
    que abrir la migracion para saber que hay que acotar.
    """
    excluida = ExcludedTable(table=tabla_excluida_con_dato_personal, reason="tabla de prueba")

    async with session.unscoped_session() as sesion:
        columnas = await rls_assertion.read_columns(sesion, [excluida.table])

    por_nombre = {columna.column: columna for columna in columnas}
    fallo = rls_assertion.check_column(por_nombre["nota"], rls_assertion.personal_data_names())

    assert fallo is not None
    assert "sin longitud acotada" in fallo.reason
    assert "text" in fallo.reason
    # Y la acotada del lado bueno: un tope escrito es lo que distingue a las dos.
    assert rls_assertion.check_column(por_nombre["id"], rls_assertion.personal_data_names()) is None


async def test_ninguna_columna_de_las_tres_tablas_del_dinero_coincide_con_la_lista(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """El falso positivo que habria que mirar, mirado.

    `spend_entry` tiene columnas como `provider`, `model`, `case_ref` y `use`, y
    la lista tiene entradas como `name`, `policy` y `document`. Se comprueba una
    por una que ninguna coincide, en vez de confiar en que la asercion global en
    verde lo demuestre: si un dia coincidiera, lo que hay que hacer es renombrar
    la columna o escribir por que esa entrada no aplica, nunca quitar la entrada
    de la lista.
    """
    nombres = rls_assertion.personal_data_names()
    assert nombres, "la lista versionada de nombres de dato personal esta vacia"

    async with session.unscoped_session() as sesion:
        columnas = await rls_assertion.read_columns(sesion, list(DEL_DINERO))

    assert columnas, "el catalogo no devolvio ninguna columna de las tres tablas"
    fallos = [
        f"{columna.table}.{columna.column}: {fallo.reason}"
        for columna in columnas
        if (fallo := rls_assertion.check_column(columna, nombres)) is not None
    ]

    assert fallos == [], (
        "estas columnas del dinero coinciden con la lista de nombres de dato "
        f"personal: {fallos}. La salida es renombrar la columna o escribir por "
        "que esa entrada no aplica, nunca quitar la entrada de la lista"
    )


# --- La cuarta tabla, que si es de un visitante -------------------------------


async def test_un_resumen_de_traza_no_se_ve_desde_otra_aseguradora(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR7.4 y BR6.6. La politica de fila filtra antes de que llegue el codigo.

    No es que se compare y se disimule: la consulta devuelve cero filas, igual
    que si el resumen no existiera, y este codigo no tendria forma de
    distinguirlos aunque quisiera.
    """
    async with session.session_for("stonecroft") as sesion:
        await session.execute_sql(
            sesion,
            CREAR_CASO,
            case_id="CASO-TRAZA",
            tenant_id="stonecroft",
            numero="STO-000900",
            ahora=AHORA,
        )
        await session.execute_sql(
            sesion,
            CREAR_RESUMEN,
            trace_id="TRAZA-1",
            tenant_id="stonecroft",
            case_id="CASO-TRAZA",
            navegador="resumen-de-la-clave",
            ahora=AHORA,
        )

    async with session.session_for("stonecroft") as sesion:
        propia = await session.fetch_one(
            sesion, "SELECT trace_id FROM trace_summary WHERE trace_id = :id", id="TRAZA-1"
        )
    async with session.session_for("sunmeadow") as sesion:
        ajena = await session.fetch_one(
            sesion, "SELECT trace_id FROM trace_summary WHERE trace_id = :id", id="TRAZA-1"
        )

    assert propia is not None
    assert ajena is None


async def test_el_resumen_de_traza_lleva_su_marca_y_alguien_se_compromete_a_borrarlo(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR7.4 y C-11. La marca sin purgador seria una promesa de retencion vacia.

    Lo borra la cascada del caso, igual que a las cuatro tablas hijas de U4, y
    por eso esta declarada en el purgador del caso y no en uno propio: darle un
    segundo dueno a un borrado que ya ocurre deja dos listas que un dia
    discrepan.
    """
    marcadas = await purge.visitor_data_tables()

    assert "trace_summary" in marcadas
    # Y ninguna de las tres del dinero la lleva: no son dato de visitante, y la
    # marca es lo que decide que se borra cada noche.
    assert marcadas.isdisjoint(DEL_DINERO)
