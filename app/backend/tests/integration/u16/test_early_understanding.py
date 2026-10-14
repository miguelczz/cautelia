"""La lectura adelantada, con el motor y el ciclo de la llamada de verdad (2026-10-13).

`tests/unit/voice/test_early_understanding.py` prueba la pieza sola. Aqui se prueba lo que la
rodea: **cuando** el motor decide adelantar (y cuando no), que el turno recoja lo adelantado sin
volver a llamar al modelo, y que el ciclo la lance, la cancele y la suelte segun lo que oye.

El modelo es un doble que cuenta sus llamadas y puede quedarse esperando; ningun proveedor se
toca. El turno es el doble de `test_call_engine` (`_TurnoRegistrado`), que guarda lo que recibe:
ahi se mira `understood` y `understood_by_channel`.
"""

from __future__ import annotations

import asyncio
import io
import json
import sys
import time
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

import pytest

from untangle import observability
from untangle.orchestration.contracts import InboundTurn, TurnEvent
from untangle.orchestration.nodes.intake.understanding import UnderstandingResponse, Want
from untangle.voice import answers
from untangle.voice.call import CallEngine
from untangle.voice.early_understanding import Discard
from untangle.voice.loop import CallRunner
from untangle.voice.turn_detection import SpeechEnd

from ...unit.voice.dobles import final as final_con_tiempos
from ...unit.voice.dobles import parcial, senal
from .conftest import AHORA
from .test_call_engine import _final_simple, _motor, _TurnoRegistrado
from .test_call_loop import SILENCIO, CanalFalso, VozDoble

pytestmark = pytest.mark.usefixtures("base_de_u16")

#: Un reporte de choque: sustancia de sobra, sin codigos, sin pedir nada aparte.
REPORTE = "My car was hit on the highway this morning."
MAS = "And nobody was hurt at all."

ENTENDIDO = UnderstandingResponse(wants=Want.REPORT_ACCIDENT, reply="Understood.")


@dataclass
class Lector:
    """El modelo, con la forma de `understand_turn`: cuenta sus llamadas y puede bloquearse."""

    respuesta: UnderstandingResponse | None = ENTENDIDO
    #: La primera lectura se queda esperando para siempre (hasta que la cancelen): es la que
    #: la persona deja atras al seguir hablando.
    bloquea_la_primera: bool = False
    #: Cuanto tarda cada lectura, en segundos reales.
    tarda: float = 0.0
    textos: list[str] = field(default_factory=list)
    empezo_a: list[float] = field(default_factory=list)
    canceladas: int = 0

    async def __call__(self, turn: InboundTurn) -> UnderstandingResponse | None:
        self.textos.append(turn.text)
        self.empezo_a.append(time.monotonic())
        try:
            if self.bloquea_la_primera and len(self.textos) == 1:
                await asyncio.Event().wait()
            if self.tarda:
                await asyncio.sleep(self.tarda)
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


async def _ceder(veces: int = 50) -> None:
    for _ in range(veces):
        await asyncio.sleep(0)


async def _motor_que_adelanta(
    tenant_id: str, lector: Lector, *, decidido: bool = True
) -> tuple[CallEngine, _TurnoRegistrado]:
    """El motor con la apertura dicha, el modelo enchufado y, por omision, a que llama ya decidido."""
    motor, grafo = await _motor(tenant_id, guion=(_final_simple("Got it."),))
    motor = replace(
        motor,
        understand=lector,
        # Las esperas de estas pruebas son reales: pocas decimas.
        end_of_speech=timedelta(milliseconds=250),
        unpunctuated_end_of_speech=timedelta(milliseconds=250),
        incomplete_end_of_speech=timedelta(milliseconds=250),
        signal_grace=timedelta(milliseconds=250),
        signal_only_extension=timedelta(milliseconds=250),
    )
    await motor.opening_finished(at=AHORA)
    motor._proposito_decidido = decidido
    return motor, grafo


def _habla(texto: str, *, confianza: float | None = 0.95) -> SpeechEnd:
    return SpeechEnd(
        text=texto,
        at=AHORA + timedelta(seconds=1),
        last_audible_word_at=None,
        last=final_con_tiempos(texto, confianza=confianza),
    )


async def _decir_el_turno(motor: CallEngine, habla: SpeechEnd, *, turn_id: str = "t-1") -> None:
    async def _todo() -> None:
        async for _ in motor.speak_turn(habla, turn_id=turn_id):
            pass

    # Con un tope: si una regla se rompe, el turno se quedaria esperando una lectura que no termina.
    await asyncio.wait_for(_todo(), timeout=5)


# --- El motor: cuando adelanta y cuando el turno recoge lo adelantado ------------------


async def test_el_turno_recoge_la_lectura_adelantada_y_no_vuelve_a_llamar_al_modelo(
    dos_aseguradoras: tuple[str, str], salida: io.StringIO
) -> None:
    a, _ = dos_aseguradoras
    lector = Lector(tarda=0.01)
    motor, grafo = await _motor_que_adelanta(a, lector)
    habla = _habla(REPORTE)

    motor.advance_understanding(habla)
    await _decir_el_turno(motor, habla)
    await motor.close_advanced()

    (turno,) = grafo.recibidos
    assert turno.understood == ENTENDIDO
    assert turno.understood_by_channel is True
    assert lector.textos == [REPORTE], "el turno no debe volver a llamar al modelo"
    (evento,) = _eventos(salida)
    assert (evento["outcome"], evento["turn_id"]) == ("used", "t-1")
    assert evento["understood"] is True


async def test_sin_lectura_adelantada_el_turno_llega_al_grafo_como_siempre(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    motor, grafo = await _motor_que_adelanta(a, Lector())

    await _decir_el_turno(motor, _habla(REPORTE))

    (turno,) = grafo.recibidos
    assert turno.understood is None
    assert turno.understood_by_channel is False, "el grafo lee por su cuenta"


async def test_si_el_modelo_no_pudo_el_turno_sigue_por_reglas_sin_volver_a_llamarlo(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Igual que el chat: repetir la llamada duplicaria la espera justo cuando el proveedor
    anda mal."""
    a, _ = dos_aseguradoras
    lector = Lector(respuesta=None)
    motor, grafo = await _motor_que_adelanta(a, lector)
    habla = _habla(REPORTE)

    motor.advance_understanding(habla)
    await _decir_el_turno(motor, habla)

    (turno,) = grafo.recibidos
    assert turno.understood is None
    assert turno.understood_by_channel is True
    assert lector.textos == [REPORTE]


async def test_la_lectura_en_vuelo_se_espera_cuando_el_turno_cierra(
    dos_aseguradoras: tuple[str, str], salida: io.StringIO
) -> None:
    a, _ = dos_aseguradoras
    lector = Lector(tarda=0.15)
    motor, grafo = await _motor_que_adelanta(a, lector)
    habla = _habla(REPORTE)

    motor.advance_understanding(habla)
    await _ceder()
    await _decir_el_turno(motor, habla)

    (turno,) = grafo.recibidos
    assert turno.understood == ENTENDIDO
    (evento,) = _eventos(salida)
    assert evento["outcome"] == "used"
    assert isinstance(evento["waited_ms"], int)
    assert evento["waited_ms"] > 0, "la lectura seguia en vuelo y el turno la espero"
    assert isinstance(evento["saved_ms"], int)
    assert evento["saved_ms"] >= 0


@pytest.mark.parametrize("cambio", ["idioma", "texto"])
async def test_la_lectura_no_vale_si_cambio_el_idioma_o_el_texto(
    dos_aseguradoras: tuple[str, str], salida: io.StringIO, cambio: str
) -> None:
    a, _ = dos_aseguradoras
    lector = Lector(bloquea_la_primera=True)
    motor, grafo = await _motor_que_adelanta(a, lector)
    motor.advance_understanding(_habla(REPORTE))
    await _ceder()

    habla = _habla(REPORTE)
    if cambio == "idioma":
        motor.call = replace(motor.call, language="es")
    else:
        habla = _habla(f"{REPORTE} {MAS}")
    await _decir_el_turno(motor, habla)
    await motor.close_advanced()

    (turno,) = grafo.recibidos
    assert turno.understood is None
    assert turno.understood_by_channel is False, "el turno lee por su cuenta lo que ya no vale"
    (evento,) = _eventos(salida)
    assert (evento["outcome"], evento["cause"], evento["turn_id"]) == (
        "discarded",
        "state_changed",
        "t-1",
    )
    assert lector.canceladas == 1


async def test_la_lectura_de_un_caso_no_sirve_para_otro(
    dos_aseguradoras: tuple[str, str], salida: io.StringIO
) -> None:
    a, _ = dos_aseguradoras
    lector = Lector(bloquea_la_primera=True)
    motor, _ = await _motor_que_adelanta(a, lector)
    motor.advance_understanding(_habla(REPORTE))
    await _ceder()
    adelantada = motor._early
    assert adelantada is not None

    motor.call = replace(motor.call, case_id="otro-caso")
    tomada = await asyncio.wait_for(
        adelantada.take(motor._inbound(REPORTE, received_at=AHORA), turn_id="t-1"), timeout=5
    )
    await motor.close_advanced()

    assert tomada is None
    assert [e["cause"] for e in _eventos(salida)] == ["state_changed"]
    assert lector.canceladas == 1


# --- Cuando NO se adelanta: el turno va por una regla de la llamada o no llega al modelo ---


def _esperando_confirmar(motor: CallEngine) -> None:
    motor._por_confirmar = ("ABC123", "mi placa es ABC123")


def _con_oferta(motor: CallEngine) -> None:
    motor._oferta_pendiente = True


def _cerrado(motor: CallEngine) -> None:
    motor.closed = True


_DICTADO = "ay as in alpha, bee as in bravo, see as in charlie, one, two, three"


@pytest.mark.parametrize(
    ("dicho", "confianza", "preparar"),
    [
        pytest.param("yes please", 0.95, None, id="una-respuesta-de-dos-palabras"),
        pytest.param("give me a second please", 0.95, None, id="pide-que-se-espere"),
        pytest.param("En español, por favor", 0.95, None, id="pide-otro-idioma"),
        pytest.param(REPORTE, 0.2, None, id="no-se-entendio-bien"),
        pytest.param(_DICTADO, 0.95, None, id="dicta-una-placa-que-se-lee-de-vuelta"),
        pytest.param(REPORTE, 0.95, _esperando_confirmar, id="espera-confirmar-un-codigo"),
        pytest.param(REPORTE, 0.95, _con_oferta, id="espera-la-respuesta-a-la-oferta"),
        pytest.param(REPORTE, 0.95, _cerrado, id="el-cierre-ya-se-dijo"),
    ],
)
async def test_lo_que_resuelve_una_regla_de_la_llamada_no_se_adelanta(
    dos_aseguradoras: tuple[str, str],
    dicho: str,
    confianza: float,
    preparar: Callable[[CallEngine], None] | None,
) -> None:
    a, _ = dos_aseguradoras
    lector = Lector()
    motor, _ = await _motor_que_adelanta(a, lector)
    if preparar is not None:
        preparar(motor)

    motor.advance_understanding(_habla(dicho, confianza=confianza))
    await _ceder()
    await motor.close_advanced()

    assert lector.textos == [], "se pago una lectura que el turno iba a tirar"


async def test_el_primer_turno_que_abre_otro_caso_no_se_adelanta(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Una duda de su poliza abre una consulta: la lectura seria del caso viejo."""
    a, _ = dos_aseguradoras
    lector = Lector()
    motor, _ = await _motor_que_adelanta(a, lector, decidido=False)

    motor.advance_understanding(_habla("I have a question about my policy coverage"))
    await _ceder()
    await motor.close_advanced()

    assert lector.textos == []


async def test_el_primer_turno_que_reporta_un_choque_si_se_adelanta(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Es el turno mas largo de la llamada y el que mas se nota; sigue en el mismo caso."""
    a, _ = dos_aseguradoras
    lector = Lector()
    motor, grafo = await _motor_que_adelanta(a, lector, decidido=False)
    habla = _habla(REPORTE)

    motor.advance_understanding(habla)
    await _decir_el_turno(motor, habla)

    assert lector.textos == [REPORTE]
    assert grafo.recibidos[0].understood == ENTENDIDO


async def test_sin_modelo_enchufado_no_hay_nada_que_adelantar(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    motor, grafo = await _motor(a, guion=(_final_simple("Got it."),))
    await motor.opening_finished(at=AHORA)
    motor._proposito_decidido = True
    habla = _habla(REPORTE)

    motor.advance_understanding(habla)
    motor.drop_advanced(Discard.KEPT_TALKING)
    await _decir_el_turno(motor, habla)
    await motor.close_advanced()

    assert grafo.recibidos[0].understood_by_channel is False


# --- El ciclo: lanza, cancela y suelta segun lo que oye --------------------------------


def _reloj() -> datetime:
    return AHORA + timedelta(seconds=1)


def _ciclo(motor: CallEngine, doble: VozDoble | None = None) -> CallRunner:
    return CallRunner(
        engine=motor,
        channel=CanalFalso(),
        speech=doble if doble is not None else VozDoble(),
        now=_reloj,
        max_call=timedelta(seconds=180),
        warn_at=timedelta(seconds=30),
    )


async def test_el_final_lanza_la_lectura_sin_esperar_la_tolerancia(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    lector = Lector()
    motor, _ = await _motor_que_adelanta(a, lector)
    ciclo = _ciclo(motor)
    detector = motor.listening(since=_reloj())

    await ciclo._oir(final_con_tiempos(REPORTE), detector)
    await _ceder()

    assert detector.speaking
    assert lector.textos == [REPORTE]
    await motor.close_advanced()


async def test_un_parcial_con_palabras_cancela_la_lectura_y_el_final_siguiente_la_relee_completa(
    dos_aseguradoras: tuple[str, str], salida: io.StringIO
) -> None:
    a, _ = dos_aseguradoras
    lector = Lector(bloquea_la_primera=True)
    motor, grafo = await _motor_que_adelanta(a, lector)
    ciclo = _ciclo(motor)
    detector = motor.listening(since=_reloj())

    await ciclo._oir(final_con_tiempos(REPORTE), detector)
    await _ceder()
    await ciclo._oir(parcial("and"), detector)
    await _ceder()
    assert lector.canceladas == 1, "la lectura de la frase a medias se cancela"

    await ciclo._oir(final_con_tiempos(MAS), detector)
    await _ceder()
    cerrado = detector.close()
    await ciclo._atender(cerrado)

    completo = f"{REPORTE} {MAS}"
    assert lector.textos == [REPORTE, completo]
    assert grafo.recibidos[-1].text == completo
    assert grafo.recibidos[-1].understood == ENTENDIDO
    assert [(e["outcome"], e.get("cause")) for e in _eventos(salida)] == [
        ("discarded", "kept_talking"),
        ("used", None),
    ]


async def test_una_frase_a_medias_no_se_adelanta(dos_aseguradoras: tuple[str, str]) -> None:
    """Termina en una palabra que pide continuacion: casi nunca esta acabada, y su espera es la
    mas larga a proposito. Leerla antes seria pagar el modelo para tirarlo."""
    a, _ = dos_aseguradoras
    lector = Lector()
    motor, _ = await _motor_que_adelanta(a, lector)
    ciclo = _ciclo(motor)
    detector = motor.listening(since=_reloj())

    await ciclo._oir(final_con_tiempos("I was driving on the highway and my"), detector)
    await _ceder()

    assert lector.textos == []


async def test_si_la_frase_crece_hasta_quedar_a_medias_la_lectura_anterior_se_suelta(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    lector = Lector(bloquea_la_primera=True)
    motor, _ = await _motor_que_adelanta(a, lector)
    ciclo = _ciclo(motor)
    detector = motor.listening(since=_reloj())

    await ciclo._oir(final_con_tiempos(REPORTE), detector)
    await _ceder()
    await ciclo._oir(final_con_tiempos("And the other driver was driving with the"), detector)
    await _ceder()

    assert lector.canceladas == 1
    assert len(lector.textos) == 1, "la frase nueva termina a medias: no se lee todavia"


async def test_una_respuesta_del_fondo_descarta_la_lectura_adelantada(
    dos_aseguradoras: tuple[str, str], salida: io.StringIO
) -> None:
    """El estado del caso que la lectura vio ya no es el de ahora."""
    a, _ = dos_aseguradoras
    lector = Lector(bloquea_la_primera=True)
    motor, _ = await _motor_que_adelanta(a, lector)
    ciclo = _ciclo(motor)
    detector = motor.listening(since=_reloj())
    await ciclo._oir(final_con_tiempos(REPORTE), detector)
    await _ceder()

    ciclo._llego_del_fondo(answers.BackgroundAnswer(text="I found the clause."))
    await _ceder()
    await motor.close_advanced()

    assert lector.canceladas == 1
    (evento,) = _eventos(salida)
    assert (evento["outcome"], evento["cause"]) == ("discarded", "state_changed")


async def test_si_el_turno_toma_otro_camino_la_lectura_se_suelta_y_dice_en_que_turno(
    dos_aseguradoras: tuple[str, str], salida: io.StringIO
) -> None:
    """La red de seguridad: si lo que el motor supuso al adelantar dejo de ser cierto y el turno
    no llega al modelo, la lectura no queda esperando a nadie."""
    a, _ = dos_aseguradoras
    lector = Lector(bloquea_la_primera=True)
    motor, grafo = await _motor_que_adelanta(a, lector)
    ciclo = _ciclo(motor)
    detector = motor.listening(since=_reloj())
    # Una lectura lanzada para un texto que el turno resuelve aparte (un pedido de espera).
    pedido = "give me a second please"
    assert motor._early is not None
    motor._early.start(motor._inbound(pedido, received_at=_reloj()))
    await _ceder()
    detector.observe(final_con_tiempos(pedido), at=_reloj())

    hubo, motivo = await ciclo._al_vencer(detector, _reloj(), _reloj() + timedelta(seconds=1))
    await motor.close_advanced()

    assert (hubo, motivo) == (True, None)
    assert grafo.recibidos == [], "un pedido de espera no llega al grafo"
    (evento,) = _eventos(salida)
    assert (evento["outcome"], evento["cause"]) == ("discarded", "not_needed")
    assert evento["turn_id"] == f"{motor.call.call_id}-t1"
    assert lector.canceladas == 1


async def _correr_de_verdad(
    motor: CallEngine, doble: VozDoble, *, hasta: int = 2
) -> tuple[CallRunner, CanalFalso]:
    """La llamada entera, con el reloj de pared: la tolerancia es real, de pocas decimas."""
    canal = CanalFalso(seguir=lambda: len(doble.dicho) < hasta)
    ciclo = CallRunner(
        engine=motor,
        channel=canal,
        speech=doble,
        now=lambda: datetime.now(UTC),
        # La llamada se sembro en una fecha fija: una duracion larga evita la despedida por tiempo.
        max_call=timedelta(days=3650),
        warn_at=timedelta(seconds=30),
    )
    await asyncio.wait_for(ciclo.run(), timeout=10)
    return ciclo, canal


async def test_en_la_llamada_entera_la_lectura_arranca_con_el_final_y_el_turno_la_recoge(
    dos_aseguradoras: tuple[str, str], salida: io.StringIO
) -> None:
    """El cambio de fondo: el modelo ya leyo cuando vence la tolerancia (250 ms reales)."""
    a, _ = dos_aseguradoras
    lector = Lector(tarda=0.05)
    motor, grafo = await _motor_que_adelanta(a, lector)
    arranco_el_turno: list[float] = []
    original = grafo._emitir

    def _emitir(turn: InboundTurn) -> AsyncIterator[TurnEvent]:
        arranco_el_turno.append(time.monotonic())
        return original(turn)

    grafo._emitir = _emitir  # type: ignore[method-assign]
    doble = VozDoble(guion=[final_con_tiempos(REPORTE)])
    doble.esperar_a = lambda: motor.disclosed_at is not None

    await _correr_de_verdad(motor, doble)

    assert lector.textos == [REPORTE]
    (turno,) = grafo.recibidos
    assert turno.understood == ENTENDIDO and turno.understood_by_channel
    adelanto = arranco_el_turno[0] - lector.empezo_a[0]
    assert adelanto >= 0.15, f"la lectura arranco solo {adelanto:.3f} s antes del turno"
    (evento,) = _eventos(salida)
    assert evento["outcome"] == "used"
    assert evento["waited_ms"] == 0, "la lectura ya habia terminado cuando vencio la tolerancia"
    assert isinstance(evento["saved_ms"], int) and evento["saved_ms"] > 0
    # Y la medida de la espera de la persona sigue siendo la de siempre: desde el fin del habla.
    (primero,) = [e for e in _todos(salida) if e["event"] == "voice.first_audio"]
    assert isinstance(primero["elapsed_ms"], int)
    assert "elapsed_from_last_word_ms" in primero


def _todos(salida: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(linea) for linea in salida.getvalue().splitlines() if linea.strip()]


async def test_en_la_llamada_entera_la_senal_sola_no_cancela_la_lectura(
    dos_aseguradoras: tuple[str, str], salida: io.StringIO
) -> None:
    """Un ruido tras el final (la senal de voz sin palabras) no es la persona retomando la
    frase: la lectura que corre sigue, el turno la recoge y no se paga una segunda (2026-10-13).
    Cambia a proposito la prueba de 2026-10-13 que esperaba cancelarla con la senal."""
    a, _ = dos_aseguradoras
    lector = Lector(tarda=0.05)
    motor, grafo = await _motor_que_adelanta(a, lector)
    doble = VozDoble(guion=[final_con_tiempos(REPORTE), senal(0.3)])
    doble.esperar_a = lambda: motor.disclosed_at is not None

    await _correr_de_verdad(motor, doble)

    assert lector.canceladas == 0
    assert lector.textos == [REPORTE], "una sola lectura: la del final"
    (turno,) = grafo.recibidos
    assert turno.understood == ENTENDIDO and turno.understood_by_channel
    assert [(e["outcome"], e.get("cause")) for e in _eventos(salida)] == [("used", None)]
    (ruido,) = [e for e in _todos(salida) if e["event"] == "voice.speech_signal_discarded"]
    assert ruido["signals"] == 1


async def test_en_la_llamada_entera_la_senal_con_palabras_cancela_la_lectura(
    dos_aseguradoras: tuple[str, str], salida: io.StringIO
) -> None:
    """La senal y, detras, un parcial con palabras: la persona retomo de verdad. Se suelta la
    lectura, como antes, pero ahora lo decide el parcial y no la senal."""
    a, _ = dos_aseguradoras
    lector = Lector(bloquea_la_primera=True)
    motor, grafo = await _motor_que_adelanta(a, lector)
    doble = VozDoble(guion=[final_con_tiempos(REPORTE), senal(0.3), parcial("and")])
    doble.esperar_a = lambda: motor.disclosed_at is not None

    await _correr_de_verdad(motor, doble)

    assert lector.canceladas == 1
    assert lector.textos == [REPORTE], "sin final nuevo no se lee otra vez"
    (turno,) = grafo.recibidos
    assert turno.understood is None and turno.understood_by_channel is False
    causas = [(e["outcome"], e.get("cause")) for e in _eventos(salida)]
    assert causas == [("discarded", "kept_talking")]
    assert [e for e in _todos(salida) if e["event"] == "voice.speech_signal_discarded"] == []


async def test_si_cancelan_la_llamada_con_una_lectura_en_vuelo_no_queda_nada_colgando(
    dos_aseguradoras: tuple[str, str], salida: io.StringIO
) -> None:
    a, _ = dos_aseguradoras
    lector = Lector(bloquea_la_primera=True)
    motor, _ = await _motor_que_adelanta(a, lector)
    # Sin ceder por tolerancia: el turno no cierra mientras la prueba mira.
    motor.end_of_speech = timedelta(seconds=30)
    motor.unpunctuated_end_of_speech = timedelta(seconds=30)
    doble = VozDoble(guion=[final_con_tiempos(REPORTE)])
    doble.esperar_a = lambda: motor.disclosed_at is not None
    canal = CanalFalso(entrantes=[SILENCIO], seguir=lambda: True)
    ciclo = CallRunner(
        engine=motor,
        channel=canal,
        speech=doble,
        now=lambda: datetime.now(UTC),
        max_call=timedelta(days=3650),
        warn_at=timedelta(seconds=30),
    )
    antes = {t for t in asyncio.all_tasks() if t is not asyncio.current_task()}

    llamada = asyncio.create_task(ciclo.run())
    for _ in range(500):
        if lector.textos:
            break
        await asyncio.sleep(0.01)
    assert lector.textos == [REPORTE], "la lectura no llego a lanzarse"
    llamada.cancel()
    with pytest.raises(asyncio.CancelledError):
        await llamada

    assert lector.canceladas == 1
    assert {t for t in asyncio.all_tasks() if t is not asyncio.current_task()} == antes
    assert [e.get("cause") for e in _eventos(salida)] == ["call_ended"]
