"""Los cupos de la demostracion: cuanto cabe hoy, y que se responde cuando no.

Aritmetica pura, como la del presupuesto, y por la misma razon: la medianoche y
el cambio de ventana son **conducta**, no ambiente. Un calculo que leyera el
reloj del proceso solo se podria probar esperando a que pase el dia.

Dos decisiones cargan casi todo este archivo:

1. **El cupo del sitio se deriva, no se fija.** Es el menor entre su tope y lo
   que el presupuesto publico restante alcanza a pagar en los dias que quedan.
   Un cupo fijo se llevaria el presupuesto en un dia bueno y dejaria sin voz los
   ochenta y nueve siguientes; uno derivado hace que un dia de trafico alto
   reduzca el cupo de los dias siguientes en vez de adelantar el corte (BR5.6).
2. **Una negacion es un valor, nunca una excepcion.** Un rechazo que llega como
   excepcion se convierte en un error generico en la pantalla, que es justo lo
   que FR4.6 prohibe (BR5.3).

**La zona horaria entra por argumento.** No se lee de ningun sitio aqui: la del
servidor moveria la medianoche al cambiar de maquina y regalaria o quitaria una
llamada (BR5.2), y no hay todavia ningun documento aprobado que fije cual es la
del proyecto ni donde se declara. Recibirla explicita deja esa decision a la
vista de quien construya la superficie, en vez de enterrarla aqui como un valor
por defecto que nadie eligio.
"""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta, tzinfo

from untangle.telemetry.spend.models import (
    DAILY_SCOPES,
    CallReserve,
    Money,
    QuotaDecision,
    QuotaReason,
    QuotaScope,
    VoiceMode,
)

#: Que motivo devuelve cada alcance cuando se pasa de su limite. Se declara como
#: mapa y no como cadena de `if` para que anadir un alcance obligue a decidir aqui
#: que se le responde a quien lo pida, en vez de caer en una rama por defecto que
#: dice lo primero que haya.
_MOTIVO_POR_ALCANCE: dict[QuotaScope, QuotaReason] = {
    QuotaScope.CHAT_MESSAGES_SESSION: QuotaReason.RATE_LIMITED_SESSION,
    QuotaScope.CHAT_MESSAGES_DAY: QuotaReason.RATE_LIMITED_DAILY,
    QuotaScope.VOICE_CALLS_VISITOR_DAY: QuotaReason.RATE_LIMITED_DAILY,
    QuotaScope.VOICE_CALLS_SITE_DAY: QuotaReason.RATE_LIMITED_SITE,
}


# --- El dia, en la zona configurada -------------------------------------------


def day_period_start(now: datetime, zone: tzinfo) -> datetime:
    """La medianoche del dia de `now` **en esa zona**.

    El instante se convierte a la zona antes de recortar la hora. Recortar
    primero y convertir despues daria la medianoche de otro dia siempre que el
    desfase cruce el cambio de fecha, que es exactamente el caso que esta funcion
    existe para que no ocurra.
    """
    if now.tzinfo is None:
        msg = (
            "el instante tiene que llevar zona horaria: sin ella, la medianoche es "
            "la del servidor y un cambio de maquina mueve el corte del dia (BR5.2)"
        )
        raise ValueError(msg)
    local = now.astimezone(zone)
    return datetime.combine(local.date(), time.min, tzinfo=zone)


def seconds_until_next_day(now: datetime, zone: tzinfo) -> int:
    """Cuanto falta para que el contador diario se abra de nuevo.

    Es lo que se le dice a quien pidio y no cabia, para que sepa cuando tiene
    sentido volver. Se redondea hacia arriba: decir un segundo de menos invita a
    reintentar justo antes de que el periodo cambie.
    """
    siguiente = day_period_start(now, zone) + timedelta(days=1)
    return max(0, math.ceil((siguiente - now).total_seconds()))


def days_remaining(today: date, window_end: date) -> int:
    """Dias que le quedan a la ventana, contando hoy.

    El fin es **exclusivo**: la ventana de noventa dias que empieza el 2026-09-16
    termina el 2026-12-15, y ese dia ya no se reparte. Contarlo daria noventa y
    un dias de reparto para una ventana de noventa.
    """
    return max(0, (window_end - today).days)


# --- El cupo del sitio --------------------------------------------------------


def site_daily_quota(
    public_remaining: Money,
    *,
    days_left: int,
    call_reserve: CallReserve,
    site_daily_cap: int,
) -> int:
    """Cuantas llamadas publicas caben hoy (BR5.6).

    El menor entre el tope y el piso de dividir el presupuesto publico restante
    entre los dias que faltan por la reserva de una llamada. Con el presupuesto a
    la mitad y la ventana a la mitad, lo que sale alcanza para llegar al dia
    noventa; con el presupuesto agotado sale cero, que es el corte del enlace
    publico expresado como cupo.

    El restante entra como **par** y no como decimal: asi no hay forma de
    pasarle un cero que en realidad significaba "no se pudo calcular". Cuatro
    bordes, cada uno con su respuesta y su razon:

    - **El restante no esta medido.** Cupo cero, y el estado del presupuesto lo
      dice aparte: `unmeasured`, no `exhausted`. La conducta es la misma --se
      cierra el carril publico-- y lo que cambia es que el panel no afirma que
      se gasto un presupuesto que nadie gasto.
    - **La reserva por llamada no esta medida.** No se puede dividir por lo que
      no se sabe, y suponerlo barato vaciaria el presupuesto el primer dia.
      Cero: se cierra el carril publico y se deja abierto el de grabacion,
      porque entre las dos cosas que pueden perderse, la demostracion se vuelve
      a encender manana y el video de la semana doce no.
    - **La ventana se acabo.** No quedan dias entre los que repartir. Cero.
    - **La reserva vale cero.** Una llamada no cuesta nada, asi que lo unico que
      la limita es el tope.

    **Y un piso de una llamada** desde la tanda 2 de U17: mientras el restante
    alcance para una, el cupo es al menos una. La razon esta abajo, junto al
    calculo.

    La reserva que entra aqui es la de la **voz de respaldo**, que es la barata: lo
    que este cupo responde es cuantas llamadas caben hoy, y mientras quepa una con
    la voz de respaldo el enlace sigue vivo. Con la de la voz principal, el enlace
    se cerraba justo cuando el modo de respaldo existe para mantenerlo abierto.
    """
    if public_remaining.amount_usd is None:
        return 0
    if call_reserve.reserve.amount_usd is None or days_left <= 0:
        return 0

    por_llamada = call_reserve.reserve.amount_usd
    if por_llamada <= 0:
        return site_daily_cap

    cabidas = int(public_remaining.amount_usd // (days_left * por_llamada))
    if cabidas == 0 and public_remaining.amount_usd >= por_llamada:
        # **El piso de una llamada** (U17, tanda 2). Sin el, un presupuesto que no
        # alcanza para una llamada **cada dia de los que faltan** cierra el enlace
        # entero, aunque alcance para decenas de llamadas: con 5 USD, noventa dias
        # y una llamada de tres minutos, el reparto da cero desde el primer dia y
        # el enlace publico de voz no habria abierto ni una sola.
        #
        # Lo que se acepta a cambio: el presupuesto puede agotarse antes de que la
        # ventana termine. Es un cambio real de lo que la regla del reparto decia
        # --"con el presupuesto a la mitad y la ventana a la mitad, alcanza para
        # llegar al dia noventa"-- y se acepta porque **el tope diario del sitio ya
        # acota la rafaga**: una llamada al dia no se lleva el presupuesto en una
        # tarde, y un enlace cerrado los noventa dias no demuestra nada.
        return min(site_daily_cap, 1)
    return max(0, min(site_daily_cap, cabidas))


def covers_primary_voice(public_remaining: Money, primary_call_reserve: CallReserve) -> bool:
    """Si el presupuesto cubre una llamada completa a la voz principal (BR5.7).

    Se decide **antes** de abrir la llamada y no cambia a mitad: cambiar de voz a
    mitad de llamada suena a fallo, aunque sea un ahorro.

    Con cualquiera de los dos sin medir se responde que no. Afirmar que cabe lo
    que no se sabe cuanto cuesta, o que cabe en un presupuesto que no se pudo
    calcular, es la forma de pasarse del techo sin haberlo decidido: cerrado
    para lo que cuesta dinero (NFR-U5-3).
    """
    if public_remaining.amount_usd is None or primary_call_reserve.reserve.amount_usd is None:
        return False
    return public_remaining.amount_usd >= primary_call_reserve.reserve.amount_usd


def voice_mode(public_remaining: Money, primary_call_reserve: CallReserve) -> VoiceMode:
    """Con que voz se abre la llamada, decidido una vez y para toda ella."""
    if covers_primary_voice(public_remaining, primary_call_reserve):
        return VoiceMode.PRIMARY
    return VoiceMode.FALLBACK


# --- La decision --------------------------------------------------------------


def decide(
    scope: QuotaScope,
    *,
    count: int,
    limit: int,
    now: datetime | None = None,
    zone: tzinfo | None = None,
) -> QuotaDecision:
    """Si este sujeto puede hacer una mas, y si no, por que y cuando volver.

    `now` y `zone` solo sirven para responder el "cuando": un alcance diario se
    abre de nuevo en la medianoche de la zona configurada. Sin ellos la decision
    se toma igual y se omite el reintento, porque un "vuelva en un rato" sin
    numero no ayuda a nadie.
    """
    if count < limit:
        return QuotaDecision(allowed=True)

    motivo = _MOTIVO_POR_ALCANCE[scope]
    reintento: int | None = None
    if scope in DAILY_SCOPES and now is not None and zone is not None:
        reintento = seconds_until_next_day(now, zone)
    return QuotaDecision(allowed=False, reason_code=motivo, retry_after_seconds=reintento)


def budget_exhausted() -> QuotaDecision:
    """La negacion que no es una cuota sino el techo (BR4.4).

    Va sin reintento a proposito: el acumulado de la ventana solo sube, asi que
    no hay cuando. Decirle a quien llama que vuelva en una hora seria mentirle.

    **Discrepancia declarada, no heredada.** Esta es tambien la respuesta cuando
    el estado del presupuesto es `unmeasured`, aunque ahi no se haya agotado
    nada. El motivo que sale hacia C-08 tiene **cuatro valores cerrados** y
    ampliarlo es tocar un contrato ya firmado con U13, U16, U17 y U22, asi que
    hacia fuera las dos causas comparten codigo. Dentro **no se colapsan**:
    `BudgetStatus` las distingue, el panel de gasto muestra "no medida" en vez
    de "agotado", y la traza registra cual de las dos fue. El dia que C-08 se
    enmiende, aqui entra su motivo propio y esta nota se va con el.
    """
    return QuotaDecision(allowed=False, reason_code=QuotaReason.BUDGET_EXHAUSTED)
