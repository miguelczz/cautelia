"""El libro mayor y la lista de proveedores dicen lo mismo (U15, `u15_speech_0001`).

`ProviderName` y la restriccion `spend_entry_proveedor_valido` enumeran los
proveedores en dos sitios, y durante una semana dijeron cosas distintas: la base
seguia aceptando `fallback_tts`, un lugar reservado por U5 que la enmienda del
2026-09-21 de ADR-008 dejo sin nada construido detras. Nadie lo noto porque un
valor aceptado de mas no rompe ninguna pantalla.

Son de integracion porque lo que se compara es **la base viva**, migrada hasta la
cabeza: leer la revision como texto comprobaria el archivo, no lo que el motor
aplica.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from untangle.base import ProviderName
from untangle.tenancy import ephemeral, session

RESTRICCION = "spend_entry_proveedor_valido"

_INSERTAR = """
    INSERT INTO spend_entry (
        entry_id, provider, model, use, tenant_ref, case_ref, units, unit_kind,
        unit_price_usd, price_list_version, price_list_effective_date, cost_usd,
        cost_status, billable, lane, source, occurred_at
    ) VALUES (
        :entrada, :proveedor, 'modelo-de-prueba', 'voice', NULL, NULL, 1, 'characters',
        NULL, NULL, NULL, NULL, 'not_measured', false, 'public', 'counted_locally', :ahora
    )
"""


@pytest.fixture
async def libro(sesiones: ephemeral.EphemeralDatabase) -> AsyncIterator[None]:
    """El libro mayor vacio antes y despues: la prueba escribe filas en el."""
    async with session.unscoped_session() as sesion:
        await session.execute_sql(sesion, "DELETE FROM spend_entry")
    yield
    async with session.unscoped_session() as sesion:
        await session.execute_sql(sesion, "DELETE FROM spend_entry")


async def _insertar(proveedor: str) -> None:
    async with session.unscoped_session() as sesion:
        await session.execute_sql(
            sesion,
            _INSERTAR,
            entrada=f"prueba-{uuid.uuid4().hex}",
            proveedor=proveedor,
            ahora=datetime(2026, 9, 21, 12, 0, tzinfo=UTC),
        )


async def test_la_restriccion_del_libro_enumera_exactamente_los_proveedores(libro: None) -> None:
    """La base y `ProviderName` dicen lo mismo: ni uno de mas ni uno de menos."""
    async with session.unscoped_session() as sesion:
        fila = await session.fetch_one(
            sesion,
            "SELECT pg_get_constraintdef(oid) AS definicion FROM pg_constraint "
            "WHERE conname = :nombre",
            nombre=RESTRICCION,
        )
    assert fila is not None, f"la restriccion '{RESTRICCION}' no existe en la base migrada"
    en_la_base = set(re.findall(r"'([^']+)'::", str(fila["definicion"])))
    assert en_la_base == {proveedor.value for proveedor in ProviderName}


async def test_el_libro_rechaza_el_proveedor_retirado(libro: None) -> None:
    """`fallback_tts` ya no describe nada construido y la base ya no lo acepta."""
    with pytest.raises(IntegrityError, match=RESTRICCION):
        await _insertar("fallback_tts")


async def test_el_libro_acepta_los_dos_proveedores_de_voz(libro: None) -> None:
    """Estrechar la restriccion no puede dejar fuera a quien si esta construido."""
    await _insertar(ProviderName.DEEPGRAM.value)
    await _insertar(ProviderName.CARTESIA.value)
    async with session.unscoped_session() as sesion:
        filas = await session.fetch_all(
            sesion, "SELECT provider FROM spend_entry ORDER BY provider"
        )
    assert [str(f["provider"]) for f in filas] == ["cartesia", "deepgram"]
