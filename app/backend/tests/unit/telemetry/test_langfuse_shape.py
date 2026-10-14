"""La forma del lote para Langfuse: derivada de lo que el tramo trae, y redactada igual.

Tres cosas se afirman aqui y las tres son de "no entra nada nuevo":

- cada atributo de Langfuse sale de un campo del tramo, y un tramo que no lo
  trae no lo recibe (ni un costo en cero, ni una sesion inventada);
- el lote de Langfuse pasa por el mismo punto unico de redaccion que el del
  archivo, con los cuatro datos personales sembrados y el detector de verdad;
- la forma del archivo de la corrida no cambia.

Sin red: el transporte es uno en memoria que declara la forma de Langfuse.
"""

from __future__ import annotations

import hashlib
import io
import itertools
import json
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from untangle import observability
from untangle.base import Locale, ProviderName, Use
from untangle.compliance.redaction import detector as deteccion
from untangle.compliance.redaction.api import Redacted, allow_public_terms
from untangle.compliance.redaction.api import redact as redactar
from untangle.settings import Settings
from untangle.telemetry.spend.models import Money
from untangle.telemetry.traces import api, export, langfuse_shape
from untangle.telemetry.traces.models import CaseMoment, NodeName, SpanLevel

AHORA = datetime(2026, 10, 14, 15, 0, tzinfo=UTC)

#: Una traza de 32 cifras, como las que produce `api._identificador_nuevo`.
TRAZA = "48215069371502846913720465183927"

TELEFONO = "3005551234"
CEDULA = "1032456789"
PLACA = "ABC123"
POLIZA = "POL-100042"
SEMBRADOS = (TELEFONO, CEDULA, PLACA, POLIZA)


@dataclass
class TransporteDeLangfuse:
    """Un transporte en memoria que pide la forma de Langfuse, como el de verdad."""

    wire_format = export.WireFormat.LANGFUSE
    lotes: list[str] = field(default_factory=list)

    def send(self, payload: Redacted) -> None:
        self.lotes.append(str(payload))


@pytest.fixture(scope="module", autouse=True)
def _detector_cargado() -> Iterator[None]:
    """El detector de verdad, con los nombres de atributo como los instala la raiz de composicion."""
    deteccion.install(deteccion.load())
    allow_public_terms(export.wire_vocabulary())
    yield
    allow_public_terms(())
    deteccion.reset()


@pytest.fixture
def _eventos_de_la_prueba() -> Iterator[io.StringIO]:
    salida = io.StringIO()
    observability.set_stream(salida)
    yield salida
    observability.set_stream(sys.stdout)


@pytest.fixture(autouse=True)
def _modulo_limpio(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Identificadores de tramo deterministas y estado del modulo propio.

    Los de `uuid4` son aleatorios, y el modelo de nombres del detector decide por
    cadena concreta: con azar de verdad, esta prueba seria intermitente por culpa del
    detector y no del codigo. La semilla fija hace que sea la misma en cada corrida.
    """
    # Sin `random` (esta prohibido en el proyecto): una semilla fija y SHA-256.
    contador = itertools.count(1)

    def uuid_fijo() -> Any:
        resumen = hashlib.sha256(f"id-{next(contador)}".encode()).digest()
        return SimpleNamespace(int=int.from_bytes(resumen[:16], "big") >> 6)

    monkeypatch.setattr(api, "uuid4", uuid_fijo)
    api.reset()
    api.install_clock(SimpleNamespace(now=lambda: AHORA))
    export.install_transport(None)
    yield
    api.reset()
    api.install_clock(None)
    export.install_transport(None)


def _turno(
    *, caso: str = "CASE-1", costo: Money | None = None, con_modelo: bool = True
) -> tuple[api.FinishedSpan, ...]:
    """Un turno de verdad: turno, un nodo y la llamada al modelo."""
    with (
        api.turn_span(
            tenant_id="stonecroft", case_id=caso, turn_id="TURN-1", use=Use.CHAT, trace_id=TRAZA
        ),
        api.node_span(NodeName.DECISION),
        api.call_span(
            provider=ProviderName.GEMINI,
            model="gemini-2.5-flash-001" if con_modelo else "x",
            use=Use.CHAT,
            attempt=2,
            attributes={"gen_ai.usage.input_tokens": 412, "gen_ai.usage.output_tokens": 88},
        ) as llamada,
    ):
        llamada.set_cost(costo if costo is not None else Money.measured(Decimal("0.000231")))
    tramos = api.current_recorder()
    assert isinstance(tramos, api.BufferedRecorder)
    return tramos.drain()


def _por_nombre(tramos: tuple[api.FinishedSpan, ...]) -> dict[str, api.FinishedSpan]:
    return {tramo.name: tramo for tramo in tramos}


# --- Que sale y de que campo sale ---------------------------------------------


def test_el_tramo_raiz_del_turno_lleva_sesion_nombre_publico_etiqueta_y_aseguradora() -> None:
    raiz = _por_nombre(_turno())["turn"]

    assert langfuse_shape.derive(raiz) == {
        "langfuse.session.id": "CASE-1",  # untangle.case_id
        "langfuse.trace.name": "turn",  # el nombre del tramo
        "langfuse.trace.public": True,
        "langfuse.trace.tags": ("chat",),  # untangle.use
        "langfuse.trace.metadata.tenant_id": "stonecroft",  # la aseguradora del tramo
        "langfuse.observation.metadata.tenant_id": "stonecroft",
    }


def test_el_tramo_del_nodo_lleva_el_nodo_y_ningun_dato_de_traza() -> None:
    nodo = _por_nombre(_turno())["decision"]

    derivado = langfuse_shape.derive(nodo)

    assert derivado["langfuse.observation.metadata.node"] == "decision"
    assert derivado["langfuse.session.id"] == "CASE-1"
    # Nombre, visibilidad y etiquetas son de la traza y los pone su raiz, no cada tramo.
    assert not {k for k in derivado if k.startswith("langfuse.trace.")}


def test_la_llamada_al_modelo_es_una_generacion_con_tokens_costo_e_intento() -> None:
    llamada = _por_nombre(_turno())["call.gemini"]

    derivado = langfuse_shape.derive(llamada)

    assert derivado["langfuse.observation.type"] == "generation"
    assert json.loads(str(derivado["langfuse.observation.usage_details"])) == {
        "input": 412,  # gen_ai.usage.input_tokens
        "output": 88,  # gen_ai.usage.output_tokens
    }
    # El costo sale del decimal en texto de `untangle.cost_usd`, sin pasar por un flotante.
    assert derivado["langfuse.observation.cost_details"] == '{"total": 0.000231}'
    assert derivado["langfuse.observation.metadata.attempt"] == "2"  # untangle.attempt


def test_un_costo_no_medido_no_se_escribe_como_cero() -> None:
    """BR3.3: un cero se suma despues como si fuera cierto."""
    llamada = _por_nombre(_turno(costo=Money.not_measured()))["call.gemini"]

    derivado = langfuse_shape.derive(llamada)

    assert "langfuse.observation.cost_details" not in derivado
    # Lo demas de la generacion sigue saliendo: solo falta lo que no se midio.
    assert derivado["langfuse.observation.type"] == "generation"


def test_la_pausa_y_la_reanudacion_son_raices_que_no_renombran_la_traza() -> None:
    with api.case_moment_span(
        CaseMoment.PAUSED, tenant_id="stonecroft", case_id="CASE-1", trace_id=TRAZA
    ):
        pass
    recorder = api.current_recorder()
    assert isinstance(recorder, api.BufferedRecorder)
    (pausa,) = recorder.drain()

    derivado = langfuse_shape.derive(pausa)

    assert derivado["langfuse.trace.public"] is True
    assert derivado["langfuse.session.id"] == "CASE-1"
    # La traza ya tiene el nombre y las etiquetas del turno que la abrio.
    assert "langfuse.trace.name" not in derivado
    assert "langfuse.trace.tags" not in derivado


def test_solo_salen_claves_conocidas_y_cada_valor_viene_de_un_campo_del_tramo() -> None:
    """Lo que esta derivacion nunca hace: inventar texto.

    Para cada tramo del turno se comprueba que toda clave derivada esta en la lista
    de arriba y que todo texto que lleva es uno de los campos que el tramo ya tenia.
    """
    for tramo in _turno():
        campos = {
            tramo.name,
            tramo.tenant_id,
            *(str(v) for v in tramo.attributes.values()),
        }
        for clave, valor in langfuse_shape.derive(tramo).items():
            assert clave in langfuse_shape.DERIVED_KEYS, clave
            if isinstance(valor, bool) or clave == "langfuse.observation.type":
                # Una constante del vocabulario de Langfuse ("generation"), no un campo.
                continue
            textos = valor if isinstance(valor, tuple) else (valor,)
            if clave in {
                "langfuse.observation.usage_details",
                "langfuse.observation.cost_details",
            }:
                # Un numero que salio de un atributo, dentro de un JSON.
                assert re.fullmatch(r"[{}\":, a-z0-9.]+", str(valor)), valor
                continue
            for texto in textos:
                assert str(texto) in campos, f"{clave}={texto!r} no sale de ningun campo del tramo"


def test_un_tramo_sin_caso_ni_tokens_no_recibe_sesion_ni_uso() -> None:
    """Lo que el tramo no trae, no se inventa."""
    desnudo = api.FinishedSpan(
        trace_id=TRAZA,
        tenant_id="stonecroft",
        span_id="b" * 32,
        parent_span_id="c" * 32,
        name="call.gemini",
        level=SpanLevel.CALL,
        started_at=AHORA,
        ended_at=AHORA,
        duration_ms=0,
        attributes={"gen_ai.request.model": "gemini-2.5-flash-001"},
    )

    derivado = langfuse_shape.derive(desnudo)

    assert "langfuse.session.id" not in derivado
    assert "langfuse.observation.usage_details" not in derivado
    assert "langfuse.observation.cost_details" not in derivado
    assert "langfuse.observation.metadata.attempt" not in derivado


# --- La forma del cable --------------------------------------------------------


def _tramos_del_cable(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return list(payload["resourceSpans"][0]["scopeSpans"][0]["spans"])


def _atributos(tramo: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {a["key"]: a["value"] for a in tramo["attributes"]}


def test_la_forma_de_langfuse_acorta_los_ids_de_tramo_y_escribe_enteros_y_tiempos_como_texto() -> (
    None
):
    tramos = _turno()

    cable = _tramos_del_cable(export.otlp_payload(tramos, wire=export.WireFormat.LANGFUSE))

    ids = {t["spanId"] for t in cable}
    assert all(re.fullmatch(r"[0-9a-f]{16}", i) for i in ids)
    assert len(ids) == len(cable), "acortar no puede juntar dos tramos"
    # El arbol es el mismo: cada padre es el id acortado de un tramo del lote.
    for tramo in cable:
        assert tramo.get("parentSpanId") is None or tramo["parentSpanId"] in ids
    # La raiz no trae `parentSpanId`, en vez de una cadena vacia que quien lee tendria que
    # interpretar; el archivo de la corrida sigue escribiendola vacia.
    (raiz_del_cable,) = [t for t in cable if t["name"] == "turn"]
    assert "parentSpanId" not in raiz_del_cable
    assert all(t["traceId"] == TRAZA for t in cable)
    for tramo in cable:
        assert isinstance(tramo["startTimeUnixNano"], str)
        assert isinstance(tramo["endTimeUnixNano"], str)

    raiz = next(t for t in cable if t["name"] == "turn")
    atributos = _atributos(raiz)
    assert atributos["langfuse.trace.public"] == {"boolValue": True}
    assert atributos["langfuse.trace.tags"] == {"arrayValue": {"values": [{"stringValue": "chat"}]}}
    assert atributos["langfuse.session.id"] == {"stringValue": "CASE-1"}

    llamada = next(t for t in cable if t["name"] == "call.gemini")
    atributos = _atributos(llamada)
    assert atributos["gen_ai.usage.input_tokens"] == {"intValue": "412"}
    assert atributos["langfuse.observation.type"] == {"stringValue": "generation"}
    # Los atributos propios de la lista cerrada siguen viajando: Langfuse los
    # guarda como metadato y el modelo y los tokens salen de los `gen_ai.*`.
    assert atributos["gen_ai.request.model"] == {"stringValue": "gemini-2.5-flash-001"}


def test_la_forma_del_archivo_de_la_corrida_no_cambia() -> None:
    """Sin pedir otra forma, el lote es el de siempre: ids de 32, numeros y nada de Langfuse."""
    cable = _tramos_del_cable(export.otlp_payload(_turno()))

    assert all(len(t["spanId"]) == 32 for t in cable)
    assert all(isinstance(t["startTimeUnixNano"], int) for t in cable)
    llamada = next(t for t in cable if t["name"] == "call.gemini")
    assert _atributos(llamada)["gen_ai.usage.input_tokens"] == {"intValue": 412}
    claves = {k for t in cable for k in _atributos(t)}
    assert not {k for k in claves if k.startswith("langfuse.")}


# --- Redactado igual: lo sembrado no sale, y lo que Langfuse necesita si ------


def test_un_turno_sembrado_con_los_cuatro_datos_sale_tapado_tambien_en_la_forma_de_langfuse() -> (
    None
):
    """RT-14 por el transporte de Langfuse: el mismo punto unico de salida.

    Los cuatro datos van en el prompt del turno, que no tiene donde entrar en un tramo; para
    poner a prueba el punto de salida en serio ademas se siembran en el unico campo de texto
    del lote que una persona podria influir: el nombre del tramo del turno.
    """
    transporte = TransporteDeLangfuse()
    export.install_transport(transporte)
    sembrado = f"cedula {CEDULA} telefono {TELEFONO} placa {PLACA} poliza {POLIZA}"
    tramos = list(_turno())
    tramos[0] = replace(tramos[0], name=sembrado)

    resultado = export.export_batch(
        tuple(tramos), settings=Settings(env="ci", traces_endpoint=None)
    )

    assert resultado.ok
    (lote,) = transporte.lotes
    for dato in SEMBRADOS:
        assert dato not in lote, f"'{dato}' salio hacia Langfuse sin tapar"


def test_los_identificadores_tiempos_y_costos_que_langfuse_necesita_sobreviven_a_la_redaccion() -> (
    None
):
    """Si el detector comiera un id o un tiempo, el arbol y el enlace se romperian en silencio."""
    transporte = TransporteDeLangfuse()
    export.install_transport(transporte)
    tramos = _turno()

    resultado = export.export_batch(tramos, settings=Settings(env="ci", traces_endpoint=None))

    assert resultado.ok
    (lote,) = transporte.lotes
    cable = _tramos_del_cable(json.loads(lote))  # sigue siendo JSON valido
    esperado = export.otlp_payload(tramos, wire=export.WireFormat.LANGFUSE)
    # Redactar un lote sin datos personales lo deja igual, tramo por tramo.
    assert cable == _tramos_del_cable(esperado)


def test_si_la_redaccion_estropea_un_id_de_tramo_se_rearma_con_otros_y_sale_sano(
    monkeypatch: pytest.MonkeyPatch, _eventos_de_la_prueba: io.StringIO
) -> None:
    """El modelo de nombres toma por persona alguna cadena de cifras, por cadena concreta.

    Se provoca con una redaccion de mentira que estropea el id de un tramo **solo la primera
    vez**: el segundo armado trae otros ids para los tramos, el arbol sigue entero y el lote sale.
    """
    transporte = TransporteDeLangfuse()
    export.install_transport(transporte)
    tramos = _turno()
    estropeado = tramos[1].span_id[:16]
    llamadas = 0

    def estropea_la_primera(texto: str, *, language: Locale) -> Redacted:
        nonlocal llamadas
        llamadas += 1
        malo = texto.replace(estropeado, "[NAME 1]") if llamadas == 1 else texto
        return redactar(malo, language=language)

    monkeypatch.setattr("untangle.telemetry.traces.export.redact", estropea_la_primera)

    resultado = export.export_batch(tramos, settings=Settings(env="ci", traces_endpoint=None))

    assert resultado.ok
    assert llamadas == 2
    assert '"event": "traces.export_ids_altered"' in _eventos_de_la_prueba.getvalue()
    (lote,) = transporte.lotes
    cable = _tramos_del_cable(json.loads(lote))
    ids = {t["spanId"] for t in cable}
    assert estropeado not in ids  # el segundo armado derivo otros
    assert all(re.fullmatch(r"[0-9]{16}", i) for i in ids)
    # El arbol sigue siendo el mismo: cada padre es el id de un tramo del lote.
    assert all(t.get("parentSpanId") is None or t["parentSpanId"] in ids for t in cable)
    assert {t["traceId"] for t in cable} == {TRAZA}


def test_si_la_redaccion_estropea_el_id_de_la_traza_el_lote_no_se_entrega(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El id de la traza no se puede cambiar --el enlace del visitante lo lleva--: no sale.

    Un id roto es un arbol huerfano y un enlace a una traza que no existe.
    """
    transporte = TransporteDeLangfuse()
    export.install_transport(transporte)
    tramos = _turno()
    llamadas = 0

    def estropea_siempre(texto: str, *, language: Locale) -> Redacted:
        nonlocal llamadas
        llamadas += 1
        return redactar(texto.replace(TRAZA, "[NAME 1]"), language=language)

    monkeypatch.setattr("untangle.telemetry.traces.export.redact", estropea_siempre)

    resultado = export.export_batch(tramos, settings=Settings(env="ci", traces_endpoint=None))

    assert not resultado.ok
    assert resultado.failure == "redaction_altered_ids"
    assert llamadas == 3  # los tres armados posibles
    assert transporte.lotes == []


def test_el_archivo_de_la_corrida_no_reintenta_porque_sus_ids_no_cambian_de_un_armado_a_otro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llamadas = 0

    def estropea_siempre(texto: str, *, language: Locale) -> Redacted:
        nonlocal llamadas
        llamadas += 1
        return redactar(texto.replace(TRAZA, "[NAME 1]"), language=language)

    class TransporteDeArchivo:
        def send(self, payload: Redacted) -> None: ...

    export.install_transport(TransporteDeArchivo())
    monkeypatch.setattr("untangle.telemetry.traces.export.redact", estropea_siempre)

    resultado = export.export_batch(_turno(), settings=Settings(env="ci", traces_endpoint=None))

    assert resultado.failure == "redaction_altered_ids"
    assert llamadas == 1


def test_el_vocabulario_de_nombres_cubre_toda_clave_que_el_exportador_puede_escribir() -> None:
    """La raiz de composicion lo pasa a la lista de nombres publicos de la redaccion."""
    vocabulario = set(export.wire_vocabulary())

    assert set(api.ALLOWED_ATTRIBUTES) <= vocabulario
    assert langfuse_shape.DERIVED_KEYS <= vocabulario
    assert "service.name" in vocabulario


def test_los_identificadores_nuevos_son_treinta_y_dos_cifras_distintas() -> None:
    identificadores = {api._identificador_nuevo() for _ in range(500)}

    assert len(identificadores) == 500
    assert all(re.fullmatch(r"[0-9]{32}", i) for i in identificadores)
