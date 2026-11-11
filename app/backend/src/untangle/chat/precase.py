"""Lo hablado en el chat antes de que exista un caso, guardado por conversacion.

Un saludo, una duda general o «tengo una duda de mi poliza» no abren caso, y sin caso no hay
transcripcion donde guardarlos. Hasta el 2026-11-11 vivian solo en la memoria del proceso
(`delivery._HISTORIA_SIN_CASO`): al recargar la pantalla, reiniciar el servidor o caer en otra
instancia, la persona volvia a una ventana sin lo que habia hablado. Aqui se guardan, y la
pantalla (`history.load`) y el contexto que ve el modelo (`delivery`) los leen de aqui.

**Se guarda el texto tal como se escribio, sin tapar** (decision de Miguel, 2026-10-30: la
conversacion de la propia persona se guarda sin redactar). La redaccion sigue donde las
compuertas la miden: logs, trazas, exportaciones y el contexto que se le da al modelo.

**Tope de `MAX_MESSAGES` mensajes por conversacion.** Pasado el tope los siguientes no se guardan
y no es un error: es una demostracion publica, y una conversacion sin caso que llega a cuarenta
mensajes ya es un uso que el limite de sesion del chat se encarga de acotar.

**El orden es `seq`**, asignado por la propia sentencia de insercion; dos turnos en vuelo de una
misma conversacion que chocaran en el mismo numero dejan pasar uno, sin error.

Toda consulta sale del punto unico de sesion, con la aseguradora fijada.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from untangle.base import Locale
from untangle.tenancy import session as db
from untangle.tenancy.models import TenantId

#: Cuantos mensajes se guardan por conversacion antes de que abra caso.
MAX_MESSAGES = 40

PrecaseSpeaker = Literal["person", "agent"]

#: Una insercion que numera sola y respeta el tope: no inserta si ya hay `:tope` mensajes, y si
#: otro turno tomo el mismo numero en el mismo instante, ese choque no se trata como error.
_INSERTAR = """
    INSERT INTO chat_session_message
        (message_id, tenant_id, chat_session_id, seq, speaker, text, language, created_at)
    SELECT :message_id, :tenant_id, :chat_session_id, n.siguiente, :speaker, :text,
           :language, :created_at
    FROM (
        SELECT COALESCE(max(seq), 0) + 1 AS siguiente, count(*) AS total
        FROM chat_session_message
        WHERE tenant_id = :tenant_id AND chat_session_id = :chat_session_id
    ) AS n
    WHERE n.total < :tope
    ON CONFLICT DO NOTHING
"""

_LEER = """
    SELECT message_id, speaker, text, language, created_at, seq
    FROM chat_session_message
    WHERE tenant_id = :tenant_id AND chat_session_id = :chat_session_id
    ORDER BY seq
"""

#: Los ultimos `:cantidad`, ya en orden: se ordena de mas nuevo a mas viejo para acotar y se
#: reordena por fuera de la subconsulta.
_LEER_ULTIMOS = """
    SELECT message_id, speaker, text, language, created_at, seq FROM (
        SELECT message_id, speaker, text, language, created_at, seq
        FROM chat_session_message
        WHERE tenant_id = :tenant_id AND chat_session_id = :chat_session_id
        ORDER BY seq DESC
        LIMIT :cantidad
    ) AS recientes
    ORDER BY seq
"""


@dataclass(frozen=True)
class PrecaseMessage:
    """Un mensaje de antes del caso, tal como se escribio."""

    message_id: str
    speaker: PrecaseSpeaker
    text: str
    language: Locale
    created_at: datetime


def _de_fila(fila: Mapping[str, Any]) -> PrecaseMessage:
    return PrecaseMessage(
        message_id=str(fila["message_id"]),
        speaker=fila["speaker"],
        text=str(fila["text"]),
        language=fila["language"],
        created_at=fila["created_at"],
    )


@dataclass(frozen=True)
class Exchange:
    """Lo que dijo la persona y lo que contesto la agente en un turno, tal como se dijo."""

    person_text: str
    agent_text: str
    language: Locale


async def append_precase_exchange(
    *, tenant_id: TenantId, chat_session_id: str, exchange: Exchange, now: datetime
) -> None:
    """Guarda lo que dijo la persona y lo que contesto la agente, en ese orden.

    Los dos van en la misma transaccion. Pasado el tope no se guarda nada y no se levanta nada.
    """
    async with db.session_for(tenant_id) as sesion:
        for hablante, texto in (("person", exchange.person_text), ("agent", exchange.agent_text)):
            await db.execute_sql(
                sesion,
                _INSERTAR,
                message_id=uuid.uuid4().hex,
                tenant_id=tenant_id,
                chat_session_id=chat_session_id,
                speaker=hablante,
                text=texto,
                language=exchange.language,
                created_at=now,
                tope=MAX_MESSAGES,
            )


async def load_precase_messages(
    *, tenant_id: TenantId, chat_session_id: str, last: int | None = None
) -> tuple[PrecaseMessage, ...]:
    """Los mensajes de antes del caso de esa conversacion, por `seq`.

    Con `last`, solo los ultimos `last`, igualmente en orden.
    """
    async with db.session_for(tenant_id) as sesion:
        if last is None:
            filas = await db.fetch_all(
                sesion, _LEER, tenant_id=tenant_id, chat_session_id=chat_session_id
            )
        else:
            filas = await db.fetch_all(
                sesion,
                _LEER_ULTIMOS,
                tenant_id=tenant_id,
                chat_session_id=chat_session_id,
                cantidad=last,
            )
    return tuple(_de_fila(fila) for fila in filas)


__all__ = [
    "MAX_MESSAGES",
    "Exchange",
    "PrecaseMessage",
    "PrecaseSpeaker",
    "append_precase_exchange",
    "load_precase_messages",
]
