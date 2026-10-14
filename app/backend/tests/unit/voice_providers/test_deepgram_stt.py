"""La transcripcion de Deepgram contra sus respuestas grabadas (BR3.1, BR3.2, BR5.1, BR6.1).

Las dos respuestas de contrato se capturaron el 2026-09-21 transcribiendo el
audio de Catalina en espanol y en ingles con `nova-3` en modo `multi`. De ahi
salen los hechos que estas pruebas fijan:

- Deepgram **si** manda la confianza de cada palabra en streaming (PA-2): once de
  once en espanol y nueve de nueve en ingles.
- El idioma detectado llega en la alternativa (`languages`) y en cada palabra.
- El resultado forzado por `Finalize` llega marcado `from_finalize` y trae la
  frase entera.
"""

from __future__ import annotations

import copy
from collections.abc import AsyncIterator, Iterator
from decimal import Decimal
from typing import Any

import pytest

from untangle.base import ProviderErrorKind, ProviderName, SpendSource, UnitKind, Use
from untangle.providers.adapters.deepgram import DeepgramSpeechToText
from untangle.providers.adapters.speech_common import SpeechMisconfiguredError
from untangle.providers.ports import (
    BudgetExhausted,
    ExhaustedResource,
    ProviderError,
    SpeechStarted,
    Transcript,
)
from untangle.providers.voice_availability import SpeechModel
from untangle.tenancy.models import TranscriptionMode

from . import replay
from .apoyo import TIEMPOS, Abierto, Eventos, Registro, audio_de, clientes, techo

MODELO = SpeechModel(provider=ProviderName.DEEPGRAM, model="nova-3", mode=TranscriptionMode.MULTI)


def _adaptador(
    fixture: dict[str, Any], *, gate: Any = None, reloj: Any = None
) -> tuple[DeepgramSpeechToText, replay.ReplayTransport, Registro]:
    caller, transporte, _ = clientes(ProviderName.DEEPGRAM, fixture)
    registro = Registro()
    extra = {"clock": reloj} if reloj is not None else {}
    stt = DeepgramSpeechToText(
        caller,
        model=MODELO,
        gate=gate if gate is not None else Abierto(),
        usage=registro,
        timeouts=TIEMPOS,
        **extra,
    )
    return stt, transporte, registro


async def _transcritos(stt: DeepgramSpeechToText, audio: AsyncIterator[bytes]) -> list[Transcript]:
    """Solo los transcritos de lo que entrega la escucha: sin las senales de voz."""
    return [e async for e in stt.stream(audio, language="es") if isinstance(e, Transcript)]


def _palabras_finales(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    final = next(m["text"] for m in fixture["received"] if m["text"].get("from_finalize"))
    palabras = final["channel"]["alternatives"][0]["words"]
    assert isinstance(palabras, list)
    return palabras


@pytest.mark.parametrize("idioma", ["es", "en"])
async def test_la_respuesta_grabada_cumple_el_contrato(idioma: str) -> None:
    """BR6.1 y BR3.1: parciales y finales, confianza por palabra e idioma detectado."""
    grabada = replay.load(f"deepgram-listen-nova-3-{idioma}")
    stt, transporte, registro = _adaptador(grabada)
    bytes_subidos = 48000

    eventos = [e async for e in stt.stream(audio_de(bytes_subidos), language="es")]

    assert not any(isinstance(e, SpeechStarted) for e in eventos), "la grabacion no las trae"
    resultados = [e for e in eventos if isinstance(e, Transcript)]
    assert any(not t.is_final for t in resultados), "sin parciales"
    finales = [t for t in resultados if t.is_final]
    assert len(finales) == 1
    assert {t.language for t in resultados} == {idioma}
    # PA-2: la confianza de cada palabra se conserva **tal cual** la mando Deepgram.
    esperadas = [p["confidence"] for p in _palabras_finales(grabada)]
    assert [p.confidence for p in finales[0].words] == esperadas
    assert all(p.end_s >= p.start_s for p in finales[0].words)

    peticion = transporte.requests[0]
    assert peticion.path == "v1/listen"
    assert dict(peticion.query) == {
        "model": "nova-3",
        "language": "multi",
        "encoding": "linear16",
        "sample_rate": "24000",
        "channels": "1",
        "interim_results": "true",
        # Desde el 2026-10-12: la senal de que alguien empezo a hablar, en decimas de
        # segundo. Las grabaciones de contrato son anteriores y no traen `SpeechStarted`.
        "vad_events": "true",
        # Desde el 2026-10-09: la puntuacion y las cifras escritas como cifras. La
        # llamada usa el punto final para saber si la frase termino.
        "smart_format": "true",
    }
    canal = transporte.channels[0]
    assert [m["type"] for m in canal.sent_texts] == ["Finalize", "CloseStream"]
    assert canal.sent_bytes == bytes_subidos

    # El gasto: los segundos de audio que subieron, con el modelo que tiene precio.
    (reporte,) = registro.reports
    assert (reporte.provider, reporte.model, reporte.use) == (
        ProviderName.DEEPGRAM,
        "nova-3",
        Use.VOICE,
    )
    assert reporte.source is SpendSource.COUNTED_LOCALLY
    assert [(u.unit_kind, u.units) for u in reporte.units] == [(UnitKind.AUDIO_SECONDS, Decimal(1))]


async def test_una_palabra_sin_confianza_la_lleva_nula_y_nunca_cero() -> None:
    """BR3.1: si el proveedor no la manda, nula. Cero diria "seguro de que se equivoco"."""
    grabada = copy.deepcopy(replay.load("deepgram-listen-nova-3-es"))
    for marco in grabada["received"]:
        for palabra in marco["text"]["channel"]["alternatives"][0]["words"]:
            palabra.pop("confidence", None)
    stt, _, _ = _adaptador(grabada)

    resultados = await _transcritos(stt, audio_de(960))

    palabras = [p for t in resultados for p in t.words]
    assert palabras
    assert all(p.confidence is None for p in palabras)


async def test_el_final_espera_a_finalize_y_trae_la_frase_entera() -> None:
    """La leccion del experimento 1: el fin es la respuesta a `Finalize`, no el primer final."""
    grabada = replay.load("deepgram-listen-nova-3-es")
    stt, transporte, _ = _adaptador(grabada)

    resultados = await _transcritos(stt, audio_de(9600))

    final = resultados[-1]
    assert final.is_final
    assert (
        final.text
        == grabada["received"][-1]["text"]["channel"]["alternatives"][0]["transcript"].strip()
    )
    # `Finalize` salio despues de todo el audio, y `CloseStream` despues del final.
    assert transporte.channels[0].sent_bytes == 9600
    assert transporte.channels[0].sent_texts[-1] == {"type": "CloseStream"}


# --- La senal de voz (`vad_events`, 2026-10-12) -------------------------------------
#
# Las grabaciones de contrato se capturaron sin pedir `vad_events` y no traen ningun
# `SpeechStarted`: estas pruebas los insertan en la grabacion con la forma que documenta
# Deepgram (`type`, `channel`, `timestamp`). El contrato real queda por capturar con
# `mise run voice:contract-live -- --record`.


_AUSENTE = object()


def _senal(marca: object) -> dict[str, Any]:
    mensaje: dict[str, Any] = {"type": "SpeechStarted", "channel": [0]}
    if marca is not _AUSENTE:
        mensaje["timestamp"] = marca
    return {"text": mensaje}


def _con_senales(*senales: tuple[int, dict[str, Any]]) -> dict[str, Any]:
    """La grabacion en espanol con cada senal insertada en su posicion de `received`."""
    grabada = copy.deepcopy(replay.load("deepgram-listen-nova-3-es"))
    for posicion, marco in sorted(senales, key=lambda senal: senal[0], reverse=True):
        grabada["received"].insert(posicion, marco)
    return grabada


async def test_la_senal_de_voz_se_entrega_con_su_tipo_y_su_tiempo_entre_los_transcritos() -> None:
    sin_senales = await _transcritos(
        _adaptador(replay.load("deepgram-listen-nova-3-es"))[0], audio_de(960)
    )
    stt, _, _ = _adaptador(_con_senales((0, _senal(0.3)), (2, _senal(1.75))))

    eventos = [e async for e in stt.stream(audio_de(960), language="es")]

    assert [e for e in eventos if isinstance(e, Transcript)] == sin_senales
    assert eventos[0] == SpeechStarted(at_s=0.3)
    assert eventos[3] == SpeechStarted(at_s=1.75), "la senal sale donde llego, entre dos parciales"
    assert [e.at_s for e in eventos if isinstance(e, SpeechStarted)] == [0.3, 1.75]


async def test_una_senal_a_los_cero_segundos_y_una_con_entero_se_entregan_como_flotantes() -> None:
    stt, _, _ = _adaptador(_con_senales((0, _senal(0)), (1, _senal(1))))

    eventos = [e async for e in stt.stream(audio_de(960), language="es")]

    entero = eventos[2]
    assert entero == SpeechStarted(at_s=1.0)
    assert isinstance(entero, SpeechStarted)
    assert type(entero.at_s) is float
    assert eventos[0] == SpeechStarted(at_s=0.0)


@pytest.mark.parametrize(
    "marca",
    [
        pytest.param(_AUSENTE, id="sin-timestamp"),
        pytest.param(None, id="timestamp-nulo"),
        pytest.param("0.3", id="timestamp-texto"),
        pytest.param(True, id="timestamp-booleano"),
        pytest.param(-0.5, id="timestamp-negativo"),
        pytest.param(float("nan"), id="timestamp-nan"),
        pytest.param(float("inf"), id="timestamp-infinito"),
        pytest.param([0.3], id="timestamp-lista"),
    ],
)
async def test_una_senal_mal_formada_no_rompe_la_escucha(marca: object) -> None:
    """La senal es una ayuda: sin ella la llamada queda como antes de pedirla. Un mensaje
    que no se entiende se descarta, y los transcritos de alrededor llegan completos y sin
    ningun error. Distinto de un `Results` roto, que si es una respuesta invalida."""
    sin_senales = await _transcritos(
        _adaptador(replay.load("deepgram-listen-nova-3-es"))[0], audio_de(960)
    )
    stt, _, registro = _adaptador(_con_senales((0, _senal(marca)), (2, _senal(marca))))

    eventos = [e async for e in stt.stream(audio_de(960), language="es")]

    assert eventos == sin_senales
    assert len(registro.reports) == 1, "la llamada se cerro con su gasto, sin fallar"


def _sin_final_forzado(nombre: str) -> dict[str, Any]:
    grabada = copy.deepcopy(replay.load(nombre))
    grabada["received"] = [m for m in grabada["received"] if not m["text"].get("from_finalize")]
    return grabada


def _resultado_roto(nombre: str) -> dict[str, Any]:
    grabada = copy.deepcopy(replay.load(nombre))
    del grabada["received"][0]["text"]["channel"]
    return grabada


class _Reloj:
    """Un reloj que avanza un segundo cada vez que se mira: el tiempo maximo de dos
    segundos se agota en tres miradas, sin esperar de verdad."""

    def __init__(self) -> None:
        self.ahora = 0.0

    def __call__(self) -> float:
        self.ahora += 1.0
        return self.ahora


@pytest.mark.parametrize(
    ("fixture", "esperado"),
    [
        pytest.param(
            replay.load("deepgram-listen-402-no-credit"), "exhausted", id="402-saldo-agotado"
        ),
        pytest.param(
            replay.load("deepgram-listen-closed-1011"),
            ProviderErrorKind.UNAVAILABLE,
            id="cierre-1011",
        ),
        pytest.param(
            _resultado_roto("deepgram-listen-nova-3-es"),
            ProviderErrorKind.INVALID_RESPONSE,
            id="resultado-sin-channel",
        ),
        pytest.param(
            _sin_final_forzado("deepgram-listen-nova-3-en"),
            ProviderErrorKind.TIMEOUT,
            id="finalize-sin-respuesta",
        ),
    ],
)
async def test_cada_error_sale_en_la_taxonomia_con_un_solo_intento(
    fixture: dict[str, Any], esperado: ProviderErrorKind | str, eventos: Eventos
) -> None:
    """BR1.4: ningun tipo del proveedor cruza, el saldo agotado es parada, y no se reintenta."""
    stt, transporte, registro = _adaptador(fixture, reloj=_Reloj())

    with pytest.raises((ProviderError, BudgetExhausted)) as capturado:
        _ = [t async for t in stt.stream(audio_de(960), language="es")]

    if esperado == "exhausted":
        assert isinstance(capturado.value, BudgetExhausted)
        assert capturado.value.resource is ExhaustedResource.PROVIDER_QUOTA
    else:
        assert isinstance(capturado.value, ProviderError)
        assert capturado.value.kind is esperado
        assert capturado.value.attempt == 1
    assert len(transporte.requests) == 1
    # La llamada existio y deja su fila, con lo que subio: nunca "no medida".
    assert len(registro.reports) == 1
    assert registro.reports[0].units[0].unit_kind is UnitKind.AUDIO_SECONDS


async def test_con_el_techo_cerrado_no_se_abre_ninguna_conexion(eventos: Eventos) -> None:
    """BR5.1, SEC-U15.3: acumulado forzado al techo, cero llamadas y parada sin reintento."""
    stt, transporte, registro = _adaptador(
        replay.load("deepgram-listen-nova-3-es"), gate=techo(gastado="5.00")
    )

    with pytest.raises(BudgetExhausted) as capturado:
        _ = [t async for t in stt.stream(audio_de(960), language="es")]

    assert capturado.value.resource is ExhaustedResource.PROJECT_CAP
    assert transporte.requests == []
    assert registro.reports == []
    assert [e["event"] for e in eventos.lineas if e["event"].startswith("providers.")] == [
        "providers.budget_exhausted"
    ]


async def test_ni_el_texto_transcrito_ni_el_audio_salen_en_un_evento(eventos: Eventos) -> None:
    """BR3.2, SEC-U15.4, NFR11.9: los eventos llevan proveedor, uso y tipo; nada mas."""
    for nombre in ("deepgram-listen-nova-3-es", "deepgram-listen-closed-1011"):
        stt, _, _ = _adaptador(replay.load(nombre))
        try:
            _ = [t async for t in stt.stream(audio_de(960), language="es")]
        except ProviderError:
            pass

    propios = [e for e in eventos.lineas if e["event"].startswith("providers.")]
    assert propios, "el error tenia que dejar su evento"
    assert all(set(e) <= {"event", "provider", "use", "error_kind"} for e in propios)
    for palabra in ("hola", "prueba", "demostración"):
        assert palabra not in eventos.crudo


def test_el_adaptador_no_acepta_un_modelo_de_otro_proveedor() -> None:
    caller, _, _ = clientes(ProviderName.DEEPGRAM, {})
    ajeno = SpeechModel(
        provider=ProviderName.CARTESIA, model="nova-3", mode=TranscriptionMode.MULTI
    )
    with pytest.raises(SpeechMisconfiguredError):
        DeepgramSpeechToText(
            caller, model=ajeno, gate=Abierto(), usage=Registro(), timeouts=TIEMPOS
        )


@pytest.fixture(autouse=True)
def _sin_escribir_en_disco(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """NFR19.5: la transcripcion no escribe nada en disco, ni audio ni texto."""
    import builtins
    import io as io_modulo

    original = builtins.open

    def _abrir(archivo: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if any(letra in mode for letra in "wax+"):
            msg = f"el adaptador intento escribir en disco: {archivo!r}"
            raise AssertionError(msg)
        return original(archivo, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", _abrir)
    monkeypatch.setattr(io_modulo, "open", _abrir)
    yield
