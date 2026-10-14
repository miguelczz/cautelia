"""La voz de respaldo, Aura-2, contra sus respuestas grabadas (BR4.1, BR1.4, BR5.1, BR6.1).

Las dos respuestas de contrato se capturaron el 2026-09-21 con `aura-2-celeste-es`
y `aura-2-thalia-en`. Lo que fijan: Deepgram contesta `audio/l16;rate=24000`,
que es el formato unico, y su cabecera `dg-char-count` dice **los mismos
caracteres** que cuenta el adaptador --54 y 40--, asi que el gasto que se
registra es el que el proveedor cobra.
"""

from __future__ import annotations

import copy
from decimal import Decimal
from typing import Any

import pytest

from untangle.base import Locale, ProviderErrorKind, ProviderName, SpendSource, UnitKind, Use
from untangle.providers.adapters.deepgram import DeepgramAuraTextToSpeech
from untangle.providers.adapters.speech_common import SpeechMisconfiguredError
from untangle.providers.ports import BudgetExhausted, ExhaustedResource, ProviderError, VoiceRef
from untangle.server.voice_cli import FRASES

from . import replay
from .apoyo import TIEMPOS, Abierto, Eventos, Registro, clientes, redactado, techo

VOCES = {
    "es": VoiceRef(
        provider=ProviderName.DEEPGRAM, model="aura-2", voice_id="aura-2-celeste-es", language="es"
    ),
    "en": VoiceRef(
        provider=ProviderName.DEEPGRAM, model="aura-2", voice_id="aura-2-thalia-en", language="en"
    ),
}


def _adaptador(
    fixture: dict[str, Any], *, gate: Any = None
) -> tuple[DeepgramAuraTextToSpeech, replay.ReplayTransport, Registro]:
    caller, transporte, _ = clientes(ProviderName.DEEPGRAM, fixture)
    registro = Registro()
    tts = DeepgramAuraTextToSpeech(
        caller, gate=gate if gate is not None else Abierto(), usage=registro, timeouts=TIEMPOS
    )
    return tts, transporte, registro


@pytest.mark.parametrize("idioma", ["es", "en"])
async def test_la_respuesta_grabada_cumple_el_contrato(idioma: Locale) -> None:
    """BR4.1 y BR6.1: PCM de 16 bits a 24 kHz, en muestras enteras, y el gasto exacto."""
    grabada = replay.load(f"deepgram-speak-aura-2-{idioma}")
    tts, transporte, registro = _adaptador(grabada)
    texto = redactado(FRASES[idioma], idioma)

    trozos = [t async for t in tts.synthesize(texto, voice=VOCES[idioma])]

    assert trozos
    assert all(len(t) % 2 == 0 for t in trozos)
    assert sum(len(t) for t in trozos) == 960 * len(grabada["received"])

    peticion = transporte.requests[0]
    assert peticion.path == "v1/speak"
    assert dict(peticion.query) == {
        "model": VOCES[idioma].voice_id,
        "encoding": "linear16",
        "sample_rate": "24000",
        "container": "none",
    }
    assert peticion.body == {"text": FRASES[idioma]}

    (reporte,) = registro.reports
    assert (reporte.provider, reporte.model, reporte.use) == (
        ProviderName.DEEPGRAM,
        "aura-2",
        Use.VOICE,
    )
    assert reporte.source is SpendSource.COUNTED_LOCALLY
    contados = reporte.units[0].units
    assert reporte.units[0].unit_kind is UnitKind.CHARACTERS
    # Lo que cuenta el adaptador es lo que cobra Deepgram.
    assert contados == Decimal(grabada["response"]["headers"]["dg-char-count"])


def _con(nombre: str, **cambios: Any) -> dict[str, Any]:
    grabada = copy.deepcopy(replay.load(nombre))
    grabada.update(cambios)
    return grabada


@pytest.mark.parametrize(
    ("fixture", "esperado", "caracteres"),
    [
        pytest.param(
            replay.load("deepgram-speak-unknown-voice"),
            ProviderErrorKind.UNAVAILABLE,
            0,
            id="voz-inexistente-403-capturada",
        ),
        pytest.param(
            replay.load("deepgram-speak-429-rate-limited"),
            ProviderErrorKind.RATE_LIMITED,
            0,
            id="429",
        ),
        pytest.param(
            replay.load("deepgram-speak-503-unavailable"),
            ProviderErrorKind.UNAVAILABLE,
            0,
            id="503",
        ),
        pytest.param(
            _con("deepgram-speak-aura-2-es", fail_after_chunks=1),
            ProviderErrorKind.TIMEOUT,
            54,
            id="se-corta-a-mitad",
        ),
        pytest.param(
            _con(
                "deepgram-speak-aura-2-es",
                response={"headers": {"content-type": "application/json"}},
            ),
            ProviderErrorKind.INVALID_RESPONSE,
            54,
            id="no-es-audio",
        ),
        pytest.param(
            _con("deepgram-speak-aura-2-es", received=[]),
            ProviderErrorKind.INVALID_RESPONSE,
            54,
            id="aceptada-sin-audio",
        ),
    ],
)
async def test_cada_error_sale_en_la_taxonomia_y_deja_su_gasto(
    fixture: dict[str, Any], esperado: ProviderErrorKind, caracteres: int, eventos: Eventos
) -> None:
    """BR1.4: un solo intento, el tipo cerrado y la fila de gasto --cero si fue rechazada--."""
    tts, transporte, registro = _adaptador(fixture)
    texto = redactado(FRASES["es"], "es")

    with pytest.raises(ProviderError) as capturado:
        _ = [t async for t in tts.synthesize(texto, voice=VOCES["es"])]

    assert capturado.value.kind is esperado
    assert capturado.value.attempt == 1
    assert len(transporte.requests) == 1
    assert [r.units[0].units for r in registro.reports] == [Decimal(caracteres)]
    propios = [e for e in eventos.lineas if e["event"].startswith("providers.")]
    assert propios == [
        {
            "event": "providers.speech_call_failed",
            "provider": "deepgram",
            "use": "voice",
            "error_kind": esperado.value,
        }
    ]


async def test_saldo_agotado_es_una_parada_y_no_uno_de_los_cuatro_errores() -> None:
    """BR1.4: el 402 sale como `BudgetExhausted` del proveedor, que no se reintenta."""
    fixture = _con(
        "deepgram-speak-429-rate-limited",
        rejected={"status_code": 402, "body": {"err_code": "INSUFFICIENT_CREDITS"}},
    )
    tts, transporte, _ = _adaptador(fixture)

    with pytest.raises(BudgetExhausted) as capturado:
        _ = [t async for t in tts.synthesize(redactado(FRASES["es"], "es"), voice=VOCES["es"])]

    assert capturado.value.resource is ExhaustedResource.PROVIDER_QUOTA
    assert len(transporte.requests) == 1


@pytest.mark.parametrize(("gastado", "sin_valorar"), [("5.00", 0), ("0.10", 1)])
async def test_con_el_techo_cerrado_no_sale_ninguna_peticion(
    gastado: str, sin_valorar: int
) -> None:
    """BR5.1, SEC-U15.3: techo alcanzado, o una llamada sin valorar, y la voz no llama."""
    tts, transporte, registro = _adaptador(
        replay.load("deepgram-speak-aura-2-es"),
        gate=techo(gastado=gastado, sin_valorar=sin_valorar),
    )

    with pytest.raises(BudgetExhausted) as capturado:
        _ = [t async for t in tts.synthesize(redactado(FRASES["es"], "es"), voice=VOCES["es"])]

    assert capturado.value.resource is ExhaustedResource.PROJECT_CAP
    assert transporte.requests == []
    assert registro.reports == []


async def test_una_voz_de_otro_proveedor_falla_antes_de_llamar() -> None:
    tts, transporte, _ = _adaptador(replay.load("deepgram-speak-aura-2-es"))
    catalina = VOCES["es"].evolve(provider=ProviderName.CARTESIA)

    with pytest.raises(SpeechMisconfiguredError):
        _ = [t async for t in tts.synthesize(redactado(FRASES["es"], "es"), voice=catalina)]

    assert transporte.requests == []
