"""Lo que el ajustador anota para las reglas: la parte que no necesita base de datos.

Tres cosas: que "sin anotar" no se vuelva "no" por el camino (un insumo ausente no dispara
y uno en falso afirma que se comprobo), que guardar lo mismo otra vez no ensucie el
historial, y que los tres datos sean de verdad campos que alguna regla de cada aseguradora
lee --el hueco que tuvieron: un campo que nadie produce no falla, simplemente no dispara--.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from untangle.inbox import triage_notes
from untangle.inbox.triage_notes import TriageChange, TriageValues
from untangle.rules import loading as rules_loading
from untangle.rules.conditions import fields_read
from untangle.rules.fields import TRIAGE_FIELDS
from untangle.tenancy import config as tenancy_config


@pytest.fixture
def reglas() -> Iterator[None]:
    tenancy_config.reset()
    rules_loading.reset()
    yield
    tenancy_config.reset()
    rules_loading.reset()


# --- Sin anotar no es "no" ------------------------------------------------------------


def test_lo_que_no_esta_anotado_no_llega_a_las_reglas() -> None:
    assert TriageValues().rule_inputs() == {}


def test_un_no_anotado_llega_como_falso_y_no_se_confunde_con_sin_anotar() -> None:
    valores = TriageValues(coverage_disputed=False, fraud_suspected=None)

    assert valores.rule_inputs() == {"coverage_disputed": False}


def test_un_monto_cero_es_un_monto_anotado() -> None:
    """Cero es una estimacion; la ausencia es otra cosa, y `if valor:` las confundiria."""
    assert TriageValues(claim_amount=0).rule_inputs() == {"claim_amount": 0}


def test_los_tres_anotados_llegan_con_los_nombres_del_motor() -> None:
    valores = TriageValues(claim_amount=2500, coverage_disputed=True, fraud_suspected=False)

    assert valores.rule_inputs() == {
        "claim_amount": 2500,
        "coverage_disputed": True,
        "fraud_suspected": False,
    }


@pytest.mark.parametrize("monto", [-1, triage_notes.MAX_CLAIM_AMOUNT + 1, True])
def test_un_monto_fuera_de_rango_no_se_construye(monto: int) -> None:
    with pytest.raises(ValueError, match="monto estimado"):
        TriageValues(claim_amount=monto)


# --- El historial dice lo que cambio, no cuantas veces se pulso guardar ----------------


def test_guardar_lo_mismo_otra_vez_no_cambia_nada() -> None:
    antes = TriageValues(claim_amount=1500, coverage_disputed=True)

    assert triage_notes.changes_between(antes, antes) == ()


def test_la_primera_anotacion_parte_de_sin_anotar() -> None:
    cambios = triage_notes.changes_between(TriageValues(), TriageValues(claim_amount=1500))

    assert cambios == (TriageChange("claim_amount", "unset", "1500"),)


def test_dejar_un_dato_otra_vez_sin_anotar_tambien_es_un_cambio() -> None:
    """La pantalla tiene que poder quitar lo anotado, y eso queda a la vista."""
    antes = TriageValues(fraud_suspected=False)

    cambios = triage_notes.changes_between(antes, TriageValues())

    assert cambios == (TriageChange("fraud_suspected", "false", "unset"),)


def test_de_no_a_si_es_un_cambio_y_de_sin_anotar_a_no_tambien() -> None:
    cambios = triage_notes.changes_between(
        TriageValues(coverage_disputed=False),
        TriageValues(coverage_disputed=True, fraud_suspected=False),
    )

    assert cambios == (
        TriageChange("coverage_disputed", "false", "true"),
        TriageChange("fraud_suspected", "unset", "false"),
    )


def test_varios_cambios_salen_en_el_orden_de_la_pantalla() -> None:
    cambios = triage_notes.changes_between(
        TriageValues(),
        TriageValues(claim_amount=10, coverage_disputed=True, fraud_suspected=True),
    )

    assert [cambio.field_key for cambio in cambios] == list(triage_notes.NOTED_FIELDS)


# --- Son campos de triage que las reglas leen -----------------------------------------


def test_lo_que_se_anota_son_campos_declarados_del_vocabulario_de_triage() -> None:
    assert set(triage_notes.NOTED_FIELDS) <= TRIAGE_FIELDS


def test_lo_anotado_y_lo_derivado_de_la_conversacion_no_se_pisan() -> None:
    """Dos productores del mismo insumo serian dos verdades; aqui cada campo tiene uno."""
    derivados_de_la_conversacion = {"injuries_present", "other_parties_data_pending"}

    assert not set(triage_notes.NOTED_FIELDS) & derivados_de_la_conversacion


@pytest.mark.usefixtures("reglas")
def test_cada_aseguradora_tiene_una_regla_que_lee_cada_dato_anotado() -> None:
    """Sin esto, anotar algo seria escribir una fila que ninguna regla va a mirar."""
    conjuntos = rules_loading.loaded().available
    assert conjuntos, "no hay ningun conjunto de reglas cargado"

    for tenant_id, conjunto in conjuntos.items():
        leidos = frozenset().union(*(fields_read(regla.condition) for regla in conjunto.rules))
        faltan = set(triage_notes.NOTED_FIELDS) - leidos
        assert not faltan, f"'{tenant_id}' no tiene ninguna regla que lea {sorted(faltan)}"
