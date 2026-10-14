"""La decision queda en la conversacion aunque nadie la estuviera escuchando (B2).

El enlace al caso abre en la misma pestana: quien decide desde ahi cierra el flujo
del chat, y al volver lo unico que ve es el historial. Sin la decision en la
transcripcion, la pagina del caso prometia un aviso que no llegaba.
"""

from __future__ import annotations

import pytest

from untangle.case_record import api as casos
from untangle.case_record.models import Resolution, Speaker
from untangle.inbox import decision
from untangle.server import composition

from .conftest import nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u13", "cifrador")


async def test_el_aviso_de_la_decision_queda_en_la_transcripcion(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    vista = await casos.get_case(propia, caso.case_id)
    assert vista is not None

    await composition._avisar_la_decision_al_chat(
        decision.DecisionMade(
            tenant_id=propia,
            case_id=caso.case_id,
            case_number=str(vista.case_number),
            resolution=Resolution.APPROVED.value,
            comment="Revisamos las fotos.",
            ref="recibo-1",
            language="es",
        )
    )

    [turno] = await casos.transcript_of(propia, caso.case_id)
    assert turno.speaker is Speaker.AGENT
    assert str(vista.case_number) in turno.text_redacted
    assert "Revisamos las fotos." in turno.text_redacted
