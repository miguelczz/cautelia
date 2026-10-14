"""La linea de resumen que imprime el comando de evaluaciones, con la latencia del chat.

Quien corre las evaluaciones ve aqui, antes de publicar nada, lo que la linea base va a decir:
la latencia por idioma con su recuento, y si el recuento no alcanza, que no se publica.
"""

from __future__ import annotations

from untangle.evals.cli import summarize
from untangle.evals.latency_summary import ChannelLatency, LatencySummary
from untangle.evals.models import Channel

from .gates.builders import fila, reporte


def _reporte_con(canal: ChannelLatency):  # type: ignore[no-untyped-def]
    return reporte((fila("DS-2/es/1"),), subset=None).evolve(latencies={Channel.CHAT: canal})


def test_el_resumen_dice_la_latencia_por_idioma_con_su_recuento() -> None:
    canal = ChannelLatency(
        datasets=("DS-2",),
        es=LatencySummary(turns=52, p50_ms=1180, p95_ms=2810),
        en=LatencySummary(turns=47, p50_ms=1420, p95_ms=3090),
    )

    texto = summarize(_reporte_con(canal))

    assert "latencia del chat, es: p50 1180 ms, p95 2810 ms sobre 52 turnos" in texto
    assert "latencia del chat, en: p50 1420 ms, p95 3090 ms sobre 47 turnos" in texto


def test_con_pocos_turnos_el_resumen_avisa_que_no_se_publica() -> None:
    canal = ChannelLatency(
        datasets=("DS-2",),
        es=LatencySummary(turns=7, p50_ms=900, p95_ms=2100),
        en=LatencySummary(),
    )

    texto = summarize(_reporte_con(canal))

    assert (
        "latencia del chat, es: p50 900 ms, p95 2100 ms sobre 7 turnos (menos de 20: no se publica)"
        in texto
    )
    assert "latencia del chat, en: ningun turno medido" in texto


def test_una_corrida_que_no_converso_no_imprime_latencias() -> None:
    texto = summarize(reporte((fila("DS-2/es/1"),), subset=None))

    assert "latencia" not in texto
