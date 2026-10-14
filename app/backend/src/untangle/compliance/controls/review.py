"""La revision completa de los cuatro controles, sin modelo (BR5.1 a BR5.3).

Corre en el ritmo de fondo, al cierre o en la derivacion, y comprueba cuatro
cosas **leyendo el caso**, nunca preguntandole a un modelo (BR5.3, FD-U10-3):

- `disclosure_ok`: hay divulgacion registrada (BR4.1).
- `human_route_ok`: si la persona pidio una persona, el turno de la agente que
  siguio a la peticion **es** el de la derivacion (BR2.2).
- `pii_ok`: la transcripcion revisada no tiene hallazgos del detector de U3.
- `explainability_ok`: estan la transcripcion, las citas --o la respuesta
  verificada sin clausula--, las reglas disparadas con sus insumos y el
  identificador de la traza (FR1.7, AC1.16.2). El quinto adjunto, el resultado
  de los controles, es esta misma revision.

Revisa la conversacion **hasta el turno pedido**: el de la derivacion si la
hubo, el ultimo si no (BR5.2). Lo que se dijo despues de derivar ya no es de la
conversacion que se revisa.

## Los puertos, por closure (C-15, decision 3 del conductor)

Este modulo no importa el registro del caso: `compliance` y `case_record` se
importarian en ciclo, y el contrato `sin-ciclos` lo prohibe. La transcripcion
llega por un puerto que construye la raiz de composicion, igual que el detector
de datos personales y el guardado; asi la revision se prueba sin base de datos y
sin modelos de lenguaje, y en produccion usa los de verdad.

## Idempotente al reanudar (BR6.3)

El guardado es por clave (caso, turno revisado): la reejecucion del nodo tras
`interrupt()` no crea otra revision ni reescribe la que habia, y devuelve la
guardada. La revision que el nodo ve es siempre la que quedo en la base.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import Field

from untangle.base import Frozen, Locale
from untangle.compliance.controls.models import (
    ID_MAX_LENGTH,
    ComplianceReview,
    DisclosureRecord,
    FindingCode,
)
from untangle.compliance.controls.patterns import PatternLibrary
from untangle.compliance.controls.signals import human_request_match
from untangle.tenancy.models import TENANT_ID_PATTERN, TenantId


class EvidenceState(StrEnum):
    """El estado de un adjunto del caso, con la grafia de `AttachmentKind` de U4.

    `EMPTY` se miro y no habia --una respuesta verificada sin clausula es eso--;
    `NOT_EVALUATED` no se miro. Nunca se colapsan: colapsarlos dejaria cerrar un
    caso que nadie reviso. Se repite aqui por el contrato `sin-ciclos`.
    """

    PRESENT = "present"
    EMPTY = "empty"
    NOT_EVALUATED = "not_evaluated"


class ReviewEvidence(Frozen):
    """Lo que la explicabilidad necesita, ademas de la transcripcion (FR1.7)."""

    #: Las citas con identificador y version, o la respuesta verificada sin
    #: clausula (`EMPTY`).
    citations: EvidenceState
    fired_rules: EvidenceState
    trace_id: EvidenceState

    @property
    def complete(self) -> bool:
        """Ningun adjunto quedo sin mirar."""
        return EvidenceState.NOT_EVALUATED not in (self.citations, self.fired_rules, self.trace_id)


class TranscriptLine(Frozen):
    """Un turno de la transcripcion tal como lo lee la revision: ya redactado."""

    turn_id: str = Field(min_length=1, max_length=ID_MAX_LENGTH)
    speaker: Literal["insured", "agent", "staff"]
    text: str


class ReviewRequest(Frozen):
    """Que revisar: el caso, hasta que turno, y los adjuntos que trae el estado."""

    tenant_id: TenantId = Field(pattern=TENANT_ID_PATTERN)
    case_id: str = Field(min_length=1, max_length=ID_MAX_LENGTH)
    language: Locale
    #: El ultimo turno revisado: el de la derivacion si la hubo (BR5.2).
    through_turn: str = Field(min_length=1, max_length=ID_MAX_LENGTH)
    #: El turno de la derivacion, si la hubo. Es lo que dice si una peticion de
    #: persona se derivo en el turno siguiente.
    handoff_turn: str | None = Field(default=None, min_length=1, max_length=ID_MAX_LENGTH)
    evidence: ReviewEvidence


class TranscriptSource(Protocol):
    """El puerto de lectura de la transcripcion, en orden (lo construye la raiz)."""

    def __call__(self, tenant_id: str, case_id: str, /) -> Awaitable[Sequence[TranscriptLine]]: ...


class DisclosureSource(Protocol):
    """El puerto de lectura de las divulgaciones registradas del caso."""

    def __call__(
        self, tenant_id: str, case_id: str, /
    ) -> Awaitable[Sequence[DisclosureRecord]]: ...


class PersonalDataCounter(Protocol):
    """Cuantos hallazgos encuentra el detector de U3 en un texto (BR5.1, `pii_ok`)."""

    def __call__(self, text: str, /, *, language: Locale) -> int: ...


class ReviewStore(Protocol):
    """Guarda la revision por su clave y devuelve la que quedo (BR6.3)."""

    def __call__(self, review: ComplianceReview, /) -> Awaitable[ComplianceReview]: ...


@dataclass(frozen=True)
class ReviewPorts:
    """Lo que la revision necesita de fuera, inyectado por la raiz de composicion."""

    transcript: TranscriptSource
    disclosures: DisclosureSource
    personal_data: PersonalDataCounter
    store: ReviewStore
    library: Callable[[], PatternLibrary]
    clock: Callable[[], datetime]
    new_id: Callable[[], str]


class TurnNotInTranscriptError(LookupError):
    """El turno hasta el que se pidio revisar no esta en la transcripcion del caso.

    Levanta en vez de revisar menos: una revision que se quedara corta sin
    decirlo aprobaria una conversacion que nadie leyo entera.
    """


def _hasta(turnos: Sequence[TranscriptLine], through_turn: str) -> tuple[TranscriptLine, ...]:
    """Los turnos hasta el pedido, inclusive (BR5.2)."""
    for indice, turno in enumerate(turnos):
        if turno.turn_id == through_turn:
            return tuple(turnos[: indice + 1])
    msg = (
        f"el turno '{through_turn}' no esta en la transcripcion del caso; la "
        "revision no se hace sobre menos de lo pedido (BR5.2)"
    )
    raise TurnNotInTranscriptError(msg)


def human_route_ok(
    turns: Sequence[TranscriptLine], *, handoff_turn: str | None, library: PatternLibrary
) -> bool:
    """Toda peticion de persona se derivo en el turno siguiente (BR2.2, BR5.1).

    Basta con mirar la **primera** peticion: tras la derivacion la revision ya no
    sigue, asi que una peticion posterior no esta en lo revisado, y si la primera
    no se derivo en el turno siguiente la regla ya no se cumple.
    """
    for indice, turno in enumerate(turns):
        if turno.speaker != "insured" or human_request_match(turno.text, library=library) is None:
            continue
        siguiente = next((t for t in turns[indice + 1 :] if t.speaker == "agent"), None)
        return siguiente is not None and siguiente.turn_id == handoff_turn
    return True


@dataclass(frozen=True)
class ControlResults:
    """Los cuatro controles de la revision, antes de guardarla."""

    disclosure_ok: bool
    human_route_ok: bool
    pii_ok: bool
    explainability_ok: bool

    def findings(self) -> tuple[FindingCode, ...]:
        """El codigo de cada control que no paso, en el orden de la regla (BR5.1)."""
        return tuple(
            codigo
            for paso, codigo in (
                (self.disclosure_ok, FindingCode.DISCLOSURE_MISSING),
                (self.human_route_ok, FindingCode.HUMAN_ROUTE_MISSED),
                (self.pii_ok, FindingCode.PII_FOUND),
                (self.explainability_ok, FindingCode.ATTACHMENT_MISSING),
            )
            if not paso
        )


def assess(
    request: ReviewRequest,
    *,
    turns: Sequence[TranscriptLine],
    disclosures: Sequence[DisclosureRecord],
    personal_data: PersonalDataCounter,
    library: PatternLibrary,
) -> ControlResults:
    """Los cuatro controles, puros, sobre lo que ya se leyo (BR5.1)."""
    revisados = _hasta(turns, request.through_turn)
    return ControlResults(
        disclosure_ok=bool(disclosures),
        human_route_ok=human_route_ok(
            revisados, handoff_turn=request.handoff_turn, library=library
        ),
        pii_ok=all(
            personal_data(turno.text, language=request.language) == 0 for turno in revisados
        ),
        explainability_ok=bool(revisados) and request.evidence.complete,
    )


async def final_review(request: ReviewRequest, *, ports: ReviewPorts) -> ComplianceReview:
    """La revision completa, guardada por su clave, y la que quedo (BR5.1 a BR6.3)."""
    turnos = await ports.transcript(request.tenant_id, request.case_id)
    divulgaciones = await ports.disclosures(request.tenant_id, request.case_id)
    controles = assess(
        request,
        turns=turnos,
        disclosures=divulgaciones,
        personal_data=ports.personal_data,
        library=ports.library(),
    )
    revision = ComplianceReview(
        review_id=ports.new_id(),
        tenant_id=request.tenant_id,
        case_id=request.case_id,
        disclosure_ok=controles.disclosure_ok,
        human_route_ok=controles.human_route_ok,
        pii_ok=controles.pii_ok,
        explainability_ok=controles.explainability_ok,
        findings=controles.findings(),
        reviewed_through_turn=request.through_turn,
        reviewed_at=ports.clock(),
    )
    return await ports.store(revision)
