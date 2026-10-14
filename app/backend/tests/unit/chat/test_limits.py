"""Los cinco controles de entrada del chat (BR3.1, BR3.2, PERF-U13.1, PERF-U13.2).

Son pruebas unitarias y sin base a proposito: la decision es pura, y lo que hay que
cubrir son los bordes de cada limite --justo debajo pasa, justo encima no-- que es
donde un `>` en vez de un `>=` vive sin que nadie lo note.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pytest

from untangle import paths
from untangle.chat.limits import (
    LIMIT_COPY_KEYS,
    Counters,
    LimitDecision,
    LimitKind,
    decide,
)
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.tenancy.models import ChatConfig

AHORA = datetime(2026, 9, 28, 15, 0, tzinfo=UTC)

#: Numeros pequenos y **distintos entre si** a proposito: con los tres iguales,
#: una decision que mirara el contador equivocado pasaria todas las pruebas.
CONFIG = ChatConfig(
    messages_per_session=3,
    messages_per_origin_per_day=5,
    messages_per_site_per_day=7,
    min_seconds_between_messages=2.0,
    max_message_characters=100,
)


def _contadores(
    *, sesion: int = 0, origen: int = 0, sitio: int = 0, anterior: datetime | None = None
) -> Counters:
    return Counters(
        session_messages=sesion,
        origin_messages_today=origen,
        site_messages_today=sitio,
        last_message_at=anterior,
    )


def _decidir(
    contadores: Counters, *, caracteres: int = 10, ahora: datetime = AHORA
) -> LimitDecision:
    return decide(config=CONFIG, counters=contadores, message_characters=caracteres, now=ahora)


# --- El caso que pasa ---------------------------------------------------------


def test_un_mensaje_normal_pasa_los_cinco() -> None:
    """El control positivo. Sin el, una decision que rechazara siempre pasaria
    todas las pruebas de abajo."""
    decision = _decidir(_contadores(sesion=1, origen=2, sitio=3))

    assert decision.allowed
    assert decision.kind is None


# --- Los bordes de cada limite ------------------------------------------------


@pytest.mark.parametrize(
    ("nombre", "contadores", "esperado"),
    [
        ("sesion", _contadores(sesion=3), LimitKind.SESSION),
        ("origen", _contadores(origen=5), LimitKind.ORIGIN),
        ("sitio", _contadores(sitio=7), LimitKind.SITE_DAY),
    ],
)
def test_cada_contador_rechaza_al_llegar_a_su_limite(
    nombre: str, contadores: Counters, esperado: LimitKind
) -> None:
    """Al **llegar** al limite, no al pasarlo: el enesimo mensaje es el que sobra."""
    decision = _decidir(contadores)

    assert decision.rejected, nombre
    assert decision.kind is esperado


@pytest.mark.parametrize(
    ("nombre", "contadores"),
    [
        ("sesion", _contadores(sesion=2)),
        ("origen", _contadores(origen=4)),
        ("sitio", _contadores(sitio=6)),
    ],
)
def test_justo_debajo_de_cada_limite_todavia_pasa(nombre: str, contadores: Counters) -> None:
    """El otro lado del borde. Con solo la prueba de arriba, un limite puesto uno
    mas abajo rechazaria al que si cabia y nadie lo notaria."""
    assert _decidir(contadores).allowed, nombre


# --- El tamano y la rafaga ----------------------------------------------------


def test_un_mensaje_mas_largo_que_el_maximo_se_rechaza() -> None:
    decision = _decidir(_contadores(), caracteres=101)

    assert decision.kind is LimitKind.SIZE
    assert decision.retry_after is None, "esperar no hace mas corto el mensaje"


def test_el_mensaje_del_tamano_exacto_pasa() -> None:
    assert _decidir(_contadores(), caracteres=100).allowed


def test_dos_mensajes_mas_seguidos_que_el_intervalo_se_rechazan() -> None:
    decision = _decidir(_contadores(anterior=AHORA - timedelta(seconds=1)))

    assert decision.kind is LimitKind.RATE
    assert decision.retry_after == AHORA - timedelta(seconds=1) + timedelta(seconds=2)


def test_pasado_el_intervalo_el_siguiente_pasa() -> None:
    assert _decidir(_contadores(anterior=AHORA - timedelta(seconds=2))).allowed


def test_el_primer_mensaje_no_tiene_intervalo_que_respetar() -> None:
    assert _decidir(_contadores(anterior=None)).allowed


# --- El orden, que es parte de la regla ---------------------------------------


def test_el_tamano_se_comprueba_antes_que_los_contadores() -> None:
    """BR3.2: un mensaje enorme no paga tres consultas antes de rechazarse.

    Con los tres contadores agotados **y** el mensaje demasiado largo, el que
    responde es el tamano. Si el orden se invirtiera, un mensaje de cien mil
    caracteres costaria el trabajo de mirar los contadores primero.
    """
    decision = _decidir(_contadores(sesion=3, origen=5, sitio=7), caracteres=101)

    assert decision.kind is LimitKind.SIZE


def test_la_rafaga_se_comprueba_antes_que_los_contadores() -> None:
    decision = _decidir(_contadores(sesion=3, anterior=AHORA - timedelta(seconds=1)))

    assert decision.kind is LimitKind.RATE


# --- Lo que se le promete a la persona ----------------------------------------


def test_los_limites_diarios_dicen_cuando_se_puede_seguir() -> None:
    """Se reinician solos, asi que la espera se puede prometer con honestidad."""
    manana = datetime(2026, 9, 29, 0, 0, tzinfo=UTC)

    assert _decidir(_contadores(origen=5)).retry_after == manana
    assert _decidir(_contadores(sitio=7)).retry_after == manana


def test_el_limite_de_sesion_no_promete_una_hora_que_no_puede_cumplir() -> None:
    """La conversacion ya gasto lo suyo y no se reinicia sola: decir una hora
    seria inventarla, y el proyecto prohibe prometer lo que no existe."""
    assert _decidir(_contadores(sesion=3)).retry_after is None


# --- PERF-U13.1: los cinco, sumados, por debajo de un milisegundo -------------


def test_los_cinco_controles_tardan_menos_de_un_milisegundo() -> None:
    """PERF-U13.1. El umbral esta mil veces por encima de la medicion a proposito.

    Los cinco controles son aritmetica sobre dos estructuras en memoria: una
    medicion tipica ronda el microsegundo. Un umbral pegado a ella fallaria por
    el ruido de la maquina; uno mil veces por encima solo falla cuando cambio la
    naturaleza del control --por ejemplo, si alguien metiera una consulta aqui
    dentro--, que es exactamente lo que se quiere que falle.
    """
    contadores = _contadores(sesion=1, origen=2, sitio=3, anterior=AHORA - timedelta(seconds=5))
    repeticiones = 1000

    inicio = time.perf_counter()
    for _ in range(repeticiones):
        decide(config=CONFIG, counters=contadores, message_characters=10, now=AHORA)
    por_llamada_ms = (time.perf_counter() - inicio) * 1000 / repeticiones

    assert por_llamada_ms < 1.0, f"los cinco controles tardaron {por_llamada_ms:.4f} ms"


# --- Cada limite tiene una frase que el catalogo sabe resolver (BR3.1) --------


@pytest.mark.usefixtures("catalogo_cargado")
def test_los_cinco_limites_tienen_una_clave_y_la_clave_existe() -> None:
    """El defecto de esta tanda, con su prueba.

    La ruta componia la clave con `f"chat.limit.{limite.value}"` y **ninguna de las
    cinco existia en el catalogo**: quien llegaba a un limite recibia una clave que
    su navegador no sabe resolver. Ninguna compuerta lo vio porque el chequeo de
    claves sin consumidor solo encuentra claves escritas literales, y una clave
    compuesta en tiempo de ejecucion no lo es.

    La asercion es que el texto **no sea la clave**, y no que la llamada no falle:
    el catalogo devuelve la clave misma cuando falta --a proposito, para que se vea
    que falta-- asi que una prueba que solo mirara que no levanta pasaria con las
    cinco claves inventadas. Es justo el error que esta prueba tuvo primero.
    """
    faltantes: list[tuple[LimitKind, str]] = []
    for limite in LimitKind:
        clave = LIMIT_COPY_KEYS[limite]
        # En los dos idiomas: una frase que solo existe en uno deja al otro sin
        # nada que decir, que es el mismo fallo por la mitad (P12).
        for idioma in ("es", "en"):
            if copy_api.t(CopyKey(clave), locale=idioma) == clave:
                faltantes.append((limite, f"{clave} ({idioma})"))

    assert faltantes == [], f"limites sin frase en el catalogo: {faltantes}"


def test_ningun_limite_se_queda_fuera_de_la_tabla() -> None:
    """La tabla es cerrada: un sexto limite sin frase falla aqui y no en pantalla."""
    assert set(LIMIT_COPY_KEYS) == set(LimitKind)


def test_el_navegador_sabe_decir_los_cinco_limites() -> None:
    """Las dos tablas tienen que coincidir, y nada las ataba.

    El servidor decide **cual** limite salio y manda su clave; el navegador la
    resuelve con su propia tabla, porque `t()` exige la clave escrita literal. Son
    dos listas en dos lenguajes, y una clave que el servidor manda y el navegador
    no conoce cae en la frase de error: la persona ve "tuve un problema" en vez de
    saber que llego a un limite.

    Se comprueba con un grep, que es lo que una convencion entre dos lenguajes
    admite, y por eso la tabla del navegador escribe cada clave literal.
    """
    tabla = (
        paths.repo_root() / "app" / "frontend" / "src" / "pages" / "chat" / "chat-copy.ts"
    ).read_text(encoding="utf-8")

    faltantes = [clave for clave in LIMIT_COPY_KEYS.values() if f'"{clave}"' not in tabla]

    assert faltantes == [], f"claves que el navegador no sabe decir: {faltantes}"
