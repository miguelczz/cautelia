"""Donde queda la elegibilidad de una solicitud, y de donde la lee el turno.

**Ninguna conexion propia**, igual que el resto: toda consulta pasa por el punto
unico de sesion, con la aseguradora fijada, y los parametros se ligan.

**Una fila por caso, y la ultima gana.** La elegibilidad se evalua cuando los
cuatro bloques quedan capturados (BR2.5); si el visitante corrige un campo y se
vuelve a evaluar, lo que vale es lo ultimo. Un historial de intentos invitaria a
que la bandeja mostrara uno viejo, y lo que de verdad hace falta auditar --cada
corrida con su instante y sus reglas-- ya esta en la traza.

Por eso la escritura **no** es idempotente por identificador como la del triage:
es un reemplazo por caso. Repetirla con el mismo resultado deja la misma fila, y
repetirla con otro deja el nuevo, que es justo lo que se quiere.
"""

from __future__ import annotations

import json
from datetime import datetime

from untangle.rules.eligibility import EligibilityOutcome
from untangle.tenancy import api as tenancy
from untangle.tenancy.models import TenantId

__all__ = ["eligibility_of", "save_eligibility"]

_GUARDAR = """
    INSERT INTO quote_eligibility (tenant_id, case_id, ruleset_version, outcome, band,
                                   deciding_rules, explanation_key, evaluated_at)
    VALUES (:tenant_id, :case_id, :ruleset_version, :outcome, :band,
            CAST(:deciding_rules AS jsonb), :explanation_key, :evaluated_at)
    ON CONFLICT (tenant_id, case_id) DO UPDATE SET
        ruleset_version = EXCLUDED.ruleset_version,
        outcome = EXCLUDED.outcome,
        band = EXCLUDED.band,
        deciding_rules = EXCLUDED.deciding_rules,
        explanation_key = EXCLUDED.explanation_key,
        evaluated_at = EXCLUDED.evaluated_at
"""

_LEER = """
    SELECT ruleset_version, outcome, band, deciding_rules, explanation_key
    FROM quote_eligibility
    WHERE case_id = :case_id
"""


async def save_eligibility(
    tenant_id: TenantId, case_id: str, outcome: EligibilityOutcome, *, evaluated_at: datetime
) -> None:
    """Deja la elegibilidad del caso, reemplazando la anterior si la habia."""
    volcado = outcome.model_dump(mode="json")
    async with tenancy.session_for(tenant_id) as sesion:
        await tenancy.execute_sql(
            sesion,
            _GUARDAR,
            tenant_id=tenant_id,
            case_id=case_id,
            ruleset_version=volcado["ruleset_version"],
            outcome=volcado["outcome"],
            band=volcado["band"],
            # El driver no adapta una lista de Python a `jsonb` en una consulta de
            # texto: se manda la cadena y el `CAST` la convierte en la base.
            deciding_rules=json.dumps(volcado["deciding_rules"]),
            explanation_key=volcado["explanation_key"],
            evaluated_at=evaluated_at,
        )


async def eligibility_of(tenant_id: TenantId, case_id: str) -> EligibilityOutcome | None:
    """La elegibilidad guardada del caso, o `None` si todavia no se evaluo.

    `None` es "el fondo no ha terminado", y es lo que distingue "espera" de
    "no elegible": colapsarlos diria que no a quien todavia no se le ha mirado.
    """
    async with tenancy.session_for(tenant_id) as sesion:
        fila = await tenancy.fetch_one(sesion, _LEER, case_id=case_id)
    return None if fila is None else EligibilityOutcome.model_validate(dict(fila))
