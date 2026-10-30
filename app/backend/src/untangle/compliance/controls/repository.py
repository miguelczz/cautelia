"""Donde se guardan la divulgacion, las intervenciones y la revision (BR4.2, BR6.3).

**Ninguna conexion propia.** Toda consulta pasa por el punto unico de sesion de
U2, con la aseguradora fijada: las tres tablas llevan politica, y sin
aseguradora no se veria ni se escribiria ninguna fila. Los parametros se ligan;
nada se arma por concatenacion. Un contrato de importacion falla ante cualquier
apertura de conexion plantada aqui.

## Las tres escrituras son idempotentes

El nodo `compliance` se vuelve a ejecutar entero al reanudar tras `interrupt()`
(C-15), y el registro de la divulgacion puede llegar dos veces si la apertura se
reintenta. Ninguna de las dos cosas puede dejar filas de mas, y ninguna necesita
leer antes de escribir: la unicidad la impone la tabla y la escritura la respeta
con `ON CONFLICT DO NOTHING`, sin ventana entre leer y escribir.

- **La divulgacion**, una por caso y canal (BR4.2). Devuelve si esta fue la que
  quedo.
- **La intervencion**, una por identificador. El identificador lo elige quien
  llama, asi que reintentar con el mismo no la duplica.
- **La revision**, una por caso y turno revisado (BR6.3). La primera de ese punto
  es la que queda, y se devuelve la guardada: la reejecucion no crea otra ni
  reescribe la que ya existe.

Si algo falla, levanta. Decidir que hacer con el fallo es de quien llama, que es
quien sabe si el turno puede seguir (convencion 8b del equipo).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from untangle.compliance.controls.models import (
    ComplianceReview,
    DisclosureRecord,
    GuardIntervention,
)
from untangle.tenancy import api as tenancy

INSERTAR_DIVULGACION = """
    INSERT INTO disclosure_record (disclosure_id, tenant_id, case_id, channel, language,
                                   catalog_key, disclosed_at)
    VALUES (:disclosure_id, :tenant_id, :case_id, :channel, :language,
            :catalog_key, :disclosed_at)
    ON CONFLICT (case_id, channel) DO NOTHING
    RETURNING disclosure_id
"""

INSERTAR_INTERVENCION = """
    INSERT INTO guard_intervention (intervention_id, tenant_id, case_id, turn_id, category,
                                    pattern_id, action, catalog_key, occurred_at)
    VALUES (:intervention_id, :tenant_id, :case_id, :turn_id, :category,
            :pattern_id, :action, :catalog_key, :occurred_at)
    ON CONFLICT (intervention_id) DO NOTHING
    RETURNING intervention_id
"""

INSERTAR_REVISION = """
    INSERT INTO compliance_review (review_id, tenant_id, case_id, disclosure_ok,
                                   human_route_ok, explainability_ok, findings,
                                   reviewed_through_turn, reviewed_at)
    VALUES (:review_id, :tenant_id, :case_id, :disclosure_ok,
            :human_route_ok, :explainability_ok, CAST(:findings AS varchar[]),
            :reviewed_through_turn, :reviewed_at)
    ON CONFLICT (case_id, reviewed_through_turn) DO NOTHING
    RETURNING review_id
"""

LEER_DIVULGACIONES = """
    SELECT disclosure_id, tenant_id, case_id, channel, language, catalog_key, disclosed_at
    FROM disclosure_record
    WHERE case_id = :case_id
    ORDER BY disclosed_at, channel
"""

LEER_INTERVENCIONES = """
    SELECT intervention_id, tenant_id, case_id, turn_id, category, pattern_id, action,
           catalog_key, occurred_at
    FROM guard_intervention
    WHERE case_id = :case_id
    ORDER BY occurred_at, intervention_id
"""

#: La revision mas reciente de un caso (enmienda aditiva a C-20, 2026-09-28).
#:
#: La de abajo pide el turno hasta el que se reviso, que es lo que necesita quien
#: **escribe** la revision --para no repetir la del mismo punto--. Quien la **lee**
#: al abrir un caso no conoce ese turno: lo que quiere es el resultado vigente de
#: los controles. Pedida por U14 para su sexto bloque.
LEER_ULTIMA_REVISION = """
    SELECT review_id, tenant_id, case_id, disclosure_ok, human_route_ok,
           explainability_ok, findings, reviewed_through_turn, reviewed_at
    FROM compliance_review
    WHERE case_id = :case_id
    ORDER BY reviewed_at DESC, review_id DESC
    LIMIT 1
"""

LEER_REVISION = """
    SELECT review_id, tenant_id, case_id, disclosure_ok, human_route_ok,
           explainability_ok, findings, reviewed_through_turn, reviewed_at
    FROM compliance_review
    WHERE case_id = :case_id AND reviewed_through_turn = :reviewed_through_turn
"""


def _parametros(modelo: DisclosureRecord | GuardIntervention | ComplianceReview) -> dict[str, Any]:
    """Los valores de la fila, listos para ligar.

    El volcado a JSON deja los enums como su texto y los hallazgos como lista,
    que es lo que la base espera. Las marcas de tiempo se devuelven como el
    instante que eran, con su zona, y no como la cadena del volcado: convertirla
    de vuelta seria abrir la puerta a perder la zona.
    """
    volcado = modelo.model_dump(mode="json")
    return {
        campo: original if isinstance(original := getattr(modelo, campo), datetime) else valor
        for campo, valor in volcado.items()
    }


async def record_disclosure(registro: DisclosureRecord) -> bool:
    """Registra la divulgacion si el caso no la tenia en ese canal (BR4.1, BR4.2).

    Devuelve si esta fue la que quedo. `False` no es un error: es la segunda vez
    que el mismo caso registra el mismo canal, y la primera sigue en su sitio.
    """
    async with tenancy.session_for(registro.tenant_id) as sesion:
        nueva = await tenancy.fetch_one(sesion, INSERTAR_DIVULGACION, **_parametros(registro))
    return nueva is not None


async def record_intervention(intervencion: GuardIntervention) -> bool:
    """Registra una intervencion de la guardia, sin la frase original (BR1.6).

    Devuelve si esta fue la que quedo: reintentar con el mismo identificador no
    crea otra fila.
    """
    async with tenancy.session_for(intervencion.tenant_id) as sesion:
        nueva = await tenancy.fetch_one(sesion, INSERTAR_INTERVENCION, **_parametros(intervencion))
    return nueva is not None


async def save_review(revision: ComplianceReview) -> ComplianceReview:
    """Guarda la revision por su clave (caso, turno revisado) y devuelve la guardada (BR6.3).

    Si ese punto ya tenia revision, no se escribe otra ni se reescribe la que
    habia: se devuelve la guardada. Asi la reejecucion del nodo al reanudar
    produce exactamente una fila y el llamador ve siempre la que quedo.

    La insercion y la lectura van en la misma transaccion: entre las dos no hay
    ventana en la que otra ejecucion pudiera cambiar lo que se devuelve.
    """
    async with tenancy.session_for(revision.tenant_id) as sesion:
        nueva = await tenancy.fetch_one(sesion, INSERTAR_REVISION, **_parametros(revision))
        if nueva is not None:
            return revision
        guardada = await tenancy.fetch_one(
            sesion,
            LEER_REVISION,
            case_id=revision.case_id,
            reviewed_through_turn=revision.reviewed_through_turn,
        )
    if guardada is None:  # pragma: no cover -- el conflicto garantiza que existe
        msg = (
            f"la revision del caso '{revision.case_id}' hasta el turno "
            f"'{revision.reviewed_through_turn}' choco con otra y no se pudo leer"
        )
        raise LookupError(msg)
    return ComplianceReview.model_validate(dict(guardada))


async def disclosures(tenant_id: str, case_id: str) -> tuple[DisclosureRecord, ...]:
    """Las divulgaciones registradas del caso, en el orden en que salieron.

    Un caso de otra aseguradora y uno inexistente responden igual --vacio--
    porque la politica de fila filtra antes de que este codigo lo vea.
    """
    async with tenancy.session_for(tenant_id) as sesion:
        filas = await tenancy.fetch_all(sesion, LEER_DIVULGACIONES, case_id=case_id)
    return tuple(DisclosureRecord.model_validate(dict(fila)) for fila in filas)


async def interventions(tenant_id: str, case_id: str) -> tuple[GuardIntervention, ...]:
    """Las intervenciones de la guardia en el caso, en el orden en que ocurrieron."""
    async with tenancy.session_for(tenant_id) as sesion:
        filas = await tenancy.fetch_all(sesion, LEER_INTERVENCIONES, case_id=case_id)
    return tuple(GuardIntervention.model_validate(dict(fila)) for fila in filas)


async def latest_review(tenant_id: str, case_id: str) -> ComplianceReview | None:
    """La revision vigente de los cuatro controles de un caso, o nada si no se hizo.

    "Nada" es una respuesta valida y no un fallo: un caso derivado antes de que la
    revision completa corriera no tiene resultado, y la bandeja dice eso en vez de
    inventar cuatro verdes.
    """
    async with tenancy.session_for(tenant_id) as sesion:
        fila = await tenancy.fetch_one(sesion, LEER_ULTIMA_REVISION, case_id=case_id)
    return ComplianceReview.model_validate(dict(fila)) if fila is not None else None


async def review_through(
    tenant_id: str, case_id: str, reviewed_through_turn: str
) -> ComplianceReview | None:
    """La revision del caso hasta ese turno, o nada si todavia no se hizo."""
    async with tenancy.session_for(tenant_id) as sesion:
        fila = await tenancy.fetch_one(
            sesion,
            LEER_REVISION,
            case_id=case_id,
            reviewed_through_turn=reviewed_through_turn,
        )
    return ComplianceReview.model_validate(dict(fila)) if fila is not None else None
