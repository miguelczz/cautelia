"""El aviso de que un caso acaba de derivarse, por un puerto que enchufa la raiz de composicion.

Quien atiende un caso derivado --hoy, el ajustador de IA-- esta por encima de este paquete en el
contrato de capas, asi que no se importa: se le deja un enchufe, con el mismo patron que
`install_resume_handler` de la bandeja. Sin nadie enchufado, derivar no dispara nada y el
producto se comporta como antes.

**Avisar no puede deshacer la derivacion.** El caso ya esta en `derived` cuando se avisa; si el
oyente falla, se deja rastro y el reintento al leer el caso lo recoge. El oyente tampoco espera
al trabajo: agenda y devuelve, porque quien deriva esta en medio de un turno.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from untangle import observability
from untangle.tenancy.models import TenantId

DerivedListener = Callable[[TenantId, str], Awaitable[None]]

_OYENTE: DerivedListener | None = None


def install_derived_listener(listener: DerivedListener | None) -> None:
    """La raiz de composicion enchufa quien atiende los casos derivados; `None` lo quita."""
    global _OYENTE
    _OYENTE = listener


async def notify_derived(tenant_id: TenantId, case_id: str) -> None:
    """Avisa que el caso se derivo. Un fallo del oyente se registra y no se propaga."""
    if _OYENTE is None:
        return
    try:
        await _OYENTE(tenant_id, case_id)
    except Exception as error:  # noqa: BLE001 -- el caso ya esta derivado; el reintento al leerlo lo recoge
        observability.emit(
            "orchestration.derived_notice_failed",
            tenant_id=tenant_id,
            case_id=case_id,
            error=type(error).__name__,
        )
