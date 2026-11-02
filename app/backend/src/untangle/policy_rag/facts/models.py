"""Los datos de una poliza emitida, tipados (plan 09, punto 6).

Lo que contesta una pregunta **rigida** --«¿cual es mi deducible?», «¿hasta cuando esta vigente?»,
«¿que carros figuran?»-- no se interpreta: es un dato guardado en la poliza emitida. Estos modelos
son la forma en que ese dato sale de `policy_rag.facts`, para quien lo pida: la respuesta del
chat y de la llamada, el servidor MCP y, mas adelante, el subagente ajustador. Cada valor sale
tal cual del registro; lo unico que se calcula es la vigencia contra una fecha que el llamador
entrega (el modulo no lee el reloj).

**Los montos** viajan con sus tres formas --la unidad del corpus, los pesos y el texto ya
escrito para el idioma-- para que nadie tenga que adivinar la unidad: el corpus guarda miles de
pesos colombianos (decision de Miguel del 2026-10-07) y la pestana de polizas los muestra
multiplicados por mil.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import Field

from untangle.base import Frozen, Locale
from untangle.tenancy.models import TENANT_ID_PATTERN, TenantId


class PolicyStatus(StrEnum):
    """Donde cae una fecha respecto del periodo de la poliza. Los extremos cuentan como vigentes."""

    IN_FORCE = "in_force"
    EXPIRED = "expired"
    NOT_YET_IN_FORCE = "not_yet_in_force"


class Amount(Frozen):
    """Un monto de la poliza: la unidad del corpus, los pesos y el texto para el idioma."""

    #: Miles de pesos colombianos, tal como los guarda el corpus.
    units: int = Field(ge=0)
    #: Pesos colombianos (`units` por mil).
    pesos: int = Field(ge=0)
    #: Como lo muestra la pestana de polizas en ese idioma: `$ 1.500.000` o `COP 1,500,000`.
    formatted: str = Field(min_length=1)
    language: Locale


class LimitFact(Frozen):
    """Un limite de la poliza, con la clave estable del corpus y su rotulo."""

    #: La clave del corpus, p. ej. `a.bodily_injury_per_person`.
    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    amount: Amount


class DeductibleFact(Frozen):
    """Un deducible de la poliza (las claves del corpus que terminan en `_deductible`)."""

    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    amount: Amount


class VehicleFact(Frozen):
    """Un vehiculo asegurado. Solo su descripcion: ni placa ni VIN salen de este modulo."""

    description: str = Field(min_length=1)


class DriverFact(Frozen):
    """Un conductor que la poliza declara. El titular va primero."""

    full_name: str = Field(min_length=1)
    is_holder: bool


class EndorsementFact(Frozen):
    """Un endoso de la poliza y que clausulas cambia, por su clave."""

    form_id: str = Field(min_length=1)
    clause_keys: tuple[str, ...] = ()
    #: Lo que cambia, dicho en el idioma pedido, una frase por clausula conocida. Una clave que
    #: el catalogo no conoce no se inventa: no aparece aqui y queda en `clause_keys`.
    summaries: tuple[str, ...] = ()


class ClauseFact(Frozen):
    """Una clausula de la poliza, tal como esta en el corpus de su aseguradora (solo lectura)."""

    clause_id: str = Field(min_length=1)
    clause_key: str = Field(min_length=1)
    form_id: str = Field(min_length=1)
    form_version: str = Field(min_length=1)
    part: str = Field(min_length=1)
    language: Locale
    text: str = Field(min_length=1)


class PolicySummary(Frozen):
    """Quien es el titular, quien emite, el periodo y si rige en la fecha pedida."""

    tenant_id: TenantId = Field(pattern=TENANT_ID_PATTERN)
    policy_number: str = Field(min_length=1)
    holder_name: str
    issuer_tenant: TenantId = Field(pattern=TENANT_ID_PATTERN)
    form_id: str = Field(min_length=1)
    form_version: str = Field(min_length=1)
    period_start: date
    period_end: date
    #: La fecha contra la que se calculo `status`.
    as_of: date
    status: PolicyStatus
    vehicle_count: int = Field(ge=0)
    driver_count: int = Field(ge=0)
    endorsement_count: int = Field(ge=0)


__all__ = [
    "Amount",
    "ClauseFact",
    "DeductibleFact",
    "DriverFact",
    "EndorsementFact",
    "LimitFact",
    "PolicyStatus",
    "PolicySummary",
    "VehicleFact",
]
