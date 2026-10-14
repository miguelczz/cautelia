"""BR5.5, FD-U11-7: una version que contradice no reemplaza el valor confirmado."""

from __future__ import annotations

from untangle.orchestration.nodes.intake import contradictions


def test_una_version_distinta_de_la_confirmada_es_contradiccion() -> None:
    assert contradictions.is_contradiction("2026-12-15", "2026-10-15") is True


def test_la_misma_version_no_es_contradiccion() -> None:
    assert contradictions.is_contradiction("2026-12-15", "2026-12-15") is False


def test_sin_valor_confirmado_todavia_no_hay_nada_que_contradecir() -> None:
    """La prueba que aisla BR5.5: la primera version nunca es 'la segunda'."""
    assert contradictions.is_contradiction(None, "2026-10-15") is False


def test_el_mismo_dato_escrito_distinto_no_es_una_contradiccion() -> None:
    """BR5.5: "12 de Marzo" y "12 de marzo" son el mismo dato dicho dos veces.

    Anotarlos como version alterna le pondria al caso una contradiccion que
    nadie dijo, y la regla de la aseguradora que mira si existe una version
    alterna es la que puede derivar el caso.
    """
    assert not contradictions.is_contradiction("12 de marzo", "12 de Marzo")
    assert contradictions.is_contradiction("12 de marzo", "13 de marzo")
