"""La configuracion de voz por aseguradora y su disponibilidad (BR2.1 a BR2.3).

Lo que se defiende aqui tiene dos fallos posibles, y los dos son malos por
razones opuestas:

- **Una voz rota que se activa.** La llamada abriria el microfono y fallaria a
  mitad de la primera frase, con el visitante ya hablando.
- **Una voz rota que apaga mas de la cuenta.** Un error de configuracion en el
  bloque de voz no puede tumbar el chat de esa aseguradora ni la voz de las
  otras dos (AC5.10.4).

Las pruebas parten de los archivos **del repositorio** --los tres `tenant.yaml`
y `providers.yaml`-- y los rompen de una forma cada vez, en una carpeta propia:
asi lo que se comprueba es la configuracion que se publica, no una de juguete.
"""

from __future__ import annotations

import io
import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

from untangle import observability, paths
from untangle.base import ProviderName
from untangle.copy_catalog import api as catalogo
from untangle.providers import config as provider_config
from untangle.providers.voice_availability import (
    REASON_KEYS,
    SpeechAdapterInfo,
    VoiceAvailability,
    VoiceOffReason,
    VoiceUnavailableError,
    availability_by_tenant,
    transcription_model,
    voice_availability,
    voice_ref,
)
from untangle.telemetry.spend.models import VoiceMode
from untangle.tenancy import config as tenant_config
from untangle.tenancy.models import TenantConfig, TranscriptionMode, VoiceConfig

#: Los dos adaptadores con sus respuestas grabadas. Es el registro que la raiz
#: de composicion arma con lo que declara cada paquete; aqui se escribe a mano
#: para que cada prueba pueda quitarle una pieza.
REGISTRO: dict[ProviderName, SpeechAdapterInfo] = {
    ProviderName.DEEPGRAM: SpeechAdapterInfo(
        provider=ProviderName.DEEPGRAM, contract_models=frozenset({"nova-3", "aura-2"})
    ),
    ProviderName.CARTESIA: SpeechAdapterInfo(
        provider=ProviderName.CARTESIA, contract_models=frozenset({"sonic-3.6"})
    ),
}


def _proveedores() -> provider_config.ProvidersConfig:
    return provider_config.load().providers


def _voz_del_repositorio() -> dict[str, object]:
    """El bloque `voice` de una aseguradora del repositorio, como datos crudos."""
    carpeta = sorted(p for p in paths.tenants_dir().iterdir() if p.is_dir())[0]
    crudo = yaml.safe_load((carpeta / tenant_config.TENANT_FILE).read_text(encoding="utf-8"))
    bloque = crudo["voice"]
    assert isinstance(bloque, dict)
    return bloque


def _con(cambio: dict[str, object]) -> VoiceConfig:
    """El bloque del repositorio con un cambio aplicado en profundidad."""
    datos = json.loads(json.dumps(_voz_del_repositorio()))
    for ruta, valor in cambio.items():
        partes = ruta.split(".")
        destino = datos
        for parte in partes[:-1]:
            destino = destino[parte]
        if valor is None:
            destino.pop(partes[-1], None)
        else:
            destino[partes[-1]] = valor
    return VoiceConfig.model_validate(datos)


def test_las_tres_aseguradoras_del_repositorio_tienen_voz_en_los_dos_idiomas() -> None:
    """NFR20.3: ninguna sin voz principal o de respaldo en alguno de los dos idiomas."""
    aseguradoras = tenant_config.load()
    assert len(aseguradoras.available) == 3
    assert not aseguradoras.unavailable

    estados = availability_by_tenant(
        aseguradoras.available, providers=_proveedores(), adapters=REGISTRO
    )
    assert estados == {t.tenant_id: VoiceAvailability.on() for t in aseguradoras.available}

    for tenant in aseguradoras.available:
        principal = voice_ref(tenant.voice, mode=VoiceMode.PRIMARY, language="en")
        assert principal.provider is ProviderName.CARTESIA
        assert principal.model == "sonic-3.6"
        modelo = transcription_model(tenant.voice)
        assert (modelo.provider, modelo.model, modelo.mode) == (
            ProviderName.DEEPGRAM,
            "nova-3",
            # Un idioma por llamada desde el 2026-10-09.
            TranscriptionMode.MONOLINGUAL,
        )


def test_cambiar_la_configuracion_cambia_la_voz_que_se_usa() -> None:
    """AC5.10.1: proveedor, modelo y voz se cambian editando configuracion y nada mas."""
    antes = _con({})
    despues = _con(
        {
            "primary.es.provider": "deepgram",
            "primary.es.model": "aura-2",
            "primary.es.voice_id": "aura-2-celeste-es",
        }
    )
    assert voice_availability(despues, providers=_proveedores(), adapters=REGISTRO).available

    ref_antes = voice_ref(antes, mode=VoiceMode.PRIMARY, language="es")
    ref_despues = voice_ref(despues, mode=VoiceMode.PRIMARY, language="es")
    assert (ref_antes.provider, ref_antes.model) == (ProviderName.CARTESIA, "sonic-3.6")
    assert (ref_despues.provider, ref_despues.model, ref_despues.voice_id) == (
        ProviderName.DEEPGRAM,
        "aura-2",
        "aura-2-celeste-es",
    )
    # El respaldo en ingles no cambio: solo se toco una clave.
    assert voice_ref(despues, mode=VoiceMode.FALLBACK, language="en").voice_id == (
        "aura-2-thalia-en"
    )


@pytest.mark.parametrize(
    ("cambio", "motivo", "campo"),
    [
        pytest.param({"stt": None}, VoiceOffReason.NOT_CONFIGURED, "stt", id="sin-transcripcion"),
        pytest.param(
            {"fallback": None}, VoiceOffReason.NOT_CONFIGURED, "fallback", id="sin-respaldo"
        ),
        pytest.param(
            {"fallback.en": None},
            VoiceOffReason.MISSING_LANGUAGE,
            "fallback.en",
            id="respaldo-sin-ingles",
        ),
        pytest.param(
            {"primary.es.provider": "elevenlabs"},
            VoiceOffReason.UNKNOWN_PROVIDER,
            "primary.es.provider",
            id="proveedor-desconocido",
        ),
        pytest.param(
            {"stt.provider": "gemini"},
            VoiceOffReason.UNKNOWN_PROVIDER,
            "stt.provider",
            id="proveedor-sin-adaptador-de-voz",
        ),
        pytest.param(
            {"stt.model": "nova-2"},
            VoiceOffReason.UNKNOWN_MODEL,
            "stt.model",
            id="modelo-no-anclado",
        ),
        pytest.param(
            {"stt.model": "aura-2"},
            VoiceOffReason.UNKNOWN_MODEL,
            "stt.model",
            id="modelo-de-sintesis-como-transcripcion",
        ),
        pytest.param(
            {"fallback.es.voice_id": "aura-2-inventada-es"},
            VoiceOffReason.UNKNOWN_VOICE,
            "fallback.es.voice_id",
            id="voz-inexistente",
        ),
        pytest.param(
            {"fallback.en.voice_id": "aura-2-celeste-es"},
            VoiceOffReason.VOICE_MISMATCH,
            "fallback.en.voice_id",
            id="voz-en-otro-idioma",
        ),
        pytest.param(
            {"primary.en.voice_id": ""},
            VoiceOffReason.UNKNOWN_VOICE,
            "primary.en.voice_id",
            id="voz-vacia",
        ),
    ],
)
def test_cada_forma_de_romperla_apaga_la_voz_con_su_motivo(
    cambio: dict[str, object], motivo: VoiceOffReason, campo: str
) -> None:
    """BR2.2: el motivo nombra la clave rota, y la frase sale del catalogo."""
    estado = voice_availability(_con(cambio), providers=_proveedores(), adapters=REGISTRO)
    assert estado == VoiceAvailability.off(motivo, field=campo)
    assert estado.reason_key == REASON_KEYS[motivo]


def test_un_proveedor_sin_respuesta_grabada_no_se_activa() -> None:
    """BR2.3: un modelo anclado sin prueba de contrato no se puede activar."""
    sin_grabar = {
        **REGISTRO,
        ProviderName.CARTESIA: SpeechAdapterInfo(
            provider=ProviderName.CARTESIA, contract_models=frozenset()
        ),
    }
    estado = voice_availability(_con({}), providers=_proveedores(), adapters=sin_grabar)
    assert estado == VoiceAvailability.off(VoiceOffReason.NO_CONTRACT, field="primary.es.model")


def test_con_la_voz_rota_el_chat_de_esa_aseguradora_sigue_vivo(tmp_path: Path) -> None:
    """AC5.10.4: la carpeta carga --el chat la sirve-- y solo su voz se apaga.

    Se copia el directorio de aseguradoras entero y se rompe **una**: las otras
    dos siguen con voz, y ninguna de las tres cae del cargador.
    """
    raiz = tmp_path / "tenants"
    shutil.copytree(paths.tenants_dir(), raiz)
    rota = sorted(p for p in raiz.iterdir() if p.is_dir())[0]
    archivo = rota / tenant_config.TENANT_FILE
    crudo = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    crudo["voice"]["primary"]["es"]["provider"] = "elevenlabs"
    archivo.write_text(yaml.safe_dump(crudo, allow_unicode=True), encoding="utf-8")

    cargadas = tenant_config.load(raiz)
    assert not cargadas.unavailable
    assert rota.name in cargadas.ids

    salida = io.StringIO()
    observability.set_stream(salida)
    try:
        estados = availability_by_tenant(
            cargadas.available, providers=_proveedores(), adapters=REGISTRO
        )
    finally:
        observability.set_stream(sys.stdout)

    apagadas = {tenant for tenant, estado in estados.items() if not estado.available}
    assert apagadas == {rota.name}
    evento = json.loads(salida.getvalue().strip())
    assert evento == {
        "event": "providers.voice_unavailable",
        "tenant_id": rota.name,
        "reason": "unknown_provider",
        "field": "primary.es.provider",
    }
    # El evento nombra la clave, nunca el valor que la rompio.
    assert "elevenlabs" not in salida.getvalue()


def test_cada_motivo_tiene_su_frase_en_los_dos_idiomas() -> None:
    """La consola nunca muestra un motivo sin frase, ni en espanol ni en ingles."""
    textos = catalogo.load()
    assert set(REASON_KEYS) == set(VoiceOffReason)
    for clave in set(REASON_KEYS.values()):
        for idioma in ("es", "en"):
            assert textos.t(clave, locale=idioma).strip()
    assert REASON_KEYS[VoiceOffReason.NOT_CONFIGURED] != REASON_KEYS[VoiceOffReason.UNKNOWN_VOICE]


def test_pedir_una_voz_no_configurada_falla_nombrando_la_causa() -> None:
    """Quien pide la voz sin mirar la disponibilidad recibe un error, no una voz vacia."""
    sin_bloques = _con({"primary": None})
    with pytest.raises(VoiceUnavailableError, match="no esta configurada"):
        voice_ref(sin_bloques, mode=VoiceMode.PRIMARY, language="es")
    with pytest.raises(VoiceUnavailableError, match="proveedor de transcripcion"):
        transcription_model(_con({"stt.provider": "elevenlabs"}))
    with pytest.raises(VoiceUnavailableError, match="proveedor desconocido"):
        voice_ref(
            _con({"fallback.es.provider": "elevenlabs"}), mode=VoiceMode.FALLBACK, language="es"
        )
    with pytest.raises(ValueError, match="motivo"):
        VoiceAvailability(available=False)


def test_una_voz_declarada_con_alias_movil_o_modelo_ajeno_no_carga(tmp_path: Path) -> None:
    """El catalogo de voces se ancla igual que los modelos (BR1.4)."""
    crudo = yaml.safe_load(paths.providers_dir().joinpath("providers.yaml").read_text("utf-8"))
    deepgram = next(p for p in crudo["providers"] if p["name"] == "deepgram")

    deepgram["voices"].append({"id": "aura-2-latest-en", "model": "aura-2", "languages": ["en"]})
    (tmp_path / "providers.yaml").write_text(yaml.safe_dump(crudo), encoding="utf-8")
    with pytest.raises(provider_config.ProviderConfigError, match="alias movil"):
        provider_config.load_providers(tmp_path / "providers.yaml")

    deepgram["voices"][-1] = {"id": "aura-2-luna-en", "model": "nova-3", "languages": ["en"]}
    (tmp_path / "providers.yaml").write_text(yaml.safe_dump(crudo), encoding="utf-8")
    with pytest.raises(provider_config.ProviderConfigError, match="modelo de sintesis"):
        provider_config.load_providers(tmp_path / "providers.yaml")


def test_la_aseguradora_se_valida_igual_sin_los_campos_nuevos() -> None:
    """C-25: los campos de U15 llegan opcionales; sin ellos la carpeta sigue valida."""
    tenant = TenantConfig.model_validate(
        {
            "tenant_id": "prueba",
            "display_name": "Prueba",
            "kind": "carrier",
            "default_language": "es",
            "jurisdiction": "corvane",
            "example_policy": "POL-01",
            "case_number_prefix": "PR",
            "voice": {"primary_voice": "catalina", "language_default": "es"},
        }
    )
    estado = voice_availability(tenant.voice, providers=_proveedores(), adapters=REGISTRO)
    assert estado == VoiceAvailability.off(VoiceOffReason.NOT_CONFIGURED, field="stt")
