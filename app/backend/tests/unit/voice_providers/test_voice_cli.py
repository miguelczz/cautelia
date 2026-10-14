"""Los comandos a mano de la voz, con el adaptador doble (U15, pasos 10 y 11).

`voice:say` y `voice:contract-live` hablan con los proveedores de verdad y nunca
corren en GitHub Actions (BR6.2). Lo que si corre en cada entrega es todo lo
demas, con la respuesta grabada en lugar del proveedor:

- **`say` recorre el camino del aplicativo** --plataforma, techo, adaptador y
  gasto-- y deja un WAV en el formato unico (BR6.3, BR4.1); con `--no-play` no
  toca el reproductor.
- **Lo gastado se imprime** en unidades y en dolares a precio de lista, con la
  misma tabla del libro mayor, y lo que no tiene precio se dice (NFR14.4).
- **El libro es el de la base del proyecto** (2026-10-13): el comando imprime el
  acumulado real de la ventana y ya no existe un libro temporal que avisar. Sin esa
  base --o con ella apagada-- no llama a nadie.
- **Una parada no se reintenta** y deja su gasto a la vista (BR1.4).
- **`contract-live` publica la latencia al primer audio** con el texto fijo
  (TECH-U15.2) y no sintetiza nada si una voz no esta en la lista del proveedor.

El registro de gasto se sustituye en las pruebas por el acumulado forzado de
`apoyo.py`: ninguna prueba gasta ni abre una base (regla de `project.md`).
"""

from __future__ import annotations

import secrets
import shutil
import subprocess
import wave
from collections.abc import AsyncIterator, Iterator, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from untangle.base import ProviderName, SpendSource, UnitKind, Use
from untangle.copy_catalog import api as copy_api
from untangle.providers import config as provider_config
from untangle.providers.ports import UsageReport, UsageUnits
from untangle.providers.speech_wire import ByteStream, DuplexChannel, SpeechRequest
from untangle.server import speech, voice_cli
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend import pricing
from untangle.telemetry.spend.models import BudgetState, VoiceMode
from untangle.tenancy import config as tenant_config

from . import replay
from .apoyo import Abierto, Registro, foto, redactado, techo

CATALINA = "162e0f37-8504-474c-bb33-c606c01890dc"


@pytest.fixture(autouse=True)
def proceso_limpio() -> Iterator[None]:
    yield
    copy_api.reset()
    spend.reset()


def _tenant() -> str:
    """La primera aseguradora cargada, sin escribir su identificador en la prueba."""
    return sorted(tenant_config.load().ids)[0]


def _ajustes() -> Settings:
    return Settings(
        voice_deepgram_api_key=secrets.token_urlsafe(24),
        voice_cartesia_api_key=secrets.token_urlsafe(24),
    )


def _plataforma(
    transportes: Mapping[ProviderName, Any], *, gate: Any = None
) -> tuple[speech.SpeechPlatform, voice_cli._Anotador]:
    anotador = voice_cli._Anotador(Registro())
    plataforma = speech.build_speech_platform(
        _ajustes(),
        provider_config.load(),
        tenant_config.load().available,
        transports=transportes,
        gate=gate if gate is not None else Abierto(),
        usage=anotador,
    )
    return plataforma, anotador


def _reproductor_espia(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    llamadas: list[list[str]] = []

    def correr(argumentos: list[str], **_: Any) -> subprocess.CompletedProcess[bytes]:
        llamadas.append(argumentos)
        return subprocess.CompletedProcess(argumentos, 0)

    monkeypatch.setattr(subprocess, "run", correr)
    return llamadas


def _wavs(carpeta: Path) -> list[Path]:
    """Los audios que dejo el comando. Fuera de las pruebas asincronas: lee el disco."""
    return sorted(carpeta.glob("*.wav"))


def _registro_simulado(monkeypatch: pytest.MonkeyPatch) -> None:
    """El libro de gasto, sustituido: ninguna prueba abre la base del proyecto."""

    async def abrir(*_: Any, **__: Any) -> None:
        return None

    async def cerrar() -> Decimal | None:
        return Decimal("0.0026")

    def registro(_ajustes: Settings) -> str:
        return "sin-base"

    monkeypatch.setattr(voice_cli, "_abrir_registro", abrir)
    monkeypatch.setattr(voice_cli, "_cerrar_registro", cerrar)
    monkeypatch.setattr(voice_cli, "_registro", registro)


# --- say, por el camino del aplicativo -----------------------------------------


async def test_say_deja_un_wav_en_el_formato_unico_por_el_camino_del_aplicativo(
    tmp_path: Path,
) -> None:
    """BR6.3, BR4.1: la voz de la aseguradora, con techo y gasto, en PCM16 mono 24 kHz."""
    fabrica = replay.ReplayFactory(replay.ReplayTransport(replay.load("cartesia-tts-sonic-3.6-es")))
    plataforma, anotador = _plataforma({ProviderName.CARTESIA: fabrica})
    pedido = voice_cli.SayRequest(
        tenant_id=_tenant(), language="es", mode=VoiceMode.PRIMARY, text=None
    )
    resultado = await voice_cli.say(
        plataforma,
        pedido,
        redactado(voice_cli.FRASES["es"], "es"),
        out_dir=tmp_path / "voz",
        now=datetime(2026, 9, 21, 12, 0, tzinfo=UTC),
    )

    assert resultado.path.parent == tmp_path / "voz"
    assert resultado.path.name == f"{_tenant()}-es-primary-20260921T120000.wav"
    assert resultado.voice.voice_id == CATALINA
    assert resultado.first_audio_ms is not None
    with wave.open(str(resultado.path), "rb") as archivo:
        assert archivo.getnchannels() == 1
        assert archivo.getsampwidth() == 2
        assert archivo.getframerate() == 24000
        assert archivo.getnframes() > 0
    assert [(r.provider, r.model) for r in anotador.reports] == [
        (ProviderName.CARTESIA, "sonic-3.6")
    ]


def test_sin_idioma_se_usa_el_de_la_voz_de_la_aseguradora() -> None:
    plataforma, _ = _plataforma({})
    pedido = voice_cli.SayRequest(
        tenant_id=_tenant(), language=None, mode=VoiceMode.FALLBACK, text=None
    )
    voz = voice_cli.resolve_voice(plataforma, pedido)
    assert voz.language == plataforma.voices[_tenant()].language_default
    assert voz.provider is ProviderName.DEEPGRAM


async def test_say_imprime_lo_gastado_y_el_acumulado_del_proyecto_y_no_reproduce(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """El gasto se anota en el libro del proyecto y la salida dice cuanto lleva la ventana."""
    _registro_simulado(monkeypatch)
    llamadas = _reproductor_espia(monkeypatch)
    fabrica = replay.ReplayFactory(replay.ReplayTransport(replay.load("cartesia-tts-sonic-3.6-es")))
    plataforma, anotador = _plataforma({ProviderName.CARTESIA: fabrica})
    pedido = voice_cli.SayRequest(
        tenant_id=_tenant(), language="es", mode=VoiceMode.PRIMARY, text=None
    )

    codigo = await voice_cli._say_live(
        plataforma,
        anotador,
        provider_config.load(),
        pedido,
        texto=redactado(voice_cli.FRASES["es"], "es"),
        url="sin-base",
        out_dir=tmp_path,
        reproducir=False,
    )

    salida = capsys.readouterr().out
    assert codigo == 0
    assert llamadas == []
    assert "Sin reproducir (--no-play)" in salida
    assert "Registro temporal" not in salida
    assert "cartesia  sonic-3.6  characters" in salida
    #: 54 caracteres a 0,00005 USD: la misma aritmetica que el libro mayor.
    assert "0.002700 USD" in salida
    assert "libro de gasto de la base del proyecto: 0.002600 USD" in salida
    assert "base efimera" not in salida
    assert _wavs(tmp_path)


async def test_con_el_techo_cerrado_say_se_detiene_sin_audio_y_lo_dice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """BR1.4, BR5.1: parada sin reintento, sin archivo y sin reproducir."""
    _registro_simulado(monkeypatch)
    llamadas = _reproductor_espia(monkeypatch)
    fabrica = replay.ReplayFactory(replay.ReplayTransport(replay.load("cartesia-tts-sonic-3.6-es")))
    plataforma, anotador = _plataforma({ProviderName.CARTESIA: fabrica}, gate=techo(gastado="5.00"))
    pedido = voice_cli.SayRequest(
        tenant_id=_tenant(), language="es", mode=VoiceMode.PRIMARY, text=None
    )

    codigo = await voice_cli._say_live(
        plataforma,
        anotador,
        provider_config.load(),
        pedido,
        texto=redactado("Hola.", "es"),
        url="sin-base",
        out_dir=tmp_path,
        reproducir=True,
    )

    salida = capsys.readouterr().out
    assert codigo == 2
    assert "SE DETUVO" in salida
    assert "ninguna llamada llego a contar unidades" in salida
    assert "libro de gasto de la base del proyecto" in salida
    assert not _wavs(tmp_path)
    assert llamadas == []
    assert isinstance(fabrica.transport, replay.ReplayTransport)
    assert fabrica.transport.requests == []


async def test_un_error_del_proveedor_en_say_sale_con_su_tipo_y_sin_reintento(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _registro_simulado(monkeypatch)
    _reproductor_espia(monkeypatch)
    fabrica = replay.ReplayFactory(
        replay.ReplayTransport(replay.load("cartesia-tts-error-500-unavailable"))
    )
    plataforma, anotador = _plataforma({ProviderName.CARTESIA: fabrica})
    pedido = voice_cli.SayRequest(
        tenant_id=_tenant(), language="es", mode=VoiceMode.PRIMARY, text=None
    )

    codigo = await voice_cli._say_live(
        plataforma,
        anotador,
        provider_config.load(),
        pedido,
        texto=redactado("Hola.", "es"),
        url="sin-base",
        out_dir=tmp_path,
        reproducir=True,
    )

    assert codigo == 1
    assert "La sintesis fallo: unavailable" in capsys.readouterr().out
    assert isinstance(fabrica.transport, replay.ReplayTransport)
    assert len(fabrica.transport.requests) == 1


# --- Lo gastado, a precio de lista ----------------------------------------------


def _reporte(proveedor: ProviderName, modelo: str, *unidades: tuple[UnitKind, str]) -> UsageReport:
    return UsageReport(
        provider=proveedor,
        model=modelo,
        use=Use.VOICE,
        units=tuple(UsageUnits(unit_kind=clase, units=Decimal(n)) for clase, n in unidades),
        source=SpendSource.COUNTED_LOCALLY,
    )


def test_lo_gastado_sale_en_unidades_y_dolares_con_la_tabla_del_libro_mayor() -> None:
    """NFR14.4: se suma por proveedor, modelo y clase, y se valora con la tabla versionada."""
    tabla = pricing.PriceTable.from_entries(provider_config.load().prices.price_entries())
    lineas = voice_cli.spend_lines(
        [
            _reporte(ProviderName.CARTESIA, "sonic-3.6", (UnitKind.CHARACTERS, "54")),
            _reporte(ProviderName.CARTESIA, "sonic-3.6", (UnitKind.CHARACTERS, "46")),
            _reporte(ProviderName.DEEPGRAM, "nova-3", (UnitKind.AUDIO_SECONDS, "6")),
        ],
        tabla,
    )

    assert lineas[0].split() == ["cartesia", "sonic-3.6", "characters", "100.00", "0.005000", "USD"]
    assert lineas[1].split()[:4] == ["deepgram", "nova-3", "audio_seconds", "6.00"]
    assert lineas[-1] == "  Total a precio de lista: 0.005920 USD"


def test_lo_que_no_tiene_precio_o_recuento_se_dice_y_el_total_avisa() -> None:
    """Nunca se suma como cero: una linea sin precio y una llamada sin recuento se nombran."""
    tabla = pricing.PriceTable.from_entries(provider_config.load().prices.price_entries())
    lineas = voice_cli.spend_lines(
        [
            _reporte(ProviderName.CARTESIA, "modelo-sin-precio", (UnitKind.CHARACTERS, "10")),
            _reporte(ProviderName.DEEPGRAM, "aura-2"),
        ],
        tabla,
    )

    assert "sin precio de lista" in lineas[0]
    assert any("1 llamada(s) sin recuento" in linea for linea in lineas)
    assert lineas[-1].endswith("(se queda corto: hay gasto sin valorar)")


# --- El reproductor ---------------------------------------------------------------


def test_se_usa_el_primer_reproductor_que_exista(monkeypatch: pytest.MonkeyPatch) -> None:
    existentes = {"aplay": "/usr/bin/aplay", "ffplay": "/usr/bin/ffplay"}
    monkeypatch.setattr(shutil, "which", existentes.get)
    assert voice_cli.find_player() == ["/usr/bin/aplay", "-q"]
    monkeypatch.setattr(shutil, "which", lambda _: None)
    assert voice_cli.find_player() is None


def test_reproducir_pasa_la_ruta_absoluta_y_el_archivo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    llamadas = _reproductor_espia(monkeypatch)
    archivo = tmp_path / "frase.wav"
    assert voice_cli.play(archivo, ["/usr/bin/afplay"])
    assert llamadas == [["/usr/bin/afplay", str(archivo)]]


@pytest.mark.parametrize("fallo", [OSError("sin permiso"), subprocess.TimeoutExpired("x", 60)])
def test_un_reproductor_que_falla_no_rompe_el_comando(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fallo: Exception,
) -> None:
    def correr(*_: Any, **__: Any) -> subprocess.CompletedProcess[bytes]:
        raise fallo

    monkeypatch.setattr(subprocess, "run", correr)
    monkeypatch.setattr(voice_cli, "find_player", lambda: ["/usr/bin/afplay"])
    voice_cli._reproducir_o_decir(tmp_path / "frase.wav", reproducir=True)
    assert "El reproductor no termino bien" in capsys.readouterr().out


def test_sin_reproductor_se_dice_donde_quedo_el_audio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(voice_cli, "find_player", lambda: None)
    voice_cli._reproducir_o_decir(tmp_path / "frase.wav", reproducir=True)
    assert "No hay reproductor" in capsys.readouterr().out


# --- La entrada del comando ---------------------------------------------------------


def _con_claves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNTANGLE_VOICE_DEEPGRAM_API_KEY", secrets.token_urlsafe(24))
    monkeypatch.setenv("UNTANGLE_VOICE_CARTESIA_API_KEY", secrets.token_urlsafe(24))


def test_main_say_de_punta_a_punta_con_el_doble(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """La entrada entera: argumentos, plataforma, voz, clave, redaccion, techo y archivo."""
    _con_claves(monkeypatch)
    _registro_simulado(monkeypatch)
    llamadas = _reproductor_espia(monkeypatch)

    async def presupuesto_abierto(**_: Any) -> BudgetState:
        return foto(gastado="0")

    async def libro(**_: Any) -> None:
        return None

    monkeypatch.setattr(spend, "budget_state", presupuesto_abierto)
    monkeypatch.setattr(spend, "record_spend", libro)
    fabrica = replay.ReplayFactory(replay.ReplayTransport(replay.load("deepgram-speak-aura-2-en")))
    monkeypatch.setattr(speech, "speech_transports", lambda: {ProviderName.DEEPGRAM: fabrica})

    codigo = voice_cli.main(
        [
            "say",
            "--tenant",
            _tenant(),
            "--language",
            "en",
            "--mode",
            "fallback",
            "--text",
            "Hello there.",
            "--no-play",
            "--out-dir",
            str(tmp_path),
        ]
    )

    salida = capsys.readouterr().out
    assert codigo == 0
    assert llamadas == []
    (archivo,) = tmp_path.glob("*.wav")
    assert archivo.name.startswith(f"{_tenant()}-en-fallback-")
    assert "aura-2-thalia-en" in salida
    assert isinstance(fabrica.transport, replay.ReplayTransport)
    assert fabrica.transport.requests[0].body == {"text": "Hello there."}


def test_main_say_con_una_aseguradora_que_no_existe_no_abre_ningun_registro(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    abiertos: list[str] = []

    def registro(_: Settings) -> str:
        abiertos.append("abierto")
        return "sin-base"

    monkeypatch.setattr(voice_cli, "_registro", registro)
    codigo = voice_cli.main(["say", "--tenant", "aseguradora-que-no-existe", "--no-play"])
    assert codigo == 1
    assert "no esta cargada" in capsys.readouterr().err
    assert abiertos == []


@pytest.mark.parametrize("comando", ["say", "contract-live"])
def test_main_sin_clave_de_voz_falla_nombrando_la_variable_antes_del_registro(
    comando: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("UNTANGLE_VOICE_DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("UNTANGLE_VOICE_CARTESIA_API_KEY", raising=False)
    argumentos = [comando]
    if comando == "say":
        argumentos += ["--tenant", _tenant(), "--no-play"]

    assert voice_cli.main(argumentos) == 2
    assert "UNTANGLE_VOICE_CARTESIA_API_KEY" in capsys.readouterr().err


def test_sin_base_del_proyecto_el_comando_no_llama(monkeypatch: pytest.MonkeyPatch) -> None:
    """La voz falla cerrada: sin registro de gasto no hay llamada (BR5.1)."""
    _con_claves(monkeypatch)
    monkeypatch.delenv("UNTANGLE_DATABASE_URL", raising=False)
    with pytest.raises(SystemExit, match="UNTANGLE_DATABASE_URL") as parada:
        voice_cli.main(["say", "--tenant", _tenant(), "--no-play"])
    # Dice que falta y que no se llamo a nadie; ya no ofrece un libro temporal.
    assert "No se llamo a ningun proveedor" in str(parada.value)
    assert "ephemeral" not in str(parada.value)


def test_el_libro_temporal_ya_no_se_ofrece(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un gasto en un libro que se borra no cuenta contra el techo: la bandera ya no existe."""
    for comando in (["say", "--tenant", _tenant()], ["contract-live"], ["call-live"]):
        with pytest.raises(SystemExit) as salida:
            voice_cli.main([*comando, "--ledger", "ephemeral"])
        assert salida.value.code == 2  # argparse: argumento no reconocido


async def test_con_el_libro_abre_antes_de_correr_y_cierra_aunque_la_corrida_se_corte(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`call-live` no abria el libro: ahora lo abre antes de gastar y lo cierra siempre."""
    pasos: list[str] = []

    async def abrir(_config: Any, url: str) -> None:
        pasos.append(f"abrir {url}")

    async def cerrar() -> Decimal | None:
        pasos.append("cerrar")
        return Decimal("0.5")

    async def correr() -> int:
        pasos.append("correr")
        msg = "la corrida se corto"
        raise RuntimeError(msg)

    monkeypatch.setattr(voice_cli, "_abrir_registro", abrir)
    monkeypatch.setattr(voice_cli, "_cerrar_registro", cerrar)
    anotador = voice_cli._Anotador(Registro())

    with pytest.raises(RuntimeError, match="se corto"):
        await voice_cli._con_el_libro(provider_config.load(), anotador, "el-libro", correr)

    assert pasos == ["abrir el-libro", "correr", "cerrar"]
    assert "libro de gasto de la base del proyecto: 0.500000 USD" in capsys.readouterr().out


async def test_con_el_libro_no_corre_nada_si_el_libro_no_se_puede_abrir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin libro no se llama a nadie: la corrida ni empieza y no hay nada que cerrar."""
    pasos: list[str] = []

    async def abrir(_config: Any, _url: str) -> None:
        msg = "la base del proyecto no esta"
        raise SystemExit(msg)

    async def cerrar() -> Decimal | None:
        pasos.append("cerrar")
        return None

    async def correr() -> int:
        pasos.append("correr")
        return 0

    monkeypatch.setattr(voice_cli, "_abrir_registro", abrir)
    monkeypatch.setattr(voice_cli, "_cerrar_registro", cerrar)

    with pytest.raises(SystemExit, match="la base del proyecto no esta"):
        await voice_cli._con_el_libro(
            provider_config.load(), voice_cli._Anotador(Registro()), "el-libro", correr
        )

    assert pasos == []


# --- contract-live, con la respuesta grabada en lugar del proveedor ----------------


class _Enrutado:
    """Un proveedor grabado que contesta cada peticion con la grabacion de su ruta, en orden."""

    def __init__(self, colas: dict[str, list[str]], catalogo: dict[str, Any]) -> None:
        self._colas = {ruta: list(nombres) for ruta, nombres in colas.items()}
        self._catalogo = catalogo
        self.requests: list[SpeechRequest] = []

    def _siguiente(self, request: SpeechRequest) -> replay.ReplayTransport:
        return replay.ReplayTransport(replay.load(self._colas[request.path].pop(0)))

    @asynccontextmanager
    async def open_duplex(self, request: SpeechRequest) -> AsyncIterator[DuplexChannel]:
        self.requests.append(request)
        async with self._siguiente(request).open_duplex(request) as canal:
            yield canal

    @asynccontextmanager
    async def stream_post(self, request: SpeechRequest) -> AsyncIterator[ByteStream]:
        self.requests.append(request)
        async with self._siguiente(request).stream_post(request) as flujo:
            yield flujo

    async def get_json(self, request: SpeechRequest) -> tuple[int, Mapping[str, object]]:
        return await replay.ReplayTransport({"catalog": self._catalogo}).get_json(request)


def _proveedores_grabados(voces_de_deepgram: list[str]) -> dict[ProviderName, replay.ReplayFactory]:
    deepgram = _Enrutado(
        {
            "v1/speak": ["deepgram-speak-aura-2-es", "deepgram-speak-aura-2-en"],
            "v1/listen": ["deepgram-listen-nova-3-es", "deepgram-listen-nova-3-en"],
        },
        {
            "v1/models": {
                "status": 200,
                "body": {"tts": [{"canonical_name": v} for v in voces_de_deepgram]},
            }
        },
    )
    cartesia = _Enrutado(
        {"tts/websocket": ["cartesia-tts-sonic-3.6-en", "cartesia-tts-sonic-3.6-es"]},
        {f"voices/{CATALINA}": {"status": 200}},
    )
    return {
        ProviderName.DEEPGRAM: replay.ReplayFactory(deepgram),
        ProviderName.CARTESIA: replay.ReplayFactory(cartesia),
    }


async def test_contract_live_publica_la_latencia_al_primer_audio_de_cada_voz(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """TECH-U15.2: el texto fijo, cada voz de las aseguradoras, su tiempo y su gasto."""
    _registro_simulado(monkeypatch)
    plataforma, anotador = _plataforma(
        _proveedores_grabados(["aura-2-celeste-es", "aura-2-thalia-en"])
    )

    codigo = await voice_cli._contract_live(
        plataforma, anotador, provider_config.load(), None, "sin-base"
    )

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "TECH-U15.2" in salida
    # Del renglon siguiente al encabezado hasta el encabezado del bloque de gasto.
    bloque = salida.split("(TECH-U15.2)", 1)[1].split("\n", 1)[1].split("\n---", 1)[0]
    for sonda in (
        "cartesia-tts-sonic-3.6-en",
        "cartesia-tts-sonic-3.6-es",
        "deepgram-speak-aura-2-es",
        "deepgram-speak-aura-2-en",
    ):
        assert sonda in bloque
    assert bloque.count(" ms") == 4
    assert "[OK ] deepgram-listen-nova-3-es" in salida
    assert "[OK ] deepgram-listen-nova-3-en" in salida
    assert "audio_seconds" in salida
    assert "libro de gasto de la base del proyecto: 0.002600 USD" in salida
    assert "Registro temporal" not in salida


async def test_contract_live_no_sintetiza_si_una_voz_no_esta_en_la_lista(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Las consultas de catalogo no cuestan; la primera sintesis si, y no ocurre."""
    _registro_simulado(monkeypatch)
    fabricas = _proveedores_grabados(["aura-2-celeste-es"])
    plataforma, anotador = _plataforma(fabricas)

    codigo = await voice_cli._contract_live(
        plataforma, anotador, provider_config.load(), None, "sin-base"
    )

    assert codigo == 1
    assert "deepgram:aura-2-thalia-en" in capsys.readouterr().out
    for fabrica in fabricas.values():
        enrutado = fabrica.transport
        assert isinstance(enrutado, _Enrutado)
        assert all(r.path.startswith(("v1/models", "voices/")) for r in enrutado.requests)
    assert anotador.reports == []


def test_las_voces_declaradas_son_las_de_las_aseguradoras_con_voz() -> None:
    plataforma, _ = _plataforma({})
    voces, modelos = voice_cli.declared_voices(plataforma)
    assert {(v.provider, v.voice_id, v.language) for v in voces} == {
        (ProviderName.CARTESIA, CATALINA, "es"),
        (ProviderName.CARTESIA, CATALINA, "en"),
        (ProviderName.DEEPGRAM, "aura-2-celeste-es", "es"),
        (ProviderName.DEEPGRAM, "aura-2-thalia-en", "en"),
    }
    assert [m.model for m in modelos] == ["nova-3"]
