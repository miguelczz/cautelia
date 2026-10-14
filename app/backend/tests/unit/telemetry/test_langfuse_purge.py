"""El purgador de las trazas sabe borrar de Langfuse, y un Langfuse que no responde no cierra la demo.

Sin red: o un transporte de mentira que dice lo que alcanzo a borrar, o el de Langfuse de verdad
sobre un transporte de `httpx2` falso. Lo que importa de la rama que falla (2026-10-14): el
purgador no levanta --una corrida `partial` cerraria el chat y la voz a casos nuevos durante un
dia por un backend de trazas caido, que es lo que BR4.8 prohibe--, devuelve solo lo que el
backend acepto borrar y lo dice en `traces.backend_purge_incomplete`.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import io
import json
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import httpx2
import pytest

from untangle import observability
from untangle.compliance.redaction.api import Redacted
from untangle.demo_operations.models import ResetOutcome
from untangle.demo_operations.reset import accepts_new_cases, run_reset
from untangle.providers.adapters.langfuse import LangfuseTransport
from untangle.server import demo_reset, trace_shipping
from untangle.settings import Settings
from untangle.telemetry.traces import export
from untangle.telemetry.traces.purge import (
    TRACES_BACKEND_PURGER,
)
from untangle.tenancy.models import PurgeResult, VisitorDataPurger

CORTE = datetime(2026, 10, 14, 8, 0, tzinfo=UTC)
CLAVE_PUBLICA = "pk-lf-x"
CLAVE_SECRETA = "sk-lf-x"


def _ajustes() -> Settings:
    return Settings(env="ci", traces_endpoint=None)


@pytest.fixture(autouse=True)
def _estado() -> Iterator[io.StringIO]:
    export.install_transport(None)
    eventos = io.StringIO()
    observability.set_stream(eventos)
    yield eventos
    observability.set_stream(sys.stdout)
    export.install_transport(None)


@dataclasses.dataclass
class BackendRemoto:
    """Un transporte que sabe borrar lo entregado, y dice lo que alcanzo."""

    resultado: export.RemotePurge
    llamadas: list[tuple[datetime, bool]] = dataclasses.field(default_factory=list)

    def send(self, payload: Redacted) -> None: ...

    def purge_before(self, cutoff: datetime, *, dry_run: bool = False) -> export.RemotePurge:
        self.llamadas.append((cutoff, dry_run))
        return self.resultado


def _purgador() -> VisitorDataPurger:
    return dataclasses.replace(TRACES_BACKEND_PURGER, settings_factory=_ajustes)


# --- Un backend que sabe borrar ---------------------------------------------------


async def test_borra_lo_anterior_al_corte_y_cuenta_lo_que_el_backend_acepto() -> None:
    backend = BackendRemoto(export.RemotePurge(deleted=12))
    export.install_transport(backend)

    resultado = await _purgador().purge(older_than=CORTE)

    assert resultado == PurgeResult(name="traces_backend", deleted=12, kept=0)
    assert backend.llamadas == [(CORTE, False)]


async def test_el_ensayo_llega_al_backend_como_ensayo() -> None:
    backend = BackendRemoto(export.RemotePurge(deleted=4))
    export.install_transport(backend)

    resultado = await _purgador().purge(older_than=CORTE, dry_run=True)

    assert resultado.deleted == 4
    assert backend.llamadas == [(CORTE, True)]


async def test_si_el_backend_no_termino_el_purgador_no_levanta_y_dice_cuanto_alcanzo(
    _estado: io.StringIO,
) -> None:
    export.install_transport(BackendRemoto(export.RemotePurge(deleted=3, failure="list_http_503")))

    resultado = await _purgador().purge(older_than=CORTE)

    assert resultado.deleted == 3
    # "No pude borrar" no se confunde con "borre todo": lo dice su propio evento, con la razon.
    evento = _estado.getvalue()
    assert '"event": "traces.backend_purge_incomplete"' in evento
    assert '"deleted": 3' in evento
    assert '"failure": "list_http_503"' in evento


# --- Lo que el reinicio hace con eso ------------------------------------------------


@dataclasses.dataclass(frozen=True)
class PurgadorSano:
    """Otro dueno del registro, que borra lo suyo sin problema."""

    name: str = "otro"
    tables: tuple[str, ...] = ("una_tabla",)

    async def purge(self, *, older_than: datetime, dry_run: bool = False) -> PurgeResult:
        return PurgeResult(name=self.name, deleted=5, kept=1)


def _reloj() -> datetime:
    return CORTE + timedelta(minutes=1)


async def test_un_langfuse_que_no_responde_no_cierra_la_demo_a_casos_nuevos(
    _estado: io.StringIO,
) -> None:
    """Los otros borran lo suyo, la corrida reinicia la ventana de 24 horas y queda el aviso."""
    export.install_transport(BackendRemoto(export.RemotePurge(deleted=0, failure="list_timeout")))

    corrida = await run_reset(
        [PurgadorSano(), _purgador()],
        clock=_reloj,
        older_than=CORTE,
        reset_run_id="reset-1",
    )

    assert corrida.outcome is ResetOutcome.SUCCEEDED
    assert corrida.failures == ()
    sano = next(fila for fila in corrida.purgers if fila.name == "otro")
    assert (sano.deleted, sano.kept) == (5, 1)
    assert accepts_new_cases([corrida], now=CORTE + timedelta(hours=1))
    assert '"failure": "list_timeout"' in _estado.getvalue()


async def test_un_langfuse_que_termino_deja_la_corrida_limpia() -> None:
    export.install_transport(BackendRemoto(export.RemotePurge(deleted=9)))

    corrida = await run_reset(
        [PurgadorSano(), _purgador()],
        clock=_reloj,
        older_than=CORTE,
        reset_run_id="reset-2",
    )

    assert corrida.outcome is ResetOutcome.SUCCEEDED
    assert accepts_new_cases([corrida], now=CORTE + timedelta(hours=1))


# --- Con el transporte de Langfuse de verdad, sobre una red de mentira -------------------


def _langfuse(manejador: httpx2.MockTransport) -> LangfuseTransport:
    return LangfuseTransport(
        public_key=CLAVE_PUBLICA,
        secret_key=CLAVE_SECRETA,
        host="https://us.cloud.langfuse.com",
        network=manejador,
    )


async def test_langfuse_que_rechaza_el_borrado_no_se_cuenta_como_borrado(
    _estado: io.StringIO,
) -> None:
    """Lo que Langfuse rechazo no es borrado: el conteo es cero y el aviso dice por que."""

    def manejador(peticion: httpx2.Request) -> httpx2.Response:
        if peticion.method == "GET":
            return httpx2.Response(
                200,
                json={"data": [{"traceId": "1" * 32}, {"traceId": "2" * 32}], "meta": {}},
            )
        return httpx2.Response(500)

    export.install_transport(_langfuse(httpx2.MockTransport(manejador)))

    resultado = await _purgador().purge(older_than=CORTE)

    assert resultado.deleted == 0
    assert '"failure": "delete_http_500"' in _estado.getvalue()


async def test_langfuse_caido_no_cuenta_nada_y_langfuse_sano_cuenta_lo_que_acepto(
    _estado: io.StringIO,
) -> None:
    borrados: list[list[str]] = []

    def sano(peticion: httpx2.Request) -> httpx2.Response:
        if peticion.method == "GET":
            return httpx2.Response(
                200,
                json={"data": [{"traceId": "1" * 32}, {"traceId": "2" * 32}], "meta": {}},
            )
        borrados.append(json.loads(peticion.content)["traceIds"])
        return httpx2.Response(200, json={"message": "ok"})

    def caido(_: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("sin red")

    export.install_transport(_langfuse(httpx2.MockTransport(caido)))
    assert (await _purgador().purge(older_than=CORTE)).deleted == 0
    assert '"failure": "list_ConnectError"' in _estado.getvalue()

    export.install_transport(_langfuse(httpx2.MockTransport(sano)))
    resultado = await _purgador().purge(older_than=CORTE)

    assert resultado.deleted == 2
    assert borrados == [["1" * 32, "2" * 32]]


def test_el_proceso_del_reinicio_instala_el_transporte_de_langfuse_para_que_el_purgador_lo_vea() -> (
    None
):
    """`demo_reset` no pasa por `build_app`: sin esto el purgador miraria el archivo de la corrida."""
    ajustes = Settings(
        env="ci",
        langfuse_public_key=CLAVE_PUBLICA,
        langfuse_secret_key=CLAVE_SECRETA,
        langfuse_host="https://us.cloud.langfuse.com",
    )

    transporte = trace_shipping.install_transport(ajustes)
    try:
        assert isinstance(export.transport_for(ajustes), export.PurgeableSpanTransport)
    finally:
        trace_shipping.release_transport(transporte)

    assert isinstance(export.transport_for(_ajustes()), export.FileTransport)
    assert trace_shipping.install_transport(_ajustes()) is None


def test_el_reinicio_nocturno_instala_el_transporte_antes_de_barrer() -> None:
    """Que `demo_reset.main` lo llame no se prueba corriendo la base: se comprueba en su codigo."""
    arbol = ast.parse(inspect.getsource(demo_reset.main))
    llamadas = {
        f"{nodo.func.value.id}.{nodo.func.attr}"
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Call)
        and isinstance(nodo.func, ast.Attribute)
        and isinstance(nodo.func.value, ast.Name)
    }

    assert {"trace_shipping.install_transport", "trace_shipping.release_transport"} <= llamadas
