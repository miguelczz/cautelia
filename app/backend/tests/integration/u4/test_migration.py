"""Lo que la revision de U4 promete y la base tiene que cumplir.

Tres garantias que no viven en Python: la cascada, el historial de solo anexar y
el cierre completo. Se prueban contra la base porque es la base quien las
impone, y una garantia estructural que nadie ejercita es una linea de SQL que se
cree que funciona.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import sqlalchemy.exc

from untangle.tenancy import ephemeral, session

AHORA = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)

CREAR_CASO = """
    INSERT INTO case_record (case_id, tenant_id, case_number, record_type,
                             state, channel, origin, language, created_at, updated_at)
    VALUES (:case_id, 'stonecroft', :numero, 'claim', :estado, 'chat',
            'public_chat', 'es', :ahora, :ahora)
"""


async def _crear_caso(case_id: str, numero: str, estado: str = "capturing") -> None:
    async with session.session_for("stonecroft") as sesion:
        await session.execute_sql(
            sesion, CREAR_CASO, case_id=case_id, numero=numero, estado=estado, ahora=AHORA
        )


async def test_el_historial_no_se_puede_editar(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """SEC-U4.11: de solo anexar, y lo impone la base y no la costumbre.

    Para corregir un campo se anexa otra entrada. Editar la anterior borraria el
    rastro de quien lo cambio, que es justo lo que el historial existe para
    guardar.
    """
    await _crear_caso("CASO-1", "STO-000001")
    async with session.session_for("stonecroft") as sesion:
        await session.execute_sql(
            sesion,
            """
            INSERT INTO case_change (change_id, tenant_id, case_id, change_kind,
                                     field_key, actor_type, changed_at)
            VALUES ('CAMBIO-1', 'stonecroft', 'CASO-1', 'field_set', 'location',
                    'agent', :ahora)
            """,
            ahora=AHORA,
        )

    with pytest.raises(sqlalchemy.exc.DatabaseError) as error:
        async with session.session_for("stonecroft") as sesion:
            await session.execute_sql(
                sesion, "UPDATE case_change SET detail = 'otra cosa' WHERE change_id = 'CAMBIO-1'"
            )

    assert "solo anexar" in str(error.value)


async def test_el_historial_si_se_puede_borrar_con_su_caso(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """La asimetria es deliberada: el reinicio nocturno tiene que poder borrar.

    Lo que la regla prohibe es que una entrada **cambie**, no que la retencion
    acotada se cumpla. Un historial que tampoco se pudiera borrar convertiria la
    marca de dato de visitante en una promesa imposible.
    """
    await _crear_caso("CASO-1", "STO-000001")
    async with session.session_for("stonecroft") as sesion:
        await session.execute_sql(
            sesion,
            """
            INSERT INTO case_change (change_id, tenant_id, case_id, change_kind,
                                     field_key, actor_type, changed_at)
            VALUES ('CAMBIO-1', 'stonecroft', 'CASO-1', 'field_set', 'location',
                    'agent', :ahora)
            """,
            ahora=AHORA,
        )
        await session.execute_sql(sesion, "DELETE FROM case_record WHERE case_id = 'CASO-1'")
        fila = await session.fetch_one(sesion, "SELECT count(*) AS total FROM case_change")

    assert fila is not None
    assert int(fila["total"]) == 0


async def test_un_caso_no_llega_a_cerrado_sin_su_evidencia(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """SEC-U4.13 por debajo del codigo: "cerrado" no es un estado alcanzable
    sin resolucion, sin fecha y sin los cinco adjuntos.

    La validacion de cierre vive en la logica de negocio, donde puede decir cual
    adjunto falto. Esto es la red de abajo: el dia que una ruta nueva escriba en
    la tabla sin pasar por ella, la base la para.
    """
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await _crear_caso("CASO-2", "STO-000002", estado="closed")


async def test_un_numero_de_caso_con_otra_forma_no_entra(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """El numero es lo que una persona anota y dicta: tres letras, guion, seis
    digitos. Una fila con otra forma se leeria mal por telefono."""
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await _crear_caso("CASO-3", "sto-1")
