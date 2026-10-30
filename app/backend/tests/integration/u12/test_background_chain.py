"""La cadena del ritmo de fondo: cobertura → decisión → cumplimiento (PENDIENTES 1.8).

Lo que faltaba no era el grafo: era **que alguien encadenara los otros dos nodos**.
`compile_background_graph` existe y lo cubren las pruebas de esta carpeta, pero
producción no lo compila --su fábrica de entrada se fija al compilar y la de la
cobertura depende del caso-- así que la verificación de póliza corría sola y el
caso se quedaba sin decisión y sin revisión de cumplimiento para siempre.

Aquí la cadena corre con **los dos nodos reales** --el motor de reglas de U9 con
su guardado y la revisión completa de U10 con sus tres puertos, los que monta la
raíz de composición-- y el estado entra con la escritura de la cobertura ya hecha.
La cobertura no se ejecuta: llamar al proveedor de embeddings cuesta dinero, y lo
que esta carpeta prueba es la cadena, no el nodo que ya tiene sus pruebas.
"""

from __future__ import annotations

import asyncio
import contextvars
import dataclasses
import io
import sys
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI

from untangle import observability
from untangle.base import Frozen, Locale, Use
from untangle.case_record import api as casos
from untangle.case_record import crypto, history, repository
from untangle.case_record import transcript as transcripcion
from untangle.case_record.models import (
    Actor,
    ActorType,
    CaseField,
    CaseParty,
    CaseState,
    ChangeKind,
    Channel,
    DerivationReason,
    FieldStatus,
    Origin,
    PartyRole,
    RecordType,
    Resolution,
    Speaker,
)
from untangle.compliance.controls import api as cumplimiento
from untangle.compliance.controls.api import HandoffReason
from untangle.compliance.redaction.api import redact
from untangle.copy_catalog import api as copy_api
from untangle.orchestration import case_context, closing_outcome, closing_plan
from untangle.orchestration import turn as orchestration_turn
from untangle.orchestration.contracts import InboundTurn
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.orchestration.nodes.intake.extraction import ExtractedField
from untangle.orchestration.nodes.intake.node import IntakeNodeOutput
from untangle.orchestration.state import GraphState
from untangle.policy_rag.citations.models import CoverageOutcome
from untangle.policy_rag.corpus.models import DeclaredDriver, FormKind, IssuedPolicy, PolicyForm
from untangle.policy_rag.corpus.repository import upsert_reference_data
from untangle.rules.models import FiredRule
from untangle.server import composition
from untangle.telemetry.traces import api as trazas
from untangle.telemetry.traces.models import NodeName
from untangle.tenancy import ephemeral, session

AHORA = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)

CONTAR_EVALUACIONES = "SELECT count(*) AS total FROM rule_evaluation WHERE case_id = :case_id"
CONTAR_REVISIONES = "SELECT count(*) AS total FROM compliance_review WHERE case_id = :case_id"


@pytest.fixture
async def app(
    sesiones: ephemeral.EphemeralDatabase,
    demo_abierta: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[FastAPI]:
    """La aplicación de verdad: es la que monta los dos nodos de fondo reales.

    Con la clave de cifrado puesta, porque sin ella no hay runtime: los puntos de
    control van cifrados.
    """
    del demo_abierta
    monkeypatch.setenv(crypto.KEY_ENV_VAR, crypto.generate_key())
    from untangle.settings import Settings

    construida = composition.build_app(
        Settings(
            env="local",
            database_url=sesiones.app_url,
            commit_sha="abc1234",
            case_link_signing_key="marca-de-clave-de-enlaces-del-fondo-00012",
            case_field_encryption_key=crypto.generate_key(),
        ),
        dist_dir=tmp_path,
    )
    try:
        yield construida
    finally:
        await session.dispose()
        session.configure(sesiones.app_url)
        trazas.reset_summaries()
        copy_api.reset()
        orchestration_turn.reset_runtime()
        crypto.reset()


def _aseguradora() -> str:
    from untangle.tenancy import api as tenancy

    return tenancy.available_ids()[0]


async def _caso_con_transcripcion(tenant_id: str, case_id: str = "case-del-fondo") -> str:
    """Un caso de visitante con dos turnos, que es lo que la revisión acota."""
    await casos.create_case(
        tenant_id,
        casos.NewCase(
            case_id=case_id,
            record_type=RecordType.CLAIM,
            channel=Channel.CHAT,
            origin=Origin.PUBLIC_CHAT,
            language="es",
            # La poliza identificada: sin ella `preload` no lanza nada --una
            # conversacion que todavia no dijo quien es-- y la cadena no llegaria a
            # correr. Es la de ejemplo de la aseguradora, la misma que el corpus trae.
            policy_ref="POL-11",
        ),
        now=AHORA,
    )
    for indice, (quien, texto) in enumerate(
        (
            (Speaker.INSURED, "Me chocaron el carro ayer por la tarde"),
            (Speaker.AGENT, "Lo siento. Cuenteme que paso"),
        )
    ):
        await casos.append_turn(
            tenant_id,
            transcripcion.TurnDraft(
                # El identificador lleva el caso: una prueba que abre dos casos
                # choca con la clave primaria de la transcripcion si no lo lleva.
                turn_id=f"{case_id}-turno-{indice}",
                case_id=case_id,
                speaker=quien,
                channel=Channel.CHAT,
                language="es",
                started_at=AHORA,
            ),
            redact(texto, language="es"),
        )
    return case_id


def _con_cobertura(tenant_id: str, case_id: str) -> GraphState:
    """El estado tal como lo deja la verificación de póliza: su conjunto de escritura.

    Se escribe a mano **con los nombres reales de su `Output`**: si el nodo
    renombrara un campo, `transition()` dejaría de enrutar y esta prueba lo diría.
    """
    return GraphState(
        tenant_id=tenant_id,
        case_id=case_id,
        turn_id="fondo-de-la-prueba",
        turn_text="",
        node_writes={
            "outcome": CoverageOutcome.NO_CLAUSE_FOUND,
            "answer_id": "respuesta-de-la-prueba",
            "citation_check_ids": (),
            "clause_language": None,
            "citations": (),
        },
        pending_background=frozenset(),
    )


async def _contexto(tenant_id: str, case_id: str) -> case_context.CaseContext:
    return await case_context.load_case_context(tenant_id, case_id, turn_text="", now=AHORA)


@contextmanager
def _eventos() -> Iterator[io.StringIO]:
    """Los eventos de la traza de este rato, sin tocar la salida global.

    `observability.set_stream` existe para esto: capturar con `capsys` mezclaria
    los eventos de las fixtures --que abren sesiones y emiten los suyos-- con los
    de la prueba.
    """
    recogidos = io.StringIO()
    observability.set_stream(recogidos)
    try:
        yield recogidos
    finally:
        observability.set_stream(sys.stdout)


async def _correr_la_cadena(
    runtime: orchestration_turn.GraphRuntime, tenant_id: str, case_id: str
) -> GraphState:
    """La cadena **dentro de su tramo de turno**, como corre en produccion.

    El tramo no es decoracion: los tramos de nodo cuelgan de uno de turno por
    regla escrita (BR6.1 de U5), y el trabajo de fondo abre el suyo en `preload`.
    Una prueba que lo llamara sin tramo estaria probando un camino que no existe.
    """
    estado = _con_cobertura(tenant_id, case_id)
    with trazas.turn_span(
        tenant_id=tenant_id, case_id=case_id, use=Use.CHAT, turn_id=estado.turn_id
    ):
        return await orchestration_turn._continuar_el_fondo(
            runtime, await _contexto(tenant_id, case_id), estado
        )


async def _contar(tenant_id: str, consulta: str, case_id: str) -> int:
    async with session.session_for(tenant_id) as sesion:
        fila = await session.fetch_one(sesion, consulta, case_id=case_id)
    return int(fila["total"]) if fila is not None else 0


async def test_la_cadena_llega_hasta_la_revision_de_cumplimiento(app: FastAPI) -> None:
    """El camino entero: la decisión se evalúa y se guarda, y la revisión también.

    Las dos filas en la base son la prueba de que los nodos corrieron **de verdad**:
    el estado podría llevar los campos escritos por un doble, pero `rule_evaluation`
    y `compliance_review` solo las escribe quien hizo el trabajo.
    """
    del app
    tenant_id = _aseguradora()
    case_id = await _caso_con_transcripcion(tenant_id)
    runtime = orchestration_turn.get_runtime()

    final = await _correr_la_cadena(runtime, tenant_id, case_id)

    assert final.written("category") is not None, "la decisión no corrió"
    assert final.written("compliance_review") is not None, "la revisión no corrió"
    assert await _contar(tenant_id, CONTAR_EVALUACIONES, case_id) == 1
    assert await _contar(tenant_id, CONTAR_REVISIONES, case_id) == 1


async def test_la_precarga_es_quien_llama_a_la_cadena(app: FastAPI) -> None:
    """La pregunta que no se puede dejar sin responder: **¿quien llama a esto?**

    La cadena correcta y sin llamador seria la misma forma de defecto que esta
    tanda vino a cerrar --la decision pura que produccion no invoca-- asi que aqui
    se entra por `preload`, que es por donde se entra de verdad, con el nodo de
    cobertura sustituido por un doble: llamar al proveedor de embeddings cuesta
    dinero, y lo que falta por comprobar no es ese nodo.
    """
    del app
    import asyncio
    import contextvars
    import dataclasses

    tenant_id = _aseguradora()
    case_id = await _caso_con_transcripcion(tenant_id)
    base = orchestration_turn.get_runtime()

    lanzadas: list[asyncio.Task[None]] = []

    def _fabrica(coro: object) -> asyncio.Task[None]:
        tarea: asyncio.Task[None] = asyncio.create_task(
            coro,  # type: ignore[arg-type]
            context=contextvars.Context(),
        )
        lanzadas.append(tarea)
        return tarea

    runtime = dataclasses.replace(
        base,
        coverage=_CoberturaDoble(base.background[NodeName.DECISION].node.spec),
        build_coverage_input=lambda _contexto, _pregunta, _turno: _SinEntrada(),
        task_factory=_fabrica,
    )
    orchestration_turn.install_runtime(runtime)

    lanzado = await orchestration_turn.preload(
        case_id, question="cubre granizo", tenant_id=tenant_id
    )

    assert lanzado is True
    await asyncio.gather(*lanzadas)
    assert await _contar(tenant_id, CONTAR_EVALUACIONES, case_id) == 1
    assert await _contar(tenant_id, CONTAR_REVISIONES, case_id) == 1


async def test_la_secuencia_es_la_que_decide_la_transicion(app: FastAPI) -> None:
    """Y el orden se comprueba por las filas del ejecutor, no por el estado final.

    Un estado con los dos campos escritos no dice en qué orden se escribieron, y el
    orden es la regla: la revisión completa necesita las reglas disparadas, así que
    correrla antes dejaría su evidencia incompleta.
    """
    del app
    tenant_id = _aseguradora()
    case_id = await _caso_con_transcripcion(tenant_id)
    runtime = orchestration_turn.get_runtime()

    await _correr_la_cadena(runtime, tenant_id, case_id)

    async with session.session_for(tenant_id) as sesion:
        filas = await session.fetch_all(
            sesion,
            "SELECT node FROM node_run WHERE case_id = :case_id ORDER BY started_at, node",
            case_id=case_id,
        )
    assert [str(fila["node"]) for fila in filas] == [
        NodeName.DECISION.value,
        NodeName.COMPLIANCE.value,
    ]


async def test_un_paso_sin_enchufar_detiene_la_cadena_y_lo_dice(app: FastAPI) -> None:
    """Un despliegue con el fondo a medias no se queda en silencio.

    Es la mitad que faltaba antes de esta tanda, y la que no se veía: la cadena
    terminaba después de la cobertura y nada decía que el caso se había quedado sin
    decisión.
    """
    del app
    import dataclasses

    tenant_id = _aseguradora()
    case_id = await _caso_con_transcripcion(tenant_id)
    runtime = dataclasses.replace(orchestration_turn.get_runtime(), background={})

    with _eventos() as salida:
        final = await _correr_la_cadena(runtime, tenant_id, case_id)

    assert final.written("category") is None
    assert await _contar(tenant_id, CONTAR_EVALUACIONES, case_id) == 0
    # Y lo dice **con el nombre del nodo que falta**: un evento sin el obligaria a
    # adivinar cual de los dos pasos no estaba.
    assert "orchestration.background_step_not_installed" in salida.getvalue()
    assert NodeName.DECISION.value in salida.getvalue()


async def test_un_caso_derivado_no_se_revisa_porque_no_se_puede_acotar(
    app: FastAPI,
) -> None:
    """La revisión de un caso derivado necesita el turno de la derivación, y nadie lo guarda.

    Las dos formas de inventarlo son peores que no revisar: con el último turno, la
    revisión absolvería una derivación que llegó tarde; con nada, acusaría de no
    haber derivado a un caso que sí se derivó. La decisión **sí** corre: lo que no
    se puede acotar es la revisión.
    """
    del app
    tenant_id = _aseguradora()
    case_id = await _caso_con_transcripcion(tenant_id)
    await _derivar(tenant_id, case_id)
    runtime = orchestration_turn.get_runtime()

    with _eventos() as salida:
        final = await _correr_la_cadena(runtime, tenant_id, case_id)

    assert final.written("category") is not None
    assert final.written("compliance_review") is None
    assert await _contar(tenant_id, CONTAR_REVISIONES, case_id) == 0
    assert "orchestration.background_step_skipped" in salida.getvalue()


async def test_un_caso_derivado_con_su_turno_si_se_revisa_y_la_revision_se_acota_ahi(
    app: FastAPI,
) -> None:
    """La otra mitad de la de arriba, y la que el turno de la derivacion desbloquea.

    Un caso derivado **con** su turno anotado si recibe su revision, y la revision
    llega **hasta ese turno** y no hasta el ultimo de la conversacion: lo que se
    dijo despues de que una persona tomara el caso no es responsabilidad de la
    agente (BR5.2 de U10).

    Se deriva por el camino del canal --`derive_case`, que es quien lo hace en
    produccion-- y no escribiendo el estado a mano: lo que se comprueba es que los
    dos extremos de la costura encajen.
    """
    del app
    tenant_id = _aseguradora()
    case_id = await _caso_con_transcripcion(tenant_id)
    turnos = await casos.transcript_of(tenant_id, case_id)
    derivado = await case_context.derive_case(
        tenant_id=tenant_id,
        case_id=case_id,
        reason=HandoffReason.HUMAN_REQUEST,
        turn_id=turnos[0].turn_id,
        now=datetime.now(UTC),
    )
    assert derivado is True

    final = await _correr_la_cadena(orchestration_turn.get_runtime(), tenant_id, case_id)

    assert final.written("compliance_review") is not None
    async with session.session_for(tenant_id) as sesion:
        fila = await session.fetch_one(
            sesion,
            "SELECT reviewed_through_turn FROM compliance_review WHERE case_id = :case_id",
            case_id=case_id,
        )
    assert fila is not None
    # **Hasta el turno de la derivacion**, que es el primero de los dos: la
    # transcripcion tiene dos y la revision no llego al segundo.
    assert str(fila["reviewed_through_turn"]) == turnos[0].turn_id


async def test_cada_nodo_deja_su_punto_de_control_antes_del_siguiente(
    app: FastAPI,
) -> None:
    """Lo que la cadena conserva cuando el último nodo se rompe.

    Se rompe la revisión --su nodo levanta un error que no es de los dos que el
    ejecutor atrapa-- y lo que queda escrito es la decisión: una cadena que
    escribiera solo al final perdería el trabajo de los dos primeros nodos cada vez
    que el tercero falle.

    **El defecto sale, y eso es a propósito**: el ejecutor aplica la política de
    fallo de lo que un nodo *puede* fallar --plazo agotado, error de proveedor-- y
    cualquier otra excepción es un defecto que el proyecto deja propagarse.
    `launch_background` la recoge y la deja en la traza; lo que esta cadena añade es
    el evento que dice en qué nodo y en qué caso pasó.

    Así que lo que se comprueba no es el valor de retorno --no hay ninguno-- sino el
    **punto de control**, que es lo que sobrevive: es la pregunta de verdad, porque
    el turno siguiente lee de ahí y no de lo que esta función devolvió.
    """
    del app
    import dataclasses

    tenant_id = _aseguradora()
    case_id = await _caso_con_transcripcion(tenant_id)
    base = orchestration_turn.get_runtime()

    class _RevisionCaida:
        spec = base.background[NodeName.COMPLIANCE].node.spec

        async def run(self, state: object) -> object:
            del state
            msg = "la revisión no pudo leer la transcripción"
            raise RuntimeError(msg)

    runtime = dataclasses.replace(
        base,
        background={
            NodeName.DECISION: base.background[NodeName.DECISION],
            NodeName.COMPLIANCE: orchestration_turn.BackgroundStep(
                node=_RevisionCaida(),
                build_input=base.background[NodeName.COMPLIANCE].build_input,
            ),
        },
    )

    with pytest.raises(RuntimeError, match="transcripción"):
        await _correr_la_cadena(runtime, tenant_id, case_id)

    # La decisión quedó guardada y en el punto de control; la revisión no corrió.
    assert await _contar(tenant_id, CONTAR_EVALUACIONES, case_id) == 1
    assert await _contar(tenant_id, CONTAR_REVISIONES, case_id) == 0
    guardado = await orchestration_turn._current_state(
        orchestration_turn.get_runtime(), tenant_id, case_id
    )
    assert guardado.written("category") is not None
    assert guardado.written("compliance_review") is None


class _SinEntrada(Frozen):
    """La entrada del doble de cobertura: no mira nada.

    Es un modelo y no un objeto suelto porque el ejecutor guarda la entrada del
    nodo en su fila --`model_dump`-- y un doble que no lo fuera estaria probando un
    camino que produccion no tiene.
    """


class _CoberturaDoble:
    """Un nodo de cobertura que devuelve la escritura de una respuesta sin clausula.

    Devuelve lo mismo que el nodo real deja en el estado --sus campos, con sus
    nombres-- porque es lo que `transition()` lee para decidir quien sigue. Un
    doble con otros nombres pasaria esta prueba y no probaria la cadena.
    """

    def __init__(self, spec: object) -> None:
        from untangle.orchestration.nodes.policy_verification.node import (
            POLICY_VERIFICATION_SPEC,
        )

        del spec
        self.spec = POLICY_VERIFICATION_SPEC

    async def run(self, state: object) -> object:
        from untangle.orchestration.nodes.policy_verification.node import (
            PolicyVerificationNodeOutput,
        )

        del state
        return PolicyVerificationNodeOutput(
            outcome=CoverageOutcome.NO_CLAUSE_FOUND,
            answer_id="respuesta-del-doble",
            citation_check_ids=(),
            clause_language=None,
            citations=(),
            response_key="policy_rag.coverage.no_clause_found",
            response_text="No encuentro una clausula que lo cubra.",
        )


async def _derivar(tenant_id: str, case_id: str) -> None:
    """Lleva el caso a derivado por el camino de U4, con su motivo."""
    from untangle.case_record.models import Actor, ActorType, CaseState, DerivationReason
    from untangle.case_record.rules import TransitionContext

    # El camino corto de la tabla de transiciones: capturando y de ahi derivado.
    for estado in (CaseState.CAPTURING, CaseState.DERIVED):
        await casos.apply_transition(
            tenant_id,
            case_id,
            estado,
            context=TransitionContext(
                now=AHORA,
                actor=Actor(actor_type=ActorType.SYSTEM),
                channel=Channel.CHAT,
                derivation_reason=(DerivationReason.RULE if estado is CaseState.DERIVED else None),
            ),
        )


# --- Los insumos del motor de reglas, derivados del caso (PENDIENTES 1.8) -----

#: La regla de Knotwell que lee `other_parties_data_pending`. Se nombra aqui y no
#: se busca por su texto: el identificador es lo que el conjunto versiona.
REGLA_DE_TERCEROS = "KNO-R-06"


def _identificadores(disparadas: tuple[object, ...]) -> set[str]:
    """Los identificadores de las reglas disparadas. Se compara por identificador y
    no por su clave de explicacion: varias reglas comparten la clave y el
    identificador es lo que el conjunto versiona."""
    return {regla.id for regla in disparadas if isinstance(regla, FiredRule)}


async def _tercero_sin_telefono(tenant_id: str, case_id: str, cifrador: crypto.Cipher) -> None:
    """Un otro conductor del que se sabe el nombre y no cómo ubicarlo.

    Y el bloque de terceros **dicho**: sin él la derivación devuelve ausente a
    propósito --nadie preguntó-- y la regla no tendría por qué disparar.
    """
    await casos.register_party(
        tenant_id,
        CaseParty(
            party_id="parte-0001",
            case_id=case_id,
            role=PartyRole.OTHER_DRIVER,
            name=cifrador.seal("Lucía Restrepo"),
        ),
        cipher=cifrador,
    )
    await casos.set_field(
        tenant_id,
        CaseField(
            case_id=case_id,
            field_key="other_parties",
            value=cifrador.seal("otro carro, la conductora"),
            status=FieldStatus.STATED,
            evidence_turn_id=f"{case_id}-turno-0",
            updated_at=AHORA,
        ),
        cipher=cifrador,
        actor=Actor(actor_type=ActorType.INSURED),
        channel=Channel.CHAT,
    )


async def test_un_tercero_con_datos_pendientes_dispara_su_regla(
    app: FastAPI, cifrador: crypto.Cipher
) -> None:
    """La mitad 2 de 1.8, por el camino real: la decisión ya no va a ciegas.

    Hasta el 2026-10-03 `inputs` iba vacío y **ninguna regla de triage podía
    disparar**: todo caso caía en la de por defecto. Lo que se comprueba aquí no
    es que la función derive --eso lo prueban las unitarias, rompiéndola regla por
    regla-- sino que lo derivado **llega al motor**, que es la costura que faltaba.
    """
    tenant_id = _aseguradora()
    case_id = await _caso_con_transcripcion(tenant_id, "case-con-tercero")
    await _tercero_sin_telefono(tenant_id, case_id, cifrador)
    del app

    final = await _correr_la_cadena(orchestration_turn.get_runtime(), tenant_id, case_id)

    disparadas = final.written("fired_rules")
    assert isinstance(disparadas, tuple), "la decisión no corrió"
    # Se compara el **identificador** de la regla, que es lo estable: la clave de
    # explicacion la comparten varias reglas y el identificador no.
    assert REGLA_DE_TERCEROS in _identificadores(disparadas), disparadas


async def test_sin_terceros_esa_regla_no_dispara(app: FastAPI) -> None:
    """El control contrario, y no es decorativo.

    Sin él, una derivación que devolviera siempre cierto pasaría la de arriba y
    mandaría a revisión por terceros **todos** los casos, incluidos los que no
    tienen ninguno.
    """
    tenant_id = _aseguradora()
    case_id = await _caso_con_transcripcion(tenant_id, "case-sin-terceros")
    del app

    final = await _correr_la_cadena(orchestration_turn.get_runtime(), tenant_id, case_id)

    disparadas = final.written("fired_rules")
    assert isinstance(disparadas, tuple), "la decisión no corrió"
    assert REGLA_DE_TERCEROS not in _identificadores(disparadas), disparadas


async def _bloque_de_terceros_dicho(tenant_id: str, case_id: str, texto: str) -> None:
    """El bloque de terceros del caso, sellado con el cifrador del runtime.

    No con el de la fixture `cifrador`: la cadena ahora **abre** este valor para ver si niega a
    los terceros, y un valor que el runtime no puede abrir se omite en silencio, que es justo lo
    que esta prueba no debe confundir con «nadie dijo nada».
    """
    cifrador = orchestration_turn.get_runtime().cipher
    await casos.set_field(
        tenant_id,
        CaseField(
            case_id=case_id,
            field_key="other_parties",
            value=cifrador.seal(texto),
            status=FieldStatus.STATED,
            evidence_turn_id=f"{case_id}-turno-0",
            updated_at=AHORA,
        ),
        cipher=cifrador,
        actor=Actor(actor_type=ActorType.INSURED),
        channel=Channel.CHAT,
    )


async def test_preguntado_sin_terceros_no_es_lo_mismo_que_no_preguntado(
    app: FastAPI, cifrador: crypto.Cipher
) -> None:
    """La distinción que el proyecto hace en todas partes, aquí también.

    «Nadie preguntó» deja el campo **ausente** y la decisión va a ciegas: el evento
    `decision_without_inputs` existe para contar esas. «Se preguntó y no había
    terceros» es una respuesta comprobada, vale `false`, y esa decisión **no** va a
    ciegas aunque ninguna regla llegue a disparar con ella.

    Sin esta prueba las dos se pueden colapsar sin que nada se caiga: ninguna regla
    de triage dispara con `false`, así que el único sitio donde hoy se nota la
    diferencia es la traza --y es justo la diferencia que mañana deja, o no, cerrar
    directo un choque de un solo auto--.
    """
    tenant_id = _aseguradora()
    sin_preguntar = await _caso_con_transcripcion(tenant_id, "case-sin-preguntar")
    preguntado = await _caso_con_transcripcion(tenant_id, "case-preguntado")
    await _bloque_de_terceros_dicho(tenant_id, preguntado, "no hubo nadie más")
    del app
    runtime = orchestration_turn.get_runtime()

    with _eventos() as recogidos:
        await _correr_la_cadena(runtime, tenant_id, sin_preguntar)
        await _correr_la_cadena(runtime, tenant_id, preguntado)

    a_ciegas = {
        linea for linea in recogidos.getvalue().splitlines() if "decision_without_inputs" in linea
    }
    assert any(sin_preguntar in linea for linea in a_ciegas), a_ciegas
    assert not any(preguntado in linea for linea in a_ciegas), a_ciegas


# --- Los heridos del caso llegan al motor (2026-10-13) -------------------------------

#: La aseguradora con regla de cierre directo (SUN-R-01) y con la de heridos (SUN-R-05).
CON_CIERRE_DIRECTO = "sunmeadow"
REGLA_DE_CIERRE_DIRECTO = "SUN-R-01"
REGLA_DE_HERIDOS = "SUN-R-05"


def _disparadas(estado: GraphState) -> set[str]:
    disparadas = estado.written("fired_rules")
    assert isinstance(disparadas, tuple), "la decisión no corrió"
    return _identificadores(disparadas)


async def _anotar_heridos(
    tenant_id: str, case_id: str, texto: str, *, status: FieldStatus = FieldStatus.STATED
) -> None:
    """El campo `injuries` del caso, sellado con el cifrador del runtime.

    No con el de la fixture `cifrador`: es otra clave, y un valor que el runtime no puede
    abrir se omite en silencio, que es justo lo que esta prueba no debe confundir con
    «nadie dijo nada».
    """
    cifrador = orchestration_turn.get_runtime().cipher
    await casos.set_field(
        tenant_id,
        CaseField(
            case_id=case_id,
            field_key="injuries",
            value=cifrador.seal(texto),
            status=status,
            evidence_turn_id=f"{case_id}-turno-0",
            updated_at=AHORA,
        ),
        cipher=cifrador,
        actor=Actor(actor_type=ActorType.INSURED),
        channel=Channel.CHAT,
    )


async def _decidir(
    case_id: str,
    heridos: str | None,
    cifrador: crypto.Cipher,
    *,
    status: FieldStatus = FieldStatus.STATED,
    terceros: str = "ninguno",
) -> GraphState:
    """Un reporte de Sunmeadow con lo que dijo de heridos y de terceros (por omision, «ninguno»)."""
    await _caso_con_transcripcion(CON_CIERRE_DIRECTO, case_id)
    await _bloque_de_terceros_dicho(CON_CIERRE_DIRECTO, case_id, terceros)
    if heridos is not None:
        await _anotar_heridos(CON_CIERRE_DIRECTO, case_id, heridos, status=status)
    return await _correr_la_cadena(orchestration_turn.get_runtime(), CON_CIERRE_DIRECTO, case_id)


async def test_sin_heridos_ni_terceros_pendientes_la_decision_es_cierre_directo(
    app: FastAPI, cifrador: crypto.Cipher
) -> None:
    """Lo que la pantalla de inicio promete: «cierra por su cuenta los reportes simples».

    Hasta hoy `injuries_present` no lo producía nadie y esta decisión salía siempre en
    revisión estándar. Aquí el campo se guarda sellado, la cadena lo abre, lo deriva y el
    motor real de Sunmeadow dispara su primera regla.
    """
    del app

    final = await _decidir("case-sin-heridos", "No, nadie se lastimó.", cifrador)

    assert final.written("category") == "direct_close"
    assert final.written("closable") is True
    assert REGLA_DE_CIERRE_DIRECTO in _disparadas(final)


async def test_un_campo_confirmado_cuenta_igual_que_uno_dicho(
    app: FastAPI, cifrador: crypto.Cipher
) -> None:
    del app

    final = await _decidir("case-heridos-confirmados", "no", cifrador, status=FieldStatus.CONFIRMED)

    assert final.written("category") == "direct_close"


async def test_con_heridos_la_decision_deriva_y_no_cierra(
    app: FastAPI, cifrador: crypto.Cipher
) -> None:
    del app

    final = await _decidir("case-con-heridos", "Sí, mi esposa se golpeó la cabeza.", cifrador)

    disparadas = _disparadas(final)
    assert final.written("category") == "referral"
    assert final.written("closable") is False
    assert REGLA_DE_HERIDOS in disparadas
    assert REGLA_DE_CIERRE_DIRECTO not in disparadas


@pytest.mark.parametrize(
    ("sufijo", "dicho"),
    [
        pytest.param("duda", "Creo que no.", id="duda"),
        pytest.param("nada-grave", "Nada grave.", id="nada-grave"),
        pytest.param("no-pero", "No, pero mi hijo se golpeó la cabeza.", id="no-pero-hay-daño"),
        pytest.param("sin-decir", None, id="nadie-lo-dijo"),
    ],
)
async def test_lo_dudoso_o_ausente_no_cierra_directo(
    app: FastAPI, cifrador: crypto.Cipher, sufijo: str, dicho: str | None
) -> None:
    """El error caro es cerrar sin ajustador un reporte con lesionados.

    «Creo que no» y «nada grave» dejan el insumo ausente (revisión estándar) y «no, pero mi
    hijo se golpeó» lo deja verdadero (deriva). Ninguno puede llegar como falso.
    """
    del app

    final = await _decidir(f"case-dudoso-{sufijo}", dicho, cifrador)

    assert final.written("closable") is False
    assert REGLA_DE_CIERRE_DIRECTO not in _disparadas(final)


async def test_lo_que_dijo_la_persona_no_sale_en_la_traza(
    app: FastAPI, cifrador: crypto.Cipher
) -> None:
    """El valor del campo es dato personal: se abre para derivar y no se emite en claro.

    Un nombre dentro de la frase (que la deja sin poder leerse) y que no aparezca en ningún
    evento de la cadena, incluido el que dice que el campo se dijo y no se pudo leer.
    """
    del app

    with _eventos() as recogidos:
        await _decidir("case-heridos-con-nombre", "No, Josefina Zuluaga no se lastimó.", cifrador)

    # Sin el evento la prueba pasaria igual si la cadena no abriera el campo.
    assert "injuries_not_derivable" in recogidos.getvalue()
    assert "Zuluaga" not in recogidos.getvalue()
    assert "Josefina" not in recogidos.getvalue()


# --- Los terceros del caso llegan al motor (2026-10-13) ------------------------------------


@pytest.mark.parametrize(
    ("sufijo", "dicho"),
    [
        pytest.param("taxi", "Me chocó un taxi y se fue", id="tercero-nombrado"),
        pytest.param("moto", "Una moto, no alcancé a ver la placa", id="otro-vehiculo"),
        pytest.param("duda", "No sé si había alguien más", id="duda"),
        pytest.param("no-pero", "No, pero un taxi se fue", id="no-pero-hay-tercero"),
    ],
)
async def test_un_tercero_nombrado_sin_datos_no_cierra_directo(
    app: FastAPI, cifrador: crypto.Cipher, sufijo: str, dicho: str
) -> None:
    """El error caro de dejar el cierre directo real: cerrar solo un choque con un tercero.

    El bloque de terceros se dijo y no hay ninguna fila de partes que lo respalde (nadie le
    registro al taxi un dato). Antes eso valia `false` y, con la regla de cierre directo,
    el caso se cerraba sin ajustador. Ahora el insumo queda ausente: revision estandar.
    """
    del app

    final = await _decidir(f"case-tercero-{sufijo}", "no", cifrador, terceros=dicho)

    assert final.written("closable") is False
    assert REGLA_DE_CIERRE_DIRECTO not in _disparadas(final)


async def test_los_terceros_que_no_se_pudieron_leer_se_dicen_sin_el_valor(
    app: FastAPI, cifrador: crypto.Cipher
) -> None:
    """Se abre para decidir, no se emite: el evento nombra el estado y nunca lo dicho."""
    del app

    with _eventos() as recogidos:
        await _decidir(
            "case-terceros-con-nombre", "no", cifrador, terceros="Me chocó Josefina Zuluaga"
        )

    assert "other_parties_not_derivable" in recogidos.getvalue()
    assert "Zuluaga" not in recogidos.getvalue()
    assert "Josefina" not in recogidos.getvalue()


# --- El reporte termina cerrado o con un ajustador (US1.17, 2026-10-13) ----------------------
#
# Lo que se comprueba aqui es el efecto sobre el caso, con los dos nodos reales y la base de
# verdad: el corredor de evaluaciones solo puede mirar la decision pura (`DS-2/*/rules-closure-*`).


class _Avisos:
    """El chat de mentira: guarda lo que el fondo le dice a la persona."""

    def __init__(self) -> None:
        self.dichos: list[str] = []

    async def notify(  # noqa: PLR0913 -- la firma del puerto CaseNotifier
        self,
        tenant_id: str,
        case_id: str,
        *,
        text: str,
        citations: tuple[object, ...] = (),
        suggestions: tuple[str, ...] = (),
        coverage_outcome: str | None = None,
        language: Locale | None = None,
    ) -> bool:
        del tenant_id, case_id, citations, suggestions, coverage_outcome, language
        self.dichos.append(text)
        return True


async def _reporte_listo(
    case_id: str,
    *,
    heridos: str | None = "No, nadie se lastimó.",
    terceros: str | None = "ninguno",
    tenant_id: str = CON_CIERRE_DIRECTO,
    divulgado: bool = True,
) -> str:
    """Un reporte de Sunmeadow con la captura cerrada: el caso ya esta en `deciding`."""
    await _caso_con_transcripcion(tenant_id, case_id)
    if divulgado:
        await cumplimiento.record_disclosure(
            tenant_id=tenant_id,
            case_id=case_id,
            channel=cumplimiento.DisclosureChannel.CHAT,
            language="es",
            catalog_key="chat.opening.disclosure",
            disclosed_at=AHORA,
        )
    if terceros is not None:
        await _bloque_de_terceros_dicho(tenant_id, case_id, terceros)
    if heridos is not None:
        await _anotar_heridos(tenant_id, case_id, heridos)
    assert await case_context.begin_review(tenant_id=tenant_id, case_id=case_id, now=AHORA)
    return case_id


async def _cerrar_el_reporte(
    case_id: str, *, tenant_id: str = CON_CIERRE_DIRECTO, spoken: bool = False
) -> _Avisos:
    """El cierre en el fondo, esperado, con un chat de mentira que recoge lo que dice."""
    avisos = _Avisos()
    runtime = dataclasses.replace(orchestration_turn.get_runtime(), notifier=avisos)
    await orchestration_turn._cerrar_en_el_fondo(runtime, tenant_id, case_id, spoken=spoken)
    return avisos


async def _caso(case_id: str, tenant_id: str = CON_CIERRE_DIRECTO) -> casos.CaseView:
    vista = await casos.get_case(tenant_id, case_id)
    assert vista is not None
    return vista


async def _frases_de_la_agente(case_id: str, tenant_id: str = CON_CIERRE_DIRECTO) -> list[str]:
    turnos = await casos.transcript_of(tenant_id, case_id)
    return [t.text_redacted for t in turnos if t.speaker is Speaker.AGENT]


def _frase(clave: str) -> str:
    return copy_api.t(copy_api.CopyKey(clave), locale="es")


async def _oferta_abierta(
    case_id: str, *, abierta: bool, tenant_id: str = CON_CIERRE_DIRECTO
) -> None:
    """Deja en el punto de control lo que dejaria el turno de la captura: la oferta de datos
    opcionales abierta, o ya contestada. Un turno que contesta la oferta escribe
    `intake_capture_closed` en falso, y el cierre tiene que saberlo."""
    await orchestration_turn._write_checkpoint(
        orchestration_turn.get_runtime(),
        GraphState(
            tenant_id=tenant_id,
            case_id=case_id,
            turn_id="turno-de-la-captura",
            turn_text="",
            node_writes={
                "intake_awaiting_confirmation": Block.FINAL_CONFIRMATION if abierta else None,
                "intake_capture_closed": abierta,
            },
        ),
    )


# El paso del caso por revision ------------------------------------------------------------


async def test_la_captura_cerrada_lleva_el_caso_por_t2_y_t4_y_repetirlo_no_toca_nada(
    app: FastAPI,
) -> None:
    del app
    caso = await _caso_con_transcripcion(CON_CIERRE_DIRECTO, "case-revision")

    assert await case_context.begin_review(tenant_id=CON_CIERRE_DIRECTO, case_id=caso, now=AHORA)
    assert (await _caso(caso)).state is CaseState.DECIDING
    cambios = await history.of_case(CON_CIERRE_DIRECTO, caso)
    pasos = [c.detail for c in cambios if c.change_kind is ChangeKind.TRANSITION_APPLIED]
    assert pasos == [
        "T1: open -> capturing",
        "T2: capturing -> verifying",
        "T4: verifying -> deciding",
    ]
    # Las dos de la revision las hace el sistema, no la persona.
    revision = [c for c in cambios if c.detail in pasos[1:]]
    assert {c.actor.actor_type for c in revision} == {ActorType.SYSTEM}

    assert await case_context.begin_review(tenant_id=CON_CIERRE_DIRECTO, case_id=caso, now=AHORA), (
        "un caso que ya esta en revision sigue estandolo"
    )
    assert len(await history.of_case(CON_CIERRE_DIRECTO, caso)) == len(cambios), (
        "volver a pedirlo no puede dejar rastro de un rechazo"
    )


async def test_un_caso_que_ya_no_admite_la_revision_se_dice_y_no_se_toca(app: FastAPI) -> None:
    del app
    caso = await _caso_con_transcripcion(CON_CIERRE_DIRECTO, "case-ya-derivado")
    await _derivar(CON_CIERRE_DIRECTO, caso)
    antes = len(await history.of_case(CON_CIERRE_DIRECTO, caso))

    with _eventos() as recogidos:
        asi = await case_context.begin_review(tenant_id=CON_CIERRE_DIRECTO, case_id=caso, now=AHORA)

    assert asi is False
    assert (await _caso(caso)).state is CaseState.DERIVED
    assert "orchestration.review_not_started" in recogidos.getvalue()
    assert len(await history.of_case(CON_CIERRE_DIRECTO, caso)) == antes


# Cierra solo ------------------------------------------------------------------------------


async def test_un_reporte_simple_se_cierra_solo_como_registrado_sin_pasar_por_la_bandeja(
    app: FastAPI,
) -> None:
    """AC1.17.1 y AC1.17.2: sin heridos y con «ninguno» en terceros, las reglas de Sunmeadow dan
    cierre directo, los cuatro controles pasan y el caso queda `closed` con `registered`."""
    del app
    caso = await _reporte_listo("case-cierra-solo")

    avisos = await _cerrar_el_reporte(caso)

    vista = await _caso(caso)
    assert vista.state is CaseState.CLOSED
    assert vista.resolution is Resolution.REGISTERED
    completo = await repository.load_case(CON_CIERRE_DIRECTO, caso)
    assert completo is not None
    assert completo.closing_evidence is not None
    assert completo.closing_evidence.complete is True
    # El actor es el sistema, y no hubo decision humana: ninguna entrada es de personal.
    cambios = await history.of_case(CON_CIERRE_DIRECTO, caso)
    cierre = [c for c in cambios if c.detail is not None and c.detail.startswith("T6")]
    assert len(cierre) == 1
    assert cierre[0].actor.actor_type is ActorType.SYSTEM
    assert not any(c.actor.actor_type is ActorType.STAFF for c in cambios)
    # Se anuncia con la frase de cierre directo: al chat, y queda en la transcripcion.
    directa = _frase("compliance.closure.direct")
    assert avisos.dichos == [directa]
    assert (await _frases_de_la_agente(caso))[-1] == directa
    # Y las reglas disparadas y la revision quedaron adjuntas.
    assert await _contar(CON_CIERRE_DIRECTO, CONTAR_EVALUACIONES, caso) == 1
    assert await _contar(CON_CIERRE_DIRECTO, CONTAR_REVISIONES, caso) == 1


async def test_la_evidencia_de_cierre_dice_lo_mismo_que_la_revision_de_cumplimiento(
    app: FastAPI,
) -> None:
    """Las dos leen el mismo estado: si una dijera «vacio» donde la otra dice «no evaluado», un
    caso se cerraria con una evidencia que su propia revision habria rechazado."""
    del app
    caso = await _reporte_listo("case-misma-evidencia")
    runtime = orchestration_turn.get_runtime()
    estado = await orchestration_turn._estado_para_decidir(runtime, CON_CIERRE_DIRECTO, caso)
    contexto = await case_context.read_case_context(CON_CIERRE_DIRECTO, caso)
    with trazas.turn_span(
        tenant_id=CON_CIERRE_DIRECTO, case_id=caso, use=Use.CHAT, turn_id="fondo-de-la-prueba"
    ):
        final = await orchestration_turn._continuar_el_fondo(runtime, contexto, estado)
    assert final.written("compliance_review") is not None

    revision = composition._evidencia(final)
    cierre = closing_plan.closing_evidence(
        final, case_id=caso, has_transcript=True, trace_ref="traza"
    )

    assert revision.citations.value == cierre.cited_clauses.kind.value
    assert revision.fired_rules.value == cierre.fired_rules.kind.value


# Nunca cierra solo ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sufijo", "heridos", "terceros"),
    [
        pytest.param(
            "taxi", "No, nadie se lastimó.", "Me chocó un taxi y se fue", id="tercero-nombrado"
        ),
        pytest.param("sin-terceros", "No, nadie se lastimó.", None, id="nadie-dijo-lo-de-terceros"),
        pytest.param("herido", "Sí, mi esposa se golpeó la cabeza.", "ninguno", id="heridos"),
        pytest.param("duda", "Creo que no.", "ninguno", id="duda-de-heridos"),
        pytest.param("sin-heridos", None, "ninguno", id="nadie-dijo-lo-de-heridos"),
    ],
)
async def test_lo_que_no_es_un_cierre_limpio_termina_con_un_ajustador(
    app: FastAPI, sufijo: str, heridos: str | None, terceros: str | None
) -> None:
    """Regla 5 de punta a punta: un tercero nombrado sin datos nunca da cierre directo."""
    del app
    caso = await _reporte_listo(f"case-con-ajustador-{sufijo}", heridos=heridos, terceros=terceros)

    avisos = await _cerrar_el_reporte(caso)

    vista = await _caso(caso)
    assert vista.state is CaseState.DERIVED
    assert vista.resolution is None
    assert vista.derivation_reason == DerivationReason.RULE.value
    turnos = await casos.transcript_of(CON_CIERRE_DIRECTO, caso)
    ultimo_de_la_persona = [t for t in turnos if t.speaker is Speaker.INSURED][-1]
    assert vista.derived_turn_id == ultimo_de_la_persona.turn_id
    derivacion = _frase("compliance.handoff.adjuster_review")
    assert avisos.dichos == [derivacion]
    assert (await _frases_de_la_agente(caso))[-1] == derivacion
    # Y las reglas y la revision estan para que el ajustador las vea al abrirlo.
    assert await _contar(CON_CIERRE_DIRECTO, CONTAR_EVALUACIONES, caso) == 1
    assert await _contar(CON_CIERRE_DIRECTO, CONTAR_REVISIONES, caso) == 1


async def test_una_aseguradora_que_no_cierra_directo_deriva_aunque_todo_este_limpio(
    app: FastAPI,
) -> None:
    del app
    caso = await _reporte_listo("case-sin-regla-de-cierre", tenant_id="stonecroft")

    await _cerrar_el_reporte(caso, tenant_id="stonecroft")

    assert (await _caso(caso, "stonecroft")).state is CaseState.DERIVED


async def test_sin_la_divulgacion_registrada_cumplimiento_rechaza_y_el_caso_se_deriva(
    app: FastAPI,
) -> None:
    """Los cuatro controles tienen que pasar: la categoria sola no basta para cerrar."""
    del app
    caso = await _reporte_listo("case-sin-divulgacion", divulgado=False)

    avisos = await _cerrar_el_reporte(caso)

    assert (await _caso(caso)).state is CaseState.DERIVED
    assert avisos.dichos == [_frase("compliance.handoff.adjuster_review")]


# A prueba de fallos -----------------------------------------------------------------------


class _RevisionCaida:
    """Una revision de cumplimiento que revienta con un defecto que el ejecutor no atrapa."""

    def __init__(self, real: object) -> None:
        self.spec = real.spec  # type: ignore[attr-defined]

    async def run(self, state: object) -> object:
        del state
        msg = "la revision no pudo leer la transcripcion"
        raise RuntimeError(msg)


def _sin_revision(runtime: orchestration_turn.GraphRuntime) -> orchestration_turn.GraphRuntime:
    paso = runtime.background[NodeName.COMPLIANCE]
    return dataclasses.replace(
        runtime,
        background={
            **runtime.background,
            NodeName.COMPLIANCE: orchestration_turn.BackgroundStep(
                node=_RevisionCaida(paso.node), build_input=paso.build_input
            ),
        },
    )


async def test_si_la_cadena_falla_el_caso_queda_con_un_ajustador_y_el_error_sale(
    app: FastAPI,
) -> None:
    """Regla 2: un reporte terminado nunca se queda en `deciding`, y el defecto no se traga."""
    del app
    caso = await _reporte_listo("case-cadena-caida")
    avisos = _Avisos()
    runtime = dataclasses.replace(_sin_revision(orchestration_turn.get_runtime()), notifier=avisos)

    with _eventos() as recogidos, pytest.raises(RuntimeError, match="transcripcion"):
        await orchestration_turn._cerrar_en_el_fondo(runtime, CON_CIERRE_DIRECTO, caso)

    assert (await _caso(caso)).state is CaseState.DERIVED
    assert avisos.dichos == [_frase("compliance.handoff.adjuster_review")]
    # La traza dice en que nodo paso y de que tipo fue el error, sin lo que dijo la persona.
    linea = next(
        linea for linea in recogidos.getvalue().splitlines() if "background_node_crashed" in linea
    )
    assert NodeName.COMPLIANCE.value in linea
    assert "RuntimeError" in linea
    assert "orchestration.closing_failed" in recogidos.getvalue()


async def test_si_el_cierre_del_caso_levanta_el_caso_queda_con_un_ajustador(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El desenlace tambien falla: aqui `close_case` levanta algo que U4 no espera."""
    del app
    caso = await _reporte_listo("case-cierre-caido")

    async def _revienta(*_args: object, **_kwargs: object) -> object:
        msg = "la base se cayo al cerrar"
        raise RuntimeError(msg)

    monkeypatch.setattr(casos, "close_case", _revienta)

    with pytest.raises(RuntimeError, match="al cerrar"):
        await _cerrar_el_reporte(caso)

    assert (await _caso(caso)).state is CaseState.DERIVED


async def test_un_cierre_que_u4_rechaza_se_deriva_en_vez_de_quedarse_a_medias(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un adjunto sin evaluar hace que U4 rechace el cierre: el caso sigue vivo y se deriva."""
    del app
    caso = await _reporte_listo("case-cierre-rechazado")

    async def _rechaza(*_args: object, **_kwargs: object) -> object:
        msg = "no se puede cerrar: ['trace_id'] sin evaluar"
        raise casos.ClosingRejectedError(msg)

    monkeypatch.setattr(casos, "close_case", _rechaza)

    with _eventos() as recogidos:
        avisos = await _cerrar_el_reporte(caso)

    assert (await _caso(caso)).state is CaseState.DERIVED
    assert avisos.dichos == [_frase("compliance.handoff.adjuster_review")]
    assert "orchestration.direct_closure_rejected" in recogidos.getvalue()


async def test_sin_ningun_turno_de_la_persona_el_reporte_igual_se_deriva(app: FastAPI) -> None:
    del app
    caso = await _reporte_listo("case-sin-turnos")
    async with session.session_for(CON_CIERRE_DIRECTO) as sesion:
        await session.execute_sql(
            sesion, "DELETE FROM case_transcript_turn WHERE case_id = :case_id", case_id=caso
        )

    with _eventos() as recogidos:
        await _cerrar_el_reporte(caso)

    assert (await _caso(caso)).state is CaseState.DERIVED
    assert "orchestration.closing_without_person_turn" in recogidos.getvalue()


# La oferta de datos opcionales ------------------------------------------------------------


async def test_con_la_oferta_abierta_no_se_cierra_ni_se_deriva_y_al_contestarla_si(
    app: FastAPI,
) -> None:
    """Regla 3: mientras la persona decide si agrega algo, el caso espera en `deciding`; el turno
    que cierra la oferta lo resuelve con las mismas reglas."""
    del app
    caso = await _reporte_listo("case-oferta")
    await _oferta_abierta(caso, abierta=True)

    avisos = await _cerrar_el_reporte(caso)

    assert (await _caso(caso)).state is CaseState.DECIDING
    assert avisos.dichos == [], "no se anuncia nada con la oferta abierta"
    # Las reglas y la revision si corrieron: el ajustador las tiene aunque la persona no conteste.
    assert await _contar(CON_CIERRE_DIRECTO, CONTAR_EVALUACIONES, caso) == 1
    assert await _contar(CON_CIERRE_DIRECTO, CONTAR_REVISIONES, caso) == 1

    # La persona contesta «no, asi esta bien»: la oferta se cierra y el turno vuelve a lanzar la
    # decision. Las reglas ven los mismos insumos y la misma revision acota al mismo turno: el
    # ejecutor las da por terminadas, y el cierre recupera su salida en vez de quedarse sin ella.
    await _oferta_abierta(caso, abierta=False)
    with _eventos() as recogidos:
        avisos = await _cerrar_el_reporte(caso)

    vista = await _caso(caso)
    assert vista.state is CaseState.CLOSED
    assert vista.resolution is Resolution.REGISTERED
    assert avisos.dichos == [_frase("compliance.closure.direct")]
    assert recogidos.getvalue().count("orchestration.background_step_replayed") == 2
    assert await _contar(CON_CIERRE_DIRECTO, CONTAR_EVALUACIONES, caso) == 1, "no duplica filas"
    assert await _contar(CON_CIERRE_DIRECTO, CONTAR_REVISIONES, caso) == 1, "no duplica filas"


async def test_si_ni_recuperar_la_corrida_guardada_es_posible_el_caso_se_deriva(
    app: FastAPI,
) -> None:
    """La recuperacion tambien tiene plazo: si el nodo no responde, no se cierra por suponer."""
    del app
    otro = await _reporte_listo("case-sin-recuperar")
    await _oferta_abierta(otro, abierta=True)
    await _cerrar_el_reporte(otro)
    await _oferta_abierta(otro, abierta=False)
    runtime = orchestration_turn.get_runtime()
    decision = runtime.background[NodeName.DECISION]

    class _DecisionMuda:
        spec = decision.node.spec

        async def run(self, state: object) -> object:
            del state
            raise TimeoutError

    runtime = dataclasses.replace(
        runtime,
        background={
            **runtime.background,
            NodeName.DECISION: orchestration_turn.BackgroundStep(
                node=_DecisionMuda(), build_input=decision.build_input
            ),
        },
    )
    avisos = _Avisos()
    runtime = dataclasses.replace(runtime, notifier=avisos)

    await orchestration_turn._cerrar_en_el_fondo(runtime, CON_CIERRE_DIRECTO, otro)

    assert (await _caso(otro)).state is CaseState.DERIVED
    assert avisos.dichos == [_frase("compliance.handoff.adjuster_review")]


# Decisiones viejas y pedidos a la vez -----------------------------------------------------


async def test_una_decision_vieja_de_mitad_de_conversacion_no_decide_el_cierre(
    app: FastAPI,
) -> None:
    """Regla 4. La cadena pudo correr tras una pregunta de cobertura con datos incompletos y
    dejo su categoria en el punto de control: `transition()` la daria por terminada. El cierre
    tiene que decidir con los datos finales."""
    del app
    caso = await _reporte_listo("case-decision-vieja", heridos="No sé.")
    runtime = orchestration_turn.get_runtime()
    await _correr_la_cadena(runtime, CON_CIERRE_DIRECTO, caso)
    guardado = await orchestration_turn._current_state(runtime, CON_CIERRE_DIRECTO, caso)
    assert guardado.written("category") == "standard_review", "la decision de mitad de camino"
    assert guardado.written("closable") is False
    # Despues la persona aclara que nadie se lastimo.
    await _anotar_heridos(CON_CIERRE_DIRECTO, caso, "No, nadie se lastimó.")

    avisos = await _cerrar_el_reporte(caso)

    assert (await _caso(caso)).state is CaseState.CLOSED
    assert avisos.dichos == [_frase("compliance.closure.direct")]
    final = await orchestration_turn._current_state(runtime, CON_CIERRE_DIRECTO, caso)
    assert final.written("category") == "direct_close"
    assert final.written("closable") is True


async def test_el_cierre_no_deja_una_categoria_vieja_en_el_punto_de_control(app: FastAPI) -> None:
    """Aunque la cadena no llegue a terminar, lo que queda escrito no es una decision que se
    descarto."""
    del app
    caso = await _reporte_listo("case-punto-limpio", heridos="No sé.")
    runtime = orchestration_turn.get_runtime()
    await _correr_la_cadena(runtime, CON_CIERRE_DIRECTO, caso)

    estado = await orchestration_turn._estado_para_decidir(runtime, CON_CIERRE_DIRECTO, caso)

    for escritura in ("category", "closable", "fired_rules", "closure", "compliance_review"):
        assert estado.written(escritura) is None, escritura
    assert estado.written("intake_capture_closed") is True
    guardado = await orchestration_turn._current_state(runtime, CON_CIERRE_DIRECTO, caso)
    assert guardado.written("category") is None


class _DecisionConPuerta:
    """El nodo `decision` real, que en su primera llamada espera a que la prueba lo suelte."""

    def __init__(self, real: object) -> None:
        self._real = real
        self.spec = real.spec  # type: ignore[attr-defined]
        self.llamadas = 0
        self.entro = asyncio.Event()
        self.puerta = asyncio.Event()

    async def run(self, state: object) -> object:
        self.llamadas += 1
        if self.llamadas == 1:
            self.entro.set()
            await self.puerta.wait()
        return await self._real.run(state)  # type: ignore[attr-defined]


async def test_dos_pedidos_a_la_vez_dan_un_solo_desenlace_con_los_datos_de_ahora(
    app: FastAPI,
) -> None:
    """Un pedido que llega mientras el cierre corre no lanza una segunda cadena en paralelo: hace
    que la que corre vuelva a empezar, y solo la ultima vuelta aplica el desenlace."""
    del app
    caso = await _reporte_listo("case-dos-pedidos")
    base = orchestration_turn.get_runtime()
    lenta = _DecisionConPuerta(base.background[NodeName.DECISION].node)
    avisos = _Avisos()
    runtime = dataclasses.replace(
        base,
        notifier=avisos,
        background={
            **base.background,
            NodeName.DECISION: orchestration_turn.BackgroundStep(
                node=lenta, build_input=base.background[NodeName.DECISION].build_input
            ),
        },
    )

    primera = asyncio.create_task(
        orchestration_turn._cerrar_en_el_fondo(runtime, CON_CIERRE_DIRECTO, caso)
    )
    await lenta.entro.wait()
    await orchestration_turn._cerrar_en_el_fondo(runtime, CON_CIERRE_DIRECTO, caso)
    lenta.puerta.set()
    await primera

    assert (await _caso(caso)).state is CaseState.CLOSED
    assert avisos.dichos == [_frase("compliance.closure.direct")], "se anuncia una sola vez"
    assert lenta.llamadas == 2, "la primera vuelta y la que pidio el segundo pedido"


# La voz -----------------------------------------------------------------------------------


async def test_en_una_llamada_el_resultado_se_guarda_pero_no_se_publica_dos_veces(
    app: FastAPI,
) -> None:
    """La despedida de la llamada es la que dice el resultado. El aviso de fondo, que en una
    llamada viva se diria encima, solo guarda la frase en la transcripcion."""
    del app
    caso = await _reporte_listo("case-por-voz")

    avisos = await _cerrar_el_reporte(caso, spoken=True)

    assert (await _caso(caso)).state is CaseState.CLOSED
    assert avisos.dichos == [], "ni al chat ni al oyente de la llamada"
    assert (await _frases_de_la_agente(caso))[-1] == _frase("voice.closing.registered")
    cambios = await history.of_case(CON_CIERRE_DIRECTO, caso)
    cierre = next(c for c in cambios if c.detail is not None and c.detail.startswith("T6"))
    assert cierre.channel is Channel.VOICE


async def test_en_una_llamada_un_reporte_derivado_guarda_la_frase_de_la_despedida(
    app: FastAPI,
) -> None:
    del app
    caso = await _reporte_listo("case-por-voz-derivado", terceros="Un taxi")

    avisos = await _cerrar_el_reporte(caso, spoken=True)

    assert (await _caso(caso)).state is CaseState.DERIVED
    assert avisos.dichos == []
    assert (await _frases_de_la_agente(caso))[-1] == _frase("voice.closing.next_step")


async def test_la_red_de_seguridad_de_la_voz_da_la_oferta_por_rechazada_y_resuelve(
    app: FastAPI,
) -> None:
    """Una llamada que termina con la oferta sin contestar no deja el caso en revision."""
    del app
    caso = await _reporte_listo("case-llamada-terminada")
    await _oferta_abierta(caso, abierta=True)
    lanzadas: list[asyncio.Task[None]] = []

    def _fabrica(coro: object) -> asyncio.Task[None]:
        tarea: asyncio.Task[None] = asyncio.create_task(
            coro,  # type: ignore[arg-type]
            context=contextvars.Context(),
        )
        lanzadas.append(tarea)
        return tarea

    orchestration_turn.install_runtime(
        dataclasses.replace(orchestration_turn.get_runtime(), task_factory=_fabrica)
    )

    await orchestration_turn.settle_review(caso, tenant_id=CON_CIERRE_DIRECTO)
    await asyncio.gather(*lanzadas)

    vista = await _caso(caso)
    assert vista.state is CaseState.CLOSED
    assert vista.resolution is Resolution.REGISTERED
    guardado = await orchestration_turn._current_state(
        orchestration_turn.get_runtime(), CON_CIERRE_DIRECTO, caso
    )
    assert guardado.written("intake_awaiting_confirmation") is None


async def test_rechazar_la_oferta_mientras_corre_el_cierre_que_la_hizo_resuelve_igual(
    app: FastAPI,
) -> None:
    """La corrida completa del 2026-10-15: doce conversaciones terminaron con la oferta abierta
    y con el cierre que la hizo todavia corriendo. El rechazo llegaba a mitad; esa corrida
    escribia al terminar su estado de antes, con la oferta abierta, encima del rechazo, y la
    vuelta siguiente la volvia a ver abierta y no hacia nada: el caso se quedaba en revision.
    Es lo que le pasa a una llamada que se cuelga justo tras la oferta."""
    del app
    caso = await _reporte_listo("case-rechazo-a-mitad")
    await _oferta_abierta(caso, abierta=True)
    base = orchestration_turn.get_runtime()
    lenta = _DecisionConPuerta(base.background[NodeName.DECISION].node)
    lanzadas: list[asyncio.Task[None]] = []

    def _fabrica(coro: object) -> asyncio.Task[None]:
        tarea: asyncio.Task[None] = asyncio.create_task(
            coro,  # type: ignore[arg-type]
            context=contextvars.Context(),
        )
        lanzadas.append(tarea)
        return tarea

    orchestration_turn.install_runtime(
        dataclasses.replace(
            base,
            task_factory=_fabrica,
            background={
                **base.background,
                NodeName.DECISION: orchestration_turn.BackgroundStep(
                    node=lenta, build_input=base.background[NodeName.DECISION].build_input
                ),
            },
        )
    )
    runtime = orchestration_turn.get_runtime()

    # El cierre que empezo con la oferta abierta, detenido a mitad de la cadena.
    primera = asyncio.create_task(
        orchestration_turn._cerrar_en_el_fondo(runtime, CON_CIERRE_DIRECTO, caso)
    )
    await lenta.entro.wait()
    # La persona se va sin contestar: la oferta se da por rechazada mientras corre.
    await orchestration_turn.settle_review(caso, tenant_id=CON_CIERRE_DIRECTO)
    lenta.puerta.set()
    await primera
    await asyncio.gather(*lanzadas)

    vista = await _caso(caso)
    assert vista.state is CaseState.CLOSED, "el caso se quedo en revision con la oferta rechazada"
    assert vista.resolution is Resolution.REGISTERED
    assert lenta.llamadas == 2, "la vuelta que pidio el rechazo corrio de nuevo la cadena"


async def _sin_espera() -> None:
    """La espera del chat a la respuesta de la oferta, ya cumplida."""


async def test_en_el_chat_una_oferta_que_nadie_contesta_se_da_por_rechazada_y_resuelve(
    app: FastAPI,
) -> None:
    """Quien cierra la pestana con la oferta abierta no deja su caso en revision."""
    del app
    caso = await _reporte_listo("case-chat-abandonado")
    await _oferta_abierta(caso, abierta=True)
    avisos = _Avisos()
    lanzadas: list[asyncio.Task[None]] = []

    def _fabrica(coro: object) -> asyncio.Task[None]:
        tarea: asyncio.Task[None] = asyncio.create_task(
            coro,  # type: ignore[arg-type]
            context=contextvars.Context(),
        )
        lanzadas.append(tarea)
        return tarea

    runtime = dataclasses.replace(
        orchestration_turn.get_runtime(),
        notifier=avisos,
        task_factory=_fabrica,
        offer_wait=_sin_espera,
    )

    await orchestration_turn._resolver_si_nadie_contesta(
        runtime, CON_CIERRE_DIRECTO, caso, turn_id="turno-de-la-captura"
    )
    await asyncio.gather(*lanzadas)

    vista = await _caso(caso)
    assert vista.state is CaseState.CLOSED
    assert vista.resolution is Resolution.REGISTERED
    # Por el chat, y por eso se publica: en una llamada solo se guardaria.
    assert avisos.dichos == [_frase("compliance.closure.direct")]


@pytest.mark.parametrize(
    ("turno_del_punto_de_control", "abierta"),
    [("un-turno-posterior", True), ("turno-de-la-captura", False)],
    ids=["llego-otro-turno", "ya-contesto"],
)
async def test_la_espera_del_chat_no_resuelve_si_la_persona_siguio_la_conversacion(
    app: FastAPI, turno_del_punto_de_control: str, abierta: bool
) -> None:
    """Otro turno, o la oferta ya contestada: de eso se encarga ese turno, no la espera."""
    del app
    caso = await _reporte_listo("case-chat-activo")
    await orchestration_turn._write_checkpoint(
        orchestration_turn.get_runtime(),
        GraphState(
            tenant_id=CON_CIERRE_DIRECTO,
            case_id=caso,
            turn_id=turno_del_punto_de_control,
            turn_text="",
            node_writes={
                "intake_awaiting_confirmation": Block.FINAL_CONFIRMATION if abierta else None,
                "intake_capture_closed": False,
            },
        ),
    )
    lanzadas: list[object] = []

    def _fabrica(coro: object) -> object:
        lanzadas.append(coro)
        close = getattr(coro, "close", None)
        if close is not None:
            close()
        return None

    runtime = dataclasses.replace(
        orchestration_turn.get_runtime(),
        task_factory=_fabrica,  # type: ignore[arg-type]
        offer_wait=_sin_espera,
    )

    await orchestration_turn._resolver_si_nadie_contesta(
        runtime, CON_CIERRE_DIRECTO, caso, turn_id="turno-de-la-captura"
    )

    assert lanzadas == []
    assert (await _caso(caso)).state is CaseState.DECIDING


async def test_un_desenlace_que_ya_no_puede_derivar_no_anuncia_nada(app: FastAPI) -> None:
    """Si un ajustador tomo el caso mientras corria la cadena, la agente no dice que lo derivo."""
    del app
    from untangle.case_record.models import Actor, ActorType, DerivationReason
    from untangle.case_record.rules import TransitionContext

    caso = await _reporte_listo("case-tomado")
    contexto = await _contexto(CON_CIERRE_DIRECTO, caso)
    estado = await orchestration_turn._current_state(
        orchestration_turn.get_runtime(), CON_CIERRE_DIRECTO, caso
    )
    # El ajustador lo toma justo despues de que el desenlace leyo el caso en revision.
    leer = casos.get_case
    tomado = False

    async def leer_y_ceder(tenant_id: str, case_id: str) -> casos.CaseView | None:
        nonlocal tomado
        vista = await leer(tenant_id, case_id)
        if not tomado:
            tomado = True
            await casos.apply_transition(
                tenant_id,
                case_id,
                CaseState.DERIVED,
                context=TransitionContext(
                    now=AHORA,
                    actor=Actor(actor_type=ActorType.STAFF, actor_id="ajustador-1"),
                    channel=Channel.CHAT,
                    derivation_reason=DerivationReason.RULE,
                ),
            )
        return vista

    avisos = _Avisos()
    with pytest.MonkeyPatch.context() as parche:
        parche.setattr(casos, "get_case", leer_y_ceder)
        hecho = await closing_outcome.conclude(
            tenant_id=CON_CIERRE_DIRECTO,
            case_id=caso,
            context=contexto,
            state=estado,
            offer_open=False,
            turn_id="turno-1",
            trace_ref=None,
            delivery=closing_outcome.Delivery(notifier=avisos, clock=lambda: AHORA),
        )

    assert hecho.step is closing_plan.Step.NOTHING
    assert hecho.reason == "case_moved_meanwhile"
    assert avisos.dichos == []


async def test_la_red_de_seguridad_no_toca_un_caso_que_ya_no_esta_en_revision(
    app: FastAPI,
) -> None:
    del app
    caso = await _caso_con_transcripcion(CON_CIERRE_DIRECTO, "case-ya-resuelto")
    await _derivar(CON_CIERRE_DIRECTO, caso)
    lanzadas: list[object] = []

    def _fabrica(coro: object) -> object:
        lanzadas.append(coro)
        close = getattr(coro, "close", None)
        if close is not None:
            close()
        return None

    orchestration_turn.install_runtime(
        dataclasses.replace(
            orchestration_turn.get_runtime(),
            task_factory=_fabrica,  # type: ignore[arg-type]
        )
    )

    await orchestration_turn.settle_review(caso, tenant_id=CON_CIERRE_DIRECTO)

    assert lanzadas == []
    assert (await _caso(caso)).state is CaseState.DERIVED


# Un turno sobre un caso que las reglas ya cerraron ---------------------------------------


async def test_un_turno_que_llega_con_el_caso_ya_cerrado_no_escribe_ni_rompe(
    app: FastAPI,
) -> None:
    """El caso se cerro mientras el turno corria: sus campos ya no cambian (BR6.4 de U4), pero
    el turno no se cae por eso."""
    del app
    caso = await _reporte_listo("case-turno-tardio")
    await _cerrar_el_reporte(caso)
    assert (await _caso(caso)).state is CaseState.CLOSED
    runtime = orchestration_turn.get_runtime()
    contexto = await case_context.read_case_context(CON_CIERRE_DIRECTO, caso)
    salida = IntakeNodeOutput(
        intake_next_block=Block.DONE,
        intake_extracted=(
            ExtractedField(
                field_key="vehicle_and_driver",
                value="mi Mazda",
                normalized=None,
                evidence_turn_id=f"{caso}-turno-0",
                evidence_verbatim_redacted="mi Mazda",
            ),
        ),
        intake_awaiting_confirmation=None,
        intake_readback_resolved=None,
        intake_response_key="intake.closing.fast_claim_registered",
        intake_response_text="ya quedó registrado",
        intake_session_ended=None,
    )
    entrante = InboundTurn(
        tenant_id=CON_CIERRE_DIRECTO,
        session_ref="sesion",
        case_id=caso,
        text="mi Mazda",
        language="es",
        channel="chat",
        received_at=AHORA,
    )

    with _eventos() as recogidos:
        await orchestration_turn._guardar_la_captura(
            runtime,
            entrante,
            contexto,
            GraphState(tenant_id=CON_CIERRE_DIRECTO, case_id=caso, turn_id="", turn_text=""),
            salida,
            turn_id="turno-x",
            now=AHORA,
        )

    assert "orchestration.capture_on_closed_case" in recogidos.getvalue()
    valores = await casos.open_field_values(
        CON_CIERRE_DIRECTO, caso, ("vehicle_and_driver",), cipher=runtime.cipher
    )
    assert valores == {}, "un caso cerrado no recibe campos"


# --- El conductor del caso llega al motor (2026-10-13) ----------------------------------------
#
# El sexto insumo, `unlisted_driver`, se deriva de lo que la persona dijo del conductor y de los
# conductores que declara la poliza **del caso**: la poliza se lee de la base por el numero que
# el caso tiene atado. Estas pruebas cubren la costura que las unitarias no pueden: la columna
# `drivers` de verdad, su ingesta y el motor real de Sunmeadow.

#: La regla de Sunmeadow que lee `unlisted_driver`, y la poliza que `_caso_con_transcripcion` ata.
REGLA_DE_CONDUCTOR = "SUN-R-08"
POLIZA_DEL_CASO = "POL-11"
TITULAR = "Natalia Henao Rendón"
ADICIONAL = "Mateo Henao Gómez"


async def _declarar_conductores(tenant_id: str, *conductores: str) -> None:
    """La poliza del caso, con los conductores que declara, por el mismo camino que la ingesta."""
    formulario = PolicyForm(
        tenant_id=tenant_id,
        form_id="form-del-conductor",
        form_version="2026.1",
        form_kind=FormKind.BASE,
        language="es",
        issuer_label=f"{tenant_id} Mutual",
        issuer_tenant=tenant_id,
    )
    poliza = IssuedPolicy(
        tenant_id=tenant_id,
        policy_number=POLIZA_DEL_CASO,
        issuer_tenant=tenant_id,
        form_id=formulario.form_id,
        form_version=formulario.form_version,
        named_insured={"full_name": TITULAR},
        drivers=tuple(DeclaredDriver(full_name=n) for n in conductores),
        period_start=date(2026, 1, 1),
        period_end=date(2027, 1, 1),
    )
    await upsert_reference_data(
        tenant_id, forms=(formulario,), clauses=(), relations=(), policies=(poliza,)
    )


async def _anotar_conductor(tenant_id: str, case_id: str, texto: str) -> None:
    """El campo `vehicle_and_driver`, sellado con el cifrador del runtime."""
    cifrador = orchestration_turn.get_runtime().cipher
    await casos.set_field(
        tenant_id,
        CaseField(
            case_id=case_id,
            field_key="vehicle_and_driver",
            value=cifrador.seal(texto),
            status=FieldStatus.STATED,
            evidence_turn_id=f"{case_id}-turno-0",
            updated_at=AHORA,
        ),
        cipher=cifrador,
        actor=Actor(actor_type=ActorType.INSURED),
        channel=Channel.CHAT,
    )


async def _decidir_con_conductor(
    case_id: str, conductor: str, cifrador: crypto.Cipher
) -> GraphState:
    """Un reporte de Sunmeadow sin heridos ni terceros --que cerraria directo-- y con lo que dijo
    la persona del conductor."""
    del cifrador
    await _caso_con_transcripcion(CON_CIERRE_DIRECTO, case_id)
    await _bloque_de_terceros_dicho(CON_CIERRE_DIRECTO, case_id, "ninguno")
    await _anotar_heridos(CON_CIERRE_DIRECTO, case_id, "No, nadie se lastimó.")
    await _anotar_conductor(CON_CIERRE_DIRECTO, case_id, conductor)
    return await _correr_la_cadena(orchestration_turn.get_runtime(), CON_CIERRE_DIRECTO, case_id)


async def test_un_conductor_que_la_poliza_no_declara_dispara_su_regla_y_no_cierra_directo(
    app: FastAPI, cifrador: crypto.Cipher
) -> None:
    """La costura entera: campo sellado, poliza en la base, derivacion y motor real.

    El mismo reporte sin lo del conductor cierra directo (otras pruebas de este archivo), asi que
    lo unico que puede llevarlo a `referral` es que `unlisted_driver` llegue al motor en verdadero.
    """
    del app
    await _declarar_conductores(CON_CIERRE_DIRECTO, TITULAR, ADICIONAL)

    final = await _decidir_con_conductor(
        "case-conductor-ajeno",
        "Renault Logan 2024. Lo manejaba mi hijo Carlos Ruiz Mora.",
        cifrador,
    )

    assert REGLA_DE_CONDUCTOR in _disparadas(final)
    assert final.written("category") == "referral"
    assert final.written("closable") is False


@pytest.mark.parametrize(
    ("sufijo", "dicho"),
    [
        pytest.param("titular", "Renault Logan 2024, conducía el titular", id="el-titular"),
        pytest.param("adicional", "Lo manejaba Mateo Henao Gómez", id="un-declarado"),
        pytest.param("sin-nombre", "Manejaba su hijo", id="un-hijo-sin-nombre"),
        pytest.param("duda", "Creo que lo manejaba Carlos Ruiz Mora", id="con-una-duda"),
        pytest.param("de-pila", "Lo manejaba Carlos", id="solo-un-nombre-de-pila"),
    ],
)
async def test_el_conductor_que_figura_o_que_no_se_sabe_no_dispara_la_regla(
    app: FastAPI, cifrador: crypto.Cipher, sufijo: str, dicho: str
) -> None:
    """El control contrario: ni el titular, ni un declarado, ni lo dudoso mandan a un ajustador
    por conductor. Sin esto, una derivacion que devolviera siempre cierto pasaria la de arriba."""
    del app
    await _declarar_conductores(CON_CIERRE_DIRECTO, TITULAR, ADICIONAL)

    final = await _decidir_con_conductor(f"case-conductor-{sufijo}", dicho, cifrador)

    assert REGLA_DE_CONDUCTOR not in _disparadas(final)
    assert final.written("category") == "direct_close"


async def test_si_la_poliza_no_declara_conductores_el_insumo_queda_ausente_y_se_dice_por_que(
    app: FastAPI, cifrador: crypto.Cipher
) -> None:
    """Lo que trae una base cuyas polizas se ingirieron antes de la columna `drivers`.

    Con la lista vacia todo conductor parecia ajeno: el resultado tiene que ser ausente, y la
    traza lo nombra sin llevar lo que dijo la persona.
    """
    del app
    await _declarar_conductores(CON_CIERRE_DIRECTO)

    with _eventos() as recogidos:
        final = await _decidir_con_conductor(
            "case-poliza-sin-conductores",
            "Lo manejaba mi hijo Carlos Ruiz Mora",
            cifrador,
        )

    traza = recogidos.getvalue()
    assert REGLA_DE_CONDUCTOR not in _disparadas(final)
    assert "driver_not_derivable" in traza
    assert '"policy_declares_drivers": false' in traza
    assert "Carlos" not in traza
    assert "Ruiz" not in traza
