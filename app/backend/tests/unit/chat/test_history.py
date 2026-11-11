"""El historial que la pantalla recupera al abrirse: la parte pura, sin base.

Lo que se comprueba es lo que la pantalla va a dibujar: que la apertura solo se
compone si de verdad salio, que cada turno guardado llega con su lado y su texto
**tal como se guardo** --redactado--, y que el identificador de la apertura es el
mismo que viaja por el flujo, porque de eso depende que no se lea dos veces.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from untangle.case_record import api as casos
from untangle.case_record.models import Channel, Speaker, TranscriptTurn
from untangle.chat import history, opening, precase
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
        case_number="SA-7",
    )

    assert [turno.speaker for turno in recuperado.turns] == ["visitor", "agent", "agent"]
    assert recuperado.turns[0].text == "Mi póliza es [PÓLIZA 1]"
    assert recuperado.turns[0].turn_id == "turn-1"
    assert recuperado.turns[0].channel == "chat"
    assert recuperado.turns[0].at == AHORA.replace(second=1).isoformat()
    assert recuperado.case_number == "SA-7"


@pytest.mark.parametrize(
    ("hablante", "lado"),
    [(Speaker.INSURED, "visitor"), (Speaker.AGENT, "agent"), (Speaker.STAFF, "agent")],
)
def test_los_tres_hablantes_tienen_lado(hablante: Speaker, lado: str) -> None:
    """Tabla cerrada: cada hablante de la transcripcion decide de que lado se
    dibuja. Un cuarto tendria que entrar aqui a proposito."""
    assert history.speaker_of(hablante) == lado


# --- Lo hablado antes de abrir caso (2026-11-11) ------------------------------


def _previo(n: int, hablante: precase.PrecaseSpeaker, texto: str) -> precase.PrecaseMessage:
    return precase.PrecaseMessage(
        message_id=f"m{n}",
        speaker=hablante,
        text=texto,
        language="es",
        created_at=AHORA.replace(second=n),
    )


def test_lo_previo_al_caso_se_dibuja_sin_caso_y_en_orden(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    config = aseguradoras[0]
    previos = (
        _previo(1, "person", "Hola, tengo una duda de mi póliza"),
        _previo(2, "agent", "Claro, ¿cuál es su duda?"),
    )

    recuperado = history.compose(
        _conversacion(config, divulgada=True, case_id=None),
        config=config,
        turns=(),
        case_number=None,
        precase_messages=previos,
    )

    assert [t.speaker for t in recuperado.turns] == ["visitor", "agent"]
    assert [t.text for t in recuperado.turns] == [
        "Hola, tengo una duda de mi póliza",
        "Claro, ¿cuál es su duda?",
    ]
    # Sintetico y estable: el mismo mensaje se llama igual en cada carga.
    assert [t.turn_id for t in recuperado.turns] == ["pre-m1", "pre-m2"]
    assert recuperado.turns[0].channel == "chat"
    assert recuperado.turns[0].at == AHORA.replace(second=1).isoformat()
    assert recuperado.turns[0].citations == ()
    assert recuperado.case_number is None


def test_con_caso_lo_previo_va_primero_y_los_turnos_del_caso_despues_sin_duplicarse(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    config = aseguradoras[0]
    previos = (_previo(1, "person", "Hola"), _previo(2, "agent", "¿En qué le ayudo?"))
    turnos = (
        _turno(speaker=Speaker.INSURED, texto="Me chocaron ayer", segundos=10),
        _turno(speaker=Speaker.AGENT, texto="Lamento oírlo. ¿Hay heridos?", segundos=11),
    )

    recuperado = history.compose(
        _conversacion(config, divulgada=True, case_id="caso-1"),
        config=config,
        turns=turnos,
        case_number="SA-7",
        precase_messages=previos,
    )

    assert [t.turn_id for t in recuperado.turns] == ["pre-m1", "pre-m2", "turn-10", "turn-11"]
    assert len({t.turn_id for t in recuperado.turns}) == 4
    assert recuperado.case_number == "SA-7"


def test_sin_lo_previo_el_historial_es_el_de_siempre(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    config = aseguradoras[0]

    recuperado = history.compose(
        _conversacion(config, divulgada=True, case_id=None),
        config=config,
        turns=(),
        case_number=None,
    )

    assert recuperado.turns == ()


async def test_load_sin_caso_devuelve_lo_previo(
    aseguradoras: tuple[TenantConfig, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    config = aseguradoras[0]
    pedidos: list[dict[str, object]] = []

    async def previos(**kwargs: object) -> tuple[precase.PrecaseMessage, ...]:
        pedidos.append(kwargs)
        return (_previo(1, "person", "Hola"), _previo(2, "agent", "Buenas"))

    monkeypatch.setattr(precase, "load_precase_messages", previos)

    cargado = await history.load(_conversacion(config, divulgada=True, case_id=None), config=config)

    assert [t.turn_id for t in cargado.turns] == ["pre-m1", "pre-m2"]
    assert pedidos == [{"tenant_id": config.tenant_id, "chat_session_id": "chat-abc"}]


async def test_load_con_caso_pone_lo_previo_antes_de_la_transcripcion(
    aseguradoras: tuple[TenantConfig, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    config = aseguradoras[0]

    async def previos(**_: object) -> tuple[precase.PrecaseMessage, ...]:
        return (_previo(1, "person", "Hola"),)

    async def un_caso(tenant_id: str, case_id: str) -> object:
        del tenant_id, case_id
        return SimpleNamespace(case_number="SA-7")

    async def transcripcion(tenant_id: str, case_id: str) -> tuple[TranscriptTurn, ...]:
        del tenant_id, case_id
        return (_turno(speaker=Speaker.INSURED, texto="Me chocaron", segundos=10),)

    async def sin_citas(tenant_id: str, turnos: tuple[TranscriptTurn, ...]) -> dict[str, tuple]:  # type: ignore[type-arg]
        del tenant_id, turnos
        return {}

    monkeypatch.setattr(precase, "load_precase_messages", previos)
    monkeypatch.setattr(casos, "get_case", un_caso)
    monkeypatch.setattr(casos, "conversation_transcript", transcripcion)
    monkeypatch.setattr(history, "_citas_de_la_conversacion", sin_citas)

    cargado = await history.load(
        _conversacion(config, divulgada=True, case_id="caso-1"), config=config
    )

    assert [t.turn_id for t in cargado.turns] == ["pre-m1", "turn-10"]
    assert cargado.case_number == "SA-7"
