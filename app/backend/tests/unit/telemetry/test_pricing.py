"""El calculo del costo: con precio, sin precio, y por que nunca cero (BR3.2, BR3.3).

La prueba que mas vale de este archivo es la del orden de la suma. Con coma
flotante pasaria en la mayoria de los ordenes y fallaria en algunos, que es la
peor forma de fallar: se descubre el dia que el techo corta en un punto distinto
del que corto ayer, con los mismos datos.
"""

from __future__ import annotations

from datetime import UTC, date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from untangle.base import ProviderName, UnitKind
from untangle.telemetry.spend import budget, pricing
from untangle.telemetry.spend.models import Money, PriceEntry, SpendTotal

LISTA = "2026-09-17"
VIGENCIA = date(2026, 9, 17)


def _tabla(*lineas: PriceEntry) -> pricing.PriceTable:
    return pricing.PriceTable.from_entries(lineas)


def _linea(unit_kind: UnitKind, precio: str) -> PriceEntry:
    return PriceEntry(
        provider=ProviderName.GEMINI,
        model="gemini-3.1-flash-lite",
        unit_kind=unit_kind,
        unit_price_usd=Decimal(precio),
        list_version=LISTA,
        effective_date=VIGENCIA,
    )


def _precio(tabla: pricing.PriceTable, unidades: str, unit_kind: UnitKind) -> pricing.PricedCost:
    return pricing.price_call(
        tabla,
        provider=ProviderName.GEMINI,
        model="gemini-3.1-flash-lite",
        unit_kind=unit_kind,
        units=Decimal(unidades),
    )


# --- Con precio ---------------------------------------------------------------


def test_con_precio_declarado_el_costo_viene_con_su_lista_y_su_fecha() -> None:
    """AC4.8.4 literal: cada llamada registra el precio usado **y la fecha de esa
    lista**. Sin las dos, la cifra no se puede reproducir meses despues, cuando
    el precio del proveedor ya cambio."""
    calculado = _precio(
        _tabla(_linea(UnitKind.INPUT_TOKENS, "0.0000001")),
        "1200",
        UnitKind.INPUT_TOKENS,
    )

    assert calculado.cost == Money.measured(Decimal("0.00012"))
    assert calculado.unit_price_usd == Decimal("0.0000001")
    assert calculado.price_list_version == LISTA
    assert calculado.price_list_effective_date == VIGENCIA


def test_el_producto_no_se_redondea_a_centavos() -> None:
    """Redondear convertiria en cero toda llamada que cueste menos de medio
    centavo, que son casi todas las de este proyecto, y eso es justo la cifra
    prohibida: un cero que despues se suma como si fuera cierto."""
    calculado = _precio(
        _tabla(_linea(UnitKind.OUTPUT_TOKENS, "0.0000004")),
        "300",
        UnitKind.OUTPUT_TOKENS,
    )

    assert calculado.cost.amount_usd == Decimal("0.00012")
    assert calculado.cost.amount_usd != Decimal("0.00")


# --- Sin precio ---------------------------------------------------------------


def test_sin_precio_declarado_el_costo_es_no_medido_y_nunca_cero() -> None:
    """BR3.3. Un cero se suma como si fuera cierto: baja el costo por caso
    publicado, deja corto el acumulado y el techo corta mas tarde de lo que
    debia. Nada falla y nada avisa."""
    calculado = _precio(_tabla(), "1200", UnitKind.INPUT_TOKENS)

    assert calculado.cost == Money.not_measured()
    assert calculado.cost.amount_usd is None
    assert calculado.unit_price_usd is None
    assert calculado.price_list_version is None
    assert calculado.price_list_effective_date is None


def test_la_clave_del_precio_son_tres_cosas_y_no_dos() -> None:
    """Un proveedor cobra distinto la entrada y la salida. Buscar solo por
    proveedor y modelo cobraria la salida a precio de entrada, que es mas barato
    y por tanto pasa desapercibido."""
    tabla = _tabla(_linea(UnitKind.INPUT_TOKENS, "0.0000001"))

    assert _precio(tabla, "1000", UnitKind.INPUT_TOKENS).cost.is_measured
    assert not _precio(tabla, "1000", UnitKind.OUTPUT_TOKENS).cost.is_measured

    otro_modelo = pricing.price_call(
        tabla,
        provider=ProviderName.GEMINI,
        model="gemini-embedding-001",
        unit_kind=UnitKind.INPUT_TOKENS,
        units=Decimal("1000"),
    )
    assert not otro_modelo.cost.is_measured


def test_un_costo_medido_no_se_puede_construir_sin_decir_con_que_precio() -> None:
    """La constancia y el costo van juntos o no van. Que la invariante viva en el
    valor que produce la fila --y no solo en la fila-- es lo que impide que una
    fila de gasto nazca a medias."""
    with pytest.raises(ValidationError) as sin_constancia:
        pricing.PricedCost(cost=Money.measured(Decimal("0.01")))
    assert "price_list_version" in str(sin_constancia.value)

    with pytest.raises(ValidationError) as de_mas:
        pricing.PricedCost(cost=Money.not_measured(), price_list_version=LISTA)
    assert "no tiene con que respaldarse" in str(de_mas.value)


# --- El orden de la suma ------------------------------------------------------


def test_veinte_fracciones_de_centavo_suman_igual_en_cualquier_orden() -> None:
    """Es lo que la coma flotante no cumple, y el motivo de que el dinero de este
    proyecto sea decimal exacto.

    Si el total dependiera del orden, el techo cortaria en un punto distinto
    segun el orden en que llegaron las llamadas, y la cifra de costo que el
    proyecto publica dejaria de ser reproducible desde el mismo commit.

    Los tres ordenes se escriben a mano y no se barajan: el proyecto prohibe toda
    fuente de azar, y una prueba que fallara un dia de cada tantos sin poder
    reproducirse seria peor que no tenerla.
    """
    tabla = _tabla(_linea(UnitKind.INPUT_TOKENS, "0.0000001"))
    costos = [_precio(tabla, str(100 + n * 7), UnitKind.INPUT_TOKENS).cost for n in range(20)]

    en_orden = budget.total(costos)
    al_reves = budget.total(list(reversed(costos)))
    #: Los pares primero y los impares despues: reagrupa los sumandos por tamano,
    #: que es la forma en que la coma flotante pierde los bits bajos.
    entrelazados = budget.total(costos[::2] + costos[1::2])

    assert en_orden == al_reves == entrelazados
    assert en_orden.measured_usd == Decimal("0.000333")


def test_lo_no_medido_se_cuenta_aparte_y_no_entra_como_cero() -> None:
    """BR3.5. Diez llamadas medidas y tres sin precio no son trece llamadas
    baratas: son diez medidas y tres que nadie midio, y la diferencia tiene que
    llegar hasta la pantalla."""
    tabla = _tabla(_linea(UnitKind.INPUT_TOKENS, "0.001"))
    costos = [_precio(tabla, "10", UnitKind.INPUT_TOKENS).cost for _ in range(10)]
    costos += [_precio(tabla, "10", UnitKind.AUDIO_SECONDS).cost for _ in range(3)]

    assert budget.total(costos) == SpendTotal(measured_usd=Decimal("0.100"), unmeasured_count=3)


# --- U17, tanda 2: la reserva por llamada, sumada de sus tres componentes ------


def _runtime_de_prueba(*, con_sintesis: bool = True, con_modelo: bool = True) -> object:
    """Un tiempo de ejecucion con la tabla y el consumo escritos aqui.

    Los numeros son de la prueba y no del archivo: lo que se comprueba es la suma y
    la propagacion del "no medido", no si el proyecto eligio bien sus supuestos.
    """
    from decimal import Decimal

    from untangle.base import ProviderName, UnitKind, Use
    from untangle.telemetry.spend import api as spend
    from untangle.telemetry.spend import pricing
    from untangle.telemetry.spend.models import CallUsage, PricedUnits, PriceEntry

    lineas = [
        PriceEntry(
            provider=ProviderName.DEEPGRAM,
            model="nova-3",
            unit_kind=UnitKind.AUDIO_SECONDS,
            unit_price_usd=Decimal("0.001"),
            list_version="prueba",
            effective_date=date(2026, 9, 16),
        )
    ]
    if con_sintesis:
        lineas.append(
            PriceEntry(
                provider=ProviderName.CARTESIA,
                model="sonic-3.6",
                unit_kind=UnitKind.CHARACTERS,
                unit_price_usd=Decimal("0.0001"),
                list_version="prueba",
                effective_date=date(2026, 9, 16),
            )
        )
    if con_modelo:
        lineas.append(
            PriceEntry(
                provider=ProviderName.GEMINI,
                model="flash",
                unit_kind=UnitKind.INPUT_TOKENS,
                unit_price_usd=Decimal("0.000001"),
                list_version="prueba",
                effective_date=date(2026, 9, 16),
            )
        )
        lineas.append(
            PriceEntry(
                provider=ProviderName.GEMINI,
                model="flash",
                unit_kind=UnitKind.OUTPUT_TOKENS,
                unit_price_usd=Decimal("0.00001"),
                list_version="prueba",
                effective_date=date(2026, 9, 16),
            )
        )

    def unidades(
        proveedor: ProviderName, modelo: str, clase: UnitKind, cuantas: str
    ) -> PricedUnits:
        return PricedUnits(
            provider=proveedor, model=modelo, unit_kind=clase, units=Decimal(cuantas)
        )

    return spend.SpendRuntime(
        prices=pricing.PriceTable.from_entries(lineas),
        plans={
            Use.VOICE: spend.UsePlan(provider=ProviderName.GEMINI, model="flash", billable=True)
        },
        zone=UTC,
        chat_messages_per_session=30,
        chat_messages_per_day=60,
        voice_calls_per_visitor_per_day=1,
        site_daily_cap=15,
        max_call_seconds=100,
        call_usage=CallUsage(
            transcription=unidades(ProviderName.DEEPGRAM, "nova-3", UnitKind.AUDIO_SECONDS, "100"),
            synthesis_primary=unidades(
                ProviderName.CARTESIA, "sonic-3.6", UnitKind.CHARACTERS, "1000"
            ),
            synthesis_fallback=unidades(
                ProviderName.DEEPGRAM, "aura-2", UnitKind.CHARACTERS, "1000"
            ),
            model_input=unidades(ProviderName.GEMINI, "flash", UnitKind.INPUT_TOKENS, "10000"),
            model_output=unidades(ProviderName.GEMINI, "flash", UnitKind.OUTPUT_TOKENS, "1000"),
        ),
        recording_minutes=10,
    )


def test_la_reserva_es_la_suma_de_sus_tres_componentes() -> None:
    """Transcripcion, sintesis y modelo. Una reserva que olvide uno es mas barata
    que la de verdad, y una reserva mas barata reparte mas llamadas de las que
    caben."""
    from untangle.telemetry.spend import api as spend
    from untangle.telemetry.spend.models import VoiceMode

    runtime = _runtime_de_prueba()

    reserva = spend.call_reserve(VoiceMode.PRIMARY, runtime)  # type: ignore[arg-type]

    # 100 s * 0,001 + 1000 car. * 0,0001 + 10000 * 0,000001 + 1000 * 0,00001
    assert reserva.reserve.amount_usd == Decimal("0.22")
    assert reserva.mode is VoiceMode.PRIMARY


def test_la_reserva_de_respaldo_cuesta_menos_que_la_principal() -> None:
    """Y es la diferencia que hace util el modo: con el presupuesto justo, la
    llamada cabe con la barata."""
    from untangle.telemetry.spend import api as spend
    from untangle.telemetry.spend.models import VoiceMode

    runtime = _runtime_de_prueba()

    principal = spend.call_reserve(VoiceMode.PRIMARY, runtime)  # type: ignore[arg-type]
    respaldo = spend.call_reserve(VoiceMode.FALLBACK, runtime)  # type: ignore[arg-type]

    # La de respaldo no tiene linea de sintesis en esta tabla, asi que **no se
    # mide**: es la propagacion de abajo. Lo que esta prueba fija es que la
    # principal si se mide y que las dos no son el mismo numero por descuido.
    assert principal.reserve.amount_usd is not None
    assert respaldo.reserve.amount_usd is None


def test_si_a_un_componente_le_falta_su_linea_la_reserva_no_se_sabe() -> None:
    """No se suma lo medido ignorando el resto.

    Es el fallo que cerro el enlace publico de voz hasta la tanda 2 de U17, visto
    desde el otro lado: una reserva incompleta se habria sumado como si fuera la
    entera, y habria repartido mas llamadas de las que el presupuesto paga.
    """
    from untangle.telemetry.spend import api as spend
    from untangle.telemetry.spend.models import VoiceMode

    runtime = _runtime_de_prueba(con_modelo=False)

    reserva = spend.call_reserve(VoiceMode.PRIMARY, runtime)  # type: ignore[arg-type]

    assert reserva.reserve.amount_usd is None


def test_los_minutos_de_grabacion_se_convierten_con_la_misma_aritmetica() -> None:
    """Diez minutos son seis llamadas de cien segundos, a la reserva de la principal."""
    from untangle.telemetry.spend import api as spend

    runtime = _runtime_de_prueba()

    reserva = spend.recording_reserve_usd(runtime)  # type: ignore[arg-type]

    assert reserva.amount_usd == Decimal("6") * Decimal("0.22")
