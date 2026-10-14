"""Lo que comparten los tres adaptadores de voz (U15, BR1.4, BR5.1, BR3.2).

Tres adaptadores --la transcripcion de Deepgram, Catalina en Cartesia y Aura-2 en
Deepgram-- hacen lo mismo alrededor de su protocolo, y ese "lo mismo" vive aqui
una sola vez para que no pueda divergir entre los tres:

1. **El techo antes de salir** (BR5.1). Si el techo esta cerrado no hay llamada:
   sale `BudgetExhausted` y no se reintenta.
2. **El gasto despues**, con su unidad de precio: segundos de audio para la
   transcripcion y caracteres para la sintesis, **contados aqui** con lo que se
   mando. Contados y no leidos del proveedor porque asi toda llamada tiene su
   recuento --tambien la que fallo a mitad--, y ninguna queda "no medida"
   (NFR14.4). Una llamada que el proveedor rechazo antes de abrir cuenta cero,
   que es lo que consumio.
3. **Los errores en la taxonomia cerrada** (BR1.4): `timeout`, `rate_limited`,
   `unavailable` o `invalid_response`, y el saldo agotado como parada. Ningun
   tipo del proveedor cruza.
4. **Nada de audio ni de texto en ningun evento** (BR3.2, SEC-U15.4). Los eventos
   de este archivo llevan proveedor, uso, tipo de error y recurso agotado, y
   ningun campo mas: ni el texto que se sintetizo, ni lo que se transcribio, ni
   el cuerpo del error, que es prosa del proveedor.

## Sin tramo de llamada, y por que

El adaptador de Gemini abre un tramo de llamada que cuelga de un tramo de nodo.
La voz **no corre dentro de un nodo**: corre en el manejador del turno de U16,
que no puede llamar al grafo de forma sincrona (convencion 5d). Un tramo de
llamada sin nodo padre es lo que el ayudante de trazas rechaza (AC4.8.1), asi
que la latencia de la voz la mide U16 alrededor del turno. Lo que si se atribuye
es el gasto: el caso sale del contexto de traza, igual que en Gemini.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from untangle import observability
from untangle.base import ProviderErrorKind, ProviderName, SpendSource, UnitKind, Use
from untangle.providers.ports import (
    SPEECH_AUDIO,
    BudgetExhausted,
    ExhaustedResource,
    ProviderError,
    SpendGate,
    UsageReport,
    UsageSink,
    UsageUnits,
)
from untangle.providers.speech_wire import (
    SpeechCaller,
    SpeechRequest,
    WireClosedError,
    WireRejectedError,
)
from untangle.providers.transport import TransportError
from untangle.telemetry.traces import api as trazas

__all__ = [
    "UN_SOLO_INTENTO",
    "SpeechCall",
    "SpeechMisconfiguredError",
    "WholeSamples",
    "audio_seconds",
    "catalog_lookup",
    "catalog_request",
    "kind_for_close",
    "kind_for_status",
]

#: El adaptador hace **una** llamada por invocacion y no reintenta: ante
#: `rate_limited` decide la politica del turno de U16, nunca el adaptador.
UN_SOLO_INTENTO = 1

#: Que codigo de estado HTTP es que tipo. Lo que no esta cae en
#: `invalid_response`, igual que en Gemini: un codigo que no reconocemos no es
#: razon para declarar caido a un proveedor que acaba de contestar.
_POR_CODIGO: dict[int, ProviderErrorKind] = {
    408: ProviderErrorKind.TIMEOUT,
    504: ProviderErrorKind.TIMEOUT,
    # No nos sirve con esta credencial. Desde el turno es indistinguible de caido.
    401: ProviderErrorKind.UNAVAILABLE,
    403: ProviderErrorKind.UNAVAILABLE,
    500: ProviderErrorKind.UNAVAILABLE,
    502: ProviderErrorKind.UNAVAILABLE,
    503: ProviderErrorKind.UNAVAILABLE,
    429: ProviderErrorKind.RATE_LIMITED,
}

#: Un 402 es "paga": saldo o cupo agotado, sin mirar el cuerpo.
CODIGO_DE_PAGO = 402

#: Que codigo de cierre de WebSocket es que tipo (RFC 6455, seccion 7.4.1).
_POR_CIERRE: dict[int, ProviderErrorKind] = {
    # Violacion de politica: el proveedor rechazo lo que se le mando (en
    # Deepgram, un audio que no pudo decodificar). Es un problema del contenido.
    1008: ProviderErrorKind.INVALID_RESPONSE,
    # Error interno del servidor.
    1011: ProviderErrorKind.UNAVAILABLE,
    # "Vuelva mas tarde": el proveedor esta saturado.
    1013: ProviderErrorKind.RATE_LIMITED,
    # Cierre normal **antes** de la respuesta que el contrato promete: el
    # proveedor termino sin decir lo que tenia que decir.
    1000: ProviderErrorKind.INVALID_RESPONSE,
}


def kind_for_status(status_code: int) -> ProviderErrorKind:
    """El tipo de un codigo de estado, sin mirar el cuerpo."""
    return _POR_CODIGO.get(status_code, ProviderErrorKind.INVALID_RESPONSE)


def kind_for_close(code: int | None) -> ProviderErrorKind:
    """El tipo de un cierre inesperado. Sin codigo --la red se corto-- es `unavailable`."""
    if code is None:
        return ProviderErrorKind.UNAVAILABLE
    return _POR_CIERRE.get(code, ProviderErrorKind.UNAVAILABLE)


def audio_seconds(byte_count: int) -> Decimal:
    """Los segundos de audio que ocupan esos bytes en el formato unico."""
    return Decimal(byte_count) / Decimal(SPEECH_AUDIO.bytes_per_second)


class SpeechMisconfiguredError(RuntimeError):
    """Este adaptador recibio una voz de otro proveedor. Es un fallo de cableado.

    No es uno de los cuatro tipos ni la parada: falla **antes** de llamar, porque
    llamar al proveedor equivocado con la clave equivocada es lo que las claves
    separadas existen para impedir.
    """


class WholeSamples:
    """Entrega el audio en muestras enteras aunque llegue partido (BR4.1).

    Una muestra de PCM de 16 bits son dos bytes, y un trozo de red puede cortar
    por la mitad de una. Si el trozo impar saliera tal cual, U16 recibiria un
    byte suelto y todo el audio siguiente sonaria desplazado: ruido. El byte que
    sobra se guarda y va delante del trozo siguiente.
    """

    def __init__(self) -> None:
        self._resto = b""

    def feed(self, trozo: bytes) -> bytes:
        junto = self._resto + trozo
        corte = len(junto) - (len(junto) % 2)
        self._resto = junto[corte:]
        return junto[:corte]

    @property
    def pending(self) -> bool:
        """Si quedo medio byte sin pareja al terminar: el audio llego truncado."""
        return bool(self._resto)


def _caso_actual() -> str | None:
    """El caso al que atribuir el gasto, del contexto de traza si lo hay."""
    contexto = trazas.current_context()
    return contexto.case_id if contexto is not None else None


@dataclass(frozen=True)
class SpeechCall:
    """Una llamada de voz: su techo, su gasto y sus errores, en un solo sitio.

    Se construye una por invocacion. `model` es el que cobra la tabla de precios
    --la terna es proveedor, modelo y unidad--, asi que su gasto nunca queda sin
    precio (NFR14.4).
    """

    provider: ProviderName
    model: str
    use: Use
    unit_kind: UnitKind
    gate: SpendGate
    usage: UsageSink

    async def open(self) -> None:
        """El techo, **antes** de tocar la red (BR5.1). Si levanta, no hay llamada."""
        try:
            await self.gate.ensure_open(provider=self.provider, use=self.use)
        except BudgetExhausted as parada:
            self._evento_de_parada(parada.resource)
            raise

    async def report(self, units: Decimal) -> None:
        """Lo que consumio esta llamada, contado aqui con lo que se mando."""
        await self.usage.report(
            UsageReport(
                provider=self.provider,
                model=self.model,
                use=self.use,
                units=(UsageUnits(unit_kind=self.unit_kind, units=units),),
                source=SpendSource.COUNTED_LOCALLY,
                case_ref=_caso_actual(),
            )
        )

    def failure(self, kind: ProviderErrorKind) -> ProviderError:
        """El error, ya en la taxonomia cerrada, con su evento sin contenido."""
        observability.emit(
            "providers.speech_call_failed",
            provider=self.provider.value,
            use=self.use.value,
            error_kind=kind.value,
        )
        return ProviderError(kind, provider=self.provider, use=self.use, attempt=UN_SOLO_INTENTO)

    def exhausted(self) -> BudgetExhausted:
        """El saldo o el cupo del proveedor se agotaron: parada, sin reintento."""
        self._evento_de_parada(ExhaustedResource.PROVIDER_QUOTA)
        return BudgetExhausted(
            ExhaustedResource.PROVIDER_QUOTA, provider=self.provider, use=self.use
        )

    def _evento_de_parada(self, resource: ExhaustedResource) -> None:
        observability.emit(
            "providers.budget_exhausted",
            provider=self.provider.value,
            use=self.use.value,
            resource=resource.value,
        )

    def from_rejection(
        self,
        rejected: WireRejectedError,
        *,
        says_exhausted: Callable[[Mapping[str, object]], bool],
    ) -> ProviderError | BudgetExhausted:
        """Un rechazo antes de abrir el flujo, traducido.

        `says_exhausted` es la regla de cada proveedor para leer en el cuerpo
        "se acabo el saldo". Se consulta ademas del 402, porque no todos los
        proveedores usan ese codigo para decirlo.
        """
        if rejected.status_code == CODIGO_DE_PAGO or says_exhausted(rejected.body):
            return self.exhausted()
        return self.failure(kind_for_status(rejected.status_code))

    def from_transport(self, failure: TransportError) -> ProviderError:
        """No hubo con quien hablar, o no contesto a tiempo."""
        kind = ProviderErrorKind.TIMEOUT if failure.timed_out else ProviderErrorKind.UNAVAILABLE
        return self.failure(kind)

    def from_close(self, closed: WireClosedError) -> ProviderError:
        """El canal se cerro antes de tiempo."""
        return self.failure(kind_for_close(closed.code))


# --- La consulta de catalogo: la lista de voces, que no cuesta -----------------

#: Sin prisa: nadie espera una voz mientras se consulta un catalogo. Solo la usan
#: los comandos a mano (`voice:contract-live`), nunca el turno.
_CATALOGO_CONEXION_MS = 5000
_CATALOGO_LECTURA_MS = 15000


def catalog_request(path: str) -> SpeechRequest:
    """Una consulta de catalogo: la lista de voces o la ficha de una voz."""
    return SpeechRequest(
        path=path,
        connect_timeout_ms=_CATALOGO_CONEXION_MS,
        read_timeout_ms=_CATALOGO_LECTURA_MS,
    )


async def catalog_lookup(
    caller: SpeechCaller, request: SpeechRequest, *, provider: ProviderName
) -> tuple[int, Mapping[str, object]]:
    """La consulta, con el cliente del uso `voice` y el fallo de red ya traducido.

    Devuelve el codigo y el cuerpo: que un codigo distinto de 200 signifique "esa
    voz no esta publicada" lo decide el catalogo de cada adaptador. Lo que no
    llega a tener codigo --la red no esta, o no contesto a tiempo-- sale en la
    taxonomia cerrada, con su evento sin contenido, igual que una llamada.
    """
    try:
        return await caller.get_json(request, provider=provider, use=Use.VOICE)
    except TransportError as fallo:
        kind = ProviderErrorKind.TIMEOUT if fallo.timed_out else ProviderErrorKind.UNAVAILABLE
        observability.emit(
            "providers.speech_call_failed",
            provider=provider.value,
            use=Use.VOICE.value,
            error_kind=kind.value,
        )
        raise ProviderError(
            kind, provider=provider, use=Use.VOICE, attempt=UN_SOLO_INTENTO
        ) from None
