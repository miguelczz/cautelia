"""La pregunta que la agente dejo en el aire, sacada de lo que dijo."""

from __future__ import annotations

import pytest

from untangle.voice.pending_question import last_question


@pytest.mark.parametrize(
    ("dicho", "pregunta"),
    [
        ("Para empezar, ¿hubo alguien herido?", "¿hubo alguien herido?"),
        ("Gracias, Marcela. ¿Dónde ocurrió?", "¿Dónde ocurrió?"),
        ("¿Fue ayer? ¿O el lunes?", "¿O el lunes?"),
        ("Thanks, noted. Where did it happen?", "Where did it happen?"),
        ("First, was anyone injured?", "First, was anyone injured?"),
    ],
)
def test_es_la_ultima_pregunta_sin_el_acuse(dicho: str, pregunta: str) -> None:
    assert last_question(dicho) == pregunta


@pytest.mark.parametrize("dicho", ["Gracias, lo anoto.", "Déjame revisar tu póliza.", "", "   "])
def test_lo_que_no_termina_preguntando_no_deja_pregunta(dicho: str) -> None:
    assert last_question(dicho) is None


def test_una_pregunta_en_medio_no_cuenta_si_despues_se_dijo_otra_cosa() -> None:
    """Lo que hay que repetir es lo que quedo en el aire, no lo que ya se cerro."""
    assert last_question("¿Hubo heridos? Lo dejo anotado.") is None
