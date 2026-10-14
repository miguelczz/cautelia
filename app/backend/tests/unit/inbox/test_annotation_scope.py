"""Cuando un caso admite anotaciones para las reglas, y quien puede hacerlas.

Una sola pregunta (`can_annotate`) que contestan la ruta y la vista: si la pantalla
decidiera por su cuenta cuando ofrecer el bloque, el dia que una regla cambie la otra
seguiria diciendo lo de antes. Las tablas son cerradas, y lo que se comprueba es sobre todo
que no les falte ninguna fila.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from untangle.case_record.models import CaseState, RecordType
from untangle.inbox import annotation, decision
from untangle.inbox.triage_notes import TriageNote, TriageValues
from untangle.tenancy import staff_identity
from untangle.tenancy.models import Action, Role


@pytest.mark.parametrize("estado", list(CaseState))
def test_solo_un_siniestro_con_un_ajustador_o_esperando_al_asegurado_admite_anotaciones(
    estado: CaseState,
) -> None:
    esperado = estado in {CaseState.DERIVED, CaseState.AWAITING_INSURED}

    assert annotation.can_annotate(state=estado, record_type=RecordType.CLAIM) is esperado


@pytest.mark.parametrize("tipo", [RecordType.COVERAGE_INQUIRY, RecordType.QUOTE_REQUEST])
@pytest.mark.parametrize("estado", list(CaseState))
def test_lo_que_no_es_un_siniestro_no_admite_anotaciones_en_ningun_estado(
    estado: CaseState, tipo: RecordType
) -> None:
    """Las reglas de triage miran heridos, terceros, monto y fraude de un siniestro."""
    assert annotation.can_annotate(state=estado, record_type=tipo) is False


def test_los_estados_que_admiten_son_exactamente_dos() -> None:
    assert annotation.ANNOTATABLE_STATES == {CaseState.DERIVED, CaseState.AWAITING_INSURED}


def test_el_ajustador_anota_y_los_otros_dos_roles_no() -> None:
    """La anotacion es un juicio del ajustador: la agencia no decide cobertura ni estima
    montos, y el suscriptor lee solicitudes de cotizacion que estas reglas no evaluan."""
    assert staff_identity.is_permitted(Role.ADJUSTER, Action.ANNOTATE_TRIAGE)
    assert not staff_identity.is_permitted(Role.ACCOUNT_AGENT, Action.ANNOTATE_TRIAGE)
    assert not staff_identity.is_permitted(Role.UNDERWRITER, Action.ANNOTATE_TRIAGE)


def _nota(noted_by: str) -> TriageNote:
    return TriageNote(
        values=TriageValues(fraud_suspected=True),
        noted_by=noted_by,
        updated_at=datetime(2026, 10, 13, 12, 0, tzinfo=UTC),
    )


def test_sin_nota_o_con_la_del_visitante_el_visitante_la_lee_y_la_cambia() -> None:
    assert annotation.note_is_visitors(None) is True
    assert annotation.note_is_visitors(_nota(decision.VISITOR_ACTOR_ID)) is True


@pytest.mark.parametrize("persona", ["diana", "marcus-webb", "una-persona-cualquiera"])
def test_la_nota_de_una_persona_de_la_aseguradora_no_es_del_visitante(persona: str) -> None:
    assert annotation.note_is_visitors(_nota(persona)) is False
