"""El elegidor sembrado: mismo flujo, mismas elecciones; flujos distintos, independientes (BR1.2)."""

from __future__ import annotations

import pytest

from untangle.synthetic_data.chooser import ChooserFactory, SeededChooser

SEMILLA = 20260916


def _secuencia(elegidor: SeededChooser, n: int = 20) -> list[int]:
    return [elegidor.below(1000) for _ in range(n)]


def test_la_misma_semilla_y_la_misma_salida_dan_las_mismas_elecciones() -> None:
    uno = ChooserFactory(SEMILLA).for_output("tenants/stonecroft/issued_policies/POL-11.json")
    otro = ChooserFactory(SEMILLA).for_output("tenants/stonecroft/issued_policies/POL-11.json")

    assert _secuencia(uno) == _secuencia(otro)


def test_pedir_el_flujo_de_otra_salida_no_mueve_el_de_esta() -> None:
    """Es la propiedad que deja anadir un archivo sin cambiar los demas."""
    sola = ChooserFactory(SEMILLA)
    esperado = _secuencia(sola.for_output("a.json"))

    acompanada = ChooserFactory(SEMILLA)
    _secuencia(acompanada.for_output("nueva.json"), 50)
    assert _secuencia(acompanada.for_output("a.json")) == esperado


def test_salidas_semillas_y_propositos_distintos_dan_flujos_distintos() -> None:
    fabrica = ChooserFactory(SEMILLA)
    base = _secuencia(fabrica.for_output("a.json"))

    assert _secuencia(fabrica.for_output("b.json")) != base
    assert _secuencia(fabrica.for_output("a.json", purpose="vehiculos")) != base
    assert _secuencia(ChooserFactory(SEMILLA + 1).for_output("a.json")) != base


def test_un_flujo_no_se_entrega_dos_veces_en_una_generacion() -> None:
    fabrica = ChooserFactory(SEMILLA)
    fabrica.for_output("a.json")

    with pytest.raises(ValueError, match=r"el flujo 'a\.json' ya se entrego"):
        fabrica.for_output("a.json")


def test_las_elecciones_respetan_sus_limites_y_no_repiten_en_una_muestra() -> None:
    elegidor = ChooserFactory(SEMILLA).for_output("limites.json")

    assert all(0 <= elegidor.below(7) < 7 for _ in range(500))
    assert all(3 <= elegidor.between(3, 5) <= 5 for _ in range(500))
    muestra = elegidor.sample(list(range(40)), 10)
    assert len(set(muestra)) == 10
    assert sorted(elegidor.shuffled(["x", "y", "z"])) == ["x", "y", "z"]
    assert len(elegidor.digits(6)) == 6
    assert elegidor.digits(6).isdigit()


def test_las_elecciones_se_reparten_sin_sesgo_evidente() -> None:
    """Con el modulo directo, los numeros bajos saldrian mas: aqui los tres por igual."""
    elegidor = ChooserFactory(SEMILLA).for_output("reparto.json")
    cuentas = [0, 0, 0]
    for _ in range(3000):
        cuentas[elegidor.below(3)] += 1

    assert all(900 < cuenta < 1100 for cuenta in cuentas)


def test_pedir_lo_imposible_falla_en_vez_de_inventar() -> None:
    elegidor = ChooserFactory(SEMILLA).for_output("imposible.json")

    with pytest.raises(ValueError, match="no hay ningun entero"):
        elegidor.below(0)
    with pytest.raises(ValueError, match="no hay nada que elegir"):
        elegidor.choice([])
    with pytest.raises(ValueError, match="no se pueden elegir 4 de 3"):
        elegidor.sample([1, 2, 3], 4)
    with pytest.raises(ValueError, match="esta vacio"):
        elegidor.between(5, 4)
