"""El acceso del visitante: el enlace de una hora y la clave del navegador.

Dos cosas, las dos ligadas a su aseguradora y ninguna con identidad de nadie.

**Del token se guarda su resumen, nunca el token** (FD-U2-8). Quien lea la tabla
no puede reconstruir ningun enlace. El token se firma con la biblioteca estandar
y con **su propia clave**, distinta de la de la bandeja: tienen radios de dano
distintos, y que esten separadas no se declara, se prueba presentando lo firmado
con una al verificador de la otra (NFR-U2-1).

**El enlace es reutilizable mientras valga** (BR3.2, FD-U2-3). Quemarlo con el
primer canje deja fuera a quien recargue la pagina o cierre la pestana, con un
"enlace vencido" que quien evalua la demostracion lee como un error nuestro. La
ventana de riesgo ya la acota la hora.

**Las cuatro causas de rechazo responden igual**: invalido, caducado, revocado y
de otro caso son indistinguibles de un caso que nunca existio (BR3.3).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from untangle import observability
from untangle.settings import CASE_LINK_SIGNING_KEY_VAR
from untangle.tenancy import session
from untangle.tenancy.models import (
    CaseLinkGrant,
    IssuedCaseLink,
    LinkRejectedError,
    LinkRejection,
    TenantId,
    VisitorKeyRecord,
)

#: Una hora desde que se emite (FR8.7, BR3.1).
LINK_LIFETIME = timedelta(hours=1)

#: El mismo minimo de clave que la bandeja (RFC 7518 seccion 3.2).
MINIMUM_SIGNING_KEY_BYTES = 32

#: El unico alcance que existe hoy: ver el caso propio y decidir sobre el. Nunca
#: la lista de la aseguradora, que expondria los casos de otros visitantes.
ACCESS_VIEW_AND_DECIDE = "view_and_decide"

INSERTAR_ENLACE = """
    INSERT INTO case_access_link (
        link_id, tenant_id, case_id, token_digest, access,
        created_at, expires_at, redeemed_count
    ) VALUES (
        :link_id, :tenant_id, :case_id, :token_digest, :access,
        :created_at, :expires_at, 0
    )
"""

BUSCAR_POR_RESUMEN = """
    SELECT link_id, tenant_id, case_id, token_digest, access,
           expires_at, revoked_at, redeemed_count
    FROM case_access_link
    WHERE token_digest = :token_digest
"""

SUBIR_CONTADOR = """
    UPDATE case_access_link
    SET redeemed_count = redeemed_count + 1
    WHERE link_id = :link_id
    RETURNING redeemed_count
"""

REVOCAR = """
    UPDATE case_access_link
    SET revoked_at = :revoked_at
    WHERE link_id = :link_id AND revoked_at IS NULL
"""

INSERTAR_CLAVE = """
    INSERT INTO visitor_key (
        tenant_id, visitor_key_hash, origin, created_at, last_seen_at
    ) VALUES (
        :tenant_id, :visitor_key_hash, :origin, :created_at, :created_at
    )
"""

TOCAR_CLAVE = """
    UPDATE visitor_key
    SET last_seen_at = :last_seen_at
    WHERE visitor_key_hash = :visitor_key_hash
    RETURNING created_at, origin
"""


class LinkSigningKeyMissingError(RuntimeError):
    """No hay clave de firma de enlaces. Falla, nunca acepta en silencio."""


def require_signing_key(key: str | None, *, variable: str) -> bytes:
    """La clave de firma, comprobada, o un error que **nombra la que falta**.

    **Publica desde U16.** Hasta entonces solo la usaba el enlace de caso de esta
    unidad; el token de llamada de voz comprueba su clave aqui mismo, porque
    duplicar la comprobacion y su mensaje seria tener dos sitios que dicen que
    mide una clave valida, y un dia dejan de coincidir.

    `variable` entra por argumento desde el 2026-10-03, cuando la voz paso a
    firmar con la suya: un mensaje que nombrara siempre el enlace de caso
    mandaria a definir la variable equivocada a la unica persona que puede
    arreglarlo.
    """
    return _require_key(key, variable)


def _require_key(key: str | None, variable: str = CASE_LINK_SIGNING_KEY_VAR) -> bytes:
    if not key:
        msg = (
            f"falta la clave de firma: defina {variable} en el entorno. Es **otra** "
            "clave, distinta de la de la bandeja, y ninguna vive en el repositorio."
        )
        raise LinkSigningKeyMissingError(msg)
    crudo = key.encode("utf-8")
    # El mismo minimo que la clave de la bandeja, y por la misma razon: HMAC con
    # SHA-256 pide al menos 32 bytes (RFC 7518 seccion 3.2).
    if len(crudo) < MINIMUM_SIGNING_KEY_BYTES:
        msg = (
            f"{variable} mide {len(crudo)} bytes y el minimo "
            f"son {MINIMUM_SIGNING_KEY_BYTES} (RFC 7518 seccion 3.2). Genere una "
            "con `python -c 'import secrets; print(secrets.token_urlsafe(32))'`."
        )
        raise LinkSigningKeyMissingError(msg)
    return crudo


def _sign(secret: str, key: bytes) -> str:
    return hmac.new(key, secret.encode("utf-8"), hashlib.sha256).hexdigest()


def token_digest(token: str) -> str:
    """El resumen que se guarda en la fila. El token en claro no se guarda nunca."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def visitor_key_digest(visitor_key: str) -> str:
    """El resumen de la clave del navegador. La clave en claro tampoco se guarda."""
    return hashlib.sha256(visitor_key.encode("utf-8")).hexdigest()


def new_visitor_key() -> str:
    """Una clave de navegador nueva. Se entrega una vez y se guarda su resumen."""
    return secrets.token_urlsafe(32)


# --- El enlace de caso --------------------------------------------------------


async def issue_case_link(
    *,
    tenant_id: TenantId,
    case_id: str,
    signing_key: str | None,
    now: datetime | None = None,
) -> IssuedCaseLink:
    """Emite el enlace de un caso, con una hora de vida (BR3.1).

    Devuelve el token **una sola vez**: de la fila queda su resumen. El enlace se
    arma despues de modo que el token viaje en el fragmento de la direccion, que
    el navegador nunca manda al servidor, asi que no aparece en la barra, ni en
    la cabecera de procedencia, ni en los registros (C-07).
    """
    clave = _require_key(signing_key)
    creado = now if now is not None else datetime.now(UTC)
    caduca = creado + LINK_LIFETIME

    secreto = secrets.token_urlsafe(32)
    token = f"{secreto}.{_sign(secreto, clave)}"
    link_id = f"lnk-{secrets.token_hex(12)}"

    async with session.session_for(tenant_id) as sesion:
        await session.execute_sql(
            sesion,
            INSERTAR_ENLACE,
            link_id=link_id,
            tenant_id=tenant_id,
            case_id=case_id,
            token_digest=token_digest(token),
            access=ACCESS_VIEW_AND_DECIDE,
            created_at=creado,
            expires_at=caduca,
        )

    observability.emit(
        "tenancy.case_link_issued",
        tenant_id=tenant_id,
        link_id=link_id,
        expires_at=caduca.isoformat(),
    )
    return IssuedCaseLink(
        link_id=link_id,
        token=token,
        tenant_id=tenant_id,
        case_id=case_id,
        expires_at=caduca,
    )


def _rechazar(cause: LinkRejection, *, tenant_id: str) -> LinkRejectedError:
    """Deja el rastro y devuelve el error. La causa real sale **solo aqui**."""
    observability.emit(
        "tenancy.case_link_rejected",
        attempted_tenant=tenant_id,
        cause=cause.value,
    )
    return LinkRejectedError(cause)


def _token_valido(token: str, clave: bytes) -> bool:
    """Comprueba la firma en **tiempo constante**.

    Un token firmado con la clave de la bandeja llega hasta aqui y se cae: es lo
    unico que prueba que las dos claves estan separadas de verdad.
    """
    secreto, _, firma = token.partition(".")
    if not secreto or not firma:
        return False
    return hmac.compare_digest(firma, _sign(secreto, clave))


async def verify_case_link(
    token: str,
    *,
    tenant_id: TenantId,
    signing_key: str | None,
    expected_case: str | None = None,
    now: datetime | None = None,
) -> CaseLinkGrant:
    """Comprueba el token **sin** subir el contador de canjes.

    Enmienda aditiva a C-07 del 2026-09-28, pedida por U14. Canjear es lo que hace
    la pantalla **una vez al cargar**, y su contador existe para que un canje
    repetido sea un hecho observable. Comprobar es lo que hace **cada peticion
    siguiente** con la cookie de caso: contarlas como canjes convertiria el
    contador en un contador de clics y dejaria de decir lo que dice.

    Todo lo demas es identico, incluidas las cuatro causas de rechazo y su unica
    respuesta hacia fuera.
    """
    return await _mirar_enlace(
        token,
        tenant_id=tenant_id,
        signing_key=signing_key,
        expected_case=expected_case,
        now=now,
        contar=False,
    )


async def redeem_case_link(
    token: str,
    *,
    tenant_id: TenantId,
    signing_key: str | None,
    expected_case: str | None = None,
    now: datetime | None = None,
) -> CaseLinkGrant:
    """Canjea el token por acceso a **un** caso (BR3.2, BR3.3, BR3.4).

    No quema el token: mientras no haya caducado ni este revocado, se puede
    volver a canjear y quien cierre la pestana vuelve a entrar. Lo que si sube es
    el contador, para que un canje repetido sea un hecho observable.
    """
    return await _mirar_enlace(
        token,
        tenant_id=tenant_id,
        signing_key=signing_key,
        expected_case=expected_case,
        now=now,
        contar=True,
    )


async def _mirar_enlace(  # noqa: PLR0913 -- las cinco cosas del canje mas si cuenta
    token: str,
    *,
    tenant_id: TenantId,
    signing_key: str | None,
    expected_case: str | None,
    now: datetime | None,
    contar: bool,
) -> CaseLinkGrant:
    """El camino unico de las dos: mismas comprobaciones, mismo orden, mismo rechazo.

    Uno solo y no dos copias: el dia que se separaran, la que se olvidara de una
    comprobacion seria la que mas se usa.
    """
    clave = _require_key(signing_key)
    momento = now if now is not None else datetime.now(UTC)

    if not _token_valido(token, clave):
        raise _rechazar(LinkRejection.INVALID, tenant_id=tenant_id)

    resumen = token_digest(token)

    async with session.session_for(tenant_id) as sesion:
        # La politica de la tabla ya acota la busqueda a esta aseguradora: un
        # enlace de otra no se encuentra aqui, y por eso responde igual que uno
        # que nunca existio.
        fila = await session.fetch_one(sesion, BUSCAR_POR_RESUMEN, token_digest=resumen)
        if fila is None:
            raise _rechazar(LinkRejection.INVALID, tenant_id=tenant_id)

        # El resumen ya vino de una comparacion por igualdad en la base; esta es
        # la comparacion en tiempo constante que exige el diseno de seguridad.
        if not hmac.compare_digest(str(fila["token_digest"]), resumen):
            raise _rechazar(LinkRejection.INVALID, tenant_id=tenant_id)

        if fila["revoked_at"] is not None:
            raise _rechazar(LinkRejection.REVOKED, tenant_id=tenant_id)

        caduca: datetime = fila["expires_at"]
        if caduca <= momento:
            raise _rechazar(LinkRejection.EXPIRED, tenant_id=tenant_id)

        if expected_case is not None and str(fila["case_id"]) != expected_case:
            raise _rechazar(LinkRejection.OTHER_CASE, tenant_id=tenant_id)

        if contar:
            canjes = await session.fetch_one(sesion, SUBIR_CONTADOR, link_id=fila["link_id"])
            contador = int(canjes["redeemed_count"]) if canjes is not None else 0
        else:
            contador = int(fila["redeemed_count"])

        concesion = CaseLinkGrant(
            tenant_id=str(fila["tenant_id"]),
            case_id=str(fila["case_id"]),
            access=str(fila["access"]),
            # Nunca mas que lo que le quede al enlace (BR3.4).
            expires_at=caduca,
            redeemed_count=contador,
        )

    if contar:
        observability.emit(
            "tenancy.case_link_redeemed",
            tenant_id=concesion.tenant_id,
            link_id=str(fila["link_id"]),
            redeemed_count=contador,
        )
    return concesion


def authorize_case(grant: CaseLinkGrant, case_id: str) -> None:
    """Comprueba que la concesion abre **ese** caso y no otro (BR3.1).

    Pedir la lista de casos, o cualquier otro caso, responde como si no
    existiera: mostrarla expondria los casos de otros visitantes.
    """
    if grant.case_id != case_id:
        raise _rechazar(LinkRejection.OTHER_CASE, tenant_id=grant.tenant_id)


async def revoke_case_link(
    *, tenant_id: TenantId, link_id: str, now: datetime | None = None
) -> bool:
    """Revoca un enlace. Una vez revocado, no se vuelve atras."""
    momento = now if now is not None else datetime.now(UTC)
    async with session.session_for(tenant_id) as sesion:
        tocadas = await session.execute_sql(sesion, REVOCAR, link_id=link_id, revoked_at=momento)
    if tocadas:
        observability.emit("tenancy.case_link_revoked", tenant_id=tenant_id, link_id=link_id)
    return bool(tocadas)


# --- La clave del navegador ---------------------------------------------------


async def resolve_visitor_key(
    *,
    tenant_id: TenantId,
    visitor_key: str,
    origin: str,
    now: datetime | None = None,
) -> VisitorKeyRecord:
    """Reconoce el navegador **dentro de esta aseguradora** (BR3.5).

    Una clave usada en otra aseguradora no encuentra fila aqui: crea la suya, y
    las dos quedan separadas. No se guarda nada que identifique a una persona:
    ni nombre, ni correo, ni direccion de red.
    """
    momento = now if now is not None else datetime.now(UTC)
    resumen = visitor_key_digest(visitor_key)

    async with session.session_for(tenant_id) as sesion:
        tocada = await session.fetch_one(
            sesion, TOCAR_CLAVE, visitor_key_hash=resumen, last_seen_at=momento
        )
        if tocada is not None:
            return VisitorKeyRecord(
                tenant_id=tenant_id,
                visitor_key_hash=resumen,
                origin=str(tocada["origin"]),
                created_at=tocada["created_at"],
                last_seen_at=momento,
            )

        await session.execute_sql(
            sesion,
            INSERTAR_CLAVE,
            tenant_id=tenant_id,
            visitor_key_hash=resumen,
            origin=origin,
            created_at=momento,
        )

    observability.emit("tenancy.visitor_key_registered", tenant_id=tenant_id)
    return VisitorKeyRecord(
        tenant_id=tenant_id,
        visitor_key_hash=resumen,
        origin=origin,
        created_at=momento,
        last_seen_at=momento,
    )
