"""El contrato de borrado de datos de visitante (C-11, BR3.6, NFR19.1).

La prueba que importa aqui no es que los purgadores borren: es que **el registro
este completo**. Y eso no se comprueba comparando dos listas escritas a mano,
porque quien olvida una olvida las dos. Se le pregunta al catalogo de la base que
tablas llevan la marca de dato de visitante --la que cada revision escribe junto
a su aislamiento-- y se exige que cada una tenga purgador.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from untangle.server import composition
from untangle.tenancy import ephemeral, purge, session, visitor_access
from untangle.tenancy.models import PurgeResult

CLAVE_DE_ENLACES = "clave-de-prueba-de-los-enlaces-para-la-firma-hmac"
AYER = datetime(2026, 9, 19, 22, 0, tzinfo=UTC)
HOY = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)


async def _sembrar_datos_de_ayer() -> None:
    await visitor_access.issue_case_link(
        tenant_id="stonecroft", case_id="CASE-AYER", signing_key=CLAVE_DE_ENLACES, now=AYER
    )
    await visitor_access.issue_case_link(
        tenant_id="sunmeadow", case_id="CASE-AYER", signing_key=CLAVE_DE_ENLACES, now=AYER
    )
    await visitor_access.resolve_visitor_key(
        tenant_id="stonecroft",
        visitor_key=visitor_access.new_visitor_key(),
        origin="https://demo.untangle.local",
        now=AYER,
    )


async def _contar(tabla_sql: str) -> int:
    total = 0
    for tenant_id in ("stonecroft", "sunmeadow", "knotwell"):
        async with session.session_for(tenant_id) as sesion:
            fila = await session.fetch_one(sesion, tabla_sql)
            total += int(fila["total"]) if fila is not None else 0
    return total


async def test_toda_tabla_con_datos_de_visitante_tiene_purgador(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR3.6: la prueba que hace que el registro no se quede corto.

    Le pregunta a la base, no a una lista. El dia que una unidad cree una tabla
    de datos de visitante y se olvide de apuntarla en la raiz de composicion,
    esta prueba la nombra.
    """
    sin_purgador = await purge.tables_without_purger(composition.PURGADORES)

    assert sin_purgador == frozenset(), (
        f"estas tablas guardan datos de visitante y nadie se comprometio a "
        f"borrarlas: {sorted(sin_purgador)}"
    )


async def test_las_dos_tablas_de_u2_llevan_su_marca_en_la_base(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """La marca la escribe la revision que crea la tabla, como el aislamiento.

    Se comprueba que las dos de U2 **estan**, no que sean las unicas: otras
    unidades marcan las suyas y esta prueba no es el sitio donde se lleva esa
    cuenta. Quien lleva la cuenta completa es la de arriba, que le pregunta a la
    base y exige purgador para cada una.
    """
    marcadas = await purge.visitor_data_tables()

    assert {"case_access_link", "visitor_key"} <= marcadas


def test_el_registro_de_la_raiz_se_lee_entero_en_un_solo_archivo() -> None:
    """El registro es explicito, escrito a mano y sin descubrimiento (C-11).

    Se nombra purgador por purgador a proposito: el dia que alguien borre uno
    sin querer, esta prueba lo dice por su nombre en vez de contar cuantos hay.
    """
    assert [p.name for p in composition.PURGADORES] == [
        "case_access_link",
        "visitor_key",
        "case_record",
        "spend_quota_counters",
        "activation_progress",
        "chat_session",
        "inbox_event",
        "call_session",
        # El noveno lo trae U20, y es el unico que no cubre ninguna tabla: barre
        # lo que ya **salio** hacia las trazas. BR2.1 lo nombra aparte porque el
        # backend no esta en la base, asi que la comprobacion de arriba --que le
        # pregunta al catalogo por la marca-- no podia echarlo de menos.
        "traces_backend",
    ]


async def test_una_tabla_de_datos_de_visitante_sin_purgador_hace_fallar_la_prueba(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """La comprobacion se prueba con una violacion de verdad.

    Un registro al que le falta un dueno tiene que ser un fallo, no un silencio:
    es exactamente el caso que la retencion acotada no puede permitirse.
    """
    # Se quita **el que cubre tablas marcadas**, y se nombra por esa propiedad y
    # no por su posicion. Hasta U5 valia quitar el ultimo, porque las tablas de
    # todos los purgadores llevaban la marca; el purgador de U5 cubre
    # `quota_counter`, que es dato del proyecto y **no** la lleva --esta excluida
    # del aislamiento por BR7.1-- asi que quitarlo no haria faltar ninguna tabla
    # marcada y la prueba pasaria sin comprobar nada. Elegirlo por la propiedad
    # que la comprobacion mira es lo que la mantiene viva cuando el registro
    # crece con purgadores de las dos clases.
    marcadas = await purge.visitor_data_tables()
    olvidado = next(p for p in composition.PURGADORES if set(p.tables) & marcadas)
    incompleto = tuple(p for p in composition.PURGADORES if p is not olvidado)

    sin_purgador = await purge.tables_without_purger(incompleto)

    assert sin_purgador == set(olvidado.tables) & marcadas
    assert sin_purgador != frozenset()


async def test_el_reinicio_borra_las_dos_tablas(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """NFR19.1: cero enlaces y cero claves del dia anterior sobreviven.

    Se corren los dos purgadores **de U2**, no el registro entero: cada unidad
    comprueba el borrado de sus propias tablas, y una prueba que abarcara todas
    tendria que cambiar cada vez que una unidad nueva aporta la suya.
    """
    await _sembrar_datos_de_ayer()
    assert await _contar("SELECT count(*) AS total FROM case_access_link") == 2
    assert await _contar("SELECT count(*) AS total FROM visitor_key") == 1

    de_u2 = (purge.CASE_ACCESS_LINK_PURGER, purge.VISITOR_KEY_PURGER)
    resultados = [await purgador.purge(older_than=HOY) for purgador in de_u2]

    assert resultados == [
        PurgeResult(name="case_access_link", deleted=2, kept=0),
        PurgeResult(name="visitor_key", deleted=1, kept=0),
    ]
    assert await _contar("SELECT count(*) AS total FROM case_access_link") == 0
    assert await _contar("SELECT count(*) AS total FROM visitor_key") == 0


async def test_el_ensayo_cuenta_sin_borrar(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Poder ensayar es lo que permite mirar antes de ejecutar un borrado."""
    await _sembrar_datos_de_ayer()

    ensayo = await composition.PURGADORES[0].purge(older_than=HOY, dry_run=True)

    assert ensayo.deleted == 2
    assert await _contar("SELECT count(*) AS total FROM case_access_link") == 2


async def test_lo_de_hoy_no_se_borra(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """El corte es por fecha, no "todo": lo que entro despues sigue vivo."""
    await visitor_access.issue_case_link(
        tenant_id="stonecroft", case_id="CASE-HOY", signing_key=CLAVE_DE_ENLACES, now=HOY
    )

    resultado = await composition.PURGADORES[0].purge(older_than=HOY - timedelta(hours=1))

    assert resultado.deleted == 0
    assert await _contar("SELECT count(*) AS total FROM case_access_link") == 1
