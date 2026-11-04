"""Lo que el codigo comprueba de la salida del modelo antes de aceptarla como decision."""

from __future__ import annotations

import pytest

from untangle.adjuster import validation
from untangle.adjuster.errors import ErrorKind


@pytest.mark.parametrize(
    ("texto", "quitar", "esperado"),
    [
        ("Cubre el choque (SM-X.A). Y nada mas.", ["SM-X.A"], "Cubre el choque. Y nada mas."),
        ("Segun [SM-X.A] cubre el choque.", ["SM-X.A"], "Segun cubre el choque."),
        ("Segun SM-X.A cubre el choque.", ["SM-X.A"], "Segun cubre el choque."),
        ("Citas SM-X.AB y SM-X.A.", ["SM-X.A", "SM-X.AB"], "Citas y."),
        ("Sin identificadores aqui.", ["SM-X.A"], "Sin identificadores aqui."),
        ("Cubre (SM-X.A, SM-X.B) el choque.", ["SM-X.A", "SM-X.B"], "Cubre el choque."),
    ],
)
def test_una_cita_quitada_no_deja_su_identificador_en_el_texto(
    texto: str, quitar: list[str], esperado: str
) -> None:
    assert validation.remove_clause_ids(texto, quitar) == esperado


def test_los_motivos_de_un_intento_fallido_son_un_vocabulario_cerrado() -> None:
    assert {kind.value for kind in ErrorKind} >= {
        "action_not_allowed",
        "no_verified_citation",
        "guard_blocked",
        "wrong_language",
        "no_reasons",
        "case_not_found",
        "case_not_decidable",
        "internal_error",
    }
