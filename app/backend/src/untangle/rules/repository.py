"""Donde se guarda la evaluacion de reglas de un caso (BR4.1, CG-U9-4).

**Ninguna conexion propia**, igual que U10: toda consulta pasa por el punto
unico de sesion de U2, con la aseguradora fijada, y los parametros se ligan. La
llave hacia el caso es **compuesta** -- `(tenant_id, case_id)` -- desde la
primera migracion de esta tabla: el hueco de aislamiento que U10 tuvo que
cerrar en una segunda revision (`u10_compliance_0002_tenant_fks`) no se vuelve
a abrir aqui (UG-3).

**La escritura es idempotente por identificador** (ADR-003): el nodo `decision`
se puede volver a ejecutar entero al reanudar tras `interrupt()`, y guardar dos
veces la misma evaluacion no puede dejar dos filas. Quien llama elige el
identificador; reintentar con el mismo no duplica, y se devuelve la que quedo
guardada la primera vez -- el mismo patron que `compliance/controls/repository.py`.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from untangle.rules.models import RuleEvaluation
from untangle.tenancy import api as tenancy

INSERTAR = """
    INSERT INTO rule_evaluation (evaluation_id, tenant_id, case_id, ruleset_version, category,
                                 fired_rules, inputs_snapshot, explanation_key, evaluated_at)
    VALUES (:evaluation_id, :tenant_id, :case_id, :ruleset_version, :category,
            CAST(:fired_rules AS jsonb), CAST(:inputs_snapshot AS jsonb),
            :explanation_key, :evaluated_at)
    ON CONFLICT (evaluation_id) DO NOTHING
    RETURNING evaluation_id
"""

LEER_DEL_CASO = """
    SELECT evaluation_id, tenant_id, case_id, ruleset_version, category, fired_rules,
           inputs_snapshot, explanation_key, evaluated_at
    FROM rule_evaluation
    WHERE case_id = :case_id
    ORDER BY evaluated_at, evaluation_id
"""


def _parametros(evaluation: RuleEvaluation) -> dict[str, Any]:
    """Los valores de la fila, listos para ligar (mismo patron que U10).

    Los dos campos JSON se serializan aparte porque el driver no adapta un
    `dict`/`list` de Python a `jsonb` por si solo en una consulta de texto: se
    manda la cadena y `CAST(... AS jsonb)` la convierte en la base (igual que
    `closing_evidence` en U4).
    """
    volcado = evaluation.model_dump(mode="json")
    parametros: dict[str, Any] = {
        campo: original if isinstance(original := getattr(evaluation, campo), datetime) else valor
        for campo, valor in volcado.items()
    }
    parametros["fired_rules"] = json.dumps(volcado["fired_rules"])
    parametros["inputs_snapshot"] = json.dumps(volcado["inputs_snapshot"])
    return parametros


async def save_evaluation(evaluation: RuleEvaluation) -> RuleEvaluation:
    """Guarda la evaluacion por su identificador y devuelve la que quedo (BR3.1)."""
    async with tenancy.session_for(evaluation.tenant_id) as sesion:
        nueva = await tenancy.fetch_one(sesion, INSERTAR, **_parametros(evaluation))
    if nueva is not None:
        return evaluation

    guardadas = await evaluations_for(evaluation.tenant_id, evaluation.case_id)
    for guardada in guardadas:
        if guardada.evaluation_id == evaluation.evaluation_id:
            return guardada
    msg = (  # pragma: no cover -- el conflicto de la insercion garantiza que existe
        f"la evaluacion '{evaluation.evaluation_id}' choco al guardarse y no se pudo releer"
    )
    raise LookupError(msg)  # pragma: no cover


async def evaluations_for(tenant_id: str, case_id: str) -> tuple[RuleEvaluation, ...]:
    """Las evaluaciones guardadas del caso, en el orden en que se hicieron."""
    async with tenancy.session_for(tenant_id) as sesion:
        filas = await tenancy.fetch_all(sesion, LEER_DEL_CASO, case_id=case_id)
    return tuple(RuleEvaluation.model_validate(dict(fila)) for fila in filas)
