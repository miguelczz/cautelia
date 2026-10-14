"""El transporte de Langfuse: autenticacion, ruta, fallos y que la clave no salga.

Sin red: el transporte de `httpx2` es uno falso que responde lo que cada prueba
dice, y sin Langfuse de verdad. Una prueba que le hablara gastaria el cupo del plan
gratuito y dependeria de un tercero.
"""

from __future__ import annotations

import base64
import io
import json
import sys
import traceback
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2
import pytest

from untangle import observability
from untangle.compliance.redaction import detector as deteccion
from untangle.compliance.redaction.api import Redacted
from untangle.compliance.redaction.api import redact as redactar
from untangle.providers.adapters.langfuse import LangfuseError, LangfuseTransport, build_transport
from untangle.settings import Settings
from untangle.telemetry.traces import api, export
from untangle.telemetry.traces.models import SpanLevel

HOST = "https://us.cloud.langfuse.com"
CLAVE_PUBLICA = "pk-lf-publica-de-prueba"
CLAVE_SECRETA = "sk-lf-secreta-de-prueba"
AUTORIZACION = "Basic " + base64.b64encode(f"{CLAVE_PUBLICA}:{CLAVE_SECRETA}".encode()).decode()

Manejador = Callable[[httpx2.Request], httpx2.Response]


def _transporte(manejador: Manejador) -> LangfuseTransport:
    return LangfuseTransport(
        public_key=CLAVE_PUBLICA,
        secret_key=CLAVE_SECRETA,
        host=HOST,
        network=httpx2.MockTransport(manejador),
    )


@pytest.fixture(scope="module", autouse=True)
def _detector_cargado() -> Iterator[None]:
    """Un `Redacted` solo lo produce la redaccion de verdad: la prueba se lo pide a ella."""
    deteccion.install(deteccion.load())
    yield
    deteccion.reset()


def _lote(texto: str = "{}") -> Redacted:
    """Un lote ya redactado, por el unico camino que lo fabrica (BR1.8)."""
    return redactar(texto, language="en")


@pytest.fixture(autouse=True)
def _eventos() -> Iterator[io.StringIO]:
    """Lo que el aplicativo escribe como evento tecnico, para poder buscar en el la clave."""
    salida = io.StringIO()
    observability.set_stream(salida)
    yield salida
    observability.set_stream(sys.stdout)


# --- Entregar ------------------------------------------------------------------


def test_el_lote_sale_por_post_a_la_ruta_otlp_con_autenticacion_y_json() -> None:
    vistas: list[httpx2.Request] = []

    def manejador(peticion: httpx2.Request) -> httpx2.Response:
        vistas.append(peticion)
        return httpx2.Response(200, json={})

    lote = _lote('{"resourceSpans": []}')
    _transporte(manejador).send(lote)

    (peticion,) = vistas
    assert peticion.method == "POST"
    assert str(peticion.url) == f"{HOST}/api/public/otel/v1/traces"
    assert peticion.headers["authorization"] == AUTORIZACION
    assert peticion.headers["content-type"] == "application/json"
    assert peticion.headers["x-langfuse-ingestion-version"] == "4"
    assert peticion.content == str(lote).encode()


@pytest.mark.parametrize("estado", [400, 401, 403, 413, 429, 500, 503])
def test_una_respuesta_que_no_es_2xx_es_un_fallo(estado: int) -> None:
    transporte = _transporte(lambda _: httpx2.Response(estado, json={"error": "no"}))

    with pytest.raises(LangfuseError, match=f"http_{estado}"):
        transporte.send(_lote())


@pytest.mark.parametrize("estado", [200, 201, 202, 207])
def test_cualquier_2xx_es_una_entrega(estado: int) -> None:
    _transporte(lambda _: httpx2.Response(estado, json={})).send(_lote())


def test_un_plazo_agotado_y_una_red_caida_son_fallos_con_codigo_corto() -> None:
    def tarda(_: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("la direccion con la clave no debe salir")

    def cae(_: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("tampoco esta")

    with pytest.raises(LangfuseError, match=r"^timeout$"):
        _transporte(tarda).send(_lote())
    with pytest.raises(LangfuseError, match=r"^ConnectError$"):
        _transporte(cae).send(_lote())


# --- La clave no sale -----------------------------------------------------------


def _todo_lo_visible(error: BaseException) -> str:
    return " ".join(
        [
            str(error),
            repr(error),
            "".join(traceback.format_exception(error)),
            repr(error.__context__),
            repr(error.__cause__),
        ]
    )


def _rechaza_con_la_clave_en_el_cuerpo(_: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(401, text=f"clave {CLAVE_SECRETA} invalida")


def _red_que_nombra_la_clave(_: httpx2.Request) -> httpx2.Response:
    raise httpx2.ConnectError(f"{HOST} {CLAVE_SECRETA}")


def _plazo_que_nombra_la_cabecera(_: httpx2.Request) -> httpx2.Response:
    raise httpx2.ReadTimeout(AUTORIZACION)


@pytest.mark.parametrize(
    "falla",
    [_rechaza_con_la_clave_en_el_cuerpo, _red_que_nombra_la_clave, _plazo_que_nombra_la_cabecera],
)
def test_la_clave_no_aparece_en_ningun_error(falla: Manejador) -> None:
    with pytest.raises(LangfuseError) as error:
        _transporte(falla).send(_lote())

    visible = _todo_lo_visible(error.value)
    for secreto in (CLAVE_SECRETA, CLAVE_PUBLICA, AUTORIZACION.split()[1]):
        assert secreto not in visible


def test_la_clave_no_aparece_en_la_representacion_del_objeto() -> None:
    transporte = _transporte(lambda _: httpx2.Response(200))

    texto = f"{transporte!r} {transporte} {vars(transporte).keys()}"

    assert HOST in texto
    for secreto in (CLAVE_SECRETA, CLAVE_PUBLICA, AUTORIZACION.split()[1]):
        assert secreto not in texto
    # No hay atributo propio donde la clave quede: vive solo en las cabeceras del cliente.
    propios = {nombre: valor for nombre, valor in vars(transporte).items() if nombre != "_cliente"}
    assert all(CLAVE_SECRETA not in str(valor) for valor in propios.values())


def test_un_fallo_de_entrega_no_deja_la_clave_en_los_eventos_de_la_exportacion(
    _eventos: io.StringIO,
) -> None:
    """Por el camino de verdad: `export_batch` atrapa el fallo y lo escribe como evento."""
    try:
        export.install_transport(_transporte(lambda _: httpx2.Response(500, text=CLAVE_SECRETA)))
        ahora = datetime(2026, 10, 14, 15, 0, tzinfo=UTC)
        tramo = api.FinishedSpan(
            trace_id="48215069371502846913720465183927",
            tenant_id="stonecroft",
            span_id="1" * 32,
            parent_span_id=None,
            name="turn",
            level=SpanLevel.TURN,
            started_at=ahora,
            ended_at=ahora + timedelta(milliseconds=5),
            duration_ms=5,
            attributes={},
        )

        resultado = export.export_batch((tramo,), settings=Settings(env="ci"))
    finally:
        export.install_transport(None)

    assert not resultado.ok
    assert resultado.failure == "transport"
    eventos = _eventos.getvalue()
    assert "traces.export_failed" in eventos
    for secreto in (CLAVE_SECRETA, CLAVE_PUBLICA, AUTORIZACION.split()[1]):
        assert secreto not in eventos


# --- El identificador del proyecto ----------------------------------------------


def test_el_identificador_del_proyecto_sale_de_la_primera_fila() -> None:
    vistas: list[httpx2.Request] = []

    def manejador(peticion: httpx2.Request) -> httpx2.Response:
        vistas.append(peticion)
        return httpx2.Response(
            200, json={"data": [{"id": "clx1proyecto", "name": "cautelia-local"}]}
        )

    assert _transporte(manejador).project_id() == "clx1proyecto"

    (peticion,) = vistas
    assert peticion.method == "GET"
    assert str(peticion.url) == f"{HOST}/api/public/projects"
    assert peticion.headers["authorization"] == AUTORIZACION


@pytest.mark.parametrize(
    "cuerpo",
    [{}, {"data": []}, {"data": [{}]}, {"data": [{"id": 7}]}, {"data": [{"id": ""}]}, []],
)
def test_una_respuesta_de_proyectos_con_otra_forma_es_un_fallo(cuerpo: Any) -> None:
    with pytest.raises(LangfuseError, match="projects_shape"):
        _transporte(lambda _: httpx2.Response(200, json=cuerpo)).project_id()


def test_un_proyecto_pedido_con_una_clave_rechazada_es_un_fallo() -> None:
    with pytest.raises(LangfuseError, match="http_401"):
        _transporte(lambda _: httpx2.Response(401)).project_id()


# --- Borrar lo anterior a un corte ------------------------------------------------

CORTE = datetime(2026, 10, 14, 8, 0, tzinfo=UTC)


class FalsoLangfuse:
    """Un Langfuse en memoria que lista y borra, y anota que le pidieron."""

    def __init__(
        self,
        ids: list[str],
        *,
        falla_lista_en: int | None = None,
        falla_borrado_en: int | None = None,
    ) -> None:
        self.ids = ids
        self.falla_lista_en = falla_lista_en
        self.falla_borrado_en = falla_borrado_en
        self.listados: list[dict[str, str]] = []
        self.borrados: list[list[str]] = []
        self.autorizaciones: set[str] = set()

    def __call__(self, peticion: httpx2.Request) -> httpx2.Response:
        self.autorizaciones.add(peticion.headers["authorization"])
        if peticion.method == "GET":
            return self._lista(peticion)
        if peticion.method == "DELETE":
            return self._borra(peticion)
        return httpx2.Response(405)

    def _lista(self, peticion: httpx2.Request) -> httpx2.Response:
        """La lista de observaciones v2: varias por traza, y un cursor mientras queden."""
        consulta = dict(peticion.url.params)
        self.listados.append(consulta)
        if self.falla_lista_en == len(self.listados):
            return httpx2.Response(503)
        desde, limite = int(consulta.get("cursor", "0")), int(consulta["limit"])
        observaciones = [i for i in self.ids for _ in range(2)]  # el turno y una llamada
        trozo = observaciones[desde : desde + limite]
        hay_mas = desde + limite < len(observaciones)
        return httpx2.Response(
            200,
            json={
                "data": [{"id": f"obs-{n}", "traceId": i} for n, i in enumerate(trozo)],
                "meta": {"cursor": str(desde + limite)} if hay_mas else {},
            },
        )

    def _borra(self, peticion: httpx2.Request) -> httpx2.Response:
        if self.falla_borrado_en == len(self.borrados) + 1:
            self.borrados.append([])
            return httpx2.Response(500)
        self.borrados.append(json.loads(peticion.content)["traceIds"])
        return httpx2.Response(200, json={"message": "Traces deleted"})


def _ids(cuantos: int) -> list[str]:
    return [f"{n:032d}" for n in range(1, cuantos + 1)]


def test_el_borrado_lista_lo_anterior_al_corte_y_lo_borra_en_un_solo_pedido() -> None:
    falso = FalsoLangfuse(_ids(3))

    resultado = _transporte(falso).purge_before(CORTE)

    assert (resultado.deleted, resultado.failure) == (3, None)
    assert resultado.complete
    assert falso.borrados == [_ids(3)]
    # La pregunta lleva los dos extremos en UTC, al segundo, y pide solo lo esencial.
    (consulta,) = falso.listados
    assert consulta["toStartTime"] == "2026-10-14T08:00:00Z"
    assert consulta["fromStartTime"] == "2026-07-16T08:00:00Z"
    assert (consulta["limit"], consulta["fields"]) == ("1000", "core")
    assert "cursor" not in consulta
    assert falso.autorizaciones == {AUTORIZACION}


def test_el_borrado_sigue_el_cursor_antes_de_borrar_y_borra_cada_traza_una_vez() -> None:
    falso = FalsoLangfuse(_ids(1_120))

    resultado = _transporte(falso).purge_before(CORTE)

    assert (resultado.deleted, resultado.failure) == (1_120, None)
    # Dos observaciones por traza, de a mil por pagina: tres paginas, cada una con su cursor.
    assert [consulta.get("cursor") for consulta in falso.listados] == [None, "1000", "2000"]
    assert [len(lote) for lote in falso.borrados] == [500, 500, 120]
    assert [i for lote in falso.borrados for i in lote] == _ids(1_120)


def test_sin_nada_anterior_al_corte_no_hay_nada_que_borrar_y_no_es_un_fallo() -> None:
    falso = FalsoLangfuse([])

    resultado = _transporte(falso).purge_before(CORTE)

    assert (resultado.deleted, resultado.failure) == (0, None)
    assert falso.borrados == []


def test_el_ensayo_cuenta_y_no_borra() -> None:
    falso = FalsoLangfuse(_ids(7))

    resultado = _transporte(falso).purge_before(CORTE, dry_run=True)

    assert (resultado.deleted, resultado.failure) == (7, None)
    assert falso.borrados == []


def test_si_langfuse_deja_de_contestar_a_mitad_de_la_lista_se_borra_lo_listado_y_se_dice() -> None:
    falso = FalsoLangfuse(_ids(1_200), falla_lista_en=2)

    resultado = _transporte(falso).purge_before(CORTE)

    assert resultado.deleted == 500  # solo las trazas de la primera pagina (mil observaciones)
    assert resultado.failure == "list_http_503"
    assert not resultado.complete
    assert falso.borrados == [_ids(500)]


def test_si_langfuse_rechaza_un_borrado_no_se_cuenta_como_borrado() -> None:
    """Lo que Langfuse rechazo no se cuenta, y el primer fallo detiene lo que sigue."""
    falso = FalsoLangfuse(_ids(1_200), falla_borrado_en=2)

    resultado = _transporte(falso).purge_before(CORTE)

    assert resultado.deleted == 500  # el primer pedido si se acepto; el segundo no
    assert resultado.failure == "delete_http_500"
    assert len(falso.borrados) == 2  # no se intento el tercero


def test_una_clave_rechazada_en_la_lista_no_borra_nada_y_lo_dice() -> None:
    resultado = _transporte(lambda _: httpx2.Response(401)).purge_before(CORTE)

    assert (resultado.deleted, resultado.failure) == (0, "list_http_401")


@pytest.mark.parametrize("cuerpo", [{}, {"data": None, "meta": {}}, [], {"data": [], "meta": 3}])
def test_una_lista_con_otra_forma_no_borra_nada_y_lo_dice(cuerpo: Any) -> None:
    resultado = _transporte(lambda _: httpx2.Response(200, json=cuerpo)).purge_before(CORTE)

    assert resultado.deleted == 0
    assert resultado.failure == "list_shape"


def test_el_transporte_cumple_los_dos_protocolos_que_el_exportador_y_el_purgador_piden() -> None:
    transporte = _transporte(lambda _: httpx2.Response(200))

    assert isinstance(transporte, export.PurgeableSpanTransport)
    assert transporte.wire_format is export.WireFormat.LANGFUSE


# --- Construirlo ------------------------------------------------------------------


def test_sin_las_tres_variables_no_se_construye_nada() -> None:
    ajustes = Settings(env="ci", langfuse_public_key=CLAVE_PUBLICA)

    assert build_transport(ajustes) is None


def test_con_las_tres_variables_se_construye_uno_que_apunta_al_host_dicho() -> None:
    ajustes = Settings(
        env="ci",
        langfuse_public_key=CLAVE_PUBLICA,
        langfuse_secret_key=CLAVE_SECRETA,
        langfuse_host=HOST,
    )

    transporte = build_transport(ajustes)

    assert transporte is not None
    try:
        assert HOST in repr(transporte)
        assert CLAVE_SECRETA not in repr(transporte)
    finally:
        transporte.close()
