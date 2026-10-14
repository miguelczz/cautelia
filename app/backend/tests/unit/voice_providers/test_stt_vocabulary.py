"""Lo que se le pide al reconocedor ademas del audio: la variante del idioma y los terminos clave.

Origen (2026-10-13, llamada real en espanol de Colombia): «Itagui» llego como «Nitahui»,
«Luv D-Max» como «Lub Dimas» y «POL-200117» como «Paul 201 17». Deepgram `nova-3` admite
en espanol la variante de Latinoamerica (`es-419`) y el parametro `keyterm`, repetido una
vez por termino. Las dos cosas son **dato de configuracion** de la aseguradora
(`voice.stt.language_codes` y `voice.stt.keyterms`), no codigo: el aplicativo sigue
trabajando con `es` y `en`, y el SDK o el protocolo del proveedor se toca solo dentro de su
adaptador.

Sin red y sin gasto: el reproductor contesta con una respuesta grabada y estas pruebas
miran **la consulta** que el adaptador armo.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
import yaml
from pydantic import ValidationError

from untangle import paths
from untangle.base import Locale, ProviderName, Use
from untangle.providers.adapters import wire
from untangle.providers.adapters.deepgram import ENDPOINT as DEEPGRAM
from untangle.providers.adapters.deepgram import DeepgramSpeechToText, protocol
from untangle.providers.speech_wire import SpeechRequest
from untangle.providers.voice_availability import SpeechModel, transcription_model
from untangle.tenancy import config as tenant_config
from untangle.tenancy.models import (
    KEYTERMS_MAX_CHARACTERS,
    KEYTERMS_MAX_COUNT,
    SpeechModelChoice,
    TenantConfig,
    TranscriptionMode,
)

from . import replay
from .apoyo import TIEMPOS, Abierto, Registro, audio_de, clientes

LOCALES: tuple[Locale, ...] = ("es", "en")

MONOLINGUE = SpeechModel(
    provider=ProviderName.DEEPGRAM,
    model="nova-3",
    mode=TranscriptionMode.MONOLINGUAL,
    language_codes={"es": "es-419", "en": "en"},
    keyterms={"es": ("póliza", "Itagüí", "Luv D-Max"), "en": ("policy", "Itagüí")},
)


# --- La consulta que arma el adaptador ----------------------------------------


def test_en_un_solo_idioma_se_manda_la_variante_configurada_y_cada_termino_clave() -> None:
    consulta = protocol.listen_query(MONOLINGUE, "es")

    assert consulta["language"] == "es-419"
    assert consulta["keyterm"] == ("póliza", "Itagüí", "Luv D-Max")
    # Lo que ya se pedia no cambia: ni el modelo, ni la puntuacion, ni los eventos de voz.
    assert consulta["model"] == "nova-3"
    assert consulta["smart_format"] == "true"
    assert consulta["interim_results"] == "true"
    assert consulta["vad_events"] == "true"


def test_cada_idioma_de_la_llamada_manda_su_codigo_y_sus_terminos() -> None:
    consulta = protocol.listen_query(MONOLINGUE, "en")

    assert consulta["language"] == "en"
    assert consulta["keyterm"] == ("policy", "Itagüí")


def test_sin_configuracion_se_manda_el_idioma_tal_cual_y_ningun_termino() -> None:
    """Una aseguradora que no declara nada se comporta como antes del 2026-10-13."""
    sin_nada = SpeechModel(ProviderName.DEEPGRAM, "nova-3", TranscriptionMode.MONOLINGUAL)

    consulta = protocol.listen_query(sin_nada, "es")

    assert consulta["language"] == "es"
    assert "keyterm" not in consulta


def test_un_idioma_sin_codigo_ni_terminos_cae_al_idioma_de_la_llamada() -> None:
    parcial = SpeechModel(
        ProviderName.DEEPGRAM,
        "nova-3",
        TranscriptionMode.MONOLINGUAL,
        language_codes={"es": "es-419"},
        keyterms={"es": ("póliza",)},
    )

    consulta = protocol.listen_query(parcial, "en")

    assert consulta["language"] == "en"
    assert "keyterm" not in consulta


def test_en_modo_multiidioma_el_idioma_lo_detecta_el_modelo_pero_los_terminos_se_mandan() -> None:
    multi = SpeechModel(
        ProviderName.DEEPGRAM,
        "nova-3",
        TranscriptionMode.MULTI,
        language_codes={"es": "es-419"},
        keyterms={"es": ("Itagüí",)},
    )

    consulta = protocol.listen_query(multi, "es")

    assert consulta["language"] == "multi"
    assert consulta["keyterm"] == ("Itagüí",)


async def test_el_adaptador_pide_el_canal_con_los_terminos_de_su_modelo() -> None:
    caller, transporte, _ = clientes(
        ProviderName.DEEPGRAM, replay.load("deepgram-listen-nova-3-es")
    )
    stt = DeepgramSpeechToText(
        caller, model=MONOLINGUE, gate=Abierto(), usage=Registro(), timeouts=TIEMPOS
    )

    _ = [e async for e in stt.stream(audio_de(960), language="es")]

    consulta = transporte.requests[0].query
    assert consulta["language"] == "es-419"
    assert consulta["keyterm"] == ("póliza", "Itagüí", "Luv D-Max")


# --- La direccion del socket: un parametro repetido y bien codificado ----------


async def _url_del_canal(consulta: dict[str, Any]) -> str:
    """La direccion con la que el transporte abre el WebSocket, sin tocar la red."""
    vistas: list[str] = []

    class _Conexion:
        async def close(self) -> None:
            return None

    async def conectar(url: str, **_: Any) -> Any:
        vistas.append(url)
        return _Conexion()

    fabrica = wire.WireTransportFactory(DEEPGRAM, connector=conectar)
    transporte = fabrica.create(api_key="clave-de-prueba-que-no-sale", use=Use.VOICE)
    peticion = SpeechRequest(
        path="v1/listen", query=consulta, connect_timeout_ms=1000, read_timeout_ms=1000
    )
    async with transporte.open_duplex(peticion):
        pass
    return vistas[0]


async def test_cada_termino_va_en_su_propio_parametro_keyterm_y_codificado() -> None:
    url = await _url_del_canal(protocol.listen_query(MONOLINGUE, "es"))

    partes = urlsplit(url)
    assert partes.path == "/v1/listen"
    # Una frase de varias palabras va en un solo `keyterm`; el espacio, como %20 y no como
    # `+`, que no todo servidor lee igual; y las tildes, en UTF-8.
    assert "keyterm=Luv%20D-Max" in partes.query
    assert "keyterm=Itag%C3%BC%C3%AD" in partes.query
    assert partes.query.count("keyterm=") == 3
    assert parse_qs(partes.query)["keyterm"] == ["póliza", "Itagüí", "Luv D-Max"]
    assert parse_qs(partes.query)["language"] == ["es-419"]
    assert "clave-de-prueba" not in url


async def test_un_valor_suelto_se_sigue_codificando_como_antes() -> None:
    url = await _url_del_canal({"model": "nova-3", "language": "es"})

    assert urlsplit(url).query == "model=nova-3&language=es"


# --- La forma de la configuracion ---------------------------------------------


def _eleccion(**cambios: object) -> SpeechModelChoice:
    base: dict[str, object] = {"provider": "deepgram", "model": "nova-3", "mode": "monolingual"}
    return SpeechModelChoice.model_validate({**base, **cambios})


def test_la_eleccion_sin_vocabulario_sigue_cargando() -> None:
    eleccion = _eleccion()

    assert eleccion.language_codes == {}
    assert eleccion.keyterms == {}


def test_una_eleccion_valida_lleva_su_codigo_y_sus_terminos() -> None:
    eleccion = _eleccion(
        language_codes={"es": "es-419", "en": "en-US"},
        keyterms={"es": ["póliza", "POL", "Avenida 80", "Mazda CX-30"]},
    )

    assert eleccion.language_codes == {"es": "es-419", "en": "en-US"}
    assert eleccion.keyterms["es"] == ("póliza", "POL", "Avenida 80", "Mazda CX-30")


@pytest.mark.parametrize(
    ("cambio", "razon"),
    [
        pytest.param({"es": "en-US"}, "otro idioma", id="codigo-de-otro-idioma"),
        pytest.param({"es": "multi"}, "multi", id="multi-no-es-un-codigo"),
        pytest.param({"es": "es_419"}, "forma", id="guion-bajo"),
        pytest.param({"es": ""}, "forma", id="vacio"),
        pytest.param({"es": "es-419 "}, "forma", id="con-espacio"),
    ],
)
def test_un_codigo_de_idioma_que_no_es_del_idioma_de_la_llamada_no_carga(
    cambio: dict[str, str], razon: str
) -> None:
    with pytest.raises(ValidationError) as caido:
        _eleccion(language_codes=cambio)
    assert "language_codes" in str(caido.value), razon


def _mensaje(terminos: list[str]) -> str:
    with pytest.raises(ValidationError) as caido:
        _eleccion(keyterms={"es": terminos})
    return str(caido.value)


@pytest.mark.parametrize(
    "malo",
    [
        pytest.param("una,coma", id="coma"),
        pytest.param("punto;y coma", id="punto-y-coma"),
        pytest.param("termino:2", id="peso"),
        pytest.param("", id="vacio"),
        pytest.param("   ", id="solo-espacios"),
        pytest.param(" con espacio delante", id="espacio-delante"),
        pytest.param("con espacio detras ", id="espacio-detras"),
        pytest.param("con\nsalto", id="salto-de-linea"),
        pytest.param("x" * 41, id="demasiado-largo"),
    ],
)
def test_un_termino_con_lo_que_el_proveedor_no_admite_no_carga(malo: str) -> None:
    """Deepgram acepta una coma, un punto y coma o un peso sin error y **no hace nada**: el
    termino se pierde en silencio. Por eso la configuracion los rechaza al cargar."""
    assert "keyterms" in _mensaje(["póliza", malo])


def test_un_termino_repetido_no_carga_aunque_cambie_la_mayuscula() -> None:
    assert "repet" in _mensaje(["Itagüí", "itagüí"])


def test_pasarse_de_terminos_no_carga() -> None:
    demasiados = [f"Termino {n}" for n in range(KEYTERMS_MAX_COUNT + 1)]

    assert str(KEYTERMS_MAX_COUNT) in _mensaje(demasiados)


def test_pasarse_de_caracteres_no_carga_aunque_los_terminos_sean_pocos() -> None:
    por_termino = 40
    largos = [
        "x" * (por_termino - 1) + chr(ord("a") + n)
        for n in range(KEYTERMS_MAX_CHARACTERS // por_termino + 1)
    ]
    assert len(largos) < KEYTERMS_MAX_COUNT
    assert sum(len(t) for t in largos) > KEYTERMS_MAX_CHARACTERS

    assert str(KEYTERMS_MAX_CHARACTERS) in _mensaje(largos)


def test_justo_en_el_tope_si_carga() -> None:
    en_el_tope = [f"T{n:02d}" + "x" * 11 for n in range(KEYTERMS_MAX_COUNT)]
    assert sum(len(t) for t in en_el_tope) <= KEYTERMS_MAX_CHARACTERS

    assert len(_eleccion(keyterms={"es": en_el_tope}).keyterms["es"]) == KEYTERMS_MAX_COUNT


def test_el_tope_se_cuenta_por_idioma() -> None:
    mitad = [f"Termino {n}" for n in range(KEYTERMS_MAX_COUNT)]
    eleccion = _eleccion(keyterms={"es": mitad, "en": mitad})

    assert len(eleccion.keyterms["es"]) == len(eleccion.keyterms["en"]) == KEYTERMS_MAX_COUNT


def test_el_tope_es_conservador_frente_al_limite_del_proveedor() -> None:
    """500 tokens en total. 50 terminos es el techo de lo que el proveedor recomienda, y 700
    caracteres, incluso a dos caracteres por token (mucho peor que lo habitual en espanol, de
    tres o cuatro), son 350 tokens mas un separador por termino: queda por debajo de 500."""
    peor_caso_en_tokens = KEYTERMS_MAX_CHARACTERS / 2 + KEYTERMS_MAX_COUNT
    assert KEYTERMS_MAX_COUNT <= 50
    assert peor_caso_en_tokens < 500


# --- Lo que publica el repositorio --------------------------------------------


def _aseguradoras() -> tuple[TenantConfig, ...]:
    cargadas = tenant_config.load()
    assert not cargadas.unavailable
    assert len(cargadas.available) == 3
    return cargadas.available


def test_las_tres_aseguradoras_piden_espanol_de_latinoamerica_y_ingles() -> None:
    for tenant in _aseguradoras():
        assert tenant.voice.stt is not None
        assert tenant.voice.stt.language_codes == {"es": "es-419", "en": "en"}, tenant.tenant_id


@pytest.mark.parametrize("idioma", LOCALES)
def test_cada_aseguradora_declara_entre_treinta_y_cincuenta_terminos_por_idioma(
    idioma: Locale,
) -> None:
    for tenant in _aseguradoras():
        assert tenant.voice.stt is not None
        terminos = tenant.voice.stt.keyterms[idioma]
        assert 30 <= len(terminos) <= KEYTERMS_MAX_COUNT, (tenant.tenant_id, len(terminos))
        assert sum(len(t) for t in terminos) <= KEYTERMS_MAX_CHARACTERS, tenant.tenant_id


@pytest.mark.parametrize("idioma", LOCALES)
def test_los_terminos_cubren_la_poliza_los_lugares_las_vias_y_los_carros(idioma: Locale) -> None:
    obligatorios = {
        "POL",
        "Itagüí",
        "Medellín",
        "Envigado",
        "Sabaneta",
        "El Poblado",
        "Autopista Sur",
        "Avenida Las Vegas",
        "Avenida El Poblado",
        "Luv D-Max",
        "Renault Logan",
        "Chevrolet Spark",
        "Mazda 3",
        "Kia Picanto",
        "Toyota Hilux",
    }
    obligatorios.add("póliza" if idioma == "es" else "policy")
    for tenant in _aseguradoras():
        assert tenant.voice.stt is not None
        faltan = obligatorios - set(tenant.voice.stt.keyterms[idioma])
        assert not faltan, (tenant.tenant_id, sorted(faltan))


@pytest.mark.parametrize("idioma", LOCALES)
def test_cada_aseguradora_incluye_su_propio_nombre_y_el_de_su_agente(idioma: Locale) -> None:
    for tenant in _aseguradoras():
        assert tenant.voice.stt is not None
        assert tenant.agent_name is not None
        terminos = tenant.voice.stt.keyterms[idioma]
        assert tenant.display_name in terminos, tenant.tenant_id
        assert tenant.agent_name in terminos, tenant.tenant_id


def _palabras_de_titulares() -> set[str]:
    """Las palabras de los nombres de los titulares de las polizas de ejemplo."""
    palabras: set[str] = set()
    for archivo in sorted(paths.data_dir().glob("tenants/*/issued_policies/*.json")):
        titular = json.loads(archivo.read_text(encoding="utf-8"))["named_insured"]["full_name"]
        palabras.update(p.casefold() for p in str(titular).split())
    assert palabras, "no se encontraron las polizas de ejemplo"
    return palabras


@pytest.mark.parametrize("idioma", LOCALES)
def test_ningun_nombre_de_titular_de_las_polizas_de_ejemplo_esta_en_la_lista(
    idioma: Locale,
) -> None:
    """Son datos personales (sinteticos) que la lista no debe incentivar, y un reconocedor
    que los espera los oye aunque nadie los diga."""
    titulares = _palabras_de_titulares()
    for tenant in _aseguradoras():
        assert tenant.voice.stt is not None
        agente = (tenant.agent_name or "").casefold()
        for termino in tenant.voice.stt.keyterms[idioma]:
            for palabra in termino.casefold().split():
                if palabra == agente:
                    continue
                assert palabra not in titulares, (tenant.tenant_id, termino)


def test_el_modelo_de_transcripcion_lleva_lo_que_declara_la_aseguradora() -> None:
    for tenant in _aseguradoras():
        modelo = transcription_model(tenant.voice)
        assert tenant.voice.stt is not None
        assert modelo.language_codes == tenant.voice.stt.language_codes
        assert modelo.keyterms == tenant.voice.stt.keyterms
        assert protocol.listen_query(modelo, "es")["language"] == "es-419"


def test_el_esquema_publicado_conoce_los_campos_nuevos() -> None:
    esquema = json.loads((paths.schemas_dir() / "tenant.schema.json").read_text(encoding="utf-8"))
    eleccion = esquema["$defs"]["SpeechModelChoice"]["properties"]
    assert {"language_codes", "keyterms"} <= set(eleccion)


def test_una_carpeta_con_demasiados_terminos_se_apaga_nombrando_la_clave(
    tmp_path: Path,
) -> None:
    """El mismo cargador de siempre: la carpeta rota se apaga sola y dice que clave fue."""
    origen = paths.tenants_dir() / "stonecroft"
    destino = tmp_path / "stonecroft"
    shutil.copytree(origen, destino)
    archivo = destino / tenant_config.TENANT_FILE
    crudo = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    crudo["voice"]["stt"]["keyterms"]["es"] = [f"Termino {n}" for n in range(60)]
    archivo.write_text(yaml.safe_dump(crudo, allow_unicode=True), encoding="utf-8")

    cargadas = tenant_config.load(tmp_path)

    assert not cargadas.available
    (caida,) = cargadas.unavailable
    assert "voice.stt.keyterms" in caida.detail
