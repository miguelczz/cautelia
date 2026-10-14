"""El techo, la alerta y los dos carriles (BR4.1 a BR4.3, BR4.9, BR4.10).

Ninguna de estas pruebas gasta un centavo: el acumulado se **fuerza** en la
ventana, nunca se alcanza gastando. Es una regla del proyecto y no una
comodidad: una suite que consumiera el presupuesto real dejaria al proyecto sin
voz para demostrarla, que es precisamente lo que el techo existe para evitar
(BR5.9).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from untangle.telemetry.spend import budget, quota
from untangle.telemetry.spend.models import (
    WINDOW_DAYS,
    BudgetStatus,
    BudgetWindow,
    CallReserve,
    CostStatus,
    Money,
    QuotaReason,
    SpendTotal,
    VoiceMode,
)

AHORA = datetime(2026, 9, 20, 15, 30, tzinfo=UTC)
COMIENZO = date(2026, 9, 16)

#: Quince llamadas de tres minutos a la meta de costo del modelo de D7
#: (0,005 USD por minuto): 45 minutos, 0,225 USD. Es la cifra que declara
#: `providers.yaml` en minutos, convertida aqui a mano para no depender de una
#: tabla de precios que hoy no tiene ese precio.
RESERVA = Decimal("0.225")


def _ventana(**cambios: object) -> BudgetWindow:
    """Una ventana con **la reserva declarada y nula**, salvo que se diga otra.

    Declararla explicita importa desde que la reserva admite "no medida": una
    ventana que no la nombra ya no significa "reserva cero", significa "no se
    pudo calcular", y las pruebas de los tres estados del carril publico
    necesitan una reserva conocida para estar hablando de los estados y no de la
    ausencia de reserva. El caso sin medir tiene sus propias pruebas mas abajo.
    """
    base: dict[str, object] = {
        # Las pruebas de los umbrales estan escritas sobre el tope original de D11
        # (5 USD, alerta en 3); el tope vigente (40 y 24 desde el 2026-10-07) es el
        # valor por omision del modelo, y aqui se fija el de las pruebas a proposito.
        "cap_usd": Decimal("5.00"),
        "alert_usd": Decimal("3.00"),
        "window_start": COMIENZO,
        "window_end": COMIENZO + timedelta(days=WINDOW_DAYS),
        "updated_at": AHORA,
        "recording_reserve_usd": Decimal(0),
        "recording_reserve_status": CostStatus.MEASURED,
    }
    return BudgetWindow.model_validate(base | cambios)


def _con_reserva(reserva: Decimal, **cambios: object) -> BudgetWindow:
    """Una ventana con reserva medida. El par se escribe una vez, aqui."""
    return _ventana(
        recording_reserve_usd=reserva, recording_reserve_status=CostStatus.MEASURED, **cambios
    )


# --- Los tres estados ---------------------------------------------------------


def test_los_tres_estados_salen_del_acumulado_y_no_se_guardan() -> None:
    """Guardar el estado abriria la posibilidad de que el numero y el estado se
    contradigan, y entonces habria dos respuestas a la misma pregunta."""
    assert budget.status(_ventana(billable_spent_usd=Decimal("2.99"))) is BudgetStatus.OK
    assert budget.status(_ventana(billable_spent_usd=Decimal("3.00"))) is BudgetStatus.ALERTED
    assert budget.status(_ventana(billable_spent_usd=Decimal("4.99"))) is BudgetStatus.ALERTED
    assert budget.status(_ventana(billable_spent_usd=Decimal("5.00"))) is BudgetStatus.EXHAUSTED


def test_el_restante_publico_descuenta_la_reserva_y_nunca_se_informa_negativo() -> None:
    """BR4.9. La reserva se resta antes que nada: restarla despues seria no
    reservarla. Y por debajo de cero no queda "menos presupuesto", queda ninguno;
    el estado ya dice que se agoto."""
    sin_gastar = _con_reserva(RESERVA)
    assert budget.public_remaining(sin_gastar) == Money.measured(Decimal("4.775"))

    a_medias = _con_reserva(RESERVA, billable_spent_usd=Decimal("2.00"))
    assert budget.public_remaining(a_medias) == Money.measured(Decimal("2.775"))

    pasado = _con_reserva(RESERVA, billable_spent_usd=Decimal("5.00"))
    assert budget.public_remaining(pasado) == Money.measured(Decimal(0))


def test_el_carril_de_grabacion_sigue_vivo_con_el_publico_agotado() -> None:
    """BR4.10, y es la razon de que los dos carriles se informen por separado.

    `exhausted` con reserva disponible no es una contradiccion: el enlace publico
    esta cerrado y la grabacion del video de la semana doce sigue teniendo con
    que pagarse. Un unico numero de "restante" no podria decir las dos cosas.
    """
    agotado = _con_reserva(
        RESERVA,
        billable_spent_usd=Decimal("4.775"),
        recording_spent_usd=Decimal("0"),
    )

    assert budget.status(agotado) is BudgetStatus.EXHAUSTED
    assert budget.public_remaining(agotado) == Money.measured(Decimal(0))
    assert budget.recording_remaining(agotado) == Money.measured(RESERVA)

    gastando_la_reserva = agotado.evolve(
        billable_spent_usd=Decimal("4.875"),
        recording_spent_usd=Decimal("0.10"),
    )
    assert budget.recording_remaining(gastando_la_reserva) == Money.measured(Decimal("0.125"))
    #: Lo que el carril de grabacion gasta no reabre ni cierra mas el publico.
    assert budget.public_remaining(gastando_la_reserva) == Money.measured(Decimal(0))


# --- La alerta, una sola vez --------------------------------------------------


def test_la_alerta_se_cruza_una_sola_vez_en_veinte_incrementos_seguidos() -> None:
    """AC5.14.2 y BR4.3. Se simulan veinte llamadas seguidas que atraviesan el
    umbral por el medio, y solo una lo cruza.

    Lo que se prueba no es que la alerta salga: es que salga **una**. Una alerta
    por llamada convierte el aviso en ruido y se deja de leer, que es la forma
    silenciosa de quedarse sin alerta justo cuando hacia falta.
    """
    ventana = _ventana(billable_spent_usd=Decimal("2.80"))
    incremento = Decimal("0.05")
    cruces = 0

    for _ in range(20):
        if budget.crosses_alert(ventana, incremento):
            cruces += 1
            ventana = ventana.evolve(alert_sent_at=AHORA)
        ventana = ventana.evolve(
            billable_spent_usd=ventana.billable_spent_usd + incremento,
        )

    assert cruces == 1
    assert ventana.billable_spent_usd == Decimal("3.80")
    assert ventana.alert_sent_at == AHORA


def test_una_sola_llamada_que_cruza_los_dos_umbrales_tambien_alerta() -> None:
    """La transicion `ok` -> `exhausted` de golpe: se emite la alerta y se corta,
    en ese orden. Si solo se mirara el estado final, una llamada grande dejaria
    el proyecto cortado sin que nunca hubiera salido el aviso."""
    ventana = _ventana(billable_spent_usd=Decimal("2.00"))

    assert budget.crosses_alert(ventana, Decimal("3.50"))
    assert (
        budget.status(ventana.evolve(billable_spent_usd=Decimal("5.50"))) is BudgetStatus.EXHAUSTED
    )


def test_con_la_marca_escrita_no_vuelve_a_cruzarse() -> None:
    """Que la marca exista es lo unico que impide la segunda alerta. Se comprueba
    aparte del recorrido de veinte porque es la condicion de la que depende, y en
    el recorrido quedaria tapada por el resultado."""
    ya_avisada = _ventana(billable_spent_usd=Decimal("2.99"), alert_sent_at=AHORA)

    assert not budget.crosses_alert(ya_avisada, Decimal("1.00"))


# --- El par que devuelve toda agregacion --------------------------------------


def test_la_foto_del_presupuesto_lleva_el_conteo_de_no_medidas() -> None:
    """BR3.5. El acumulado sale como par y no como numero suelto, asi que una
    pantalla no puede mostrar el total sin decir cuanto no se pudo valorar.

    Y ese conteo no es decorativo: **cambia lo que la foto dice**. Con llamadas
    facturables sin valorar, el restante publico no tiene numero y el estado lo
    dice; con todas valoradas, la misma ventana vuelve a hablar del acumulado.
    Las dos mitades juntas porque son la misma cifra vista desde sus dos lados.
    """
    ventana = _con_reserva(
        RESERVA,
        billable_spent_usd=Decimal("3.20"),
        recording_spent_usd=Decimal("0.05"),
        unmeasured_billable_calls=7,
    )

    foto = budget.state(ventana)

    assert foto.spent == SpendTotal(measured_usd=Decimal("3.20"), unmeasured_count=7)
    assert foto.status is BudgetStatus.UNMEASURED
    assert foto.public_remaining_usd == Money.not_measured()
    assert foto.recording_remaining_usd == Money.measured(Decimal("0.175"))
    assert foto.window_start == COMIENZO
    assert foto.window_end == date(2026, 12, 15)

    todas_valoradas = budget.state(ventana.evolve(unmeasured_billable_calls=0))

    assert todas_valoradas.spent == SpendTotal(measured_usd=Decimal("3.20"), unmeasured_count=0)
    assert todas_valoradas.status is BudgetStatus.ALERTED
    assert todas_valoradas.public_remaining_usd == Money.measured(Decimal("1.625"))


def test_el_total_cuenta_lo_no_medido_en_vez_de_sumarlo_como_cero() -> None:
    """Es la operacion que usan las cuatro agregaciones del reporte. Si lo no
    medido entrara como cero, el total bajaria y el conteo desapareceria: dos
    errores que se tapan el uno al otro."""
    assert budget.total([]) == SpendTotal(measured_usd=Decimal(0), unmeasured_count=0)
    assert budget.total(
        [
            Money.measured(Decimal("0.01")),
            Money.not_measured(),
            Money.measured(Decimal("0.02")),
            Money.not_measured(),
        ]
    ) == SpendTotal(measured_usd=Decimal("0.03"), unmeasured_count=2)


# --- La reserva que no se pudo calcular ---------------------------------------
# Desviacion consciente de `entities.md`, que declara la reserva obligatoria con
# default 0. Se declara en minutos y se convierte con la tabla de precios, que
# hoy no publica el precio por minuto de la voz: la conversion puede quedar **no
# medida**, y un cero diria "no hay reserva" en vez de "no se pudo calcular".


def _sin_reserva(**cambios: object) -> BudgetWindow:
    return BudgetWindow.model_validate(
        {
            "window_start": COMIENZO,
            "window_end": COMIENZO + timedelta(days=WINDOW_DAYS),
            "updated_at": AHORA,
        }
        | cambios
    )


def test_una_ventana_que_no_nombra_la_reserva_dice_que_no_se_midio() -> None:
    """El default es "no se pudo calcular", no cero.

    Es la diferencia que sostiene todo lo demas de este bloque: con default cero,
    la ausencia y la nulidad se escriben igual y ninguna herramienta puede
    distinguirlas despues.
    """
    ventana = _sin_reserva()

    assert ventana.recording_reserve_usd is None
    assert ventana.recording_reserve == Money.not_measured()
    assert not ventana.recording_reserve.is_measured


def test_con_la_reserva_sin_medir_los_dos_restantes_dicen_no_medido() -> None:
    """No se resta lo que no se sabe cuanto es, y las dos salidas mienten.

    Escribir el techo entero dejaria que el trafico publico se llevara lo
    apartado para el video; escribir cero diria "no queda nada" cuando no se ha
    gastado nada. El par dice la verdad, y por eso los dos restantes son `Money`
    y no un decimal suelto.
    """
    sin_gastar = _sin_reserva()

    assert budget.public_remaining(sin_gastar) == Money.not_measured()
    assert budget.recording_remaining(sin_gastar) == Money.not_measured()


def test_no_medido_y_agotado_cierran_igual_y_se_distinguen_en_el_estado() -> None:
    """La conducta es la misma; lo que cambia es lo que se dice.

    Cerrado para lo que cuesta dinero (NFR-U5-3): con las dos, el cupo del sitio
    es cero y la voz principal no cabe, asi que una llamada facturable se
    rechaza igual. Pero `exhausted` afirma que el presupuesto se gasto, y con la
    reserva sin medir no se ha gastado nada: colapsarlos es el mismo error que
    el proyecto ya se prohibio entre "no hay clausula" y "no pude verificar", y
    convertiria una de las cinco cifras publicadas en una que miente.
    """
    reserva_por_llamada = CallReserve(max_call_seconds=180, reserve=Money.measured(RESERVA))
    sin_medir = _sin_reserva()
    agotada = _con_reserva(RESERVA, billable_spent_usd=Decimal("5.00"))

    # Lo que cambia: el estado los distingue.
    assert budget.status(sin_medir) is BudgetStatus.UNMEASURED
    assert budget.status(agotada) is BudgetStatus.EXHAUSTED

    # Lo que no cambia: las dos cierran el carril de pago.
    for ventana in (sin_medir, agotada):
        restante = budget.public_remaining(ventana)
        assert (
            quota.site_daily_quota(
                restante, days_left=45, call_reserve=reserva_por_llamada, site_daily_cap=15
            )
            == 0
        )
        assert quota.voice_mode(restante, reserva_por_llamada) is VoiceMode.FALLBACK
        assert not quota.covers_primary_voice(restante, reserva_por_llamada)

    # Y hacia fuera comparten el motivo, porque el enum de C-08 tiene cuatro
    # valores cerrados y ampliarlo es tocar un contrato firmado. La discrepancia
    # esta declarada en `quota.budget_exhausted`, no heredada en silencio.
    assert quota.budget_exhausted().reason_code is QuotaReason.BUDGET_EXHAUSTED


def test_una_reserva_medida_sin_cantidad_no_se_puede_escribir() -> None:
    """La invariante de `Money`, en las dos columnas de la fila (BR3.9).

    Sin ella, una reserva "medida" y vacia se leeria como cero en cualquier
    resta, que es el fallo silencioso que esta desviacion existe para impedir.
    """
    with pytest.raises(ValidationError):
        _sin_reserva(recording_reserve_status=CostStatus.MEASURED)

    with pytest.raises(ValidationError):
        _sin_reserva(
            recording_reserve_usd=RESERVA, recording_reserve_status=CostStatus.NOT_MEASURED
        )


# --- El gasto facturable que no se pudo valorar -------------------------------
# La segunda causa de "no medido", decidida el 2026-09-21. Una llamada
# facturable sin precio de lista suma cero al acumulado, asi que el numero con
# el que el techo decide se queda corto: el corte cierra, porque falla cerrado
# para lo que cuesta dinero.


def test_una_llamada_facturable_sin_valorar_deja_el_restante_publico_sin_numero() -> None:
    """Es el mismo argumento que el de la reserva, aplicado al otro sumando.

    No se puede restar lo que no se sabe cuanto es. Con una llamada sin valorar
    en la ventana, el acumulado es un **piso** y no una medicion: lo unico que
    se sabe del restante es que no es mayor que el que sale de la resta, y
    publicar esa resta como si fuera el restante es la forma de cruzar los 5 USD
    con el estado en `ok`.
    """
    con_una_sin_valorar = _con_reserva(
        RESERVA, billable_spent_usd=Decimal("0.10"), unmeasured_billable_calls=1
    )

    assert budget.public_remaining(con_una_sin_valorar) == Money.not_measured()
    assert budget.status(con_una_sin_valorar) is BudgetStatus.UNMEASURED


def test_el_carril_de_grabacion_conserva_su_numero_con_una_llamada_publica_sin_valorar() -> None:
    """El alcance del corte, dicho: se cierra el carril del que salio la llamada.

    La llamada sin valorar es del enlace publico --el conteo del carril de
    grabacion sigue en cero-- y la reserva del video de la semana doce se queda
    entera. Cerrarla tambien seria gastarla sin que nadie la hubiera gastado,
    que es justo lo que BR4.10 existe para impedir.
    """
    con_una_sin_valorar = _con_reserva(
        RESERVA, billable_spent_usd=Decimal("0.10"), unmeasured_billable_calls=1
    )

    assert con_una_sin_valorar.unmeasured_recording_calls == 0
    assert budget.recording_remaining(con_una_sin_valorar) == Money.measured(RESERVA)


def test_una_llamada_sin_valorar_cierra_el_cupo_del_sitio_y_la_voz_principal() -> None:
    """Las dos consecuencias que hacen del "no medido" un corte y no una etiqueta.

    El cupo del sitio y el modo de voz leen el restante publico, no el estado, y
    los dos ya saben responder a un restante sin numero: cero llamadas y voz de
    respaldo. Por eso la decision se escribe en el restante y no en cada uno de
    ellos --no hay una segunda regla que alguien pueda olvidar-- y por eso esta
    prueba mira lo que decide y no lo que se muestra.
    """
    reserva_por_llamada = CallReserve(max_call_seconds=180, reserve=Money.measured(RESERVA))
    con_una_sin_valorar = _con_reserva(
        RESERVA, billable_spent_usd=Decimal("0.10"), unmeasured_billable_calls=1
    )

    restante = budget.public_remaining(con_una_sin_valorar)

    assert (
        quota.site_daily_quota(
            restante, days_left=45, call_reserve=reserva_por_llamada, site_daily_cap=15
        )
        == 0
    )
    assert quota.voice_mode(restante, reserva_por_llamada) is VoiceMode.FALLBACK


# --- El carril de grabacion, entero -------------------------------------------
# Las dos mitades que faltaban, cerradas el 2026-09-21. La primera deja que una
# llamada de grabacion registre su exceso (BR3.1 sobre BR4.5); la segunda le da
# a ese carril el mismo corte por lo no valorado que ya tenia el publico.


def test_la_reserva_agotada_no_impide_registrar_el_gasto_y_el_restante_se_queda_en_cero() -> None:
    """BR3.1 manda: primero la fila, y el restante ya sabe informarse con piso.

    El techo se consulta **antes** de llamar al proveedor y el costo se registra
    **despues** (BR4.5), asi que la ultima llamada de un carril puede costar mas
    de lo que quedaba. Lo que esta prueba fija es que ese exceso es
    **representable**: si la ventana no pudiera escribirlo, la fila de gasto de
    una llamada que ya se pago se perderia, y una cifra publicada bajaria sin
    que nada lo dijera.

    El restante no miente por eso: llega a cero y se queda ahi.
    """
    pasada = _con_reserva(
        RESERVA,
        billable_spent_usd=Decimal("0.40"),
        recording_spent_usd=Decimal("0.30"),
    )

    assert pasada.recording_spent_usd > RESERVA
    assert budget.recording_remaining(pasada) == Money.measured(Decimal(0))
    #: Y no se lleva por delante al otro carril: lo publico sigue siendo el
    #: acumulado menos lo de grabacion, con su propio numero.
    assert budget.public_remaining(pasada) == Money.measured(Decimal("4.675"))


def test_con_la_reserva_sin_medir_tambien_se_puede_haber_gastado() -> None:
    """La mitad simetrica, y la que mas costaba ver.

    Con el tamano de la reserva desconocido, la ventana **tampoco** exige que el
    carril no haya gastado: la llamada se hizo y BR3.1 no tiene excepciones. Lo
    que el restante dice entonces es "no se pudo calcular", que es cierto por
    partida doble --no se sabe ni cuanto habia ni cuanto se lleva-- y nunca cero,
    que se leeria como "la reserva se gasto".
    """
    gastando_a_ciegas = _sin_reserva(
        billable_spent_usd=Decimal("0.10"), recording_spent_usd=Decimal("0.10")
    )

    assert gastando_a_ciegas.recording_spent_usd == Decimal("0.10")
    assert budget.recording_remaining(gastando_a_ciegas) == Money.not_measured()


def test_una_llamada_de_grabacion_sin_valorar_deja_su_restante_sin_numero() -> None:
    """El segundo hueco, y es el mismo fallo silencioso que ya se cerro enfrente.

    Una llamada de grabacion sin precio de lista suma cero a lo gastado de su
    carril --se cuenta aparte, nunca como cero silencioso (BR3.3)--, asi que la
    resta que produce el restante parte de un **piso** y no de una medicion. Sin
    este corte, ese restante sale inflado y nada lo dice: la reserva del video de
    la semana doce se gastaria con el numero diciendo que queda.
    """
    con_una_de_grabacion_sin_valorar = _con_reserva(
        RESERVA,
        billable_spent_usd=Decimal("0.10"),
        recording_spent_usd=Decimal("0.10"),
        unmeasured_billable_calls=1,
        unmeasured_recording_calls=1,
    )

    assert budget.recording_remaining(con_una_de_grabacion_sin_valorar) == Money.not_measured()


def test_una_de_grabacion_sin_valorar_no_cierra_el_carril_publico() -> None:
    """La imprecision de un carril no cierra el otro, y la aritmetica lo prueba.

    El gasto publico no se guarda: se deriva restando lo de grabacion del
    facturable. Una llamada de grabacion sin valorar suma **cero a los dos**, asi
    que al restarlos ese cero se cancela y el gasto publico sigue siendo una
    medicion exacta. Cerrar el carril publico por ella cerraria por una
    imprecision que no esta en su lado de la resta.

    No afloja el techo: el techo sigue en su cifra y el carril de grabacion --que
    es el que si queda impreciso-- se cierra por su propia causa, comprobado en
    la prueba de arriba. Lo que cambia es de que lado de la resta se mira.

    Importa hoy y no en abstracto: el precio que falta en la tabla es el del
    minuto de voz, que es justo lo que consume una grabacion. Sin este descuento,
    la primera grabacion de la semana doce apagaria el chat y la voz publicos
    durante el resto de la ventana de noventa dias.
    """
    solo_grabacion_sin_valorar = _con_reserva(
        RESERVA,
        billable_spent_usd=Decimal("0.10"),
        recording_spent_usd=Decimal("0.10"),
        unmeasured_billable_calls=1,
        unmeasured_recording_calls=1,
    )

    publico = budget.public_remaining(solo_grabacion_sin_valorar)

    assert publico.status is CostStatus.MEASURED
    # El gasto publico derivado es 0,10 - 0,10 = 0, asi que queda el techo entero
    # menos la reserva: la llamada sin valorar no movio ninguno de los dos lados.
    assert solo_grabacion_sin_valorar.public_spent_usd == Decimal("0.00")
    assert publico.amount_usd == solo_grabacion_sin_valorar.cap_usd - RESERVA
    # Y el carril que si quedo impreciso sigue cerrado, que es el contraste.
    assert budget.recording_remaining(solo_grabacion_sin_valorar) == Money.not_measured()


def test_una_del_publico_sin_valorar_sigue_cerrando_el_publico() -> None:
    """La otra mitad del descuento: lo que si esta en su lado de la resta.

    Sin esta prueba, el descuento de arriba pasaria igual con el corte del carril
    publico apagado del todo, que es justo lo que no se quiere.
    """
    una_del_publico = _con_reserva(
        RESERVA,
        billable_spent_usd=Decimal("0.10"),
        recording_spent_usd=Decimal("0.00"),
        unmeasured_billable_calls=1,
        unmeasured_recording_calls=0,
    )

    assert budget.public_remaining(una_del_publico) == Money.not_measured()


def test_las_dos_causas_del_restante_de_grabacion_sin_numero_se_distinguen_en_la_foto() -> None:
    """Dos causas, una sola respuesta: la foto tiene que decir cual fue.

    Las dos dan `not_measured` y las dos cierran igual, asi que el valor no las
    distingue --por lo mismo que `unmeasured` y `exhausted` no se colapsan--. La
    que distingue es la **reserva**, que solo puede quedarse sin numero de una
    forma; el restante ya no sirve para eso desde que tiene dos causas, y ahi
    estaba escrito antes.
    """
    reserva_ilegible = budget.state(_sin_reserva(billable_spent_usd=Decimal("0.10")))
    llamada_sin_valorar = budget.state(
        _con_reserva(
            RESERVA,
            billable_spent_usd=Decimal("0.10"),
            recording_spent_usd=Decimal("0.10"),
            unmeasured_billable_calls=1,
            unmeasured_recording_calls=1,
        )
    )

    # Lo que comparten: ninguna de las dos tiene numero que dar.
    assert reserva_ilegible.recording_remaining_usd == Money.not_measured()
    assert llamada_sin_valorar.recording_remaining_usd == Money.not_measured()

    # Lo que las separa, sin volver a la base.
    assert reserva_ilegible.recording_reserve_usd == Money.not_measured()
    assert reserva_ilegible.recording_spent.unmeasured_count == 0

    assert llamada_sin_valorar.recording_reserve_usd == Money.measured(RESERVA)
    assert llamada_sin_valorar.recording_spent == SpendTotal(
        measured_usd=Decimal("0.10"), unmeasured_count=1
    )


def test_una_reserva_medida_en_cero_no_es_lo_mismo_que_una_reserva_sin_medir() -> None:
    """El caso que la foto tiene que poder contar, y que un decimal no contaria.

    Con la reserva en cero el carril de grabacion existe y no tiene nada: su
    restante es cero, medido. Con la reserva sin medir no se sabe ni eso. Las dos
    cierran el carril, pero solo una afirma algo sobre el presupuesto, y el panel
    dice cosas distintas en cada caso.
    """
    en_cero = budget.state(_con_reserva(Decimal(0)))
    sin_medir = budget.state(_sin_reserva())

    assert en_cero.recording_reserve_usd == Money.measured(Decimal(0))
    assert en_cero.recording_remaining_usd == Money.measured(Decimal(0))
    assert sin_medir.recording_reserve_usd == Money.not_measured()
    assert sin_medir.recording_remaining_usd == Money.not_measured()
