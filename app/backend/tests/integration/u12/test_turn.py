"""El punto único de entrada y salida de un turno (paso 7, el último de U12).

Cuatro bloques:

1. **El flujo siempre cerrado** (C-14): `handle_turn` termina en `FinalText`,
   `Handoff` o `TurnError`, nunca en silencio -- también cuando el nodo real
   `intake` levanta algo que el ejecutor no sabe convertir en degradación
   (BR2.5).
2. **La compuerta dura BR3.4, su mitad de texto**: dos casos frescos que
   comparten póliza reciben, letra por letra, la misma respuesta de
   `handle_turn`; y un caso con una respuesta de cobertura ya calculada no se
   la presta al que comparte su póliza.
3. **El desvío de cobertura** (BR4.2, BR4.3): una pregunta de cobertura a
   mitad del reporte no avanza el bloque de captura, y dos preguntas seguidas
   vuelven una sola vez al mismo bloque pendiente.
4. **La sonda genérica de conversación**: recorre el guion de un caso de DS-2
   por el nodo real `intake` y los dobles deterministas de los otros tres, y
   comprueba lo que el caso declara. Es la pieza reutilizable para escribir
   los once casos que le faltan a DS-2 (unit-test-instructions.md).

Los tres nodos de fondo son dobles deterministas (CG-U12-3): construirlos de
verdad --el corpus de pólizas, las reglas de la aseguradora, la revisión
completa-- es integración de proveedor y de datos que ninguna `Fronteras` de
`functional-spec.md` le pide a esta unidad (ver el docstring de
`graph_runtime.py`). `intake` sí es la clase real de U11, con su único
proveedor (el extractor) sustituido -- el mismo patrón que
`test_performance.py` ya usa.
"""

from __future__ import annotations

import asyncio
import contextvars
import io
import json
import sys
import uuid
from collections.abc import Callable, Coroutine, Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from untangle import observability, paths
from untangle.base import Frozen, Locale, ProviderErrorKind, ProviderName, SpendSource, Use
from untangle.case_record import api as casos_api
from untangle.case_record import crypto
from untangle.case_record.models import (
    Actor,
    ActorType,
    CaseField,
    CaseState,
    FieldStatus,
    Origin,
    RecordType,
    Speaker,
)
from untangle.case_record.models import (
    Channel as CaseChannel,
)
from untangle.compliance.controls.api import HandoffReason
from untangle.compliance.controls.signals import TurnSignals
from untangle.compliance.redaction import api as redaccion
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.evals import loading as evals_loading
from untangle.evals.models import GoldenCase
from untangle.evals.scripted_insured import ScriptedInsured
from untangle.orchestration import case_context, transcript_writer
from untangle.orchestration.checkpoint import TenantCheckpointSaver
from untangle.orchestration.executor import NodeExecutor
from untangle.orchestration.graph_runtime import BackgroundBinding, compile_background_graph
from untangle.orchestration.model_reply import agent_name_of
from untangle.orchestration.node_run_repository import DatabaseNodeRunStore
from untangle.orchestration.nodes.intake import composition, understanding
from untangle.orchestration.nodes.intake import suggestions as sugerencias
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.orchestration.nodes.intake.extraction import (
    ExtractedItem,
    ExtractionResponse,
)
from untangle.orchestration.nodes.intake.node import IntakeNode, IntakeNodeInput
from untangle.orchestration.nodes.intake.policy import PolicyMatch, PolicyMatchPort
from untangle.orchestration.nodes.policy_verification import phrases as coverage_phrases
from untangle.orchestration.pause_repository import DatabaseHumanReviewRequestStore
from untangle.orchestration.state import NodeSpec
from untangle.orchestration.turn import (
    GUARD_DEGRADED,
    FinalText,
    GraphRuntime,
    Handoff,
    InboundTurn,
    TurnError,
    TurnEvent,
    Waiting,
    handle_turn,
    install_runtime,
    reset_runtime,
    resume_case,
)
from untangle.providers.ports import (
    GenerationResult,
    InstructionText,
    PromptRef,
    ProviderError,
    SystemInstruction,
    UsageReport,
)
from untangle.telemetry.traces.models import NodeName
from untangle.tenancy import config as tenancy

from .conftest import nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u12")

_AHORA = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


# --- Dobles del ritmo de fondo: policy_verification, decision, compliance -----


class _NoInput(Frozen):
    """La entrada de un doble que no necesita leer nada del estado.

    Lleva la pregunta porque el nodo de cobertura **si** la necesita en produccion, y
    un doble cuya entrada no la tuviera dejaria pasar un `preload` que la perdiera por
    el camino.
    """

    question: str = ""
    #: El turno al que se ata la respuesta: en produccion es llave foranea (2026-10-08).
    turn_id: str = ""


class _CoverageOutput(Frozen):
    outcome: str
    response_text: str
    citations: tuple[dict[str, Any], ...] = ()


class _DecisionOutput(Frozen):
    category: str = "direct_close"


class _ComplianceOutput(Frozen):
    compliance_review: str = "reviewed"


@dataclass
class _FakeCoverageNode:
    """El doble de `policy_verification`: una respuesta fija, o una que espera una señal."""

    spec: NodeSpec = field(
        default_factory=lambda: NodeSpec(
            name=NodeName.POLICY_VERIFICATION,
            reads=frozenset(),
            writes=frozenset(_CoverageOutput.model_fields),
            rhythm="background",
            timeout_ms=5_000,
            attempts=1,
            degraded_copy_key="compliance.handoff.adjuster_review",
        )
    )
    gate: asyncio.Event | None = None
    # Sin monto ni afirmación en primera persona a propósito (BR2.5): una cita
    # real nunca las lleva, y con ellas la guardia real -- que estas pruebas
    # no sustituyen -- sustituiría la frase por la de "no puedo confirmar".
    response_text: str = "La cláusula RC-04 de su póliza aplica a este tipo de daño."

    #: Las entradas que recibio, para que una prueba pueda comprobar **que le llego la
    #: pregunta de la persona** y no una cadena vacia. Sin esto, un `preload` que
    #: perdiera la pregunta por el camino pasaria igual: el doble responde lo mismo
    #: mire lo que mire, que es la forma 12 del catalogo.
    entradas: list[_NoInput] = field(default_factory=list)

    async def run(self, state: _NoInput) -> _CoverageOutput:
        self.entradas.append(state)
        if self.gate is not None:
            await self.gate.wait()
        return _CoverageOutput(outcome="verified", response_text=self.response_text)


@dataclass
class _Avisos:
    """El doble del canal que recibe lo que el fondo calcula (fase 1): guarda cada aviso."""

    entregados: list[tuple[str, str, tuple[object, ...], tuple[str, ...]]] = field(
        default_factory=list
    )

    async def notify(  # noqa: PLR0913 -- la firma del puerto CaseNotifier
        self,
        tenant_id: str,
        case_id: str,
        *,
        text: str,
        citations: tuple[object, ...] = (),
        suggestions: tuple[str, ...] = (),
        coverage_outcome: str | None = None,
        language: str | None = None,
    ) -> bool:
        del tenant_id, coverage_outcome
        self.entregados.append((case_id, text, citations, suggestions))
        return True

    def para(self, case_id: str) -> list[str]:
        return [texto for caso, texto, _, _ in self.entregados if caso == case_id]


@dataclass
class _FakeDecisionNode:
    spec: NodeSpec = field(
        default_factory=lambda: NodeSpec(
            name=NodeName.DECISION,
            reads=frozenset(),
            writes=frozenset(_DecisionOutput.model_fields),
            rhythm="background",
            timeout_ms=2_000,
            attempts=1,
            degraded_copy_key="compliance.handoff.adjuster_review",
        )
    )

    async def run(self, _state: _NoInput) -> _DecisionOutput:
        return _DecisionOutput()


@dataclass
class _FakeComplianceNode:
    spec: NodeSpec = field(
        default_factory=lambda: NodeSpec(
            name=NodeName.COMPLIANCE,
            reads=frozenset(),
            writes=frozenset(_ComplianceOutput.model_fields),
            rhythm="background",
            timeout_ms=5_000,
            attempts=1,
            degraded_copy_key="compliance.handoff.adjuster_review",
        )
    )

    async def run(self, _state: _NoInput) -> _ComplianceOutput:
        return _ComplianceOutput()


# --- El doble del único proveedor de `intake`: el extractor --------------------


@dataclass
class _ScriptedExtractor:
    """El extractor real de `intake` es un proveedor (CG-U12-3): este doble no lo es.

    `next_items` lo fija la prueba antes de cada `handle_turn`, con lo que ese
    turno debería extraer -- el mismo patrón que `test_performance.py`
    (`_ExtractorInstantaneo`), parametrizable por turno.
    """

    next_items: tuple[ExtractedItem, ...] = ()
    raise_error: bool = False

    async def __call__(self, _prompt: object) -> GenerationResult:
        if self.raise_error:
            msg = "el proveedor de extracción no respondió (inyectado por la prueba)"
            raise RuntimeError(msg)
        return GenerationResult(
            text=None,
            parsed=ExtractionResponse(items=self.next_items),
            usage=UsageReport(
                provider=ProviderName.GEMINI,
                model="gemini-2.5-flash",
                use=Use.CHAT,
                source=SpendSource.PROVIDER_REPORTED,
            ),
            prompt=PromptRef(prompt_id="intake", locale="es", sha256="a" * 64),
        )


def _instruccion(_language: str) -> SystemInstruction:
    return SystemInstruction(
        ref=PromptRef(prompt_id="intake", locale="es", sha256="a" * 64),
        text=InstructionText("Eres la agente de captura. Nunca afirmes cobertura."),
    )


# --- El runtime de las pruebas: nodo real `intake`, dobles para el fondo ------


def _capturing_task_factory(
    tareas: list[asyncio.Task[object]],
) -> Callable[[Coroutine[Any, Any, None]], asyncio.Task[None]]:
    """Un `task_factory` que sí lanza de verdad (BR2.2), pero deja la tarea a mano.

    Mismo patrón que `test_rhythm.py::test_br2_2...`: el turno no espera nada
    -- `asyncio.create_task` real --, y la prueba controla cuándo el fondo
    "termina" esperando las tareas que este factory guardó.
    """

    def _factory(coro: Coroutine[Any, Any, None]) -> asyncio.Task[None]:
        # Contexto propio, no heredado (mismo motivo que
        # `turn._detached_task_factory`): el turno que dispara esto todavía
        # tiene su propio tramo de traza abierto.
        tarea = asyncio.create_task(coro, context=contextvars.Context())
        tareas.append(tarea)
        return tarea

    return _factory


def _build_intake_input(  # noqa: PLR0913 -- la firma de `IntakeInputBuilder`, con los dos ultimos por nombre
    contexto: case_context.CaseContext,
    turn: InboundTurn,
    signals: TurnSignals,
    emergency_instruction: str | None,
    *,
    awaiting_confirmation: Block | None = None,
    stated_values: dict[str, str] | None = None,
    awaiting_policy_confirmation: PolicyMatch | None = None,
) -> IntakeNodeInput:
    return case_context.build_intake_input(
        contexto,
        turn_text=turn.text,
        turn_id=f"turno-{uuid.uuid4().hex[:8]}",
        awaiting_policy_confirmation=awaiting_policy_confirmation,
        emergency_raised=signals.emergency,
        emergency_instruction=emergency_instruction,
        awaiting_confirmation=awaiting_confirmation,
        stated_values=stated_values,
    )


def _build_runtime(
    *,
    cipher: crypto.Cipher,
    extractor: _ScriptedExtractor,
    coverage_node: _FakeCoverageNode,
    tareas: list[asyncio.Task[object]],
    lookup: PolicyMatchPort | None = None,
) -> GraphRuntime:
    intake_node = IntakeNode(
        extract=extractor,
        instruction=_instruccion,
        clock=lambda: date(2026, 9, 27),
        lookup=lookup,
    )
    executor = NodeExecutor(store=DatabaseNodeRunStore(), clock=lambda: _AHORA)
    checkpointer = TenantCheckpointSaver(cipher=cipher)
    bindings: dict[NodeName, BackgroundBinding[Any, Any]] = {
        NodeName.POLICY_VERIFICATION: BackgroundBinding(
            node=coverage_node, build_input=lambda _s: _NoInput()
        ),
        NodeName.DECISION: BackgroundBinding(
            node=_FakeDecisionNode(), build_input=lambda _s: _NoInput()
        ),
        NodeName.COMPLIANCE: BackgroundBinding(
            node=_FakeComplianceNode(), build_input=lambda _s: _NoInput()
        ),
    }
    background_graph = compile_background_graph(
        bindings, executor=executor, checkpointer=checkpointer
    )
    return GraphRuntime(
        intake=intake_node,
        build_intake_input=_build_intake_input,
        background_graph=background_graph,
        # El nodo de cobertura entra **por el ejecutor directo**, como en produccion:
        # su entrada depende del caso y no solo de `GraphState`. La fabrica de entrada
        # de aqui es la del doble --que no mira nada-- pero recibe la pregunta, que es
        # lo que una prueba puede comprobar.
        coverage=coverage_node,
        build_coverage_input=lambda _contexto, pregunta, turno: _NoInput(
            question=pregunta, turn_id=turno
        ),
        executor=executor,
        checkpointer=checkpointer,
        pause_store=DatabaseHumanReviewRequestStore(),
        cipher=cipher,
        clock=lambda: _AHORA,
        task_factory=_capturing_task_factory(tareas),
    )


@pytest.fixture(autouse=True)
def _sin_estado_compartido() -> Iterator[None]:
    """Ni el runtime instalado ni la memoria de turnos de `case_context` cruzan pruebas."""
    reset_runtime()
    case_context._person_turns.clear()
    yield
    reset_runtime()
    case_context._person_turns.clear()


async def _turno(
    case_id: str,
    tenant_id: str,
    texto: str,
    *,
    channel: str = "chat",
    language: Locale = "es",
    **del_turno: Any,
) -> list[TurnEvent]:
    entrante = InboundTurn(
        tenant_id=tenant_id,
        session_ref=f"sesion-{case_id}",
        case_id=case_id,
        text=texto,
        language=language,
        channel=channel,  # type: ignore[arg-type]
        received_at=_AHORA,
        **del_turno,
    )
    # Como el canal: el mensaje de la persona se guarda antes de entregar el turno, y
    # la respuesta de cobertura se ata a el (2026-10-08).
    await transcript_writer.record_person_turn(
        transcript_writer.TranscriptScope(
            tenant_id=tenant_id,
            case_id=case_id,
            channel=CaseChannel.CHAT if channel == "chat" else CaseChannel.VOICE,
            language=language,
        ),
        text=texto,
        now=_AHORA,
    )
    return [evento async for evento in handle_turn(entrante)]


async def _nuevo_caso_en_idioma(tenant_id: str, *, language: Locale, policy_ref: str | None) -> str:
    """Como `conftest.nuevo_caso`, pero con el idioma que declare el caso de DS-2.

    `conftest.nuevo_caso` (paso 6, sin tocar) fija `language="es"` porque
    ninguna de sus pruebas necesitaba lo contrario; los dos casos de DS-2 en
    inglés sí lo necesitan -- `case_record.api.get_case(...).language` es de
    donde `intake` lee el idioma de su respuesta, no del `InboundTurn`.
    """
    case_id = f"u12-caso-{uuid.uuid4().hex[:12]}"
    await casos_api.create_case(
        tenant_id,
        casos_api.NewCase(
            case_id=case_id,
            record_type=RecordType.CLAIM,
            channel=CaseChannel.CHAT,
            origin=Origin.PUBLIC_CHAT,
            language=language,
            policy_ref=policy_ref,
        ),
        now=_AHORA,
    )
    return case_id


async def _seed_safety_confirmed(
    tenant_id: str, case_id: str, *, cipher: crypto.Cipher, language: Locale
) -> None:
    """Siembra `SAFETY` (heridos) ya confirmado, antes del primer turno.

    Mismo patrón que `evals/intake_probes.py` (ver el docstring de los dos
    casos de DS-2 de este archivo): la pregunta de seguridad la abre el
    primer turno del canal, que ninguna de las dos sondas modela, así que se
    siembra confirmada para que el guion, que empieza directo en
    `identity_and_policy`, avance por los bloques que sí prueba.
    """
    texto = {"es": "sin heridos", "en": "no injuries"}[language]
    await casos_api.set_field(
        tenant_id,
        CaseField(
            case_id=case_id,
            field_key="injuries",
            value=cipher.seal(texto),
            status=FieldStatus.CONFIRMED,
            evidence_turn_id="turno-safety-sembrado",
            confirmed_aloud_at=_AHORA,
            updated_at=_AHORA,
        ),
        cipher=cipher,
        actor=Actor(actor_type=ActorType.INSURED),
        channel=CaseChannel.CHAT,
    )


async def _drenar(tareas: list[asyncio.Task[object]]) -> None:
    """Espera lo que el ritmo de fondo lanzó, para comprobar su resultado (BR2.2)."""
    if tareas:
        await asyncio.gather(*tareas)
        tareas.clear()


# --- 1. El flujo siempre termina en uno de los tres eventos (C-14, BR2.5) -----


async def test_un_turno_normal_termina_en_final_text(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    tareas: list[asyncio.Task[object]] = []
    extractor = _ScriptedExtractor(
        next_items=(
            ExtractedItem(field_key="identity_and_policy", value="Marcela Rios, POL-000001"),
        )
    )
    runtime = _build_runtime(
        cipher=cifrador, extractor=extractor, coverage_node=_FakeCoverageNode(), tareas=tareas
    )
    install_runtime(runtime)

    eventos = await _turno(caso.case_id, propia, "Soy Marcela Rios, mi poliza es POL-000001.")

    assert len(eventos) == 1
    assert isinstance(eventos[0], FinalText)
    # `from_catalog` no es decoracion: es lo que le dice al canal que esta frase la
    # escribimos nosotros y que **no** se le puede pasar el detector de datos
    # personales (U18). Sin esta linea, quitarlo no rompia nada y la respuesta en
    # espanol volvia a salir con una palabra tachada en medio.
    assert eventos[0].from_catalog is True
    await _drenar(tareas)


async def test_br2_5_un_fallo_sin_politica_termina_en_turnerror_por_la_guardia(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """BR2.5, el camino de error: un fallo que ninguna política sabe degradar
    (ni `ProviderError` ni `TimeoutError`) igual termina en un evento cerrado,
    con su texto pasado por la guardia -- nunca la excepción cruda escapando
    al canal."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    tareas: list[asyncio.Task[object]] = []
    extractor = _ScriptedExtractor(raise_error=True)
    runtime = _build_runtime(
        cipher=cifrador, extractor=extractor, coverage_node=_FakeCoverageNode(), tareas=tareas
    )
    install_runtime(runtime)

    # Larga a proposito: una respuesta corta a la pregunta pendiente se guarda por
    # regla sin llamar al modelo (2026-10-07), y aqui lo que se prueba es el fallo
    # del modelo.
    eventos = await _turno(
        caso.case_id,
        propia,
        "Soy Marcela Rios, mi poliza es POL-000001, y le cuento que el choque fue ayer "
        "por la tarde saliendo del trabajo cuando un taxi se me atraveso",
    )

    assert len(eventos) == 1
    assert isinstance(eventos[0], TurnError)
    assert "el proveedor de extracción no respondió" not in eventos[0].text
    assert eventos[0].text  # la guardia resolvió una frase real, no un vacío


# --- 2. La compuerta dura BR3.4, su mitad de texto ----------------------------


async def test_br3_4_dos_casos_frescos_con_la_misma_poliza_responden_igual(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """La respuesta del segundo navegador es idéntica, letra por letra, a la
    de un caso sin ninguna relación -- la mitad "en texto" de BR3.4 que
    `test_resume.py` (paso 6) dejó escrita como pendiente de este paso."""
    _, propia = dos_aseguradoras
    poliza = "POL-000009"
    con_historia = await nuevo_caso(propia, policy_ref=poliza)
    misma_poliza_sin_historia = await nuevo_caso(propia, policy_ref=poliza)
    sin_relacion = await nuevo_caso(propia, policy_ref="POL-000010")

    texto_turno = "Soy Marcela Rios, mi poliza es POL-000001."
    tareas: list[asyncio.Task[object]] = []
    extractor = _ScriptedExtractor(
        next_items=(ExtractedItem(field_key="identity_and_policy", value="Marcela Rios"),)
    )
    runtime = _build_runtime(
        cipher=cifrador, extractor=extractor, coverage_node=_FakeCoverageNode(), tareas=tareas
    )
    install_runtime(runtime)

    eventos_historia = await _turno(con_historia.case_id, propia, texto_turno)
    await _drenar(tareas)
    eventos_b = await _turno(misma_poliza_sin_historia.case_id, propia, texto_turno)
    await _drenar(tareas)
    eventos_c = await _turno(sin_relacion.case_id, propia, texto_turno)
    await _drenar(tareas)

    def _texto(eventos: list[TurnEvent]) -> str:
        (final,) = [e for e in eventos if isinstance(e, FinalText)]
        return final.text

    assert _texto(eventos_b) == _texto(eventos_c) == _texto(eventos_historia)


async def test_br3_4_la_respuesta_de_cobertura_no_se_presta_al_que_comparte_poliza(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """La mitad "en texto" de BR3.4 sobre lo que más importa filtrar: una cita
    de cobertura ya calculada. El segundo navegador, sin su propia identidad
    confirmada, no tiene nada de fondo que ofrecer -- nunca lo del primero."""
    _, propia = dos_aseguradoras
    poliza = "POL-000011"
    con_historia = await nuevo_caso(propia, policy_ref=poliza)
    misma_poliza_sin_historia = await nuevo_caso(propia, policy_ref=poliza)

    tareas: list[asyncio.Task[object]] = []
    extractor = _ScriptedExtractor()
    coverage_node = _FakeCoverageNode(
        response_text="La cláusula RC-04 de su póliza aplica a este tipo de daño."
    )
    avisos = _Avisos()
    runtime = _build_runtime(
        cipher=cifrador, extractor=extractor, coverage_node=coverage_node, tareas=tareas
    )
    install_runtime(replace(runtime, notifier=avisos))

    extractor.next_items = (ExtractedItem(field_key="identity_and_policy", value="Juan Perez"),)
    await _turno(con_historia.case_id, propia, "Soy Juan Perez, mi poliza es POL-000011.")
    await _turno(con_historia.case_id, propia, "¿Está cubierto mi choque?")
    await _drenar(tareas)  # con_historia ya tiene una respuesta de cobertura calculada

    extractor.next_items = ()
    eventos = await _turno(misma_poliza_sin_historia.case_id, propia, "¿Está cubierto mi choque?")
    await _drenar(tareas)

    assert len(eventos) == 1
    # Fase 1 (2026-10-08): en el chat el turno dice que revisa la poliza y la respuesta
    # llega sola. Lo de BR3.4 sigue: ese turno no trae nada calculado para otro caso.
    assert isinstance(eventos[0], FinalText)
    assert "RC-04" not in eventos[0].text
    assert all(
        caso in {con_historia.case_id, misma_poliza_sin_historia.case_id}
        for caso, _, _, _ in avisos.entregados
    )

    # Y aqui esta la mitad que "no se filtro la cita" no cubre. BR3.4 no pide
    # que la respuesta **no traiga** el dato ajeno: pide que sea **identica** a
    # la de una sesion sin casos. Si el que comparte poliza recibiera algo
    # distinto de lo que recibe un desconocido -- aunque fuera una frase
    # inofensiva -- esa diferencia **es** la filtracion: le dice que por esa
    # poliza hay un caso abierto. Un tercer caso, sin ninguna relacion con la
    # poliza, hace la misma pregunta en las mismas condiciones.
    sin_relacion = await nuevo_caso(propia, policy_ref="POL-000012")
    extractor.next_items = ()
    eventos_sin_relacion = await _turno(sin_relacion.case_id, propia, "¿Está cubierto mi choque?")
    await _drenar(tareas)

    assert len(eventos_sin_relacion) == 1
    assert type(eventos[0]) is type(eventos_sin_relacion[0]), (
        "el que comparte poliza recibe un tipo de evento distinto del que recibe "
        "un desconocido: la diferencia ya revela que el caso del otro existe"
    )
    assert eventos[0].text == eventos_sin_relacion[0].text, (
        "misma pregunta, dos casos sin historia propia, y el texto difiere: "
        f"{eventos[0].text!r} vs {eventos_sin_relacion[0].text!r}"
    )


# --- 3. El desvío de cobertura: BR4.2, BR4.3 -----------------------------------


async def test_br4_2_la_pregunta_de_cobertura_no_escribe_ningun_campo_de_la_captura(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia, policy_ref="POL-000001")
    tareas: list[asyncio.Task[object]] = []
    extractor = _ScriptedExtractor()
    coverage_node = _FakeCoverageNode(
        response_text="La cláusula RC-04 de su póliza aplica a este tipo de daño."
    )
    avisos = _Avisos()
    runtime = _build_runtime(
        cipher=cifrador, extractor=extractor, coverage_node=coverage_node, tareas=tareas
    )
    install_runtime(replace(runtime, notifier=avisos))

    extractor.next_items = (
        ExtractedItem(field_key="identity_and_policy", value="Marcela Rios, POL-000001"),
    )
    await _turno(caso.case_id, propia, "Soy Marcela Rios, mi poliza es POL-000001.")
    await _drenar(tareas)

    completitud_antes = await case_context.completeness_of(propia, caso.case_id)

    extractor.next_items = ()  # una pregunta de cobertura no extrae ningún campo
    eventos_1 = await _turno(caso.case_id, propia, "¿Está cubierto mi choque?")
    await _drenar(tareas)
    eventos_2 = await _turno(caso.case_id, propia, "¿Y hasta cuánto cubre?")
    await _drenar(tareas)

    completitud_despues = await case_context.completeness_of(propia, caso.case_id)

    assert len(eventos_1) == 1, "el desvío tiene que cerrar el turno"
    assert isinstance(eventos_1[0], FinalText)
    assert len(eventos_2) == 1, "el desvío tiene que cerrar el turno"
    assert isinstance(eventos_2[0], FinalText)
    # Fase 1 (2026-10-08): la respuesta llega sola, una por pregunta, y retoma el
    # reporte en el mismo punto: BR4.3, la misma pregunta pendiente las dos veces.
    respuestas = avisos.para(caso.case_id)
    assert len(respuestas) == 2
    assert all("RC-04" in r for r in respuestas)
    assert respuestas[0] == respuestas[1]
    assert eventos_1[0].text == eventos_2[0].text
    # La respuesta de cobertura se compone del catálogo --el resumen de la cita, o la
    # frase de degradación--, y lo declara para que el canal no le pase el detector
    # de datos personales (U18). Sin esta aserción, quitarlo no rompía nada y en
    # español la respuesta salía diciendo "[LUGAR 1] la cláusula dentro de...".
    assert eventos_1[0].from_catalog is True
    # BR4.2: el desvío no escribió ningún campo de la captura.
    assert completitud_despues == completitud_antes
    # Y quedan en la conversación: llegaban solo en vivo, y al volver al chat ya no
    # estaban (visto el 2026-10-08).
    dichos = [t.text_redacted for t in await casos_api.transcript_of(propia, caso.case_id)]
    assert sum(1 for d in dichos if "RC-04" in d) == 2


async def test_en_una_llamada_la_pregunta_de_cobertura_se_espera_y_se_responde(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Decision de Miguel del 2026-10-11. Antes la agente decia "dejame revisar tu
    poliza" y la respuesta no llegaba: quien la entregaba solo conocia el chat. Y la
    segunda pregunta recibia la respuesta de la primera, que seguia guardada."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia, policy_ref="POL-000001")
    tareas: list[asyncio.Task[object]] = []
    extractor = _ScriptedExtractor()
    coverage_node = _FakeCoverageNode(response_text="La cláusula RC-04 trata este daño.")
    avisos = _Avisos()
    runtime = _build_runtime(
        cipher=cifrador, extractor=extractor, coverage_node=coverage_node, tareas=tareas
    )
    install_runtime(replace(runtime, notifier=avisos))

    extractor.next_items = ()
    eventos_1 = await _turno(caso.case_id, propia, "¿Está cubierto mi choque?", channel="voice")
    await _drenar(tareas)
    coverage_node.response_text = "La cláusula RC-07 trata la grúa."
    eventos_2 = await _turno(caso.case_id, propia, "¿Y me cubre la grúa?", channel="voice")
    await _drenar(tareas)

    # El turno cierra con la frase de espera, que es lo que le dice a la llamada
    # que viene una respuesta.
    assert [type(e) for e in eventos_1] == [Waiting]
    assert [type(e) for e in eventos_2] == [Waiting]
    respuestas = avisos.para(caso.case_id)
    assert len(respuestas) == 2
    assert "RC-04" in respuestas[0]
    # Cada pregunta, su respuesta: no la que quedo guardada de la anterior.
    assert "RC-07" in respuestas[1]
    assert "RC-04" not in respuestas[1]
    # Lo pendiente lo retoma quien habla, al decirla: aqui no va pegado.
    retomar = coverage_phrases.back_to_report_text(locale="es")
    assert all(retomar not in r for r in respuestas)
    # Y queda en la transcripcion como turno de la llamada.
    de_la_agente = [
        t
        for t in await casos_api.transcript_of(propia, caso.case_id)
        if t.speaker is Speaker.AGENT and "RC-0" in t.text_redacted
    ]
    assert [t.channel for t in de_la_agente] == [CaseChannel.VOICE, CaseChannel.VOICE]


async def test_en_una_llamada_sin_poliza_se_dice_que_hace_falta(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Antes salia la frase de "no pude preparar esta respuesta", que no era verdad:
    lo que falta es la poliza."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    tareas: list[asyncio.Task[object]] = []
    extractor = _ScriptedExtractor()
    runtime = _build_runtime(
        cipher=cifrador, extractor=extractor, coverage_node=_FakeCoverageNode(), tareas=tareas
    )
    install_runtime(replace(runtime, notifier=_Avisos()))

    extractor.next_items = ()
    eventos = await _turno(caso.case_id, propia, "¿Está cubierto mi choque?", channel="voice")

    assert len(eventos) == 1
    assert isinstance(eventos[0], FinalText)
    assert eventos[0].text.startswith(coverage_phrases.need_policy_text(locale="es"))


async def test_la_pregunta_de_la_persona_llega_al_nodo_de_cobertura(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Lo que se verifica es **lo que preguntó**, no una cadena vacía.

    `preload` recibía solo el caso, así que la pregunta se quedaba en el turno y el
    nodo de fondo habría verificado contra nada. Un doble que no mira su entrada deja
    pasar eso entero --la forma 12 del catálogo--, así que este la guarda y aquí se
    compara con lo que la persona escribió.

    Se pregunta **de primeras**, sin turno de identidad delante: la póliza ya está en
    el caso, y con un turno de captura antes el ritmo de fondo ya habría corrido su
    precarga y el desvío respondería del estado sin lanzar nada (BR4.3), que es
    correcto y dejaría esta prueba mirando una lista vacía.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia, policy_ref="POL-000001")
    tareas: list[asyncio.Task[object]] = []
    coverage_node = _FakeCoverageNode()
    install_runtime(
        _build_runtime(
            cipher=cifrador,
            extractor=_ScriptedExtractor(),
            coverage_node=coverage_node,
            tareas=tareas,
        )
    )

    await _turno(caso.case_id, propia, "¿Mi póliza cubre el granizo?")
    await _drenar(tareas)

    assert coverage_node.entradas, "el desvío no lanzó la verificación"
    assert coverage_node.entradas[-1].question == "¿Mi póliza cubre el granizo?"
    # La respuesta se guarda con llave foranea al turno: uno inventado la rompia en
    # produccion y ninguna respuesta de cobertura llegaba (2026-10-08).
    [pregunta] = await casos_api.transcript_of(propia, caso.case_id)
    assert coverage_node.entradas[-1].turn_id == pregunta.turn_id


async def test_sin_ritmo_de_fondo_el_desvio_no_promete_lo_que_no_puede_traer(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Un despliegue con el ritmo del turno cableado y el de fondo todavía no.

    Es el estado real de hoy: la raíz de composición enchufa `intake` y deja
    `background_graph` en `None` a propósito, porque los tres enlaces de fondo
    necesitan entradas que `GraphState` no lleva. La frase de espera **no cierra el
    turno**, así que prometerla aquí dejaría al navegador esperando una respuesta
    que nadie va a traer -- que es el modo de fallo que REL-U13.1 prohíbe. Se
    responde con la frase de degradación del catálogo, que sí lo cierra.

    Y **no** con la de "no pude verificar" (`policy_rag.coverage.unverifiable`): esa
    la escribe el nodo cuando de verdad intentó verificar y no pudo, y usarla aquí
    contaminaría una cifra publicada con un fallo de cableado, que es exactamente lo
    que la convención 8 del equipo prohíbe colapsar.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia, policy_ref="POL-000001")
    tareas: list[asyncio.Task[object]] = []
    extractor = _ScriptedExtractor()
    completo = _build_runtime(
        cipher=cifrador, extractor=extractor, coverage_node=_FakeCoverageNode(), tareas=tareas
    )
    install_runtime(replace(completo, background_graph=None, coverage=None))

    # El caso tiene que estar capturando para que el desvío sea alcanzable: es la
    # misma preparación que el resto de esta sección.
    extractor.next_items = (
        ExtractedItem(field_key="identity_and_policy", value="Marcela Rios, POL-000001"),
    )
    await _turno(caso.case_id, propia, "Soy Marcela Rios, mi poliza es POL-000001.")

    extractor.next_items = ()
    eventos = await _turno(caso.case_id, propia, "¿Está cubierto mi choque?")

    assert len(eventos) == 1
    evento = eventos[0]
    assert isinstance(evento, TurnError), f"el turno no se cerró: {evento}"
    assert evento.copy_key == GUARD_DEGRADED
    assert evento.code == "background_rhythm_unavailable"
    # Y nada se lanzó: sin grafo de fondo no hay trabajo que lanzar.
    assert tareas == []


async def test_sin_ritmo_de_fondo_reanudar_no_revienta_la_decision_de_la_bandeja(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """La bandeja registra la decisión **antes** de reanudar, y reanudar viene después.

    Si esto levantara, una decisión ya firmada y válida devolvería un `500` por una
    pausa que no existe: el `interrupt()` que `resume_case` retira solo lo abre el
    grafo de fondo, así que sin él ningún caso puede estar pausado así. Lo que no vale
    es no hacer nada **en silencio**, y de eso se encarga su evento.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    tareas: list[asyncio.Task[object]] = []
    completo = _build_runtime(
        cipher=cifrador,
        extractor=_ScriptedExtractor(),
        coverage_node=_FakeCoverageNode(),
        tareas=tareas,
    )
    install_runtime(replace(completo, background_graph=None, coverage=None))

    eventos = io.StringIO()
    observability.set_stream(eventos)
    try:
        await resume_case(caso.case_id, "approve", tenant_id=propia)
    finally:
        observability.set_stream(sys.stdout)

    assert "orchestration.resume_without_background_rhythm" in eventos.getvalue(), (
        "reanudar sin ritmo de fondo no hizo nada y no lo dijo"
    )


async def test_br4_2_tras_el_desvio_la_captura_sigue_exactamente_donde_iba(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Control positivo del anterior: sin el desvío, el mismo turno de captura
    produce la misma respuesta que con dos preguntas de cobertura en medio."""
    _, propia = dos_aseguradoras
    con_desvio = await nuevo_caso(propia, policy_ref="POL-000001")
    sin_desvio = await nuevo_caso(propia, policy_ref="POL-000001")
    tareas: list[asyncio.Task[object]] = []
    extractor = _ScriptedExtractor()
    coverage_node = _FakeCoverageNode(
        response_text="La cláusula RC-04 de su póliza aplica a este tipo de daño."
    )
    runtime = _build_runtime(
        cipher=cifrador, extractor=extractor, coverage_node=coverage_node, tareas=tareas
    )
    install_runtime(runtime)

    identidad = ExtractedItem(field_key="identity_and_policy", value="Marcela Rios, POL-000001")
    siguiente_turno = "Un camion me choco por detras."
    siguiente_campo = ExtractedItem(field_key="description", value=siguiente_turno)

    for caso in (con_desvio, sin_desvio):
        case_context.forget_case(propia, caso.case_id)
        extractor.next_items = (identidad,)
        await _turno(caso.case_id, propia, "Soy Marcela Rios, mi poliza es POL-000001.")
        await _drenar(tareas)

    extractor.next_items = ()
    await _turno(con_desvio.case_id, propia, "¿Está cubierto mi choque?")
    await _turno(con_desvio.case_id, propia, "¿Y hasta cuánto cubre?")

    extractor.next_items = (siguiente_campo,)
    respuesta_con_desvio = await _turno(con_desvio.case_id, propia, siguiente_turno)
    respuesta_sin_desvio = await _turno(sin_desvio.case_id, propia, siguiente_turno)

    texto_con = next(e.text for e in respuesta_con_desvio if isinstance(e, FinalText))
    texto_sin = next(e.text for e in respuesta_sin_desvio if isinstance(e, FinalText))
    assert texto_con == texto_sin


# --- 4. La sonda genérica de conversación, sobre los dos casos de DS-2 --------


def _campos_declarados(case: GoldenCase) -> tuple[str, ...]:
    """Los campos de `case.script`, en el orden de declaración y sin repetir."""
    vistos: list[str] = []
    for respuesta in case.script:
        if respuesta.field_key not in vistos:
            vistos.append(respuesta.field_key)
    return tuple(vistos)


async def _run_scripted_case(  # noqa: PLR0913 -- el caso, sus tres llaves de identidad y los dos colaboradores (extractor, asegurado), ninguno derivable de otro
    case: GoldenCase,
    *,
    tenant_id: str,
    case_id: str,
    extractor: _ScriptedExtractor,
    responder: ScriptedInsured,
    tareas: list[asyncio.Task[object]],
    fields: tuple[str, ...] | None = None,
) -> dict[str, list[TurnEvent]]:
    """La sonda genérica: recorre el guion de un caso de DS-2 por los nodos reales.

    Sirve para **cualquier** caso de DS-2 cuyo `script` esté indexado por campo
    (`ScriptAnswer`, el mismo formato que ya usa `ScriptedInsured` en
    `evals/intake_probes.py`): contesta cada campo en el orden en que el caso
    lo declara -- o el subconjunto y el orden que `fields` pida, para dirigir
    solo un tramo de la captura -- con el asegurado simulado real, no una
    segunda implementación, y devuelve los eventos de cada turno por campo.

    `responder` se recibe ya construido, y no una vez por llamada: lleva
    estado (qué corrección ya entregó, `evals/scripted_insured.py`) y una
    prueba que dirige el mismo caso en dos tramos -- antes y después de un
    desvío o de un reinicio simulado -- necesita el mismo asegurado
    recordando por dónde iba, igual que una persona real no repite lo que ya
    dijo.

    Quien escriba el siguiente caso de DS-2 (el encargo reservado para la
    nube) tiene aquí, de un vistazo, qué declara un caso (`script`,
    `expected_verdicts`) y qué comprueba esta sonda (los eventos reales de
    `handle_turn`, uno por campo). Lo que la sonda **no** hace por sí sola es
    decidir cuándo insertar una pregunta de cobertura o un reinicio simulado
    -- eso es un guion de la unidad que se está probando, no del esquema de
    `GoldenCase` (ver el docstring de los dos casos), así que cada prueba de
    este archivo llama a `_turno` directamente para esos puntos y usa esta
    función para los tramos de captura pura alrededor.

    Drena el fondo (`tareas`) después de **cada** turno, no solo al final:
    `identity_and_policy` dispara `preload` (BR2.1), y un segundo turno que
    llegara mientras ese trabajo de fondo todavía escribe sus propios puntos
    de control competiría por el mismo número de paso del mismo hilo con el
    punto de control que ese segundo turno también tiene que escribir
    (BR3.1) -- las dos escrituras son reales, contra la misma base, y nada
    en `TenantCheckpointSaver` las serializa entre sí.
    """
    eventos_por_campo: dict[str, list[TurnEvent]] = {}
    for campo in fields if fields is not None else _campos_declarados(case):
        respuesta = responder.answer(campo)
        extractor.next_items = (ExtractedItem(field_key=campo, value=respuesta.text),)
        eventos_por_campo[campo] = await _turno(
            case_id,
            tenant_id,
            respuesta.text,
            channel="voice" if case.channel == "voice" else "chat",
            language=case.language,
        )
        await _drenar(tareas)
    return eventos_por_campo


def _load_ds2(slug: str, language: str) -> GoldenCase:
    ruta = paths.repo_root() / "app" / "evals" / "cases" / "ds2" / slug / f"{language}.yaml"
    return evals_loading.load_case(ruta)


@pytest.mark.parametrize("language", ["es", "en"])
async def test_ds2_coverage_question_mid_report(language: Locale, cifrador: crypto.Cipher) -> None:
    """`DS-2/{es,en}/coverage-question-mid-report`: AC2.4.1, AC2.4.2, BR4.2, BR4.3.

    Antes de que `handle_turn` existiera, esta prueba fallaba con un
    `ImportError` nombrando `untangle.orchestration.turn` -- el módulo de este
    paso, que hoy no existía (el eje de DS-2 que `unit-test-instructions.md`
    pide escribir primero). Con `handle_turn` construido, corre el guion real.
    """
    caso = _load_ds2("coverage-question-mid-report", language)
    tenant_id = caso.tenant or "knotwell"
    case_id = await _nuevo_caso_en_idioma(tenant_id, language=language, policy_ref="POL-000001")
    await _seed_safety_confirmed(tenant_id, case_id, cipher=cifrador, language=language)
    case_context.forget_case(tenant_id, case_id)

    tareas: list[asyncio.Task[object]] = []
    extractor = _ScriptedExtractor()
    # Sin monto ni afirmación en primera persona (BR2.5): una cita real nunca
    # las lleva (convención del proyecto), y con ellas la guardia sustituiría
    # esta frase por la de "no puedo confirmar" -- justo lo que le pasó a esta
    # prueba antes de corregirlo.
    texto_cobertura = {
        "es": "La cláusula de responsabilidad civil de su póliza aplica a este tipo de daño.",
        "en": "Your policy's liability clause applies to this kind of damage.",
    }[language]
    coverage_node = _FakeCoverageNode(response_text=texto_cobertura)
    avisos = _Avisos()
    runtime = _build_runtime(
        cipher=cifrador, extractor=extractor, coverage_node=coverage_node, tareas=tareas
    )
    install_runtime(replace(runtime, notifier=avisos))

    # 1) identity_and_policy, y solo ese campo: dispara el fondo (BR2.1).
    responder = ScriptedInsured(caso)
    await _run_scripted_case(
        caso,
        tenant_id=tenant_id,
        case_id=case_id,
        extractor=extractor,
        responder=responder,
        tareas=tareas,
        fields=("identity_and_policy",),
    )

    completitud_antes = await case_context.completeness_of(tenant_id, case_id)

    # 2) La pregunta de cobertura, dos veces seguidas (AC2.4.1, AC2.4.2).
    pregunta = {"es": "¿Está cubierto mi choque?", "en": "Is my crash covered?"}[language]
    extractor.next_items = ()
    eventos_1 = await _turno(case_id, tenant_id, pregunta, language=language)
    await _drenar(tareas)
    eventos_2 = await _turno(case_id, tenant_id, pregunta, language=language)
    await _drenar(tareas)

    completitud_despues = await case_context.completeness_of(tenant_id, case_id)

    assert len(eventos_1) == 1, "el desvío tiene que cerrar el turno"
    assert isinstance(eventos_1[0], FinalText)
    assert len(eventos_2) == 1, "el desvío tiene que cerrar el turno"
    assert isinstance(eventos_2[0], FinalText)
    assert eventos_1[0].text == eventos_2[0].text
    # Fase 1: la respuesta llega sola, con la frase de la cita, y retoma el reporte.
    respuestas = avisos.para(case_id)
    assert len(respuestas) == 2
    assert all(texto_cobertura in r for r in respuestas), respuestas
    assert completitud_despues == completitud_antes

    # 3) La captura sigue: el siguiente campo del guion se pide con normalidad.
    siguiente_campo = next(c for c in _campos_declarados(caso) if c != "identity_and_policy")
    eventos_resto = await _run_scripted_case(
        caso,
        tenant_id=tenant_id,
        case_id=case_id,
        extractor=extractor,
        responder=responder,
        tareas=tareas,
        fields=(siguiente_campo,),
    )
    eventos_3 = eventos_resto[siguiente_campo]
    assert isinstance(eventos_3[0], FinalText)
    assert texto_cobertura not in eventos_3[0].text

    assert caso.expected_verdicts == {
        "coverage_question_mid_report_does_not_derail_capture": "pass",
        "two_consecutive_coverage_questions_return_once": "pass",
    }


@pytest.mark.parametrize("language", ["es", "en"])
async def test_ds2_dropped_call_resumed(language: Locale, cifrador: crypto.Cipher) -> None:
    """`DS-2/{es,en}/dropped-call-resumed`: BR3.1, BR3.2.

    Simula el reinicio del proceso -- mismo patrón que
    `test_resume.py::test_reanudar_tras_un_reinicio_simulado_lee_lo_confirmado`
    (paso 6) -- con un `GraphRuntime` nuevo sobre la misma base: nada se
    comparte con el turno de antes del corte salvo la base de datos.
    """
    caso = _load_ds2("dropped-call-resumed", language)
    tenant_id = caso.tenant or "knotwell"
    case_id = await _nuevo_caso_en_idioma(tenant_id, language=language, policy_ref="POL-000002")
    await _seed_safety_confirmed(tenant_id, case_id, cipher=cifrador, language=language)
    case_context.forget_case(tenant_id, case_id)
    responder = ScriptedInsured(caso)

    orden = _campos_declarados(caso)
    antes_del_corte, despues_del_corte = orden[:2], orden[2:]
    assert despues_del_corte, "el guion necesita al menos tres campos para simular un corte a mitad"

    # --- Antes del corte: un runtime, un proceso -------------------------------
    tareas_1: list[asyncio.Task[object]] = []
    extractor_1 = _ScriptedExtractor()
    runtime_1 = _build_runtime(
        cipher=cifrador, extractor=extractor_1, coverage_node=_FakeCoverageNode(), tareas=tareas_1
    )
    install_runtime(runtime_1)
    await _run_scripted_case(
        caso,
        tenant_id=tenant_id,
        case_id=case_id,
        extractor=extractor_1,
        responder=responder,
        tareas=tareas_1,
        fields=antes_del_corte,
    )

    completitud_antes_del_corte = await case_context.completeness_of(tenant_id, case_id)
    for campo in antes_del_corte:
        assert completitud_antes_del_corte.per_field.get(campo) is True

    # --- "Se corta la llamada": se pierde todo lo que no sea la base -----------
    reset_runtime()
    case_context.forget_case(tenant_id, case_id)

    # --- Una sesión nueva retoma el mismo caso ---------------------------------
    tareas_2: list[asyncio.Task[object]] = []
    extractor_2 = _ScriptedExtractor()
    runtime_2 = _build_runtime(
        cipher=cifrador, extractor=extractor_2, coverage_node=_FakeCoverageNode(), tareas=tareas_2
    )
    install_runtime(runtime_2)

    eventos_resto = await _run_scripted_case(
        caso,
        tenant_id=tenant_id,
        case_id=case_id,
        extractor=extractor_2,
        responder=responder,
        tareas=tareas_2,
        fields=despues_del_corte,
    )
    eventos_finales = eventos_resto[despues_del_corte[-1]]

    completitud_final = await case_context.completeness_of(tenant_id, case_id)
    for campo in antes_del_corte:
        assert completitud_final.per_field.get(campo) is True, (
            f"'{campo}' se confirmó antes del corte y la reanudación lo perdió (BR3.2)"
        )
    for campo in despues_del_corte:
        assert completitud_final.per_field.get(campo) is True

    assert isinstance(eventos_finales[0], FinalText)
    assert caso.expected_verdicts == {
        "resume_after_simulated_restart_does_not_reask_confirmed_fields": "pass"
    }


# --- La lectura de confirmación cierra el bloque (BR3.1, FD-U11-8) ------------
#
# **Es el defecto que Miguel vio el 2026-09-29**: contestó "no, todos bien", dio
# su nombre y su póliza, y la agente volvió a preguntar "¿hubo alguien herido?"
# dos veces más. Las pruebas de la unidad no lo veían porque ninguna llegaba a un
# segundo turno sobre el mismo campo: el defecto solo existe **entre** turnos.


async def _campo(tenant_id: str, case_id: str, clave: str) -> CaseField | None:
    resultado = await casos_api.summary_with_fields(tenant_id, case_id)
    if resultado is None:
        return None
    _, campos = resultado
    return next((campo for campo in campos if campo.field_key == clave), None)


async def _sembrar_dichos(
    tenant_id: str, case_id: str, *, cipher: crypto.Cipher, **valores: str
) -> None:
    """Siembra campos ya dichos (`stated`), como los deja un turno de la captura."""
    for clave, texto in valores.items():
        await casos_api.set_field(
            tenant_id,
            CaseField(
                case_id=case_id,
                field_key=clave,
                value=cipher.seal(texto),
                status=FieldStatus.STATED,
                evidence_turn_id=f"turno-{clave}-sembrado",
                updated_at=_AHORA,
            ),
            cipher=cipher,
            actor=Actor(actor_type=ActorType.INSURED),
            channel=CaseChannel.CHAT,
        )


def _dicho(eventos: list[TurnEvent]) -> str:
    return " ".join(e.text for e in eventos if isinstance(e, FinalText))


async def test_lo_dicho_cuenta_sin_lectura_y_la_agente_sigue(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """P4: lo que la persona dice se guarda y cuenta; nadie le pregunta si es correcto.

    Hasta el 2026-10-06 el campo quedaba `stated` sin contar, la agente lo leia de
    vuelta y pedia un si. Miguel: «no quiero que el chat pregunte si es correcto lo
    que le estan diciendo, simplemente quiero que lo que le digan lo guarde».
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    tareas: list[asyncio.Task[object]] = []
    extractor = _ScriptedExtractor(
        next_items=(ExtractedItem(field_key="injuries", value="nadie se lastimó"),)
    )
    install_runtime(
        _build_runtime(
            cipher=cifrador, extractor=extractor, coverage_node=_FakeCoverageNode(), tareas=tareas
        )
    )

    eventos = await _turno(caso.case_id, propia, "no, todos bien, nadie se lastimó")

    dicho = await _campo(propia, caso.case_id, "injuries")
    assert dicho is not None
    assert dicho.status is FieldStatus.STATED
    vista = await casos_api.get_case(propia, caso.case_id)
    assert vista is not None
    assert vista.completeness.per_field["injuries"] is True, "lo dicho cuenta sin confirmarlo"
    respuesta = _dicho(eventos)
    assert "nadie se lastimó" not in respuesta, f"lo leyo de vuelta: {respuesta!r}"
    assert "?" in respuesta and "herid" not in respuesta.lower(), (
        f"tenia que seguir con otra pregunta: {respuesta!r}"
    )
    await _drenar(tareas)


async def test_perdon_no_eran_dos_sino_tres_reemplaza_el_dato_y_lo_dice(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """P4: un dato ya dicho que vuelve a decirse se reemplaza y se anuncia."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    tareas: list[asyncio.Task[object]] = []
    extractor = _ScriptedExtractor(
        next_items=(ExtractedItem(field_key="injuries", value="dos heridos"),)
    )
    install_runtime(
        _build_runtime(
            cipher=cifrador, extractor=extractor, coverage_node=_FakeCoverageNode(), tareas=tareas
        )
    )
    await _turno(caso.case_id, propia, "hubo dos heridos")

    extractor.next_items = (ExtractedItem(field_key="injuries", value="tres heridos"),)
    eventos = await _turno(caso.case_id, propia, "perdón, no eran dos sino tres")

    valores = await casos_api.open_field_values(
        propia, caso.case_id, ("injuries",), cipher=cifrador
    )
    assert valores == {"injuries": "tres heridos"}, "lo nuevo reemplaza a lo anterior"
    respuesta = _dicho(eventos)
    assert respuesta.startswith(composition.compose_correction("tres heridos", language="es")), (
        respuesta
    )
    assert "herid" not in respuesta.split(".", 1)[1].lower(), (
        f"volvio a preguntar por lo corregido: {respuesta!r}"
    )
    await _drenar(tareas)


async def test_con_los_obligatorios_dichos_el_caso_pasa_a_revision_en_ese_turno(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """P4 + US1.17: el ultimo obligatorio cierra la captura, la agente dice que ya tiene lo
    necesario y ofrece lo opcional, y el caso **ya esta en revision** cuando lo dice: ni
    cerrado ni con un ajustador, porque las reglas todavia no decidieron.

    Hasta el 2026-10-13 el caso se derivaba aqui mismo, siempre. Hasta el 2026-10-06 un
    siniestro completo nunca salia de `capturing`, y la cola excluye ese estado: nada de lo
    capturado por el chat llegaba a nadie.
    """
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _sembrar_dichos(
        propia,
        caso.case_id,
        cipher=cifrador,
        identity_and_policy="Laura Gomez, POL-480915",
        description="me chocaron por detras",
        incident_datetime="ayer a las cinco",
        location="avenida Boyaca con calle 80",
    )
    tareas: list[asyncio.Task[object]] = []
    extractor = _ScriptedExtractor(
        next_items=(ExtractedItem(field_key="injuries", value="nadie se lastimó"),)
    )
    install_runtime(
        _build_runtime(
            cipher=cifrador, extractor=extractor, coverage_node=_FakeCoverageNode(), tareas=tareas
        )
    )

    eventos = await _turno(caso.case_id, propia, "no, nadie se lastimó")

    vista = await casos_api.get_case(propia, caso.case_id)
    assert vista is not None
    assert vista.state is CaseState.DECIDING, f"el caso esta en {vista.state.value}"
    respuesta = _dicho(eventos)
    assert str(vista.case_number) in respuesta, f"el cierre no nombra el caso: {respuesta!r}"
    assert "ajustador" not in respuesta.lower(), f"promete un ajustador: {respuesta!r}"
    assert composition.block_label(Block.VEHICLE_AND_DRIVER, language="es") in respuesta, (
        f"no ofrecio lo opcional: {respuesta!r}"
    )

    # Con la oferta abierta el desenlace espera: ni se cierra ni se deriva.
    await _drenar(tareas)
    vista = await casos_api.get_case(propia, caso.case_id)
    assert vista is not None
    assert vista.state is CaseState.DECIDING, "la oferta sin contestar no puede decidir el caso"

    # Y la respuesta a la oferta llega con el caso en revision y se anota igual.
    extractor.next_items = (ExtractedItem(field_key="vehicle_and_driver", value="mi Mazda, yo"),)
    eventos = await _turno(caso.case_id, propia, "iba en mi Mazda, conducía yo")
    valores = await casos_api.open_field_values(
        propia, caso.case_id, ("vehicle_and_driver",), cipher=cifrador
    )
    assert valores == {"vehicle_and_driver": "mi Mazda, yo"}
    assert "?" in _dicho(eventos), "quedaba un bloque opcional por ofrecer"
    await _drenar(tareas)
    vista = await casos_api.get_case(propia, caso.case_id)
    assert vista is not None
    assert vista.state is CaseState.DECIDING, "seguia habiendo una oferta abierta"

    # Al declinar lo que queda, la oferta se cierra y el caso llega a su desenlace: este
    # despliegue de prueba no tiene reglas cableadas, y sin decision de cierre se deriva.
    extractor.next_items = ()
    await _turno(caso.case_id, propia, "no, así está bien")
    await _drenar(tareas)
    vista = await casos_api.get_case(propia, caso.case_id)
    assert vista is not None
    assert vista.state is CaseState.DERIVED, f"el caso sigue en {vista.state.value}"
    # **Derivado en un turno que la transcripcion tiene** (2026-10-11). Se acotaba al
    # identificador interno del turno del grafo, que no esta en ella, y la revision
    # de cumplimiento de todo reporte cerrado asi fallaba al buscarlo.
    en_la_transcripcion = {t.turn_id for t in await casos_api.transcript_of(propia, caso.case_id)}
    assert vista.derived_turn_id in en_la_transcripcion, vista.derived_turn_id


# --- Fase 0 (2026-10-07): el turno entiende el mensaje con el contexto del caso ---


@dataclass
class _Entendedor:
    """Un entendedor de mentira: devuelve lo que se le diga y guarda lo que vio."""

    respuesta: understanding.UnderstandingResponse
    peticiones: list[understanding.UnderstandingRequest] = field(default_factory=list)

    async def __call__(
        self, peticion: understanding.UnderstandingRequest
    ) -> understanding.UnderstandingResponse:
        self.peticiones.append(peticion)
        return self.respuesta


async def _turno_con_entendedor(  # noqa: PLR0913 -- el escenario de la prueba, por nombre
    dos_aseguradoras: tuple[str, str],
    cifrador: crypto.Cipher,
    entendedor: _Entendedor,
    texto: str,
    *,
    extractor: _ScriptedExtractor | None = None,
    channel: str = "chat",
    dicho_antes: tuple[str, ...] = (),
    sembrar: dict[str, str] | None = None,
    **del_turno: Any,
) -> tuple[str, list[TurnEvent]]:
    """Un turno con un entendedor de mentira. `dicho_antes` es lo que la agente ya habia dicho
    (guardado como lo guarda el canal) y `sembrar` los datos que la persona ya habia dado."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    for orden, dicho in enumerate(dicho_antes):
        await transcript_writer.record_agent_turn(
            transcript_writer.TranscriptScope(
                tenant_id=propia,
                case_id=caso.case_id,
                channel=CaseChannel.CHAT,
                language="es",
            ),
            text=dicho,
            now=_AHORA - timedelta(minutes=len(dicho_antes) - orden),
            from_catalog=False,
        )
    if sembrar:
        await _sembrar_dichos(propia, caso.case_id, cipher=cifrador, **sembrar)
    tareas: list[asyncio.Task[object]] = []
    base = _build_runtime(
        cipher=cifrador,
        extractor=extractor or _ScriptedExtractor(),
        coverage_node=_FakeCoverageNode(),
        tareas=tareas,
    )
    install_runtime(replace(base, understander=entendedor))
    eventos = await _turno(caso.case_id, propia, texto, channel=channel, **del_turno)
    await _drenar(tareas)
    return caso.case_id, eventos


async def test_los_datos_entendidos_llegan_al_caso_sin_el_extractor(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    entendedor = _Entendedor(
        understanding.UnderstandingResponse(
            wants=understanding.Want.CONTINUE,
            items=(understanding.UnderstoodItem(field_key="injuries", value="no"),),
        )
    )
    extractor = _ScriptedExtractor(raise_error=True)

    case_id, eventos = await _turno_con_entendedor(
        dos_aseguradoras,
        cifrador,
        entendedor,
        "tranquila, ninguno salió lastimado",
        extractor=extractor,
    )

    assert any(isinstance(e, FinalText) for e in eventos)
    vista = await casos_api.get_case(dos_aseguradoras[1], case_id)
    assert vista is not None
    assert vista.completeness.per_field["injuries"]
    [peticion] = entendedor.peticiones
    assert peticion.record_type is RecordType.CLAIM
    assert "injuries" in peticion.missing


async def test_un_dato_y_una_pregunta_de_cobertura_en_el_mismo_mensaje_no_pierden_el_dato(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """RT-10 (2026-10-09): «Nadie se lastimo. ¿Mi poliza cubre esto?» contestaba la
    pregunta y perdia el dato; la agente volvia a preguntar si hubo heridos."""
    entendedor = _Entendedor(
        understanding.UnderstandingResponse(
            wants=understanding.Want.POLICY_QUESTION,
            items=(understanding.UnderstoodItem(field_key="injuries", value="no"),),
            asks_about_coverage=True,
            person_question="¿Mi póliza cubre esto?",
        )
    )

    case_id, eventos = await _turno_con_entendedor(
        dos_aseguradoras,
        cifrador,
        entendedor,
        "Nadie se lastimó. ¿Mi póliza cubre esto y cuánto me van a pagar?",
        extractor=_ScriptedExtractor(raise_error=True),
    )

    vista = await casos_api.get_case(dos_aseguradoras[1], case_id)
    assert vista is not None
    assert vista.completeness.per_field["injuries"]
    assert any(isinstance(e, FinalText) for e in eventos)


async def test_en_la_voz_una_respuesta_larga_pasa_por_quien_entiende(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Fase 3 (2026-10-09): lo que en la voz ya iba a un modelo lo entiende Claude."""
    entendedor = _Entendedor(
        understanding.UnderstandingResponse(
            wants=understanding.Want.CONTINUE,
            items=(understanding.UnderstoodItem(field_key="injuries", value="no"),),
        )
    )

    case_id, _ = await _turno_con_entendedor(
        dos_aseguradoras,
        cifrador,
        entendedor,
        "tranquila, por suerte ninguno de los que ibamos en el carro salio lastimado",
        extractor=_ScriptedExtractor(raise_error=True),
        channel="voice",
    )

    assert len(entendedor.peticiones) == 1
    vista = await casos_api.get_case(dos_aseguradoras[1], case_id)
    assert vista is not None
    assert vista.completeness.per_field["injuries"]


async def test_en_la_voz_una_respuesta_corta_no_espera_al_modelo(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Lo corto lo resuelven reglas al instante: la voz no espera a nadie de mas."""
    entendedor = _Entendedor(understanding.UnderstandingResponse(wants=understanding.Want.CONTINUE))

    await _turno_con_entendedor(dos_aseguradoras, cifrador, entendedor, "no", channel="voice")

    assert entendedor.peticiones == []


async def test_pedir_un_asesor_dicho_de_otra_forma_deriva_al_ajustador(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """La senal por reglas no reconoce «de carne y hueso»; lo entendido si."""
    entendedor = _Entendedor(
        understanding.UnderstandingResponse(wants=understanding.Want.TALK_TO_PERSON)
    )

    _, eventos = await _turno_con_entendedor(
        dos_aseguradoras, cifrador, entendedor, "prefiero un asesor de carne y hueso"
    )

    assert [type(e).__name__ for e in eventos][-1] == "Handoff"


async def test_en_la_voz_un_no_corto_no_pasa_por_la_comprension(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Hasta dos palabras la llamada sigue por reglas, al instante (2026-10-09: antes
    toda la voz iba por reglas y se comportaba distinto del chat)."""
    entendedor = _Entendedor(
        understanding.UnderstandingResponse(wants=understanding.Want.TALK_TO_PERSON)
    )

    _, eventos = await _turno_con_entendedor(
        dos_aseguradoras, cifrador, entendedor, "no, nadie", channel="voice"
    )

    assert entendedor.peticiones == []
    assert not any(type(e).__name__ == "Handoff" for e in eventos)


async def test_la_pregunta_del_chat_lleva_sus_botones_y_la_de_voz_no(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Tras la pregunta de seguridad viene la de identidad, que pide nombre y poliza: su
    boton contesta las dos con el titular de la poliza de ejemplo (2026-10-08)."""
    entendido = understanding.UnderstandingResponse(
        wants=understanding.Want.CONTINUE,
        items=(understanding.UnderstoodItem(field_key="injuries", value="no"),),
    )
    _, propia = dos_aseguradoras
    ejemplo = tenancy.require(propia).example_policy

    async def corpus(_tenant: str, numero: str) -> PolicyMatch | None:
        return PolicyMatch(policy_number=numero, holder_name="Natalia Henao Rendón", vehicle=None)

    caso = await nuevo_caso(propia)
    tareas: list[asyncio.Task[object]] = []
    base = _build_runtime(
        cipher=cifrador,
        extractor=_ScriptedExtractor(),
        coverage_node=_FakeCoverageNode(),
        tareas=tareas,
    )
    install_runtime(replace(base, understander=_Entendedor(entendido), policy_lookup=corpus))
    chat = await _turno(caso.case_id, propia, "nadie se lastimó")
    await _drenar(tareas)
    _, sin_corpus = await _turno_con_entendedor(
        dos_aseguradoras, cifrador, _Entendedor(entendido), "nadie se lastimó"
    )
    _, voz = await _turno_con_entendedor(
        dos_aseguradoras, cifrador, _Entendedor(entendido), "nadie se lastimó", channel="voice"
    )

    [final_chat] = [e for e in chat if isinstance(e, FinalText)]
    [final_sin_corpus] = [e for e in sin_corpus if isinstance(e, FinalText)]
    [final_voz] = [e for e in voz if isinstance(e, FinalText)]
    assert final_chat.suggestions == (f"Soy Natalia Henao Rendón, mi póliza es {ejemplo}",)
    assert final_sin_corpus.suggestions == (f"Mi póliza es {ejemplo}",)
    assert final_voz.suggestions == ()


async def test_una_consulta_con_poliza_responde_la_pregunta_y_sin_pregunta_la_pide(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Fase 1 (2026-10-08): la consulta no se cierra con un resumen vacio; con la poliza
    identificada, cada pregunta se responde sola y ofrece seguir."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(
        propia, policy_ref="POL-000001", record_type=RecordType.COVERAGE_INQUIRY
    )
    tareas: list[asyncio.Task[object]] = []
    avisos = _Avisos()
    coverage_node = _FakeCoverageNode()
    base = _build_runtime(
        cipher=cifrador,
        extractor=_ScriptedExtractor(),
        coverage_node=coverage_node,
        tareas=tareas,
    )
    install_runtime(replace(base, notifier=avisos))

    sin_pregunta = await _turno(caso.case_id, propia, "Tengo otra pregunta")
    con_pregunta = await _turno(caso.case_id, propia, "¿Mi póliza cubre el granizo?")
    await _drenar(tareas)

    [pide] = sin_pregunta
    assert isinstance(pide, FinalText)
    assert pide.text == copy_api.t(CopyKey("policy_rag.coverage.ask_question"), locale="es")
    [revisa] = con_pregunta
    assert isinstance(revisa, FinalText)
    assert revisa.text == copy_api.t(CopyKey("policy_rag.coverage.checking"), locale="es")
    [(_, respuesta, _, botones)] = avisos.entregados
    assert "RC-04" in respuesta
    assert botones == (
        copy_api.t(CopyKey("chat.chip.adjuster_review"), locale="es"),
        copy_api.t(CopyKey("chat.chip.another_question"), locale="es"),
    )
    assert coverage_node.entradas[-1].question == "¿Mi póliza cubre el granizo?"


# --- 2026-10-12: el modelo contesta, y el codigo esta de guardia ----------------------
#
# Una sola llamada entiende y contesta (`UnderstandingResponse.reply`). Que texto sale de
# verdad lo decide `turn._texto_del_turno`, rama por rama; la guardia de salida corre despues.
# Sin modelo: el entendedor es un doble que devuelve el formulario.


def _contesta(
    reply: str | None,
    *,
    items: tuple[tuple[str, str], ...] = (("injuries", "no"),),
    **mas: Any,
) -> _Entendedor:
    return _Entendedor(
        understanding.UnderstandingResponse(
            wants=understanding.Want.CONTINUE,
            items=tuple(
                understanding.UnderstoodItem(field_key=k, value=v)  # type: ignore[arg-type]
                for k, v in items
            ),
            reply=reply,
            **mas,
        )
    )


@pytest.fixture
def rastro() -> Iterator[io.StringIO]:
    destino = io.StringIO()
    observability.set_stream(destino)
    yield destino
    observability.set_stream(sys.stdout)


def _lo_que_se_dijo(rastro: io.StringIO) -> list[tuple[str, str | None]]:
    """Los eventos de que texto salio: `("chat.reply_model", None)` o `("chat.reply_fallback",
    motivo)`. Uno por turno, y ninguno lleva texto."""
    salida: list[tuple[str, str | None]] = []
    for linea in rastro.getvalue().splitlines():
        if not linea.startswith("{"):
            continue
        evento = json.loads(linea)
        if evento.get("event") not in ("chat.reply_model", "chat.reply_fallback"):
            continue
        assert "text" not in evento and "reply" not in evento
        salida.append((evento["event"], evento.get("reason")))
    return salida


_RESPUESTA = "Qué alivio que estén todos bien. ¿Me cuentas qué pasó?"


async def test_cuando_todo_cuadra_sale_lo_que_el_modelo_escribio(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher, rastro: io.StringIO
) -> None:
    _, eventos = await _turno_con_entendedor(
        dos_aseguradoras, cifrador, _contesta(_RESPUESTA), "no, todos bien, nadie se lastimó"
    )

    [final] = [e for e in eventos if isinstance(e, FinalText)]
    assert final.text == _RESPUESTA
    assert final.from_catalog is False, "el texto del modelo se trata como texto de fuera"
    assert _lo_que_se_dijo(rastro) == [("chat.reply_model", None)]


async def test_un_hito_lo_dice_siempre_el_codigo_con_su_frase_fija(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher, rastro: io.StringIO
) -> None:
    """El ultimo obligatorio cierra el reporte: la frase nombra el caso y ofrece lo opcional, y
    eso lo dice el codigo aunque el modelo haya escrito otra cosa."""
    _, propia = dos_aseguradoras
    case_id, eventos = await _turno_con_entendedor(
        dos_aseguradoras,
        cifrador,
        _contesta("Perfecto, ya quedó todo. Un ajustador te escribirá pronto."),
        "no, nadie se lastimó",
        sembrar={
            "identity_and_policy": "Laura Gomez, POL-480915",
            "description": "me chocaron por detras",
            "incident_datetime": "ayer a las cinco",
            "location": "avenida Boyaca con calle 80",
        },
    )

    [final] = [e for e in eventos if isinstance(e, FinalText)]
    vista = await casos_api.get_case(propia, case_id)
    assert vista is not None
    assert str(vista.case_number) in final.text
    assert "escribirá" not in final.text
    assert final.from_catalog is True
    assert _lo_que_se_dijo(rastro) == [("chat.reply_fallback", "milestone")]


async def test_una_emergencia_la_dice_el_codigo_y_no_el_modelo(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher, rastro: io.StringIO
) -> None:
    _, eventos = await _turno_con_entendedor(
        dos_aseguradoras,
        cifrador,
        _contesta("Tranquila, respira.", items=()),
        "necesito una ambulancia, alguien está sangrando",
    )

    [final] = [e for e in eventos if isinstance(e, FinalText)]
    assert "Tranquila, respira." not in final.text
    assert final.from_catalog is True
    assert _lo_que_se_dijo(rastro) == [("chat.reply_fallback", "milestone")]


@pytest.mark.parametrize(
    ("texto", "items"),
    [
        # Un campo que el tipo de caso no declara: el codigo lo descarta.
        ("tranquila, ninguno salió lastimado", (("injuries", "no"), ("driver_name", "Laura"))),
        # Heridos que la persona no menciono: el codigo descarta el dato de seguridad.
        ("fue ayer a las cinco", (("injuries", "no"), ("incident_datetime", "ayer a las cinco"))),
    ],
    ids=["campo-de-otro-tipo", "heridos-sin-evidencia"],
)
async def test_si_el_codigo_rechazo_un_dato_que_el_modelo_anoto_sale_la_frase_del_catalogo(
    dos_aseguradoras: tuple[str, str],
    cifrador: crypto.Cipher,
    rastro: io.StringIO,
    texto: str,
    items: tuple[tuple[str, str], ...],
) -> None:
    """La respuesta del modelo se escribio contando con ese dato; si no entro al caso, la
    persona leeria «ya lo anote» de algo que sigue faltando."""
    _, eventos = await _turno_con_entendedor(
        dos_aseguradoras, cifrador, _contesta("Listo, ya lo anoté todo.", items=items), texto
    )

    [final] = [e for e in eventos if isinstance(e, FinalText)]
    assert "ya lo anoté" not in final.text
    assert final.from_catalog is True
    assert _lo_que_se_dijo(rastro) == [("chat.reply_fallback", "items_rejected")]


@pytest.mark.parametrize(
    "reply",
    [
        None,
        "",
        "   ",
        "a" * 601,
        "Mira https://untangle.example/caso para verlo.",
        "Escríbenos a ayuda@aseguradora.com cuando quieras.",
    ],
    ids=["nula", "vacia", "espacios", "larga", "enlace", "correo"],
)
async def test_una_respuesta_que_no_vale_deja_la_frase_del_catalogo(
    dos_aseguradoras: tuple[str, str],
    cifrador: crypto.Cipher,
    rastro: io.StringIO,
    reply: str | None,
) -> None:
    _, eventos = await _turno_con_entendedor(
        dos_aseguradoras, cifrador, _contesta(reply), "no, todos bien, nadie se lastimó"
    )

    [final] = [e for e in eventos if isinstance(e, FinalText)]
    assert final.text and final.text != reply
    assert final.from_catalog is True
    assert _lo_que_se_dijo(rastro) == [("chat.reply_fallback", "invalid_reply")]


async def test_si_el_modelo_se_presenta_con_el_nombre_de_la_agente_sale_la_frase_del_catalogo(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher, rastro: io.StringIO
) -> None:
    """2026-10-11: «Hello, I'm Valeria...» en mitad de la conversacion. Las frases del
    catalogo que no traen el nombre tampoco lo dicen."""
    _, propia = dos_aseguradoras
    nombre = agent_name_of(propia, "es")

    _, eventos = await _turno_con_entendedor(
        dos_aseguradoras, cifrador, _contesta(f"Hola, soy {nombre}. ¿Qué pasó?"), "no, nadie"
    )

    [final] = [e for e in eventos if isinstance(e, FinalText)]
    assert nombre not in final.text
    assert _lo_que_se_dijo(rastro) == [("chat.reply_fallback", "invalid_reply")]


async def test_si_la_guardia_rechaza_la_respuesta_del_modelo_sale_la_frase_del_turno(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher, rastro: io.StringIO
) -> None:
    """Visto el 2026-10-08: la guardia reemplazaba la respuesta por su frase de seguridad y la
    pregunta del turno se perdia. Ahora sale la frase base, con su pregunta."""
    _, eventos = await _turno_con_entendedor(
        dos_aseguradoras,
        cifrador,
        _contesta("El otro conductor tiene toda la culpa. ¿Qué más pasó?"),
        "no, todos bien, soy Marcela Rios",
    )

    [final] = [e for e in eventos if isinstance(e, FinalText)]
    assert "culpa" not in final.text
    assert "?" in final.text
    assert final.from_catalog is True
    assert _lo_que_se_dijo(rastro) == [("chat.reply_fallback", "guard")]


async def test_sin_modelo_sale_la_frase_del_catalogo_como_siempre(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher, rastro: io.StringIO
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    tareas: list[asyncio.Task[object]] = []
    install_runtime(
        _build_runtime(
            cipher=cifrador,
            extractor=_ScriptedExtractor(
                next_items=(ExtractedItem(field_key="injuries", value="nadie se lastimó"),)
            ),
            coverage_node=_FakeCoverageNode(),
            tareas=tareas,
        )
    )

    eventos = await _turno(caso.case_id, propia, "no, todos bien, nadie se lastimó")
    await _drenar(tareas)

    [final] = [e for e in eventos if isinstance(e, FinalText)]
    assert final.from_catalog is True
    vista = await casos_api.get_case(propia, caso.case_id)
    assert vista is not None
    assert vista.completeness.per_field["injuries"], "por reglas y extraccion, como antes"
    assert _lo_que_se_dijo(rastro) == [("chat.reply_fallback", "no_model")]


async def test_si_el_modelo_falla_el_turno_sigue_por_reglas(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher, rastro: io.StringIO
) -> None:
    class _Caido:
        async def __call__(self, _p: understanding.UnderstandingRequest) -> object:
            raise ProviderError(
                ProviderErrorKind.TIMEOUT, provider=ProviderName.ANTHROPIC, use=Use.CHAT_REPLY
            )

    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    tareas: list[asyncio.Task[object]] = []
    base = _build_runtime(
        cipher=cifrador,
        extractor=_ScriptedExtractor(
            next_items=(ExtractedItem(field_key="injuries", value="nadie se lastimó"),)
        ),
        coverage_node=_FakeCoverageNode(),
        tareas=tareas,
    )
    install_runtime(replace(base, understander=_Caido()))  # type: ignore[arg-type]

    eventos = await _turno(caso.case_id, propia, "no, todos bien, nadie se lastimó")
    await _drenar(tareas)

    [final] = [e for e in eventos if isinstance(e, FinalText)]
    assert final.from_catalog is True
    assert _lo_que_se_dijo(rastro) == [("chat.reply_fallback", "no_model")]


async def test_el_primer_mensaje_que_abrio_el_caso_dice_la_frase_del_catalogo(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher, rastro: io.StringIO
) -> None:
    """Se entendio sin caso: la respuesta del modelo se escribio sin saber que datos faltan
    (con la lista vacia, la instruccion le dice que solo agradezca)."""
    entendedor = _contesta("Gracias por contármelo.", items=())

    _, eventos = await _turno_con_entendedor(
        dos_aseguradoras,
        cifrador,
        entendedor,
        "Tuve un choque ayer",
        understood=entendedor.respuesta,
        understood_by_channel=True,
        understood_without_case=True,
    )

    [final] = [e for e in eventos if isinstance(e, FinalText)]
    assert "Gracias por contármelo." not in final.text
    assert "?" in final.text, "la pregunta que toca la hace el codigo"
    assert entendedor.peticiones == [], "ya estaba entendido: no se vuelve a llamar"
    assert _lo_que_se_dijo(rastro) == [("chat.reply_fallback", "opening_turn")]


async def test_lo_que_el_canal_ya_entendio_no_se_vuelve_a_entender_y_su_respuesta_es_la_del_turno(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher, rastro: io.StringIO
) -> None:
    ya = _contesta(_RESPUESTA)
    otro = _contesta("Esto no debe decirse.")

    _, eventos = await _turno_con_entendedor(
        dos_aseguradoras,
        cifrador,
        otro,
        "no, todos bien, nadie se lastimó",
        understood=ya.respuesta,
        understood_by_channel=True,
    )

    [final] = [e for e in eventos if isinstance(e, FinalText)]
    assert final.text == _RESPUESTA
    assert otro.peticiones == []


async def test_si_el_canal_lo_intento_y_el_modelo_no_pudo_el_turno_no_lo_llama_otra_vez(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher, rastro: io.StringIO
) -> None:
    """Duplicaria la espera de la persona justo cuando el proveedor anda mal."""
    otro = _contesta("Esto no debe decirse.")

    _, eventos = await _turno_con_entendedor(
        dos_aseguradoras,
        cifrador,
        otro,
        "no, todos bien, nadie se lastimó",
        understood_by_channel=True,
    )

    assert otro.peticiones == []
    [final] = [e for e in eventos if isinstance(e, FinalText)]
    assert final.from_catalog is True
    assert _lo_que_se_dijo(rastro) == [("chat.reply_fallback", "no_model")]


async def test_el_modelo_recibe_la_conversacion_el_estado_y_lo_anotado_con_su_valor(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    entendedor = _contesta(_RESPUESTA)

    await _turno_con_entendedor(
        dos_aseguradoras,
        cifrador,
        entendedor,
        "no, nadie se lastimó",
        dicho_antes=("Hola, ¿en qué te ayudo?", "¿Hubo alguien herido?"),
        sembrar={"identity_and_policy": "Laura Gomez, POL-480915", "location": "la calle 80"},
    )

    [peticion] = entendedor.peticiones
    assert [(linea.speaker, linea.text) for linea in peticion.history] == [
        ("agent", "Hola, ¿en qué te ayudo?"),
        ("agent", "¿Hubo alguien herido?"),
    ], "el mensaje de ahora va aparte, no en la conversacion"
    assert peticion.person_text == "no, nadie se lastimó"
    assert {dato.field_key: dato.value for dato in peticion.noted} == {
        "identity_and_policy": None,
        "location": "la calle 80",
    }
    assert peticion.missing[0] == "injuries"
    assert peticion.channel == "chat"
    assert peticion.case_status is understanding.CaseStatus.RECEIVING
    assert peticion.policy_identified is False
    assert peticion.answer_pending is False


# --- La llamada: lo que se dice es siempre lo que el redactor ya no cambia --------------


async def test_en_la_voz_sale_la_respuesta_del_modelo_si_el_redactor_no_la_cambia(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher, rastro: io.StringIO
) -> None:
    entendedor = _contesta("Qué bueno que todos están bien. ¿Dónde fue?")

    _, eventos = await _turno_con_entendedor(
        dos_aseguradoras,
        cifrador,
        entendedor,
        "no, por suerte todos estamos bien",
        channel="voice",
    )

    [final] = [e for e in eventos if isinstance(e, FinalText)]
    assert final.text == "Qué bueno que todos están bien. ¿Dónde fue?"
    assert entendedor.peticiones[0].channel == "voice"
    assert _lo_que_se_dijo(rastro) == [("chat.reply_model", None)]


@pytest.mark.parametrize(
    "reply",
    [
        "Gracias, Marcela Ríos. ¿Dónde fue?",
        "Tengo anotada la póliza POL-000001. ¿Dónde fue?",
    ],
    ids=["un-nombre", "una-poliza"],
)
async def test_en_la_voz_si_el_redactor_tapa_algo_sale_la_frase_del_catalogo(
    dos_aseguradoras: tuple[str, str],
    cifrador: crypto.Cipher,
    rastro: io.StringIO,
    reply: str,
) -> None:
    """La agente nunca dice una etiqueta en voz alta, ni por un dato de verdad ni por una
    palabra corriente que el detector confunda con uno."""
    assert str(redaccion.redact(reply, language="es")) != reply, "el redactor la cambia"

    _, eventos = await _turno_con_entendedor(
        dos_aseguradoras,
        cifrador,
        _contesta(reply),
        "no, por suerte todos estamos bien",
        channel="voice",
    )

    [final] = [e for e in eventos if isinstance(e, FinalText)]
    assert final.text != reply
    assert "[" not in final.text
    assert final.from_catalog is True
    assert _lo_que_se_dijo(rastro) == [("chat.reply_fallback", "redacted_voice")]


@pytest.mark.parametrize("canal", ["chat", "voice"])
async def test_si_el_modelo_da_el_reporte_por_hecho_con_datos_por_pedir_sale_lo_que_falta(
    dos_aseguradoras: tuple[str, str],
    cifrador: crypto.Cipher,
    rastro: io.StringIO,
    canal: str,
) -> None:
    """2026-10-13, una llamada simulada: el caso seguia tomando datos, la persona dijo «eso es
    todo» y el modelo contesto que ya quedaba anotado y que lo revisaba un ajustador. En su
    lugar sale la verdad en una frase del catalogo --que falta, que queda guardado, una pregunta--
    y el motivo queda en la traza."""
    promesa = "De nada. Ya quedó anotado tu reporte; un ajustador lo revisará con tu póliza."

    caso, eventos = await _turno_con_entendedor(
        dos_aseguradoras,
        cifrador,
        _contesta(promesa, items=()),
        "No, así está bien, eso es todo, gracias.",
        channel=canal,
    )

    [final] = [e for e in eventos if isinstance(e, FinalText)]
    # El caso no avanzo: sigue en captura, y el bloque que toca es el que se nombra.
    faltante = composition.block_label(Block.SAFETY, language="es")
    assert final.text == composition.compose_unfinished(Block.SAFETY, language="es")[1]
    assert faltante in final.text
    assert "ajustador" not in final.text and "anotado" not in final.text
    assert final.from_catalog is True
    assert _lo_que_se_dijo(rastro) == [("chat.reply_fallback", "report_not_done")]
    vista = await casos_api.get_case(dos_aseguradoras[1], caso)
    assert vista is not None
    assert vista.state is CaseState.CAPTURING, "la respuesta no movio el caso"


async def test_si_el_modelo_ofrece_el_ajustador_o_dice_que_falta_algo_sale_su_respuesta(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher, rastro: io.StringIO
) -> None:
    """Ofrecer pasar el caso es una frase legitima del producto; el rechazo es de afirmarlo."""
    reply = "Aún me falta saber si hubo heridos. Si prefieres, paso tu caso a un ajustador."

    _, eventos = await _turno_con_entendedor(
        dos_aseguradoras,
        cifrador,
        _contesta(reply, items=()),
        "No, así está bien, eso es todo, gracias.",
    )

    [final] = [e for e in eventos if isinstance(e, FinalText)]
    assert final.text == reply
    assert _lo_que_se_dijo(rastro) == [("chat.reply_model", None)]


async def test_la_regla_del_redactor_es_de_la_llamada_y_no_del_chat(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher, rastro: io.StringIO
) -> None:
    """En el chat el texto sale por la guardia, que tiene sus propias reglas."""
    reply = "Gracias por contarme. ¿Dónde fue?"
    assert str(redaccion.redact(reply, language="es")) == reply

    _, eventos = await _turno_con_entendedor(
        dos_aseguradoras, cifrador, _contesta(reply), "no, por suerte todos estamos bien"
    )

    [final] = [e for e in eventos if isinstance(e, FinalText)]
    assert final.text == reply
    assert _lo_que_se_dijo(rastro) == [("chat.reply_model", None)]


async def test_en_la_voz_el_acuse_de_la_comprension_ya_no_se_antepone(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Desde el 2026-10-12 el acuse es parte de lo que el modelo contesta (`reply`), no una
    frase aparte que el codigo pega delante de la del catalogo."""
    entendedor = _contesta(None, acknowledgement="Qué bueno que todos están bien.")

    _, eventos = await _turno_con_entendedor(
        dos_aseguradoras,
        cifrador,
        entendedor,
        "no, por suerte todos estamos bien",
        channel="voice",
        extractor=_ScriptedExtractor(raise_error=True),
    )

    [final] = [e for e in eventos if isinstance(e, FinalText)]
    assert "Qué bueno que todos están bien." not in final.text
    assert final.from_catalog is True


# --- 2026-10-12: «te respondo en un momento» solo si hay algo que revisar -----------
#
# El dueño entro por «Preguntar por mi poliza», dio su nombre y su poliza y la agente
# dijo dos cosas --«¿Que quieres saber?» y «Deja revisar tu poliza; te respondo en un
# momento»-- y despues nada: no habia pregunta, la revision no arranco, y la primera
# frase se publico por el aviso de fondo sin guardarse.


async def _corpus_de_daniel(_tenant: str, numero: str) -> PolicyMatch | None:
    if numero != "POL-200341":
        return None
    return PolicyMatch(policy_number=numero, holder_name="Daniel Foster", vehicle=None)


def _se_identifica(poliza: str, **mas: object) -> understanding.UnderstandingResponse:
    return understanding.UnderstandingResponse(
        wants=understanding.Want.POLICY_QUESTION,
        items=(
            understanding.UnderstoodItem(
                field_key="identity_and_policy", value=f"Daniel Foster, {poliza}"
            ),
        ),
        **mas,  # type: ignore[arg-type]
    )


@dataclass
class _Consulta:
    """Una consulta de cobertura lista para conversar: runtime, avisos y fondo."""

    tenant_id: str
    case_id: str
    avisos: _Avisos
    coverage_node: _FakeCoverageNode
    tareas: list[asyncio.Task[object]]
    base: GraphRuntime

    def con_lo_que_entiende(self, entendido: understanding.UnderstandingResponse) -> None:
        install_runtime(replace(self.base, understander=_Entendedor(entendido)))


async def _consulta_abierta(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> _Consulta:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia, record_type=RecordType.COVERAGE_INQUIRY)
    tareas: list[asyncio.Task[object]] = []
    avisos = _Avisos()
    coverage_node = _FakeCoverageNode()
    base = replace(
        _build_runtime(
            cipher=cifrador,
            extractor=_ScriptedExtractor(),
            coverage_node=coverage_node,
            tareas=tareas,
            lookup=_corpus_de_daniel,
        ),
        notifier=avisos,
        policy_lookup=_corpus_de_daniel,
    )
    return _Consulta(propia, caso.case_id, avisos, coverage_node, tareas, base)


async def _textos_de_la_agente(tenant_id: str, case_id: str) -> list[str]:
    return [
        str(turno.text_redacted)
        for turno in await casos_api.transcript_of(tenant_id, case_id)
        if turno.speaker is Speaker.AGENT
    ]


async def _lo_publicado_esta_guardado(consulta: _Consulta) -> None:
    """La regla: todo texto que el fondo publica queda en la transcripcion del caso."""
    guardados = await _textos_de_la_agente(consulta.tenant_id, consulta.case_id)
    for publicado in consulta.avisos.para(consulta.case_id):
        assert str(redaccion.redact_composed(publicado, language="es")) in guardados, publicado


async def test_la_consulta_que_entro_sin_pregunta_la_pide_y_no_promete_nada(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    consulta = await _consulta_abierta(dos_aseguradoras, cifrador)
    consulta.con_lo_que_entiende(_se_identifica("POL-200341"))

    eventos = await _turno(
        consulta.case_id, consulta.tenant_id, "Soy Daniel Foster, mi póliza es POL-200341"
    )
    await _drenar(consulta.tareas)

    # Un solo texto, el que pregunta; la espera no se dice porque no hay nada que esperar.
    [pide] = eventos
    assert isinstance(pide, FinalText)
    assert pide.text == copy_api.t(CopyKey("policy_rag.coverage.ask_question"), locale="es")
    assert pide.answer_pending is False
    assert pide.suggestions == sugerencias.sample_questions(language="es")
    # Ni se lanzo una revision, ni se publico nada por el aviso de fondo.
    assert consulta.coverage_node.entradas == []
    assert consulta.avisos.entregados == []
    vista = await casos_api.get_case(consulta.tenant_id, consulta.case_id)
    assert vista is not None
    assert vista.policy_ref == "POL-200341"


async def test_la_consulta_con_la_pregunta_hecha_lanza_la_revision_y_la_respuesta_queda_guardada(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """El control positivo del anterior: con pregunta, la espera es verdad."""
    consulta = await _consulta_abierta(dos_aseguradoras, cifrador)
    consulta.con_lo_que_entiende(
        understanding.UnderstandingResponse(
            wants=understanding.Want.POLICY_QUESTION,
            asks_about_coverage=True,
            person_question="¿Me cubre el granizo?",
        )
    )
    await _turno(consulta.case_id, consulta.tenant_id, "¿Me cubre el granizo?")
    consulta.con_lo_que_entiende(_se_identifica("POL-200341"))

    eventos = await _turno(
        consulta.case_id, consulta.tenant_id, "Soy Daniel Foster, mi póliza es POL-200341"
    )
    await _drenar(consulta.tareas)

    [espera] = eventos
    assert isinstance(espera, FinalText)
    assert espera.text == copy_api.t(CopyKey("policy_rag.coverage.checking"), locale="es")
    assert espera.answer_pending is True
    assert consulta.coverage_node.entradas[-1].question == "¿Me cubre el granizo?"
    [(_, respuesta, _, _)] = consulta.avisos.entregados
    assert "RC-04" in respuesta
    await _lo_publicado_esta_guardado(consulta)


async def test_si_la_revision_no_se_puede_lanzar_no_se_dice_que_llegara_una_respuesta(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """La pregunta esta y la poliza esta atada, pero este despliegue no tiene el fondo:
    la frase de espera prometeria una respuesta que nadie va a traer."""
    consulta = await _consulta_abierta(dos_aseguradoras, cifrador)
    sin_fondo = replace(consulta.base, coverage=None, build_coverage_input=None)
    install_runtime(
        replace(
            sin_fondo,
            understander=_Entendedor(
                _se_identifica(
                    "POL-200341", asks_about_coverage=True, person_question="¿Me cubre el granizo?"
                )
            ),
        )
    )

    eventos = await _turno(
        consulta.case_id,
        consulta.tenant_id,
        "Soy Daniel Foster, mi póliza es POL-200341. ¿Me cubre el granizo?",
    )

    [evento] = eventos
    assert isinstance(evento, TurnError)
    assert evento.code == "background_rhythm_unavailable"
    assert evento.text != copy_api.t(CopyKey("policy_rag.coverage.checking"), locale="es")


async def test_si_la_poliza_no_esta_en_el_corpus_se_dice_que_hace_falta_y_no_se_promete_revisar(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    consulta = await _consulta_abierta(dos_aseguradoras, cifrador)
    consulta.con_lo_que_entiende(
        _se_identifica(
            "POL-999999", asks_about_coverage=True, person_question="¿Me cubre el granizo?"
        )
    )

    eventos = await _turno(
        consulta.case_id,
        consulta.tenant_id,
        "Soy Daniel Foster, mi póliza es POL-999999. ¿Me cubre el granizo?",
    )
    await _drenar(consulta.tareas)

    [evento] = eventos
    assert isinstance(evento, FinalText)
    assert evento.text == copy_api.t(CopyKey("policy_rag.coverage.need_policy"), locale="es")
    assert evento.answer_pending is False
    assert consulta.coverage_node.entradas == []


async def test_pedir_un_ajustador_en_una_consulta_deriva_con_su_frase_y_su_texto_viaja(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """2026-10-12: el caso se derivaba bien y la pantalla decia «tuve un problema»: la clave
    de la derivacion de una consulta era nueva para ella. Del lado del servidor, la
    derivacion lleva su clave y su texto en el idioma del turno, y el cable manda las dos."""
    from untangle.chat import stream

    consulta = await _consulta_abierta(dos_aseguradoras, cifrador)
    consulta.con_lo_que_entiende(_se_identifica("POL-200341"))
    await _turno(consulta.case_id, consulta.tenant_id, "Soy Daniel Foster, mi póliza es POL-200341")
    consulta.con_lo_que_entiende(
        understanding.UnderstandingResponse(wants=understanding.Want.TALK_TO_PERSON)
    )

    eventos = await _turno(consulta.case_id, consulta.tenant_id, "Que lo revise un ajustador")

    [derivacion] = eventos
    assert isinstance(derivacion, Handoff)
    assert derivacion.copy_key == "compliance.handoff.adjuster_review_inquiry"
    esperado = copy_api.t(CopyKey("compliance.handoff.adjuster_review_inquiry"), locale="es")
    assert derivacion.text == esperado
    cable = stream.to_wire(derivacion)
    assert (cable["copy_key"], cable["text"]) == (derivacion.copy_key, esperado)


async def test_al_tercer_insulto_el_caso_queda_de_verdad_con_un_ajustador(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """C4, visto el 2026-10-07: la frase de cierre prometia un ajustador y el caso no se
    derivaba. Ahora el turno termina en `Handoff`, con la frase literal del catalogo."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    tareas: list[asyncio.Task[object]] = []
    install_runtime(
        _build_runtime(
            cipher=cifrador,
            extractor=_ScriptedExtractor(),
            coverage_node=_FakeCoverageNode(),
            tareas=tareas,
        )
    )

    for insulto in ("son unos inutiles", "son unos incompetentes"):
        await _turno(caso.case_id, propia, insulto)
    eventos = await _turno(caso.case_id, propia, "son unos idiotas")
    await _drenar(tareas)

    [ultimo] = eventos[-1:]
    assert isinstance(ultimo, Handoff)
    assert ultimo.reason_code is HandoffReason.RULE
    # Con un motivo fuera de esta tabla el canal no deriva el caso.
    assert ultimo.reason_code in case_context.MOTIVO_DEL_CASO
    assert ultimo.copy_key == "intake.tone.closing_abuse"
