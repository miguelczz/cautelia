"""La superficie de la activacion, sin base (BR8.3, BR8.4, OBS-U6.4, OBS-U6.6).

El repositorio se sustituye para provocar lo que con una base de verdad costaria
reproducir: una base que no esta, una que tarda, una que rechaza. Lo que se
prueba es que hace la superficie con cada cosa: **nunca lanza, nunca demora mas
que su presupuesto, y siempre deja su evento sin nombrar la sesion**.

Que el conteo de verdad sea uno por sesion lo prueban las de integracion, contra
PostgreSQL.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError

from untangle.base import Use
from untangle.telemetry.activation import api as activation
from untangle.telemetry.activation import repository
from untangle.telemetry.traces import api as trazas
from untangle.tenancy.models import SessionNotConfiguredError, UnknownTenantError

from ..web.eventos import Eventos

AHORA = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
#: Un resumen con la forma de uno de verdad. No viene de ninguna persona.
RESUMEN = "a" * 64


def _registro(resultado: bool | BaseException | float) -> tuple[list[dict[str, Any]], Any]:
    """Un repositorio sustituto: devuelve, levanta, o tarda esos segundos."""
    llamadas: list[dict[str, Any]] = []

    async def record(**campos: Any) -> bool:
        llamadas.append(campos)
        if isinstance(resultado, BaseException):
            raise resultado
        if isinstance(resultado, float):
            await asyncio.sleep(resultado)
            return True
        return resultado

    return llamadas, record


async def _informar(source: activation.ActivationSource) -> activation.MilestoneOutcome:
    return await activation.record_milestone(
        tenant_id="stonecroft",
        visitor_key_hash=RESUMEN,
        milestone=activation.ActivationMilestone.FIRST_MESSAGE,
        source=source,
        now=AHORA,
    )


async def test_el_primer_registro_cuenta_y_el_repetido_no(monkeypatch: pytest.MonkeyPatch) -> None:
    llamadas, record = _registro(True)
    monkeypatch.setattr(repository, "record", record)
    assert (
        await _informar(activation.ActivationSource.VISITOR) is activation.MilestoneOutcome.COUNTED
    )
    assert llamadas == [
        {
            "tenant_id": "stonecroft",
            "visitor_key_hash": RESUMEN,
            "milestone": activation.ActivationMilestone.FIRST_MESSAGE,
            "reached_at": AHORA,
        }
    ]

    _, ya_estaba = _registro(False)
    monkeypatch.setattr(repository, "record", ya_estaba)
    resultado = await _informar(activation.ActivationSource.VISITOR)
    assert resultado is activation.MilestoneOutcome.ALREADY_REACHED


@pytest.mark.parametrize(
    "fuente",
    [activation.ActivationSource.HEALTH_CHECK, activation.ActivationSource.EVAL_RUNNER],
)
async def test_el_chequeo_y_el_corredor_no_cuentan_como_sesion(
    monkeypatch: pytest.MonkeyPatch, fuente: activation.ActivationSource
) -> None:
    """BR8.4: ni siquiera llegan al repositorio."""
    llamadas, record = _registro(True)
    monkeypatch.setattr(repository, "record", record)

    resultado = await _informar(fuente)

    assert resultado is activation.MilestoneOutcome.NOT_A_SESSION
    assert llamadas == []


async def test_con_la_base_caida_el_turno_sigue_y_queda_el_evento_sin_la_sesion(
    monkeypatch: pytest.MonkeyPatch, eventos: Eventos
) -> None:
    """BR8.3 y REL-U6.3: no lanza; OBS-U6.4 y OBS-U6.6: evento con tipo y sin resumen."""
    caida = OperationalError("INSERT ...", {}, ConnectionRefusedError("refused"))
    _, record = _registro(caida)
    monkeypatch.setattr(repository, "record", record)

    resultado = await _informar(activation.ActivationSource.VISITOR)

    assert resultado is activation.MilestoneOutcome.FAILED
    [evento] = [e for e in eventos() if e["event"] == "activation.milestone_failed"]
    assert evento["milestone"] == "first_message"
    assert evento["error_kind"] == "unavailable"
    assert evento["error_type"] == "OperationalError"
    assert RESUMEN not in str(eventos())


async def test_una_base_lenta_no_demora_el_turno_mas_que_su_presupuesto(
    monkeypatch: pytest.MonkeyPatch, eventos: Eventos
) -> None:
    """BR8.3: una escritura colgada se corta; el turno espera como mucho eso."""
    _, record = _registro(5.0)
    monkeypatch.setattr(repository, "record", record)

    inicio = time.perf_counter()
    resultado = await _informar(activation.ActivationSource.VISITOR)
    transcurrido = time.perf_counter() - inicio

    assert resultado is activation.MilestoneOutcome.FAILED
    assert transcurrido < activation.RECORD_TIMEOUT_S + 0.2
    [evento] = [e for e in eventos() if e["event"] == "activation.milestone_failed"]
    assert evento["error_kind"] == "timeout"


async def test_el_evento_lleva_la_traza_del_turno_que_informo(
    monkeypatch: pytest.MonkeyPatch, eventos: Eventos
) -> None:
    """El fallo se cruza con el turno por su traza, no por la sesion."""
    _, record = _registro(RuntimeError("inesperado"))
    monkeypatch.setattr(repository, "record", record)
    traza = "0" * 31 + "7"

    with trazas.turn_span(tenant_id="stonecroft", case_id="CASE-1", use=Use.CHAT, trace_id=traza):
        resultado = await _informar(activation.ActivationSource.VISITOR)

    assert resultado is activation.MilestoneOutcome.FAILED
    [evento] = [e for e in eventos() if e["event"] == "activation.milestone_failed"]
    assert evento["trace_id"] == traza
    assert evento["error_kind"] == "unexpected"


@pytest.mark.parametrize(
    ("error", "tipo"),
    [
        (TimeoutError(), activation.RecordFailure.TIMEOUT),
        (IntegrityError("INSERT ...", {}, Exception("fk")), activation.RecordFailure.REJECTED),
        (UnknownTenantError("no existe"), activation.RecordFailure.REJECTED),
        (OperationalError("SELECT 1", {}, Exception("down")), activation.RecordFailure.UNAVAILABLE),
        (SessionNotConfiguredError("sin base"), activation.RecordFailure.UNAVAILABLE),
        (ConnectionRefusedError(), activation.RecordFailure.UNAVAILABLE),
        (ValueError("zona horaria"), activation.RecordFailure.UNEXPECTED),
    ],
)
def test_cada_fallo_cae_en_su_tipo_de_la_taxonomia_cerrada(
    error: BaseException, tipo: activation.RecordFailure
) -> None:
    """OBS-U6.4, con las excepciones reales del cliente de base y de U2."""
    assert activation.classify_failure(error) is tipo
