"""El cableado de la voz: fabrica por uso, disponibilidad en proceso y topes (U15, paso 11).

Lo que se comprueba es que las piezas del paso 8 esten **conectadas**, no que
cada una funcione --eso lo dicen las pruebas de cada adaptador--:

- **La raiz del proceso servido expone la voz** en `app.state.speech`, con la
  disponibilidad de cada aseguradora decidida al arrancar y sin red (BR2.1,
  BR2.2), que es donde U16 la lee.
- **La fabrica del uso `voice`** construye cada proveedor con su clave y ninguna
  otra (BR1.3, SEC-U15.2), y la plataforma habla y escucha por el techo, el
  adaptador y el gasto (BR5.1).
- **Una voz apagada no se construye**: pedirla falla nombrando el motivo antes
  de que salga ninguna peticion.
- **Sin base, la voz del proceso servido queda cerrada** (BR5.1).
- **El catalogo de voces vive en cada adaptador** (BR1.1) y su fallo de red sale
  en la taxonomia cerrada, sin contenido.
- **Todo proveedor de voz declara su tope** del uso `voice`, y `schema:check`
  falla si falta (PA-9.2).

Ninguna prueba sale a la red: la guardia de `conftest.py` la haria fallar.
"""

from __future__ import annotations

import copy
import secrets
import shutil
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from untangle import paths
from untangle.base import ProviderErrorKind, ProviderName, Use
from untangle.copy_catalog import api as copy_api
from untangle.providers import config as provider_config
from untangle.providers.config import CapKind
from untangle.providers.ports import (
    BudgetExhausted,
    ExhaustedResource,
    ProviderError,
    Transcript,
    VoiceRef,
)
from untangle.providers.transport import TransportError
from untangle.providers.voice_availability import VoiceOffReason, VoiceUnavailableError
from untangle.server import composition, speech, spend_wiring
from untangle.settings import Settings
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend.models import VoiceMode
from untangle.tenancy import config as tenant_config
from untangle.tenancy import session
from untangle.workspace import schema_check

from . import replay
from .apoyo import Abierto, Eventos, Registro, audio_de, redactado

CATALINA = "162e0f37-8504-474c-bb33-c606c01890dc"


@pytest.fixture(autouse=True)
def proceso_limpio() -> Iterator[None]:
    """La raiz instala el catalogo y la contabilidad en variables de modulo."""
    yield
    copy_api.reset()
    spend.reset()


def _ajustes() -> Settings:
    """Claves generadas en cada prueba: ninguna es real ni fija."""
    return Settings(
        voice_deepgram_api_key=secrets.token_urlsafe(24),
        voice_cartesia_api_key=secrets.token_urlsafe(24),
        chat_model_api_key=secrets.token_urlsafe(24),
    )


def _fabricas(
    deepgram: str | None = None, cartesia: str | None = None
) -> dict[ProviderName, replay.ReplayFactory]:
    return {
        ProviderName.DEEPGRAM: replay.ReplayFactory(
            replay.ReplayTransport(replay.load(deepgram) if deepgram else {})
        ),
        ProviderName.CARTESIA: replay.ReplayFactory(
            replay.ReplayTransport(replay.load(cartesia) if cartesia else {})
        ),
    }


def _plataforma(
    fabricas: dict[ProviderName, replay.ReplayFactory],
    *,
    ajustes: Settings | None = None,
    registro: Registro | None = None,
    techo: Abierto | None = None,
) -> tuple[speech.SpeechPlatform, Registro, Abierto]:
    usado = registro if registro is not None else Registro()
    gate = techo if techo is not None else Abierto()
    plataforma = speech.build_speech_platform(
        ajustes if ajustes is not None else _ajustes(),
        provider_config.load(),
        tenant_config.load().available,
        transports=fabricas,
        gate=gate,
        usage=usado,
    )
    return plataforma, usado, gate


def _una_aseguradora() -> str:
    """La primera aseguradora cargada, sin escribir su identificador en la prueba."""
    return sorted(tenant_config.load().ids)[0]


# --- La raiz del proceso servido ----------------------------------------------


def test_la_raiz_expone_la_voz_de_cada_aseguradora_en_proceso() -> None:
    """U16 lee `app.state.speech`: la disponibilidad ya decidida, sin red y sin claves."""
    app = composition.build_app(Settings(env="local", database_url=None))

    voz = app.state.speech
    assert isinstance(voz, speech.SpeechPlatform)
    cargadas = tenant_config.load().ids
    assert set(voz.availability) == set(cargadas)
    for tenant_id in cargadas:
        assert voz.availability_for(tenant_id).available
    #: Sin claves de voz no se construye ningun cliente, y nada falla al arrancar.
    assert voz.clients.available() == ()
    #: El gasto de la voz va al libro mayor de verdad, no a un doble.
    assert isinstance(voz.usage, spend_wiring.LedgerUsageSink)


async def test_sin_base_la_voz_del_proceso_servido_queda_cerrada() -> None:
    """BR5.1: el techo de la raiz no se puede leer sin base, y la voz no llama."""
    await session.dispose()
    spend.install(spend_wiring.spend_runtime(provider_config.load()))
    fabricas = _fabricas(cartesia="cartesia-tts-sonic-3.6-es")
    plataforma = speech.build_speech_platform(
        _ajustes(), provider_config.load(), tenant_config.load().available, transports=fabricas
    )
    tenant = _una_aseguradora()

    with pytest.raises(BudgetExhausted):
        _ = [
            t
            async for t in plataforma.speak(
                tenant, redactado("Hola.", "es"), mode=VoiceMode.PRIMARY, language="es"
            )
        ]

    transporte = fabricas[ProviderName.CARTESIA].transport
    assert isinstance(transporte, replay.ReplayTransport)
    assert transporte.requests == []


# --- La fabrica del uso `voice` y la plataforma --------------------------------


def test_la_fabrica_construye_cada_proveedor_de_voz_con_su_clave() -> None:
    """BR1.3, SEC-U15.2: la de Deepgram a Deepgram, la de Cartesia a Cartesia, uso `voice`."""
    ajustes = _ajustes()
    fabricas = _fabricas()
    plataforma, _, _ = _plataforma(fabricas, ajustes=ajustes)

    assert fabricas[ProviderName.DEEPGRAM].created == [(ajustes.voice_deepgram_api_key, Use.VOICE)]
    assert fabricas[ProviderName.CARTESIA].created == [(ajustes.voice_cartesia_api_key, Use.VOICE)]
    assert ajustes.chat_model_api_key not in {
        clave for fabrica in fabricas.values() for clave, _ in fabrica.created
    }
    assert plataforma.clients.available() == (ProviderName.CARTESIA, ProviderName.DEEPGRAM)
    #: Los tiempos son los del uso `voice` de `providers.yaml`.
    uso = provider_config.load().providers.for_use(Use.VOICE)
    assert plataforma.timeouts.read_timeout_ms == uso.read_timeout_ms


@pytest.mark.parametrize(
    ("modo", "grabada", "proveedor", "modelo"),
    [
        (VoiceMode.PRIMARY, "cartesia-tts-sonic-3.6-es", ProviderName.CARTESIA, "sonic-3.6"),
        (VoiceMode.FALLBACK, "deepgram-speak-aura-2-es", ProviderName.DEEPGRAM, "aura-2"),
    ],
)
async def test_hablar_por_la_plataforma_pasa_por_techo_adaptador_y_gasto(
    modo: VoiceMode, grabada: str, proveedor: ProviderName, modelo: str
) -> None:
    """La voz de la aseguradora en ese modo, con el techo antes y el gasto despues."""
    fabricas = _fabricas(
        deepgram=grabada if proveedor is ProviderName.DEEPGRAM else None,
        cartesia=grabada if proveedor is ProviderName.CARTESIA else None,
    )
    plataforma, registro, techo = _plataforma(fabricas)
    tenant = _una_aseguradora()

    audio = b"".join(
        [
            t
            async for t in plataforma.speak(
                tenant, redactado("Hola, esta es una prueba.", "es"), mode=modo, language="es"
            )
        ]
    )

    assert audio
    assert len(audio) % 2 == 0
    assert techo.consultas == 1
    assert [(r.provider, r.model) for r in registro.reports] == [(proveedor, modelo)]
    assert plataforma.voice_for(tenant, mode=modo, language="es").provider is proveedor


# --- La voz de respaldo cuando la principal se queda sin cupo (2026-10-03) -----

SIN_CUPO = "cartesia-tts-error-402-no-credit"
RESPALDO = "deepgram-speak-aura-2-es"
FRASE = "Hola, esta es una prueba."


async def _hablar(plataforma: speech.SpeechPlatform, tenant: str) -> bytes:
    frase = redactado(FRASE, "es")
    trozos = plataforma.speak(tenant, frase, mode=VoiceMode.PRIMARY, language="es")
    return b"".join([t async for t in trozos])


async def test_sin_cupo_en_la_voz_principal_la_frase_suena_con_la_de_respaldo() -> None:
    """El proveedor de la principal contesta 402 y quien llama oye la otra voz, no un fallo."""
    plataforma, registro, _ = _plataforma(_fabricas(deepgram=RESPALDO, cartesia=SIN_CUPO))

    audio = await _hablar(plataforma, _una_aseguradora())

    assert audio
    # El intento rechazado tambien deja su fila: el adaptador cuenta lo que mando.
    assert [r.provider for r in registro.reports] == [ProviderName.CARTESIA, ProviderName.DEEPGRAM]


async def test_a_la_voz_sin_cupo_no_se_le_pregunta_otra_vez_hasta_que_pasa_el_plazo() -> None:
    """Se le cree al proveedor un rato: la frase siguiente va directo a la de respaldo."""
    instante = [datetime(2026, 10, 11, 12, 0, tzinfo=UTC)]
    plataforma, _, techo = _plataforma(_fabricas(deepgram=RESPALDO, cartesia=SIN_CUPO))
    plataforma = replace(plataforma, now=lambda: instante[0])
    tenant = _una_aseguradora()

    await _hablar(plataforma, tenant)
    tras_el_rechazo = techo.consultas
    await _hablar(plataforma, tenant)
    dentro_del_plazo = techo.consultas - tras_el_rechazo
    instante[0] += speech.PRIMARY_RETRY_AFTER
    await _hablar(plataforma, tenant)
    pasado_el_plazo = techo.consultas - tras_el_rechazo - dentro_del_plazo

    # El techo se consulta una vez por proveedor al que se le pide la frase.
    assert (tras_el_rechazo, dentro_del_plazo, pasado_el_plazo) == (2, 1, 2)


class _TechoDelProyecto:
    """El techo del proyecto alcanzado: para a cualquier proveedor."""

    async def ensure_open(self, *, provider: ProviderName, use: Use) -> None:
        raise BudgetExhausted(ExhaustedResource.PROJECT_CAP, provider=provider, use=use)


async def test_el_techo_del_proyecto_no_se_esquiva_con_la_voz_de_respaldo() -> None:
    """Lo que se acabo es el presupuesto, no el cupo de un proveedor: la llamada para."""
    plataforma, registro, _ = _plataforma(_fabricas(deepgram=RESPALDO, cartesia=SIN_CUPO))
    plataforma = replace(plataforma, gate=_TechoDelProyecto())

    with pytest.raises(BudgetExhausted) as parada:
        await _hablar(plataforma, _una_aseguradora())

    assert parada.value.resource is ExhaustedResource.PROJECT_CAP
    assert parada.value.provider is ProviderName.CARTESIA
    assert registro.reports == []


# --- Cualquier otro fallo de la principal, tambien a mitad de frase (AC2.10.4) ---


def _principal_que_se_corta(*, tras_trozos: int, cierre: int | None) -> dict[str, Any]:
    """La grabada de Cartesia, cortada tras `tras_trozos` trozos de audio.

    Con `cierre` el canal se cae con ese codigo; sin el, el proveedor deja de mandar y se
    agota el tiempo de lectura. Es lo que pasa cuando la voz se cae **con la frase empezada**.
    """
    grabada = copy.deepcopy(replay.load("cartesia-tts-sonic-3.6-es"))
    grabada["received"] = grabada["received"][:tras_trozos]
    grabada["closed"] = None if cierre is None else {"code": cierre}
    return grabada


def _fabricas_con(principal: dict[str, Any]) -> dict[ProviderName, replay.ReplayFactory]:
    return {
        ProviderName.DEEPGRAM: replay.ReplayFactory(
            replay.ReplayTransport(replay.load("deepgram-speak-aura-2-es"))
        ),
        ProviderName.CARTESIA: replay.ReplayFactory(replay.ReplayTransport(principal)),
    }


@pytest.mark.parametrize(
    ("principal", "tipo"),
    [
        ("cartesia-tts-error-500-unavailable", ProviderErrorKind.UNAVAILABLE),
        ("cartesia-tts-error-429-rate-limited", ProviderErrorKind.RATE_LIMITED),
    ],
)
async def test_un_fallo_de_la_principal_que_no_es_de_cupo_tambien_pasa_a_la_de_respaldo(
    principal: str, tipo: ProviderErrorKind, eventos: Eventos
) -> None:
    """Antes solo el cupo cambiaba de voz y cualquier otro fallo terminaba la llamada."""
    plataforma, registro, _ = _plataforma(_fabricas(deepgram=RESPALDO, cartesia=principal))

    audio = await _hablar(plataforma, _una_aseguradora())

    assert audio
    assert ProviderName.DEEPGRAM in [r.provider for r in registro.reports]
    caida = [e for e in eventos.lineas if e["event"] == "voice.primary_failed"]
    assert len(caida) == 1
    assert caida[0]["error_kind"] == tipo.value
    assert (caida[0]["provider"], caida[0]["fallback"]) == ("cartesia", "deepgram")
    assert caida[0]["mid_phrase"] is False


@pytest.mark.parametrize(
    ("cierre", "tipo"),
    [(1011, ProviderErrorKind.UNAVAILABLE), (None, ProviderErrorKind.TIMEOUT)],
)
async def test_la_principal_que_se_corta_a_mitad_de_frase_sigue_con_la_de_respaldo(
    cierre: int | None, tipo: ProviderErrorKind, eventos: Eventos
) -> None:
    """La conexion se cae, o el proveedor deja de mandar, con un trozo ya enviado.

    Lo ya enviado suena; la frase se repite **entera** en la de respaldo, y el evento dice
    que el audio ya habia salido.
    """
    corte = _principal_que_se_corta(tras_trozos=1, cierre=cierre)
    plataforma, registro, _ = _plataforma(_fabricas_con(corte))

    audio = await _hablar(plataforma, _una_aseguradora())

    completo = b"".join(
        [
            t
            async for t in _plataforma(_fabricas(deepgram=RESPALDO))[0].speak(
                _una_aseguradora(),
                redactado(FRASE, "es"),
                mode=VoiceMode.FALLBACK,
                language="es",
            )
        ]
    )
    # Lo que ya habia sonado de la principal (un trozo de 20 ms) y despues la frase entera.
    assert audio.endswith(completo)
    assert len(audio) == len(completo) + 960
    assert [r.provider for r in registro.reports] == [ProviderName.CARTESIA, ProviderName.DEEPGRAM]
    caida = [e for e in eventos.lineas if e["event"] == "voice.primary_failed"]
    assert [(e["error_kind"], e["mid_phrase"]) for e in caida] == [(tipo.value, True)]


async def test_tras_un_fallo_de_la_principal_las_frases_siguientes_van_directo_a_la_de_respaldo() -> (
    None
):
    """Lo que queda de la llamada suena con una sola voz; pasado el plazo se vuelve a probar."""
    instante = [datetime(2026, 10, 13, 12, 0, tzinfo=UTC)]
    fabricas = _fabricas(deepgram=RESPALDO, cartesia="cartesia-tts-error-500-unavailable")
    plataforma, _, techo = _plataforma(fabricas)
    plataforma = replace(plataforma, now=lambda: instante[0])
    tenant = _una_aseguradora()

    await _hablar(plataforma, tenant)
    tras_el_fallo = techo.consultas
    await _hablar(plataforma, tenant)
    dentro_del_plazo = techo.consultas - tras_el_fallo
    instante[0] += speech.PRIMARY_FAILURE_RETRY_AFTER
    await _hablar(plataforma, tenant)
    pasado_el_plazo = techo.consultas - tras_el_fallo - dentro_del_plazo

    # El techo se consulta una vez por proveedor al que se le pide la frase.
    assert (tras_el_fallo, dentro_del_plazo, pasado_el_plazo) == (2, 1, 2)
    # Y un fallo corriente aparta la voz menos que el cupo agotado, que tarda una hora.
    assert speech.PRIMARY_FAILURE_RETRY_AFTER < speech.PRIMARY_RETRY_AFTER
    assert speech.PRIMARY_FAILURE_RETRY_AFTER > timedelta(seconds=240)


async def test_el_plazo_corto_no_acorta_el_de_sin_cupo() -> None:
    """Si la principal ya esta fuera por cupo, un fallo corriente no la devuelve antes."""
    instante = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
    plataforma, _, _ = _plataforma(_fabricas())
    fuera = plataforma.out_of_service
    fuera.marcar(ProviderName.CARTESIA, instante, por=speech.PRIMARY_RETRY_AFTER)
    fuera.marcar(ProviderName.CARTESIA, instante, por=speech.PRIMARY_FAILURE_RETRY_AFTER)

    assert fuera.sigue(ProviderName.CARTESIA, instante + speech.PRIMARY_RETRY_AFTER / 2)


async def test_si_tambien_falla_la_de_respaldo_el_fallo_sale() -> None:
    """Las dos voces caidas: la llamada termina como siempre, con el fallo de la ultima."""
    fabricas = _fabricas(
        deepgram="deepgram-speak-503-unavailable", cartesia="cartesia-tts-error-500-unavailable"
    )
    plataforma, registro, _ = _plataforma(fabricas)

    with pytest.raises(ProviderError) as fallo:
        await _hablar(plataforma, _una_aseguradora())

    assert fallo.value.provider is ProviderName.DEEPGRAM
    assert fallo.value.kind is ProviderErrorKind.UNAVAILABLE
    assert [r.provider for r in registro.reports] == [ProviderName.CARTESIA, ProviderName.DEEPGRAM]


async def test_el_evento_de_la_caida_no_lleva_el_texto_de_la_frase(eventos: Eventos) -> None:
    """Regla del proyecto: el texto de la persona no sale en ningun evento."""
    plataforma, _, _ = _plataforma(
        _fabricas(deepgram=RESPALDO, cartesia="cartesia-tts-error-500-unavailable")
    )

    await _hablar(plataforma, _una_aseguradora())

    assert "prueba" not in eventos.crudo
    assert FRASE not in eventos.crudo


async def test_escuchar_por_la_plataforma_usa_el_modelo_de_la_aseguradora() -> None:
    """La transcripcion de la aseguradora: su modelo, su idioma detectado, su gasto."""
    fabricas = _fabricas(deepgram="deepgram-listen-nova-3-es")
    plataforma, registro, _ = _plataforma(fabricas)

    resultados = [
        t
        async for t in plataforma.listen(_una_aseguradora(), audio_de(4800), language="es")
        if isinstance(t, Transcript)
    ]

    finales = [t for t in resultados if t.is_final]
    assert finales
    assert {t.language for t in finales} == {"es"}
    transporte = fabricas[ProviderName.DEEPGRAM].transport
    assert isinstance(transporte, replay.ReplayTransport)
    assert transporte.requests[0].query["model"] == "nova-3"
    # Y pide la senal de voz: sin ella la llamada vuelve a enterarse tarde de que la
    # persona retomo la frase.
    assert transporte.requests[0].query["vad_events"] == "true"
    assert [r.model for r in registro.reports] == ["nova-3"]


def _tenants_con_una_rota(raiz: Path) -> tuple[Path, str]:
    destino = raiz / "tenants"
    shutil.copytree(paths.tenants_dir(), destino)
    rota = sorted(p for p in destino.iterdir() if p.is_dir())[0]
    archivo = rota / tenant_config.TENANT_FILE
    crudo = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    crudo["voice"]["primary"]["en"]["voice_id"] = "voz-que-no-existe"
    archivo.write_text(yaml.safe_dump(crudo, allow_unicode=True), encoding="utf-8")
    return destino, rota.name


async def test_una_voz_apagada_no_se_construye_y_la_de_las_demas_sigue(
    tmp_path: Path, eventos: Eventos
) -> None:
    """BR2.2: pedir la voz apagada falla con su motivo y sin ninguna peticion."""
    destino, rota = _tenants_con_una_rota(tmp_path)
    fabricas = _fabricas(cartesia="cartesia-tts-sonic-3.6-es")
    plataforma = speech.build_speech_platform(
        _ajustes(),
        provider_config.load(),
        tenant_config.load(destino).available,
        transports=fabricas,
        gate=Abierto(),
        usage=Registro(),
    )

    estado = plataforma.availability_for(rota)
    assert not estado.available
    assert estado.reason is VoiceOffReason.UNKNOWN_VOICE
    with pytest.raises(VoiceUnavailableError, match="unknown_voice"):
        plataforma.speak(rota, redactado("Hola.", "es"), mode=VoiceMode.PRIMARY, language="es")
    with pytest.raises(VoiceUnavailableError, match="apagada"):
        plataforma.transcriber(rota)

    transporte = fabricas[ProviderName.CARTESIA].transport
    assert isinstance(transporte, replay.ReplayTransport)
    assert transporte.requests == []
    otras = sorted(t for t in plataforma.availability if t != rota)
    assert all(plataforma.availability_for(t).available for t in otras)
    #: El arranque dejo su evento, con la clave y nunca el valor que la rompio.
    assert [e["event"] for e in eventos.lineas] == ["providers.voice_unavailable"]
    assert "voz-que-no-existe" not in eventos.crudo


def test_una_aseguradora_que_no_esta_cargada_no_tiene_voz() -> None:
    plataforma, _, _ = _plataforma(_fabricas())
    with pytest.raises(VoiceUnavailableError, match="no esta cargada"):
        plataforma.availability_for("aseguradora-que-no-existe")


# --- El catalogo de voces, dentro de cada adaptador ----------------------------


def _catalogo(proveedor: ProviderName, rutas: dict[str, object]) -> replay.ReplayFactory:
    return replay.ReplayFactory(replay.ReplayTransport({"catalog": rutas}))


async def test_el_catalogo_de_cada_adaptador_dice_que_voces_faltan() -> None:
    """BR1.1: la ruta y la forma de la lista son de cada adaptador, no del comando."""
    fabricas = {
        ProviderName.DEEPGRAM: _catalogo(
            ProviderName.DEEPGRAM,
            {
                "v1/models": {
                    "status": 200,
                    "body": {"tts": [{"canonical_name": "aura-2-celeste-es"}]},
                }
            },
        ),
        ProviderName.CARTESIA: _catalogo(
            ProviderName.CARTESIA,
            {f"voices/{CATALINA}": {"status": 200}, "voices/no-publicada": {"status": 404}},
        ),
    }
    plataforma, _, _ = _plataforma(fabricas)
    voces = [
        VoiceRef(provider=ProviderName.CARTESIA, model="sonic-3.6", voice_id=v, language="es")
        for v in (CATALINA, "no-publicada", CATALINA)
    ] + [
        VoiceRef(provider=ProviderName.DEEPGRAM, model="aura-2", voice_id=v, language="es")
        for v in ("aura-2-celeste-es", "aura-2-thalia-en")
    ]

    faltan = await speech.unpublished_voices(plataforma.clients, voces)

    assert faltan == ["cartesia:no-publicada", "deepgram:aura-2-thalia-en"]


async def test_sin_lista_de_voces_ninguna_cuenta_como_publicada() -> None:
    """Un 401 en la lista no puede afirmar que una voz existe."""
    fabricas = {
        ProviderName.DEEPGRAM: _catalogo(ProviderName.DEEPGRAM, {"v1/models": {"status": 401}}),
        ProviderName.CARTESIA: _catalogo(ProviderName.CARTESIA, {}),
    }
    plataforma, _, _ = _plataforma(fabricas)
    voz = VoiceRef(
        provider=ProviderName.DEEPGRAM, model="aura-2", voice_id="aura-2-celeste-es", language="es"
    )
    assert await speech.unpublished_voices(plataforma.clients, [voz]) == [
        "deepgram:aura-2-celeste-es"
    ]


@pytest.mark.parametrize(
    ("agotado", "esperado"),
    [(True, ProviderErrorKind.TIMEOUT), (False, ProviderErrorKind.UNAVAILABLE)],
)
async def test_un_catalogo_sin_red_sale_en_la_taxonomia_sin_contenido(
    agotado: bool, esperado: ProviderErrorKind, eventos: Eventos
) -> None:
    fallo = TransportError("ConnectError", timed_out=agotado)
    fabricas = {
        ProviderName.DEEPGRAM: _catalogo(ProviderName.DEEPGRAM, {}),
        ProviderName.CARTESIA: _catalogo(ProviderName.CARTESIA, {f"voices/{CATALINA}": fallo}),
    }
    plataforma, _, _ = _plataforma(fabricas)
    voz = VoiceRef(
        provider=ProviderName.CARTESIA, model="sonic-3.6", voice_id=CATALINA, language="es"
    )

    with pytest.raises(ProviderError) as error:
        await speech.unpublished_voices(plataforma.clients, [voz])

    assert error.value.kind is esperado
    assert error.value.use is Use.VOICE
    assert [e["event"] for e in eventos.lineas] == ["providers.speech_call_failed"]
    assert CATALINA not in eventos.crudo


# --- Los topes de la voz, exigidos por el chequeo de esquema -------------------


def test_los_dos_proveedores_de_voz_declaran_su_tope_vigente() -> None:
    """PA-9.2 sobre la carpeta versionada: las dos filas, con su figura y su fecha."""
    precios = provider_config.load().prices
    topes = {(t.provider, t.use): t for t in precios.caps}
    assert topes[(ProviderName.DEEPGRAM, Use.VOICE)].cap_kind.value == "prepaid_balance"
    assert topes[(ProviderName.CARTESIA, Use.VOICE)].cap_kind.value == "monthly_cap"
    assert schema_check.revisar_proveedores(paths.providers_dir(), today=date(2026, 9, 21)) == []


def test_un_proveedor_de_voz_sin_su_tope_falla_el_chequeo_de_esquema(tmp_path: Path) -> None:
    """Quitar la fila de Deepgram hace fallar `schema:check` nombrandolo."""
    carpeta = tmp_path / "providers"
    shutil.copytree(paths.providers_dir(), carpeta)
    archivo = carpeta / provider_config.PRICES_FILE
    crudo = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    crudo["caps"] = [
        tope
        for tope in crudo["caps"]
        if not (tope["provider"] == "deepgram" and tope["use"] == "voice")
    ]
    archivo.write_text(yaml.safe_dump(crudo, allow_unicode=True), encoding="utf-8")

    problemas = schema_check.revisar_proveedores(carpeta, today=date(2026, 9, 21))

    assert len(problemas) == 1
    assert "'deepgram'" in problemas[0]
    assert "PA-9.2" in problemas[0]


def test_el_tope_de_la_voz_caduca_como_cualquier_otro() -> None:
    """A los 31 dias de comprobado deja de contar como control y el chequeo lo nombra.

    **El dia se deriva de la fila, no se escribe.** Con una fecha fija aqui, cada vez
    que Miguel vuelve a leer una consola y refresca `last_checked_at` esta prueba cae
    por una razon que no es la suya --paso el 2026-10-02-- y la tentacion es correr el
    literal, que es escribir la prueba a la medida del archivo. Lo que la regla dice es
    "treinta dias despues de comprobado", y eso es lo que se mide.
    """
    carpeta = paths.providers_dir()
    topes = provider_config.load_prices(carpeta / "prices.yaml").caps
    de_voz = [t for t in topes if t.use is Use.VOICE and t.cap_kind is not CapKind.NONE_AVAILABLE]
    assert de_voz, "ninguna fila de tope de voz que comprobar"
    vencidas = max(t.last_checked_at for t in de_voz) + timedelta(
        days=schema_check.CAP_MAX_AGE_DAYS + 1
    )

    problemas = schema_check.revisar_proveedores(carpeta, today=vencidas)

    assert any("'deepgram' para el uso 'voice'" in p for p in problemas)
    assert any("'cartesia' para el uso 'voice'" in p for p in problemas)
    # Y **el dia antes no**, que es lo que distingue "caduca a los treinta" de
    # "caduca algun dia": sin esta linea, un chequeo que se quejara siempre pasaria.
    assert schema_check.revisar_proveedores(carpeta, today=vencidas - timedelta(days=2)) == []
