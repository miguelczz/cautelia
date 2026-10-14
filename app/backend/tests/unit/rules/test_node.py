"""El nodo `decision`: evalua, guarda y pasa a `compliance` (BR3.1, C-15).

El nodo se prueba como lo va a usar el runtime: construido con sus puertos por
closure (reloj y guardado), con un estado de entrada, devolviendo solo su
conjunto de escritura. El guardado es un doble que imita la insercion
`ON CONFLICT DO NOTHING` de `rules/repository.py` -- la persistencia real
tiene sus propias pruebas de integracion (`tests/integration/u9`). `evaluate()`
no se dobla: corre contra las tres aseguradoras reales de la configuracion
(`app/config/tenants/`), para que estas pruebas midan el motor de verdad.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from untangle.compliance.controls import phrases
from untangle.orchestration.nodes.decision.node import (
    DECISION_SPEC,
    DecisionNode,
    DecisionNodeInput,
    DecisionNodeOutput,
    next_node,
)
from untangle.orchestration.state import NodeSpec, NodeSpecError
from untangle.rules.api import RuleEvaluation
from untangle.rules.fields import RuleValue
from untangle.telemetry.traces.models import NodeName

AHORA = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


class _Almacen:
    """El puerto de guardado: una fila por identificador, como `ON CONFLICT DO NOTHING`."""

    def __init__(self) -> None:
        self.filas: dict[str, RuleEvaluation] = {}
        self.llamadas = 0

    async def __call__(self, evaluation: RuleEvaluation) -> RuleEvaluation:
        self.llamadas += 1
        return self.filas.setdefault(evaluation.evaluation_id, evaluation)


def _nodo(almacen: _Almacen | None = None) -> tuple[DecisionNode, _Almacen]:
    almacen = almacen if almacen is not None else _Almacen()
    return DecisionNode(clock=lambda: AHORA, save=almacen), almacen


def _estado(tenant_id: str, *, case_id: str = "caso-1", **inputs: RuleValue) -> DecisionNodeInput:
    return DecisionNodeInput(tenant_id=tenant_id, case_id=case_id, inputs=inputs)


async def test_stonecroft_con_heridos_deriva_sin_dinero() -> None:
    """CG-U9-1: Stonecroft es estricta y deriva heridos sin ninguna otra senal."""
    nodo, _ = _nodo()

    salida = await nodo.run(_estado("stonecroft", injuries_present=True))

    assert salida.category == "referral"
    assert salida.closable is False
    assert any(regla.id == "STO-R-04" for regla in salida.fired_rules)


async def test_stonecroft_sin_ninguna_senal_va_a_revision_estandar() -> None:
    """BR1.3, BR2.2: solo dispara la regla por defecto."""
    nodo, _ = _nodo()

    salida = await nodo.run(_estado("stonecroft"))

    assert salida.category == "standard_review"
    assert salida.closable is False
    assert [regla.id for regla in salida.fired_rules] == ["STO-R-10"]


async def test_sunmeadow_simple_cierra_directo_y_es_cerrable() -> None:
    """CG-U9-1: Sunmeadow cierra directo lo simple, sin terceros ni heridos."""
    nodo, _ = _nodo()

    salida = await nodo.run(
        _estado("sunmeadow", injuries_present=False, other_parties_data_pending=False)
    )

    assert salida.category == "direct_close"
    assert salida.closable is True


async def test_knotwell_deriva_siempre_por_la_regla_de_la_agencia() -> None:
    """BR2.6, FR6.4: la agencia deriva incluso con un caso completamente limpio."""
    nodo, _ = _nodo()

    salida = await nodo.run(_estado("knotwell"))

    assert salida.category == "referral"
    assert salida.closable is False
    assert any(regla.id == "KNO-R-01" for regla in salida.fired_rules)


async def test_una_regla_de_dinero_fuerza_la_derivacion_y_no_es_cerrable() -> None:
    """BR2.3, compuerta dura AC1.17.3: el monto fuerza referral pese a cualquier otra senal."""
    nodo, _ = _nodo()

    salida = await nodo.run(_estado("stonecroft", claim_amount=50000))

    assert salida.category == "referral"
    assert salida.closable is False
    assert any(regla.touches_money for regla in salida.fired_rules)


async def test_reanudar_con_el_mismo_estado_no_duplica_la_evaluacion_guardada() -> None:
    """ADR-003: el identificador es determinista, y el guardado no duplica al reanudar."""
    nodo, almacen = _nodo()
    estado = _estado("stonecroft", injuries_present=True)

    primera = await nodo.run(estado)
    segunda = await nodo.run(estado)

    assert primera == segunda
    assert almacen.llamadas == 2  # el nodo se reejecuta entero al reanudar (C-15)
    assert len(almacen.filas) == 1  # pero la fila guardada es una sola (ADR-003)


async def test_dos_casos_distintos_del_mismo_caso_id_guardan_evaluaciones_distintas() -> None:
    """El identificador depende tambien de los insumos, no solo del caso (ADR-003)."""
    nodo, almacen = _nodo()

    await nodo.run(_estado("stonecroft", case_id="caso-1", injuries_present=True))
    await nodo.run(_estado("stonecroft", case_id="caso-1", injuries_present=False))

    assert len(almacen.filas) == 2


def test_el_siguiente_nodo_es_siempre_compliance() -> None:
    """BR3.1, F3: una funcion pura, sin importar la categoria que decidio."""
    salida_referral = DecisionNodeOutput(category="referral", closable=False, fired_rules=())
    salida_cierre = DecisionNodeOutput(category="direct_close", closable=True, fired_rules=())

    assert next_node(salida_referral) is NodeName.COMPLIANCE
    assert next_node(salida_cierre) is NodeName.COMPLIANCE


def test_la_especificacion_declara_su_conjunto_de_escritura_y_su_politica_de_fallo() -> None:
    """C-15: lecturas y escrituras salen de los modelos; la degradacion es la derivacion."""
    assert DECISION_SPEC.name is NodeName.DECISION
    assert DECISION_SPEC.rhythm == "background"
    assert set(DecisionNodeInput.model_fields) == DECISION_SPEC.reads
    assert set(DecisionNodeOutput.model_fields) == DECISION_SPEC.writes
    assert DECISION_SPEC.attempts == 2
    assert DECISION_SPEC.degraded_copy_key == phrases.HANDOFF
    assert DecisionNode.spec is DECISION_SPEC


def test_sus_escrituras_no_se_solapan_con_las_del_nodo_compliance() -> None:
    """Convencion 6: dos nodos no comparten ningun campo de su conjunto de escritura."""
    from untangle.orchestration.nodes.compliance.node import COMPLIANCE_SPEC

    assert DECISION_SPEC.writes.isdisjoint(COMPLIANCE_SPEC.writes)


@pytest.mark.parametrize(
    ("declarar", "fragmento"),
    [
        (lambda: replace(DECISION_SPEC, writes=frozenset()), "no declara ningun campo"),
        (lambda: replace(DECISION_SPEC, timeout_ms=0), "tiempo maximo"),
        (lambda: replace(DECISION_SPEC, attempts=0), "se intentaria 0 veces"),
        (lambda: replace(DECISION_SPEC, degraded_copy_key="texto libre"), "no tiene forma"),
    ],
)
def test_una_especificacion_imposible_falla_al_declararla(
    declarar: Callable[[], NodeSpec], fragmento: str
) -> None:
    with pytest.raises(NodeSpecError, match=fragmento):
        declarar()
