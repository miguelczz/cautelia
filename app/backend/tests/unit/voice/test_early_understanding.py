"""La lectura que se adelanta mientras corre la tolerancia de fin de habla (2026-10-13).

Sin base ni reloj de pared: el lector es un doble que se queda esperando a que la prueba lo
suelte, y el reloj monotono entra por argumento, asi que el "cuanto ahorro" se prueba con
numeros exactos y no con dormir.

Lo que estas pruebas cuidan es lo que no se ve en una llamada que sale bien: que una lectura
descartada no deje tareas colgando, que cancelar no rompa el rastro del turno (la lectura abre
variables de contexto como el turno de verdad) y que el evento diga que paso **sin decir que
se dijo**.
"""

from __future__ import annotations

import asyncio
import io
import json
import sys
from collections.abc import Iterator
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

import pytest

from untangle import observability
from untangle.orchestration.contracts import InboundTurn
from untangle.orchestration.nodes.intake.understanding import UnderstandingResponse, Want
from untangle.voice.early_understanding import Discard, EarlyUnderstanding, Taken

AHORA = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
TEXTO = "tuve un choque con mi carro en la calle diez"

#: Lo que "entiende" el lector de las pruebas.
ENTENDIDO = UnderstandingResponse(wants=Want.REPORT_ACCIDENT)


def _turno(texto: str = TEXTO, *, caso: str | None = "caso-1", idioma: str = "es") -> InboundTurn:
    return InboundTurn(
        tenant_id="aseguradora",
        session_ref="llamada-1",
        case_id=caso,
        text=texto,
        language=idioma,  # type: ignore[arg-type]
        channel="voice",
        received_at=AHORA,
    )


@dataclass
class Reloj:
    """El reloj monotono de la lectura: avanza solo cuando la prueba lo dice."""

    t: float = 0.0

    def __call__(self) -> float:
        return self.t


@dataclass
class Lector:
    """Quien lee, con la forma de `understand_turn`: se queda esperando hasta que lo sueltan."""

    reloj: Reloj
    respuesta: UnderstandingResponse | None = ENTENDIDO
    #: Si se da, la lectura espera a que se encienda antes de contestar.
    soltar: asyncio.Event | None = None
    #: Cuanto tarda, en el reloj de la prueba: avanza el reloj justo antes de contestar.
    tarda: float = 0.0
    falla: Exception | None = None
    textos: list[str] = field(default_factory=list)
    canceladas: int = 0

    async def __call__(self, turn: InboundTurn) -> UnderstandingResponse | None:
        self.textos.append(turn.text)
        try:
            if self.soltar is not None:
                await self.soltar.wait()
            if self.falla is not None:
                raise self.falla
            self.reloj.t += self.tarda
            return self.respuesta
        except asyncio.CancelledError:
            self.canceladas += 1
            raise


@pytest.fixture
def salida() -> Iterator[io.StringIO]:
    destino = io.StringIO()
    observability.set_stream(destino)
    try:
        yield destino
    finally:
        observability.set_stream(sys.stdout)


def _eventos(salida: io.StringIO) -> list[dict[str, object]]:
    lineas = (json.loads(linea) for linea in salida.getvalue().splitlines() if linea.strip())
    return [e for e in lineas if e.get("event") == "voice.early_understanding"]


def _lectura(lector: Lector, reloj: Reloj) -> EarlyUnderstanding:
    return EarlyUnderstanding(lector, tenant_id="aseguradora", call_id="llamada-1", monotonic=reloj)


async def _ceder(veces: int = 20) -> None:
    for _ in range(veces):
        await asyncio.sleep(0)


def _tareas_ajenas() -> set[asyncio.Task[object]]:
    return {t for t in asyncio.all_tasks() if t is not asyncio.current_task()}


# --- Usada ----------------------------------------------------------------------------


async def test_una_lectura_ya_terminada_se_usa_sin_esperar_y_ahorra_lo_que_duro(
    salida: io.StringIO,
) -> None:
    reloj = Reloj()
    lector = Lector(reloj, tarda=1.8)
    lectura = _lectura(lector, reloj)

    lectura.start(_turno())
    await _ceder()
    reloj.t = 2.5  # la tolerancia vencio mucho despues de que la lectura termino (en 1,8)

    tomada = await lectura.take(_turno(), turn_id="llamada-1-t1")

    assert tomada == Taken(response=ENTENDIDO)
    (evento,) = _eventos(salida)
    assert evento["outcome"] == "used"
    assert evento["turn_id"] == "llamada-1-t1"
    assert evento["ran_ms"] == 1800
    assert evento["waited_ms"] == 0
    assert evento["saved_ms"] == 1800
    assert evento["understood"] is True


async def test_una_lectura_en_vuelo_se_espera_y_ahorra_solo_lo_que_avanzo(
    salida: io.StringIO,
) -> None:
    reloj = Reloj()
    lector = Lector(reloj, soltar=asyncio.Event())
    lectura = _lectura(lector, reloj)

    lectura.start(_turno())
    await _ceder()
    reloj.t = 0.7  # la tolerancia vence con la lectura a medias
    espera = asyncio.create_task(lectura.take(_turno(), turn_id="llamada-1-t1"))
    await _ceder()
    assert not espera.done(), "el turno debe esperar lo que falta de la lectura"

    reloj.t = 1.9  # la lectura contesta
    lector.soltar.set()  # type: ignore[union-attr]
    tomada = await asyncio.wait_for(espera, timeout=2)

    assert tomada == Taken(response=ENTENDIDO)
    (evento,) = _eventos(salida)
    assert evento["ran_ms"] == 1900
    assert evento["waited_ms"] == 1200
    assert evento["saved_ms"] == 700, (
        "ahorro: lo que la lectura avanzo antes de que cerrara el turno"
    )


async def test_un_resultado_nulo_tambien_se_entrega_para_que_el_turno_no_lo_repita(
    salida: io.StringIO,
) -> None:
    """El modelo fallo o tardo: el turno sigue por reglas, pero no lo vuelve a llamar."""
    reloj = Reloj()
    lectura = _lectura(Lector(reloj, respuesta=None), reloj)

    lectura.start(_turno())
    await _ceder()
    tomada = await lectura.take(_turno(), turn_id="llamada-1-t1")

    assert tomada == Taken(response=None)
    assert _eventos(salida)[0]["understood"] is False


async def test_empezar_dos_veces_con_el_mismo_texto_lee_una_sola_vez() -> None:
    reloj = Reloj()
    lector = Lector(reloj, soltar=asyncio.Event())
    lectura = _lectura(lector, reloj)

    lectura.start(_turno())
    lectura.start(_turno())
    await _ceder()
    lector.soltar.set()  # type: ignore[union-attr]
    await lectura.take(_turno(), turn_id="llamada-1-t1")

    assert lector.textos == [TEXTO]
    assert lector.canceladas == 0


async def test_sin_lectura_en_vuelo_no_hay_nada_que_tomar() -> None:
    reloj = Reloj()
    lectura = _lectura(Lector(reloj), reloj)

    assert await lectura.take(_turno(), turn_id="llamada-1-t1") is None


# --- Descartada -----------------------------------------------------------------------


async def test_un_texto_nuevo_suelta_la_lectura_anterior_y_empieza_otra(
    salida: io.StringIO,
) -> None:
    reloj = Reloj()
    lector = Lector(reloj, soltar=asyncio.Event())
    lectura = _lectura(lector, reloj)
    mas = f"{TEXTO} y no hubo heridos"

    lectura.start(_turno())
    await _ceder()
    lectura.start(_turno(mas))
    await _ceder()
    lector.soltar.set()  # type: ignore[union-attr]
    tomada = await lectura.take(_turno(mas), turn_id="llamada-1-t1")
    await lectura.aclose()

    assert tomada is not None
    assert lector.textos == [TEXTO, mas]
    assert lector.canceladas == 1, "la lectura del texto viejo se cancela, no se deja correr"
    descartada, usada = _eventos(salida)
    assert (descartada["outcome"], descartada["cause"]) == ("discarded", "kept_talking")
    assert descartada["turn_id"] is None, "todavia no habia turno"
    assert usada["outcome"] == "used"


@pytest.mark.parametrize("terminada", [False, True])
async def test_soltar_cancela_la_lectura_y_dice_si_el_modelo_ya_habia_contestado(
    salida: io.StringIO, terminada: bool
) -> None:
    reloj = Reloj()
    lector = Lector(reloj, soltar=None if terminada else asyncio.Event())
    lectura = _lectura(lector, reloj)

    lectura.start(_turno())
    await _ceder()
    reloj.t = 0.5
    lectura.drop(Discard.KEPT_TALKING)
    await lectura.aclose()

    assert not lectura.in_flight
    (evento,) = _eventos(salida)
    assert evento["outcome"] == "discarded"
    assert evento["cause"] == "kept_talking"
    assert evento["finished"] is terminada, "si ya contesto, el llamado se pago de todos modos"
    assert lector.canceladas == (0 if terminada else 1)


@pytest.mark.parametrize(
    "distinto",
    [
        _turno("tuve un choque con mi carro en la calle once"),
        _turno(idioma="en"),
        _turno(caso="caso-2"),
    ],
    ids=["texto", "idioma", "caso"],
)
async def test_la_lectura_no_vale_si_cambio_el_texto_el_idioma_o_el_caso(
    salida: io.StringIO, distinto: InboundTurn
) -> None:
    reloj = Reloj()
    lector = Lector(reloj, soltar=asyncio.Event())
    lectura = _lectura(lector, reloj)

    lectura.start(_turno())
    await _ceder()
    # Con un tope: si la regla se rompe, el turno se quedaria esperando una lectura que no termina.
    tomada = await asyncio.wait_for(lectura.take(distinto, turn_id="llamada-1-t1"), timeout=2)
    await lectura.aclose()

    assert tomada is None
    assert lector.canceladas == 1
    (evento,) = _eventos(salida)
    assert (evento["outcome"], evento["cause"]) == ("discarded", "state_changed")
    assert evento["turn_id"] == "llamada-1-t1"


async def test_al_cerrar_la_llamada_no_queda_ninguna_tarea_colgando(salida: io.StringIO) -> None:
    antes = _tareas_ajenas()
    reloj = Reloj()
    lector = Lector(reloj, soltar=asyncio.Event())
    lectura = _lectura(lector, reloj)

    lectura.start(_turno())
    await _ceder()
    lectura.drop(Discard.KEPT_TALKING)
    lectura.start(_turno("otra cosa que dijo la persona"))
    await _ceder()
    await lectura.aclose()

    assert _tareas_ajenas() == antes
    assert [e["cause"] for e in _eventos(salida)] == ["kept_talking", "call_ended"]
    assert lector.canceladas == 2


async def test_cancelar_a_quien_espera_la_lectura_la_cancela_tambien() -> None:
    antes = _tareas_ajenas()
    reloj = Reloj()
    lector = Lector(reloj, soltar=asyncio.Event())
    lectura = _lectura(lector, reloj)
    lectura.start(_turno())
    await _ceder()

    espera = asyncio.create_task(lectura.take(_turno(), turn_id="llamada-1-t1"))
    await _ceder()
    espera.cancel()
    with pytest.raises(asyncio.CancelledError):
        await espera
    await lectura.aclose()

    assert lector.canceladas == 1
    assert _tareas_ajenas() == antes


# --- Fallos y rastro ------------------------------------------------------------------


async def test_un_fallo_inesperado_no_tumba_el_turno_y_deja_tipo_y_sitio_sin_mensaje(
    salida: io.StringIO,
) -> None:
    reloj = Reloj()
    lector = Lector(reloj, falla=RuntimeError("mi placa es ABC123"))
    lectura = _lectura(lector, reloj)

    lectura.start(_turno())
    await _ceder()
    tomada = await lectura.take(_turno(), turn_id="llamada-1-t1")

    assert tomada is None, "el turno lee por su cuenta"
    (evento,) = _eventos(salida)
    assert evento["outcome"] == "failed"
    assert evento["error_type"] == "RuntimeError"
    assert isinstance(evento["where"], str)
    assert "ABC123" not in salida.getvalue()


async def test_un_fallo_de_una_lectura_ya_soltada_tambien_deja_rastro(
    salida: io.StringIO,
) -> None:
    reloj = Reloj()
    lector = Lector(reloj, falla=ValueError("dato de la persona"))
    lectura = _lectura(lector, reloj)

    lectura.start(_turno())
    await _ceder()
    lectura.drop(Discard.KEPT_TALKING)
    await lectura.aclose()

    assert [e["outcome"] for e in _eventos(salida)] == ["discarded", "failed"]
    assert "dato de la persona" not in salida.getvalue()


_RASTRO: ContextVar[str] = ContextVar("rastro_de_la_prueba", default="sin turno")


@dataclass
class LectorConRastro(Lector):
    """Un lector que abre y cierra una variable de contexto, como el turno de verdad.

    Cancelarlo con la variable puesta es lo que rompia las llamadas reales el 2026-10-12 cuando
    el generador se consumia desde otra tarea: aqui la lectura es una corrutina que vive y muere
    en una sola tarea, y la variable se pone y se repone ahi.
    """

    async def __call__(self, turn: InboundTurn) -> UnderstandingResponse | None:
        marca = _RASTRO.set("turno de la lectura")
        try:
            return await super().__call__(turn)
        finally:
            _RASTRO.reset(marca)


async def test_cancelar_una_lectura_con_el_rastro_abierto_no_rompe_nada_ni_ensucia_a_la_llamada() -> (
    None
):
    reloj = Reloj()
    lector = LectorConRastro(reloj, soltar=asyncio.Event())
    lectura = _lectura(lector, reloj)

    lectura.start(_turno())
    await _ceder()
    assert _RASTRO.get() == "sin turno", "la variable de la lectura no se filtra a la llamada"
    lectura.drop(Discard.KEPT_TALKING)
    await lectura.aclose()

    assert lector.canceladas == 1
    assert _RASTRO.get() == "sin turno"


async def test_el_evento_lleva_recuentos_y_milisegundos_pero_nunca_el_texto(
    salida: io.StringIO,
) -> None:
    reloj = Reloj()
    lectura = _lectura(Lector(reloj, tarda=0.5), reloj)

    lectura.start(_turno())
    await _ceder()
    await lectura.take(_turno(), turn_id="llamada-1-t1")

    (evento,) = _eventos(salida)
    assert evento["words"] == len(TEXTO.split())
    assert "choque" not in salida.getvalue()
    assert set(evento) <= {
        "event",
        "tenant_id",
        "call_id",
        "turn_id",
        "outcome",
        "cause",
        "words",
        "ran_ms",
        "finished",
        "understood",
        "waited_ms",
        "saved_ms",
        "error_type",
        "where",
    }


async def test_la_hora_de_llegada_del_turno_no_invalida_la_lectura() -> None:
    """Lo comparado es el caso, el idioma y el texto. Un final vacio que llega despues mueve la
    hora del turno sin cambiar lo que dijo la persona."""
    reloj = Reloj()
    lectura = _lectura(Lector(reloj), reloj)

    lectura.start(_turno())
    await _ceder()
    mas_tarde = replace(_turno(), received_at=AHORA.replace(minute=5))

    assert await lectura.take(mas_tarde, turn_id="llamada-1-t1") == Taken(response=ENTENDIDO)
