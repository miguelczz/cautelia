"""Los adjuntos que la revision de cumplimiento da por mirados (2026-10-11)."""

from __future__ import annotations

from untangle.compliance.controls import api as cumplimiento
from untangle.orchestration.state import GraphState
from untangle.server import composition


def _estado(node_writes: dict[str, object]) -> GraphState:
    return GraphState(
        tenant_id="una-aseguradora",
        case_id="case-1",
        turn_id="turn-1",
        turn_text="",
        node_writes=node_writes,
    )


def test_un_reporte_cerrado_sin_pregunta_de_cobertura_no_tiene_nada_que_citar() -> None:
    """Se miro y no habia: antes contaba como "no se miro" y todo reporte cerrado
    sin preguntar salia con el hallazgo "falta un adjunto"."""
    evidencia = composition._evidencia(
        _estado({"intake_capture_closed": True, "fired_rules": ("STO-R-10",)})
    )

    assert evidencia.citations is cumplimiento.EvidenceState.EMPTY
    assert evidencia.complete is True


def test_una_verificacion_que_no_dejo_citas_sigue_sin_mirar() -> None:
    """Si hubo pregunta y el nodo no escribio sus citas, eso no se da por mirado: es
    justo lo que la revision tiene que ver."""
    evidencia = composition._evidencia(
        _estado({"intake_capture_closed": True, "outcome": "unverifiable", "fired_rules": ()})
    )

    assert evidencia.citations is cumplimiento.EvidenceState.NOT_EVALUATED
    assert evidencia.complete is False


def test_sin_cierre_ni_pregunta_las_citas_no_se_dan_por_miradas() -> None:
    evidencia = composition._evidencia(_estado({"fired_rules": ()}))

    assert evidencia.citations is cumplimiento.EvidenceState.NOT_EVALUATED
