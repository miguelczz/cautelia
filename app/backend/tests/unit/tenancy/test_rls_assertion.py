"""La asercion de aislamiento: modelo de datos y conducta de la base (AC4.11.1).

La parte que compone el informe es **pura**, y por eso estas pruebas no necesitan
base: se le entrega lo que el catalogo respondio y se comprueba que decide bien.
Las dos preguntas al motor --que tablas hay y que puede el rol vivo-- se ejercen
contra PostgreSQL de verdad en la ultima prueba del archivo, que es donde una
consulta mal escrita se nota.
"""

from __future__ import annotations

from dataclasses import replace

from untangle import paths
from untangle.tenancy import ephemeral, rls_assertion, session
from untangle.tenancy.models import ConnectionRole, ExcludedTable, ForeignKey, TableIsolation

ROL_SIN_SALTO = ConnectionRole(name="untangle_app", bypass_rls=False, superuser=False)

TABLA_CORRECTA = TableIsolation(
    table="case_access_link",
    row_security=True,
    force_row_security=True,
    tenant_policies=1,
)


def test_pasa_con_el_esquema_correcto() -> None:
    informe = rls_assertion.evaluate([TABLA_CORRECTA], ROL_SIN_SALTO, [])

    assert informe.ok
    assert informe.checked_tables == ("case_access_link",)
    assert informe.failures == ()


def test_falla_ante_una_tabla_sin_politica_y_dice_que_le_falta() -> None:
    """Nunca dice solo "falta RLS": nombra la tabla y que le falta de las tres."""
    sin_politica = TableIsolation(
        table="visitor_key",
        row_security=True,
        force_row_security=True,
        tenant_policies=0,
    )

    informe = rls_assertion.evaluate([sin_politica], ROL_SIN_SALTO, [])

    assert not informe.ok
    assert informe.failures[0].table == "visitor_key"
    assert informe.failures[0].missing == (rls_assertion.FALTA_POLITICA,)
    assert informe.lines() == ("visitor_key: le falta politica de aseguradora",)


def test_falla_ante_una_tabla_sin_aislamiento_habilitado_ni_forzado() -> None:
    """Una tabla nueva que nadie aislo: las tres carencias salen nombradas."""
    desnuda = TableIsolation(
        table="graph_checkpoint",
        row_security=False,
        force_row_security=False,
        tenant_policies=0,
    )

    informe = rls_assertion.evaluate([desnuda], ROL_SIN_SALTO, [])

    assert informe.failures[0].missing == (
        rls_assertion.FALTA_HABILITADO,
        rls_assertion.FALTA_FORZADO,
        rls_assertion.FALTA_POLITICA,
    )


def test_falla_ante_un_rol_con_privilegio_de_salto_aunque_las_tablas_esten_bien() -> None:
    """El fallo que no avisa: con un rol asi, la suite entera mide nada."""
    con_salto = ConnectionRole(name="postgres", bypass_rls=True, superuser=False)

    informe = rls_assertion.evaluate([TABLA_CORRECTA], con_salto, [])

    assert not informe.ok
    assert informe.failures[0].missing == (rls_assertion.FALTA_ROL_SIN_SALTO,)
    assert "postgres" in informe.failures[0].table


def test_un_superusuario_tambien_falla() -> None:
    """`rolsuper` se salta las politicas sin necesitar `rolbypassrls`."""
    superusuario = ConnectionRole(name="postgres", bypass_rls=False, superuser=True)

    informe = rls_assertion.evaluate([TABLA_CORRECTA], superusuario, [])

    assert not informe.ok


def test_una_tabla_excluida_no_se_revisa_y_su_razon_viaja_en_el_informe() -> None:
    """La exclusion se ve siempre, no solo cuando algo falla."""
    versiones = TableIsolation(
        table="alembic_version",
        row_security=False,
        force_row_security=False,
        tenant_policies=0,
    )
    excluida = ExcludedTable(table="alembic_version", reason="no guarda datos del aplicativo")

    informe = rls_assertion.evaluate([versiones, TABLA_CORRECTA], ROL_SIN_SALTO, [excluida])

    assert informe.ok
    assert informe.checked_tables == ("case_access_link",)
    assert informe.excluded_tables == (excluida,)


def test_la_lista_de_exclusion_versionada_trae_su_razon_por_entrada() -> None:
    """Cada exclusion lleva escrito por que, y ninguna tabla aparece dos veces.

    Se comprueba que la de U2 **este**, no que sea la unica: la lista crece cada
    vez que una unidad saca una tabla del aislamiento --U5 saca las tres del
    dinero-- y una prueba que la enumerara habria que reescribirla en cada una
    sin comprobar nada mas que hoy. Es el mismo criterio que la asercion
    completa de mas abajo.

    Lo que si se comprueba entero es lo que hace util a la lista: que ninguna
    entrada llegue sin razon, y que ninguna tabla se excluya dos veces, porque
    una exclusion repetida esconde una segunda razon que nadie lee.
    """
    excluidas = rls_assertion.excluded_tables()
    tablas = [entrada.table for entrada in excluidas]

    assert "alembic_version" in tablas
    assert all(entrada.reason.strip() for entrada in excluidas)
    assert len(tablas) == len(set(tablas))


def test_la_historia_de_migraciones_tiene_una_sola_cabeza() -> None:
    """BR1.11: dos cabezas son un conflicto que la compuerta rechaza.

    Se comprueba que haya **una**, no cual: la cabeza cambia cada vez que una
    unidad anade su revision, y una prueba que la nombrara habria que
    reescribirla en cada una sin comprobar nada mas que hoy.
    """
    assert ephemeral.require_single_head()


def test_la_imagen_efimera_es_la_misma_que_la_del_entorno_local() -> None:
    """Un solo camino: lo que corre en la tuberia es lo que corre en local.

    Si las dos se separaran, un fallo que solo aparece en una de ellas volveria a
    ser un misterio, que es justo lo que anclar por huella evita.
    """
    compose = paths.repo_root() / "docker-compose.yml"
    contenido = compose.read_text(encoding="utf-8")

    assert ephemeral.POSTGRES_IMAGE in contenido


async def test_la_asercion_completa_pasa_contra_el_esquema_real(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Las dos preguntas al motor, contra PostgreSQL de verdad.

    Una consulta mal escrita se nota aqui y en ningun otro sitio: la parte pura
    de arriba pasaria igual con un catalogo inventado.
    """
    informe = await rls_assertion.assert_rls_complete()

    assert informe.ok, informe.lines()
    # Las dos de U2 estan; las de otras unidades tambien, y no se cuentan aqui.
    # Lo que esta prueba defiende es que la asercion **corra de verdad** contra
    # el motor, no cuantas tablas tiene el proyecto esta semana.
    assert {"case_access_link", "visitor_key"} <= set(informe.checked_tables)
    assert informe.role is not None
    assert informe.role.name == ephemeral.APP_ROLE
    assert informe.role.bypass_rls is False


# --- La cuarta pregunta: las llaves entre tablas aisladas (U10, decision 4) -----


def _llave(
    columnas: tuple[str, ...], apuntadas: tuple[str, ...], *, tabla: str = "disclosure_record"
) -> ForeignKey:
    return ForeignKey(
        constraint=f"{tabla}_del_caso",
        table=tabla,
        referenced_table="case_record",
        columns=columnas,
        referenced_columns=apuntadas,
    )


def test_una_llave_con_la_aseguradora_en_las_dos_puntas_pasa() -> None:
    llave = _llave(("tenant_id", "case_id"), ("tenant_id", "case_id"))

    miradas, fallos = rls_assertion.check_foreign_keys(
        [llave], ["disclosure_record", "case_record"]
    )

    assert miradas == ("disclosure_record_del_caso",)
    assert fallos == ()


def test_una_llave_de_una_sola_columna_entre_tablas_aisladas_falla_nombrandola() -> None:
    """Las llaves foraneas no pasan por las politicas: sin la aseguradora, se cruzan."""
    llave = _llave(("case_id",), ("case_id",))

    _, fallos = rls_assertion.check_foreign_keys([llave], ["disclosure_record", "case_record"])

    assert [f.constraint for f in fallos] == ["disclosure_record_del_caso"]
    assert "tenant_id" in fallos[0].reason


def test_la_aseguradora_en_otra_posicion_tampoco_basta() -> None:
    """`(tenant_id, case_id) -> (case_id, tenant_id)` empareja la aseguradora con un caso."""
    llave = _llave(("tenant_id", "case_id"), ("case_id", "tenant_id"))

    _, fallos = rls_assertion.check_foreign_keys([llave], ["disclosure_record", "case_record"])

    assert len(fallos) == 1


def test_una_llave_desde_una_tabla_excluida_no_se_exige() -> None:
    """El libro mayor del gasto nombra un caso y no esta separado por aseguradora (BR7.2)."""
    llave = _llave(("case_ref",), ("case_id",), tabla="spend_entry")

    miradas, fallos = rls_assertion.check_foreign_keys([llave], ["case_record"])

    assert miradas == ()
    assert fallos == ()


def test_un_fallo_de_llave_pone_el_informe_en_rojo_y_se_lee_en_sus_lineas() -> None:
    llave = _llave(("case_id",), ("case_id",))
    _, fallos = rls_assertion.check_foreign_keys([llave], ["disclosure_record", "case_record"])
    informe = replace(
        rls_assertion.evaluate([TABLA_CORRECTA], ROL_SIN_SALTO, []), foreign_key_failures=fallos
    )

    assert not informe.ok
    assert any("disclosure_record -> case_record" in linea for linea in informe.lines())


async def test_las_llaves_del_esquema_real_llevan_la_aseguradora(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Contra el catalogo vivo: la consulta lee las columnas en el orden de la llave."""
    async with session.unscoped_session() as sesion:
        llaves = {
            llave.constraint: llave for llave in await rls_assertion.read_foreign_keys(sesion)
        }

    assert llaves["disclosure_record_del_caso"].columns == ("tenant_id", "case_id")
    assert llaves["guard_intervention_de_su_turno"].referenced_columns == ("tenant_id", "turn_id")
    informe = await rls_assertion.assert_rls_complete()
    assert informe.foreign_key_failures == (), informe.lines()
    assert "case_field_del_caso" in informe.checked_foreign_keys
