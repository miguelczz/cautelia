"""El libro mayor contra la base: la transaccion, la carrera y lo que sobrevive.

Lo que se prueba aqui son conductas **del motor** --que dos escrituras se
serialicen sobre la misma fila, que un fallo de la segunda sentencia se lleve la
primera, que un borrado deje la columna en nulo en vez de llevarse la fila-- y
un doble no las tiene. Una suite de transacciones contra un simulador comprueba
el simulador.

**Ninguna prueba gasta un centavo.** El acumulado se fuerza en la fila de la
ventana; nunca se llega al techo gastando de verdad (BR5.9).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
import sqlalchemy.exc

from untangle.base import ProviderName, SpendSource, UnitKind, Use
from untangle.case_record import purge as case_purge
from untangle.telemetry.spend import budget, repository
from untangle.telemetry.spend.models import (
    SITE_SUBJECT,
    WINDOW_START,
    BudgetLane,
    CostStatus,
    Money,
    QuotaPeriod,
    QuotaScope,
    SpendEntry,
    SpendTotal,
    derive_counter_key,
)
from untangle.tenancy import ephemeral, session

from .conftest import AHORA, VENTANA_FIN, sembrar_ventana

PRECIO = Decimal("0.00000025")

CREAR_CASO = """
    INSERT INTO case_record (case_id, tenant_id, case_number, record_type,
                             state, channel, origin, language, created_at, updated_at)
    VALUES (:case_id, 'stonecroft', :numero, 'claim', 'capturing', 'chat',
            'public_chat', 'es', :creado, :creado)
"""


def _gasto(
    entry_id: str,
    *,
    costo: Decimal | None = Decimal("0.05"),
    billable: bool = True,
    case_ref: str | None = None,
    occurred_at: datetime = AHORA,
) -> SpendEntry:
    """Una fila de gasto. Con `costo=None` es una llamada que no se pudo valorar.

    Las cuatro columnas de precio van juntas o no va ninguna, y cual de las dos
    lo dice `cost_status` (BR3.4): el helper lo impone para que ninguna prueba
    pueda escribir una fila a medias por descuido.

    El carril no es argumento: sale siempre publico y la unica prueba que usa el
    de grabacion lo cambia con `evolve`, que **vuelve a validar**. Asi el carril
    se lee en la prueba que lo necesita en vez de en la firma de un ayudante que
    las demas leen sin usarlo.
    """
    medido = costo is not None
    return SpendEntry(
        entry_id=entry_id,
        provider=ProviderName.GEMINI,
        model="gemini-3.1-flash-lite",
        use=Use.VOICE,
        tenant_ref="stonecroft",
        case_ref=case_ref,
        units=Decimal(200000),
        unit_kind=UnitKind.INPUT_TOKENS,
        unit_price_usd=PRECIO if medido else None,
        price_list_version="1" if medido else None,
        price_list_effective_date=datetime(2026, 9, 21).date() if medido else None,
        cost_usd=costo,
        cost_status=CostStatus.MEASURED if medido else CostStatus.NOT_MEASURED,
        billable=billable,
        lane=BudgetLane.PUBLIC,
        source=SpendSource.PROVIDER_REPORTED,
        occurred_at=occurred_at,
    )


async def _contar_gastos() -> int:
    async with session.unscoped_session() as sesion:
        fila = await session.fetch_one(sesion, "SELECT count(*) AS total FROM spend_entry")
    return int(fila["total"]) if fila is not None else 0


# --- La carrera que la transaccion cierra -------------------------------------


async def test_dos_escrituras_simultaneas_no_pasan_el_techo_las_dos(
    dinero: None,
) -> None:
    """BR4.6. La que pierde la carrera encuentra el acumulado **ya incrementado**.

    Es la razon de que la sentencia devuelva el acumulado nuevo en vez de
    releerlo: con una relectura, las dos verian el mismo numero de partida y las
    dos creerian que todavia cabia su llamada. Aqui una ve 4,00 y la otra 5,00, y
    la segunda sabe que el techo quedo alcanzado.
    """
    await sembrar_ventana(gastado=Decimal("3.00"))
    grande = Decimal("1.00")

    primera, segunda = await asyncio.gather(
        repository.record_billable(_gasto("G-1", costo=grande), now=AHORA),
        repository.record_billable(_gasto("G-2", costo=grande), now=AHORA),
    )

    vistos = sorted([primera.window.billable_spent_usd, segunda.window.billable_spent_usd])
    # Ninguna de las dos vio el mismo numero: la segunda leyo lo que dejo la
    # primera. Con una lectura previa, las dos habrian visto 3,00.
    assert vistos == [Decimal("4.00"), Decimal("5.00")]

    final = await repository.load_window(WINDOW_START)
    assert final is not None
    assert final.billable_spent_usd == Decimal("5.00")
    assert await _contar_gastos() == 2


async def test_la_alerta_se_emite_exactamente_una_vez_en_veinte_incrementos(
    dinero: None,
) -> None:
    """AC5.14.2 y BR4.3, contra la base y no contra la aritmetica pura.

    Veinte llamadas seguidas atraviesan el umbral por el medio. Lo que se prueba
    no es que la alerta salga: es que salga **una**. Una alerta por llamada
    convierte el aviso en ruido y se deja de leer, que es la forma silenciosa de
    quedarse sin alerta justo cuando hacia falta.
    """
    await sembrar_ventana(gastado=Decimal("2.80"))
    incremento = Decimal("0.05")

    cruces = 0
    for numero in range(20):
        escrito = await repository.record_billable(
            _gasto(f"G-{numero}", costo=incremento), now=AHORA
        )
        if escrito.crossed_alert:
            cruces += 1

    assert cruces == 1

    final = await repository.load_window(WINDOW_START)
    assert final is not None
    assert final.billable_spent_usd == Decimal("3.80")
    # La marca quedo escrita dentro de la misma transaccion que la detecto: si
    # se escribiera fuera, dos llamadas que cruzaran a la vez emitirian dos.
    assert final.alert_sent_at == AHORA


async def test_con_la_marca_ya_escrita_no_se_vuelve_a_avisar_ni_se_pisa_la_fecha(
    dinero: None,
) -> None:
    """Que la marca exista es lo unico que impide la segunda alerta (BR4.3).

    Se prueba aparte del recorrido de veinte porque alli queda tapada: despues
    del cruce el acumulado ya esta por encima del umbral, asi que la condicion
    del umbral sola basta para que no se repita. Esta es la que ejerce **la
    marca**: una ventana avisada cuyo acumulado sigue por debajo del umbral
    --porque alguien corrigio la fila o subio la alerta-- y a la que le entra un
    gasto que lo cruza. Sin mirar la marca, ahi saldria un segundo aviso y la
    fecha del primero se perderia.
    """
    primera_vez = AHORA - timedelta(days=1)
    await sembrar_ventana(gastado=Decimal("2.99"), avisada=primera_vez)

    escrito = await repository.record_billable(_gasto("G-OTRA", costo=Decimal("1.00")), now=AHORA)

    assert not escrito.crossed_alert
    assert escrito.window.alert_sent_at == primera_vez


# --- Lo que revierte y lo que sobrevive ---------------------------------------


async def test_la_fila_repetida_no_deja_el_acumulado_movido(
    dinero: None,
) -> None:
    """La mitad "ni acumulado sin fila" de BR4.6, con un fallo real de la base.

    El caso no es rebuscado: quien reintenta una escritura que parecio fallar
    manda el mismo identificador de fila, y la clave primaria del libro mayor lo
    rechaza. Lo que esta prueba fija es que ese rechazo **no deje el acumulado
    movido**: si la segunda llamada incrementara la ventana antes de chocar, el
    techo cortaria antes de tiempo por un gasto que solo existio una vez.

    La otra mitad --"ni fila sin acumulado"-- la cubre la prueba de la ventana
    que no existe, justo abajo. Hasta el 2026-09-21 la cubria tambien una llamada
    de grabacion contra una reserva agotada; esa ya no falla, y no fallar es
    precisamente lo que se arreglo (BR3.1 sobre BR4.5).
    """
    await sembrar_ventana(gastado=Decimal("1.00"))
    await repository.record_billable(_gasto("G-REPETIDA", costo=Decimal("0.10")), now=AHORA)

    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await repository.record_billable(_gasto("G-REPETIDA", costo=Decimal("0.10")), now=AHORA)

    assert await _contar_gastos() == 1
    intacta = await repository.load_window(WINDOW_START)
    assert intacta is not None
    assert intacta.billable_spent_usd == Decimal("1.10")


async def test_una_llamada_de_grabacion_deja_su_fila_con_la_reserva_agotada(
    dinero: None,
) -> None:
    """BR3.1 sobre BR4.5, comprobado contra la base y no contra el modelo.

    El techo se consulta **antes** de llamar al proveedor y el costo se registra
    **despues**, asi que la ultima llamada de un carril puede costar mas de lo
    que quedaba. Hasta el 2026-09-21 la restriccion
    `budget_window_grabacion_dentro_de_su_reserva` hacia levantar esa escritura,
    y con ella se iba la fila de gasto de una llamada que **ya se habia pagado**:
    una cifra publicada bajaba sin que nada lo dijera.

    Las dos mitades, porque la restriccion tenia dos: con la reserva agotada y
    con la reserva sin medir. La segunda es la que mas cuesta ver y la que mas se
    va a dar --la tabla de precios no publica el precio por minuto de la voz--.
    """
    await sembrar_ventana(
        gastado=Decimal("0.10"), reserva=Decimal("0.10"), gastado_en_grabacion=Decimal("0.10")
    )

    escrito = await repository.record_billable(
        _gasto("G-EXCESO", costo=Decimal("0.05")).evolve(lane=BudgetLane.RECORDING), now=AHORA
    )

    assert await _contar_gastos() == 1
    assert escrito.window.recording_spent_usd == Decimal("0.15")
    assert escrito.window.billable_spent_usd == Decimal("0.15")
    #: Y el restante no miente por eso: llega a cero y se queda ahi.
    assert budget.recording_remaining(escrito.window) == Money.measured(Decimal(0))


async def test_una_llamada_de_grabacion_deja_su_fila_con_la_reserva_sin_medir(
    dinero: None,
) -> None:
    """La mitad simetrica de la anterior, y la que mas se va a dar.

    La reserva se declara en minutos y se convierte con la tabla de precios, que
    hoy no publica el precio por minuto de la voz: la conversion queda **no
    medida**, y con la restriccion puesta ninguna llamada de grabacion podia
    registrar su gasto. El restante sigue diciendo la verdad --"no se pudo
    calcular"-- y nunca cero.
    """
    await sembrar_ventana(gastado=Decimal("1.00"), reserva=None)

    escrito = await repository.record_billable(
        _gasto("G-GRABACION", costo=Decimal("0.10")).evolve(lane=BudgetLane.RECORDING), now=AHORA
    )

    assert await _contar_gastos() == 1
    assert escrito.window.recording_spent_usd == Decimal("0.10")
    assert budget.recording_remaining(escrito.window) == Money.not_measured()


async def test_una_llamada_de_grabacion_sin_valorar_sube_el_conteo_de_su_carril(
    dinero: None,
) -> None:
    """El conteo se reparte por carril en la misma transaccion que el dinero.

    Sin esta mitad, la fila sabe **cuantas** llamadas no se valoraron pero no de
    que carril salieron, y el corte por lo no valorado solo puede aplicarse al
    carril publico: una llamada de grabacion sin valorar inflaria el restante de
    su carril sin que nada lo dijera.

    Las dos direcciones en la misma prueba porque lo que se afirma es el
    **reparto**: la de grabacion sube los dos conteos y la publica sube solo el
    total. Con una sola de las dos, una sentencia que subiera siempre los dos
    pasaria igual.
    """
    await sembrar_ventana()

    de_grabacion = await repository.record_billable(
        _gasto("G-SIN-PRECIO-GRABACION", costo=None).evolve(lane=BudgetLane.RECORDING), now=AHORA
    )

    assert de_grabacion.window.unmeasured_billable_calls == 1
    assert de_grabacion.window.unmeasured_recording_calls == 1
    assert budget.recording_remaining(de_grabacion.window) == Money.not_measured()

    publica = await repository.record_billable(
        _gasto("G-SIN-PRECIO-PUBLICA", costo=None), now=AHORA
    )

    assert publica.window.unmeasured_billable_calls == 2
    assert publica.window.unmeasured_recording_calls == 1


async def test_sin_ventana_no_se_escribe_la_fila_contra_un_acumulado_inventado(
    dinero: None,
) -> None:
    """La otra mitad del mismo rollback, y la unica que nombra la fecha.

    Crear la ventana al vuelo seria peor que fallar: nacera con el techo por
    defecto y sin la marca de alerta de la anterior, de modo que un error de
    configuracion se convertiria en presupuesto nuevo que nadie aprobo.
    """
    with pytest.raises(repository.WindowNotFoundError) as error:
        await repository.record_billable(_gasto("G-SIN-VENTANA"), now=AHORA)

    assert str(WINDOW_START) in str(error.value)
    assert await _contar_gastos() == 0


async def test_borrar_el_caso_deja_la_columna_en_nulo_y_la_fila_viva_con_su_costo(
    dinero: None,
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR7.5 y AC5.14.4. El caso se **nombra**, no se cuelga.

    Con borrado en cascada, el reinicio nocturno vaciaria cada noche el registro
    de lo que el proyecto ya pago, y el costo por caso publicado seria el de los
    casos de hoy en vez del historico.
    """
    await sembrar_ventana()
    async with session.session_for("stonecroft") as sesion:
        await session.execute_sql(
            sesion, CREAR_CASO, case_id="CASO-GASTO", numero="SA-901", creado=AHORA
        )
    await repository.record_billable(
        _gasto("G-DEL-CASO", costo=Decimal("0.02"), case_ref="CASO-GASTO"), now=AHORA
    )
    assert await repository.spend_by_case("CASO-GASTO") == SpendTotal(
        measured_usd=Decimal("0.02"), unmeasured_count=0
    )

    async with session.session_for("stonecroft") as sesion:
        await session.execute_sql(sesion, "DELETE FROM case_record WHERE case_id = 'CASO-GASTO'")

    async with session.unscoped_session() as sesion:
        fila = await session.fetch_one(
            sesion,
            "SELECT case_ref, cost_usd, cost_status FROM spend_entry WHERE entry_id = :id",
            id="G-DEL-CASO",
        )

    assert fila is not None, "la fila de gasto se fue con el caso: el borrado es en cascada"
    assert fila["case_ref"] is None
    assert fila["cost_usd"] == Decimal("0.02")
    assert fila["cost_status"] == "measured"


async def test_la_ventana_sobrevive_al_purgador_y_al_cambio_de_mes(
    dinero: None,
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """AC5.14.4 y BR4.7. El acumulado no se reinicia por nada de lo dos.

    El reloj entra por argumento: con el del proceso, esta prueba solo se podria
    escribir esperando a que cambiara el mes. La ventana es **acumulada de
    noventa dias**, asi que un gasto de octubre suma al mismo numero que uno de
    septiembre, y el reporte por mes los separa sin que el techo se entere.
    """
    await sembrar_ventana()
    octubre = AHORA + timedelta(days=20)

    await repository.record_billable(_gasto("G-SEP", costo=Decimal("0.10")), now=AHORA)
    await repository.record_billable(
        _gasto("G-OCT", costo=Decimal("0.20"), occurred_at=octubre), now=octubre
    )

    await case_purge.CASE_RECORD_PURGER.purge(older_than=octubre + timedelta(days=1))

    ventana = await repository.load_window(WINDOW_START)
    assert ventana is not None
    assert ventana.billable_spent_usd == Decimal("0.30")

    por_mes = await repository.spend_by_month()
    assert [mes for mes, _ in por_mes] == ["2026-09", "2026-10"]
    assert dict(por_mes)["2026-10"] == SpendTotal(measured_usd=Decimal("0.20"), unmeasured_count=0)


# --- Las cuotas y el reporte --------------------------------------------------


async def test_la_cuota_se_consulta_y_se_consume_en_un_solo_acto(
    dinero: None,
) -> None:
    """BR5.1 y RT-13. Entre consultar y consumir no queda hueco.

    Dos peticiones simultaneas del mismo visitante con cupo para una: pasa una y
    solo una. Con una consulta y despues un incremento, las dos leerian cero y
    las dos pasarian, que es el escenario del que salio esta forma.
    """
    periodo = QuotaPeriod(period_start=AHORA, limit=1)

    primera, segunda = await asyncio.gather(
        repository.consume_quota(
            QuotaScope.VOICE_CALLS_VISITOR_DAY, "resumen-1", periodo, now=AHORA
        ),
        repository.consume_quota(
            QuotaScope.VOICE_CALLS_VISITOR_DAY, "resumen-1", periodo, now=AHORA
        ),
    )

    pasaron = [r for r in (primera, segunda) if r is not None]
    assert len(pasaron) == 1
    assert pasaron[0].count == 1
    assert pasaron[0].limit_at_period_start == 1

    # Y la tercera tampoco, porque el limite quedo escrito con el que rigio al
    # abrirse el periodo: un rechazo se puede explicar meses despues.
    tercera = await repository.consume_quota(
        QuotaScope.VOICE_CALLS_VISITOR_DAY, "resumen-1", periodo, now=AHORA
    )
    assert tercera is None


async def test_un_cupo_de_cero_no_deja_pasar_ni_la_primera(
    dinero: None,
) -> None:
    """El caso que la condicion del `ON CONFLICT` no cubria, y que muerde.

    Cero no es un limite raro: es **exactamente** lo que devuelve el cupo del
    sitio cuando el presupuesto publico se agota (BR5.6), o sea el corte del
    enlace publico expresado como cupo. La condicion que impide pasarse solo
    gobierna la fila que ya existe; la primera peticion de un periodo va por el
    inserto, que no miraba el limite y por tanto **pasaba siempre**.

    El sintoma habria sido una llamada de voz al dia con el presupuesto agotado,
    y habria sido invisible: el contador quedaba escrito con `count = 1` sobre un
    limite de cero, que es una fila que se lee como si todo estuviera bien.

    Con cupo cero el periodo **no se abre**: no hay contador que escribir, y eso
    tambien se comprueba, porque escribirlo seria dejar la mentira en la base.
    """
    periodo = QuotaPeriod(period_start=AHORA, limit=0)

    primera = await repository.consume_quota(
        QuotaScope.VOICE_CALLS_SITE_DAY, SITE_SUBJECT, periodo, now=AHORA
    )

    assert primera is None

    clave = derive_counter_key(QuotaScope.VOICE_CALLS_SITE_DAY, SITE_SUBJECT, AHORA)
    assert await repository.load_counter(clave) is None


async def test_el_contador_se_lee_por_su_clave_derivada_y_dentro_de_una_sesion_dada(
    dinero: None,
) -> None:
    """La lectura por clave del camino de disponibilidad, sin recorrer nada.

    La clave **se deriva** de alcance, sujeto y periodo, y esa derivacion es lo
    que hace que dos contadores del mismo sujeto en el mismo periodo sean uno
    solo. Se comprueba aqui que la misma derivacion que escribe es la que lee:
    si divergieran, cada llamada abriria un contador nuevo y el cupo no limitaria
    nada.

    Se lee ademas **dentro de una sesion que llega de fuera**, que es como la
    usara la superficie cuando componga varias operaciones en una transaccion.
    Un contador que no existe responde nada, no cero: el periodo aun no se abrio.
    """
    periodo = QuotaPeriod(period_start=AHORA, limit=3)
    clave = derive_counter_key(QuotaScope.CHAT_MESSAGES_DAY, "resumen-2", AHORA)

    assert await repository.load_counter(clave) is None

    await repository.consume_quota(QuotaScope.CHAT_MESSAGES_DAY, "resumen-2", periodo, now=AHORA)

    async with session.unscoped_session() as sesion:
        leido = await repository.load_counter(clave, en=sesion)

    assert leido is not None
    assert leido.counter_key == clave
    assert leido.count == 1
    assert leido.subject_key == "resumen-2"


async def test_las_cuatro_agregaciones_devuelven_el_par_medido_y_sin_medir(
    dinero: None,
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR3.5. Ninguna de las cuatro deja publicar el total sin decir que falta.

    Lo no medido **no entra como cero**: se cuenta aparte. Si entrara como cero,
    el total bajaria y el conteo desapareceria, dos errores que se tapan el uno
    al otro y dejan una cifra publicada que ya no describe lo que dice describir.
    """
    await sembrar_ventana()
    async with session.session_for("stonecroft") as sesion:
        await session.execute_sql(
            sesion, CREAR_CASO, case_id="CASO-MIXTO", numero="SA-902", creado=AHORA
        )

    await repository.record_billable(
        _gasto("G-A", costo=Decimal("0.03"), case_ref="CASO-MIXTO"), now=AHORA
    )
    await repository.record_billable(_gasto("G-B", costo=None, case_ref="CASO-MIXTO"), now=AHORA)
    await repository.record_non_billable(
        _gasto("G-C", costo=Decimal("0.01"), billable=False, case_ref="CASO-MIXTO")
    )

    esperado = SpendTotal(measured_usd=Decimal("0.04"), unmeasured_count=1)
    assert await repository.spend_by_case("CASO-MIXTO") == esperado
    assert dict(await repository.spend_by_provider())[ProviderName.GEMINI] == esperado
    assert dict(await repository.spend_by_month())["2026-09"] == esperado

    # El acumulado del reporte cuenta **solo** lo facturable, igual que el techo:
    # la fila no facturable esta en los tres de arriba y no en este.
    assert await repository.window_spend(WINDOW_START, VENTANA_FIN) == SpendTotal(
        measured_usd=Decimal("0.03"), unmeasured_count=1
    )


async def test_lo_no_facturable_se_escribe_y_no_toca_el_acumulado(
    dinero: None,
) -> None:
    """BR4.2. El chat en plan gratuito no se come el presupuesto de la voz.

    Su fila se escribe igual: sin ella, el costo por caso quedaria por debajo del
    real y nadie lo notaria. Y el par de metodos no es una comodidad: llamar al
    equivocado falla en el acto en vez de dejar el acumulado torcido en silencio.
    """
    await sembrar_ventana(gastado=Decimal("1.00"))

    await repository.record_non_billable(_gasto("G-GRATIS", billable=False))

    ventana = await repository.load_window(WINDOW_START)
    assert ventana is not None
    assert ventana.billable_spent_usd == Decimal("1.00")
    assert await _contar_gastos() == 1

    with pytest.raises(ValueError, match="no es facturable"):
        await repository.record_billable(_gasto("G-X", billable=False), now=AHORA)
    with pytest.raises(ValueError, match="es facturable"):
        await repository.record_non_billable(_gasto("G-Y", billable=True))


async def test_una_llamada_sin_precio_cuenta_aparte_y_no_suma_cero(
    dinero: None,
) -> None:
    """BR3.3 y BR3.5, en la misma transaccion que escribe la fila.

    El acumulado no se mueve --no hay cantidad que sumar-- y el conteo de no
    medidas sube. Sumarla como cero haria que el techo cortara mas tarde de lo
    que debia, sin que nada fallara ni avisara.
    """
    await sembrar_ventana(gastado=Decimal("1.00"))

    escrito = await repository.record_billable(_gasto("G-SIN-PRECIO", costo=None), now=AHORA)

    assert escrito.window.billable_spent_usd == Decimal("1.00")
    assert escrito.window.unmeasured_billable_calls == 1
    assert not escrito.crossed_alert


async def test_el_libro_mayor_acepta_todos_los_usos_del_enum(dinero: None) -> None:
    """Ningun `Use` puede quedarse fuera de la restriccion de la tabla.

    Sale de la primera ingesta real de U8, el 2026-09-27. La tanda que anadio el
    uso `corpus` --el de los embeddings, con su propia clave-- no toco
    `spend_entry_uso_valido`, que enumeraba los cuatro usos que existian
    entonces, asi que **cada llamada de embeddings fallaba al anotarse**.

    Nadie se entero, y ese es el punto: `_escribir_diferida` traga la excepcion
    a proposito, porque una fila del libro mayor que falla no puede tumbar el
    turno que la genero. Lo correcto para el turno era exactamente lo que
    escondia el fallo, y el costo por caso salia por debajo del real.

    Esta prueba recorre el enum entero en vez de nombrar `corpus`: un sexto uso
    sin su migracion falla aqui, y no en la salida de un comando seis semanas
    despues.
    """
    await sembrar_ventana()
    async with session.session_for("stonecroft") as sesion:
        await session.execute_sql(
            sesion, CREAR_CASO, case_id="CASO-USOS", numero="SA-931", creado=AHORA
        )

    for uso in Use:
        entrada = _gasto(
            f"G-USO-{uso.value}", costo=None, billable=False, case_ref="CASO-USOS"
        ).evolve(use=uso)
        await repository.record_non_billable(entrada)

    # Si la restriccion dejara fuera un uso, la escritura de arriba habria
    # levantado `IntegrityError` y la prueba no llegaria aqui. Esto comprueba
    # ademas que las filas cuentan: un uso que se escribe y no se lee seria el
    # mismo agujero con otra forma.
    total = await repository.spend_by_case("CASO-USOS")
    assert total.unmeasured_count == len(Use)
