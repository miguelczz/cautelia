"""El cupo del sitio, el dia de la zona configurada y la forma de negar (BR5.1 a BR5.7).

El reloj y la zona se inyectan en todas estas pruebas. No es una comodidad: la
medianoche y el cambio de ventana son conducta del sistema, y un calculo que
leyera el reloj del proceso solo se podria comprobar esperando a que pase el dia.

Los bordes que se cubren son los que nombran los criterios de aceptacion:
presupuesto a la mitad con la ventana a la mitad, presupuesto agotado, el tope de
quince, y la medianoche de la zona configurada frente a la del servidor.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from untangle.telemetry.spend import quota
from untangle.telemetry.spend.models import (
    WINDOW_DAYS,
    CallReserve,
    Money,
    QuotaReason,
    QuotaScope,
    VoiceMode,
)

COMIENZO = date(2026, 9, 16)
FIN = COMIENZO + timedelta(days=WINDOW_DAYS)

#: Quince llamadas de tres minutos a la meta de costo del modelo de D7 dan la
#: reserva de grabacion; la de **una** llamada es tres minutos a esa meta.
RESERVA_POR_LLAMADA = CallReserve(max_call_seconds=180, reserve=Money.measured(Decimal("0.015")))
SIN_MEDIR = CallReserve(max_call_seconds=180, reserve=Money.not_measured())

#: Dos zonas con desfase opuesto y suficientemente grande para que la medianoche
#: caiga en dias distintos. Es la unica forma de que la prueba distinga "se uso
#: la zona configurada" de "se uso la del servidor" sin depender de donde corre.
BOGOTA = ZoneInfo("America/Bogota")  # UTC-5
KIRITIMATI = ZoneInfo("Pacific/Kiritimati")  # UTC+14


# --- El cupo del sitio --------------------------------------------------------


def test_con_el_presupuesto_a_la_mitad_y_la_ventana_a_la_mitad_se_llega_al_dia_90() -> None:
    """El criterio literal de FR3.9.

    Lo que se comprueba no es el numero sino la propiedad: gastar el cupo entero
    todos los dias que quedan no pasa del presupuesto que queda. Es lo que
    distingue un cupo derivado de uno fijo, que se llevaria el presupuesto en un
    dia bueno y dejaria sin voz los ochenta y nueve siguientes.
    """
    restante = Money.measured(Decimal("2.50"))
    faltan = quota.days_remaining(COMIENZO + timedelta(days=45), FIN)
    assert faltan == 45

    cupo = quota.site_daily_quota(
        restante,
        days_left=faltan,
        call_reserve=RESERVA_POR_LLAMADA,
        site_daily_cap=15,
    )

    assert cupo == 3
    gasto_maximo = cupo * faltan * Decimal("0.015")
    assert restante.amount_usd is not None
    assert gasto_maximo <= restante.amount_usd


def test_con_el_presupuesto_agotado_el_cupo_es_cero() -> None:
    """Es el corte del enlace publico expresado como cupo: la consola rechaza la
    llamada antes de pedir el microfono, que es la forma barata de decir que no.
    """
    assert (
        quota.site_daily_quota(
            Money.measured(Decimal(0)),
            days_left=45,
            call_reserve=RESERVA_POR_LLAMADA,
            site_daily_cap=15,
        )
        == 0
    )


def test_el_cupo_nunca_pasa_de_su_tope_aunque_sobre_presupuesto() -> None:
    """Con presupuesto de sobra y un dia por delante, la division daria cientos.
    El tope existe para que un solo dia no pueda consumir la ventana entera."""
    assert (
        quota.site_daily_quota(
            Money.measured(Decimal("5.00")),
            days_left=1,
            call_reserve=RESERVA_POR_LLAMADA,
            site_daily_cap=15,
        )
        == 15
    )


def test_sin_precio_medido_el_carril_publico_se_cierra() -> None:
    """No se puede dividir por lo que no se sabe, y suponerlo barato vaciaria el
    presupuesto el primer dia.

    Entre las dos cosas que pueden perderse, la demostracion se vuelve a encender
    manana y el video de la semana doce no: por eso el cupo publico cae a cero y
    la reserva de grabacion se queda intacta.
    """
    assert (
        quota.site_daily_quota(
            Money.measured(Decimal("5.00")),
            days_left=45,
            call_reserve=SIN_MEDIR,
            site_daily_cap=15,
        )
        == 0
    )


def test_con_la_ventana_terminada_no_quedan_dias_entre_los_que_repartir() -> None:
    """El fin de la ventana es exclusivo: el 2026-12-15 ya no se reparte.
    Contarlo daria noventa y un dias de reparto para una ventana de noventa."""
    assert quota.days_remaining(FIN - timedelta(days=1), FIN) == 1
    assert quota.days_remaining(FIN, FIN) == 0
    assert quota.days_remaining(FIN + timedelta(days=10), FIN) == 0

    assert (
        quota.site_daily_quota(
            Money.measured(Decimal("5.00")),
            days_left=0,
            call_reserve=RESERVA_POR_LLAMADA,
            site_daily_cap=15,
        )
        == 0
    )


# --- La medianoche de la zona configurada -------------------------------------


def test_el_dia_se_cierra_en_la_zona_configurada_y_no_en_la_del_servidor() -> None:
    """BR5.2. El instante elegido cae en tres dias distintos segun la zona:
    todavia el 20 en Bogota, ya el 21 en UTC y en Kiritimati.

    Un cambio de servidor moveria la medianoche y regalaria o quitaria una
    llamada a quien estuviera justo en el borde, sin que ningun cambio de codigo
    lo explicara.
    """
    instante = datetime(2026, 9, 21, 2, 0, tzinfo=UTC)

    assert quota.day_period_start(instante, BOGOTA).date() == date(2026, 9, 20)
    assert quota.day_period_start(instante, UTC).date() == date(2026, 9, 21)
    assert quota.day_period_start(instante, KIRITIMATI).date() == date(2026, 9, 21)

    #: Y el comienzo es la medianoche **de esa zona**, no las 00:00 UTC vistas
    #: desde ella.
    en_bogota = quota.day_period_start(instante, BOGOTA)
    assert (en_bogota.hour, en_bogota.minute) == (0, 0)
    assert en_bogota.astimezone(UTC) == datetime(2026, 9, 20, 5, 0, tzinfo=UTC)


def test_el_reintento_apunta_a_la_medianoche_de_esa_misma_zona() -> None:
    """Redondeado hacia arriba: decir un segundo de menos invita a reintentar
    justo antes de que el periodo cambie, y a recibir el mismo rechazo."""
    instante = datetime(2026, 9, 21, 2, 0, tzinfo=UTC)

    #: En Bogota son las 21:00 del dia 20: faltan tres horas.
    assert quota.seconds_until_next_day(instante, BOGOTA) == 3 * 3600
    #: En UTC acaban de dar las 02:00: faltan veintidos.
    assert quota.seconds_until_next_day(instante, UTC) == 22 * 3600


def test_un_instante_sin_zona_no_produce_periodo() -> None:
    """Sin zona no hay medianoche que calcular, solo la del servidor disfrazada."""
    with pytest.raises(ValueError, match="zona horaria"):
        quota.day_period_start(datetime(2026, 9, 21, 2, 0), BOGOTA)


# --- La decision --------------------------------------------------------------


def test_cada_alcance_niega_con_su_propio_motivo() -> None:
    """BR5.3 y C-08. Tres de los cuatro motivos son los que la disponibilidad de
    la voz devuelve; el de sesion es del chat. Un rechazo sin motivo llega a la
    pantalla como un error generico, que es lo que FR4.6 prohibe."""
    ahora = datetime(2026, 9, 21, 2, 0, tzinfo=UTC)

    permitida = quota.decide(QuotaScope.CHAT_MESSAGES_DAY, count=4, limit=10)
    assert permitida.allowed
    assert permitida.reason_code is None

    por_sesion = quota.decide(QuotaScope.CHAT_MESSAGES_SESSION, count=10, limit=10)
    assert por_sesion.reason_code is QuotaReason.RATE_LIMITED_SESSION
    #: El limite de sesion no se abre esperando: se abre empezando otra sesion,
    #: asi que no hay un "cuando" que ofrecer.
    assert por_sesion.retry_after_seconds is None

    del_visitante = quota.decide(
        QuotaScope.VOICE_CALLS_VISITOR_DAY,
        count=1,
        limit=1,
        now=ahora,
        zone=BOGOTA,
    )
    assert del_visitante.reason_code is QuotaReason.RATE_LIMITED_DAILY
    assert del_visitante.retry_after_seconds == 3 * 3600

    del_sitio = quota.decide(QuotaScope.VOICE_CALLS_SITE_DAY, count=15, limit=15)
    assert del_sitio.reason_code is QuotaReason.RATE_LIMITED_SITE


def test_el_techo_niega_sin_ofrecer_un_cuando() -> None:
    """BR4.4. El acumulado de la ventana solo sube, asi que no hay cuando:
    decirle a quien llama que vuelva en una hora seria mentirle."""
    negada = quota.budget_exhausted()

    assert not negada.allowed
    assert negada.reason_code is QuotaReason.BUDGET_EXHAUSTED
    assert negada.retry_after_seconds is None


# --- El modo de voz -----------------------------------------------------------


def test_el_modo_de_voz_se_decide_antes_de_abrir_y_con_la_llamada_entera() -> None:
    """BR5.7. Lo que se comprueba es que cabe una llamada **completa**, no un
    turno: cambiar de voz a mitad de llamada suena a fallo, aunque sea un ahorro.
    Y sin precio medido se responde respaldo, porque afirmar que cabe lo que no
    se sabe cuanto cuesta es la forma de pasarse del techo sin decidirlo."""
    assert (
        quota.voice_mode(Money.measured(Decimal("0.015")), RESERVA_POR_LLAMADA) is VoiceMode.PRIMARY
    )
    assert (
        quota.voice_mode(Money.measured(Decimal("0.0149")), RESERVA_POR_LLAMADA)
        is VoiceMode.FALLBACK
    )
    assert quota.voice_mode(Money.measured(Decimal("5.00")), SIN_MEDIR) is VoiceMode.FALLBACK
    # Y con el restante sin medir tampoco: no se afirma que cabe una llamada en
    # un presupuesto que no se pudo calcular (NFR-U5-3).
    assert quota.voice_mode(Money.not_measured(), RESERVA_POR_LLAMADA) is VoiceMode.FALLBACK


# --- U17, tanda 2: el cupo con la voz barata y el modo con la cara -------------

#: La reserva de la voz de respaldo, mas barata que la principal. Son los dos
#: numeros que el proyecto tiene de verdad, redondeados: 0,098 y 0,072.
RESERVA_DE_RESPALDO = CallReserve(
    max_call_seconds=180, reserve=Money.measured(Decimal("0.072")), mode=VoiceMode.FALLBACK
)
RESERVA_PRINCIPAL = CallReserve(
    max_call_seconds=180, reserve=Money.measured(Decimal("0.098")), mode=VoiceMode.PRIMARY
)


def test_mientras_alcance_para_una_llamada_el_cupo_es_al_menos_una() -> None:
    """El piso que abrio el enlace publico de voz (U17, tanda 2).

    Sin el, el cupo es el reparto del restante entre **todos** los dias que faltan,
    y con 5 USD y noventa dias eso da cero desde el primer dia: el enlace no habria
    abierto ni una llamada en toda la ventana, teniendo presupuesto para casi
    cincuenta.
    """
    restante = Money.measured(Decimal("3.53"))

    cupo = quota.site_daily_quota(
        restante, days_left=74, call_reserve=RESERVA_DE_RESPALDO, site_daily_cap=15
    )

    assert cupo == 1
    # Y el reparto, sin el piso, habria dado cero: 74 dias por 0,072 son 5,33.
    assert restante.amount_usd is not None
    assert restante.amount_usd < 74 * Decimal("0.072")


def test_sin_presupuesto_para_una_llamada_el_cupo_es_cero() -> None:
    """El piso es de **una**, no de cortesia: lo que no se puede pagar no se ofrece."""
    assert (
        quota.site_daily_quota(
            Money.measured(Decimal("0.05")),
            days_left=74,
            call_reserve=RESERVA_DE_RESPALDO,
            site_daily_cap=15,
        )
        == 0
    )


def test_la_voz_de_respaldo_es_alcanzable_con_el_cupo_de_la_barata() -> None:
    """La otra mitad del arreglo, y la razon por la que el modo de respaldo existe.

    El cupo se calcula con la reserva de la voz **de respaldo** y el modo con la de
    la **principal**, asi que hay un tramo --entre las dos reservas-- en el que la
    llamada cabe y la voz principal no: ahi suena la de respaldo, que es
    exactamente para lo que esta.

    Antes de la tanda 2 las dos preguntas usaban la misma reserva, y entonces el
    tramo no existia: siempre que una llamada cabia, cabia con la voz principal, y
    la rama de respaldo de `voice_mode` era inalcanzable por este camino. **Esta
    prueba se cae el dia que alguien vuelva a usar la misma reserva en las dos.**
    """
    entre_las_dos = Money.measured(Decimal("0.080"))

    cupo = quota.site_daily_quota(
        entre_las_dos, days_left=74, call_reserve=RESERVA_DE_RESPALDO, site_daily_cap=15
    )

    assert cupo == 1, "la llamada cabe con la voz barata"
    assert not quota.covers_primary_voice(entre_las_dos, RESERVA_PRINCIPAL)
    assert quota.voice_mode(entre_las_dos, RESERVA_PRINCIPAL) is VoiceMode.FALLBACK
