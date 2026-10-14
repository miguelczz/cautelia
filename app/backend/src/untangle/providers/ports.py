"""Los cuatro puertos que usa el nucleo, y nada mas (C-16, BR1.1).

Es lo que ven U7, U8, U10, U11, U15 y U21. Su propiedad mas util no es lo que
tiene sino lo que **no** tiene: ningun SDK, ningun cliente, ningun tipo de
proveedor. Por eso un nodo se puede probar con un doble sin instalar nada y sin
tener una clave.

## Las dos cosas que el tipo impide, y por que se escriben asi

**1. El texto de origen externo no puede ocupar la posicion de instruccion**
(SEC-U5.16, RT-1, RT-2, RT-5). Hay dos tipos distintos de texto y no se pueden
confundir:

- `ExternalText`: lo que escribio el asegurado, lo que trajo el corpus, lo que
  venia en un documento. Solo cabe en `PromptPart`, que es contenido.
- `InstructionText`: la instruccion de sistema. **La produce un solo sitio**,
  `prompts.py`, leyendola de su archivo versionado.

Los dos son `NewType` sobre `str`, y `NewType` no es convertible en el otro
sentido: pasar un `ExternalText` donde va un `InstructionText` **no compila**.
Lo que sostiene la garantia de verdad, sin embargo, no es el tipo --que se borra
en ejecucion, igual que `Redacted` en U3-- sino que **ninguna funcion de esta
unidad acepta una cadena para la posicion de instruccion**: el cargador recibe un
identificador y un idioma, nunca texto. No hay donde intercalar porque no hay
argumento donde meterlo.

**2. Saldo agotado no es uno de los cuatro errores.** `ProviderErrorKind` tiene
cuatro valores y los cuatro admiten politica de reintento del nodo.
`BudgetExhausted` esta **fuera** de esa lista a proposito: significa "para", y
meterlo dentro invitaria a reintentarlo (BR2.3, reliability-design).

## De donde viene el vocabulario cerrado

`Use`, `ProviderName`, `UnitKind`, `SpendSource`, `UnitCount` y
`ProviderErrorKind` vienen de `untangle/base.py`, que es la hoja sin
dependencias del aplicativo. Estuvieron en `telemetry/` mientras la contabilidad
y las trazas fueron las unicas piezas construidas que los necesitaban, y
subieron en el bloque F: los escriben tambien el adaptador y este archivo, asi
que no son vocabulario de la contabilidad.

Con eso, **este archivo no importa nada de `telemetry/`** --la primera regla de
direccion de `nfr-design/logical-components.md`-- y el contrato de importacion
que lo comprueba se puede escribir como la frase entera en vez de con una lista
de excepciones que nadie sabria leer en seis semanas.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, NewType, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from untangle.base import (
    Frozen,
    Locale,
    ProviderErrorKind,
    ProviderName,
    SpendSource,
    UnitCount,
    UnitKind,
    Use,
)

if TYPE_CHECKING:
    # Solo para el comprobador de tipos: `Redacted` es un `NewType` que se borra
    # en ejecucion, y `compliance.redaction.api` arrastra el motor de
    # reconocedores. Importarlo de verdad meteria esa dependencia en todo modulo
    # que consuma un puerto, que es justo lo que este archivo existe para
    # impedir.
    from untangle.compliance.redaction.api import Redacted

__all__ = [
    "SPEECH_AUDIO",
    "AudioEncoding",
    "AudioFormat",
    "BudgetExhausted",
    "Embedder",
    "ExhaustedResource",
    "ExternalText",
    "GenerationResult",
    "InstructionText",
    "ListenEvent",
    "Prompt",
    "PromptPart",
    "PromptRef",
    "ProviderError",
    "ProviderErrorKind",
    "SessionTextToSpeech",
    "SpeechStarted",
    "SpeechToText",
    "SpendGate",
    "SystemInstruction",
    "TextGenerator",
    "TextToSpeech",
    "Transcript",
    "UsageReport",
    "UsageSink",
    "UsageUnits",
    "Vector",
    "VoiceRef",
    "WordHypothesis",
]


# --- Los dos registros de texto, que no se pueden confundir -------------------

#: Texto de origen externo: el asegurado, el corpus recuperado, un documento
#: adjunto. Entra al modelo como **contenido delimitado** y nunca como
#: instruccion (regla de `project.md`, SEC-U5.16).
ExternalText = NewType("ExternalText", str)

#: El texto de una instruccion de sistema. Lo produce **solo** `prompts.py`,
#: leyendo el archivo versionado de ese prompt y ese idioma (BR1.7).
InstructionText = NewType("InstructionText", str)

#: Un vector de embeddings, ya truncado y normalizado por su adaptador. Coma
#: flotante es lo correcto aqui: no es dinero, es geometria.
type Vector = tuple[float, ...]


class PromptRef(Frozen):
    """Que prompt se uso, en que idioma y con que contenido exacto (BR1.7).

    El hash no es decoracion: viaja en la traza y en el registro de la corrida de
    evaluaciones, y cambiarlo dispara la compuerta. Sin el, dos corridas del
    mismo commit con el archivo editado a mano se compararian como si fueran la
    misma.
    """

    prompt_id: str = Field(min_length=1)
    locale: Locale
    #: SHA-256 en hexadecimal del contenido del archivo. Misma forma que exige el
    #: atributo `untangle.prompt_hash` del ayudante de tramos.
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SystemInstruction(Frozen):
    """La instruccion de sistema, con la constancia de de donde salio.

    **No se construye con texto de nadie.** La unica via publica para obtener una
    es `prompts.load_system_instruction(prompt_id, locale)`, que lee el archivo
    versionado. El tipo de su texto --`InstructionText`-- cierra la otra puerta:
    un `ExternalText` ahi dentro no compila.
    """

    ref: PromptRef
    text: InstructionText


class PromptPart(Frozen):
    """Un turno de la conversacion. Su texto es **siempre** de origen externo.

    Es la unica posicion del prompt donde entra lo que escribio una persona, y
    por eso su tipo lo dice: `ExternalText`. Un `str` cualquiera no compila, asi
    que no hay forma de meter aqui algo que nadie marco como externo, ni de
    llevar lo de aqui a la instruccion.
    """

    #: Los dos roles de la conversacion, con la grafia del proveedor.
    role: str = Field(pattern=r"^(user|model)$")
    text: ExternalText


class Prompt(Frozen):
    """Lo que se le pide al modelo: una instruccion y un contenido, separados.

    Separados **en el tipo y en la peticion**, no por convencion: la API del
    proveedor distingue las dos posiciones y el adaptador usa esa separacion
    nativa en vez de armar una sola cadena. No hay ningun punto donde las dos se
    junten (capa 7 del diseno de seguridad).
    """

    instruction: SystemInstruction
    parts: tuple[PromptPart, ...] = Field(min_length=1)


# --- Lo que se reporta a la contabilidad --------------------------------------


class UsageUnits(Frozen):
    """Cuantas unidades de una clase cobro una llamada.

    Una llamada de generacion produce **dos** de estas --tokens de entrada y de
    salida-- porque el proveedor las cobra a precios distintos. Convertirlas a
    una unidad comun perderia el precio de lista con el que se calculo cada una,
    que es lo que AC4.8.4 exige guardar.
    """

    unit_kind: UnitKind
    units: UnitCount


class UsageReport(Frozen):
    """Lo que una llamada consumio, tal como el adaptador lo supo.

    El adaptador **no** calcula el costo ni escribe la fila: reporta unidades y
    la contabilidad las valora con la tabla de precios versionada (C-17). Asi el
    precio vive en un solo sitio y el adaptador no tiene forma de publicar una
    cifra con otro precio.

    `units` puede venir **vacia**: una llamada que fallo antes de que el
    proveedor contara nada no consumio unidades que el adaptador pueda reportar.
    Que fila produce eso lo decide la contabilidad, no el adaptador.
    """

    provider: ProviderName
    #: El identificador exacto del modelo, nunca un alias movil (BR1.4).
    model: str = Field(min_length=1)
    use: Use
    units: tuple[UsageUnits, ...] = ()
    source: SpendSource
    #: El caso al que atribuir el gasto, si la llamada ocurrio dentro de un turno
    #: con contexto de traza abierto. Nulo para lo que no tiene caso
    #: --evaluaciones, generacion, operacion-- y para una llamada fuera de turno.
    case_ref: str | None = None


class UsageSink(Protocol):
    """Quien recibe el uso reportado: la contabilidad de C-17.

    Es un puerto y no un import directo, y **la razon sobrevive a que las dos
    piezas existan**: `untangle.providers` esta encima de `untangle.telemetry` en
    el contrato de capas, asi que la contabilidad no puede leer un
    `UsageReport`, y este archivo no puede llamarla sin arrastrar su base de
    datos hasta lo que ven seis unidades. Las conecta la raiz de composicion, que
    es el unico sitio que ve los dos lados.
    """

    async def report(self, usage: UsageReport) -> None: ...


class SpendGate(Protocol):
    """El techo de gasto, consultado **antes** de cada llamada de voz (BR5.1, U15).

    Es un puerto por la misma razon que `UsageSink`: el techo vive en la
    contabilidad, que esta debajo de `providers` en el contrato de capas, y lo
    conecta la raiz de composicion. El adaptador no sabe como se decide; sabe que
    si esto levanta, **no llama**.

    Levanta `BudgetExhausted` con el recurso `PROJECT_CAP` cuando el techo esta
    cerrado o no se pudo leer. No devuelve un booleano a proposito: un booleano
    se puede olvidar de mirar, y una excepcion no.
    """

    async def ensure_open(self, *, provider: ProviderName, use: Use) -> None: ...


# --- Lo que devuelve una generacion -------------------------------------------


@dataclass(frozen=True)
class GenerationResult:
    """Lo que el modelo respondio, ya validado dentro del adaptador.

    Es un `dataclass` y no un modelo de Pydantic por `parsed`: un campo declarado
    `BaseModel` dentro de un modelo de Pydantic se **revalida** contra `BaseModel`
    al construirse, y eso descarta en silencio los campos de la subclase. El
    objeto que llega aqui ya paso por su esquema dentro del adaptador; volver a
    validarlo contra el tipo base solo podria perderlo.
    """

    #: El texto de la respuesta cuando no se pidio esquema. Nulo cuando si.
    text: str | None
    #: La respuesta ya validada contra el esquema pedido. Nula cuando no se pidio.
    parsed: BaseModel | None
    usage: UsageReport
    #: Que prompt la produjo. Viaja hasta la traza y el registro de evaluaciones.
    prompt: PromptRef

    def parsed_as[T: BaseModel](self, schema: type[T]) -> T:
        """La respuesta validada, con su tipo concreto.

        Existe para que cada consumidor no escriba su propia comprobacion: con
        `parsed: BaseModel | None` el comprobador de tipos no sabe cual es, y
        veinte `assert isinstance(...)` repartidos son veinte sitios donde uno
        puede faltar.
        """
        if not isinstance(self.parsed, schema):
            encontrado = type(self.parsed).__name__
            msg = (
                f"se pidio la respuesta como '{schema.__name__}' y lo que hay es "
                f"'{encontrado}': el esquema de la llamada y el de la lectura tienen "
                "que ser el mismo"
            )
            raise TypeError(msg)
        return self.parsed


# --- Los errores: cuatro, y una parada que no es ninguno de ellos -------------


class ProviderError(Exception):
    """El unico error que un adaptador deja salir (BR2.1, BR2.2).

    **Su representacion esta definida, no heredada** (capa 2 del diseno de
    seguridad, regla 2): lleva el tipo, el proveedor, el uso y el numero de
    intento, y **nada mas**. Ni el prompt, ni la respuesta, ni la clave. Un error
    que arrastrara el cuerpo de la respuesta convertiria el camino de fallo en el
    punto de fuga que esta unidad evita.

    Los cuatro tipos admiten politica de reintento del nodo, que decide el
    ejecutor comun de U12; el adaptador no reintenta (BR2.4).
    """

    def __init__(
        self,
        kind: ProviderErrorKind,
        *,
        provider: ProviderName,
        use: Use,
        attempt: int = 1,
    ) -> None:
        self.kind = kind
        self.provider = provider
        self.use = use
        self.attempt = attempt
        super().__init__(self._mensaje())

    def _mensaje(self) -> str:
        return (
            f"{self.kind.value} en '{self.provider.value}' para el uso "
            f"'{self.use.value}' (intento {self.attempt})"
        )

    def __str__(self) -> str:
        return self._mensaje()

    def __repr__(self) -> str:
        return f"ProviderError({self._mensaje()})"


class ExhaustedResource(StrEnum):
    """Que se acabo. La senal lo **nombra** para no tener que deducirlo.

    La regla del proyecto dice que cuando se acaba un saldo el trabajo se
    detiene, se identifica que se acabo y Miguel decide. Sin este campo, la
    identificacion habria que hacerla mirando la consola del proveedor.
    """

    #: El techo acumulado del proyecto en su ventana de 90 dias (D11).
    PROJECT_CAP = "project_cap"
    #: El saldo o la cuota de ese proveedor para ese uso, del lado del proveedor.
    PROVIDER_QUOTA = "provider_quota"


# El nombre sin sufijo `Error` lo deletrea C-16 y lo consumen U7, U8, U10, U11,
# U15 y U21: el contrato manda sobre la preferencia del linter, igual que con la
# firma del catalogo de textos en C-21. Y la ausencia del sufijo dice algo
# cierto: esto no es un error del proveedor, es una senal de parada.
class BudgetExhausted(Exception):  # noqa: N818
    """Saldo o cuota agotados: **no** se reintenta y no se degrada a otro proveedor.

    Deliberadamente **fuera** de `ProviderErrorKind`: los cuatro de esa lista
    admiten politica de reintento y este significa "para" (BR2.3). El
    cortacircuitos tampoco se abre por esto: el proveedor esta sano; lo que se
    acabo es el dinero.

    Su representacion sigue la misma regla que `ProviderError`: nombra el
    proveedor, el uso y que se acabo, y nada mas.
    """

    def __init__(
        self,
        resource: ExhaustedResource,
        *,
        provider: ProviderName,
        use: Use,
    ) -> None:
        self.resource = resource
        self.provider = provider
        self.use = use
        super().__init__(self._mensaje())

    def _mensaje(self) -> str:
        return (
            f"se agoto '{self.resource.value}' en '{self.provider.value}' para el uso "
            f"'{self.use.value}': no se reintenta y no se recarga por iniciativa propia"
        )

    def __str__(self) -> str:
        return self._mensaje()

    def __repr__(self) -> str:
        return f"BudgetExhausted({self._mensaje()})"


# --- Los tipos de la voz, que llena U15 ---------------------------------------


class VoiceRef(Frozen):
    """Una voz concreta que un adaptador de sintesis sabe usar (C-16, U15).

    Lleva **las cuatro cosas** que la llamada necesita y ninguna mas: con quien
    se habla, con que modelo, con que voz y en que idioma. El modelo va aparte de
    la voz porque la tabla de precios cobra por modelo --la terna es proveedor,
    modelo y unidad-- y una voz nueva del mismo modelo no tiene que tocar esa
    tabla. Todo anclado por identificador exacto, nunca por un alias movil
    (BR1.4).
    """

    provider: ProviderName
    model: str = Field(min_length=1)
    voice_id: str = Field(min_length=1)
    language: Locale


class AudioEncoding(StrEnum):
    """Como viajan las muestras. Uno solo, y a proposito (BR4.1)."""

    #: PCM lineal de 16 bits con signo, extremo menor primero.
    PCM_S16LE = "pcm_s16le"


class AudioFormat(Frozen):
    """El formato del audio que cruza los puertos de voz (entidad del mismo nombre)."""

    encoding: AudioEncoding
    sample_rate_hz: int = Field(ge=8000)
    channels: int = Field(ge=1, le=1)

    @property
    def bytes_per_second(self) -> int:
        """Cuantos bytes ocupa un segundo. PCM de 16 bits: dos por muestra."""
        return self.sample_rate_hz * 2 * self.channels


#: **El** formato de audio del aplicativo (CG-U15-1): PCM de 16 bits, mono, a
#: 24 kHz. Lo entregan los dos adaptadores de sintesis --Cartesia y Aura-2
#: ofrecen los dos esa salida-- y lo recibe la transcripcion, asi que dentro del
#: aplicativo hay un solo formato y U16 convierte en la frontera de su
#: transporte. Vive en el codigo y no en configuracion (`entities.md`): cambiarlo
#: exige tocar la conversion de U16, y eso es un cambio de codigo.
SPEECH_AUDIO = AudioFormat(encoding=AudioEncoding.PCM_S16LE, sample_rate_hz=24000, channels=1)


class WordHypothesis(Frozen):
    """Una palabra transcrita, con su tiempo y su confianza (PA-2).

    La confianza es **nula cuando el proveedor no la manda, nunca cero** (BR3.1):
    cero diria "el proveedor esta seguro de que se equivoco", que es una
    afirmacion distinta, y la politica de pedir que se repita (AC1.23.3) la
    trataria como la peor palabra posible.

    Tiempos y confianza van en coma flotante: no son dinero ni unidades
    cobrables, son geometria del audio.
    """

    text: ExternalText
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)


class Transcript(Frozen):
    """Un trozo de transcripcion, parcial o final (C-16, U15).

    Su texto es de origen externo por definicion --lo dijo una persona-- y por
    eso lleva ese tipo: lo que se transcribe no puede acabar en la posicion de
    instruccion de ningun prompt.

    `language` es el idioma **detectado** en modo multiidioma, y es nulo cuando
    el proveedor no lo dice. Nulo y no el idioma pedido: inventarlo esconderia
    justo el caso en que la deteccion no funciono.
    """

    text: ExternalText
    is_final: bool
    words: tuple[WordHypothesis, ...] = ()
    language: Locale | None = None


class SpeechStarted(Frozen):
    """El reconocedor oyo que alguien empezo a hablar (deteccion de voz del proveedor).

    Llega en decimas de segundo, mucho antes que el primer parcial con palabras, y por eso
    sirve para una sola cosa: saber que quien hizo una pausa **retomo** la frase. No dice
    que se dijo ni que termino, y puede ser ruido; quien lo usa tiene que seguir andando
    sin el, porque ningun proveedor lo garantiza.

    `at_s` son los segundos de audio recibidos desde que se abrio el canal: el mismo eje
    que `WordHypothesis`. No es un instante de pared; tampoco se convierte aqui.
    """

    at_s: float = Field(ge=0)


#: Lo que entrega la escucha: transcritos, y la senal de voz entre ellos.
type ListenEvent = Transcript | SpeechStarted


# --- Los cuatro puertos -------------------------------------------------------
# Los adaptadores **heredan** de estos `Protocol` para que el comprobador de
# tipos verifique la conformidad en el archivo del adaptador y no en el sitio de
# llamada (ADR-018, enmienda del 2026-09-17).


@runtime_checkable
class TextGenerator(Protocol):
    """Generar texto, con esquema o sin el. Lo implementa U5 (Gemini)."""

    async def generate(
        self, prompt: Prompt, *, schema: type[BaseModel] | None, use: Use
    ) -> GenerationResult: ...


@runtime_checkable
class Embedder(Protocol):
    """Calcular embeddings. Lo implementa U5 (Gemini)."""

    async def embed(self, texts: Sequence[str], *, use: Use) -> list[Vector]: ...


@runtime_checkable
class SpeechToText(Protocol):
    """Transcribir en streaming. **Lo implementa U15** `speech-providers`.

    Se declara aqui y no alli porque el contrato es de esta unidad: U15 hereda la
    firma sin cambiarla, igual que hereda el esquema de la tabla de topes.
    """

    def stream(
        self, audio: AsyncIterator[bytes], *, language: Locale
    ) -> AsyncIterator[ListenEvent]: ...


@runtime_checkable
class TextToSpeech(Protocol):
    """Sintetizar y transmitir. **Lo implementa U15** `speech-providers`.

    Recibe `Redacted` y no `str`: lo que se sintetiza va hacia una persona, y
    todo texto que llega al asegurado pasa antes por el punto unico de salida
    (regla de `project.md`). Un puerto que aceptara `str` seria un punto de
    salida sin redaccion.
    """

    def synthesize(self, text: Redacted, *, voice: VoiceRef) -> AsyncIterator[bytes]: ...


@runtime_checkable
class SessionTextToSpeech(TextToSpeech, Protocol):
    """Una sintesis que puede mantener abierto su canal entre una frase y la siguiente.

    Conectar con el proveedor cuesta varias decimas de segundo, y una llamada dice
    una frase detras de otra durante minutos: abrir un canal por frase es pagar esa
    espera delante de cada una. `open_session` abre una vez y devuelve una sintesis
    con la misma firma que esta, que reutiliza el canal; al salir del contexto lo
    cierra, tambien cuando la llamada termina mal.

    **Una frase a la vez.** Si dos se piden juntas, la segunda espera a la primera:
    el audio de dos frases nunca se mezcla. Quien deja de leer una frase a medias
    tiene que cerrar su iterador (`aclose`) antes de pedir la siguiente.
    """

    def open_session(self) -> AbstractAsyncContextManager[TextToSpeech]: ...
