"""La identidad del personal de la bandeja (US5.7, BR2.1 a BR2.6).

Cinco pasos, en este orden, **antes de tocar la base**: leer la credencial,
comprobar la firma, comprobar la caducidad, comprobar que la aseguradora de la
credencial es la de los datos que se piden, y consultar la tabla de permisos con
la pareja (rol, accion).

Los pasos dos, tres y cuatro producen **una respuesta identica en bytes**. No es
cortesia: una respuesta distinta por causa le dice a quien prueba cual de las
tres acerto, y eso convierte el rechazo en un oraculo. La causa real viaja al
rastro, que es donde sirve.

El paso cinco no vive en ninguna ruta: vive aqui, por donde pasan todas, para
que una ruta nueva no pueda olvidarse de el.

**Ninguna credencial se guarda.** La de la bandeja viaja en una cookie y se
verifica con la firma en cada peticion; se emite con un comando y no se publica
(D23, BR2.6).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import yaml

from untangle import observability, paths
from untangle.tenancy import config
from untangle.tenancy.models import (
    Action,
    CredentialRejectedError,
    CredentialRejection,
    Role,
    RolePermission,
    StaffCredential,
    TenantConfigError,
    TenantId,
    UnknownTenantError,
)

#: Doce horas: cubren una sesion de trabajo o una demostracion completa sin
#: renovar, y una credencial que se escape muere el mismo dia (BR2.2, FD-U2-2).
CREDENTIAL_LIFETIME = timedelta(hours=12)

#: El algoritmo de firma. Se pasa explicito al verificar: aceptar el que diga el
#: propio token es la via por la que un token con `alg: none` se cuela.
SIGNING_ALGORITHM = "HS256"

#: Largo minimo de una clave de firma, en bytes. Lo pide la RFC 7518 seccion 3.2
#: para HMAC con SHA-256. La biblioteca solo **avisa** cuando la clave es mas
#: corta; aqui se falla, porque un aviso en un registro que nadie lee es lo mismo
#: que no tener el control.
MINIMUM_SIGNING_KEY_BYTES = 32


class SigningKeyMissingError(RuntimeError):
    """No hay clave de firma. Falla al emitir o al verificar, nunca en silencio.

    Verificar sin clave no puede devolver "no vale": seria indistinguible de una
    credencial mala y esconderia un despliegue mal configurado.
    """


def _require_key(key: str | None, nombre_de_la_variable: str) -> str:
    if not key:
        msg = (
            f"falta la clave de firma: defina {nombre_de_la_variable} en el "
            "entorno. Las dos claves de U2 estan separadas por uso y ninguna "
            "vive en el repositorio."
        )
        raise SigningKeyMissingError(msg)
    largo = len(key.encode("utf-8"))
    if largo < MINIMUM_SIGNING_KEY_BYTES:
        msg = (
            f"{nombre_de_la_variable} mide {largo} bytes y el minimo son "
            f"{MINIMUM_SIGNING_KEY_BYTES} (RFC 7518 seccion 3.2). Genere una con "
            "`python -c 'import secrets; print(secrets.token_urlsafe(32))'`."
        )
        raise SigningKeyMissingError(msg)
    return key


# --- La tabla de permisos -----------------------------------------------------


def load_permissions(path: Path | None = None) -> tuple[RolePermission, ...]:
    """La tabla versionada de rol y accion (decision Q4)."""
    archivo = path if path is not None else paths.role_permissions_path()
    if not archivo.is_file():
        msg = f"falta la tabla de permisos: se esperaba '{archivo}'"
        raise TenantConfigError(msg)

    datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    if not isinstance(datos, dict) or "permissions" not in datos:
        msg = f"'{archivo}' no declara una lista 'permissions'"
        raise TenantConfigError(msg)

    filas: list[RolePermission] = []
    for cruda in datos["permissions"]:
        try:
            filas.append(
                RolePermission(
                    role=Role(cruda["role"]),
                    action=Action(cruda["action"]),
                    allowed=bool(cruda["allowed"]),
                )
            )
        except (KeyError, ValueError) as error:
            msg = f"'{archivo}' tiene una fila de permisos invalida: {cruda!r} ({error})"
            raise TenantConfigError(msg) from error
    return tuple(filas)


_permissions: tuple[RolePermission, ...] | None = None


def install_permissions(permissions: tuple[RolePermission, ...]) -> None:
    """Fija la tabla del proceso. La llama la raiz de composicion."""
    global _permissions
    _permissions = permissions


def permissions() -> tuple[RolePermission, ...]:
    global _permissions
    if _permissions is None:
        _permissions = load_permissions()
    return _permissions


def reset_permissions() -> None:
    """Olvida la tabla cargada. Lo usan las pruebas para no compartir estado."""
    global _permissions
    _permissions = None


def is_permitted(role: Role, action: Action) -> bool:
    """Si la tabla declara esa pareja como permitida.

    Lo que no esta declarado se deniega. No hay valor por defecto permisivo:
    una pareja que nadie declaro es una pareja que nadie penso (BR2.5).
    """
    for fila in permissions():
        if fila.role is role and fila.action is action:
            return fila.allowed
    return False


# --- Emision ------------------------------------------------------------------


def issue_credential(
    *,
    tenant_id: TenantId,
    principal_id: str,
    signing_key: str | None,
    now: datetime | None = None,
) -> str:
    """Emite la credencial firmada de una persona de la bandeja (BR2.1, BR2.2).

    Comprueba antes que la persona exista en la configuracion de su aseguradora:
    emitir para alguien que no esta declarado produciria una credencial que
    despues nadie puede verificar, y el error aparecerian doce horas mas tarde.
    """
    clave = _require_key(signing_key, "UNTANGLE_STAFF_CREDENTIAL_SIGNING_KEY")
    tenant = config.require(tenant_id)
    persona = tenant.principal(principal_id)
    if persona is None:
        declaradas = ", ".join(p.principal_id for p in tenant.staff) or "(ninguna)"
        msg = (
            f"la persona '{principal_id}' no esta declarada en la aseguradora "
            f"'{tenant_id}'; declaradas: {declaradas}"
        )
        raise UnknownTenantError(msg)

    emitida = now if now is not None else datetime.now(UTC)
    caduca = emitida + CREDENTIAL_LIFETIME

    observability.emit(
        "tenancy.staff_credential_issued",
        tenant_id=tenant.tenant_id,
        principal_id=persona.principal_id,
        role=persona.role.value,
        expires_at=caduca.isoformat(),
    )
    return jwt.encode(
        {
            "tenant": tenant.tenant_id,
            "principal": persona.principal_id,
            "role": persona.role.value,
            "iat": int(emitida.timestamp()),
            "exp": int(caduca.timestamp()),
        },
        clave,
        algorithm=SIGNING_ALGORITHM,
    )


# --- Verificacion -------------------------------------------------------------


def _rechazar(cause: CredentialRejection, *, tenant_id: str, role: str) -> CredentialRejectedError:
    """Deja el rastro y devuelve el error. La causa real sale **solo aqui**.

    El evento lleva la aseguradora que se intento abrir, el rol que afirmaba la
    credencial y la causa real. Es la diferencia entre detectar un sondeo y
    enterarse por casualidad (NFR-U2-2, SEC-U2.11).
    """
    observability.emit(
        "tenancy.staff_credential_rejected",
        attempted_tenant=tenant_id,
        asserted_role=role,
        cause=cause.value,
    )
    return CredentialRejectedError(cause)


def verify_credential(
    token: str | None,
    *,
    expected_tenant: TenantId,
    signing_key: str | None,
    now: datetime | None = None,
) -> StaffCredential:
    """Verifica la credencial en **cada** peticion, no solo al entrar (BR2.3).

    Verificar solo al entrar deja una sesion abierta valiendo mas que la
    credencial que la abrio.
    """
    clave = _require_key(signing_key, "UNTANGLE_STAFF_CREDENTIAL_SIGNING_KEY")

    if not token:
        raise _rechazar(
            CredentialRejection.MISSING, tenant_id=expected_tenant, role="(sin credencial)"
        )

    momento = now if now is not None else datetime.now(UTC)
    try:
        contenido = jwt.decode(
            token,
            clave,
            algorithms=[SIGNING_ALGORITHM],
            options={"require": ["exp", "iat"], "verify_exp": False},
        )
    except jwt.InvalidTokenError:
        # Firma alterada, token ilegible o clave equivocada --incluida la del
        # **otro uso**--. Las tres llegan aqui y salen iguales.
        raise _rechazar(
            CredentialRejection.SIGNATURE_INVALID,
            tenant_id=expected_tenant,
            role="(ilegible)",
        ) from None

    rol_afirmado = str(contenido.get("role", "(sin rol)"))
    caduca = datetime.fromtimestamp(int(contenido["exp"]), tz=UTC)
    if caduca <= momento:
        raise _rechazar(
            CredentialRejection.EXPIRED,
            tenant_id=str(contenido.get("tenant", expected_tenant)),
            role=rol_afirmado,
        )

    if str(contenido.get("tenant")) != expected_tenant:
        raise _rechazar(
            CredentialRejection.WRONG_TENANT,
            tenant_id=str(contenido.get("tenant", "(sin aseguradora)")),
            role=rol_afirmado,
        )

    try:
        rol = Role(rol_afirmado)
    except ValueError:
        raise _rechazar(
            CredentialRejection.UNKNOWN_PRINCIPAL,
            tenant_id=expected_tenant,
            role=rol_afirmado,
        ) from None

    return StaffCredential(
        tenant_id=str(contenido["tenant"]),
        principal_id=str(contenido["principal"]),
        role=rol,
        issued_at=datetime.fromtimestamp(int(contenido["iat"]), tz=UTC),
        expires_at=caduca,
    )


def authorize(credential: StaffCredential, action: Action) -> None:
    """El paso cinco: la pareja (rol, accion) contra la tabla versionada.

    Una peticion directa a la interfaz programatica recorre este mismo paso que
    una que venga de la pantalla; la pantalla no es donde se comprueba nada.
    """
    if not is_permitted(credential.role, action):
        raise _rechazar(
            CredentialRejection.ACTION_NOT_PERMITTED,
            tenant_id=credential.tenant_id,
            role=credential.role.value,
        )
