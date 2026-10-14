"""Los tipos del dinero y de las cuotas: la factura del proyecto.

Cuatro entidades se guardan --el registro de gasto, los contadores de cuota, el
acumulado de la ventana y el resumen de traza, este ultimo en `traces/models.py`
porque es dato de un visitante-- y el resto son valores que se devuelven y no se
persisten.

Este modulo es una **hoja**: no importa el repositorio ni la sesion. Es lo que
permite probar la aritmetica del techo y del cupo sin levantar un contenedor, y
es la razon por la que los pasos 7 a 9 de esta unidad son funciones puras.

**Lo que ya no vive aqui.** `Use`, `ProviderName`, `UnitKind`, `SpendSource`,
`ProviderErrorKind` y la regla de la coma flotante con `UnitCount` subieron a
`untangle/base.py` en el bloque F: no son vocabulario de la contabilidad sino
del aplicativo, los escriben tambien el adaptador y la traza, y tenerlos aqui
obligaba a `providers/ports.py` --lo que ven seis unidades-- a importar
`telemetry/`. Lo que se queda es el dinero, que si es de este modulo.

Tres invariantes cargan casi todo el peso, y las tres estan aqui:

1. **El costo viaja con su estado** (BR3.9). `Money` es el par, no dos campos que
   alguien recuerde escribir juntos. La consecuencia practica es que la forma de
   registrar cero por falta de precio **no esta disponible**: hay que elegir
   `NOT_MEASURED` a proposito, que es justo lo que BR3.3 exige.
2. **El dinero es decimal exacto y el tipo rechaza la coma flotante** en la
   construccion, no en un comentario. Con coma flotante, sumar veinte fracciones
   de centavo da un total que depende del orden en que se sumaron: el techo
   cortaria en un punto distinto segun el orden de las llamadas y la cifra
   publicada dejaria de ser reproducible desde el mismo commit
   (`nfr-requirements/tech-stack-decisions.md`).
3. **Toda agregacion devuelve `SpendTotal`** (BR3.5): el total medido y cuantas
   llamadas no se pudieron medir. Publicar el primero sin el segundo exige
   desarmar el tipo a proposito.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BeforeValidator, Field, model_validator

from untangle.base import (
    Frozen,
    ProviderName,
    SpendSource,
    UnitCount,
    UnitKind,
    Use,
    reject_float,
)

# --- Identificadores ----------------------------------------------------------

#: La fila del libro mayor. Opaco: no se deriva de nada y no significa nada.
type SpendEntryId = str

#: La clave de un contador de cuota. **Se deriva** de alcance, sujeto y comienzo
#: del periodo (ver `derive_counter_key`), porque dos contadores del mismo
#: alcance y sujeto en el mismo periodo tienen que ser uno solo.
type CounterKey = str

#: El resumen de la clave del navegador, nunca la clave (BR7.3). Guardar la clave
#: permitiria suplantar al visitante con lo que hay en la base.
type SubjectKey = str

#: La llamada de voz que produjo un gasto. Es el mismo identificador que C-17 ya
#: nombra en `reserve_primary_voice(call_id)`: no es un dato nuevo, es el que
#: hasta ahora no se guardaba.
#:
#: Sin el, la pregunta que F4 le hace al registro de gasto --"¿dejo **esta
#: sesion** alguna fila de audio?"-- no se puede responder: el caso no alcanza,
#: porque un caso puede tener mas de una llamada y la fila de un dia anterior
#: contestaria por la de hoy.
type CallRef = str

#: El sujeto del cupo del sitio. El cupo del sitio no es de nadie, asi que no
#: tiene resumen de nada: lleva este literal.
SITE_SUBJECT: SubjectKey = "site"

#: La ventana vigente empieza aqui (D11). Es acumulada de noventa dias y nunca
#: mensual: con un contador que se reinicia cada mes, el techo no protege nada.
WINDOW_START = date(2026, 9, 16)

#: Cuanto dura una ventana. `BudgetWindow` comprueba que su fin sea exactamente
#: esto despues de su comienzo, para que no existan dos ventanas de largos
#: distintos que despues nadie sepa comparar.
WINDOW_DAYS = 90

#: Cuanto cabe en la nota de un asiento de ajuste. Es el tope de la columna: una
#: tabla que no guarda nada personal solo admite texto acotado (BR7.2).
MAX_ADJUSTMENT_NOTE = 200


# --- Dinero exacto ------------------------------------------------------------
# La regla --ni el dinero ni las unidades se escriben en coma flotante-- vive en
# `untangle/base.py` porque la comparten el adaptador, que reporta unidades, y
# esta contabilidad, que las valora. Aqui se queda el importe, que si es de este
# modulo.

#: Un importe en dolares. Nunca negativo, nunca en coma flotante.
UsdAmount = Annotated[Decimal, BeforeValidator(reject_float), Field(ge=0)]


# --- Enums cerrados -----------------------------------------------------------
# Los cuatro que hablan los dos lados de una llamada --`Use`, `ProviderName`,
# `UnitKind` y `SpendSource`-- viven en `untangle/base.py`. Los de abajo son de
# la contabilidad y de nadie mas: nadie fuera de este modulo decide que es un
# costo no medido ni de que carril sale una llamada.


class CostStatus(StrEnum):
    """Si el costo se pudo valorar (BR3.3, BR3.9).

    `NOT_MEASURED` no es cero y no se colapsa con el: un cero por falta de precio
    contamina una cifra publicada con un fallo de configuracion, que es la misma
    confusion que el proyecto prohibe entre "no hay clausula" y "no pude
    verificar".
    """

    MEASURED = "measured"
    NOT_MEASURED = "not_measured"


class BudgetLane(StrEnum):
    """De que carril del presupuesto sale una llamada (BR4.9, BR4.10).

    `RECORDING` solo lo puede pedir quien entra con credencial de la aseguradora.
    Una marca que el visitante pudiera poner convertiria la reserva en
    presupuesto publico con otro nombre, y la vaciaria el primer dia.
    """

    PUBLIC = "public"
    RECORDING = "recording"


class QuotaScope(StrEnum):
    """Los cuatro alcances de cuota, y solo cuatro (BR5.1)."""

    CHAT_MESSAGES_SESSION = "chat_messages_session"
    CHAT_MESSAGES_DAY = "chat_messages_day"
    VOICE_CALLS_VISITOR_DAY = "voice_calls_visitor_day"
    VOICE_CALLS_SITE_DAY = "voice_calls_site_day"


#: Los alcances cuyo periodo es un dia natural. Se declara como conjunto y no
#: como comparacion suelta para que anadir un alcance obligue a decidir aqui si
#: su periodo es diario, en vez de olvidarlo en un `if` a mitad de un archivo.
DAILY_SCOPES: frozenset[QuotaScope] = frozenset(
    {
        QuotaScope.CHAT_MESSAGES_DAY,
        QuotaScope.VOICE_CALLS_VISITOR_DAY,
        QuotaScope.VOICE_CALLS_SITE_DAY,
    }
)


#: Que clases de unidad son **el audio de una llamada** (BR5.5).
#:
#: Dos y no una. `AUDIO_SECONDS` es lo que cobra la transcripcion y `CHARACTERS`
#: lo que cobra la sintesis, y las dos son audio que el visitante oyo o dijo: una
#: llamada en la que solo sono el saludo grabado **costo dinero**, asi que su
#: cupo no se devuelve. Contar solo los segundos devolveria el cupo de una
#: llamada que ya se habia pagado.
#:
#: Se declara como conjunto para que una clase nueva obligue a decidir aqui si es
#: audio, en vez de olvidarse dentro de una consulta.
AUDIO_UNIT_KINDS: frozenset[UnitKind] = frozenset({UnitKind.AUDIO_SECONDS, UnitKind.CHARACTERS})


class QuotaReason(StrEnum):
    """Por que se nego una cuota (BR5.3).

    Cuatro motivos y solo cuatro. Un rechazo que llegara como excepcion se
    convertiria en un error generico en la pantalla, que es justo lo que FR4.6
    prohibe. C-08 anade ademas `provider_unavailable`, que no es una cuota y no
    se decide aqui.
    """

    RATE_LIMITED_SESSION = "rate_limited_session"
    RATE_LIMITED_DAILY = "rate_limited_daily"
    RATE_LIMITED_SITE = "rate_limited_site"
    BUDGET_EXHAUSTED = "budget_exhausted"


class BudgetStatus(StrEnum):
    """Los cuatro estados del **carril publico**, que es el que ve un visitante.

    No se guardan: se derivan del acumulado, de la marca de alerta y de si la
    reserva de grabacion se pudo calcular. Guardarlos abriria la posibilidad de
    que el estado y el numero se contradigan.

    `EXHAUSTED` con reserva de grabacion disponible es un estado normal y
    esperado (BR4.10): el carril publico esta cerrado y el de grabacion no.
    """

    OK = "ok"
    ALERTED = "alerted"
    EXHAUSTED = "exhausted"
    #: El presupuesto publico restante **no se puede calcular**, por cualquiera
    #: de sus dos sumandos: la reserva de grabacion sin medir, o una llamada
    #: facturable que no se pudo valorar y que por tanto deja el acumulado corto
    #: (decision del 2026-09-21). No es `EXHAUSTED`: "se gasto todo" y "no se
    #: pudo saber cuanto queda" son cosas distintas, y colapsarlas es el mismo
    #: error que el proyecto ya se prohibio entre "no hay clausula" y "no pude
    #: verificar" (convencion 8c del equipo). Con `EXHAUSTED` el panel diria
    #: "presupuesto agotado" sin que se hubiera gastado nada, y esa es una de
    #: las cinco cifras que el proyecto publica. Cual de las dos causas fue se
    #: lee en la propia foto: `recording_reserve_usd` sin medir senala la
    #: primera, y `spent.unmeasured_count` mayor que cero la segunda.
    #:
    #: **La primera causa se lee en la reserva y no en `recording_remaining_usd`**,
    #: y eso cambio el 2026-09-21 con el conteo propio del carril de grabacion:
    #: desde entonces ese restante tambien se queda sin numero por una llamada de
    #: grabacion sin valorar, asi que mirarlo ya no distingue nada. La reserva si,
    #: porque tiene una sola forma de quedarse sin numero.
    #:
    #: **La conducta es la misma que con `EXHAUSTED`** y eso es a proposito
    #: (NFR-U5-3, respuesta Q5 de `nfr-requirements`): cerrado para lo que cuesta
    #: dinero, abierto para lo que no. Lo que cambia es lo que se dice, no lo que
    #: se hace.
    UNMEASURED = "unmeasured"


class SpendActivity(StrEnum):
    """En que se fue el gasto, como lo entiende quien mira la telemetria (2026-10-09).

    No es el `Use`: el uso decide la clave y el plan, y una llamada de voz gasta en
    tres usos --transcripcion, voz y el modelo que entiende--. Lo que una persona
    quiere saber es cuanto costaron las llamadas, cuanto el chat y cuanto las
    pruebas. Lo deriva la consulta, con la regla escrita en `repository.ACTIVIDAD`.
    """

    CALLS = "calls"
    CHAT = "chat"
    QUALITY_TESTS = "quality_tests"
    POLICY_READING = "policy_reading"
    OPERATIONS = "operations"


class VoiceMode(StrEnum):
    """Con que voz se atiende la llamada (BR5.7).

    Se decide antes de abrir y no cambia a mitad: cambiar de voz a mitad de
    llamada suena a fallo, aunque sea un ahorro.
    """

    PRIMARY = "primary"
    FALLBACK = "fallback"


# --- Objetos de valor ---------------------------------------------------------


class Money(Frozen):
    """Una cantidad de dinero **y si se midio**. El par es el tipo (BR3.4).

    No existe un costo suelto en esta unidad. Es lo que impide que "no se pudo
    valorar" se escriba como cero y despues se sume como si fuera cierto.
    """

    amount_usd: UsdAmount | None = None
    status: CostStatus

    @model_validator(mode="after")
    def _la_cantidad_acompana_al_estado(self) -> Self:
        if self.status is CostStatus.MEASURED and self.amount_usd is None:
            msg = (
                "un costo 'measured' tiene que traer su cantidad; si no se pudo "
                "valorar, el estado es 'not_measured' y la cantidad va ausente"
            )
            raise ValueError(msg)
        if self.status is CostStatus.NOT_MEASURED and self.amount_usd is not None:
            msg = (
                f"un costo 'not_measured' no lleva cantidad, y llego {self.amount_usd}; "
                "escribir cero por falta de precio es lo que BR3.3 prohibe"
            )
            raise ValueError(msg)
        return self

    @classmethod
    def measured(cls, amount_usd: Decimal) -> Money:
        """Un costo que se pudo valorar."""
        return cls(amount_usd=amount_usd, status=CostStatus.MEASURED)

    @classmethod
    def not_measured(cls) -> Money:
        """Un costo que no se pudo valorar. **No** es cero."""
        return cls(amount_usd=None, status=CostStatus.NOT_MEASURED)

    @property
    def is_measured(self) -> bool:
        return self.status is CostStatus.MEASURED


class SpendTotal(Frozen):
    """Lo que devuelve **toda** agregacion de costo de esta unidad (BR3.5).

    Lleva dentro el conteo de llamadas no medidas, asi que publicar el total sin
    decir cuanto no se midio exige desarmar el tipo a proposito.
    """

    measured_usd: UsdAmount
    unmeasured_count: int = Field(ge=0)

    def __add__(self, otro: SpendTotal) -> SpendTotal:
        """Dos parciales se suman como parciales: los dos lados, no solo uno."""
        return SpendTotal(
            measured_usd=self.measured_usd + otro.measured_usd,
            unmeasured_count=self.unmeasured_count + otro.unmeasured_count,
        )


#: Las clases de unidad que son **tokens**. Los embeddings de Gemini se registran
#: como entrada, pero la clase propia existe y se cuenta igual si un adaptador la
#: escribe un dia: la lista vive aqui para que sea un solo sitio.
TOKEN_UNIT_KINDS: frozenset[UnitKind] = frozenset(
    {UnitKind.INPUT_TOKENS, UnitKind.OUTPUT_TOKENS, UnitKind.EMBEDDING_TOKENS}
)


class UnpricedUsage(Frozen):
    """Lo que consumieron las llamadas **sin precio publicado**, en tokens (2026-10-11).

    Existe porque "sin precio" no es "sin dato": el proveedor reporta cuantos
    tokens conto aunque la tabla de precios no tenga la linea de ese modelo. Viaja
    **al lado** de `SpendTotal` y no dentro, porque ese tipo lo consume la cuenta
    del techo y esto es solo para mostrar: nada de aqui suma contra el presupuesto.

    - `tokens`: los de las llamadas sin precio que traen recuento.
    - `uncounted`: cuantas llamadas sin precio **no** traen recuento de tokens (el
      proveedor no lo reporto, o la unidad no es de tokens). De ellas no se sabe
      nada, y por eso no suman a `tokens`.
    - `free_plan`: todas las llamadas sin precio --traigan recuento o no-- son de un
      uso en plan gratuito (`billable` en falso). Con una sola de pago, o sin
      ninguna, es falso: la pantalla solo dice "plan gratuito" cuando el dato lo
      respalda. Cubre tambien las que no traen recuento porque es el caso real: el
      servicio de vectores de Google no reporta tokens (comprobado el 2026-10-11),
      y de esas lo que se puede decir con verdad es cuantas fueron y que no cuestan.
    """

    tokens: int = Field(default=0, ge=0)
    uncounted: int = Field(default=0, ge=0)
    free_plan: bool = False

    def __add__(self, otro: UnpricedUsage) -> UnpricedUsage:
        """Dos parciales: gratuito solo si todo lo que no tiene precio lo es."""
        vacio_a = self.tokens == 0 and self.uncounted == 0
        vacio_b = otro.tokens == 0 and otro.uncounted == 0
        return UnpricedUsage(
            tokens=self.tokens + otro.tokens,
            uncounted=self.uncounted + otro.uncounted,
            free_plan=not (vacio_a and vacio_b)
            and (self.free_plan or vacio_a)
            and (otro.free_plan or vacio_b),
        )


class PriceEntry(Frozen):
    """Una linea de la tabla versionada de precios de lista (BR3.2).

    Vive en configuracion versionada y no en una tabla: cambiar un precio es un
    cambio de codigo que queda en el historial y dispara la compuerta de
    evaluaciones, porque mueve una cifra publicada.
    """

    provider: ProviderName
    model: str
    unit_kind: UnitKind
    unit_price_usd: UsdAmount
    list_version: str
    effective_date: date


class BudgetState(Frozen):
    """La foto del presupuesto que consumen la consola de voz, el chat y el gasto.

    Los dos restantes corren aparte a proposito (BR4.9): el publico es lo que un
    visitante puede consumir, y el de grabacion existe para que un dia de trafico
    en el enlace publico no deje al proyecto sin presupuesto para grabar el video
    de la semana doce.
    """

    window_start: date
    window_end: date
    #: El acumulado de **los dos carriles**, con cuantas llamadas facturables no
    #: se pudieron valorar (BR3.5).
    spent: SpendTotal
    cap_usd: UsdAmount
    alert_usd: UsdAmount
    #: La reserva apartada, tal como la fila la guarda. Esta en la foto porque
    #: es **una de las dos causas** por las que un restante se queda sin numero,
    #: y las dos tienen que poder distinguirse sin volver a la base: una reserva
    #: ilegible deja sin numero a los dos carriles a la vez, mientras que una
    #: llamada sin valorar deja sin numero al carril del que salio. Sin este
    #: campo, "no se pudo calcular" no diria cual de las dos fue.
    recording_reserve_usd: Money
    #: Lo gastado en el carril de grabacion, con **su propio** conteo de
    #: llamadas sin valorar. Es el otro lado de la distincion de arriba: con el
    #: conteo en cero, un restante de grabacion sin numero solo puede venir de
    #: la reserva.
    recording_spent: SpendTotal
    #: Los dos restantes viajan como **par**, no como decimal suelto, por la
    #: misma razon que el costo (BR3.9): un decimal no puede decir "no medido".
    #: Los dos salen de restar la reserva de grabacion, y esa reserva se declara
    #: en minutos y se convierte con la tabla de precios, que hoy no publica el
    #: precio por minuto de la voz. Con un decimal suelto, ese hueco se
    #: escribiria como `0.00` y el panel diria "no queda nada" cuando lo cierto
    #: es "no se pudo saber cuanto queda".
    public_remaining_usd: Money
    recording_remaining_usd: Money
    status: BudgetStatus


class QuotaDecision(Frozen):
    """La respuesta a "puede este sujeto hacer esto ahora" (BR5.3).

    Es un valor, nunca una excepcion: una negacion es una respuesta normal.
    """

    allowed: bool
    reason_code: QuotaReason | None = None
    retry_after_seconds: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _una_negacion_dice_por_que(self) -> Self:
        if not self.allowed and self.reason_code is None:
            msg = (
                "una cuota negada tiene que traer su motivo de la lista cerrada; "
                "sin el, el rechazo llega a la pantalla como un error generico"
            )
            raise ValueError(msg)
        if self.allowed and self.reason_code is not None:
            msg = f"una cuota permitida no lleva motivo, y llego '{self.reason_code}'"
            raise ValueError(msg)
        if (
            self.reason_code is QuotaReason.BUDGET_EXHAUSTED
            and self.retry_after_seconds is not None
        ):
            msg = (
                "el techo no tiene cuando: decirle a quien llama que reintente en "
                "unos segundos seria mentirle, porque el acumulado solo sube"
            )
            raise ValueError(msg)
        return self


class ReleaseOutcome(StrEnum):
    """Que paso al cerrar la llamada y preguntar por su cupo (BR5.5).

    Cuatro valores cerrados, y los cuatro son **respuestas**: devolver el cupo o
    no devolverlo son conductas normales, y no poder decidirlo tambien lo es.
    Ninguna sale como excepcion, por la misma razon que una negacion de cuota no
    sale como excepcion (BR5.3).
    """

    #: La llamada no dejo audio facturable y el cupo se devolvio.
    RETURNED = "returned"
    #: La llamada dejo audio facturable: el cupo se gasto y no se toca.
    BILLABLE_AUDIO = "billable_audio"
    #: Esta llamada ya se habia cerrado antes. Lo que esta operacion hace la
    #: segunda vez es **nada**, y eso es lo que la hace idempotente: quien cierra
    #: la sesion la cierra siempre, tambien cuando la llamada se cae, asi que el
    #: doble cierre es el caso normal y no el raro.
    ALREADY_DECIDED = "already_decided"
    #: No se pudo decidir --la base no respondio--. El cupo **no** se devuelve, y
    #: reintentar es seguro: la marca de decision no quedo escrita, y si hubiera
    #: quedado el reintento veria `ALREADY_DECIDED`.
    UNAVAILABLE = "unavailable"
    #: La llamada nunca tomo cupo, asi que no hay nada que devolver. Es el carril
    #: de grabacion: no pasa por el cupo del sitio ni por el del visitante (F3
    #: paso 4), y devolverle uno le regalaria al enlace publico una llamada que
    #: nadie del enlace publico hizo.
    NOT_HELD = "not_held"


class QuotaRelease(Frozen):
    """La respuesta a "¿se devuelve el cupo de esta llamada?" (BR5.5).

    Lleva la llamada dentro para que quien la registre no tenga que volver a
    juntarla con su identificador: es el mismo motivo por el que la decision de
    cuota lleva su motivo.
    """

    call_ref: CallRef
    outcome: ReleaseOutcome

    @property
    def released(self) -> bool:
        """Si **esta** llamada devolvio el cupo.

        Solo el primer cierre puede devolverlo. Un segundo cierre responde que ya
        estaba decidido, y esa respuesta no es un fallo.
        """
        return self.outcome is ReleaseOutcome.RETURNED


class PricedUnits(Frozen):
    """Un consumo que la tabla de precios puede valorar: que, de quien, y cuanto."""

    provider: ProviderName
    model: str
    unit_kind: UnitKind
    units: Decimal


class CallUsage(Frozen):
    """Lo que consume una llamada publica de duracion maxima, por componente.

    Es la copia que la contabilidad recibe de `providers.yaml` --`telemetry` esta
    debajo de `providers` en el contrato de capas-- y lo que convierte una
    suposicion declarada en un numero: cada componente se valora con la tabla de
    precios y la reserva es la suma.

    **La sintesis entra dos veces, una por modo**, y esa es la diferencia que hace
    util la voz de respaldo: con el presupuesto justo, el cupo del sitio se calcula
    con la voz barata y el enlace sigue vivo en vez de cerrarse.
    """

    transcription: PricedUnits
    synthesis_primary: PricedUnits
    synthesis_fallback: PricedUnits
    model_input: PricedUnits
    model_output: PricedUnits

    def components_for(self, mode: VoiceMode) -> tuple[PricedUnits, ...]:
        """Los tres consumos de una llamada en ese modo, en orden de peso."""
        sintesis = self.synthesis_primary if mode is VoiceMode.PRIMARY else self.synthesis_fallback
        return (self.transcription, sintesis, self.model_input, self.model_output)


class CallReserve(Frozen):
    """Lo que se supone que cuesta una llamada completa (BR5.6, BR5.7).

    Es lo que divide el presupuesto restante para sacar el cupo del sitio y lo
    que decide si la voz principal cabe.

    La reserva es `Money` y no un decimal suelto porque **puede no estar
    medida**: se suma de tres componentes --transcripcion, sintesis y modelo-- y
    si a cualquiera le falta su linea en la tabla, la suma no se sabe. Sin el par,
    esa ausencia se escribiria como cero y el cupo del sitio saldria infinito, que
    es exactamente el fallo que la reserva existe para impedir.

    **Lleva su modo**, porque la sintesis cuesta distinto en cada uno: la reserva
    de la voz principal decide si esa voz cabe, y la de la de respaldo es la que
    divide el presupuesto para sacar el cupo del dia.
    """

    max_call_seconds: int = Field(ge=1)
    reserve: Money
    mode: VoiceMode = VoiceMode.PRIMARY


# --- Lo que se guarda ---------------------------------------------------------


class SpendEntry(Frozen):
    """Una llamada a un proveedor y lo que costo (BR3.1).

    Una fila por llamada, sin excepcion, incluida la que fallo y la que no se
    pudo valorar. Si faltaran las que fallan, el costo por caso quedaria por
    debajo del real y nadie lo notaria: es el fallo silencioso que esta unidad
    existe para impedir.

    Las cuatro columnas de precio se guardan explicitas en vez de dentro de un
    `Money` porque BR3.4 las ata a las tres: con que precio, de que lista y de
    que fecha se calculo. `cost` las vuelve a juntar en el par cuando alguien
    quiere sumarlas.
    """

    entry_id: SpendEntryId
    provider: ProviderName
    #: El identificador exacto del modelo o de la voz, nunca un alias movil
    #: (BR1.4). Un alias se mueve del lado del proveedor y la cifra publicada
    #: deja de poder reproducirse.
    model: str
    use: Use
    #: Atribucion, no aislamiento: esta tabla no lleva politica de aseguradora
    #: (BR7.1). Nula cuando el uso no tiene aseguradora --evaluaciones,
    #: generacion, operacion--.
    tenant_ref: str | None = None
    #: Lo **nombra**, no cuelga de el: el reinicio nocturno deja esta columna en
    #: nulo y la fila sobrevive (BR7.5). Un gasto que desapareciera con su caso
    #: borraria el historial de lo que el proyecto ya pago.
    case_ref: str | None = None
    #: La llamada de voz que produjo este gasto, cuando lo produjo una. Nula en
    #: todo lo que no es voz --el chat, las evaluaciones, la generacion--.
    #:
    #: Existe por BR5.5 y por nada mas: la devolucion del cupo se decide
    #: preguntandole al registro de gasto si **esa sesion** dejo audio, y sin esta
    #: columna el registro no puede distinguir una sesion de otra del mismo caso.
    #: **No** lleva clave foranea: la llamada la abre U16 y su tabla no existe
    #: todavia; y aunque existiera, un gasto que desapareciera con su llamada
    #: tendria el mismo problema que BR7.5 resuelve para el caso.
    call_ref: CallRef | None = None
    units: UnitCount
    unit_kind: UnitKind
    unit_price_usd: UsdAmount | None = None
    price_list_version: str | None = None
    price_list_effective_date: date | None = None
    cost_usd: UsdAmount | None = None
    cost_status: CostStatus
    #: Si esta llamada se factura de verdad. Sale del plan del uso, que vive en
    #: configuracion versionada. Solo las facturables suman contra el techo
    #: (BR4.2): sin esta columna, el chat en plan gratuito se comeria el
    #: presupuesto de la voz sin que nadie hubiera pagado nada.
    billable: bool
    lane: BudgetLane = BudgetLane.PUBLIC
    source: SpendSource
    #: Cuando termino la llamada. Decide en que ventana cae.
    occurred_at: datetime
    #: De donde salio la cifra de un asiento de ajuste ("consola de Anthropic,
    #: 2026-10-13"). **Solo lo lleva un ajuste**, y todo ajuste lo lleva: es la unica
    #: columna de texto del libro, acotada, y la escribe quien opera el proyecto y no
    #: un visitante. Nunca sale por la API publica.
    note: Annotated[str, Field(min_length=1, max_length=MAX_ADJUSTMENT_NOTE)] | None = None

    @model_validator(mode="after")
    def _las_cuatro_columnas_de_precio_van_juntas(self) -> Self:
        if self.source is SpendSource.RECONCILED_ADJUSTMENT:
            return self._un_ajuste_es_un_importe_con_su_nota()
        if self.note is not None:
            msg = (
                "solo un asiento de ajuste lleva nota; una llamada a un proveedor no tiene "
                "texto libre, porque este libro no guarda nada que una persona haya escrito"
            )
            raise ValueError(msg)
        columnas = {
            "unit_price_usd": self.unit_price_usd,
            "price_list_version": self.price_list_version,
            "price_list_effective_date": self.price_list_effective_date,
            "cost_usd": self.cost_usd,
        }
        faltan = sorted(nombre for nombre, valor in columnas.items() if valor is None)
        sobran = sorted(nombre for nombre, valor in columnas.items() if valor is not None)

        if self.cost_status is CostStatus.MEASURED and faltan:
            msg = (
                f"un gasto 'measured' guarda las cuatro columnas de precio y faltan: "
                f"{', '.join(faltan)}. Si no habia precio en la tabla, el estado es "
                "'not_measured' y las cuatro van vacias"
            )
            raise ValueError(msg)
        if self.cost_status is CostStatus.NOT_MEASURED and sobran:
            msg = (
                f"un gasto 'not_measured' no guarda ninguna columna de precio y llegaron: "
                f"{', '.join(sobran)}"
            )
            raise ValueError(msg)
        return self

    def _un_ajuste_es_un_importe_con_su_nota(self) -> Self:
        """Un ajuste conciliado: el importe y su nota, sin recuento ni precio de lista.

        No lo valoro la tabla de precios --lo dijo la consola del proveedor--, asi que
        de las cuatro columnas de precio lleva solo el importe. Y no cuenta unidades:
        un ajuste que dijera cuantos tokens fueron estaria inventando un recuento.
        """
        problemas: list[str] = []
        if self.note is None:
            problemas.append("falta la nota de donde salio la cifra")
        if self.cost_status is not CostStatus.MEASURED or self.cost_usd is None:
            problemas.append("el importe es obligatorio y esta medido (si no, no es un ajuste)")
        for nombre in ("unit_price_usd", "price_list_version", "price_list_effective_date"):
            if getattr(self, nombre) is not None:
                problemas.append(f"'{nombre}' va vacio: no lo valoro la lista de precios")
        if self.units != 0:
            problemas.append("no cuenta unidades")
        if self.case_ref is not None or self.call_ref is not None or self.tenant_ref is not None:
            problemas.append("no nombra ni un caso ni una llamada ni una aseguradora")
        if problemas:
            msg = "un asiento de ajuste conciliado: " + "; ".join(problemas)
            raise ValueError(msg)
        return self

    @property
    def cost(self) -> Money:
        """El costo como par, que es como se suma (BR3.9).

        Se mira la cantidad y no el estado porque el validador ya los ato: la
        cantidad esta ausente exactamente cuando el estado es `NOT_MEASURED`.
        """
        if self.cost_usd is None:
            return Money.not_measured()
        return Money.measured(self.cost_usd)


def derive_counter_key(
    scope: QuotaScope,
    subject_key: SubjectKey,
    period_start: datetime,
) -> CounterKey:
    """La clave de un contador, derivada y no inventada.

    Dos contadores del mismo alcance y sujeto en el mismo periodo tienen que ser
    **uno**: si la clave se eligiera al crearlos, abrir dos llamadas a la vez
    crearia dos filas y cada una dejaria pasar la suya, que es el escenario
    RT-13.

    El instante se normaliza a UTC antes de escribirlo porque la medianoche se
    calcula en la zona configurada (BR5.2): sin normalizar, el mismo instante
    escrito en dos zonas daria dos claves distintas para el mismo periodo.
    """
    if period_start.tzinfo is None:
        msg = (
            "el comienzo del periodo tiene que llevar zona horaria: sin ella, la "
            "medianoche depende de la del servidor, que es lo que BR5.2 prohibe"
        )
        raise ValueError(msg)
    return f"{scope.value}:{subject_key}:{period_start.astimezone(UTC).isoformat()}"


class QuotaPeriod(Frozen):
    """El periodo abierto y **con que limite se abrio** (BR5.2, BR5.6).

    Los dos viajan juntos porque se deciden juntos: el cupo del sitio se
    recalcula cada dia, asi que el limite solo significa algo al lado del
    periodo en el que rigio. Separarlos dejaria escribir un contador de hoy con
    el cupo de ayer, y un rechazo que meses despues nadie sabria explicar.
    """

    period_start: datetime
    limit: int = Field(ge=0)


class QuotaCounter(Frozen):
    """Cuanto lleva consumido un sujeto en un periodo (BR5.1, BR5.2).

    Es lo que impide que un visitante abra diez llamadas a la vez y lo que corta
    el chat cuando el plan gratuito se acaba.
    """

    counter_key: CounterKey
    scope: QuotaScope
    subject_key: SubjectKey
    period_start: datetime
    count: int = Field(default=0, ge=0)
    #: El limite vigente cuando se abrio el periodo. El cupo del sitio se
    #: recalcula cada dia (BR5.6); esto deja escrito con cual se decidio, de modo
    #: que un rechazo se pueda explicar meses despues.
    limit_at_period_start: int = Field(ge=0)
    updated_at: datetime

    @model_validator(mode="after")
    def _la_clave_sale_de_sus_tres_partes(self) -> Self:
        esperada = derive_counter_key(self.scope, self.subject_key, self.period_start)
        if self.counter_key != esperada:
            msg = (
                f"la clave del contador tiene que derivarse de alcance, sujeto y "
                f"periodo; llego '{self.counter_key}' y se esperaba '{esperada}'"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _el_cupo_del_sitio_no_es_de_nadie(self) -> Self:
        es_del_sitio = self.scope is QuotaScope.VOICE_CALLS_SITE_DAY
        if es_del_sitio and self.subject_key != SITE_SUBJECT:
            msg = (
                f"el cupo del sitio lleva el sujeto literal '{SITE_SUBJECT}' y llego "
                f"'{self.subject_key}': no es de ningun visitante"
            )
            raise ValueError(msg)
        if not es_del_sitio and self.subject_key == SITE_SUBJECT:
            msg = (
                f"'{SITE_SUBJECT}' esta reservado para el cupo del sitio; un contador "
                f"de alcance '{self.scope}' lleva el resumen de la clave del navegador"
            )
            raise ValueError(msg)
        return self


class BudgetWindow(Frozen):
    """El acumulado de la ventana de noventa dias, con su techo y su alerta.

    Es **una sola fila** y existe por dos razones que el registro de gasto no
    cubre: el corte tiene que poder decidirse sin recorrer el historial (BR3.8),
    y dos llamadas simultaneas tienen que competir por la misma fila para que
    ninguna pase el techo creyendo que la otra no existe (BR4.6). Una fila unica
    se bloquea; una suma no.
    """

    window_start: date
    window_end: date
    #: Suma solo las filas facturables (BR4.2), e **incluye** lo gastado en el
    #: carril de grabacion.
    billable_spent_usd: UsdAmount = Decimal(0)
    #: El tope original de D11. **El vigente vive en la fila de la base**, no aqui: en
    #: produccion es 40 USD con alerta en 24 desde el 2026-10-07 (decision de Miguel),
    #: y lo siembra `manual_ledger` con esos valores. Este por omision se conserva
    #: porque decenas de pruebas de umbrales estan escritas sobre el.
    cap_usd: UsdAmount = Decimal("5.00")
    alert_usd: UsdAmount = Decimal("3.00")
    #: Se escribe una sola vez. Que exista es lo que impide una segunda alerta
    #: (BR4.3): una alerta por llamada convierte el aviso en ruido y deja de
    #: leerse.
    alert_sent_at: datetime | None = None
    #: La porcion del techo que el enlace publico no puede tocar (BR4.9). Se
    #: declara en **minutos** en configuracion versionada y se convierte con la
    #: tabla de precios; esta columna guarda el resultado de esa conversion.
    #:
    #: **Admite nulo y viaja con su estado**, igual que el costo, y eso es una
    #: desviacion consciente de `entities.md`, que la declara obligatoria con
    #: default 0. La tabla de precios no publica hoy el precio por minuto de la
    #: voz, asi que la conversion puede quedar **no medida**; un cero diria "no
    #: hay reserva" cuando lo cierto es "no se pudo calcular", y el carril
    #: publico se llevaria tambien lo apartado para grabar el video de la semana
    #: doce. Es el mismo par que `CallReserve` usa para este mismo dato.
    recording_reserve_usd: UsdAmount | None = None
    recording_reserve_status: CostStatus = CostStatus.NOT_MEASURED
    #: Que parte del acumulado facturable es del carril de grabacion.
    recording_spent_usd: UsdAmount = Decimal(0)
    #: Cuantas llamadas facturables no se pudieron valorar. Viaja con el
    #: acumulado para que ninguna pantalla pueda mostrar el total sin decir
    #: cuanto no se midio (BR3.5), y desde el 2026-09-21 **decide ademas el
    #: corte**: con una sola, el restante publico deja de tener numero y el
    #: carril de pago se cierra (ver `budget.public_remaining`). Antes de esa
    #: decision su unico consumidor era la pantalla, y el acumulado que decide
    #: el techo podia quedarse corto sin que nada lo dijera.
    #:
    #: Cuenta **los dos carriles**, igual que `billable_spent_usd`.
    unmeasured_billable_calls: int = Field(default=0, ge=0)
    #: Que parte de ese conteo es del carril de grabacion. Es al conteo lo que
    #: `recording_spent_usd` es al acumulado, y existe por la misma razon: sin
    #: el, la fila sabe **cuantas** llamadas no se valoraron pero no de que
    #: carril salieron, y entonces el corte por lo no valorado solo se puede
    #: aplicar al carril publico --cerrar tambien la grabacion por una llamada
    #: que pudo venir del enlace publico gastaria la reserva del video sin que
    #: nadie la hubiera gastado (BR4.10)--. La consecuencia de que no exista es
    #: simetrica y tan fea como la otra: una llamada de grabacion sin valorar
    #: infla el restante de su carril sin que nada lo diga.
    unmeasured_recording_calls: int = Field(default=0, ge=0)
    updated_at: datetime

    @model_validator(mode="after")
    def _la_ventana_dura_noventa_dias(self) -> Self:
        esperado = self.window_start + timedelta(days=WINDOW_DAYS)
        if self.window_end != esperado:
            msg = (
                f"la ventana es acumulada de {WINDOW_DAYS} dias (BR4.1): con comienzo "
                f"{self.window_start} el fin es {esperado} y llego {self.window_end}"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _la_reserva_viaja_con_su_estado(self) -> Self:
        """La misma invariante que `Money`, en las dos columnas de la fila.

        Sin ella, una reserva `measured` sin cantidad se leeria como cero en
        cualquier resta, que es el fallo silencioso que BR3.3 prohibe en el
        costo y que aqui costaria el presupuesto del video.
        """
        medida = self.recording_reserve_status is CostStatus.MEASURED
        if medida and self.recording_reserve_usd is None:
            msg = (
                "una reserva de grabacion 'measured' trae su cantidad; si no se pudo "
                "convertir a dolares, el estado es 'not_measured' y la cantidad va ausente"
            )
            raise ValueError(msg)
        if not medida and self.recording_reserve_usd is not None:
            msg = (
                f"una reserva 'not_measured' no lleva cantidad, y llego "
                f"{self.recording_reserve_usd}"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _los_dos_carriles_caben_en_el_techo(self) -> Self:
        # **Lo que aqui NO se exige, y por que.** Hasta el 2026-09-21 esta
        # invariante tambien exigia `recording_spent_usd <= recording_reserve_usd`
        # --y cero cuando la reserva no se pudo medir--. Se quito, y con ella la
        # restriccion gemela de la base, porque enfrentaba dos reglas aprobadas y
        # manda BR3.1:
        #
        # - **BR4.5** acepta el exceso: el techo se consulta **antes** de llamar
        #   al proveedor y el costo se registra **despues**, asi que el exceso de
        #   la llamada en vuelo es parte del diseno y no un error.
        # - **BR3.1** exige que toda llamada deje su fila, sin excepcion.
        #
        # Con la invariante puesta, registrar el gasto de una llamada de
        # grabacion con la reserva agotada **levantaba** en vez de escribir la
        # fila. Una fila de gasto perdida falsea una cifra publicada y no deja
        # rastro de que falta; un restante que llega a cero y se queda ahi no
        # falsea nada, porque el restante ya se informa con piso en cero
        # (`budget.recording_remaining`). Perder la fila es el fallo silencioso
        # que esta unidad entera existe para impedir.
        #
        # O sea: **el gasto acumulado de un carril puede superar su reserva; el
        # restante es el que nunca baja de cero.**
        if self.recording_reserve_usd is not None and self.recording_reserve_usd > self.cap_usd:
            msg = (
                f"la reserva de grabacion ({self.recording_reserve_usd}) no cabe en el "
                f"techo ({self.cap_usd}): apartar mas de lo que hay dejaria el carril "
                "publico cerrado desde el primer dia"
            )
            raise ValueError(msg)
        if self.recording_spent_usd > self.billable_spent_usd:
            msg = (
                f"lo gastado en grabacion ({self.recording_spent_usd}) esta incluido en "
                f"el acumulado facturable ({self.billable_spent_usd}) y no puede "
                "superarlo"
            )
            raise ValueError(msg)
        # La misma contencion, en el conteo. Las llamadas de grabacion sin
        # valorar son un **subconjunto** de las facturables sin valorar, igual
        # que su gasto es una parte del acumulado: un conteo de carril mayor que
        # el total no describe ningun estado alcanzable, y dejaria el corte del
        # carril publico opinando sobre llamadas que el total no vio.
        if self.unmeasured_recording_calls > self.unmeasured_billable_calls:
            msg = (
                f"las llamadas de grabacion sin valorar ({self.unmeasured_recording_calls}) "
                f"son parte de las facturables sin valorar ({self.unmeasured_billable_calls}) "
                "y no pueden superarlas"
            )
            raise ValueError(msg)
        if self.alert_usd > self.cap_usd:
            msg = (
                f"la alerta ({self.alert_usd}) tiene que avisar antes del techo "
                f"({self.cap_usd}), no despues"
            )
            raise ValueError(msg)
        return self

    @property
    def public_spent_usd(self) -> Decimal:
        """Lo que el carril publico lleva gastado.

        Se deriva y no se guarda: una tercera columna podria contradecir a las
        dos de las que sale.
        """
        return self.billable_spent_usd - self.recording_spent_usd

    @property
    def recording_reserve(self) -> Money:
        """La reserva como par, que es como se mira antes de restarla.

        Se mira la cantidad y no el estado porque el validador ya los ato: la
        cantidad esta ausente exactamente cuando el estado es `NOT_MEASURED`.
        Es el mismo camino que `SpendEntry.cost`.
        """
        if self.recording_reserve_usd is None:
            return Money.not_measured()
        return Money.measured(self.recording_reserve_usd)
