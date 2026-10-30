"""El borrado nocturno del caso completo (SEC-U4.4, SEC-U4.5, C-11).

Dos preguntas, y la segunda es la que se olvida: **que desaparece entero** y
**que se conserva**. Un purgador que borrara de mas pasaria la primera prueba
sin problema, y vaciaria el corpus de demostracion la primera noche.

El caso se siembra con las cinco tablas pobladas a proposito. Contar solo los
casos no comprobaria nada del "sin dejar huerfanos": un `DELETE` sobre la tabla
del caso que dejara los campos atras daria el mismo cero.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from untangle.case_record import crypto, purge
from untangle.tenancy import ephemeral, session

AYER = datetime(2026, 9, 19, 22, 0, tzinfo=UTC)
HOY = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)

TABLAS = ("case_record", "case_field", "case_party", "case_transcript_turn", "case_change")


@pytest.fixture
def cifrador(monkeypatch: pytest.MonkeyPatch) -> crypto.Cipher:
    monkeypatch.setenv(crypto.KEY_ENV_VAR, crypto.generate_key())
    return crypto.Cipher.from_settings()


async def _sembrar_caso(
    cifrador: crypto.Cipher,
    *,
    tenant_id: str,
    case_id: str,
    numero: str,
    origin: str,
) -> None:
    """Un caso con sus cinco tablas pobladas, por el punto unico de sesion."""
    async with session.session_for(tenant_id) as sesion:
        await session.execute_sql(
            sesion,
            """
            INSERT INTO case_record (case_id, tenant_id, case_number, record_type,
                                     state, channel, origin, language,
                                     created_at, updated_at)
            VALUES (:case_id, :tenant_id, :numero, 'claim', 'capturing',
                    'chat', :origin, 'es', :ayer, :ayer)
            """,
            case_id=case_id,
            tenant_id=tenant_id,
            numero=numero,
            origin=origin,
            ayer=AYER,
        )
        await session.execute_sql(
            sesion,
            """
            INSERT INTO case_field (case_id, tenant_id, field_key, value,
                                    sealed_key_id, status, evidence_turn_id, updated_at)
            VALUES (:case_id, :tenant_id, 'location', :valor, :clave,
                    'stated', :turno, :ayer)
            """,
            case_id=case_id,
            tenant_id=tenant_id,
            valor=bytes(cifrador.seal("Calle 42 con Carrera 7")),
            clave=cifrador.id,
            turno=f"{case_id}-turno-1",
            ayer=AYER,
        )
        await session.execute_sql(
            sesion,
            """
            INSERT INTO case_party (party_id, tenant_id, case_id, role, name,
                                    sealed_key_id, plate_status)
            VALUES (:party_id, :tenant_id, :case_id, 'witness', :nombre,
                    :clave, 'not_stated')
            """,
            party_id=f"{case_id}-parte-1",
            tenant_id=tenant_id,
            case_id=case_id,
            nombre=bytes(cifrador.seal("Nayibe Quintero Ospina")),
            clave=cifrador.id,
        )
        await session.execute_sql(
            sesion,
            """
            INSERT INTO case_transcript_turn (turn_id, tenant_id, case_id, speaker,
                                              channel, language, text_redacted, started_at)
            VALUES (:turn_id, :tenant_id, :case_id, 'insured', 'chat', 'es',
                    'Choque en [DIRECCION 1]', :ayer)
            """,
            turn_id=f"{case_id}-turno-1",
            tenant_id=tenant_id,
            case_id=case_id,
            ayer=AYER,
        )
        await session.execute_sql(
            sesion,
            """
            INSERT INTO case_change (change_id, tenant_id, case_id, change_kind,
                                     field_key, new_value, sealed_key_id,
                                     actor_type, changed_at)
            VALUES (:change_id, :tenant_id, :case_id, 'field_set', 'location',
                    :valor, :clave, 'agent', :ayer)
            """,
            change_id=f"{case_id}-cambio-1",
            tenant_id=tenant_id,
            case_id=case_id,
            valor=bytes(cifrador.seal("Calle 42 con Carrera 7")),
            clave=cifrador.id,
            ayer=AYER,
        )


async def _contar(tabla: str, tenant_id: str = "stonecroft") -> int:
    async with session.session_for(tenant_id) as sesion:
        fila = await session.fetch_one(sesion, f"SELECT count(*) AS total FROM {tabla}")  # noqa: S608
    return int(fila["total"]) if fila is not None else 0


# --- Lo que desaparece --------------------------------------------------------


async def test_el_caso_de_un_visitante_desaparece_entero(
    sesiones: ephemeral.EphemeralDatabase, cifrador: crypto.Cipher
) -> None:
    """SEC-U4.5: las cinco tablas quedan en cero, no solo la del caso.

    Se cuentan las cinco porque un borrado que dejara los campos atras daria el
    mismo cero en la primera, y un campo huerfano es un dato personal cifrado
    que ya nadie sabe a quien pertenecia ni cuando tocaba borrarlo.
    """
    await _sembrar_caso(
        cifrador,
        tenant_id="stonecroft",
        case_id="CASO-PUBLICO",
        numero="SA-1",
        origin="public_chat",
    )
    for tabla in TABLAS:
        assert await _contar(tabla) == 1, tabla

    resultado = await purge.CASE_RECORD_PURGER.purge(older_than=HOY)

    assert resultado.deleted == 1
    for tabla in TABLAS:
        assert await _contar(tabla) == 0, tabla


async def test_el_caso_de_la_consola_de_voz_tambien_se_borra(
    sesiones: ephemeral.EphemeralDatabase, cifrador: crypto.Cipher
) -> None:
    """Las dos superficies publicas cuentan, no solo el chat.

    Los origenes salen del modelo y no de una lista escrita en el purgador: una
    superficie publica nueva entra al borrado sola.
    """
    await _sembrar_caso(
        cifrador,
        tenant_id="stonecroft",
        case_id="CASO-VOZ",
        numero="SA-2",
        origin="public_voice_console",
    )

    resultado = await purge.CASE_RECORD_PURGER.purge(older_than=HOY)

    assert resultado.deleted == 1
    assert await _contar("case_record") == 0


# --- Lo que se conserva -------------------------------------------------------


async def test_el_caso_del_despliegue_local_se_conserva(
    sesiones: ephemeral.EphemeralDatabase, cifrador: crypto.Cipher
) -> None:
    """Es sintetico: borrarlo cada noche vaciaria el corpus de demostracion.

    Y la cifra viaja en `kept`, no en un silencio: un purgador que solo dijera
    cuanto borro no dejaria ver el dia que empezara a conservar de mas.
    """
    await _sembrar_caso(
        cifrador,
        tenant_id="stonecroft",
        case_id="CASO-LOCAL",
        numero="SA-3",
        origin="local_deployment",
    )

    resultado = await purge.CASE_RECORD_PURGER.purge(older_than=HOY)

    assert resultado.deleted == 0
    assert resultado.kept == 1
    assert await _contar("case_record") == 1
    assert await _contar("case_field") == 1


async def test_el_caso_de_hoy_sobrevive_al_reinicio_de_hoy(
    sesiones: ephemeral.EphemeralDatabase, cifrador: crypto.Cipher
) -> None:
    """El corte es por fecha y no por origen a secas: un caso abierto hace un
    rato sigue vivo, o el visitante perderia su caso a mitad de la conversacion."""
    await _sembrar_caso(
        cifrador,
        tenant_id="stonecroft",
        case_id="CASO-DE-HOY",
        numero="SA-4",
        origin="public_chat",
    )

    resultado = await purge.CASE_RECORD_PURGER.purge(older_than=AYER)

    assert resultado.deleted == 0
    assert await _contar("case_record") == 1


# --- El ensayo ----------------------------------------------------------------


async def test_el_ensayo_cuenta_sin_borrar(
    sesiones: ephemeral.EphemeralDatabase, cifrador: crypto.Cipher
) -> None:
    """Poder mirar antes de ejecutar un borrado es lo que lo hace revisable."""
    await _sembrar_caso(
        cifrador,
        tenant_id="stonecroft",
        case_id="CASO-PUBLICO",
        numero="SA-1",
        origin="public_chat",
    )

    ensayo = await purge.CASE_RECORD_PURGER.purge(older_than=HOY, dry_run=True)

    assert ensayo.deleted == 1
    assert await _contar("case_record") == 1


# --- El aislamiento no deja de aplicarse para borrar --------------------------


async def test_el_borrado_no_cruza_de_una_aseguradora_a_otra(
    sesiones: ephemeral.EphemeralDatabase, cifrador: crypto.Cipher
) -> None:
    """Recorre las aseguradoras una por una porque la politica de fila sigue
    puesta: sin aseguradora fijada, un borrado global borraria exactamente cero.

    Se siembran dos y se borran las dos, contadas por separado.
    """
    await _sembrar_caso(
        cifrador,
        tenant_id="stonecroft",
        case_id="CASO-STO",
        numero="SA-1",
        origin="public_chat",
    )
    await _sembrar_caso(
        cifrador,
        tenant_id="sunmeadow",
        case_id="CASO-SUN",
        numero="AP-1",
        origin="public_chat",
    )

    resultado = await purge.CASE_RECORD_PURGER.purge(older_than=HOY)

    assert resultado.deleted == 2
    assert await _contar("case_record", "stonecroft") == 0
    assert await _contar("case_record", "sunmeadow") == 0
