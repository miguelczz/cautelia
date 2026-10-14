"""Catalina en Cartesia contra sus respuestas grabadas (BR4.1, BR1.4, BR5.1, BR6.1).

Las dos respuestas de contrato se capturaron el 2026-09-21 con la voz de Catalina
en espanol y en ingles. Lo que fijan: por el WebSocket sube **un** mensaje con el
texto, la voz, el idioma y el formato; bajan trozos `chunk` con el audio en
base64 y un `done` que cierra, todos con el `context_id` de la peticion. Y la voz
que no existe no rechaza el apreton: contesta con un marco `error` y su codigo.
"""

from __future__ import annotations

import base64
import copy
from decimal import Decimal
from typing import Any

import pytest

from untangle.base import Locale, ProviderErrorKind, ProviderName, SpendSource, UnitKind, Use
from untangle.providers.adapters.cartesia import CartesiaTextToSpeech
from untangle.providers.adapters.speech_common import SpeechMisconfiguredError
from untangle.providers.ports import BudgetExhausted, ExhaustedResource, ProviderError, VoiceRef
from untangle.server.voice_cli import FRASES

from . import replay
from .apoyo import TIEMPOS, Abierto, Eventos, Registro, clientes, redactado, techo

CATALINA = "162e0f37-8504-474c-bb33-c606c01890dc"


def _voz(idioma: Locale) -> VoiceRef:
    return VoiceRef(
        provider=ProviderName.CARTESIA, model="sonic-3.6", voice_id=CATALINA, language=idioma
    )


def _adaptador(
    fixture: dict[str, Any], *, gate: Any = None
) -> tuple[CartesiaTextToSpeech, replay.ReplayTransport, Registro]:
    caller, transporte, _ = clientes(ProviderName.CARTESIA, fixture)
    registro = Registro()
    tts = CartesiaTextToSpeech(
        caller, gate=gate if gate is not None else Abierto(), usage=registro, timeouts=TIEMPOS
    )
    return tts, transporte, registro


@pytest.mark.parametrize("idioma", ["es", "en"])
async def test_la_respuesta_grabada_cumple_el_contrato(idioma: Locale) -> None:
    """BR4.1 y BR6.1: el mensaje que sube, el audio que baja y el gasto en caracteres."""
    grabada = replay.load(f"cartesia-tts-sonic-3.6-{idioma}")
    tts, transporte, registro = _adaptador(grabada)

    trozos = [
        t async for t in tts.synthesize(redactado(FRASES[idioma], idioma), voice=_voz(idioma))
    ]

    audio = [m for m in grabada["received"] if m["text"]["type"] == "chunk"]
    assert [len(t) for t in trozos] == [len(base64.b64decode(m["text"]["data"])) for m in audio]
    assert all(len(t) % 2 == 0 for t in trozos)

    (mensaje,) = transporte.channels[0].sent_texts
    assert mensaje == {
        "model_id": "sonic-3.6",
        "transcript": FRASES[idioma],
        "voice": {"mode": "id", "id": CATALINA},
        "language": idioma,
        "context_id": mensaje["context_id"],
        "output_format": {"container": "raw", "encoding": "pcm_s16le", "sample_rate": 24000},
        "continue": False,
    }
    # La forma del mensaje es la misma que se mando el dia de la captura.
    assert set(mensaje) == set(grabada["sent"][0]["text"])

    (reporte,) = registro.reports
    assert (reporte.provider, reporte.model, reporte.use) == (
        ProviderName.CARTESIA,
        "sonic-3.6",
        Use.VOICE,
    )
    assert reporte.source is SpendSource.COUNTED_LOCALLY
    assert [(u.unit_kind, u.units) for u in reporte.units] == [
        (UnitKind.CHARACTERS, Decimal(len(FRASES[idioma])))
    ]


def _sin_done(nombre: str) -> dict[str, Any]:
    grabada = copy.deepcopy(replay.load(nombre))
    grabada["received"] = [m for m in grabada["received"] if m["text"]["type"] != "done"]
    return grabada


def _de_otra_peticion(nombre: str) -> dict[str, Any]:
    grabada = copy.deepcopy(replay.load(nombre))
    grabada["received"][0]["text"]["context_id"] = "de-otra-peticion"
    return grabada


def _audio_no_base64(nombre: str) -> dict[str, Any]:
    grabada = copy.deepcopy(replay.load(nombre))
    grabada["received"][0]["text"]["data"] = "esto no es base64!"
    return grabada


@pytest.mark.parametrize(
    ("fixture", "esperado"),
    [
        pytest.param(
            replay.load("cartesia-tts-unknown-voice"),
            ProviderErrorKind.INVALID_RESPONSE,
            id="voz-inexistente-404-capturada",
        ),
        pytest.param(
            replay.load("cartesia-tts-error-429-rate-limited"),
            ProviderErrorKind.RATE_LIMITED,
            id="429",
        ),
        pytest.param(
            replay.load("cartesia-tts-error-500-unavailable"),
            ProviderErrorKind.UNAVAILABLE,
            id="500",
        ),
        pytest.param(
            _sin_done("cartesia-tts-sonic-3.6-es"), ProviderErrorKind.TIMEOUT, id="se-queda-callada"
        ),
        pytest.param(
            _audio_no_base64("cartesia-tts-sonic-3.6-es"),
            ProviderErrorKind.INVALID_RESPONSE,
            id="audio-que-no-es-base64",
        ),
    ],
)
async def test_cada_error_sale_en_la_taxonomia_con_un_solo_intento(
    fixture: dict[str, Any], esperado: ProviderErrorKind, eventos: Eventos
) -> None:
    """BR1.4: el tipo sale de `status_code`, nunca de la prosa del proveedor."""
    tts, transporte, registro = _adaptador(fixture)

    with pytest.raises(ProviderError) as capturado:
        _ = [t async for t in tts.synthesize(redactado(FRASES["es"], "es"), voice=_voz("es"))]

    assert capturado.value.kind is esperado
    assert capturado.value.attempt == 1
    assert len(transporte.requests) == 1
    # El mensaje salio: sus caracteres se cuentan, del lado conservador.
    assert [r.units[0].units for r in registro.reports] == [Decimal(len(FRASES["es"]))]
    # El texto del error del proveedor no llega a ningun evento.
    assert "not found" not in eventos.crudo.lower()


async def test_un_marco_de_otra_peticion_no_se_acepta() -> None:
    tts, _, _ = _adaptador(_de_otra_peticion("cartesia-tts-sonic-3.6-es"))
    with pytest.raises(ProviderError) as capturado:
        _ = [t async for t in tts.synthesize(redactado(FRASES["es"], "es"), voice=_voz("es"))]
    assert capturado.value.kind is ProviderErrorKind.INVALID_RESPONSE


async def test_cupo_agotado_es_una_parada_del_proveedor() -> None:
    """BR1.4: el marco `error` con 402 sale como `BudgetExhausted`, sin reintento."""
    tts, transporte, _ = _adaptador(replay.load("cartesia-tts-error-402-no-credit"))

    with pytest.raises(BudgetExhausted) as capturado:
        _ = [t async for t in tts.synthesize(redactado(FRASES["es"], "es"), voice=_voz("es"))]

    assert capturado.value.resource is ExhaustedResource.PROVIDER_QUOTA
    assert len(transporte.requests) == 1


async def test_con_el_techo_cerrado_no_se_abre_el_canal() -> None:
    """BR5.1, SEC-U15.3: el acumulado forzado al techo y Cartesia no recibe nada."""
    tts, transporte, registro = _adaptador(
        replay.load("cartesia-tts-sonic-3.6-es"), gate=techo(gastado="5.00")
    )

    with pytest.raises(BudgetExhausted) as capturado:
        _ = [t async for t in tts.synthesize(redactado(FRASES["es"], "es"), voice=_voz("es"))]

    assert capturado.value.resource is ExhaustedResource.PROJECT_CAP
    assert transporte.requests == []
    assert registro.reports == []


async def test_una_voz_de_otro_proveedor_falla_antes_de_llamar() -> None:
    tts, transporte, _ = _adaptador(replay.load("cartesia-tts-sonic-3.6-es"))
    with pytest.raises(SpeechMisconfiguredError):
        _ = [
            t
            async for t in tts.synthesize(
                redactado(FRASES["es"], "es"),
                voice=_voz("es").evolve(provider=ProviderName.DEEPGRAM),
            )
        ]
    assert transporte.requests == []
