"""La superficie de los controles de cumplimiento (C-20, FD-U10-4).

Lo que U12 --el punto unico de salida y el nodo `compliance`-- y U14 consumen de
U10, y nada mas. C-20 declaraba cinco funciones; FD-U10-4 le anade dos como
cambio aditivo de su dueno --`detect_identity_question` y `delimit_untrusted`--,
y esta superficie trae ademas lo que las cinco necesitaban para poder usarse:

| C-20 | Aqui | Por que difiere |
| --- | --- | --- |
| `guard_output(text, *, tenant_id, language, case_id)` | la misma, mas `case_number`, `turn` y `source_key`, opcionales | El reemplazo es una vez **por turno** (BR1.4) y alguien tiene que recordar el turno; la revelacion compara contra el **numero** del caso en curso (BR1.7); la exencion de las plantillas es por su clave (BR1.8). Sin ellos la guardia no podria cumplir sus reglas |
| `final_review(case_id)` | `final_review(request, *, ports)` | Revisa hasta un turno (BR5.2) con los adjuntos que trae el estado, y la transcripcion llega por un puerto (decision 3 del conductor) |
| `record_disclosure(case_id, *, channel, language)` | con `tenant_id`, `catalog_key` y `disclosed_at` | El punto unico de sesion exige la aseguradora; la entidad guarda la clave de la apertura y la hora (BR4.1) |

**Dentro del turno corren solo los tres controles baratos** --la guardia, la
peticion de persona y la emergencia-- (D22); la revision completa es del ritmo de
fondo. Ninguno llama a un modelo: un contrato de importacion falla si este
paquete llega a importar un proveedor (BR5.3).

**Si la guardia no puede evaluar, el texto no sale** (C-20): sale la frase de
degradacion y queda un evento con el tipo del error, nunca con la frase.
"""

from __future__ import annotations

from untangle import observability
from untangle.base import Locale
from untangle.compliance.controls import patterns, phrases, signals
from untangle.compliance.controls.closure import (
    ClosureDecision,
    ClosureOutcome,
    ComplianceFinding,
    Handoff,
    HandoffReason,
    decide_closure,
)
from untangle.compliance.controls.delimitation import (
    CLOSE_DELIMITER,
    Delimited,
    UntrustedSource,
    delimit_untrusted,
    open_delimiter,
)
from untangle.compliance.controls.disclosure import record_disclosure
from untangle.compliance.controls.guard import (
    GuardContext,
    GuardResult,
    GuardTurn,
    guard_sentence,
    not_evaluable,
)
from untangle.compliance.controls.models import (
    ComplianceReview,
    DisclosureChannel,
    GuardCategory,
    GuardIntervention,
    InterventionDraft,
)
from untangle.compliance.controls.patterns import PatternLibrary, PatternLoadError
from untangle.compliance.controls.phrases import EmergencyPhraseMode
from untangle.compliance.controls.repository import (
    disclosures,
    latest_review,
    record_intervention,
    save_review,
)
from untangle.compliance.controls.review import (
    EvidenceState,
    ReviewEvidence,
    ReviewPorts,
    ReviewRequest,
    TranscriptLine,
    final_review,
)
from untangle.compliance.controls.signals import TurnSignals
from untangle.copy_catalog.api import CopyKey
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import TenantId


def load_patterns() -> PatternLibrary:
    """Carga y valida los ocho archivos de patrones. Un archivo invalido levanta (TECH-U10.1)."""
    return patterns.load_library()


def install_patterns(library: PatternLibrary) -> None:
    """Fija los patrones del proceso. La llama la raiz de composicion al arrancar."""
    patterns.install(library)


def current_patterns() -> PatternLibrary:
    """Los patrones del proceso, para quien los recibe por closure (la revision)."""
    return patterns.get_library()


def _dejar_rastro(
    resultado: GuardResult,
    error: Exception | None,
    *,
    tenant_id: TenantId,
    case_id: str | None,
) -> None:
    """Un evento por intervencion, y uno si no se pudo evaluar (BR1.6).

    Con la categoria, el patron y la accion, **nunca con la frase**: la frase
    podria traer lo que el visitante dijo, y lo que si salio ya esta en la
    transcripcion.

    Sale por el punto unico de eventos y **no** como atributo del tramo del
    turno: este paquete no puede importar las trazas --`telemetry` ya importa
    `compliance` para redactar antes de exportar, y la arista contraria cerraria
    el ciclo que el contrato `sin-ciclos` prohibe--. Quien tiene el tramo abierto
    es el punto unico de salida de U12, y es quien anota ahi la intervencion con
    lo que este resultado le devuelve.
    """
    if error is not None:
        observability.emit(
            "compliance.guard_not_evaluable",
            tenant_id=tenant_id,
            case_id=case_id,
            error_type=type(error).__name__,
        )
    for intervencion in resultado.interventions:
        observability.emit(
            "compliance.guard_intervened",
            tenant_id=tenant_id,
            case_id=case_id,
            category=intervencion.category.value if intervencion.category else None,
            pattern_id=intervencion.pattern_id,
            action=intervencion.action.value,
            catalog_key=intervencion.catalog_key,
        )


async def guard_output(  # noqa: PLR0913 -- las cuatro de C-20 mas las tres que sus reglas exigen, todas por nombre
    text: str,
    *,
    tenant_id: TenantId,
    language: Locale,
    case_id: str | None = None,
    case_number: str | None = None,
    turn: GuardTurn | None = None,
    source_key: str | None = None,
) -> GuardResult:
    """La guardia sobre una frase hacia el asegurado (C-20, BR1.1 a BR1.8).

    `turn` es el de la frase: la misma instancia para todas las frases de un
    turno, para que el reemplazo sea una vez por categoria (BR1.4). Sin turno, la
    frase se evalua como la primera de un turno nuevo.
    """
    fallo: Exception | None
    try:
        contexto = GuardContext.for_tenant(
            tenant_id,
            language=language,
            tenants=tenancy_config.loaded().available,
            case_number=case_number,
            source_key=source_key,
        )
    except Exception as error:  # noqa: BLE001 -- falla cerrado (C-20, BR1.5): sin la configuracion de las aseguradoras no se puede evaluar la revelacion, y la frase no sale
        resultado, fallo = not_evaluable(language=language), error
    else:
        resultado, fallo = guard_sentence(
            text,
            context=contexto,
            turn=turn if turn is not None else GuardTurn(),
            library=patterns.get_library,
        )
    _dejar_rastro(resultado, fallo, tenant_id=tenant_id, case_id=case_id)
    return resultado


async def detect_human_request(text: str) -> bool:
    """La persona pide hablar con una persona, en cualquier idioma (C-20, BR2.1)."""
    return signals.human_request_match(text, library=patterns.get_library()) is not None


async def detect_identity_question(text: str) -> bool:
    """La persona pregunta si la agente es una persona (FD-U10-4, BR2.4)."""
    return signals.identity_question_match(text, library=patterns.get_library()) is not None


async def detect_emergency(text: str) -> bool:
    """Hay un herido grave o peligro en el turno (C-20, BR3.1, BR3.2)."""
    return signals.emergency_match(text, library=patterns.get_library()) is not None


async def read_turn_signals(text: str) -> TurnSignals:
    """Las tres senales de un turno de una sola vez, para el punto unico de U12."""
    return signals.read_signals(text, library=patterns.get_library())


def identity_answer(*, language: Locale) -> tuple[CopyKey, str]:
    """La respuesta fija a la pregunta de identidad, con su clave (AC1.10.1, AC1.10.2)."""
    return phrases.IDENTITY_ANSWER, phrases.identity_answer_text(locale=language)


def emergency_instruction(mode: EmergencyPhraseMode, *, language: Locale) -> tuple[CopyKey, str]:
    """La indicacion de emergencia de ese despliegue, con su clave (AC1.6.3, BR3.3)."""
    return phrases.emergency_key(mode), phrases.emergency_text(mode, locale=language)


__all__ = [
    "CLOSE_DELIMITER",
    "ClosureDecision",
    "ClosureOutcome",
    "ComplianceFinding",
    "ComplianceReview",
    "Delimited",
    "DisclosureChannel",
    "EmergencyPhraseMode",
    "EvidenceState",
    "GuardCategory",
    "GuardIntervention",
    "GuardResult",
    "GuardTurn",
    "Handoff",
    "HandoffReason",
    "InterventionDraft",
    "PatternLibrary",
    "PatternLoadError",
    "ReviewEvidence",
    "ReviewPorts",
    "ReviewRequest",
    "TranscriptLine",
    "TurnSignals",
    "UntrustedSource",
    "current_patterns",
    "decide_closure",
    "delimit_untrusted",
    "detect_emergency",
    "detect_human_request",
    "detect_identity_question",
    "disclosures",
    "emergency_instruction",
    "final_review",
    "guard_output",
    "identity_answer",
    "install_patterns",
    "latest_review",
    "load_patterns",
    "open_delimiter",
    "read_turn_signals",
    "record_disclosure",
    "record_intervention",
    "save_review",
]
