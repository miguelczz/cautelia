"""La asercion de aislamiento, contra el catalogo vivo (BR1.2, SEC-U2.1, SEC-U2.4).

Tres preguntas al motor, ninguna a un archivo:

1. **Que tablas tiene el esquema del aplicativo.** De cada una se exige
   aislamiento habilitado, aislamiento forzado y al menos una politica que lea
   la variable de aseguradora. Una lista de tablas escrita a mano solo cubre las
   que alguien se acordo de anadir; la tabla que nadie anadio pasa la compuerta
   en verde sin estar aislada, y nadie va a buscarla porque el archivo se ve
   bien.
2. **Que privilegios tiene el rol vivo de esta conexion.** Si puede saltarse las
   politicas, la asercion falla **aunque todas las tablas esten bien**: en ese
   caso las pruebas de aislamiento pasarian sin que exista aislamiento. Leer la
   migracion que creo el rol no prueba con que rol se esta conectado ahora.
3. **Que columnas tienen las tablas excluidas, y de que tipo.** Es la pregunta
   que anade U5 y la que **paga la exclusion** (BR7.2). Una tabla que sale del
   aislamiento por aseguradora deja de estar filtrada por politica, asi que a
   cambio se le prohibe guardar nada personal, y esa prohibicion se comprueba en
   vez de prometerse: falla ante una columna de texto sin longitud acotada, o
   ante un nombre que contenga --sin distinguir mayusculas-- una entrada de la
   lista versionada de nombres de dato personal.

Por eso una tabla excluida ya **no se salta**: se comprueba de otra manera. Las
dos listas --la de exclusion y la de nombres-- son versionadas, cortas y con
**su razon por entrada**, y viven juntas en el manifiesto para que una revision
las lea a la vez.

**Lo que esta asercion no puede.** No impide guardar un dato personal en una
columna de nombre inocente y longitud acotada. Contra eso no hay asercion de
esquema; lo que hay es que ninguna de las tablas excluidas tiene una columna de
texto libre en su diseno, y que anadir una se ve en la revision del cambio.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path

from untangle import observability, paths
from untangle.tenancy import session
from untangle.tenancy.models import (
    ColumnFailure,
    ConnectionRole,
    ExcludedTable,
    ForeignKey,
    ForeignKeyFailure,
    PersonalDataName,
    RlsFailure,
    RlsReport,
    TableColumn,
    TableIsolation,
)

#: El esquema donde el aplicativo crea sus tablas.
APP_SCHEMA = "public"

#: Las tres cosas que se le exigen a cada tabla, con el nombre que sale en el
#: mensaje de fallo. Nunca se dice solo "falta RLS": a las seis semanas eso
#: cuesta una tarde.
FALTA_HABILITADO = "aislamiento habilitado"
FALTA_FORZADO = "aislamiento forzado"
FALTA_POLITICA = "politica de aseguradora"
FALTA_ROL_SIN_SALTO = "un rol que no pueda saltarse las politicas"

#: Los tipos que guardan texto. Se declaran por su nombre en el motor y como
#: conjunto cerrado: un tipo nuevo tiene que entrar aqui a proposito, no colarse
#: por una heuristica sobre la cadena.
#:
#: `json`, `jsonb` y `xml` estan en la lista a proposito. Son texto libre con
#: otro nombre: una columna asi en una tabla excluida admite una frase del
#: asegurado igual que un `text`, y quedaria en la unica parte del aplicativo
#: que nadie filtra por aseguradora. Ademas **nunca** llevan tope, asi que la
#: unica forma de tener una es decidirlo y cambiar esta lista.
TIPOS_DE_TEXTO = frozenset(
    {
        "text",
        "character varying",
        "character",
        "citext",
        "json",
        "jsonb",
        "xml",
    }
)

#: Como se dice en el informe que una columna es texto libre. El tipo va dentro
#: del mensaje: sin el, quien lee la compuerta en rojo tiene que abrir la
#: migracion para saber que hay que acotar.
TEXTO_SIN_TOPE = "texto sin longitud acotada (tipo {tipo}); una tabla excluida no puede tenerlo"

#: Y como se dice que el nombre coincidio. Nombra **la entrada** y su razon: un
#: mensaje que solo dijera "parece dato personal" obligaria a adivinar cual de
#: las catorce entradas salto.
NOMBRE_DE_DATO_PERSONAL = (
    "el nombre contiene '{entrada}', de la lista de nombres de dato personal ({razon})"
)

TABLAS_DEL_ESQUEMA = """
    SELECT c.relname AS table_name,
           c.relrowsecurity AS row_security,
           c.relforcerowsecurity AS force_row_security,
           (
               SELECT count(*)
               FROM pg_policies p
               WHERE p.schemaname = n.nspname
                 AND p.tablename = c.relname
                 AND (
                     coalesce(p.qual, '') LIKE :patron
                     OR coalesce(p.with_check, '') LIKE :patron
                 )
           ) AS tenant_policies
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'r'
      AND n.nspname = :esquema
    ORDER BY c.relname
"""

ROL_DE_LA_CONEXION = """
    SELECT rolname, rolbypassrls, rolsuper
    FROM pg_roles
    WHERE rolname = current_user
"""

#: La segunda consulta al catalogo, la que anade U5. `format_type` devuelve el
#: tipo **con su tope escrito** --`character varying(32)`, `numeric(20,12)`,
#: `text`--, que es justo lo que hace falta para distinguir un texto acotado de
#: uno que no lo esta. Se pregunta solo por las tablas excluidas: las demas ya
#: las cubre la politica de aseguradora.
COLUMNAS_DE_LAS_TABLAS = """
    SELECT c.relname AS table_name,
           a.attname AS column_name,
           format_type(a.atttypid, a.atttypmod) AS data_type
    FROM pg_attribute a
    JOIN pg_class c ON c.oid = a.attrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'r'
      AND n.nspname = :esquema
      AND c.relname = ANY(:tablas)
      AND a.attnum > 0
      AND NOT a.attisdropped
    ORDER BY c.relname, a.attnum
"""


#: La cuarta pregunta, la que anade U10: las llaves foraneas del esquema, con sus
#: columnas **en el orden de la llave** en las dos puntas. `WITH ORDINALITY`
#: conserva ese orden, que es el que empareja cada columna con la que apunta.
LLAVES_FORANEAS = """
    SELECT con.conname AS constraint_name,
           src.relname AS table_name,
           dst.relname AS referenced_table,
           ARRAY(
               SELECT a.attname::text
               FROM unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord)
               JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum
               ORDER BY k.ord
           ) AS columns,
           ARRAY(
               SELECT a.attname::text
               FROM unnest(con.confkey) WITH ORDINALITY AS k(attnum, ord)
               JOIN pg_attribute a ON a.attrelid = con.confrelid AND a.attnum = k.attnum
               ORDER BY k.ord
           ) AS referenced_columns
    FROM pg_constraint con
    JOIN pg_class src ON src.oid = con.conrelid
    JOIN pg_class dst ON dst.oid = con.confrelid
    JOIN pg_namespace n ON n.oid = src.relnamespace
    WHERE con.contype = 'f'
      AND n.nspname = :esquema
    ORDER BY src.relname, con.conname
"""

#: La columna de la aseguradora, con la grafia de todas las tablas aisladas.
COLUMNA_DE_ASEGURADORA = "tenant_id"

#: Como se dice en el informe que una llave no lleva la aseguradora.
LLAVE_SIN_ASEGURADORA = (
    "la llave no lleva 'tenant_id' en las dos puntas y en la misma posicion; las "
    "llaves foraneas no pasan por las politicas de fila, y sin la aseguradora una "
    "fila de una aseguradora puede apuntar a una de otra"
)


def _manifiesto(root: Path | None = None) -> Mapping[str, object]:
    """El bloque `[tool.untangle.rls]` del manifiesto, leido una vez.

    Las dos listas viven ahi y no en una bandera de linea de comandos: lo que se
    pasa al invocar no lo ve nadie en una revision de codigo.
    """
    base = root if root is not None else paths.repo_root()
    manifiesto = base / "app" / "backend" / "pyproject.toml"
    datos = tomllib.loads(manifiesto.read_text(encoding="utf-8"))
    bloque = datos.get("tool", {}).get("untangle", {}).get("rls", {})
    return bloque if isinstance(bloque, dict) else {}


def excluded_tables(root: Path | None = None) -> tuple[ExcludedTable, ...]:
    """La lista de exclusion versionada, con su razon por entrada."""
    entradas = _manifiesto(root).get("excluded", [])
    if not isinstance(entradas, list):  # pragma: no cover -- el manifiesto es nuestro
        return ()
    return tuple(
        ExcludedTable(table=str(entrada["table"]), reason=str(entrada["reason"]))
        for entrada in entradas
    )


def personal_data_names(root: Path | None = None) -> tuple[PersonalDataName, ...]:
    """La lista versionada de nombres de dato personal (BR7.2).

    Vive **al lado** de la lista de exclusion que paga, en el mismo bloque del
    manifiesto, para que una revision las lea juntas: la primera dice que tablas
    salen del aislamiento y la segunda es el precio que pagan.
    """
    entradas = _manifiesto(root).get("personal_data_column_names", [])
    if not isinstance(entradas, list):  # pragma: no cover -- el manifiesto es nuestro
        return ()
    return tuple(
        PersonalDataName(name=str(entrada["name"]), reason=str(entrada["reason"]))
        for entrada in entradas
    )


def es_texto_sin_tope(data_type: str) -> bool:
    """Si ese tipo guarda texto y **nadie le escribio un tope**.

    El motor escribe el tope entre parentesis: `character varying(32)` lo lleva
    y `text` no. Asi que la pregunta son dos: que el tipo base sea de texto, y
    que no haya parentesis. Se mira **la presencia** del parentesis y no el
    numero de dentro, porque lo que distingue una columna acotada de una que no
    lo esta es que alguien escribio un tope, sea cual sea.

    Un `numeric(20,12)` tambien lleva parentesis y no es texto: la primera
    pregunta ya lo deja fuera, y por eso el orden de las dos no importa.
    """
    tipo_base = data_type.split("(", 1)[0].strip().lower()
    if tipo_base not in TIPOS_DE_TEXTO:
        return False
    return "(" not in data_type


def check_column(
    column: TableColumn, personal_names: Sequence[PersonalDataName]
) -> ColumnFailure | None:
    """Que le pasa a esta columna, o nada. Pura, y por eso se prueba sin base.

    Dos motivos y solo dos, los dos de BR7.2: texto sin tope, o un nombre que
    **contiene** una entrada de la lista versionada, sin distinguir mayusculas.
    Se busca por contenido y no por igualdad a proposito: `visitor_email`,
    `email_hash` y `EmailAddr` son la misma columna con tres nombres, y una
    comparacion exacta las dejaria pasar a las tres.
    """
    if es_texto_sin_tope(column.data_type):
        return ColumnFailure(
            table=column.table,
            column=column.column,
            reason=TEXTO_SIN_TOPE.format(tipo=column.data_type),
        )

    nombre = column.column.lower()
    for entrada in personal_names:
        if entrada.name.lower() in nombre:
            return ColumnFailure(
                table=column.table,
                column=column.column,
                reason=NOMBRE_DE_DATO_PERSONAL.format(entrada=entrada.name, razon=entrada.reason),
            )
    return None


def check_foreign_key(key: ForeignKey) -> ForeignKeyFailure | None:
    """Que le pasa a una llave entre dos tablas aisladas, o nada. Pura.

    Exige `tenant_id` en la misma posicion en las dos puntas: una llave
    `(tenant_id, case_id) -> (case_id, tenant_id)` lleva la columna y seguiria
    emparejando la aseguradora con un caso.
    """
    columna = COLUMNA_DE_ASEGURADORA
    if columna in key.columns and columna in key.referenced_columns:
        posicion = key.columns.index(columna)
        if key.referenced_columns[posicion] == columna:
            return None
    return ForeignKeyFailure(
        constraint=key.constraint,
        table=key.table,
        referenced_table=key.referenced_table,
        reason=LLAVE_SIN_ASEGURADORA,
    )


def check_foreign_keys(
    keys: Sequence[ForeignKey], isolated_tables: Sequence[str]
) -> tuple[tuple[str, ...], tuple[ForeignKeyFailure, ...]]:
    """Las llaves entre dos tablas aisladas: cuales se miraron y cuales fallan.

    Solo las que van **de una tabla aislada a otra**. Una llave desde una tabla
    excluida --el libro mayor del gasto nombra un caso-- no mezcla filas de dos
    aseguradoras que la politica separe: la tabla excluida no esta separada por
    aseguradora, y lo que la protege es no guardar nada personal (BR7.2).
    """
    aisladas = set(isolated_tables)
    miradas: list[str] = []
    fallos: list[ForeignKeyFailure] = []
    for llave in keys:
        if llave.table not in aisladas or llave.referenced_table not in aisladas:
            continue
        miradas.append(llave.constraint)
        fallo = check_foreign_key(llave)
        if fallo is not None:
            fallos.append(fallo)
    return tuple(miradas), tuple(fallos)


def _que_le_falta(tabla: TableIsolation) -> tuple[str, ...]:
    """Cual de las tres cosas le falta a una tabla aislada, por su nombre.

    Nunca se dice solo "falta RLS": a las seis semanas eso cuesta una tarde.
    """
    falta: list[str] = []
    if not tabla.row_security:
        falta.append(FALTA_HABILITADO)
    if not tabla.force_row_security:
        falta.append(FALTA_FORZADO)
    if tabla.tenant_policies < 1:
        falta.append(FALTA_POLITICA)
    return tuple(falta)


def check_excluded_table(
    columns: Sequence[TableColumn], personal_names: Sequence[PersonalDataName]
) -> tuple[tuple[str, ...], tuple[ColumnFailure, ...]]:
    """Lo que se le comprueba a una tabla excluida: sus columnas (BR7.2).

    Devuelve **las dos cosas**: que se miro y que fallo. Lo primero importa
    tanto como lo segundo, porque una tabla excluida de la que no se miro
    ninguna columna esta de hecho saltada, y sin ese dato las dos se ven igual
    en verde.
    """
    revisadas: list[str] = []
    fallos: list[ColumnFailure] = []
    for columna in columns:
        revisadas.append(f"{columna.table}.{columna.column}")
        fallo = check_column(columna, personal_names)
        if fallo is not None:
            fallos.append(fallo)
    return tuple(revisadas), tuple(fallos)


def evaluate(
    tables: Sequence[TableIsolation],
    role: ConnectionRole,
    excluded: Sequence[ExcludedTable],
    columns: Sequence[TableColumn] = (),
    personal_names: Sequence[PersonalDataName] = (),
) -> RlsReport:
    """Compone el informe. Es pura: se puede probar sin base de datos.

    Una tabla de la lista de exclusion **ya no se salta**: se comprueba de otra
    manera, mirando sus columnas contra BR7.2. Es lo que paga la exclusion, y
    por eso `columns` y `personal_names` entran aqui en vez de en una segunda
    funcion que alguien pudiera olvidarse de llamar.
    """
    fuera = {entrada.table for entrada in excluded}
    revisadas: list[str] = []
    fallos: list[RlsFailure] = []

    por_tabla: dict[str, list[TableColumn]] = {}
    for columna in columns:
        por_tabla.setdefault(columna.table, []).append(columna)

    columnas_revisadas: list[str] = []
    fallos_de_columna: list[ColumnFailure] = []

    for tabla in tables:
        if tabla.table in fuera:
            # No se salta: se comprueba de otra manera. Sin politica de
            # aseguradora que la filtre, lo que la protege es no tener ahi
            # dentro nada que aislar (BR7.1, BR7.2).
            miradas, rotas = check_excluded_table(por_tabla.get(tabla.table, []), personal_names)
            columnas_revisadas.extend(miradas)
            fallos_de_columna.extend(rotas)
            continue

        revisadas.append(tabla.table)
        falta = _que_le_falta(tabla)
        if falta:
            fallos.append(RlsFailure(table=tabla.table, missing=falta))

    # Un rol que puede saltarse las politicas invalida el resultado entero: con
    # el, todas las tablas de arriba podrian estar perfectas y la suite seguiria
    # midiendo nada.
    if role.bypass_rls or role.superuser:
        fallos.append(RlsFailure(table=f"rol {role.name}", missing=(FALTA_ROL_SIN_SALTO,)))

    return RlsReport(
        checked_tables=tuple(revisadas),
        excluded_tables=tuple(excluded),
        failures=tuple(fallos),
        role=role,
        checked_columns=tuple(columnas_revisadas),
        column_failures=tuple(fallos_de_columna),
    )


async def read_tables(sesion: session.TenantSession) -> tuple[TableIsolation, ...]:
    """Que tablas hay y que aislamiento tiene cada una, segun el catalogo vivo."""
    filas = await session.fetch_all(
        sesion,
        TABLAS_DEL_ESQUEMA,
        esquema=APP_SCHEMA,
        patron=f"%{session.TENANT_SETTING}%",
    )
    return tuple(
        TableIsolation(
            table=str(fila["table_name"]),
            row_security=bool(fila["row_security"]),
            force_row_security=bool(fila["force_row_security"]),
            tenant_policies=int(fila["tenant_policies"]),
        )
        for fila in filas
    )


async def read_columns(
    sesion: session.TenantSession, tables: Sequence[str]
) -> tuple[TableColumn, ...]:
    """Que columnas tienen esas tablas y de que tipo, segun el catalogo vivo.

    Se le pregunta al motor y no al archivo de migracion por la misma razon que
    todo lo demas de este modulo: la migracion dice lo que alguien quiso hacer,
    y el catalogo dice lo que hay. Una columna anadida a mano en una base viva no
    aparece en ninguna revision.
    """
    if not tables:
        return ()
    filas = await session.fetch_all(
        sesion,
        COLUMNAS_DE_LAS_TABLAS,
        esquema=APP_SCHEMA,
        tablas=list(tables),
    )
    return tuple(
        TableColumn(
            table=str(fila["table_name"]),
            column=str(fila["column_name"]),
            data_type=str(fila["data_type"]),
        )
        for fila in filas
    )


async def read_foreign_keys(sesion: session.TenantSession) -> tuple[ForeignKey, ...]:
    """Las llaves foraneas del esquema, con sus columnas en orden, segun el catalogo vivo."""
    filas = await session.fetch_all(sesion, LLAVES_FORANEAS, esquema=APP_SCHEMA)
    return tuple(
        ForeignKey(
            constraint=str(fila["constraint_name"]),
            table=str(fila["table_name"]),
            referenced_table=str(fila["referenced_table"]),
            columns=tuple(str(c) for c in fila["columns"]),
            referenced_columns=tuple(str(c) for c in fila["referenced_columns"]),
        )
        for fila in filas
    )


async def read_role(sesion: session.TenantSession) -> ConnectionRole:
    """Que privilegios tiene el rol **vivo** de esta conexion."""
    fila = await session.fetch_one(sesion, ROL_DE_LA_CONEXION)
    if fila is None:  # pragma: no cover -- PostgreSQL siempre responde a current_user
        msg = "el motor no devolvio ninguna fila para el rol de la conexion"
        raise RuntimeError(msg)
    return ConnectionRole(
        name=str(fila["rolname"]),
        bypass_rls=bool(fila["rolbypassrls"]),
        superuser=bool(fila["rolsuper"]),
    )


async def assert_rls_complete(root: Path | None = None) -> RlsReport:
    """La asercion completa (C-10). Corre en `verify.sh` y al arrancar el proceso.

    Al arrancar es **condicion de arranque**: si no se puede ejecutar --base
    caida o inalcanzable-- el proceso no arranca, lo dice nombrando la causa y
    reintenta. Arrancar sin haber podido comprobar el aislamiento es exactamente
    el estado en el que una fuga pasa desapercibida (decision Q2 del diseno de
    calidad).
    """
    excluidas = excluded_tables(root)
    nombres = personal_data_names(root)

    async with session.unscoped_session() as sesion:
        tablas = await read_tables(sesion)
        rol = await read_role(sesion)
        # La tercera pregunta: solo por las tablas excluidas, que son las que
        # dejaron de estar filtradas por politica y tienen que pagarlo (BR7.2).
        columnas = await read_columns(sesion, [entrada.table for entrada in excluidas])
        # La cuarta: las llaves entre tablas aisladas llevan la aseguradora.
        llaves = await read_foreign_keys(sesion)

    informe = evaluate(tablas, rol, excluidas, columnas, nombres)
    miradas, rotas = check_foreign_keys(llaves, informe.checked_tables)
    informe = replace(informe, checked_foreign_keys=miradas, foreign_key_failures=rotas)
    observability.emit(
        "tenancy.rls_asserted",
        checked=len(informe.checked_tables),
        excluded=len(informe.excluded_tables),
        checked_columns=len(informe.checked_columns),
        failures=len(informe.failures),
        column_failures=len(informe.column_failures),
        checked_foreign_keys=len(informe.checked_foreign_keys),
        foreign_key_failures=len(informe.foreign_key_failures),
        role=rol.name,
        role_can_bypass=rol.bypass_rls or rol.superuser,
    )
    return informe
