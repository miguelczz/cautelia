"""Los comandos de U2: la asercion de aislamiento y la historia de migraciones.

Vive fuera de las seis piezas a proposito: es quien las **compone** para una
invocacion desde el archivo de tareas. El archivo de tareas de la raiz es el
contrato entre lo que corre una persona y lo que corre la tuberia (convencion 10
del equipo), asi que estos comandos tienen nombre alli y la tuberia los invoca en
vez de mantener su propia lista.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from untangle.settings import Settings
from untangle.tenancy import (
    ephemeral,
    rls_assertion,
    session,
    staff_identity,
    visitor_access,
)
from untangle.tenancy.models import RlsReport, UnknownTenantError

TABLAS_QUE_QUEDAN = """
    SELECT c.relname AS table_name
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'r' AND n.nspname = :esquema
    ORDER BY c.relname
"""


def _imprimir(informe: RlsReport) -> None:
    """El informe, siempre con lo revisado y lo excluido a la vista.

    Lo excluido se imprime con su razon aunque todo este en verde: una exclusion
    que solo se ve cuando algo falla es una exclusion que nadie revisa.
    """
    for excluida in informe.excluded_tables:
        print(f"excluida  {excluida.table}: {excluida.reason}")
    # Cuantas columnas se miraron de esas tablas. Sin esta linea, una tabla
    # excluida a la que el catalogo no respondio ninguna columna se veria igual
    # que una comprobada entera, y las dos en verde (BR7.2).
    if informe.excluded_tables:
        print(f"columnas  {len(informe.checked_columns)} de las tablas excluidas")
    for tabla in informe.checked_tables:
        print(f"revisada  {tabla}")
    # Cuantas llaves entre tablas aisladas se miraron (U10, decision 4). Por la
    # misma razon que las columnas: cero miradas y cero fallos se ven igual.
    print(f"llaves    {len(informe.checked_foreign_keys)} entre tablas aisladas")
    if informe.role is not None:
        salto = "SI" if (informe.role.bypass_rls or informe.role.superuser) else "no"
        print(f"rol       {informe.role.name} (puede saltarse las politicas: {salto})")


async def _asertar_sobre_la_base_que_haya() -> RlsReport:
    """Pregunta a la base que haya: la declarada, o una efimera propia.

    Cuando `UNTANGLE_DATABASE_URL` esta puesta se pregunta a **esa** base, que es
    la que de verdad sirve al aplicativo. Cuando no, el comando levanta la suya y
    la migra: asi se puede invocar solo, sin haber arrancado nada, y sigue
    midiendo el esquema real en vez de leer un archivo.
    """
    opciones = Settings()
    if opciones.database_url:
        session.configure(opciones.database_url)
        try:
            return await rls_assertion.assert_rls_complete()
        finally:
            await session.dispose()

    with ephemeral.ephemeral_database() as base:
        session.configure(base.app_url)
        try:
            ephemeral.upgrade_to_head(base.app_url)
            return await rls_assertion.assert_rls_complete()
        finally:
            await session.dispose()


async def _rls_check() -> int:
    informe = await _asertar_sobre_la_base_que_haya()
    _imprimir(informe)

    if informe.ok:
        print(
            f"\naislamiento: {len(informe.checked_tables)} tabla(s) con politica, "
            "y el rol de la conexion no puede saltarse ninguna"
        )
        return 0

    print("", file=sys.stderr)
    for linea in informe.lines():
        print(linea, file=sys.stderr)
    print(
        f"\n{len(informe.lines())} fallo(s) de aislamiento. La compuerta se pone "
        "roja: una tabla sin politica es una fuga esperando a que alguien "
        "consulte sin filtro.",
        file=sys.stderr,
    )
    return 1


async def _comprobar_esquema_vacio() -> list[str]:
    """Las tablas que sobreviven a un `downgrade` hasta la base."""
    fuera = {entrada.table for entrada in rls_assertion.excluded_tables()}
    async with session.unscoped_session() as sesion:
        filas = await session.fetch_all(sesion, TABLAS_QUE_QUEDAN, esquema=rls_assertion.APP_SCHEMA)
    return [str(fila["table_name"]) for fila in filas if str(fila["table_name"]) not in fuera]


async def _migrate_check() -> int:
    """Sube, baja y vuelve a subir contra una base virgen (BR1.11, SEC-U2.12).

    La suya propia, no la de la suite: necesita una base sin nada para que el
    `downgrade` tenga algo que demostrar.
    """
    cabeza = ephemeral.require_single_head()
    print(f"cabeza unica: {cabeza}")

    with ephemeral.ephemeral_database() as base:
        session.configure(base.app_url)
        try:
            ephemeral.upgrade_to_head(base.app_url)
            print("subida      ok")

            informe = await rls_assertion.assert_rls_complete()
            if not informe.ok:
                for linea in informe.lines():
                    print(linea, file=sys.stderr)
                print(
                    "\nuna revision creo una tabla sin su aislamiento en la misma "
                    "revision (BR1.10). No existe una revision posterior que lo "
                    "agregue: entre una y otra habria una ventana con datos sin aislar.",
                    file=sys.stderr,
                )
                return 1
            print(f"aislamiento ok ({len(informe.checked_tables)} tabla(s))")

            ephemeral.downgrade_to_base(base.app_url)
            sobrantes = await _comprobar_esquema_vacio()
            if sobrantes:
                print(
                    f"bajada      falla: quedan tablas tras bajar hasta la base: "
                    f"{', '.join(sobrantes)}",
                    file=sys.stderr,
                )
                return 1
            print("bajada      ok")

            ephemeral.upgrade_to_head(base.app_url)
            print("resubida    ok")
        finally:
            await session.dispose()

    print("\nmigraciones: una sola cabeza, reversible y con su aislamiento")
    return 0


def _issue_credential(tenant_id: str, principal_id: str) -> int:
    """Emite una credencial de bandeja **a la salida estandar** (BR2.6, D23).

    No hay opcion de escribirla en un archivo, y no es un olvido: una credencial
    en un archivo del repositorio es una credencial publicada, y de ahi no se
    vuelve borrandola --una clave que llego a un commit se rota en su origen--.

    Es para Miguel, el despliegue local y las pruebas. Los visitantes no usan
    esto: entran con el enlace firmado de su propio caso.
    """
    opciones = Settings()
    try:
        token = staff_identity.issue_credential(
            tenant_id=tenant_id,
            principal_id=principal_id,
            signing_key=opciones.staff_credential_signing_key,
        )
    except (UnknownTenantError, staff_identity.SigningKeyMissingError) as error:
        print(str(error), file=sys.stderr)
        return 1

    # El token, solo, en la salida estandar: asi se puede canalizar. Todo lo
    # demas va por la de error, para que no se cuele en lo que alguien pegue.
    print(token)
    print(
        f"\ncredencial de '{principal_id}' en '{tenant_id}', valida "
        f"{int(staff_identity.CREDENTIAL_LIFETIME.total_seconds() // 3600)} horas.\n"
        "No la guarde en ningun archivo del repositorio: una credencial que llega "
        "a un commit se considera comprometida y la clave se rota en su origen.",
        file=sys.stderr,
    )
    return 0


async def _issue_case_link(tenant_id: str, case_id: str) -> int:
    """Emite el enlace de un caso **a la salida estandar** (C-07, BR3.1).

    Por la misma razon que la credencial, y con el mismo cuidado: el token se emite una
    sola vez y de la fila queda solo su resumen, asi que un archivo con el token dentro
    seria el unico sitio donde vive y a la vez el sitio donde no debe estar.

    Existe porque **nada lo emite todavia en produccion**: el enlace que el chat o la
    consola entregan al cerrar es de U13 y de U17, y sin este comando la pantalla del
    visitante --la que entra en la linea base de accesibilidad (D25)-- no se puede abrir
    con las manos. Es el hermano de `issue-credential` y sirve a lo mismo: Miguel, el
    despliegue local y las pruebas.

    Imprime la **direccion entera** y no solo el token, con el token en el fragmento:
    armarla a mano es exactamente el paso donde alguien lo pone en la ruta y lo deja en
    cada registro que la vea pasar.
    """
    opciones = Settings()
    try:
        emitido = await visitor_access.issue_case_link(
            tenant_id=tenant_id,
            case_id=case_id,
            signing_key=opciones.case_link_signing_key,
        )
    except (UnknownTenantError, visitor_access.LinkSigningKeyMissingError) as error:
        print(str(error), file=sys.stderr)
        return 1

    print(f"/c#{emitido.token}")
    print(
        f"\nenlace del caso '{case_id}' en '{tenant_id}', valido "
        f"{int(visitor_access.LINK_LIFETIME.total_seconds() // 60)} minutos.\n"
        "El token va en el fragmento de la direccion: el navegador nunca lo manda al "
        "servidor, asi que no aparece en la barra, ni en la cabecera de procedencia, "
        "ni en ningun registro. No lo guarde en ningun archivo del repositorio.",
        file=sys.stderr,
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="untangle-tenancy",
        description=(
            "Comprobaciones de aislamiento, migraciones y emision de credenciales y "
            "enlaces de caso de U2."
        ),
    )
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser(
        "rls-check",
        help="Pregunta al catalogo vivo que tablas hay y al rol vivo que puede hacer.",
    )
    sub.add_parser(
        "migrate-check",
        help="Sube, baja y vuelve a subir contra una base efimera propia.",
    )
    credencial = sub.add_parser(
        "issue-credential",
        help="Emite una credencial de bandeja a la salida estandar. Nunca a un archivo.",
    )
    credencial.add_argument("--tenant", required=True, help="Identificador de la aseguradora.")
    credencial.add_argument("--principal", required=True, help="Identificador de la persona.")
    enlace = sub.add_parser(
        "issue-case-link",
        help="Emite el enlace de un caso a la salida estandar. Nunca a un archivo.",
    )
    enlace.add_argument("--tenant", required=True, help="Identificador de la aseguradora.")
    enlace.add_argument("--case", required=True, help="Identificador del caso.")
    return parser


def main(argv: list[str] | None = None) -> int:
    argumentos = _parser().parse_args(argv)
    if argumentos.comando == "rls-check":
        return asyncio.run(_rls_check())
    if argumentos.comando == "issue-credential":
        return _issue_credential(argumentos.tenant, argumentos.principal)
    if argumentos.comando == "issue-case-link":
        return asyncio.run(_issue_case_link(argumentos.tenant, argumentos.case))
    return asyncio.run(_migrate_check())


if __name__ == "__main__":
    sys.exit(main())
