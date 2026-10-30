"""El ritmo de la llamada: la apertura, el turno y los silencios.

Es de integracion porque la compuerta BR2.1 se apoya en el registro de
divulgacion de U10, que vive en la base. Lo que **no** toca la red es el
reconocedor ni la sintesis: entran como dobles que heredan de los `Protocol` de
C-16.
"""

from __future__ import annotations

import asyncio
import io
import json
from collections.abc import AsyncIterator, Coroutine
from contextvars import ContextVar
from datetime import timedelta

import pytest

from untangle import observability
from untangle.case_record import api as casos
from untangle.case_record import crypto
from untangle.case_record.models import (
    Actor,
    ActorType,
    CaseField,
    DerivationReason,
    FieldStatus,
    Speaker,
)
from untangle.case_record.models import Channel as CaseChannel
from untangle.compliance.controls import api as u10
from untangle.compliance.controls.api import HandoffReason
from untangle.copy_catalog import api as copy_api
from untangle.orchestration.contracts import (
    FinalText,
    Handoff,
    InboundTurn,
    PartialText,
    TurnError,
    TurnEvent,
    Waiting,
)
from untangle.tenancy import config as tenancy_config
from untangle.voice import (
    barge_in,
    call,
    case_number,
    case_opening,
    closing,
    latency,
    opening,
    readback,
    retry,
    silence,
)
from untangle.voice import session as llamadas
from untangle.voice.call import CallEngine, Utterance
from untangle.voice.models import EndReason, VoiceMode
from untangle.voice.turn_detection import Ending, SpeechEnd, TurnDetector

from ...unit.voice.dobles import VACIO, con_rastro, final
from .conftest import AHORA

pytestmark = pytest.mark.usefixtures("base_de_u16")

MI_NAVEGADOR = "3" * 64

_RASTRO = ContextVar[str | None]("rastro_del_grafo", default=None)


class _TurnoRegistrado:
    """Un manejador de turnos que guarda lo que le entregaron y devuelve un guion.

    **No es mas permisivo que la pieza real**: `handle_turn` levanta si el turno
    llega sin caso, y este hace lo mismo. Un doble que aceptara un turno sin caso
    es exactamente la forma que dejo el chat sin atender a nadie.
    """

    def __init__(self, guion: tuple[TurnEvent, ...]) -> None:
        self.guion = guion
        self.recibidos: list[InboundTurn] = []

    async def _emitir(self, turn: InboundTurn) -> AsyncIterator[TurnEvent]:
        if turn.case_id is None:
            msg = "handle_turn necesita case_id"
            raise ValueError(msg)
        self.recibidos.append(turn)
        for evento in self.guion:
            yield evento

    def __call__(self, turn: InboundTurn) -> AsyncIterator[TurnEvent]:
        return self._emitir(turn)


def _primer_motivo() -> HandoffReason:
    """Un motivo de derivacion del conjunto cerrado, sin escribir cual."""
    return next(iter(HandoffReason))


def _final_simple(texto: str) -> FinalText:
    return FinalText(message_id="m-1", text=texto, language="en")


async def _motor(
    tenant_id: str, *, guion: tuple[TurnEvent, ...] = ()
) -> tuple[CallEngine, _TurnoRegistrado]:
    copy_api.install(copy_api.load())
    config = tenancy_config.require(tenant_id)
    case_id = await case_opening.open_for_call(tenant_id, language="en", now=AHORA)
    llamada = await llamadas.open_call(
        tenant_id=tenant_id,
        visitor_key_digest=MI_NAVEGADOR,
        language="en",
        voice_mode=VoiceMode.PRIMARY,
        now=AHORA,
    )
    llamada = await llamadas.attach_case(llamada, case_id=case_id)
    manejador = _TurnoRegistrado(guion)
    return CallEngine(call=llamada, config=config, handle_turn=con_rastro(manejador)), manejador


def _habla(motor: CallEngine, texto: str, *, segundos: float = 1.0) -> SpeechEnd:
    """Un turno de la persona ya cerrado, con su marca."""
    llegada = AHORA + timedelta(seconds=segundos)
    # El flujo de audio de la llamada empieza con la prueba: los tiempos de palabra del
    # doble cuentan desde ahi, y la ultima palabra audible se calcula contra ese origen.
    detector = motor.listening(since=AHORA, stream_started_at=AHORA)
    detector.observe(final(texto) if texto else VACIO, at=llegada)
    return detector.close()


async def _completar_caso(tenant_id: str, case_id: str, cifrador: crypto.Cipher) -> None:
    """Deja el caso con todos sus campos confirmados, por la API de U4.

    Se recorren los que la propia completitud declara pendientes en vez de
    escribir la lista: si el esquema gana un campo, esto lo llena igual y la
    prueba sigue midiendo lo mismo.
    """
    actor = Actor(actor_type=ActorType.INSURED)
    for _ in range(20):
        vista = await casos.get_case(tenant_id, case_id)
        assert vista is not None
        pendientes = [c for c, listo in vista.completeness.per_field.items() if not listo]
        if not pendientes:
            return
        await casos.set_field(
            tenant_id,
            CaseField(
                case_id=case_id,
                field_key=pendientes[0],
                value=cifrador.seal("lo que dijo"),
                status=FieldStatus.CONFIRMED,
                evidence_turn_id=f"turno-{pendientes[0]}",
                confirmed_aloud_at=AHORA,
                updated_at=AHORA,
            ),
            cipher=cifrador,
            actor=actor,
        )
    msg = "el caso no llego a completarse"
    raise AssertionError(msg)


# --- La apertura (BR2.1 a BR2.4) ---------------------------------------------


async def test_la_apertura_sale_del_catalogo_y_ya_redactada(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a)
    dicha = motor.opening()
    assert isinstance(dicha, Utterance)
    assert dicha.copy_key == opening.DISCLOSURE
    assert "transcribed" in dicha.text


async def test_ningun_turno_se_atiende_antes_de_la_apertura(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR2.1, compuerta dura. Es la misma que ya cumple el chat, y en voz pesa
    mas: hablar es mas facil que escribir y no hay pantalla que lo recuerde."""
    a, _ = dos_aseguradoras
    motor, manejador = await _motor(a, guion=(_final_simple("ok"),))
    with pytest.raises(ValueError, match=r"BR2\.1"):
        async for _ in motor.speak_turn(_habla(motor, "hello"), turn_id="t-1"):
            pass
    assert manejador.recibidos == []


async def test_la_divulgacion_se_registra_con_la_hora_del_final(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR2.3: una apertura que no llego al final no esta dicha, y lo que las
    distingue es que esta llamada no ocurrio."""
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a)
    fin = AHORA + timedelta(seconds=12)
    assert await motor.opening_finished(at=fin)
    assert motor.call.case_id is not None
    registros = await u10.disclosures(a, motor.call.case_id)
    assert len(registros) == 1
    assert registros[0].disclosed_at == fin
    assert registros[0].channel.value == "voice"


async def test_la_segunda_llamada_no_duplica_el_registro(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR2.4: `False` no es un error, es la segunda vez, y la primera sigue."""
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a)
    primera = AHORA + timedelta(seconds=12)
    assert await motor.opening_finished(at=primera)
    assert not await motor.opening_finished(at=primera + timedelta(minutes=5))
    assert motor.call.case_id is not None
    registros = await u10.disclosures(a, motor.call.case_id)
    assert len(registros) == 1
    assert registros[0].disclosed_at == primera


# --- El turno hablado (BR3.2, BR3.4, BR3.6, BR3.8) ---------------------------


async def test_el_turno_llega_al_grafo_por_el_mismo_contrato_que_el_chat(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR3.2: es lo que hace cierto AC1.23.1, que el mismo guion por los dos
    canales deje los mismos campos."""
    a, _ = dos_aseguradoras
    motor, manejador = await _motor(a, guion=(_final_simple("Got it."),))
    await motor.opening_finished(at=AHORA)

    dichas = [
        u async for u in motor.speak_turn(_habla(motor, "highway exit twelve"), turn_id="t-1")
    ]

    assert len(manejador.recibidos) == 1
    turno = manejador.recibidos[0]
    assert turno.channel == "voice"
    assert turno.case_id == motor.call.case_id
    assert turno.text == "highway exit twelve"
    assert turno.session_ref == motor.call.call_id
    assert [str(u.text) for u in dichas] == ["Got it."]


async def test_cortar_el_turno_a_medias_cierra_el_grafo_en_la_tarea_de_quien_lo_corta(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Cerrar `speak_turn` antes de agotarlo cierra tambien al grafo que recorre: lo que se
    deja al recolector se cierra desde otra tarea, y el rastro del turno (variables de
    contexto) no se repone fuera de la tarea donde se abrio (2026-10-12)."""
    a, _ = dos_aseguradoras
    visto: list[str | None] = []

    async def grafo(turn: InboundTurn) -> AsyncIterator[TurnEvent]:
        token = _RASTRO.set(turn.session_ref)
        try:
            yield _final_simple("Uno.")
            yield _final_simple("Dos.")
        finally:
            _RASTRO.reset(token)
            visto.append("cerrado")

    motor, _ = await _motor(a)
    motor.handle_turn = grafo
    await motor.opening_finished(at=AHORA)
    frases = motor.speak_turn(_habla(motor, "highway exit twelve"), turn_id="t-1")

    assert str((await anext(frases)).text) == "Uno."
    assert _RASTRO.get() is not None
    await frases.aclose()

    assert visto == ["cerrado"], "el grafo siguio abierto al cerrar el turno"
    assert _RASTRO.get() is None


async def test_los_cinco_eventos_de_c14_tienen_forma_hablada(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR3.6. La union es cerrada y `assert_never` lo obliga: un sexto evento
    deja de compilar. Esta prueba comprueba que los cinco **suenan**."""
    a, _ = dos_aseguradoras
    guion: tuple[TurnEvent, ...] = (
        PartialText(message_id="m", seq=0, text="Got"),
        Waiting(copy_key=copy_api.CopyKey("orchestration.turn.waiting"), text="One moment."),
        FinalText(message_id="m", text="Got it.", language="en"),
        Handoff(
            reason_code=_primer_motivo(),
            copy_key=copy_api.CopyKey("compliance.handoff.adjuster_review"),
            text="A person will review your case.",
        ),
        TurnError(
            code="internal_error",
            copy_key=copy_api.CopyKey("orchestration.turn.error"),
            text="I had trouble answering that.",
        ),
    )
    motor, _ = await _motor(a, guion=guion)
    await motor.opening_finished(at=AHORA)

    dichas = [u async for u in motor.speak_turn(_habla(motor, "hello"), turn_id="t-1")]

    # Una frase por evento, y una mas: tras pasar el caso a un ajustador la agente
    # se despide con el numero de caso (2026-10-11).
    assert len(dichas) == len(guion) + 1
    assert all(str(u.text).strip() for u in dichas)
    # La frase de espera llega con su texto ya resuelto, que es para lo que C-14
    # se lo manda a la voz y no solo la clave.
    assert "One moment." in [str(u.text) for u in dichas]


async def test_una_transcripcion_vacia_no_llega_al_grafo_y_pide_que_lo_repita(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR3.4: no es un dato incompleto, es un dato que no se tiene."""
    a, _ = dos_aseguradoras
    motor, manejador = await _motor(a, guion=(_final_simple("Got it."),))
    await motor.opening_finished(at=AHORA)

    dichas = [u async for u in motor.speak_turn(_habla(motor, ""), turn_id="t-1")]

    assert manejador.recibidos == []
    assert [u.copy_key for u in dichas] == [retry.NOT_UNDERSTOOD]


async def test_a_la_tercera_ofrece_guardar_el_caso_o_pasarlo(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """**El segundo peldano cambio con U18** (BR4.4): la escalera entera, vista
    desde el motor. Decia "no te escuche bien" dos veces y ahora el segundo dice
    que idiomas se atienden; el tercero no se movio.

    Lo que esta prueba sostiene no cambio: tres turnos sin entender no son tres
    veces la misma frase, y el tercero deja de pedir y ofrece otra cosa.
    """
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a)
    await motor.opening_finished(at=AHORA)

    claves = []
    for n in range(3):
        claves += [
            u.copy_key
            async for u in motor.speak_turn(_habla(motor, "", segundos=n + 1), turn_id=f"t-{n}")
        ]

    assert claves == [retry.NOT_UNDERSTOOD, retry.ONLY_TWO_LANGUAGES, retry.OFFER]


async def test_un_turno_bueno_reinicia_la_cuenta(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a, guion=(_final_simple("Got it."),))
    await motor.opening_finished(at=AHORA)

    async for _ in motor.speak_turn(_habla(motor, ""), turn_id="t-1"):
        pass
    async for _ in motor.speak_turn(_habla(motor, "highway", segundos=2), turn_id="t-2"):
        pass
    claves = [
        u.copy_key async for u in motor.speak_turn(_habla(motor, "", segundos=3), turn_id="t-3")
    ]

    assert claves == [retry.NOT_UNDERSTOOD], "la cuenta no se reinicio con el turno bueno"


# --- Los silencios (BR5.1, BR5.2) --------------------------------------------


async def test_los_tres_silencios_van_en_orden_y_solo_el_tercero_cuelga(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a)
    await motor.opening_finished(at=AHORA)

    dichas = [motor.on_silence() for _ in range(3)]

    assert [u.copy_key for u in dichas if u] == [
        silence.STILL_THERE,
        silence.OFFER,
        silence.FAREWELL,
    ]
    assert [u.end_reason for u in dichas if u] == [None, None, EndReason.SILENCE]


async def test_un_turno_reinicia_la_cuenta_de_silencios(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Si no la reiniciara, dos silencios separados por media conversacion
    colgarian la llamada a la tercera pausa del dia."""
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a, guion=(_final_simple("Got it."),))
    await motor.opening_finished(at=AHORA)

    motor.on_silence()
    motor.on_silence()
    async for _ in motor.speak_turn(_habla(motor, "highway"), turn_id="t-1"):
        pass
    primera = motor.on_silence()

    assert primera is not None
    assert primera.copy_key == silence.STILL_THERE


async def test_el_plazo_de_silencio_cuenta_desde_que_la_agente_callo(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR5.1: si corriera mientras habla, su propia respuesta contaria como
    silencio de la persona y la llamada se cerraria sola."""
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a)
    callo = AHORA + timedelta(seconds=30)
    assert motor.silence_deadline(since=callo) == callo + silence.DEFAULT_TOLERANCE


# --- Las trazas (BR8.1) -------------------------------------------------------


async def test_cada_turno_deja_el_evento_de_fin_del_habla_con_sus_dos_variantes(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """AC1.23.5 pide publicar las dos y no la mas favorable."""
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a, guion=(_final_simple("Got it."),))
    await motor.opening_finished(at=AHORA)
    rastro = io.StringIO()
    observability.set_stream(rastro)

    async for _ in motor.speak_turn(_habla(motor, "highway exit twelve"), turn_id="t-1"):
        pass

    lineas = [json.loads(linea) for linea in rastro.getvalue().splitlines() if linea.strip()]
    eventos = [e for e in lineas if e["event"] == latency.SPEECH_END]
    assert len(eventos) == 1
    assert eventos[0]["turn_id"] == "t-1"
    assert eventos[0]["at"]
    assert eventos[0]["last_audible_word_at"]


async def test_el_evento_de_fin_del_habla_no_lleva_lo_que_se_dijo(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """ADR-013: contenido en trazas solo despues de redactar, y estos eventos
    llevan tiempos, no contenido. Es lo que cierra RT-14."""
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a, guion=(_final_simple("Got it."),))
    await motor.opening_finished(at=AHORA)
    rastro = io.StringIO()
    observability.set_stream(rastro)

    async for _ in motor.speak_turn(_habla(motor, "ABC123"), turn_id="t-1"):
        pass

    assert "ABC123" not in rastro.getvalue()


# --- El detector, enchufado ---------------------------------------------------


async def test_la_llamada_abre_su_detector_al_empezar_a_escuchar(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a)
    assert isinstance(motor.listening(since=AHORA), TurnDetector)


async def test_el_detector_recibe_las_tres_esperas_del_motor(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Las esperas del fin del habla son datos del motor: si el motor no las pasa al
    detector, cambiarlas en la configuracion no cambia nada (2026-10-12)."""
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a)
    motor.end_of_speech = timedelta(seconds=1)
    motor.unpunctuated_end_of_speech = timedelta(seconds=2)
    motor.incomplete_end_of_speech = timedelta(seconds=3)

    detector = motor.listening(since=AHORA)

    assert detector.wait_for(Ending.CLOSED) == timedelta(seconds=1)
    assert detector.wait_for(Ending.UNPUNCTUATED) == timedelta(seconds=2)
    assert detector.wait_for(Ending.INCOMPLETE) == timedelta(seconds=3)


async def test_lo_que_se_va_a_sintetizar_va_redactado(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR3.8, y no basta con el tipo.

    El puerto `TextToSpeech` recibe `Redacted` y no `str`, asi que la regla es de
    tipos... hasta que alguien escribe un `type: ignore`. Se comprobo: quitando
    la redaccion y silenciando el comprobador, **ninguna prueba se caia**. Esta
    es la que se cae, y mira el texto que de verdad saldria por el altavoz.
    """
    a, _ = dos_aseguradoras
    placa = "ABC123"
    motor, _ = await _motor(a, guion=(_final_simple(f"I have your plate as {placa}."),))
    await motor.opening_finished(at=AHORA)

    dichas = [u async for u in motor.speak_turn(_habla(motor, "hello"), turn_id="t-1")]

    assert dichas
    assert placa not in str(dichas[0].text)
    assert "[PLATE" in str(dichas[0].text), "se redacto de mas o de menos"


async def test_tambien_va_redactado_lo_que_dice_la_propia_llamada(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La apertura, los silencios y el 'no le entendi' salen del catalogo, pero
    pasan por el mismo camino: un punto de salida que solo cubriera lo que viene
    del grafo seria un punto de salida con un agujero del tamano de la mitad de
    lo que la agente dice."""
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a)
    for dicha in (motor.opening(), motor.on_silence()):
        assert dicha is not None
        assert isinstance(dicha.text, str)
        assert str(dicha.text)


# --- La interrupcion (BR4.1, BR4.3, BR4.5) -----------------------------------


async def test_la_parada_por_interrupcion_deja_su_marca(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """AC1.24.5: la traza de cada interrupcion tiene su marca de parada. Sin
    ella, NFR2 se mediria con un cronometro a mano."""
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a)
    rastro = io.StringIO()
    observability.set_stream(rastro)

    motor.on_barge_in(
        final("no exit fourteen"),
        detected_at=AHORA,
        stopped_at=AHORA + timedelta(milliseconds=180),
        turn_id="t-1",
    )

    lineas = [json.loads(linea) for linea in rastro.getvalue().splitlines() if linea.strip()]
    eventos = [e for e in lineas if e["event"] == latency.BARGE_IN_STOP]
    assert len(eventos) == 1
    assert eventos[0]["elapsed_ms"] == 180


async def test_una_interrupcion_con_correccion_no_hace_repetirla(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Responder 'si, digame' a quien ya dijo lo que queria corregir es hacerle
    repetirlo."""
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a)
    dicha = motor.on_barge_in(
        final("no exit fourteen"), detected_at=AHORA, stopped_at=AHORA, turn_id="t-1"
    )
    assert dicha is None


async def test_una_interrupcion_sin_correccion_cede_el_turno(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a)
    dicha = motor.on_barge_in(VACIO, detected_at=AHORA, stopped_at=AHORA, turn_id="t-1")
    assert dicha is not None
    assert dicha.copy_key == barge_in.ACKNOWLEDGE


async def test_la_apertura_cortada_se_repite_entera(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR4.5: media divulgacion no es divulgacion, y se sabe por la hora de fin."""
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a)
    primera = motor.opening()
    assert motor.needs_opening_again

    motor.on_barge_in(final("hold on"), detected_at=AHORA, stopped_at=AHORA, turn_id="t-1")

    assert motor.needs_opening_again, "una apertura cortada no puede darse por dicha"
    assert motor.opening().text == primera.text


async def test_una_apertura_completa_no_se_repite(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a)
    await motor.opening_finished(at=AHORA + timedelta(seconds=12))
    assert not motor.needs_opening_again


async def test_el_ruido_no_cuenta_como_interrupcion(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """AC1.24.3, por el camino que usa la llamada."""
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a)
    assert not motor.interrupted_by(final("uh", confianza=0.3))
    assert motor.interrupted_by(final("no wait"))


# --- La lectura de confirmacion, cableada (BR3.5) -----------------------------


async def test_una_placa_con_letra_confundible_no_llega_al_grafo_sin_confirmar(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """AC1.23.2. Anotar sin confirmar seria guardar una placa que nadie dijo."""
    a, _ = dos_aseguradoras
    motor, manejador = await _motor(a, guion=(_final_simple("Got it."),))
    await motor.opening_finished(at=AHORA)

    dichas = [u async for u in motor.speak_turn(_habla(motor, "ABC123"), turn_id="t-1")]

    assert manejador.recibidos == [], "la placa llego al grafo sin confirmarse"
    assert [u.copy_key for u in dichas] == [readback.CONFIRM]
    assert "alpha" in str(dichas[0].text)


async def test_confirmada_la_placa_el_turno_original_llega_al_grafo(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    motor, manejador = await _motor(a, guion=(_final_simple("Got it."),))
    await motor.opening_finished(at=AHORA)

    async for _ in motor.speak_turn(_habla(motor, "ABC123"), turn_id="t-1"):
        pass
    async for _ in motor.speak_turn(_habla(motor, "yes", segundos=2), turn_id="t-2"):
        pass

    assert len(manejador.recibidos) == 1
    assert "ABC123" in manejador.recibidos[0].text


async def test_sin_confirmar_no_se_anota_nada_y_se_vuelve_a_pedir(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    motor, manejador = await _motor(a, guion=(_final_simple("Got it."),))
    await motor.opening_finished(at=AHORA)

    async for _ in motor.speak_turn(_habla(motor, "ABC123"), turn_id="t-1"):
        pass
    dichas = [u async for u in motor.speak_turn(_habla(motor, "no", segundos=2), turn_id="t-2")]

    assert manejador.recibidos == []
    assert [u.copy_key for u in dichas] == [retry.NOT_UNDERSTOOD]


async def test_una_placa_dictada_letra_a_letra_tambien_se_lee(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Es la forma en que de verdad se dicta una placa por telefono, y la que el
    decodificador de U11 existe para entender."""
    a, _ = dos_aseguradoras
    motor, manejador = await _motor(a, guion=(_final_simple("Got it."),))
    await motor.opening_finished(at=AHORA)

    dictado = "ay as in alpha, bee as in bravo, see as in charlie, one, two, three"
    dichas = [u async for u in motor.speak_turn(_habla(motor, dictado), turn_id="t-1")]

    assert manejador.recibidos == []
    assert [u.copy_key for u in dichas] == [readback.CONFIRM]


async def test_un_turno_sin_codigo_no_pide_confirmacion(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Leer de vuelta todo convierte la confirmacion en ruido y la gente deja de
    escucharla."""
    a, _ = dos_aseguradoras
    motor, manejador = await _motor(a, guion=(_final_simple("Got it."),))
    await motor.opening_finished(at=AHORA)

    async for _ in motor.speak_turn(_habla(motor, "highway exit twelve"), turn_id="t-1"):
        pass

    assert len(manejador.recibidos) == 1


# --- El cierre, cableado (BR3.7) ----------------------------------------------


async def test_un_caso_completo_cierra_con_su_numero_y_termina_la_llamada(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """BR3.7. El resumen lo trajo el grafo; esto es la cola: que sigue, el
    numero digito a digito y la despedida."""
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a, guion=(_final_simple("Got it."),))
    await motor.opening_finished(at=AHORA)
    assert motor.call.case_id is not None
    await _completar_caso(a, motor.call.case_id, cifrador)

    dichas = [u async for u in motor.speak_turn(_habla(motor, "highway"), turn_id="t-1")]

    assert len(dichas) == 2, "falta el cierre despues de la respuesta del grafo"
    cierre = dichas[-1]
    assert cierre.end_reason is EndReason.COMPLETED

    vista = await casos.get_case(a, motor.call.case_id)
    assert vista is not None
    dichos = case_number.spell(str(vista.case_number), language="en")
    assert dichos in str(cierre.text), "el numero no se dijo digito a digito"
    assert motor.config.display_name in str(cierre.text)
    # Cada cifra del contador, una a una (decision D2; contador desde el 2026-10-30).
    cifras = sum(c.isdigit() for c in str(vista.case_number))
    assert len(dichos.replace(",", "").split()) == cifras


async def test_si_la_agente_acaba_de_preguntar_no_cuelga_hasta_la_respuesta(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """C6, visto el 2026-10-07: con el caso completo, la llamada colgaba justo despues
    de "¿quiere agregar algo, o lo dejamos para el ajustador?". El cierre espera."""
    a, _ = dos_aseguradoras
    pregunta = _final_simple("Do you want to add anything, or leave it to the adjuster?")
    motor, manejador = await _motor(a, guion=(pregunta,))
    await motor.opening_finished(at=AHORA)
    assert motor.call.case_id is not None
    await _completar_caso(a, motor.call.case_id, cifrador)

    primero = [u async for u in motor.speak_turn(_habla(motor, "highway"), turn_id="t-1")]
    manejador.guion = (_final_simple("All right."),)
    segundo = [
        u async for u in motor.speak_turn(_habla(motor, "no, leave it", segundos=2), turn_id="t-2")
    ]

    assert [u.end_reason for u in primero] == [None]
    assert segundo[-1].end_reason is EndReason.COMPLETED


async def test_un_caso_incompleto_no_cierra(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a, guion=(_final_simple("Got it."),))
    await motor.opening_finished(at=AHORA)

    dichas = [u async for u in motor.speak_turn(_habla(motor, "highway"), turn_id="t-1")]

    assert [u.end_reason for u in dichas] == [None]


async def test_el_cierre_se_dice_una_sola_vez(
    dos_aseguradoras: tuple[str, str], cifrador: crypto.Cipher
) -> None:
    """Un caso completo sigue completo en el turno siguiente; despedirse dos
    veces es peor que no despedirse."""
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a, guion=(_final_simple("Got it."),))
    await motor.opening_finished(at=AHORA)
    assert motor.call.case_id is not None
    await _completar_caso(a, motor.call.case_id, cifrador)

    async for _ in motor.speak_turn(_habla(motor, "highway"), turn_id="t-1"):
        pass
    dichas = [u async for u in motor.speak_turn(_habla(motor, "thanks", segundos=2), turn_id="t-2")]

    assert [u.end_reason for u in dichas] == [None]


# --- La transcripción de la llamada (PENDIENTES 1.18) -------------------------


async def _drenar_el_fondo() -> None:
    """Espera lo que la anotación lanzó sin esperar.

    La escritura va **fuera del turno** a propósito: este es el camino con el
    presupuesto de latencia más estricto del proyecto. Una prueba que mirara la
    transcripción sin esperar vería una tabla vacía la mitad de las veces, que es la
    clase de prueba que falla sola los martes.
    """
    pendientes = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if pendientes:
        await asyncio.wait(pendientes, timeout=5)


async def test_una_llamada_deja_los_dos_lados_en_la_transcripcion(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """**La voz no escribía ninguna línea**, y eso dejaba el caso sin poder cerrarse.

    `case_transcript_turn` solo la llena `append_turn`, y por el camino de la voz
    nadie la llamaba. Lo que eso significaba: la revisión de cumplimiento no se
    podía acotar --no hay turno hasta donde llegar--, la evidencia de cierre
    prometía una transcripción que no existía, y la bandeja mostraba el caso de una
    llamada sin una sola palabra de lo que se dijo.

    Se comprueba **quién habla en cada línea** y no cuántas hay: dos líneas del
    mismo hablante pasarían un conteo.
    """
    tenant_id, _ = dos_aseguradoras
    motor, _ = await _motor(tenant_id, guion=(_final_simple("Noted. Tell me what happened."),))
    motor.disclosed_at = AHORA
    assert motor.call.case_id is not None

    async for _ in motor.speak_turn(_habla(motor, "someone hit my car"), turn_id="t-1"):
        pass
    await _drenar_el_fondo()

    turnos = await casos.transcript_of(tenant_id, motor.call.case_id)
    assert [t.speaker for t in turnos] == [Speaker.INSURED, Speaker.AGENT]
    # Y con el canal de la voz, que es lo que distingue una llamada de un chat en la
    # bandeja y en la evidencia de cierre.
    assert {t.channel for t in turnos} == {CaseChannel.VOICE}
    assert "Noted" in turnos[1].text_redacted


async def test_lo_que_no_se_entendio_tambien_queda_escrito(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Un turno que el reconocedor oyó mal no llega al grafo, pero **se dijo**.

    Es justo lo que el ajustador necesita leer para saber por qué se le repreguntó a
    alguien. **Esta prueba movió el código**: la anotación estaba detrás de la
    comprobación de confianza y perdía exactamente los turnos que más hay que
    auditar.
    """
    tenant_id, _ = dos_aseguradoras
    motor, _ = await _motor(tenant_id)
    motor.disclosed_at = AHORA
    assert motor.call.case_id is not None
    # Se oyó algo, pero con una confianza por debajo del piso: no es silencio.
    llegada = AHORA + timedelta(seconds=1)
    detector = motor.listening(since=AHORA)
    detector.observe(final("mumbled words", confianza=0.1), at=llegada)

    dichas = [u async for u in motor.speak_turn(detector.close(), turn_id="t-1")]
    await _drenar_el_fondo()

    assert dichas, "no se dijo nada ante un turno que no se entendió"
    turnos = await casos.transcript_of(tenant_id, motor.call.case_id)
    assert [t.speaker for t in turnos] == [Speaker.INSURED, Speaker.AGENT]
    assert "mumbled" in turnos[0].text_redacted


async def test_un_silencio_no_deja_turno_de_la_persona(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """El control contrario, y marca el límite.

    Quien no dijo nada audible no tuvo un turno. Anotar la línea vacía dejaría la
    transcripción contando silencios como si fueran frases, y la revisión de
    cumplimiento acotándose a un turno en el que nadie habló.
    """
    tenant_id, _ = dos_aseguradoras
    motor, _ = await _motor(tenant_id)
    motor.disclosed_at = AHORA
    assert motor.call.case_id is not None

    async for _ in motor.speak_turn(_habla(motor, ""), turn_id="t-1"):
        pass
    await _drenar_el_fondo()

    turnos = await casos.transcript_of(tenant_id, motor.call.case_id)
    assert [t.speaker for t in turnos] == [Speaker.AGENT]


# --- Lo que se dice fuera de un turno, y los cierres (2026-10-11) -------------------


@pytest.fixture
def fondo(monkeypatch: pytest.MonkeyPatch) -> list[asyncio.Task[object]]:
    """Lo que la llamada lanza sin esperar, a la mano para esperarlo en la prueba."""
    from untangle.voice import call as modulo

    lanzadas: list[asyncio.Task[object]] = []

    def lanzar(work: Coroutine[object, object, object]) -> asyncio.Task[object]:
        tarea = asyncio.create_task(work)
        lanzadas.append(tarea)
        return tarea

    monkeypatch.setattr(modulo, "launch_background", lanzar)
    return lanzadas


def _pedir_persona() -> Handoff:
    return Handoff(
        reason_code=HandoffReason.HUMAN_REQUEST,
        copy_key=copy_api.CopyKey("compliance.handoff.adjuster_review"),
        text="I'm passing this to an adjuster with everything we've captured.",
    )


async def test_pedir_un_ajustador_cierra_la_llamada_con_el_numero_de_caso(
    dos_aseguradoras: tuple[str, str], fondo: list[asyncio.Task[object]]
) -> None:
    """Antes la llamada seguia abierta, preguntaba "¿sigues ahi?" y moria por
    silencio sin haber dicho el numero."""
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a, guion=(_pedir_persona(),))
    await motor.opening_finished(at=AHORA)
    assert motor.call.case_id is not None
    vista = await casos.get_case(a, motor.call.case_id)
    assert vista is not None

    dichas = [u async for u in motor.speak_turn(_habla(motor, "I want a person"), turn_id="t-1")]

    assert [u.end_reason for u in dichas] == [None, EndReason.HANDED_OFF]
    digitos = case_number.spell(str(vista.case_number), language="en")
    assert digitos in str(dichas[-1].text)
    assert motor.closed is True


async def test_pedir_un_ajustador_por_telefono_deja_el_caso_en_su_cola(
    dos_aseguradoras: tuple[str, str], fondo: list[asyncio.Task[object]]
) -> None:
    """En el chat lo hacia quien entrega el turno; en la llamada no lo hacia nadie y
    el caso se quedaba en captura, fuera de la cola de cualquier ajustador."""
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a, guion=(_pedir_persona(),))
    await motor.opening_finished(at=AHORA)
    assert motor.call.case_id is not None

    _ = [u async for u in motor.speak_turn(_habla(motor, "I want a person"), turn_id="t-1")]
    await asyncio.gather(*fondo)

    vista = await casos.get_case(a, motor.call.case_id)
    assert vista is not None
    assert vista.state.value == "derived"
    dicho_por_la_agente = [
        t for t in await casos.transcript_of(a, motor.call.case_id) if t.speaker is Speaker.AGENT
    ]
    assert len(dicho_por_la_agente) == 1


async def test_la_frase_de_espera_deja_una_respuesta_pendiente_una_sola_vez(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    espera = Waiting(copy_key=copy_api.CopyKey("orchestration.turn.waiting"), text="One moment.")
    motor, _ = await _motor(a, guion=(espera,))
    await motor.opening_finished(at=AHORA)

    assert motor.take_awaited_answer() is False
    _ = [u async for u in motor.speak_turn(_habla(motor, "is it covered"), turn_id="t-1")]

    assert motor.take_awaited_answer() is True
    assert motor.take_awaited_answer() is False


async def test_la_respuesta_del_fondo_retoma_la_pregunta_que_quedo_en_el_aire(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La persona todavia debe "¿hubo alguien herido?": sin repetirla, lo que sigue
    es un silencio y despues "¿sigues ahi?"."""
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a)
    motor.opening()

    dicha = str(motor.background_answer("In your policy, Part D addresses this.").text)

    assert dicha.startswith("In your policy, Part D addresses this.")
    assert copy_api.t(copy_api.CopyKey("voice.answer.back_to_report"), locale="en") in dicha
    assert dicha.endswith(copy_api.t(opening.FIRST_QUESTION, locale="en"))


async def test_la_pregunta_pendiente_es_la_ultima_que_hizo_la_agente(
    dos_aseguradoras: tuple[str, str],
) -> None:
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a, guion=(_final_simple("Thanks, noted. Where did it happen?"),))
    motor.opening()
    await motor.opening_finished(at=AHORA)

    _ = [u async for u in motor.speak_turn(_habla(motor, "nobody was hurt"), turn_id="t-1")]
    dicha = str(motor.answer_delayed().text)

    assert dicha.endswith("Where did it happen?")
    assert "Thanks, noted." not in dicha


async def test_al_acabarse_el_tiempo_se_dice_el_numero_y_el_caso_va_al_ajustador(
    dos_aseguradoras: tuple[str, str], fondo: list[asyncio.Task[object]]
) -> None:
    """Antes cortaba en seco. La frase dice que un ajustador lo revisa, y un caso
    que se quedara en captura no lo veria ninguno."""
    a, _ = dos_aseguradoras
    motor, _ = await _motor(a)
    await motor.opening_finished(at=AHORA)
    assert motor.call.case_id is not None
    vista = await casos.get_case(a, motor.call.case_id)
    assert vista is not None
    # Un caso en captura, como el de cualquier llamada con un turno.
    await motor_turno_cualquiera(motor)

    cierre = await motor.time_is_up()
    await asyncio.gather(*fondo)

    assert cierre.end_reason is EndReason.MAX_DURATION
    assert case_number.spell(str(vista.case_number), language="en") in str(cierre.text)
    despues = await casos.get_case(a, motor.call.case_id)
    assert despues is not None
    assert despues.state.value == "derived"


async def motor_turno_cualquiera(motor: CallEngine) -> None:
    """Un turno de la persona, para que el caso salga de recien abierto."""
    motor.handle_turn = con_rastro(_TurnoRegistrado((_final_simple("Noted."),)))
    _ = [u async for u in motor.speak_turn(_habla(motor, "hello there"), turn_id="t-0")]


# --- A que llama la persona: lo decide su primer turno (2026-10-11) -----------------


async def test_lo_primero_que_dice_con_sustancia_decide_a_que_llama_y_solo_una_vez(
    dos_aseguradoras: tuple[str, str],
) -> None:
    from untangle.voice.first_turn import CallPurpose

    a, _ = dos_aseguradoras
    motor, _ = await _motor(a)

    solo_saluda = motor.first_turn_purpose(_habla(motor, "hello there"))
    pregunta = motor.first_turn_purpose(_habla(motor, "I have a question about my policy"))
    despues = motor.first_turn_purpose(_habla(motor, "does my policy cover a rental car"))

    assert solo_saluda is None, "un saludo todavia no dice a que llama"
    assert pregunta is CallPurpose.POLICY_QUESTION
    assert despues is None, "ya se sabe: la conversacion sigue por su caso"


async def test_quien_llama_a_cotizar_oye_que_es_por_chat_y_no_abre_un_reporte(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La voz no toma cotizaciones. Antes se le preguntaba si hubo heridos."""
    a, _ = dos_aseguradoras
    motor, manejador = await _motor(a, guion=(_final_simple("Noted."),))
    motor.config = motor.config.model_copy(update={"quote_enabled": True})
    await motor.opening_finished(at=AHORA)
    habla = _habla(motor, "I would like a quote for my car")

    motor.first_turn_purpose(habla)
    dichas = [u async for u in motor.speak_turn(habla, turn_id="t-1")]

    assert [u.copy_key for u in dichas] == [copy_api.CopyKey("voice.quote.by_chat")]
    assert manejador.recibidos == [], "pedir cotizar no llega al grafo como un reporte"
    # Y no decide la llamada: lo siguiente que diga si puede ser un reporte.
    assert motor.first_turn_purpose(_habla(motor, "then I want to report a crash")) is not None


async def test_una_primera_frase_que_no_dice_a_que_viene_pregunta_y_no_sigue_por_el_reporte(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """**El defecto (2026-10-13):** quien abria la llamada con «quería consultar sobre...» o
    «tengo una pregunta» seguia por el reporte de un accidente, porque lo que no era una duda
    de poliza ni una cotizacion caia en el reporte con que nacio la llamada.

    Ahora se le pregunta a que viene, con una frase que no es la de la apertura, y la frase
    no llega al grafo.
    """
    from untangle.voice.first_turn import CallPurpose

    a, _ = dos_aseguradoras
    motor, manejador = await _motor(a, guion=(_final_simple("Noted."),))
    await motor.opening_finished(at=AHORA)
    habla = _habla(motor, "I have a question")

    proposito = motor.first_turn_purpose(habla)
    dichas = [u async for u in motor.speak_turn(habla, turn_id="t-1")]

    assert proposito is CallPurpose.NOT_STATED
    assert [u.copy_key for u in dichas] == [copy_api.CopyKey("voice.first_turn.clarify")]
    assert dichas[0].text != motor.opening().text
    assert manejador.recibidos == [], "una frase que no dice nada no llega al grafo como reporte"
    # Y no decide la llamada: lo siguiente que diga si puede decir a que viene.
    despues = motor.first_turn_purpose(_habla(motor, "then I want to report a crash"))
    assert despues is CallPurpose.CLAIM


async def test_la_segunda_frase_vaga_no_repite_la_pregunta_y_sigue_por_donde_iba(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Preguntarle dos veces lo mismo con las mismas palabras es peor que lo de antes."""
    from untangle.voice.first_turn import CallPurpose

    a, _ = dos_aseguradoras
    motor, manejador = await _motor(a, guion=(_final_simple("Noted."),))
    await motor.opening_finished(at=AHORA)
    primera = _habla(motor, "I have a question")
    motor.first_turn_purpose(primera)
    _ = [u async for u in motor.speak_turn(primera, turn_id="t-1")]

    segunda = _habla(motor, "I need some help")
    proposito = motor.first_turn_purpose(segunda)
    dichas = [u async for u in motor.speak_turn(segunda, turn_id="t-2")]

    assert proposito is CallPurpose.CLAIM
    assert copy_api.CopyKey("voice.first_turn.clarify") not in [u.copy_key for u in dichas]
    assert len(manejador.recibidos) == 1, "la segunda va al grafo, que ve el caso y la charla"


async def test_una_respuesta_que_anuncia_la_revision_tambien_deja_la_espera(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Una consulta que acaba de confirmar su poliza: la captura dice "dejame
    revisar" y el fondo ya esta revisando."""
    a, _ = dos_aseguradoras
    anuncia = FinalText(
        message_id="m", text="Let me check your policy.", language="en", answer_pending=True
    )
    motor, _ = await _motor(a, guion=(anuncia,))
    await motor.opening_finished(at=AHORA)

    _ = [u async for u in motor.speak_turn(_habla(motor, "yes that is me"), turn_id="t-1")]

    assert motor.take_awaited_answer() is True


# --- "¿Lo dejamos guardado o se lo paso a un ajustador?" (2026-10-11) ------------


async def _con_la_oferta_abierta(
    tenant_id: str, *, por: str, guion: tuple[TurnEvent, ...] = ()
) -> tuple[CallEngine, _TurnoRegistrado]:
    """Un motor al que se le acaba de decir la oferta, por el camino que se pida.

    Son dos y las dos dicen la misma frase: el segundo silencio, y la tercera vez que no
    se entiende lo que la persona dijo.
    """
    motor, manejador = await _motor(tenant_id, guion=guion)
    await motor.opening_finished(at=AHORA)
    if por == "silencio":
        assert [motor.on_silence() for _ in range(2)][-1].copy_key == silence.OFFER  # type: ignore[union-attr]
    else:
        claves = []
        for n in range(3):
            claves += [
                u.copy_key
                async for u in motor.speak_turn(_habla(motor, "", segundos=n + 1), turn_id=f"t-{n}")
            ]
        assert claves[-1] == retry.OFFER
    return motor, manejador


@pytest.mark.parametrize("por", ["silencio", "no_entendido"])
@pytest.mark.parametrize("dicho", ["pass it to the adjuster", "yes, pass it", "the adjuster"])
async def test_elegir_el_ajustador_deriva_el_caso_y_se_despide_con_el_numero(
    dos_aseguradoras: tuple[str, str],
    fondo: list[asyncio.Task[object]],
    por: str,
    dicho: str,
) -> None:
    """La oferta se decia y su respuesta no hacia nada: entraba al grafo como un turno
    mas. Ahora deriva por el mismo camino que cuando se pide un ajustador, y la
    despedida lleva el numero de caso."""
    a, _ = dos_aseguradoras
    motor, manejador = await _con_la_oferta_abierta(a, por=por)
    assert motor.call.case_id is not None
    vista = await casos.get_case(a, motor.call.case_id)
    assert vista is not None

    dichas = [u async for u in motor.speak_turn(_habla(motor, dicho, segundos=9), turn_id="t-9")]
    await asyncio.gather(*fondo)

    assert [u.copy_key for u in dichas] == [call.OFFER_HANDED_OFF]
    assert [u.end_reason for u in dichas] == [EndReason.HANDED_OFF]
    texto = str(dichas[0].text)
    assert texto.startswith(copy_api.t(call.OFFER_HANDED_OFF, locale="en"))
    assert case_number.spell(str(vista.case_number), language="en") in texto
    assert manejador.recibidos == [], "la respuesta a la oferta llego al grafo"
    derivado = await casos.get_case(a, motor.call.case_id)
    assert derivado is not None
    assert derivado.state.value == "derived"
    assert derivado.derivation_reason == DerivationReason.PERSON_REQUESTED.value
    assert motor.closed is True


@pytest.mark.parametrize("por", ["silencio", "no_entendido"])
@pytest.mark.parametrize("dicho", ["keep it saved", "save it please", "I'll finish later"])
async def test_dejarlo_guardado_se_despide_con_la_ventana_y_termina_con_su_motivo(
    dos_aseguradoras: tuple[str, str],
    fondo: list[asyncio.Task[object]],
    por: str,
    dicho: str,
) -> None:
    """Dice con verdad que queda guardado y hasta cuando puede retomarlo: la ventana
    de retoma de la aseguradora, no un plazo escrito aqui. Y no deriva nada."""
    a, _ = dos_aseguradoras
    motor, manejador = await _con_la_oferta_abierta(a, por=por)
    assert motor.call.case_id is not None
    ventana = tenancy_config.require(a).call.resume_window_seconds

    dichas = [u async for u in motor.speak_turn(_habla(motor, dicho, segundos=9), turn_id="t-9")]
    await asyncio.gather(*fondo)

    assert [u.end_reason for u in dichas] == [EndReason.SAVED]
    texto = str(dichas[0].text)
    assert f"{ventana // 60} minutes" in texto
    assert texto.endswith(copy_api.t(closing.FAREWELL, locale="en"))
    assert manejador.recibidos == []
    sigue = await casos.get_case(a, motor.call.case_id)
    assert sigue is not None
    assert sigue.state.value != "derived", "dejarlo guardado no es pasarlo a un ajustador"


async def test_contar_otra_cosa_cierra_la_oferta_y_sigue_la_conversacion(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Con contenido, la conversacion sigue normal: el turno llega al grafo, y la oferta
    ya no espera respuesta, asi que un "guardalo" posterior es un turno mas."""
    a, _ = dos_aseguradoras
    motor, manejador = await _con_la_oferta_abierta(
        a, por="silencio", guion=(_final_simple("Got it."),)
    )

    primera = [
        u async for u in motor.speak_turn(_habla(motor, "the bumper is dented"), turn_id="t-8")
    ]
    segunda = [
        u async for u in motor.speak_turn(_habla(motor, "keep it saved", segundos=2), turn_id="t-9")
    ]

    assert [u.end_reason for u in primera + segunda] == [None, None]
    assert [t.text for t in manejador.recibidos] == ["the bumper is dented", "keep it saved"]


async def test_un_si_a_secas_repregunta_una_vez_y_no_llega_al_grafo(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """ "Si" a una pregunta de dos opciones no elige ninguna, y como respuesta del grafo
    quedaria anotado como el "si" a otra pregunta --"¿hubo heridos?"--."""
    a, _ = dos_aseguradoras
    motor, manejador = await _con_la_oferta_abierta(
        a, por="silencio", guion=(_final_simple("Got it."),)
    )

    primera = [u async for u in motor.speak_turn(_habla(motor, "yes"), turn_id="t-8")]
    assert [u.copy_key for u in primera] == [call.OFFER_CHOOSE]
    assert manejador.recibidos == []

    elegida = [
        u async for u in motor.speak_turn(_habla(motor, "pass it", segundos=2), turn_id="t-9")
    ]
    assert [u.end_reason for u in elegida] == [EndReason.HANDED_OFF]


async def test_la_oferta_solo_se_lee_con_la_oferta_abierta(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """ "Keep it" o "the adjuster" son turnos como cualquiera si nadie ofrecio nada."""
    a, _ = dos_aseguradoras
    motor, manejador = await _motor(a, guion=(_final_simple("Got it."),))
    await motor.opening_finished(at=AHORA)

    dichas = [u async for u in motor.speak_turn(_habla(motor, "keep it saved"), turn_id="t-1")]

    assert all(u.end_reason is None for u in dichas)
    assert [t.text for t in manejador.recibidos] == ["keep it saved"]


async def test_lo_que_no_se_oyo_no_cierra_la_oferta(dos_aseguradoras: tuple[str, str]) -> None:
    """Un turno vacio es de la escalera de reintentos: la oferta sigue esperando."""
    a, _ = dos_aseguradoras
    motor, _ = await _con_la_oferta_abierta(a, por="silencio")

    _ = [u async for u in motor.speak_turn(_habla(motor, ""), turn_id="t-8")]
    dichas = [
        u async for u in motor.speak_turn(_habla(motor, "keep it", segundos=2), turn_id="t-9")
    ]

    assert [u.end_reason for u in dichas] == [EndReason.SAVED]
