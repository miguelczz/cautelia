"""La politica de fallo del corredor, en sus tres capas (REL-U1.5).

El corredor **no ve tipos de error del proveedor**. Los ve traducidos a la
taxonomia cerrada de cuatro valores que fija la convencion 8(a) del equipo, y
decide sobre ella. Esa taxonomia describe *que clase de fallo fue*; lo que el
resultado del caso guarda es *por que no se pudo medir*, que es un vocabulario
distinto y mas grueso. La traduccion entre los dos esta aqui y no implicita en
un `if` perdido.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum

from untangle.evals.models import NotMeasuredCause, RootCause


class ProviderErrorKind(StrEnum):
    """La taxonomia cerrada de la frontera del proveedor (convencion 8a)."""

    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    INVALID_RESPONSE = "invalid_response"


class ProviderError(Exception):
    """Lo unico que un adaptador deja cruzar hacia el corredor.

    El tipo del SDK del proveedor no llega hasta aqui: se traduce en su
    adaptador (ADR-018).
    """

    def __init__(self, kind: ProviderErrorKind, detail: str = "") -> None:
        super().__init__(f"{kind.value}: {detail}" if detail else kind.value)
        self.kind = kind
        self.detail = detail


class BudgetExhaustedError(Exception):
    """El registro de gasto alcanzo el techo del proyecto antes de la llamada.

    No la levanta un proveedor: la levanta el corredor por su cuenta, y por eso
    no se reintenta nunca. Reintentar un presupuesto agotado gasta exactamente
    lo que se esta intentando proteger.
    """


class QuotaExhaustedError(Exception):
    """El proveedor senalo que la cuota se acabo, no que hay que esperar.

    **U1 no la levanta nunca.** Existe porque la taxonomia de cuatro valores no
    puede distinguir "demasiadas peticiones ahora mismo" de "tu cuota se acabo",
    y esa distincion la trae la frontera de U5 `provider-platform`. El corredor
    ya sabe que hacer con ella: no la reintenta y cuenta para el cortacircuitos.
    Dejarla escrita aqui es lo que evita que U5 tenga que inventar un mecanismo
    nuevo y que el corte por cuota llegue tarde.
    """


class TargetUnavailableError(Exception):
    """El caso necesita un despliegue vivo y no hay ninguno al que apuntar.

    La levanta una sonda contra el despliegue --hoy, el escenario RT-4--. No es
    un fallo del producto: es una compuerta que no se pudo ejecutar, y el
    proyecto tiene una sola respuesta para eso, que es declararla "no medida" con
    su causa. Nunca se omite y nunca se da por verde.
    """


class RunnerTimeoutError(Exception):
    """El caso supero el tiempo maximo que el propio corredor le da.

    Es un limite nuestro, no del proveedor, y por eso no cuenta para el
    cortacircuitos.
    """


class ChannelDriverMissingError(LookupError):
    """El caso declara un canal cuyo conductor no esta registrado todavia (PASO 0.2).

    No es un fallo del proveedor ni una cuota agotada: es que la conducta que
    el caso mide no esta construida. Antes de esta excepcion, `_execute`
    levantaba un `LookupError` a secas, que esta capa no sabia traducir
    (`classify` devolvia `None`) y que por lo tanto subia sin clasificar y
    tumbaba la corrida entera -- exactamente lo que le paso a DS-3 en cuanto
    sus 40 casos, todos de canal `chat`, se sumaron a la corrida sin que
    ningun conductor de chat estuviera registrado.

    El caso previo de la rama evaluada tiene que poder reportar esto --
    fallado, con su causa -- sin tumbar el resto de la corrida: un caso que
    hace caer la corrida entera no se ha visto fallar, se ha visto explotar.
    """


class TranscriptCheckMissingError(LookupError):
    """Un caso con canal corrio y un criterio de su transcripcion no esta registrado.

    Los criterios de transcripcion los aplica el corredor a todo caso con canal, sin que el
    caso los pida. Si nadie registro uno, dejar pasar la conversacion sin leerla seria justo
    el defecto que existen para cerrar: se falla nombrando el criterio, igual que un
    conductor ausente.
    """

    def __init__(self, criterion: str, message: str) -> None:
        super().__init__(message)
        self.criterion = criterion


@dataclass(frozen=True)
class Verdict:
    """Que hacer con un fallo: si se reintenta y como se registra."""

    transient: bool
    #: `None` significa que el caso queda `failed`, no `not_measured`.
    cause: NotMeasuredCause | None
    #: Si cuenta para abrir el cortacircuitos de la capa 3.
    counts_for_breaker: bool
    #: La clave de `criteria_results` con la que un fallo `failed` (cause=None)
    #: se registra. Un `invalid_response` es el proveedor respondiendo con algo
    #: que no sirve; un conductor ausente es una conducta que no existe
    #: todavia. Son dos causas raiz distintas y el reporte las tiene que poder
    #: distinguir, no agrupar bajo la misma clave.
    failure_criterion: str = "provider_response"
    #: La causa raiz con la que se registra un fallo `failed` (cause=None).
    #: `None` deja el campo vacio, que es lo correcto cuando la causa depende
    #: del caso y no del tipo de fallo. Un conductor ausente si la tiene fija:
    #: la conducta no esta construida (U21, BR1.1).
    root_cause: RootCause | None = None


# Capa 1 -- la traduccion, escrita una sola vez.
#
# `invalid_response` no es un caso no medido: el proveedor respondio, y lo que
# devolvio no sirve. Eso es exactamente lo que la evaluacion mide, y declararlo
# "no medido" convertiria un fallo de calidad en un problema de infraestructura.
# Es la misma linea que el proyecto traza entre "no hay clausula" y "no pude
# verificar": la que separa "esto esta mal" de "no lo se".
#
# `rate_limited` persistente se registra como `provider_unavailable` y **no**
# cuenta para el cortacircuitos: un proveedor senala con el mismo codigo
# "demasiadas peticiones ahora mismo" y "tu cuota se acabo", y el dato que los
# distingue lo trae U5 `provider-platform`, no U1. La consecuencia esta acotada y
# dicha: una cuota agotada disfrazada de tasa momentanea gasta un reintento por
# caso hasta que el techo de gasto corte.
TRADUCCION: dict[ProviderErrorKind, Verdict] = {
    ProviderErrorKind.TIMEOUT: Verdict(
        transient=True,
        cause=NotMeasuredCause.PROVIDER_TIMEOUT,
        counts_for_breaker=False,
    ),
    ProviderErrorKind.RATE_LIMITED: Verdict(
        transient=True,
        cause=NotMeasuredCause.PROVIDER_UNAVAILABLE,
        counts_for_breaker=False,
    ),
    ProviderErrorKind.UNAVAILABLE: Verdict(
        transient=True,
        cause=NotMeasuredCause.PROVIDER_UNAVAILABLE,
        counts_for_breaker=False,
    ),
    ProviderErrorKind.INVALID_RESPONSE: Verdict(
        transient=False,
        cause=None,
        counts_for_breaker=False,
    ),
}

VEREDICTO_DE_PRESUPUESTO = Verdict(
    transient=False,
    cause=NotMeasuredCause.BUDGET_EXHAUSTED,
    counts_for_breaker=True,
)

VEREDICTO_DE_TIEMPO_DEL_CORREDOR = Verdict(
    transient=False,
    cause=NotMeasuredCause.RUNNER_TIMEOUT,
    counts_for_breaker=False,
)

VEREDICTO_DE_CUOTA = Verdict(
    transient=False,
    cause=NotMeasuredCause.QUOTA_EXHAUSTED,
    counts_for_breaker=True,
)

# No se reintenta y **no** cuenta para el cortacircuitos: que no haya despliegue
# al que apuntar no mejora esperando, y tampoco es senal de que el resto de la
# corrida vaya a fallar.
VEREDICTO_DE_DESPLIEGUE_AUSENTE = Verdict(
    transient=False,
    cause=NotMeasuredCause.TARGET_UNAVAILABLE,
    counts_for_breaker=False,
)

# No se reintenta -- reintentar no hace aparecer un conductor -- y **no** cuenta
# para el cortacircuitos: que falte el conductor de un canal no dice nada sobre
# si el caso siguiente va a fallar. `cause=None` dice "failed", no "not_measured"
# (PASO 0.2): es la conducta que el caso mide, todavia sin construir, y eso es
# exactamente lo que un caso previo tiene que poder reportar.
VEREDICTO_DE_CONDUCTOR_AUSENTE = Verdict(
    transient=False,
    cause=None,
    counts_for_breaker=False,
    failure_criterion="channel_driver",
    root_cause=RootCause.NOT_BUILT,
)


def verdict_for_missing_transcript_check(criterion: str) -> Verdict:
    """Es la misma forma que un conductor ausente y por la misma razon: la conducta que se
    mide --que nada de lo dicho afirme cobertura ni copie un prompt-- no esta cableada, y eso
    se reporta como caso en rojo con el criterio que falta, nunca como un hueco de
    infraestructura ni en verde."""
    return Verdict(
        transient=False,
        cause=None,
        counts_for_breaker=False,
        failure_criterion=criterion,
        root_cause=RootCause.NOT_BUILT,
    )


#: Las excepciones de un solo veredicto fijo, sin dato propio que traducir --al
#: reves que `ProviderError`, que necesita mirar `.kind`--. Una tabla en vez de
#: un `if` por tipo mantiene `classify` en pocas sentencias de retorno.
_VEREDICTOS_FIJOS: tuple[tuple[type[Exception], Verdict], ...] = (
    (BudgetExhaustedError, VEREDICTO_DE_PRESUPUESTO),
    (QuotaExhaustedError, VEREDICTO_DE_CUOTA),
    (RunnerTimeoutError, VEREDICTO_DE_TIEMPO_DEL_CORREDOR),
    (TargetUnavailableError, VEREDICTO_DE_DESPLIEGUE_AUSENTE),
    (ChannelDriverMissingError, VEREDICTO_DE_CONDUCTOR_AUSENTE),
)


def _tipo_del_adaptador(error: Exception) -> ProviderErrorKind | None:
    """El tipo de un error de proveedor **de verdad**, leido por su valor.

    Las sondas que llaman a un modelo levantan el error del adaptador
    (`untangle.providers.ports.ProviderError`), que no es la clase de este modulo
    y que el corredor no importa. Lleva la misma taxonomia cerrada en `kind`. Hasta
    el 2026-10-11 no se reconocia, y **un solo plazo vencido tumbaba la corrida
    entera sin guardar nada**: paso en la corrida completa de ese dia.
    """
    tipo = getattr(error, "kind", None)
    valor = getattr(tipo, "value", tipo)
    if not isinstance(valor, str):
        return None
    try:
        return ProviderErrorKind(valor)
    except ValueError:
        return None


def classify(error: Exception) -> Verdict | None:
    """El veredicto de un fallo, o `None` si no es un fallo que esta capa conozca."""
    if isinstance(error, ProviderError):
        return TRADUCCION[error.kind]
    if isinstance(error, TranscriptCheckMissingError):
        return verdict_for_missing_transcript_check(error.criterion)
    del_adaptador = _tipo_del_adaptador(error)
    if del_adaptador is not None:
        return TRADUCCION[del_adaptador]
    for tipo, veredicto in _VEREDICTOS_FIJOS:
        if isinstance(error, tipo):
            return veredicto
    return None


# Capa 2 -- un reintento para lo pasajero, cero para la cuota.
#
# Un reintento y no tres: el segundo intento cubre el parpadeo de red, que es el
# fallo que de verdad ocurre; del tercero en adelante se paga tiempo por un caso
# que casi nunca se recupera.
REINTENTOS_PARA_LO_PASAJERO = 1
ESPERA_BASE_SEGUNDOS = 0.5
DISPERSION_MAXIMA_SEGUNDOS = 0.25


def backoff_seconds(case_key: str, attempt: int) -> float:
    """La espera antes de un reintento, con dispersion por caso.

    La dispersion **no es aleatoria**: sale de un hash del identificador del
    caso. Reparte los reintentos para que varios casos no vuelvan sincronizados,
    que es lo que la dispersion tiene que conseguir, y a la vez deja que dos
    corridas del mismo commit tarden lo mismo. Una espera aleatoria compraria lo
    primero pagando con lo segundo, y lo segundo es la propiedad que esta unidad
    existe para sostener.
    """
    digest = hashlib.sha256(case_key.encode("utf-8")).digest()
    fraccion = digest[0] / 255
    return ESPERA_BASE_SEGUNDOS * attempt + DISPERSION_MAXIMA_SEGUNDOS * fraccion


# Capa 3 -- corte de la corrida tras tres fallos seguidos de cuota o presupuesto.
#
# Uno puede ser un caso raro; tres seguidos es que se acabo. Recorrer los casos
# restantes fallando uno por uno gasta tiempo y no anade informacion.
FALLOS_SEGUIDOS_QUE_ABREN_EL_CORTE = 3


class CircuitBreaker:
    """Cuenta fallos seguidos de cuota o presupuesto. No se vuelve a cerrar.

    Dentro de la misma corrida no hay nada que sondear: una cuota agotada no se
    repone en segundos.
    """

    def __init__(self, threshold: int = FALLOS_SEGUIDOS_QUE_ABREN_EL_CORTE) -> None:
        self._threshold = threshold
        self._consecutive = 0
        self._open = False
        self._cause: NotMeasuredCause | None = None

    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def cause(self) -> NotMeasuredCause | None:
        return self._cause

    def record(self, verdict: Verdict | None) -> None:
        """Registra el desenlace de un caso. `None` significa que no fallo."""
        if verdict is None or not verdict.counts_for_breaker:
            self._consecutive = 0
            return
        self._consecutive += 1
        self._cause = verdict.cause
        if self._consecutive >= self._threshold:
            self._open = True
