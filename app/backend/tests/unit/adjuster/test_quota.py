"""El tope diario de casos del ajustador: el limite sale de su configuracion y llega a la cuota."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from untangle.adjuster import config, quota
from untangle.telemetry.spend import api as spend_api
from untangle.telemetry.spend.api import QuotaState
from untangle.telemetry.spend.models import SITE_SUBJECT, QuotaDecision, QuotaReason, QuotaScope

CONFIGURACION = config.AdjusterConfig.model_validate(
    {
        "config_version": 1,
        "max_searches": 3,
        "allowed_domains": ["fasecolda.com"],
        "daily_case_cap": 7,
        "attempts": 3,
        "vehicle_value_range_cop": [8_000_000, 800_000_000],
    }
)
AHORA = datetime(2026, 11, 3, 15, 0, tzinfo=UTC)


async def test_reservar_un_caso_cuenta_en_el_cupo_del_sitio_con_el_tope_de_su_configuracion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llamadas: list[dict[str, Any]] = []

    async def check_quota(scope: QuotaScope, subject: str, **kwargs: Any) -> QuotaDecision:
        llamadas.append({"scope": scope, "subject": subject, **kwargs})
        return QuotaDecision(allowed=True)

    monkeypatch.setattr(spend_api, "check_quota", check_quota)

    decision = await quota.reserve_case(CONFIGURACION, now=AHORA)

    assert decision.allowed
    assert llamadas == [
        {
            "scope": QuotaScope.ADJUSTER_CASES_SITE_DAY,
            "subject": SITE_SUBJECT,
            "now": AHORA,
            "limit": 7,
        }
    ]


async def test_una_negacion_es_un_valor_con_su_motivo_y_no_una_excepcion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def check_quota(scope: QuotaScope, subject: str, **kwargs: Any) -> QuotaDecision:
        del scope, subject, kwargs
        return QuotaDecision(
            allowed=False, reason_code=QuotaReason.RATE_LIMITED_SITE, retry_after_seconds=3600
        )

    monkeypatch.setattr(spend_api, "check_quota", check_quota)

    decision = await quota.reserve_case(CONFIGURACION)

    assert not decision.allowed
    assert decision.reason_code is QuotaReason.RATE_LIMITED_SITE
    assert decision.retry_after_seconds == 3600


async def test_consultar_lo_de_hoy_no_consume_y_dice_cuantos_quedan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pedidos: list[dict[str, Any]] = []

    async def quota_state(scope: QuotaScope, subject: str, **kwargs: Any) -> QuotaState:
        pedidos.append({"scope": scope, "subject": subject, **kwargs})
        return QuotaState(count=5, limit=kwargs["limit"])

    async def check_quota(*args: Any, **kwargs: Any) -> QuotaDecision:  # pragma: no cover
        msg = "consultar no debe consumir"
        raise AssertionError(msg)

    monkeypatch.setattr(spend_api, "quota_state", quota_state)
    monkeypatch.setattr(spend_api, "check_quota", check_quota)

    hoy = await quota.cases_today(CONFIGURACION, now=AHORA)

    assert (hoy.used, hoy.limit, hoy.remaining) == (5, 7, 2)
    assert pedidos[0]["scope"] is QuotaScope.ADJUSTER_CASES_SITE_DAY
    assert pedidos[0]["limit"] == 7


def test_pasado_el_tope_no_quedan_casos_y_nunca_son_negativos() -> None:
    assert quota.CasesToday(used=9, limit=7).remaining == 0
