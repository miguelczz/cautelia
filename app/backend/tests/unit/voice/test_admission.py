"""La admision de una llamada publica (BR1.2, BR1.3, BR1.5, PERF-U17.1).

Unitarias y sin base, como las del chat: la decision es pura y lo que hay que cubrir
son los bordes --justo debajo pasa, justo encima no--, la asimetria de la retoma y
que el reloj sea el que entra por argumento.
"""

from __future__ import annotations

import ast
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from untangle.providers.config import VoiceLimits
from untangle.tenancy.models import CallConfig
from untangle.voice import admission
from untangle.voice.admission import CallCounters, CallLanes, CutCall, decide
from untangle.voice.availability import OFF_CODE_KEYS, VoiceOffCode

AHORA = datetime(2026, 9, 30, 15, 0, tzinfo=UTC)

#: Distintos entre si a proposito: con los dos iguales, una decision que mirara el
#: contador equivocado pasaria todas las pruebas.
LANES = CallLanes(calls_per_visitor_day=2, calls_per_site_day=5, resume_window_seconds=900)


def _contadores(visitante: int = 0, sitio: int = 0, corte: CutCall | None = None) -> CallCounters:
    return CallCounters(visitor_calls_today=visitante, site_calls_today=sitio, cut_call=corte)


def _corte(hace: timedelta) -> CutCall:
    return CutCall(case_id="case-1", ended_at=AHORA - hace)


# --- Los dos carriles ----------------------------------------------------------


def test_una_llamada_con_margen_en_los_dos_carriles_se_admite() -> None:
    decision = decide(lanes=LANES, counters=_contadores(1, 4), now=AHORA)

    assert decision.admitted
    assert decision.off_code is None
    assert decision.resumes_case is None


def test_el_carril_de_la_conexion_rechaza_al_llegar_a_su_limite() -> None:
    decision = decide(lanes=LANES, counters=_contadores(visitante=2), now=AHORA)

    assert not decision.admitted
    assert decision.off_code is VoiceOffCode.RATE_LIMITED_DAILY


def test_el_carril_del_sitio_rechaza_al_llegar_a_su_limite() -> None:
    decision = decide(lanes=LANES, counters=_contadores(sitio=5), now=AHORA)

    assert not decision.admitted
    assert decision.off_code is VoiceOffCode.RATE_LIMITED_SITE


@pytest.mark.parametrize(("visitante", "sitio"), [(1, 0), (0, 4), (1, 4)])
def test_justo_debajo_de_cada_limite_todavia_pasa(visitante: int, sitio: int) -> None:
    """Donde un `>` en vez de un `>=` vive sin que nadie lo note."""
    assert decide(lanes=LANES, counters=_contadores(visitante, sitio), now=AHORA).admitted


def test_con_los_dos_agotados_responde_el_de_la_conexion() -> None:
    """El orden esta fijado: el carril que la persona entiende como suyo va primero."""
    decision = decide(lanes=LANES, counters=_contadores(2, 5), now=AHORA)

    assert decision.off_code is VoiceOffCode.RATE_LIMITED_DAILY


def test_los_valores_por_omision_son_una_llamada_por_conexion_y_quince_del_sitio() -> None:
    por_omision = CallLanes(
        calls_per_visitor_day=1, calls_per_site_day=15, resume_window_seconds=900
    )

    assert por_omision.calls_per_visitor_day == 1
    assert por_omision.calls_per_site_day == 15
    assert decide(lanes=por_omision, counters=_contadores(1, 0), now=AHORA).off_code is (
        VoiceOffCode.RATE_LIMITED_DAILY
    )
    assert decide(lanes=por_omision, counters=_contadores(0, 15), now=AHORA).off_code is (
        VoiceOffCode.RATE_LIMITED_SITE
    )


def test_los_limites_son_configuracion_y_no_codigo() -> None:
    """AC5.12.4: cambiar el valor cambia la decision sin tocar el modulo."""
    holgada = CallLanes(calls_per_visitor_day=3, calls_per_site_day=30, resume_window_seconds=900)

    assert decide(lanes=holgada, counters=_contadores(2, 29), now=AHORA).admitted
    assert not decide(lanes=holgada, counters=_contadores(3, 0), now=AHORA).admitted


# --- La retoma ------------------------------------------------------------------


def test_una_retoma_dentro_de_la_ventana_no_gasta_la_llamada_del_dia() -> None:
    """Con el carril de la conexion agotado, la retoma entra: es lo que protege que
    quien prueba termine lo que empezo."""
    decision = decide(
        lanes=LANES,
        counters=_contadores(visitante=2, corte=_corte(timedelta(minutes=14, seconds=59))),
        now=AHORA,
    )

    assert decision.admitted
    assert decision.resumes_case == "case-1"


def test_una_retoma_dentro_de_la_ventana_si_cuenta_contra_el_sitio() -> None:
    """La otra mitad de la asimetria: el sitio protege el dinero, y una retoma
    cuesta lo mismo que una llamada nueva."""
    decision = decide(
        lanes=LANES,
        counters=_contadores(visitante=1, sitio=5, corte=_corte(timedelta(minutes=1))),
        now=AHORA,
    )

    assert not decision.admitted
    assert decision.off_code is VoiceOffCode.RATE_LIMITED_SITE
    assert decision.resumes_case is None


def test_fuera_de_la_ventana_es_una_llamada_nueva() -> None:
    decision = decide(
        lanes=LANES,
        counters=_contadores(visitante=2, corte=_corte(timedelta(minutes=15, seconds=1))),
        now=AHORA,
    )

    assert not decision.admitted
    assert decision.off_code is VoiceOffCode.RATE_LIMITED_DAILY


def test_fuera_de_la_ventana_y_con_margen_abre_sin_retomar() -> None:
    decision = decide(
        lanes=LANES,
        counters=_contadores(visitante=1, corte=_corte(timedelta(minutes=30))),
        now=AHORA,
    )

    assert decision.admitted
    assert decision.resumes_case is None


def test_en_el_borde_exacto_la_ventana_ya_se_cerro() -> None:
    """Igual que `find_resumable` (`resume_until > ahora`): a los 900 s exactos no hay
    retoma. Si esta decision y esa consulta discreparan, la disponibilidad ofreceria
    una retoma que la admision trataria como llamada nueva."""
    en_el_borde = decide(
        lanes=LANES,
        counters=_contadores(visitante=2, corte=_corte(timedelta(seconds=900))),
        now=AHORA,
    )
    un_segundo_antes = decide(
        lanes=LANES,
        counters=_contadores(visitante=2, corte=_corte(timedelta(seconds=899))),
        now=AHORA,
    )

    assert not en_el_borde.admitted
    assert un_segundo_antes.admitted


def test_la_ventana_es_la_de_la_configuracion() -> None:
    corta = CallLanes(calls_per_visitor_day=1, calls_per_site_day=15, resume_window_seconds=60)
    corte = _corte(timedelta(seconds=120))

    assert not decide(lanes=corta, counters=_contadores(1, corte=corte), now=AHORA).admitted
    assert decide(lanes=LANES, counters=_contadores(1, corte=corte), now=AHORA).admitted


# --- Pura: el reloj entra por argumento (BR1.2) ---------------------------------


@pytest.mark.parametrize(
    "ahora", [datetime(2001, 1, 1, tzinfo=UTC), datetime(2999, 1, 1, tzinfo=UTC)]
)
def test_la_decision_sigue_al_reloj_que_se_le_pasa_y_no_al_de_la_maquina(ahora: datetime) -> None:
    corte = CutCall(case_id="case-1", ended_at=ahora - timedelta(minutes=5))

    assert decide(lanes=LANES, counters=_contadores(2, corte=corte), now=ahora).admitted
    viejo = CutCall(case_id="case-1", ended_at=ahora - timedelta(hours=1))
    assert not decide(lanes=LANES, counters=_contadores(2, corte=viejo), now=ahora).admitted


def test_un_instante_sin_zona_horaria_se_rechaza() -> None:
    with pytest.raises(ValueError, match="zona horaria"):
        decide(lanes=LANES, counters=_contadores(), now=datetime(2026, 9, 30, 15, 0))


def test_el_modulo_no_lee_el_reloj_ni_abre_sesion_ni_compone_texto() -> None:
    """La pureza tambien se comprueba mirando el codigo, porque la prueba de arriba
    no vera una lectura del reloj que casualmente coincida con el argumento."""
    arbol = ast.parse(Path(admission.__file__).read_text(encoding="utf-8"))
    importados = {
        nombre.name
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Import | ast.ImportFrom)
        for nombre in nodo.names
    }
    modulos = {nodo.module or "" for nodo in ast.walk(arbol) if isinstance(nodo, ast.ImportFrom)}
    llamadas = {
        f"{getattr(nodo.func.value, 'id', '')}.{nodo.func.attr}"
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
    }

    assert "time" not in importados
    assert not {"datetime.now", "datetime.utcnow", "time.time", "date.today"} & llamadas
    assert not {
        m
        for m in modulos
        if m.startswith(("untangle.db", "untangle.server", "untangle.copy_catalog"))
    }


def test_la_decision_devuelve_el_codigo_y_la_frase_sale_del_catalogo() -> None:
    """BR1.2: ningun texto en la decision, y cada codigo que emite tiene su clave."""
    for contadores in (_contadores(2, 0), _contadores(0, 5)):
        decision = decide(lanes=LANES, counters=contadores, now=AHORA)
        assert isinstance(decision.off_code, VoiceOffCode)
        assert decision.off_code in OFF_CODE_KEYS


# --- De donde salen los carriles (BR1.5) ----------------------------------------


def test_el_cupo_del_sitio_puede_quedar_por_debajo_del_de_una_conexion() -> None:
    """Y hasta en cero, sin ser una configuracion rota (U17, tanda 2).

    El numero del sitio que la decision compara es el **cupo de hoy**, que U5
    deriva del presupuesto que queda y los dias que faltan (BR5.6): con el
    presupuesto agotado sale cero con todo el archivo bien escrito. Lo que si es
    un error de archivo --que el **tope** quede por debajo-- lo comprueba
    `VoiceLimits`, que es donde esta escrito una sola vez.

    Aqui vivia ese invariante hasta la tanda 2, y rechazaba el cupo de un dia sin
    presupuesto como si fuera un archivo invalido.
    """
    carriles = CallLanes(calls_per_visitor_day=1, calls_per_site_day=0, resume_window_seconds=900)

    decision = decide(
        lanes=carriles,
        counters=CallCounters(visitor_calls_today=0, site_calls_today=0),
        now=AHORA,
    )

    # El carril de la conexion deja pasar --no ha llamado-- y el del sitio para.
    assert not decision.admitted
    assert decision.off_code is VoiceOffCode.RATE_LIMITED_SITE


def test_la_carpeta_de_una_aseguradora_no_declara_los_carriles() -> None:
    """**Los carriles son del sitio, no de una aseguradora.**

    "Quince llamadas del sitio" escrito en tres carpetas son cuarenta y cinco, o
    las que toque leer. Esta prueba existe porque el diseno de la unidad los puso
    ahi por error y la tanda 1 los construyo asi: si alguien vuelve a anadirlos a
    `CallConfig`, se cae aqui.
    """
    declarados = set(CallConfig.model_fields)

    assert "calls_per_visitor_day" not in declarados
    assert "calls_per_site_day" not in declarados
    assert declarados == {"max_call_seconds", "warn_at_seconds", "resume_window_seconds"}


def test_los_carriles_del_sitio_salen_de_la_plataforma() -> None:
    """Y salen de `VoiceLimits`, que los declara **sin valor por omision**.

    Un limite que el archivo no escribe es un limite que nadie decidio, y ese es el
    archivo que se revisa cuando hay que explicar por que se rechazo una llamada.
    """
    campos = VoiceLimits.model_fields

    assert {"calls_per_visitor_per_day", "site_daily_cap"} <= set(campos)
    assert all(
        campos[nombre].is_required() for nombre in ("calls_per_visitor_per_day", "site_daily_cap")
    )


def test_el_tope_del_sitio_por_debajo_del_de_una_conexion_no_carga() -> None:
    """El invariante, en el archivo donde es un error de verdad (U17, tanda 2).

    Un tope del sitio por debajo del de una conexion quedaria alcanzado antes, y la
    frase que ve la persona nombraria el carril equivocado: le diria que el sitio
    esta ocupado cuando lo que se acabo es su propia llamada del dia.

    Estaba en `CallLanes` y rechazaba tambien el **cupo** de un dia sin presupuesto,
    que es legitimo y no un archivo roto.
    """
    with pytest.raises(ValidationError, match="site_daily_cap"):
        VoiceLimits(max_call_seconds=180, calls_per_visitor_per_day=5, site_daily_cap=4)


def test_el_tope_del_sitio_igual_al_de_una_conexion_si_carga() -> None:
    """El borde: igual vale, y es el control positivo del de arriba."""
    limites = VoiceLimits(max_call_seconds=180, calls_per_visitor_per_day=5, site_daily_cap=5)

    assert limites.site_daily_cap == 5


# --- PERF-U17.1: la decision, por debajo de un milisegundo ----------------------


def test_la_decision_de_los_dos_carriles_tarda_menos_de_un_milisegundo() -> None:
    """El umbral esta mil veces por encima de la medicion a proposito: la decision
    es pura, asi que el numero mide la decision y no la maquina."""
    contadores = _contadores(1, 4, _corte(timedelta(minutes=5)))
    repeticiones = 2000
    inicio = time.perf_counter()
    for _ in range(repeticiones):
        decide(lanes=LANES, counters=contadores, now=AHORA)
    por_llamada_ms = (time.perf_counter() - inicio) * 1000 / repeticiones

    assert por_llamada_ms < 1.0, f"la decision tardo {por_llamada_ms:.4f} ms"


# --- U17, tanda 2: ningun modo escrito a mano en el camino de la llamada ------


def test_la_ruta_no_escribe_ningun_modo_de_voz_a_mano() -> None:
    """El modo lo decide la contabilidad, y la ruta no puede volver a elegirlo.

    Habia **cuatro** `VoiceMode.PRIMARY` escritos a mano en `voice_routes.py`: dos
    en las respuestas de "no hay voz", uno en la que si la hay y uno al abrir la
    llamada. Mientras estuvieran, la decision de U5 --que ya existia, probada y sin
    consumidor-- no cambiaba nada: la consola avisaba de la voz principal y la
    llamada se abria con ella aunque el presupuesto no la cubriera.

    Se mira el codigo y no la conducta porque la conducta **no los distingue**: con
    presupuesto de sobra, el valor escrito a mano y el que decide la contabilidad
    son el mismo, y la prueba pasaria con el defecto puesto. Es la misma forma del
    `VoiceMode.PRIMARY` que U17 encontro en su diseno.

    Los usos legitimos que quedan son de **tipo**, no de valor: anotaciones del
    contrato. Por eso se buscan accesos al atributo y no el nombre del enum.
    """
    from untangle.server import voice_routes

    arbol = ast.parse(Path(voice_routes.__file__).read_text(encoding="utf-8"))
    escritos = [
        f"VoiceMode.{nodo.attr}"
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Attribute)
        and isinstance(nodo.value, ast.Name)
        and nodo.value.id == "VoiceMode"
    ]

    assert escritos == [], f"la ruta vuelve a elegir el modo: {escritos}"
