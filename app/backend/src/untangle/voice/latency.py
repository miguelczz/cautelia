"""Los eventos de rastro de la llamada: los de latencia y los de lo que la agente decidio hacer.

Los de latencia son FR10.2 y BR8.1 a BR8.4. `language_switched` y `listening_reopened`
(2026-10-13) dicen que la llamada cambio de idioma y por que, y que el reconocedor se
reabrio en el nuevo; `hold_requested` (2026-10-11), que la agente espero porque se lo pidieron.

Son los unicos eventos que esta unidad anade a la traza, y **llevan tiempos e
identificadores, nunca contenido**: es ADR-013, y RT-14 --la fuga por trazas-- es
lo que esa regla cierra.

Existen porque sin ellos NFR1, NFR2 y NFR3 no se pueden medir, y una meta que no
se mide no existe. El reporte del hito los nombra por su nombre.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from untangle import observability
from untangle.tenancy.models import TenantId

SPEECH_END = "voice.speech_end"
FIRST_AUDIO = "voice.first_audio"
BARGE_IN_STOP = "voice.barge_in_stop"
RESUME_AFTER_DROP = "voice.resume_after_drop"
LANGUAGE_SWITCHED = "voice.language_switched"
LANGUAGE_DETECTION_FAILED = "voice.language_detection_failed"
LISTENING_REOPENED = "voice.listening_reopened"
HOLD_REQUESTED = "voice.hold_requested"
NOT_UNDERSTOOD = "voice.not_understood"
FILLER_SAID = "voice.filler_said"
EARLY_UNDERSTANDING = "voice.early_understanding"
SPEECH_SIGNAL_DISCARDED = "voice.speech_signal_discarded"


def _ms(desde: datetime, hasta: datetime) -> int:
    return int((hasta - desde).total_seconds() * 1000)


def speech_end(
    *,
    tenant_id: TenantId,
    call_id: str,
    turn_id: str,
    at: datetime,
    last_audible_word_at: datetime | None,
) -> None:
    """El extremo izquierdo de NFR1 (BR8.1).

    Lleva las **dos** variantes que AC1.23.5 pide publicar: la marca del ultimo
    transcrito final, que es la que cuenta, y la de la ultima palabra audible.
    Las dos, y no la mas favorable.
    """
    observability.emit(
        SPEECH_END,
        tenant_id=tenant_id,
        call_id=call_id,
        turn_id=turn_id,
        at=at.isoformat(),
        last_audible_word_at=last_audible_word_at.isoformat() if last_audible_word_at else None,
    )


@dataclass(frozen=True)
class FirstAudio:
    """Las dos medidas del primer audio de un turno, las que quedaron en la traza."""

    #: Desde el ultimo transcrito final: la definicion de la meta de latencia (NFR1).
    elapsed_ms: int
    #: Desde la ultima palabra que la persona dijo, que es lo que vive. Nula si no se
    #: pudo calcular --el proveedor no mando tiempos, o la hora salio imposible--.
    from_last_word_ms: int | None


def first_audio(  # noqa: PLR0913 -- los datos de la marca, todos por nombre
    *,
    tenant_id: TenantId,
    call_id: str,
    turn_id: str,
    speech_end_at: datetime,
    at: datetime,
    last_audible_word_at: datetime | None = None,
    filler_said: bool = False,
) -> FirstAudio:
    """El extremo derecho de NFR1: el primer byte sintetizado del turno (BR8.1).

    **Devuelve lo que acaba de escribir en la traza**, y por eso no devuelve nada antes
    de la tanda 2 de U17: la consola tiene que mostrar esa cifra (BR3.3) y medirla por
    su cuenta daria dos numeros con el mismo nombre que un dia no coinciden. Se calcula
    aqui, se escribe aqui, y quien la muestra la recibe.

    `elapsed_ms` es la definicion de la meta y no cambia. `elapsed_from_last_word_ms` es
    la otra medida, desde la ultima palabra audible (2026-10-12): la que la persona vive,
    porque el reconocedor y la tolerancia de fin de habla pasan antes de que llegue el
    final. Las dos, y no la mas favorable.

    **`after_filler` dice que antes de este audio sono una muletilla, y la muletilla no es
    el primer audio**: la marca sigue siendo la del primer trozo de la respuesta de verdad.
    Si no fuera asi, la meta mejoraria sin que la respuesta llegara antes.
    """
    elapsed_ms = _ms(speech_end_at, at)
    from_last_word_ms = None if last_audible_word_at is None else _ms(last_audible_word_at, at)
    observability.emit(
        FIRST_AUDIO,
        tenant_id=tenant_id,
        call_id=call_id,
        turn_id=turn_id,
        at=at.isoformat(),
        elapsed_ms=elapsed_ms,
        elapsed_from_last_word_ms=from_last_word_ms,
        after_filler=filler_said,
    )
    return FirstAudio(elapsed_ms=elapsed_ms, from_last_word_ms=from_last_word_ms)


def filler_said(
    *, tenant_id: TenantId, call_id: str, turn_id: str, speech_end_at: datetime, at: datetime
) -> None:
    """Se dijo una muletilla mientras el motor preparaba la respuesta (2026-10-12).

    Lleva el turno y los milisegundos desde el fin del habla, **nunca el texto**: es
    ADR-013. Existe para poder decir cuantos turnos necesitaron la muletilla, y para que la
    meta de latencia no se lea sin saber que habia una.
    """
    observability.emit(
        FILLER_SAID,
        tenant_id=tenant_id,
        call_id=call_id,
        turn_id=turn_id,
        at=at.isoformat(),
        elapsed_ms=_ms(speech_end_at, at),
    )


def early_understanding(  # noqa: PLR0913 -- los datos del evento, todos por nombre
    *,
    tenant_id: TenantId,
    call_id: str,
    turn_id: str | None,
    outcome: str,
    words: int | None,
    ran_ms: int | None,
    finished: bool,
    cause: str | None = None,
    understood: bool | None = None,
    waited_ms: int | None = None,
    saved_ms: int | None = None,
    error_type: str | None = None,
    where: str | None = None,
) -> None:
    """Que paso con la lectura que se adelanto mientras corria la tolerancia de fin de habla.

    `outcome` es `used` (el turno la recogio: `waited_ms` es lo que aun espero, `saved_ms` lo que
    se ahorro frente a leer despues de cerrar el turno, y `understood` si el modelo devolvio
    algo), `discarded` (`cause`: `kept_talking`, `state_changed`, `not_needed` o `call_ended`;
    `finished` dice si el modelo ya habia contestado, es decir, si el llamado se pago de todos
    modos) o `failed` (`error_type` y `where`, nunca el mensaje).

    `turn_id` es nulo cuando se descarta antes de que el turno cierre, porque todavia no
    existe. **Lleva recuentos y milisegundos, nunca el texto**: es ADR-013.
    """
    observability.emit(
        EARLY_UNDERSTANDING,
        tenant_id=tenant_id,
        call_id=call_id,
        turn_id=turn_id,
        outcome=outcome,
        cause=cause,
        words=words,
        ran_ms=ran_ms,
        finished=finished,
        understood=understood,
        waited_ms=waited_ms,
        saved_ms=saved_ms,
        error_type=error_type,
        where=where,
    )


def speech_signal_discarded(
    *, tenant_id: TenantId, call_id: str, turn_id: str, signals: int, held_ms: int
) -> None:
    """Llegaron senales de voz con el turno abierto y ninguna trajo palabras (2026-10-13).

    El reconocedor avisa de voz por energia, y una tos, el teclado o el eco tambien la
    disparan: la senal sola no retoma el turno, solo lo mantiene abierto un rato corto
    (`turn_detection.SIGNAL_GRACE`). Sin este evento, "la agente tarda en contestar" no se
    distingue de un ruido que esta estirando el turno. Sale una vez por turno, al cerrarlo:
    `signals` es cuantas fueron y `held_ms` cuanto alargaron el plazo, como maximo.

    Lleva recuentos y milisegundos, **nunca el texto**: es ADR-013.
    """
    observability.emit(
        SPEECH_SIGNAL_DISCARDED,
        tenant_id=tenant_id,
        call_id=call_id,
        turn_id=turn_id,
        signals=signals,
        held_ms=held_ms,
    )


def barge_in_stop(
    *, tenant_id: TenantId, call_id: str, turn_id: str, detected_at: datetime, at: datetime
) -> None:
    """La marca de parada de una interrupcion (BR8.2, NFR2)."""
    observability.emit(
        BARGE_IN_STOP,
        tenant_id=tenant_id,
        call_id=call_id,
        turn_id=turn_id,
        at=at.isoformat(),
        elapsed_ms=_ms(detected_at, at),
    )


def resume_after_drop(  # noqa: PLR0913 -- los datos de la marca, todos por nombre
    *,
    tenant_id: TenantId,
    call_id: str,
    case_id: str,
    dropped_call_id: str,
    previous_end_reason: str | None,
    at: datetime,
) -> None:
    """La recuperacion tras un corte, **enlazada al caso original** (BR8.3, NFR3).

    El enlace no es decorativo: sin el, la marca no distingue una retoma de una
    llamada nueva, y NFR3 se contaria sobre el denominador equivocado. Y lleva como
    termino la llamada anterior: desde el 2026-10-11 tambien se retoma una que la
    persona dejo guardada, y esa no es un corte.
    """
    observability.emit(
        RESUME_AFTER_DROP,
        tenant_id=tenant_id,
        call_id=call_id,
        case_id=case_id,
        dropped_call_id=dropped_call_id,
        previous_end_reason=previous_end_reason,
        at=at.isoformat(),
    )


def language_switched(*, tenant_id: TenantId, call_id: str, frm: str, to: str, reason: str) -> None:
    """La llamada cambio de idioma, y **por que** (U18).

    El motivo separa dos cosas que se miden distinto: los cambios que la persona
    pidio --que deben ser el 100 %-- y los que la deteccion decidio sola, que es
    una tasa de acierto. Un solo contador de "cambios de idioma" mezclaria una
    compuerta con una estimacion.

    Lleva los dos idiomas y el motivo, **nunca el turno**: es ADR-013, y es lo que
    cierra RT-14.
    """
    observability.emit(
        LANGUAGE_SWITCHED,
        tenant_id=tenant_id,
        call_id=call_id,
        **{"from": frm},
        to=to,
        reason=reason,
    )


def language_detection_failed(*, tenant_id: TenantId, call_id: str, error_type: str) -> None:
    """La deteccion automatica levanto, y la llamada siguio en su idioma (U18).

    Existe para que ese fallo **no sea silencioso**. La deteccion es una comodidad
    --US1.32 es Should y la primera en la regla de corte-- y una llamada no se
    cae porque una comodidad falle; pero tragarse la excepcion sin dejar rastro
    convertiria "el detector esta roto" en "la agente nunca cambia de idioma", que
    es lo mismo que se ve cuando la aseguradora lo tiene apagado.

    Lleva el **tipo** del error y nunca su mensaje: un mensaje de excepcion puede
    traer el texto que se estaba mirando, y eso es RT-14.
    """
    observability.emit(
        LANGUAGE_DETECTION_FAILED,
        tenant_id=tenant_id,
        call_id=call_id,
        error_type=error_type,
    )


def listening_reopened(*, tenant_id: TenantId, call_id: str, language: str) -> None:
    """El reconocedor se cerro y se abrio de nuevo en el idioma al que paso la llamada.

    Solo ocurre con un reconocedor de un solo idioma por conexion (`stt.mode:
    monolingual`): el idioma se le dice al abrir, asi que cambiar la voz sin cambiar el
    oido dejaba a la persona hablando con quien no la entendia (V18). Sin este evento,
    "la agente no me oyo despues de cambiar" no se distingue de un reconocedor que no
    volvio a abrirse. No lleva texto.
    """
    observability.emit(LISTENING_REOPENED, tenant_id=tenant_id, call_id=call_id, language=language)


def hold_requested(*, tenant_id: TenantId, call_id: str) -> None:
    """La persona pidio que se esperara y la agente dijo que espera (2026-10-11).

    Sin el evento, "la agente tardo en preguntar si seguia ahi" no se distingue de un
    reloj mal puesto. No lleva texto: es solo que ocurrio.
    """
    observability.emit(HOLD_REQUESTED, tenant_id=tenant_id, call_id=call_id)


def not_understood(
    *,
    tenant_id: TenantId,
    call_id: str,
    words: int,
    low_confidence_words: int,
    min_confidence: float | None,
) -> None:
    """Un turno que se descarto por no entenderse, con **por que** (2026-10-07).

    Sin esto, "la agente no me oye" no se distingue de "la oyo y la descarto":
    las dos se ven como una repregunta. Lleva recuentos y la peor confianza, nunca
    el texto (RT-14).
    """
    observability.emit(
        NOT_UNDERSTOOD,
        tenant_id=tenant_id,
        call_id=call_id,
        words=words,
        low_confidence_words=low_confidence_words,
        min_confidence=min_confidence,
    )


__all__ = [
    "BARGE_IN_STOP",
    "EARLY_UNDERSTANDING",
    "FILLER_SAID",
    "FIRST_AUDIO",
    "HOLD_REQUESTED",
    "LANGUAGE_DETECTION_FAILED",
    "LANGUAGE_SWITCHED",
    "LISTENING_REOPENED",
    "NOT_UNDERSTOOD",
    "RESUME_AFTER_DROP",
    "SPEECH_END",
    "FirstAudio",
    "barge_in_stop",
    "early_understanding",
    "filler_said",
    "first_audio",
    "hold_requested",
    "language_detection_failed",
    "language_switched",
    "listening_reopened",
    "not_understood",
    "resume_after_drop",
    "speech_end",
]
