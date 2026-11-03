"""El tope diario de casos del ajustador, contra el contador de cuota de verdad.

Que reservar es consumir en un solo acto, que el limite lo manda quien llama y que un contador del
ajustador es del sitio entero y de nadie mas: lo que la base y el repositorio imponen, no lo que
el codigo cree.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from untangle.telemetry.spend import repository
from untangle.telemetry.spend.models import SITE_SUBJECT, QuotaPeriod, QuotaScope
from untangle.tenancy import session

from .conftest import AHORA

pytestmark = pytest.mark.usefixtures("dinero")

ALCANCE = QuotaScope.ADJUSTER_CASES_SITE_DAY


async def test_el_tope_deja_pasar_exactamente_los_casos_del_limite() -> None:
    periodo = QuotaPeriod(period_start=AHORA, limit=2)

    primero = await repository.consume_quota(ALCANCE, SITE_SUBJECT, periodo, now=AHORA)
    segundo = await repository.consume_quota(ALCANCE, SITE_SUBJECT, periodo, now=AHORA)
    tercero = await repository.consume_quota(ALCANCE, SITE_SUBJECT, periodo, now=AHORA)

    assert primero is not None
    assert segundo is not None
    assert segundo.count == 2
    assert segundo.limit_at_period_start == 2
    assert tercero is None, "el tercer caso del dia no cabe"


async def test_un_tope_de_cero_no_abre_el_periodo() -> None:
    periodo = QuotaPeriod(period_start=AHORA, limit=0)

    assert await repository.consume_quota(ALCANCE, SITE_SUBJECT, periodo, now=AHORA) is None


async def test_el_contador_del_ajustador_no_comparte_cuenta_con_el_de_la_voz() -> None:
    periodo = QuotaPeriod(period_start=AHORA, limit=1)

    del_ajustador = await repository.consume_quota(ALCANCE, SITE_SUBJECT, periodo, now=AHORA)
    de_la_voz = await repository.consume_quota(
        QuotaScope.VOICE_CALLS_SITE_DAY, SITE_SUBJECT, periodo, now=AHORA
    )

    assert del_ajustador is not None
    assert de_la_voz is not None, "gastar el cupo del ajustador no gasta el de la voz"


async def test_la_base_rechaza_un_contador_del_ajustador_de_un_visitante() -> None:
    """Un alcance del sitio lleva el sujeto `site`, y ningun visitante puede llamarse asi."""
    periodo = QuotaPeriod(period_start=AHORA, limit=5)

    with pytest.raises(IntegrityError) as rechazo:
        await repository.consume_quota(ALCANCE, "resumen-de-un-visitante", periodo, now=AHORA)

    assert "quota_counter_sitio_sin_dueno" in str(rechazo.value)


async def test_el_reinicio_nocturno_conserva_el_contador_del_ajustador() -> None:
    """Borrarlo cada noche le regalaria al dia siguiente el cupo ya gastado."""
    from datetime import timedelta

    from untangle.telemetry.spend import purge

    periodo = QuotaPeriod(period_start=AHORA, limit=3)
    await repository.consume_quota(ALCANCE, SITE_SUBJECT, periodo, now=AHORA)
    await repository.consume_quota(QuotaScope.CHAT_MESSAGES_DAY, "visitante", periodo, now=AHORA)

    resultado = await purge.SPEND_PURGER.purge(older_than=AHORA + timedelta(days=1))

    async with session.unscoped_session() as sesion:
        filas = await session.fetch_all(sesion, "SELECT scope FROM quota_counter")
    assert {str(f["scope"]) for f in filas} == {ALCANCE.value}
    assert resultado.deleted >= 1
