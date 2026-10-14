"""El token que ata un socket a **una** llamada (BR1.4, BR1.5).

**Por que no es el enlace firmado de caso de U2.** Los dos firman con HMAC y la
tentacion es compartir el camino, pero son cosas distintas:

- el enlace de caso (C-07) es un **portador en una URL**, con fila en la base,
  contador de canjes, revocacion y una hora de vida;
- este token no va en ninguna URL, no se guarda, no se canjea mas de una vez
  --un socket se abre una sola vez-- y vive lo que tarda el navegador en
  conectar.

Reutilizar el primero para el segundo traeria una fila y una revocacion que nadie
necesita y --peor-- un token de llamada que un dia alguien podria pegar en una
barra de direcciones, que es exactamente lo que BR1.4 existe para impedir.

**Quien es el visitante no lo dice este token.** Eso ya lo dice la galleta en el
apreton de manos del WebSocket, que es del mismo origen. Este token dice *que
llamada*, y nada mas.

**Y firma con su propia clave desde el 2026-10-03.** Hasta entonces reusaba la
del enlace de caso, con el argumento de que eran dos usos de un mismo secreto
del despliegue. El argumento no se sostiene: con una sola clave, rotar la del
enlace de caso tumba todos los sockets vivos, y un compromiso de esa clave
abarca las dos superficies en vez de una. Son dos secretos porque son dos radios
de dano.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from untangle.settings import VOICE_SOCKET_SIGNING_KEY_VAR
from untangle.tenancy.visitor_access import require_signing_key

#: Cuanto vive un token. Es lo que tarda un navegador en abrir el socket despues
#: de recibir la respuesta de `POST /voice/sessions`: una ida y vuelta, no una
#: sesion. Un minuto deja sitio a una red lenta y sigue siendo demasiado poco
#: para que el token sirva de nada si se filtra.
TOKEN_LIFETIME = timedelta(seconds=60)

#: Lo que el navegador debe mandar antes de que el servidor cierre el socket. Es
#: mas corto que la vida del token a proposito: un socket que se abre y calla es
#: un socket que hay que soltar, no uno que esperar.
AUTH_DEADLINE_SECONDS = 5.0

_SEPARADOR = "."

#: Cuerpo, vencimiento y firma.
_PARTES = 3


class TokenRejection(StrEnum):
    """Por que se rechazo un token. **Solo para la traza del servidor** (BR1.5).

    Hacia afuera los cuatro motivos se responden igual: distinguirlos le diria a
    quien esta probando tokens cual acerto a medias. Hacia adentro si se
    distinguen, porque un token alterado y uno vencido son incidentes distintos.
    """

    #: No llego cuadro de autenticacion, o llego sin token.
    MISSING = "missing"
    #: Bien firmado, pero su instante ya paso.
    EXPIRED = "expired"
    #: Bien firmado, pero para otra llamada.
    OTHER_CALL = "other_call"
    #: La firma no cuadra: alterado, o de otra clave.
    TAMPERED = "tampered"


@dataclass(frozen=True)
class TokenVerdict:
    """El resultado de verificar. `accepted` es lo unico que sale del servidor."""

    accepted: bool
    #: Nulo cuando se acepto. Nunca viaja al navegador.
    rejection: TokenRejection | None = None


ACEPTADO = TokenVerdict(accepted=True)


def _clave(signing_key: str | None) -> bytes:
    """La clave propia de la voz, con la **misma comprobacion** que el enlace de caso.

    Se comparte la comprobacion y no la clave. La comprobacion se **llama**, no se
    copia: dos sitios diciendo que mide una clave valida se separan. La clave es
    otra, y el mensaje de la que falta nombra la variable de la voz, porque es la
    que hay que definir.
    """
    return require_signing_key(signing_key, variable=VOICE_SOCKET_SIGNING_KEY_VAR)


def _firmar(cuerpo: str, clave: bytes) -> str:
    firma = hmac.new(clave, cuerpo.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(firma).decode("ascii").rstrip("=")


def issue(call_id: str, *, signing_key: str | None, now: datetime) -> str:
    """El token de una llamada, valido `TOKEN_LIFETIME` a partir de `now`.

    No se guarda en ninguna parte: lo que lo hace valido es la firma, y lo que lo
    hace caducar es su propio instante. El reloj entra por argumento, como en el
    resto del proyecto.
    """
    clave = _clave(signing_key)
    vence = int((now + TOKEN_LIFETIME).timestamp())
    cuerpo = f"{call_id}{_SEPARADOR}{vence}"
    return f"{cuerpo}{_SEPARADOR}{_firmar(cuerpo, clave)}"


def _motivo(
    token: str | None, *, call_id: str, clave: bytes, now: datetime
) -> TokenRejection | None:
    """Por que se rechaza este token, o `None` si no se rechaza.

    El orden importa y no es casual: primero la firma y solo despues el
    contenido. Al reves, un token alterado con un vencimiento futuro pasaria la
    comprobacion de tiempo y diria por el camino que tomo cuanto se acerco.
    """
    if not token:
        return TokenRejection.MISSING

    partes = token.split(_SEPARADOR)
    if len(partes) != _PARTES:
        return TokenRejection.TAMPERED

    token_call_id, vence_crudo, firma = partes
    cuerpo = f"{token_call_id}{_SEPARADOR}{vence_crudo}"
    # Las dos comprobaciones van juntas porque las dos dicen lo mismo: el token no
    # lo emitio esta clave. Un vencimiento ilegible con firma valida no se puede
    # dar sin la clave, pero un `int()` que revienta convertiria un caso
    # imposible en un 500.
    if not hmac.compare_digest(firma, _firmar(cuerpo, clave)) or not vence_crudo.isdigit():
        return TokenRejection.TAMPERED

    if not hmac.compare_digest(token_call_id, call_id):
        return TokenRejection.OTHER_CALL

    if now.timestamp() > int(vence_crudo):
        return TokenRejection.EXPIRED

    return None


def verify(
    token: str | None, *, call_id: str, signing_key: str | None, now: datetime
) -> TokenVerdict:
    """Si este token abre **esta** llamada ahora.

    Lo unico que sale del servidor es `accepted` (BR1.5). El motivo viaja aparte,
    para la traza: distinguir los cuatro rechazos en la respuesta le diria a quien
    esta probando tokens cual acerto a medias.
    """
    motivo = _motivo(token, call_id=call_id, clave=_clave(signing_key), now=now)
    if motivo is None:
        return ACEPTADO
    return TokenVerdict(accepted=False, rejection=motivo)


__all__ = [
    "ACEPTADO",
    "AUTH_DEADLINE_SECONDS",
    "TOKEN_LIFETIME",
    "TokenRejection",
    "TokenVerdict",
    "issue",
    "verify",
]
