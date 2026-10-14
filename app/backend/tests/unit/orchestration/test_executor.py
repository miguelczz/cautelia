"""El ejecutor comun (paso 4 de U12): la politica de fallo como dato (BR5.1 a BR5.4).

Todos los fallos de este archivo se inyectan con dobles deterministas
(CG-U12-3): ningun proveedor real se llama. `InMemoryNodeRunStore` sustituye a
`node_run_repository.DatabaseNodeRunStore` -- lo que este archivo prueba es la
politica del ejecutor, no el motor de base de datos; ese lado vive en
`tests/integration/u12/test_node_run_repository.py`.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest

from untangle.base import Frozen, ProviderErrorKind, ProviderName, Use
from untangle.orchestration import executor as executor_module
from untangle.orchestration.executor import NodeExecutionResult, NodeExecutor
from untangle.orchestration.node_run import NodeRunOutcome, NodeRunRecord, idempotency_key
from untangle.orchestration.state import NodeSpec
from untangle.providers.ports import ProviderError
from untangle.telemetry.traces import api as traces
from untangle.telemetry.traces.models import NodeName

# --- Dobles --------------------------------------------------------------------


class FakeInput(Frozen):
    """Una entrada de nodo fabricada: lo unico que le importa a la clave de BR5.4."""

    question: str


class FakeOutput(Frozen):
    """Una salida de nodo fabricada."""

    answer: str


class FakeNode:
    """Un `Node` (C-15) cuyo `.run` hace exactamente lo que la prueba le pida.

    `behaviors` es una cola: un elemento por llamada. Un `Exception` en la cola
    se levanta (como dejaria subir un nodo real); `"timeout"` duerme mas de lo
    que el `NodeSpec` tolera; un `float` duerme esos segundos y **si** devuelve
    --un nodo lento que termina, que es distinto de uno que no termina nunca--;
    cualquier otra cosa se devuelve como salida.
    """

    def __init__(self, spec: NodeSpec, behaviors: list[object]) -> None:
        self.spec = spec
        self._behaviors = list(behaviors)
        self.calls: list[FakeInput] = []

    async def run(self, state: FakeInput) -> FakeOutput:
        self.calls.append(state)
        comportamiento = self._behaviors.pop(0)
        if isinstance(comportamiento, Exception):
            raise comportamiento
        if comportamiento == "timeout":
            await asyncio.sleep(1)
            msg = "no deberia llegar aqui: el ejecutor tiene que cortar antes"
            raise AssertionError(msg)
        if isinstance(comportamiento, float):
            # Lento pero termina: con presupuesto suficiente devuelve, y sin el lo
            # corta el ejecutor. Es lo que hace un proveedor de verdad, y lo que
            # `"timeout"` no puede representar porque afirma que siempre lo cortan.
            await asyncio.sleep(comportamiento)
            return FakeOutput(answer="lento")
        assert isinstance(comportamiento, FakeOutput)
        return comportamiento


def _spec(  # noqa: PLR0913 -- las seis piezas de un `NodeSpec` de prueba, todas con su propio valor por omision
    *,
    name: NodeName = NodeName.DECISION,
    attempts: int = 2,
    timeout_ms: int = 200,
    retries_owned_by: Literal["executor", "node"] = "executor",
    degraded_copy_key: str = "compliance.handoff.adjuster_review",
    rhythm: Literal["turn", "background"] = "background",
) -> NodeSpec:
    return NodeSpec(
        name=name,
        reads=frozenset({"question"}),
        writes=frozenset({"answer"}),
        rhythm=rhythm,
        timeout_ms=timeout_ms,
        attempts=attempts,
        degraded_copy_key=degraded_copy_key,
        retries_owned_by=retries_owned_by,
    )


@dataclass
class InMemoryNodeRunStore:
    """El `NodeRunStore` de las pruebas: un diccionario por `(tenant_id, clave)`."""

    filas: dict[tuple[str, str], NodeRunRecord] = field(default_factory=dict)

    async def find(self, *, tenant_id: str, idempotency_key: str) -> NodeRunRecord | None:
        return self.filas.get((tenant_id, idempotency_key))

    async def find_stale_running(
        self, *, tenant_id: str, before: datetime
    ) -> tuple[NodeRunRecord, ...]:
        """Ninguna prueba de este archivo la llama: el barrido (BR5.5) es de `test_sweep.py`.

        Existe solo para que este doble siga cumpliendo `NodeRunStore` (paso 5
        le sumo el metodo al puerto); ver `test_sweep.py::InMemoryLeaseStore`
        para una implementacion de verdad.
        """
        return ()

    async def upsert(self, record: NodeRunRecord) -> None:
        self.filas[(record.tenant_id, record.idempotency_key)] = record


def _reloj(inicio: datetime, paso: timedelta = timedelta(milliseconds=1)) -> Callable[[], datetime]:
    """Un reloj que avanza un paso fijo en cada lectura -- nunca el de la maquina."""
    estado = {"ahora": inicio}

    def leer() -> datetime:
        actual = estado["ahora"]
        estado["ahora"] = actual + paso
        return actual

    return leer


_TENANT_ID = "acme"
_CASE_ID = "case-1"
_AHORA = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _trazas_limpias() -> Iterator[None]:
    """Cada prueba abre su propio turno: `node_span` exige uno abierto (BR6.1)."""
    traces.reset()
    yield
    traces.reset()


def _entrada(pregunta: str = "hola") -> FakeInput:
    return FakeInput(question=pregunta)


async def _correr(
    node: FakeNode,
    node_input: FakeInput,
    *,
    store: InMemoryNodeRunStore,
    clock: Callable[[], datetime],
    timeout_ms: int | None = None,
) -> NodeExecutionResult[FakeOutput]:
    ejecutor = NodeExecutor(store=store, clock=clock)
    with traces.turn_span(tenant_id=_TENANT_ID, case_id=_CASE_ID, use=Use.OPERATIONS):
        return await ejecutor.run(
            node, node_input, tenant_id=_TENANT_ID, case_id=_CASE_ID, timeout_ms=timeout_ms
        )


def _provider_error(kind: ProviderErrorKind, *, attempt: int = 1) -> ProviderError:
    return ProviderError(kind, provider=ProviderName.GEMINI, use=Use.OPERATIONS, attempt=attempt)


# --- El caso feliz ---------------------------------------------------------------


async def test_el_nodo_que_responde_a_la_primera_no_deja_ningun_error() -> None:
    salida = FakeOutput(answer="listo")
    nodo = FakeNode(_spec(), behaviors=[salida])
    store = InMemoryNodeRunStore()

    resultado = await _correr(nodo, _entrada(), store=store, clock=_reloj(_AHORA))

    assert resultado.outcome is NodeRunOutcome.SUCCEEDED
    assert resultado.output == salida
    assert resultado.attempts == 1
    assert resultado.error_kind is None
    fila = next(iter(store.filas.values()))
    assert fila.outcome is NodeRunOutcome.SUCCEEDED
    assert fila.error_type is None


# --- BR5.2 / BR5.3: un reintento, y despues degradacion sin perder el turno ------


async def test_un_reintento_y_no_mas_antes_de_degradar() -> None:
    """Dos fallos con `attempts=2`: dos llamadas, ninguna tercera."""
    nodo = FakeNode(
        _spec(attempts=2),
        behaviors=[
            _provider_error(ProviderErrorKind.UNAVAILABLE),
            _provider_error(ProviderErrorKind.UNAVAILABLE),
        ],
    )
    store = InMemoryNodeRunStore()

    resultado = await _correr(nodo, _entrada(), store=store, clock=_reloj(_AHORA))

    assert len(nodo.calls) == 2, "un reintento y no mas: dos llamadas en total"
    assert resultado.outcome is NodeRunOutcome.DEGRADED
    assert resultado.attempts == 2
    assert resultado.error_kind is ProviderErrorKind.UNAVAILABLE
    assert resultado.degraded_copy_key == "compliance.handoff.adjuster_review"


async def test_el_fallo_no_sube_ninguna_excepcion_el_turno_sigue_abierto() -> None:
    """BR5.3: el caso y el turno se conservan -- ninguna excepcion de politica sube."""
    nodo = FakeNode(_spec(attempts=1), behaviors=[_provider_error(ProviderErrorKind.TIMEOUT)])
    store = InMemoryNodeRunStore()

    # Si el ejecutor dejara subir el fallo, esta llamada lanzaria y la prueba
    # fallaria por una excepcion no capturada, no por una aserción.
    resultado = await _correr(nodo, _entrada(), store=store, clock=_reloj(_AHORA))

    assert resultado.outcome is NodeRunOutcome.DEGRADED


async def test_un_tiempo_agotado_se_registra_como_timeout_de_la_taxonomia_cerrada() -> None:
    nodo = FakeNode(_spec(attempts=1, timeout_ms=10), behaviors=["timeout"])
    store = InMemoryNodeRunStore()

    resultado = await _correr(nodo, _entrada(), store=store, clock=_reloj(_AHORA))

    assert resultado.outcome is NodeRunOutcome.DEGRADED
    assert resultado.error_kind is ProviderErrorKind.TIMEOUT


# --- BR5.1: la politica es dato, sin rama por nombre de nodo ---------------------


@pytest.mark.parametrize(
    "clave",
    ["compliance.handoff.adjuster_review", "policy_rag.coverage.unverifiable"],
)
async def test_la_clave_de_degradacion_es_la_que_declara_el_spec(clave: str) -> None:
    """Dos claves reales distintas, para que la asercion no pueda pasar por casualidad.

    Con una sola clave --la misma que `_spec` pone por omision-- un ejecutor que
    devolviera ese literal en duro pasaria igual, y la regla que se quiere
    comprobar es justo que la clave sale del `NodeSpec` (convencion 4 del
    equipo: la frase nunca se escribe en linea, y su clave la declara el nodo).
    """
    nodo = FakeNode(
        _spec(attempts=1, degraded_copy_key=clave),
        behaviors=[_provider_error(ProviderErrorKind.UNAVAILABLE)],
    )

    resultado = await _correr(nodo, _entrada(), store=InMemoryNodeRunStore(), clock=_reloj(_AHORA))

    assert resultado.outcome is NodeRunOutcome.DEGRADED
    assert resultado.degraded_copy_key == clave


def test_el_ejecutor_no_tiene_ninguna_rama_por_nombre_de_nodo() -> None:
    """BR5.1, literal: 'aparece un if por nombre de nodo en el ejecutor' es la violacion.

    Analiza el arbol sintactico -- no el texto -- para que la prosa del
    docstring del modulo (que si nombra `spec.name` al explicar la regla) no
    de un falso positivo: lo que cuenta es codigo que compare contra el nombre
    de un nodo, no que lo mencione.
    """
    arbol = ast.parse(inspect.getsource(executor_module))
    nombres_de_nodo = {n.value for n in NodeName}
    miembros_del_enum = {n.name for n in NodeName}
    for nodo_ast in ast.walk(arbol):
        if isinstance(nodo_ast, ast.Compare):
            # Se recorre **todo el subarbol** de la comparacion, no solo sus
            # operandos de primer nivel: un nombre de nodo cabe como literal
            # ("policy_verification"), como miembro del enum
            # (`NodeName.POLICY_VERIFICATION`) y tambien dentro de un conjunto
            # (`spec.name.value in {"policy_verification"}`). Una version
            # anterior de esta prueba solo miraba los operandos y dejaba pasar
            # esa tercera forma.
            piezas = list(ast.walk(nodo_ast))
            literales = {p.value for p in piezas if isinstance(p, ast.Constant)}
            atributos = {p.attr for p in piezas if isinstance(p, ast.Attribute)}
            if (literales & nombres_de_nodo) or (atributos & miembros_del_enum):
                msg = f"comparacion sospechosa contra un nombre de nodo: {ast.dump(nodo_ast)}"
                raise AssertionError(msg)


async def test_dos_specs_solo_distintas_en_sus_datos_producen_conductas_distintas() -> None:
    """La politica sale de `NodeSpec`, no de que nodo es cual (BR5.1)."""
    uno_reintento = _spec(name=NodeName.INTAKE, attempts=2)
    sin_reintento = _spec(name=NodeName.COMPLIANCE, attempts=1)

    nodo_a = FakeNode(
        uno_reintento,
        behaviors=[_provider_error(ProviderErrorKind.UNAVAILABLE), FakeOutput(answer="ok")],
    )
    nodo_b = FakeNode(sin_reintento, behaviors=[_provider_error(ProviderErrorKind.UNAVAILABLE)])

    resultado_a = await _correr(
        nodo_a, _entrada(), store=InMemoryNodeRunStore(), clock=_reloj(_AHORA)
    )
    resultado_b = await _correr(
        nodo_b, _entrada(), store=InMemoryNodeRunStore(), clock=_reloj(_AHORA)
    )

    assert resultado_a.outcome is NodeRunOutcome.SUCCEEDED, "attempts=2 le dio su reintento"
    assert len(nodo_a.calls) == 2
    assert resultado_b.outcome is NodeRunOutcome.DEGRADED, "attempts=1 no le dio ninguno"
    assert len(nodo_b.calls) == 1


# --- FD-U12-2: quien cuenta los reintentos es dato de C-15 -----------------------


async def test_el_nodo_que_cuenta_sus_propios_reintentos_no_se_reintenta_dos_veces() -> None:
    """`retries_owned_by='node'`: el ejecutor llama una sola vez pese a `attempts=2`."""
    nodo = FakeNode(
        _spec(name=NodeName.POLICY_VERIFICATION, attempts=2, retries_owned_by="node"),
        behaviors=[_provider_error(ProviderErrorKind.RATE_LIMITED)],
    )
    store = InMemoryNodeRunStore()

    resultado = await _correr(nodo, _entrada(), store=store, clock=_reloj(_AHORA))

    assert len(nodo.calls) == 1, "el ejecutor no le aplica un segundo bucle de reintento"
    assert resultado.outcome is NodeRunOutcome.DEGRADED
    assert resultado.attempts == 1


# --- BR5.4: la clave de idempotencia y el relanzamiento que no gasta dos veces ---


def test_la_clave_de_idempotencia_no_cambia_entre_corridas_del_mismo_trabajo() -> None:
    clave_1 = idempotency_key(
        tenant_id=_TENANT_ID, case_id=_CASE_ID, node=NodeName.DECISION, node_input=_entrada("misma")
    )
    clave_2 = idempotency_key(
        tenant_id=_TENANT_ID, case_id=_CASE_ID, node=NodeName.DECISION, node_input=_entrada("misma")
    )

    assert clave_1 == clave_2


def test_la_clave_de_idempotencia_cambia_si_cambia_el_caso_el_nodo_o_la_entrada() -> None:
    base = idempotency_key(
        tenant_id=_TENANT_ID, case_id=_CASE_ID, node=NodeName.DECISION, node_input=_entrada("x")
    )
    otro_caso = idempotency_key(
        tenant_id=_TENANT_ID, case_id="case-2", node=NodeName.DECISION, node_input=_entrada("x")
    )
    otro_nodo = idempotency_key(
        tenant_id=_TENANT_ID, case_id=_CASE_ID, node=NodeName.COMPLIANCE, node_input=_entrada("x")
    )
    otra_entrada = idempotency_key(
        tenant_id=_TENANT_ID, case_id=_CASE_ID, node=NodeName.DECISION, node_input=_entrada("y")
    )

    assert len({base, otro_caso, otro_nodo, otra_entrada}) == 4


def test_la_clave_no_depende_del_reloj() -> None:
    """BR5.4, literal: 'nunca del reloj ni de un aleatorio': la firma no recibe ninguno de los dos."""
    parametros = set(inspect.signature(idempotency_key).parameters)
    assert parametros == {"tenant_id", "case_id", "node", "node_input"}


async def test_un_relanzamiento_sobre_un_trabajo_ya_degradado_no_llama_al_nodo() -> None:
    """BR5.4: el segundo relanzamiento encuentra la fila terminal y no gasta de nuevo.

    `attempts=2` en la especificacion actual, con solo un intento gastado en la
    fila guardada, es a proposito: si el ejecutor no comprobara el desenlace
    terminal **antes** de decidir cuantos intentos le quedan, todavia le
    quedaria uno por la cuenta de intentos sola, y llamaria al nodo. La unica
    razon por la que no lo hace es el desenlace terminal.
    """
    spec = _spec(attempts=2, degraded_copy_key="compliance.handoff.adjuster_review")
    clave = idempotency_key(
        tenant_id=_TENANT_ID, case_id=_CASE_ID, node=spec.name, node_input=_entrada()
    )
    store = InMemoryNodeRunStore(
        filas={
            (_TENANT_ID, clave): NodeRunRecord(
                tenant_id=_TENANT_ID,
                case_id=_CASE_ID,
                node=spec.name,
                rhythm="background",
                attempt=1,
                max_attempts=2,
                outcome=NodeRunOutcome.DEGRADED,
                idempotency_key=clave,
                started_at=_AHORA,
                finished_at=_AHORA,
                error_type=ProviderErrorKind.UNAVAILABLE,
            )
        }
    )

    class _NodoQueNoDeberiaLlamarse(FakeNode):
        async def run(self, state: FakeInput) -> FakeOutput:
            msg = "BR5.4: un relanzamiento sobre 'degraded' no vuelve a llamar al proveedor"
            raise AssertionError(msg)

    nodo = _NodoQueNoDeberiaLlamarse(spec, behaviors=[])
    resultado = await _correr(nodo, _entrada(), store=store, clock=_reloj(_AHORA))

    assert resultado.outcome is NodeRunOutcome.DEGRADED
    assert resultado.error_kind is ProviderErrorKind.UNAVAILABLE
    assert resultado.degraded_copy_key == "compliance.handoff.adjuster_review"


async def test_un_relanzamiento_a_medias_retoma_el_conteo_en_vez_de_reiniciarlo() -> None:
    """Un intento ya gastado antes de que el proceso muriera no se regala de vuelta."""
    spec = _spec(attempts=2)
    clave = idempotency_key(
        tenant_id=_TENANT_ID, case_id=_CASE_ID, node=spec.name, node_input=_entrada()
    )
    store = InMemoryNodeRunStore(
        filas={
            (_TENANT_ID, clave): NodeRunRecord(
                tenant_id=_TENANT_ID,
                case_id=_CASE_ID,
                node=spec.name,
                rhythm="background",
                attempt=1,
                max_attempts=2,
                outcome=NodeRunOutcome.RUNNING,
                idempotency_key=clave,
                started_at=_AHORA,
                # Sin `error_type`: una fila `running` nunca lo lleva (la
                # restriccion `node_run_error_con_su_desenlace` de la
                # migracion solo lo exige, y lo permite, en `failed`/`degraded`).
            )
        }
    )
    nodo = FakeNode(spec, behaviors=[_provider_error(ProviderErrorKind.UNAVAILABLE)])

    resultado = await _correr(nodo, _entrada(), store=store, clock=_reloj(_AHORA))

    assert len(nodo.calls) == 1, "solo quedaba un intento disponible (2 en total, 1 ya gastado)"
    assert resultado.attempts == 2
    assert resultado.outcome is NodeRunOutcome.DEGRADED


# --- BR5.3: la traza registra el nodo, el tipo de error y el intento ------------


async def test_la_traza_registra_nodo_tipo_de_error_e_intento() -> None:
    recorder = traces.BufferedRecorder()
    traces.install_recorder(recorder)
    nodo = FakeNode(
        _spec(name=NodeName.COMPLIANCE, attempts=2),
        behaviors=[
            _provider_error(ProviderErrorKind.RATE_LIMITED),
            _provider_error(ProviderErrorKind.RATE_LIMITED),
        ],
    )

    await _correr(nodo, _entrada(), store=InMemoryNodeRunStore(), clock=_reloj(_AHORA))

    tramos_de_nodo = [t for t in recorder.drain() if t.name == NodeName.COMPLIANCE.value]
    assert len(tramos_de_nodo) == 1
    tramo = tramos_de_nodo[0]
    assert tramo.attributes["untangle.node"] == NodeName.COMPLIANCE.value
    assert tramo.attributes["untangle.error_kind"] == ProviderErrorKind.RATE_LIMITED.value
    assert tramo.attributes["untangle.attempt"] == 2


# --- Paso 5: el hallazgo -- en el ritmo del turno, el plazo es de la ejecucion
# completa, no de cada intento (PERF-U12.4) -------------------------------------


async def test_el_ritmo_del_turno_no_gasta_el_doble_del_plazo_declarado() -> None:
    """Un proveedor mas lento que el plazo, con dos intentos, no puede tardar el doble.

    `FakeNode` con el comportamiento `"timeout"` duerme un segundo real (muy por
    encima de cualquier plazo de esta prueba): lo unico que puede cortarlo es
    `asyncio.wait_for`. Con el ejecutor de antes de este paso, cada intento
    recibia el plazo entero y la ejecucion completa habria tardado cerca del
    doble del declarado.
    """
    # El plazo es de 300 ms y no de unas decenas a proposito. Lo que separa la
    # conducta correcta de la rota es la diferencia entre gastar el plazo una vez
    # y gastarlo dos, asi que un plazo pequeno deja esa diferencia del tamano del
    # ruido de la maquina: con 60 ms, la correcta media ~65 y la rota ~122, y el
    # umbral quedaba a 14 ms de la rota. Con 300 la correcta ronda los 305 y la
    # rota pasa de 600, asi que el umbral tiene margen por los dos lados y no
    # falla por una maquina cargada. Cuesta 300 ms de suite, que es lo que vale
    # una prueba cronometrada que no hay que volver a mirar.
    plazo_ms = 300
    nodo = FakeNode(
        _spec(attempts=2, timeout_ms=plazo_ms, rhythm="turn"),
        behaviors=["timeout", "timeout"],
    )
    store = InMemoryNodeRunStore()

    inicio = asyncio.get_running_loop().time()
    resultado = await _correr(nodo, _entrada(), store=store, clock=_reloj(_AHORA))
    transcurrido_ms = (asyncio.get_running_loop().time() - inicio) * 1000

    assert resultado.outcome is NodeRunOutcome.DEGRADED
    assert resultado.error_kind is ProviderErrorKind.TIMEOUT
    # El segundo intento no gasto nada de tiempo real: el presupuesto ya se
    # habia agotado en el primero, y `_deadline_s` lo corta antes de llamar al
    # nodo (`len(nodo.calls) == 1` lo confirma abajo).
    assert len(nodo.calls) == 1, "el segundo intento no llego a llamar al nodo: no quedaba plazo"
    assert transcurrido_ms < plazo_ms * 1.8, (
        f"la ejecucion completa tardo {transcurrido_ms:.0f} ms con un plazo "
        f"declarado de {plazo_ms} ms: el ritmo del turno no puede gastar el doble"
    )


async def test_un_plazo_por_llamada_sustituye_al_de_la_especificacion() -> None:
    """Un mismo nodo, dos canales, dos presupuestos (BR5.2).

    El plazo de `intake` sale de doblar la meta p95 de la **voz**, donde alguien
    espera al teléfono; el chat lo heredaba por compartir el `NodeSpec` y se
    degradaba en cada turno que el proveedor tardara más de 1,6 s -- que es casi
    siempre. Quien invoca el grafo sabe por qué canal entró el turno, y es quien
    pasa el presupuesto.

    Se comprueban **los dos lados**: con el argumento, el nodo lento termina; sin
    él, con el mismo nodo y el mismo `NodeSpec`, se degrada. Con un solo lado la
    prueba pasa igual contra un ejecutor que ignore el argumento.
    """

    # El mismo `NodeSpec` y el mismo nodo en los dos lados: un proveedor que tarda
    # 300 ms contra un plazo declarado de 60. Lo único que cambia es el argumento.
    def _lento() -> FakeNode:
        return FakeNode(_spec(attempts=1, timeout_ms=60, rhythm="turn"), behaviors=[0.3])

    # El control: sin argumento manda la especificación, y 300 ms no caben en 60.
    apretado = await _correr(
        _lento(), _entrada(), store=InMemoryNodeRunStore(), clock=_reloj(_AHORA)
    )
    assert apretado.outcome is NodeRunOutcome.DEGRADED
    assert apretado.error_kind is ProviderErrorKind.TIMEOUT

    # Y con el argumento, el mismo nodo termina.
    ancho = await _correr(
        _lento(), _entrada(), store=InMemoryNodeRunStore(), clock=_reloj(_AHORA), timeout_ms=5_000
    )
    assert ancho.outcome is NodeRunOutcome.SUCCEEDED


async def test_el_ritmo_de_fondo_no_cambia_cada_intento_sigue_con_su_plazo_completo() -> None:
    """Control positivo del anterior: en `background`, cada intento recibe el plazo entero.

    Con `rhythm="turn"` este mismo `NodeSpec` habria cortado el segundo intento
    sin llamarlo (prueba de arriba); en `background` los dos intentos llaman de
    verdad al nodo, porque nadie espera a un nodo de fondo (BR5.2).
    """
    nodo = FakeNode(
        _spec(attempts=2, timeout_ms=200, rhythm="background"),
        behaviors=[
            _provider_error(ProviderErrorKind.UNAVAILABLE),
            FakeOutput(answer="listo"),
        ],
    )
    store = InMemoryNodeRunStore()

    resultado = await _correr(nodo, _entrada(), store=store, clock=_reloj(_AHORA))

    assert resultado.outcome is NodeRunOutcome.SUCCEEDED
    assert len(nodo.calls) == 2, "el ritmo de fondo si le da su plazo completo al segundo intento"


# --- Paso 5, BR5.5: el arrendamiento con latido ---------------------------------


@dataclass
class _StoreConHistorial(InMemoryNodeRunStore):
    """El mismo doble de arriba, mas el historial de cada `upsert` en orden.

    `InMemoryNodeRunStore.filas` solo deja ver la ultima escritura por clave --
    exactamente lo que BR5.4 necesita probar --, pero BR5.5 pregunta por lo que
    se escribio **antes** de llamar al nodo, que una escritura posterior a la
    misma clave ya taparia.
    """

    historial: list[NodeRunRecord] = field(default_factory=list)

    async def upsert(self, record: NodeRunRecord) -> None:
        self.historial.append(record)
        await super().upsert(record)


async def test_el_intento_deja_un_arrendamiento_con_dueno_y_latido_antes_de_llamar_al_nodo() -> (
    None
):
    """BR5.5: el proceso que ejecuta renueva su latido -- antes del intento, no despues."""
    nodo = FakeNode(_spec(timeout_ms=100), behaviors=[FakeOutput(answer="listo")])
    historial = _StoreConHistorial()
    ejecutor = NodeExecutor(store=historial, clock=_reloj(_AHORA), owner="proceso-1")

    with traces.turn_span(tenant_id=_TENANT_ID, case_id=_CASE_ID, use=Use.OPERATIONS):
        resultado = await ejecutor.run(nodo, _entrada(), tenant_id=_TENANT_ID, case_id=_CASE_ID)

    # Control positivo: la ejecucion de verdad tuvo un intento que registrar.
    assert resultado.outcome is NodeRunOutcome.SUCCEEDED
    assert len(historial.historial) >= 1
    primer_registro = historial.historial[0]
    assert primer_registro.outcome is NodeRunOutcome.RUNNING
    assert primer_registro.lease_owner == "proceso-1"
    assert primer_registro.heartbeat_at is not None
    assert primer_registro.lease_expires_at is not None
    assert primer_registro.lease_expires_at > primer_registro.heartbeat_at


async def test_un_desenlace_terminal_suelta_el_arrendamiento() -> None:
    """BR5.5: nadie necesita retomar un trabajo que ya termino."""
    nodo = FakeNode(_spec(timeout_ms=100), behaviors=[FakeOutput(answer="listo")])
    store = InMemoryNodeRunStore()

    resultado = await _correr(nodo, _entrada(), store=store, clock=_reloj(_AHORA))

    assert resultado.outcome is NodeRunOutcome.SUCCEEDED
    fila_final = next(iter(store.filas.values()))
    assert fila_final.outcome is NodeRunOutcome.SUCCEEDED
    assert fila_final.lease_owner is None
    assert fila_final.lease_expires_at is None
