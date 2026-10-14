"""Los tipos del dinero, las cuotas y el rastro (BR3.4, BR3.9, BR5.3, BR6.6).

Lo que estas pruebas defienden es que las invariantes del dinero vivan en el
**tipo** y no en la disciplina de quien escribe la siguiente fila. Las tres que
mas pesan:

1. Un costo sin su estado no se puede construir, y "no medido" no se puede
   escribir como cero. Si se pudiera, un fallo de configuracion --un precio que
   falta-- se sumaria como si fuera una llamada gratis, y la cifra publicada
   bajaria sin que nada fallara.
2. La coma flotante no entra donde va dinero. Su fallo tampoco avisa: el tipo
   sigue diciendo `Decimal` y la perdida de exactitud viaja hasta el total.
3. Una negacion de cuota trae su motivo. Un rechazo sin motivo llega a la
   pantalla como un error generico, que es lo que FR4.6 prohibe.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from untangle.base import ProviderName, SpendSource, UnitKind, Use
from untangle.telemetry.spend.models import (
    SITE_SUBJECT,
    WINDOW_DAYS,
    BudgetLane,
    BudgetWindow,
    CostStatus,
    Money,
    QuotaCounter,
    QuotaDecision,
    QuotaReason,
    QuotaScope,
    SpendEntry,
    SpendTotal,
    derive_counter_key,
)
from untangle.telemetry.traces.models import (
    NodeName,
    NodeTiming,
    TraceSummary,
    TraceSummaryStatus,
)

AHORA = datetime(2026, 9, 20, 15, 30, tzinfo=UTC)
COMIENZO = date(2026, 9, 16)


def _gasto(**cambios: object) -> dict[str, object]:
    """Una fila de gasto medida, sobre la que cada prueba cambia lo suyo."""
    base: dict[str, object] = {
        "entry_id": "sp-0001",
        "provider": ProviderName.GEMINI,
        "model": "gemini-3.1-flash-lite",
        "use": Use.VOICE,
        "units": Decimal("1200"),
        "unit_kind": UnitKind.INPUT_TOKENS,
        "unit_price_usd": Decimal("0.0000001"),
        "price_list_version": "0",
        "price_list_effective_date": date(2026, 9, 17),
        "cost_usd": Decimal("0.00012"),
        "cost_status": CostStatus.MEASURED,
        "billable": True,
        "lane": BudgetLane.PUBLIC,
        "source": SpendSource.PROVIDER_REPORTED,
        "occurred_at": AHORA,
    }
    return base | cambios


def _ventana(**cambios: object) -> dict[str, object]:
    base: dict[str, object] = {
        "window_start": COMIENZO,
        "window_end": COMIENZO + timedelta(days=WINDOW_DAYS),
        "updated_at": AHORA,
    }
    return base | cambios


# --- El asiento de ajuste conciliado (2026-10-13) -----------------------------


def _ajuste(**cambios: object) -> dict[str, object]:
    """Un ajuste valido: importe medido y nota, sin unidades ni precio de lista."""
    base: dict[str, object] = {
        "entry_id": "adj-0001",
        "provider": ProviderName.ANTHROPIC,
        "model": "claude-haiku-5-5",
        "use": Use.EVALS_CHAT,
        "units": Decimal(0),
        "unit_kind": UnitKind.INPUT_TOKENS,
        "cost_usd": Decimal("0.24"),
        "cost_status": CostStatus.MEASURED,
        "billable": True,
        "source": SpendSource.RECONCILED_ADJUSTMENT,
        "occurred_at": AHORA,
        "note": "consola de Anthropic, 2026-10-13",
    }
    return base | cambios


def test_un_ajuste_lleva_el_importe_y_la_nota_y_ninguna_columna_de_lista() -> None:
    """No lo valoro ninguna lista: llenar el precio y la version seria afirmar uno que nadie fijo."""
    ajuste = SpendEntry.model_validate(_ajuste())

    assert ajuste.cost == Money.measured(Decimal("0.24"))
    assert ajuste.unit_price_usd is None
    assert ajuste.price_list_version is None
    assert ajuste.note == "consola de Anthropic, 2026-10-13"


@pytest.mark.parametrize(
    ("cambio", "dice"),
    [
        ({"note": None}, "falta la nota"),
        ({"cost_usd": None, "cost_status": CostStatus.NOT_MEASURED}, "el importe es obligatorio"),
        ({"cost_status": CostStatus.NOT_MEASURED}, "el importe es obligatorio"),
        ({"units": Decimal(5)}, "no cuenta unidades"),
        ({"unit_price_usd": Decimal("0.1")}, "'unit_price_usd' va vacio"),
        ({"price_list_version": "0"}, "'price_list_version' va vacio"),
        ({"case_ref": "caso-1"}, "no nombra ni un caso"),
        ({"call_ref": "llamada-1"}, "no nombra ni un caso"),
    ],
)
def test_un_ajuste_mal_formado_no_se_puede_construir(cambio: dict[str, object], dice: str) -> None:
    with pytest.raises(ValidationError) as error:
        SpendEntry.model_validate(_ajuste(**cambio))
    assert dice in str(error.value)


def test_solo_un_ajuste_lleva_nota() -> None:
    """El libro no guarda texto que una persona haya escrito, salvo la nota de un ajuste."""
    with pytest.raises(ValidationError) as error:
        SpendEntry.model_validate(_gasto(note="una frase"))
    assert "solo un asiento de ajuste lleva nota" in str(error.value)


def test_la_nota_esta_acotada() -> None:
    """Una columna de texto sin tope es donde un dia cabe una frase de otra persona (BR7.2)."""
    with pytest.raises(ValidationError):
        SpendEntry.model_validate(_ajuste(note="x" * 201))
    with pytest.raises(ValidationError):
        SpendEntry.model_validate(_ajuste(note=""))
    assert SpendEntry.model_validate(_ajuste(note="x" * 200)).note == "x" * 200


# --- El costo y su estado viajan juntos ---------------------------------------


def test_el_costo_no_se_puede_construir_sin_su_estado_ni_contra_el() -> None:
    """BR3.9 en sus dos direcciones.

    La segunda es la que importa de verdad: si `not_measured` admitiera una
    cantidad, la forma de escribir cero por falta de precio volveria a estar
    disponible, y "no se pudo valorar" se sumaria como una llamada gratis.
    """
    assert Money.measured(Decimal("0.25")).is_measured
    assert not Money.not_measured().is_measured

    with pytest.raises(ValidationError) as sin_cantidad:
        Money(amount_usd=None, status=CostStatus.MEASURED)
    assert "not_measured" in str(sin_cantidad.value)

    with pytest.raises(ValidationError) as con_cantidad:
        Money(amount_usd=Decimal("0"), status=CostStatus.NOT_MEASURED)
    assert "cero" in str(con_cantidad.value)


def test_el_dinero_y_las_unidades_rechazan_la_coma_flotante() -> None:
    """El tipo lo impide en la construccion, no en un comentario.

    Se comprueban los dos factores de la multiplicacion --el importe y el
    recuento de unidades-- porque basta con que uno sea inexacto para que el
    producto lo sea, y el producto es lo que se acumula contra el techo.

    Se construye por `model_validate` a proposito: es el camino por el que entra
    un YAML, donde un numero sin comillas se lee como coma flotante. Por el
    constructor directo, el comprobador de tipos ya lo rechaza antes de correr.
    """
    with pytest.raises(ValidationError) as importe:
        Money.model_validate({"amount_usd": 0.1, "status": "measured"})
    #: Y el mensaje dice que hacer, porque quien lo ve viene de editar un YAML
    #: donde el numero iba sin comillas.
    assert "comillas" in str(importe.value)

    with pytest.raises(ValidationError) as unidades:
        SpendEntry.model_validate(_gasto(units=1200.0))
    assert "coma flotante" in str(unidades.value)

    #: La cadena si entra, y es la forma en que se escribe en los archivos
    #: versionados: `Decimal("0.1")` es exacto y `Decimal(0.1)` no.
    assert Money.model_validate({"amount_usd": "0.1", "status": "measured"}).amount_usd == Decimal(
        "0.1"
    )


def test_las_cuatro_columnas_de_precio_estan_todas_o_ninguna() -> None:
    """BR3.4. Una fila `measured` a la que le falte la fecha de la lista no se
    puede reproducir meses despues; una `not_measured` que traiga un precio
    afirma haber medido lo que no midio."""
    completa = SpendEntry.model_validate(_gasto())
    assert completa.cost == Money.measured(Decimal("0.00012"))

    with pytest.raises(ValidationError) as falta:
        SpendEntry.model_validate(_gasto(price_list_effective_date=None))
    assert "price_list_effective_date" in str(falta.value)

    sin_precio = SpendEntry.model_validate(
        _gasto(
            cost_status=CostStatus.NOT_MEASURED,
            unit_price_usd=None,
            price_list_version=None,
            price_list_effective_date=None,
            cost_usd=None,
        )
    )
    assert sin_precio.cost == Money.not_measured()

    with pytest.raises(ValidationError) as sobra:
        SpendEntry.model_validate(_gasto(cost_status=CostStatus.NOT_MEASURED))
    assert "not_measured" in str(sobra.value)


def test_toda_agregacion_lleva_su_conteo_de_no_medidas() -> None:
    """BR3.5. Sumar dos parciales suma **los dos** lados: el dia que alguien
    publique el total tendra que desarmar el tipo para dejar fuera el conteo, y
    eso se ve en la revision."""
    uno = SpendTotal(measured_usd=Decimal("0.40"), unmeasured_count=2)
    otro = SpendTotal(measured_usd=Decimal("0.25"), unmeasured_count=1)

    assert uno + otro == SpendTotal(measured_usd=Decimal("0.65"), unmeasured_count=3)


# --- La ventana ---------------------------------------------------------------


def test_la_reserva_de_grabacion_cabe_en_el_techo_y_su_gasto_en_el_acumulado() -> None:
    """BR4.9. Las dos contenciones que si se sostienen, y la que no.

    Apartar mas de lo que hay dejaria el carril publico cerrado desde el primer
    dia, y lo gastado en grabacion esta **incluido** en el acumulado facturable,
    asi que no puede superarlo.

    Lo que **no** se exige es que el gasto de grabacion quepa en su reserva: esa
    invariante se quito el 2026-09-21 y tiene su propia prueba abajo.
    """
    sana = BudgetWindow.model_validate(
        _ventana(
            billable_spent_usd=Decimal("1.00"),
            recording_reserve_usd=Decimal("0.225"),
            recording_reserve_status=CostStatus.MEASURED,
            recording_spent_usd=Decimal("0.10"),
        )
    )
    assert sana.public_spent_usd == Decimal("0.90")

    with pytest.raises(ValidationError) as reserva:
        BudgetWindow.model_validate(
            _ventana(
                # Mas que el techo: se fija el techo para que la prueba no dependa
                # del valor por omision (40 USD desde el 2026-10-07).
                cap_usd=Decimal("5.00"),
                alert_usd=Decimal("3.00"),
                recording_reserve_usd=Decimal("6.00"),
                recording_reserve_status=CostStatus.MEASURED,
            )
        )
    assert "no cabe en el techo" in str(reserva.value)

    with pytest.raises(ValidationError) as acumulado:
        BudgetWindow.model_validate(
            _ventana(
                billable_spent_usd=Decimal("0.05"),
                recording_reserve_usd=Decimal("0.225"),
                recording_reserve_status=CostStatus.MEASURED,
                recording_spent_usd=Decimal("0.30"),
            )
        )
    assert "no puede superarlo" in str(acumulado.value)


def test_el_carril_de_grabacion_puede_pasarse_de_su_reserva_y_dejar_su_fila() -> None:
    """BR3.1 manda sobre la contencion de la reserva, y esta es la razon.

    El techo se consulta **antes** de llamar al proveedor y el costo se registra
    **despues** (BR4.5), asi que la ultima llamada de un carril puede terminar
    costando mas de lo que quedaba. Con la invariante puesta, registrar ese
    exceso **levantaba**: la llamada ya se hizo y su fila no se escribia.

    Una fila de gasto perdida falsea una cifra publicada y no deja rastro de que
    falta. Un acumulado que se pasa de su reserva no falsea nada, porque el
    restante se informa con piso en cero y ya dice que no queda.
    """
    pasada = BudgetWindow.model_validate(
        _ventana(
            billable_spent_usd=Decimal("0.40"),
            recording_reserve_usd=Decimal("0.225"),
            recording_reserve_status=CostStatus.MEASURED,
            recording_spent_usd=Decimal("0.30"),
        )
    )

    assert pasada.recording_spent_usd > Decimal("0.225")
    assert pasada.public_spent_usd == Decimal("0.10")

    # Y la mitad simetrica: con la reserva sin medir tampoco se exige cero. La
    # llamada de grabacion que se hizo con el tamano de la reserva desconocido
    # deja su fila igual, porque BR3.1 no tiene excepciones.
    sin_saber_cuanto = BudgetWindow.model_validate(
        _ventana(billable_spent_usd=Decimal("0.10"), recording_spent_usd=Decimal("0.10"))
    )

    assert sin_saber_cuanto.recording_reserve == Money.not_measured()
    assert sin_saber_cuanto.recording_spent_usd == Decimal("0.10")


def test_las_llamadas_de_grabacion_sin_valorar_son_parte_de_las_facturables() -> None:
    """La contencion del conteo, gemela de la del gasto.

    Un conteo de carril mayor que el total no describe ningun estado alcanzable:
    la llamada que sube el del carril sube el total en el mismo acto. Sin esta
    invariante, una fila torcida dejaria el corte del carril publico opinando
    sobre llamadas que el total nunca vio.
    """
    repartidas = BudgetWindow.model_validate(
        _ventana(unmeasured_billable_calls=3, unmeasured_recording_calls=1)
    )
    assert repartidas.unmeasured_recording_calls == 1

    with pytest.raises(ValidationError) as torcida:
        BudgetWindow.model_validate(
            _ventana(unmeasured_billable_calls=1, unmeasured_recording_calls=2)
        )
    assert "no pueden superarlas" in str(torcida.value)


def test_la_ventana_es_acumulada_de_noventa_dias_y_nunca_mensual() -> None:
    """BR4.1 y D11. Con un contador que se reiniciara cada mes, el techo no
    protegeria nada: bastaria con esperar al dia primero."""
    assert BudgetWindow.model_validate(_ventana()).window_end == date(2026, 12, 15)

    with pytest.raises(ValidationError) as mensual:
        BudgetWindow.model_validate(
            _ventana(window_end=COMIENZO + timedelta(days=30)),
        )
    assert str(WINDOW_DAYS) in str(mensual.value)


# --- Las cuotas ---------------------------------------------------------------


def test_una_cuota_negada_trae_su_motivo_y_el_techo_no_trae_cuando() -> None:
    """BR5.3. Y el caso del techo aparte: decirle a quien llama que reintente en
    unos segundos seria mentirle, porque el acumulado de la ventana solo sube."""
    QuotaDecision(allowed=True)
    QuotaDecision(
        allowed=False,
        reason_code=QuotaReason.RATE_LIMITED_DAILY,
        retry_after_seconds=3600,
    )

    with pytest.raises(ValidationError) as sin_motivo:
        QuotaDecision(allowed=False)
    assert "motivo" in str(sin_motivo.value)

    with pytest.raises(ValidationError) as con_motivo:
        QuotaDecision(allowed=True, reason_code=QuotaReason.RATE_LIMITED_SITE)
    assert "permitida" in str(con_motivo.value)

    with pytest.raises(ValidationError) as techo:
        QuotaDecision(
            allowed=False,
            reason_code=QuotaReason.BUDGET_EXHAUSTED,
            retry_after_seconds=60,
        )
    assert "no tiene cuando" in str(techo.value)


def test_el_contador_deriva_su_clave_y_el_cupo_del_sitio_no_es_de_nadie() -> None:
    """Dos contadores del mismo alcance, sujeto y periodo tienen que ser **uno**:
    si la clave se eligiera al crearlos, abrir dos llamadas a la vez crearia dos
    filas y cada una dejaria pasar la suya, que es el escenario RT-13."""
    periodo = datetime(2026, 9, 20, 5, 0, tzinfo=UTC)
    clave = derive_counter_key(QuotaScope.VOICE_CALLS_VISITOR_DAY, "hash-de-navegador", periodo)

    contador = QuotaCounter(
        counter_key=clave,
        scope=QuotaScope.VOICE_CALLS_VISITOR_DAY,
        subject_key="hash-de-navegador",
        period_start=periodo,
        count=1,
        limit_at_period_start=1,
        updated_at=AHORA,
    )
    assert contador.counter_key == clave

    with pytest.raises(ValidationError) as inventada:
        contador.evolve(counter_key="la-que-yo-quiera")
    assert "derivarse" in str(inventada.value)

    #: El cupo del sitio no es de ningun visitante, asi que no lleva el resumen
    #: de ninguna clave de navegador.
    del_sitio = derive_counter_key(QuotaScope.VOICE_CALLS_SITE_DAY, SITE_SUBJECT, periodo)
    QuotaCounter(
        counter_key=del_sitio,
        scope=QuotaScope.VOICE_CALLS_SITE_DAY,
        subject_key=SITE_SUBJECT,
        period_start=periodo,
        limit_at_period_start=15,
        updated_at=AHORA,
    )

    with pytest.raises(ValidationError) as ajeno:
        QuotaCounter(
            counter_key=derive_counter_key(
                QuotaScope.VOICE_CALLS_SITE_DAY, "hash-de-navegador", periodo
            ),
            scope=QuotaScope.VOICE_CALLS_SITE_DAY,
            subject_key="hash-de-navegador",
            period_start=periodo,
            limit_at_period_start=15,
            updated_at=AHORA,
        )
    assert SITE_SUBJECT in str(ajeno.value)


def test_un_periodo_sin_zona_horaria_no_produce_clave() -> None:
    """BR5.2. Sin zona, la medianoche es la del servidor: un cambio de maquina
    moveria el corte del dia y regalaria o quitaria una llamada."""
    with pytest.raises(ValueError, match="zona horaria"):
        derive_counter_key(
            QuotaScope.CHAT_MESSAGES_DAY,
            "hash-de-navegador",
            datetime(2026, 9, 20, 5, 0),
        )


# --- El resumen de traza ------------------------------------------------------


def test_el_resumen_no_verifica_mas_clausulas_de_las_que_recupero() -> None:
    """Verificar lo que no se recupero no significa nada, y publicado como
    metrica diria que el verificador funciona mejor de lo que funciona."""
    with pytest.raises(ValidationError) as mas:
        TraceSummary(
            trace_id="tr-1",
            tenant_id="stonecroft",
            case_id="case-1",
            visitor_key_hash="hash",
            clauses_retrieved=2,
            clauses_verified=3,
            created_at=AHORA,
        )
    assert "no se recupero" in str(mas.value)


def test_un_resumen_listo_trae_sus_nodos_y_su_latencia() -> None:
    """Vacio y `ready` seria un resumen que miente. Mientras el rastro no haya
    llegado, el estado es `recording`, que es una respuesta honesta y es lo que
    el visitante ve como "registrandose"."""
    en_curso = TraceSummary(
        trace_id="tr-2",
        tenant_id="stonecroft",
        case_id="case-1",
        visitor_key_hash="hash",
        created_at=AHORA,
    )
    assert en_curso.status is TraceSummaryStatus.RECORDING
    assert en_curso.cost == Money.not_measured()

    listo = en_curso.evolve(
        status=TraceSummaryStatus.READY,
        latency_ms=820,
        nodes=(
            NodeTiming(
                node=NodeName.INTAKE,
                started_at=AHORA,
                duration_ms=310,
                cost=Money.measured(Decimal("0.00012")),
            ),
        ),
    )
    assert listo.nodes[0].node is NodeName.INTAKE

    with pytest.raises(ValidationError) as sin_nodos:
        en_curso.evolve(status=TraceSummaryStatus.READY, latency_ms=820)
    assert "miente" in str(sin_nodos.value)
