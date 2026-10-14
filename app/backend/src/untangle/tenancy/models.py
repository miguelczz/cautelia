"""Los tipos de U2: aseguradoras, identidad, enlaces y borrado.

Ocho entidades, de las cuales **solo dos son tablas**: el enlace de caso y la
clave del navegador. Las demas viven en configuracion versionada --la
aseguradora, la persona de bandeja, la tabla de permisos-- o son valores que se
devuelven y no se guardan --la credencial, el informe de aislamiento, el
resultado de un purgador--.

Esa proporcion es el diseno y no una casualidad: todo lo que distingue a una
aseguradora de otra se lee en una revision de codigo, y a la base solo llegan
las dos cosas que necesitan poder revocarse y borrarse cada noche.

Este modulo es una hoja: no importa ninguna otra pieza de `tenancy`, para que el
cargador de configuracion pueda validar una carpeta sin que exista base de
datos.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, Self, runtime_checkable

from pydantic import Field, field_validator, model_validator

from untangle.base import Frozen, Locale

#: El identificador de una aseguradora. Es el mismo valor que nombra su carpeta,
#: viaja en la variable de sesion y llena la columna de aislamiento de cada
#: tabla, asi que no cambia una vez publicado.
type TenantId = str

#: Forma del identificador: minusculas, digitos y guiones. Un identificador con
#: mayusculas o espacios acabaria escrito de dos maneras distintas el dia que
#: alguien lo teclee a mano.
TENANT_ID_PATTERN = r"^[a-z][a-z0-9-]{1,30}$"


# --- Errores ------------------------------------------------------------------


class UnknownTenantError(LookupError):
    """Se pidio algo para una aseguradora que no esta en la configuracion.

    Falla en el acto y nombra el identificador. Devolver una sesion vacia
    convertiria un error del codigo en "no hay datos", que es la misma confusion
    que el proyecto prohibe entre "no hay clausula" y "no pude verificar"
    (BR1.5).
    """


class SessionNotConfiguredError(RuntimeError):
    """Se pidio una sesion antes de decirle al modulo a que base conectarse.

    Falla al primer uso y dice como arreglarlo, en vez de abrir una conexion a
    un destino adivinado.
    """


class TenantConfigError(ValueError):
    """Una carpeta de aseguradora no valida. El mensaje nombra archivo y clave."""


class CredentialRejectedError(Exception):
    """La credencial de bandeja no vale, y hacia fuera no se dice por que.

    La causa real viaja en `cause` para el evento de rastro; la respuesta que ve
    quien la presento es la misma en las tres causas (BR2.4, SEC-U2.6).
    """

    def __init__(self, cause: CredentialRejection) -> None:
        super().__init__(REJECTION_MESSAGE)
        self.cause = cause
        self.denial = staff_denial(cause)


class LinkRejectedError(Exception):
    """El canje del enlace no vale, y hacia fuera responde como un caso inexistente.

    Las cuatro causas --invalido, caducado, revocado, de otro caso-- comparten
    respuesta; distinguirlas diria que enlaces existieron alguna vez (BR3.3).
    """

    def __init__(self, cause: LinkRejection) -> None:
        super().__init__(REJECTION_MESSAGE)
        self.cause = cause
        self.denial = link_denial(cause)


#: Lo unico que se dice hacia fuera ante un rechazo, sea cual sea la causa. No es
#: texto para una persona: la pantalla resuelve el suyo por el catalogo de copy.
REJECTION_MESSAGE = "not_found"


@dataclass(frozen=True)
class Denial:
    """La respuesta de un rechazo: la misma para todas las causas de su familia.

    No "identica en significado": **identica en bytes**, mismo codigo y mismo
    cuerpo. Una respuesta distinta por causa le dice a quien prueba cual de las
    causas acerto, y eso convierte el rechazo en un oraculo (BR2.4, BR3.3).
    """

    status: int
    code: str

    def body(self) -> bytes:
        """El cuerpo exacto que se devuelve. Lo comparan las pruebas entre si."""
        return f'{{"code":"{self.code}"}}'.encode()


def staff_denial(cause: CredentialRejection) -> Denial:
    """La respuesta ante una credencial de bandeja rechazada.

    Recibe la causa **y no la usa**: esta escrito asi a proposito, para que la
    prueba que compara las tres respuestas entre si detecte el dia que alguien
    meta la causa en el cuerpo "solo para depurar". La causa viaja al rastro, no
    al cliente (SEC-U2.6, SEC-U2.11).
    """
    del cause
    return Denial(status=404, code=REJECTION_MESSAGE)


def link_denial(cause: LinkRejection) -> Denial:
    """La respuesta ante un enlace de caso rechazado.

    Las cuatro causas responden `404 link_invalid`, igual que un caso que nunca
    existio (C-07, BR3.3). Igual que arriba, la causa entra y no sale.
    """
    del cause
    return Denial(status=404, code="link_invalid")


class CredentialRejection(StrEnum):
    """Por que se rechazo una credencial de bandeja. Lista cerrada, para el rastro."""

    MISSING = "missing"
    SIGNATURE_INVALID = "signature_invalid"
    EXPIRED = "expired"
    WRONG_TENANT = "wrong_tenant"
    UNKNOWN_PRINCIPAL = "unknown_principal"
    ACTION_NOT_PERMITTED = "action_not_permitted"


class LinkRejection(StrEnum):
    """Las cuatro causas de rechazo de un enlace de caso (BR3.3)."""

    INVALID = "invalid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    OTHER_CASE = "other_case"


# --- Configuracion por aseguradora --------------------------------------------


class Role(StrEnum):
    """Los roles de la bandeja. Lo que puede hacer cada uno lo decide la tabla
    de permisos, no este valor por si solo (BR2.5)."""

    ADJUSTER = "adjuster"
    ACCOUNT_AGENT = "account_agent"
    #: Quien decide una solicitud de cotizacion derivada, y solo eso (BR4.1 de
    #: U19). No decide cobertura: aprobar un siniestro y aprobar una solicitud son
    #: dos acciones distintas de la tabla, no la misma vista desde otro rol.
    UNDERWRITER = "underwriter"


class Action(StrEnum):
    """Las acciones de la bandeja que hoy nombran las historias.

    Una accion nueva la anade la unidad que la introduce, con su fila en la
    tabla de permisos y su prueba.
    """

    VIEW_CASE = "view_case"
    LIST_CASES = "list_cases"
    DECIDE_CASE = "decide_case"
    CORRECT_FIELD = "correct_field"
    SEND_MESSAGE = "send_message"
    #: Marcar un caso como enviado a la aseguradora emisora. Es la accion propia
    #: de una agencia y la anadio U14, la unidad que la introdujo (BR4.6).
    MARK_SENT = "mark_sent"
    #: Decidir una solicitud de cotizacion derivada. La anadio U19 (BR4.1).
    #:
    #: **Accion propia y no `DECIDE_CASE`**: esa esta en `true` para el ajustador,
    #: porque decide la cobertura de los siniestros de su aseguradora. Reusarla
    #: aqui habria hecho imposible lo que AC6.3.3 comprueba --que una credencial
    #: de ajustador **no** decida una solicitud-- sin quitarle lo que si le toca.
    DECIDE_QUOTE = "decide_quote"
    #: Anotar para las reglas de triage el monto estimado, la cobertura disputada o la
    #: sospecha de fraude. Lo anadio la bandeja (2026-10-13).
    #:
    #: **Accion propia y no `CORRECT_FIELD`**: corregir un campo es arreglar un error de
    #: captura y lo hace tambien la agencia; estimar un monto o dudar de una cobertura es
    #: un juicio del ajustador (decision del 2026-10-03), y la tabla tiene que poder
    #: dar lo uno sin lo otro.
    ANNOTATE_TRIAGE = "annotate_triage"


class TenantKind(StrEnum):
    """Una agencia deriva siempre a quien emitio la poliza; una aseguradora decide."""

    CARRIER = "carrier"
    AGENCY = "agency"


class StaffPrincipal(Frozen):
    """Una persona de la bandeja. Las credenciales NO viven aqui (D23)."""

    principal_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,30}$")
    role: Role
    display_name: str = Field(min_length=1)


class TranscriptionMode(StrEnum):
    """Como transcribe el modelo: detectando el idioma o en uno solo (ADR-007)."""

    #: Detecta el idioma en cada palabra. Es el modo de ADR-007: el de menor error
    #: medido en espanol, y el que deja cambiar de idioma sin selector.
    MULTI = "multi"
    #: Transcribe en el idioma que se le pide.
    MONOLINGUAL = "monolingual"


#: Cuantos terminos clave se le mandan al reconocedor por idioma, como maximo. El
#: reconocedor admite 500 tokens en total y recomienda de 20 a 50 terminos; 50 es el
#: techo de lo recomendado. Un termino de mas no falla en el proveedor: se pierde.
KEYTERMS_MAX_COUNT = 50

#: Cuantos caracteres suman los terminos de un idioma, como maximo. No hay tokenizador del
#: proveedor en el repositorio, asi que el tope se escoge por el peor caso: a dos caracteres
#: por token (el espanol rinde tres o cuatro) 700 caracteres son 350 tokens, y con un
#: separador por termino siguen siendo menos de 450 de los 500 admitidos.
KEYTERMS_MAX_CHARACTERS = 700

#: Un termino clave es corto: un lugar, una via, un modelo de carro. Mas largo es una frase.
KEYTERM_MAX_LENGTH = 40

#: Lo que cabe en un termino. Letras (con tildes), cifras, espacio, guion, apostrofo y punto.
#: Quedan fuera la coma, el punto y coma y los dos puntos: el reconocedor los acepta sin
#: error y **no hace nada con el termino**, que es el peor fallo posible (se cree que ayuda).
_KEYTERM_PATTERN = re.compile(r"^[\w][\w .'\-]*$")

#: Un codigo de idioma tal como lo escribe el proveedor: `es`, `es-419`, `en-US`.
_LANGUAGE_CODE_PATTERN = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


class SpeechModelChoice(Frozen):
    """El modelo de transcripcion de una aseguradora (entidad `SpeechModelRef`).

    `provider` y `model` son **texto y no un conjunto cerrado**, a proposito: un
    proveedor o un modelo que no existen tienen que apagar la voz de esa
    aseguradora con su motivo, y no la aseguradora entera (BR2.2). Si fueran un
    enum, la carpeta no validaria su esquema y el cargador apagaria tambien el
    chat. Quien decide si el valor sirve es la disponibilidad de la voz, en
    `providers/voice_availability.py`.

    **Lo que se le pide al reconocedor ademas del audio** (2026-10-13) son dos claves
    opcionales, por idioma de la llamada. Viven aqui y no en `providers.yaml` porque se
    parecen a `mode`: son parametros de transcripcion que escoge cada aseguradora, y porque
    cada una lleva el nombre de la suya y el de su agente en la lista. Son opcionales por
    C-25: una aseguradora que no las declara transcribe como antes.
    """

    provider: str
    model: str
    mode: TranscriptionMode
    #: El codigo de idioma que recibe el proveedor por cada idioma de la llamada. El
    #: aplicativo sigue trabajando con `es` y `en`; esto solo dice que variante pide: para
    #: `es`, `es-419` (Latinoamerica). Un idioma sin entrada se manda tal cual.
    language_codes: dict[Locale, str] = Field(default_factory=dict)
    #: Los terminos que el reconocedor debe esperar oir, por idioma de la llamada: la forma
    #: del numero de poliza, los lugares y las vias del valle de Aburra, los carros mas
    #: comunes y el nombre de la aseguradora y de su agente. **Nunca nombres de personas**.
    keyterms: dict[Locale, tuple[str, ...]] = Field(default_factory=dict)

    @field_validator("language_codes")
    @classmethod
    def _codigos_de_idioma(cls, codigos: dict[Locale, str]) -> dict[Locale, str]:
        for idioma, codigo in codigos.items():
            if _LANGUAGE_CODE_PATTERN.fullmatch(codigo) is None:
                msg = (
                    f"'{codigo}' no tiene la forma de un codigo de idioma (por ejemplo "
                    "'es-419'); 'multi' tampoco vale, el modo ya lo decide `mode`"
                )
                raise ValueError(msg)
            if codigo.split("-", 1)[0] != idioma:
                msg = (
                    f"el codigo '{codigo}' no es una variante de '{idioma}': cada idioma de "
                    "la llamada pide una variante de si mismo"
                )
                raise ValueError(msg)
        return codigos

    @field_validator("keyterms")
    @classmethod
    def _terminos_clave(
        cls, por_idioma: dict[Locale, tuple[str, ...]]
    ) -> dict[Locale, tuple[str, ...]]:
        for idioma, terminos in por_idioma.items():
            for termino in terminos:
                if (
                    not termino
                    or termino != termino.strip()
                    or len(termino) > KEYTERM_MAX_LENGTH
                    or _KEYTERM_PATTERN.fullmatch(termino) is None
                ):
                    msg = (
                        f"el termino {termino!r} de '{idioma}' no vale: va sin espacios "
                        f"sobrantes, con hasta {KEYTERM_MAX_LENGTH} caracteres y sin comas, "
                        "punto y coma ni dos puntos, que el reconocedor acepta sin error "
                        "y no hace nada con ellos"
                    )
                    raise ValueError(msg)
            plegados = [t.casefold() for t in terminos]
            if len(set(plegados)) != len(plegados):
                repetido = next(t for t in terminos if plegados.count(t.casefold()) > 1)
                msg = f"el termino '{repetido}' de '{idioma}' esta repetido"
                raise ValueError(msg)
            if len(terminos) > KEYTERMS_MAX_COUNT:
                msg = (
                    f"'{idioma}' declara {len(terminos)} terminos clave y el tope es "
                    f"{KEYTERMS_MAX_COUNT}: el reconocedor admite 500 tokens en total y lo "
                    "que sobra se pierde sin avisar"
                )
                raise ValueError(msg)
            caracteres = sum(len(t) for t in terminos)
            if caracteres > KEYTERMS_MAX_CHARACTERS:
                msg = (
                    f"los terminos clave de '{idioma}' suman {caracteres} caracteres y el "
                    f"tope es {KEYTERMS_MAX_CHARACTERS}: el reconocedor admite 500 tokens "
                    "en total y lo que sobra se pierde sin avisar"
                )
                raise ValueError(msg)
        return por_idioma


class VoiceChoice(Frozen):
    """Una voz de sintesis, tal como la escribe la configuracion (entidad `VoiceRef`).

    Texto y no conjuntos cerrados, por la misma razon que el modelo de
    transcripcion: un valor desconocido apaga la voz, no la aseguradora (BR2.2).
    """

    provider: str
    model: str
    voice_id: str


class VoicesByLanguage(Frozen):
    """Una voz por idioma. Los dos son opcionales **en la forma** y obligatorios
    en la disponibilidad: si falta uno, la voz de esa aseguradora queda apagada
    con su motivo (NFR20.3), y el chat sigue."""

    es: VoiceChoice | None = None
    en: VoiceChoice | None = None

    def for_language(self, language: Locale) -> VoiceChoice | None:
        return self.es if language == "es" else self.en


class VoiceConfig(Frozen):
    """El bloque de voz. Su significado lo fijan U15 y U16; U2 solo su forma.

    Dos generaciones de campos conviven aqui, y conviene leerlas asi:

    - `primary_voice`, `fallback_voice` y `language_default` son los de C-25.
      `primary_voice` es **el nombre con el que el proyecto habla de la voz**
      --Catalina-- y no un identificador que ningun proveedor entienda.
    - `stt`, `primary` y `fallback` los anade U15 (CG-U15-4) y son los que usa la
      llamada: proveedor, modelo y voz por idioma, principal y de respaldo
      (BR2.1). Llegan **opcionales**, como pide C-25 para una clave nueva, y sin
      subir `config_version`. Si falta alguno, la voz de esa aseguradora queda
      apagada con su motivo del catalogo y el chat sigue (BR2.2).

    Lo que apaga la voz sin apagar la aseguradora son los **valores**: un
    proveedor, un modelo o una voz que no existen, o un idioma sin voz. Una clave
    mal escrita dentro del bloque sigue la regla de toda la carpeta --no valida
    su esquema y el cargador la nombra--, igual que cualquier otra clave de este
    archivo.
    """

    primary_voice: str = Field(min_length=1)
    fallback_voice: str | None = None
    language_default: Locale
    #: Si la agente cambia de idioma al notar que la persona cambio, sin que se lo
    #: pidan (U18, BR3.1). **Apagado por omision**, y no es prudencia: AC1.31.5
    #: escribe explicitamente la conducta con esto apagado, asi que las dos ramas
    #: existen en el criterio y la que decide es esta carpeta, nunca un `if` por
    #: aseguradora. Ademas US1.32 es la ultima historia en la regla de corte del
    #: PRD: si se corta, lo que queda es la conducta que ya esta construida.
    #:
    #: **Sin efecto del 2026-10-11 al 2026-10-13, y otra vez con efecto desde entonces.**
    #: Mientras el reconocedor era de un solo idioma por conexion y no se reabria, cambiar
    #: la voz sola dejaba a la persona hablando con quien no la entendia. Ahora el ciclo
    #: reabre el reconocedor en el idioma nuevo (`CallRunner._escuchar`). Las tres
    #: aseguradoras lo traen encendido en su carpeta.
    auto_language_detection: bool = False
    stt: SpeechModelChoice | None = None
    primary: VoicesByLanguage | None = None
    fallback: VoicesByLanguage | None = None


#: Un color de la marca, en hexadecimal de seis digitos. La forma se impone aqui
#: y no en la interfaz: un color mal escrito en la configuracion tiene que
#: apagar la carpeta al arrancar, nombrando el archivo y la clave (BR4.1), y no
#: llegar como un estilo invalido que el navegador ignora en silencio.
BRAND_COLOR_PATTERN = r"^#[0-9A-Fa-f]{6}$"

#: La forma de una clave del catalogo de textos. Es la misma que fija
#: `copy_catalog.models.COPY_KEY_PATTERN`, escrita otra vez porque `tenancy` esta
#: debajo del catalogo en el contrato de capas y no puede importarlo. Si una
#: cambiara sin la otra, la prueba de U6 que compara las dos lo diria.
CHARACTER_KEY_PATTERN = r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$"


class Monogram(StrEnum):
    """La forma geometrica que dibuja la interfaz como marca de una aseguradora.

    La configuracion elige la forma; el codigo no sabe que aseguradora la usa
    (BR1.6, convencion 9 del equipo).
    """

    ARCH = "arch"
    HORIZON = "horizon"
    RINGS = "rings"


class TenantBrand(Frozen):
    """La marca minima de una aseguradora: su acento en cada modo y su monograma.

    Es un agregado **aditivo** a C-25 (FD-U6-5, CG-U6-4): llega opcional y sin
    subir `config_version`. El contraste de cada acento contra su texto lo fijo
    `design-system-mapping.md` y lo mide el arnes de accesibilidad; aqui solo se
    impone la forma.
    """

    #: Acento del modo claro. Con texto blanco encima pasa 4,5:1.
    accent: str = Field(pattern=BRAND_COLOR_PATTERN)
    #: Variante del modo oscuro. Con la tinta del fondo oscuro encima pasa 4,5:1.
    accent_on_dark: str = Field(pattern=BRAND_COLOR_PATTERN)
    monogram: Monogram


class IntakeConfig(Frozen):
    """Cuantos insultos disparan cada paso de la captura, por aseguradora (BR5.4, TECH-U11.5).

    Es un agregado **aditivo** a C-25 (U11, misma forma que `TenantBrand`):
    llega con su valor por omision y sin subir `config_version`, para que una
    aseguradora que todavia no lo declara en su archivo siga cargando igual.
    "El numero lo fija la configuracion de cada aseguradora, no el codigo"
    (AC1.13.3) es justo lo que este bloque hace posible: un numero en el
    codigo seria la diferencia entre aseguradoras metida en una rama que la
    convencion 9 del equipo prohibe.
    """

    #: Al llegar a este insulto, la frase de calma y la oferta de que una
    #: persona revise el caso. **Dos**, y no uno: AC1.13.3 empieza "dado que
    #: insulto a la agente dos veces seguidas".
    calm_after_insults: int = Field(default=2, ge=1)
    #: Al llegar a este insulto, la frase de cierre por abuso: la sesion
    #: termina y el caso queda "esperando al asegurado" con ese motivo. **Tres**:
    #: el "y si vuelvo a insultar" del mismo criterio. Terminar la sesion un
    #: insulto antes de lo que dice el criterio aprobado le cuelga la llamada a
    #: quien todavia tenia un turno.
    close_after_insults: int = Field(default=3, ge=1)

    @model_validator(mode="after")
    def _el_cierre_llega_despues_de_la_calma(self) -> Self:
        if self.close_after_insults <= self.calm_after_insults:
            msg = (
                "'close_after_insults' tiene que ser mayor que "
                "'calm_after_insults': el cierre por abuso llega despues de la "
                "calma, nunca antes ni al mismo tiempo (BR5.4)"
            )
            raise ValueError(msg)
        return self


class ChatConfig(Frozen):
    """Los limites del chat publico de una aseguradora (BR3.1, BR3.2 de U13).

    Es un agregado **aditivo** a C-25, con la misma forma que `IntakeConfig`:
    llega con sus valores por omision y sin subir `config_version`, para que una
    aseguradora que todavia no lo declara siga cargando igual.

    Los cinco numeros viven aqui y no en el codigo por la convencion 9 del
    equipo: una diferencia entre aseguradoras metida en una rama del codigo es
    exactamente lo que el proyecto prohibe. Y viven en configuracion versionada
    --no en la base-- porque cambiarlos es una decision que se revisa en un
    diff, no un valor que alguien ajusta en caliente.

    **Ninguno de estos limites sustituye al tope del proveedor** (BR3.3): un
    limite que vive solo en la aplicacion falla abierto cuando lo que falla es
    la aplicacion.
    """

    #: Mensajes por conversacion antes de la frase de limite.
    messages_per_session: int = Field(default=20, ge=1)
    #: Mensajes por origen y dia. Mas alto que el de sesion: un origen puede
    #: tener varias conversaciones legitimas --una oficina, una universidad--.
    messages_per_origin_per_day: int = Field(default=120, ge=1)
    #: Mensajes de todo el sitio por dia, que es el que protege la cuota.
    messages_per_site_per_day: int = Field(default=600, ge=1)
    #: Segundos minimos entre dos mensajes de la misma conversacion.
    min_seconds_between_messages: float = Field(default=1.0, ge=0)
    #: Caracteres maximos de un mensaje. Uno mas largo se rechaza **sin llamar
    #: al modelo**: cobrar por un mensaje que no se va a atender es justo lo que
    #: el limite existe para evitar.
    max_message_characters: int = Field(default=2000, ge=1)

    @model_validator(mode="after")
    def _el_limite_del_sitio_no_es_menor_que_el_de_un_origen(self) -> Self:
        if self.messages_per_site_per_day < self.messages_per_origin_per_day:
            msg = (
                "'messages_per_site_per_day' no puede ser menor que "
                "'messages_per_origin_per_day': el limite del sitio quedaria "
                "alcanzado antes que el de un solo origen, y la frase que ve la "
                "persona nombraria el limite equivocado (BR3.1)"
            )
            raise ValueError(msg)
        return self


class CallConfig(Frozen):
    """Los tiempos de una llamada de voz de una aseguradora (U16, C-08).

    Aditivo a C-25, con la misma forma que `ChatConfig`: llega con sus valores por
    omision y sin subir `config_version`, para que una aseguradora que todavia no
    lo declara siga cargando igual.

    **Son tres y no cinco.** C-08 declara ademas los carriles por visitante y por
    sitio, y esos **no son de una aseguradora**: "quince llamadas del sitio" escrito
    en tres carpetas son cuarenta y cinco, o las que toque leer. Viven en
    `VoiceLimits` (`providers.yaml`), que los declara sin valor por omision a
    proposito, y U17 los aplica desde ahi con `voice.admission.decide`. Los tres de
    aqui si son de cada aseguradora: cuanto dura una llamada, cuando se avisa y
    cuanto queda retomable son decisiones de como conversa cada una.
    """

    #: Cuanto puede durar una llamada. Al agotarse termina con `max_duration`.
    max_call_seconds: int = Field(default=240, ge=30)
    #: Cuanto antes del final se avisa. Cortar sin avisar es la peor pantalla
    #: posible, y avisar con la llamada ya terminada no es avisar.
    warn_at_seconds: int = Field(default=45, ge=5)
    #: Cuanto tiempo queda retomable un caso despues de un corte (BR6.1).
    resume_window_seconds: int = Field(default=900, ge=60)

    @model_validator(mode="after")
    def _el_aviso_cabe_dentro_de_la_llamada(self) -> Self:
        if self.warn_at_seconds >= self.max_call_seconds:
            msg = (
                "'warn_at_seconds' tiene que ser menor que 'max_call_seconds': un "
                "aviso que vence al empezar la llamada avisa de nada, y uno que "
                "vence despues del final no llega a decirse"
            )
            raise ValueError(msg)
        return self


class TenantConfig(Frozen):
    """Una aseguradora, tal como la declara su carpeta versionada (C-25).

    Anadir una cuarta es anadir una carpeta: no hay tabla que migrar ni codigo
    que tocar (FR9.3, BR4.3).
    """

    config_version: int = Field(default=1, ge=1)
    tenant_id: str = Field(pattern=TENANT_ID_PATTERN)
    display_name: str = Field(min_length=1)
    kind: TenantKind
    default_language: Locale
    jurisdiction: str = Field(min_length=1)
    quote_enabled: bool = False
    #: Si el chat de esta aseguradora puede seguir un caso que se empezo por llamada, cuando la
    #: persona escribe su numero desde el mismo navegador (US1.20, AC1.19.5). Apagado, el chat no
    #: promete retomarlo: explica que un caso se retoma por el canal en el que empezo. Es dato de la
    #: aseguradora y no una rama del codigo (convencion 9); por omision apagado, como
    #: `quote_enabled`, y cada carpeta lo declara.
    voice_to_chat_continuity: bool = False
    example_policy: str = Field(min_length=1)
    #: Quien emitio la poliza de ejemplo, por su identificador de aseguradora
    #: (decision Q2 de U23). **Obligatorio en una agencia y prohibido en una
    #: emisora**: una agencia coloca polizas que emite otra, y la vista de
    #: comparacion tiene que nombrarla (BR1.2 de U23); una emisora que lo
    #: declarara estaria diciendo que su propia poliza la emitio alguien mas.
    #:
    #: Se declara el **identificador** y no el nombre visible: el nombre es dato
    #: de la otra carpeta, y copiarlo aqui seria una segunda verdad que el dia que
    #: esa aseguradora se renombre dejaria a esta mintiendo. El nombre lo resuelve
    #: el directorio del inicio, que tiene las tres cargadas.
    #:
    #: Y un chequeo compara lo declarado con el `issuer_tenant` de la poliza en los
    #: datos versionados: declarar y comprobar, en vez de elegir entre duplicar el
    #: dato o acoplar el inicio al corpus.
    example_policy_issuer: str | None = Field(default=None, pattern=TENANT_ID_PATTERN)
    #: El prefijo de tres letras del numero de caso (BR4.1, decision FD-U4-1 de
    #: Miguel). Lo consume U4 `case-record`, pero vive aqui porque es **dato de
    #: la aseguradora**: escribirlo en el codigo seria la ramificacion por
    #: inquilino que el proyecto prohibe. Que dos no lo repitan lo comprueba U4
    #: al arrancar, porque es una propiedad del conjunto y no de una carpeta.
    case_number_prefix: str = Field(pattern=r"^[A-Z]{3}$")
    copy_overrides: tuple[str, ...] = ()
    voice: VoiceConfig
    staff: tuple[StaffPrincipal, ...] = ()
    #: La marca que el inicio y las cabeceras dibujan (U6, FD-U6-5). **Opcional**
    #: por C-25 (CG-U6-4): sin ella, la fila usa los tokens de Untangle y no
    #: dibuja monograma; nada se inventa (BR4.2).
    brand: TenantBrand | None = None
    #: La clave del catalogo con el caracter de la aseguradora, en los dos
    #: idiomas (U6). Opcional por la misma razon: sin ella, la fila omite esa
    #: linea (BR4.2).
    character_key: str | None = Field(default=None, pattern=CHARACTER_KEY_PATTERN)
    #: Como se llama la agente de esta aseguradora (decision de Miguel, 2026-10-11:
    #: una por aseguradora). Un nombre de pila, igual en los dos idiomas. Opcional:
    #: sin el, se usa el del catalogo (`insurer.agent.name`). Tiene que sobrevivir al
    #: detector de datos personales: la raiz lo instala como nombre publico.
    agent_name: str | None = Field(default=None, pattern=r"^[A-Za-zÁÉÍÓÚÑáéíóúñ]{2,24}$")
    #: BR5.4, TECH-U11.5: cuantos insultos disparan la calma y el cierre.
    intake: IntakeConfig = Field(default_factory=IntakeConfig)
    #: BR3.1, BR3.2 de U13: los cinco limites del chat publico.
    chat: ChatConfig = Field(default_factory=ChatConfig)
    #: Los tiempos de la llamada de voz (U16): duracion, aviso y ventana de retoma.
    call: CallConfig = Field(default_factory=CallConfig)

    @model_validator(mode="after")
    def _el_emisor_lo_declara_quien_no_emite(self) -> Self:
        """Q2 de U23: obligatorio en una agencia, prohibido en una emisora.

        Una carpeta de agencia sin emisor **no carga**, que es mas fuerte que
        fallar cerrado en la pantalla: el patron del proyecto es que una carpeta
        rota se apaga sola, y asi el dato no puede faltar en ejecucion.
        """
        if self.kind is TenantKind.AGENCY and self.example_policy_issuer is None:
            msg = (
                f"la agencia '{self.tenant_id}' no declara 'example_policy_issuer': "
                "una agencia coloca polizas que emite otra y la vista de comparacion "
                "tiene que nombrarla"
            )
            raise ValueError(msg)
        if self.kind is TenantKind.CARRIER and self.example_policy_issuer is not None:
            msg = (
                f"la aseguradora '{self.tenant_id}' emite sus polizas y declara "
                "'example_policy_issuer': eso diria que su poliza de ejemplo la emitio "
                "alguien mas"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _dos_personas_no_comparten_identificador(self) -> Self:
        vistos = [persona.principal_id for persona in self.staff]
        repetidos = sorted({p for p in vistos if vistos.count(p) > 1})
        if repetidos:
            msg = f"la aseguradora '{self.tenant_id}' repite las personas {repetidos}"
            raise ValueError(msg)
        return self

    def principal(self, principal_id: str) -> StaffPrincipal | None:
        for persona in self.staff:
            if persona.principal_id == principal_id:
                return persona
        return None


class RuleDefinition(Frozen):
    """Una regla del motor por aseguradora. U2 fija su **forma**; su significado
    es de U9, que la ejecuta, y por eso `when` y `then` quedan abiertos aqui."""

    id: str = Field(min_length=1)
    version: int = Field(ge=1)
    when: dict[str, object]
    then: dict[str, object]
    tests: tuple[dict[str, object], ...] = ()

    @model_validator(mode="after")
    def _toda_regla_trae_su_caso(self) -> Self:
        # Cada regla viene con su test (M5). Una regla sin caso es una regla que
        # nadie comprueba, y el motor de reglas es donde eso se paga.
        if not self.tests:
            msg = f"la regla '{self.id}' no trae ningun caso de prueba (M5)"
            raise ValueError(msg)
        return self


class RuleSet(Frozen):
    """El archivo de reglas de una aseguradora (C-25)."""

    ruleset_version: str = Field(min_length=1)
    rules: tuple[RuleDefinition, ...] = ()

    @model_validator(mode="after")
    def _dos_reglas_no_comparten_identificador(self) -> Self:
        vistos = [regla.id for regla in self.rules]
        repetidos = sorted({r for r in vistos if vistos.count(r) > 1})
        if repetidos:
            msg = f"el conjunto de reglas repite los identificadores {repetidos}"
            raise ValueError(msg)
        return self


@dataclass(frozen=True)
class UnavailableTenant:
    """Una carpeta que no valida. Su aseguradora queda fuera, las demas siguen.

    Un error de una carpeta que tumbara las tres convertiria un descuido de
    configuracion en una caida total (BR4.1).
    """

    tenant_id: TenantId
    detail: str


# --- Identidad ----------------------------------------------------------------


@dataclass(frozen=True)
class StaffCredential:
    """El contenido firmado que identifica a una persona de la bandeja.

    No se guarda en ninguna tabla: viaja en una cookie y se verifica con la firma
    en cada peticion (BR2.3).
    """

    tenant_id: TenantId
    principal_id: str
    role: Role
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class RolePermission:
    """Una fila de la tabla versionada de permisos (decision Q4)."""

    role: Role
    action: Action
    allowed: bool


# --- Aislamiento --------------------------------------------------------------


@dataclass(frozen=True)
class TableIsolation:
    """Lo que el catalogo vivo respondio sobre una tabla."""

    table: str
    row_security: bool
    force_row_security: bool
    tenant_policies: int


@dataclass(frozen=True)
class ConnectionRole:
    """Lo que el motor respondio sobre el rol **vivo** de esta conexion.

    Se le pregunta al motor y no a la migracion que lo creo: leer como se creo un
    rol no prueba con que rol se esta conectado ahora (BR1.7).
    """

    name: str
    bypass_rls: bool
    superuser: bool


@dataclass(frozen=True)
class RlsFailure:
    """Una tabla que falla, con el nombre y **que le falta** de las tres."""

    table: str
    missing: tuple[str, ...]


@dataclass(frozen=True)
class ExcludedTable:
    """Una tabla fuera de la asercion, con su razon escrita."""

    table: str
    reason: str


@dataclass(frozen=True)
class TableColumn:
    """Lo que el catalogo vivo respondio sobre **una columna** (BR7.2).

    Existe porque la pregunta de arriba no la responde: `TableIsolation` trae
    informacion de tabla --si el aislamiento esta habilitado, forzado y con
    politica-- y **ninguna de columnas**. Una tabla que sale del aislamiento
    paga con una segunda pregunta, y esta es la forma de su respuesta.

    `data_type` llega tal como lo escribe el motor: `text`, `character
    varying(32)`, `numeric(20,12)`. Se guarda entero y no troceado porque el
    mensaje de fallo lo nombra, y un tipo a medias no le dice nada a quien lee
    la compuerta en rojo.
    """

    table: str
    column: str
    data_type: str


@dataclass(frozen=True)
class PersonalDataName:
    """Una entrada de la lista versionada de nombres de dato personal (BR7.2).

    Lleva su razon por la misma razon que la lista de exclusion: las dos viven
    juntas en el manifiesto para que una revision las lea a la vez, y una
    entrada sin razon es una que nadie sabe si puede quitar.
    """

    name: str
    reason: str


@dataclass(frozen=True)
class ColumnFailure:
    """Una columna que una tabla excluida del aislamiento no puede tener.

    Nombra **las tres cosas**: la tabla, la columna y por que --el tipo sin
    tope, o la entrada de la lista con la que coincidio--. Un fallo que solo
    dijera "la tabla no pasa" obligaria a abrir la migracion y comparar a mano.
    """

    table: str
    column: str
    reason: str


@dataclass(frozen=True)
class ForeignKey:
    """Lo que el catalogo vivo respondio sobre **una llave foranea** (U10, decision 4).

    Las columnas van en el orden de la llave, que es el que empareja cada columna
    de la tabla con la que apunta en la otra: `(tenant_id, case_id)` apunta a
    `(tenant_id, case_id)` y no a `(case_id, tenant_id)`.
    """

    constraint: str
    table: str
    referenced_table: str
    columns: tuple[str, ...]
    referenced_columns: tuple[str, ...]


@dataclass(frozen=True)
class ForeignKeyFailure:
    """Una llave foranea entre dos tablas aisladas que no lleva la aseguradora.

    Nombra la llave, las dos tablas y la razon: las comprobaciones de llave
    foranea no pasan por las politicas de fila, asi que sin la aseguradora en la
    llave una fila de una aseguradora puede apuntar a una fila de otra.
    """

    constraint: str
    table: str
    referenced_table: str
    reason: str


@dataclass(frozen=True)
class RlsReport:
    """El resultado de la asercion de aislamiento. No se guarda: se devuelve."""

    checked_tables: tuple[str, ...]
    excluded_tables: tuple[ExcludedTable, ...]
    failures: tuple[RlsFailure, ...]
    role: ConnectionRole | None = None
    #: Las columnas de las tablas excluidas que si se miraron, en forma
    #: `tabla.columna`. Viaja en el informe para que se vea **cuanto** se
    #: comprobo: una tabla excluida con cero columnas revisadas es una tabla que
    #: de hecho se salto, y sin este dato las dos cosas se ven igual en verde.
    checked_columns: tuple[str, ...] = ()
    column_failures: tuple[ColumnFailure, ...] = ()
    #: Las llaves foraneas entre tablas aisladas que se miraron, por su nombre,
    #: y las que no llevan la aseguradora (U10, decision 4). Viajan en el informe
    #: por la misma razon que las columnas: cero llaves miradas y cero fallos se
    #: ven igual en verde.
    checked_foreign_keys: tuple[str, ...] = ()
    foreign_key_failures: tuple[ForeignKeyFailure, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.failures and not self.column_failures and not self.foreign_key_failures

    def lines(self) -> tuple[str, ...]:
        """Una linea por fallo, nombrando la tabla y que le falta.

        Nunca dice solo "falta RLS": a las seis semanas eso cuesta una tarde.
        Las columnas de las tablas excluidas nombran ademas la columna y la
        razon, que es lo que paga la exclusion (BR7.2).
        """
        de_tabla = tuple(
            f"{fallo.table}: le falta {', '.join(fallo.missing)}" for fallo in self.failures
        )
        de_columna = tuple(
            f"{fallo.table}.{fallo.column}: {fallo.reason}" for fallo in self.column_failures
        )
        de_llave = tuple(
            f"{fallo.table} -> {fallo.referenced_table} ({fallo.constraint}): {fallo.reason}"
            for fallo in self.foreign_key_failures
        )
        return de_tabla + de_columna + de_llave


# --- Borrado de datos de visitante (C-11) -------------------------------------

#: Que es un dato de visitante. Vive escrito en un solo sitio a proposito: si
#: cada dueno lo decidiera por su cuenta, la retencion acotada dejaria de estarlo
#: sin que nadie lo notara.
VISITOR_DATA = "dato ligado al origen publico o a la clave de navegador de un visitante"

#: Con que se marca una tabla de datos de visitante **en la base**, en la misma
#: revision que la crea. La marca es lo que permite que una prueba pregunte al
#: catalogo cuales hay y las compare contra el registro de purgadores: comparar
#: dos listas escritas a mano no comprueba nada, porque quien olvida una olvida
#: las dos (BR3.6, C-11).
VISITOR_DATA_MARK = "visitor-data"


@dataclass(frozen=True)
class VisitorKeyRecord:
    """La fila de una clave de navegador, tal como quedo tras reconocerla."""

    tenant_id: TenantId
    visitor_key_hash: str
    origin: str
    created_at: datetime
    last_seen_at: datetime


@dataclass(frozen=True)
class IssuedCaseLink:
    """Lo que devuelve emitir un enlace. El token se entrega **una sola vez**."""

    link_id: str
    token: str
    tenant_id: TenantId
    case_id: str
    expires_at: datetime


@dataclass(frozen=True)
class CaseLinkGrant:
    """Lo que entrega un canje: acceso a **un** caso, por lo que le quede al enlace.

    Nunca vive mas que el enlace que lo origino: si al enlace le quedan N
    minutos, esto dura N minutos y no una hora completa (BR3.4).
    """

    tenant_id: TenantId
    case_id: str
    access: str
    expires_at: datetime
    redeemed_count: int


@dataclass(frozen=True)
class PurgeResult:
    """Lo que devuelve un purgador. `kept` es lo que se conserva a proposito."""

    name: str
    deleted: int
    kept: int = 0


@runtime_checkable
class VisitorDataPurger(Protocol):
    """Quien sabe borrar los datos de visitante de una tabla (C-11).

    El registro de purgadores es **explicito** en la raiz de composicion: una
    lista escrita a mano, nunca descubrimiento automatico. Un descubrimiento deja
    de encontrar lo que alguien nombro distinto (BR3.6).
    """

    @property
    def name(self) -> str: ...

    @property
    def tables(self) -> Sequence[str]: ...

    async def purge(self, *, older_than: datetime, dry_run: bool = False) -> PurgeResult: ...
