"""Los controles cableados como los arma la raiz de composicion (C-15, C-24, BR5.3, BR6.3).

Contra PostgreSQL de verdad, con el rol del aplicativo, la transcripcion leida
por la API de U4 y el detector de datos personales de U3 **real**: lo que se
prueba aqui es el cableado, que la unidad no puede probar con dobles.

- El nodo, con su revision por closure, cierra, deriva o rechaza leyendo el caso.
- La reejecucion al reanudar deja **una sola** revision guardada (BR6.3).
- Ningun control llama al modelo: el adaptador del proveedor esta espiado y
  cualquier llamada hace fallar la prueba (BR5.3).
- Una aseguradora no puede revisar el caso de otra: la transcripcion le llega
  vacia y la revision se niega a revisar menos de lo pedido.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest

from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record.models import Channel, Origin, RecordType, Speaker
from untangle.case_record.transcript import TurnDraft
from untangle.compliance.controls import api as cumplimiento
from untangle.compliance.controls import patterns, repository
from untangle.compliance.redaction.api import redact
from untangle.orchestration.nodes.compliance.node import ComplianceNodeInput
from untangle.providers.adapters.gemini import api as gemini
from untangle.server import composition
from untangle.settings import Settings
from untangle.tenancy import session

from .conftest import AHORA

pytestmark = pytest.mark.usefixtures("base_de_u10")

TODO_EVALUADO = cumplimiento.ReviewEvidence(
    citations=cumplimiento.EvidenceState.PRESENT,
    fired_rules=cumplimiento.EvidenceState.EMPTY,
    trace_id=cumplimiento.EvidenceState.PRESENT,
)


@pytest.fixture
def controles() -> Iterator[composition.ComplianceControls]:
    """Los controles de U10 tal como los arma la raiz, con los patrones instalados."""
    cumplimiento.install_patterns(cumplimiento.load_patterns())
    yield composition.build_compliance(Settings(database_url=None))
    # Nada queda instalado para la prueba siguiente.
    patterns.reset()


@pytest.fixture
def modelo_espiado(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """BR5.3: cada llamada al modelo o a los embeddings queda anotada y falla."""
    llamadas: list[str] = []

    async def espia_de_generacion(*_: object, **__: object) -> object:
        llamadas.append("generate")
        msg = "un control de cumplimiento llamo al modelo (BR5.3)"
        raise AssertionError(msg)

    async def espia_de_embeddings(*_: object, **__: object) -> object:
        llamadas.append("embed")
        msg = "un control de cumplimiento pidio embeddings (BR5.3)"
        raise AssertionError(msg)

    monkeypatch.setattr(gemini.GeminiTextGenerator, "generate", espia_de_generacion)
    monkeypatch.setattr(gemini.GeminiEmbedder, "embed", espia_de_embeddings)
    return llamadas


async def _caso(
    tenant_id: str, turnos: list[tuple[Speaker, str]], *, language: Locale = "es"
) -> tuple[str, list[str]]:
    """Un caso con esos turnos, por la API de U4 y con el texto redactado antes."""
    case_id = f"u10-cableado-{uuid.uuid4().hex[:12]}"
    await casos.create_case(
        tenant_id,
        casos.NewCase(
            case_id=case_id,
            record_type=RecordType.CLAIM,
            channel=Channel.CHAT,
            origin=Origin.PUBLIC_CHAT,
            language=language,
        ),
        now=AHORA,
    )
    ids: list[str] = []
    for numero, (hablante, texto) in enumerate(turnos, start=1):
        turn_id = f"{case_id}-t{numero}"
        await casos.append_turn(
            tenant_id,
            TurnDraft(
                turn_id=turn_id,
                case_id=case_id,
                speaker=hablante,
                channel=Channel.CHAT,
                language=language,
                started_at=AHORA.replace(second=numero),
            ),
            redact(texto, language=language),
        )
        ids.append(turn_id)
    return case_id, ids


async def _divulgar(tenant_id: str, case_id: str) -> None:
    await cumplimiento.record_disclosure(
        tenant_id=tenant_id,
        case_id=case_id,
        channel=cumplimiento.DisclosureChannel.CHAT,
        language="es",
        catalog_key="chat.opening.disclosure",
        disclosed_at=AHORA,
    )


def _estado(
    tenant_id: str,
    case_id: str,
    ultimo: str,
    *,
    handoff: cumplimiento.Handoff | None = None,
) -> ComplianceNodeInput:
    return ComplianceNodeInput(
        tenant_id=tenant_id,
        case_id=case_id,
        language="es",
        last_turn_id=ultimo,
        handoff=handoff,
        closable=True,
        evidence=TODO_EVALUADO,
    )


CONVERSACION = [
    (Speaker.AGENT, "Hola, soy la asistente de inteligencia artificial de la aseguradora."),
    (Speaker.INSURED, "Me llamo Carlos Pérez y choqué en la esquina del parque."),
    (Speaker.AGENT, "Entiendo. ¿Hay alguien herido?"),
    (Speaker.INSURED, "No, todos estamos bien."),
]


async def test_con_la_divulgacion_y_la_transcripcion_redactada_el_caso_cierra(
    controles: composition.ComplianceControls, dos_aseguradoras: tuple[str, str]
) -> None:
    """El nombre de la persona se redacto al guardarse: el detector de U3 no encuentra nada."""
    tenant, _ = dos_aseguradoras
    case_id, turnos = await _caso(tenant, CONVERSACION)
    await _divulgar(tenant, case_id)

    salida = await controles.node.run(_estado(tenant, case_id, turnos[-1]))

    assert salida.compliance_review.passed
    assert salida.closure.outcome is cumplimiento.ClosureOutcome.CLOSE
    guardada = await repository.review_through(tenant, case_id, turnos[-1])
    assert guardada == salida.compliance_review


async def test_la_reejecucion_al_reanudar_deja_una_sola_revision(
    controles: composition.ComplianceControls, dos_aseguradoras: tuple[str, str]
) -> None:
    """BR6.3: el nodo se ejecuta entero otra vez tras `interrupt()`, y no duplica."""
    tenant, _ = dos_aseguradoras
    case_id, turnos = await _caso(tenant, CONVERSACION)
    estado = _estado(tenant, case_id, turnos[-1])

    primera = await controles.node.run(estado)
    segunda = await controles.node.run(estado)

    assert segunda == primera
    async with session.session_for(tenant) as sesion:
        filas = await session.fetch_all(
            sesion, "SELECT review_id FROM compliance_review WHERE case_id = :c", c=case_id
        )
    assert [f["review_id"] for f in filas] == [primera.compliance_review.review_id]


async def test_sin_divulgacion_el_cierre_se_rechaza_diciendo_que_falta(
    controles: composition.ComplianceControls, dos_aseguradoras: tuple[str, str]
) -> None:
    tenant, _ = dos_aseguradoras
    case_id, turnos = await _caso(tenant, CONVERSACION)

    salida = await controles.node.run(_estado(tenant, case_id, turnos[-1]))

    assert salida.closure.outcome is cumplimiento.ClosureOutcome.REFUSED
    assert [f.code.value for f in salida.closure.missing] == ["disclosure_missing"]


async def test_el_caso_derivado_por_peticion_se_revisa_hasta_la_derivacion(
    controles: composition.ComplianceControls, dos_aseguradoras: tuple[str, str]
) -> None:
    """AC1.16.4 y BR2.2: la peticion se derivo en el turno siguiente, y lo de despues no cuenta."""
    tenant, _ = dos_aseguradoras
    case_id, turnos = await _caso(
        tenant,
        [
            *CONVERSACION[:2],
            (Speaker.INSURED, "Mejor que me llame alguien de ustedes."),
            (Speaker.AGENT, "Con lo que me contó, este caso lo revisa un ajustador."),
            (Speaker.INSURED, "Gracias."),
        ],
    )
    await _divulgar(tenant, case_id)
    derivacion = cumplimiento.Handoff(
        turn_id=turnos[3], reason=cumplimiento.HandoffReason.HUMAN_REQUEST
    )

    salida = await controles.node.run(_estado(tenant, case_id, turnos[-1], handoff=derivacion))

    assert salida.compliance_review.reviewed_through_turn == turnos[3]
    assert salida.compliance_review.human_route_ok
    assert salida.closure.reason_code is cumplimiento.HandoffReason.HUMAN_REQUEST


async def test_ningun_control_llama_al_modelo(
    controles: composition.ComplianceControls,
    dos_aseguradoras: tuple[str, str],
    modelo_espiado: list[str],
) -> None:
    """BR5.3: la guardia, las senales, la revision y el nodo, con el modelo espiado."""
    tenant, _ = dos_aseguradoras
    case_id, turnos = await _caso(tenant, CONVERSACION)
    await _divulgar(tenant, case_id)

    await cumplimiento.guard_output(
        "Sí, está cubierto.", tenant_id=tenant, language="es", case_id=case_id
    )
    await cumplimiento.read_turn_signals("Quiero hablar con una persona.")
    await controles.node.run(_estado(tenant, case_id, turnos[-1]))

    assert modelo_espiado == []


async def test_una_aseguradora_no_puede_revisar_el_caso_de_otra(
    controles: composition.ComplianceControls, dos_aseguradoras: tuple[str, str]
) -> None:
    """La transcripcion ajena llega vacia, y la revision no revisa menos de lo pedido."""
    duena, otra = dos_aseguradoras
    case_id, turnos = await _caso(duena, CONVERSACION)

    assert await casos.transcript_of(otra, case_id) == ()
    with pytest.raises(LookupError):
        await controles.node.run(_estado(otra, case_id, turnos[-1]))


async def test_la_intervencion_de_la_guardia_se_guarda_sin_la_frase(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR1.6, SEC-U10.3: la guardia devuelve el borrador; quien persiste lo completa."""
    tenant, _ = dos_aseguradoras
    case_id, turnos = await _caso(tenant, CONVERSACION)
    frase = "Le van a pagar 900 dólares."
    resultado = await cumplimiento.guard_output(
        frase, tenant_id=tenant, language="es", case_id=case_id
    )

    borrador = resultado.interventions[0]
    await cumplimiento.record_intervention(
        borrador.complete(
            intervention_id=f"{case_id}-i1",
            tenant_id=tenant,
            case_id=case_id,
            turn_id=turnos[-1],
            occurred_at=AHORA,
        )
    )

    guardadas = await repository.interventions(tenant, case_id)
    assert [g.category for g in guardadas] == [cumplimiento.GuardCategory.AMOUNT]
    assert "900" not in guardadas[0].model_dump_json()
