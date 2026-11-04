"""Por que un intento del ajustador no llego a decidir: un vocabulario cerrado.

Es lo que se guarda en `adjuster_run.error_kind` cuando la corrida queda fallida, y lo unico que
dice el rastro sobre un fallo: el motivo, nunca el texto que el modelo escribio. Un fallo nunca
inventa una decision (A12); el caso sigue en `derived` y el reintento lo vuelve a intentar.
"""

from __future__ import annotations

from enum import StrEnum

from untangle.base import ProviderErrorKind


class ErrorKind(StrEnum):
    """Los motivos de un intento fallido."""

    #: La accion del modelo no es de las que ofrece ese tipo de aseguradora (A3).
    ACTION_NOT_ALLOWED = "action_not_allowed"
    #: Una aprobacion o un rechazo sin una sola cita verificada (A4, P2).
    NO_VERIFIED_CITATION = "no_verified_citation"
    #: La guardia de salida intervino en el texto de la decision: no se muestra la frase generica.
    GUARD_BLOCKED = "guard_blocked"
    #: El texto del modelo no esta en el idioma del caso.
    WRONG_LANGUAGE = "wrong_language"
    #: Una decision sin una sola razon no se explica.
    NO_REASONS = "no_reasons"
    CASE_NOT_FOUND = "case_not_found"
    #: El caso ya no esta derivado: lo tomo otro o ya se decidio.
    CASE_NOT_DECIDABLE = "case_not_decidable"
    #: El proceso que llevaba la corrida se cayo sin cerrarla y ya no quedaban intentos.
    RUN_ABANDONED = "run_abandoned"
    #: Un fallo que el proceso no sabia nombrar. Se registra el tipo de la excepcion, no su texto.
    INTERNAL_ERROR = "internal_error"
    #: Los cuatro de la frontera del proveedor, con la misma grafia del adaptador.
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_INVALID_RESPONSE = "provider_invalid_response"

    @classmethod
    def from_provider(cls, kind: ProviderErrorKind) -> ErrorKind:
        return cls(f"provider_{kind.value}")
