"""Lo que no es de la aseguradora, con un caso abierto (plan 09, punto 5).

El turno (chat o llamada) que lee `off_topic` --porque el modelo lo ve asi, o porque el sondeo
previo lo reconoce-- responde con la frase fija del catalogo y vuelve al caso; lo que el modelo
haya escrito en esa llamada no sale. Pura: sin base ni modelo.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from untangle.copy_catalog import api as copy_api
from untangle.orchestration import contracts, off_topic, turn
from untangle.orchestration.output import ExitGate
from untangle.tenancy import config as tenancy_config


@pytest.fixture(autouse=True)
def _catalogo_y_aseguradoras() -> Iterator[None]:
    copy_api.install(copy_api.load())
    tenancy_config.install(tenancy_config.load())
    yield
    copy_api.reset()
    tenancy_config.reset()


def _mensaje(idioma: str, canal: str = "chat") -> contracts.InboundTurn:
    tenant = sorted(c.tenant_id for c in tenancy_config.loaded().available)[0]
    return contracts.InboundTurn(
        tenant_id=tenant,
        session_ref="s",
        case_id="c",
        text="Escríbeme un poema",
        language=idioma,  # type: ignore[arg-type]
        channel=canal,  # type: ignore[arg-type]
        received_at=datetime(2026, 11, 2, 12, 0, tzinfo=UTC),
    )


@pytest.mark.parametrize("canal", ["chat", "voice"])
@pytest.mark.parametrize("idioma", ["es", "en"])
async def test_el_turno_fuera_de_tema_dice_la_frase_fija_y_vuelve_al_caso(
    idioma: str, canal: str
) -> None:
    mensaje = _mensaje(idioma, canal)
    puerta = ExitGate(tenant_id=mensaje.tenant_id, language=mensaje.language)

    evento = await turn._fuera_de_tema(mensaje, case_id="c", turn_id="t1", gate=puerta)

    assert isinstance(evento, contracts.FinalText)
    assert evento.text == off_topic.with_case_text(language=mensaje.language)
    assert evento.from_catalog is True
    assert evento.case_id == "c"
    assert evento.message_id == "t1"


def test_pedir_algo_ajeno_no_cambia_de_tema_ni_abre_un_caso() -> None:
    from untangle.case_record.models import RecordType
    from untangle.orchestration.nodes.intake import understanding

    lectura = understanding.UnderstandingResponse(wants=understanding.Want.OFF_TOPIC)

    assert understanding.opening_record_type(lectura, quote_enabled=True) is None
    for actual in RecordType:
        assert understanding.switch_record_type(lectura, current=actual, quote_enabled=True) is None
