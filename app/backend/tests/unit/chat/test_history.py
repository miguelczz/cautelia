"""El historial que la pantalla recupera al abrirse: la parte pura, sin base.

Lo que se comprueba es lo que la pantalla va a dibujar: que la apertura solo se
compone si de verdad salio, que cada turno guardado llega con su lado y su texto
**tal como se guardo** --redactado--, y que el identificador de la apertura es el
mismo que viaja por el flujo, porque de eso depende que no se lea dos veces.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from untangle.case_record.models import Channel, Speaker, TranscriptTurn
from untangle.chat import history, opening
from untangle.chat import session as chat
from untangle.tenancy.models import TenantConfig

pytestmark = pytest.mark.usefixtures("catalogo_cargado")

AHORA = datetime(2026, 10, 6, 21, 0, tzinfo=UTC)


def _conversacion(
    config: TenantConfig, *, divulgada: bool, case_id: str | None
) -> chat.ChatSession:
    return chat.ChatSession(
        chat_session_id="chat-abc",
        tenant_id=config.tenant_id,
        language=config.default_language,
        origin_digest="origen",
        message_count=2,
        case_id=case_id,
        disclosed_at=AHORA if divulgada else None,
    )


def _turno(*, speaker: Speaker, texto: str, segundos: int) -> TranscriptTurn:
    return TranscriptTurn(
        turn_id=f"turn-{segundos}",
        case_id="caso-1",
        speaker=speaker,
        channel=Channel.CHAT,
        language="es",
        text_redacted=texto,
        started_at=AHORA.replace(second=segundos),
    )


def test_la_apertura_solo_se_compone_si_salio(aseguradoras: tuple[TenantConfig, ...]) -> None:
    """Componerla para una conversacion sin divulgar diria que la persona leyo
    algo que no leyo, que es lo que el registro de la divulgacion impide."""
    config = aseguradoras[0]

    sin = history.compose(
        _conversacion(config, divulgada=False, case_id=None),
        config=config,
        turns=(),
        case_number=None,
    )
    con = history.compose(
        _conversacion(config, divulgada=True, case_id=None),
        config=config,
        turns=(),
        case_number=None,
    )

    assert sin.opening is None
    assert con.opening is not None
    assert con.opening.text == opening.compose(config, language=config.default_language).text
    assert con.opening.language == config.default_language


def test_el_identificador_de_la_apertura_es_el_que_viaja_por_el_flujo(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    """La pantalla quita repetidos por identificador: si el historial y el flujo
    la nombraran distinto, la apertura se leeria dos veces."""
    config = aseguradoras[0]
    conversacion = _conversacion(config, divulgada=True, case_id=None)

    recuperado = history.compose(conversacion, config=config, turns=(), case_number=None)

    assert recuperado.opening is not None
    assert recuperado.opening.message_id == history.opening_message_id(conversacion)
    assert recuperado.opening.message_id == f"opening-{conversacion.chat_session_id}"


def test_cada_turno_guardado_llega_con_su_lado_y_su_texto_redactado(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    """Lo que la persona vuelve a leer de si misma es lo que se guardo: tapado.
    No se destapa nada aqui, y la prueba lo mira en el texto."""
    config = aseguradoras[0]
    turnos = (
        _turno(speaker=Speaker.INSURED, texto="Mi póliza es [PÓLIZA 1]", segundos=1),
        _turno(speaker=Speaker.AGENT, texto="Anotado. ¿Hay heridos?", segundos=2),
        _turno(speaker=Speaker.STAFF, texto="Un ajustador revisó su caso.", segundos=3),
    )

    recuperado = history.compose(
        _conversacion(config, divulgada=True, case_id="caso-1"),
        config=config,
        turns=turnos,
        case_number="STO-000007",
    )

    assert [turno.speaker for turno in recuperado.turns] == ["visitor", "agent", "agent"]
    assert recuperado.turns[0].text == "Mi póliza es [PÓLIZA 1]"
    assert recuperado.turns[0].turn_id == "turn-1"
    assert recuperado.turns[0].channel == "chat"
    assert recuperado.turns[0].at == AHORA.replace(second=1).isoformat()
    assert recuperado.case_number == "STO-000007"


@pytest.mark.parametrize(
    ("hablante", "lado"),
    [(Speaker.INSURED, "visitor"), (Speaker.AGENT, "agent"), (Speaker.STAFF, "agent")],
)
def test_los_tres_hablantes_tienen_lado(hablante: Speaker, lado: str) -> None:
    """Tabla cerrada: cada hablante de la transcripcion decide de que lado se
    dibuja. Un cuarto tendria que entrar aqui a proposito."""
    assert history.speaker_of(hablante) == lado
