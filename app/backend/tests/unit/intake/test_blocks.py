"""BR3.2, BR3.3, FD-U11-1: el bloque que toca, deducido del caso."""

from __future__ import annotations

from untangle.case_record.models import CaseState, Completeness, RecordType
from untangle.orchestration.nodes.intake import blocks

_CAMPOS_SINIESTRO = (
    "identity_and_policy",
    "incident_datetime",
    "location",
    "description",
    "vehicle_and_driver",
    "other_parties",
    "injuries",
)


def _completitud(**dichos: bool) -> Completeness:
    """Una `Completeness` de siniestro, con los campos nombrados en `True`."""
    por_campo = {clave: dichos.get(clave, False) for clave in _CAMPOS_SINIESTRO}
    return Completeness(per_field=por_campo, complete=sum(por_campo.values()), total=len(por_campo))


def test_nada_confirmado_pide_seguridad_primero() -> None:
    completitud = _completitud()
    assert (
        blocks.next_block(RecordType.CLAIM, completitud, CaseState.CAPTURING) is blocks.Block.SAFETY
    )


def test_el_bloque_se_deduce_del_caso_y_no_de_un_contador() -> None:
    """La prueba que aisla BR3.2: mismo caso, dos corridas, la misma pregunta.

    No hay ningun argumento de "turno numero N" en la firma de `next_block` --
    la unica entrada es el estado del caso -- asi que dos llamadas con la
    misma completitud tienen que devolver, siempre, el mismo bloque.
    """
    completitud = _completitud(injuries=True, identity_and_policy=True)
    primera = blocks.next_block(RecordType.CLAIM, completitud, CaseState.CAPTURING)
    segunda = blocks.next_block(RecordType.CLAIM, completitud, CaseState.CAPTURING)
    assert primera is segunda is blocks.Block.WHAT_HAPPENED


def test_cuando_y_donde_es_un_solo_bloque_de_dos_campos() -> None:
    completitud = _completitud(injuries=True, identity_and_policy=True, description=True)
    assert (
        blocks.next_block(RecordType.CLAIM, completitud, CaseState.CAPTURING)
        is blocks.Block.WHEN_AND_WHERE
    )


def test_un_dato_adelantado_no_vuelve_a_pedirse_en_su_bloque() -> None:
    """BR3.3: `location` ya llego adelantada; el bloque solo pide `incident_datetime`."""
    completitud = _completitud(
        injuries=True, identity_and_policy=True, description=True, location=True
    )
    assert blocks.missing_fields_in_block(
        RecordType.CLAIM, blocks.Block.WHEN_AND_WHERE, completitud
    ) == ("incident_datetime",)


def test_todo_confirmado_pide_la_confirmacion_final() -> None:
    completitud = _completitud(**dict.fromkeys(_CAMPOS_SINIESTRO, True))
    assert (
        blocks.next_block(RecordType.CLAIM, completitud, CaseState.CAPTURING)
        is blocks.Block.FINAL_CONFIRMATION
    )


def test_un_estado_fuera_de_captura_es_bloque_terminado() -> None:
    """Un caso derivado a mitad de captura no tiene mas bloque que preguntar."""
    completitud = _completitud(injuries=True)
    assert blocks.next_block(RecordType.CLAIM, completitud, CaseState.DERIVED) is blocks.Block.DONE


def test_consulta_de_cobertura_no_pide_bloque_de_seguridad() -> None:
    """AC1.3.6: sin pregunta de seguridad, el primer bloque es identidad y poliza."""
    completitud = Completeness(
        per_field={"identity_and_policy": False, "question_asked": False}, complete=0, total=2
    )
    assert (
        blocks.next_block(RecordType.COVERAGE_INQUIRY, completitud, CaseState.CAPTURING)
        is blocks.Block.IDENTITY_AND_POLICY
    )


def test_una_pregunta_de_cobertura_a_mitad_no_mueve_el_bloque_en_curso() -> None:
    """La prueba que aisla BR4.2: la pregunta de cobertura no escribe ningun
    campo del siniestro, asi que la completitud es identica antes y despues
    -- y con ella, el bloque que toca."""
    completitud = _completitud(injuries=True, identity_and_policy=True)
    antes = blocks.next_block(RecordType.CLAIM, completitud, CaseState.CAPTURING)

    # La pregunta de cobertura la responde U8, en el ritmo de fondo (BR4.2);
    # no toca `case_field` del siniestro, asi que la completitud no cambia.
    despues_de_la_interrupcion = completitud

    despues = blocks.next_block(RecordType.CLAIM, despues_de_la_interrupcion, CaseState.CAPTURING)
    assert antes is despues is blocks.Block.WHAT_HAPPENED
