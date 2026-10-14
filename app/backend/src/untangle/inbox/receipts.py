"""El recibo que impide aplicar dos veces la misma escritura (C-05, BR4.4).

C-05 promete que repetir una clave de idempotencia devuelve **la primera** escritura
y no crea otra. Esa promesa vive en la base --en la restriccion unica de
`decision_receipt`-- y no en un `if` de este archivo: dos peticiones a la vez con la
misma clave leerian las dos "no hay recibo" antes de que ninguna escribiera, y las
dos seguirian adelante. Lo que decide es el choque.

**La huella de la peticion es lo que separa dos cosas distintas.** "La misma
peticion otra vez" devuelve el resultado guardado; "otra peticion con la clave
reciclada" es un conflicto. Devolverle a alguien el resultado de una peticion que no
hizo es peor que fallar: le dice que su correccion se aplico cuando lo que se aplico
fue otra.

Una sola tabla para las tres escrituras --decidir, corregir y anotar para las reglas--
porque es un solo mecanismo. Dos tablas serian dos sitios donde arreglar el mismo fallo.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from untangle.tenancy import api as tenancy
from untangle.tenancy.models import TenantId


class Operation(StrEnum):
    """Las tres escrituras idempotentes de la bandeja. Conjunto cerrado."""

    DECISION = "decision"
    FIELD_CORRECTION = "field_correction"
    #: Lo que el ajustador anota para las reglas de triage (monto, cobertura, fraude).
    TRIAGE_NOTE = "triage_note"


class RecycledKeyError(RuntimeError):
    """La clave ya se uso para **otra** peticion.

    No es "ya lo hiciste": es "esta clave dice una cosa y tu peticion dice otra".
    Responde `409`, nunca el resultado guardado.
    """


@dataclass(frozen=True)
class Receipt:
    """Lo que quedo escrito de una escritura idempotente."""

    receipt_id: str
    operation: Operation
    case_id: str
    request_digest: str
    result_ref: str
    created_at: datetime


_INSERTAR = """
    INSERT INTO decision_receipt
        (receipt_id, tenant_id, idempotency_key, operation, case_id, request_digest,
         result_ref, created_at)
    VALUES
        (:receipt_id, :tenant_id, :idempotency_key, :operation, :case_id, :request_digest,
         :result_ref, :created_at)
    ON CONFLICT (tenant_id, operation, idempotency_key) DO NOTHING
    RETURNING receipt_id
"""

_LEER = """
    SELECT receipt_id, operation, case_id, request_digest, result_ref, created_at
    FROM decision_receipt
    WHERE tenant_id = :tenant_id AND operation = :operation AND idempotency_key = :idempotency_key
"""


def digest_of(*partes: str) -> str:
    """La huella de lo que se pidio. Nunca guarda el valor, solo su resumen.

    Un valor corregido es dato personal: guardarlo aqui abriria un punto de salida
    mas, y lo unico que hace falta es poder decir si dos peticiones son la misma.
    """
    crudo = "\u001f".join(partes)
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()


async def find(
    tenant_id: TenantId, *, operation: Operation, idempotency_key: str
) -> Receipt | None:
    """El recibo de esa clave, o nada."""
    async with tenancy.session_for(tenant_id) as sesion:
        fila = await tenancy.fetch_one(
            sesion,
            _LEER,
            tenant_id=tenant_id,
            operation=operation.value,
            idempotency_key=idempotency_key,
        )
    if fila is None:
        return None
    return Receipt(
        receipt_id=str(fila["receipt_id"]),
        operation=Operation(fila["operation"]),
        case_id=str(fila["case_id"]),
        request_digest=str(fila["request_digest"]),
        result_ref=str(fila["result_ref"]),
        created_at=fila["created_at"],
    )


async def reuse_or_none(
    tenant_id: TenantId,
    *,
    operation: Operation,
    idempotency_key: str,
    request_digest: str,
) -> Receipt | None:
    """El recibo anterior si la peticion es **la misma**; nada si es la primera.

    Levanta si la clave se reciclo para otra peticion. Las tres salidas son
    distintas a proposito: repetir, empezar y chocar no son lo mismo y la ruta las
    responde distinto.
    """
    anterior = await find(tenant_id, operation=operation, idempotency_key=idempotency_key)
    if anterior is None:
        return None
    if anterior.request_digest != request_digest:
        msg = (
            f"la clave de idempotencia ya se uso para otra peticion de "
            f"'{operation.value}' sobre el caso '{anterior.case_id}'"
        )
        raise RecycledKeyError(msg)
    return anterior


async def record(  # noqa: PLR0913 -- los campos del recibo, ninguno derivable de otro
    tenant_id: TenantId,
    *,
    operation: Operation,
    idempotency_key: str,
    case_id: str,
    request_digest: str,
    result_ref: str,
    now: datetime,
) -> Receipt:
    """Escribe el recibo, o devuelve el que gano la carrera.

    Cuando dos peticiones identicas llegan a la vez, una inserta y la otra choca
    contra la restriccion unica; la que choca relee y devuelve la primera, que es
    exactamente lo que C-05 promete.
    """
    recibo = Receipt(
        receipt_id=f"rec-{uuid.uuid4().hex}",
        operation=operation,
        case_id=case_id,
        request_digest=request_digest,
        result_ref=result_ref,
        created_at=now,
    )
    async with tenancy.session_for(tenant_id) as sesion:
        escrita = await tenancy.fetch_one(
            sesion,
            _INSERTAR,
            receipt_id=recibo.receipt_id,
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            operation=operation.value,
            case_id=case_id,
            request_digest=request_digest,
            result_ref=result_ref,
            created_at=now,
        )
    if escrita is not None:
        return recibo

    # Perdio la carrera: otra peticion con la misma clave escribio primero. Se
    # relee y se devuelve la suya, que es lo que C-05 promete. El `ON CONFLICT`
    # lo detecta sin levantar, porque el contrato de importaciones no deja que una
    # unidad conozca las excepciones del motor --y no hace falta: el conflicto es
    # un resultado previsto, no un fallo--.
    gano = await find(tenant_id, operation=operation, idempotency_key=idempotency_key)
    if gano is None:  # pragma: no cover -- el conflicto garantiza que hay fila
        msg = f"la clave '{idempotency_key}' choco al escribirse y no se pudo releer"
        raise LookupError(msg)  # pragma: no cover
    if gano.request_digest != request_digest:
        msg = "la clave de idempotencia se uso para otra peticion mientras esta corria"
        raise RecycledKeyError(msg)
    return gano
