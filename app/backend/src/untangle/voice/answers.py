"""Lo que el ritmo de fondo calculo, llevado a una llamada en curso (2026-10-11).

En el chat, la respuesta de cobertura llega sola por el flujo del navegador. En
una llamada no llegaba nunca: quien la entregaba solo conocia el chat, y la
agente decia "dejame revisar tu poliza" y no volvia a hablar del tema.

Esto es la otra mitad del puerto `CaseNotifier` de la orquestacion: la llamada
viva de un caso se apunta aqui, y lo que el fondo tenga que decirle le llega
como una frase por decir. **Decide el ciclo cuando decirla** --no encima de la
persona--, no este modulo.

En memoria del proceso, como las colas del chat y por la misma razon: es la
llamada viva de este proceso, y una llamada que ya no esta no tiene a quien
decirle nada.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from untangle import observability
from untangle.base import Locale
from untangle.tenancy.models import TenantId


@dataclass(frozen=True)
class BackgroundAnswer:
    """Una respuesta del fondo, ya pasada por la guardia de salida."""

    text: str


Deliver = Callable[[BackgroundAnswer], None]

_OYENTES: dict[tuple[str, str], Deliver] = {}


def listen(tenant_id: TenantId, case_id: str, deliver: Deliver) -> None:
    """La llamada viva de este caso recibe desde ahora lo que el fondo le diga."""
    _OYENTES[(tenant_id, case_id)] = deliver


def stop(tenant_id: TenantId, case_id: str) -> None:
    _OYENTES.pop((tenant_id, case_id), None)


class _CallNotifier:
    """Cumple `orchestration.contracts.CaseNotifier` para un caso con llamada viva.

    Devuelve `False` cuando no hay ninguna: quien lo enchufa prueba entonces con el
    chat. Las citas y los botones no se dicen: la clausula queda en el caso.
    """

    async def notify(  # noqa: PLR0913 -- la firma del puerto CaseNotifier
        self,
        tenant_id: str,
        case_id: str,
        *,
        text: str,
        citations: tuple[object, ...] = (),
        suggestions: tuple[str, ...] = (),
        coverage_outcome: str | None = None,
        language: Locale | None = None,
    ) -> bool:
        del citations, suggestions, coverage_outcome, language
        entregar = _OYENTES.get((tenant_id, case_id))
        if entregar is None:
            return False
        entregar(BackgroundAnswer(text=text))
        observability.emit("voice.background_answer_queued", tenant_id=tenant_id, case_id=case_id)
        return True


#: El puerto que la raiz enchufa, delante del del chat.
CASE_NOTIFIER = _CallNotifier()

__all__ = ["CASE_NOTIFIER", "BackgroundAnswer", "Deliver", "listen", "stop"]
