"""La apertura de la llamada: la divulgacion y lo que se ofrece (BR2.1 a BR2.4).

Misma forma que `chat/opening.py`, y a proposito: lo que cambia entre los dos
canales es el texto, no la regla. **Compuerta dura BR2.1:** la divulgacion sale
antes de cualquier pregunta, y mientras no este emitida y registrada el manejador
del turno no atiende nada.

**Dos diferencias con el chat, y las dos vienen del criterio.**

La primera es el texto: la apertura hablada dice ademas que la llamada queda
transcrita, y termina preguntando si hay heridos. Por eso son claves propias y no
las de `chat.opening.*`: un mismo texto para los dos canales obligaria a que uno
de los dos dijera algo que su criterio no aprobo.

La segunda es **cuando se registra**: al terminar de emitirse, no al empezar. En
el chat el mensaje aparece entero o no aparece; una apertura hablada se puede
cortar a la mitad, y AC1.24.4 necesita distinguir las dos cosas. Una apertura sin
hora de fin es una apertura que hay que repetir entera (BR4.5).

**El registro es de U10 y no se reescribe aqui**, igual que en el chat.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from untangle.base import Locale
from untangle.compliance.controls import disclosure as u10_disclosure
from untangle.compliance.controls.models import DisclosureChannel
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.tenancy.models import TenantConfig, TenantId

#: Las claves de la apertura hablada. Cada una se nombra literal en su unico
#: consumidor, que es lo que el chequeo de claves sin consumidor necesita.
AGENT_NAME = CopyKey("insurer.agent.name")
DISCLOSURE = CopyKey("voice.opening.disclosure")
FIRST_QUESTION = CopyKey("voice.opening.first_question")


@dataclass(frozen=True)
class Opening:
    """Lo primero que se oye, y la clave con la que quedara registrado.

    El texto y la clave viajan juntos porque lo que se registra es **la clave** y
    nunca el texto (U10): quien emite tiene que tener las dos a la vista y no
    recomponer la clave despues.
    """

    copy_key: CopyKey
    text: str


def compose(config: TenantConfig, *, language: Locale, ask_how_to_help: bool = True) -> Opening:
    """La apertura de una aseguradora en un idioma (BR2.2).

    Es pura: no toca la base ni el reloj.

    `ask_how_to_help` es falso al retomar un caso cortado (2026-10-11): la divulgacion
    va entera, pero la pregunta de "en que te puedo ayudar" se quita, porque justo
    despues viene la oferta de seguir con el caso y dos preguntas seguidas dejan a la
    persona sin saber a cual contestar. Lo que se registra es la divulgacion, no la
    pregunta, asi que BR2.1 sigue entera.

    **La voz no ofrece cotizar, aunque la aseguradora lo tenga activo.** `quote_enabled`
    dice que *la aseguradora* cotiza, no que lo haga por este canal: la solicitud se
    captura en el chat --`chat.case_opening` es quien abre un caso de tipo
    `quote_request`-- y la voz no abre ninguno. Ofrecerlo aqui seria prometer una
    capacidad que este canal no tiene, que es lo que P7 prohibe, y la prueba de abajo
    existe para que no vuelva.

    El dia que la voz capture solicitudes, esto cambia con su prueba; mientras tanto, la
    diferencia entre "esta aseguradora cotiza" y "este canal cotiza" es real y se nota
    aqui.
    """
    agente = config.agent_name or copy_api.t(AGENT_NAME, locale=language)
    # Sin la lista de capacidades ni la oferta de pasar a una persona: Miguel la
    # quito el 2026-10-07 porque alargaba la apertura (y la sintesis se paga por
    # caracter) sin decir nada que la persona necesite antes de la primera pregunta.
    partes = [copy_api.t(DISCLOSURE, locale=language, agent=agente, insurer=config.display_name)]
    if ask_how_to_help:
        partes.append(copy_api.t(FIRST_QUESTION, locale=language))
    return Opening(copy_key=DISCLOSURE, text=" ".join(partes))


def first_question(*, language: Locale) -> str:
    """La pregunta con que se cierra la apertura: "¿en que te puedo ayudar?"."""
    return copy_api.t(FIRST_QUESTION, locale=language)


async def record(
    *, tenant_id: TenantId, case_id: str, language: Locale, opening: Opening, finished_at: datetime
) -> bool:
    """Deja constancia de que la apertura **termino** de sonar (BR2.3).

    `finished_at` y no `started_at`: una apertura que no llego al final no esta
    dicha, y lo que distingue las dos es que esta llamada no ocurrio. Devuelve si
    esta fue la que quedo; `False` no es un error, es la segunda llamada del
    mismo caso, y la primera sigue en su sitio (BR2.4).
    """
    return await u10_disclosure.record_disclosure(
        tenant_id=tenant_id,
        case_id=case_id,
        channel=DisclosureChannel.VOICE,
        language=language,
        catalog_key=opening.copy_key,
        disclosed_at=finished_at,
    )


__all__ = [
    "AGENT_NAME",
    "DISCLOSURE",
    "FIRST_QUESTION",
    "Opening",
    "compose",
    "first_question",
    "record",
]
