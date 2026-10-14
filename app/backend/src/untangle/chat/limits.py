"""Los cinco controles de entrada del chat publico (BR3.1, BR3.2).

**La decision es pura.** `decide` recibe la configuracion de la aseguradora, lo que
los contadores ya dicen y el reloj como argumento; no abre sesion, no llama a nadie y
no mira el reloj del proceso. Eso es lo que la hace medible contra PERF-U13.1 --un
milisegundo para los cinco sumados-- sin depender de la maquina, y lo que deja que
las pruebas cubran los bordes de cada limite sin base de datos.

**El orden importa y no es alfabetico.** Se comprueba primero lo que no cuesta nada
--el tamano del mensaje y el intervalo desde el anterior-- y despues los tres
contadores. Un mensaje de cien mil caracteres no tiene por que costar tres consultas
antes de rechazarse.

**Lo que este modulo no hace:** no llama al proveedor, no compone texto y no decide
que frase se dice. Devuelve **cual** limite se alcanzo; la frase sale del catalogo por
su clave, en el punto unico de salida, como todo lo que lee una persona.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from untangle.tenancy.models import ChatConfig


class LimitKind(StrEnum):
    """Cual de los cinco controles rechazo el mensaje. Conjunto cerrado.

    Viaja al evento de la traza (OBS-U13.2) y decide la clave del catalogo con
    la que se responde. **El texto del mensaje rechazado no viaja con el**: para
    entender un rechazo basta saber cual limite fue.
    """

    #: Mensajes de esta conversacion.
    SESSION = "session"
    #: Mensajes de este origen hoy.
    ORIGIN = "origin"
    #: Mensajes de todo el sitio hoy.
    SITE_DAY = "site_day"
    #: Dos mensajes mas seguidos que el intervalo minimo.
    RATE = "rate"
    #: Un mensaje mas largo que el maximo.
    SIZE = "size"


#: La frase de cada limite, **junto a la definicion del enum** y no repartida.
#:
#: Es donde el propio catalogo dice que tiene que vivir: "la correspondencia entre
#: cada motivo y su clave vive en un solo archivo del codigo, junto a la definicion
#: del enum". Hasta esta tanda la ruta componia la clave con una f-string
#: --`f"chat.limit.{limite.value}"`-- y **ninguna de las cinco existia**: quien
#: llegaba a un limite recibia una clave que su catalogo no sabe resolver, asi que
#: no veia nada. Una clave compuesta tampoco aparece en el chequeo de claves sin
#: consumidor, que es lo que habria avisado.
#:
#: Las dos primeras reusan la frase que ya existe y esta escrita para el chat. La
#: del sitio no se reusa: la de `spend.quota.rate_limited_site` habla de llamadas
#: y es de la voz.
LIMIT_COPY_KEYS: Mapping[LimitKind, str] = {
    LimitKind.SESSION: "spend.quota.rate_limited_session",
    LimitKind.ORIGIN: "spend.quota.rate_limited_daily",
    LimitKind.SITE_DAY: "chat.limit.site_day",
    LimitKind.RATE: "chat.limit.rate",
    LimitKind.SIZE: "chat.limit.size",
}


@dataclass(frozen=True)
class Counters:
    """Lo que los contadores ya dicen cuando llega un mensaje.

    Los tres son **lo ya contado**, sin incluir el mensaje que acaba de llegar:
    quien decide compara contra el limite y el que suma es otro. Mezclar las dos
    cosas es como se acaba rechazando el mensaje que justamente cabia.
    """

    session_messages: int
    origin_messages_today: int
    site_messages_today: int
    #: Cuando llego el anterior de esta conversacion, o `None` si es el primero.
    last_message_at: datetime | None = None


@dataclass(frozen=True)
class LimitDecision:
    """Si el mensaje pasa, y si no, cual limite lo paro y cuando se puede seguir.

    `retry_after` es `None` cuando la espera no se puede prometer con honestidad:
    el limite de sesion no se reinicia solo --la conversacion ya gasto lo suyo--
    y decir una hora seria inventarla. Los que si se reinician la traen.
    """

    allowed: bool
    kind: LimitKind | None = None
    retry_after: datetime | None = None

    @property
    def rejected(self) -> bool:
        return not self.allowed


def _siguiente_dia(now: datetime) -> datetime:
    """El inicio del dia siguiente en UTC: cuando los contadores diarios vuelven a cero."""
    inicio = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return inicio + timedelta(days=1)


def decide(
    *,
    config: ChatConfig,
    counters: Counters,
    message_characters: int,
    now: datetime,
) -> LimitDecision:
    """Si este mensaje se atiende, y si no, por cual de los cinco limites (BR3.1, BR3.2).

    Pura: el reloj entra por argumento y no se lee de ningun sitio. Quien la llama
    ya tiene los contadores; sumarlos es de despues y solo si esto deja pasar.
    """
    if message_characters > config.max_message_characters:
        # Sin `retry_after`: esperar no hace mas corto el mensaje.
        return LimitDecision(allowed=False, kind=LimitKind.SIZE)

    anterior = counters.last_message_at
    if anterior is not None:
        minimo = timedelta(seconds=config.min_seconds_between_messages)
        if now - anterior < minimo:
            return LimitDecision(allowed=False, kind=LimitKind.RATE, retry_after=anterior + minimo)

    if counters.session_messages >= config.messages_per_session:
        return LimitDecision(allowed=False, kind=LimitKind.SESSION)

    manana = _siguiente_dia(now)
    if counters.origin_messages_today >= config.messages_per_origin_per_day:
        return LimitDecision(allowed=False, kind=LimitKind.ORIGIN, retry_after=manana)

    if counters.site_messages_today >= config.messages_per_site_per_day:
        return LimitDecision(allowed=False, kind=LimitKind.SITE_DAY, retry_after=manana)

    return LimitDecision(allowed=True)


__all__ = ["LIMIT_COPY_KEYS", "Counters", "LimitDecision", "LimitKind", "decide"]
