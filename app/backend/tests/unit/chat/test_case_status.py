"""Donde va el caso de la conversacion: la parte pura (decision de Miguel, 2026-10-06)."""

from __future__ import annotations

from untangle.case_record.api import CaseView
from untangle.case_record.models import CaseState, Channel, Completeness, Origin, RecordType
from untangle.chat import case_status


def _vista(*, complete: int, total: int, state: CaseState = CaseState.CAPTURING) -> CaseView:
    return CaseView(
        case_id="caso-1",
        case_number="STO-000123",
        record_type=RecordType.CLAIM,
        state=state,
        resolution=None,
        channel=Channel.CHAT,
        origin=Origin.PUBLIC_CHAT,
        language="es",
        policy_ref=None,
        derivation_reason=None,
        derived_turn_id=None,
        completeness=Completeness(
            per_field={f"campo_{i}": i < complete for i in range(total)},
            complete=complete,
            total=total,
        ),
    )


def test_el_estado_dice_que_bloque_esta_preguntando_la_agente() -> None:
    """Con la seguridad respondida, lo que toca es la identidad y la poliza: es
    cuando la pantalla ofrece la poliza de ejemplo (P3)."""
    vista = _vista(complete=1, total=7)
    vista = CaseView(
        **{
            **vista.__dict__,
            "completeness": Completeness(
                per_field={"injuries": True, **{f"campo_{i}": False for i in range(6)}},
                complete=1,
                total=7,
            ),
        }
    )
    # El esquema real del siniestro, no campos inventados: el bloque sale de el.
    from untangle.case_record import fields

    claves = [d.key for d in fields.definitions_for(RecordType.CLAIM)]
    vista = CaseView(
        **{
            **vista.__dict__,
            "completeness": Completeness(
                per_field={clave: clave == "injuries" for clave in claves},
                complete=1,
                total=len(claves),
            ),
        }
    )

    estado = case_status.view_of(vista, case_link=None)

    assert estado.pending_block == "identity_and_policy"
    assert estado.policy_ref is None


def test_el_estado_lleva_numero_avance_y_enlace_tal_cual() -> None:
    estado = case_status.view_of(_vista(complete=2, total=7), case_link="/c#token")

    assert estado.case_number == "STO-000123"
    assert estado.state == "capturing"
    assert (estado.complete, estado.total) == (2, 7)
    assert estado.case_link == "/c#token"


def test_sin_clave_de_enlace_el_avance_se_ve_igual() -> None:
    """Ver que el caso avanza no depende de poder abrirlo."""
    estado = case_status.view_of(_vista(complete=0, total=7), case_link=None)

    assert estado.case_link is None
    assert estado.total == 7


def test_el_estado_dice_que_datos_del_siniestro_ya_quedaron_anotados() -> None:
    """Lo que la agente lleva anotado (2026-10-09): cada dato en su orden, con su
    etiqueta del catalogo y si ya quedo; nunca su valor."""
    from untangle.case_record import fields

    claves = [d.key for d in fields.definitions_for(RecordType.CLAIM)]
    vista = CaseView(
        **{
            **_vista(complete=1, total=len(claves)).__dict__,
            "completeness": Completeness(
                per_field={clave: clave == "injuries" for clave in claves},
                complete=1,
                total=len(claves),
            ),
        }
    )

    estado = case_status.view_of(vista, case_link=None)

    assert [c.field_key for c in estado.fields] == claves
    assert [c.field_key for c in estado.fields if c.done] == ["injuries"]
    assert all(c.label_key.startswith("case.field.") for c in estado.fields)


def test_un_caso_en_revision_sigue_dando_su_enlace_y_ya_no_tiene_nada_que_preguntar() -> None:
    """US1.17: al cerrar la captura el caso pasa por `verifying` y `deciding` antes de cerrarse
    o llegar a un ajustador. El enlace de arriba no depende del estado, y la pantalla no ofrece
    la poliza de ejemplo ni espera otro dato."""
    for estado in (CaseState.VERIFYING, CaseState.DECIDING):
        resultado = case_status.view_of(
            _vista(complete=5, total=5, state=estado), case_link="/c#token"
        )

        assert resultado.state == estado.value
        assert resultado.case_link == "/c#token"
        assert resultado.pending_block is None
