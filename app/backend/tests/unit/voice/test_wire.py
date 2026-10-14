"""El protocolo del socket de voz (C-29). Ida y vuelta, y lo que se rechaza."""

from __future__ import annotations

import pytest

from untangle.copy_catalog.api import CopyKey
from untangle.voice import wire
from untangle.voice.models import CallState, EndReason

# --- Del navegador al servidor ------------------------------------------------


def test_el_cuadro_de_autenticacion_llega_tipado() -> None:
    cuadro = wire.from_client({"type": "auth", "token": "t-1"})
    # S106: no es una credencial, es el cuadro que se esta probando. El token
    # de verdad lo firma `voice.tokens` y su prueba esta en `test_tokens.py`.
    assert cuadro == wire.Auth(token="t-1")  # noqa: S106


def test_colgar_llega_tipado() -> None:
    assert wire.from_client({"type": "hangup"}) == wire.Hangup()


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "auth"},
        {"type": "auth", "token": ""},
        {"type": "auth", "token": 7},
        {"type": "audio", "data": "..."},
        {"type": "stop_audio"},
        {},
        "hangup",
        None,
        [{"type": "hangup"}],
    ],
)
def test_lo_que_no_es_un_cuadro_conocido_se_rechaza(payload: object) -> None:
    """Aceptar un cuadro desconocido saltandoselo dejaria al navegador creyendo
    que dijo algo que nadie escucho."""
    with pytest.raises(wire.UnknownFrameError):
        wire.from_client(payload)


def test_un_cuadro_del_servidor_no_se_acepta_como_entrante() -> None:
    """Los dos vocabularios son distintos y el entrante no conoce al saliente."""
    with pytest.raises(wire.UnknownFrameError):
        wire.from_client(wire.to_client(wire.StopAudio()))


# --- Del servidor al navegador ------------------------------------------------


def test_el_estado_viaja_con_su_valor() -> None:
    assert wire.to_client(wire.State(value=CallState.LIVE)) == {
        "type": "state",
        "value": "live",
    }


def test_el_estado_admite_los_dos_que_la_base_no_guarda() -> None:
    """`listening` y `speaking` son de la conversacion, no de la fila."""
    assert wire.to_client(wire.State(value="listening"))["value"] == "listening"
    assert wire.to_client(wire.State(value="speaking"))["value"] == "speaking"


def test_la_transcripcion_lleva_hablante_y_finalidad() -> None:
    cuadro = wire.to_client(wire.Transcript(speaker="insured", text="highway, exit 12", final=True))
    assert cuadro == {
        "type": "transcript",
        "speaker": "insured",
        "text": "highway, exit 12",
        "final": True,
    }


def test_la_parada_de_audio_no_lleva_nada_mas_que_su_tipo() -> None:
    assert wire.to_client(wire.StopAudio()) == {"type": "stop_audio"}


def test_el_caso_viaja_con_su_numero() -> None:
    assert wire.to_client(wire.Case(case_id="case-1", case_number="SUN482913")) == {
        "type": "case",
        "case_id": "case-1",
        "case_number": "SUN482913",
    }


def test_el_aviso_manda_la_clave_y_nunca_el_texto() -> None:
    """Una frase resuelta en los dos lados acaba diciendose de dos maneras."""
    cuadro = wire.to_client(wire.Notice(copy_key=CopyKey("voice.availability.not_configured")))
    assert cuadro == {"type": "notice", "copy_key": "voice.availability.not_configured"}
    assert "text" not in cuadro


def test_el_final_viaja_con_su_motivo() -> None:
    assert wire.to_client(wire.Ended(reason=EndReason.DROPPED)) == {
        "type": "ended",
        "reason": "dropped",
    }


def test_los_ocho_motivos_de_final_viajan() -> None:
    """Eran cinco hasta que el cierre por voz encontro el que faltaba: un
    reporte terminado no es ni colgar ni un silencio. El septimo es el caso que
    paso a un ajustador (2026-10-11) y el octavo, el que la persona pidio dejar
    guardado: la unica despedida deliberada que deja el caso retomable."""
    motivos = {wire.to_client(wire.Ended(reason=r))["reason"] for r in EndReason}
    assert motivos == {
        "hangup",
        "silence",
        "max_duration",
        "dropped",
        "error",
        "completed",
        "handed_off",
        "saved",
    }


def test_cada_cuadro_del_servidor_tiene_su_forma_y_ninguno_se_repite() -> None:
    """La union es cerrada: si entra un cuadro nuevo sin rama, esto se cae."""
    ejemplos: list[wire.ServerFrame] = [
        wire.State(value=CallState.ENDED),
        wire.Transcript(speaker="agent", text="ok", final=False),
        wire.StopAudio(),
        wire.Case(case_id="c", case_number="SUN000001"),
        wire.Notice(copy_key=CopyKey("voice.availability.misconfigured")),
        wire.Latency(turn_id="t-1", elapsed_ms=640),
        wire.Ended(reason=EndReason.HANGUP),
    ]
    tipos = [wire.to_client(c)["type"] for c in ejemplos]
    assert len(set(tipos)) == len(tipos)
    assert set(tipos) == {
        "state",
        "transcript",
        "stop_audio",
        "case",
        "notice",
        "latency",
        "ended",
    }


def test_el_cuadro_de_latencia_lleva_su_turno_y_sus_milisegundos() -> None:
    """Y el turno no es decoracion: sin el, la consola tendria que suponer que el
    ultimo cuadro es del ultimo turno."""
    assert wire.to_client(wire.Latency(turn_id="turno-7", elapsed_ms=640)) == {
        "type": "latency",
        "turn_id": "turno-7",
        "elapsed_ms": 640,
    }


def test_el_cuadro_de_latencia_lleva_la_medida_desde_la_ultima_palabra_si_existe() -> None:
    """Campo nuevo, opcional y aditivo: sin el, el cuadro viaja como siempre."""
    assert wire.to_client(
        wire.Latency(turn_id="turno-7", elapsed_ms=640, from_last_word_ms=1490)
    ) == {"type": "latency", "turn_id": "turno-7", "elapsed_ms": 640, "from_last_word_ms": 1490}
    assert "from_last_word_ms" not in wire.to_client(
        wire.Latency(turn_id="turno-7", elapsed_ms=640)
    )


def test_algo_que_no_es_un_cuadro_del_servidor_no_se_serializa() -> None:
    with pytest.raises(wire.UnknownFrameError):
        wire.to_client("state")  # type: ignore[arg-type]


def test_ningun_cuadro_lleva_audio() -> None:
    """El audio va en cuadros binarios: meterlo en JSON costaria un tercio mas."""
    ejemplos: list[wire.ServerFrame] = [
        wire.State(value=CallState.LIVE),
        wire.Transcript(speaker="agent", text="ok", final=True),
        wire.StopAudio(),
        wire.Ended(reason=EndReason.ERROR),
    ]
    for cuadro in ejemplos:
        assert "audio" not in wire.to_client(cuadro)
