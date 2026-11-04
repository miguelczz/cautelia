"""Los puertos del ajustador: lo que enchufa la raiz de composicion.

El paquete no importa un SDK ni un adaptador: recibe la decision y la investigacion como puertos
(`TextGenerator`, `WebResearcher`), la forma de calcular un embedding y quien registra el cierre
del caso. Las pruebas enchufan dobles; el servidor, los de verdad.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from untangle.case_record.crypto import Cipher
from untangle.inbox.actions import InboxAction
from untangle.providers.ports import TextGenerator, Vector, WebResearcher
from untangle.tenancy.models import TenantId


@dataclass(frozen=True)
class DecisionToRecord:
    """Lo que se le pide al registro del cierre: la decision de la corrida, tal como quedo guardada.

    El comentario es el titular que ya esta en la corrida: la huella del recibo lo incluye, y un
    texto generado otra vez en un reintento daria `RecycledKeyError` (A5). La llave es estable por
    caso, asi que dos registros del mismo cierre son el mismo recibo.
    """

    tenant_id: TenantId
    case_id: str
    action: InboxAction
    comment: str
    idempotency_key: str


RecordDecision = Callable[[DecisionToRecord], Awaitable[None]]
Embed = Callable[[Sequence[str]], Awaitable[list[Vector]]]


@dataclass(frozen=True)
class AdjusterPorts:
    generate: TextGenerator
    research: WebResearcher
    embed: Embed
    embedding_model: str
    #: El modelo de la decision, tal como se guarda en la corrida.
    model: str
    cipher: Cipher
    now: Callable[[], datetime]
    record_decision: RecordDecision
