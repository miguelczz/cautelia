"""Las otras partes del accidente: lo que se supo, y lo que no (BR1.7, FR1.2).

**Un atributo que no se sabe queda vacio y es un dato pendiente, nunca un valor
supuesto** (BR1.8, AC1.8.2). Es la regla entera de este archivo. Un nombre
inventado para que la ficha se vea completa es peor que un hueco: el hueco se ve
y se pregunta; el invento se cita.

Los tres atributos personales --nombre, contacto y placa-- se sellan aqui, en un
solo acto y con una sola clave, y por eso la fila lleva un identificador de
clave y no tres: se escriben juntos.

**La placa lleva su propio estado y su propia evidencia** (decision de U4). Una
placa que se oyo mal y no se confirmo no cuenta como completa, y distinguirlo
importa porque una placa equivocada manda a la aseguradora a perseguir a otra
persona.
"""

from __future__ import annotations

from dataclasses import dataclass

from untangle.case_record.crypto import Cipher
from untangle.case_record.models import (
    CaseId,
    CaseParty,
    FieldStatus,
    PartyId,
    PartyRole,
    TurnId,
)


@dataclass(frozen=True)
class PlateReading:
    """La placa del otro vehiculo, con cuanto se confia en ella.

    `value` viene en claro y se sella al registrar: es el ultimo sitio del
    camino donde existe legible, y vive aqui unos milisegundos a proposito.
    """

    value: str
    status: FieldStatus
    evidence_turn_id: TurnId


@dataclass(frozen=True)
class PartyDetails:
    """Lo que se supo de la otra parte, en claro, un instante antes de sellarse.

    Todo opcional, y ninguno se rellena. La ausencia es informacion: dice que
    nadie lo pregunto o que la persona no lo sabia, y las dos cosas son datos
    que el ajustador necesita.
    """

    name: str | None = None
    contact: str | None = None
    plate: PlateReading | None = None
    injury_status: str | None = None
    vehicle_description: str | None = None
    statement_version: str | None = None
    #: La relacion de quien reporta con el asegurado, **ya redactada** por
    #: quien llama (U11, FD-U11-5): este modulo no importa el modulo de
    #: redaccion de U3 -- solo sella y guarda, la misma frontera que ya
    #: respetaba con `name` y `contact`.
    relation: str | None = None


def register_party(
    *, case_id: CaseId, party_id: PartyId, role: PartyRole, details: PartyDetails, cipher: Cipher
) -> CaseParty:
    """Registra una parte, sellando sus tres atributos personales.

    El cifrador entra por parametro y no se resuelve aqui dentro: es lo que
    permite que una prueba use su propia clave, y lo que impide que este archivo
    conozca de donde sale la de verdad.

    `relation` no se sella: sigue el precedente de `injury_status` y
    `vehicle_description`, las otras dos columnas de texto libre de esta tabla
    (`u11_intake_0001_reporter_party`).
    """
    placa = details.plate
    return CaseParty(
        party_id=party_id,
        case_id=case_id,
        role=role,
        name=cipher.seal(details.name) if details.name else None,
        contact=cipher.seal(details.contact) if details.contact else None,
        plate=cipher.seal(placa.value) if placa else None,
        plate_status=placa.status if placa else FieldStatus.NOT_STATED,
        plate_evidence_turn_id=placa.evidence_turn_id if placa else None,
        injury_status=details.injury_status,
        vehicle_description=details.vehicle_description,
        statement_version=details.statement_version,
        relation=details.relation,
    )
