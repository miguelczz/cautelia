"""La exportacion periodica hacia Langfuse: se instala solo con las tres variables, corre fuera del bucle y no muere.

Sin red y sin Langfuse: el transporte de `httpx2` es uno falso. El intervalo se baja a
decimas de segundo para no esperar quince, y las esperas son por evento y no por
reloj: una prueba que durmiera "lo suficiente" mediria la maquina y no la regla.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import itertools
import json
import sys
import time
from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any

import httpx2
import pytest

from untangle import observability
from untangle.base import ProviderName, Use
from untangle.compliance.redaction import detector as deteccion
from untangle.compliance.redaction.api import allow_public_terms
from untangle.providers.adapters.langfuse import LangfuseTransport
from untangle.server import trace_shipping
from untangle.settings import Settings
from untangle.telemetry.spend.models import Money
from untangle.telemetry.traces import api, export, links
from untangle.telemetry.traces.models import NodeName, TraceSummaryStatus

HOST = "https://us.cloud.langfuse.com"
CLAVE_PUBLICA = "pk-lf-x"
CLAVE_SECRETA = "sk-lf-x"


def _ajustes(*, con_langfuse: bool = True) -> Settings:
    if not con_langfuse:
        return Settings(env="ci")
    return Settings(
        env="ci",
        langfuse_public_key=CLAVE_PUBLICA,
        langfuse_secret_key=CLAVE_SECRETA,
        langfuse_host=HOST,
    )


@pytest.fixture(scope="module", autouse=True)
def _detector_cargado() -> Iterator[None]:
    deteccion.install(deteccion.load())
    yield
    deteccion.reset()


@pytest.fixture(autouse=True)
def _nombres_de_atributo() -> None:
    """Por prueba y no por modulo: la raiz de las pruebas vacia la lista antes de cada una."""
    allow_public_terms(export.wire_vocabulary())


@pytest.fixture(autouse=True)
def _estado_limpio(monkeypatch: pytest.MonkeyPatch) -> Iterator[io.StringIO]:
    """Registrador, resumenes, enlaces, transporte y eventos propios; ids deterministas."""
    contador = itertools.count(1)

    def uuid_fijo() -> Any:
        resumen = hashlib.sha256(f"envio-{next(contador)}".encode()).digest()
        return SimpleNamespace(int=int.from_bytes(resumen[:16], "big") >> 6)

    monkeypatch.setattr(api, "uuid4", uuid_fijo)
    api.reset()
    api.reset_summaries()
    export.install_transport(None)
    links.install(None)
    eventos = io.StringIO()
    observability.set_stream(eventos)
    yield eventos
    observability.set_stream(sys.stdout)
    api.reset()
    api.reset_summaries()
    export.install_transport(None)
    links.install(None)


class FalsoLangfuse:
    """Un Langfuse que anota los lotes que le llegan y puede fallar las primeras veces."""

    def __init__(
        self,
        *,
        fallar_envios: int = 0,
        proyecto: str | None = "proyecto-local",
        fallar_proyecto: int = 0,
        espera_segundos: float = 0.0,
    ) -> None:
        self.lotes: list[dict[str, Any]] = []
        self.envios = 0
        self.consultas_de_proyecto = 0
        self._fallar_envios = fallar_envios
        self._proyecto = proyecto
        self._fallar_proyecto = fallar_proyecto
        self._espera = espera_segundos
        self.llego = asyncio.Event()
        self._bucle = asyncio.get_running_loop()

    def __call__(self, peticion: httpx2.Request) -> httpx2.Response:
        if peticion.url.path == "/api/public/projects":
            self.consultas_de_proyecto += 1
            if self._proyecto is None or self.consultas_de_proyecto <= self._fallar_proyecto:
                return httpx2.Response(503)
            return httpx2.Response(200, json={"data": [{"id": self._proyecto}]})
        # Estamos en el hilo de la entrega: bloquear aqui no debe detener el bucle de eventos.
        if self._espera:
            time.sleep(self._espera)
        self.envios += 1
        if self.envios <= self._fallar_envios:
            return httpx2.Response(500)
        self.lotes.append(json.loads(peticion.content))
        self._bucle.call_soon_threadsafe(self.llego.set)
        return httpx2.Response(200, json={})

    def transporte(self) -> LangfuseTransport:
        return LangfuseTransport(
            public_key=CLAVE_PUBLICA,
            secret_key=CLAVE_SECRETA,
            host=HOST,
            network=httpx2.MockTransport(self),
        )

    def nombres_de_tramos(self) -> list[str]:
        return [
            tramo["name"]
            for lote in self.lotes
            for tramo in lote["resourceSpans"][0]["scopeSpans"][0]["spans"]
        ]


def _envio(falso: FalsoLangfuse, *, intervalo: float = 0.05) -> trace_shipping.TraceShipping:
    transporte = falso.transporte()
    export.install_transport(transporte)
    return trace_shipping.TraceShipping(
        transport=transporte, settings=_ajustes(), interval_seconds=intervalo
    )


def _turno(caso: str = "case-1", traza: str | None = None) -> None:
    with (
        api.turn_span(
            tenant_id="stonecroft", case_id=caso, turn_id="TURN-1", use=Use.CHAT, trace_id=traza
        ),
        api.node_span(NodeName.DECISION),
        api.call_span(
            provider=ProviderName.GEMINI,
            model="gemini-2.5-flash-001",
            use=Use.CHAT,
            attributes={"gen_ai.usage.input_tokens": 12, "gen_ai.usage.output_tokens": 3},
        ) as llamada,
    ):
        llamada.set_cost(Money.not_measured())


async def _esperar(evento: asyncio.Event, *, segundos: float = 10.0) -> None:
    await asyncio.wait_for(evento.wait(), timeout=segundos)


async def _hasta(condicion: Callable[[], bool], *, intentos: int = 1000) -> None:
    """Espera a que algo ocurra sin que la prueba dependa de cuanto tarda la maquina."""
    for _ in range(intentos):
        if condicion():
            return
        await asyncio.sleep(0.01)
    msg = "la condicion no se cumplio a tiempo"
    raise AssertionError(msg)


# --- Sin las variables no corre nada nuevo --------------------------------------


def test_sin_las_tres_variables_no_se_instala_nada() -> None:
    assert trace_shipping.build(_ajustes(con_langfuse=False)) is None

    # Todo queda como estaba: el archivo de la corrida.
    assert isinstance(export.transport_for(_ajustes(con_langfuse=False)), export.FileTransport)


async def test_con_las_tres_variables_se_instala_el_transporte_de_langfuse() -> None:
    envio = trace_shipping.build(_ajustes())

    assert envio is not None
    transporte = export.transport_for(_ajustes())
    try:
        assert isinstance(transporte, LangfuseTransport)
        assert transporte.wire_format is export.WireFormat.LANGFUSE
    finally:
        await envio.stop()


# --- El ciclo --------------------------------------------------------------------


async def test_cada_vuelta_exporta_lo_acumulado_en_la_forma_de_langfuse() -> None:
    falso = FalsoLangfuse()
    envio = _envio(falso)
    await envio.start()
    try:
        _turno()
        await _esperar(falso.llego)
    finally:
        await envio.stop()

    assert sorted(falso.nombres_de_tramos()) == ["call.gemini", "decision", "turn"]
    raiz = next(
        t
        for t in falso.lotes[0]["resourceSpans"][0]["scopeSpans"][0]["spans"]
        if t["name"] == "turn"
    )
    atributos = {a["key"] for a in raiz["attributes"]}
    assert {"langfuse.session.id", "langfuse.trace.public", "langfuse.trace.name"} <= atributos


async def test_al_apagar_exporta_una_vez_mas_lo_que_quedaba() -> None:
    """El intervalo es largo: lo que sale lo saca `stop`, no el ciclo."""
    falso = FalsoLangfuse()
    envio = _envio(falso, intervalo=3600)
    await envio.start()
    _turno()
    assert falso.envios == 0

    await envio.stop()

    assert sorted(falso.nombres_de_tramos()) == ["call.gemini", "decision", "turn"]


async def test_la_entrega_corre_fuera_del_bucle_de_eventos() -> None:
    """Un destino que tarda trescientos milisegundos no detiene el resto del proceso."""
    falso = FalsoLangfuse(espera_segundos=0.3)
    envio = _envio(falso)
    marcas = 0

    async def reloj() -> None:
        nonlocal marcas
        while not falso.llego.is_set():
            await asyncio.sleep(0.02)
            marcas += 1

    await envio.start()
    try:
        _turno()
        await asyncio.gather(reloj(), _esperar(falso.llego))
    finally:
        await envio.stop()

    # Con la entrega en el bucle, no habria casi marcas durante los 300 ms bloqueados.
    assert marcas >= 5


async def test_un_fallo_de_langfuse_no_para_el_ciclo_y_marca_perdido_el_resumen(
    _estado_limpio: io.StringIO,
) -> None:
    falso = FalsoLangfuse(fallar_envios=1)
    envio = _envio(falso)
    await api.open_summary(
        trace_id="1" * 32, tenant_id="stonecroft", case_id="case-1", visitor_key_hash="dueno"
    )
    await envio.start()
    try:
        _turno("case-1", "1" * 32)
        # La primera entrega falla (500) y el ciclo sigue: lo siguiente si llega.
        await _hasta(lambda: falso.envios >= 1)
        _turno("case-2")
        await _esperar(falso.llego)
    finally:
        await envio.stop()

    assert falso.envios >= 2
    assert "traces.export_failed" in _estado_limpio.getvalue()
    perdido = await api.summary_by_trace("1" * 32, tenant_id="stonecroft", visitor_key_hash="dueno")
    assert perdido is not None
    assert perdido.status is TraceSummaryStatus.LOST


async def test_una_excepcion_inesperada_se_registra_y_el_ciclo_sigue(
    monkeypatch: pytest.MonkeyPatch, _estado_limpio: io.StringIO
) -> None:
    llamadas = 0
    original = export.export_pending

    async def rota(**argumentos: Any) -> export.ExportResult:
        nonlocal llamadas
        llamadas += 1
        if llamadas == 1:
            msg = "algo que nadie previo"
            raise RuntimeError(msg)
        return await original(**argumentos)

    monkeypatch.setattr(export, "export_pending", rota)
    falso = FalsoLangfuse()
    envio = _envio(falso)
    await envio.start()
    try:
        _turno()
        await _esperar(falso.llego)
    finally:
        await envio.stop()

    assert llamadas >= 2
    assert "traces.export_cycle_failed" in _estado_limpio.getvalue()
    assert "RuntimeError" in _estado_limpio.getvalue()


async def test_cada_traza_se_entrega_sola_y_un_destino_caido_corta_el_resto_del_ciclo() -> None:
    """Un solo intento por ciclo contra un destino que no contesta, y todas las trazas perdidas."""
    falso = FalsoLangfuse(fallar_envios=99)
    export.install_transport(falso.transporte())
    for traza, caso in (("1" * 32, "case-1"), ("2" * 32, "case-2"), ("3" * 32, "case-3")):
        await api.open_summary(
            trace_id=traza, tenant_id="stonecroft", case_id=caso, visitor_key_hash="dueno"
        )
        _turno(caso, traza)

    resultado = await export.export_pending(settings=_ajustes())

    assert not resultado.ok
    assert resultado.failure == "transport"
    assert falso.envios == 1  # no se espero el plazo de las otras dos
    for traza in ("1" * 32, "2" * 32, "3" * 32):
        resumen = await api.summary_by_trace(
            traza, tenant_id="stonecroft", visitor_key_hash="dueno"
        )
        assert resumen is not None
        assert resumen.status is TraceSummaryStatus.LOST


async def test_dos_trazas_salen_en_dos_entregas() -> None:
    falso = FalsoLangfuse()
    export.install_transport(falso.transporte())
    _turno("case-1", "1" * 32)
    _turno("case-2", "2" * 32)

    resultado = await export.export_pending(settings=_ajustes())

    assert resultado.ok
    assert resultado.exported == 6
    assert falso.envios == 2
    trazas = [
        {t["traceId"] for t in lote["resourceSpans"][0]["scopeSpans"][0]["spans"]}
        for lote in falso.lotes
    ]
    assert trazas == [{"1" * 32}, {"2" * 32}]


# --- El enlace --------------------------------------------------------------------


async def test_al_arrancar_se_pide_el_proyecto_una_vez_y_queda_el_enlace() -> None:
    falso = FalsoLangfuse()
    envio = _envio(falso)

    await envio.start()
    try:
        await _hasta(links.available)
        await asyncio.sleep(0.15)  # varias vueltas mas: no vuelve a preguntar
    finally:
        await envio.stop()

    assert falso.consultas_de_proyecto == 1
    # Al apagar, el enlace se retira junto con el transporte.
    assert not links.available()


async def test_si_el_proyecto_no_contesta_no_hay_enlace_se_avisa_una_vez_y_se_reintenta(
    _estado_limpio: io.StringIO,
) -> None:
    falso = FalsoLangfuse(fallar_proyecto=3)
    envio = _envio(falso)

    await envio.start()
    try:
        await _hasta(links.available)
    finally:
        await envio.stop()

    assert falso.consultas_de_proyecto == 4
    # Tres fallos seguidos, un solo aviso: el registro no se llena de lo mismo.
    assert _estado_limpio.getvalue().count("traces.langfuse_project_unavailable") == 1


def test_la_direccion_de_una_traza_lleva_host_proyecto_y_traza_sin_poder_cambiar_la_ruta() -> None:
    enlaces = links.TraceLinks(host=HOST + "/", project_id="proy1")

    assert enlaces.url_for("123") == f"{HOST}/project/proy1/traces/123"
    # Un identificador con barras o consulta no cambia la ruta ni anade nada.
    assert enlaces.url_for("../x?a=b") == f"{HOST}/project/proy1/traces/..%2Fx%3Fa%3Db"


def test_sin_enlace_enchufado_no_hay_direccion() -> None:
    links.install(None)

    assert links.trace_url("123") is None
