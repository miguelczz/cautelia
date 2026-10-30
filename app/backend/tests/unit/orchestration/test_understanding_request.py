"""Lo que se le cuenta al modelo que entiende y contesta (2026-10-12).

La conversacion, el estado del caso, lo anotado **con su valor** y lo que falta en el orden en
que el codigo lo pide. Antes el modelo veia solo el ultimo mensaje y la lista de datos
pendientes, y por eso no podia «recordar de que le hablan» (C4 de las correcciones del
2026-10-12). Sin modelo y sin base: el contexto del caso es un doble.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

import pytest

from untangle.case_record import api as casos
from untangle.case_record import fields as case_fields
from untangle.case_record.models import (
    CaseState,
    Channel,
    Completeness,
    RecordType,
    Speaker,
    TranscriptTurn,
)
from untangle.orchestration import turn
from untangle.orchestration.nodes.intake.understanding import (
    HISTORY_LINES,
    CaseStatus,
    HistoryLine,
    NotedDetail,
)
from untangle.tenancy import api as tenancy

_AHORA = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def aseguradoras() -> None:
    tenancy.install(tenancy.load())


def _contexto(
    record_type: RecordType,
    per_field: dict[str, bool],
    *,
    state: CaseState = CaseState.CAPTURING,
    awaiting: frozenset[str] = frozenset(),
    policy_ref: str | None = None,
) -> Any:
    return SimpleNamespace(
        record_type=record_type,
        quote_enabled=True,
        state=state,
        policy_ref=policy_ref,
        completeness=Completeness(
            per_field=per_field,
            awaiting_readback=awaiting,
            complete=sum(per_field.values()),
            total=len(per_field),
        ),
    )


def _peticion(
    contexto: Any,
    *,
    pendiente: bool = False,
    channel: str = "chat",
    **mas: Any,
) -> Any:
    entrante = SimpleNamespace(tenant_id="sunmeadow", language="es", text="Tres", channel=channel)
    estado = SimpleNamespace(
        node_writes={},
        pending_background=frozenset({"policy_verification"}) if pendiente else frozenset(),
    )
    return turn._peticion_de_comprension(
        cast(Any, entrante), contexto, cast(Any, estado), _AHORA, **mas
    )


def _cotizacion(**dichos: bool) -> dict[str, bool]:
    """Todos los campos de la solicitud, como los trae un caso de verdad, con los que se digan."""
    return {
        d.key: dichos.get(d.key, False)
        for d in case_fields.definitions_for(RecordType.QUOTE_REQUEST)
    }


_CLAIM_VACIO = {
    "identity_and_policy": False,
    "incident_datetime": False,
    "location": False,
    "description": False,
    "vehicle_and_driver": False,
    "other_parties": False,
    "injuries": False,
}


def test_lo_que_falta_va_en_el_orden_en_que_el_codigo_lo_pide_y_sin_los_opcionales() -> None:
    peticion = _peticion(_contexto(RecordType.CLAIM, _CLAIM_VACIO))

    # Seguridad, identidad, que paso, cuando y donde. El vehiculo y las otras partes son
    # opcionales: se ofrecen al cerrar y no se piden de entrada.
    assert peticion.missing == (
        "injuries",
        "identity_and_policy",
        "description",
        "incident_datetime",
        "location",
    )


def test_lo_anotado_lleva_su_valor_y_lo_de_identidad_va_sin_el() -> None:
    contexto = _contexto(
        RecordType.CLAIM,
        {**_CLAIM_VACIO, "identity_and_policy": True, "location": True, "injuries": True},
    )

    peticion = _peticion(
        contexto,
        noted_values={
            "identity_and_policy": "Marcela Ríos, POL-01",
            "location": "la calle 80 con 30",
            "injuries": "no",
        },
    )

    assert peticion.noted == (
        NotedDetail("identity_and_policy", None),
        NotedDetail("location", "la calle 80 con 30"),
        NotedDetail("injuries", "no"),
    )
    assert "Marcela" not in repr(peticion), "el valor de la identidad no viaja"


def test_el_nombre_del_conductor_de_una_cotizacion_tampoco_viaja() -> None:
    contexto = _contexto(
        RecordType.QUOTE_REQUEST, _cotizacion(driver_name=True, driver_birth_date=True)
    )

    peticion = _peticion(
        contexto, noted_values={"driver_name": "Marcela Ríos", "driver_birth_date": "1990-05-04"}
    )

    assert peticion.noted == (
        NotedDetail("driver_name", None),
        NotedDetail("driver_birth_date", "1990-05-04"),
    )


def test_lo_que_dijo_y_espera_su_lectura_cuenta_como_anotado_y_no_como_faltante() -> None:
    """Contado como faltante, la agente lo volvia a pedir."""
    contexto = _contexto(
        RecordType.QUOTE_REQUEST, _cotizacion(), awaiting=frozenset({"driver_name"})
    )

    peticion = _peticion(contexto, noted_values={"driver_name": "x"})

    assert [dato.field_key for dato in peticion.noted] == ["driver_name"]
    assert "driver_name" not in peticion.missing
    assert peticion.missing[0] == "driver_birth_date"


def test_la_antiguedad_del_carro_la_escribe_el_codigo_y_no_se_pide_ni_se_cuenta() -> None:
    contexto = _contexto(RecordType.QUOTE_REQUEST, _cotizacion(vehicle_make=True))

    peticion = _peticion(contexto)

    assert "vehicle_age_years" not in peticion.missing
    assert "vehicle_year" in peticion.missing
    assert "vehicle_age_years" in contexto.completeness.per_field, "existe, y no se pide"


@pytest.mark.parametrize(
    ("estado", "esperado"),
    [
        (CaseState.OPEN, CaseStatus.RECEIVING),
        (CaseState.CAPTURING, CaseStatus.RECEIVING),
        # En revision (US1.17): las reglas todavia no dicen si lo cierra la agente o lo mira un
        # ajustador, asi que no se le cuenta al modelo que ya lo tiene uno.
        (CaseState.VERIFYING, CaseStatus.IN_REVIEW),
        (CaseState.DECIDING, CaseStatus.IN_REVIEW),
        (CaseState.DERIVED, CaseStatus.WITH_ADJUSTER),
        (CaseState.AWAITING_INSURED, CaseStatus.WITH_ADJUSTER),
        (CaseState.CLOSED, CaseStatus.CLOSED),
    ],
)
def test_el_estado_del_caso_se_cuenta_en_las_cinco_palabras(
    estado: CaseState, esperado: CaseStatus
) -> None:
    peticion = _peticion(_contexto(RecordType.CLAIM, _CLAIM_VACIO, state=estado))

    assert peticion.case_status is esperado


def test_un_caso_que_ya_no_captura_no_tiene_nada_que_pedir() -> None:
    peticion = _peticion(_contexto(RecordType.CLAIM, _CLAIM_VACIO, state=CaseState.DERIVED))

    assert peticion.missing == ()


def test_la_poliza_identificada_y_la_respuesta_pendiente_salen_del_caso_y_del_estado() -> None:
    sin = _peticion(_contexto(RecordType.COVERAGE_INQUIRY, {"identity_and_policy": False}))
    con = _peticion(
        _contexto(RecordType.COVERAGE_INQUIRY, {"identity_and_policy": True}, policy_ref="POL-01"),
        pendiente=True,
    )

    assert (sin.policy_identified, sin.answer_pending) == (False, False)
    assert (con.policy_identified, con.answer_pending) == (True, True)


def test_el_canal_el_nombre_de_la_agente_y_el_mensaje_viajan_tal_cual() -> None:
    peticion = _peticion(_contexto(RecordType.CLAIM, _CLAIM_VACIO), channel="voice")

    assert peticion.channel == "voice"
    assert peticion.agent_name
    assert peticion.person_text == "Tres"
    assert peticion.today == _AHORA.date()


# --- La conversacion: lo que se dijo antes de este mensaje ----------------------------


def _dicho(orden: int, speaker: Speaker, texto: str) -> TranscriptTurn:
    return TranscriptTurn(
        turn_id=f"t{orden}",
        case_id="caso-1",
        speaker=speaker,
        channel=Channel.CHAT,
        language="es",
        text_redacted=texto,
        started_at=_AHORA - timedelta(minutes=60 - orden),
    )


@pytest.fixture
def transcripcion(monkeypatch: pytest.MonkeyPatch) -> list[TranscriptTurn]:
    turnos: list[TranscriptTurn] = []

    async def _transcript(_tenant_id: str, _case_id: str) -> tuple[TranscriptTurn, ...]:
        return tuple(turnos)

    monkeypatch.setattr(casos, "conversation_transcript", _transcript)
    return turnos


def _mensaje() -> Any:
    return SimpleNamespace(tenant_id="sunmeadow", received_at=_AHORA)


async def test_la_conversacion_es_lo_guardado_ya_tapado_y_dice_quien_hablo(
    transcripcion: list[TranscriptTurn],
) -> None:
    transcripcion += [
        _dicho(1, Speaker.AGENT, "Hola, soy Catalina."),
        _dicho(2, Speaker.INSURED, "Soy [NOMBRE 1], mi póliza es [PÓLIZA 1]"),
        _dicho(3, Speaker.AGENT, "Gracias. ¿Qué quieres saber de tu póliza?"),
    ]

    historia = await turn._historial_de_la_conversacion(_mensaje(), "caso-1")

    assert historia == (
        HistoryLine("agent", "Hola, soy Catalina."),
        HistoryLine("person", "Soy [NOMBRE 1], mi póliza es [PÓLIZA 1]"),
        HistoryLine("agent", "Gracias. ¿Qué quieres saber de tu póliza?"),
    )


async def test_el_mensaje_de_ahora_no_es_historia_aunque_el_canal_ya_lo_haya_guardado(
    transcripcion: list[TranscriptTurn],
) -> None:
    """El mensaje actual va aparte y sin tapar: que ya este en la transcripcion no lo
    duplica en la conversacion."""
    transcripcion += [
        _dicho(1, Speaker.AGENT, "¿Qué quieres saber?"),
        _dicho(2, Speaker.INSURED, "este es el mensaje de ahora").model_copy(
            update={"started_at": _AHORA}
        ),
    ]

    historia = await turn._historial_de_la_conversacion(_mensaje(), "caso-1")

    assert historia == (HistoryLine("agent", "¿Qué quieres saber?"),)


async def test_solo_las_ultimas_doce_intervenciones(
    transcripcion: list[TranscriptTurn],
) -> None:
    transcripcion += [
        _dicho(orden, Speaker.INSURED if orden % 2 else Speaker.AGENT, f"turno {orden}")
        for orden in range(1, 31)
    ]

    historia = await turn._historial_de_la_conversacion(_mensaje(), "caso-1")

    assert len(historia) == HISTORY_LINES == 12
    assert historia[0].text == "turno 19"
    assert historia[-1].text == "turno 30"


async def test_lo_que_escribe_el_personal_de_la_bandeja_es_una_voz_mas_de_la_agente(
    transcripcion: list[TranscriptTurn],
) -> None:
    transcripcion += [_dicho(1, Speaker.STAFF, "Ya revisé tu caso.")]

    historia = await turn._historial_de_la_conversacion(_mensaje(), "caso-1")

    assert historia == (HistoryLine("agent", "Ya revisé tu caso."),)
