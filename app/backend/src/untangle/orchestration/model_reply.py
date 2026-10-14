"""Lo unico que se comprueba de lo que el modelo contesta (2026-10-12).

Hasta el 2026-10-12 el modelo reescribia una frase del catalogo y una docena de
comprobaciones --cifras, preguntas, la palabra «cobertura», si repetia el arranque, si
decia «anotado»-- descartaban entre una de cada diez y una de cada tres respuestas. Desde
que la misma llamada que entiende tambien contesta
(`understanding.UnderstandingResponse.reply`) esas reglas viven en la instruccion
`conversation`, donde el modelo las puede cumplir, y aqui quedan solo las dos que cuidan a
la persona y **no dependen de que el modelo las entienda**: sin enlaces ni correos, y sin el
nombre de la agente si nadie lo pregunto. Mas lo que hace falta para que haya un texto que
mandar: que no este vacio ni se alargue de mas.

Desde el 2026-10-13 hay una mas, de la misma clase: que no diga que el reporte quedo hecho ni que
un ajustador lo revisa mientras la captura sigue abierta (`outcome_claim`, aplicada por el
turno). La instruccion ya lo pedia y una llamada real la incumplio: lo que le pasa a un reporte
al terminar lo sabe el codigo y no el modelo, asi que no se deja a su criterio.

Este modulo no llama a ningun modelo. Lo que sale de verdad --`reply` o la frase del
catalogo-- lo decide el turno (`turn._texto_del_turno`), y la guardia de salida corre
despues sobre el resultado, como sobre cualquier texto.
"""

from __future__ import annotations

import re
from enum import StrEnum

from untangle import observability
from untangle.base import Locale
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import TenantId


class FallbackReason(StrEnum):
    """Por que salio la frase del codigo y no lo que escribio el modelo. Lista cerrada.

    Es el valor de `reason` en `chat.reply_fallback`: una caida a la frase fija se veria igual
    que un chat que nunca contesto el modelo, y cuantas veces cae cada motivo es lo que dice
    si la instruccion se esta cumpliendo.
    """

    #: El turno es un hito --derivacion, cierre del reporte, lectura, emergencia, error,
    #: limite, caso ya decidido--: su frase la dice el codigo, siempre.
    MILESTONE = "milestone"
    #: No hubo modelo: sin clave, fallo, tardo, o la voz resolvio el turno por reglas.
    NO_MODEL = "no_model"
    #: El mensaje que abrio el caso --el primero, o el que cambio de tema--: se entendio sin
    #: ese caso, asi que la respuesta se escribio sin saber que datos faltan en el.
    OPENING_TURN = "opening_turn"
    #: El codigo rechazo algun dato que el modelo anoto: su respuesta contaba con el.
    ITEMS_REJECTED = "items_rejected"
    #: La respuesta no vale (`usable_reply`).
    INVALID_REPLY = "invalid_reply"
    #: La respuesta esta escrita en el otro idioma: el modelo siguio a la persona, pero el
    #: idioma de la conversacion no cambio y lo demas --frases fijas, reconocedor, voz--
    #: seguiria en el primero.
    WRONG_LANGUAGE = "wrong_language"
    #: La respuesta afirma que el reporte quedo hecho, o que un ajustador lo revisa, y la
    #: captura sigue abierta (`outcome_claim`). Lo que le pasa a un reporte al terminar lo dice
    #: solo el codigo, cuando pasa; en su lugar sale `intake.unfinished`, que dice que falta.
    REPORT_NOT_DONE = "report_not_done"
    #: La guardia de salida sustituyo lo que escribio el modelo.
    GUARD = "guard"
    #: En una llamada, el redactor de datos personales cambia algo de la respuesta.
    REDACTED_VOICE = "redacted_voice"


def record_outcome(tenant_id: TenantId, channel: str, reason: FallbackReason | None) -> None:
    """Un evento por turno que dice que texto salio: `chat.reply_model` si fue el del modelo,
    `chat.reply_fallback` con su motivo si no. Sin texto: no lleva nada de lo que se dijo."""
    if reason is None:
        observability.emit("chat.reply_model", tenant_id=tenant_id, channel=channel)
        return
    observability.emit(
        "chat.reply_fallback", tenant_id=tenant_id, channel=channel, reason=reason.value
    )


#: Mas que esto no es una respuesta de chat: tres frases caben de sobra.
MAX_REPLY_CHARS = 600

#: Lo que nunca sale de una respuesta del modelo: un enlace o un correo. Los de verdad
#: --el caso, la bandeja-- los pone el codigo; uno escrito por el modelo es inventado.
_ENLACE_O_CORREO = re.compile(r"https?://|www\.|@\w", re.IGNORECASE)


def agent_name_of(tenant_id: TenantId, language: Locale) -> str:
    """Como se llama la agente de esta aseguradora: su nombre propio, o el del catalogo.

    Un solo sitio, porque lo usan dos: la etiqueta `tu_nombre` que ve el modelo y la
    comprobacion de `usable_reply` que descarta una respuesta que lo dice sin que toque.
    """
    propio = tenancy_config.require(tenant_id).agent_name
    return propio or copy_api.t(CopyKey("insurer.agent.name"), locale=language)


def has_link_or_email(text: str) -> bool:
    """Si el texto trae un enlace o un correo."""
    return _ENLACE_O_CORREO.search(text) is not None


def says_agent_name(reply: str, *, base: str, agent_name: str | None) -> bool:
    """Si la respuesta dice el nombre de la agente y la frase base no lo trae.

    El nombre solo lo dice quien lo pregunta: una respuesta que se presenta en mitad de la
    conversacion («Hello, I'm Valeria...», visto el 2026-10-11) suena a otra conversacion.
    `None` si quien arma la peticion no lo sabe, y entonces no se comprueba.
    """
    if not agent_name:
        return False
    nombre = re.compile(rf"\b{re.escape(agent_name)}\b", re.IGNORECASE)
    return nombre.search(reply) is not None and nombre.search(base) is None


def usable_reply(reply: str | None, *, base: str, agent_name: str | None) -> str | None:
    """La respuesta del modelo lista para mandar, o `None` si sale la frase base.

    `None` cuando esta vacia, pasa de `MAX_REPLY_CHARS`, trae un enlace o un correo, o dice
    el nombre de la agente sin que la frase base lo traiga. Nada mas: el estilo no se vigila
    con reglas sobre el texto, se mide con las evaluaciones.
    """
    texto = (reply or "").strip()
    if not texto or len(texto) > MAX_REPLY_CHARS or has_link_or_email(texto):
        return None
    if says_agent_name(texto, base=base, agent_name=agent_name):
        return None
    return texto


__all__ = [
    "MAX_REPLY_CHARS",
    "FallbackReason",
    "agent_name_of",
    "has_link_or_email",
    "record_outcome",
    "says_agent_name",
    "usable_reply",
]
