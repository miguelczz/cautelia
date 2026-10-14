"""Donde el gasto se escribe y de donde se lee.

**Ninguna conexion propia.** Toda consulta pasa por el punto unico de sesion de
U2 (SEC-U5.3). Este archivo no sabe la direccion de la base, no construye un
motor y no arma SQL por concatenacion: los parametros se ligan. Un contrato de
importacion falla ante cualquier apertura de conexion plantada aqui.

**Sesion sin aseguradora, y por que es la correcta.** Las cuatro tablas que este
archivo escribe --el registro de gasto, los contadores de cuota, el acumulado de
la ventana y la marca de cierre de llamada-- son dato del proyecto: no llevan
columna de aseguradora, estan en la lista de exclusion versionada y no tienen
politica que fijar (BR7.1). El techo es uno solo para todo el proyecto y el gasto
de evaluaciones, generacion y operacion no pertenece a ninguna aseguradora. Pedir
una sesion con aseguradora fijada aqui seria fingir una atribucion que no existe.

## La escritura facturable: una transaccion, dos sentencias, ninguna lectura

Es la pieza central de este archivo y la unica cuya forma no es negociable
(BR4.6, diseno de rendimiento):

- **No hay lectura previa**, asi que no hay ventana entre leer y escribir. El
  motor serializa por si solo las escrituras sobre la fila unica de la ventana.
- **La sentencia devuelve el acumulado ya incrementado**, que es exactamente lo
  que hace falta para saber si *esta* llamada cruzo la alerta y le toca
  emitirla. Sin ese valor de vuelta habria que releer, y la relectura reabriria
  la carrera que esta forma cierra.
- **La marca de alerta se decide y se escribe dentro de la misma sentencia**,
  por la misma razon por la que la marca existe: dos llamadas que cruzaran a la
  vez emitirian dos alertas si la marca se escribiera fuera (BR4.3).
- **Las dos sentencias son una transaccion.** Si la segunda falla, la primera no
  queda: el registro y el acumulado no se pueden separar.

La condicion de cruce se escribe **dos veces a proposito** --una en el `CASE`
que escribe la marca y otra en el `RETURNING` que la informa-- y las dos miran
solo la fila objetivo y los parametros. Es lo que las hace correctas bajo
concurrencia: cuando una transaccion espera a otra sobre la misma fila,
PostgreSQL vuelve a evaluar las expresiones de la tabla objetivo contra la fila
ya actualizada, de modo que la segunda llamada ve el acumulado que dejo la
primera. Una version que leyera el valor anterior por un `FROM` sobre la misma
tabla veria la foto del inicio de la sentencia, y las dos creerian haber sido la
que cruzo.

El `RETURNING` compara ademas `alert_sent_at` con **este** instante, y no se
conforma con que la marca no este vacia. La diferencia se paga cuando la marca
ya venia escrita de antes y el acumulado sigue por debajo del umbral --porque
alguien corrigio la fila o subio la alerta-- y entra un gasto que lo cruza: sin
la comparacion, ahi se informaria un segundo aviso aunque el `CASE` haya hecho
lo correcto y no haya tocado la fecha. Lo encontro la prueba de ese caso, no la
lectura del codigo.

**Su limite, dicho.** La comparacion falla si la marca anterior coincidiera al
microsegundo con el instante de esta llamada. Ese estado no lo produce este
codigo --la marca se escribe una vez y las llamadas siguientes llegan despues--
y solo se alcanza sembrando la fila a mano con ese instante exacto.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from untangle.base import Frozen, ProviderName, SpendSource
from untangle.telemetry.spend.models import (
    AUDIO_UNIT_KINDS,
    SITE_SUBJECT,
    TOKEN_UNIT_KINDS,
    WINDOW_START,
    BudgetLane,
    BudgetWindow,
    CallRef,
    CostStatus,
    CounterKey,
    QuotaCounter,
    QuotaPeriod,
    QuotaScope,
    ReleaseOutcome,
    SpendActivity,
    SpendEntry,
    SpendTotal,
    SubjectKey,
    UnpricedUsage,
    derive_counter_key,
)
from untangle.tenancy import session

#: Cero, escrito una vez. Lo usan el incremento de una llamada no medida --que
#: no suma dinero pero si cuenta-- y el carril publico, que no toca la columna
#: de grabacion.
_CERO = Decimal(0)

INSERTAR_GASTO = """
    INSERT INTO spend_entry (
        entry_id, provider, model, use, tenant_ref, case_ref, call_ref, units, unit_kind,
        unit_price_usd, price_list_version, price_list_effective_date,
        cost_usd, cost_status, billable, lane, source, occurred_at, note
    ) VALUES (
        :entry_id, :provider, :model, :use, :tenant_ref, :case_ref, :call_ref,
        :units, :unit_kind,
        :unit_price_usd, :price_list_version, :price_list_effective_date,
        :cost_usd, :cost_status, :billable, :lane, :source, :occurred_at, :note
    )
"""

#: El mismo asiento, para un ajuste conciliado: **idempotente por su identificador**.
#: Reintentar el mismo comando no escribe una segunda fila ni suma dos veces al
#: acumulado, porque `ON CONFLICT DO NOTHING` deja el numero de filas tocadas en cero
#: y quien llama no incrementa la ventana (`record_adjustment`). El gasto de una
#: llamada no lo necesita: su identificador es nuevo en cada llamada.
INSERTAR_AJUSTE = """
    INSERT INTO spend_entry (
        entry_id, provider, model, use, tenant_ref, case_ref, call_ref, units, unit_kind,
        unit_price_usd, price_list_version, price_list_effective_date,
        cost_usd, cost_status, billable, lane, source, occurred_at, note
    ) VALUES (
        :entry_id, :provider, :model, :use, :tenant_ref, :case_ref, :call_ref,
        :units, :unit_kind,
        :unit_price_usd, :price_list_version, :price_list_effective_date,
        :cost_usd, :cost_status, :billable, :lane, :source, :occurred_at, :note
    )
    ON CONFLICT (entry_id) DO NOTHING
"""

#: La segunda sentencia de la transaccion facturable. Incrementa, decide la
#: alerta y devuelve el acumulado nuevo, todo en una (BR4.6, BR4.3).
#:
#: `unmeasured_billable_calls` sube **solo** cuando la llamada no se pudo
#: valorar, y en ese caso el costo que suma es cero: una llamada sin precio no
#: se suma como cero silencioso, se cuenta aparte (BR3.5).
#:
#: `unmeasured_recording_calls` sube en el mismo acto y con el mismo criterio,
#: pero solo cuando la llamada era del carril de grabacion. Los dos parametros
#: viajan por separado --no se deriva uno del otro dentro de la sentencia--
#: exactamente igual que `:costo` y `:costo_de_grabacion`: quien sabe de que
#: carril salio la llamada es quien la escribe, y una sentencia que lo
#: adivinara repetiria esa decision en un segundo sitio.
#:
#: **Dos trampas encontradas al construir esto, y las dos por una prueba y no
#: por leer el codigo. Estan escritas aqui porque es donde se vuelven a romper.**
#:
#: 1. `w.alert_sent_at IS NULL` en el `CASE` parece redundante --si el acumulado
#:    viejo estaba por debajo del umbral, la marca no deberia existir-- y
#:    quitarlo **no rompe** la prueba de los veinte incrementos seguidos: despues
#:    del cruce el acumulado ya esta por encima, asi que la condicion del umbral
#:    sola basta para que no se repita. La linea la ejerce otra prueba, la de una
#:    ventana ya avisada cuyo acumulado sigue por debajo del umbral. Si alguien
#:    borra esa linea por parecer de mas, esa prueba es la que lo dice.
#: 2. El `RETURNING` decia `alert_sent_at IS NOT NULL` y era un **falso
#:    positivo**: con la marca escrita de antes informaba un segundo aviso
#:    aunque el `CASE` no hubiera tocado la fecha. Compara contra `:ahora`
#:    justamente por eso.
INCREMENTAR_VENTANA = """
    UPDATE budget_window AS w
       SET billable_spent_usd = w.billable_spent_usd + :costo,
           recording_spent_usd = w.recording_spent_usd + :costo_de_grabacion,
           unmeasured_billable_calls = w.unmeasured_billable_calls + :no_medida,
           unmeasured_recording_calls =
               w.unmeasured_recording_calls + :no_medida_de_grabacion,
           alert_sent_at = CASE
               WHEN w.alert_sent_at IS NULL
                AND w.billable_spent_usd < w.alert_usd
                AND w.billable_spent_usd + :costo >= w.alert_usd
               THEN :ahora
               ELSE w.alert_sent_at
           END,
           updated_at = :ahora
     WHERE w.window_start = :ventana
 RETURNING w.window_start,
           w.window_end,
           w.billable_spent_usd,
           w.cap_usd,
           w.alert_usd,
           w.alert_sent_at,
           w.recording_reserve_usd,
           w.recording_reserve_status,
           w.recording_spent_usd,
           w.unmeasured_billable_calls,
           w.unmeasured_recording_calls,
           w.updated_at,
           (
               w.alert_sent_at = :ahora
               AND w.billable_spent_usd - :costo < w.alert_usd
               AND w.billable_spent_usd >= w.alert_usd
           ) AS crossed_alert
"""

LEER_VENTANA = "SELECT * FROM budget_window WHERE window_start = :ventana"

LEER_CONTADOR = "SELECT * FROM quota_counter WHERE counter_key = :clave"

#: Consulta e incremento en una sola sentencia y una sola transaccion (BR5.1).
#: `ON CONFLICT` cierra la carrera de dos llamadas simultaneas del mismo sujeto:
#: la fila se crea una vez y la segunda incrementa la que ya existe, en vez de
#: crear una segunda que dejaria pasar el doble de lo permitido (RT-13).
#:
#: El incremento es **condicional**: solo sube si todavia cabe. Asi la decision y
#: el consumo son el mismo acto, y entre los dos no hay hueco por el que se
#: cuelen dos peticiones.
#:
#: **El `WHERE :limite > 0` del inserto no es adorno, y encontrarlo costo una
#: prueba.** La condicion del `ON CONFLICT` solo gobierna la fila que ya existe;
#: la primera peticion de un periodo va por el inserto, que no miraba el limite y
#: por tanto **pasaba siempre**, incluso con el limite en cero. Y cero no es un
#: caso raro: es exactamente lo que devuelve el cupo del sitio cuando el
#: presupuesto publico se agota (BR5.6), o sea el corte del enlace publico
#: expresado como cupo. Sin esta linea, ese corte dejaba entrar una llamada por
#: dia --la primera-- y el fallo era invisible: el contador quedaba escrito con
#: `count = 1` y `limit_at_period_start = 0`, que es una fila que se lee como si
#: todo estuviera bien.
#:
#: Se escribe como `INSERT ... SELECT ... WHERE` y no como una comprobacion en
#: Python porque la decision tiene que seguir siendo **una sola sentencia**: un
#: `if` antes del inserto reabriria el hueco entre decidir y consumir que esta
#: forma cierra.
# Se compara contra el limite **vigente** (`:limite`), no contra el que se escribio
# al abrir el periodo, y el guardado se refresca: el cupo del sitio se deriva del
# presupuesto, y el 2026-10-07 el tope subio a mitad de dia (de 5 a 40 USD) sin que
# la admision lo viera --la disponibilidad decia "7" y la apertura seguia rechazando
# con el "1" guardado por la manana--. Lo guardado sigue explicando un rechazo:
# es el limite que regia en la ultima consumicion de ese periodo.
CONSUMIR_CUOTA = """
    INSERT INTO quota_counter (
        counter_key, scope, subject_key, period_start, count,
        limit_at_period_start, updated_at
    )
    SELECT :clave, :alcance, :sujeto, :periodo, 1, :limite, :ahora
     WHERE :limite > 0
    ON CONFLICT (counter_key) DO UPDATE
       SET count = quota_counter.count + 1,
           limit_at_period_start = :limite,
           updated_at = :ahora
     WHERE quota_counter.count < :limite
 RETURNING counter_key, scope, subject_key, period_start, count,
           limit_at_period_start, updated_at
"""

#: La pregunta que F4 le hace al registro de gasto, y **solo** al registro de
#: gasto: ¿dejo esta llamada alguna fila de audio con unidades mayores que cero?
#:
#: Contra el libro mayor y nunca contra lo que diga la consola, porque la consola
#: es de quien llama: un cliente que mintiera se devolveria a si mismo el cupo de
#: una llamada que si se gasto (BR5.5).
#:
#: `EXISTS` y no `count(*)`: la pregunta es si hay alguna, y el motor para en la
#: primera. Las clases de audio viajan como parametro en vez de escribirse en la
#: cadena, para que `AUDIO_UNIT_KINDS` siga siendo el unico sitio donde se decide
#: que cuenta como audio.
HAY_AUDIO_FACTURABLE = """
    SELECT EXISTS (
        SELECT 1
          FROM spend_entry
         WHERE call_ref = :llamada
           AND unit_kind = ANY(:clases)
           AND units > 0
    ) AS hay_audio
"""

#: La marca del cierre, y todo el mecanismo de idempotencia de BR5.5.
#:
#: `ON CONFLICT DO NOTHING RETURNING` devuelve fila **solo la primera vez**: el
#: segundo cierre de la misma llamada no recibe nada y por tanto no decrementa
#: nada. Dos cierres simultaneos compiten por la clave primaria y uno de los dos
#: espera; cuando sigue, la fila ya esta y tampoco decrementa.
#:
#: Va en la misma transaccion que los decrementos por la misma razon por la que
#: la fila de gasto y el acumulado van juntos (BR4.6): si la marca quedara
#: escrita y el decremento no, el cupo se perderia para siempre sin que nada lo
#: dijera.
MARCAR_CIERRE = """
    INSERT INTO voice_call_release (call_ref, released, decided_at)
    VALUES (:llamada, :devuelto, :ahora)
    ON CONFLICT (call_ref) DO NOTHING
 RETURNING call_ref
"""

#: El decremento, con su guarda. `count > 0` no es defensa por si acaso: el
#: contador del visitante se borra cada noche (BR7.6) y una llamada abierta antes
#: del reinicio se cierra despues, asi que el caso de decrementar un contador que
#: ya no existe --o que existe en cero-- es normal y no excepcional. Un contador
#: negativo es cupo regalado.
DEVOLVER_CUPO = """
    UPDATE quota_counter
       SET count = count - 1,
           updated_at = :ahora
     WHERE counter_key = :clave
       AND count > 0
"""

# Las cuatro agregaciones del reporte. Las cuatro devuelven **el par**: lo
# medido y cuantas llamadas no se pudieron valorar (BR3.5). Publicar el total
# sin el conteo exige desarmar el tipo a proposito.
#
# `FILTER` en vez de `CASE WHEN`: dice lo que hace y no puede confundir un cero
# por falta de precio con un cero sumado.
#
# Las dos lineas del par se repiten enteras en las cuatro consultas en vez de
# componerse desde un fragmento. Es deliberado: una consulta armada con una
# cadena de Python es SQL construido por concatenacion, que es lo que BR1.6
# prohibe y lo que el linter marca. La alternativa seria silenciar el hallazgo
# con una supresion, y un hallazgo de seguridad no se silencia: se quita la
# forma que lo produce.

GASTO_POR_CASO = """
    SELECT COALESCE(SUM(cost_usd) FILTER (WHERE cost_status = 'measured'), 0) AS measured_usd,
           COUNT(*) FILTER (WHERE cost_status = 'not_measured') AS unmeasured_count
    FROM spend_entry
    WHERE case_ref = :caso
"""

#: Los casos que mas costaron, de mayor a menor. Existe porque "ver el costo por
#: caso" (AC5.14.1) con una sola consulta por identificador obliga a saber cual
#: preguntar, y quien mira el gasto para no gastar de mas no sabe todavia cual
#: mirar: lo que necesita es que la lista se lo diga.
#:
#: **Ordena por lo medido y desempata por el identificador**, para que dos
#: corridas sobre los mismos datos devuelvan siempre el mismo orden. Los casos sin
#: nada medido entran igual, con su conteo de no medidos: un caso que solo tiene
#: llamadas sin medir no cuesta cero, cuesta "no se sabe".
GASTO_POR_CASO_TOP = """
    SELECT case_ref,
           COALESCE(SUM(cost_usd) FILTER (WHERE cost_status = 'measured'), 0) AS measured_usd,
           COUNT(*) FILTER (WHERE cost_status = 'not_measured') AS unmeasured_count
    FROM spend_entry
    WHERE case_ref IS NOT NULL
    GROUP BY case_ref
    ORDER BY measured_usd DESC, case_ref ASC
    LIMIT :tope
"""

GASTO_POR_PROVEEDOR = """
    SELECT provider,
           COALESCE(SUM(cost_usd) FILTER (WHERE cost_status = 'measured'), 0) AS measured_usd,
           COUNT(*) FILTER (WHERE cost_status = 'not_measured') AS unmeasured_count
    FROM spend_entry
    GROUP BY provider
    ORDER BY provider
"""

#: Lo que costo cada modelo de cada proveedor (2026-10-10): el tablero dice con que
#: modelo se hace cada parte, y el identificador es el exacto que se cobro.
GASTO_POR_MODELO = """
    SELECT provider, model,
           COALESCE(SUM(cost_usd) FILTER (WHERE cost_status = 'measured'), 0) AS measured_usd,
           COUNT(*) FILTER (WHERE cost_status = 'not_measured') AS unmeasured_count
    FROM spend_entry
    GROUP BY provider, model
    ORDER BY provider, measured_usd DESC, model
"""

#: El mes se calcula en UTC **explicito** y no en la zona de la sesion: sin esa
#: conversion, la misma fila caeria en dos meses distintos segun la maquina que
#: corriera el reporte, y la cifra publicada dejaria de reproducirse desde el
#: mismo commit.
GASTO_POR_MES = """
    SELECT to_char(date_trunc('month', occurred_at AT TIME ZONE 'UTC'), 'YYYY-MM') AS month,
           COALESCE(SUM(cost_usd) FILTER (WHERE cost_status = 'measured'), 0) AS measured_usd,
           COUNT(*) FILTER (WHERE cost_status = 'not_measured') AS unmeasured_count
    FROM spend_entry
    GROUP BY month
    ORDER BY month
"""

#: Lo que costo cada actividad cada dia, en UTC por la misma razon que el mes.
#: **Lo que ocurrio dentro de una llamada es de la llamada** (2026-10-09), sea cual
#: sea su uso: el modelo que entiende lo que dijo la persona gasta con la clave
#: del chat, y sin esta regla el costo de una llamada apareceria repartido en el
#: del chat. Es la unica consulta que decide la actividad: los totales por
#: actividad salen de sumar estas filas, asi que no hay dos reglas que discrepen.
GASTO_POR_DIA_Y_ACTIVIDAD = """
    SELECT (occurred_at AT TIME ZONE 'UTC')::date AS day,
           CASE
             WHEN call_ref IS NOT NULL OR use = 'voice' THEN 'calls'
             WHEN use IN ('chat', 'chat_reply') THEN 'chat'
             WHEN use IN ('evals', 'evals_chat') THEN 'quality_tests'
             WHEN use = 'corpus' THEN 'policy_reading'
             ELSE 'operations'
           END AS activity,
           COALESCE(SUM(cost_usd) FILTER (WHERE cost_status = 'measured'), 0) AS measured_usd,
           COUNT(*) FILTER (WHERE cost_status = 'not_measured') AS unmeasured_count
    FROM spend_entry
    WHERE occurred_at >= :desde
    GROUP BY day, activity
    ORDER BY day, activity
"""

#: Los casos con gasto mas recientes, con lo que costo cada proveedor. Las
#: pruebas de calidad no entran: sus "casos" son de la corrida, no de nadie.
#:
#: Las tres ultimas columnas (2026-10-11) son los tokens de las llamadas **sin
#: precio**: lo que el proveedor conto aunque la tabla no tenga la linea de ese
#: modelo. `units > 0` separa "conto tokens" de "la llamada salio y no hay
#: recuento", que `record_spend` escribe con cero unidades. Las mismas tres
#: columnas, con la misma condicion, estan en las otras dos consultas de
#: `SIN_PRECIO_*`: una prueba comprueba que no discrepen.
CASOS_RECIENTES = """
    WITH recientes AS (
      SELECT case_ref, MAX(tenant_ref) AS tenant_ref, MAX(occurred_at) AS last_at
      FROM spend_entry
      WHERE case_ref IS NOT NULL AND tenant_ref IS NOT NULL
        AND use NOT IN ('evals', 'evals_chat')
      GROUP BY case_ref
      ORDER BY last_at DESC
      LIMIT :tope
    )
    SELECT r.case_ref, r.tenant_ref, r.last_at, e.provider,
           COALESCE(SUM(e.cost_usd) FILTER (WHERE e.cost_status = 'measured'), 0) AS measured_usd,
           COUNT(*) FILTER (WHERE e.cost_status = 'not_measured') AS unmeasured_count,
           COALESCE(SUM(e.units) FILTER (
               WHERE e.cost_status = 'not_measured'
                 AND e.unit_kind = ANY(:clases) AND e.units > 0), 0) AS unpriced_tokens,
           COUNT(*) FILTER (
               WHERE e.cost_status = 'not_measured'
                 AND NOT (e.unit_kind = ANY(:clases) AND e.units > 0)) AS unpriced_uncounted,
           COALESCE(BOOL_AND(NOT e.billable) FILTER (
               WHERE e.cost_status = 'not_measured'), FALSE) AS unpriced_free_plan
    FROM recientes r
    JOIN spend_entry e ON e.case_ref = r.case_ref
    WHERE e.use NOT IN ('evals', 'evals_chat')
    GROUP BY r.case_ref, r.tenant_ref, r.last_at, e.provider
    ORDER BY r.last_at DESC, e.provider
"""

#: Los tokens sin precio de cada proveedor, sobre todo el historial. Va aparte de
#: `GASTO_POR_PROVEEDOR` y no dentro para no cambiar la forma de una consulta que
#: consume tambien el reporte del operador: lo que aqui se agrega es solo para
#: mostrar.
SIN_PRECIO_POR_PROVEEDOR = """
    SELECT provider,
           COALESCE(SUM(units) FILTER (
               WHERE cost_status = 'not_measured'
                 AND unit_kind = ANY(:clases) AND units > 0), 0) AS unpriced_tokens,
           COUNT(*) FILTER (
               WHERE cost_status = 'not_measured'
                 AND NOT (unit_kind = ANY(:clases) AND units > 0)) AS unpriced_uncounted,
           COALESCE(BOOL_AND(NOT billable) FILTER (
               WHERE cost_status = 'not_measured'), FALSE) AS unpriced_free_plan
    FROM spend_entry
    GROUP BY provider
    ORDER BY provider
"""

#: Lo mismo por actividad, con **la misma regla de actividad** que
#: `GASTO_POR_DIA_Y_ACTIVIDAD` (el `CASE` es identico, y una prueba lo comprueba)
#: y desde la misma fecha, para que los tokens y los dolares de una actividad
#: hablen de las mismas filas.
SIN_PRECIO_POR_ACTIVIDAD = """
    SELECT CASE
             WHEN call_ref IS NOT NULL OR use = 'voice' THEN 'calls'
             WHEN use IN ('chat', 'chat_reply') THEN 'chat'
             WHEN use IN ('evals', 'evals_chat') THEN 'quality_tests'
             WHEN use = 'corpus' THEN 'policy_reading'
             ELSE 'operations'
           END AS activity,
           COALESCE(SUM(units) FILTER (
               WHERE cost_status = 'not_measured'
                 AND unit_kind = ANY(:clases) AND units > 0), 0) AS unpriced_tokens,
           COUNT(*) FILTER (
               WHERE cost_status = 'not_measured'
                 AND NOT (unit_kind = ANY(:clases) AND units > 0)) AS unpriced_uncounted,
           COALESCE(BOOL_AND(NOT billable) FILTER (
               WHERE cost_status = 'not_measured'), FALSE) AS unpriced_free_plan
    FROM spend_entry
    WHERE occurred_at >= :desde
    GROUP BY activity
    ORDER BY activity
"""

#: Lo que cuestan todas las llamadas y cuantas fueron. El promedio lo saca quien
#: lo muestra, y asi puede decir sobre cuantas se calculo.
GASTO_DE_LAS_LLAMADAS = """
    SELECT COUNT(DISTINCT call_ref) AS n,
           COALESCE(SUM(cost_usd) FILTER (WHERE cost_status = 'measured'), 0) AS measured_usd,
           COUNT(*) FILTER (WHERE cost_status = 'not_measured') AS unmeasured_count
    FROM spend_entry
    WHERE call_ref IS NOT NULL
"""

#: Lo mismo para las conversaciones de chat que abrieron caso.
GASTO_DE_LOS_CHATS = """
    SELECT COUNT(DISTINCT case_ref) AS n,
           COALESCE(SUM(cost_usd) FILTER (WHERE cost_status = 'measured'), 0) AS measured_usd,
           COUNT(*) FILTER (WHERE cost_status = 'not_measured') AS unmeasured_count
    FROM spend_entry
    WHERE call_ref IS NULL AND case_ref IS NOT NULL AND use IN ('chat', 'chat_reply')
"""

#: El acumulado de la ventana **recorriendo el historial**. No es el que decide
#: el corte --ese vive en la fila de la ventana y se incrementa en la misma
#: transaccion que escribe la fila (BR4.6)--: este existe para el reporte y para
#: poder conciliar los dos. Que discrepen es justo lo que hay que poder ver.
GASTO_DE_LA_VENTANA = """
    SELECT COALESCE(SUM(cost_usd) FILTER (WHERE cost_status = 'measured'), 0) AS measured_usd,
           COUNT(*) FILTER (WHERE cost_status = 'not_measured') AS unmeasured_count
    FROM spend_entry
    WHERE billable
      AND occurred_at >= :desde
      AND occurred_at < :hasta
"""


class BillableWrite(Frozen):
    """Lo que devuelve la transaccion facturable.

    Lleva la ventana **ya incrementada** y si fue *esta* llamada la que cruzo la
    alerta. Las dos cosas salen de la misma sentencia porque separarlas seria
    releer, y releer reabre la carrera que la sentencia cierra.
    """

    window: BudgetWindow
    #: Si le toca a esta llamada emitir la alerta. La marca **ya esta escrita**
    #: en la base cuando esto es cierto: quien reciba el valor emite el aviso,
    #: no lo decide (BR4.3).
    crossed_alert: bool


class AdjustmentWrite(Frozen):
    """Lo que devuelve la escritura de un ajuste.

    `written` es falso cuando el identificador ya estaba: es el reintento de un
    comando que ya se corrio, y no escribio nada. En ese caso no hay ventana que
    devolver. Tampoco la hay cuando el uso del ajuste no es facturable, porque esa
    fila no toca el acumulado (BR4.2).
    """

    written: bool
    window: BudgetWindow | None = None
    crossed_alert: bool = False


class WindowNotFoundError(LookupError):
    """Se registro un gasto facturable contra una ventana que no existe.

    Falla en el acto y nombra la fecha. Crear la fila al vuelo seria peor: una
    ventana inventada nace con el techo por defecto y sin la marca de alerta de
    la anterior, de modo que un error de configuracion se convertiria en
    presupuesto nuevo sin que nadie lo hubiera aprobado (BR4.1).
    """


@asynccontextmanager
async def _en_sesion_del_proyecto(
    dada: session.TenantSession | None = None,
) -> AsyncIterator[session.TenantSession]:
    """La sesion que me pasan, o una propia del proyecto si no me pasan ninguna.

    Sin aseguradora fijada porque estas cuatro tablas no tienen ninguna que fijar
    (BR7.1). Sigue saliendo del punto unico de U2: lo que cambia es que aqui no
    hay variable de sesion que poner, no que se abra una segunda via.

    Admitir una sesion de fuera existe por la misma razon que en U4: escribir la
    fila de gasto e incrementar el acumulado son **una sola cosa** (BR4.6), y
    con una sesion por operacion cada una confirmaria por separado.
    """
    if dada is not None:
        yield dada
    else:
        async with session.unscoped_session() as nueva:
            yield nueva


#: El tiempo maximo de una sentencia, fijado **dentro** de la transaccion.
#:
#: Se escribe con `set_config(..., true)` y no con `SET LOCAL statement_timeout =
#: <n>`, que es la forma que aparece en todas partes, por una razon concreta:
#: `SET LOCAL` no admite parametros ligados, asi que el numero habria que
#: interpolarlo en la cadena --SQL construido por concatenacion, que es lo que
#: BR1.6 prohibe y lo que el linter marca--. `set_config` si lo admite, y es
#: ademas la misma forma con la que el punto unico de sesion fija la
#: aseguradora. El `true` final la hace local a la transaccion: al cerrarla se va
#: con ella y no queda pegada a una conexion que despues reutilice otro.
FIJAR_TIEMPO_MAXIMO = "SELECT set_config('statement_timeout', :milisegundos, true)"


@asynccontextmanager
async def bounded_session(milliseconds: int) -> AsyncIterator[session.TenantSession]:
    """Una sesion del proyecto en la que **ninguna sentencia puede esperar mas**.

    Es lo que hace que el corte falle cerrado (NFR-U5-3, `reliability-design`):
    la lectura del presupuesto no se queda esperando a una base que no responde,
    porque esperar consumiria tambien el presupuesto de latencia del endpoint que
    la llamo. Falla, y quien la llama convierte ese fallo en el rechazo de la
    llamada facturable.

    Sigue saliendo del punto unico de sesion de U2: lo unico que anade es el
    limite, dentro de la misma transaccion.
    """
    async with session.unscoped_session() as sesion:
        await session.execute_sql(sesion, FIJAR_TIEMPO_MAXIMO, milisegundos=str(milliseconds))
        yield sesion


def _del_gasto(entry: SpendEntry) -> dict[str, Any]:
    """La fila, tal como va a la sentencia. Los enums salen por su valor."""
    return {
        "entry_id": entry.entry_id,
        "provider": entry.provider.value,
        "model": entry.model,
        "use": entry.use.value,
        "tenant_ref": entry.tenant_ref,
        "case_ref": entry.case_ref,
        "call_ref": entry.call_ref,
        "units": entry.units,
        "unit_kind": entry.unit_kind.value,
        "unit_price_usd": entry.unit_price_usd,
        "price_list_version": entry.price_list_version,
        "price_list_effective_date": entry.price_list_effective_date,
        "cost_usd": entry.cost_usd,
        "cost_status": entry.cost_status.value,
        "billable": entry.billable,
        "lane": entry.lane.value,
        "source": entry.source.value,
        "occurred_at": entry.occurred_at,
        "note": entry.note,
    }


def _a_ventana(fila: Any) -> BudgetWindow:
    return BudgetWindow(
        window_start=fila["window_start"],
        window_end=fila["window_end"],
        billable_spent_usd=fila["billable_spent_usd"],
        cap_usd=fila["cap_usd"],
        alert_usd=fila["alert_usd"],
        alert_sent_at=fila["alert_sent_at"],
        recording_reserve_usd=fila["recording_reserve_usd"],
        recording_reserve_status=CostStatus(fila["recording_reserve_status"]),
        recording_spent_usd=fila["recording_spent_usd"],
        unmeasured_billable_calls=int(fila["unmeasured_billable_calls"]),
        unmeasured_recording_calls=int(fila["unmeasured_recording_calls"]),
        updated_at=fila["updated_at"],
    )


def _a_contador(fila: Any) -> QuotaCounter:
    return QuotaCounter(
        counter_key=str(fila["counter_key"]),
        scope=QuotaScope(fila["scope"]),
        subject_key=str(fila["subject_key"]),
        period_start=fila["period_start"],
        count=int(fila["count"]),
        limit_at_period_start=int(fila["limit_at_period_start"]),
        updated_at=fila["updated_at"],
    )


def _a_total(fila: Any) -> SpendTotal:
    """El par que devuelve **toda** agregacion de esta unidad (BR3.5)."""
    return SpendTotal(
        measured_usd=fila["measured_usd"],
        unmeasured_count=int(fila["unmeasured_count"]),
    )


def _a_sin_precio(fila: Any) -> UnpricedUsage:
    """Los tokens de lo que no tiene precio, tal como los devuelven las tres consultas."""
    return UnpricedUsage(
        tokens=int(fila["unpriced_tokens"]),
        uncounted=int(fila["unpriced_uncounted"]),
        free_plan=bool(fila["unpriced_free_plan"]),
    )


#: Las clases de token como parametro, igual que `AUDIO_UNIT_KINDS` en la pregunta
#: del audio: la lista vive en un solo sitio y la cadena SQL no la repite.
def _clases_de_token() -> list[str]:
    return [clase.value for clase in sorted(TOKEN_UNIT_KINDS)]


# --- La escritura -------------------------------------------------------------


async def record_billable(
    entry: SpendEntry,
    *,
    now: datetime,
    window_start: date = WINDOW_START,
    en: session.TenantSession | None = None,
) -> BillableWrite:
    """Escribe la fila y incrementa el acumulado, en una sola transaccion.

    Las dos sentencias van juntas o no va ninguna (BR4.6). El instante entra por
    argumento y no se lee del reloj: el cruce de la alerta y el cambio de mes son
    conducta, y una conducta que lee el reloj del proceso solo se puede probar
    esperando a que pase el dia.

    El valor que vuelve trae la ventana **ya incrementada**, que es lo que
    permite decidir dentro de la transaccion si a esta llamada le toca emitir la
    alerta.
    """
    if not entry.billable:
        msg = (
            f"el gasto '{entry.entry_id}' no es facturable y no toca el acumulado: "
            "use `record_non_billable`. Solo las facturables suman contra el techo (BR4.2)"
        )
        raise ValueError(msg)

    medido = entry.cost_usd is not None
    de_grabacion = entry.lane is BudgetLane.RECORDING
    costo = entry.cost_usd if medido else _CERO
    no_medida = 0 if medido else 1
    # Las dos parejas se reparten igual --lo del carril es lo del total cuando la
    # llamada salio de el, y cero cuando no-- porque son la misma reparticion
    # vista sobre dos magnitudes: el dinero y el recuento de lo que no se pudo
    # valorar. Se reparte **aqui**, donde se sabe el carril, y no dentro de la
    # sentencia: una sentencia que lo adivinara repetiria esta decision en un
    # segundo sitio del que un dia discrepa.

    async with _en_sesion_del_proyecto(en) as sesion:
        await session.execute_sql(sesion, INSERTAR_GASTO, **_del_gasto(entry))
        fila = await session.fetch_one(
            sesion,
            INCREMENTAR_VENTANA,
            ventana=window_start,
            costo=costo,
            costo_de_grabacion=costo if de_grabacion else _CERO,
            no_medida=no_medida,
            no_medida_de_grabacion=no_medida if de_grabacion else 0,
            ahora=now,
        )
        if fila is None:
            msg = (
                f"no hay ninguna ventana de presupuesto que empiece el {window_start}: "
                "el gasto no se registra contra un acumulado inventado"
            )
            raise WindowNotFoundError(msg)

    return BillableWrite(window=_a_ventana(fila), crossed_alert=bool(fila["crossed_alert"]))


async def record_adjustment(
    entry: SpendEntry,
    *,
    now: datetime,
    window_start: date = WINDOW_START,
    en: session.TenantSession | None = None,
) -> AdjustmentWrite:
    """Escribe un asiento de ajuste conciliado, una sola vez por identificador.

    Es la misma superficie que escribe el resto del libro --la fila y el acumulado
    de la ventana, en una transaccion (BR4.6)-- con una diferencia: el identificador
    de un ajuste lo derivo quien lo anota, y reintentar el comando lo repite. Si la
    fila ya estaba, **no se vuelve a sumar** al acumulado: sumar dos veces el mismo
    ajuste cerraria el techo antes de tiempo, que es el error contrario al que el
    ajuste corrige.

    Un ajuste de un uso facturable cuenta contra el techo, igual que la llamada que
    no quedo anotada. Uno de un uso gratuito solo deja la fila.
    """
    if entry.source is not SpendSource.RECONCILED_ADJUSTMENT:
        msg = (
            f"el gasto '{entry.entry_id}' no es un ajuste conciliado: una llamada a un "
            "proveedor se escribe con `record_billable` o `record_non_billable`"
        )
        raise ValueError(msg)

    async with _en_sesion_del_proyecto(en) as sesion:
        tocadas = await session.execute_sql(sesion, INSERTAR_AJUSTE, **_del_gasto(entry))
        if tocadas == 0:
            return AdjustmentWrite(written=False)
        if not entry.billable:
            return AdjustmentWrite(written=True)
        fila = await session.fetch_one(
            sesion,
            INCREMENTAR_VENTANA,
            ventana=window_start,
            costo=entry.cost_usd,
            costo_de_grabacion=_CERO,
            no_medida=0,
            no_medida_de_grabacion=0,
            ahora=now,
        )
        if fila is None:
            msg = (
                f"no hay ninguna ventana de presupuesto que empiece el {window_start}: "
                "el ajuste no se registra contra un acumulado inventado"
            )
            raise WindowNotFoundError(msg)

    return AdjustmentWrite(
        written=True, window=_a_ventana(fila), crossed_alert=bool(fila["crossed_alert"])
    )


async def record_non_billable(
    entry: SpendEntry, *, en: session.TenantSession | None = None
) -> None:
    """Escribe la fila y **no toca el acumulado** (BR4.2).

    El chat y las evaluaciones en plan gratuito no facturan, asi que no compiten
    por la fila de la ventana ni pueden cruzar la alerta. Su fila se escribe
    igual: sin ella, el costo por caso quedaria por debajo del real y nadie lo
    notaria.
    """
    if entry.billable:
        msg = (
            f"el gasto '{entry.entry_id}' es facturable y tiene que incrementar el "
            "acumulado en la misma transaccion: use `record_billable` (BR4.6)"
        )
        raise ValueError(msg)

    async with _en_sesion_del_proyecto(en) as sesion:
        await session.execute_sql(sesion, INSERTAR_GASTO, **_del_gasto(entry))


# --- Las lecturas por clave ---------------------------------------------------


async def load_window(
    window_start: date, *, en: session.TenantSession | None = None
) -> BudgetWindow | None:
    """La ventana por su clave, o nada. Una lectura de fila unica, sin recorrer."""
    async with _en_sesion_del_proyecto(en) as sesion:
        fila = await session.fetch_one(sesion, LEER_VENTANA, ventana=window_start)
    return _a_ventana(fila) if fila is not None else None


async def load_counter(
    counter_key: CounterKey, *, en: session.TenantSession | None = None
) -> QuotaCounter | None:
    """El contador por su clave derivada, o nada si el periodo aun no se abrio."""
    async with _en_sesion_del_proyecto(en) as sesion:
        fila = await session.fetch_one(sesion, LEER_CONTADOR, clave=counter_key)
    return _a_contador(fila) if fila is not None else None


async def consume_quota(
    scope: QuotaScope,
    subject_key: SubjectKey,
    period: QuotaPeriod,
    *,
    now: datetime,
    en: session.TenantSession | None = None,
) -> QuotaCounter | None:
    """Consulta y consume en **un solo acto**, o devuelve nada si no cabia.

    Devolver nada no es un fallo: es la respuesta "no cabe", y quien llama la
    convierte en la decision con su motivo (BR5.3). Lanzar por una negacion la
    haria llegar a la pantalla como un error generico, que es lo que FR4.6
    prohibe.

    Consultar y despues incrementar en dos actos dejaria entre ellos un hueco por
    el que dos peticiones del mismo visitante pasarian las dos.

    La clave **se deriva aqui** de las tres partes y no se recibe hecha: si
    entrara por argumento junto a sus partes, nada impediria que dejaran de
    coincidir, y una clave que no corresponde a su periodo abre un contador
    nuevo cada vez (RT-13).
    """
    clave = derive_counter_key(scope, subject_key, period.period_start)
    async with _en_sesion_del_proyecto(en) as sesion:
        fila = await session.fetch_one(
            sesion,
            CONSUMIR_CUOTA,
            clave=clave,
            alcance=scope.value,
            sujeto=subject_key,
            periodo=period.period_start,
            limite=period.limit,
            ahora=now,
        )
    return _a_contador(fila) if fila is not None else None


async def release_call_quota(
    call_ref: CallRef,
    *,
    visitor_subject_key: SubjectKey,
    period_start: datetime,
    now: datetime,
    en: session.TenantSession | None = None,
) -> ReleaseOutcome:
    """Devuelve el cupo de una llamada que no gasto nada, **una sola vez** (BR5.5).

    Las tres sentencias van en una transaccion: preguntar al libro mayor, marcar
    el cierre y decrementar. Separarlas dejaria dos huecos, y los dos regalan
    cupo: entre la pregunta y la marca se colarian dos cierres simultaneos, y
    entre la marca y el decremento se perderia el cupo si la segunda fallara.

    **Se decrementan los dos contadores**, el del visitante y el del sitio. F4
    paso 3 nombra los dos y el `logic` de BR5.5 nombra solo el del visitante;
    manda el flujo, que es el mas especifico, y la discrepancia esta escrita en
    el informe de este cambio. La razon de fondo esta del lado de F4: los dos se
    consumieron al abrir (BR5.4, F3 paso 6), y devolver uno solo dejaria el cupo
    del sitio gastado por una llamada que no costo nada --que es exactamente el
    presupuesto del que BR5.6 reparte el dia siguiente--.

    El periodo entra por argumento y **no se deriva de `now`**: una llamada que
    empieza a las 23:58 y se cae a las 00:03 tiene que devolver el cupo al dia
    que se lo llevo, no al siguiente. Quien cierra la sesion sabe cuando se
    abrio; el reloj de este proceso no.
    """
    clases = [clase.value for clase in sorted(AUDIO_UNIT_KINDS)]

    async with _en_sesion_del_proyecto(en) as sesion:
        fila = await session.fetch_one(
            sesion, HAY_AUDIO_FACTURABLE, llamada=call_ref, clases=clases
        )
        if fila is None:  # pragma: no cover -- `EXISTS` siempre devuelve una fila
            # Hacia el lado de no devolver: entre equivocarse regalando cupo y
            # equivocarse sin devolverlo, lo segundo cuesta una llamada y lo
            # primero cuesta presupuesto.
            return ReleaseOutcome.BILLABLE_AUDIO
        hay_audio = bool(fila["hay_audio"])

        marca = await session.fetch_one(
            sesion, MARCAR_CIERRE, llamada=call_ref, devuelto=not hay_audio, ahora=now
        )
        if marca is None:
            return ReleaseOutcome.ALREADY_DECIDED
        if hay_audio:
            return ReleaseOutcome.BILLABLE_AUDIO

        del_visitante = derive_counter_key(
            QuotaScope.VOICE_CALLS_VISITOR_DAY, visitor_subject_key, period_start
        )
        del_sitio = derive_counter_key(QuotaScope.VOICE_CALLS_SITE_DAY, SITE_SUBJECT, period_start)
        await session.execute_sql(sesion, DEVOLVER_CUPO, clave=del_visitante, ahora=now)
        await session.execute_sql(sesion, DEVOLVER_CUPO, clave=del_sitio, ahora=now)

    return ReleaseOutcome.RETURNED


# --- Las cuatro agregaciones del reporte --------------------------------------


async def spend_by_case(case_ref: str, *, en: session.TenantSession | None = None) -> SpendTotal:
    """Lo que costo un caso, medido y sin medir (AC5.14.6).

    Un caso borrado por el reinicio nocturno deja sus filas con la columna en
    nulo, asi que su gasto ya no se atribuye a nadie y sigue contando en los
    totales: es lo que BR7.5 compra.
    """
    async with _en_sesion_del_proyecto(en) as sesion:
        fila = await session.fetch_one(sesion, GASTO_POR_CASO, caso=case_ref)
    if fila is None:  # pragma: no cover -- una agregacion siempre devuelve una fila
        return SpendTotal(measured_usd=_CERO, unmeasured_count=0)
    return _a_total(fila)


#: Cuantos casos devuelve la lista por omision. No es una pagina: es un techo, y
#: existe para que la consulta no crezca con la demostracion.
TOP_CASES_DEFAULT = 20


async def top_cases_by_spend(
    *, limit: int = TOP_CASES_DEFAULT, en: session.TenantSession | None = None
) -> tuple[tuple[str, SpendTotal], ...]:
    """Los casos que mas costaron, de mayor a menor (AC5.14.1).

    La consulta por identificador que ya existia --`spend_by_case`-- responde por
    uno; esta dice **cuales preguntar**. Sin ella, ver el gasto por caso obligaba a
    saber de antemano el identificador, y quien lo mira para no gastar de mas es
    justo quien no lo sabe.
    """
    async with _en_sesion_del_proyecto(en) as sesion:
        filas = await session.fetch_all(sesion, GASTO_POR_CASO_TOP, tope=limit)
    return tuple((str(fila["case_ref"]), _a_total(fila)) for fila in filas)


async def spend_by_provider(
    *, en: session.TenantSession | None = None
) -> tuple[tuple[ProviderName, SpendTotal], ...]:
    """Lo que costo cada proveedor. Ordenado, para que el reporte sea estable."""
    async with _en_sesion_del_proyecto(en) as sesion:
        filas = await session.fetch_all(sesion, GASTO_POR_PROVEEDOR)
    return tuple((ProviderName(fila["provider"]), _a_total(fila)) for fila in filas)


async def spend_by_model(
    *, en: session.TenantSession | None = None
) -> tuple[tuple[ProviderName, str, SpendTotal], ...]:
    """Lo que costo cada modelo, agrupado por proveedor y de mayor a menor."""
    async with _en_sesion_del_proyecto(en) as sesion:
        filas = await session.fetch_all(sesion, GASTO_POR_MODELO)
    return tuple(
        (ProviderName(fila["provider"]), str(fila["model"]), _a_total(fila)) for fila in filas
    )


async def spend_by_month(
    *, en: session.TenantSession | None = None
) -> tuple[tuple[str, SpendTotal], ...]:
    """Lo que costo cada mes, en UTC y con la clave `YYYY-MM`."""
    async with _en_sesion_del_proyecto(en) as sesion:
        filas = await session.fetch_all(sesion, GASTO_POR_MES)
    return tuple((str(fila["month"]), _a_total(fila)) for fila in filas)


class CaseProviderSpend(Frozen):
    """Lo que un proveedor cobro en un caso."""

    case_ref: str
    tenant_ref: str
    last_at: datetime
    provider: ProviderName
    total: SpendTotal
    #: Los tokens de sus llamadas sin precio. Aditivo: sin el, la fila dice lo que
    #: decia antes.
    unpriced: UnpricedUsage = Field(default_factory=UnpricedUsage)


class CountedSpend(Frozen):
    """Un total y sobre cuantas cosas se gasto: llamadas o conversaciones."""

    count: int
    total: SpendTotal


#: Cuantos dias muestra la grafica por dia.
DAYS_DEFAULT = 30
#: Cuantos casos recientes se piden. Algunos ya no existiran --los borra el
#: reinicio nocturno-- y se descartan despues, asi que se piden de sobra.
RECENT_CASES_DEFAULT = 60


async def spend_by_day_and_activity(
    since: date, *, en: session.TenantSession | None = None
) -> tuple[tuple[date, SpendActivity, SpendTotal], ...]:
    """Lo que costo cada actividad cada dia, desde `since` (UTC)."""
    async with _en_sesion_del_proyecto(en) as sesion:
        filas = await session.fetch_all(sesion, GASTO_POR_DIA_Y_ACTIVIDAD, desde=since)
    return tuple((fila["day"], SpendActivity(fila["activity"]), _a_total(fila)) for fila in filas)


async def recent_case_spend(
    *, limit: int = RECENT_CASES_DEFAULT, en: session.TenantSession | None = None
) -> tuple[CaseProviderSpend, ...]:
    """Los casos con gasto mas recientes, desglosados por proveedor."""
    async with _en_sesion_del_proyecto(en) as sesion:
        filas = await session.fetch_all(
            sesion, CASOS_RECIENTES, tope=limit, clases=_clases_de_token()
        )
    return tuple(
        CaseProviderSpend(
            case_ref=str(fila["case_ref"]),
            tenant_ref=str(fila["tenant_ref"]),
            last_at=fila["last_at"],
            provider=ProviderName(fila["provider"]),
            total=_a_total(fila),
            unpriced=_a_sin_precio(fila),
        )
        for fila in filas
    )


async def unpriced_by_provider(
    *, en: session.TenantSession | None = None
) -> dict[ProviderName, UnpricedUsage]:
    """Los tokens sin precio de cada proveedor. Solo los que tienen algo que decir."""
    async with _en_sesion_del_proyecto(en) as sesion:
        filas = await session.fetch_all(sesion, SIN_PRECIO_POR_PROVEEDOR, clases=_clases_de_token())
    return {ProviderName(fila["provider"]): _a_sin_precio(fila) for fila in filas}


async def unpriced_by_activity(
    since: date, *, en: session.TenantSession | None = None
) -> dict[SpendActivity, UnpricedUsage]:
    """Los tokens sin precio de cada actividad, desde `since` (UTC)."""
    async with _en_sesion_del_proyecto(en) as sesion:
        filas = await session.fetch_all(
            sesion, SIN_PRECIO_POR_ACTIVIDAD, clases=_clases_de_token(), desde=since
        )
    return {SpendActivity(fila["activity"]): _a_sin_precio(fila) for fila in filas}


async def spend_per_call(*, en: session.TenantSession | None = None) -> CountedSpend:
    """Lo que costaron todas las llamadas, y cuantas fueron."""
    async with _en_sesion_del_proyecto(en) as sesion:
        fila = await session.fetch_one(sesion, GASTO_DE_LAS_LLAMADAS)
    return _contado(fila)


async def spend_per_chat(*, en: session.TenantSession | None = None) -> CountedSpend:
    """Lo que costaron las conversaciones de chat con caso, y cuantas fueron."""
    async with _en_sesion_del_proyecto(en) as sesion:
        fila = await session.fetch_one(sesion, GASTO_DE_LOS_CHATS)
    return _contado(fila)


def _contado(fila: Any) -> CountedSpend:
    if fila is None:  # pragma: no cover -- una agregacion siempre devuelve una fila
        return CountedSpend(count=0, total=SpendTotal(measured_usd=_CERO, unmeasured_count=0))
    return CountedSpend(count=int(fila["n"]), total=_a_total(fila))


async def window_spend(
    window_start: date, window_end: date, *, en: session.TenantSession | None = None
) -> SpendTotal:
    """El acumulado facturable de la ventana, recorriendo el historial.

    **No** es el numero que decide el corte: ese vive en la fila de la ventana y
    lo incrementa la misma transaccion que escribe cada fila (BR4.6). Este
    existe para el reporte y para poder conciliar los dos, porque que discrepen
    es justo lo que hay que poder ver.
    """
    async with _en_sesion_del_proyecto(en) as sesion:
        fila = await session.fetch_one(
            sesion, GASTO_DE_LA_VENTANA, desde=window_start, hasta=window_end
        )
    if fila is None:  # pragma: no cover -- una agregacion siempre devuelve una fila
        return SpendTotal(measured_usd=_CERO, unmeasured_count=0)
    return _a_total(fila)
