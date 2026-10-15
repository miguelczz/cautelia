"""La unica forma de emitir un tramo, y el resumen que ve el visitante (C-23).

Esta unidad produce la telemetria de todas las demas, asi que tiene una
obligacion que las otras no: **lo que emite tiene que ser imposible de
contaminar**, no solo dificil. De ahi las tres propiedades de abajo, que no se
piden: se comprueban.

**1. La lista de atributos esta cerrada y el comprobador de tipos la impone.**
`SpanAttributes` es un `TypedDict` con las dieciseis claves del diseno y ninguna
mas --las quince de `observability-design.md` mas `untangle.decided_by`, que es
la que BR6.4 necesita y ese documento no tenia--. Un nombre inventado no llega a
la prueba de canarios: no compila. Se
comprobo plantando `untangle.inventado` y viendo fallar `mise run types` con
`typeddict-unknown-key`; y pasar un `dict[str, str]` cualquiera tampoco compila,
que era la puerta de al lado.

Los nombres llevan punto --`gen_ai.system`-- porque son los de OpenTelemetry, y
un nombre con punto no puede ser un argumento con nombre de Python. Por eso los
atributos viajan como **un mapa con nombre** y no como `**kwargs`: entre cambiar
los nombres del estandar y cambiar la forma del argumento, se cambia la forma.
Los nombres son el contrato con el estandar; la forma del argumento no es
contrato de nadie.

**2. Ningun atributo admite texto libre.** Los valores son enums cerrados,
numeros e identificadores. El texto del asegurado, la respuesta del modelo y el
contenido de una clausula no tienen donde entrar. Lo que el tipo no puede decir
--que un identificador no traiga una frase dentro-- lo dice `_validar`: sin
espacios, sin saltos de linea y acotado; y `untangle.prompt_hash` tiene que ser
un resumen de verdad, sesenta y cuatro digitos hexadecimales. Un prompt entero
pasado como "hash" es la forma mas probable de que un dato personal llegue a un
tramo, y es la que el tipo **no** atrapa.

**3. La prueba de canarios se hace igual**, como segunda capa: un turno sembrado
con los cuatro tipos de dato personal propios y cada atributo de cada tramo
inspeccionado. Dos capas, no una.

## Los tres niveles

    tramo del turno
    `-- tramo del nodo (intake | policy_verification | decision | compliance)
        `-- tramo de la llamada al proveedor

El identificador de correlacion **nace con el turno y baja por el contexto**; no
se pasa por argumento, para que no se pueda olvidar en una rama. Por eso
`node_span` y `call_span` no reciben el caso: lo leen. Y por eso abrir un tramo
de nodo sin turno, o uno de llamada sin nodo, levanta en vez de emitir un tramo
huerfano: un costo que no se puede atribuir a su nodo es lo que AC4.8.1 existe
para impedir.

## Los dos momentos del caso, que no son un turno

BR6.4 pide ademas que la pausa hacia la bandeja y la reanudacion vivan en la
traza del **mismo** caso. Esos dos no caben en los tres niveles de arriba: la
pausa deja el caso esperando y la reanudacion llega horas despues, desde la
bandeja, sin turno abierto y a menudo desde otro proceso. `case_moment_span` los
emite como tramos **raiz** del caso, con el identificador de traza por argumento
porque es el unico que no se puede heredar: entre los dos momentos no hay
contexto vivo que lo herede.

## Lo que este modulo NO hace, y es deliberado

- **No exporta.** No importa `export`, asi que cerrar un tramo no puede llamar al
  backend de trazas ni por accidente: la exportacion **no esta en el camino de la
  respuesta** y eso es una direccion de importacion, no una intencion.
- **No importa el modulo de gasto para escribir.** Lee un tipo suyo --`Money`,
  para el costo del resumen-- y nada mas; el resto del vocabulario que estampa
  (`Use`, `ProviderName`, `ProviderErrorKind`) vive en `untangle/base.py`. La
  flecha contraria --que el gasto importara las trazas-- es la que BR4.8
  prohibe: si el backend de trazas cae, el gasto se sigue registrando y el techo
  sigue cortando.

## Sin el SDK de OpenTelemetry, y por que se queda asi

`nfr-requirements/tech-stack-decisions.md` inscribio `opentelemetry-sdk` y
`opentelemetry-exporter-otlp` como dependencias de runtime. El bloque F **no las
instala**, y la razon no es el trabajo que costaria sino donde acabaria el texto:

El exportador OTLP del SDK entrega tramos **por su cuenta**, y esta unidad tiene
una regla que ningun exportador propio del SDK cumple: ninguna salida esquiva el
punto unico de redaccion (regla de `project.md`, BR6.5). El exportador de
`export.py` serializa, **redacta** y solo entonces entrega; el del SDK recibe
objetos de tramo y sale solo, de modo que instalarlo seria abrir un septimo
punto de salida sin redaccion, con el agravante de que nadie lo llamaria asi.

Lo que hay aqui, entonces, no es un provisional: es la implementacion. Y sigue
siendo **sustituible** sin cambiar este archivo, porque `SpanRecorder` tiene
exactamente la forma del procesador de tramos del SDK --recibe tramos ya
cerrados--: el dia que se quiera adoptar, lo que hay que escribir es un
procesador que pase por la redaccion antes de exportar, y se instala en
`install_recorder`. El punto de extension sigue marcado ahi.

La forma del cable tampoco se pierde: `export.py` escribe OTLP/JSON, que es el
**protocolo** y no la biblioteca, asi que un panel que lea OTLP lee esto.
"""

from __future__ import annotations

import asyncio
import hmac
import re
from collections import deque
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol, TypedDict
from uuid import uuid4

from untangle import observability
from untangle.base import ProviderErrorKind, ProviderName, Use
from untangle.telemetry.spend.models import CostStatus, Money
from untangle.telemetry.traces.models import (
    CaseMoment,
    NodeName,
    NodeTiming,
    SpanLevel,
    TraceId,
    TraceOutcome,
    TraceSummary,
    TraceSummaryStatus,
)

# --- La lista cerrada ---------------------------------------------------------

#: Los dieciseis atributos que un tramo puede llevar, y ninguno mas.
#:
#: Cada valor es un enum cerrado, un numero o un identificador. `total=False`
#: porque ningun tramo los lleva todos: un tramo de nodo no tiene modelo y uno
#: de turno no tiene tokens. Lo que si se impone en `_validar` es que los que
#: viajan en par --el costo y su estado-- no se puedan separar.
SpanAttributes = TypedDict(
    "SpanAttributes",
    {
        # Convenciones GenAI de OpenTelemetry (BR6.3). Se anclan a la version
        # que el proyecto fija en `docs/reference/arquitectura-y-tecnologia.md`
        # §11: estan en estado de desarrollo, y anclarlas es lo que impide que un
        # cambio del estandar mueva estos nombres sin avisar.
        "gen_ai.system": ProviderName,
        "gen_ai.request.model": str,
        "gen_ai.usage.input_tokens": int,
        "gen_ai.usage.output_tokens": int,
        # Los propios del proyecto.
        "untangle.node": NodeName,
        "untangle.use": Use,
        "untangle.case_id": str,
        "untangle.turn_id": str,
        "untangle.prompt_id": str,
        "untangle.prompt_hash": str,
        # El costo viaja **como texto decimal**, no como coma flotante. Un
        # atributo de OpenTelemetry solo admite texto, entero, decimal flotante o
        # booleano, y el flotante es exactamente lo que `Money` prohibe: la suma
        # de veinte fracciones de centavo no da lo mismo en cualquier orden. El
        # dato autoritativo vive en `spend_entry`; esto es su lectura.
        "untangle.cost_usd": str,
        "untangle.cost_status": CostStatus,
        "untangle.error_kind": ProviderErrorKind,
        "untangle.attempt": int,
        "untangle.provider": ProviderName,
        # Quien firmo la reanudacion de un caso (BR6.4). Es el `principal_id` de
        # la credencial de bandeja --el identificador corto que la configuracion
        # de la aseguradora le da a esa persona-- y **nunca** su nombre: un
        # nombre es texto libre y esto es un rastro que sale hacia un backend de
        # trazas. Por eso esta ademas en `_IDENTIFIER_ATTRIBUTES`:
        # la lista cerrada cierra los **nombres** de atributo, y lo que cabe
        # dentro de un `str` lo cierra la forma del valor.
        "untangle.decided_by": str,
    },
    total=False,
)

#: Las mismas dieciseis claves, en tiempo de ejecucion. Existe porque el tipo se
#: borra: `cast(SpanAttributes, {...})` es una llamada legal que el comprobador
#: acepta sin queja, igual que pasa con `Redacted` en U3. El tipo atrapa los
#: descuidos; esto atrapa los atajos.
ALLOWED_ATTRIBUTES: frozenset[str] = frozenset(SpanAttributes.__annotations__)

#: Los atributos cuyo valor es un identificador. No llevan espacios ni saltos de
#: linea y estan acotados: es lo que impide que una frase entre disfrazada de
#: identificador, que es lo unico que el tipo `str` no puede decir.
_IDENTIFIER_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "gen_ai.request.model",
        "untangle.case_id",
        "untangle.turn_id",
        "untangle.prompt_id",
        # Que este aqui no es opcional: una lista cerrada de **nombres** de
        # atributo no impide texto libre dentro de un `str`, y "quien decidio" es
        # el atributo al que mas se le parece un nombre de persona. Con la forma
        # comprobada, "Ana Rivas" deja de ser un valor valido por lo que es y no
        # por la buena fe de quien llama (NFR11, compuerta dura).
        "untangle.decided_by",
    }
)

#: Un identificador: letras, digitos y los tres separadores que el proyecto usa.
#: Deliberadamente **no** admite espacio: "Mi telefono es 3005551234" deja de ser
#: un `untangle.case_id` valido por su forma, no por la buena fe de quien llama.
_IDENTIFIER = re.compile(r"\A[A-Za-z0-9._:-]{1,128}\Z")

#: Un resumen SHA-256 en hexadecimal. Un prompt entero no tiene esta forma.
_DIGEST = re.compile(r"\A[0-9a-f]{64}\Z")

#: Cuantos digitos tiene el identificador de una traza y el de un tramo en esta
#: unidad. Son los 32 de un `uuid4` en hexadecimal, que es lo que OTLP y Langfuse
#: esperan para una traza.
_ID_DIGITS = 32


def _identificador_nuevo(digitos: int = _ID_DIGITS) -> str:
    """Un identificador de `digitos` cifras decimales, al que la redaccion casi nunca toca.

    **Solo cifras, y no es capricho.** El lote entero pasa por la redaccion antes de
    salir, y la redaccion lee texto: un identificador hexadecimal al azar sale mutilado
    sin que nada falle --`3420233387b34ddb` quedaba `[PHONE 1]b34ddb` porque diez cifras
    seguidas son un telefono, y `fe01ab0208b2485b` quedaba `[NAME 2]` porque el modelo
    de nombres lo toma por una persona--. Un identificador roto en el backend de trazas
    es un arbol huerfano y, peor, el enlace del visitante a una traza que no existe.

    Medido el 2026-10-14 con el detector de verdad, sobre lotes de nueve tramos: con
    `uuid4().hex`, en 9 de 25 lotes se mutilo algun identificador (y una vez hasta
    el tiempo de inicio); con 32 cifras, en 1 de 37. Una cadena larga de cifras no
    coincide con ningun reconocedor por formato --telefono y cedula piden de ocho a
    diez cifras exactas, la poliza lleva `POL-`, la placa y el VIN piden letras--, y
    al modelo de nombres le pasa muy de vez en cuando. Ese resto no se evita desde
    aqui: lo atrapa `export._identidad_intacta`, que no entrega un lote cuyos
    identificadores cambiaron.

    Sigue siendo texto hexadecimal valido --las cifras lo son--, con 106 bits de azar.
    """
    return f"{uuid4().int % 10**digitos:0{digitos}d}"


#: Los atributos que no se pueden escribir el uno sin el otro (BR3.4, BR3.9).
_COST_PAIR = ("untangle.cost_usd", "untangle.cost_status")

#: Los enteros que no pueden ser negativos.
_NON_NEGATIVE: frozenset[str] = frozenset(
    {"gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens", "untangle.attempt"}
)


class SpanAttributeError(ValueError):
    """Un atributo no esta en la lista, o su valor no tiene la forma que dice.

    Se levanta en vez de emitir el tramo sin ese atributo: un tramo emitido a
    medias con un valor sospechoso dentro es peor que un tramo que falta, porque
    el segundo se nota.
    """


class SpanNestingError(RuntimeError):
    """Un tramo se abrio en el nivel equivocado (BR6.1).

    Un tramo de llamada sin su nodo encima es un costo que no se puede atribuir.
    """


def _validar(attributes: Mapping[str, object]) -> dict[str, str | int]:
    """Comprueba la lista, los tipos y la forma, y devuelve el mapa del cable."""
    desconocidos = sorted(set(attributes) - ALLOWED_ATTRIBUTES)
    if desconocidos:
        msg = (
            f"atributos fuera de la lista cerrada: {desconocidos}. La lista es "
            f"{sorted(ALLOWED_ATTRIBUTES)} y anadir uno es anadirlo ahi, que es "
            "lo que se ve en una revision"
        )
        raise SpanAttributeError(msg)

    presentes = [clave for clave in _COST_PAIR if clave in attributes]
    if len(presentes) == 1:
        msg = (
            f"'{presentes[0]}' viaja con su pareja: el costo no se escribe sin su "
            "estado (BR3.4). Use `Span.set_cost`, que los escribe juntos"
        )
        raise SpanAttributeError(msg)

    cable: dict[str, str | int] = {}
    for clave, valor in attributes.items():
        cable[clave] = _valor_del_cable(clave, valor)
    return cable


def _valor_del_cable(clave: str, valor: object) -> str | int:
    """El valor de un atributo, comprobado, en la forma que viaja por el cable."""
    if clave in _NON_NEGATIVE:
        if not isinstance(valor, int) or isinstance(valor, bool):
            msg = f"'{clave}' lleva un entero y llego {type(valor).__name__}"
            raise SpanAttributeError(msg)
        if valor < 0:
            msg = f"'{clave}' no puede ser negativo, y llego {valor}"
            raise SpanAttributeError(msg)
        return valor

    if not isinstance(valor, str):
        msg = f"'{clave}' lleva texto o un enum de texto, y llego {type(valor).__name__}"
        raise SpanAttributeError(msg)

    if clave == "untangle.prompt_hash":
        if not _DIGEST.match(valor):
            msg = (
                "'untangle.prompt_hash' tiene que ser un resumen SHA-256 en "
                "hexadecimal (64 digitos). Lo que llego no lo es, y un prompt "
                "entero pasado como 'hash' es como un dato personal llega a un tramo"
            )
            raise SpanAttributeError(msg)
        return valor

    if clave == "untangle.cost_usd":
        try:
            Decimal(valor)
        except InvalidOperation as error:
            msg = f"'untangle.cost_usd' tiene que ser un decimal en texto, y llego '{valor}'"
            raise SpanAttributeError(msg) from error
        return valor

    if clave in _IDENTIFIER_ATTRIBUTES and not _IDENTIFIER.match(valor):
        msg = (
            f"'{clave}' lleva un identificador --sin espacios, sin saltos de "
            "linea y de 128 caracteres o menos--, y lo que llego no lo es. "
            "Ningun atributo de un tramo admite texto libre"
        )
        raise SpanAttributeError(msg)

    # Los enums cerrados llegan aqui: `StrEnum` **es** `str`, y lo que viaja es
    # su valor. Se normaliza con `str()` para que el cable no lleve el objeto.
    return str(valor)


# --- Los tramos ---------------------------------------------------------------


@dataclass(frozen=True)
class FinishedSpan:
    """Un tramo cerrado, tal como se le entrega al registrador.

    Es lo que el SDK de OpenTelemetry llama un tramo terminado, y por eso tiene
    esta forma: el dia que el SDK entre, su procesador de tramos recibe esto
    mismo.
    """

    trace_id: TraceId
    #: La aseguradora del turno. Es **dato de direccion, no un atributo**: no
    #: esta en la lista cerrada y no viaja en la exportacion. Existe porque el
    #: exportador tiene que poder alcanzar la fila del resumen para marcarla
    #: perdida (BR6.7), y esa fila esta detras de la politica de aislamiento, que
    #: exige la aseguradora para abrir la sesion. Meterlo en la lista cerrada
    #: seria ampliar la lista del diseno, que no es una decision de este paso.
    tenant_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    level: SpanLevel
    started_at: datetime
    ended_at: datetime
    duration_ms: int
    attributes: Mapping[str, str | int]


@dataclass
class Span:
    """Un tramo abierto. Los atributos que se conocen al cerrar se anaden aqui.

    Los tokens y el costo no se saben al abrir --solo cuando el proveedor
    responde-- asi que el ayudante tiene que dejarlos anadir. Lo que **no** deja
    es anadirlos por fuera de la lista: `set` pasa por la misma comprobacion que
    el constructor.
    """

    trace_id: TraceId
    tenant_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    level: SpanLevel
    started_at: datetime
    _attributes: dict[str, str | int] = field(default_factory=dict)

    @property
    def attributes(self) -> Mapping[str, str | int]:
        """Lo que lleva, en la forma del cable. Copia: nadie escribe por detras."""
        return dict(self._attributes)

    def set(self, attributes: SpanAttributes) -> None:
        """Anade atributos al tramo abierto, por la misma puerta cerrada."""
        self._attributes.update(_validar(dict(attributes)))

    def set_cost(self, cost: Money) -> None:
        """Escribe el costo **y su estado**, que es un solo acto (BR3.4).

        Existe para que no haya forma comoda de escribir uno sin el otro: un
        costo suelto en una traza es un cero que despues alguien suma.
        """
        if cost.amount_usd is None:
            self._attributes["untangle.cost_status"] = cost.status.value
            return
        self._attributes["untangle.cost_usd"] = str(cost.amount_usd)
        self._attributes["untangle.cost_status"] = cost.status.value


class SpanRecorder(Protocol):
    """Quien recibe los tramos ya cerrados.

    **Este es el punto de extension del SDK de OpenTelemetry.** Su procesador de
    tramos tiene exactamente esta forma, asi que el dia que se adopte se instala
    aqui y este modulo no cambia. Lo que ese procesador tendra que hacer, y el
    del SDK no hace solo, es pasar por la redaccion antes de exportar: la razon
    entera esta en el encabezado del modulo.
    """

    def record(self, span: FinishedSpan) -> None: ...


#: Cuantos tramos cerrados se guardan esperando a que alguien los exporte.
#:
#: Acotada **y descarta** al llenarse, al reves que la cola de lo no facturable
#: del gasto, que pasa a sincrona. El contraste es deliberado: perder una fila de
#: gasto falsea una cifra publicada, y perder un tramo solo empeora un
#: diagnostico. Lo que no se puede hacer nunca es lo contrario --meter la
#: exportacion en el camino de la respuesta para no perder un tramo-- porque eso
#: convierte una herramienta de diagnostico en un punto de fallo (BR6.7).
RECORDER_CAPACITY = 2048


#: De cuantas trazas recientes se guardan los tramos para armar su resumen.
RECENT_TRACES = 64


class BufferedRecorder:
    """El registrador propio: guarda lo que se emitiria, acotado."""

    def __init__(self, capacity: int = RECORDER_CAPACITY) -> None:
        self._spans: deque[FinishedSpan] = deque(maxlen=capacity)
        self._dropped = 0
        #: Los tramos de las ultimas trazas, aparte del lote: la exportacion vacia el lote
        #: cada quince segundos, y el resumen de un turno largo se arma con tramos que
        #: pueden haber salido ya (2026-10-15).
        self._recientes: dict[TraceId, list[FinishedSpan]] = {}

    def record(self, span: FinishedSpan) -> None:
        if len(self._spans) == self._spans.maxlen:
            self._dropped += 1
            observability.emit("traces.span_dropped", reason="buffer_full", span=span.name)
        self._spans.append(span)
        if span.trace_id not in self._recientes and len(self._recientes) >= RECENT_TRACES:
            del self._recientes[next(iter(self._recientes))]
        self._recientes.setdefault(span.trace_id, []).append(span)

    def finished(self, trace_id: TraceId) -> tuple[FinishedSpan, ...]:
        """Los tramos cerrados de una traza reciente, hayan salido o no en un lote."""
        return tuple(self._recientes.get(trace_id, ()))

    def drain(self) -> tuple[FinishedSpan, ...]:
        """Se lleva lo acumulado y deja el buffer vacio."""
        lote = tuple(self._spans)
        self._spans.clear()
        return lote

    @property
    def dropped(self) -> int:
        """Cuantos se perdieron por cola llena. Se reporta, no se esconde."""
        return self._dropped


_recorder: SpanRecorder = BufferedRecorder()


def install_recorder(recorder: SpanRecorder) -> None:
    """Cambia quien recibe los tramos cerrados (la raiz de composicion, y las pruebas)."""
    global _recorder
    _recorder = recorder


def current_recorder() -> SpanRecorder:
    return _recorder


def reset() -> None:
    """Devuelve el modulo a su estado inicial. Lo usan las pruebas.

    Sin esto, una prueba que instala un registrador se lo dejaria puesto a la
    siguiente, y la suite dejaria de poder correr en cualquier orden.
    """
    global _recorder
    _recorder = BufferedRecorder()
    _contexto.set(None)
    _pila.set(())


# --- El contexto: el identificador de correlacion no se pasa, se hereda --------


@dataclass(frozen=True)
class TraceContext:
    """Lo que un turno deja puesto para todo lo que cuelgue de el."""

    trace_id: TraceId
    tenant_id: str
    case_id: str
    turn_id: str | None


_contexto: ContextVar[TraceContext | None] = ContextVar("untangle_trace_context", default=None)
_pila: ContextVar[tuple[Span, ...]] = ContextVar("untangle_trace_stack", default=())


def current_context() -> TraceContext | None:
    """El contexto del turno en curso, si hay uno."""
    return _contexto.get()


def current_trace_id() -> TraceId | None:
    contexto = _contexto.get()
    return contexto.trace_id if contexto else None


def _exigir_contexto() -> TraceContext:
    contexto = _contexto.get()
    if contexto is None:
        msg = (
            "no hay turno abierto: el identificador de correlacion baja por el "
            "contexto, asi que un tramo de nodo o de llamada solo existe dentro "
            "de `turn_span` (BR6.1)"
        )
        raise SpanNestingError(msg)
    return contexto


def _padre() -> Span | None:
    pila = _pila.get()
    return pila[-1] if pila else None


@contextmanager
def _abrir(  # noqa: PLR0913 -- seis datos de un tramo, ninguno derivable de otro
    *,
    name: str,
    level: SpanLevel,
    context: TraceContext,
    now: datetime,
    attributes: Mapping[str, object],
    parent: Span | None,
) -> Iterator[Span]:
    """Abre un tramo, lo apila, y lo entrega al registrador al cerrarse.

    El padre entra por argumento y no se lee de la pila aqui dentro: los tres
    niveles del turno cuelgan de lo que tengan encima, y los dos momentos del
    caso son raices (BR6.4). Quien abre cada uno lo sabe; esta funcion no.
    """
    padre = parent
    tramo = Span(
        trace_id=context.trace_id,
        tenant_id=context.tenant_id,
        span_id=_identificador_nuevo(),
        parent_span_id=padre.span_id if padre else None,
        name=name,
        level=level,
        started_at=now,
        _attributes=_validar(attributes),
    )
    marca = _pila.set((*_pila.get(), tramo))
    try:
        yield tramo
    finally:
        _pila.reset(marca)
        fin = _reloj()
        _recorder.record(
            FinishedSpan(
                trace_id=tramo.trace_id,
                tenant_id=tramo.tenant_id,
                span_id=tramo.span_id,
                parent_span_id=tramo.parent_span_id,
                name=tramo.name,
                level=tramo.level,
                started_at=tramo.started_at,
                ended_at=fin,
                duration_ms=max(0, int((fin - tramo.started_at).total_seconds() * 1000)),
                attributes=tramo.attributes,
            )
        )


class Clock(Protocol):
    """De donde sale la hora. Inyectable porque el plazo de diez segundos se prueba."""

    def now(self) -> datetime: ...


_clock: Clock | None = None


def install_clock(clock: Clock | None) -> None:
    """Fija el reloj del modulo. `None` vuelve al del sistema."""
    global _clock
    _clock = clock


def _reloj() -> datetime:
    if _clock is not None:
        return _clock.now()
    return datetime.now(UTC)


#: El nombre del tramo de turno. Cerrado como los cuatro de nodo: un nombre libre
#: seria el unico texto sin lista del rastro, y por ahi se cuela lo demas.
TURN_SPAN_NAME = "turn"


@contextmanager
def turn_span(
    *,
    tenant_id: str,
    case_id: str,
    use: Use,
    turn_id: str | None = None,
    trace_id: TraceId | None = None,
) -> Iterator[Span]:
    """El tramo de mas afuera. **Aqui nace el identificador de correlacion.**

    Lo deja en el contexto, no en un argumento: un argumento se puede olvidar en
    una rama, y entonces esa rama emite tramos que no se pueden cruzar con nada.

    No recibe atributos, y es deliberado: los del turno son **derivados** --el
    caso, el turno y el uso-- y ninguno lo elige quien llama. Lo que se sepa
    despues se anade con `Span.set`, que pasa por la misma puerta cerrada.
    """
    if _contexto.get() is not None:
        msg = (
            "ya hay un turno abierto: los tres niveles son turno, nodo y llamada "
            "(BR6.1), y un turno dentro de otro no es ninguno de los tres"
        )
        raise SpanNestingError(msg)

    contexto = TraceContext(
        trace_id=trace_id or _identificador_nuevo(),
        tenant_id=tenant_id,
        case_id=case_id,
        turn_id=turn_id,
    )
    propios: dict[str, object] = {"untangle.case_id": case_id, "untangle.use": use}
    if turn_id is not None:
        propios["untangle.turn_id"] = turn_id
    marca = _contexto.set(contexto)
    try:
        with _abrir(
            name=TURN_SPAN_NAME,
            level=SpanLevel.TURN,
            context=contexto,
            now=_reloj(),
            attributes=propios,
            parent=_padre(),
        ) as tramo:
            yield tramo
    finally:
        _contexto.reset(marca)


@contextmanager
def node_span(node: NodeName, *, attributes: SpanAttributes | None = None) -> Iterator[Span]:
    """El tramo de un nodo. Se llama como el nodo y no de otra forma (BR6.2).

    El caso no se pasa: se lee del contexto que dejo el turno.
    """
    contexto = _exigir_contexto()
    padre = _padre()
    if padre is None or padre.level is not SpanLevel.TURN:
        msg = "un tramo de nodo cuelga del tramo del turno, no de otro nodo ni de una llamada"
        raise SpanNestingError(msg)

    propios: dict[str, object] = {"untangle.node": node, "untangle.case_id": contexto.case_id}
    if contexto.turn_id is not None:
        propios["untangle.turn_id"] = contexto.turn_id
    with _abrir(
        name=node.value,
        level=SpanLevel.NODE,
        context=contexto,
        now=_reloj(),
        attributes={**propios, **dict(attributes or {})},
        parent=padre,
    ) as tramo:
        yield tramo


@contextmanager
def call_span(
    *,
    provider: ProviderName,
    model: str,
    use: Use,
    attempt: int = 1,
    attributes: SpanAttributes | None = None,
) -> Iterator[Span]:
    """El tramo de una llamada a un proveedor (BR6.3).

    Estampa `gen_ai.system` y `untangle.provider` desde **un solo argumento**:
    son el mismo proveedor leido por dos vocabularios --el del estandar y el de
    la contabilidad-- y escribirlos por separado en cada sitio de llamada es como
    un dia dejarian de coincidir. La latencia no es un atributo: es la duracion
    del propio tramo, y duplicarla dejaria dos cifras que pueden discrepar.
    """
    contexto = _exigir_contexto()
    padre = _padre()
    if padre is None or padre.level is not SpanLevel.NODE:
        msg = (
            "un tramo de llamada cuelga de un tramo de nodo: un costo sin nodo no "
            "se puede atribuir, que es lo que AC4.8.1 existe para impedir"
        )
        raise SpanNestingError(msg)

    propios: dict[str, object] = {
        "gen_ai.system": provider,
        "gen_ai.request.model": model,
        "untangle.provider": provider,
        "untangle.use": use,
        "untangle.attempt": attempt,
        "untangle.case_id": contexto.case_id,
    }
    if contexto.turn_id is not None:
        propios["untangle.turn_id"] = contexto.turn_id
    with _abrir(
        name=f"{SpanLevel.CALL.value}.{provider.value}",
        level=SpanLevel.CALL,
        context=contexto,
        now=_reloj(),
        attributes={**propios, **dict(attributes or {})},
        parent=padre,
    ) as tramo:
        yield tramo


# --- Los dos momentos del caso (BR6.4) ----------------------------------------


@contextmanager
def case_moment_span(
    moment: CaseMoment,
    *,
    tenant_id: str,
    case_id: str,
    trace_id: TraceId,
    decided_by: str | None = None,
) -> Iterator[Span]:
    """La pausa hacia la bandeja y la reanudacion, en la traza del mismo caso.

    **Quien emite cada uno.** La pausa la emite U12 `graph-runtime` al derivar el
    caso hacia la bandeja; la reanudacion la emite U14 `inbox-decision` cuando
    una persona firma. Esta unidad solo ofrece el vocabulario: los nombres
    cerrados, el atributo de quien decidio y la forma del tramo. Aqui no hay
    ningun sitio que los emita, y eso es lo correcto.

    **Por que no vale `node_span` ni `call_span`.** Los dos exigen un turno
    abierto, porque el identificador de correlacion baja por el contexto. Estos
    dos momentos ocurren **fuera** de un turno: la pausa deja el caso esperando y
    la reanudacion llega horas despues, desde la bandeja y por otro camino y a
    menudo por otro proceso. Por eso el identificador de traza entra **por
    argumento**: es el unico de todos los tramos del proyecto que no se puede
    heredar, porque entre los dos momentos no hay contexto vivo que lo herede.

    **Es un tramo raiz**, siempre, aunque hubiera algo abierto encima. Colgarlo
    de lo que hubiera en la pila ataria la pausa al turno que la provoco, y
    entonces la reanudacion --que no tiene turno-- colgaria de otra cosa y las
    dos dejarian de leerse igual. Lo que las une es el caso, que es lo que BR6.4
    pide.

    **La hora de la pausa es la del tramo** (`started_at`) y no un atributo: el
    tramo ya la dice, y dos cifras para el mismo dato son dos cifras que un dia
    discrepan.

    `decided_by` es el `principal_id` de la credencial de bandeja
    (`tenancy.models.StaffCredential`) y **no** el nombre de la persona. Va con
    la reanudacion y solo con ella: una pausa no la decide nadie, la decide el
    caso.
    """
    if moment is CaseMoment.RESUMED and decided_by is None:
        msg = (
            "la reanudacion lleva quien decidio (BR6.4): un caso que vuelve de la "
            "bandeja sin firma obliga a reconstruir a mano quien lo aprobo, que es "
            "justo lo que esta regla existe para evitar"
        )
        raise SpanAttributeError(msg)
    if moment is CaseMoment.PAUSED and decided_by is not None:
        msg = (
            "la pausa no la decide nadie: la decide el caso al derivarse. Quien "
            "decidio va en la reanudacion, que es donde una persona firmo"
        )
        raise SpanAttributeError(msg)

    contexto = TraceContext(trace_id=trace_id, tenant_id=tenant_id, case_id=case_id, turn_id=None)
    propios: dict[str, object] = {"untangle.case_id": case_id}
    if decided_by is not None:
        propios["untangle.decided_by"] = decided_by
    with _abrir(
        name=moment.value,
        level=SpanLevel.CASE,
        context=contexto,
        now=_reloj(),
        attributes=propios,
        parent=None,
    ) as tramo:
        yield tramo


# --- El resumen de traza ------------------------------------------------------

#: Diez segundos desde que la respuesta salio. Esta atado a la meta del chat
#: --p95 menor que 3 s del envio a la primera palabra-- asi que es mas del triple
#: de la respuesta entera. El dia que esa meta cambie, este plazo **se recalcula**
#: en vez de quedarse viejo.
SUMMARY_DEADLINE_SECONDS = 10


class SummaryStore(Protocol):
    """Donde viven los resumenes.

    Es asincrono porque el almacen de verdad es una tabla --`trace_summary`, con
    su aislamiento y su borrado nocturno-- y C-23 declara asincrona la lectura
    publica. El de este archivo es el del proceso, que es lo que permite probar
    la superficie sin levantar una base; el de base vive en `repository.py` y lo
    instala la raiz de composicion (paso 22).

    **Esta superficie no importa `repository.py`**, y esa direccion no es gusto:
    `untangle.evals` tiene prohibido llegar a `untangle.tenancy.session` incluso
    por cadena, que es lo que mantiene vivo el camino "del clon al reporte" sin
    base de datos y con el la cifra publicada de NFR21.
    """

    async def put(self, summary: TraceSummary) -> None: ...

    async def get(self, trace_id: TraceId, *, tenant_id: str) -> TraceSummary | None: ...

    async def latest_for_case(self, case_id: str, *, tenant_id: str) -> TraceSummary | None: ...

    async def latest_for_cases(
        self, case_ids: Sequence[str], *, tenant_id: str
    ) -> dict[str, TraceSummary]:
        """El ultimo resumen de **cada** caso de la lista, en una sola lectura.

        Del caso a su resumen; el caso sin resumen no aparece. Es `latest_for_case` sin una
        consulta por caso: lo piden las superficies que muestran varios casos a la vez.
        """
        ...


class InProcessSummaryStore:
    """El almacen del proceso. Para las pruebas y para el camino sin base.

    Filtra por aseguradora **a mano**, porque aqui no hay politica de fila que lo
    haga: sin ese filtro, una prueba que pasara con este almacen podria fallar
    con el de base, y entonces el almacen de mentira estaria mintiendo sobre algo
    mas que la persistencia.
    """

    def __init__(self) -> None:
        self._por_traza: dict[TraceId, TraceSummary] = {}

    async def put(self, summary: TraceSummary) -> None:
        self._por_traza[summary.trace_id] = summary

    async def get(self, trace_id: TraceId, *, tenant_id: str) -> TraceSummary | None:
        resumen = self._por_traza.get(trace_id)
        if resumen is None or resumen.tenant_id != tenant_id:
            return None
        return resumen

    async def latest_for_case(self, case_id: str, *, tenant_id: str) -> TraceSummary | None:
        delcaso = [
            s for s in self._por_traza.values() if s.case_id == case_id and s.tenant_id == tenant_id
        ]
        if not delcaso:
            return None
        return max(delcaso, key=lambda s: (s.created_at, s.trace_id))

    async def latest_for_cases(
        self, case_ids: Sequence[str], *, tenant_id: str
    ) -> dict[str, TraceSummary]:
        pedidos = set(case_ids)
        ultimos: dict[str, TraceSummary] = {}
        for resumen in self._por_traza.values():
            if resumen.tenant_id != tenant_id or resumen.case_id not in pedidos:
                continue
            previo = ultimos.get(resumen.case_id)
            if previo is None or (resumen.created_at, resumen.trace_id) > (
                previo.created_at,
                previo.trace_id,
            ):
                ultimos[resumen.case_id] = resumen
        return ultimos


_store: SummaryStore = InProcessSummaryStore()


def install_summary_store(store: SummaryStore) -> None:
    """Cambia donde viven los resumenes.

    Lo llama la raiz de composicion con `repository.DatabaseSummaryStore()`. Sin
    esa llamada, los resumenes viven solo en el proceso: es el valor por defecto
    porque hay un camino --el de arranque, el del corredor de evaluaciones-- que
    llega hasta el reporte sin base de datos.
    """
    global _store
    _store = store


def current_summary_store() -> SummaryStore:
    return _store


def reset_summaries() -> None:
    """Un almacen del proceso, vacio. Lo usan las pruebas."""
    global _store
    _store = InProcessSummaryStore()


async def open_summary(
    *,
    trace_id: TraceId,
    tenant_id: str,
    case_id: str,
    visitor_key_hash: str,
    turn_ref: str | None = None,
) -> TraceSummary:
    """Nace `recording`: la respuesta salio y el rastro todavia no llego.

    Recibe el **resumen** de la clave, ya calculado por quien tiene la clave
    (`tenancy.visitor_access.visitor_key_digest`, la unica definicion del
    proyecto). No la calcula aqui: envolverla obligaria a importar
    `tenancy.visitor_access`, que arrastra el punto de sesion, y esta superficie
    es justamente la que no puede arrastrarlo.
    """
    resumen = TraceSummary(
        trace_id=trace_id,
        tenant_id=tenant_id,
        case_id=case_id,
        visitor_key_hash=visitor_key_hash,
        turn_ref=turn_ref,
        created_at=_reloj(),
    )
    await _store.put(resumen)
    return resumen


async def record_trace(
    trace_id: TraceId, outcome: TraceOutcome, *, tenant_id: str
) -> TraceSummary | None:
    """Llego el rastro. Pasa a `ready` --o a `lost` si llego tarde.

    Comprobar el plazo **aqui** y no solo al leer es lo que hace la transicion
    determinista: si dependiera de que alguien lea, dos corridas identicas darian
    resultados distintos segun si el visitante miro o no.
    """
    resumen = await _store.get(trace_id, tenant_id=tenant_id)
    if resumen is None:
        return None
    if resumen.status is not TraceSummaryStatus.RECORDING:
        return resumen

    if _vencido(resumen, _reloj()):
        return await _perder(resumen, reason="trace_arrived_after_deadline")

    listo = resumen.evolve(
        nodes=outcome.nodes,
        clauses_retrieved=outcome.clauses_retrieved,
        clauses_verified=outcome.clauses_verified,
        latency_ms=outcome.latency_ms,
        cost=outcome.cost,
        status=TraceSummaryStatus.READY,
    )
    await _store.put(listo)
    return listo


def _costo(span: FinishedSpan) -> Money:
    cantidad = span.attributes.get("untangle.cost_usd")
    if span.attributes.get("untangle.cost_status") != CostStatus.MEASURED.value or cantidad is None:
        return Money.not_measured()
    return Money.measured(Decimal(str(cantidad)))


def _sumar(costos: Sequence[Money]) -> Money:
    """Medido solo si todo lo sumado se midio: un costo sin medir no entra como cero."""
    if any(not costo.is_measured for costo in costos):
        return Money.not_measured()
    return Money.measured(sum((costo.amount_usd or Decimal(0) for costo in costos), Decimal(0)))


def outcome_from_spans(spans: Sequence[FinishedSpan]) -> TraceOutcome | None:
    """Lo que trajo el rastro de un turno, armado con sus tramos; `None` si no alcanza.

    La latencia es la del tramo del turno; cada nodo trae su duracion y el costo de las
    llamadas que colgaron de el; el costo total es el de todas las llamadas. `None` sin el
    tramo del turno --no cerro, o sus tramos ya no estan-- o sin ningun nodo: un resumen
    listo sin nodos mentiria (`TraceSummary`).
    """
    turno = next((s for s in spans if s.level is SpanLevel.TURN), None)
    nodos = sorted((s for s in spans if s.level is SpanLevel.NODE), key=lambda s: s.started_at)
    if turno is None or not nodos:
        return None
    padre = {s.span_id: s.parent_span_id for s in spans}
    de_nodo = {n.span_id for n in nodos}

    def nodo_de(span: FinishedSpan) -> str | None:
        actual = span.parent_span_id
        while actual is not None and actual not in de_nodo:
            actual = padre.get(actual)
        return actual

    llamadas = [s for s in spans if s.level is SpanLevel.CALL]
    por_nodo: dict[str, list[Money]] = {n.span_id: [] for n in nodos}
    for llamada in llamadas:
        nodo = nodo_de(llamada)
        if nodo is not None:
            por_nodo[nodo].append(_costo(llamada))
    return TraceOutcome(
        nodes=tuple(
            NodeTiming(
                node=NodeName(str(n.attributes.get("untangle.node", n.name))),
                started_at=n.started_at,
                duration_ms=n.duration_ms,
                cost=_sumar(por_nodo[n.span_id]),
            )
            for n in nodos
        ),
        latency_ms=turno.duration_ms,
        cost=_sumar([_costo(llamada) for llamada in llamadas]),
    )


async def settle_summary(trace_id: TraceId, *, tenant_id: str) -> TraceSummary | None:
    """Completa el resumen de un turno con sus propios tramos y lo deja `ready`.

    Hasta el 2026-10-15 nadie lo hacia: los resumenes de las conversaciones de verdad se
    quedaban en `recording` y ni la pantalla del caso ni la de Telemetria podian enlazar su
    traza en Langfuse, aunque la traza si llegaba. Sin tramos suficientes no toca nada.
    """
    registrador = current_recorder()
    if not isinstance(registrador, BufferedRecorder):
        return None
    resultado = outcome_from_spans(registrador.finished(trace_id))
    if resultado is None:
        return None
    return await record_trace(trace_id, resultado, tenant_id=tenant_id)


async def mark_lost(trace_id: TraceId, *, tenant_id: str, reason: str) -> TraceSummary | None:
    """El rastro no va a llegar. `lost` es un valor, no un fallo (BR6.7).

    Se **guarda** como valor y no se deja como ausencia: un resumen que
    desapareciera no diria nada, y la cifra de resumenes perdidos --la que dice si
    el backend de trazas esta sano-- se calcula contando estas filas.
    """
    resumen = await _store.get(trace_id, tenant_id=tenant_id)
    if resumen is None or resumen.status is not TraceSummaryStatus.RECORDING:
        return resumen
    return await _perder(resumen, reason=reason)


def _vencido(resumen: TraceSummary, ahora: datetime) -> bool:
    return (ahora - resumen.created_at).total_seconds() >= SUMMARY_DEADLINE_SECONDS


async def _perder(resumen: TraceSummary, *, reason: str) -> TraceSummary:
    perdido = resumen.evolve(status=TraceSummaryStatus.LOST)
    await _store.put(perdido)
    # Se registra la perdida y **nada mas se detiene**: ni el caso, ni el gasto,
    # ni el corte (BR4.8, BR6.7).
    observability.emit("traces.summary_lost", trace_id=resumen.trace_id, reason=reason)
    return perdido


async def _vencer_si_toca(resumen: TraceSummary) -> TraceSummary:
    if resumen.status is TraceSummaryStatus.RECORDING and _vencido(resumen, _reloj()):
        return await _perder(resumen, reason="deadline_elapsed")
    return resumen


async def trace_summary_for(
    case_id: str, *, tenant_id: str, visitor_key_hash: str | None
) -> TraceSummary | None:
    """El resumen de un caso, **solo para el navegador que lo produjo** (BR6.6, C-23).

    A cualquier otro se le responde `None`: **igual que si no existiera**, no
    "prohibido". Un "prohibido" confirmaria que existe, que es la mitad de lo que
    el visitante de al lado querria saber.

    La comparacion es contra el **resumen** de la clave, nunca contra la clave
    (BR7.3), y en tiempo constante: distinguir por tiempo es otra forma de
    confirmar que existe.
    """
    resumen = await _store.latest_for_case(case_id, tenant_id=tenant_id)
    return await _del_dueno(resumen, visitor_key_hash)


async def trace_summary_for_staff(case_id: str, *, tenant_id: str) -> TraceSummary | None:
    """El resumen de un caso para quien entra con credencial de la aseguradora.

    Enmienda aditiva a C-23 del 2026-09-28, pedida por U14. Las dos lecturas de
    arriba comparan contra el resumen de la clave del navegador, que es lo correcto
    para un visitante: nadie ve la traza de otro. Un ajustador no tiene esa clave y
    **no la puede tener** --no fue quien converso--, asi que por ese camino la
    bandeja no podria mostrar nunca su sexto bloque.

    Aqui la autorizacion es otra y se dice en voz alta: **la credencial**, que la
    ruta ya verifico, mas la politica de fila, que no deja salir el resumen de otra
    aseguradora aunque este codigo se equivocara. No hay comparacion de dueno
    porque no hay dueno que comparar: el caso es de la aseguradora.
    """
    return await _store.latest_for_case(case_id, tenant_id=tenant_id)


async def trace_summaries_for_visitor(
    case_ids: Sequence[str], *, tenant_id: str, visitor_key_hash: str
) -> dict[str, TraceSummary]:
    """El ultimo resumen de cada caso, **solo los del navegador que los produjo** (BR6.6).

    Es `trace_summary_for` para varios casos con una sola lectura. La comparacion de dueno
    es la misma funcion, no una copia: el resumen de un caso de otro navegador no aparece
    en la respuesta, **igual que si no existiera**.
    """
    if not case_ids:
        return {}
    leidos = await _store.latest_for_cases(case_ids, tenant_id=tenant_id)
    propios = await asyncio.gather(
        *(_del_dueno(resumen, visitor_key_hash) for resumen in leidos.values())
    )
    return {resumen.case_id: resumen for resumen in propios if resumen is not None}


async def summary_by_trace(
    trace_id: TraceId, *, tenant_id: str, visitor_key_hash: str | None
) -> TraceSummary | None:
    """Lo mismo, por identificador de traza. Misma respuesta a quien no es dueno."""
    resumen = await _store.get(trace_id, tenant_id=tenant_id)
    return await _del_dueno(resumen, visitor_key_hash)


async def _del_dueno(
    resumen: TraceSummary | None, visitor_key_hash: str | None
) -> TraceSummary | None:
    """La unica comparacion de dueno del modulo, para que no haya dos que difieran."""
    if resumen is None:
        return None
    if visitor_key_hash is None or not hmac.compare_digest(
        resumen.visitor_key_hash, visitor_key_hash
    ):
        return None
    return await _vencer_si_toca(resumen)


__all__ = [
    "ALLOWED_ATTRIBUTES",
    "RECENT_TRACES",
    "RECORDER_CAPACITY",
    "SUMMARY_DEADLINE_SECONDS",
    "TURN_SPAN_NAME",
    "BufferedRecorder",
    "Clock",
    "FinishedSpan",
    "InProcessSummaryStore",
    "Span",
    "SpanAttributeError",
    "SpanAttributes",
    "SpanNestingError",
    "SpanRecorder",
    "SummaryStore",
    "TraceContext",
    "call_span",
    "case_moment_span",
    "current_context",
    "current_recorder",
    "current_summary_store",
    "current_trace_id",
    "install_clock",
    "install_recorder",
    "install_summary_store",
    "mark_lost",
    "node_span",
    "open_summary",
    "outcome_from_spans",
    "record_trace",
    "reset",
    "reset_summaries",
    "settle_summary",
    "summary_by_trace",
    "trace_summaries_for_visitor",
    "trace_summary_for",
    "trace_summary_for_staff",
    "turn_span",
]
