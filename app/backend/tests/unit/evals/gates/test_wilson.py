"""Pruebas del intervalo de Wilson contra valores calculados a mano (TECH-U21.1).

Sin `scipy`: los valores de referencia salen de aplicar la formula de Wilson a
mano, no de una biblioteca de estadistica.
"""

from __future__ import annotations

import pytest

from untangle.evals.gates.wilson import wilson_lower_bound


def test_diez_de_diez_da_el_limite_conocido() -> None:
    # 1 / (1 + z^2/n) con z=1.959963985 y n=10.
    assert wilson_lower_bound(10, 10) == pytest.approx(0.7224, abs=1e-3)


def test_cinco_de_diez_da_el_limite_conocido() -> None:
    assert wilson_lower_bound(5, 10) == pytest.approx(0.2367, abs=1e-3)


def test_cero_de_diez_da_cero() -> None:
    assert wilson_lower_bound(0, 10) == 0.0


def test_una_muestra_pequena_y_afortunada_no_llega_al_umbral() -> None:
    """FD-U21-4: 4 aciertos de 4 no habilita al juez solo porque la media es 1.0."""
    assert wilson_lower_bound(4, 4) < 0.80


def test_n_cero_es_invalido() -> None:
    with pytest.raises(ValueError, match="n=0"):
        wilson_lower_bound(0, 0)


def test_mas_exitos_que_observaciones_es_invalido() -> None:
    with pytest.raises(ValueError, match="successes"):
        wilson_lower_bound(11, 10)
