"""La superficie publica de `demo_operations` (U20).

Dos operaciones puras --validar la carpeta de una aseguradora y orquestar el
reinicio nocturno sobre el contrato de borrado-- y el registro de lo que la
segunda hizo. Quien las conecta a la base, al corpus y al disparador es la raiz
de composicion, que es la unica capa que tiene el registro de purgadores.
"""

from __future__ import annotations

from untangle.demo_operations.folder import validate_tenant_folder
from untangle.demo_operations.models import (
    PurgerRow,
    ResetOutcome,
    ResetRun,
    TenantFault,
    TenantFolderReport,
)
from untangle.demo_operations.repository import save_run, successful_runs
from untangle.demo_operations.reset import (
    ALERT_EVENT,
    RESET_NOTICE,
    RESET_WINDOW,
    SURFACES_CLOSED,
    EmptyRegistryError,
    accepts_new_cases,
    last_successful_reset,
    run_reset,
)

__all__ = [
    "ALERT_EVENT",
    "RESET_NOTICE",
    "RESET_WINDOW",
    "SURFACES_CLOSED",
    "EmptyRegistryError",
    "PurgerRow",
    "ResetOutcome",
    "ResetRun",
    "TenantFault",
    "TenantFolderReport",
    "accepts_new_cases",
    "last_successful_reset",
    "run_reset",
    "save_run",
    "successful_runs",
    "validate_tenant_folder",
]
