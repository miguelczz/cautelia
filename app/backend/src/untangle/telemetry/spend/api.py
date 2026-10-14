"""La contabilidad del proyecto: la superficie que consumen U13, U16, U17 y U22.

Cuatro operaciones (C-17) y un purgador. Todo lo que cuesta dinero de verdad
pasa por aqui, y por eso este archivo tiene una obligacion que los demas no:
**su fallo no produce un error, produce una factura**.

## Las tres asimetrias, y que las produce

Ninguna de las tres es una rama de codigo que alguien pueda invertir. Las tres
salen de un dato declarado --`_ALCANCES_DE_PAGO`-- que dice que alcances de
cuota cuestan dinero. Anadir un alcance obliga a decidirlo ahi, a la vista, en
vez de olvidarlo en un `if` a mitad de un archivo:

1. **Quien consulta el presupuesto.** Solo los alcances de pago. El chat no lo
   consulta porque sus llamadas no son facturables, asi que el techo agotado no
   lo puede apagar (BR4.4, AC5.14.3).
2. **Hacia donde cae el fallo.** Cerrado para lo facturable y abierto para lo
   que no consume el techo (NFR-U5-3). Con la base caida, la llamada de voz se
   rechaza con el motivo de presupuesto y el chat sigue atendiendo: un limite
   que falla abierto donde hay dinero no es un limite, y apagar el chat gratuito
   no protege nada.
3. **Quien esta en el camino de la respuesta.** La fila facturable se escribe
   sincrona, dentro de la transaccion que incrementa el acumulado (BR4.6). La no
   facturable va a una cola acotada y **no puede romper el turno**: ningun techo
   depende de ella.

## La cola de lo no facturable, y por que pasa a sincrona

Acotada, drenada por una tarea del mismo proceso, y **al llenarse escribe
sincrono en vez de descartar**. Se paga latencia en el chat justo cuando la base
va lenta; a cambio no se pierde ninguna fila. Una cifra de costo a la que le
faltan llamadas no es una medicion, y el costo por caso es una de las cinco que
el proyecto publica.

Es el contrario exacto de la cola de tramos de `traces/api.py`, que si descarta,
y el contraste es deliberado: perder una fila de gasto falsea una cifra
publicada y perder un tramo solo empeora un diagnostico.

**Lo que la cola no puede prometer.** Que no descarte al llenarse no significa
que ninguna fila se pierda nunca: si la base esta caida cuando la tarea de fondo
drena, esa escritura falla. Entonces se **cuenta y se publica**
(`deferred_failures`), no se calla. Lo que no ocurre en ningun caso es que un
fallo de esa escritura rompa el turno: esa es la mitad del trato que el carril
no facturable si puede cumplir.

## Enmiendas a C-17 que este archivo implementa

Las dos primeras ya estan escritas en `contract-summary.md`, con fecha del
2026-09-21: `units` es `Decimal` y no `float`, y `BudgetState` tiene cuatro
estados y no tres. **La tercera y la cuarta se descubren aqui y hay que
llevarlas al contrato**:

**La tercera.** `record_spend` necesita ademas el **modelo** y la **clase de
unidad** que cobra la llamada. El contrato escribe `provider: str` y
`unit_kind: str`; la clave de la tabla de precios es la terna (proveedor,
modelo, unidad) y la fila guarda el identificador exacto del modelo (BR1.4,
BR3.2), asi que sin el modelo no hay precio que buscar ni cifra que reproducir
meses despues. Los tres viajan como enums cerrados y no como texto libre, por la
misma razon por la que la fila tiene una restriccion de conjunto cerrado en la
base.

**La cuarta**, del 2026-09-21: `BudgetState` lleva ademas `recording_reserve_usd`
y `recording_spent`. Un restante sin numero tiene **dos** causas --la reserva
ilegible y una llamada que no se pudo valorar-- y sin esos dos campos la foto
dice que no hay numero pero no cual de las dos fue, que es la diferencia entre
"falta un precio en la tabla" y "una llamada salio sin valorar". Los dos campos
son aditivos: nada de lo que el contrato ya prometia cambia de forma.

Y una consecuencia que conviene leer antes de sumar filas: **una llamada de
generacion deja dos filas, no una**. BR3.1 dice "una fila por llamada" y la
entidad solo admite una clase de unidad por fila, mientras el proveedor cobra
los tokens de entrada y los de salida a precios distintos. Las dos filas nombran
el mismo caso y el mismo modelo; lo que cuenta por llamada es el par (caso,
momento), no el numero de filas.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, tzinfo
from decimal import Decimal
from uuid import uuid4

from untangle import observability
from untangle.base import ProviderName, SpendSource, UnitKind, Use
from untangle.telemetry.spend import budget, pricing, quota, repository
from untangle.telemetry.spend.models import (
    WINDOW_START,
    BudgetLane,
    BudgetState,
    BudgetStatus,
    CallRef,
    CallReserve,
    CallUsage,
    CostStatus,
    Money,
    QuotaDecision,
    QuotaPeriod,
    QuotaRelease,
    QuotaScope,
    ReleaseOutcome,
    SpendEntry,
    SpendEntryId,
    SubjectKey,
    VoiceMode,
    derive_counter_key,
)

__all__ = [
    "DEFERRED_QUEUE_CAPACITY",
    "STATEMENT_TIMEOUT_MS",
    "AdjustmentResult",
    "QuotaState",
    "SpendRuntime",
    "SpendUnavailableError",
    "UsePlan",
    "adjustment_entry",
    "adjustment_id",
    "budget_state",
    "call_reserve",
    "check_quota",
    "current_runtime",
    "deferred_failures",
    "expected_voice_mode",
    "flush_deferred",
    "install",
    "open_deferred_queue",
    "pending_deferred",
    "quota_state",
    "record_adjustment",
    "record_spend",
    "release_call_quota",
    "reserve_primary_voice",
    "reset",
    "start_deferred_writer",
    "stop_deferred_writer",
]

#: Cuanto puede esperar la lectura del presupuesto antes de rendirse.
#:
#: Cincuenta milisegundos, que son los del presupuesto de consulta de
#: `performance-design` para las dos lecturas del camino de disponibilidad. No es
#: un numero de comodidad: pasado ese punto, esperar consumiria tambien el
#: presupuesto de latencia del endpoint que llamo, y el rechazo llegaria tarde
#: **ademas** de llegar.
STATEMENT_TIMEOUT_MS = 50

#: Cuantas filas no facturables caben esperando a que la tarea de fondo las
#: escriba.
#:
#: Doscientas cincuenta y seis. La cifra sale de para que existe la cola: cubrir
#: una rafaga corta mientras la base va lenta, no acumular trabajo. Con los
#: limites del chat --treinta mensajes por sesion-- son ocho conversaciones
#: enteras en vuelo a la vez, que es mas de lo que una demostracion publica ve en
#: un pico; y es lo bastante pequena como para que llenarla sea una senal y no un
#: estado normal, porque llenarla **cuesta latencia en el chat**.
DEFERRED_QUEUE_CAPACITY = 256


class SpendUnavailableError(RuntimeError):
    """No se pudo leer el presupuesto dentro de su tiempo maximo.

    No es una negacion de cuota --esas son valores, nunca excepciones (BR5.3)--
    sino el fallo de la lectura que decide. Quien lo atrapa es esta misma
    superficie, que lo convierte en el rechazo de lo facturable; hacia fuera
    nunca sale.
    """


@dataclass(frozen=True)
class UsePlan:
    """Con quien habla un uso y si su llamada se factura (BR1.3, BR3.6).

    Es la parte de `providers.yaml` que la contabilidad necesita, copiada por la
    raiz de composicion en vez de importada: `telemetry` esta **debajo** de
    `providers` en el contrato de capas, asi que este modulo no puede leer la
    configuracion de proveedores. Lo que cruza es el dato, no la dependencia.
    """

    provider: ProviderName
    model: str
    billable: bool


@dataclass(frozen=True)
class SpendRuntime:
    """Lo que la contabilidad necesita saber, instalado una vez al arrancar.

    Todo lo de aqui sale de configuracion versionada y lo copia la raiz de
    composicion. Se instala en vez de leerse por la misma razon que la tabla de
    precios no se recarga en caliente: cambiar cualquiera de estos numeros mueve
    una cifra publicada o un corte, y tiene que quedar en el historial.
    """

    prices: pricing.PriceTable
    plans: Mapping[Use, UsePlan]
    #: La zona en la que se cierra el dia de una cuota diaria (BR5.2).
    zone: tzinfo
    chat_messages_per_session: int
    chat_messages_per_day: int
    voice_calls_per_visitor_per_day: int
    site_daily_cap: int
    max_call_seconds: int
    #: Lo que consume una llamada publica, por componente (U17, tanda 2). Es la
    #: copia de `providers.yaml` que convierte una suposicion declarada en la
    #: reserva con la que se decide el cupo del dia y el modo de voz.
    call_usage: CallUsage
    #: Los minutos de grabacion apartados del techo (BR4.9), tal como los declara
    #: `providers.yaml`. En minutos y no en dolares: en dolares envejecerian mal.
    recording_minutes: int
    window_start: date = WINDOW_START

    def plan_for(self, use: Use) -> UsePlan:
        plan = self.plans.get(use)
        if plan is None:
            msg = (
                f"el uso '{use.value}' no tiene plan instalado: todo uso declara el suyo "
                "en configuracion versionada, y de esa marca depende el techo (BR3.6)"
            )
            raise LookupError(msg)
        return plan


#: Los alcances de cuota que **cuestan dinero**. Una sola tabla, tres
#: consecuencias: quien consulta el presupuesto, hacia donde cae el fallo, y que
#: limite rige. Anadir un alcance obliga a decidirlo aqui.
_ALCANCES_DE_PAGO: frozenset[QuotaScope] = frozenset(
    {QuotaScope.VOICE_CALLS_VISITOR_DAY, QuotaScope.VOICE_CALLS_SITE_DAY}
)

_runtime: SpendRuntime | None = None
_cola: asyncio.Queue[SpendEntry] | None = None
_tarea: asyncio.Task[None] | None = None
_fallos_diferidos = 0


def install(runtime: SpendRuntime) -> None:
    """Fija la configuracion de la contabilidad. La llama la raiz de composicion."""
    global _runtime
    _runtime = runtime


def current_runtime() -> SpendRuntime:
    if _runtime is None:
        msg = (
            "la contabilidad no esta instalada: la raiz de composicion llama a "
            "`install(...)` con la tabla de precios y los planes ya validados (C-24)"
        )
        raise LookupError(msg)
    return _runtime


def reset() -> None:
    """Devuelve el modulo a su estado inicial. Lo usan las pruebas.

    Sin esto, una prueba que instala su configuracion se la dejaria puesta a la
    siguiente, y la suite dejaria de poder correr en cualquier orden.
    """
    global _runtime, _cola, _tarea, _fallos_diferidos
    _runtime = None
    _cola = None
    _tarea = None
    _fallos_diferidos = 0


def _ahora(now: datetime | None) -> datetime:
    """El instante, inyectable. El cambio de dia y el de ventana son conducta."""
    return now if now is not None else datetime.now(UTC)


# --- La cola de lo no facturable ----------------------------------------------


def open_deferred_queue() -> None:
    """Abre la cola **sin** arrancar la tarea que la drena.

    Separada de `start_deferred_writer` por dos razones, y ninguna es de prueba:

    1. Abrir la cola y drenarla son dos decisiones distintas. Un proceso que
       abre la cola gana el diferimiento --la fila sale del camino de la
       respuesta-- y quien la vacia puede ser la tarea de fondo o el propio
       apagado.
    2. Que la cola no se drene sola **se puede observar**, en vez de depender de
       cuando el planificador decida darle el turno a una tarea. Lo que en una
       prueba es determinismo, en produccion es poder drenar a mano cuando la
       tarea murio.

    Sin cola abierta, la escritura no facturable es **sincrona**: es lo correcto
    para el corredor de evaluaciones y para una tarea de operacion, que no tienen
    turno que proteger.
    """
    global _cola
    if _cola is None:
        _cola = asyncio.Queue(maxsize=DEFERRED_QUEUE_CAPACITY)


def start_deferred_writer() -> None:
    """Abre la cola y arranca la tarea que la drena. La raiz, al arrancar."""
    global _tarea
    if _tarea is not None:
        return
    open_deferred_queue()
    cola = _cola
    if cola is not None:
        _tarea = asyncio.create_task(_drenar_siempre(cola))


async def stop_deferred_writer() -> None:
    """Escribe lo pendiente y cierra la tarea. La raiz, al apagarse.

    Se vacia **antes** de cerrar: un apagado que descartara filas tendria el
    mismo efecto que descartarlas al llenarse, que es justo lo que esta cola no
    hace. Y se vacia a mano en vez de esperar a la tarea, porque el apagado tiene
    que funcionar tambien cuando la tarea murio.
    """
    global _cola, _tarea
    tarea, cola, _tarea, _cola = _tarea, _cola, None, None
    if tarea is not None:
        tarea.cancel()
        try:
            await tarea
        except asyncio.CancelledError:
            pass
    if cola is not None:
        await _vaciar(cola)


def pending_deferred() -> int:
    """Cuantas filas no facturables esperan. Para la senal de salud y las pruebas."""
    return 0 if _cola is None else _cola.qsize()


def deferred_failures() -> int:
    """Cuantas filas diferidas no se pudieron escribir.

    Se **publica**, no se esconde: es la unica forma en que una fila de gasto
    puede perderse, y una cifra a la que le faltan filas tiene que decir cuantas.
    """
    return _fallos_diferidos


async def flush_deferred() -> int:
    """Escribe **ahora** todo lo que la cola tenga, y dice cuantas filas eran.

    No espera a la tarea de fondo: escribe. Es lo que usa el apagado y lo que
    permite comprobar que la fila diferida acaba en la base sin depender de
    cuando el planificador le de el turno a nadie.
    """
    if _cola is None:
        return 0
    return await _vaciar(_cola)


async def _vaciar(cola: asyncio.Queue[SpendEntry]) -> int:
    escritas = 0
    while True:
        try:
            entrada = cola.get_nowait()
        except asyncio.QueueEmpty:
            return escritas
        try:
            await _escribir_diferida(entrada)
            escritas += 1
        finally:
            cola.task_done()


async def _escribir_diferida(entrada: SpendEntry) -> None:
    """Una fila diferida, con su fallo contado y nunca propagado.

    No levanta: quien la llama es la tarea de fondo o el apagado, y en los dos
    sitios una excepcion dejaria las filas siguientes sin escribir sin que nada
    lo dijera.
    """
    global _fallos_diferidos
    try:
        await repository.record_non_billable(entrada)
    except Exception as error:  # noqa: BLE001 -- ver la razon de arriba
        _fallos_diferidos += 1
        observability.emit(
            "spend.deferred_write_failed",
            entry_id=entrada.entry_id,
            error=type(error).__name__,
        )


async def _drenar_siempre(cola: asyncio.Queue[SpendEntry]) -> None:
    """La tarea de fondo. Escribe lo que llegue y **nunca muere por un fallo**.

    Si muriera, las filas siguientes se quedarian en la cola sin que nada lo
    dijera, hasta llenarla; y con la cola llena cada escritura pasa a sincrona,
    de modo que el sintoma seria latencia en el chat y la causa estaria tres
    pasos atras. `_escribir_diferida` cuenta el fallo y sigue.
    """
    while True:
        entrada = await cola.get()
        try:
            await _escribir_diferida(entrada)
        finally:
            cola.task_done()


# --- Registrar un gasto -------------------------------------------------------


async def record_spend(  # noqa: PLR0913 -- la firma es el contrato C-17, no una eleccion
    *,
    provider: ProviderName,
    model: str,
    use: Use,
    units: Decimal | None,
    unit_kind: UnitKind,
    case_id: str | None = None,
    call_ref: CallRef | None = None,
    tenant_ref: str | None = None,
    source: SpendSource = SpendSource.PROVIDER_REPORTED,
    lane: BudgetLane = BudgetLane.PUBLIC,
    now: datetime | None = None,
) -> None:
    """Escribe lo que costo una llamada. **Nunca cero por falta de precio.**

    `units` admite `None` y no es lo mismo que cero: una llamada que salio y no
    volvio pudo haber consumido, y el adaptador no tiene recuento que reportar.
    Cero seria afirmar que no consumio nada, que es una cifra distinta y que
    ademas se sumaria como cierta.

    El carril facturable escribe **sincrono** y dentro de la transaccion que
    incrementa el acumulado (BR4.6); el no facturable va a la cola y no puede
    romper el turno.

    `call_ref` es la llamada de voz que produjo el gasto, cuando lo produjo una.
    Lo pasa quien abrio la llamada --el mismo identificador que ya recibe
    `reserve_primary_voice`-- y sirve para una sola cosa: que al cerrar la sesion
    se pueda preguntar si **esa sesion** dejo audio (BR5.5). Sin el, la pregunta
    solo se podria responder por caso, y un caso puede tener mas de una llamada.
    """
    runtime = current_runtime()
    plan = runtime.plan_for(use)
    momento = _ahora(now)

    if units is None:
        # La llamada existio y no se pudo valorar. La fila se escribe igual: sin
        # ella, el costo por caso quedaria por debajo del real y nadie lo
        # notaria. La clase de unidad no puede ir vacia --la columna es
        # obligatoria y su conjunto es cerrado-- asi que lo que esta fila afirma
        # es "esta llamada ocurrio y no se pudo valorar", no un recuento de cero.
        costo = pricing.PricedCost(cost=Money.not_measured())
        contadas = Decimal(0)
    else:
        costo = pricing.price_call(
            runtime.prices, provider=provider, model=model, unit_kind=unit_kind, units=units
        )
        contadas = units

    entrada = SpendEntry(
        entry_id=uuid4().hex,
        provider=provider,
        model=model,
        use=use,
        tenant_ref=tenant_ref,
        case_ref=case_id,
        call_ref=call_ref,
        units=contadas,
        unit_kind=unit_kind,
        unit_price_usd=costo.unit_price_usd,
        price_list_version=costo.price_list_version,
        price_list_effective_date=costo.price_list_effective_date,
        cost_usd=costo.cost.amount_usd,
        cost_status=costo.cost.status,
        billable=plan.billable,
        lane=lane,
        source=source,
        occurred_at=momento,
    )

    if plan.billable:
        await _escribir_facturable(entrada, now=momento, window_start=runtime.window_start)
        return
    await _encolar(entrada)


#: La clase de unidad de un ajuste. Un ajuste no cuenta nada --lleva cero unidades--, asi
#: que la clase no significa nada; la columna es obligatoria y su conjunto es cerrado,
#: y esta es la primera.
_UNIDAD_DE_UN_AJUSTE = UnitKind.INPUT_TOKENS


@dataclass(frozen=True)
class AdjustmentResult:
    """Lo que paso al anotar un ajuste: la fila, si se escribio, y el acumulado despues.

    `written` es falso cuando ese mismo ajuste ya estaba en el libro --es el reintento
    de un comando--: no se escribio nada y el acumulado no cambio. `spent_usd` es el
    acumulado de la ventana tras la escritura y es nulo cuando no hay nada nuevo que
    contar contra el techo (un reintento, o un uso que no factura).
    """

    entry: SpendEntry
    written: bool
    spent_usd: Decimal | None


def adjustment_id(  # noqa: PLR0913 -- las seis cosas que identifican un ajuste, por nombre
    *, provider: ProviderName, use: Use, model: str, amount_usd: Decimal, on: date, note: str
) -> SpendEntryId:
    """El identificador de un ajuste, **derivado** de lo que dice.

    No es opaco como el de una llamada: el mismo ajuste dicho dos veces tiene que ser
    el mismo asiento, porque es lo que hace que reintentar el comando no sume dos veces.
    El importe se normaliza para que `0.24` y `0.240` sean el mismo.
    """
    partes = (
        provider.value,
        use.value,
        model,
        format(amount_usd.normalize(), "f"),
        on.isoformat(),
        note.strip(),
    )
    huella = hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()[:40]
    return f"adj-{huella}"


def adjustment_entry(  # noqa: PLR0913 -- son los datos del asiento, no una eleccion
    *,
    provider: ProviderName,
    use: Use,
    amount_usd: Decimal,
    note: str,
    on: date,
    model: str | None = None,
) -> SpendEntry:
    """El asiento de un ajuste conciliado, armado y validado, sin escribir nada.

    Existe aparte de `record_adjustment` para poder **ensenar el asiento antes de
    escribirlo**: un ajuste no se borra (el libro no admite importes negativos), asi
    que quien lo anota quiere verlo antes.

    El modelo, si no se dice, es el que `providers.yaml` declara para el uso: el ajuste
    se suma al modelo que de verdad trabajaba, no a uno inventado para el.
    """
    plan = current_runtime().plan_for(use)
    if plan.provider is not provider:
        msg = (
            f"el uso '{use.value}' es de {plan.provider.value}, no de {provider.value}: "
            "un ajuste se anota donde se gasto"
        )
        raise ValueError(msg)
    modelo = model if model is not None else plan.model
    return SpendEntry(
        entry_id=adjustment_id(
            provider=provider, use=use, model=modelo, amount_usd=amount_usd, on=on, note=note
        ),
        provider=provider,
        model=modelo,
        use=use,
        units=Decimal(0),
        unit_kind=_UNIDAD_DE_UN_AJUSTE,
        cost_usd=amount_usd,
        cost_status=CostStatus.MEASURED,
        billable=plan.billable,
        source=SpendSource.RECONCILED_ADJUSTMENT,
        # Mediodia en UTC: el dia de la cifra no cambia con la zona de quien lo mire.
        occurred_at=datetime(on.year, on.month, on.day, 12, tzinfo=UTC),
        note=note.strip(),
    )


async def record_adjustment(entry: SpendEntry, *, now: datetime | None = None) -> AdjustmentResult:
    """Anota lo que el proveedor cobro y el libro no tiene: un ajuste conciliado.

    Es la **misma superficie** que escribe el resto del libro --la fila y el acumulado
    de la ventana en una transaccion, con el mismo plan por uso-- y no una sentencia
    suelta. Un ajuste de un uso facturable cuenta contra el techo, igual que lo habria
    hecho la llamada que no quedo anotada; si el libro no esta, esta funcion falla en
    vez de inventar un acumulado. Anotar dos veces el mismo ajuste (el mismo
    identificador) escribe una sola.
    """
    escritura = await repository.record_adjustment(
        entry, now=_ahora(now), window_start=current_runtime().window_start
    )
    if escritura.crossed_alert and escritura.window is not None:
        observability.emit(
            "spend.budget_alert_crossed",
            window_start=str(escritura.window.window_start),
            spent_usd=str(escritura.window.billable_spent_usd),
            alert_usd=str(escritura.window.alert_usd),
        )
    return AdjustmentResult(
        entry=entry,
        written=escritura.written,
        spent_usd=escritura.window.billable_spent_usd if escritura.window is not None else None,
    )


async def _escribir_facturable(entrada: SpendEntry, *, now: datetime, window_start: date) -> None:
    """La fila y el acumulado, en una transaccion. El fallo llega a quien llamo.

    No se atrapa nada: separar la fila del acumulado es exactamente lo que BR4.6
    prohibe, y callar el fallo dejaria el techo decidiendo con un numero que no
    incluye esta llamada.
    """
    escritura = await repository.record_billable(entrada, now=now, window_start=window_start)
    if escritura.crossed_alert:
        # La marca **ya esta escrita** en la base dentro de la misma transaccion:
        # esto emite el aviso, no decide si toca (BR4.3). El canal lo fija el
        # intent `infra` (PA-10).
        observability.emit(
            "spend.budget_alert_crossed",
            window_start=str(escritura.window.window_start),
            spent_usd=str(escritura.window.billable_spent_usd),
            alert_usd=str(escritura.window.alert_usd),
        )


async def _encolar(entrada: SpendEntry) -> None:
    """Fuera del camino de la respuesta, y sin descartar al llenarse.

    Esta funcion **no levanta**, y esa es la mitad del trato que el carril no
    facturable puede cumplir: ningun techo depende de esta fila, asi que su
    fallo no tiene por que romper el turno de nadie. Lo que si hace es contarlo.
    """
    if _cola is not None:
        try:
            _cola.put_nowait(entrada)
            return
        except asyncio.QueueFull:
            # Se paga latencia justo cuando la base va lenta, a cambio de no
            # perder la fila. Descartarla falsearia una cifra publicada.
            observability.emit(
                "spend.deferred_queue_full",
                capacity=DEFERRED_QUEUE_CAPACITY,
                entry_id=entrada.entry_id,
            )

    await _escribir_diferida(entrada)


# --- El presupuesto -----------------------------------------------------------


async def budget_state(*, now: datetime | None = None) -> BudgetState:
    """La foto del presupuesto, con tiempo maximo de sentencia (NFR-U5-3).

    Levanta `SpendUnavailableError` cuando la base no responde dentro de ese
    tiempo, en vez de esperar. Quien decide que hacer con eso es esta misma
    superficie: hacia fuera, un fallo de esta lectura se convierte en el rechazo
    de lo facturable y nunca en una excepcion.
    """
    runtime = current_runtime()
    try:
        async with repository.bounded_session(STATEMENT_TIMEOUT_MS) as sesion:
            ventana = await repository.load_window(runtime.window_start, en=sesion)
    except Exception as error:
        # Se atrapa **cualquier** fallo a proposito. Una lista de tipos conocidos
        # --tiempo agotado, conexion rechazada-- dejaria escapar el siguiente, y
        # este es el punto donde "el corte falla cerrado" tiene que valer para
        # todos los fallos y no para los que alguien se acordo de escribir. El
        # error no se traga: viaja como causa.
        observability.emit("spend.budget_read_failed", error=type(error).__name__)
        msg = (
            "no se pudo leer el presupuesto dentro de su tiempo maximo: la llamada "
            "facturable se rechaza y el chat sigue, porque no consume el techo"
        )
        raise SpendUnavailableError(msg) from error

    if ventana is None:
        msg = (
            f"no hay ninguna ventana de presupuesto que empiece el {runtime.window_start}: "
            "sin acumulado no hay techo que comprobar, y seguir seria gastar sin control"
        )
        raise SpendUnavailableError(msg)
    return budget.state(ventana)


def call_reserve(
    mode: VoiceMode = VoiceMode.PRIMARY, runtime: SpendRuntime | None = None
) -> CallReserve:
    """Lo que se supone que cuesta una llamada completa en ese modo.

    **La suma de sus tres componentes**: la transcripcion, que corre toda la
    llamada; la sintesis del modo, que es donde la voz de respaldo se abarata; y
    los tokens del modelo. Cada uno se valora con la tabla de precios y el consumo
    sale de `providers.yaml`, donde esta declarado con su razon.

    Hasta la tanda 2 de U17 esto preguntaba por el precio de los **segundos de
    audio del plan de la voz**, y ese plan es el del modelo, que se cobra por
    tokens: la linea no existe ni va a existir, asi que la reserva salia sin medir
    y el cupo del sitio salia cero. El enlace publico de voz no abria ninguna
    llamada, y lo hacia por una pregunta mal hecha y no por falta de presupuesto.

    **Si a cualquier componente le falta su linea, la reserva no se sabe.** No se
    suma lo medido ignorando el resto: una reserva incompleta es mas barata que la
    de verdad, y una reserva mas barata reparte mas llamadas de las que caben.
    """
    activo = runtime if runtime is not None else current_runtime()
    total = Decimal(0)
    for componente in activo.call_usage.components_for(mode):
        if componente.units == 0:
            # Cero unidades cuestan cero, haya precio o no: un componente que esta
            # llamada no consume no puede dejar la reserva sin medir. Es el caso de
            # un modo que no sintetiza, y el que deja declarar un consumo en cero
            # sin obligar a inventarle un precio.
            continue
        costo = pricing.price_call(
            activo.prices,
            provider=componente.provider,
            model=componente.model,
            unit_kind=componente.unit_kind,
            units=componente.units,
        )
        if costo.cost.amount_usd is None:
            return CallReserve(
                max_call_seconds=activo.max_call_seconds,
                reserve=Money.not_measured(),
                mode=mode,
            )
        total += costo.cost.amount_usd
    return CallReserve(
        max_call_seconds=activo.max_call_seconds, reserve=Money.measured(total), mode=mode
    )


def recording_reserve_usd(runtime: SpendRuntime | None = None) -> Money:
    """Los minutos de grabacion apartados, en dolares (BR4.9).

    Se declaran en minutos --en dolares envejecerian mal-- y se convierten aqui con
    la misma aritmetica que una llamada: los minutos valen tantas llamadas de
    duracion maxima como quepan, y cada una cuesta la reserva de la **voz
    principal**, porque el video se graba con la voz del producto y no con la de
    respaldo.

    Hasta la tanda 2 de U17 nadie convertia esos minutos: la fila de la ventana se
    sembraba con la reserva en nulo, y una reserva en nulo deja el restante publico
    sin medir, que cierra todo lo que cuesta dinero.
    """
    activo = runtime if runtime is not None else current_runtime()
    reserva = call_reserve(VoiceMode.PRIMARY, activo)
    if reserva.reserve.amount_usd is None:
        return Money.not_measured()
    llamadas = Decimal(activo.recording_minutes * 60) / Decimal(activo.max_call_seconds)
    return Money.measured(llamadas * reserva.reserve.amount_usd)


async def expected_voice_mode(
    *, lane: BudgetLane = BudgetLane.PUBLIC, now: datetime | None = None
) -> VoiceMode:
    """Con que voz se abriria una llamada **ahora**, sin abrir ninguna.

    Es lo que la consola necesita para avisar antes de apretar el boton: con la voz
    de respaldo, la agente puede sonar distinta. No emite el evento de decision
    --ese pertenece a una llamada de verdad y lleva su identificador-- y por eso no
    es `reserve_primary_voice` con un identificador inventado: un evento con un
    `call_id` que no existe ensucia el rastro de las llamadas que si existen.

    La politica es **la misma funcion** que la de la apertura, no una copia: si
    difirieran, la consola avisaria de una voz y sonaria la otra.

    **Cualquier** fallo de lectura responde respaldo, no solo el que U5 declara:
    es la misma razon por la que el techo se cierra ante cualquiera --aqui lo que
    esta en juego es dinero-- y esta respuesta va en una pantalla que se dibuja
    antes de saber si hay voz. Una lista de tipos conocidos dejaria escapar el
    siguiente y lo convertiria en un error de la pantalla entera.
    """
    try:
        estado = await budget_state(now=now)
        return quota.voice_mode(_restante_del_carril(estado, lane), call_reserve())
    except Exception as error:  # noqa: BLE001 -- cerrado ante la duda, como el techo
        observability.emit("spend.voice_mode_unreadable", error_type=type(error).__name__)
        return VoiceMode.FALLBACK


async def reserve_primary_voice(
    call_id: str, *, lane: BudgetLane = BudgetLane.PUBLIC, now: datetime | None = None
) -> VoiceMode:
    """Con que voz se abre la llamada, decidido **antes** y para toda ella (BR5.7).

    No escribe ninguna reserva: no hay tabla de reservas y no la hay a proposito
    (BR4.5 acepta el exceso de la llamada en vuelo en vez de una conciliacion por
    llamada). Lo que esta operacion hace es decidir el modo; fijarlo en la sesion
    es de quien la abre, porque cambiar de voz a mitad suena a fallo aunque sea
    un ahorro.

    Con el presupuesto ilegible, la respuesta es la voz de respaldo: cerrado para
    lo que cuesta dinero.
    """
    reserva = call_reserve()
    try:
        estado = await budget_state(now=now)
    except SpendUnavailableError:
        observability.emit(
            "spend.voice_mode_decided",
            call_id=call_id,
            lane=lane.value,
            mode=VoiceMode.FALLBACK.value,
            reason="budget_unreadable",
        )
        return VoiceMode.FALLBACK

    restante = _restante_del_carril(estado, lane)
    modo = quota.voice_mode(restante, reserva)
    observability.emit(
        "spend.voice_mode_decided", call_id=call_id, lane=lane.value, mode=modo.value
    )
    return modo


def _restante_del_carril(estado: BudgetState, lane: BudgetLane) -> Money:
    """Lo que queda **de ese carril**, que corren aparte (BR4.9, BR4.10)."""
    if lane is BudgetLane.RECORDING:
        return estado.recording_remaining_usd
    return estado.public_remaining_usd


# --- Las cuotas ---------------------------------------------------------------


async def check_quota(
    scope: QuotaScope,
    subject_key: SubjectKey,
    *,
    now: datetime | None = None,
    period_start: datetime | None = None,
) -> QuotaDecision:
    """Si este sujeto puede hacer una mas, **y la consume si puede** (BR5.1, BR5.4).

    Consultar y consumir son un solo acto: entre los dos habria un hueco por el
    que dos peticiones del mismo visitante pasarian las dos, que es el escenario
    RT-13.

    Una negacion es siempre un **valor**, nunca una excepcion (BR5.3): un rechazo
    que llegara como excepcion se convertiria en un error generico en la
    pantalla.

    `period_start` es obligatorio para el alcance de sesion --su periodo es la
    sesion, y solo quien la abrio sabe cuando empezo-- e ignorado en los tres
    diarios, cuyo periodo sale de la medianoche de la zona configurada.
    """
    runtime = current_runtime()
    momento = _ahora(now)
    de_pago = scope in _ALCANCES_DE_PAGO

    estado: BudgetState | None = None
    if de_pago:
        try:
            estado = await budget_state(now=momento)
        except SpendUnavailableError:
            # Cerrado para lo que cuesta dinero (NFR-U5-3).
            return quota.budget_exhausted()
        if estado.status in (BudgetStatus.EXHAUSTED, BudgetStatus.UNMEASURED):
            return quota.budget_exhausted()

    periodo = _periodo(scope, runtime, momento, period_start, estado)

    try:
        contador = await repository.consume_quota(scope, subject_key, periodo, now=momento)
    except Exception as error:  # noqa: BLE001 -- ver la razon de abajo
        # La otra mitad de NFR-U5-3, y la unica rama de este archivo que decide
        # por el carril: cerrado donde hay dinero, **abierto** donde no lo hay.
        # Apagar el chat gratuito porque no se pudo contar un mensaje no protege
        # nada y apaga lo unico que seguiria vivo con la base caida.
        observability.emit("spend.quota_read_failed", scope=scope.value, error=type(error).__name__)
        if de_pago:
            return quota.budget_exhausted()
        return QuotaDecision(allowed=True)

    if contador is None:
        return quota.decide(
            scope,
            count=periodo.limit,
            limit=periodo.limit,
            now=momento,
            zone=runtime.zone,
        )
    return QuotaDecision(allowed=True)


@dataclass(frozen=True)
class QuotaState:
    """Lo que un contador dice **ahora**, sin tocarlo.

    Existe para la respuesta de disponibilidad, que es un `GET` y no crea ni
    consume nada: un navegador que solo mira no puede gastarle a nadie su llamada
    del dia. Quien va a abrir la llamada no usa esto, usa `check_quota`, que
    consulta y consume en un solo acto (RT-13).
    """

    count: int
    limit: int

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.count)


async def quota_state(
    scope: QuotaScope, subject_key: SubjectKey | None, *, now: datetime | None = None
) -> QuotaState:
    """Cuanto lleva contado ese sujeto y cuanto admite su periodo, sin consumir.

    `subject_key` en nulo es "todavia no hay sujeto": un navegador que nunca
    escribio no tiene contador, asi que lo contado es cero y lo que interesa es el
    limite. Devolver el limite igual es lo que permite a la consola decir cuantas
    llamadas tendra **antes** de la primera.

    El limite del alcance del sitio **no es un numero fijo**: se deriva del
    presupuesto que queda y los dias que faltan (BR5.6), asi que esta lectura pasa
    por el mismo `_periodo` que la consumidora. Leerlo de otro sitio daria una
    pantalla que promete un cupo distinto del que la apertura va a aplicar.
    """
    runtime = current_runtime()
    momento = _ahora(now)
    estado: BudgetState | None = None
    if scope in _ALCANCES_DE_PAGO:
        estado = await budget_state(now=momento)

    periodo = _periodo(scope, runtime, momento, None, estado)
    if subject_key is None:
        return QuotaState(count=0, limit=periodo.limit)

    clave = derive_counter_key(scope, subject_key, periodo.period_start)
    contador = await repository.load_counter(clave)
    return QuotaState(count=0 if contador is None else contador.count, limit=periodo.limit)


def _periodo(
    scope: QuotaScope,
    runtime: SpendRuntime,
    now: datetime,
    period_start: datetime | None,
    estado: BudgetState | None,
) -> QuotaPeriod:
    """El periodo abierto y **con que limite se abrio** (BR5.2, BR5.6, FD-U5-10).

    El limite se escribe en el contador junto al periodo, y no solo se calcula:
    el cupo del sitio se recalcula cada dia, asi que un rechazo de hace un mes
    solo se puede explicar con el numero que de verdad regia entonces.
    """
    if scope is QuotaScope.CHAT_MESSAGES_SESSION:
        if period_start is None:
            msg = (
                "el alcance de sesion necesita cuando empezo la sesion: su periodo es "
                "la sesion, no el dia, y solo quien la abrio lo sabe"
            )
            raise ValueError(msg)
        return QuotaPeriod(period_start=period_start, limit=runtime.chat_messages_per_session)

    comienzo = quota.day_period_start(now, runtime.zone)
    if scope is QuotaScope.CHAT_MESSAGES_DAY:
        return QuotaPeriod(period_start=comienzo, limit=runtime.chat_messages_per_day)
    if scope is QuotaScope.VOICE_CALLS_VISITOR_DAY:
        return QuotaPeriod(period_start=comienzo, limit=runtime.voice_calls_per_visitor_per_day)

    # El cupo del sitio no es un numero fijo: se deriva del presupuesto publico
    # que queda y los dias que faltan (BR5.6). Un cupo fijo se llevaria el
    # presupuesto en un dia bueno y dejaria sin voz los ochenta y nueve
    # siguientes.
    if estado is None:  # pragma: no cover -- el alcance del sitio es de pago
        msg = "el cupo del sitio se deriva del presupuesto y no se pudo leer"
        raise SpendUnavailableError(msg)
    cupo = quota.site_daily_quota(
        estado.public_remaining_usd,
        days_left=quota.days_remaining(now.astimezone(runtime.zone).date(), estado.window_end),
        # **Con la reserva de la voz de respaldo**, que es la barata: lo que el
        # cupo responde es "cuantas llamadas caben hoy", y mientras quepa una con
        # la voz de respaldo el enlace sigue vivo. Con la de la principal, el
        # enlace se cerraba justo cuando el modo de respaldo existe para
        # mantenerlo abierto.
        call_reserve=call_reserve(VoiceMode.FALLBACK, runtime),
        site_daily_cap=runtime.site_daily_cap,
    )
    return QuotaPeriod(period_start=comienzo, limit=cupo)


async def release_call_quota(
    call_ref: CallRef,
    *,
    visitor_subject_key: SubjectKey | None = None,
    opened_at: datetime,
    lane: BudgetLane = BudgetLane.PUBLIC,
    now: datetime | None = None,
) -> QuotaRelease:
    """Cerrada la llamada, devuelve el cupo si no se gasto (BR5.5, F4).

    El cupo del dia se consume al **abrir** (BR5.4), porque contar al terminar
    dejaria pasar diez pestanas a la vez (RT-13). Esta es la otra mitad de esa
    decision: una caida de red antes del primer turno no le puede quitar el dia
    al visitante.

    **Se pregunta al registro de gasto, nunca a la consola.** La consola es de
    quien llama, asi que un cliente que mintiera se devolveria a si mismo el cupo
    de una llamada que si se pago. Lo que decide es si esa llamada dejo alguna
    fila de audio con unidades mayores que cero.

    **Es idempotente**, y no por prudencia: U16 cierra la sesion siempre, tambien
    cuando la llamada se cae, asi que el doble cierre es el caso normal. El
    segundo responde `ALREADY_DECIDED` y no toca ningun contador.

    `opened_at` es cuando se abrio la llamada, y de ahi sale el periodo de los
    contadores que hay que devolver. No se usa el reloj de ahora: una llamada que
    empieza a las 23:58 y se cae a las 00:03 devuelve el cupo al dia que se lo
    llevo.

    **El carril de grabacion no devuelve nada**, porque no tomo nada: sus
    llamadas no pasan por el cupo del sitio ni por el del visitante (F3 paso 4).
    Si esta operacion decrementara igual, una llamada de grabacion le regalaria
    al enlace publico un cupo que nadie del enlace publico gasto, y ese cupo es
    presupuesto. Por eso el carril entra por argumento en vez de darse por
    supuesto: quien cierra la sesion sabe con cual se abrio.

    **Nunca levanta por un fallo de ejecucion.** Con la base caida el cupo no se
    devuelve y se dice (`UNAVAILABLE`), en vez de romper el cierre de la sesion
    de quien llama: la devolucion es una cortesia con el visitante, y una
    cortesia no puede ser un punto de fallo del camino que apaga la llamada. Lo
    que si rechaza en el acto es una llamada **mal formada** --el carril publico
    sin el sujeto cuyo cupo devolver--, porque eso no es una condicion de
    ejecucion sino un error de quien llama, y tragarselo devolveria en silencio
    el cupo de nadie.
    """
    runtime = current_runtime()
    momento = _ahora(now)

    if lane is BudgetLane.RECORDING:
        observability.emit(
            "spend.call_quota_decided", call_ref=call_ref, outcome=ReleaseOutcome.NOT_HELD.value
        )
        return QuotaRelease(call_ref=call_ref, outcome=ReleaseOutcome.NOT_HELD)

    if visitor_subject_key is None:
        msg = (
            f"la llamada '{call_ref}' es del carril publico y no dice de quien devolver "
            "el cupo: el sujeto es el resumen de la clave del navegador que la abrio "
            "(BR7.3), y sin el no hay contador del visitante que decrementar"
        )
        raise ValueError(msg)

    periodo = quota.day_period_start(opened_at, runtime.zone)

    try:
        resultado = await repository.release_call_quota(
            call_ref,
            visitor_subject_key=visitor_subject_key,
            period_start=periodo,
            now=momento,
        )
    except Exception as error:  # noqa: BLE001 -- ver "Nunca levanta", arriba
        observability.emit(
            "spend.call_quota_release_failed", call_ref=call_ref, error=type(error).__name__
        )
        resultado = ReleaseOutcome.UNAVAILABLE

    observability.emit("spend.call_quota_decided", call_ref=call_ref, outcome=resultado.value)
    return QuotaRelease(call_ref=call_ref, outcome=resultado)
