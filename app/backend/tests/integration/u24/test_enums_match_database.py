"""Cada valor de un enum cerrado que la base enumera en una restriccion esta en la base.

Sale de la leccion de `u8_policy_0002_uso_corpus`: un valor nuevo de `Use` sin su migracion hizo
que cada llamada de embeddings fallara al anotarse, y el libro traga esa excepcion a proposito.
Aqui se lee la definicion **viva** de cada restriccion y se exige que nombre todos los valores del
enum, asi que un valor que se anade sin migracion falla en esta prueba y no semanas despues en la
salida de un comando.

Contra PostgreSQL de verdad: lo que se comprueba es lo que el motor tiene, no lo que la revision
dice que dejo.
"""

from __future__ import annotations

from enum import StrEnum

import pytest

from untangle.base import UnitKind, Use
from untangle.case_record.models import ActorType
from untangle.telemetry.spend.models import QuotaScope
from untangle.tenancy import session

pytestmark = pytest.mark.usefixtures("sesiones")

DEFINICION = """
    SELECT pg_get_constraintdef(oid) AS definicion
    FROM pg_constraint
    WHERE conname = :nombre
"""


async def _definicion(nombre: str) -> str:
    async with session.unscoped_session() as sesion:
        fila = await session.fetch_one(sesion, DEFINICION, nombre=nombre)
    assert fila is not None, f"la base no tiene la restriccion '{nombre}'"
    return str(fila["definicion"])


@pytest.mark.parametrize(
    ("restriccion", "enum"),
    [
        ("spend_entry_uso_valido", Use),
        ("spend_entry_unidad_valida", UnitKind),
        ("case_change_actor_valido", ActorType),
        ("quota_counter_alcance_valido", QuotaScope),
    ],
)
async def test_la_restriccion_nombra_todos_los_valores_del_enum(
    restriccion: str, enum: type[StrEnum]
) -> None:
    definicion = await _definicion(restriccion)

    faltan = [valor.value for valor in enum if f"'{valor.value}'" not in definicion]
    assert faltan == [], f"{restriccion} no acepta: {faltan}"


async def test_los_valores_nuevos_del_ajustador_estan_en_la_base() -> None:
    assert "'adjuster'" in await _definicion("spend_entry_uso_valido")
    assert "'web_searches'" in await _definicion("spend_entry_unidad_valida")
    assert "'adjuster_ai'" in await _definicion("case_change_actor_valido")
    assert "'adjuster_cases_site_day'" in await _definicion("quota_counter_alcance_valido")
