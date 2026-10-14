"""La superficie de la contabilidad y su purgador, contra la base de verdad.

Son de integracion porque lo que se comprueba aqui son conductas **del motor**
que un doble no tiene: que la fila y el acumulado entren en la misma
transaccion, que una escritura diferida ocurra fuera del camino de la respuesta,
y que un borrado se lleve unas filas y no otras.

**Ninguna prueba gasta un centavo.** El acumulado se fuerza en la fila de la
ventana; nunca se llega al techo gastando de verdad (BR5.9, regla del proyecto).

**La base caida se simula apuntando el punto unico de sesion a un puerto donde
no hay nadie**, no doblando el repositorio. Lo que se quiere comprobar es que el
fallo cae hacia donde tiene que caer, y con un doble estariamos comprobando el
doble.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from untangle.base import ProviderName, UnitKind, Use
from untangle.telemetry.spend import api as spend
from untangle.telemetry.spend import pricing, repository
from untangle.telemetry.spend import purge as spend_purge
from untangle.telemetry.spend.models import (
    SITE_SUBJECT,
    WINDOW_START,
    BudgetLane,
    BudgetStatus,
    CallUsage,
    Money,
    PricedUnits,
    PriceEntry,
    QuotaPeriod,
    QuotaReason,
    QuotaScope,
    SpendTotal,
    VoiceMode,
    derive_counter_key,
)
from untangle.tenancy import ephemeral, session

from .conftest import AHORA, sembrar_ventana

MODELO = "gemini-3.1-flash-lite"
PRECIO = Decimal("0.00000025")

#: Lo que `providers.yaml` aparta para grabar el video de la semana doce, ya
#: convertido a dolares: quince llamadas de tres minutos a la meta de D7.
RESERVA_DE_GRABACION = Decimal("0.225")

#: Un precio por segundo de audio **inventado para la prueba**, y esa es la
#: diferencia con el resto del archivo. La tabla de `_runtime` no lo declara a
#: proposito, porque hoy el proyecto no lo tiene; pero sin el, la reserva por
#: llamada sale no medida y los dos carriles responden lo mismo --respaldo--
#: por una razon que no es la que se quiere probar.
PRECIO_SEGUNDO = Decimal("0.001")

#: Una base a la que nadie contesta. El puerto 1 no tiene servicio y la conexion
#: se rechaza en el acto, asi que la prueba no espera: lo que se comprueba es
#: hacia donde cae el fallo, no cuanto tarda.
BASE_CAIDA = "postgresql+psycopg://nadie:nadie@127.0.0.1:1/ninguna"

CONTAR_GASTOS = "SELECT count(*) AS total FROM spend_entry"
CONTAR_CONTADORES = "SELECT count(*) AS total FROM quota_counter"


def _sin_consumo(clase: UnitKind) -> PricedUnits:
    """Un componente que esta fixture no consume. Cero unidades, cero costo."""
    return PricedUnits(
        provider=ProviderName.GEMINI, model=MODELO, unit_kind=clase, units=Decimal(0)
    )


def _runtime(**cambios: object) -> spend.SpendRuntime:
    """La configuracion de la contabilidad, con lo que cada prueba cambie.

    La tabla de precios trae **solo** los tokens de entrada: es lo que hace que
    una llamada de segundos de audio salga no medida, que es el caso que el
    proyecto tiene hoy de verdad porque el precio del minuto de voz no esta
    publicado.
    """
    base: dict[str, object] = {
        "prices": pricing.PriceTable.from_entries(
            [
                PriceEntry(
                    provider=ProviderName.GEMINI,
                    model=MODELO,
                    unit_kind=UnitKind.INPUT_TOKENS,
                    unit_price_usd=PRECIO,
                    list_version="1",
                    effective_date=AHORA.date(),
                )
            ]
        ),
        "plans": {
            Use.VOICE: spend.UsePlan(provider=ProviderName.GEMINI, model=MODELO, billable=True),
            Use.CHAT: spend.UsePlan(provider=ProviderName.GEMINI, model=MODELO, billable=False),
            Use.EVALS: spend.UsePlan(provider=ProviderName.GEMINI, model=MODELO, billable=False),
            Use.OPERATIONS: spend.UsePlan(
                provider=ProviderName.GEMINI, model=MODELO, billable=False
            ),
        },
        "zone": ZoneInfo("America/Bogota"),
        "chat_messages_per_session": 30,
        "chat_messages_per_day": 60,
        "voice_calls_per_visitor_per_day": 1,
        "site_daily_cap": 15,
        "max_call_seconds": 180,
        # El consumo por llamada de esta fixture: **solo la transcripcion**, para
        # que la reserva siga siendo los segundos de audio por su precio, que es lo
        # que estas pruebas comparan. Los otros dos componentes van en cero, y un
        # consumo en cero no necesita precio.
        "call_usage": CallUsage(
            transcription=PricedUnits(
                provider=ProviderName.GEMINI,
                model=MODELO,
                unit_kind=UnitKind.AUDIO_SECONDS,
                units=Decimal(180),
            ),
            synthesis_primary=_sin_consumo(UnitKind.CHARACTERS),
            synthesis_fallback=_sin_consumo(UnitKind.CHARACTERS),
            model_input=_sin_consumo(UnitKind.INPUT_TOKENS),
            model_output=_sin_consumo(UnitKind.OUTPUT_TOKENS),
        ),
        "recording_minutes": 45,
    }
    return spend.SpendRuntime(**{**base, **cambios})  # type: ignore[arg-type]


def _con_precio_de_voz() -> spend.SpendRuntime:
    """La misma configuracion, pero con el segundo de audio **si** en la tabla.

    Con `max_call_seconds = 180` la reserva por llamada sale medida y vale
    0,180 USD, que es lo que `reserve_primary_voice` compara contra el restante.
    """
    return _runtime(
        prices=pricing.PriceTable.from_entries(
            [
                PriceEntry(
                    provider=ProviderName.GEMINI,
                    model=MODELO,
                    unit_kind=UnitKind.INPUT_TOKENS,
                    unit_price_usd=PRECIO,
                    list_version="1",
                    effective_date=AHORA.date(),
                ),
                PriceEntry(
                    provider=ProviderName.GEMINI,
                    model=MODELO,
                    unit_kind=UnitKind.AUDIO_SECONDS,
                    unit_price_usd=PRECIO_SEGUNDO,
                    list_version="1",
                    effective_date=AHORA.date(),
                ),
            ]
        )
    )


@pytest.fixture(autouse=True)
def contabilidad(dinero: None) -> Iterator[None]:
    """Instala la contabilidad y la desinstala al salir.

    Antes y despues, y no solo despues: una prueba que dejara su configuracion
    puesta le cambiaria el techo a la siguiente, y la suite dejaria de poder
    correr en cualquier orden.
    """
    spend.reset()
    spend.install(_runtime())
    yield
    spend.reset()


async def _total_de_filas() -> int:
    async with session.unscoped_session() as sesion:
        fila = await session.fetch_one(sesion, CONTAR_GASTOS)
    return int(fila["total"]) if fila is not None else 0


async def test_lo_facturable_se_escribe_sincrono_con_su_acumulado(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """La fila y el acumulado son **una sola cosa** (BR4.6).

    Cuando `record_spend` vuelve, las dos estan escritas: no hay un momento en
    el que la fila exista y el techo no la conozca, que es el hueco por el que
    dos llamadas simultaneas se pasarian del techo.
    """
    await sembrar_ventana()

    await spend.record_spend(
        provider=ProviderName.GEMINI,
        model=MODELO,
        use=Use.VOICE,
        units=Decimal(200000),
        unit_kind=UnitKind.INPUT_TOKENS,
        case_id=None,
        now=AHORA,
    )

    assert await _total_de_filas() == 1
    ventana = await repository.load_window(WINDOW_START)
    assert ventana is not None
    assert ventana.billable_spent_usd == Decimal(200000) * PRECIO


async def test_lo_no_facturable_no_esta_en_el_camino_de_la_respuesta(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """PERF-U5.4: el chat en plan gratuito no espera a que su fila se escriba.

    Se comprueba la propiedad entera, que son dos mitades: al volver de
    `record_spend` la fila **todavia no esta**, y despues de drenar la cola
    **si**. Comprobar solo la segunda dejaria pasar una escritura sincrona
    disfrazada.
    """
    await sembrar_ventana()
    # La cola se abre **sin** su tarea de fondo: lo que se comprueba es que la
    # fila no este escrita al volver, y con la tarea corriendo eso dependeria de
    # cuando el planificador le diera el turno. Que la escritura sea diferida y
    # quien la drena son dos cosas distintas, y esta prueba mira la primera.
    spend.open_deferred_queue()
    try:
        await spend.record_spend(
            provider=ProviderName.GEMINI,
            model=MODELO,
            use=Use.CHAT,
            units=Decimal(1000),
            unit_kind=UnitKind.INPUT_TOKENS,
            case_id=None,
            now=AHORA,
        )

        assert await _total_de_filas() == 0
        assert spend.pending_deferred() == 1

        assert await spend.flush_deferred() == 1
        assert await _total_de_filas() == 1
    finally:
        await spend.stop_deferred_writer()

    # El acumulado no se toca: solo las facturables suman contra el techo
    # (BR4.2). Sin esto, el chat gratuito se comeria el presupuesto de la voz sin
    # que nadie hubiera pagado nada.
    ventana = await repository.load_window(WINDOW_START)
    assert ventana is not None
    assert ventana.billable_spent_usd == Decimal(0)


async def test_la_cola_llena_escribe_sincrono_en_vez_de_descartar(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Se paga latencia justo cuando la base va lenta; a cambio no se pierde
    ninguna fila. Una cifra de costo a la que le faltan llamadas no es una
    medicion, y el costo por caso es una de las cinco que el proyecto publica.

    La cola se llena **de verdad**: se abre y se encolan tres filas mas de las
    que caben. Las tres que no caben se escriben sincronas, y al final no falta
    ninguna.
    """
    await sembrar_ventana()
    # Sin tarea de fondo, para que la cola **llegue** a llenarse: con la tarea
    # corriendo, que se llene o no dependeria de una carrera, y lo que se
    # comprueba aqui es el borde, no quien gana.
    spend.open_deferred_queue()
    try:
        cuantas = spend.DEFERRED_QUEUE_CAPACITY + 3
        for _ in range(cuantas):
            await spend.record_spend(
                provider=ProviderName.GEMINI,
                model=MODELO,
                use=Use.EVALS,
                units=Decimal(10),
                unit_kind=UnitKind.INPUT_TOKENS,
                case_id=None,
                now=AHORA,
            )
        assert spend.pending_deferred() == spend.DEFERRED_QUEUE_CAPACITY
        await spend.flush_deferred()
    finally:
        await spend.stop_deferred_writer()

    # Ni una menos: las tres que no cupieron se escribieron sincronas.
    assert await _total_de_filas() == cuantas
    assert spend.deferred_failures() == 0


async def test_con_la_base_caida_lo_facturable_se_rechaza_y_el_chat_sigue(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """NFR-U5-3: cerrado donde hay dinero, abierto donde no lo hay.

    Las dos mitades en la misma prueba porque son **una sola decision**: la
    llamada de voz se rechaza con el motivo de presupuesto, y el chat responde.
    Un limite que falla abierto cuando lo que falla es la aplicacion no es un
    limite; y apagar el chat gratuito no protege nada, porque no cuesta dinero.
    """
    await sembrar_ventana()
    await session.dispose()
    session.configure(BASE_CAIDA)
    try:
        voz = await spend.check_quota(QuotaScope.VOICE_CALLS_VISITOR_DAY, "visitante-1", now=AHORA)
        chat = await spend.check_quota(
            QuotaScope.CHAT_MESSAGES_SESSION,
            "visitante-1",
            now=AHORA,
            period_start=AHORA,
        )
        modo = await spend.reserve_primary_voice("llamada-1", now=AHORA)

        # Y el turno del chat no se rompe: su fila no esta en el camino de la
        # respuesta, asi que un fallo de escritura no llega a quien llamo.
        await spend.record_spend(
            provider=ProviderName.GEMINI,
            model=MODELO,
            use=Use.CHAT,
            units=Decimal(10),
            unit_kind=UnitKind.INPUT_TOKENS,
            case_id=None,
            now=AHORA,
        )
    finally:
        await session.dispose()
        session.configure(sesiones.app_url)

    assert voz.allowed is False
    assert voz.reason_code is QuotaReason.BUDGET_EXHAUSTED
    #: Sin cuando, a proposito: el acumulado solo sube, asi que decirle a quien
    #: llama que reintente en unos segundos seria mentirle (BR4.4).
    assert voz.retry_after_seconds is None
    assert chat.allowed is True
    assert modo is VoiceMode.FALLBACK
    #: La fila no se perdio en silencio: se cuenta y se publica.
    assert spend.deferred_failures() == 1


async def test_el_techo_alcanzado_corta_la_voz_y_deja_el_chat_vivo(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """AC5.14.3, con el acumulado **forzado** y no gastado (BR5.9).

    Es la otra mitad de la asimetria, y esta vez sin ninguna caida: la base
    contesta, el techo esta alcanzado, y aun asi el chat sigue porque no consume
    el techo.
    """
    await sembrar_ventana(gastado=Decimal("5.00"), reserva=Decimal("0.00"))

    estado = await spend.budget_state(now=AHORA)
    voz = await spend.check_quota(QuotaScope.VOICE_CALLS_VISITOR_DAY, "visitante-1", now=AHORA)
    chat = await spend.check_quota(QuotaScope.CHAT_MESSAGES_DAY, "visitante-1", now=AHORA)

    assert estado.status is BudgetStatus.EXHAUSTED
    assert voz.allowed is False
    assert voz.reason_code is QuotaReason.BUDGET_EXHAUSTED
    assert chat.allowed is True


async def test_una_llamada_facturable_sin_valorar_cierra_la_voz_y_deja_el_chat_vivo(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """La tercera forma de cerrar el carril de pago, y la que mas cuesta ver.

    Una llamada facturable que no se pudo valorar suma **cero** al acumulado:
    la fila existe y dice "no medido", pero el numero con el que el techo decide
    se queda corto por lo que esa llamada costo de verdad. Con el subconteo, los
    5 USD y la alerta de los 3 USD se pueden cruzar sin que el estado deje de
    decir `ok`, y eso es gasto que nadie escribio como excepcion.

    Se cierra por el mismo camino que la reserva ilegible --el restante publico
    pasa a "no medido" y el estado a `unmeasured`-- y con la misma asimetria de
    siempre: el chat en plan gratuito no consulta el presupuesto y sigue
    atendiendo, porque sus llamadas no cuestan dinero (NFR-U5-3, BR4.4).

    El caso esta vivo hoy: `gemini-embedding-001` ya no tiene precio de lista.
    """
    await sembrar_ventana(gastado=Decimal("0.10"), reserva=RESERVA_DE_GRABACION, sin_valorar=1)

    estado = await spend.budget_state(now=AHORA)
    voz = await spend.check_quota(QuotaScope.VOICE_CALLS_VISITOR_DAY, "visitante-1", now=AHORA)
    chat = await spend.check_quota(QuotaScope.CHAT_MESSAGES_DAY, "visitante-1", now=AHORA)

    assert estado.status is BudgetStatus.UNMEASURED
    assert estado.public_remaining_usd == Money.not_measured()
    #: Y lo dice entero: el acumulado medido viaja con cuantas no se midieron,
    #: asi que la pantalla puede explicar por que el restante no tiene numero.
    assert estado.spent == SpendTotal(measured_usd=Decimal("0.10"), unmeasured_count=1)
    #: El carril de grabacion conserva su numero, y desde el conteo por carril
    #: eso ya no es una concesion sino una lectura: la llamada sin valorar salio
    #: del enlace publico, asi que la reserva del video sigue entera.
    assert estado.recording_spent.unmeasured_count == 0
    assert estado.recording_remaining_usd == Money.measured(RESERVA_DE_GRABACION)

    assert voz.allowed is False
    assert voz.reason_code is QuotaReason.BUDGET_EXHAUSTED
    assert chat.allowed is True


async def test_una_llamada_de_grabacion_sin_valorar_cierra_su_carril_y_no_el_publico(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """El corte por lo no valorado, aplicado al carril que no lo tenia.

    Es el mismo argumento que cerro el carril publico el 2026-09-21, visto desde
    su mitad simetrica: una llamada de grabacion sin precio de lista suma cero a
    lo gastado de su carril, asi que ese restante sale inflado y nada lo dice.
    Con el conteo propio, la voz de grabacion cae al respaldo --cerrado para lo
    que cuesta dinero-- en vez de seguir abriendo llamadas contra un numero que
    no es.

    Y el enlace publico **no** se cierra por esto mas de lo que ya se cerraba:
    su reserva sigue apartada y su propio restante no depende del carril ajeno.

    El caso esta vivo hoy: la tabla de precios no publica el precio por minuto
    de la voz, que es justo lo que una grabacion consume.
    """
    await sembrar_ventana(
        gastado=Decimal("0.10"),
        reserva=RESERVA_DE_GRABACION,
        gastado_en_grabacion=Decimal("0.10"),
        sin_valorar=1,
        sin_valorar_en_grabacion=1,
    )
    spend.install(_con_precio_de_voz())

    estado = await spend.budget_state(now=AHORA)
    grabacion = await spend.reserve_primary_voice(
        "llamada-grabada", lane=BudgetLane.RECORDING, now=AHORA
    )

    assert estado.recording_remaining_usd == Money.not_measured()
    assert grabacion is VoiceMode.FALLBACK
    #: Y la foto dice **cual** de las dos causas fue, sin volver a la base: la
    #: reserva tiene numero, asi que lo que falta es el otro sumando.
    assert estado.recording_reserve_usd == Money.measured(RESERVA_DE_GRABACION)
    assert estado.recording_spent == SpendTotal(measured_usd=Decimal("0.10"), unmeasured_count=1)


async def test_la_grabacion_abre_con_voz_principal_aunque_el_publico_este_agotado(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR4.10 y BR5.7 en la frontera entre los dos carriles, que es donde se
    decide **cual de los dos restantes** lee la voz.

    Esta es la mitad que protege la grabacion del video de la semana doce: la
    reserva existe para que un dia de trafico en el enlace publico no se la
    lleve, y si la decision de la voz leyera el restante publico, el enlace
    publico agotado apagaria la voz principal de una grabacion cuya reserva
    esta intacta. O sea: la reserva estaria apartada en el numero y gastada en
    la conducta.
    """
    await sembrar_ventana(gastado=Decimal("4.775"), reserva=RESERVA_DE_GRABACION)
    spend.install(_con_precio_de_voz())

    estado = await spend.budget_state(now=AHORA)
    publico = await spend.reserve_primary_voice("llamada-publica", now=AHORA)
    grabacion = await spend.reserve_primary_voice(
        "llamada-grabada", lane=BudgetLane.RECORDING, now=AHORA
    )

    #: El publico agotado y la reserva entera: `exhausted` con reserva
    #: disponible es un estado normal y esperado (BR4.10).
    assert estado.status is BudgetStatus.EXHAUSTED
    assert publico is VoiceMode.FALLBACK
    assert grabacion is VoiceMode.PRIMARY


async def test_la_grabacion_cae_al_respaldo_con_su_reserva_gastada_y_el_publico_con_saldo(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """La mitad simetrica, y la que protege el techo del proyecto.

    Con la reserva de grabacion gastada, una llamada de ese carril **no** puede
    reclamar voz principal contra el dinero del enlace publico: los dos carriles
    corren aparte en las dos direcciones (BR4.9), no solo en la que conviene.
    Leer el restante publico aqui convertiria la reserva en un piso y no en un
    tope, y la grabacion seguiria gastando despues de haberse acabado lo suyo.
    """
    await sembrar_ventana(
        gastado=RESERVA_DE_GRABACION,
        reserva=RESERVA_DE_GRABACION,
        gastado_en_grabacion=RESERVA_DE_GRABACION,
    )
    spend.install(_con_precio_de_voz())

    estado = await spend.budget_state(now=AHORA)
    publico = await spend.reserve_primary_voice("llamada-publica", now=AHORA)
    grabacion = await spend.reserve_primary_voice(
        "llamada-grabada", lane=BudgetLane.RECORDING, now=AHORA
    )

    assert estado.status is BudgetStatus.OK
    assert publico is VoiceMode.PRIMARY
    assert grabacion is VoiceMode.FALLBACK


async def test_el_cupo_del_sitio_se_deriva_y_queda_escrito_en_su_contador(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR5.6 y FD-U5-10. El cupo del sitio no es un numero fijo: se deriva del
    presupuesto publico que queda y los dias que faltan. Y **se escribe** en el
    contador del dia, para que un rechazo se pueda explicar meses despues con el
    numero que de verdad regia entonces.

    Con la reserva por llamada **no medida** --la tabla de precios no publica el
    segundo de voz-- el cupo es cero: no se puede dividir entre lo que no se
    sabe, y suponerlo barato vaciaria el presupuesto el primer dia.
    """
    await sembrar_ventana(reserva=Decimal("0.00"))

    decision = await spend.check_quota(QuotaScope.VOICE_CALLS_SITE_DAY, SITE_SUBJECT, now=AHORA)

    assert decision.allowed is False
    assert decision.reason_code is QuotaReason.RATE_LIMITED_SITE

    #: **Con cupo cero el dia no se abre**: no hay nada que consumir, y escribir
    #: un contador con `count = 1` sobre un limite de cero seria una fila que se
    #: lee como si todo estuviera bien. Lo que explica el rechazo entonces no es
    #: el contador sino la ventana, que si conserva sus numeros (AC5.14.4).
    medianoche = datetime(2026, 9, 21, 0, 0, tzinfo=ZoneInfo("America/Bogota"))
    clave = derive_counter_key(QuotaScope.VOICE_CALLS_SITE_DAY, SITE_SUBJECT, medianoche)
    assert await repository.load_counter(clave) is None


async def test_el_purgador_borra_lo_del_visitante_y_no_la_ventana_ni_el_sitio(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR7.6 y AC5.14.4, que es la prueba que mas importa de este archivo.

    Lo que se conserva pesa mas que lo que se borra: el contador del sitio
    reparte el presupuesto entre los dias que faltan, y la ventana es la unica
    cifra del proyecto que un criterio exige que sobreviva a todo, incluido el
    reinicio y el cambio de mes.
    """
    await sembrar_ventana(gastado=Decimal("1.50"))
    ayer = AHORA - timedelta(days=1)

    for alcance, sujeto in (
        (QuotaScope.CHAT_MESSAGES_SESSION, "sesion-1"),
        (QuotaScope.CHAT_MESSAGES_DAY, "visitante-1"),
        (QuotaScope.VOICE_CALLS_VISITOR_DAY, "visitante-1"),
        (QuotaScope.VOICE_CALLS_SITE_DAY, SITE_SUBJECT),
    ):
        await repository.consume_quota(
            alcance, sujeto, QuotaPeriod(period_start=ayer, limit=10), now=ayer
        )

    # Una fila de gasto que el reinicio **no** se lleva (C-11: aparece en `kept`).
    await spend.record_spend(
        provider=ProviderName.GEMINI,
        model=MODELO,
        use=Use.VOICE,
        units=Decimal(1000),
        unit_kind=UnitKind.INPUT_TOKENS,
        case_id=None,
        now=ayer,
    )

    resultado = await spend_purge.SPEND_PURGER.purge(older_than=AHORA)

    assert resultado.deleted == 3
    #: El contador del sitio y la fila de gasto, los dos conservados a proposito.
    assert resultado.kept == 2

    async with session.unscoped_session() as sesion:
        fila = await session.fetch_one(sesion, CONTAR_CONTADORES)
    assert fila is not None
    assert int(fila["total"]) == 1

    ventana = await repository.load_window(WINDOW_START)
    assert ventana is not None
    assert ventana.billable_spent_usd == Decimal("1.50") + Decimal(1000) * PRECIO
    assert await _total_de_filas() == 1


async def test_una_llamada_que_no_reporto_unidades_deja_su_fila_no_medida(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR3.1 y BR3.3. Una llamada que salio y no volvio **pudo haber
    consumido**: su fila existe y su costo es "no medido", nunca cero.

    Cero se sumaria como cierto y dejaria el costo por caso por debajo del real,
    que es el fallo silencioso que esta unidad existe para impedir. Y el
    acumulado no sube, pero **el conteo de no medidas si**: publicar el total sin
    decir cuanto no se midio exige desarmar el tipo a proposito (BR3.5).
    """
    await sembrar_ventana()

    await spend.record_spend(
        provider=ProviderName.GEMINI,
        model=MODELO,
        use=Use.VOICE,
        units=None,
        unit_kind=UnitKind.INPUT_TOKENS,
        case_id=None,
        now=AHORA,
    )

    ventana = await repository.load_window(WINDOW_START)
    assert ventana is not None
    assert ventana.billable_spent_usd == Decimal(0)
    assert ventana.unmeasured_billable_calls == 1

    total = await repository.window_spend(ventana.window_start, ventana.window_end)
    assert total.measured_usd == Decimal(0)
    assert total.unmeasured_count == 1


async def test_la_alerta_se_emite_una_sola_vez_aunque_se_siga_gastando(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """AC5.14.2. Una alerta por llamada convierte el aviso en ruido y deja de
    leerse, que es la forma silenciosa de quedarse sin alerta.

    Se comprueba sobre el evento emitido y no sobre la marca de la base: la
    marca ya la comprueban las pruebas del repositorio, y lo que esta unidad
    promete hacia fuera es **el aviso**.
    """
    await sembrar_ventana(gastado=Decimal("2.99"), reserva=Decimal("0.00"))
    emitidos: list[str] = []

    async def gastar() -> None:
        await spend.record_spend(
            provider=ProviderName.GEMINI,
            model=MODELO,
            use=Use.VOICE,
            units=Decimal(200000),
            unit_kind=UnitKind.INPUT_TOKENS,
            case_id=None,
            now=AHORA,
        )

    from untangle import observability

    original = observability.emit

    def espiar(event: str, **campos: object) -> None:
        emitidos.append(event)
        original(event, **campos)

    observability.emit = espiar
    try:
        for _ in range(3):
            await gastar()
    finally:
        observability.emit = original

    assert emitidos.count("spend.budget_alert_crossed") == 1


async def test_dos_llamadas_a_la_vez_no_pasan_las_dos_del_techo(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR4.6 visto desde la superficie, no desde el repositorio.

    Lo que se comprueba es que la superficie **no reintroduce** la carrera que la
    sentencia cierra: no lee antes de escribir, asi que dos llamadas simultaneas
    suman las dos y el acumulado final es exacto. Con una lectura previa, una de
    las dos se perderia.
    """
    await sembrar_ventana()

    async def gastar() -> None:
        await spend.record_spend(
            provider=ProviderName.GEMINI,
            model=MODELO,
            use=Use.VOICE,
            units=Decimal(100000),
            unit_kind=UnitKind.INPUT_TOKENS,
            case_id=None,
            now=AHORA,
        )

    await asyncio.gather(gastar(), gastar())

    ventana = await repository.load_window(WINDOW_START)
    assert ventana is not None
    assert ventana.billable_spent_usd == Decimal(200000) * PRECIO
    assert await _total_de_filas() == 2


async def test_el_reporte_de_gasto_publica_el_total_y_lo_no_medido_juntos(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR3.5. `mise run spend:report` es el productor del valor real de NFR14.1,
    y lo que se comprueba aqui es que **no pueda publicar el total a secas**: las
    dos cifras salen a la misma linea, asi que ignorar el conteo de no medidas
    exige recortar la linea a proposito.

    No es una compuerta y no entra en el guion (INF-U5-4): una compuerta sobre
    una cifra que todavia no tiene linea base no compara nada.
    """
    from untangle.workspace import spend_report

    await sembrar_ventana(gastado=Decimal("1.00"))
    await spend.record_spend(
        provider=ProviderName.GEMINI,
        model=MODELO,
        use=Use.VOICE,
        units=None,
        unit_kind=UnitKind.INPUT_TOKENS,
        case_id=None,
        now=AHORA,
    )

    lineas = await spend_report.render()
    texto = "\n".join(lineas)

    assert "acumulado facturable" in texto
    assert "1 sin medir" in texto
    assert "gemini" in texto
    #: El divisor de AC5.14.6 no se inventa aqui: lo pone U21, que es quien
    #: conoce el resultado de las compuertas.
    assert "U21" in texto
