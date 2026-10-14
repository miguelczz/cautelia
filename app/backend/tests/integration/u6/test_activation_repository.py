"""El repositorio y el purgador de la activacion, contra PostgreSQL de verdad (paso 6).

Lo que se prueba es la conducta que el repositorio promete y que solo el motor
puede cumplir: que la transaccion de dos escrituras cuenta cada hito una sola
vez por sesion (BR8.1), que dos aseguradoras no se ven (BR8.1 con NFR10.5), y
que el reinicio nocturno se lleva el avance y deja el conteo (BR8.2).

Las sesiones se crean con la funcion de U2 (`resolve_visitor_key`), nunca con un
resumen inventado: la tabla exige que la sesion sea una clave reconocida.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from untangle.telemetry.activation import repository
from untangle.telemetry.activation.models import ActivationDailyCount, ActivationMilestone
from untangle.telemetry.activation.purge import ACTIVATION_PURGER
from untangle.tenancy import session

from .conftest import AHORA, nueva_sesion

pytestmark = pytest.mark.usefixtures("activacion")

AVANCE_DE_LA_ASEGURADORA = "SELECT milestone FROM activation_progress"


def _conteos(tenant_id: str, filas: tuple[ActivationDailyCount, ...]) -> dict[str, int]:
    return {f.milestone.value: f.count for f in filas if f.tenant_id == tenant_id}


async def test_tres_registros_del_mismo_hito_en_la_misma_sesion_dan_un_solo_conteo(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR8.1: el primer registro cuenta y los dos siguientes no hacen nada."""
    primera, _ = dos_aseguradoras
    visita = await nueva_sesion(primera)

    contados = [
        await repository.record(
            tenant_id=primera,
            visitor_key_hash=visita.visitor_key_hash,
            milestone=ActivationMilestone.FIRST_MESSAGE,
            reached_at=AHORA + timedelta(seconds=intento),
        )
        for intento in range(3)
    ]

    assert contados == [True, False, False]
    assert _conteos(primera, await repository.daily_counts()) == {"first_message": 1}


async def test_dos_sesiones_con_el_mismo_hito_suman_dos_y_cada_hito_cuenta_aparte(
    dos_aseguradoras: tuple[str, str],
) -> None:
    primera, _ = dos_aseguradoras
    una = await nueva_sesion(primera)
    otra = await nueva_sesion(primera)

    for visita in (una, otra):
        await repository.record(
            tenant_id=primera,
            visitor_key_hash=visita.visitor_key_hash,
            milestone=ActivationMilestone.FIRST_MESSAGE,
            reached_at=AHORA,
        )
    await repository.record(
        tenant_id=primera,
        visitor_key_hash=una.visitor_key_hash,
        milestone=ActivationMilestone.THIRD_TURN,
        reached_at=AHORA,
    )

    assert _conteos(primera, await repository.daily_counts()) == {
        "first_message": 2,
        "third_turn": 1,
    }


async def test_dos_aseguradoras_no_se_ven_ni_en_el_avance_ni_en_el_conteo(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La misma clave en las dos, a proposito: la colision es lo que el aislamiento resiste."""
    primera, segunda = dos_aseguradoras
    clave = "clave-compartida-del-repositorio-u6"
    de_la_primera = await nueva_sesion(primera, visitor_key=clave)
    de_la_segunda = await nueva_sesion(segunda, visitor_key=clave)

    await repository.record(
        tenant_id=primera,
        visitor_key_hash=de_la_primera.visitor_key_hash,
        milestone=ActivationMilestone.LOOP_CLOSED,
        reached_at=AHORA,
    )
    # La misma sesion en la otra aseguradora **cuenta de nuevo**: es otra sesion,
    # igual que la clave es otra fila en U2 (BR3.5 de U2).
    contado_en_la_segunda = await repository.record(
        tenant_id=segunda,
        visitor_key_hash=de_la_segunda.visitor_key_hash,
        milestone=ActivationMilestone.LOOP_CLOSED,
        reached_at=AHORA,
    )

    async with session.session_for(segunda) as sesion:
        avance_visto_por_la_segunda = await session.fetch_all(sesion, AVANCE_DE_LA_ASEGURADORA)

    conteos = await repository.daily_counts()
    assert contado_en_la_segunda is True
    assert len(avance_visto_por_la_segunda) == 1
    assert _conteos(primera, conteos) == {"loop_closed": 1}
    assert _conteos(segunda, conteos) == {"loop_closed": 1}


async def test_el_dia_del_conteo_es_el_dia_en_utc(dos_aseguradoras: tuple[str, str]) -> None:
    """Las 23:30 en Bogota ya son el dia siguiente en UTC, y ahi cuenta."""
    primera, _ = dos_aseguradoras
    visita = await nueva_sesion(primera)
    bogota = timezone(timedelta(hours=-5))

    await repository.record(
        tenant_id=primera,
        visitor_key_hash=visita.visitor_key_hash,
        milestone=ActivationMilestone.FIRST_MESSAGE,
        reached_at=datetime(2026, 9, 21, 23, 30, tzinfo=bogota),
    )

    [fila] = [f for f in await repository.daily_counts() if f.tenant_id == primera]
    assert fila.day == date(2026, 9, 22)


async def test_un_instante_sin_zona_horaria_se_rechaza_antes_de_tocar_la_base(
    dos_aseguradoras: tuple[str, str],
) -> None:
    primera, _ = dos_aseguradoras
    visita = await nueva_sesion(primera)

    with pytest.raises(ValueError, match="zona horaria"):
        await repository.record(
            tenant_id=primera,
            visitor_key_hash=visita.visitor_key_hash,
            milestone=ActivationMilestone.FIRST_MESSAGE,
            # Sin zona horaria, a proposito: es justo lo que se prueba.
            reached_at=datetime(2026, 9, 21, 12, 0),
        )

    assert await repository.daily_counts() == ()


async def test_el_purgador_borra_el_avance_y_conserva_el_conteo(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR8.2 y NFR19.3: tras el reinicio no queda avance; el conteo sigue entero."""
    primera, segunda = dos_aseguradoras
    for tenant_id in (primera, segunda):
        visita = await nueva_sesion(tenant_id)
        await repository.record(
            tenant_id=tenant_id,
            visitor_key_hash=visita.visitor_key_hash,
            milestone=ActivationMilestone.FIRST_MESSAGE,
            reached_at=AHORA,
        )
    conteo_antes = await repository.daily_counts()

    resultado = await ACTIVATION_PURGER.purge(older_than=AHORA + timedelta(hours=1))

    for tenant_id in (primera, segunda):
        async with session.session_for(tenant_id) as sesion:
            assert await session.fetch_all(sesion, AVANCE_DE_LA_ASEGURADORA) == ()
    assert resultado.deleted == 2
    assert resultado.kept == 2
    assert await repository.daily_counts() == conteo_antes


async def test_el_purgador_respeta_el_corte_y_en_ensayo_no_borra(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Solo se va lo anterior al corte; en ensayo se cuenta y no se toca nada."""
    primera, _ = dos_aseguradoras
    vieja = await nueva_sesion(primera)
    reciente = await nueva_sesion(primera)
    for visita, momento in ((vieja, AHORA - timedelta(days=1)), (reciente, AHORA)):
        await repository.record(
            tenant_id=primera,
            visitor_key_hash=visita.visitor_key_hash,
            milestone=ActivationMilestone.FIRST_MESSAGE,
            reached_at=momento,
        )

    ensayo = await ACTIVATION_PURGER.purge(older_than=AHORA - timedelta(hours=1), dry_run=True)
    async with session.session_for(primera) as sesion:
        tras_el_ensayo = await session.fetch_all(sesion, AVANCE_DE_LA_ASEGURADORA)

    real = await ACTIVATION_PURGER.purge(older_than=AHORA - timedelta(hours=1))
    async with session.session_for(primera) as sesion:
        tras_el_borrado = await session.fetch_all(sesion, AVANCE_DE_LA_ASEGURADORA)

    assert ensayo.deleted == 1
    assert len(tras_el_ensayo) == 2
    assert real.deleted == 1
    assert len(tras_el_borrado) == 1
