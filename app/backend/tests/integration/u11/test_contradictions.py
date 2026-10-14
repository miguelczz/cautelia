"""BR5.5, FD-U11-7: dos versiones se guardan las dos, contra la base de verdad.

Se escribe aqui, en la nube, y se corre en la sesion local con Docker
levantado (CG-U11-5): toca `case_record.api.set_field` y `record_change`, que
es lo que la hace de integracion.
"""

from __future__ import annotations

import pytest

from untangle.case_record import api as casos
from untangle.case_record import crypto, history, repository
from untangle.case_record.models import (
    Actor,
    ActorType,
    CaseField,
    ChangeKind,
    FieldStatus,
)
from untangle.orchestration.nodes.intake import contradictions

from .conftest import AHORA, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u11")

_ASEGURADO = Actor(actor_type=ActorType.INSURED)


async def test_la_version_alterna_no_reemplaza_el_valor_confirmado(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    tenant_id = dos_aseguradoras[0]
    caso = await nuevo_caso(tenant_id)

    primero = CaseField(
        case_id=caso.case_id,
        field_key="incident_datetime",
        value=cifrador.seal("2026-12-15"),
        status=FieldStatus.CONFIRMED,
        evidence_turn_id="turno-1",
        confirmed_aloud_at=AHORA,
        updated_at=AHORA,
    )
    await casos.set_field(tenant_id, primero, cipher=cifrador, actor=_ASEGURADO)

    assert contradictions.is_contradiction("2026-12-15", "2026-10-15") is True

    await contradictions.record_alternate_version(
        tenant_id,
        case_id=caso.case_id,
        field_key="incident_datetime",
        text="2026-10-15",
        evidence_turn_id="turno-3",
        now=AHORA,
        cipher=cifrador,
        actor=_ASEGURADO,
    )

    # El campo de verdad sigue siendo el primero confirmado (FD-U11-7): la
    # version alterna no lo toco.
    campos = await repository.load_fields(tenant_id, caso.case_id)
    campo_de_verdad = next(c for c in campos if c.field_key == "incident_datetime")
    assert campo_de_verdad.status is FieldStatus.CONFIRMED
    assert campo_de_verdad.value is not None
    assert cifrador.unseal(campo_de_verdad.value, stored_key_id=cifrador.id) == "2026-12-15"

    # Las dos versiones quedan en el historial, cada una con su turno y su hora.
    historial = await history.of_case(tenant_id, caso.case_id)
    versiones_del_campo = [
        cifrador.unseal(h.new_value, stored_key_id=cifrador.id)
        for h in historial
        if h.field_key == "incident_datetime" and h.new_value is not None
    ]
    assert versiones_del_campo == ["2026-12-15", "2026-10-15"]

    # Y se distinguen: la segunda dice que **no** se acepto. Anotada como
    # `FIELD_SET`, la linea de tiempo del caso mostraria el segundo valor como el
    # vigente -- lo contrario de lo que decide FD-U11-7.
    clases = [h.change_kind for h in historial if h.field_key == "incident_datetime"]
    assert clases == [ChangeKind.FIELD_SET, ChangeKind.FIELD_VERSION_ALTERNATE]
