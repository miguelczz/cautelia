"""La superficie publica de `tenancy` (C-10, C-11, C-25).

**Una sola superficie**, tal como fija el contrato: tipos congelados y firmas, no
un documento aparte. Las veinte unidades que vienen detras consumen esto y nada
mas; el contrato de capas de `import-linter` falla si alguna importa una pieza
interna.

Lo que hay aqui dentro:

- la sesion con la aseguradora ya fijada, que es la **unica** via a la base;
- la asercion de aislamiento, que corre en la verificacion y al arrancar;
- la verificacion de credencial y la comprobacion de permiso;
- el canje de enlace y la resolucion de clave de navegador;
- el `Protocol` del purgador y con que se compara el registro.

Este modulo no tiene logica propia a proposito: si la tuviera, seria una septima
pieza escondida en la puerta de entrada.
"""

from __future__ import annotations

from untangle.tenancy.config import (
    LoadedTenants,
    available_ids,
    install,
    load,
    loaded,
    require,
)
from untangle.tenancy.models import (
    VISITOR_DATA,
    VISITOR_DATA_MARK,
    Action,
    CallConfig,
    CaseLinkGrant,
    CredentialRejectedError,
    CredentialRejection,
    Denial,
    IssuedCaseLink,
    LinkRejectedError,
    LinkRejection,
    Monogram,
    PurgeResult,
    RlsReport,
    Role,
    RolePermission,
    StaffCredential,
    StaffPrincipal,
    TenantBrand,
    TenantConfig,
    TenantConfigError,
    TenantId,
    TenantKind,
    UnavailableTenant,
    UnknownTenantError,
    VisitorDataPurger,
    VisitorKeyRecord,
)
from untangle.tenancy.purge import (
    CASE_ACCESS_LINK_PURGER,
    VISITOR_KEY_PURGER,
    registered_tables,
    tables_without_purger,
    visitor_data_tables,
)
from untangle.tenancy.rls_assertion import assert_rls_complete
from untangle.tenancy.session import (
    TenantSession,
    configure,
    configured_url,
    current_tenant,
    dispose,
    execute_sql,
    fetch_all,
    fetch_one,
    session_for,
)
from untangle.tenancy.staff_identity import (
    CREDENTIAL_LIFETIME,
    authorize,
    is_permitted,
    issue_credential,
    verify_credential,
)
from untangle.tenancy.visitor_access import (
    LINK_LIFETIME,
    authorize_case,
    issue_case_link,
    new_visitor_key,
    redeem_case_link,
    resolve_visitor_key,
    revoke_case_link,
    visitor_key_digest,
)

# Los dos purgadores de U2 se exportan **de uno en uno**, no como una lista que
# la raiz copie. El registro de C-11 es una lista escrita a mano en la raiz de
# composicion, y tiene que poder leerse entera en un solo archivo: si aqui
# hubiera una lista y alli otra, habria dos sitios donde olvidarse de uno.


__all__ = [
    "CASE_ACCESS_LINK_PURGER",
    "CREDENTIAL_LIFETIME",
    "LINK_LIFETIME",
    "VISITOR_DATA",
    "VISITOR_DATA_MARK",
    "VISITOR_KEY_PURGER",
    "Action",
    "CallConfig",
    "CaseLinkGrant",
    "CredentialRejectedError",
    "CredentialRejection",
    "Denial",
    "IssuedCaseLink",
    "LinkRejectedError",
    "LinkRejection",
    "LoadedTenants",
    "Monogram",
    "PurgeResult",
    "RlsReport",
    "Role",
    "RolePermission",
    "StaffCredential",
    "StaffPrincipal",
    "TenantBrand",
    "TenantConfig",
    "TenantConfigError",
    "TenantId",
    "TenantKind",
    "TenantSession",
    "UnavailableTenant",
    "UnknownTenantError",
    "VisitorDataPurger",
    "VisitorKeyRecord",
    "assert_rls_complete",
    "authorize",
    "authorize_case",
    "available_ids",
    "configure",
    "configured_url",
    "current_tenant",
    "dispose",
    "execute_sql",
    "fetch_all",
    "fetch_one",
    "install",
    "is_permitted",
    "issue_case_link",
    "issue_credential",
    "load",
    "loaded",
    "new_visitor_key",
    "redeem_case_link",
    "registered_tables",
    "require",
    "resolve_visitor_key",
    "revoke_case_link",
    "session_for",
    "tables_without_purger",
    "verify_credential",
    "visitor_data_tables",
    "visitor_key_digest",
]
