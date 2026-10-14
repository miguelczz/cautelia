"""La boca de una llamada, cableada: `SpeechPlatform.speech_session` (2026-10-13).

`test_cartesia_session.py` prueba el canal compartido; aqui se prueba lo que la plataforma
le suma: que una llamada abra **una** conexion con la voz principal, que la voz de respaldo
siga funcionando igual que con `speak` (la frase se repite entera en ella si la principal se
cae, tambien a mitad de frase), que abrir la sesion nunca haga fallar la llamada y que se
cierre siempre.
"""

from __future__ import annotations

import secrets
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from untangle.base import Locale, ProviderErrorKind, ProviderName
from untangle.providers import config as provider_config
from untangle.providers.ports import ProviderError
from untangle.server import speech
from untangle.settings import Settings
from untangle.telemetry.spend.models import VoiceMode
from untangle.tenancy import config as tenant_config
from untangle.voice.loop import SessionVoice

from . import replay
from .apoyo import Abierto, Eventos, Registro, redactado
from .servidor_falso import BYTES_POR_TROZO, FabricaFalsa, ServidorFalso, audio_de_la_frase

RESPALDO = "deepgram-speak-aura-2-es"
FRASE = "Hola, esta es una prueba."


def _plataforma(
    servidor: ServidorFalso, *, respaldo: str = RESPALDO
) -> tuple[speech.SpeechPlatform, replay.ReplayTransport, Registro]:
    """La plataforma con Cartesia de mentira (el servidor falso) y Deepgram grabado."""
    deepgram = replay.ReplayTransport(replay.load(respaldo))
    registro = Registro()
    ajustes = Settings(
        voice_deepgram_api_key=secrets.token_urlsafe(24),
        voice_cartesia_api_key=secrets.token_urlsafe(24),
        chat_model_api_key=secrets.token_urlsafe(24),
    )
    plataforma = speech.build_speech_platform(
        ajustes,
        provider_config.load(),
        tenant_config.load().available,
        transports={
            ProviderName.DEEPGRAM: replay.ReplayFactory(deepgram),
            ProviderName.CARTESIA: FabricaFalsa(servidor),
        },
        gate=Abierto(),
        usage=registro,
    )
    return plataforma, deepgram, registro


def _aseguradora() -> str:
    return sorted(tenant_config.load().ids)[0]


async def _decir(
    boca: speech.SpeechPlatform | speech.SpeechSession,
    *,
    idioma: Locale = "es",
    modo: VoiceMode = VoiceMode.PRIMARY,
) -> bytes:
    trozos = boca.speak(_aseguradora(), redactado(FRASE, idioma), mode=modo, language=idioma)
    return b"".join([t async for t in trozos])


async def _respaldo_entero() -> bytes:
    """Lo que dice la voz de respaldo con la frase entera, para comparar."""
    plataforma, _, _ = _plataforma(ServidorFalso())
    return await _decir(plataforma, modo=VoiceMode.FALLBACK)


# --- Una conexion por llamada ----------------------------------------------------------


def test_la_plataforma_de_voz_ofrece_la_sesion_que_el_ciclo_busca() -> None:
    """Si dejara de ofrecerla, el ciclo hablaria frase por frase sin avisar a nadie."""
    plataforma, _, _ = _plataforma(ServidorFalso())
    assert isinstance(plataforma, SessionVoice)


async def test_una_llamada_habla_por_una_sola_conexion_con_la_voz_principal() -> None:
    servidor = ServidorFalso()
    plataforma, deepgram, _ = _plataforma(servidor)

    async with plataforma.speech_session(
        _aseguradora(), mode=VoiceMode.PRIMARY, language="es"
    ) as boca:
        assert servidor.aperturas == 1, "el canal se abre al entrar, antes de la apertura"
        primera = await _decir(boca)
        segunda = await _decir(boca)
        tercera = await _decir(boca, idioma="en")

    assert servidor.aperturas == 1
    assert primera == audio_de_la_frase(1) * 3
    assert segunda == audio_de_la_frase(2) * 3
    assert tercera == audio_de_la_frase(3) * 3
    assert deepgram.requests == [], "la de respaldo no se toca mientras la principal responde"
    assert servidor.canales[0].cierres == 1


async def test_el_idioma_cambia_en_cada_frase_por_el_mismo_canal() -> None:
    servidor = ServidorFalso()
    plataforma, _, _ = _plataforma(servidor)

    async with plataforma.speech_session(
        _aseguradora(), mode=VoiceMode.PRIMARY, language="es"
    ) as boca:
        await _decir(boca, idioma="es")
        await _decir(boca, idioma="en")

    assert servidor.aperturas == 1
    assert [m["language"] for m in servidor.recibidos] == ["es", "en"]


async def test_hablar_sin_sesion_sigue_abriendo_una_conexion_por_frase() -> None:
    """`speak` suelto --la persona simulada, `voice:say`-- no cambia."""
    servidor = ServidorFalso()
    plataforma, _, _ = _plataforma(servidor)

    await _decir(plataforma)
    await _decir(plataforma)

    assert servidor.aperturas == 2


async def test_la_sesion_cierra_la_conexion_aunque_la_llamada_falle() -> None:
    servidor = ServidorFalso()
    plataforma, _, _ = _plataforma(servidor)

    with pytest.raises(RuntimeError, match="la llamada se cayo"):
        async with plataforma.speech_session(_aseguradora(), mode=VoiceMode.PRIMARY, language="es"):
            raise RuntimeError("la llamada se cayo")

    assert servidor.canales[0].cierres == 1


# --- La voz de respaldo sigue funcionando ------------------------------------------------


async def test_si_el_canal_de_la_sesion_se_cae_a_mitad_de_frase_sigue_con_la_de_respaldo(
    eventos: Eventos,
) -> None:
    """Lo ya enviado suena; la frase se repite entera en la de respaldo, y la llamada sigue."""
    servidor = ServidorFalso(cae_tras={1: 1})
    plataforma, _, registro = _plataforma(servidor)
    respaldo = await _respaldo_entero()

    async with plataforma.speech_session(
        _aseguradora(), mode=VoiceMode.PRIMARY, language="es"
    ) as boca:
        primera = await _decir(boca)
        segunda = await _decir(boca)

    assert primera.startswith(audio_de_la_frase(1))
    assert primera.endswith(respaldo)
    assert len(primera) == BYTES_POR_TROZO + len(respaldo)
    # La principal queda fuera: la frase siguiente va directo a la de respaldo, sin otra
    # conexion con Cartesia.
    assert segunda == respaldo
    assert servidor.aperturas == 1
    caida = [e for e in eventos.lineas if e["event"] == "voice.primary_failed"]
    assert [(e["error_kind"], e["mid_phrase"]) for e in caida] == [("unavailable", True)]
    assert [r.provider for r in registro.reports][-1] is ProviderName.DEEPGRAM


async def test_un_error_de_la_principal_antes_de_cualquier_audio_tambien_pasa_a_la_de_respaldo(
    eventos: Eventos,
) -> None:
    servidor = ServidorFalso(error_en={1: 429})
    plataforma, _, _ = _plataforma(servidor)
    respaldo = await _respaldo_entero()

    async with plataforma.speech_session(
        _aseguradora(), mode=VoiceMode.PRIMARY, language="es"
    ) as boca:
        primera = await _decir(boca)

    assert primera == respaldo
    caida = [e for e in eventos.lineas if e["event"] == "voice.primary_failed"]
    assert [(e["error_kind"], e["mid_phrase"]) for e in caida] == [("rate_limited", False)]


async def test_si_tambien_falla_la_de_respaldo_el_fallo_sale() -> None:
    servidor = ServidorFalso(error_en={1: 500})
    plataforma, _, _ = _plataforma(servidor, respaldo="deepgram-speak-503-unavailable")

    with pytest.raises(ProviderError) as fallo:
        async with plataforma.speech_session(
            _aseguradora(), mode=VoiceMode.PRIMARY, language="es"
        ) as boca:
            await _decir(boca)

    assert fallo.value.provider is ProviderName.DEEPGRAM
    assert fallo.value.kind is ProviderErrorKind.UNAVAILABLE


async def test_con_la_principal_fuera_de_servicio_la_sesion_no_le_abre_un_canal() -> None:
    servidor = ServidorFalso()
    plataforma, _, _ = _plataforma(servidor)
    ahora = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
    plataforma = replace(plataforma, now=lambda: ahora)
    plataforma.out_of_service.marcar(ProviderName.CARTESIA, ahora, por=speech.PRIMARY_RETRY_AFTER)
    respaldo = await _respaldo_entero()

    async with plataforma.speech_session(
        _aseguradora(), mode=VoiceMode.PRIMARY, language="es"
    ) as boca:
        audio = await _decir(boca)

    assert servidor.aperturas == 0, "abrirle un canal a una voz que se sabe caida es gastar"
    assert audio == respaldo


async def test_en_modo_de_respaldo_la_sesion_no_abre_la_principal() -> None:
    servidor = ServidorFalso()
    plataforma, _, _ = _plataforma(servidor)
    respaldo = await _respaldo_entero()

    async with plataforma.speech_session(
        _aseguradora(), mode=VoiceMode.FALLBACK, language="es"
    ) as boca:
        audio = await _decir(boca, modo=VoiceMode.FALLBACK)

    assert servidor.aperturas == 0
    assert audio == respaldo


# --- Abrir la sesion nunca hace fallar la llamada ----------------------------------------


async def test_si_la_sesion_no_puede_abrirse_la_llamada_habla_frase_por_frase(
    eventos: Eventos,
) -> None:
    servidor = ServidorFalso(falla_al_abrir=RuntimeError("detalle que no debe salir"))
    plataforma, _, _ = _plataforma(servidor)

    async with plataforma.speech_session(
        _aseguradora(), mode=VoiceMode.PRIMARY, language="es"
    ) as boca:
        servidor.falla_al_abrir = None
        audio = await _decir(boca)

    assert audio == audio_de_la_frase(1) * 3
    fallo = [e for e in eventos.lineas if e["event"] == "voice.speech_session_open_failed"]
    assert [(e["provider"], e["error_type"]) for e in fallo] == [("cartesia", "RuntimeError")]
    assert "detalle que no debe salir" not in eventos.crudo
    assert isinstance(fallo[0]["where"], str)
