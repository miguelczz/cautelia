"""Cuando nace el caso de una llamada (BR2.1, BR2.3).

**En voz el caso nace antes que la primera palabra de la persona**, y esa es la
diferencia con el chat. La divulgacion se registra contra un caso (BR2.3), y la
divulgacion va antes de cualquier pregunta: si el caso naciera con el primer
turno, como en el chat, la apertura no tendria donde quedar registrada y la
compuerta BR2.1 no podria comprobarse.

**Por eso el tipo es siempre siniestro, y no se adivina.** El chat lee el primer
mensaje con el reconocedor determinista de U12 para decidir entre siniestro y
consulta de cobertura. Aqui no hay primer mensaje que leer: la agente habla
primero. Se abre un siniestro --el camino de siete campos-- y, si lo que la
persona dice resulta ser una pregunta de cobertura, el desvio dentro del
siniestro que U12 ya construyo la atiende sin abrir otro caso. Inventar el tipo a
partir de nada seria adivinar; el desvio ya existe y no adivina.

El origen es `PUBLIC_VOICE_CONSOLE`, que es lo que decide que borra el reinicio
nocturno (BR4.6 de U4).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from untangle.base import Locale
from untangle.case_record.models import Channel, Origin
from untangle.orchestration.nodes.intake import identity
from untangle.tenancy.models import TenantId


def new_case_id() -> str:
    """La llave del caso: opaca y sin orden, igual que en el chat.

    Un identificador correlativo deja ver cuantos casos lleva la demostracion a
    cualquiera que reciba uno.
    """
    return f"case-{uuid.uuid4().hex[:16]}"


async def open_for_call(
    tenant_id: TenantId,
    *,
    language: Locale,
    origin: Origin = Origin.PUBLIC_VOICE_CONSOLE,
    now: datetime,
    intent: identity.ReportIntent = identity.ReportIntent.CLAIM,
) -> str:
    """Abre el caso de esta llamada y devuelve su identificador.

    Nace como reporte, que es a lo que mas se llama; si lo primero que la persona
    dice es una duda de su poliza, la llamada abre otro con esa intencion.

    No ata el caso a la llamada: quien llama lo hace con `session.attach_case`
    antes de seguir, porque un caso abierto que ninguna llamada reclama es un
    caso que la llamada siguiente vuelve a abrir.
    """
    vista = await identity.open_case(
        tenant_id,
        identity.OpeningRequest(
            case_id=new_case_id(),
            intent=intent,
            channel=Channel.VOICE,
            origin=origin,
            language=language,
        ),
        now=now,
    )
    return vista.case_id


__all__ = ["new_case_id", "open_for_call"]
