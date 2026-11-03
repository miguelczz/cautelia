"""El historial del caso acepta al ajustador de IA como actor, y dice la verdad de quien decidio."""

from __future__ import annotations

import pytest

from untangle.case_record import api as casos
from untangle.case_record import history as historial
from untangle.case_record.models import (
    Actor,
    ActorType,
    AttachmentKind,
    AttachmentState,
    Channel,
    ClosingEvidence,
    Resolution,
)
from untangle.case_record.rules import TransitionContext

from .conftest import AHORA, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u14")


async def test_el_cierre_de_un_caso_queda_firmado_por_el_ajustador_de_ia(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    await casos.close_case(
        propia,
        caso,
        resolution=Resolution.APPROVED,
        closing_evidence=ClosingEvidence(
            transcript=AttachmentState(kind=AttachmentKind.PRESENT, reference=caso),
            cited_clauses=AttachmentState(kind=AttachmentKind.EMPTY),
            fired_rules=AttachmentState(kind=AttachmentKind.EMPTY),
            trace_id=AttachmentState(kind=AttachmentKind.EMPTY),
            control_results=AttachmentState(kind=AttachmentKind.EMPTY),
        ),
        context=TransitionContext(
            now=AHORA,
            actor=Actor(actor_type=ActorType.ADJUSTER_AI),
            channel=Channel.CHAT,
        ),
    )

    cambios = await historial.of_case(propia, caso)
    firmados = [c for c in cambios if c.actor.actor_type is ActorType.ADJUSTER_AI]
    assert firmados, "el historial no dice que lo cerro el ajustador de IA"
    assert all(c.actor.actor_id is None for c in firmados), "la IA no es una persona con credencial"
