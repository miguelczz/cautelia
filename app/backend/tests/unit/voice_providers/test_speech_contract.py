"""Lo que cruza a los tres adaptadores de voz (BR1.2, BR1.3, BR2.3, BR4.2, BR5.1, BR6.1).

- **Sin respuesta grabada no hay activacion** (BR2.3): cada modelo que un
  adaptador declara con contrato tiene su archivo capturado, y al reves.
- **Lo grabado no lleva voz ni credencial**: todo audio es el marcador de
  silencio, y ningun archivo nombra una cabecera de autorizacion.
- **La fabrica construye la voz con las claves del uso `voice`** y con ninguna
  otra (SEC-U15.2).
- **Las dos voces dicen lo mismo** (BR4.2, AC5.11.4): el texto que llega a
  Cartesia y a Aura-2 es, byte a byte, el del catalogo.
- **Toda llamada tiene precio de lista** (NFR14.4): ninguna queda "no medida".
"""

from __future__ import annotations

import base64
import json
import secrets
from pathlib import Path
from typing import Any

import pytest

from untangle.base import ProviderName, Use
from untangle.copy_catalog import api as catalogo
from untangle.providers import config as provider_config
from untangle.providers.adapters.cartesia import ENDPOINT as CARTESIA_ENDPOINT
from untangle.providers.adapters.cartesia import CartesiaTextToSpeech
from untangle.providers.adapters.deepgram import DeepgramAuraTextToSpeech, DeepgramSpeechToText
from untangle.providers.adapters.speech_common import WholeSamples, kind_for_close
from untangle.providers.adapters.wire import WireTransportFactory
from untangle.providers.ceiling import ceiling_closed
from untangle.providers.factory import MissingProviderKeyError, SpeechClients
from untangle.providers.ports import BudgetExhausted, ProviderErrorKind, VoiceRef
from untangle.providers.speech_wire import SpeechRequest
from untangle.providers.voice_availability import (
    SpeechModel,
    VoiceAvailability,
    availability_by_tenant,
)
from untangle.server import speech
from untangle.server.voice_cli import FRASES, declared_voices
from untangle.server.voice_recording import (
    PLACEHOLDER_AUDIO_B64,
    Recorder,
    RecordingTransportFactory,
    sanitize,
)
from untangle.settings import Settings
from untangle.telemetry.spend import pricing
from untangle.telemetry.spend.models import CostStatus
from untangle.tenancy import config as tenant_config
from untangle.tenancy.models import TranscriptionMode

from . import replay
from .apoyo import TIEMPOS, Abierto, Eventos, Registro, audio_de, clientes, foto, redactado, techo

GRABADAS = sorted(replay.RECORDED.glob("*.json"))


def _grabada(ruta: Path) -> dict[str, Any]:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert isinstance(datos, dict)
    return datos


def test_cada_modelo_con_contrato_tiene_su_respuesta_capturada_y_al_reves() -> None:
    """BR2.3: la lista de cada adaptador y los archivos capturados dicen lo mismo."""
    capturadas: dict[str, set[str]] = {}
    for ruta in GRABADAS:
        datos = _grabada(ruta)
        if datos["provenance"] == "captured":
            capturadas.setdefault(datos["provider"], set()).add(datos["model"])

    declaradas = {
        proveedor.value: set(info.contract_models)
        for proveedor, info in speech.SPEECH_ADAPTERS.items()
    }
    assert declaradas == capturadas


def test_lo_grabado_no_lleva_voz_ni_credencial() -> None:
    """Ningun audio real y ninguna cabecera de autorizacion en el repositorio."""
    assert len(GRABADAS) >= 8
    for ruta in GRABADAS:
        crudo = ruta.read_text(encoding="utf-8")
        datos = _grabada(ruta)
        assert datos["_about"], ruta.name
        assert datos["provenance"] in {"captured", "documented-not-captured"}, ruta.name
        if datos["provenance"] == "documented-not-captured":
            assert datos["why_not_captured"], ruta.name
        for prohibido in ("Authorization", "X-API-Key", "Token ", "api_key", "dg-project-id"):
            assert prohibido not in crudo, (ruta.name, prohibido)
        for marco in datos["received"]:
            if "binary_b64" in marco:
                assert marco["binary_b64"] == PLACEHOLDER_AUDIO_B64, ruta.name
            texto = marco.get("text") or {}
            if texto.get("type") == "chunk":
                assert texto["data"] == PLACEHOLDER_AUDIO_B64, ruta.name
            assert texto.get("request_id") in (None, "retirado-al-grabar"), ruta.name


def test_las_aseguradoras_del_repositorio_tienen_voz_con_los_adaptadores_registrados() -> None:
    """NFR20.3 con el registro de verdad de la raiz, no con uno escrito en la prueba."""
    cargadas = tenant_config.load()
    estados = availability_by_tenant(
        cargadas.available,
        providers=provider_config.load().providers,
        adapters=speech.SPEECH_ADAPTERS,
    )
    assert set(estados.values()) == {VoiceAvailability.on()}
    plataforma = speech.build_speech_platform(
        Settings(), provider_config.load(), cargadas.available, gate=Abierto(), usage=Registro()
    )
    voces, modelos = declared_voices(plataforma)
    assert {(v.provider, v.language) for v in voces} == {
        (ProviderName.CARTESIA, "es"),
        (ProviderName.CARTESIA, "en"),
        (ProviderName.DEEPGRAM, "es"),
        (ProviderName.DEEPGRAM, "en"),
    }
    # Un idioma por llamada desde el 2026-10-09: en modo multiidioma el reconocedor entendia
    # peor el espanol de una llamada real. Se compara lo que identifica al modelo y no su
    # vocabulario (2026-10-13): los terminos clave llevan el nombre de cada aseguradora, y los
    # cubre `test_stt_vocabulary.py`.
    assert [(m.provider, m.model, m.mode) for m in modelos] == [
        (ProviderName.DEEPGRAM, "nova-3", TranscriptionMode.MONOLINGUAL)
    ]


def test_la_fabrica_construye_la_voz_con_las_claves_del_uso_voice_y_ninguna_otra() -> None:
    """BR1.3, SEC-U15.2: cada proveedor recibe **su** clave de voz, y nada mas."""
    claves = {
        campo: secrets.token_urlsafe(24)
        for campo in (
            "voice_model_api_key",
            "chat_model_api_key",
            "evals_model_api_key",
            "operations_model_api_key",
            "voice_deepgram_api_key",
            "voice_cartesia_api_key",
        )
    }
    ajustes = Settings(
        voice_model_api_key=claves["voice_model_api_key"],
        chat_model_api_key=claves["chat_model_api_key"],
        evals_model_api_key=claves["evals_model_api_key"],
        operations_model_api_key=claves["operations_model_api_key"],
        voice_deepgram_api_key=claves["voice_deepgram_api_key"],
        voice_cartesia_api_key=claves["voice_cartesia_api_key"],
    )
    fabricas = {
        ProviderName.DEEPGRAM: replay.ReplayFactory(replay.ReplayTransport({})),
        ProviderName.CARTESIA: replay.ReplayFactory(replay.ReplayTransport({})),
    }
    clientes_de_voz = SpeechClients(settings=ajustes, transports=fabricas)

    assert fabricas[ProviderName.DEEPGRAM].created == [
        (claves["voice_deepgram_api_key"], Use.VOICE)
    ]
    assert fabricas[ProviderName.CARTESIA].created == [
        (claves["voice_cartesia_api_key"], Use.VOICE)
    ]
    peticion = SpeechRequest(path="v1/listen", connect_timeout_ms=1, read_timeout_ms=1)
    with pytest.raises(MissingProviderKeyError, match="uso voice"):
        clientes_de_voz.open_duplex(peticion, provider=ProviderName.DEEPGRAM, use=Use.CHAT)


def test_sin_clave_de_voz_no_hay_cliente_y_el_fallo_nombra_la_variable() -> None:
    ajustes = Settings(voice_deepgram_api_key=secrets.token_urlsafe(24))
    fabricas = {
        ProviderName.DEEPGRAM: replay.ReplayFactory(replay.ReplayTransport({})),
        ProviderName.CARTESIA: replay.ReplayFactory(replay.ReplayTransport({})),
    }
    clientes_de_voz = SpeechClients(settings=ajustes, transports=fabricas)

    assert clientes_de_voz.available() == (ProviderName.DEEPGRAM,)
    assert fabricas[ProviderName.CARTESIA].created == []
    with pytest.raises(MissingProviderKeyError, match="UNTANGLE_VOICE_CARTESIA_API_KEY"):
        clientes_de_voz.require(ProviderName.DEEPGRAM, ProviderName.CARTESIA)
    with pytest.raises(MissingProviderKeyError, match="no es un proveedor de voz"):
        SpeechClients(
            settings=ajustes,
            transports={ProviderName.GEMINI: replay.ReplayFactory(replay.ReplayTransport({}))},
        )


def test_el_transporte_no_imprime_su_clave() -> None:
    """Capa 2 de seguridad: la representacion nombra el uso y la raiz, nunca la clave."""
    clave = secrets.token_urlsafe(24)
    transporte = WireTransportFactory(CARTESIA_ENDPOINT).create(api_key=clave, use=Use.VOICE)
    assert clave not in repr(transporte)
    assert "voice" in repr(transporte)


async def test_las_dos_voces_reciben_el_mismo_texto_del_catalogo() -> None:
    """BR4.2, AC5.11.4: cambiar de voz no cambia que se dice."""
    frase = catalogo.load().t(catalogo.CopyKey("voice.availability.misconfigured"), locale="es")
    texto = redactado(frase, "es")

    caller_c, transporte_c, _ = clientes(
        ProviderName.CARTESIA, replay.load("cartesia-tts-sonic-3.6-es")
    )
    principal = CartesiaTextToSpeech(caller_c, gate=Abierto(), usage=Registro(), timeouts=TIEMPOS)
    caller_d, transporte_d, _ = clientes(
        ProviderName.DEEPGRAM, replay.load("deepgram-speak-aura-2-es")
    )
    respaldo = DeepgramAuraTextToSpeech(
        caller_d, gate=Abierto(), usage=Registro(), timeouts=TIEMPOS
    )

    voz_c = VoiceRef(
        provider=ProviderName.CARTESIA,
        model="sonic-3.6",
        voice_id="162e0f37-8504-474c-bb33-c606c01890dc",
        language="es",
    )
    voz_d = VoiceRef(
        provider=ProviderName.DEEPGRAM, model="aura-2", voice_id="aura-2-celeste-es", language="es"
    )
    audio_c = b"".join([t async for t in principal.synthesize(texto, voice=voz_c)])
    audio_d = b"".join([t async for t in respaldo.synthesize(texto, voice=voz_d)])

    assert transporte_c.channels[0].sent_texts[0]["transcript"] == frase
    assert transporte_d.requests[0].body == {"text": frase}
    assert len(audio_c) % 2 == 0
    assert len(audio_d) % 2 == 0


async def test_toda_llamada_de_voz_tiene_precio_de_lista() -> None:
    """NFR14.4: el gasto de la transcripcion y de las dos voces se valora; nada "no medido"."""
    tabla = pricing.PriceTable.from_entries(provider_config.load().prices.price_entries())
    registro = Registro()

    caller, _, _ = clientes(ProviderName.DEEPGRAM, replay.load("deepgram-listen-nova-3-es"))
    stt = DeepgramSpeechToText(
        caller,
        model=SpeechModel(ProviderName.DEEPGRAM, "nova-3", TranscriptionMode.MULTI),
        gate=Abierto(),
        usage=registro,
        timeouts=TIEMPOS,
    )
    _ = [t async for t in stt.stream(audio_de(4800), language="es")]
    for nombre, adaptador, voz in (
        (
            "cartesia-tts-sonic-3.6-es",
            CartesiaTextToSpeech,
            VoiceRef(
                provider=ProviderName.CARTESIA, model="sonic-3.6", voice_id="v", language="es"
            ),
        ),
        (
            "deepgram-speak-aura-2-en",
            DeepgramAuraTextToSpeech,
            VoiceRef(
                provider=ProviderName.DEEPGRAM,
                model="aura-2",
                voice_id="aura-2-thalia-en",
                language="en",
            ),
        ),
    ):
        proveedor = voz.provider
        caller, _, _ = clientes(proveedor, replay.load(nombre))
        tts = adaptador(caller, gate=Abierto(), usage=registro, timeouts=TIEMPOS)
        _ = [
            t
            async for t in tts.synthesize(redactado(FRASES[voz.language], voz.language), voice=voz)
        ]

    assert len(registro.reports) == 3
    for reporte in registro.reports:
        for unidad in reporte.units:
            costo = pricing.price_call(
                tabla,
                provider=reporte.provider,
                model=reporte.model,
                unit_kind=unidad.unit_kind,
                units=unidad.units,
            )
            assert costo.cost.status is CostStatus.MEASURED, (reporte.provider, reporte.model)


@pytest.mark.parametrize(
    ("gastado", "sin_valorar", "cerrado"),
    [("4.99", 0, False), ("5.00", 0, True), ("5.01", 0, True), ("0.01", 1, True)],
)
def test_el_techo_se_cierra_en_su_borde_y_ante_lo_no_valorado(
    gastado: str, sin_valorar: int, cerrado: bool
) -> None:
    """BR5.1: el borde exacto del techo, con el acumulado forzado y sin gastar."""
    assert ceiling_closed(foto(gastado=gastado, sin_valorar=sin_valorar)) is cerrado


async def test_un_techo_ilegible_cierra_la_voz(eventos: Eventos) -> None:
    """Base caida o lenta: la voz no llama. Lo que cuesta dinero falla cerrado."""
    from untangle.providers.ceiling import CeilingGate

    async def leer_falla() -> Any:
        msg = "sin base"
        raise ConnectionError(msg)

    with pytest.raises(BudgetExhausted):
        await CeilingGate(leer_falla).ensure_open(provider=ProviderName.CARTESIA, use=Use.VOICE)
    await techo(gastado="0").ensure_open(provider=ProviderName.CARTESIA, use=Use.VOICE)
    assert [e["event"] for e in eventos.lineas] == ["providers.ceiling_unreadable"]
    assert "sin base" not in eventos.crudo


def test_el_audio_sale_en_muestras_enteras_aunque_llegue_partido() -> None:
    """BR4.1: una muestra de 16 bits son dos bytes, y un trozo de red puede partirla."""
    muestras = WholeSamples()
    primero = muestras.feed(b"\x01\x02\x03")
    a_medias = muestras.pending
    segundo = muestras.feed(b"\x04")
    entera = not muestras.pending
    assert (primero, a_medias, segundo, entera) == (b"\x01\x02", True, b"\x03\x04", True)
    assert kind_for_close(None) is ProviderErrorKind.UNAVAILABLE
    assert kind_for_close(4000) is ProviderErrorKind.UNAVAILABLE


async def test_el_grabador_guarda_la_forma_y_retira_el_audio_y_la_cuenta(tmp_path: Path) -> None:
    """CG-U15-3: lo que escribe `--record` es lo que `test:u15` puede versionar."""
    audio_real = base64.b64encode(b"\x01\x02" * 480).decode("ascii")
    grabada = replay.load("cartesia-tts-sonic-3.6-es")
    trozos = [
        {"text": {**m["text"], "data": audio_real, "request_id": "r-1"}}
        for m in grabada["received"]
        if m["text"]["type"] == "chunk"
    ]
    fin = [m for m in grabada["received"] if m["text"]["type"] == "done"]
    grabada = {**grabada, "received": trozos + trozos + fin}
    grabador = Recorder()
    ajustes = Settings(voice_cartesia_api_key=secrets.token_urlsafe(24))
    fabrica = RecordingTransportFactory(
        replay.ReplayFactory(replay.ReplayTransport(grabada)), grabador
    )
    caller = SpeechClients(settings=ajustes, transports={ProviderName.CARTESIA: fabrica})
    tts = CartesiaTextToSpeech(caller, gate=Abierto(), usage=Registro(), timeouts=TIEMPOS)
    voz = VoiceRef(provider=ProviderName.CARTESIA, model="sonic-3.6", voice_id="v", language="es")
    grabador.begin("prueba", provider=ProviderName.CARTESIA, model="sonic-3.6")

    _ = [t async for t in tts.synthesize(redactado(FRASES["es"], "es"), voice=voz)]

    (escrito,) = grabador.write(tmp_path)
    crudo = escrito.read_text(encoding="utf-8")
    datos = json.loads(crudo)
    assert audio_real not in crudo
    assert '"r-1"' not in crudo
    assert datos["audio_frames_omitted"] > 0
    assert datos["sent"][0]["text"]["transcript"] == FRASES["es"]
    assert sanitize({"x": [{"project_id": "p"}]}) == {"x": [{"project_id": "retirado-al-grabar"}]}
