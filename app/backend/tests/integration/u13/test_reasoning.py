"""El pensamiento de la agente: lo que el caso ya guarda, dicho por pasos (2026-10-09)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest

from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record.models import Actor, ActorType, CaseField, Channel, FieldStatus
from untangle.chat import reasoning
from untangle.orchestration import transcript_writer
from untangle.policy_rag.citations import api as citas
from untangle.policy_rag.citations.models import CoverageOutcome
from untangle.policy_rag.citations.verifier import CitationVerdict, VerificationResult

from .conftest import nuevo_caso
from .test_history_citations import _sembrar_clausula

pytestmark = pytest.mark.usefixtures("base_de_u13", "cifrador")

AHORA = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


async def test_dice_que_clausulas_cito_por_pregunta_y_si_las_verifico(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _sembrar_clausula(propia, "u13-razon-D.EXCL.5")
    ambito = transcript_writer.TranscriptScope(
        tenant_id=propia, case_id=caso.case_id, channel=Channel.CHAT, language="es"
    )
    pregunta = await transcript_writer.record_person_turn(
        ambito, text="¿Me cubren una llanta?", now=AHORA
    )
    await citas.record_answer(
        propia,
        case_id=caso.case_id,
        turn_id=pregunta,
        question="¿Me cubren una llanta?",
        verification=VerificationResult(
            outcome=CoverageOutcome.VERIFIED,
            citations=(
                CitationVerdict(
                    clause_id="u13-razon-D.EXCL.5",
                    claim="trata de las llantas.",
                    outcome=CoverageOutcome.VERIFIED,
                    reasons=(),
                    amended_by=(),
                    clause_version="2026.1",
                ),
            ),
            clause_language="es",
        ),
        answer_language="es",
        now=AHORA,
    )
    conversacion = cast(Any, SimpleNamespace(tenant_id=propia, case_id=caso.case_id))

    pensamiento = await reasoning.for_session(conversacion, language="es", cipher=cifrador)

    assert pensamiento is not None
    [respuesta] = pensamiento.answers
    assert respuesta.outcome == "verified"
    [clausula] = respuesta.clauses
    assert (clausula.clause_id, clausula.part, clausula.verified) == (
        "u13-razon-D.EXCL.5",
        "Parte D",
        True,
    )
    assert pensamiento.fields, "los datos del caso, con si ya quedaron"


async def test_sin_caso_no_hay_pensamiento(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    del dos_aseguradoras
    conversacion = cast(Any, SimpleNamespace(tenant_id="x", case_id=None))

    assert await reasoning.for_session(conversacion, language="es", cipher=cifrador) is None


async def test_muestra_lo_que_quedo_anotado_y_no_solo_que_se_anoto(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Decision de Miguel del 2026-10-11: antes decia "Anotado" sin mostrar que."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await casos.set_field(
        propia,
        CaseField(
            case_id=caso.case_id,
            field_key="injuries",
            value=cifrador.seal("nadie salió herido"),
            status=FieldStatus.CONFIRMED,
            evidence_turn_id="turno-heridos",
            confirmed_aloud_at=AHORA,
            updated_at=AHORA,
        ),
        cipher=cifrador,
        actor=Actor(actor_type=ActorType.INSURED),
    )
    conversacion = cast(Any, SimpleNamespace(tenant_id=propia, case_id=caso.case_id))

    pensamiento = await reasoning.for_session(conversacion, language="es", cipher=cifrador)

    assert pensamiento is not None
    por_clave = {campo.field_key: campo for campo in pensamiento.fields}
    assert por_clave["injuries"].value == "nadie salió herido"
    assert por_clave["injuries"].done is True
    sin_decir = [c for c in pensamiento.fields if c.field_key != "injuries"]
    assert all(c.value is None for c in sin_decir)
    # Los que no cuentan para "5 de 5" se dicen opcionales.
    assert any(c.optional for c in pensamiento.fields)
    assert not por_clave["injuries"].optional
