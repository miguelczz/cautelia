"""El chequeo diario del sitio publicado (`scripts/chequeo_publico.py`, 2026-10-13).

Lo que se prueba es lo que decide: con lo ya leido --los JSON y la hora--, que
veredicto sale y con que codigo de salida. Las funciones puras no tocan la red; la
capa que la toca se prueba contra un servidor local y nunca contra el sitio
publicado.

**Los cuerpos de prueba salen de los modelos del servidor**, no de diccionarios
escritos a mano: `HealthReport` y `BudgetState` serializados como los serializa la
API. Si el sitio cambia el nombre de un campo o de un estado, el guion deja de
entenderlo y esta prueba cae en vez de enterarse la noche en que haga falta.

El guion no es un modulo importable (vive en `scripts/`), asi que se carga por ruta.
"""

from __future__ import annotations

import http.server
import importlib.util
import sys
import threading
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from pydantic_core import to_jsonable_python

from untangle import paths
from untangle.server import health
from untangle.telemetry.spend import budget
from untangle.telemetry.spend.models import BudgetStatus, BudgetWindow

AHORA = datetime(2026, 10, 13, 12, 30, tzinfo=UTC)


@pytest.fixture(scope="module")
def chequeo() -> Iterator[ModuleType]:
    ruta = paths.repo_root() / "scripts" / "chequeo_publico.py"
    spec = importlib.util.spec_from_file_location("chequeo_publico", ruta)
    assert spec is not None
    assert spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    # Los dataclasses del guion buscan su modulo en `sys.modules` al resolver tipos.
    sys.modules[spec.name] = modulo
    try:
        spec.loader.exec_module(modulo)
        yield modulo
    finally:
        sys.modules.pop(spec.name, None)


# --- Cuerpos con la forma real ---------------------------------------------------


def _salud(reinicio: health.DemoResetCheck | None = None) -> dict[str, Any]:
    """El cuerpo de `GET /api/health/ready`, serializado por el modelo del servidor."""
    checks = health.HealthChecks(
        database=health.DatabaseStatus.OK,
        tenants=3,
        surfaces={},
        providers=health.ProviderIndicators(priced_units=9, uses_with_key=("chat",)),
        demo_reset=reinicio
        or health.DemoResetCheck(
            status=health.DemoResetStatus.CURRENT, last_successful_at=AHORA - timedelta(hours=5)
        ),
    )
    informe = health.HealthReport(version="7bdb096", checks=checks)
    cuerpo: dict[str, Any] = informe.model_dump(mode="json")
    return cuerpo


def _salud_sin_reinicio() -> dict[str, Any]:
    """Lo que devuelve la version publicada antes de que existiera el campo."""
    cuerpo = _salud()
    del cuerpo["checks"]["demo_reset"]
    return cuerpo


def _reinicio(estado: health.DemoResetStatus, horas_atras: float | None) -> dict[str, Any]:
    ultimo = None if horas_atras is None else AHORA - timedelta(hours=horas_atras)
    return _salud(health.DemoResetCheck(status=estado, last_successful_at=ultimo))


def _ventana(gastado: str, **cambios: Any) -> BudgetWindow:
    base: dict[str, Any] = {
        "window_start": date(2026, 9, 16),
        "window_end": date(2026, 12, 15),
        "billable_spent_usd": Decimal(gastado),
        "cap_usd": Decimal("40.00"),
        "alert_usd": Decimal("24.00"),
        "recording_reserve_usd": Decimal("0.225"),
        "recording_reserve_status": "measured",
        "updated_at": datetime(2026, 10, 1, tzinfo=UTC),
    }
    return BudgetWindow(**(base | cambios))


def _gasto(ventana: BudgetWindow, esperado: BudgetStatus) -> dict[str, Any]:
    """El cuerpo de `GET /api/spend` con la ventana real y su estado calculado por el servidor."""
    foto = budget.state(ventana)
    # La ventana de prueba tiene que producir el estado que dice: si no, la prueba miente.
    assert foto.status is esperado
    return {
        "window": foto.model_dump(mode="json"),
        "alert_sent_at": to_jsonable_python(ventana.alert_sent_at),
    }


def _gasto_en(estado: BudgetStatus, *, enviada: datetime | None = None) -> dict[str, Any]:
    ventanas = {
        BudgetStatus.OK: _ventana("1.00"),
        BudgetStatus.ALERTED: _ventana("25.00", alert_sent_at=enviada),
        BudgetStatus.EXHAUSTED: _ventana("40.00", alert_sent_at=enviada),
        BudgetStatus.UNMEASURED: _ventana(
            "1.00", recording_reserve_usd=None, recording_reserve_status="not_measured"
        ),
    }
    return _gasto(ventanas[estado], estado)


# --- La salud ----------------------------------------------------------------------


def test_un_sitio_listo_que_responde_esta_bien(chequeo: ModuleType) -> None:
    veredicto = chequeo.comprobar_salud(chequeo.Lectura(cuerpo=_salud()))

    assert veredicto.resultado is chequeo.Resultado.BIEN
    assert "7bdb096" in veredicto.razon


def test_un_sitio_que_no_responde_falla_con_la_razon_de_la_lectura(chequeo: ModuleType) -> None:
    veredicto = chequeo.comprobar_salud(chequeo.Lectura(problema="respondio HTTP 503"))

    assert veredicto.resultado is chequeo.Resultado.FALLA
    assert "503" in veredicto.razon


@pytest.mark.parametrize(
    ("cuerpo", "fragmento"),
    [
        (["no", "es", "un", "objeto"], "no es un objeto"),
        ({"status": "starting", "checks": {}}, "starting"),
        ({"status": "ready"}, "checks"),
        ({"status": "ready", "checks": None}, "checks"),
    ],
    ids=["no-es-objeto", "no-esta-listo", "sin-checks", "checks-nulo"],
)
def test_un_cuerpo_al_que_le_falta_lo_esperado_falla_sin_excepcion(
    chequeo: ModuleType, cuerpo: object, fragmento: str
) -> None:
    veredicto = chequeo.comprobar_salud(chequeo.Lectura(cuerpo=cuerpo))

    assert veredicto.resultado is chequeo.Resultado.FALLA
    assert fragmento in veredicto.razon


# --- El reinicio nocturno --------------------------------------------------------


def test_un_reinicio_al_dia_esta_bien_y_dice_cuando_fue(chequeo: ModuleType) -> None:
    salud = chequeo.Lectura(cuerpo=_reinicio(health.DemoResetStatus.CURRENT, 5))

    veredicto = chequeo.comprobar_reinicio(salud, ahora=AHORA)

    assert veredicto.resultado is chequeo.Resultado.BIEN
    assert "2026-10-13 07:30 UTC" in veredicto.razon
    assert "hace 5 horas" in veredicto.razon


def test_un_reinicio_vencido_falla_y_dice_desde_cuando(chequeo: ModuleType) -> None:
    salud = chequeo.Lectura(cuerpo=_reinicio(health.DemoResetStatus.OVERDUE, 30))

    veredicto = chequeo.comprobar_reinicio(salud, ahora=AHORA)

    assert veredicto.resultado is chequeo.Resultado.FALLA
    assert "2026-10-12 06:30 UTC" in veredicto.razon
    assert "hace 30 horas" in veredicto.razon
    assert "vencido" in veredicto.razon


def test_un_reinicio_vencido_sin_ningun_exitoso_conocido_tambien_falla(
    chequeo: ModuleType,
) -> None:
    salud = chequeo.Lectura(cuerpo=_reinicio(health.DemoResetStatus.OVERDUE, None))

    veredicto = chequeo.comprobar_reinicio(salud, ahora=AHORA)

    assert veredicto.resultado is chequeo.Resultado.FALLA
    assert "ningun reinicio exitoso" in veredicto.razon


def test_un_reinicio_que_el_sitio_no_pudo_leer_falla(chequeo: ModuleType) -> None:
    salud = chequeo.Lectura(cuerpo=_reinicio(health.DemoResetStatus.UNREADABLE, None))

    veredicto = chequeo.comprobar_reinicio(salud, ahora=AHORA)

    assert veredicto.resultado is chequeo.Resultado.FALLA
    assert "no pudo leer" in veredicto.razon


def test_un_campo_ausente_se_dice_como_no_medida_y_no_falla(chequeo: ModuleType) -> None:
    """La version publicada todavia no trae el campo: no se mide, y no suena la alarma."""
    salud = chequeo.Lectura(cuerpo=_salud_sin_reinicio())

    veredicto = chequeo.comprobar_reinicio(salud, ahora=AHORA)

    assert veredicto.resultado is chequeo.Resultado.NO_MEDIDA
    assert "demo_reset" in veredicto.razon
    assert chequeo.codigo_de_salida([veredicto]) == 0


def test_si_la_salud_no_se_leyo_el_reinicio_no_se_midio(chequeo: ModuleType) -> None:
    """La caida ya la dice el veredicto de la salud: aqui no se cuenta dos veces."""
    veredicto = chequeo.comprobar_reinicio(chequeo.Lectura(problema="HTTP 503"), ahora=AHORA)

    assert veredicto.resultado is chequeo.Resultado.NO_MEDIDA


def test_un_estado_de_reinicio_desconocido_falla_nombrandolo(chequeo: ModuleType) -> None:
    cuerpo = _salud()
    cuerpo["checks"]["demo_reset"]["status"] = "paused"

    veredicto = chequeo.comprobar_reinicio(chequeo.Lectura(cuerpo=cuerpo), ahora=AHORA)

    assert veredicto.resultado is chequeo.Resultado.FALLA
    assert "'paused'" in veredicto.razon


@pytest.mark.parametrize("malformado", [None, "current", 7, {"status": 3}, {}])
def test_un_campo_de_reinicio_con_otra_forma_falla_sin_excepcion(
    chequeo: ModuleType, malformado: object
) -> None:
    cuerpo = _salud()
    cuerpo["checks"]["demo_reset"] = malformado

    veredicto = chequeo.comprobar_reinicio(chequeo.Lectura(cuerpo=cuerpo), ahora=AHORA)

    assert veredicto.resultado is chequeo.Resultado.FALLA
    assert "forma esperada" in veredicto.razon


def test_solo_se_relee_la_salud_cuando_el_reinicio_salio_ilegible(chequeo: ModuleType) -> None:
    ilegible = chequeo.Lectura(cuerpo=_reinicio(health.DemoResetStatus.UNREADABLE, None))
    vencido = chequeo.Lectura(cuerpo=_reinicio(health.DemoResetStatus.OVERDUE, 30))

    assert chequeo.reinicio_ilegible(ilegible)
    assert not chequeo.reinicio_ilegible(vencido)
    assert not chequeo.reinicio_ilegible(chequeo.Lectura(cuerpo=_salud_sin_reinicio()))
    assert not chequeo.reinicio_ilegible(chequeo.Lectura(problema="HTTP 503"))


# --- El gasto ---------------------------------------------------------------------


def test_sin_ventana_de_presupuesto_el_gasto_no_se_mide_y_no_falla(chequeo: ModuleType) -> None:
    gasto = chequeo.Lectura(cuerpo={"window": None, "alert_sent_at": None})

    veredicto = chequeo.comprobar_gasto(gasto, ahora=AHORA)

    assert veredicto.resultado is chequeo.Resultado.NO_MEDIDA
    assert chequeo.codigo_de_salida([veredicto]) == 0


def test_un_gasto_por_debajo_de_la_alerta_esta_bien(chequeo: ModuleType) -> None:
    gasto = chequeo.Lectura(cuerpo=_gasto_en(BudgetStatus.OK))

    assert chequeo.comprobar_gasto(gasto, ahora=AHORA).resultado is chequeo.Resultado.BIEN


def test_una_alerta_recien_cruzada_hace_fallar(chequeo: ModuleType) -> None:
    gasto = chequeo.Lectura(
        cuerpo=_gasto_en(BudgetStatus.ALERTED, enviada=AHORA - timedelta(hours=2))
    )

    veredicto = chequeo.comprobar_gasto(gasto, ahora=AHORA)

    assert veredicto.resultado is chequeo.Resultado.FALLA
    assert "alerta" in veredicto.razon
    assert "hace 2 horas" in veredicto.razon


def test_el_borde_de_las_26_horas_es_un_correo_y_no_uno_diario(chequeo: ModuleType) -> None:
    """A 25 h 59 min 59 s todavia falla; a las 26 h exactas y despues, solo se dice."""
    margen = timedelta(hours=26)

    def veredicto(edad: timedelta) -> Any:
        cuerpo = _gasto_en(BudgetStatus.ALERTED, enviada=AHORA - edad)
        return chequeo.comprobar_gasto(chequeo.Lectura(cuerpo=cuerpo), ahora=AHORA)

    assert veredicto(margen - timedelta(seconds=1)).resultado is chequeo.Resultado.FALLA
    justo = veredicto(margen)
    assert justo.resultado is chequeo.Resultado.BIEN
    assert "ya se aviso" in justo.razon
    assert veredicto(margen + timedelta(seconds=1)).resultado is chequeo.Resultado.BIEN
    assert veredicto(timedelta(days=5)).resultado is chequeo.Resultado.BIEN


def test_una_alerta_con_hora_en_el_futuro_hace_fallar(chequeo: ModuleType) -> None:
    """Relojes en desacuerdo: no se puede decir que es vieja."""
    cuerpo = _gasto_en(BudgetStatus.ALERTED, enviada=AHORA + timedelta(minutes=5))

    veredicto = chequeo.comprobar_gasto(chequeo.Lectura(cuerpo=cuerpo), ahora=AHORA)

    assert veredicto.resultado is chequeo.Resultado.FALLA


@pytest.mark.parametrize("hora", [None, "ayer por la tarde", "2026-10-12T10:00:00"], ids=str)
def test_una_alerta_sin_hora_legible_falla_porque_no_se_puede_probar_que_ya_se_aviso(
    chequeo: ModuleType, hora: str | None
) -> None:
    cuerpo = _gasto_en(BudgetStatus.ALERTED, enviada=AHORA - timedelta(hours=2))
    cuerpo["alert_sent_at"] = hora

    veredicto = chequeo.comprobar_gasto(chequeo.Lectura(cuerpo=cuerpo), ahora=AHORA)

    assert veredicto.resultado is chequeo.Resultado.FALLA
    assert "hora de envio" in veredicto.razon


def test_un_presupuesto_agotado_falla_salvo_que_se_tolere_a_conciencia(
    chequeo: ModuleType,
) -> None:
    gasto = chequeo.Lectura(cuerpo=_gasto_en(BudgetStatus.EXHAUSTED, enviada=AHORA))

    sin_opcion = chequeo.comprobar_gasto(gasto, ahora=AHORA)
    con_opcion = chequeo.comprobar_gasto(gasto, ahora=AHORA, tolerar_agotado=True)

    assert sin_opcion.resultado is chequeo.Resultado.FALLA
    assert "agotado" in sin_opcion.razon
    assert con_opcion.resultado is chequeo.Resultado.BIEN
    assert "--tolerar-agotado" in con_opcion.razon


def test_tolerar_agotado_no_silencia_ningun_otro_estado(chequeo: ModuleType) -> None:
    sin_medir = chequeo.Lectura(cuerpo=_gasto_en(BudgetStatus.UNMEASURED))
    alerta = chequeo.Lectura(cuerpo=_gasto_en(BudgetStatus.ALERTED, enviada=AHORA))

    assert (
        chequeo.comprobar_gasto(sin_medir, ahora=AHORA, tolerar_agotado=True).resultado
        is chequeo.Resultado.FALLA
    )
    assert (
        chequeo.comprobar_gasto(alerta, ahora=AHORA, tolerar_agotado=True).resultado
        is chequeo.Resultado.FALLA
    )


def test_un_gasto_sin_medir_falla(chequeo: ModuleType) -> None:
    gasto = chequeo.Lectura(cuerpo=_gasto_en(BudgetStatus.UNMEASURED))

    veredicto = chequeo.comprobar_gasto(gasto, ahora=AHORA)

    assert veredicto.resultado is chequeo.Resultado.FALLA
    assert "no se pudo medir" in veredicto.razon


def test_un_estado_de_gasto_desconocido_falla_nombrandolo(chequeo: ModuleType) -> None:
    cuerpo = _gasto_en(BudgetStatus.OK)
    cuerpo["window"]["status"] = "frozen"

    veredicto = chequeo.comprobar_gasto(chequeo.Lectura(cuerpo=cuerpo), ahora=AHORA)

    assert veredicto.resultado is chequeo.Resultado.FALLA
    assert "'frozen'" in veredicto.razon


@pytest.mark.parametrize(
    "cuerpo",
    [[], {}, {"alert_sent_at": None}, {"window": "ok"}, {"window": {"status": 4}}, {"window": {}}],
    ids=["lista", "vacio", "sin-window", "window-texto", "estado-numero", "window-vacia"],
)
def test_un_cuerpo_de_gasto_con_otra_forma_falla_sin_excepcion(
    chequeo: ModuleType, cuerpo: object
) -> None:
    veredicto = chequeo.comprobar_gasto(chequeo.Lectura(cuerpo=cuerpo), ahora=AHORA)

    assert veredicto.resultado is chequeo.Resultado.FALLA


def test_un_gasto_que_no_se_pudo_leer_falla(chequeo: ModuleType) -> None:
    veredicto = chequeo.comprobar_gasto(chequeo.Lectura(problema="respondio HTTP 500"), ahora=AHORA)

    assert veredicto.resultado is chequeo.Resultado.FALLA
    assert "500" in veredicto.razon


# --- Contra el servidor: los nombres no se inventan -----------------------------------


def test_los_estados_que_el_guion_conoce_son_los_de_los_enums_del_servidor(
    chequeo: ModuleType,
) -> None:
    reinicio = {chequeo.REINICIO_AL_DIA, chequeo.REINICIO_VENCIDO, chequeo.REINICIO_ILEGIBLE}
    gasto = {
        chequeo.GASTO_OK,
        chequeo.GASTO_ALERTA,
        chequeo.GASTO_AGOTADO,
        chequeo.GASTO_SIN_MEDIR,
    }

    assert reinicio == {estado.value for estado in health.DemoResetStatus}
    assert gasto == {estado.value for estado in BudgetStatus}


def test_cada_estado_del_servidor_tiene_un_veredicto_y_ninguno_cae_en_desconocido(
    chequeo: ModuleType,
) -> None:
    for estado in health.DemoResetStatus:
        ultimo = None if estado is health.DemoResetStatus.UNREADABLE else AHORA - timedelta(hours=1)
        cuerpo = _salud(health.DemoResetCheck(status=estado, last_successful_at=ultimo))
        razon = chequeo.comprobar_reinicio(chequeo.Lectura(cuerpo=cuerpo), ahora=AHORA).razon
        assert "desconocido" not in razon
    for estado_de_gasto in BudgetStatus:
        cuerpo = _gasto_en(estado_de_gasto, enviada=AHORA - timedelta(hours=1))
        razon = chequeo.comprobar_gasto(chequeo.Lectura(cuerpo=cuerpo), ahora=AHORA).razon
        assert "desconocido" not in razon


# --- El codigo de salida -----------------------------------------------------------


def test_el_codigo_de_salida_es_cero_salvo_que_algo_falle(chequeo: ModuleType) -> None:
    bien = chequeo.Veredicto("a", chequeo.Resultado.BIEN, "x")
    sin_medir = chequeo.Veredicto("b", chequeo.Resultado.NO_MEDIDA, "x")
    falla = chequeo.Veredicto("c", chequeo.Resultado.FALLA, "x")

    assert chequeo.codigo_de_salida([bien, sin_medir]) == 0
    assert chequeo.codigo_de_salida([bien, falla, sin_medir]) == 1
    assert chequeo.codigo_de_salida([]) == 0


def test_cada_linea_dice_el_resultado_el_nombre_y_la_razon(chequeo: ModuleType) -> None:
    veredictos = chequeo.juzgar(
        chequeo.Lectura(cuerpo=_reinicio(health.DemoResetStatus.OVERDUE, 30)),
        chequeo.Lectura(cuerpo=_gasto_en(BudgetStatus.OK)),
        ahora=AHORA,
    )

    lineas = [veredicto.linea() for veredicto in veredictos]

    assert [linea.split()[0] for linea in lineas] == ["bien", "FALLA", "bien"]
    assert lineas[1].startswith("FALLA     reinicio nocturno: ")
    assert chequeo.codigo_de_salida(veredictos) == 1


# --- La red, contra un servidor local ---------------------------------------------------


class _Servidor:
    def __init__(self) -> None:
        self.visto: list[tuple[str, str, str | None]] = []
        servidor = self

        class Manejador(http.server.BaseHTTPRequestHandler):
            def _responder(self) -> None:
                servidor.visto.append((self.command, self.path, self.headers.get("User-Agent")))
                if self.path == "/json":
                    estado, cuerpo = 200, b'{"status": "ready"}'
                elif self.path == "/html":
                    estado, cuerpo = 200, b"<html>despertando</html>"
                else:
                    estado, cuerpo = 503, b'{"code": "provider_unavailable"}'
                self.send_response(estado)
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)

            do_GET = _responder  # noqa: N815 -- el nombre lo fija http.server
            do_POST = _responder  # noqa: N815 -- para que una escritura quede en el registro

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                return None

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        self._hilo = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self._httpd.server_address[1]}"

    def __enter__(self) -> _Servidor:
        self._hilo.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._hilo.join(timeout=5)


@pytest.fixture
def servidor() -> Iterator[_Servidor]:
    with _Servidor() as local:
        yield local


def test_leer_entrega_el_json_con_un_get_y_solo_un_user_agent_propio(
    chequeo: ModuleType, servidor: _Servidor
) -> None:
    lectura = chequeo.leer(f"{servidor.base}/json", espera_s=0)

    assert lectura.problema is None
    assert lectura.cuerpo == {"status": "ready"}
    assert servidor.visto == [("GET", "/json", chequeo.AGENTE)]


def test_leer_dice_que_paso_cuando_no_es_un_200_con_json(
    chequeo: ModuleType, servidor: _Servidor
) -> None:
    caida = chequeo.leer(f"{servidor.base}/caida", intentos=1)
    no_json = chequeo.leer(f"{servidor.base}/html", intentos=1)
    rechazada = chequeo.leer("http://127.0.0.1:1/", intentos=1)

    assert caida.problema == "respondio HTTP 503"
    assert caida.cuerpo is None
    assert no_json.problema is not None
    assert "no es JSON" in no_json.problema
    assert rechazada.problema is not None
    assert rechazada.problema.startswith("no se pudo leer")


def test_leer_reintenta_una_vez_con_una_pausa_y_se_rinde_diciendo_la_razon(
    chequeo: ModuleType, servidor: _Servidor
) -> None:
    pausas: list[float] = []

    lectura = chequeo.leer(f"{servidor.base}/caida", espera_s=10, dormir=pausas.append)

    assert lectura.problema == "respondio HTTP 503"
    assert len(servidor.visto) == 2
    assert pausas == [10]


def test_leer_no_reintenta_si_el_primer_intento_sale_bien(
    chequeo: ModuleType, servidor: _Servidor
) -> None:
    pausas: list[float] = []

    chequeo.leer(f"{servidor.base}/json", dormir=pausas.append)

    assert len(servidor.visto) == 1
    assert pausas == []


def test_leer_rechaza_una_direccion_que_no_es_http(chequeo: ModuleType) -> None:
    lectura = chequeo.leer("file:///etc/passwd", intentos=1)

    assert lectura.cuerpo is None
    assert lectura.problema is not None


# --- El guion entero ----------------------------------------------------------------------


class _Lecturas:
    """Sustituye la red: devuelve lo que se le diga por direccion y anota que se pidio."""

    def __init__(self, chequeo: ModuleType, respuestas: dict[str, list[object]]) -> None:
        self.pedidas: list[str] = []
        self._respuestas = respuestas
        self._chequeo = chequeo

    def __call__(self, url: str, **_: object) -> Any:
        self.pedidas.append(url)
        cola = self._respuestas[url.removeprefix("https://sitio.test")]
        cuerpo = cola.pop(0) if len(cola) > 1 else cola[0]
        return self._chequeo.Lectura(cuerpo=cuerpo)


def _correr(
    chequeo: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    respuestas: dict[str, list[object]],
    *argv: str,
) -> tuple[int, _Lecturas, list[float]]:
    lecturas = _Lecturas(chequeo, respuestas)
    pausas: list[float] = []
    monkeypatch.setattr(chequeo, "leer", lecturas)
    monkeypatch.setattr(chequeo, "time", SimpleNamespace(sleep=pausas.append))
    codigo = chequeo.main(["--base-url", "https://sitio.test/", *argv])
    return codigo, lecturas, pausas


def test_el_guion_entero_con_todo_en_orden_sale_con_cero(
    chequeo: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    respuestas: dict[str, list[object]] = {
        "/api/health/ready": [_salud()],
        "/api/spend": [_gasto_en(BudgetStatus.OK)],
    }

    codigo, lecturas, pausas = _correr(chequeo, monkeypatch, respuestas)

    salida = capsys.readouterr().out.splitlines()
    assert codigo == 0
    assert [linea.split()[0] for linea in salida[:3]] == ["bien", "bien", "bien"]
    assert salida[-1] == "resultado: todo en orden"
    # Dos lecturas, las dos por GET a la direccion base sin la barra final, y sin esperas.
    assert lecturas.pedidas == [
        "https://sitio.test/api/health/ready",
        "https://sitio.test/api/spend",
    ]
    assert pausas == []


def test_el_guion_entero_con_un_reinicio_vencido_sale_con_uno(
    chequeo: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    respuestas: dict[str, list[object]] = {
        "/api/health/ready": [_reinicio(health.DemoResetStatus.OVERDUE, 30)],
        "/api/spend": [_gasto_en(BudgetStatus.OK)],
    }

    codigo, _, _ = _correr(chequeo, monkeypatch, respuestas)

    salida = capsys.readouterr().out
    assert codigo == 1
    assert "FALLA     reinicio nocturno" in salida
    assert "resultado: 1 de 3 comprobaciones FALLARON" in salida


def test_un_reinicio_ilegible_se_vuelve_a_leer_una_vez_porque_la_primera_pregunta_despierta_la_base(
    chequeo: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    ilegible = _reinicio(health.DemoResetStatus.UNREADABLE, None)
    respuestas: dict[str, list[object]] = {
        "/api/health/ready": [ilegible, _salud()],
        "/api/spend": [_gasto_en(BudgetStatus.OK)],
    }

    codigo, lecturas, pausas = _correr(chequeo, monkeypatch, respuestas)

    assert codigo == 0
    assert lecturas.pedidas.count("https://sitio.test/api/health/ready") == 2
    assert len(pausas) == 1


def test_un_reinicio_que_sigue_ilegible_tras_la_segunda_lectura_falla(
    chequeo: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    ilegible = _reinicio(health.DemoResetStatus.UNREADABLE, None)
    respuestas: dict[str, list[object]] = {
        "/api/health/ready": [ilegible],
        "/api/spend": [_gasto_en(BudgetStatus.OK)],
    }

    codigo, lecturas, _ = _correr(chequeo, monkeypatch, respuestas)

    assert codigo == 1
    assert lecturas.pedidas.count("https://sitio.test/api/health/ready") == 2


def test_la_opcion_tolerar_agotado_llega_al_veredicto(
    chequeo: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    respuestas: dict[str, list[object]] = {
        "/api/health/ready": [_salud()],
        "/api/spend": [_gasto_en(BudgetStatus.EXHAUSTED, enviada=AHORA)],
    }

    sin_opcion, _, _ = _correr(chequeo, monkeypatch, respuestas)
    con_opcion, _, _ = _correr(chequeo, monkeypatch, respuestas, "--tolerar-agotado")

    assert (sin_opcion, con_opcion) == (1, 0)


def test_una_direccion_base_que_no_es_http_se_rechaza_antes_de_leer(chequeo: ModuleType) -> None:
    with pytest.raises(SystemExit) as salida:
        chequeo.main(["--base-url", "ftp://sitio.test"])

    assert salida.value.code == 2
