"""La otra mitad de la cuota de voz: devolver el cupo que no se gasto (BR5.5).

El cupo del dia se consume al **abrir** (BR5.4), porque contar al terminar
dejaria pasar diez pestanas a la vez (RT-13). Sin devolucion, una caida de red
antes del primer turno le quita el dia entero al visitante, que es la violacion
que la regla nombra.

Son de integracion y no unitarias porque lo que se comprueba son conductas **del
motor**: que la marca de cierre y los decrementos entren en la misma
transaccion, que la clave primaria de esa marca haga idempotente el segundo
cierre, y que la guarda `count > 0` impida un contador negativo. Con un doble
estariamos comprobando el doble.

**Ninguna prueba gasta un centavo.** El acumulado y la reserva se siembran en la
fila de la ventana; el audio que hace que un cupo no se devuelva se escribe como
fila del libro mayor, no llamando a un proveedor (BR5.9, regla del proyecto).
"""

from __future__ import annotations

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
    BudgetLane,
    CallUsage,
    PricedUnits,
    PriceEntry,
    QuotaScope,
    ReleaseOutcome,
    derive_counter_key,
)
from untangle.tenancy import ephemeral, rls_assertion, session

from .conftest import AHORA, sembrar_ventana

MODELO = "gemini-3.1-flash-lite"
VOZ = "cartesia-sonic-2"

#: El precio por segundo de audio. Sembrado, no real: el del minuto de voz lo
#: fija el experimento 1 y hoy no esta publicado. Lo que la prueba necesita de el
#: es que exista, para que la reserva por llamada quede **medida** y el cupo del
#: sitio salga mayor que cero; con la reserva sin medir el cupo es cero y no
#: habria nada que devolver.
PRECIO_DEL_SEGUNDO = Decimal("0.00008")

ZONA = ZoneInfo("America/Bogota")

VISITANTE = "a3f1c9d2e5b7"
LLAMADA = "CALL-1"

CONTAR_CIERRES = "SELECT count(*) AS total FROM voice_call_release"

#: Una base a la que nadie contesta. El puerto 1 no tiene servicio y la conexion
#: se rechaza en el acto, asi que la prueba no espera: lo que se comprueba es
#: hacia donde cae el fallo, no cuanto tarda.
BASE_CAIDA = "postgresql+psycopg://nadie:nadie@127.0.0.1:1/ninguna"


def _sin_consumo(clase: UnitKind) -> PricedUnits:
    """Un componente que esta fixture no consume. Cero unidades, cero costo."""
    return PricedUnits(
        provider=ProviderName.GEMINI, model=MODELO, unit_kind=clase, units=Decimal(0)
    )


def _runtime(**cambios: object) -> spend.SpendRuntime:
    """La contabilidad de estas pruebas, con el segundo de audio con precio."""
    base: dict[str, object] = {
        "prices": pricing.PriceTable.from_entries(
            [
                PriceEntry(
                    provider=ProviderName.CARTESIA,
                    model=VOZ,
                    unit_kind=UnitKind.AUDIO_SECONDS,
                    unit_price_usd=PRECIO_DEL_SEGUNDO,
                    list_version="1",
                    effective_date=AHORA.date(),
                )
            ]
        ),
        "plans": {
            Use.VOICE: spend.UsePlan(provider=ProviderName.CARTESIA, model=VOZ, billable=True),
            Use.CHAT: spend.UsePlan(provider=ProviderName.GEMINI, model=MODELO, billable=False),
            Use.EVALS: spend.UsePlan(provider=ProviderName.GEMINI, model=MODELO, billable=False),
            Use.OPERATIONS: spend.UsePlan(
                provider=ProviderName.GEMINI, model=MODELO, billable=False
            ),
        },
        "zone": ZONA,
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
            # El proveedor y el modelo son los que **esta tabla valora**
            # (`cartesia / VOZ`): el consumo tiene que apuntar a una linea que
            # exista, o la reserva sale sin medir y el cupo del dia sale cero.
            transcription=PricedUnits(
                provider=ProviderName.CARTESIA,
                model=VOZ,
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


@pytest.fixture(autouse=True)
def contabilidad(dinero: None) -> Iterator[None]:
    """Instala la contabilidad y la desinstala al salir.

    Antes y despues: una prueba que dejara su configuracion puesta le cambiaria
    los limites a la siguiente, y la suite dejaria de poder correr en cualquier
    orden.
    """
    spend.reset()
    spend.install(_runtime())
    yield
    spend.reset()


def _clave_del_visitante(periodo: datetime, subject_key: str = VISITANTE) -> str:
    return derive_counter_key(QuotaScope.VOICE_CALLS_VISITOR_DAY, subject_key, periodo)


def _clave_del_sitio(periodo: datetime) -> str:
    return derive_counter_key(QuotaScope.VOICE_CALLS_SITE_DAY, SITE_SUBJECT, periodo)


async def _conteo(clave: str) -> int | None:
    """Cuanto lleva ese contador, o nada si su periodo no llego a abrirse."""
    contador = await repository.load_counter(clave)
    return None if contador is None else contador.count


async def _abrir_llamada(*, cuando: datetime = AHORA, subject_key: str = VISITANTE) -> None:
    """Lo que hace F3 al crear la sesion: consumir los dos contadores (BR5.4)."""
    del_visitante = await spend.check_quota(
        QuotaScope.VOICE_CALLS_VISITOR_DAY, subject_key, now=cuando
    )
    del_sitio = await spend.check_quota(QuotaScope.VOICE_CALLS_SITE_DAY, SITE_SUBJECT, now=cuando)
    assert del_visitante.allowed, del_visitante.reason_code
    assert del_sitio.allowed, del_sitio.reason_code


async def _audio_de(llamada: str, segundos: Decimal, *, cuando: datetime = AHORA) -> None:
    """Una fila de audio del libro mayor, sin llamar a ningun proveedor."""
    await spend.record_spend(
        provider=ProviderName.CARTESIA,
        model=VOZ,
        use=Use.VOICE,
        units=segundos,
        unit_kind=UnitKind.AUDIO_SECONDS,
        call_ref=llamada,
        now=cuando,
    )


# --- El camino feliz ----------------------------------------------------------


async def test_una_llamada_sin_audio_devuelve_el_cupo_del_visitante_y_el_del_sitio(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR5.5 y F4 pasos 2 y 3. La llamada no costo nada, asi que no gasto cupo.

    Se devuelven **los dos** contadores porque los dos se consumieron al abrir
    (F3 paso 6). Devolver solo el del visitante dejaria el cupo del sitio gastado
    por una llamada que no costo nada, y ese cupo es lo que reparte el
    presupuesto entre los dias que faltan (BR5.6).
    """
    await sembrar_ventana()
    periodo = datetime(2026, 9, 21, 0, 0, tzinfo=ZONA)

    await _abrir_llamada()
    assert await _conteo(_clave_del_visitante(periodo)) == 1
    assert await _conteo(_clave_del_sitio(periodo)) == 1

    devolucion = await spend.release_call_quota(
        LLAMADA, visitor_subject_key=VISITANTE, opened_at=AHORA, now=AHORA
    )

    assert devolucion.outcome is ReleaseOutcome.RETURNED
    assert devolucion.released is True
    assert devolucion.call_ref == LLAMADA
    assert await _conteo(_clave_del_visitante(periodo)) == 0
    assert await _conteo(_clave_del_sitio(periodo)) == 0


# --- Los bordes ---------------------------------------------------------------


async def test_una_llamada_con_audio_facturable_no_devuelve_nada(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """La llamada se hablo, asi que se pago: el cupo se gasto de verdad.

    Y la comprobacion se hace contra el **registro de gasto**, que es lo unico
    que no puede mentir: la consola es de quien llama, y un cliente que dijera
    "no consumi nada" se devolveria a si mismo el cupo de una llamada que costo
    dinero (BR5.5, F4 paso 5).
    """
    await sembrar_ventana()
    periodo = datetime(2026, 9, 21, 0, 0, tzinfo=ZONA)

    await _abrir_llamada()
    await _audio_de(LLAMADA, Decimal(42))

    devolucion = await spend.release_call_quota(
        LLAMADA, visitor_subject_key=VISITANTE, opened_at=AHORA, now=AHORA
    )

    assert devolucion.outcome is ReleaseOutcome.BILLABLE_AUDIO
    assert devolucion.released is False
    assert await _conteo(_clave_del_visitante(periodo)) == 1
    assert await _conteo(_clave_del_sitio(periodo)) == 1


async def test_el_doble_cierre_devuelve_un_solo_cupo(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """U16 cierra la sesion siempre, tambien cuando la llamada se cae.

    Asi que el doble cierre es el caso normal y no el raro. Sin la marca por
    llamada, el segundo cierre le devolveria al sitio un cupo que si se gasto: la
    guarda `count > 0` protege al contador del visitante --cuyo limite es uno--
    pero no al del sitio, cuyo conteo es grande.
    """
    await sembrar_ventana()
    periodo = datetime(2026, 9, 21, 0, 0, tzinfo=ZONA)

    # Dos llamadas del sitio ese dia, para que su contador no este en uno: si lo
    # estuviera, la guarda taparia el fallo que esta prueba busca.
    await _abrir_llamada()
    await _abrir_llamada(subject_key="otro-visitante-9f")
    assert await _conteo(_clave_del_sitio(periodo)) == 2

    primero = await spend.release_call_quota(
        LLAMADA, visitor_subject_key=VISITANTE, opened_at=AHORA, now=AHORA
    )
    segundo = await spend.release_call_quota(
        LLAMADA, visitor_subject_key=VISITANTE, opened_at=AHORA, now=AHORA
    )

    assert primero.outcome is ReleaseOutcome.RETURNED
    assert segundo.outcome is ReleaseOutcome.ALREADY_DECIDED
    assert segundo.released is False
    assert await _conteo(_clave_del_sitio(periodo)) == 1
    assert await _conteo(_clave_del_visitante(periodo)) == 0


async def test_un_contador_ya_en_cero_no_se_queda_negativo(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Un contador negativo es cupo regalado, y el caso no es raro.

    El contador del visitante se borra cada noche (BR7.6): una llamada abierta
    antes del reinicio se cierra despues, y entonces el decremento cae sobre un
    contador que ya no existe o que esta en cero. Se responde igual --el cupo no
    se debia-- y no se baja de cero.
    """
    await sembrar_ventana()
    periodo = datetime(2026, 9, 21, 0, 0, tzinfo=ZONA)

    await _abrir_llamada()
    await spend.release_call_quota(
        LLAMADA, visitor_subject_key=VISITANTE, opened_at=AHORA, now=AHORA
    )
    assert await _conteo(_clave_del_visitante(periodo)) == 0

    # Otra llamada del mismo visitante --otra marca, asi que la idempotencia no
    # la tapa-- con su contador ya en cero.
    otra = await spend.release_call_quota(
        "CALL-2", visitor_subject_key=VISITANTE, opened_at=AHORA, now=AHORA
    )

    assert otra.outcome is ReleaseOutcome.RETURNED
    assert await _conteo(_clave_del_visitante(periodo)) == 0
    assert await _conteo(_clave_del_sitio(periodo)) == 0


async def test_una_fila_de_audio_de_cero_unidades_no_impide_la_devolucion(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR5.1 dice "sin un solo segundo": la fila existe, el consumo no.

    Toda llamada deja su fila, incluida la que fallo y la que no consumio nada
    (BR3.1). Mirar si hay fila en vez de mirar sus unidades le quitaria el dia a
    quien perdio la red antes del primer turno, que es la violacion que BR5.5
    nombra.
    """
    await sembrar_ventana()
    periodo = datetime(2026, 9, 21, 0, 0, tzinfo=ZONA)

    await _abrir_llamada()
    await _audio_de(LLAMADA, Decimal(0))

    devolucion = await spend.release_call_quota(
        LLAMADA, visitor_subject_key=VISITANTE, opened_at=AHORA, now=AHORA
    )

    assert devolucion.outcome is ReleaseOutcome.RETURNED
    assert await _conteo(_clave_del_visitante(periodo)) == 0


async def test_el_audio_de_otra_llamada_del_mismo_caso_no_contesta_por_esta(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Por que el libro mayor necesitaba la columna de la llamada.

    Con la pregunta hecha por caso, la fila de una llamada anterior contestaria
    por la de hoy --y contestaria "si", que es la direccion que le quita el dia
    al visitante--. Preguntada por llamada, cada una responde de si misma.
    """
    await sembrar_ventana()
    periodo = datetime(2026, 9, 21, 0, 0, tzinfo=ZONA)

    await _abrir_llamada()
    await _audio_de("CALL-ANTERIOR", Decimal(120))

    devolucion = await spend.release_call_quota(
        LLAMADA, visitor_subject_key=VISITANTE, opened_at=AHORA, now=AHORA
    )

    assert devolucion.outcome is ReleaseOutcome.RETURNED
    assert await _conteo(_clave_del_visitante(periodo)) == 0


async def test_una_llamada_que_cruza_la_medianoche_devuelve_el_cupo_al_dia_que_se_lo_llevo(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """El periodo sale de cuando se abrio la llamada, no de cuando se cierra.

    Una llamada que empieza a las 23:58 y se cae a las 00:03 tomo el cupo de
    ayer. Devolverlo al de hoy dejaria el de ayer gastado para siempre y le
    regalaria al visitante una llamada de hoy que no habia pedido.
    """
    await sembrar_ventana()
    abierta = datetime(2026, 9, 21, 23, 58, tzinfo=ZONA)
    cerrada = datetime(2026, 9, 22, 0, 3, tzinfo=ZONA)
    ayer = datetime(2026, 9, 21, 0, 0, tzinfo=ZONA)
    hoy = datetime(2026, 9, 22, 0, 0, tzinfo=ZONA)

    await _abrir_llamada(cuando=abierta)
    assert await _conteo(_clave_del_visitante(ayer)) == 1

    devolucion = await spend.release_call_quota(
        LLAMADA, visitor_subject_key=VISITANTE, opened_at=abierta, now=cerrada
    )

    assert devolucion.outcome is ReleaseOutcome.RETURNED
    assert await _conteo(_clave_del_visitante(ayer)) == 0
    # Y el dia de hoy sigue sin abrirse: no se le regala una llamada a nadie.
    assert await _conteo(_clave_del_visitante(hoy)) is None


async def test_con_la_base_caida_el_cupo_no_se_devuelve_y_el_cierre_no_se_rompe(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """La devolucion es una cortesia, y una cortesia no puede tumbar un cierre.

    Quien llama esta apagando la llamada; que esta operacion levantara dejaria la
    sesion a medio cerrar por algo que, como mucho, cuesta una llamada. Se dice
    que no se pudo (`UNAVAILABLE`) y reintentar es seguro: la marca no quedo
    escrita, y si hubiera quedado el reintento veria `ALREADY_DECIDED`.
    """
    await sembrar_ventana()
    await _abrir_llamada()

    await session.dispose()
    session.configure(BASE_CAIDA)
    try:
        devolucion = await spend.release_call_quota(
            LLAMADA, visitor_subject_key=VISITANTE, opened_at=AHORA, now=AHORA
        )
    finally:
        await session.dispose()
        session.configure(sesiones.app_url)

    assert devolucion.outcome is ReleaseOutcome.UNAVAILABLE
    assert devolucion.released is False
    # Y nada quedo decidido: el reintento todavia puede devolver el cupo.
    async with session.unscoped_session() as sesion:
        fila = await session.fetch_one(sesion, CONTAR_CIERRES)
    assert fila is not None
    assert int(fila["total"]) == 0


async def test_una_llamada_de_grabacion_no_devuelve_un_cupo_que_nunca_tomo(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """El carril de grabacion no pasa por las cuotas (F3 paso 4), asi que no debe.

    Si devolviera igual, una llamada de grabacion le regalaria al enlace publico
    un cupo que nadie del enlace publico gasto, y ese cupo es presupuesto: es la
    reserva de BR4.9 convirtiendose en carril publico por la puerta de atras.
    """
    await sembrar_ventana()
    periodo = datetime(2026, 9, 21, 0, 0, tzinfo=ZONA)

    # Una llamada del enlace publico que si tomo su cupo, para que haya algo que
    # regalar: con el contador en cero, la guarda taparia el fallo.
    await _abrir_llamada()
    assert await _conteo(_clave_del_sitio(periodo)) == 1

    devolucion = await spend.release_call_quota(
        "CALL-GRABACION", opened_at=AHORA, lane=BudgetLane.RECORDING, now=AHORA
    )

    assert devolucion.outcome is ReleaseOutcome.NOT_HELD
    assert devolucion.released is False
    assert await _conteo(_clave_del_sitio(periodo)) == 1
    assert await _conteo(_clave_del_visitante(periodo)) == 1


async def test_el_carril_publico_sin_sujeto_se_rechaza_en_el_acto(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """No es una condicion de ejecucion: es un error de quien llama.

    Tragarselo devolveria en silencio "el cupo de nadie" --decrementaria el del
    sitio sin saber de quien era el del visitante-- y el visitante se quedaria
    sin su dia igual.
    """
    await sembrar_ventana()

    with pytest.raises(ValueError, match="de quien devolver"):
        await spend.release_call_quota(LLAMADA, opened_at=AHORA, now=AHORA)


# --- Lo que paga la cuarta exclusion del aislamiento (BR7.1, BR7.2) -----------


async def test_la_marca_de_cierre_esta_excluida_con_su_razon_y_sin_dato_personal(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """BR7.1 nombra tres tablas y esta es la cuarta, asi que se declara.

    Es dato del proyecto por la misma razon que las otras tres --la llamada que
    nombra no es de ninguna aseguradora-- y paga lo mismo: sus columnas son un
    identificador acotado, un booleano y una marca de tiempo, y ninguna coincide
    con la lista versionada de nombres de dato personal.
    """
    informe = await rls_assertion.assert_rls_complete()
    assert informe.ok, informe.lines()

    por_tabla = {entrada.table: entrada.reason for entrada in rls_assertion.excluded_tables()}
    assert "voice_call_release" in por_tabla
    assert "proyecto" in por_tabla["voice_call_release"].lower()

    nombres = rls_assertion.personal_data_names()
    async with session.unscoped_session() as sesion:
        columnas = await rls_assertion.read_columns(sesion, ["voice_call_release"])

    assert columnas, "el catalogo no devolvio ninguna columna de la marca de cierre"
    fallos = [
        f"{columna.table}.{columna.column}: {fallo.reason}"
        for columna in columnas
        if (fallo := rls_assertion.check_column(columna, nombres)) is not None
    ]
    assert fallos == []


async def test_el_reinicio_nocturno_se_lleva_las_marcas_de_cierre(
    sesiones: ephemeral.EphemeralDatabase,
) -> None:
    """Una marca sin el contador que protege no protege nada y solo crece.

    El contador del visitante se va esa misma noche (BR7.6), asi que la marca que
    impedia devolverle dos veces su cupo deja de tener a quien proteger.
    """
    await sembrar_ventana()
    await _abrir_llamada()
    await spend.release_call_quota(
        LLAMADA, visitor_subject_key=VISITANTE, opened_at=AHORA, now=AHORA
    )

    # El corte va **despues** de lo escrito: el purgador borra lo anterior al
    # corte, y todo lo de esta prueba ocurrio en el mismo instante.
    resultado = await spend_purge.SPEND_PURGER.purge(older_than=AHORA + timedelta(seconds=1))

    assert resultado.deleted >= 1
    async with session.unscoped_session() as sesion:
        fila = await session.fetch_one(sesion, CONTAR_CIERRES)
    assert fila is not None
    assert int(fila["total"]) == 0
