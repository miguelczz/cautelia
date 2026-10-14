"""Los tramos, su lista cerrada, el resumen y la exportacion (BR6.1 a BR6.7, BR4.8).

Lo que aqui se protege es un **fallo silencioso**: un dato personal en una traza
no rompe ninguna pantalla y no levanta ningun error. Sigue saliendo telemetria,
solo que con el dato dentro. Es compuerta dura (RT-14), y es la razon de que la
prueba de canarios busque los cuatro tipos **enteros y por fragmentos**: una
plantilla que recorte un numero de poliza a sus seis digitos seguiria siendo una
fuga, y buscar solo el valor entero no la veria.

## La prueba de tipos: que un atributo fuera de la lista **no compile**

No puede vivir en el arbol, porque un archivo que no compila hace fallar
`mise run types` para siempre. Se comprueba plantandolo y viendo fallar el
comprobador; aqui queda el experimento exacto, para poder repetirlo:

    cat > app/backend/src/untangle/telemetry/traces/_plantado.py <<'EOF'
    from untangle.telemetry.traces.api import SpanAttributes

    def f(*, attributes: SpanAttributes) -> None: ...

    f(attributes={"gen_ai.system": "gemini"})
    f(attributes={"untangle.inventado": "x"})
    suelto = {"gen_ai.system": "gemini"}
    f(attributes=suelto)
    EOF
    mise run types

Salida observada al construir este paso, **tres errores y no uno**:

    _plantado.py:5: error: Incompatible types (expression has type "str",
        TypedDict item "gen_ai.system" has type "ProviderName") [typeddict-item]
    _plantado.py:6: error: Extra key "untangle.inventado" for TypedDict
        "SpanAttributes"  [typeddict-unknown-key]
    _plantado.py:8: error: Argument "attributes" to "f" has incompatible type
        "dict[str, str]"; expected "SpanAttributes"  [arg-type]

Las tres formas de saltarse la lista, cerradas: el nombre inventado, el valor
que no es del enum cerrado, y la puerta de al lado --pasar un `dict[str, str]`
cualquiera en vez de un literal, que es lo que un atributo construido a mano
seria--.

Lo que el comprobador **no** puede afirmar es que nadie lo esquive con un `cast`,
que se borra en tiempo de ejecucion igual que `Redacted` en U3. Eso lo afirma
`test_la_lista_de_atributos_esta_cerrada_tambien_en_ejecucion`, abajo. Dos capas,
no una.
"""

from __future__ import annotations

import ast
import hashlib
import itertools
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from untangle.base import ProviderErrorKind, ProviderName, Use
from untangle.compliance.redaction import detector as deteccion
from untangle.compliance.redaction.api import Redacted
from untangle.settings import Settings
from untangle.telemetry.spend import budget
from untangle.telemetry.spend.models import (
    WINDOW_DAYS,
    BudgetStatus,
    BudgetWindow,
    CostStatus,
    Money,
)
from untangle.telemetry.traces import api, export
from untangle.telemetry.traces.models import (
    CaseMoment,
    NodeName,
    NodeTiming,
    SpanLevel,
    TraceOutcome,
    TraceSummaryStatus,
)

AHORA = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)

#: Los cuatro tipos de dato personal propios del proyecto, con la forma que los
#: reconocedores de U3 declaran: telefono, cedula, placa y numero de poliza. La
#: poliza lleva la forma unica decidida el 2026-09-20: `POL-` y seis digitos.
TELEFONO = "3005551234"
CEDULA = "1032456789"
PLACA = "ABC123"
POLIZA = "POL-100042"
SEMBRADOS = (TELEFONO, CEDULA, PLACA, POLIZA)

#: El turno que un asegurado escribiria con los cuatro dentro. Es lo que viaja en
#: el prompt, y por tanto lo unico que podria llegar a un tramo.
TURNO_SEMBRADO = (
    f"Buenas, soy la cedula {CEDULA}, mi telefono es {TELEFONO}, "
    f"la placa del carro es {PLACA} y la poliza {POLIZA}."
)


@dataclass
class RelojFijo:
    """Un reloj que no avanza solo. El plazo de diez segundos se prueba, no se espera.

    Ninguna prueba de este archivo mide tiempo real: el plazo se cruza moviendo
    este reloj. Una prueba cronometrada con el reloj del sistema mide la maquina
    y no la regla, y falla sola detras de la suite entera.
    """

    momento: datetime = AHORA

    def now(self) -> datetime:
        return self.momento

    def avanzar(self, segundos: float) -> None:
        self.momento += timedelta(seconds=segundos)


@dataclass
class TransporteCaido:
    """Un backend de trazas que no responde. Lo unico que hace es fallar."""

    intentos: int = 0

    def send(self, payload: Redacted) -> None:
        self.intentos += 1
        msg = "el backend de trazas no responde"
        raise ConnectionError(msg)


@dataclass
class TransporteEnMemoria:
    """Guarda lo que salio, ya redactado, para poder inspeccionarlo."""

    lotes: list[str] = field(default_factory=list)

    def send(self, payload: Redacted) -> None:
        self.lotes.append(str(payload))


@pytest.fixture(scope="module", autouse=True)
def _detector_cargado() -> Iterator[None]:
    """La exportacion redacta de verdad, asi que necesita el detector de verdad.

    Se instala al entrar en este modulo y se suelta al salir: ni hereda el de
    otro archivo ni se lo deja puesto al siguiente, que es lo que permite correr
    este solo y en cualquier orden.
    """
    deteccion.install(deteccion.load())
    yield
    deteccion.reset()


@pytest.fixture(autouse=True)
def modulo_limpio(monkeypatch: pytest.MonkeyPatch) -> Iterator[RelojFijo]:
    """Cada prueba arranca con registrador, resumenes, reloj y transporte propios.

    Los cuatro son estado del proceso. Sin esto, una prueba heredaria los tramos
    de la anterior y el archivo dejaria de poder correr en cualquier orden.

    Los identificadores tambien son deterministas: la exportacion comprueba que la
    redaccion no los estropeo, y el modelo de nombres de la redaccion toma por persona,
    cada tanto y por cadena concreta, alguna cadena de cifras. Con azar de verdad, una
    de estas pruebas fallaria una de cada tantas corridas por culpa del detector y no
    del codigo. Sin `random`, que el proyecto prohibe: una semilla fija y SHA-256.
    """
    contador = itertools.count(1)

    def uuid_fijo() -> Any:
        resumen = hashlib.sha256(f"traces-{next(contador)}".encode()).digest()
        return SimpleNamespace(int=int.from_bytes(resumen[:16], "big") >> 6)

    monkeypatch.setattr(api, "uuid4", uuid_fijo)
    api.reset()
    api.reset_summaries()
    reloj = RelojFijo()
    api.install_clock(reloj)
    export.install_transport(None)
    yield reloj
    api.reset()
    api.reset_summaries()
    api.install_clock(None)
    export.install_transport(None)


def _ajustes(*, traces_endpoint: str | None = None) -> Settings:
    """Ajustes con el destino de trazas dicho explicitamente en los dos casos.

    Explicito y no por defecto: si la variable del entorno estuviera puesta en la
    maquina de quien corre la suite, estas pruebas cambiarian de rama sin que
    nadie lo pidiera.
    """
    return Settings(env="ci", traces_endpoint=traces_endpoint)


def _buffer() -> api.BufferedRecorder:
    registrador = api.current_recorder()
    assert isinstance(registrador, api.BufferedRecorder)
    return registrador


def _turno_completo(*, caso: str = "CASE-1", turno: str = "TURN-1") -> None:
    """Un turno de verdad: los tres niveles, con el prompt sembrado detras.

    Es lo que hara el adaptador de Gemini: calcula el resumen del prompt y pasa
    el identificador de la plantilla versionada. El texto del prompt **no tiene
    donde entrar**, y eso es lo que la prueba de canarios comprueba.
    """
    resumen_del_prompt = hashlib.sha256(TURNO_SEMBRADO.encode("utf-8")).hexdigest()
    with api.turn_span(tenant_id="stonecroft", case_id=caso, turn_id=turno, use=Use.CHAT):
        for nodo in NodeName:
            with (
                api.node_span(nodo),
                api.call_span(
                    provider=ProviderName.GEMINI,
                    model="gemini-2.5-flash-001",
                    use=Use.CHAT,
                    attributes={
                        "untangle.prompt_id": "chat.intake.v3",
                        "untangle.prompt_hash": resumen_del_prompt,
                        "gen_ai.usage.input_tokens": 412,
                        "gen_ai.usage.output_tokens": 88,
                    },
                ) as llamada,
            ):
                llamada.set_cost(Money.measured(Decimal("0.000231")))


def _fragmentos(valor: str, *, minimo: int = 6) -> list[str]:
    """El valor entero y cada trozo contiguo suyo de `minimo` caracteres o mas.

    Buscar solo el valor entero dejaria pasar la fuga mas probable: una plantilla
    que lo recorta. `POL-100042` truncado a `100042` sigue siendo el numero de
    poliza de alguien.
    """
    trozos = []
    for largo in range(minimo, len(valor) + 1):
        for inicio in range(len(valor) - largo + 1):
            trozos.append(valor[inicio : inicio + largo])
    return trozos


def _exigir_sin_sembrados(texto: str, *, donde: str) -> None:
    for sembrado in SEMBRADOS:
        for trozo in _fragmentos(sembrado):
            assert trozo not in texto, (
                f"'{trozo}' --fragmento de '{sembrado}'-- llego a {donde}. "
                "Es el escenario RT-14 y es compuerta dura"
            )


# --- La prueba de canarios (RT-14, BR6.5, compuerta dura) ---------------------


async def test_un_turno_sembrado_con_los_cuatro_datos_no_deja_ninguno_en_ningun_tramo() -> None:
    """Los cuatro tipos, enteros y por fragmentos, en los tramos y en lo exportado.

    Dos sitios porque son dos superficies declaradas en el registro de U3:
    `trace_span` y `trace_export`. Comprobar solo la segunda dejaria fuera lo que
    un backend de trazas lee directamente del proceso.
    """
    transporte = TransporteEnMemoria()
    export.install_transport(transporte)

    _turno_completo()
    tramos = _buffer().drain()

    assert len(tramos) == 9  # un turno, cuatro nodos, cuatro llamadas
    delosespacios = [tramo.name for tramo in tramos]
    delosespacios += [clave for tramo in tramos for clave in tramo.attributes]
    delosespacios += [str(valor) for tramo in tramos for valor in tramo.attributes.values()]
    _exigir_sin_sembrados("\n".join(delosespacios), donde="un atributo de un tramo")

    resultado = export.export_batch(tramos, settings=_ajustes())

    assert resultado.ok
    assert resultado.exported == 9
    _exigir_sin_sembrados("\n".join(transporte.lotes), donde="la exportacion de trazas")


# --- La lista cerrada (Q4, capa 4 del diseno de seguridad) --------------------


def test_la_lista_de_atributos_esta_cerrada_tambien_en_ejecucion() -> None:
    """Lo que el comprobador de tipos no puede afirmar: que nadie lo esquive.

    `cast` se borra en tiempo de ejecucion --igual que `Redacted` en U3-- asi que
    el tipo atrapa los descuidos y esto atrapa los atajos. Y lo que `str` no
    puede decir --que un identificador no traiga una frase dentro-- lo dice la
    forma del valor: el prompt entero pasado como "hash" es la via mas probable
    de que un dato personal llegue a un tramo, y los dos son `str`.
    """
    inventado = cast(api.SpanAttributes, {"untangle.inventado": "lo que sea"})

    with api.turn_span(tenant_id="stonecroft", case_id="CASE-1", use=Use.CHAT):
        with api.node_span(NodeName.INTAKE) as nodo:
            with pytest.raises(api.SpanAttributeError, match="fuera de la lista cerrada"):
                nodo.set(inventado)
            with pytest.raises(api.SpanAttributeError, match="resumen SHA-256"):
                nodo.set({"untangle.prompt_hash": TURNO_SEMBRADO})
            with pytest.raises(api.SpanAttributeError, match="identificador"):
                nodo.set({"untangle.case_id": TURNO_SEMBRADO})
            # El costo y su estado no se separan, tampoco aqui (BR3.4, BR3.9).
            with pytest.raises(api.SpanAttributeError, match="sin su estado"):
                nodo.set({"untangle.cost_usd": "0.01"})
            assert set(nodo.attributes) == {"untangle.node", "untangle.case_id"}

    assert "untangle.inventado" not in api.ALLOWED_ATTRIBUTES
    # Dieciseis: las quince de `observability-design.md` mas
    # `untangle.decided_by`, que es la que BR6.4 necesita para decir quien firmo
    # la reanudacion de un caso.
    assert len(api.ALLOWED_ATTRIBUTES) == 16


# --- Los tres niveles (BR6.1, AC4.8.1) ----------------------------------------


def test_los_tres_niveles_existen_anidados_y_no_se_pueden_abrir_sueltos() -> None:
    _turno_completo()
    tramos = {tramo.span_id: tramo for tramo in _buffer().drain()}

    porniveles = {nivel: [t for t in tramos.values() if t.level is nivel] for nivel in SpanLevel}
    assert len(porniveles[SpanLevel.TURN]) == 1
    assert len(porniveles[SpanLevel.NODE]) == 4
    assert len(porniveles[SpanLevel.CALL]) == 4

    turno = porniveles[SpanLevel.TURN][0]
    assert turno.parent_span_id is None
    assert all(nodo.parent_span_id == turno.span_id for nodo in porniveles[SpanLevel.NODE])
    for llamada in porniveles[SpanLevel.CALL]:
        assert llamada.parent_span_id is not None
        assert tramos[llamada.parent_span_id].level is SpanLevel.NODE

    # El identificador de correlacion baja por el contexto: uno solo para los
    # nueve, sin que ninguna llamada lo haya pasado por argumento.
    assert len({tramo.trace_id for tramo in tramos.values()}) == 1

    # Y un tramo sin su nivel de encima levanta en vez de quedar huerfano: un
    # costo que no se puede atribuir a su nodo es lo que AC4.8.1 impide.
    with pytest.raises(api.SpanNestingError, match="no hay turno abierto"):
        with api.node_span(NodeName.INTAKE):
            pass
    with api.turn_span(tenant_id="stonecroft", case_id="CASE-2", use=Use.CHAT):
        with pytest.raises(api.SpanNestingError, match="cuelga de un tramo de nodo"):
            with api.call_span(
                provider=ProviderName.GEMINI, model="gemini-2.5-flash-001", use=Use.CHAT
            ):
                pass


# --- La grafia de los nodos (BR6.2, AC4.8.2, convencion 3 del equipo) ---------


def test_los_nodos_se_llaman_de_las_cuatro_formas_y_de_ninguna_otra() -> None:
    _turno_completo()
    tramos = [t for t in _buffer().drain() if t.level is SpanLevel.NODE]

    assert {t.name for t in tramos} == {"intake", "policy_verification", "decision", "compliance"}
    # La misma grafia en el nombre del tramo y en su atributo: cuatro grafias del
    # mismo nodo obligan a traducir entre la traza, el reporte y el codigo.
    assert all(t.attributes["untangle.node"] == t.name for t in tramos)


# --- Los dos momentos del caso (BR6.4, AC4.8.3) -------------------------------


def test_la_pausa_y_la_reanudacion_viven_en_la_traza_del_mismo_caso(
    modulo_limpio: RelojFijo,
) -> None:
    """BR6.4. El turno, la pausa y la reanudacion, una sola traza.

    Es lo que evita tener que reconstruir a mano lo que paso entre la derivacion
    y la firma: se lee seguido, por el mismo identificador. Dos trazas separadas
    dejarian ese hueco abierto para siempre, porque entre los dos momentos pasan
    horas y nadie guarda el hilo.
    """
    _turno_completo(caso="CASE-7")
    traza = _buffer().drain()[0].trace_id

    modulo_limpio.avanzar(3600)
    with api.case_moment_span(
        CaseMoment.PAUSED, tenant_id="stonecroft", case_id="CASE-7", trace_id=traza
    ):
        pass
    modulo_limpio.avanzar(7200)
    with api.case_moment_span(
        CaseMoment.RESUMED,
        tenant_id="stonecroft",
        case_id="CASE-7",
        trace_id=traza,
        decided_by="stonecroft-ana",
    ):
        pass

    pausa, reanudacion = _buffer().drain()
    assert {pausa.trace_id, reanudacion.trace_id} == {traza}
    assert [pausa.name, reanudacion.name] == ["case.paused", "case.resumed"]
    assert pausa.attributes["untangle.case_id"] == "CASE-7"

    # Raices las dos: no cuelgan de ningun turno, porque cuando ocurren no hay
    # ninguno vivo. Colgar la pausa del turno que la provoco dejaria a la
    # reanudacion colgando de otra cosa, y las dos dejarian de leerse igual.
    assert pausa.parent_span_id is None
    assert reanudacion.parent_span_id is None

    # La hora de la pausa la da el tramo y no un atributo: el tramo ya la dice, y
    # dos cifras del mismo dato son dos cifras que un dia discrepan.
    assert pausa.started_at == AHORA + timedelta(seconds=3600)
    assert "untangle.decided_by" not in pausa.attributes

    # Y la reanudacion dice quien firmo.
    assert reanudacion.attributes["untangle.decided_by"] == "stonecroft-ana"


def test_los_dos_momentos_se_emiten_sin_ningun_turno_abierto() -> None:
    """La reanudacion llega horas despues, desde la bandeja y por otro camino.

    Es la mitad que hacia imposible cumplir BR6.4: si hiciera falta un turno
    abierto, no habria ninguno que abrir, y abrir uno de mentira ensuciaria el
    conteo de turnos con algo que no es un turno.
    """
    assert api.current_context() is None

    with api.case_moment_span(
        CaseMoment.RESUMED,
        tenant_id="stonecroft",
        case_id="CASE-8",
        trace_id="TRAZA-8",
        decided_by="stonecroft-ana",
    ):
        pass

    (tramo,) = _buffer().drain()
    assert tramo.level is SpanLevel.CASE
    assert tramo.trace_id == "TRAZA-8"


def test_la_reanudacion_sin_firma_y_la_pausa_con_firma_no_se_emiten() -> None:
    """Quien decidio va con la reanudacion, y solo con ella.

    Una reanudacion anonima obliga a reconstruir a mano quien aprobo el caso, que
    es lo que BR6.4 existe para evitar; y una pausa firmada afirmaria que alguien
    la decidio cuando la decide el caso al derivarse.
    """
    with (
        pytest.raises(api.SpanAttributeError, match="quien decidio"),
        api.case_moment_span(
            CaseMoment.RESUMED, tenant_id="stonecroft", case_id="CASE-9", trace_id="TRAZA-9"
        ),
    ):
        pass

    with (
        pytest.raises(api.SpanAttributeError, match="no la decide nadie"),
        api.case_moment_span(
            CaseMoment.PAUSED,
            tenant_id="stonecroft",
            case_id="CASE-9",
            trace_id="TRAZA-9",
            decided_by="stonecroft-ana",
        ),
    ):
        pass

    # Y ninguno de los dos dejo tramo: un tramo a medias con un valor sospechoso
    # dentro es peor que uno que falta, porque el segundo se nota.
    assert _buffer().drain() == ()


def test_quien_decidio_es_un_identificador_y_nunca_un_nombre_de_persona() -> None:
    """NFR11, compuerta dura. Es el atributo al que mas se le parece un nombre.

    La lista cerrada cierra los **nombres** de atributo y no lo que cabe dentro
    de un `str`: sin comprobar la forma del valor, "Ana Rivas, de Stonecroft"
    seria un `untangle.decided_by` perfectamente valido y estaria en una traza
    que sale hacia un backend.
    """
    with (
        pytest.raises(api.SpanAttributeError, match="identificador"),
        api.case_moment_span(
            CaseMoment.RESUMED,
            tenant_id="stonecroft",
            case_id="CASE-9",
            trace_id="TRAZA-9",
            decided_by="Ana Rivas, de Stonecroft",
        ),
    ):
        pass

    assert _buffer().drain() == ()


# --- El resumen: tres estados y diez segundos (BR6.7, C-23) -------------------


def _lo_que_trajo_el_rastro(**cambios: object) -> TraceOutcome:
    base: dict[str, object] = {
        "nodes": (
            NodeTiming(
                node=NodeName.INTAKE,
                started_at=AHORA,
                duration_ms=320,
                cost=Money.measured(Decimal("0.0002")),
            ),
        ),
        "latency_ms": 900,
        "cost": Money.measured(Decimal("0.0004")),
    }
    return TraceOutcome.model_validate(base | cambios)


async def test_el_resumen_pasa_a_lost_a_los_diez_segundos_y_a_ready_si_el_rastro_llega_antes(
    modulo_limpio: RelojFijo,
) -> None:
    """El plazo se escribe **en segundos literales**, no leyendo la constante.

    Leerla haria que la prueba se moviera con ella: alargar el plazo a diez
    minutos dejaria la suite verde, que es lo que paso la primera vez que se
    escribio este archivo. Lo que el diseno fija son diez segundos, atados a la
    meta del chat, y eso es lo que se afirma.
    """
    reloj = modulo_limpio
    assert api.SUMMARY_DEADLINE_SECONDS == 10

    tarde = await api.open_summary(
        trace_id="TRAZA-TARDE",
        tenant_id="stonecroft",
        case_id="CASE-TARDE",
        visitor_key_hash="resumen-de-la-clave",
    )
    assert tarde.status is TraceSummaryStatus.RECORDING

    # A los nueve segundos todavia se esta registrando: el plazo es un borde, y
    # un borde solo esta probado si se toca por los dos lados.
    reloj.avanzar(9)
    aun = await api.summary_by_trace(
        "TRAZA-TARDE", tenant_id="stonecroft", visitor_key_hash="resumen-de-la-clave"
    )
    assert aun is not None
    assert aun.status is TraceSummaryStatus.RECORDING

    reloj.avanzar(1)
    perdido = await api.summary_by_trace(
        "TRAZA-TARDE", tenant_id="stonecroft", visitor_key_hash="resumen-de-la-clave"
    )
    assert perdido is not None
    assert perdido.status is TraceSummaryStatus.LOST

    # El rastro que llega despues ya no lo revive: `lost` es terminal.
    tardio = await api.record_trace(
        "TRAZA-TARDE", _lo_que_trajo_el_rastro(), tenant_id="stonecroft"
    )
    assert tardio == perdido

    await api.open_summary(
        trace_id="TRAZA-A-TIEMPO",
        tenant_id="stonecroft",
        case_id="CASE-A-TIEMPO",
        visitor_key_hash="resumen-de-la-clave",
    )
    reloj.avanzar(9)
    listo = await api.record_trace(
        "TRAZA-A-TIEMPO",
        _lo_que_trajo_el_rastro(clauses_retrieved=3, clauses_verified=2, latency_ms=1450),
        tenant_id="stonecroft",
    )
    assert listo is not None
    assert listo.status is TraceSummaryStatus.READY
    assert listo.latency_ms == 1450


async def test_pedirlo_con_otra_clave_de_navegador_responde_igual_que_si_no_existiera() -> None:
    """`None` a los tres casos: un "prohibido" confirmaria que existe (BR6.6)."""
    await api.open_summary(
        trace_id="TRAZA-1",
        tenant_id="stonecroft",
        case_id="CASE-1",
        visitor_key_hash="el-del-dueno",
    )

    assert (
        await api.trace_summary_for(
            "CASE-1", tenant_id="stonecroft", visitor_key_hash="el-del-dueno"
        )
        is not None
    )
    assert (
        await api.trace_summary_for("CASE-1", tenant_id="stonecroft", visitor_key_hash="el-de-otro")
        is None
    )
    assert (
        await api.trace_summary_for(
            "CASE-99", tenant_id="stonecroft", visitor_key_hash="el-de-otro"
        )
        is None
    )
    assert (
        await api.trace_summary_for("CASE-1", tenant_id="stonecroft", visitor_key_hash=None) is None
    )


# --- La caida del backend no detiene nada (BR4.8, BR6.7) ----------------------


async def test_la_caida_del_backend_de_trazas_no_detiene_el_gasto_ni_el_corte() -> None:
    """Tres afirmaciones, porque la regla tiene tres mitades.

    Que la exportacion no propague el fallo; que el resumen pase a `lost` en vez
    de quedarse "registrandose" para siempre; y que el modulo del gasto **no
    importe** el de trazas, que es la mitad estructural. El contrato de
    importacion que lo comprueba entra con el bloque F; esta prueba lo afirma
    desde hoy, que es cuando el codigo nace.
    """
    caido = TransporteCaido()
    export.install_transport(caido)
    await api.open_summary(
        trace_id="TRAZA-CAIDA",
        tenant_id="stonecroft",
        case_id="CASE-CAIDA",
        visitor_key_hash="el-del-dueno",
    )
    with (
        api.turn_span(
            tenant_id="stonecroft", case_id="CASE-CAIDA", use=Use.CHAT, trace_id="TRAZA-CAIDA"
        ),
        api.node_span(NodeName.DECISION) as nodo,
    ):
        nodo.set({"untangle.error_kind": ProviderErrorKind.UNAVAILABLE})

    resultado = await export.export_pending(settings=_ajustes())

    assert caido.intentos == 1
    assert not resultado.ok
    assert resultado.failure == "transport"
    perdido = await api.summary_by_trace(
        "TRAZA-CAIDA", tenant_id="stonecroft", visitor_key_hash="el-del-dueno"
    )
    assert perdido is not None
    assert perdido.status is TraceSummaryStatus.LOST

    # El corte sigue cortando con el backend caido. El acumulado se **fuerza** en
    # la ventana, nunca se alcanza gastando (BR5.9).
    comienzo = date(2026, 9, 16)
    agotada = BudgetWindow(
        window_start=comienzo,
        window_end=comienzo + timedelta(days=WINDOW_DAYS),
        billable_spent_usd=Decimal("5.00"),
        cap_usd=Decimal("5.00"),
        alert_usd=Decimal("3.00"),
        recording_reserve_usd=Decimal(0),
        recording_reserve_status=CostStatus.MEASURED,
        updated_at=AHORA,
    )
    assert budget.status(agotada) is BudgetStatus.EXHAUSTED

    for archivo in sorted(Path(budget.__file__).parent.glob("*.py")):
        for modulo in _modulos_importados(archivo):
            assert "telemetry.traces" not in modulo, (
                f"{archivo.name} importa '{modulo}': el modulo del gasto no importa el "
                "de trazas, porque el corte no puede depender de la observacion"
            )


def _modulos_importados(archivo: Path) -> list[str]:
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    modulos: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.extend(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            modulos.append(nodo.module)
    return modulos


# --- La exportacion: al archivo cuando no hay destino, y la perdida declarada --


async def test_sin_destino_se_escribe_el_archivo_otlp_y_con_destino_sin_sdk_se_declara_la_perdida(
    tmp_path: Path,
) -> None:
    destino = tmp_path / "traces.otlp.jsonl"
    export.install_transport(export.FileTransport(destino))

    _turno_completo(caso="CASE-ARCHIVO", turno="TURN-ARCHIVO")
    resultado = await export.export_pending(settings=_ajustes())

    assert resultado.ok
    lote = json.loads(destino.read_text(encoding="utf-8").strip())
    tramos = lote["resourceSpans"][0]["scopeSpans"][0]["spans"]
    assert len(tramos) == 9
    assert {t["name"] for t in tramos} >= {"turn", "intake", "compliance"}

    # Con destino declarado y sin exportador OTLP instalado --la dependencia
    # entra con el bloque F-- no se finge que entrego: se declara la perdida.
    export.install_transport(None)
    _turno_completo(caso="CASE-SIN-SDK", turno="TURN-SIN-SDK")
    sin_sdk = await export.export_pending(settings=_ajustes(traces_endpoint="http://trazas:4318"))

    assert not sin_sdk.ok
    assert sin_sdk.failure == "transport"
