"""Los comandos a mano de la voz (U15): la prueba de contrato y oir una voz.

    mise run voice:contract-live
    mise run voice:contract-live -- --record
    mise run voice:say -- --tenant <id> [--language es|en] [--mode primary|fallback]
                          [--text '...'] [--no-play]
    mise run voice:simular -- --tenant <id> --guion <archivo.json> [--language es|en]
                             [--detalle]

**Ninguno corre en GitHub Actions** (BR6.2): gastan unos caracteres y segundos
del saldo gratuito y dependen de la red. Los dos recorren **el camino del
aplicativo** --configuracion, fabrica del uso `voice`, techo, adaptador y
registro de gasto--, construido por `server/speech.py` igual que en el proceso
servido: no hay una segunda forma de construir una voz.

## `contract-live`: la prueba de contrato contra los proveedores reales

1. **Comprueba que cada voz declarada existe** en la lista de su proveedor. Esas
   consultas no cuestan y las hace el catalogo de cada adaptador, porque la ruta
   y la forma de la respuesta son protocolo del proveedor (BR1.1). Si falta
   alguna se detiene sin sintetizar nada.
2. **Sintetiza una frase fija y corta con cada voz** de las aseguradoras, en su
   idioma, y **publica la latencia al primer audio** de cada una (TECH-U15.2):
   sin umbral propio, porque la meta del turno es NFR1 y es de U16.
3. **Transcribe unos segundos** --el audio de Catalina de la prueba anterior, que
   vive solo en memoria-- con el modelo de transcripcion configurado, en los dos
   idiomas.
4. Con `--record`, prueba ademas **dos errores que no cuestan** --una voz que no
   existe en cada proveedor-- y escribe todo lo capturado como respuestas
   grabadas para `test:u15` (CG-U15-3).

## `say`: oir la voz de una aseguradora (BR6.3)

Sintetiza una frase con la voz de una aseguradora, deja el audio en
`tmp/voice/` --que git ignora-- como WAV de 16 bits, mono, 24 kHz, y lo
reproduce si la maquina tiene reproductor. `--no-play` solo lo guarda. La frase
por omision es la fija de la prueba de contrato; con `--text` se dice otra, que
pasa antes por el punto unico de redaccion como cualquier texto que va hacia
una persona.

## `simular`: una llamada de mentira por el camino de verdad (2026-10-12)

Una persona que es un guion JSON llama a una aseguradora: sus frases se sintetizan con la
voz del aplicativo y entran en tiempo real por el reconocedor, el ciclo de la llamada y el
grafo, con la muletilla encendida como en la llamada real. Imprime cada cuadro con su
tiempo y, si la llamada se cae, la traza completa; con `--detalle`, tambien cada parcial y
cada senal de voz del reconocedor, con el suyo. Gasta unos centavos y no corre en
GitHub Actions. Vive en `voice_simulation.py`; el formato del guion esta en su cabecera y
hay tres de ejemplo en `app/evals/fixtures/voice-sim/`. Una frase con datos (una poliza, un
nombre) va con `decir_con_datos`: llega a la llamada ya transcrita, sin voz ni reconocedor, y
`cierre-directo.json` la usa para llegar hasta el cierre del reporte. Corre sobre la base
del proyecto, como el aplicativo servido, igual que los demas.

## El registro de gasto

Cada llamada pasa por **el techo y el libro de gasto** de U5 (BR5.1). El libro es el
de la base del proyecto que nombra `UNTANGLE_DATABASE_URL`, el mismo del aplicativo, y
sin ella --o con la base apagada-- el comando **no llama** (la voz falla cerrada): lo
comprueba antes de la primera llamada y dice que falta. Hasta el 2026-10-13 las tareas
pasaban `--ledger ephemeral`, un libro desechable que empezaba en cero y se borraba al
terminar: el techo no veia lo ya gastado y lo gastado no quedaba anotado. Ya no existe.
Imprime lo que gasto la corrida, en segundos, caracteres y dolares a precio de lista,
y el acumulado real de la ventana.

Si un proveedor contesta que se acabo el saldo o el cupo, **se detiene** y dice
cual: no se reintenta y no se recarga (regla de `project.md`).
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess  # solo para el reproductor: ruta absoluta y argumentos fijos, sin shell
import sys
import time
import wave
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from untangle import paths
from untangle.base import Locale, ProviderName
from untangle.compliance.redaction import api as redaccion
from untangle.providers import config as provider_config
from untangle.providers.factory import MissingProviderKeyError
from untangle.providers.ports import (
    SPEECH_AUDIO,
    BudgetExhausted,
    ProviderError,
    SpeechStarted,
    Transcript,
    UsageReport,
    VoiceRef,
)
from untangle.providers.speech_wire import SpeechTransportFactory
from untangle.providers.voice_availability import (
    LANGUAGES,
    SpeechModel,
    VoiceUnavailableError,
    transcription_model,
)
from untangle.server import manual_ledger, speech, spend_wiring
from untangle.server.manual_ledger import spend_lines
from untangle.server.voice_recording import Recorder, RecordingTransportFactory
from untangle.settings import Settings
from untangle.telemetry.spend.models import VoiceMode
from untangle.tenancy import api as tenancy

if TYPE_CHECKING:
    from untangle.compliance.redaction.api import Redacted

__all__ = [
    "FRASES",
    "ContractProbeResult",
    "SayRequest",
    "SayResult",
    "declared_voices",
    "find_player",
    "main",
    "play",
    "resolve_voice",
    "say",
    "spend_lines",
]

#: Las frases fijas: cortas, sin datos de nadie, una por idioma. Son el texto
#: fijo con el que se mide la latencia al primer audio (TECH-U15.2) y la frase
#: por omision de `say`. No son copy del producto: nadie las oye fuera de estos
#: dos comandos a mano.
FRASES: dict[Locale, str] = {
    "es": "Hola, esta es una prueba de la voz de la demostración.",
    "en": "Hello, this is a test of the demo voice.",
}

#: Voces que no existen, para capturar el error de cada proveedor sin gastar.
_VOZ_INEXISTENTE = {
    ProviderName.DEEPGRAM: "aura-2-inexistente-es",
    ProviderName.CARTESIA: "00000000-0000-4000-8000-000000000000",
}

#: Cuanto audio sube por trozo a la transcripcion, al ritmo real de una llamada.
_TROZO_MS = 20

#: Los reproductores que se buscan, en orden, con sus opciones fijas: macOS,
#: PulseAudio o PipeWire, ALSA y ffmpeg. Se toma el primero que exista.
_REPRODUCTORES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("afplay", ()),
    ("paplay", ()),
    ("aplay", ("-q",)),
    ("ffplay", ("-nodisp", "-autoexit", "-loglevel", "quiet")),
)

#: Cuanto se espera al reproductor. Una frase dura segundos; un reproductor
#: colgado no puede dejar el comando abierto.
_REPRODUCCION_MAXIMA_S = 60


@dataclass(frozen=True)
class ContractProbeResult:
    """Lo que midio una prueba de contrato (entidad del mismo nombre, AC5.10.3)."""

    probe: str
    provider: ProviderName
    format_ok: bool
    first_audio_ms: int | None
    source: str
    detail: str


#: El registro de gasto vive en `manual_ledger`, que comparten los comandos a mano
#: que llaman a un proveedor. Estos nombres se quedan aqui a proposito: son las
#: costuras que las pruebas de este comando sustituyen, y quitarlos obligaria a
#: parchear otro modulo para probar este.
_Anotador = manual_ledger.AnnotatingUsageSink
_abrir_registro = manual_ledger.open_ledger
_cerrar_registro = manual_ledger.close_ledger


def _registro(ajustes: Settings) -> str:
    """La base del libro de gasto de la voz: sin ella no hay llamada (BR5.1)."""
    return manual_ledger.project_ledger_url(ajustes, purpose="llamada de voz (BR5.1)")


def _imprimir_gasto(
    reportes: Sequence[UsageReport],
    config: provider_config.ProviderPlatformConfig,
    gastado: Decimal | None,
) -> None:
    manual_ledger.print_spend(reportes, config, gastado)


# --- La plataforma, la misma que la del proceso servido -----------------------


def _plataforma(
    ajustes: Settings,
    config: provider_config.ProviderPlatformConfig,
    transports: Mapping[ProviderName, SpeechTransportFactory] | None = None,
) -> tuple[speech.SpeechPlatform, _Anotador]:
    """La voz del aplicativo, con el registro envuelto para poder imprimir lo gastado."""
    anotador = _Anotador(spend_wiring.LedgerUsageSink())
    plataforma = speech.build_speech_platform(
        ajustes, config, tenancy.load().available, transports=transports, usage=anotador
    )
    return plataforma, anotador


def declared_voices(
    platform: speech.SpeechPlatform,
) -> tuple[list[VoiceRef], list[SpeechModel]]:
    """Las voces y los modelos de transcripcion **distintos** de las aseguradoras con voz."""
    voces: dict[tuple[str, str, str, str], VoiceRef] = {}
    modelos: dict[tuple[str, str, str], SpeechModel] = {}
    for tenant_id in sorted(platform.availability):
        if not platform.availability[tenant_id].available:
            continue
        for modo in (VoiceMode.PRIMARY, VoiceMode.FALLBACK):
            for idioma in LANGUAGES:
                ref = platform.voice_for(tenant_id, mode=modo, language=idioma)
                voces[(ref.provider.value, ref.model, ref.voice_id, ref.language)] = ref
        modelo = transcription_model(platform.voices[tenant_id])
        modelos[(modelo.provider.value, modelo.model, modelo.mode.value)] = modelo
    return [voces[k] for k in sorted(voces)], [modelos[k] for k in sorted(modelos)]


# --- contract-live ------------------------------------------------------------


def _nombre(voz: VoiceRef) -> str:
    base = "tts" if voz.provider is ProviderName.CARTESIA else "speak"
    return f"{voz.provider.value}-{base}-{voz.model}-{voz.language}"


async def _sintetizar(
    voz: VoiceRef, plataforma: speech.SpeechPlatform, grabador: Recorder | None
) -> tuple[ContractProbeResult, bytes]:
    nombre = _nombre(voz)
    if grabador is not None:
        grabador.begin(nombre, provider=voz.provider, model=voz.model)
    adaptador = plataforma.synthesizer(voz)
    texto = redaccion.redact(FRASES[voz.language], language=voz.language)
    trozos: list[bytes] = []
    inicio = time.perf_counter()
    primero: int | None = None
    async for trozo in adaptador.synthesize(texto, voice=voz):
        if primero is None:
            primero = round((time.perf_counter() - inicio) * 1000)
        trozos.append(trozo)
    audio = b"".join(trozos)
    formato = bool(audio) and len(audio) % 2 == 0 and all(len(t) % 2 == 0 for t in trozos)
    segundos = len(audio) / SPEECH_AUDIO.bytes_per_second
    return (
        ContractProbeResult(
            probe=nombre,
            provider=voz.provider,
            format_ok=formato,
            first_audio_ms=primero,
            source="live",
            detail=f"{segundos:.2f} s de audio en {len(trozos)} trozos",
        ),
        audio,
    )


async def _en_trozos(audio: bytes) -> AsyncIterator[bytes]:
    tamano = SPEECH_AUDIO.bytes_per_second * _TROZO_MS // 1000
    for inicio in range(0, len(audio), tamano):
        yield audio[inicio : inicio + tamano]
        await asyncio.sleep(_TROZO_MS / 1000)


async def _transcribir(
    modelo: SpeechModel,
    idioma: Locale,
    audio: bytes,
    plataforma: speech.SpeechPlatform,
    grabador: Recorder | None,
) -> ContractProbeResult:
    nombre = f"{modelo.provider.value}-listen-{modelo.model}-{idioma}"
    if grabador is not None:
        grabador.begin(nombre, provider=modelo.provider, model=modelo.model)
    adaptador = speech.transcriber_for(
        modelo,
        caller=plataforma.clients,
        gate=plataforma.gate,
        usage=plataforma.usage,
        timeouts=plataforma.timeouts,
    )
    eventos = [e async for e in adaptador.stream(_en_trozos(audio), language=idioma)]
    resultados = [e for e in eventos if isinstance(e, Transcript)]
    senales = sum(isinstance(e, SpeechStarted) for e in eventos)
    finales = [t for t in resultados if t.is_final]
    detectado = next((t.language for t in finales if t.language), None)
    con_confianza = sum(1 for t in finales for p in t.words if p.confidence is not None)
    palabras = sum(len(t.words) for t in finales)
    return ContractProbeResult(
        probe=nombre,
        provider=modelo.provider,
        format_ok=bool(finales) and detectado == idioma,
        first_audio_ms=None,
        source="live",
        detail=(
            f"{len(resultados)} resultados, {len(finales)} finales, idioma detectado "
            f"{detectado}, {con_confianza}/{palabras} palabras con confianza, "
            f"{senales} senales de voz"
        ),
    )


async def _errores_que_no_cuestan(
    plataforma: speech.SpeechPlatform, grabador: Recorder
) -> list[ContractProbeResult]:
    """Una voz que no existe en cada proveedor: el rechazo se graba y no se cobra."""
    resultados: list[ContractProbeResult] = []
    for proveedor, modelo in (
        (ProviderName.DEEPGRAM, "aura-2"),
        (ProviderName.CARTESIA, "sonic-3.6"),
    ):
        voz = VoiceRef(
            provider=proveedor, model=modelo, voice_id=_VOZ_INEXISTENTE[proveedor], language="es"
        )
        base = "tts" if proveedor is ProviderName.CARTESIA else "speak"
        nombre = f"{proveedor.value}-{base}-unknown-voice"
        grabador.begin(nombre, provider=proveedor, model=modelo)
        adaptador = plataforma.synthesizer(voz)
        texto = redaccion.redact(FRASES["es"], language="es")
        try:
            async for _ in adaptador.synthesize(texto, voice=voz):
                pass
            detalle = "el proveedor NO rechazo una voz inexistente"
            ok = False
        except ProviderError as error:
            detalle = f"rechazada como {error.kind.value}"
            ok = True
        resultados.append(
            ContractProbeResult(
                probe=nombre,
                provider=proveedor,
                format_ok=ok,
                first_audio_ms=None,
                source="live",
                detail=detalle,
            )
        )
    return resultados


async def _pruebas_de_contrato(
    plataforma: speech.SpeechPlatform,
    voces: Sequence[VoiceRef],
    modelos: Sequence[SpeechModel],
    grabador: Recorder | None,
) -> list[ContractProbeResult]:
    """Sintetiza con cada voz y transcribe el audio de Catalina en los dos idiomas."""
    resultados: list[ContractProbeResult] = []
    audio_de_catalina: dict[Locale, bytes] = {}
    try:
        for voz in voces:
            resultado, audio = await _sintetizar(voz, plataforma, grabador)
            resultados.append(resultado)
            if voz.provider is ProviderName.CARTESIA:
                audio_de_catalina[voz.language] = audio
        for modelo in modelos:
            for idioma in LANGUAGES:
                resultados.append(
                    await _transcribir(
                        modelo, idioma, audio_de_catalina[idioma], plataforma, grabador
                    )
                )
        if grabador is not None:
            resultados.extend(await _errores_que_no_cuestan(plataforma, grabador))
    finally:
        # El audio vive solo en memoria y se suelta aqui, pase lo que pase.
        audio_de_catalina.clear()
    return resultados


def _imprimir_contrato(resultados: Sequence[ContractProbeResult]) -> None:
    print("--- Pruebas de contrato contra el proveedor real ------------------")
    for r in resultados:
        marca = "OK " if r.format_ok else "MAL"
        print(f"  [{marca}] {r.probe:<32} {r.detail}")
    print("\n--- Latencia al primer audio, con el texto fijo (TECH-U15.2) ------")
    print("  Sin umbral propio: la meta del turno es NFR1, y es de U16.")
    for r in resultados:
        if r.first_audio_ms is not None:
            print(f"  {r.probe:<32} {r.first_audio_ms:>6} ms")


async def _contract_live(
    plataforma: speech.SpeechPlatform,
    anotador: _Anotador,
    config: provider_config.ProviderPlatformConfig,
    grabador: Recorder | None,
    url: str,
) -> int:
    voces, modelos = declared_voices(plataforma)
    try:
        faltan = await speech.unpublished_voices(plataforma.clients, voces)
    except ProviderError as error:
        print(f"No se pudo consultar la lista de voces del proveedor: {error}")
        return 1
    if faltan:
        print(f"Estas voces no estan en la lista del proveedor: {', '.join(faltan)}")
        print("No se sintetiza nada. Corrija providers.yaml o el tenant.yaml que las nombra.")
        return 1
    print(f"Las {len(voces)} voces declaradas existen en la lista de su proveedor.\n")

    await _abrir_registro(config, url)
    codigo = 0
    resultados: list[ContractProbeResult] = []
    try:
        resultados = await _pruebas_de_contrato(plataforma, voces, modelos, grabador)
    except BudgetExhausted as parada:
        print(f"\nSE DETUVO: {parada}. No se reintenta ni se recarga; decide Miguel.")
        codigo = 2
    finally:
        gastado = await _cerrar_registro()

    if resultados:
        _imprimir_contrato(resultados)
    _imprimir_gasto(anotador.reports, config, gastado)
    if codigo:
        return codigo
    if grabador is not None:
        escritos = grabador.write()
        print(f"\nRespuestas grabadas: {len(escritos)} archivos en {escritos[0].parent}")
    return 0 if all(r.format_ok for r in resultados) else 1


# --- say ----------------------------------------------------------------------


@dataclass(frozen=True)
class SayRequest:
    """Lo que se pide oir: de que aseguradora, en que idioma, con que voz y que frase."""

    tenant_id: str
    #: Nulo para usar el idioma por defecto de la voz de esa aseguradora.
    language: Locale | None
    mode: VoiceMode
    #: Nulo para usar la frase fija del idioma.
    text: str | None


@dataclass(frozen=True)
class SayResult:
    """Lo que salio: donde quedo el audio, con que voz, cuanto dura y cuanto tardo."""

    path: Path
    voice: VoiceRef
    audio_seconds: float
    first_audio_ms: int | None


def resolve_voice(platform: speech.SpeechPlatform, request: SayRequest) -> VoiceRef:
    """La voz pedida, por la disponibilidad de verdad. Una voz apagada no se construye."""
    platform.availability_for(request.tenant_id)
    idioma = request.language or platform.voices[request.tenant_id].language_default
    return platform.voice_for(request.tenant_id, mode=request.mode, language=idioma)


async def say(
    platform: speech.SpeechPlatform,
    request: SayRequest,
    text: Redacted,
    *,
    out_dir: Path,
    now: datetime,
) -> SayResult:
    """Sintetiza la frase por el camino del aplicativo y la deja en un WAV (BR6.3).

    Pasa por `SpeechPlatform.speak`, que es lo mismo que pedira U16: la
    disponibilidad, la voz de esa aseguradora, el techo, el adaptador y el gasto.
    El archivo es WAV porque asi lo abre cualquier reproductor sin saber el
    formato; el contenido es exactamente lo que entrega el adaptador (BR4.1).
    """
    voz = resolve_voice(platform, request)
    trozos: list[bytes] = []
    inicio = time.perf_counter()
    primero: int | None = None
    async for trozo in platform.speak(
        request.tenant_id, text, mode=request.mode, language=voz.language
    ):
        if primero is None:
            primero = round((time.perf_counter() - inicio) * 1000)
        trozos.append(trozo)
    audio = b"".join(trozos)

    marca = now.strftime("%Y%m%dT%H%M%S")
    nombre = f"{request.tenant_id}-{voz.language}-{request.mode.value}-{marca}.wav"
    # Escribir el archivo bloquea, y fuera del bucle no estorba a nadie.
    ruta = await asyncio.to_thread(_escribir_wav, out_dir / nombre, audio)
    return SayResult(
        path=ruta,
        voice=voz,
        audio_seconds=len(audio) / SPEECH_AUDIO.bytes_per_second,
        first_audio_ms=primero,
    )


def _escribir_wav(ruta: Path, audio: bytes) -> Path:
    """El audio como WAV en el formato unico: 16 bits, mono, 24 kHz (BR4.1)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(ruta), "wb") as archivo:
        archivo.setnchannels(SPEECH_AUDIO.channels)
        archivo.setsampwidth(2)
        archivo.setframerate(SPEECH_AUDIO.sample_rate_hz)
        archivo.writeframes(audio)
    return ruta


def find_player() -> list[str] | None:
    """El primer reproductor que exista en la maquina, con su ruta absoluta."""
    for nombre, opciones in _REPRODUCTORES:
        ruta = shutil.which(nombre)
        if ruta is not None:
            return [ruta, *opciones]
    return None


def play(path: Path, player: Sequence[str]) -> bool:
    """Reproduce el archivo. Devuelve si el reproductor termino bien."""
    try:
        completado = subprocess.run(  # noqa: S603 -- ruta absoluta de shutil.which y opciones fijas; el unico argumento variable es el archivo que acaba de escribir este comando
            [*player, str(path)],
            check=False,
            timeout=_REPRODUCCION_MAXIMA_S,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completado.returncode == 0


def _reproducir_o_decir(ruta: Path, *, reproducir: bool) -> None:
    if not reproducir:
        print(f"Sin reproducir (--no-play). Para oirlo, abra {ruta}")
        return
    reproductor = find_player()
    if reproductor is None:
        print(f"No hay reproductor en esta maquina (afplay, paplay, aplay, ffplay). Abra {ruta}")
        return
    if not play(ruta, reproductor):
        print(f"El reproductor no termino bien. El audio sigue en {ruta}")


async def _say_live(  # noqa: PLR0913 -- lo que ya se resolvio antes de abrir el registro, por nombre
    plataforma: speech.SpeechPlatform,
    anotador: _Anotador,
    config: provider_config.ProviderPlatformConfig,
    pedido: SayRequest,
    *,
    texto: Redacted,
    url: str,
    out_dir: Path,
    reproducir: bool,
) -> int:
    await _abrir_registro(config, url)
    resultado: SayResult | None = None
    codigo = 0
    try:
        resultado = await say(plataforma, pedido, texto, out_dir=out_dir, now=datetime.now(UTC))
    except BudgetExhausted as parada:
        print(f"SE DETUVO: {parada}. No se reintenta ni se recarga; decide Miguel.")
        codigo = 2
    except ProviderError as error:
        print(f"La sintesis fallo: {error}. No se reintenta.")
        codigo = 1
    finally:
        gastado = await _cerrar_registro()

    if resultado is not None:
        voz = resultado.voice
        primero = (
            f"{resultado.first_audio_ms} ms al primer audio"
            if resultado.first_audio_ms is not None
            else "sin audio"
        )
        print(
            f"{voz.provider.value} {voz.model} {voz.voice_id} ({voz.language}, "
            f"{pedido.mode.value}): {resultado.audio_seconds:.2f} s de audio, {primero}"
        )
        print(f"Audio en {resultado.path}")
    _imprimir_gasto(anotador.reports, config, gastado)
    if resultado is not None:
        _reproducir_o_decir(resultado.path, reproducir=reproducir)
    return codigo


# --- La entrada ---------------------------------------------------------------


def _analizador() -> argparse.ArgumentParser:
    analizador = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    sub = analizador.add_subparsers(dest="comando", required=True)

    vivo = sub.add_parser("contract-live", help="prueba de contrato contra los proveedores reales")
    vivo.add_argument("--record", action="store_true", help="escribe las respuestas grabadas")

    decir = sub.add_parser("say", help="sintetiza una frase con la voz de una aseguradora")
    decir.add_argument("--tenant", required=True, help="la aseguradora cuya voz se quiere oir")
    decir.add_argument("--language", choices=LANGUAGES, default=None)
    decir.add_argument(
        "--mode",
        choices=tuple(modo.value for modo in VoiceMode),
        default=VoiceMode.PRIMARY.value,
        help="principal (Catalina) o de respaldo (Aura-2)",
    )
    decir.add_argument("--text", default=None, help="la frase; por omision, la fija del idioma")
    decir.add_argument("--no-play", action="store_true", help="solo guarda el audio")
    decir.add_argument("--out-dir", type=Path, default=None, help="por omision, tmp/voice/")

    # DS-5 por hito: una grabacion de verdad entra por el mismo transporte que el
    # navegador y se mide lo que salio. **No es una compuerta** --gasta saldo de
    # voz y depende de grabaciones que viven fuera del repositorio-- y por eso es
    # un comando a mano, como `contract-live`.
    llamar = sub.add_parser("call-live", help="corre un caso de DS-5 por el transporte de voz")
    llamar.add_argument("--case", required=True, help="el identificador del caso, DS-5/en/003")
    llamar.add_argument("--tenant", required=True, help="la aseguradora de la llamada")
    llamar.add_argument("--language", choices=LANGUAGES, default="en")
    llamar.add_argument(
        "--recordings",
        type=Path,
        required=True,
        help="la carpeta con las grabaciones; **fuera** del repositorio (son de personas reales)",
    )

    # Una llamada simulada por el camino real: gasta voz, transcripcion y modelo de verdad,
    # asi que es un comando a mano. Su implementacion se importa al usarlo: levanta la
    # aplicacion entera, y `--help` y las pruebas de este archivo no la necesitan.
    simular = sub.add_parser(
        "simular", help="una llamada simulada por el camino real (gasta unos centavos)"
    )
    simular.add_argument("--tenant", required=True, help="la aseguradora de la llamada")
    simular.add_argument(
        "--guion",
        type=Path,
        required=True,
        help="el guion JSON de la persona; hay dos de ejemplo en app/evals/fixtures/voice-sim/",
    )
    simular.add_argument("--language", choices=LANGUAGES, default="es")
    simular.add_argument(
        "--detalle",
        action="store_true",
        help="imprime tambien cada parcial y cada senal de voz del reconocedor, con su tiempo",
    )
    return analizador


def _call_live_desde(argumentos: argparse.Namespace, ajustes: Settings) -> int:
    """Una llamada de DS-5, por el camino real menos el socket.

    El grafo entra **enchufado** y no importado, igual que en el proceso servido:
    este archivo no puede importar el modulo que lo implementa sin arrastrar
    LangGraph a la raiz de un comando a mano.
    """
    from untangle.evals.drivers import voice as conductor_de_voz
    from untangle.evals.models import Channel, Dataset, GoldenCase
    from untangle.evals.runner import api as corredor
    from untangle.orchestration import turn as orquestacion

    config = provider_config.load()
    plataforma, anotador = _plataforma(ajustes, config)
    aseguradoras = tenancy.load()
    tenancy.install(aseguradoras)
    estado = plataforma.availability_for(argumentos.tenant)
    if not estado.available:
        motivo = estado.reason.value if estado.reason is not None else "sin motivo"
        print(f"la voz de '{argumentos.tenant}' esta apagada ({motivo})", file=sys.stderr)
        return 1
    plataforma.clients.require(ProviderName.DEEPGRAM, ProviderName.CARTESIA)

    conductor_de_voz.register(
        speech=plataforma,
        handle_turn=orquestacion.handle_turn,
        recordings=argumentos.recordings,
    )
    caso = GoldenCase(
        case_key=argumentos.case,
        dataset=Dataset.DS_5,
        language=argumentos.language,
        tenant=argumentos.tenant,
        channel=Channel.VOICE,
    )

    async def _correr() -> int:
        conductor = corredor.driver_for(Channel.VOICE)
        if conductor is None:
            print("el conductor de voz no quedo registrado", file=sys.stderr)
            return 1
        try:
            transcripcion = await conductor.run_case(caso)
        except conductor_de_voz.VoiceRecordingNotFoundError as error:
            # No medida, que no es lo mismo que fallida: se dice con esa palabra.
            print(f"no medida: {error}", file=sys.stderr)
            return 1
        for turno in transcripcion.turns:
            print(f"{turno.speaker}: {turno.text}")
        print(f"registro: {transcripcion.record}")
        return 0

    return asyncio.run(_con_el_libro(config, anotador, _registro(ajustes), _correr))


async def _con_el_libro(
    config: provider_config.ProviderPlatformConfig,
    anotador: _Anotador,
    url: str,
    correr: Callable[[], Awaitable[int]],
) -> int:
    """Corre algo que gasta con el libro de la base del proyecto abierto y lo cierra al salir.

    `call-live` no abria el libro: su registro desechable se levantaba y nadie lo
    apuntaba, asi que el techo no podia leerse y la llamada se cerraba antes de
    empezar. Aqui el libro se abre antes de la primera llamada --y si no se puede
    leer, se detiene sin gastar-- y se cierra tambien cuando la corrida se corta,
    imprimiendo lo gastado y el acumulado real.
    """
    await _abrir_registro(config, url)
    try:
        return await correr()
    finally:
        gastado = await _cerrar_registro()
        _imprimir_gasto(anotador.reports, config, gastado)


def _contract_live_desde(argumentos: argparse.Namespace, ajustes: Settings) -> int:
    config = provider_config.load()
    grabador = Recorder() if argumentos.record else None
    transportes: Mapping[ProviderName, SpeechTransportFactory] = speech.speech_transports()
    if grabador is not None:
        transportes = {
            proveedor: RecordingTransportFactory(fabrica, grabador)
            for proveedor, fabrica in transportes.items()
        }
    plataforma, anotador = _plataforma(ajustes, config, transportes)
    # Las claves se exigen **antes** de levantar ninguna base: descubrir que falta
    # una despues de esperar al contenedor no le sirve a nadie.
    plataforma.clients.require(ProviderName.DEEPGRAM, ProviderName.CARTESIA)
    url = _registro(ajustes)
    return asyncio.run(_contract_live(plataforma, anotador, config, grabador, url))


def _say_desde(argumentos: argparse.Namespace, ajustes: Settings) -> int:
    config = provider_config.load()
    plataforma, anotador = _plataforma(ajustes, config)
    pedido = SayRequest(
        tenant_id=argumentos.tenant,
        language=argumentos.language,
        mode=VoiceMode(argumentos.mode),
        text=argumentos.text,
    )
    try:
        voz = resolve_voice(plataforma, pedido)
    except VoiceUnavailableError as error:
        print(str(error), file=sys.stderr)
        return 1
    # La clave del proveedor de **esa** voz, antes de levantar ninguna base.
    plataforma.clients.require(voz.provider)
    texto = redaccion.redact(pedido.text or FRASES[voz.language], language=voz.language)
    salida = argumentos.out_dir if argumentos.out_dir is not None else paths.voice_output_dir()
    url = _registro(ajustes)
    return asyncio.run(
        _say_live(
            plataforma,
            anotador,
            config,
            pedido,
            texto=texto,
            url=url,
            out_dir=salida,
            reproducir=not argumentos.no_play,
        )
    )


def main(argv: list[str] | None = None) -> int:
    argumentos = _analizador().parse_args(argv)
    ajustes = Settings()
    try:
        if argumentos.comando == "say":
            return _say_desde(argumentos, ajustes)
        if argumentos.comando == "call-live":
            return _call_live_desde(argumentos, ajustes)
        if argumentos.comando == "simular":
            from untangle.server import voice_simulation

            return voice_simulation.run(argumentos, ajustes)
        return _contract_live_desde(argumentos, ajustes)
    except MissingProviderKeyError as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
