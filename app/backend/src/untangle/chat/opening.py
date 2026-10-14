"""La apertura del chat: la divulgacion y lo que se ofrece (BR1.1, BR1.2, BR1.3).

**Compuerta dura BR1.1:** la divulgacion sale antes de cualquier texto del visitante.
No es cortesia: es la condicion para que lo que entre despues se pueda tratar como
dato de demostracion y no como una captura silenciosa. `compose` la arma y
`record` la registra; el manejador del turno no atiende un mensaje de una
conversacion que no tenga las dos hechas.

**Lo que se ofrece sale de la configuracion** (BR1.3). Reportar un siniestro,
resolver dudas de la poliza y pedir que una persona revise el caso van siempre;
cotizar solo si esa aseguradora lo tiene activo. Se compone de dos claves del
catalogo en vez de escribirse en una sola con un `if` dentro: una rama por
aseguradora en el texto es exactamente lo que la convencion 9 del equipo prohibe.

**El registro es de U10 y no se reescribe aqui.** `compliance.controls.disclosure`
ya guarda que la apertura salio --por que canal, en que idioma y con que clave-- y
su ausencia es lo que impide cerrar el caso (BR6.1 de U10). Esta unidad lo llama;
la mitad comprobable de BR1.2 ya existia.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from untangle.base import Locale
from untangle.compliance.controls import disclosure as u10_disclosure
from untangle.compliance.controls.models import DisclosureChannel
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.tenancy.models import TenantConfig, TenantId

#: Las tres claves de la apertura. Cada una se nombra literal en su unico
#: consumidor, que es lo que el chequeo de claves sin consumidor necesita (BR3.4
#: del catalogo) y la razon por la que no hay una tabla indexada aqui.
AGENT_NAME = CopyKey("insurer.agent.name")
DISCLOSURE = CopyKey("chat.opening.disclosure")
CAPABILITIES = CopyKey("chat.opening.capabilities")
CAPABILITIES_WITH_QUOTE = CopyKey("chat.opening.capabilities_with_quote")
GREETING = CopyKey("chat.greeting.hello")
#: Las opciones en una pregunta, para cuando todavia no hay caso (2026-10-07).
OPTIONS = CopyKey("chat.offer.options")
OPTIONS_WITH_QUOTE = CopyKey("chat.offer.options_with_quote")


class Surface(StrEnum):
    """Desde que pantalla se esta conversando (FD-U23-8 de U23).

    **Es un dato de la conversacion y no una rama por pantalla.** La vista de
    comparacion habla por estas mismas rutas y ya muestra **su** divulgacion --cada
    columna dice quien responde y que es una asistente de IA, y el aviso de
    demostracion va junto al cuadro de texto--; sin este dato, quien la abre leeria
    ademas tres aperturas del chat y tres ofertas de reportar un siniestro en una
    pantalla que compara coberturas.

    Lo que cambia con la superficie son dos cosas y ninguna es una rama de
    conducta: **que texto de apertura se publica** --ninguno, cuando la pantalla ya
    lo mostro-- y **que clave queda registrada** como la divulgacion que se dio.
    """

    CHAT = "chat"
    COMPARISON = "comparison"


#: La clave con la que queda registrada la divulgacion de cada superficie (BR1.4
#: de U23). Tabla cerrada: una superficie nueva anade su fila y su prueba.
#:
#: La de la comparacion nombra **el bloque** `comparison.disclosure.*` y no una de
#: sus frases, porque lo que se mostro son todas las de ese bloque; la del chat es una
#: sola frase y por eso su clave es la de esa frase. Una prueba comprueba que el
#: catalogo siga trayendo claves bajo ese prefijo: una clave registrada que ya no
#: existe en el catalogo es un registro que nombra algo que nadie puede leer.
COMPARISON_DISCLOSURE_BLOCK = "comparison.disclosure"

DISCLOSURE_KEY_OF: dict[Surface, str] = {
    Surface.CHAT: str(DISCLOSURE),
    Surface.COMPARISON: COMPARISON_DISCLOSURE_BLOCK,
}


class UndeclaredSurfaceError(RuntimeError):
    """Una superficie sin clave de divulgacion declarada.

    Falla en vez de caer en la del chat: registrar la divulgacion del chat cuando
    se mostro otra seria escribir que se dijo algo que no se dijo, y eso es
    exactamente lo que el registro existe para impedir.
    """


def disclosure_key_of(surface: Surface) -> str:
    """La clave que esa superficie registra."""
    clave = DISCLOSURE_KEY_OF.get(surface)
    if clave is None:
        msg = f"la superficie '{surface.value}' no declara su clave de divulgacion"
        raise UndeclaredSurfaceError(msg)
    return clave


@dataclass(frozen=True)
class Opening:
    """El primer mensaje, y la clave con la que quedara registrado.

    El texto y la clave viajan juntos a proposito: lo que se registra es **la
    clave** y nunca el texto (U10), asi que quien emite tiene que tener las dos a
    la vista y no recomponer la clave despues.
    """

    copy_key: CopyKey
    text: str


def compose(config: TenantConfig, *, language: Locale) -> Opening:
    """El primer mensaje de una aseguradora en un idioma (BR1.1, BR1.3).

    Es pura: no toca la base ni el reloj. Lo que decide que se ofrece es
    `config.quote_enabled`, que es dato de la aseguradora.
    """
    agente = config.agent_name or copy_api.t(AGENT_NAME, locale=language)
    divulgacion = copy_api.t(DISCLOSURE, locale=language, agent=agente, insurer=config.display_name)
    capacidades = copy_api.t(
        CAPABILITIES_WITH_QUOTE if config.quote_enabled else CAPABILITIES, locale=language
    )
    return Opening(copy_key=DISCLOSURE, text=f"{divulgacion} {capacidades}")


def options(config: TenantConfig, *, language: Locale) -> Opening:
    """Lo que la agente puede hacer, como una pregunta (2026-10-07).

    Es la frase de cuando todavia no hay caso: tras una duda general, o algo que no
    es ninguna de las opciones. Ofrece lo mismo que la apertura y nada mas, segun lo
    que esa aseguradora tiene activo.
    """
    if config.quote_enabled:
        return Opening(
            copy_key=OPTIONS_WITH_QUOTE, text=copy_api.t(OPTIONS_WITH_QUOTE, locale=language)
        )
    return Opening(copy_key=OPTIONS, text=copy_api.t(OPTIONS, locale=language))


def greeting_reply(config: TenantConfig, *, language: Locale) -> Opening:
    """Lo que se contesta a un primer mensaje que solo saluda (2026-10-07).

    Corto, y con las opciones en una pregunta: la apertura ya dijo quien habla y que
    sabe hacer, y repetirla entera era lo que Miguel vio largo.
    """
    opciones = options(config, language=language)
    return Opening(
        copy_key=GREETING, text=f"{copy_api.t(GREETING, locale=language)} {opciones.text}"
    )


async def record(
    *,
    tenant_id: TenantId,
    case_id: str,
    language: Locale,
    catalog_key: str,
    now: datetime,
) -> bool:
    """Deja constancia de que la divulgacion salio, por el registro de U10 (BR1.2).

    Devuelve si esta fue la que quedo. `False` no es un error: es la segunda vez
    que el mismo caso registra el chat, y la primera sigue en su sitio.

    **Recibe la clave y no la apertura compuesta.** Lo que se registra es la clave
    de lo que se mostro, y desde U23 eso no siempre es la apertura del chat: la
    vista de comparacion muestra la suya. Pedir el `Opening` obligaba a componer un
    texto que nadie iba a publicar para extraerle una clave.
    """
    return await u10_disclosure.record_disclosure(
        tenant_id=tenant_id,
        case_id=case_id,
        channel=DisclosureChannel.CHAT,
        language=language,
        catalog_key=catalog_key,
        disclosed_at=now,
    )


__all__ = [
    "AGENT_NAME",
    "CAPABILITIES",
    "CAPABILITIES_WITH_QUOTE",
    "COMPARISON_DISCLOSURE_BLOCK",
    "DISCLOSURE",
    "DISCLOSURE_KEY_OF",
    "GREETING",
    "OPTIONS",
    "OPTIONS_WITH_QUOTE",
    "Opening",
    "Surface",
    "UndeclaredSurfaceError",
    "compose",
    "disclosure_key_of",
    "greeting_reply",
    "options",
    "record",
]
