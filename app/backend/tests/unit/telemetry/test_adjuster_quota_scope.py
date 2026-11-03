"""El alcance de cuota del ajustador de IA: del sitio, con su limite por argumento y sin purga."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from untangle.telemetry.spend import api, purge, quota
from untangle.telemetry.spend.models import (
    DAILY_SCOPES,
    SITE_SCOPES,
    SITE_SUBJECT,
    QuotaCounter,
    QuotaReason,
    QuotaScope,
    derive_counter_key,
)

ESCOPE = QuotaScope.ADJUSTER_CASES_SITE_DAY
BOGOTA = ZoneInfo("America/Bogota")
AHORA = datetime(2026, 11, 3, 15, 0, tzinfo=UTC)


def test_todo_alcance_tiene_su_motivo_de_negacion() -> None:
    """Un alcance nuevo sin motivo caeria en una rama por defecto que dice lo primero."""
    assert set(quota._MOTIVO_POR_ALCANCE) == set(QuotaScope)


def test_el_tope_del_ajustador_es_diario_y_del_sitio() -> None:
    assert ESCOPE in DAILY_SCOPES
    assert ESCOPE in SITE_SCOPES
    assert {QuotaScope.VOICE_CALLS_SITE_DAY, ESCOPE} == SITE_SCOPES


def test_cuando_se_pasa_del_tope_dice_que_es_del_sitio_y_cuando_volver() -> None:
    cabe = quota.decide(ESCOPE, count=19, limit=20, now=AHORA, zone=BOGOTA)
    lleno = quota.decide(ESCOPE, count=20, limit=20, now=AHORA, zone=BOGOTA)

    assert cabe.allowed
    assert not lleno.allowed
    assert lleno.reason_code is QuotaReason.RATE_LIMITED_SITE
    # 15:00 UTC son las 10:00 en Bogota: faltan 14 horas para la medianoche.
    assert lleno.retry_after_seconds == 14 * 3600


def test_el_contador_del_ajustador_lleva_el_sujeto_del_sitio_y_ningun_otro() -> None:
    comienzo = quota.day_period_start(AHORA, BOGOTA)
    QuotaCounter(
        counter_key=derive_counter_key(ESCOPE, SITE_SUBJECT, comienzo),
        scope=ESCOPE,
        subject_key=SITE_SUBJECT,
        period_start=comienzo,
        limit_at_period_start=20,
        updated_at=AHORA,
    )

    with pytest.raises(ValidationError) as ajeno:
        QuotaCounter(
            counter_key=derive_counter_key(ESCOPE, "hash-de-navegador", comienzo),
            scope=ESCOPE,
            subject_key="hash-de-navegador",
            period_start=comienzo,
            limit_at_period_start=20,
            updated_at=AHORA,
        )
    assert SITE_SUBJECT in str(ajeno.value)


def test_el_reinicio_nocturno_no_borra_el_contador_del_ajustador() -> None:
    """Borrarlo cada noche le regalaria al dia siguiente el cupo ya gastado."""
    assert ESCOPE.value not in purge.ALCANCES_DE_VISITANTE
    assert QuotaScope.VOICE_CALLS_SITE_DAY.value not in purge.ALCANCES_DE_VISITANTE
    assert QuotaScope.CHAT_MESSAGES_DAY.value in purge.ALCANCES_DE_VISITANTE


def _periodo(limit: int | None) -> Any:
    runtime = cast(Any, SimpleNamespace(zone=BOGOTA))
    return api._periodo(ESCOPE, runtime, AHORA, None, None, limit=limit)


def test_el_limite_del_ajustador_llega_por_argumento_y_no_tiene_valor_por_defecto() -> None:
    periodo = _periodo(20)

    assert periodo.limit == 20
    assert periodo.period_start == datetime(2026, 11, 3, 0, 0, tzinfo=BOGOTA)

    with pytest.raises(ValueError, match=r"adjuster\.yaml"):
        _periodo(None)


def test_el_tope_del_ajustador_es_un_alcance_de_pago() -> None:
    """Cuesta dinero: con el presupuesto agotado o sin medir se cierra, y si el contador no se
    puede leer tambien."""
    assert ESCOPE in api._ALCANCES_DE_PAGO


def test_el_gasto_del_ajustador_se_nombra_en_la_actividad_de_operacion() -> None:
    """Ninguna de las otras cuatro actividades lo describe; una propia pide etiqueta en el panel."""
    from untangle.telemetry.spend import repository

    for consulta in (repository.GASTO_POR_DIA_Y_ACTIVIDAD, repository.SIN_PRECIO_POR_ACTIVIDAD):
        assert "WHEN use = 'adjuster' THEN 'operations'" in consulta
