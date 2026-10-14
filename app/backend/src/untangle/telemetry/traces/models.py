"""Los tipos del rastro: lo que una respuesta ensena de si misma.

Vive aqui y no junto al dinero por una razon de direccion de dependencias que el
diseno de esta unidad declara: **la contabilidad no importa las trazas**, para
que "el corte funciona aunque la observacion falle" (BR4.8) sea una regla de
herramienta y no una frase de un documento. La flecha contraria si existe --las
trazas leen el costo para los resumenes-- y por eso este modulo importa `Money`
de la contabilidad y no al reves.

`ProviderErrorKind` **ya no vive aqui**: subio a `untangle/base.py` en el bloque
F junto a los cuatro enums de la llamada al proveedor, porque lo escriben tres
modulos que no se importan entre si --el adaptador que traduce, el tramo que lo
estampa y el reporte que lo cuenta--.

El resumen de traza es ademas la **unica** de las cuatro entidades de esta unidad
que es dato de un visitante: lleva su aseguradora y su politica como cualquier
otra tabla de datos de visitante, y el reinicio nocturno se lo lleva con su caso
(BR7.4). Las tres del dinero son dato del proyecto y estan excluidas del
aislamiento a cambio de una prohibicion mas fuerte: ahi dentro no hay nada
personal que aislar (BR7.1, BR7.2).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from untangle.base import Frozen
from untangle.telemetry.spend.models import CostStatus, Money

# --- Identificadores ----------------------------------------------------------

#: El mismo identificador que lleva la traza exportada, para poder cruzarlas: sin
#: eso, el resumen que ve el visitante y el rastro que ve quien depura serian dos
#: cosas que hablan del mismo turno sin saberlo.
type TraceId = str


class NodeName(StrEnum):
    """Los cuatro nodos del grafo, con **una sola grafia** (BR6.2).

    El mismo token nombra el directorio del modulo, el valor del enum de
    transicion, el nombre del tramo en la traza y la etiqueta por nodo del
    reporte de evaluaciones (convencion 3 del equipo). Cuatro grafias del mismo
    nodo obligan a traducir entre la traza, el reporte y el codigo, y esa
    traduccion se hace mal una vez y se arrastra.

    Vive aqui porque las trazas son la primera pieza construida que lo necesita.
    Cuando U12 `graph-runtime` declare su enum de transicion, los dos tienen que
    ser el mismo tipo, no dos listas que coinciden hoy.

    **Se queda aqui y no sube a `untangle/base.py`**, al reves que los cuatro
    enums de la llamada al proveedor: el nombre de un nodo del grafo no lo
    escribe ningun adaptador ni ninguna fila de gasto, asi que subirlo seria
    poner en el vocabulario comun algo que solo hablan dos modulos.
    """

    INTAKE = "intake"
    POLICY_VERIFICATION = "policy_verification"
    DECISION = "decision"
    COMPLIANCE = "compliance"


class SpanLevel(StrEnum):
    """Los niveles del rastro. El nivel decide que puede colgar de que.

    **Los tres primeros son los de BR6.1**, y son los del *turno*: por turno, por
    nodo y por llamada a proveedor, anidados, y los tres existen siempre que
    corre un turno. Un tramo de llamada sin su nodo encima es un costo que no se
    puede atribuir, que es justo lo que AC4.8.1 existe para impedir.

    **`CASE` es el cuarto, y que sean cuatro se declara en vez de heredarse.**
    BR6.4 pide que la pausa hacia la bandeja y la reanudacion vivan en la traza
    del mismo caso, y esos dos momentos **no ocurren dentro de un turno**: la
    pausa deja el caso esperando y la reanudacion llega horas despues, desde la
    bandeja y por otro camino. No son un turno, no son un nodo y no son una
    llamada a un proveedor, asi que darles cualquiera de los tres niveles de
    BR6.1 seria mentir sobre lo que son y permitir que un nodo colgara de ellos.
    Los tres de BR6.1 siguen siendo los tres del turno; este no cuenta turnos.
    """

    TURN = "turn"
    NODE = "node"
    CALL = "call"
    CASE = "case"


class CaseMoment(StrEnum):
    """Los dos momentos del caso que viven fuera de un turno (BR6.4).

    Nombres de **conjunto cerrado**, igual que los cuatro nodos y que el tramo
    del turno, y por la misma razon: un nombre libre seria el unico texto sin
    lista del rastro, y por ahi se cuela lo demas.

    **Esta unidad solo ofrece el vocabulario.** Quien emite la pausa es U12
    `graph-runtime` al derivar el caso hacia la bandeja; quien emite la
    reanudacion es U14 `inbox-decision` cuando una persona firma. Aqui no hay
    ningun sitio que los emita, y eso es correcto: lo que faltaba no era una
    llamada, era que la llamada fuera **posible**.
    """

    #: El caso queda esperando a una persona. Su hora es la del tramo
    #: (`started_at`) y no un atributo: el tramo ya la dice, y dos cifras para el
    #: mismo dato son dos cifras que un dia discrepan.
    PAUSED = "case.paused"
    #: Una persona decidio y el grafo sigue. Lleva **quien** decidio.
    RESUMED = "case.resumed"


class TraceSummaryStatus(StrEnum):
    """Los tres estados de un resumen (BR6.7).

    `LOST` es un valor, no un fallo: el backend de trazas no la recibio y nada se
    detuvo. Un caso que se cayera porque el panel de trazas esta caido
    convertiria una herramienta de diagnostico en un punto de fallo.
    """

    RECORDING = "recording"
    READY = "ready"
    LOST = "lost"


class NodeTiming(Frozen):
    """Lo que un nodo aporto a una respuesta, tal como sale en el resumen."""

    node: NodeName
    started_at: datetime
    duration_ms: int = Field(ge=0)
    cost: Money


class TraceOutcome(Frozen):
    """Lo que el rastro trajo cuando llego: con que completar un resumen.

    Viaja junto y no como cinco argumentos sueltos porque son **una sola
    llegada**: los nodos que corrieron, lo que cito, cuanto tardo y cuanto
    costo. Separarlos deja escribir la latencia sin los nodos, que es
    exactamente el resumen que miente que `TraceSummary` prohibe.
    """

    nodes: tuple[NodeTiming, ...]
    latency_ms: int = Field(ge=0)
    cost: Money
    clauses_retrieved: int = Field(default=0, ge=0)
    clauses_verified: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _no_se_verifica_lo_que_no_se_recupero(self) -> Self:
        if self.clauses_verified > self.clauses_retrieved:
            msg = (
                f"se verificaron {self.clauses_verified} clausulas y se recuperaron "
                f"{self.clauses_retrieved}: verificar lo que no se recupero no significa nada"
            )
            raise ValueError(msg)
        return self


class TraceSummary(Frozen):
    """Por que nodos paso una respuesta, que cito, cuanto tardo y cuanto costo.

    Es dato de un visitante: solo lo ve el navegador que lo produjo (BR6.6) y el
    reinicio nocturno lo borra con su caso.
    """

    trace_id: TraceId
    #: Toda lectura y escritura pasa por el punto unico de sesion, que ya lo fijo
    #: antes de devolver la conexion.
    tenant_id: str
    #: Cuelga del caso: el reinicio nocturno se lo lleva con el (BR7.4).
    case_id: str
    #: El resumen de la clave del navegador, nunca la clave (BR7.3). Decide a
    #: quien se le muestra.
    visitor_key_hash: str
    #: El turno cuya respuesta resume. Nulo en el resumen de un caso entero.
    turn_ref: str | None = None
    #: Puede estar vacia mientras el estado es `RECORDING`. Vacia y `READY` seria
    #: un resumen que miente.
    nodes: tuple[NodeTiming, ...] = ()
    clauses_retrieved: int = Field(default=0, ge=0)
    clauses_verified: int = Field(default=0, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    cost: Money = Money(status=CostStatus.NOT_MEASURED)
    status: TraceSummaryStatus = TraceSummaryStatus.RECORDING
    created_at: datetime

    @model_validator(mode="after")
    def _no_se_verifica_lo_que_no_se_recupero(self) -> Self:
        if self.clauses_verified > self.clauses_retrieved:
            msg = (
                f"se verificaron {self.clauses_verified} clausulas y se recuperaron "
                f"{self.clauses_retrieved}: verificar lo que no se recupero no "
                "significa nada"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _un_resumen_listo_esta_completo(self) -> Self:
        if self.status is not TraceSummaryStatus.READY:
            return self
        if not self.nodes:
            msg = (
                "un resumen 'ready' sin nodos miente: mientras el rastro no haya "
                "llegado, el estado es 'recording'"
            )
            raise ValueError(msg)
        if self.latency_ms is None:
            msg = "un resumen 'ready' trae su latencia; sin ella el estado es 'recording'"
            raise ValueError(msg)
        return self
