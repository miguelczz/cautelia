"""El registro de la divulgacion cuando sale la apertura (BR4.1, BR4.2).

Cuando la apertura con la divulgacion de inteligencia artificial sale, se
registra por que canal, en que idioma, con que clave del catalogo y cuando
(FR7.1). Una por caso y canal: registrarla dos veces --la apertura se reintenta,
el nodo se reejecuta al reanudar-- no crea otra fila, y la escritura es
idempotente sin leer antes (BR4.2). Un caso de voz retomado por chat lleva dos,
una por canal.

Sin esta fila, la revision completa marca `disclosure_missing` y el caso no se
cierra (BR6.1): la divulgacion no se da por dicha porque la apertura exista en el
catalogo, sino porque quedo registrada.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from untangle.base import Locale
from untangle.compliance.controls import repository
from untangle.compliance.controls.models import DisclosureChannel, DisclosureRecord
from untangle.tenancy.models import TenantId


async def record_disclosure(  # noqa: PLR0913 -- seis datos de la fila de BR4.1, ninguno derivable de otro, todos por nombre
    *,
    tenant_id: TenantId,
    case_id: str,
    channel: DisclosureChannel,
    language: Locale,
    catalog_key: str,
    disclosed_at: datetime,
) -> bool:
    """Registra que salio la apertura, si ese caso no la tenia en ese canal (BR4.1).

    Devuelve si esta fue la que quedo. `False` no es un error: es la segunda vez
    que el mismo caso registra el mismo canal, y la primera sigue en su sitio.
    """
    registro = DisclosureRecord(
        disclosure_id=f"disclosure-{uuid.uuid4().hex}",
        tenant_id=tenant_id,
        case_id=case_id,
        channel=channel,
        language=language,
        catalog_key=catalog_key,
        disclosed_at=disclosed_at,
    )
    return await repository.record_disclosure(registro)
