"""Los pasos que son de codigo: lo que el caso dice, lo que la poliza dice y lo que las reglas dijeron.

Nada de aqui llama a un modelo. Leer el reporte, la poliza y las reglas es un hecho exacto, y el
modelo decide sobre hechos exactos y no sobre lo que recuerde (A2).

**El relato y los campos se abren aqui y solo aqui**, con el cifrador que enchufa la raiz de
composicion: la vista del caso trae las claves de los campos y no sus valores. **La poliza se lee
por `policy_rag.facts`**, la misma superficie que usan la respuesta del chat y el servidor MCP: la
vigencia se calcula contra la fecha que entrega quien llama y no contra el reloj.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date

from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record.crypto import Cipher
from untangle.case_record.models import Speaker
from untangle.inbox import case_view
from untangle.policy_rag.facts import api as facts
from untangle.policy_rag.facts.models import (
    DeductibleFact,
    DriverFact,
    EndorsementFact,
    LimitFact,
    PolicySummary,
    VehicleFact,
)
from untangle.tenancy.models import TenantId

#: El campo que guarda lo que la persona conto, tal como lo escribio.
NARRATIVE_FIELD = "description"


@dataclass(frozen=True)
class CaseReading:
    """Lo que el reporte dice: el caso con su evidencia, el relato y los demas campos."""

    detail: case_view.CaseDetail
    narrative: str
    #: Los campos anotados distintos del relato, con su valor, en el orden de la vista.
    fields: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class PolicyReading:
    """Lo que dice la poliza del reporte. `summary` nulo es que no hay poliza que leer."""

    policy_number: str | None
    summary: PolicySummary | None
    vehicles: tuple[VehicleFact, ...] = ()
    drivers: tuple[DriverFact, ...] = ()
    deductibles: tuple[DeductibleFact, ...] = ()
    limits: tuple[LimitFact, ...] = ()
    endorsements: tuple[EndorsementFact, ...] = ()


async def read_case_state(tenant_id: TenantId, case_id: str) -> casos.CaseView | None:
    """El caso tal como esta ahora (su estado y su poliza), o nada."""
    return await casos.get_case(tenant_id, case_id)


async def read_case(tenant_id: TenantId, case_id: str, *, cipher: Cipher) -> CaseReading | None:
    """El reporte con todo lo que anoto la persona, abierto en claro para quien decide."""
    detalle = await case_view.detail_for(tenant_id, case_id)
    if detalle is None:
        return None
    claves = [campo.field_key for campo in detalle.fields]
    valores = await casos.open_field_values(tenant_id, case_id, claves, cipher=cipher)
    relato = valores.get(NARRATIVE_FIELD) or " ".join(
        turno.text_redacted for turno in detalle.transcript if turno.speaker is Speaker.INSURED
    )
    campos = tuple(
        (clave, valores[clave]) for clave in claves if clave != NARRATIVE_FIELD and clave in valores
    )
    return CaseReading(detail=detalle, narrative=relato, fields=campos)


async def read_policy(
    tenant_id: TenantId, policy_number: str | None, *, language: Locale, on: date
) -> PolicyReading:
    """La poliza que nombra el reporte, hecho por hecho. Sin numero o sin poliza, lo dice vacia."""
    if policy_number is None:
        return PolicyReading(policy_number=None, summary=None)
    resumen = await facts.policy_summary(tenant_id, policy_number, on=on)
    if resumen is None:
        return PolicyReading(policy_number=policy_number, summary=None)
    vehiculos, conductores, deducibles, limites, endosos = await asyncio.gather(
        facts.vehicles(tenant_id, policy_number),
        facts.drivers(tenant_id, policy_number),
        facts.deductibles(tenant_id, policy_number, language=language),
        facts.limits(tenant_id, policy_number, language=language),
        facts.endorsements(tenant_id, policy_number, language=language),
    )
    return PolicyReading(
        policy_number=policy_number,
        summary=resumen,
        vehicles=vehiculos or (),
        drivers=conductores or (),
        deductibles=deducibles or (),
        limits=limites or (),
        endorsements=endosos or (),
    )
