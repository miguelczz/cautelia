"""Que valores se abren para leer de vuelta un bloque (`stated_values_for_readback`).

Un bloque de varios campos se completa **en el turno que trae el ultimo**, y en el turno
anterior su lectura todavia no estaba debida. La funcion elegia "el primer bloque cuya lectura
esta debida" y devolvia nada, asi que la lectura nombraba solo el campo de ese turno y dejaba el
resto en blanco. Con los dos campos de «cuando y donde» pasaba de largo; con los cuatro o seis de
un bloque de la solicitud (U19), que se preguntan de a uno, pasaria siempre.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from untangle.case_record import api as casos
from untangle.case_record.models import Completeness, RecordType
from untangle.orchestration import case_context


def _completitud(
    tipo: RecordType, *, hechos: Sequence[str], esperando: Sequence[str]
) -> Completeness:
    from untangle.case_record import fields

    claves = [d.key for d in fields.definitions_for(tipo)]
    por_campo = {k: k in hechos for k in claves}
    return Completeness(
        per_field=por_campo,
        awaiting_readback=frozenset(esperando),
        complete=sum(por_campo.values()),
        total=len(claves),
    )


@pytest.fixture
def abiertos(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    """Registra las claves que se pidieron abrir, sin tocar la base."""
    pedidos: list[tuple[str, ...]] = []

    async def _abrir(
        _tenant: str, _case: str, claves: tuple[str, ...], *, cipher: object
    ) -> dict[str, str]:
        pedidos.append(claves)
        return dict.fromkeys(claves, "x")

    monkeypatch.setattr(casos, "open_field_values", _abrir)
    return pedidos


async def test_la_solicitud_abre_todos_sus_campos_para_su_unica_lectura(
    abiertos: list[tuple[str, ...]],
) -> None:
    """Desde el 2026-10-08 la solicitud se confirma de una vez: su lectura nombra los campos
    de todos sus bloques, y con solo los del primero diria una frase a medias."""
    completitud = _completitud(
        RecordType.QUOTE_REQUEST, hechos=[], esperando=["driver_name", "driver_birth_date"]
    )

    valores = await case_context.stated_values_for_readback(
        "sunmeadow",
        "C-1",
        RecordType.QUOTE_REQUEST,
        completitud,
        cipher=object(),  # type: ignore[arg-type]
    )

    [pedidos] = abiertos
    assert {"driver_name", "license_jurisdiction", "vin", "prior_coverage_active"} <= set(pedidos)
    assert set(valores) == set(pedidos)


async def test_con_un_bloque_ya_confirmado_la_lectura_sigue_abriendo_toda_la_solicitud(
    abiertos: list[tuple[str, ...]],
) -> None:
    completitud = _completitud(
        RecordType.QUOTE_REQUEST,
        hechos=["driver_name", "driver_birth_date", "license_years", "license_jurisdiction"],
        esperando=["vehicle_year"],
    )

    await case_context.stated_values_for_readback(
        "sunmeadow",
        "C-1",
        RecordType.QUOTE_REQUEST,
        completitud,
        cipher=object(),  # type: ignore[arg-type]
    )

    assert "vehicle_year" in abiertos[0]
    assert "driver_name" in abiertos[0]


async def test_cuando_y_donde_de_un_siniestro_tambien_abre_los_dos_campos(
    abiertos: list[tuple[str, ...]],
) -> None:
    """El caso del siniestro que la correccion tambien arregla: el lugar esperando su lectura
    y la fecha por decir en este turno."""
    completitud = _completitud(
        RecordType.CLAIM,
        hechos=["identity_and_policy", "injuries", "description"],
        esperando=["location"],
    )

    await case_context.stated_values_for_readback(
        "knotwell",
        "C-1",
        RecordType.CLAIM,
        completitud,
        cipher=object(),  # type: ignore[arg-type]
    )

    assert set(abiertos[0]) == {"incident_datetime", "location"}


async def test_sin_nada_esperando_su_lectura_no_se_abre_nada(
    abiertos: list[tuple[str, ...]],
) -> None:
    completitud = _completitud(RecordType.QUOTE_REQUEST, hechos=[], esperando=[])

    valores = await case_context.stated_values_for_readback(
        "sunmeadow",
        "C-1",
        RecordType.QUOTE_REQUEST,
        completitud,
        cipher=object(),  # type: ignore[arg-type]
    )

    assert valores == {}
    assert abiertos == []
