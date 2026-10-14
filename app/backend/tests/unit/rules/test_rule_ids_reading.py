"""Que reglas leen un campo: lo que la bandeja usa para no contarle al asegurado una anotacion.

Con los conjuntos reales de las aseguradoras, por identificador: la prueba que importa es
que el identificador de la regla de fraude --y no el de heridos, que la persona conto con
sus palabras-- sea el que queda fuera.
"""

from __future__ import annotations

import pytest

from untangle.rules import api as reglas
from untangle.rules.models import RuleNotConfiguredError

ANOTADOS = frozenset({"claim_amount", "coverage_disputed", "fraud_suspected"})


def test_las_reglas_de_dinero_cobertura_y_fraude_de_una_aseguradora() -> None:
    leen = reglas.rule_ids_reading(tenant_id="stonecroft", fields=ANOTADOS)

    # Cobertura, los dos umbrales de monto, fraude y el monto bajo.
    assert leen == {"STO-R-01", "STO-R-02", "STO-R-03", "STO-R-06", "STO-R-08"}


def test_una_regla_que_lee_lo_que_dijo_la_persona_no_se_cuenta() -> None:
    """Heridos y terceros pendientes los conto la persona: su regla no es una anotacion."""
    leen = reglas.rule_ids_reading(tenant_id="stonecroft", fields=ANOTADOS)

    assert "STO-R-04" not in leen
    assert "STO-R-05" not in leen
    assert "STO-R-10" not in leen, "la regla por defecto no lee ningun campo"


def test_las_reglas_de_cierre_directo_de_otra_aseguradora_tampoco_se_cuentan() -> None:
    """El cierre directo de Sunmeadow lee heridos y terceros: no es de lo anotado."""
    leen = reglas.rule_ids_reading(tenant_id="sunmeadow", fields=ANOTADOS)

    assert "SUN-R-01" not in leen
    assert {"SUN-R-02", "SUN-R-03", "SUN-R-04", "SUN-R-07", "SUN-R-09"} <= leen


def test_sin_campos_no_hay_reglas() -> None:
    assert reglas.rule_ids_reading(tenant_id="stonecroft", fields=frozenset()) == frozenset()


def test_una_aseguradora_sin_reglas_cargadas_lo_dice() -> None:
    with pytest.raises(RuleNotConfiguredError):
        reglas.rule_ids_reading(tenant_id="no-existe", fields=ANOTADOS)
