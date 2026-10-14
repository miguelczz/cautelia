"""C-14: el punto único de entrada y salida de un turno (paso 7, el último de U12).

`handle_turn`, `resume_case` y `preload` tienen la forma exacta del contrato:
un turno entra, un flujo de eventos tipados sale, y ese flujo **siempre**
termina en `FinalText`, `Handoff` o `TurnError` -- nunca en silencio (C-14,
"el turno nunca queda abierto en silencio").

## Cómo se compone este módulo con los seis anteriores

- `orchestration.rhythm.run_turn_controls` sigue siendo quien corre los tres
  controles baratos del turno (BR2.3); este módulo los llama una vez, al
  principio, sobre el texto **entrante**.
- `orchestration.output.ExitGate` es el punto único de salida (BR2.5): todo
  `text` de todo evento de este módulo sale de una llamada a `gate.send(...)`,
  sin excepción, incluidos los caminos de degradación y de error.
- `orchestration.graph_runtime` compila el grafo real (`intake` como su propio
  grafo de un nodo; `policy_verification → decision → compliance` como el de
  fondo) sobre el mismo `TenantCheckpointSaver` (paso 2): los puntos de
  control de los dos ritmos son puntos del mismo hilo (BR3.1).
- `orchestration.case_context` es la mitad de C-12 que ningún paso anterior
  construía: leer el caso real antes de correr `intake` y aplicarle de vuelta
  lo que `intake` extrajo, para que la completitud persista entre turnos
  (BR3.2) sin que este módulo tenga que llevar su propia copia.
- `orchestration.coverage_detour` es el reconocedor propio de esta unidad
  (FD-U12-6, BR4.2, BR4.3): el desvío no es un nodo ni una rama del grafo, es
  este módulo leyendo lo que el ritmo de fondo ya dejó en el estado.

## La compuerta dura BR3.4, su mitad de texto

`resume_case`/`handle_turn` nunca leen ni escriben nada indexado por póliza:
`orchestration.resume.resume_state` (paso 6) ya cerró la mitad "en estado" --
un `case_id` sin historia propia da el mismo `ResumeState` que uno sin
relación, aunque comparta póliza con otro--, y esta mitad, "en texto", es
literal: cuando `resume_state` no tiene nada que ofrecer, el turno de este
caso compone su respuesta **exactamente** como lo haría un caso sin ningún
antecedente -- no hay ninguna rama en este módulo que lea `resume_state` y
elija un texto distinto según lo que encontró. El test que lo comprueba está
en `tests/integration/u12/test_turn.py` (paso 7).
"""

from __future__ import annotations

import asyncio
import contextvars
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import Checkpoint, CheckpointMetadata
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from untangle import language as idioma_del_texto
from untangle import observability
from untangle.base import Locale, Use
from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record.models import CaseState, RecordType, Speaker
from untangle.case_record.models import Channel as CaseChannel
from untangle.compliance.controls import api as controls
from untangle.compliance.controls.api import HandoffReason
from untangle.compliance.controls.phrases import EmergencyPhraseMode
from untangle.compliance.controls.signals import TurnSignals
from untangle.compliance.redaction import api as redaccion
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration import (
    case_context,
    closing_outcome,
    closing_plan,
    coverage_detour,
    outcome_claim,
    quote_reply,
    rhythm,
    stated_purpose,
    transcript_writer,
)
from untangle.orchestration.checkpoint import TenantCheckpointSaver
from untangle.orchestration.contracts import (
    VOICE_RULES_MAX_WORDS,
    CaseNotifier,
    EligibilityPort,
    FinalText,
    Handoff,
    InboundTurn,
    PartialText,
    TurnError,
    TurnEvent,
    Waiting,
)
from untangle.orchestration.executor import Node, NodeExecutor
from untangle.orchestration.model_reply import (
    FallbackReason,
    agent_name_of,
    record_outcome,
    usable_reply,
)
from untangle.orchestration.node_run import NodeRunOutcome
from untangle.orchestration.nodes.intake import blocks, understanding
from untangle.orchestration.nodes.intake import composition as intake_composition
from untangle.orchestration.nodes.intake import suggestions as sugerencias
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.orchestration.nodes.intake.extraction import DERIVED_FIELDS
from untangle.orchestration.nodes.intake.node import IntakeNodeInput, IntakeNodeOutput, SessionEnd
from untangle.orchestration.nodes.intake.policy import PolicyMatch, PolicyMatchPort
from untangle.orchestration.nodes.policy_verification import phrases as coverage_phrases
from untangle.orchestration.output import ExitGate, send_rewrite_or_base
from untangle.orchestration.pause import (
    HumanReviewRequestStore,
    PauseReason,
    open_pause,
)
from untangle.orchestration.state import GraphState
from untangle.orchestration.transition import transition
from untangle.providers.ports import ProviderError
from untangle.telemetry.traces import api as traces
from untangle.telemetry.traces.models import NodeName
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import TenantId

# --- C-14: el vocabulario, que vive en `contracts.py` --------------------------
#
# Los tipos del contrato bajaron a `orchestration/contracts.py` el 2026-09-28,
# cuando U13 fue el primer canal en consumirlos de verdad: tenerlos aqui obligaba
# a cada canal a importar este modulo, que importa LangGraph, y el contrato de
# importacion del proyecto lo caza por transitividad. Se reexportan para que nada
# de lo ya escrito tenga que cambiar de import.


class UnaddressedTurnError(ValueError):
    """`handle_turn` recibió un turno sin `case_id`.

    Crear un caso desde nada es una decisión del canal (cuándo, con qué tipo de
    registro, con qué origen) que ninguna `Fronteras` de `functional-spec.md`
    le pide a esta unidad: la fila de U4 en esa tabla es "crear el caso **y**
    aplicarle las transiciones", y esta unidad cubre la segunda mitad y la
    lectura -- `case_context.load_case_context` -- desde el primer turno que ya
    tiene un `case_id`. Cablear cuándo nace un caso es de U13/U16.
    """


# --- El runtime instalado: qué necesita `handle_turn` para ser real -----------


def _detached_task_factory(coro: Any) -> asyncio.Task[object]:
    """`asyncio.create_task`, pero en un `Context` propio (ver `GraphRuntime.task_factory`)."""
    return asyncio.create_task(coro, context=contextvars.Context())


class IntakeInputBuilder(Protocol):
    """Quien traduce el caso cargado mas el turno a la entrada de `intake` (C-15).

    Los dos ultimos entran **por nombre** y no por posicion: se anadieron el
    2026-09-29 con la lectura de confirmacion, y una lista de seis argumentos
    posicionales es la forma mas segura de que el septimo acabe en el sitio
    equivocado sin que nada avise.
    """

    def __call__(  # noqa: PLR0913 -- el caso, el turno, las senales y tres datos mas; ninguno derivable de otro
        self,
        context: case_context.CaseContext,
        turn: InboundTurn,
        signals: TurnSignals,
        emergency_instruction: str | None,
        /,
        *,
        awaiting_confirmation: Block | None,
        stated_values: dict[str, str] | None,
        awaiting_policy_confirmation: PolicyMatch | None = None,
    ) -> IntakeNodeInput: ...


#: Como se arma la entrada de un nodo de fondo: del **caso cargado** y del
#: estado. Las dos cosas y no solo el estado, por lo mismo que `intake` y la
#: cobertura: el idioma, el tipo de registro y la derivacion son del caso, y
#: `GraphState.node_writes` solo admite lo que un `NodeSpec` real declara (BR1.5).
#:
#: **Es `async`** porque la de `compliance` tiene que leer hasta donde revisar --el
#: ultimo turno de la transcripcion-- y eso es una consulta. Hacerla sincrona
#: obligaria a cargar la transcripcion en cada turno para algo que solo el fondo
#: necesita.
#:
#: Devuelve `None` cuando ese nodo **no tiene nada que hacer** con este caso: la
#: revision de un caso sin un solo turno no es una revision vacia, es una revision
#: que no se puede acotar. La cadena lo dice y se detiene, en vez de inventar un
#: limite.
type BackgroundInputBuilder = Callable[
    [case_context.CaseContext, GraphState], Awaitable[Any | None]
]


@dataclass(frozen=True)
class BackgroundStep:
    """Un nodo del ritmo de fondo y quien le arma la entrada.

    Los dos juntos y los dos obligatorios, igual que `coverage` y
    `build_coverage_input`: un nodo sin quien le arme la entrada no se puede
    ejecutar, y una fabrica sin nodo no tiene a quien darsela.
    """

    node: Node[Any, Any]
    build_input: BackgroundInputBuilder


@dataclass(frozen=True)
class GraphRuntime:
    """Lo que `handle_turn`, `resume_case` y `preload` necesitan para correr de verdad.

    `intake` es la clase real de U11; `build_intake_input` es la única pieza
    que traduce `CaseContext` (el caso, ya cargado) más el turno en su entrada
    tipada (C-15) -- la pieza que `executor.py` dejó escrita como pendiente.
    Corre por `executor` directo, no por un grafo compilado: su entrada
    depende del caso (`CaseContext`), no solo de `GraphState`, así que un
    `build_input` fijado al compilar un grafo -- como el que sí tiene sentido
    para el ritmo de fondo, ver `graph_runtime.compile_turn_graph` -- no podría
    variar por turno sin filtrar campos del caso al estado persistido
    (`GraphState.node_writes` solo admite lo que un `NodeSpec` real declara,
    BR1.5). El punto de control del turno de `intake` se escribe a mano, con
    la misma forma mínima de `Checkpoint` que ya prueba
    `test_checkpointer.py`.

    `background_graph` sí es el grafo real de `graph_runtime.py`, porque
    `interrupt()`/`Command(resume=...)` (BR4.1, BR4.4) son semántica de
    LangGraph que ningún código de mano reproduce con la misma garantía.

    **`background_graph` admite `None`, y no tiene valor por omisión.** Es la
    forma de decir, en el tipo, que un despliegue puede tener el ritmo del turno
    cableado y el de fondo todavía no: los tres nodos de fondo necesitan entradas
    que `GraphState` hoy no lleva -- la pregunta de cobertura y el número de
    póliza --, y compilar el grafo con enlaces que no pueden construir su entrada
    convertiría **toda** pregunta de cobertura en "no pude verificar" por un fallo
    de cableado. La convención 8 del equipo prohíbe exactamente eso: colapsar "no
    hay cláusula" con "no pude verificar" contamina una métrica publicada con
    fallos de infraestructura. Sin él, `preload` no lanza nada y lo dice --
    devuelve `False` y emite su evento --, y el desvío de cobertura responde con la
    frase de degradación del catálogo en vez de una de espera que no llega nunca.
    Que no tenga valor por omisión es a propósito: quien construya un runtime tiene
    que elegir, no olvidarse.
    """

    intake: Node[IntakeNodeInput, IntakeNodeOutput]
    build_intake_input: IntakeInputBuilder
    background_graph: CompiledStateGraph[GraphState, None, GraphState, GraphState] | None
    executor: NodeExecutor
    checkpointer: TenantCheckpointSaver
    pause_store: HumanReviewRequestStore
    cipher: crypto.Cipher
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    emergency_mode: EmergencyPhraseMode = EmergencyPhraseMode.PUBLIC
    #: Quien evalua y relee la elegibilidad de una solicitud (U19, BR2.5). Opcional
    #: como el resto del ritmo de fondo: un despliegue sin ella lo dice con su
    #: evento en vez de prometer una respuesta que nadie va a traer. Entra por
    #: puerto y no por importacion porque el motor de reglas no puede aparecer en
    #: la cadena de llamadas del turno: un contrato de capas lo prohibe, y la razon
    #: es que importarlo lo metria en el camino que BR2.5 quiere mantener fuera.
    eligibility: EligibilityPort | None = None
    #: BR2.2: lanza sin esperar. Por omisión, no el `asyncio.create_task` llano
    #: de `rhythm.py` -- ese copia el `contextvars.Context` de quien llama, y
    #: el turno que dispara `preload` todavía tiene su propio tramo de traza
    #: abierto (`traces.turn_span`, BR6.1: "un turno dentro de otro no es
    #: ninguno de los tres"). El trabajo de fondo abre su **propio** tramo de
    #: turno, así que necesita arrancar sin heredar el del que lo lanzó.
    task_factory: rhythm.TaskFactory[None] | None = None
    #: El nodo `policy_verification` de U8 y cómo construir su entrada desde el caso
    #: cargado más la pregunta. **Van juntos y admiten `None` los dos**: un nodo sin
    #: quién le arme la entrada no se puede ejecutar, y una fábrica de entrada sin
    #: nodo no tiene a quién dársela.
    #:
    #: Corre **por el ejecutor directo**, no dentro de `background_graph`, por la misma
    #: razón escrita para `intake`: su entrada depende del caso --el número de póliza y
    #: el idioma-- y no solo de `GraphState`, así que un `build_input` fijado al
    #: compilar el grafo no podría variar por caso sin filtrar campos del caso al
    #: estado persistido (BR1.5). Lo que `preload` deja en el punto de control es su
    #: conjunto de escritura, que es lo que el desvío de cobertura lee en el turno
    #: siguiente.
    coverage: Node[Any, Any] | None = None
    build_coverage_input: Callable[[case_context.CaseContext, str, str], Any] | None = None
    #: Los dos nodos que siguen a la cobertura en el ritmo de fondo: `decision` y
    #: `compliance`, cada uno con su fabrica de entrada.
    #:
    #: **Corren por el ejecutor directo y no dentro de `background_graph`**, y la
    #: razon es la misma que PENDIENTES 1.8 dejo escrita: el grafo compilado fija la
    #: fabrica de entrada de cada nodo **al compilar**, y la de la cobertura depende
    #: del caso. Encadenarlos a mano no duplica la secuencia: la decide
    #: `transition()`, que es pura, cerrada y ya existe, y es la misma que enruta el
    #: grafo compilado.
    #:
    #: Vacio es un despliegue sin el fondo encadenado: la cobertura corre igual y la
    #: cadena se detiene diciendolo. Un diccionario a medias --`decision` si y
    #: `compliance` no-- tambien se detiene donde falta, con el nombre del nodo que
    #: falta en su evento.
    background: Mapping[NodeName, BackgroundStep] = field(default_factory=dict)
    #: Quien entiende cada mensaje con el contexto del caso (fase 0, 2026-10-07) y, desde el
    #: 2026-10-12, tambien lo contesta (`UnderstandingResponse.reply`). Opcional: sin el, o si
    #: falla o tarda, el turno sigue por reglas y extraccion, y sale la frase del catalogo.
    understander: understanding.Understander | None = None
    #: Quien busca una poliza en el corpus de la aseguradora: el mismo puerto de la
    #: captura. Lo usa el boton de la poliza de ejemplo para nombrar a su titular.
    policy_lookup: PolicyMatchPort | None = None
    #: Quien le lleva al chat la respuesta de cobertura cuando el fondo termina (fase
    #: 1, 2026-10-08). Sin el, la respuesta queda guardada y la lee el turno siguiente.
    notifier: CaseNotifier | None = None
    #: Cuanto espera el chat a que la persona conteste la oferta de datos opcionales antes de
    #: darla por rechazada (`_resolver_si_nadie_contesta`). Opcional como el resto del ritmo
    #: de fondo: sin ella no hay espera y el caso de quien no contesta se queda en revision
    #: hasta que un ajustador lo tome. La duracion la fija la raiz de composicion.
    offer_wait: Callable[[], Awaitable[None]] | None = None

    def __post_init__(self) -> None:
        if self.task_factory is None:
            object.__setattr__(self, "task_factory", _detached_task_factory)


_runtime: GraphRuntime | None = None


def install_runtime(runtime: GraphRuntime) -> None:
    """Instala el runtime del proceso. Lo llama la raíz de composición (C-24)."""
    global _runtime
    _runtime = runtime


def get_runtime() -> GraphRuntime:
    if _runtime is None:
        msg = "el runtime de orquestación no está instalado (llame a install_runtime primero)"
        raise RuntimeError(msg)
    return _runtime


def reset_runtime() -> None:
    """Lo usan las pruebas para no compartir runtime entre corridas."""
    global _runtime
    _runtime = None


_USE_OF: dict[str, Use] = {"chat": Use.CHAT, "voice": Use.VOICE}

#: El presupuesto del nodo de captura **en el chat**, en milisegundos.
#:
#: `INTAKE_SPEC.timeout_ms` son 1.600 ms, el doble de la meta p95 de la **voz**,
#: donde alguien espera al teléfono y dos segundos de silencio ya se notan. El chat
#: heredaba ese número por compartir el mismo `NodeSpec`, y no le corresponde: quien
#: escribe está mirando una pantalla que dice que la agente está respondiendo.
#:
#: El primer número fueron 8.000 ms, de tres medidas contra el proveedor de verdad
#: --5.300, 3.719 y 2.892 ms-- más la primera conversación que Miguel tuvo por la
#: pantalla, donde dos de tres turnos se degradaron.
#:
#: El 2026-10-06 se volvió a medir, porque en producción cuatro de cinco corridas
#: del nodo se degradaron a los 8 s y la que acabó tardó 3.653 ms (`node_run`).
#: Siete llamadas de extracción al plan gratuito de `gemini-3.1-flash-lite` dieron
#: 5.360, 5.588, 5.644, 8.802, 11.673, 13.285 y 17.750 ms, más un 503 de "alta
#: demanda" y una que no respondió en 20 s. Con 11.500 ms entran dos de esas siete
#: que con 8.000 se perdían, y el plazo sigue **por debajo** del de lectura del
#: proveedor para este uso (12.000 ms, `providers.yaml`), para que el que corte
#: siga siendo este y no el transporte. Lo que no entra no lo arregla ningún número:
#: es capacidad del plan gratuito, y está escrito en `docs/PENDIENTES-MIGUEL.md`.
#:
#: **No relaja ninguna meta aprobada**: la de la voz es la de `INTAKE_SPEC` y no se
#: toca. Este número es del chat.
INTAKE_TIMEOUT_CHAT_MS = 11_500


def _intake_timeout_ms(channel: str) -> int | None:
    """El presupuesto del nodo de captura para este canal.

    `None` en la voz, que es decir "el de su especificación": repetir ahí el 1.600
    daría dos sitios donde vive el mismo número aprobado, y el día que el PRD lo
    mueva solo se cambiaría uno.
    """
    return INTAKE_TIMEOUT_CHAT_MS if channel == "chat" else None


# Las claves del catalogo van como constantes de este modulo, cada una con su
# literal escrito aqui, y **cada rama repite la suya en su propia llamada**. No es
# verbosidad: BR3.4 del catalogo exige que la clave se pueda encontrar con un grep
# en el consumidor, porque de eso depende el chequeo de claves sin consumidor. Una
# tabla indexada por canal --`_WAITING_KEY_OF[turn.channel]`-- arma la clave en
# ejecucion y deja ese chequeo ciego; el catalogo lo rechaza, y con razon.
WAITING_CHAT = CopyKey("chat.turn.waiting")
WAITING_VOICE = CopyKey("orchestration.turn.waiting")
ERROR_CHAT = CopyKey("chat.turn.error")
ERROR_VOICE = CopyKey("orchestration.turn.error")
HANDOFF_ADJUSTER = CopyKey("compliance.handoff.adjuster_review")
#: La misma derivacion en una consulta, donde nadie "conto" nada (2026-10-08).
HANDOFF_ADJUSTER_INQUIRY = CopyKey("compliance.handoff.adjuster_review_inquiry")
GUARD_DEGRADED = CopyKey("compliance.guard.degraded")
#: Las claves de degradacion que declaran los cuatro `NodeSpec`. El ejecutor
#: devuelve **la clave**, no la frase, y aqui se resuelve a texto: cada una en su
#: rama, por la misma razon de arriba.
DEGRADED_INTAKE = CopyKey("intake.degraded")
DEGRADED_TONE_CALM = CopyKey("intake.tone.calm")
DEGRADED_UNVERIFIABLE = CopyKey("policy_rag.coverage.unverifiable")
DEGRADED_HANDOFF = CopyKey("compliance.handoff.adjuster_review")


def _waiting_phrase(channel: str, *, language: Locale) -> tuple[CopyKey, str]:
    """La frase de espera del canal (BR2.4), con su clave repetida en cada rama."""
    if channel == "chat":
        return WAITING_CHAT, copy_api.t(WAITING_CHAT, locale=language)
    return WAITING_VOICE, copy_api.t(WAITING_VOICE, locale=language)


def _error_phrase(channel: str, *, language: Locale) -> tuple[CopyKey, str]:
    """La frase de error del canal (BR2.5), con su clave repetida en cada rama."""
    if channel == "chat":
        return ERROR_CHAT, copy_api.t(ERROR_CHAT, locale=language)
    return ERROR_VOICE, copy_api.t(ERROR_VOICE, locale=language)


def _degraded_phrase(clave: CopyKey | None, *, language: Locale) -> tuple[CopyKey, str]:
    """La frase de degradacion que el `NodeSpec` declaro, resuelta a texto.

    El conjunto es cerrado --son las claves de los cuatro nodos-- y se recorre
    con una rama por clave. Si un nodo declarara una clave que no este aqui, cae
    en la frase generica de la guardia en vez de quedarse sin texto: un turno sin
    respuesta es peor que uno con la respuesta menos precisa.
    """
    if clave == DEGRADED_INTAKE:
        return DEGRADED_INTAKE, copy_api.t(DEGRADED_INTAKE, locale=language)
    if clave == DEGRADED_TONE_CALM:
        return DEGRADED_TONE_CALM, copy_api.t(DEGRADED_TONE_CALM, locale=language)
    if clave == DEGRADED_UNVERIFIABLE:
        return DEGRADED_UNVERIFIABLE, copy_api.t(DEGRADED_UNVERIFIABLE, locale=language)
    if clave == DEGRADED_HANDOFF:
        return DEGRADED_HANDOFF, copy_api.t(DEGRADED_HANDOFF, locale=language)
    return GUARD_DEGRADED, copy_api.t(GUARD_DEGRADED, locale=language)


def _config(tenant_id: TenantId, case_id: str) -> RunnableConfig:
    return {"configurable": {"tenant_id": tenant_id, "thread_id": case_id}}


async def _current_state(runtime: GraphRuntime, tenant_id: TenantId, case_id: str) -> GraphState:
    """El último punto de control del caso, o un estado vacío si no hay ninguno (BR3.1, BR3.2)."""
    tupla = await runtime.checkpointer.aget_tuple(_config(tenant_id, case_id))
    if tupla is None:
        return GraphState(tenant_id=tenant_id, case_id=case_id, turn_id="", turn_text="")
    valores = tupla.checkpoint.get("channel_values", {})
    return GraphState(
        tenant_id=tenant_id,
        case_id=case_id,
        turn_id=valores.get("turn_id", ""),
        turn_text=valores.get("turn_text", ""),
        node_writes=dict(valores.get("node_writes", {})),
        pending_background=frozenset(valores.get("pending_background", frozenset())),
    )


def _escrituras_de(salida: Any) -> dict[str, Any]:
    """El conjunto de escritura de un nodo, campo por campo de su `Output`.

    Sale de los campos del modelo y no de una lista escrita aparte, que es lo que
    `NodeSpec.writes` ya exige: una lista suelta deja de coincidir con el modelo el
    dia que el nodo escribe un campo mas.
    """
    return {campo: getattr(salida, campo) for campo in type(salida).model_fields}


async def _continuar_el_fondo(
    runtime: GraphRuntime,
    contexto: case_context.CaseContext,
    estado: GraphState,
    *,
    replay_cached: bool = False,
) -> GraphState:
    """Encadena lo que sigue a la cobertura: `decision` y despues `compliance`.

    **La secuencia no se escribe aqui**: la decide `transition()`, que es pura,
    cerrada y la misma que enruta el grafo compilado. Este bucle solo pregunta
    "¿quien sigue?" y ejecuta, y `INTAKE` es su forma de decir que la secuencia
    termino --en el ritmo de fondo ese nombre no es un destino, es el final--.

    Cada nodo deja su punto de control antes de que corra el siguiente: una cadena
    que escribiera solo al final perderia el trabajo de los dos primeros nodos
    cuando el tercero falle, y es justo el caso que su presupuesto de latencia
    contempla.

    **Un nodo que no termina detiene la cadena, y no se traga.** El ejecutor ya
    dejo su rastro doble --la fila del nodo y el evento del tramo-- y lo que el
    estado conserva es lo que de verdad se calculo: seguir sin la decision dejaria
    a `compliance` revisando un caso sin reglas disparadas, que es exactamente la
    evidencia incompleta que su propia regla rechaza.

    **`replay_cached`** es para el cierre de un reporte (US1.17, 2026-10-13). El ejecutor
    guarda cada corrida por caso, nodo y entrada (BR5.4): si la entrada es la misma, devuelve
    "ya estaba terminada" **sin la salida**, porque la salida vive en el punto de control. El
    cierre limpia esas escrituras antes de empezar --una decision vieja, calculada a mitad de la
    conversacion con datos incompletos, no puede decidir el cierre-- y entonces "ya estaba" deja
    la cadena sin decision: justo lo que pasa cuando la persona contesta "asi esta bien" a la
    oferta de datos opcionales y las reglas ven los mismos insumos que la primera vez. Con la
    bandera, la salida se recupera volviendo a correr el nodo, que es idempotente por contrato
    (`decision` guarda su evaluacion por un identificador determinista y `compliance` guarda su
    revision por (caso, turno revisado)): da lo mismo y no duplica filas. Si ni eso se puede, la
    cadena se detiene y el cierre deriva.
    """
    corridos: set[NodeName] = set()
    while (siguiente := transition(estado)) is not NodeName.INTAKE:
        if siguiente in corridos:
            # **La guarda del bucle.** La cadena avanza porque cada nodo escribe el
            # campo que `transition` mira; el dia que un nodo deje de escribirlo, sin
            # esto el trabajo de fondo giraria para siempre --y gira en una tarea que
            # nadie espera, asi que no se notaria hasta que el proceso se cayera--.
            observability.emit(
                "orchestration.background_step_repeated",
                tenant_id=estado.tenant_id,
                case_id=estado.case_id,
                node=siguiente.value,
            )
            return estado
        corridos.add(siguiente)
        paso = runtime.background.get(siguiente)
        if paso is None:
            # Un despliegue con el fondo a medias. Se dice con el nombre del nodo
            # que falta: sin este evento, la cadena se detendria en silencio y el
            # caso se quedaria sin decision sin que nada lo explicara.
            observability.emit(
                "orchestration.background_step_not_installed",
                tenant_id=estado.tenant_id,
                case_id=estado.case_id,
                node=siguiente.value,
            )
            return estado
        entrada = await paso.build_input(contexto, estado)
        if entrada is None:
            # El nodo no tiene nada que hacer con este caso, y quien lo sabe es su
            # fabrica de entrada. Tambien se dice.
            observability.emit(
                "orchestration.background_step_skipped",
                tenant_id=estado.tenant_id,
                case_id=estado.case_id,
                node=siguiente.value,
            )
            return estado
        try:
            resultado = await runtime.executor.run(
                paso.node, entrada, tenant_id=estado.tenant_id, case_id=estado.case_id
            )
        except Exception as error:
            # **No se traga y no se convierte en un fallo de nodo.** El ejecutor
            # aplica la politica de fallo de lo que un nodo puede fallar --plazo
            # agotado y error de proveedor-- y cualquier otra excepcion es un
            # defecto, que el proyecto deja salir a proposito. Lo que esto anade es
            # **donde paso**: `launch_background` ya recoge la excepcion de la tarea
            # y la deja en la traza, pero con el tipo del error y nada mas; sin esta
            # linea, un defecto en la cadena se veria como un `KeyError` sin caso y
            # sin nodo.
            observability.emit(
                "orchestration.background_node_crashed",
                tenant_id=estado.tenant_id,
                case_id=estado.case_id,
                node=siguiente.value,
                error_type=type(error).__name__,
            )
            raise
        if resultado.outcome is not NodeRunOutcome.SUCCEEDED:
            return estado
        salida = resultado.output
        if salida is None and replay_cached:
            salida = await _reproducir_la_corrida_guardada(
                paso, entrada, tenant_id=estado.tenant_id, case_id=estado.case_id, node=siguiente
            )
        if salida is None:
            return estado
        estado = GraphState(
            tenant_id=estado.tenant_id,
            case_id=estado.case_id,
            turn_id=estado.turn_id,
            turn_text=estado.turn_text,
            node_writes={**estado.node_writes, **_escrituras_de(salida)},
            pending_background=frozenset(),
        )
        await _write_checkpoint(runtime, estado)
    return estado


async def _reproducir_la_corrida_guardada(
    paso: BackgroundStep, entrada: Any, *, tenant_id: str, case_id: str, node: NodeName
) -> Any | None:
    """La salida de un nodo cuya corrida el ejecutor ya tenia terminada, o `None` si no se pudo.

    Vuelve a correr el nodo **sin pasar por el ejecutor**, que es quien dijo "ya estaba": los
    dos nodos de esta cadena son idempotentes por contrato y su salida es una funcion de su
    entrada. Lo que el ejecutor aporta --plazo, reintento, degradacion-- se conserva a medias:
    el mismo plazo del nodo, y si vence o el proveedor falla, `None` y la cadena se detiene.
    """
    observability.emit(
        "orchestration.background_step_replayed",
        tenant_id=tenant_id,
        case_id=case_id,
        node=node.value,
    )
    try:
        with traces.node_span(paso.node.spec.name):
            return await asyncio.wait_for(
                paso.node.run(entrada), timeout=paso.node.spec.timeout_ms / 1000
            )
    except (TimeoutError, ProviderError):
        observability.emit(
            "orchestration.background_step_replay_failed",
            tenant_id=tenant_id,
            case_id=case_id,
            node=node.value,
        )
        return None


async def _write_checkpoint(runtime: GraphRuntime, state: GraphState) -> None:
    """Un punto de control después de este turno (BR3.1), con la forma mínima ya probada.

    La misma forma de `Checkpoint` que `test_checkpointer.py` ya ejercita: sin
    pasar por un grafo compilado, porque la entrada de `intake` depende del
    caso y no solo de `GraphState` (ver el docstring de `GraphRuntime`).
    """
    valores: dict[str, object] = {
        "tenant_id": state.tenant_id,
        "case_id": state.case_id,
        "turn_id": state.turn_id,
        "turn_text": state.turn_text,
        "node_writes": dict(state.node_writes),
        "pending_background": state.pending_background,
    }
    checkpoint: Checkpoint = {
        "v": 4,
        "id": str(uuid.uuid4()),
        "ts": datetime.now(UTC).isoformat(),
        "channel_values": valores,
        # Version entera, no cadena: `TenantCheckpointSaver` no redefine
        # `get_next_version` y la base de LangGraph solo sabe incrementar
        # enteros (`langgraph.checkpoint.base.BaseCheckpointSaver.
        # get_next_version`) -- necesario porque el grafo de fondo, real,
        # sigue escribiendo puntos de control sobre este mismo hilo.
        "channel_versions": dict.fromkeys(valores, 1),
        "versions_seen": {},
        "updated_channels": None,
    }
    metadata: CheckpointMetadata = {"source": "loop", "step": 0, "parents": {}}
    await runtime.checkpointer.aput(
        _config(state.tenant_id, state.case_id), checkpoint, metadata, {}
    )


def _has_coverage_answer(state: GraphState) -> bool:
    """Hay una respuesta de `policy_verification` en el estado, lista para citar (BR4.2)."""
    return state.written("outcome") is not None


def _citations_of(state: GraphState) -> tuple[object, ...]:
    """Las citas que `policy_verification` dejó en el estado, o nada."""
    citas = state.written("citations")
    return citas if isinstance(citas, tuple) else ()


def _verificacion_de_cobertura(
    runtime: GraphRuntime,
) -> tuple[Node[Any, Any], Callable[[case_context.CaseContext, str, str], Any]] | None:
    """El nodo de cobertura y su fábrica de entrada, o nada si falta alguno.

    Los dos o ninguno: un nodo sin quién le arme la entrada no se puede ejecutar, y
    devolver la pareja resuelta evita que quien la use tenga que comprobar dos veces
    lo mismo y equivocarse en una.
    """
    if runtime.coverage is None or runtime.build_coverage_input is None:
        return None
    return runtime.coverage, runtime.build_coverage_input


async def preload(  # noqa: PLR0913 -- el caso, la pregunta y lo que acompana la respuesta
    case_id: str,
    *,
    tenant_id: TenantId | None = None,
    question: str = "",
    follow_up: str | None = None,
    suggestions: tuple[str, ...] = (),
    fresh: bool = False,
    spoken: bool = False,
) -> bool:
    """Dispara el ritmo de fondo; el turno nunca lo espera (BR2.1, BR2.2, FR2.3).

    `spoken` dice que la respuesta se va a **oir** en una llamada: se compone sin
    "abajo le dejo la clausula" y se guarda como turno de voz.

    `tenant_id` es opcional en la firma de C-14 solo en apariencia: esta
    unidad no tiene ningún directorio "por caso" que lo derive, así que quien
    llama (el canal, que sí lo sabe) lo pasa. Si no llega, se busca el estado
    ya guardado del caso en cualquiera de las aseguradoras conocidas -- la
    política de fila filtra por su cuenta cuál es la propia.

    Devuelve **si hay trabajo de fondo en vuelo** para este caso, contando el que
    ya estaba: `True` cuando se lanzó aquí o cuando ya había uno, `False` solo
    cuando este despliegue no tiene el ritmo de fondo cableado. Lo devuelve porque
    el desvío de cobertura tiene que elegir entre la frase de espera y la de
    degradación, y sin este dato elegiría siempre la de espera -- que prometería una
    respuesta que nadie va a traer.
    """
    runtime = get_runtime()
    resuelto = tenant_id
    if resuelto is None:
        msg = "preload necesita tenant_id: esta unidad no lo deriva de ningún directorio por caso"
        raise ValueError(msg)
    corredor = _verificacion_de_cobertura(runtime)
    if corredor is None:
        # No es un fallo del turno y no levanta: es un despliegue sin el ritmo de
        # fondo cableado. Queda en la traza para que se vea cuántas preguntas de
        # cobertura se están degradando por esta causa.
        observability.emit(
            "orchestration.background_rhythm_not_installed",
            tenant_id=resuelto,
            case_id=case_id,
        )
        return False
    nodo, construir = corredor
    if not question.strip():
        # Sin pregunta no hay que verificar: la entrada del nodo la exige, y lanzar
        # el fondo con una vacia rompia el turno que completaba la identidad.
        observability.emit(
            "orchestration.coverage_without_question", tenant_id=resuelto, case_id=case_id
        )
        return False
    estado = await _current_state(runtime, resuelto, case_id)
    if estado.pending_background or (_has_coverage_answer(estado) and not fresh):
        return True  # BR5.4: ya hay un trabajo de fondo en vuelo o ya terminado.

    contexto = await case_context.load_case_context(
        resuelto, case_id, turn_text="", now=runtime.clock()
    )
    if contexto.policy_ref is None:
        # Sin póliza identificada no hay nada contra qué verificar, y **no es un
        # fallo**: es una conversación que todavía no dijo quién es. Se dice en la
        # traza y se responde `False`, que es lo que hace que el turno degrade con su
        # frase en vez de prometer una respuesta que nadie puede calcular.
        observability.emit(
            "orchestration.coverage_without_policy",
            tenant_id=resuelto,
            case_id=case_id,
        )
        return False

    turn_id = await _turno_de_la_pregunta(resuelto, case_id, spoken=spoken)
    if turn_id is None:
        observability.emit(
            "orchestration.coverage_without_person_turn", tenant_id=resuelto, case_id=case_id
        )
        return False
    entrada = construir(contexto, question, turn_id)

    async def _correr() -> None:
        # `Use.CHAT` por aproximación: `preload(case_id)` no recibe el canal en
        # su firma (C-14 tampoco se lo da), y el trabajo de fondo no es ni
        # texto ni voz -- es del caso, no de una sesión de un canal concreto.
        # **El tramo abarca la cadena entera**, y no solo la cobertura: los tramos de
        # nodo cuelgan de uno de turno por regla escrita (BR6.1 de U5), asi que un
        # `decision` lanzado fuera de este `with` no tendria turno abierto y la
        # tarea de fondo moriria con `SpanNestingError`. Y ademas es lo correcto de
        # leer: los tres nodos son **un** trabajo de fondo de este caso, no tres.
        with traces.turn_span(tenant_id=resuelto, case_id=case_id, use=Use.CHAT, turn_id=turn_id):
            resultado = await runtime.executor.run(
                nodo, entrada, tenant_id=resuelto, case_id=case_id
            )
            if resultado.outcome is NodeRunOutcome.SUCCEEDED and resultado.output is None:
                # El ejecutor ya tenia esta misma corrida terminada (BR5.4): la
                # respuesta esta en el estado, y es la que se le lleva al chat.
                ya = await _current_state(runtime, resuelto, case_id)
                await _avisar_cobertura(
                    runtime,
                    contexto,
                    _RespuestaGuardada.de(ya),
                    follow_up=follow_up,
                    suggestions=suggestions,
                    spoken=spoken,
                )
                return
            if resultado.outcome is not NodeRunOutcome.SUCCEEDED or resultado.output is None:
                # El ejecutor ya dejó su rastro doble --la fila del nodo y el evento
                # del tramo-- y el estado se queda sin respuesta de cobertura, que es
                # lo que hace que el turno siguiente vuelva a degradar en vez de citar
                # algo que no se verificó. No se escribe nada: un punto de control con
                # la mitad de una verificación es peor que ninguno. **Pero se avisa**:
                # quien espera en el chat no puede quedarse con "un momento" (A6).
                await _avisar_cobertura(runtime, contexto, None, follow_up=follow_up, spoken=spoken)
                return
            salida = resultado.output
            await _avisar_cobertura(
                runtime,
                contexto,
                salida,
                follow_up=follow_up,
                suggestions=suggestions,
                spoken=spoken,
            )
            con_cobertura = GraphState(
                tenant_id=resuelto,
                case_id=case_id,
                turn_id=turn_id,
                turn_text="",
                node_writes={
                    **estado.node_writes,
                    **_escrituras_de(salida),
                },
                pending_background=frozenset(),
            )
            await _write_checkpoint(runtime, con_cobertura)
            # Y la secuencia sigue: `decision` y despues `compliance`.
            await _continuar_el_fondo(runtime, contexto, con_cobertura)

    # BR2.2: no se espera aquí. Una prueba que quiera ver el fondo terminado
    # antes de seguir usa su propio `task_factory` (paso 5) y espera lo que
    # esa fábrica le devuelve.
    rhythm.launch_background(_correr(), task_factory=runtime.task_factory)
    return True


#: Cuantas veces, y cada cuanto, se vuelve a buscar el turno de la persona en una
#: llamada. La voz lo escribe **sin esperarlo** --su turno tiene el presupuesto de
#: latencia mas estricto--, asi que en el primer turno puede no estar todavia.
_REINTENTOS_DEL_TURNO_HABLADO = 4
_PAUSA_DEL_TURNO_HABLADO_S = 0.25


async def _turno_de_la_pregunta(
    tenant_id: TenantId, case_id: str, *, spoken: bool = False
) -> str | None:
    """El turno de la transcripcion al que pertenece la respuesta de cobertura.

    Es el ultimo mensaje de la persona: el canal lo guarda antes de entregar el turno,
    asi que ya existe cuando el fondo arranca. La respuesta se guarda con una llave
    foranea a ese turno, y un identificador inventado (`fondo-...`) la rompia: en
    produccion ninguna respuesta de cobertura llegaba a guardarse ni al chat
    (2026-10-08). Sin turno de la persona --un caso sin transcripcion-- `None`, y el
    turno degrada con su frase en vez de prometer una respuesta.
    """
    intentos = _REINTENTOS_DEL_TURNO_HABLADO if spoken else 1
    for intento in range(intentos):
        for turno in reversed(await casos.transcript_of(tenant_id, case_id)):
            if turno.speaker is Speaker.INSURED:
                return str(turno.turn_id)
        if intento + 1 < intentos:
            await asyncio.sleep(_PAUSA_DEL_TURNO_HABLADO_S)
    return None


def _solicitud_ya_capturada(contexto: case_context.CaseContext) -> bool:
    """Una solicitud de cotizacion con sus cuatro bloques capturados (BR2.5).

    `total > 0` no es defensa contra lo imposible: un caso recien abierto puede
    llegar aqui con el mapa vacio, y `0 == 0` lo daria por completo --respondiendo
    una solicitud que nadie ha contado--.
    """
    completitud = contexto.completeness
    return (
        contexto.record_type is RecordType.QUOTE_REQUEST
        and completitud.total > 0
        and completitud.complete == completitud.total
    )


async def _responder_la_solicitud(
    runtime: GraphRuntime,
    turn: InboundTurn,
    contexto: case_context.CaseContext,
    *,
    turn_id: str,
    gate: ExitGate,
) -> AsyncIterator[TurnEvent]:
    """La respuesta a una solicitud ya capturada: la salida, la razon y la banda.

    **Tres desenlaces, y los tres son distintos a proposito.**

    - Con la elegibilidad guardada, se responde con la frase compuesta del catalogo:
      sin identificadores de regla, sin nombre de aseguradora y sin una sola cifra
      (BR2.3, BR3.1).
    - Sin ella y **con** el puerto enchufado, la frase de espera: el fondo esta
      corriendo y la respuesta llega. No se dice que no a quien todavia no se le ha
      mirado --colapsar "todavia no" con "no elegible" es la confusion que esta
      unidad existe para evitar--.
    - Sin el puerto, la frase de degradacion, que **si cierra el turno**: la de
      espera no lo cierra, asi que prometer una respuesta que nadie va a traer
      dejaria al navegador esperando para siempre. Es la misma eleccion que ya hace
      el desvio de cobertura cuando el fondo no esta cableado.
    """
    if runtime.eligibility is None:
        observability.emit(
            "orchestration.eligibility_not_wired",
            tenant_id=turn.tenant_id,
            case_id=contexto.case_id,
        )
        clave, texto_base = _degraded_phrase(None, language=turn.language)
        texto, _ = await gate.send(texto_base)
        yield TurnError(code="background_rhythm_unavailable", copy_key=clave, text=texto)
        return

    guardada = await runtime.eligibility.stored(turn.tenant_id, contexto.case_id)
    if guardada is None:
        _lanzar_elegibilidad(runtime, turn.tenant_id, contexto.case_id)
        clave, texto_base = _waiting_phrase(turn.channel, language=turn.language)
        texto, _ = await gate.send(texto_base)
        yield Waiting(copy_key=clave, text=texto)
        return

    texto_base = quote_reply.compose_eligibility_reply(
        guardada.outcome, guardada.band, guardada.explanation_key, language=turn.language
    )
    texto, _ = await gate.send(texto_base)
    yield FinalText(
        message_id=turn_id,
        text=texto,
        language=turn.language,
        case_id=contexto.case_id,
        # Compuesta de frases fijas del catalogo, ninguna la improvisa un modelo.
        from_catalog=True,
    )


def _lanzar_elegibilidad(runtime: GraphRuntime, tenant_id: TenantId, case_id: str) -> None:
    """Lanza la evaluacion de la solicitud **fuera del turno** (BR2.5 de U19).

    No se espera, igual que el resto del ritmo de fondo (BR2.2): meterla dentro
    haria que el presupuesto de latencia del turno dependiera de cuantas reglas
    tenga una aseguradora, que es justo lo que BR2.5 prohibe.

    Se dispara **en cada turno de una solicitud incompleta**, no solo en el que la
    completa, y es deliberado: `evaluate_and_store` se niega sola mientras falte un
    campo --deja su evento y no guarda nada-- asi que no hace falta adivinar aqui
    cual es el ultimo bloque. Adivinarlo seria repetir en el turno la cuenta que la
    completitud ya hace, y el dia que esa cuenta cambiara habria dos versiones.
    """

    puerto = runtime.eligibility
    if puerto is None:
        # Un despliegue sin la elegibilidad enchufada. Se dice con su evento, por la
        # misma razon que el paso de fondo que falta: sin el, la solicitud se
        # quedaria sin respuesta y nada lo explicaria.
        observability.emit(
            "orchestration.eligibility_not_wired", tenant_id=tenant_id, case_id=case_id
        )
        return

    async def _correr() -> None:
        await puerto.evaluate(tenant_id, case_id)

    rhythm.launch_background(_correr(), task_factory=runtime.task_factory)


async def resume_case(case_id: str, decision: object, *, tenant_id: TenantId | None = None) -> None:
    """Retira la pausa y reanuda desde el punto de control (BR4.4).

    **Sin ritmo de fondo cableado no hay nada que reanudar, y se dice.** La pausa que
    esta función retira es un `interrupt()` de LangGraph, y solo el grafo de fondo lo
    abre: en un despliegue sin él, ningún caso puede estar pausado así, y levantar
    haría fallar la decisión de la bandeja --que ya quedó registrada y es válida--
    por una pausa que no existe. Queda su evento, que es lo que convierte "no hacer
    nada" en algo que se ve: sin él sería el mismo silencio que esta tanda vino a
    cerrar.
    """
    runtime = get_runtime()
    if tenant_id is None:
        msg = (
            "resume_case necesita tenant_id: esta unidad no lo deriva de ningún directorio por caso"
        )
        raise ValueError(msg)
    if runtime.background_graph is None:
        observability.emit(
            "orchestration.resume_without_background_rhythm",
            tenant_id=tenant_id,
            case_id=case_id,
        )
        return
    await runtime.background_graph.ainvoke(Command(resume=decision), _config(tenant_id, case_id))


def _human_request_reason() -> PauseReason:
    """El motivo de pausa más cercano a "pidió una persona" del conjunto cerrado de BR4.1.

    `PauseReason` no declara un valor propio para esta señal (paso 6, C-11):
    `COMPLIANCE_REFERRAL` es, letra por letra, "se deriva a una persona", que
    es exactamente lo que pasó.
    """
    return PauseReason.COMPLIANCE_REFERRAL


async def handle_turn(turn: InboundTurn) -> AsyncIterator[TurnEvent]:
    """C-14: un turno entra, un flujo de eventos sale, siempre cerrado (BR2.5)."""
    if turn.case_id is None:
        raise UnaddressedTurnError("handle_turn necesita case_id (ver el docstring de la clase)")

    runtime = get_runtime()
    turn_id = f"turno-{uuid.uuid4().hex[:12]}"
    gate = ExitGate(tenant_id=turn.tenant_id, language=turn.language, case_id=turn.case_id)

    with traces.turn_span(
        tenant_id=turn.tenant_id, case_id=turn.case_id, use=_USE_OF[turn.channel], turn_id=turn_id
    ):
        try:
            async for evento in _dirigir_turno(runtime, turn, turn_id=turn_id, gate=gate):
                yield evento
        except Exception as error:  # noqa: BLE001 -- BR2.5: el camino de error tambien pasa por la puerta
            observability.emit(
                "orchestration.turn_failed",
                tenant_id=turn.tenant_id,
                case_id=turn.case_id,
                error_type=type(error).__name__,
                # Donde fallo, nunca con que: el mensaje del error puede llevar lo que
                # escribio la persona, y el archivo y la linea no (2026-10-10). Sin
                # esto un turno caido solo decia su tipo y no habia por donde buscar.
                where=observability.failure_location(error),
            )
            clave, texto_base = _error_phrase(turn.channel, language=turn.language)
            texto, _ = await gate.send(texto_base)
            yield TurnError(code="internal_error", copy_key=clave, text=texto)


#: El resultado verificado de una respuesta de cobertura. Por su valor: el turno no
#: importa el paquete de citas (contrato de capas del grafo).
_VERIFICADA = "verified"
_NO_VERIFICABLE = "unverifiable"


@dataclass(frozen=True)
class _RespuestaGuardada:
    """Una respuesta de cobertura leida del estado, con la forma de la salida del nodo."""

    outcome: object
    citations: tuple[object, ...]
    response_text: str | None
    cross_language_notice: str | None

    @staticmethod
    def de(estado: GraphState) -> _RespuestaGuardada | None:
        if not _has_coverage_answer(estado):
            return None
        texto = estado.written("response_text")
        aviso = estado.written("cross_language_notice")
        return _RespuestaGuardada(
            outcome=estado.written("outcome"),
            citations=_citations_of(estado),
            response_text=texto if isinstance(texto, str) else None,
            cross_language_notice=aviso if isinstance(aviso, str) else None,
        )


def _verificada(salida: Any) -> bool:
    return str(getattr(salida.outcome, "value", salida.outcome)) == _VERIFICADA


def _texto_de_cobertura(salida: Any | None, *, language: Locale, spoken: bool = False) -> str:
    """La respuesta de cobertura, del catalogo (fase 1, 2026-10-08).

    En una llamada no hay "abajo": la frase hablada nombra la parte y dice que la
    clausula queda en el caso.

    Verificada: nombra la parte de la poliza y la clausula exacta va debajo, como
    cita; si un endoso trae un limite, dice que el monto lo confirma un ajustador; si
    la clausula esta en otro idioma, lo avisa. Lo demas --no hay clausula, no se pudo
    verificar, se deriva-- es la frase que el nodo ya eligio.
    """
    if salida is None:
        return coverage_phrases.unverifiable_text(locale=language)
    citas = tuple(getattr(salida, "citations", ()))
    if _verificada(salida) and citas:
        # Tres frases y nada mas (2026-10-08): la parte en el idioma de la conversacion
        # --una condicion especial manda sobre la clausula que modifica--, la clausula
        # debajo, y quien confirma si aplica y por cuanto. El aviso del idioma de la
        # clausula ya lo da su tarjeta, y el del monto cabe en "y por cuanto".
        especial = next((c for c in citas if "-END-" in str(c.clause_id)), citas[0])
        parte = coverage_phrases.part_label(str(especial.clause_id), locale=language)
        if spoken:
            return coverage_phrases.found_voice_text(locale=language, part=parte)
        return coverage_phrases.found_chat_text(locale=language, part=parte)
    return salida.response_text or coverage_phrases.unverifiable_text(locale=language)


def _texto_con_explicacion(
    salida: Any | None, *, language: Locale, spoken: bool = False
) -> str | None:
    """La respuesta con lo que la IA dice que trata la clausula, o nada si no hay.

    Es la misma respuesta de `_texto_de_cobertura` con la oracion de la IA, ya
    verificada contra la clausula, en medio: que se vea que leyo la poliza
    (decision de Miguel del 2026-10-08). La guardia decide si sale.
    """
    if salida is None or not _verificada(salida):
        return None
    citas = tuple(getattr(salida, "citations", ()))
    especial = next((c for c in citas if "-END-" in str(c.clause_id)), citas[0] if citas else None)
    claim = str(getattr(especial, "claim", "") or "").strip() if especial is not None else ""
    if especial is None or not claim:
        return None
    parte = coverage_phrases.part_label(str(especial.clause_id), locale=language)
    if spoken:
        return coverage_phrases.found_voice_claim_text(locale=language, part=parte, claim=claim)
    return coverage_phrases.found_chat_claim_text(locale=language, part=parte, claim=claim)


async def _avisar_cobertura(  # noqa: PLR0913 -- la respuesta y lo que la acompana, por nombre
    runtime: GraphRuntime,
    contexto: case_context.CaseContext,
    salida: Any | None,
    *,
    follow_up: str | None = None,
    suggestions: tuple[str, ...] = (),
    spoken: bool = False,
) -> None:
    """Le lleva al canal la respuesta de cobertura que el fondo acaba de calcular.

    Pasa por la guardia de salida como todo texto al asegurado. Si habia una
    pregunta del reporte pendiente, la respuesta la retoma al final. En una llamada
    la retoma quien habla, con la pregunta que este pendiente **al decirla**.
    """
    if runtime.notifier is None:
        return
    texto_base = _texto_de_cobertura(salida, language=contexto.language, spoken=spoken)
    con_explicacion = _texto_con_explicacion(salida, language=contexto.language, spoken=spoken)
    if follow_up:
        retomar = coverage_phrases.back_to_report_text(locale=contexto.language)
        texto_base = f"{texto_base} {retomar} {follow_up}"
        if con_explicacion is not None:
            con_explicacion = f"{con_explicacion} {retomar} {follow_up}"
    puerta = ExitGate(
        tenant_id=contexto.tenant_id, language=contexto.language, case_id=contexto.case_id
    )
    puerta.case_number = contexto.case_number
    # La explicacion es de la IA: si la guardia la rechaza --un monto, una
    # afirmacion de cobertura--, sale la respuesta sin ella, nunca la de seguridad.
    texto, del_catalogo = await send_rewrite_or_base(puerta, con_explicacion, texto_base)
    verificada = salida is not None and _verificada(salida)
    # Tambien a la transcripcion: llegaba solo en vivo, y al volver al chat la
    # respuesta ya no estaba (visto el 2026-10-08). Frases del catalogo.
    await transcript_writer.say_without_turn(
        runtime.notifier,
        transcript_writer.TranscriptScope(
            tenant_id=contexto.tenant_id,
            case_id=contexto.case_id,
            channel=CaseChannel.VOICE if spoken else CaseChannel.CHAT,
            language=contexto.language,
        ),
        text=texto,
        now=runtime.clock(),
        from_catalog=del_catalogo,
        turn_id=(
            f"{transcript_writer.COVERAGE_TURN_PREFIX}{uuid.uuid4().hex[:16]}"
            if verificada and bool(getattr(salida, "citations", None))
            else None
        ),
        citations=tuple(getattr(salida, "citations", ())) if verificada else (),
        suggestions=suggestions,
        coverage_outcome=(
            str(getattr(salida.outcome, "value", salida.outcome))
            if salida is not None
            else _NO_VERIFICABLE
        ),
    )


async def _preguntar_por_cobertura(  # noqa: PLR0913 -- el turno y lo que acompana la pregunta
    runtime: GraphRuntime,
    turn: InboundTurn,
    contexto: case_context.CaseContext,
    *,
    question: str,
    follow_up: str | None,
    suggestions: tuple[str, ...],
    turn_id: str,
    gate: ExitGate,
) -> AsyncIterator[TurnEvent]:
    """Una pregunta de cobertura, en el chat o en una llamada (fase 1, 2026-10-08).

    El turno se cierra con "dejeme revisar su poliza" y la respuesta llega sola cuando
    el fondo termina, con su clausula. Sin poliza todavia, se dice que hace falta y se
    retoma lo pendiente. Antes la pantalla se quedaba en "un momento" (A6) o
    contestaba "no pude preparar esta respuesta" (A7).

    **En una llamada es lo mismo, dicho** (decision de Miguel del 2026-10-11): la
    frase de espera, y la respuesta en cuanto el fondo la tiene. La revision sigue
    corriendo en el fondo, no en el turno. Antes la respuesta no llegaba nunca --quien
    la entregaba solo existia para el chat-- y la segunda pregunta recibia la
    respuesta de la primera, que seguia guardada.
    """
    assert turn.case_id is not None  # noqa: S101 -- ya lo comprobó `handle_turn`
    en_llamada = turn.channel == "voice"
    if contexto.policy_ref is None:
        texto_base = coverage_phrases.need_policy_text(locale=turn.language)
        if follow_up:
            texto_base = f"{texto_base} {follow_up}"
    elif await preload(
        turn.case_id,
        tenant_id=turn.tenant_id,
        question=question,
        # En la llamada, lo pendiente lo retoma quien habla al decir la respuesta.
        follow_up=None if en_llamada else follow_up,
        suggestions=suggestions,
        fresh=True,
        spoken=en_llamada,
    ):
        if en_llamada:
            clave, texto_espera = _waiting_phrase(turn.channel, language=turn.language)
            texto, _ = await gate.send(texto_espera)
            yield Waiting(copy_key=clave, text=texto)
            return
        texto_base = coverage_phrases.checking_text(locale=turn.language)
    else:
        clave, texto_degradado = _degraded_phrase(None, language=turn.language)
        texto, _ = await gate.send(texto_degradado)
        yield TurnError(code="background_rhythm_unavailable", copy_key=clave, text=texto)
        return
    texto, _ = await gate.send(texto_base)
    yield FinalText(
        message_id=turn_id,
        text=texto,
        language=turn.language,
        case_id=turn.case_id,
        from_catalog=True,
        # Solo se llega aqui con la revision lanzada (o con la frase de "necesito tu
        # poliza", que no promete nada): la pantalla muestra que se esta revisando.
        answer_pending=contexto.policy_ref is not None,
    )


def _ruta_de_cobertura(  # noqa: PLR0913 -- lo que el turno ya resolvio, por nombre
    runtime: GraphRuntime,
    turn: InboundTurn,
    contexto: case_context.CaseContext,
    previo: GraphState,
    entendido: understanding.UnderstandingResponse | None,
    *,
    asks: bool,
    turn_id: str,
    gate: ExitGate,
) -> AsyncIterator[TurnEvent] | None:
    """La ruta de cobertura que toca, o `None` si el turno sigue su camino.

    En medio de un reporte, la pregunta se revisa y despues se retoma lo pendiente,
    en el chat y en una llamada. En una consulta del chat con la poliza ya
    identificada, cada pregunta se responde y sin pregunta se pide una, con un
    ejemplo: la captura ya no tiene nada que preguntar.
    """
    pregunta = (
        entendido.person_question
        if entendido is not None and entendido.person_question
        else turn.text
    )
    if contexto.record_type is RecordType.CLAIM and asks:
        return _preguntar_por_cobertura(
            runtime,
            turn,
            contexto,
            question=pregunta,
            follow_up=_lo_pendiente(previo, contexto, language=turn.language),
            suggestions=(),
            turn_id=turn_id,
            gate=gate,
        )
    if contexto.record_type is not RecordType.COVERAGE_INQUIRY or contexto.policy_ref is None:
        return None
    if asks:
        return _preguntar_por_cobertura(
            runtime,
            turn,
            contexto,
            question=pregunta,
            follow_up=None,
            suggestions=sugerencias.after_coverage(language=turn.language),
            turn_id=turn_id,
            gate=gate,
        )
    return _pedir_la_pregunta(turn, turn_id=turn_id, gate=gate)


async def _sin_perder_el_dato(
    turn: InboundTurn,
    contexto: case_context.CaseContext,
    entendido: understanding.UnderstandingResponse | None,
    *,
    asks: bool,
) -> bool:
    """Si el turno sigue como pregunta de cobertura, o como captura.

    Un dato y una pregunta en el mismo mensaje ("Nadie se lastimo. ¿Mi poliza cubre
    esto?"): el dato se anota y la pregunta se revisa en el fondo, y su respuesta llega
    sola. Antes se contestaba la pregunta y el dato se perdia, y la agente volvia a
    preguntarlo (RT-10, primera corrida completa de evaluaciones, 2026-10-09).
    """
    if not (
        asks
        and contexto.record_type is RecordType.CLAIM
        and entendido is not None
        and entendido.items
    ):
        return asks
    if contexto.policy_ref is not None:
        await preload(
            contexto.case_id,
            tenant_id=turn.tenant_id,
            question=entendido.person_question or turn.text,
            follow_up=None,
            suggestions=(),
            fresh=True,
            spoken=turn.channel == "voice",
        )
    return False


def _lo_pendiente(
    previo: GraphState, contexto: case_context.CaseContext, *, language: Locale
) -> str | None:
    """Lo que la agente estaba preguntando, para retomarlo tras la cobertura.

    En el idioma de este turno: si la persona cambio de idioma, la frase guardada
    esta en el anterior y la respuesta salia mitad en uno y mitad en otro ("To check
    that, I first need your policy. ¿Hubo alguien herido?", RT-10, 2026-10-09). Se
    vuelve a componer la pregunta del bloque pendiente en el idioma del turno.
    """
    ultimo = previo.node_writes.get("intake_response_text")
    guardado = ultimo if isinstance(ultimo, str) else None
    if language == contexto.language:
        return guardado
    bloque = blocks.next_block(contexto.record_type, contexto.completeness, contexto.state)
    if bloque in (Block.FINAL_CONFIRMATION, Block.DONE):
        return None
    faltan = blocks.missing_fields_in_block(contexto.record_type, bloque, contexto.completeness)
    return intake_composition.compose_question(bloque, faltan, language=language)


async def _pedir_la_pregunta(
    turn: InboundTurn, *, turn_id: str, gate: ExitGate
) -> AsyncIterator[TurnEvent]:
    texto, _ = await gate.send(coverage_phrases.ask_question_text(locale=turn.language))
    yield FinalText(
        message_id=turn_id,
        text=texto,
        language=turn.language,
        case_id=turn.case_id,
        from_catalog=True,
        # Preguntas de ejemplo como botones: orientan a quien no sabe que preguntar.
        suggestions=sugerencias.sample_questions(language=turn.language),
    )


async def _dirigir_turno(  # noqa: C901 -- guardas en orden, cada una corta y devuelve
    # Senales, cotizacion apagada o precio, solicitud ya capturada, desvio de cobertura,
    # y la captura. Son guardas en orden y cada una devuelve: la alternativa --un
    # despachador por tipo de turno-- esconderia el **orden**, que es lo unico que
    # importa aqui. Una emergencia tiene que cortar antes que una pregunta de precio, y
    # eso se lee en la secuencia o no se lee en ninguna parte.
    runtime: GraphRuntime,
    turn: InboundTurn,
    *,
    turn_id: str,
    gate: ExitGate,
) -> AsyncIterator[TurnEvent]:
    assert turn.case_id is not None  # noqa: S101 -- ya lo comprobó `handle_turn`
    tenant_id, case_id = turn.tenant_id, turn.case_id
    ahora = runtime.clock()

    signals = await controls.read_turn_signals(turn.text)

    # --- BR2.3/D22: peticion de persona e identidad, antes de tocar la captura -
    if signals.human_request:
        # El tipo de caso solo decide la frase: una consulta no "conto" nada.
        vista = await casos.get_case(tenant_id, case_id)
        yield await _derivar_a_persona(
            runtime,
            turn,
            case_id=case_id,
            now=ahora,
            gate=gate,
            record_type=None if vista is None else vista.record_type,
        )
        return

    if signals.identity_question:
        _, texto_base = controls.identity_answer(language=turn.language)
        texto, _ = await gate.send(texto_base)
        yield FinalText(
            message_id=turn_id,
            text=texto,
            language=turn.language,
            case_id=case_id,
            from_catalog=True,
        )
        return

    # --- BR4.2/BR4.3: el desvio de cobertura, leyendo lo que el fondo ya dejo -
    # El caso, el estado del turno anterior y la conversacion se leen a la vez: son tres
    # lecturas independientes, y en produccion cada ida a la base cuenta (2026-10-08).
    #
    # La conversacion solo se lee si este turno va a entender el mensaje: el canal que ya lo
    # entendio antes de entregarlo (el chat, para saber si cambio de tema) trae su lectura.
    entiende_aqui = (
        turn.understood is None and not turn.understood_by_channel and _entiende_con_el_modelo(turn)
    )
    tiempos: dict[str, int] = {}
    empezo = time.monotonic()
    contexto, previo, historial = await asyncio.gather(
        case_context.load_case_context(tenant_id, case_id, turn_text=turn.text, now=ahora),
        _current_state(runtime, tenant_id, case_id),
        _historial_de_la_conversacion(turn, case_id) if entiende_aqui else _nada_dicho(),
    )
    tiempos["context_ms"] = _ms_desde(empezo)
    # La guardia compara todo numero con forma de caso contra el del caso en curso
    # (BR1.7): sin este, el cierre que nombra el numero del propio caso (P4) salia
    # sustituido por "no puedo compartir esa informacion".
    gate.case_number = contexto.case_number

    # --- Fase 0 (2026-10-07): la agente entiende el mensaje con el contexto del caso.
    # La conversacion y el estado del turno anterior son lo que una respuesta corta contesta.
    entendido = turn.understood
    if entiende_aqui:
        empezo = time.monotonic()
        entendido = await _entender_con_contexto(
            runtime, turn, contexto, previo, ahora, history=historial
        )
        tiempos["understand_ms"] = _ms_desde(empezo)
    if entendido is not None and entendido.wants is understanding.Want.TALK_TO_PERSON:
        # La misma derivacion que la senal por reglas: pedir una persona dicho de
        # otra forma («prefiero un asesor de carne y hueso») tambien la pide.
        yield await _derivar_a_persona(
            runtime, turn, case_id=case_id, now=ahora, gate=gate, record_type=contexto.record_type
        )
        return

    # --- U19, AC6.1.3 y AC6.2.4: una peticion de cotizar donde esta apagada, o de un
    # precio dentro de una solicitud, recibe una frase fija del catalogo. Va antes de la
    # captura y no la extrae: el turno no se gasta en interpretar una pregunta que ya tiene
    # respuesta. No toca el motor de reglas (BR2.5): la banda todavia no la deja el fondo.
    respuesta_de_cotizacion = quote_reply.reply_before_capture(
        record_type=contexto.record_type,
        anything_captured=bool(
            contexto.completeness.complete or contexto.completeness.awaiting_readback
        ),
        quote_enabled=contexto.quote_enabled,
        text=turn.text,
        language=turn.language,
    )
    if respuesta_de_cotizacion is not None:
        texto, _ = await gate.send(respuesta_de_cotizacion.text)
        yield FinalText(
            message_id=turn_id,
            text=texto,
            language=turn.language,
            case_id=case_id,
            from_catalog=True,
        )
        return
    # --- U19, BR2.3: la solicitud ya capturada entera recibe su respuesta ---------
    # Lo mismo que hace el desvio de cobertura: el turno **lee** lo que el ritmo de
    # fondo dejo, no evalua. Va antes de la captura porque no hay nada mas que
    # capturar; dejarlo despues haria que la agente volviera a preguntar sobre una
    # solicitud completa.
    if _solicitud_ya_capturada(contexto):
        async for evento in _responder_la_solicitud(
            runtime, turn, contexto, turn_id=turn_id, gate=gate
        ):
            yield evento
        return

    pregunta_de_cobertura = (
        entendido.asks_about_coverage
        if entendido is not None
        else coverage_detour.is_coverage_question(turn.text, language=turn.language)
    )
    pregunta_de_cobertura = await _sin_perder_el_dato(
        turn, contexto, entendido, asks=pregunta_de_cobertura
    )
    ruta = _ruta_de_cobertura(
        runtime,
        turn,
        contexto,
        previo,
        entendido,
        asks=pregunta_de_cobertura,
        turn_id=turn_id,
        gate=gate,
    )
    if ruta is not None:
        async for evento in ruta:
            yield evento
        return

    # --- El turno normal de captura: el nodo real `intake`, por el ejecutor --
    async for evento in _capturar(
        runtime,
        turn,
        contexto,
        previo,
        entendido,
        signals=signals,
        turn_id=turn_id,
        gate=gate,
        tiempos=tiempos,
    ):
        yield evento


async def _capturar(  # noqa: PLR0913 -- lo que el turno ya resolvio arriba, por nombre
    runtime: GraphRuntime,
    turn: InboundTurn,
    contexto: case_context.CaseContext,
    previo: GraphState,
    entendido: understanding.UnderstandingResponse | None,
    *,
    signals: TurnSignals,
    turn_id: str,
    gate: ExitGate,
    tiempos: dict[str, int],
) -> AsyncIterator[TurnEvent]:
    """La captura: el nodo `intake` por el ejecutor, lo extraido al caso, el punto de
    control y la respuesta del turno (la del modelo, o la frase del catalogo)."""
    assert turn.case_id is not None  # noqa: S101 -- ya lo comprobó `handle_turn`
    tenant_id, case_id = turn.tenant_id, turn.case_id
    ahora = runtime.clock()
    emergency_instruction: str | None = None
    if signals.emergency:
        _, emergency_instruction = controls.emergency_instruction(
            runtime.emergency_mode, language=turn.language
        )

    # El estado del turno anterior (`previo`, leido arriba) da el bloque cuya
    # lectura quedo esperando respuesta, que es lo unico que distingue "este turno
    # es la respuesta a la lectura" de "toca leer".
    node_input = runtime.build_intake_input(
        contexto,
        turn,
        signals,
        emergency_instruction,
        awaiting_confirmation=_bloque_en_espera(previo),
        stated_values=await case_context.stated_values_for_readback(
            tenant_id, case_id, contexto.record_type, contexto.completeness, cipher=runtime.cipher
        ),
        awaiting_policy_confirmation=_poliza_en_espera(previo),
    ).model_copy(
        update={
            "spoken": turn.channel == "voice",
            "previous_block": _bloque_anterior(previo),
            "policy_repeat_asked": _poliza_repetida(previo),
            "policy_confirm_reasked": _confirmacion_repetida(previo),
        }
    )
    if entendido is not None:
        node_input = node_input.model_copy(
            update={"understood": _con_la_pregunta_de_la_consulta(entendido, contexto, turn)}
        )
    empezo = time.monotonic()
    resultado = await runtime.executor.run(
        runtime.intake,
        node_input,
        tenant_id=tenant_id,
        case_id=case_id,
        timeout_ms=_intake_timeout_ms(turn.channel),
    )

    if resultado.outcome is NodeRunOutcome.DEGRADED:
        # BR3.1: un punto de control por turno tambien cuando se degrada -- el
        # caso se conserva (BR5.2, BR5.3), y eso incluye lo que el fondo ya
        # tenia escrito antes de este turno.
        await _write_checkpoint(
            runtime,
            GraphState(
                tenant_id=tenant_id,
                case_id=case_id,
                turn_id=turn_id,
                turn_text=turn.text,
                node_writes=dict(previo.node_writes),
                pending_background=previo.pending_background,
            ),
        )
        clave, texto_base = _degraded_phrase(resultado.degraded_copy_key, language=turn.language)
        texto, _ = await gate.send(texto_base)
        yield TurnError(code=str(resultado.error_kind), copy_key=clave, text=texto)
        return

    salida = resultado.output
    assert salida is not None  # noqa: S101 -- un `succeeded` sin relanzamiento siempre trae salida
    tiempos["intake_ms"] = _ms_desde(empezo)

    # Los botones de la pregunta ya estan decididos: se buscan mientras se escribe en la
    # base, y no despues (2026-10-08). Nada de lo que sigue cambia el texto, solo lo guarda.
    botones_pedidos = asyncio.create_task(_botones_del_turno(runtime, turn, salida))
    empezo = time.monotonic()
    try:
        revision_lanzada = await _guardar_la_captura(
            runtime, turn, contexto, previo, salida, turn_id=turn_id, now=ahora
        )
    except BaseException:
        botones_pedidos.cancel()
        raise
    tiempos["writes_ms"] = _ms_desde(empezo)
    if salida.intake_session_ended is SessionEnd.ABUSE:
        botones_pedidos.cancel()
        yield await _derivar_por_abuso(runtime, turn, salida, case_id=case_id, now=ahora, gate=gate)
        return
    if salida.intake_response_key == str(intake_composition.COVERAGE_CHECKING) and (
        not revision_lanzada
    ):
        # El nodo dijo "te respondo en un momento" y no hay revision en marcha: nadie va
        # a traer esa respuesta. Se dice lo que de verdad pasa, en vez de dejar la
        # promesa (visto el 2026-10-12, con la consulta que entro sin pregunta).
        botones_pedidos.cancel()
        yield await _sin_revision_que_prometer(
            turn, salida, case_id=case_id, turn_id=turn_id, gate=gate
        )
        return
    empezo = time.monotonic()
    botones = await botones_pedidos
    tiempos["buttons_wait_ms"] = _ms_desde(empezo)

    del_modelo, motivo = _texto_del_turno(
        turn, signals, entendido, salida, revision_lanzada=revision_lanzada
    )
    texto_base = _frase_base(salida, motivo, language=turn.language)
    texto, del_catalogo = await send_rewrite_or_base(gate, del_modelo, texto_base)
    if del_modelo is not None and del_catalogo:
        # La guardia sustituyo lo que escribio el modelo: sale la frase del turno.
        motivo = FallbackReason.GUARD
    record_outcome(tenant_id, turn.channel, motivo)
    observability.emit("chat.turn_timing", tenant_id=tenant_id, channel=turn.channel, **tiempos)
    # La pregunta del nodo de captura se compone de frases del catalogo --varias por
    # turno-- y de lo que la persona ya dijo, que entra tapado por la guardia. Lo que
    # escribio el modelo ya no es del catalogo, y se trata como texto de fuera.
    yield FinalText(
        message_id=turn_id,
        text=texto,
        language=turn.language,
        case_id=case_id,
        from_catalog=del_catalogo,
        suggestions=botones,
        # La captura dijo "dejame revisar tu poliza" y el fondo ya esta revisando: en
        # una llamada quien habla aguarda callado, y en el chat la pantalla muestra que
        # se revisa. Sale de que la revision **de verdad se lanzo** y no de que el nodo
        # haya elegido esa frase.
        answer_pending=revision_lanzada,
    )


async def _sin_revision_que_prometer(
    turn: InboundTurn,
    salida: IntakeNodeOutput,
    *,
    case_id: str,
    turn_id: str,
    gate: ExitGate,
) -> FinalText | TurnError:
    """La respuesta cuando el nodo prometio una revision que no se pudo lanzar.

    Sin poliza atada la frase es la de "necesito primero tu poliza" (el numero que la
    persona dio no esta en el corpus de esta aseguradora); con la poliza atada, la
    revision no arranco por el fondo --no cableado, o sin turno de la persona--, y se
    dice con la frase de degradacion."""
    if salida.intake_policy_confirmed is None:
        texto, _ = await gate.send(coverage_phrases.need_policy_text(locale=turn.language))
        return FinalText(
            message_id=turn_id,
            text=texto,
            language=turn.language,
            case_id=case_id,
            from_catalog=True,
        )
    clave, texto_degradado = _degraded_phrase(None, language=turn.language)
    texto, _ = await gate.send(texto_degradado)
    return TurnError(code="background_rhythm_unavailable", copy_key=clave, text=texto)


async def _guardar_la_captura(  # noqa: PLR0913 -- lo que el turno ya resolvio, por nombre
    runtime: GraphRuntime,
    turn: InboundTurn,
    contexto: case_context.CaseContext,
    previo: GraphState,
    salida: IntakeNodeOutput,
    *,
    turn_id: str,
    now: datetime,
) -> bool:
    """Lo extraido al caso, la lectura resuelta, el punto de control y lo que sigue.

    Devuelve si la revision de cobertura quedo lanzada (`_despues_de_la_captura`)."""
    assert turn.case_id is not None  # noqa: S101 -- ya lo comprobó `handle_turn`
    tenant_id, case_id, ahora = turn.tenant_id, turn.case_id, now
    try:
        await case_context.apply_extracted_fields(
            tenant_id,
            case_id,
            salida.intake_extracted,
            cipher=runtime.cipher,
            channel=CaseChannel(turn.channel),
            now=ahora,
        )
        # **Despues de lo extraido y no antes**: quien rechaza una lectura suele
        # corregirla en la misma frase, y el nodo ya dejo fuera de la resolucion los
        # campos que este turno volvio a decir. Al reves, el rechazo borraria la
        # correccion recien llegada.
        if salida.intake_readback_resolved is not None:
            await case_context.apply_readback_resolution(
                tenant_id,
                case_id,
                salida.intake_readback_resolved,
                cipher=runtime.cipher,
                channel=CaseChannel(turn.channel),
                now=ahora,
            )
    except casos.CaseClosedError:
        # El caso se cerro mientras este turno corria --las reglas lo cerraron como `registered`
        # entre que se leyo y que se guardo--. Sus campos ya no cambian: su evidencia de cierre
        # atestigua lo que habia al cerrarlo. El turno no se rompe por eso: lo dicho queda en
        # la transcripcion, y la respuesta es la del caso cerrado.
        observability.emit(
            "orchestration.capture_on_closed_case", tenant_id=tenant_id, case_id=case_id
        )

    await _write_checkpoint(
        runtime,
        GraphState(
            tenant_id=tenant_id,
            case_id=case_id,
            turn_id=turn_id,
            turn_text=turn.text,
            node_writes=_writes_del_turno(previo, salida),
            pending_background=previo.pending_background,
        ),
    )

    revision_lanzada = await _despues_de_la_captura(
        tenant_id,
        case_id,
        contexto,
        salida,
        turn_id=turn_id,
        runtime=runtime,
        spoken=turn.channel == "voice",
    )

    # --- BR2.5 de U19: la elegibilidad, cuando los cuatro bloques quedan capturados -
    if (
        contexto.record_type is RecordType.QUOTE_REQUEST
        and contexto.completeness.complete < contexto.completeness.total
    ):
        _lanzar_elegibilidad(runtime, tenant_id, case_id)
    return revision_lanzada


def _entiende_con_el_modelo(turn: InboundTurn) -> bool:
    """Si el turno pasa por quien entiende (fase 3, 2026-10-09).

    En el chat, siempre. En la voz, todo lo que pasa de dos palabras (2026-10-09): con
    solo lo "largo", casi ningun turno de una llamada real llegaba al modelo y la
    llamada se comportaba distinto del chat. Un "si" o un "no" sueltos los siguen
    resolviendo reglas al instante; entender con Claude cuesta alrededor de 1 s.
    """
    if turn.channel == "chat":
        return True
    return len(turn.text.split()) > VOICE_RULES_MAX_WORDS


# --- Que texto sale: lo que escribio el modelo, o la frase del catalogo (2026-10-12) ----

#: Las frases del nodo de captura que son un hito: las dice el codigo, siempre, con su
#: frase fija. Por prefijo de la clave del catalogo: el cierre del reporte y su oferta, las
#: lecturas de confirmacion, la poliza que se encontro y la que se descarto, la calma ante
#: insultos y la emergencia.
_PREFIJOS_DE_HITO = (
    "intake.closing.",
    "intake.readback.",
    "intake.policy.",
    "intake.tone.",
    "intake.emergency.",
)


def _es_un_hito(signals: TurnSignals, salida: IntakeNodeOutput, *, revision_lanzada: bool) -> bool:
    """Si la frase de este turno la dice siempre el codigo, no el modelo.

    Son los turnos donde la frase **hace algo** que el modelo no puede saber ni prometer: la
    emergencia, el cierre del reporte con su numero, una lectura o una oferta que espera un
    si o un no, la poliza que el corpus encontro ("¿eres tu?"), la espera de una revision
    que de verdad arranco. Se reconocen por lo que el nodo escribio, no por su texto.
    """
    return (
        signals.emergency
        or salida.intake_session_ended is not None
        or salida.intake_capture_closed
        or salida.intake_awaiting_confirmation is not None
        or salida.intake_policy_match is not None
        or revision_lanzada
        or salida.intake_response_key.startswith(_PREFIJOS_DE_HITO)
        or salida.intake_response_key == str(intake_composition.COVERAGE_CHECKING)
    )


def _motivo_de_la_frase_base(
    turn: InboundTurn,
    signals: TurnSignals,
    entendido: understanding.UnderstandingResponse | None,
    salida: IntakeNodeOutput,
    *,
    revision_lanzada: bool,
) -> FallbackReason | None:
    """Por que este turno no puede decir lo que escribio el modelo, o `None` si puede."""
    if _es_un_hito(signals, salida, revision_lanzada=revision_lanzada):
        return FallbackReason.MILESTONE
    if entendido is None:
        return FallbackReason.NO_MODEL
    if turn.understood_without_case:
        return FallbackReason.OPENING_TURN
    anotados = {campo.field_key for campo in salida.intake_extracted}
    if any(item.field_key not in anotados for item in entendido.items):
        return FallbackReason.ITEMS_REJECTED
    return None


def _texto_del_turno(
    turn: InboundTurn,
    signals: TurnSignals,
    entendido: understanding.UnderstandingResponse | None,
    salida: IntakeNodeOutput,
    *,
    revision_lanzada: bool,
) -> tuple[str | None, FallbackReason | None]:
    """Lo que escribio el modelo si se puede decir, o `None` y por que sale la frase base.

    En este orden, y la primera que aplica manda:

    1. un hito (`_es_un_hito`): la frase fija;
    2. sin modelo, o el primer mensaje que abrio el caso (su respuesta se escribio sin saber
       que datos faltan): la frase base;
    3. el codigo rechazo algun dato que el modelo anoto --la respuesta se escribio contando
       con el--: la frase base;
    4. la respuesta no vale (vacia, larga, con enlace o correo, con el nombre de la agente):
       la frase base;
    5. esta escrita en el otro idioma: la frase base, en el idioma de la conversacion;
    6. la captura sigue abierta y la respuesta afirma que el reporte quedo hecho o que lo revisa
       un ajustador (`outcome_claim`): la frase de `_frase_base`, que dice lo que falta;
    7. en una llamada, si el redactor de datos personales cambia algo: la frase base, porque
       la agente nunca dice una etiqueta en voz alta;
    8. si no, `reply`. La guardia de salida corre despues, en `_capturar`.
    """
    motivo = _motivo_de_la_frase_base(
        turn, signals, entendido, salida, revision_lanzada=revision_lanzada
    )
    if motivo is not None or entendido is None:
        return None, motivo or FallbackReason.NO_MODEL
    reply = usable_reply(
        entendido.reply,
        base=salida.intake_response_text,
        agent_name=agent_name_of(turn.tenant_id, turn.language),
    )
    if reply is None:
        return None, FallbackReason.INVALID_REPLY
    if _en_el_otro_idioma(reply, turn.language):
        return None, FallbackReason.WRONG_LANGUAGE
    if _la_captura_sigue_abierta(salida) and outcome_claim.claims_outcome(reply):
        return None, FallbackReason.REPORT_NOT_DONE
    if turn.channel == "voice" and _la_voz_taparia_algo(reply, turn.language):
        return None, FallbackReason.REDACTED_VOICE
    return reply, None


def _la_captura_sigue_abierta(salida: IntakeNodeOutput) -> bool:
    """Si al terminar este turno el caso todavia tiene datos por pedir.

    Lo dice el propio nodo: el bloque que toca es uno de campos. `FINAL_CONFIRMATION` es el
    cierre y `DONE` un caso que ya salio de la captura --en revision, con un ajustador o
    cerrado--, y en esos la respuesta puede hablar del desenlace (el hito, ademas, ya lo
    dijo el codigo).
    """
    return salida.intake_next_block not in (Block.FINAL_CONFIRMATION, Block.DONE)


def _frase_base(
    salida: IntakeNodeOutput, motivo: FallbackReason | None, *, language: Locale
) -> str:
    """La frase del codigo que sale cuando no sale la del modelo.

    Casi siempre es la que compuso el nodo. La excepcion es una respuesta que dio el reporte
    por hecho sin estarlo (`REPORT_NOT_DONE`): quien llega a ese punto suele haber dicho «eso
    es todo», y la pregunta del nodo --«¿Donde ocurrio?»-- no le dice que su reporte no esta
    completo. Se le dice que falta lo siguiente, que lo que lleva queda guardado y se le pregunta
    si sigue: una sola pregunta, y nada que el aplicativo no haga.
    """
    if motivo is FallbackReason.REPORT_NOT_DONE:
        return intake_composition.compose_unfinished(salida.intake_next_block, language=language)[1]
    return salida.intake_response_text


def _en_el_otro_idioma(reply: str, language: Locale) -> bool:
    """Si lo que escribio el modelo esta, con claridad, en el otro idioma.

    Visto en una llamada simulada (2026-10-13): la llamada iba en espanol, la persona dijo
    «En English, please» y el modelo contesto en ingles por su cuenta. Sonaba bien y dejaba
    la llamada a medias: el reconocedor seguia oyendo en espanol y las frases fijas saliendo
    en espanol. El idioma lo cambia quien lleva la conversacion (`language.for_turn` en el
    chat, `CallEngine` en la llamada), no una respuesta. Sin senal suficiente --una frase
    corta, un nombre-- no se descarta nada.
    """
    leido = idioma_del_texto.for_turn(reply, current=language)
    return leido.outcome is idioma_del_texto.LanguageOutcome.DETECTED and leido.language != language


def _la_voz_taparia_algo(reply: str, language: Locale) -> bool:
    """Si el redactor de datos personales cambia algo de lo que el modelo escribio.

    Una llamada dice lo que ya paso por el redactor, y la agente nunca dice una etiqueta
    ("[NOMBRE 1]") en voz alta: ni por un dato de verdad ni por una palabra corriente que el
    detector confunda con uno. Si el redactor no puede ejecutarse tampoco se dice: falla
    cerrado, como en todo punto de salida.
    """
    try:
        return str(redaccion.redact(reply, language=language)) != reply
    except Exception:  # noqa: BLE001 -- el detector fallo: no se dice nada que no haya pasado por el
        return True


async def _historial_de_la_conversacion(
    turn: InboundTurn, case_id: str
) -> tuple[understanding.HistoryLine, ...]:
    """Las ultimas intervenciones de la conversacion **antes** de este mensaje, tal como se guardaron.

    Salen de la transcripcion, ya tapadas: lo que el modelo ve de lo anterior no lleva datos
    personales en claro. El mensaje de ahora va aparte en la peticion. Antes que el: lo que
    se dijo desde que llego el mensaje --el canal ya lo guardo en la transcripcion-- no es
    historia.

    **Incluye los casos por los que paso la conversacion** (2026-10-13): quien cambia de tema
    --consultaba su poliza y dice «quiero reportar eso como un accidente»-- sigue en un caso
    nuevo, y sin lo dicho antes la agente no sabria que es «eso».
    """
    previos = [
        dicho
        for dicho in await casos.conversation_transcript(turn.tenant_id, case_id)
        if dicho.started_at < turn.received_at
    ]
    return tuple(
        understanding.HistoryLine(
            speaker="person" if dicho.speaker is Speaker.INSURED else "agent",
            text=dicho.text_redacted,
        )
        for dicho in previos[-understanding.HISTORY_LINES :]
    )


async def _nada_dicho() -> tuple[understanding.HistoryLine, ...]:
    return ()


async def _botones_del_turno(
    runtime: GraphRuntime, turn: InboundTurn, salida: IntakeNodeOutput
) -> tuple[str, ...]:
    """Los botones de la pregunta, solo en el chat: la voz no tiene donde dibujarlos."""
    if turn.channel != "chat":
        return ()
    return await _botones(runtime, salida.intake_response_key, turn.tenant_id, turn.language)


def _con_la_pregunta_de_la_consulta(
    entendido: understanding.UnderstandingResponse,
    contexto: case_context.CaseContext,
    turn: InboundTurn,
) -> understanding.UnderstandingResponse:
    """En una consulta, la pregunta que la abrio queda guardada aunque el modelo no la
    haya puesto como dato: es lo que se responde cuando llega la poliza (fase 1)."""
    if sugerencias.is_option(turn.text) or stated_purpose.only_announces_a_policy_question(
        turn.text, language=turn.language
    ):
        # El boton «Preguntar por mi poliza» no es la pregunta: se guardaba como tal y
        # la respuesta era «no encuentro una clausula que hable de eso» (2026-10-09). Lo
        # mismo dicho con palabras --«queria preguntar por mi poliza»--: en una llamada
        # del 2026-10-14 se reviso la poliza contra ese anuncio y la consulta termino con
        # un ajustador sin que la persona hubiera hecho su pregunta.
        return entendido.model_copy(
            update={
                "items": tuple(i for i in entendido.items if i.field_key != "question_asked"),
                "person_question": None,
                "asks_about_coverage": False,
            }
        )
    if (
        contexto.record_type is not RecordType.COVERAGE_INQUIRY
        or contexto.completeness.per_field.get("question_asked", False)
        or any(item.field_key == "question_asked" for item in entendido.items)
        or not (entendido.asks_about_coverage or entendido.person_question)
    ):
        return entendido
    pregunta = understanding.UnderstoodItem(
        field_key="question_asked", value=entendido.person_question or turn.text
    )
    return entendido.model_copy(update={"items": (*entendido.items, pregunta)})


def _ms_desde(empezo: float) -> int:
    return int((time.monotonic() - empezo) * 1000)


async def _botones(
    runtime: GraphRuntime, question_key: str, tenant_id: TenantId, language: Locale
) -> tuple[str, ...]:
    """Los botones de la pregunta. El de la poliza de ejemplo nombra a su titular,
    para que conteste nombre y poliza a la vez (pedido de Miguel, 2026-10-08)."""
    ejemplo = tenancy_config.require(tenant_id).example_policy
    titular: str | None = None
    if question_key == "intake.question.identity_and_policy" and runtime.policy_lookup:
        coincidencia = await runtime.policy_lookup(tenant_id, ejemplo)
        titular = coincidencia.holder_name if coincidencia is not None else None
    return sugerencias.for_question(
        question_key, language=language, example_policy=ejemplo, example_holder=titular
    )


#: Los datos de identidad se le cuentan al modelo como «ya lo dio», sin el valor: su respuesta
#: no puede repetir el nombre ni el numero de poliza de la persona.
_SIN_VALOR_PARA_EL_MODELO = frozenset({"identity_and_policy", "driver_name"})

#: Como se le cuenta al modelo en que va el caso.
_ESTADO_PARA_EL_MODELO: dict[CaseState, understanding.CaseStatus] = {
    CaseState.OPEN: understanding.CaseStatus.RECEIVING,
    CaseState.CAPTURING: understanding.CaseStatus.RECEIVING,
    # El reporte esta completo y las reglas lo revisan: todavia no esta con un ajustador, y
    # decirle al modelo que si le haria prometer algo que puede no pasar (US1.17).
    CaseState.VERIFYING: understanding.CaseStatus.IN_REVIEW,
    CaseState.DECIDING: understanding.CaseStatus.IN_REVIEW,
    CaseState.CLOSED: understanding.CaseStatus.CLOSED,
}


def _datos_para_el_modelo(
    contexto: case_context.CaseContext,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Las claves de los datos anotados y las de los que faltan, estas en el orden en que se
    piden. Un caso que ya no esta capturando no tiene nada que pedir.

    Anotado es lo que la persona ya dijo, **tambien lo que espera su lectura de confirmacion**:
    antes ese dato contaba como faltante y la agente volvia a pedirlo. Los derivados --que
    solo escribe el codigo-- no son ni una cosa ni otra.
    """
    avance = contexto.completeness
    anotados = tuple(
        clave
        for clave, dicho in avance.per_field.items()
        if (dicho or clave in avance.awaiting_readback) and clave not in DERIVED_FIELDS
    )
    if contexto.state not in (CaseState.OPEN, CaseState.CAPTURING):
        return anotados, ()
    faltan = tuple(
        clave
        for bloque in blocks.missing_blocks(contexto.record_type, avance)
        for clave in blocks.missing_fields_in_block(contexto.record_type, bloque, avance)
        if clave not in DERIVED_FIELDS
    )
    return anotados, faltan


def _peticion_de_comprension(  # noqa: PLR0913 -- el turno, el caso, el estado y lo que se leyo aparte
    turn: InboundTurn,
    contexto: case_context.CaseContext,
    previo: GraphState,
    ahora: datetime,
    *,
    history: tuple[understanding.HistoryLine, ...] = (),
    noted_values: Mapping[str, str] | None = None,
) -> understanding.UnderstandingRequest:
    """Lo que el modelo necesita para entender y contestar: el caso, lo anotado con su valor,
    lo que falta en orden, la conversacion y el mensaje (2026-10-12).

    Pura: lo que cuesta una lectura --la conversacion, los valores abiertos-- llega ya leido.
    """
    anotados, faltan = _datos_para_el_modelo(contexto)
    valores = noted_values or {}
    return understanding.UnderstandingRequest(
        tenant_id=turn.tenant_id,
        language=turn.language,
        today=ahora.date(),
        record_type=contexto.record_type,
        quote_enabled=contexto.quote_enabled,
        noted=tuple(
            understanding.NotedDetail(
                clave, None if clave in _SIN_VALOR_PARA_EL_MODELO else valores.get(clave)
            )
            for clave in anotados
        ),
        missing=faltan,
        person_text=turn.text,
        channel=turn.channel,
        agent_name=agent_name_of(turn.tenant_id, turn.language),
        case_status=_ESTADO_PARA_EL_MODELO.get(
            contexto.state, understanding.CaseStatus.WITH_ADJUSTER
        ),
        policy_identified=contexto.policy_ref is not None,
        answer_pending=bool(previo.pending_background),
        history=history,
    )


async def _entender_con_contexto(  # noqa: PLR0913 -- el turno, el caso, el estado, la hora y la conversacion ya leida
    runtime: GraphRuntime,
    turn: InboundTurn,
    contexto: case_context.CaseContext,
    previo: GraphState,
    ahora: datetime,
    *,
    history: tuple[understanding.HistoryLine, ...],
) -> understanding.UnderstandingResponse | None:
    """El mensaje entendido (y contestado) con el contexto del caso, o `None` si no se pudo.

    Abre en claro los valores de lo ya anotado --salvo los de identidad--: es lo que le
    permite a la respuesta no pedir lo que ya se dio. Se abren solo los de campos anotados,
    nunca el caso entero (`open_field_values`).
    """
    if runtime.understander is None:
        return None
    anotados, _ = _datos_para_el_modelo(contexto)
    pedidos = tuple(clave for clave in anotados if clave not in _SIN_VALOR_PARA_EL_MODELO)
    valores = await casos.open_field_values(
        turn.tenant_id, contexto.case_id, pedidos, cipher=runtime.cipher
    )
    return await understanding.understand(
        runtime.understander,
        _peticion_de_comprension(
            turn, contexto, previo, ahora, history=history, noted_values=valores
        ),
    )


async def understand_turn(turn: InboundTurn) -> understanding.UnderstandingResponse | None:
    """El mensaje de un chat con caso, entendido **antes** de entregarlo al turno (2026-10-12).

    Lo pide el canal para saber si la persona cambio de tema y hay que abrir otro caso, y el
    turno no vuelve a llamar al modelo: recibe lo entendido en `InboundTurn.understood`.

    `None` si no hay modelo, si fallo o tardo, o si el turno lo resuelve una senal por reglas
    --pedir a un ajustador, preguntar quien es la agente-- o por una regla de palabras --una
    respuesta de voz de una o dos palabras--: esas ni llaman al modelo en el turno, y llamarlo
    aqui seria pagarlo para tirar la respuesta.

    **Lo piden dos canales**: el chat, antes de entregar el mensaje, y la llamada, en cuanto el
    reconocedor entrega el final de la frase y mientras corre la tolerancia de fin de habla
    (`voice.early_understanding`). La llamada la puede cancelar y descartar si la persona sigue
    hablando; por eso esta funcion no escribe nada: lee el caso, la conversacion y el modelo.
    """
    runtime = _runtime
    if runtime is None or turn.case_id is None or runtime.understander is None:
        # Sin runtime instalado no hay a quien entender; si el turno de verdad se entrega,
        # `handle_turn` es quien lo dice (`get_runtime` levanta con su mensaje).
        return None
    if not _entiende_con_el_modelo(turn):
        # Una respuesta de una o dos palabras en la voz la resuelven las reglas: leerla aqui
        # seria pagar el modelo para tirar la lectura (la llamada adelanta esta lectura).
        return None
    senales = await controls.read_turn_signals(turn.text)
    if senales.human_request or senales.identity_question:
        return None
    contexto, previo, historial = await asyncio.gather(
        case_context.read_case_context(turn.tenant_id, turn.case_id),
        _current_state(runtime, turn.tenant_id, turn.case_id),
        _historial_de_la_conversacion(turn, turn.case_id),
    )
    return await _entender_con_contexto(
        runtime, turn, contexto, previo, runtime.clock(), history=historial
    )


@dataclass(frozen=True)
class ChatCaseTurnSupport:
    """Lo que el nucleo le ofrece al chat para el cambio de tema: el `CaseTurnSupport` real.

    La raiz de composicion lo enchufa en el canal; el canal solo conoce el puerto."""

    async def understand(self, turn: InboundTurn) -> understanding.UnderstandingResponse | None:
        return await understand_turn(turn)

    async def carry_over(self, *, tenant_id: str, from_case_id: str, to_case_id: str) -> None:
        runtime = get_runtime()
        llevado = await case_context.carry_over_identity(
            tenant_id,
            from_case_id,
            to_case_id,
            cipher=runtime.cipher,
            channel=CaseChannel.CHAT,
            now=runtime.clock(),
        )
        observability.emit(
            "chat.topic_change_carried_over",
            tenant_id=tenant_id,
            case_id=to_case_id,
            carried=",".join(llevado),
        )


async def _derivar_por_abuso(  # noqa: PLR0913 -- lo que el turno ya resolvio, por nombre
    runtime: GraphRuntime,
    turn: InboundTurn,
    salida: IntakeNodeOutput,
    *,
    case_id: str,
    now: datetime,
    gate: ExitGate,
) -> Handoff:
    """C4: al cierre por insultos el caso queda de verdad con un ajustador.

    La frase de cierre lo promete y nadie lo hacia: la senal `intake_session_ended`
    no la leia ningun consumidor (visto el 2026-10-07). Va por la misma pausa que la
    peticion de persona, y la frase sale literal del catalogo, sin reformular.
    """
    await open_pause(
        runtime.pause_store,
        tenant_id=turn.tenant_id,
        case_id=case_id,
        reason=_human_request_reason(),
        now=now,
    )
    texto, _ = await gate.send(salida.intake_response_text)
    return Handoff(
        # Los umbrales de insultos son reglas de la aseguradora (BR5.4), y `RULE` es un
        # motivo con el que el canal de verdad deriva el caso (`MOTIVO_DEL_CASO`);
        # con `COMPLIANCE` se abria la pausa y el caso no llegaba a la bandeja.
        reason_code=HandoffReason.RULE,
        copy_key=CopyKey(salida.intake_response_key),
        text=texto,
        case_id=case_id,
    )


async def _derivar_a_persona(  # noqa: PLR0913 -- lo que el turno ya resolvio, por nombre
    runtime: GraphRuntime,
    turn: InboundTurn,
    *,
    case_id: str,
    now: datetime,
    gate: ExitGate,
    record_type: RecordType | None = None,
) -> Handoff:
    """BR2.3/D22: la persona pide hablar con alguien, y el caso queda con un ajustador."""
    await open_pause(
        runtime.pause_store,
        tenant_id=turn.tenant_id,
        case_id=case_id,
        reason=_human_request_reason(),
        now=now,
    )
    if record_type is RecordType.COVERAGE_INQUIRY:
        clave = HANDOFF_ADJUSTER_INQUIRY
        texto, _ = await gate.send(copy_api.t(HANDOFF_ADJUSTER_INQUIRY, locale=turn.language))
    else:
        clave = HANDOFF_ADJUSTER
        texto, _ = await gate.send(copy_api.t(HANDOFF_ADJUSTER, locale=turn.language))
    return Handoff(
        reason_code=HandoffReason.HUMAN_REQUEST,
        copy_key=clave,
        text=texto,
        case_id=case_id,
    )


__all__ = [
    "INTAKE_TIMEOUT_CHAT_MS",
    "ChatCaseTurnSupport",
    "FinalText",
    "GraphRuntime",
    "Handoff",
    "InboundTurn",
    "PartialText",
    "TurnError",
    "TurnEvent",
    "UnaddressedTurnError",
    "Waiting",
    "get_runtime",
    "handle_turn",
    "install_runtime",
    "preload",
    "reset_runtime",
    "resume_case",
    "settle_review",
    "understand_turn",
]


async def _despues_de_la_captura(  # noqa: PLR0913 -- el caso, el contexto, la salida del nodo, el turno y el reloj
    tenant_id: str,
    case_id: str,
    contexto: case_context.CaseContext,
    salida: IntakeNodeOutput,
    *,
    turn_id: str,
    runtime: GraphRuntime,
    spoken: bool = False,
) -> bool:
    """Lo que el turno hace con el caso despues de aplicar lo capturado.

    La poliza confirmada se ata al caso (P3), y si la identidad acaba de quedar
    completa se precarga la verificacion de cobertura, que ya tiene contra que
    verificar.

    Devuelve **si la revision de cobertura quedo lanzada en este turno**. Es lo que
    decide si la respuesta puede decir "te respondo en un momento": antes esta funcion
    publicaba por su cuenta, por el aviso de fondo, la frase de "que quieres saber"
    cuando no habia pregunta, y la pantalla mostraba dos textos en un turno y la
    transcripcion guardaba uno (visto el 2026-10-12). Un turno publica un solo texto,
    y lo dice `_capturar`.
    """
    await _atar_poliza_confirmada(tenant_id, case_id, salida.intake_policy_confirmed)
    if salida.intake_capture_closed:
        # P4 + US1.17: la captura termino y el caso **pasa a revision**, no a un ajustador.
        # Hasta el 2026-10-13 se derivaba aqui mismo, siempre, y la decision de cierre que las
        # reglas producen despues no la ejecutaba nadie. Ahora el caso recorre el ciclo de vida
        # que la tabla de transiciones ya tenia --`capturing -> verifying -> deciding`-- y de
        # `deciding` sale por el desenlace de la cadena de fondo (`closing_outcome`): cerrado
        # como `registered` si las reglas dicen cierre directo, o derivado si no.
        await case_context.begin_review(
            tenant_id=tenant_id,
            case_id=case_id,
            now=runtime.clock(),
            channel=CaseChannel.VOICE if spoken else CaseChannel.CHAT,
        )
        # Las reglas y la revision de cumplimiento, en el fondo. Antes solo corrian tras una
        # pregunta de cobertura, y un reporte cerrado sin preguntar llegaba sin ninguna de las
        # dos. Con la oferta de datos opcionales abierta corre igual, para que el ajustador
        # tenga que ver; el desenlace espera a que se conteste.
        rhythm.launch_background(
            _cerrar_en_el_fondo(runtime, tenant_id, case_id, spoken=spoken),
            task_factory=runtime.task_factory,
        )
    elif (
        contexto.state in closing_plan.REVIEW_STATES
        and salida.intake_awaiting_confirmation is None
        and salida.intake_session_ended is None
    ):
        # Un turno que llega con el caso ya en revision y sin oferta abierta: la persona acaba de
        # contestarla --«no, asi esta bien», o agrego lo que le ofrecian--, o escribio algo
        # mientras se revisaba. Es el mismo mecanismo para las dos cosas: se vuelve a decidir con
        # los datos de ahora. Si la cadena de antes murio, esto es lo que la retoma.
        rhythm.launch_background(
            _cerrar_en_el_fondo(runtime, tenant_id, case_id, spoken=spoken),
            task_factory=runtime.task_factory,
        )
    if (
        not spoken
        and runtime.offer_wait is not None
        and salida.intake_awaiting_confirmation is Block.FINAL_CONFIRMATION
        and (salida.intake_capture_closed or contexto.state in closing_plan.REVIEW_STATES)
    ):
        # La oferta de datos opcionales queda abierta y el desenlace la espera. En una
        # llamada la resuelve el fin de la llamada (`settle_review`); el chat no tiene un
        # final, asi que espera un rato y la da por rechazada.
        rhythm.launch_background(
            _resolver_si_nadie_contesta(runtime, tenant_id, case_id, turn_id=turn_id),
            task_factory=runtime.task_factory,
        )
    if (
        contexto.record_type is RecordType.COVERAGE_INQUIRY
        and salida.intake_policy_confirmed is not None
        and runtime.cipher is not None
    ):
        # Fase 1 (2026-10-08): la consulta acaba de identificar su poliza: se responde
        # la pregunta que abrio el caso. Sin pregunta guardada `preload` no lanza nada
        # y devuelve `False`; el nodo ya pidio la pregunta en su respuesta.
        guardada = await casos.open_field_values(
            tenant_id, case_id, ("question_asked",), cipher=runtime.cipher
        )
        return await preload(
            case_id,
            tenant_id=tenant_id,
            question=guardada.get("question_asked", ""),
            suggestions=sugerencias.after_coverage(language=contexto.language),
            fresh=True,
            spoken=spoken,
        )
    return False


#: Las escrituras de la cadena de fondo que el cierre de un reporte borra antes de volver a
#: correrla. La cadena pudo correr a mitad de la conversacion, tras una pregunta de cobertura, con
#: datos incompletos: esas escrituras siguen en el punto de control, y `transition()` --que mira
#: si `category` o `compliance_review` ya estan escritas-- daria la cadena por terminada sin
#: volver a decidir. La decision de cerrar tiene que salir de los datos finales.
_ESCRITURAS_DE_LA_CADENA = frozenset(
    {"category", "closable", "fired_rules", "closure", "compliance_review"}
)

#: Los cierres en vuelo, por aseguradora y caso. El valor dice si llego otro pedido mientras
#: corria: ese pedido no lanza una segunda cadena en paralelo --dos corridas del mismo caso
#: escribiendo el mismo punto de control-- sino que hace que la que corre **vuelva a empezar con
#: los datos de ahora** en vez de aplicar un desenlace que ya no es el de los datos.
_CIERRES_EN_CURSO: dict[tuple[str, str], bool] = {}


async def _cerrar_en_el_fondo(
    runtime: GraphRuntime, tenant_id: str, case_id: str, *, spoken: bool = False
) -> None:
    """Las reglas y la revision de un reporte que acaba de cerrar, y lo que se hace con el.

    La misma cadena que sigue a una respuesta de cobertura (`_continuar_el_fondo`),
    arrancada por el cierre, y despues **el desenlace** (`closing_outcome`): cerrar el caso
    como `registered` si las reglas dicen cierre directo, o derivarlo a un ajustador. Un solo
    cierre por caso a la vez: un pedido que llega mientras corre hace que vuelva a empezar.
    """
    llave = (tenant_id, case_id)
    if llave in _CIERRES_EN_CURSO:
        _CIERRES_EN_CURSO[llave] = True
        observability.emit(
            "orchestration.closing_rerun_requested", tenant_id=tenant_id, case_id=case_id
        )
        return
    _CIERRES_EN_CURSO[llave] = False
    try:
        await _cadena_y_desenlace(runtime, tenant_id, case_id, spoken=spoken)
    finally:
        _CIERRES_EN_CURSO.pop(llave, None)


async def settle_review(case_id: str, *, tenant_id: TenantId) -> None:
    """Una llamada termino con el reporte completo: si sigue en revision, se resuelve (US1.17).

    Colgar, un corte, el limite de tiempo o los silencios pueden terminar una llamada con la
    captura cerrada y la oferta de datos opcionales sin contestar. El desenlace espera a esa
    respuesta, y una llamada que ya no existe no la va a dar: el caso se quedaria en revision
    para siempre. **La oferta se da por rechazada** --nadie agrego nada-- y se corre el cierre,
    que cierra el caso o lo deriva. Un caso que ya no esta en revision no se toca.

    Lanza el cierre al fondo y vuelve: el fin de la llamada no espera a las reglas.
    """
    await _dar_la_oferta_por_rechazada(get_runtime(), tenant_id, case_id, spoken=True)


async def _resolver_si_nadie_contesta(
    runtime: GraphRuntime, tenant_id: str, case_id: str, *, turn_id: str
) -> None:
    """El chat no tiene un final: si nadie contesta la oferta, se da por rechazada (US1.17).

    Quien termina su reporte y cierra la pestana con la oferta abierta dejaba el caso en
    revision hasta que un ajustador lo tomara. Tras la espera, si el punto de control sigue
    siendo el del turno que hizo la oferta --no llego ningun otro-- y la oferta sigue abierta,
    se resuelve como en una llamada que termino. Un turno posterior que deje la oferta abierta
    lanza su propia espera, y esta no hace nada.

    **Es una ayuda, no la garantia.** Vive en el proceso: si se reinicia o la plataforma le
    quita el procesador mientras espera, no corre a tiempo o no corre. La garantia es que el
    caso sigue en la cola y un ajustador con credencial lo puede tomar (`inbox.actions`).
    """
    if runtime.offer_wait is None:
        return
    await runtime.offer_wait()
    estado = await _current_state(runtime, tenant_id, case_id)
    if estado.turn_id != turn_id or _bloque_en_espera(estado) is not Block.FINAL_CONFIRMATION:
        return
    await _dar_la_oferta_por_rechazada(runtime, tenant_id, case_id, spoken=False)


async def _dar_la_oferta_por_rechazada(
    runtime: GraphRuntime, tenant_id: str, case_id: str, *, spoken: bool
) -> None:
    contexto = await case_context.read_case_context(tenant_id, case_id)
    if contexto.state not in closing_plan.REVIEW_STATES:
        return
    estado = await _current_state(runtime, tenant_id, case_id)
    if _bloque_en_espera(estado) is not None:
        await _write_checkpoint(
            runtime,
            GraphState(
                tenant_id=tenant_id,
                case_id=case_id,
                turn_id=estado.turn_id,
                turn_text=estado.turn_text,
                node_writes={**estado.node_writes, "intake_awaiting_confirmation": None},
                pending_background=estado.pending_background,
            ),
        )
    observability.emit(
        "orchestration.review_settled",
        tenant_id=tenant_id,
        case_id=case_id,
        channel="voice" if spoken else "chat",
    )
    rhythm.launch_background(
        _cerrar_en_el_fondo(runtime, tenant_id, case_id, spoken=spoken),
        task_factory=runtime.task_factory,
    )


async def _estado_para_decidir(runtime: GraphRuntime, tenant_id: str, case_id: str) -> GraphState:
    """El punto de control sin las decisiones de antes y con la captura dada por cerrada.

    `intake_capture_closed` se reafirma porque el turno que contesta la oferta de datos
    opcionales lo escribio en falso (su salida ya no cierra nada) y `transition()` lo lee para
    saber que la cadena empieza en las reglas. Se guarda enseguida: un punto de control que
    sigue diciendo una categoria que se descarto es una decision que ya no es la del caso.
    """
    previo = await _current_state(runtime, tenant_id, case_id)
    vigentes = {
        clave: valor
        for clave, valor in previo.node_writes.items()
        if clave not in _ESCRITURAS_DE_LA_CADENA
    }
    estado = GraphState(
        tenant_id=tenant_id,
        case_id=case_id,
        turn_id=previo.turn_id,
        turn_text=previo.turn_text,
        node_writes={**vigentes, "intake_capture_closed": True},
        pending_background=frozenset(),
    )
    await _write_checkpoint(runtime, estado)
    return estado


async def _cadena_y_desenlace(
    runtime: GraphRuntime, tenant_id: str, case_id: str, *, spoken: bool
) -> None:
    """La cadena de fondo con los datos finales y su desenlace; **a prueba de fallos**.

    Un reporte terminado siempre acaba cerrado o con un ajustador, nunca se queda en
    `deciding`: si la cadena o el desenlace levantan, el caso se deriva antes de dejar salir la
    excepcion, que no se traga (`launch_background` la recoge y la deja en la traza).
    """
    entrega = closing_outcome.Delivery(
        notifier=runtime.notifier, clock=runtime.clock, spoken=spoken
    )
    contexto = await case_context.read_case_context(tenant_id, case_id)
    if contexto.state is CaseState.CLOSED:
        return
    turno = await _turno_de_la_pregunta(tenant_id, case_id, spoken=spoken)
    if turno is None:
        observability.emit(
            "orchestration.closing_without_person_turn", tenant_id=tenant_id, case_id=case_id
        )
        # Sin un turno de la persona no hay hasta donde acotar la revision, pero un reporte
        # terminado no se queda esperando: se deriva, sin inventarle un turno.
        await closing_outcome.refer_to_adjuster(
            tenant_id=tenant_id,
            case_id=case_id,
            context=contexto,
            turn_id=None,
            reason="no_person_turn",
            delivery=entrega,
        )
        return
    resuelto = False
    try:
        with traces.turn_span(tenant_id=tenant_id, case_id=case_id, use=Use.CHAT, turn_id=turno):
            while True:
                estado = await _estado_para_decidir(runtime, tenant_id, case_id)
                final = await _continuar_el_fondo(runtime, contexto, estado, replay_cached=True)
                if _CIERRES_EN_CURSO.get((tenant_id, case_id)):
                    # Llegaron datos mientras corria: el desenlace de esta vuelta ya no es el
                    # de los datos. Se vuelve a empezar, y se lee el caso otra vez.
                    _CIERRES_EN_CURSO[(tenant_id, case_id)] = False
                    contexto = await case_context.read_case_context(tenant_id, case_id)
                    turno = await _turno_de_la_pregunta(tenant_id, case_id, spoken=spoken) or turno
                    continue
                resuelto = False
                await closing_outcome.conclude(
                    tenant_id=tenant_id,
                    case_id=case_id,
                    context=contexto,
                    state=final,
                    offer_open=_bloque_en_espera(final) is Block.FINAL_CONFIRMATION,
                    turn_id=turno,
                    trace_ref=traces.current_trace_id(),
                    delivery=entrega,
                )
                resuelto = True
                if not _CIERRES_EN_CURSO.get((tenant_id, case_id)):
                    return
                # Llego un pedido mientras se aplicaba el desenlace --la respuesta a la
                # oferta, justo cuando esta vuelta decidia esperarla--: sin esta vuelta se
                # perderia, porque quien lo pidio ya se fue confiando en esta corrida.
                _CIERRES_EN_CURSO[(tenant_id, case_id)] = False
                contexto = await case_context.read_case_context(tenant_id, case_id)
                turno = await _turno_de_la_pregunta(tenant_id, case_id, spoken=spoken) or turno
    except Exception as error:
        observability.emit(
            "orchestration.closing_failed",
            tenant_id=tenant_id,
            case_id=case_id,
            error_type=type(error).__name__,
            where=observability.failure_location(error),
        )
        raise
    finally:
        if not resuelto:
            await closing_outcome.refer_to_adjuster(
                tenant_id=tenant_id,
                case_id=case_id,
                context=contexto,
                turn_id=turno,
                reason="closing_failed",
                delivery=entrega,
            )


async def _atar_poliza_confirmada(tenant_id: str, case_id: str, policy_number: str | None) -> None:
    """P3: la persona confirmo que la poliza es suya; el caso queda atado a ella y la
    pregunta de cobertura ya tiene contra que verificar."""
    if policy_number is None:
        return
    await casos.set_policy_ref(tenant_id, case_id, policy_number)
    observability.emit("orchestration.policy_confirmed", tenant_id=tenant_id, case_id=case_id)


def _poliza_en_espera(state: GraphState) -> PolicyMatch | None:
    """La poliza que el corpus devolvio en el turno anterior y espera el si (P3).

    Del punto de control, como el bloque en espera. Guardada como el modelo o
    como su diccionario, segun venga del proceso o de la base; cualquier otra
    cosa se descarta y la conversacion sigue sin pregunta pendiente.
    """
    valor = state.node_writes.get("intake_policy_match")
    if isinstance(valor, PolicyMatch):
        return valor
    if isinstance(valor, dict):
        try:
            return PolicyMatch.model_validate(valor)
        except ValueError:
            return None
    return None


def _poliza_repetida(state: GraphState) -> bool:
    """Si ya se le pidio a la persona que repitiera su poliza cifra por cifra (2026-10-13).

    Del punto de control. Solo vale el `True` guardado: cualquier otra cosa --ausente, nulo, un
    texto-- es que no se ha pedido, y se puede pedir.
    """
    return state.node_writes.get("intake_policy_repeat_asked") is True


def _confirmacion_repetida(state: GraphState) -> bool:
    """Si ya se volvio a preguntar "¿eres tu?" en esta conversacion (2026-10-14). Como
    `_poliza_repetida`: solo vale el `True` guardado."""
    return state.node_writes.get("intake_policy_confirm_reasked") is True


def _writes_del_turno(previo: GraphState, salida: IntakeNodeOutput) -> dict[str, Any]:
    """Lo que el punto de control guarda tras la captura: lo anterior, con lo que escribio el nodo.

    Casi todo se reemplaza turno a turno. **Dos excepciones**: que ya se pidio repetir la poliza
    y que ya se volvio a preguntar "¿eres tu?" sobreviven, porque cada una se hace una sola vez
    por conversacion y el nodo de un turno cualquiera escribe `False` por omision.
    """
    nuevos: dict[str, Any] = {
        **previo.node_writes,
        **{campo: getattr(salida, campo) for campo in type(salida).model_fields},
    }
    if _poliza_repetida(previo):
        nuevos["intake_policy_repeat_asked"] = True
    if _confirmacion_repetida(previo):
        nuevos["intake_policy_confirm_reasked"] = True
    return nuevos


def _bloque_anterior(state: GraphState) -> Block | None:
    """El bloque que la agente pregunto en el turno anterior, o `None` si no hubo.

    Del punto de control, como el bloque en espera (2026-10-10). Lo usa la captura
    para saber si un "no" corto contesta a "¿hubo alguien herido?".
    """
    return _como_bloque(state.node_writes.get("intake_next_block"))


def _bloque_en_espera(state: GraphState) -> Block | None:
    """El bloque cuya lectura de confirmacion quedo esperando respuesta.

    Sale del punto de control --el conjunto de escritura del turno anterior-- y
    no de un contador propio, por la misma razon que `blocks.next_block` no lo
    tiene: un contador se desincroniza al reanudar tras `interrupt()` y el punto
    de control no.
    """
    return _como_bloque(state.node_writes.get("intake_awaiting_confirmation"))


def _como_bloque(valor: object) -> Block | None:
    if isinstance(valor, Block):
        return valor
    # El punto de control guarda el valor del enum como texto, asi que al volver
    # llega como `str`. Un valor que no sea ninguno de los bloques se descarta en
    # vez de levantar: un punto de control de una version anterior no tiene por
    # que tumbar el turno.
    if isinstance(valor, str):
        try:
            return Block(valor)
        except ValueError:
            return None
    return None
