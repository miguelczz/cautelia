"""La voz de cada aseguradora: si puede atender y, si no, por que (U15, BR2.1 a BR2.3).

Se decide **al arrancar** y sin preguntarle a ningun proveedor. Lo que se compara
son tres cosas versionadas en el repositorio:

1. el bloque `voice` de cada `tenant.yaml` --que proveedor, modelo y voz usa la
   aseguradora, por idioma, principal y de respaldo (BR2.1)--;
2. `app/config/providers/providers.yaml` --que modelos ancla el proyecto y que
   voces comprobo que existen--;
3. lo que la raiz de composicion sabe de cada adaptador registrado: **para que
   modelos existe una respuesta grabada** con su prueba de contrato (BR2.3).

## Lo que apaga la voz, y lo que no

Una configuracion rota apaga **la voz de esa aseguradora**, con un motivo del
catalogo que la consola de U16 muestra, y **nada mas**: el proceso arranca, el
chat de esa aseguradora sigue vivo y la voz de las otras dos tambien (BR2.2,
AC5.10.4). Por eso esta funcion **devuelve un valor y no levanta**: una
excepcion aqui convertiria un descuido de configuracion en una caida.

Para quien visita hay dos frases y no una por motivo: "todavia no hay voz" y "la
voz se rompio". El motivo exacto --cual valor fallo y en que clave-- es para
quien opera la demostracion y sale en el evento tecnico, con su valor cerrado.

## Lo que este modulo no hace

- **No abre ninguna conexion** ni importa ningun adaptador: el contrato
  `raiz-de-composicion` dice que solo `untangle.server` los importa. Lo que
  sabe de cada uno lo recibe como dato (`SpeechAdapterInfo`).
- **No decide entre la voz principal y la de respaldo.** Eso es de U17, antes de
  cada llamada (C-17, `reserve_primary_voice`). Aqui solo se exige que las dos
  existan en los dos idiomas (NFR20.3).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Self

from pydantic import model_validator

from untangle import observability
from untangle.base import Frozen, Locale, ProviderName
from untangle.copy_catalog.api import CopyKey
from untangle.providers.config import ModelKind, ProvidersConfig
from untangle.providers.ports import VoiceRef
from untangle.telemetry.spend.models import VoiceMode
from untangle.tenancy.models import (
    SpeechModelChoice,
    TenantConfig,
    TenantId,
    TranscriptionMode,
    VoiceChoice,
    VoiceConfig,
    VoicesByLanguage,
)

__all__ = [
    "LANGUAGES",
    "REASON_KEYS",
    "SpeechAdapterInfo",
    "SpeechModel",
    "VoiceAvailability",
    "VoiceOffReason",
    "VoiceUnavailableError",
    "availability_by_tenant",
    "transcription_model",
    "voice_availability",
    "voice_ref",
]

#: Los dos idiomas en los que **toda** aseguradora tiene voz principal y de
#: respaldo (NFR20.3). Paridad, no preferencia: una capacidad que solo funciona
#: en un idioma se esconde detras de un promedio (P12).
LANGUAGES: tuple[Locale, ...] = ("es", "en")


class VoiceOffReason(StrEnum):
    """Por que la voz de una aseguradora esta apagada. Conjunto cerrado.

    Es un valor tecnico y nunca se imprime hacia una persona: la frase sale del
    catalogo por `REASON_KEYS` (convencion 4 del equipo).
    """

    #: Falta `stt`, `primary` o `fallback`: los campos de U15 llegan opcionales
    #: (CG-U15-4), y sin ellos no hay con que atender.
    NOT_CONFIGURED = "not_configured"
    #: Falta la voz principal o la de respaldo en uno de los dos idiomas.
    MISSING_LANGUAGE = "missing_language"
    #: El proveedor no tiene adaptador registrado en este proceso.
    UNKNOWN_PROVIDER = "unknown_provider"
    #: El modelo no esta anclado en `providers.yaml` para ese proveedor y ese uso.
    UNKNOWN_MODEL = "unknown_model"
    #: El modelo esta anclado pero no tiene respuesta grabada ni prueba de
    #: contrato: un proveedor que no la pasa no se puede activar (BR2.3).
    NO_CONTRACT = "no_contract"
    #: La voz no esta entre las que el proyecto comprobo que existen.
    UNKNOWN_VOICE = "unknown_voice"
    #: La voz existe, pero no con ese modelo o no en ese idioma.
    VOICE_MISMATCH = "voice_mismatch"


#: La frase que ve quien visita, por motivo. Escrita entera y **sin componer** la
#: clave: el chequeo del catalogo exige un consumidor literal para cada clave, y
#: un motivo nuevo sin su linea tiene que fallar aqui y no salir vacio en
#: pantalla.
REASON_KEYS: dict[VoiceOffReason, CopyKey] = {
    VoiceOffReason.NOT_CONFIGURED: CopyKey("voice.availability.not_configured"),
    VoiceOffReason.MISSING_LANGUAGE: CopyKey("voice.availability.misconfigured"),
    VoiceOffReason.UNKNOWN_PROVIDER: CopyKey("voice.availability.misconfigured"),
    VoiceOffReason.UNKNOWN_MODEL: CopyKey("voice.availability.misconfigured"),
    VoiceOffReason.NO_CONTRACT: CopyKey("voice.availability.misconfigured"),
    VoiceOffReason.UNKNOWN_VOICE: CopyKey("voice.availability.misconfigured"),
    VoiceOffReason.VOICE_MISMATCH: CopyKey("voice.availability.misconfigured"),
}


@dataclass(frozen=True)
class SpeechAdapterInfo:
    """Lo que la raiz de composicion sabe de un adaptador de voz registrado.

    `contract_models` son los modelos para los que **existe una respuesta
    grabada** y corre su prueba de contrato en cada entrega. Lo declara el
    paquete de cada adaptador, y una prueba de `test:u15` comprueba que cada
    modelo de la lista tiene su archivo grabado: asi "sin prueba de contrato no
    se activa" (BR2.3) es una propiedad que una herramienta mira, no una frase.
    """

    provider: ProviderName
    contract_models: frozenset[str]


class VoiceAvailability(Frozen):
    """Si la voz de una aseguradora puede atender, y por que no (entidad del mismo nombre)."""

    available: bool
    reason: VoiceOffReason | None = None
    #: La frase del catalogo que muestra la consola. Obligatoria si esta apagada.
    reason_key: CopyKey | None = None
    #: La clave del bloque `voice` donde fallo --`primary.en.voice_id`--, para
    #: quien opera. Es la ruta de una clave, nunca un valor.
    field: str | None = None

    @model_validator(mode="after")
    def _apagada_lleva_su_motivo(self) -> Self:
        if self.available and (self.reason or self.reason_key or self.field):
            msg = "una voz disponible no lleva motivo de apagado"
            raise ValueError(msg)
        if not self.available and (self.reason is None or self.reason_key is None):
            msg = "una voz apagada lleva su motivo y su frase del catalogo (BR2.2)"
            raise ValueError(msg)
        return self

    @classmethod
    def on(cls) -> VoiceAvailability:
        return cls(available=True)

    @classmethod
    def off(cls, reason: VoiceOffReason, *, field: str) -> VoiceAvailability:
        return cls(available=False, reason=reason, reason_key=REASON_KEYS[reason], field=field)


class VoiceUnavailableError(LookupError):
    """Se pidio la voz de una aseguradora cuya configuracion no la permite.

    Solo la levanta quien pide una voz **sin** haber mirado la disponibilidad:
    U16 mira `VoiceAvailability` antes de abrir la llamada, asi que en la ruta
    normal nunca sale.
    """


@dataclass(frozen=True)
class SpeechModel:
    """El modelo de transcripcion ya validado, con el que se construye el adaptador.

    Lleva ademas lo que la aseguradora le pide al reconocedor por idioma de la llamada
    (2026-10-13): el codigo de idioma que recibe el proveedor y los terminos clave. Los dos
    son opcionales y vacios por omision; quedan fuera del hash porque son mapas.
    """

    provider: ProviderName
    model: str
    mode: TranscriptionMode
    language_codes: Mapping[Locale, str] = field(default_factory=dict, hash=False)
    keyterms: Mapping[Locale, tuple[str, ...]] = field(default_factory=dict, hash=False)

    def language_code(self, language: Locale) -> str:
        """El codigo de idioma que se le manda al proveedor: el configurado, o el idioma tal cual."""
        return self.language_codes.get(language, language)

    def keyterms_for(self, language: Locale) -> tuple[str, ...]:
        """Los terminos clave de ese idioma de la llamada; vacio si la aseguradora no declara."""
        return self.keyterms.get(language, ())


# --- La validacion ------------------------------------------------------------


@dataclass(frozen=True)
class _Catalogo:
    """Lo declarado en `providers.yaml` y lo registrado en la raiz, juntos."""

    providers: ProvidersConfig
    adapters: Mapping[ProviderName, SpeechAdapterInfo]


def _proveedor(valor: str) -> ProviderName | None:
    try:
        return ProviderName(valor)
    except ValueError:
        return None


def _comprobar_modelo(
    *,
    provider_text: str,
    model: str,
    kind: ModelKind,
    field: str,
    catalogo: _Catalogo,
) -> VoiceAvailability | None:
    """El proveedor y el modelo de una eleccion. `None` si los dos valen."""
    nombre = _proveedor(provider_text)
    adaptador = catalogo.adapters.get(nombre) if nombre is not None else None
    if nombre is None or adaptador is None:
        return VoiceAvailability.off(VoiceOffReason.UNKNOWN_PROVIDER, field=f"{field}.provider")

    entrada = catalogo.providers.provider(nombre)
    if entrada is None or not entrada.has_model(model, kind=kind):
        return VoiceAvailability.off(VoiceOffReason.UNKNOWN_MODEL, field=f"{field}.model")

    if model not in adaptador.contract_models:
        return VoiceAvailability.off(VoiceOffReason.NO_CONTRACT, field=f"{field}.model")
    return None


def _comprobar_voz(
    eleccion: VoiceChoice, *, language: Locale, field: str, catalogo: _Catalogo
) -> VoiceAvailability | None:
    """Una voz de sintesis en un idioma. `None` si vale."""
    fallo = _comprobar_modelo(
        provider_text=eleccion.provider,
        model=eleccion.model,
        kind=ModelKind.SYNTHESIS,
        field=field,
        catalogo=catalogo,
    )
    if fallo is not None:
        return fallo

    # `_comprobar_modelo` ya garantizo que el proveedor existe y esta declarado.
    entrada = catalogo.providers.provider(ProviderName(eleccion.provider))
    voz = entrada.voice(eleccion.voice_id) if entrada is not None else None
    if voz is None:
        return VoiceAvailability.off(VoiceOffReason.UNKNOWN_VOICE, field=f"{field}.voice_id")
    if voz.model != eleccion.model or language not in voz.languages:
        return VoiceAvailability.off(VoiceOffReason.VOICE_MISMATCH, field=f"{field}.voice_id")
    return None


def _voces_de(
    bloque: VoicesByLanguage, *, nombre: str, catalogo: _Catalogo
) -> VoiceAvailability | None:
    """Las voces de un bloque --principal o de respaldo-- en los dos idiomas."""
    for idioma in LANGUAGES:
        eleccion = bloque.for_language(idioma)
        campo = f"{nombre}.{idioma}"
        if eleccion is None:
            return VoiceAvailability.off(VoiceOffReason.MISSING_LANGUAGE, field=campo)
        fallo = _comprobar_voz(eleccion, language=idioma, field=campo, catalogo=catalogo)
        if fallo is not None:
            return fallo
    return None


def voice_availability(
    voice: VoiceConfig,
    *,
    providers: ProvidersConfig,
    adapters: Mapping[ProviderName, SpeechAdapterInfo],
) -> VoiceAvailability:
    """Si la voz de una aseguradora puede atender. **Devuelve; no levanta.**

    El orden de las comprobaciones es fijo y se reporta el **primer** fallo: una
    configuracion con tres errores se arregla de uno en uno, y un motivo estable
    entre corridas es lo que permite escribir una prueba por cada forma de
    romperla. El orden es: que esten los tres bloques, la transcripcion, la voz
    principal en espanol y en ingles, y la de respaldo en los dos.
    """
    if voice.stt is None:
        return VoiceAvailability.off(VoiceOffReason.NOT_CONFIGURED, field="stt")
    if voice.primary is None:
        return VoiceAvailability.off(VoiceOffReason.NOT_CONFIGURED, field="primary")
    if voice.fallback is None:
        return VoiceAvailability.off(VoiceOffReason.NOT_CONFIGURED, field="fallback")

    catalogo = _Catalogo(providers=providers, adapters=adapters)
    fallo = _comprobar_modelo(
        provider_text=voice.stt.provider,
        model=voice.stt.model,
        kind=ModelKind.TRANSCRIPTION,
        field="stt",
        catalogo=catalogo,
    )
    if fallo is not None:
        return fallo

    for nombre, bloque in (("primary", voice.primary), ("fallback", voice.fallback)):
        fallo = _voces_de(bloque, nombre=nombre, catalogo=catalogo)
        if fallo is not None:
            return fallo
    return VoiceAvailability.on()


def availability_by_tenant(
    tenants: Iterable[TenantConfig],
    *,
    providers: ProvidersConfig,
    adapters: Mapping[ProviderName, SpeechAdapterInfo],
) -> dict[TenantId, VoiceAvailability]:
    """La disponibilidad de la voz de cada aseguradora, y un evento por cada apagada.

    El evento lleva la aseguradora, el motivo cerrado y la **clave** que fallo,
    nunca su valor: es lo que quien opera necesita para arreglarla sin abrir el
    codigo, y no es un dato de nadie.
    """
    resultado: dict[TenantId, VoiceAvailability] = {}
    for tenant in tenants:
        estado = voice_availability(tenant.voice, providers=providers, adapters=adapters)
        resultado[tenant.tenant_id] = estado
        if not estado.available and estado.reason is not None:
            observability.emit(
                "providers.voice_unavailable",
                tenant_id=tenant.tenant_id,
                reason=estado.reason.value,
                field=estado.field,
            )
    return resultado


# --- De la configuracion a lo que recibe el adaptador -------------------------


def _exigir(voice: VoiceConfig) -> tuple[SpeechModelChoice, VoicesByLanguage, VoicesByLanguage]:
    if voice.stt is None or voice.primary is None or voice.fallback is None:
        msg = (
            "la voz de esta aseguradora no esta configurada: mire su disponibilidad "
            "antes de pedirla (BR2.2)"
        )
        raise VoiceUnavailableError(msg)
    return voice.stt, voice.primary, voice.fallback


def voice_ref(voice: VoiceConfig, *, mode: VoiceMode, language: Locale) -> VoiceRef:
    """La voz que se usa en esa llamada, en ese idioma y en ese modo.

    Lo que cambia entre la principal y la de respaldo es **solo** esta eleccion:
    el texto y sus claves del catalogo vienen de antes del adaptador, asi que las
    dos dicen lo mismo (BR4.2).
    """
    _, principal, respaldo = _exigir(voice)
    bloque = principal if mode is VoiceMode.PRIMARY else respaldo
    eleccion = bloque.for_language(language)
    nombre = _proveedor(eleccion.provider) if eleccion is not None else None
    if eleccion is None or nombre is None:
        msg = (
            f"la voz '{mode.value}' en '{language}' no esta configurada o nombra un "
            "proveedor desconocido: mire su disponibilidad antes de pedirla (BR2.2)"
        )
        raise VoiceUnavailableError(msg)
    return VoiceRef(
        provider=nombre, model=eleccion.model, voice_id=eleccion.voice_id, language=language
    )


def transcription_model(voice: VoiceConfig) -> SpeechModel:
    """El modelo de transcripcion de una aseguradora, ya con su proveedor cerrado."""
    stt, _, _ = _exigir(voice)
    nombre = _proveedor(stt.provider)
    if nombre is None:
        msg = (
            f"el proveedor de transcripcion '{stt.provider}' no existe: mire la "
            "disponibilidad antes de pedirlo (BR2.2)"
        )
        raise VoiceUnavailableError(msg)
    return SpeechModel(
        provider=nombre,
        model=stt.model,
        mode=stt.mode,
        language_codes=dict(stt.language_codes),
        keyterms=dict(stt.keyterms),
    )
