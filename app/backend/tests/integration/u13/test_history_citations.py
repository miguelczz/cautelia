"""Al volver al chat, la respuesta de cobertura trae otra vez sus clausulas (2026-10-08).

Antes el historial devolvia solo el texto: las tarjetas de las clausulas, que llegaron en
vivo, desaparecian al salir y volver a entrar.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record.models import Channel
from untangle.chat import history
from untangle.chat import session as chat_session
from untangle.orchestration import transcript_writer
from untangle.policy_rag.citations import api as citas
from untangle.policy_rag.citations.models import CoverageOutcome
from untangle.policy_rag.citations.verifier import CitationVerdict, VerificationResult
from untangle.policy_rag.corpus.models import Clause, FormKind, PolicyForm
from untangle.policy_rag.corpus.repository import upsert_reference_data
from untangle.tenancy import config as tenancy_config

from .conftest import nuevo_caso
from .test_delivery import _conversacion_nueva

pytestmark = pytest.mark.usefixtures("base_de_u13", "cifrador")

AHORA = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


async def _sembrar_clausula(
    tenant_id: str,
    clause_id: str,
    *,
    language: Locale = "es",
    part: str = "Parte D",
    text: str = "No cubrimos el dano limitado a las llantas.",
) -> None:
    formulario = PolicyForm(
        tenant_id=tenant_id,
        form_id="form-u13-hist",
        form_version="2026.1",
        form_kind=FormKind.BASE,
        language=language,
        issuer_label="Mutual",
        issuer_tenant=tenant_id,
        clause_ids=(clause_id,),
    )
    clausula = Clause(
        tenant_id=tenant_id,
        clause_id=clause_id,
        clause_key="D.EXCL.5",
        form_id=formulario.form_id,
        form_version=formulario.form_version,
        part=part,
        language=language,
        text=text,
        is_distractor=False,
        issuer_label="Mutual",
    )
    await upsert_reference_data(
        tenant_id, forms=(formulario,), clauses=(clausula,), relations=(), policies=()
    )


async def test_la_respuesta_de_cobertura_vuelve_con_sus_clausulas(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _sembrar_clausula(propia, "u13-hist-D.EXCL.5")
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
                    clause_id="u13-hist-D.EXCL.5",
                    claim="Trata de las llantas.",
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
    respuesta = await transcript_writer.record_agent_turn(
        ambito,
        text="En su póliza, esto lo trata la Parte D.",
        now=AHORA,
        from_catalog=True,
        turn_id=f"{transcript_writer.COVERAGE_TURN_PREFIX}u13",
    )
    otro = await transcript_writer.record_agent_turn(
        ambito, text="¿Algo más?", now=AHORA, from_catalog=True
    )

    turnos = await casos.transcript_of(propia, caso.case_id)
    citas_por_turno = await history._citas_de_cobertura(propia, caso.case_id, turnos)

    assert [c.clause_id for c in citas_por_turno[respuesta]] == ["u13-hist-D.EXCL.5"]
    assert otro not in citas_por_turno


@pytest.mark.parametrize(
    ("idioma_de_la_clausula", "idioma_de_la_respuesta", "parte", "rotulo_esperado"),
    [
        (
            "en",
            "es",
            "Part D — Coverage for Damage to Your Auto",
            "Parte D — Daños a su vehículo",
        ),
        (
            "es",
            "en",
            "Parte D — Daños a su vehículo",
            "Part D — Coverage for Damage to Your Auto",
        ),
    ],
    ids=["poliza-en-ingles-respuesta-en-espanol", "poliza-en-espanol-respuesta-en-ingles"],
)
async def test_al_recargar_la_tarjeta_se_rotula_en_el_idioma_en_que_se_respondio(
    dos_aseguradoras: tuple[str, str],
    idioma_de_la_clausula: Locale,
    idioma_de_la_respuesta: Locale,
    parte: str,
    rotulo_esperado: str,
) -> None:
    """C17 (auditoria del 2026-10-10): la tarjeta llegaba en vivo con el nombre de la parte en el
    idioma de la respuesta y al recargar volvia con el de la poliza. Aqui la conversacion esta en
    el idioma de la poliza --como una aseguradora que arranca en ingles-- y la respuesta se dio en
    el otro: el rotulo es el de la respuesta, no el de la conversacion."""
    _, propia = dos_aseguradoras
    conversacion, _ = await _conversacion_nueva(propia, language=idioma_de_la_clausula)
    caso = await nuevo_caso(propia)
    conversacion = await chat_session.attach_case(conversacion, case_id=caso.case_id)
    await _sembrar_clausula(
        propia, "u13-hist-rotulo", language=idioma_de_la_clausula, part=parte, text="Texto."
    )
    ambito = transcript_writer.TranscriptScope(
        tenant_id=propia,
        case_id=caso.case_id,
        channel=Channel.CHAT,
        language=idioma_de_la_respuesta,
    )
    pregunta = await transcript_writer.record_person_turn(ambito, text="¿Me cubren?", now=AHORA)
    await citas.record_answer(
        propia,
        case_id=caso.case_id,
        turn_id=pregunta,
        question="¿Me cubren?",
        verification=VerificationResult(
            outcome=CoverageOutcome.VERIFIED,
            citations=(
                CitationVerdict(
                    clause_id="u13-hist-rotulo",
                    claim="Trata de eso.",
                    outcome=CoverageOutcome.VERIFIED,
                    reasons=(),
                    amended_by=(),
                    clause_version="2026.1",
                ),
            ),
            clause_language=idioma_de_la_clausula,
        ),
        answer_language=idioma_de_la_respuesta,
        now=AHORA,
    )
    respuesta = await transcript_writer.record_agent_turn(
        ambito,
        text="Esto lo trata esa parte.",
        now=AHORA,
        from_catalog=True,
        turn_id=f"{transcript_writer.COVERAGE_TURN_PREFIX}u13-rotulo",
    )

    cargado = await history.load(conversacion, config=tenancy_config.require(propia))

    [tarjeta] = next(t for t in cargado.turns if t.turn_id == respuesta).citations
    assert tarjeta.part == parte, "el texto y el nombre original no se tocan"
    assert tarjeta.translated_part == rotulo_esperado
