"""Que caso elige `mise run demo:ajustador` para hacer de ajustador (2026-10-14)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from untangle.case_record import fields
from untangle.case_record.api import CaseSummary
from untangle.case_record.models import CaseState, Channel, Origin, Priority, RecordType
from untangle.server.demo_adjuster_link import choose_case

AHORA = datetime(2026, 10, 14, 12, tzinfo=UTC)


def _caso(
    case_id: str,
    estado: CaseState,
    *,
    tipo: RecordType = RecordType.CLAIM,
    hace_horas: float = 0,
) -> CaseSummary:
    creado = AHORA - timedelta(hours=hace_horas)
    return CaseSummary(
        case_id=case_id,
        case_number=f"XXX-{case_id}",
        record_type=tipo,
        state=estado,
        resolution=None,
        channel=Channel.CHAT,
        language="es",
        priority=Priority.NORMAL,
        derivation_reason=None,
        completeness=fields.completeness_of(tipo, ()),
        created_at=creado,
        updated_at=creado,
        priority_rank=1,
    )


def test_sin_casos_que_admitan_anotaciones_no_elige_ninguno() -> None:
    casos = (
        _caso("a", CaseState.CAPTURING),
        _caso("b", CaseState.CLOSED),
        _caso("c", CaseState.DERIVED, tipo=RecordType.QUOTE_REQUEST),
    )

    assert choose_case(casos) is None


def test_un_derivado_va_antes_que_uno_que_espera_al_asegurado() -> None:
    casos = (
        _caso("espera", CaseState.AWAITING_INSURED),
        _caso("derivado", CaseState.DERIVED, hace_horas=48),
    )

    elegido = choose_case(casos)

    assert elegido is not None
    assert elegido.case_id == "derivado"


def test_entre_derivados_el_del_visitante_va_antes_que_el_del_generador() -> None:
    casos = (
        _caso("sembrado", CaseState.DERIVED),
        _caso("propio", CaseState.DERIVED, hace_horas=5),
    )
    origenes = {"sembrado": Origin.GENERATOR.value, "propio": Origin.PUBLIC_CHAT.value}

    elegido = choose_case(casos, origins=origenes)

    assert elegido is not None
    assert elegido.case_id == "propio"


def test_en_igualdad_gana_el_mas_reciente() -> None:
    casos = (
        _caso("viejo", CaseState.DERIVED, hace_horas=30),
        _caso("nuevo", CaseState.DERIVED, hace_horas=1),
    )
    origenes = {"viejo": Origin.GENERATOR.value, "nuevo": Origin.GENERATOR.value}

    elegido = choose_case(casos, origins=origenes)

    assert elegido is not None
    assert elegido.case_id == "nuevo"


def test_un_caso_que_espera_al_asegurado_sirve_si_no_hay_derivados() -> None:
    elegido = choose_case((_caso("espera", CaseState.AWAITING_INSURED),))

    assert elegido is not None
    assert elegido.case_id == "espera"
