"""La correspondencia entre cada valor del enum y su clave del catalogo.

**Ninguna salida imprime el valor interno de un estado, una resolucion, un tipo
de registro o un motivo de derivacion** (SEC-U4.15, BR3.6, AC4.10.2).
`awaiting_insured` no es texto para una persona: es un valor cerrado del modelo,
y la etiqueta que se lee sale del catalogo en su idioma.

**La correspondencia se escribe entera, valor por valor, y no se compone.** Una
clave armada con `f"case.state.{estado.value}"` seria mas corta y romperia dos
cosas a la vez: el chequeo que exige que cada clave del catalogo tenga un
consumidor **literal** en el codigo dejaria de encontrarlas --y las daria por
muertas--, y un valor de enum nuevo sin su clave no fallaria en ningun sitio,
solo saldria vacio en pantalla.

Aqui, en cambio, el valor nuevo sin clave hace fallar la prueba que compara los
dos conjuntos, y la clave sin valor hace fallar el chequeo del catalogo. Los dos
sentidos cubiertos, que es lo que hace util una correspondencia.
"""

from __future__ import annotations

from untangle.case_record.models import (
    CaseState,
    DerivationReason,
    RecordType,
    Resolution,
)
from untangle.copy_catalog.api import CopyKey

#: Lo que se muestra en lugar de un campo que no se pudo descifrar.
FIELD_UNAVAILABLE = CopyKey("case.field_unavailable")

STATE_KEYS: dict[CaseState, CopyKey] = {
    CaseState.OPEN: CopyKey("case.state.open"),
    CaseState.CAPTURING: CopyKey("case.state.capturing"),
    CaseState.VERIFYING: CopyKey("case.state.verifying"),
    CaseState.DECIDING: CopyKey("case.state.deciding"),
    CaseState.DERIVED: CopyKey("case.state.derived"),
    CaseState.AWAITING_INSURED: CopyKey("case.state.awaiting_insured"),
    CaseState.CLOSED: CopyKey("case.state.closed"),
}

RESOLUTION_KEYS: dict[Resolution, CopyKey] = {
    Resolution.REGISTERED: CopyKey("case.resolution.registered"),
    Resolution.APPROVED: CopyKey("case.resolution.approved"),
    Resolution.REJECTED: CopyKey("case.resolution.rejected"),
    Resolution.SENT_TO_INSURER: CopyKey("case.resolution.sent_to_insurer"),
}

RECORD_TYPE_KEYS: dict[RecordType, CopyKey] = {
    RecordType.CLAIM: CopyKey("case.record_type.claim"),
    RecordType.COVERAGE_INQUIRY: CopyKey("case.record_type.coverage_inquiry"),
    RecordType.QUOTE_REQUEST: CopyKey("case.record_type.quote_request"),
}

#: La etiqueta de cada campo del caso. La pide la bandeja (U14): una pantalla que
#: mostrara `vehicle_and_driver` estaria imprimiendo el valor interno de un campo,
#: que es lo mismo que SEC-U4.15 prohibe de los estados.
#:
#: **Va aqui y no en la interfaz** porque el juego de campos lo declara
#: `schema/fields.yaml`, que es de esta unidad: su prueba compara los dos
#: conjuntos en los dos sentidos, asi que un campo nuevo sin etiqueta falla aqui y
#: una etiqueta sin campo tambien. Una tabla en la interfaz no podria comprobar
#: ninguna de las dos cosas, y la bandeja recibe la clave por el cable.
FIELD_KEYS: dict[str, CopyKey] = {
    "identity_and_policy": CopyKey("case.field.identity_and_policy"),
    "incident_datetime": CopyKey("case.field.incident_datetime"),
    "location": CopyKey("case.field.location"),
    "description": CopyKey("case.field.description"),
    "vehicle_and_driver": CopyKey("case.field.vehicle_and_driver"),
    "other_parties": CopyKey("case.field.other_parties"),
    "injuries": CopyKey("case.field.injuries"),
    "question_asked": CopyKey("case.field.question_asked"),
    # La solicitud de cotizacion (U19). Un campo por clave del esquema, en los dos
    # sentidos: la prueba que compara los dos conjuntos falla ante uno sin etiqueta.
    "driver_name": CopyKey("case.field.driver_name"),
    "driver_birth_date": CopyKey("case.field.driver_birth_date"),
    "license_years": CopyKey("case.field.license_years"),
    "license_jurisdiction": CopyKey("case.field.license_jurisdiction"),
    "vehicle_year": CopyKey("case.field.vehicle_year"),
    "vehicle_make": CopyKey("case.field.vehicle_make"),
    "vehicle_model": CopyKey("case.field.vehicle_model"),
    "vin": CopyKey("case.field.vin"),
    "salvage_title": CopyKey("case.field.salvage_title"),
    "vehicle_age_years": CopyKey("case.field.vehicle_age_years"),
    "use_type": CopyKey("case.field.use_type"),
    "annual_mileage_band": CopyKey("case.field.annual_mileage_band"),
    "garaging_jurisdiction": CopyKey("case.field.garaging_jurisdiction"),
    "at_fault_losses_3y": CopyKey("case.field.at_fault_losses_3y"),
    "claims_3y": CopyKey("case.field.claims_3y"),
    "prior_coverage_active": CopyKey("case.field.prior_coverage_active"),
    "lapse_months": CopyKey("case.field.lapse_months"),
}

DERIVATION_REASON_KEYS: dict[DerivationReason, CopyKey] = {
    DerivationReason.DEMO_LIMIT: CopyKey("case.derivation_reason.demo_limit"),
    DerivationReason.PERSON_REQUESTED: CopyKey("case.derivation_reason.person_requested"),
    DerivationReason.RULE: CopyKey("case.derivation_reason.rule"),
}


def all_keys() -> frozenset[CopyKey]:
    """Todas las claves que este modulo promete que el catalogo trae."""
    return frozenset(
        [
            FIELD_UNAVAILABLE,
            *STATE_KEYS.values(),
            *RESOLUTION_KEYS.values(),
            *RECORD_TYPE_KEYS.values(),
            *DERIVATION_REASON_KEYS.values(),
            *FIELD_KEYS.values(),
        ]
    )
