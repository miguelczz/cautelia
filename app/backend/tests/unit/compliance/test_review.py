"""La revision completa de los tres controles, sin modelo (BR5.1 a BR5.3).

Con los puertos de la raiz sustituidos por dobles en memoria: la transcripcion,
las divulgaciones y el guardado. Lo que se prueba es **que decide la revision** con
lo que lee; que lea de verdad de la base lo prueba la integracion
(`tests/integration/u10`).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal

import pytest

from untangle.compliance.controls import patterns
from untangle.compliance.controls.models import (
    ComplianceReview,
    DisclosureChannel,
    DisclosureRecord,
    FindingCode,
)
from untangle.compliance.controls.review import (
    EvidenceState,
    ReviewEvidence,
    ReviewPorts,
    ReviewRequest,
    TranscriptLine,
    TurnNotInTranscriptError,
    final_review,
)
from untangle.tenancy.models import TenantConfig

AHORA = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
TODO_EVALUADO = ReviewEvidence(
    citations=EvidenceState.PRESENT,
    fired_rules=EvidenceState.PRESENT,
    trace_id=EvidenceState.PRESENT,
)

Hablante = Literal["insured", "agent", "staff"]


def _linea(turn_id: str, speaker: Hablante, text: str) -> TranscriptLine:
    return TranscriptLine(turn_id=turn_id, speaker=speaker, text=text)


class _Base:
    """Los puertos de la revision, en memoria. Cuenta lo que se guarda."""

    def __init__(
        self,
        tenant_id: str,
        turnos: Sequence[TranscriptLine],
        *,
        divulgada: bool = True,
    ) -> None:
        self.tenant_id = tenant_id
        self.turnos = tuple(turnos)
        self.divulgada = divulgada
        self.guardadas: dict[tuple[str, str], ComplianceReview] = {}

    async def transcripcion(self, tenant_id: str, case_id: str) -> Sequence[TranscriptLine]:
        return self.turnos

    async def divulgaciones(self, tenant_id: str, case_id: str) -> Sequence[DisclosureRecord]:
        if not self.divulgada:
            return ()
        return (
            DisclosureRecord(
                disclosure_id="divulgacion-1",
                tenant_id=tenant_id,
                case_id=case_id,
                channel=DisclosureChannel.CHAT,
                language="es",
                catalog_key="chat.opening.disclosure",
                disclosed_at=AHORA,
            ),
        )

    async def guardar(self, review: ComplianceReview, /) -> ComplianceReview:
        # Como la base: la primera de cada (caso, turno revisado) es la que queda.
        clave = (review.case_id, review.reviewed_through_turn)
        return self.guardadas.setdefault(clave, review)

    def puertos(self, biblioteca: patterns.PatternLibrary) -> ReviewPorts:
        contador = iter(range(1, 1000))
        return ReviewPorts(
            transcript=self.transcripcion,
            disclosures=self.divulgaciones,
            store=self.guardar,
            library=lambda: biblioteca,
            clock=lambda: AHORA,
            new_id=lambda: f"revision-{next(contador)}",
        )


def _pedido(
    tenant_id: str,
    through_turn: str,
    *,
    handoff_turn: str | None = None,
    evidence: ReviewEvidence = TODO_EVALUADO,
) -> ReviewRequest:
    return ReviewRequest(
        tenant_id=tenant_id,
        case_id="caso-1",
        language="es",
        through_turn=through_turn,
        handoff_turn=handoff_turn,
        evidence=evidence,
    )


CONVERSACION_LIMPIA = (
    _linea("t1", "agent", "Hola, soy la asistente de inteligencia artificial."),
    _linea("t2", "insured", "Choqué en la esquina del parque."),
    _linea("t3", "agent", "Entiendo. ¿Hay alguien herido?"),
    _linea("t4", "insured", "No, todos estamos bien."),
)


async def test_una_conversacion_en_orden_pasa_los_tres_controles(
    biblioteca: patterns.PatternLibrary, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    base = _Base(aseguradoras[0].tenant_id, CONVERSACION_LIMPIA)

    revision = await final_review(_pedido(base.tenant_id, "t4"), ports=base.puertos(biblioteca))

    assert revision.passed
    assert revision.findings == ()
    assert revision.reviewed_through_turn == "t4"


async def test_sin_divulgacion_deja_exactamente_su_codigo(
    biblioteca: patterns.PatternLibrary, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    base = _Base(aseguradoras[0].tenant_id, CONVERSACION_LIMPIA, divulgada=False)

    revision = await final_review(_pedido(base.tenant_id, "t4"), ports=base.puertos(biblioteca))

    assert revision.findings == (FindingCode.DISCLOSURE_MISSING,)


async def test_una_conversacion_con_el_nombre_y_la_poliza_pasa_la_revision(
    biblioteca: patterns.PatternLibrary, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    """Desde el 2026-10-30 la conversacion se guarda como se escribio (decision de
    Miguel): que la persona diga su nombre y su poliza no es un hallazgo, y el caso
    se puede cerrar."""
    turnos = (
        _linea("t1", "agent", "Hola, soy la asistente de inteligencia artificial."),
        _linea("t2", "insured", "Soy Lina Diaz, mi póliza es POL-21. Choqué en el parque."),
        _linea("t3", "agent", "Encontré la póliza POL-21 a nombre de Lina Diaz."),
    )
    base = _Base(aseguradoras[0].tenant_id, turnos)

    revision = await final_review(_pedido(base.tenant_id, "t3"), ports=base.puertos(biblioteca))

    assert revision.passed
    assert revision.findings == ()


async def test_un_adjunto_sin_evaluar_falla_la_explicabilidad(
    biblioteca: patterns.PatternLibrary, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    """Una respuesta verificada sin clausula (vacio) si cuenta; una sin mirar, no."""
    base = _Base(aseguradoras[0].tenant_id, CONVERSACION_LIMPIA)
    sin_citas_miradas = ReviewEvidence(
        citations=EvidenceState.NOT_EVALUATED,
        fired_rules=EvidenceState.PRESENT,
        trace_id=EvidenceState.PRESENT,
    )
    sin_clausula = sin_citas_miradas.model_copy(update={"citations": EvidenceState.EMPTY})

    rota = await final_review(
        _pedido(base.tenant_id, "t4", evidence=sin_citas_miradas),
        ports=base.puertos(biblioteca),
    )
    verificada = await final_review(
        _pedido(base.tenant_id, "t3", evidence=sin_clausula), ports=base.puertos(biblioteca)
    )

    assert rota.findings == (FindingCode.ATTACHMENT_MISSING,)
    assert verificada.passed


async def test_una_peticion_de_persona_sin_derivar_en_el_turno_siguiente_falla(
    biblioteca: patterns.PatternLibrary, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    """BR2.2: el turno de la agente que sigue a la peticion tiene que ser la derivacion."""
    turnos = (
        _linea("t1", "insured", "Quiero hablar con una persona."),
        _linea("t2", "agent", "Claro, pero primero dígame la placa."),
        _linea("t3", "insured", "ABC123."),
        _linea("t4", "agent", "Con lo que me contó, este caso lo revisa un ajustador."),
    )
    base = _Base(aseguradoras[0].tenant_id, turnos)

    tarde = await final_review(
        _pedido(base.tenant_id, "t4", handoff_turn="t4"), ports=base.puertos(biblioteca)
    )

    assert tarde.findings == (FindingCode.HUMAN_ROUTE_MISSED,)


async def test_el_caso_derivado_a_mitad_se_revisa_hasta_la_derivacion(
    biblioteca: patterns.PatternLibrary, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    """BR5.2, AC1.16.4: lo que se dijo despues de derivar no es de la conversacion revisada."""
    turnos = (
        _linea("t1", "agent", "Hola, soy la asistente de inteligencia artificial."),
        _linea("t2", "insured", "Mejor que me llame alguien de ustedes."),
        _linea("t3", "agent", "Con lo que me contó, este caso lo revisa un ajustador."),
        # Despues de la derivacion: una peticion de persona sin respuesta, que habria
        # fallado la ruta a persona si se revisara.
        _linea("t4", "insured", "Quiero hablar con una persona."),
    )
    base = _Base(aseguradoras[0].tenant_id, turnos)

    revision = await final_review(
        _pedido(base.tenant_id, "t3", handoff_turn="t3"), ports=base.puertos(biblioteca)
    )

    assert revision.passed
    assert revision.reviewed_through_turn == "t3"


async def test_revisar_hasta_un_turno_que_no_existe_levanta_en_vez_de_revisar_menos(
    biblioteca: patterns.PatternLibrary, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    base = _Base(aseguradoras[0].tenant_id, CONVERSACION_LIMPIA)

    with pytest.raises(TurnNotInTranscriptError, match="t9"):
        await final_review(_pedido(base.tenant_id, "t9"), ports=base.puertos(biblioteca))
    assert base.guardadas == {}


async def test_repetir_la_revision_del_mismo_punto_devuelve_la_guardada(
    biblioteca: patterns.PatternLibrary, aseguradoras: tuple[TenantConfig, ...]
) -> None:
    """BR6.3: la reejecucion al reanudar no crea otra ni reescribe la que habia."""
    base = _Base(aseguradoras[0].tenant_id, CONVERSACION_LIMPIA)
    puertos = base.puertos(biblioteca)

    primera = await final_review(_pedido(base.tenant_id, "t4"), ports=puertos)
    segunda = await final_review(_pedido(base.tenant_id, "t4"), ports=puertos)

    assert segunda == primera
    assert len(base.guardadas) == 1
