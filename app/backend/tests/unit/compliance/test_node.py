"""El nodo `compliance` y su decision de cierre (BR6.1 a BR6.4, C-15).

El nodo se prueba como lo va a usar el runtime: construido con su puerto de
revision por closure, con un estado de entrada, devolviendo solo su conjunto de
escritura. El puerto aqui es un doble que devuelve la revision que cada prueba
necesita; la revision de verdad tiene sus propias pruebas.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from untangle.compliance.controls import phrases
from untangle.compliance.controls.api import (
    ClosureDecision,
    ClosureOutcome,
    ComplianceReview,
    EvidenceState,
    Handoff,
    HandoffReason,
    ReviewEvidence,
    ReviewRequest,
)
from untangle.compliance.controls.models import FindingCode
from untangle.orchestration.nodes.compliance.node import (
    COMPLIANCE_SPEC,
    ComplianceNode,
    ComplianceNodeInput,
    ComplianceNodeOutput,
)
from untangle.orchestration.state import NodeSpec, NodeSpecError
from untangle.telemetry.traces.models import NodeName
from untangle.tenancy.models import TenantConfig

AHORA = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
TODO_EVALUADO = ReviewEvidence(
    citations=EvidenceState.PRESENT,
    fired_rules=EvidenceState.PRESENT,
    trace_id=EvidenceState.PRESENT,
)


def _revision(request: ReviewRequest, *hallazgos: FindingCode) -> ComplianceReview:
    return ComplianceReview(
        review_id="revision-1",
        tenant_id=request.tenant_id,
        case_id=request.case_id,
        disclosure_ok=FindingCode.DISCLOSURE_MISSING not in hallazgos,
        human_route_ok=FindingCode.HUMAN_ROUTE_MISSED not in hallazgos,
        explainability_ok=FindingCode.ATTACHMENT_MISSING not in hallazgos,
        findings=hallazgos,
        reviewed_through_turn=request.through_turn,
        reviewed_at=AHORA,
    )


class _Revisor:
    """El puerto de revision: devuelve una revision con los hallazgos pedidos."""

    def __init__(self, *hallazgos: FindingCode) -> None:
        self.hallazgos = hallazgos
        self.pedidos: list[ReviewRequest] = []

    async def __call__(self, request: ReviewRequest) -> ComplianceReview:
        self.pedidos.append(request)
        return _revision(request, *self.hallazgos)


def _estado(
    tenant_id: str, *, handoff: Handoff | None = None, closable: bool = True
) -> ComplianceNodeInput:
    return ComplianceNodeInput(
        tenant_id=tenant_id,
        case_id="caso-1",
        language="es",
        last_turn_id="t9",
        handoff=handoff,
        closable=closable,
        evidence=TODO_EVALUADO,
    )


async def test_con_los_controles_en_orden_y_las_reglas_de_acuerdo_cierra(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    """AC1.17.1: cierre directo, con la frase del catalogo de AC1.17.2 (BR6.4)."""
    revisor = _Revisor()

    salida = await ComplianceNode(review=revisor).run(_estado(aseguradoras[0].tenant_id))

    assert salida.closure == ClosureDecision(
        outcome=ClosureOutcome.CLOSE, copy_key=phrases.DIRECT_CLOSE
    )
    assert revisor.pedidos[0].through_turn == "t9"


async def test_una_derivacion_deriva_con_su_motivo_y_revisa_hasta_su_turno(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    """BR5.2, BR6.2: la revision llega hasta el turno de la derivacion, no hasta el ultimo."""
    revisor = _Revisor(FindingCode.ATTACHMENT_MISSING)
    derivacion = Handoff(turn_id="t4", reason=HandoffReason.HUMAN_REQUEST)

    salida = await ComplianceNode(review=revisor).run(
        _estado(aseguradoras[0].tenant_id, handoff=derivacion)
    )

    # Un caso que va a una persona no se esta intentando cerrar: deriva aunque
    # a la revision le falte algo, y la revision se adjunta igual.
    assert salida.closure.outcome is ClosureOutcome.REFER
    assert salida.closure.reason_code is HandoffReason.HUMAN_REQUEST
    assert salida.closure.copy_key == phrases.HANDOFF
    assert revisor.pedidos[0].through_turn == "t4"
    assert revisor.pedidos[0].handoff_turn == "t4"
    assert salida.compliance_review.findings == (FindingCode.ATTACHMENT_MISSING,)


async def test_cerrar_sin_los_controles_se_rechaza_diciendo_que_falta(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    """BR6.1, AC1.16.1: sin divulgacion y sin adjuntos, el rechazo nombra las dos cosas."""
    revisor = _Revisor(FindingCode.DISCLOSURE_MISSING, FindingCode.ATTACHMENT_MISSING)

    salida = await ComplianceNode(review=revisor).run(_estado(aseguradoras[0].tenant_id))

    assert salida.closure.outcome is ClosureOutcome.REFUSED
    assert [f.code for f in salida.closure.missing] == [
        FindingCode.DISCLOSURE_MISSING,
        FindingCode.ATTACHMENT_MISSING,
    ]
    assert [f.detail_key for f in salida.closure.missing] == [
        phrases.FINDING_DISCLOSURE_MISSING,
        phrases.FINDING_ATTACHMENT_MISSING,
    ]
    # El rechazo no le dice nada al asegurado: es un estado interno (BR6.4).
    assert salida.closure.copy_key is None


async def test_si_las_reglas_no_permiten_cerrar_sin_persona_deriva_por_regla(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    salida = await ComplianceNode(review=_Revisor()).run(
        _estado(aseguradoras[0].tenant_id, closable=False)
    )

    assert salida.closure.outcome is ClosureOutcome.REFER
    assert salida.closure.reason_code is HandoffReason.RULE


async def test_la_reejecucion_con_el_mismo_estado_da_la_misma_decision(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    """C-15, BR6.3: el nodo es puro. Lo que no se duplica al guardar lo prueba la integracion."""
    nodo = ComplianceNode(review=_Revisor(FindingCode.ATTACHMENT_MISSING))
    estado = _estado(aseguradoras[0].tenant_id)

    primera = await nodo.run(estado)
    segunda = await nodo.run(estado)

    assert primera == segunda
    assert primera.closure.outcome is ClosureOutcome.REFUSED


def test_la_especificacion_declara_su_conjunto_de_escritura_y_su_politica_de_fallo() -> None:
    """C-15: lecturas y escrituras salen de los modelos; la degradacion es la derivacion."""
    assert COMPLIANCE_SPEC.name is NodeName.COMPLIANCE
    assert COMPLIANCE_SPEC.rhythm == "background"
    assert set(ComplianceNodeInput.model_fields) == COMPLIANCE_SPEC.reads
    assert set(ComplianceNodeOutput.model_fields) == COMPLIANCE_SPEC.writes
    assert COMPLIANCE_SPEC.attempts == 2
    assert COMPLIANCE_SPEC.degraded_copy_key == phrases.HANDOFF
    assert ComplianceNode.spec is COMPLIANCE_SPEC


@pytest.mark.parametrize(
    ("declarar", "fragmento"),
    [
        (lambda: replace(COMPLIANCE_SPEC, writes=frozenset()), "no declara ningun campo"),
        (lambda: replace(COMPLIANCE_SPEC, timeout_ms=0), "tiempo maximo"),
        (lambda: replace(COMPLIANCE_SPEC, attempts=0), "se intentaria 0 veces"),
        (lambda: replace(COMPLIANCE_SPEC, degraded_copy_key="texto libre"), "no tiene forma"),
    ],
)
def test_una_especificacion_imposible_falla_al_declararla(
    declarar: Callable[[], NodeSpec], fragmento: str
) -> None:
    with pytest.raises(NodeSpecError, match=fragmento):
        declarar()


@pytest.mark.parametrize(
    "campos",
    [
        # Derivar sin motivo.
        {"outcome": ClosureOutcome.REFER, "copy_key": phrases.HANDOFF},
        # Rechazar sin decir que falta.
        {"outcome": ClosureOutcome.REFUSED},
        # Cerrar sin la frase de cierre.
        {"outcome": ClosureOutcome.CLOSE},
        # Un motivo fuera de la lista cerrada de C-04.
        {"outcome": ClosureOutcome.REFER, "reason_code": "otro", "copy_key": phrases.HANDOFF},
    ],
)
def test_una_decision_incoherente_no_se_construye(campos: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ClosureDecision.model_validate(campos)
