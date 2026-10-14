"""El techo, la alerta y los dos carriles: aritmetica pura, sin base de datos.

Todo lo de aqui son funciones de sus argumentos. No es purismo: el corte del
gasto es la unica conducta del proyecto cuyo fallo no produce un error sino una
factura, y una conducta asi tiene que poder probarse en sus bordes --el cruce de
la alerta, el techo exacto, la reserva agotada-- sin levantar un contenedor y sin
gastar un centavo del presupuesto que protege (BR5.9).

Lo que **no** vive aqui, y por que:

- **Tomar la fila y sumarla.** Eso es del repositorio, que lo hace en una sola
  sentencia condicional dentro de la transaccion que escribe la fila de gasto
  (BR4.6). Aqui se decide **que** significa el numero; alla se consigue que dos
  llamadas simultaneas no lean el mismo.
- **Emitir la alerta.** Aqui se responde si esta llamada la cruzo; el canal lo
  fija el intent `infra`.
- **Cualquier cosa de trazas.** La contabilidad no importa las trazas, para que
  "el corte funciona aunque la observacion falle" (BR4.8) sea una regla que una
  herramienta comprueba y no una frase de un documento.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from untangle.telemetry.spend.models import (
    BudgetState,
    BudgetStatus,
    BudgetWindow,
    Money,
    SpendTotal,
)

#: Cero, escrito una vez. Un importe nunca se informa negativo: por debajo de
#: cero no queda "menos presupuesto", queda ninguno, y el estado ya dice que se
#: agoto (BR4.9).
_CERO = Decimal(0)


def public_remaining(window: BudgetWindow) -> Money:
    """Lo que el enlace publico todavia puede gastar (BR4.9). **Par, no numero.**

    Techo menos reserva de grabacion menos lo que el carril publico lleva
    gastado. La reserva se resta **antes** que nada: existe para que un dia de
    trafico en el enlace publico no deje al proyecto sin presupuesto para grabar
    el video de la semana doce, y restarla despues seria no reservarla.

    **Dos cosas lo dejan sin numero, y las dos por el mismo argumento**: no se
    puede restar lo que no se sabe cuanto es. Una es la reserva sin medir; la
    otra es el minuendo, o sea una llamada facturable que no se pudo valorar. En
    los dos casos la respuesta es `not_measured` y nunca cero ni el techo
    entero, que son las dos mentiras que esta unidad existe para no contar:
    escribir el techo dejaria que el trafico publico se llevara lo apartado para
    el video, y escribir cero diria "no queda nada" cuando no se ha gastado
    nada. El par dice la verdad --"no se pudo calcular"-- y quien lo consuma
    decide con esa informacion en la mano.

    Que el corte cierre ante lo no valorado es **decision de Miguel del
    2026-09-21**, y su razon es la que gobierna la unidad entera: el corte falla
    cerrado para lo que cuesta dinero, y equivocarse hacia "sigue gastando" es
    exactamente el modo de fallo que el techo existe para impedir.
    """
    apartado = window.recording_reserve_usd
    if apartado is None:
        return Money.not_measured()
    sin_valorar_del_publico = window.unmeasured_billable_calls - window.unmeasured_recording_calls
    if sin_valorar_del_publico > 0:
        # Una llamada facturable sin precio de lista suma **cero** al acumulado
        # (BR3.3: se cuenta aparte, nunca se suma como cero silencioso). El
        # acumulado pasa entonces a ser un **piso** y no una medicion, y de un
        # piso no sale un restante: lo unico que se sabe es que el restante de
        # verdad no es mayor que el de la resta. Publicar esa resta como si
        # fuera el restante es como se cruzan los 5 USD y la alerta de los 3 USD
        # con el estado diciendo `ok`, que es gasto sin excepcion escrita.
        #
        # **La cuenta descuenta las llamadas de grabacion, y la aritmetica dice
        # por que.** El gasto publico no se guarda: se deriva restando lo de
        # grabacion del facturable. Una llamada de grabacion sin valorar suma
        # cero a los **dos**, asi que al restarlos ese cero se cancela y el
        # gasto publico sigue siendo una medicion exacta, no un piso. Cerrar el
        # carril publico por ella no protegeria nada: cerraria por una
        # imprecision que no esta en su lado de la resta.
        #
        # No es aflojar el techo. El techo sigue en su cifra, el corte sigue
        # fallando cerrado, y lo que la llamada de grabacion si vuelve
        # impreciso --el restante de **su** carril-- lo cierra `recording_remaining`
        # por su segunda causa. Lo que cambia es **de que lado de la resta** se
        # mira la imprecision, que es donde estaba el error.
        #
        # Y no es teorico: el precio que hoy falta en la tabla es justo el del
        # minuto de voz, o sea el que consume una grabacion. Sin este descuento,
        # la primera grabacion de la semana doce apagaria el chat y la voz
        # publicos durante el resto de la ventana de noventa dias, que es
        # exactamente la demostracion que la grabacion existe para mostrar.
        return Money.not_measured()
    restante = window.cap_usd - apartado - window.public_spent_usd
    return Money.measured(max(_CERO, restante))


def recording_remaining(window: BudgetWindow) -> Money:
    """Lo que queda de la reserva de grabacion. Corre aparte del publico.

    Tambien es un par, y por la mitad simetrica del mismo argumento: no se puede
    afirmar que quede algo --ni que no quede nada-- de una reserva cuyo tamano no
    se conoce. Un cero aqui se leeria como "la reserva se gasto", que es
    exactamente lo contrario de lo que pasa.

    **Dos causas lo dejan sin numero, y se comprueban en este orden**, el mismo
    que el del carril publico porque es el mismo argumento aplicado a los dos
    terminos de la resta:

    1. **La reserva**, que es el minuendo. No se resta de lo que no se sabe
       cuanto es. Es la causa que existe desde el primer dia: la reserva se
       declara en minutos y la tabla de precios no publica el precio por minuto
       de la voz.
    2. **El sustraendo**, o sea una llamada de grabacion que no se pudo valorar.
       Suma cero a `recording_spent_usd` --nunca como cero silencioso, se cuenta
       aparte (BR3.3)--, asi que lo gastado pasa a ser un **piso** y no una
       medicion, y de un piso no sale un restante: lo unico que se sabe es que
       el restante de verdad no es mayor que el de la resta. Publicar esa resta
       como si fuera el restante es como la reserva del video de la semana doce
       se gasta con el estado diciendo que queda.

    **Cual de las dos fue se lee en la foto** (`budget.state`), y no hay que
    volver a la base para saberlo: `recording_spent.unmeasured_count` mayor que
    cero senala la segunda, y `recording_reserve_usd` sin medir la primera. La
    reserva es la que distingue, porque tiene una sola forma de quedarse sin
    numero; este restante ya no sirve para eso desde que tiene dos causas.

    Que el corte cierre ante lo no valorado --y que cerrar de mas cueste menos
    que gastar de mas-- es la misma decision del 2026-09-21 que gobierna el
    carril publico, aplicada al carril que no la tenia.
    """
    apartado = window.recording_reserve_usd
    if apartado is None:
        return Money.not_measured()
    if window.unmeasured_recording_calls > 0:
        return Money.not_measured()
    return Money.measured(max(_CERO, apartado - window.recording_spent_usd))


def status(window: BudgetWindow) -> BudgetStatus:
    """El estado del **carril publico**, que es el que ve un visitante.

    Cuatro estados y este es el orden en que se deciden:

    1. **`unmeasured`** cuando el restante publico no se puede calcular: la
       reserva de grabacion sin medir, o alguna llamada facturable que no se
       pudo valorar. Va primero porque sin ese numero las dos comparaciones de
       abajo no significan nada, y **las dos causas entran por aqui** porque las
       dos las resuelve `public_remaining`: no hay una segunda regla en este
       archivo que alguien pueda olvidar al anadir una tercera causa.
    2. **`exhausted`** cuando el restante publico llego a cero.
    3. **`alerted`** cuando el acumulado facturable alcanzo su umbral.
    4. **`ok`** en lo demas.

    El agotamiento se comprueba antes que la alerta porque los dos umbrales
    miden cosas distintas: la alerta mira el acumulado facturable contra su
    umbral, y el agotamiento mira el restante **publico**, que ya descuenta la
    reserva. Con reserva apartada, el carril publico se cierra antes de que el
    acumulado llegue al techo, y eso es lo correcto: `exhausted` con reserva
    disponible es un estado normal y esperado (BR4.10).

    **`unmeasured` y `exhausted` cierran igual el carril de pago** (NFR-U5-3):
    lo que cambia es lo que se dice, no lo que se hace.
    """
    restante = public_remaining(window)
    if restante.amount_usd is None:
        return BudgetStatus.UNMEASURED
    if restante.amount_usd <= _CERO:
        return BudgetStatus.EXHAUSTED
    if window.billable_spent_usd >= window.alert_usd:
        return BudgetStatus.ALERTED
    return BudgetStatus.OK


def crosses_alert(window: BudgetWindow, added_usd: Decimal) -> bool:
    """Si **esta** llamada cruza la alerta, y por tanto si hay que emitirla.

    Cruzar es pasar de estar por debajo del umbral a alcanzarlo o superarlo, y
    solo cuenta si la marca de envio esta vacia (BR4.3). La marca es lo que
    convierte "una alerta" en una sola: sin ella, cada llamada por encima de los
    3 USD emitiria la suya, el aviso se volveria ruido y se dejaria de leer, que
    es la forma silenciosa de quedarse sin alerta.
    """
    if window.alert_sent_at is not None:
        return False
    if window.billable_spent_usd >= window.alert_usd:
        return False
    return window.billable_spent_usd + added_usd >= window.alert_usd


def total(costs: Iterable[Money]) -> SpendTotal:
    """El par que devuelve **toda** agregacion de esta unidad (BR3.5).

    Lo medido se suma en decimal exacto, asi que el resultado no depende del
    orden en que llegaron los costos; lo no medido se cuenta aparte en vez de
    entrar como cero. Quien quiera publicar el total sin decir cuanto no se midio
    tiene que desarmar el tipo a proposito, y eso se ve en una revision.
    """
    medido = _CERO
    sin_medir = 0
    for costo in costs:
        if costo.amount_usd is None:
            sin_medir += 1
        else:
            medido += costo.amount_usd
    return SpendTotal(measured_usd=medido, unmeasured_count=sin_medir)


def state(window: BudgetWindow) -> BudgetState:
    """La foto que consumen la consola de voz, el chat y la pantalla de gasto.

    El acumulado viaja como `SpendTotal` y no como un numero suelto: el conteo de
    llamadas facturables que no se pudieron valorar lo lleva la propia fila de la
    ventana, asi que la foto no puede salir de aqui sin el.

    **Y lleva con que explicarse.** Un restante sin numero tiene dos causas --la
    reserva ilegible y una llamada sin valorar-- y la foto trae las dos: la
    reserva, que solo puede quedarse sin numero de una forma, y el gasto de
    grabacion con su propio conteo. Sin ellas, "no se pudo calcular" seria un
    callejon sin salida para quien lea la pantalla: sabria que no hay numero y no
    que hacer para que lo haya.
    """
    return BudgetState(
        window_start=window.window_start,
        window_end=window.window_end,
        spent=SpendTotal(
            measured_usd=window.billable_spent_usd,
            unmeasured_count=window.unmeasured_billable_calls,
        ),
        cap_usd=window.cap_usd,
        alert_usd=window.alert_usd,
        recording_reserve_usd=window.recording_reserve,
        recording_spent=SpendTotal(
            measured_usd=window.recording_spent_usd,
            unmeasured_count=window.unmeasured_recording_calls,
        ),
        public_remaining_usd=public_remaining(window),
        recording_remaining_usd=recording_remaining(window),
        status=status(window),
    )
