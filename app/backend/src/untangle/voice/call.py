"""El ciclo de una llamada: escuchar, decidir que se dijo, hablar.

Esta unidad **no tiene conversacion propia**. Lo que la agente responde lo decide
`handle_turn` (C-14), el mismo que atiende el chat, y por eso AC1.23.1 puede ser
cierto: el mismo guion entregado por los dos canales deja los mismos campos. Lo
que esta aqui es el ritmo --cuando escuchar, cuando hablar, que hacer con el
silencio-- y las frases que son de la llamada y no de la conversacion: la
apertura, los silencios y el "no le entendi".

**El manejador de turnos entra enchufado y no importado.** Es la misma costura
que usa el chat, y su razon es un contrato de importacion: el modulo que
implementa `handle_turn` importa LangGraph, y un canal que lo importara
arrastraria el framework del grafo por transitividad. Lo que este modulo conoce
son los tipos de C-14, que viven en un modulo hoja.

**Todo lo que se dice pasa por la redaccion antes de sintetizarse** (BR3.8). El
puerto `TextToSpeech` recibe `Redacted` y no `str`, asi que la regla es de tipos
y no de disciplina: un puerto que aceptara texto crudo seria un punto de salida
sin redaccion. Vale igual para los caminos de degradacion y de error, que es
donde se suele olvidar.

**Aqui no hay reloj.** El motor recibe el instante en cada llamada. Un
temporizador propio obligaria a dormir para probarlo, y ninguna prueba de esta
unidad duerme.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol, assert_never

from untangle import language as deteccion
from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record.models import CaseState, Channel, Resolution, Speaker
from untangle.compliance.controls.api import HandoffReason
from untangle.compliance.redaction import api as redaccion
from untangle.compliance.redaction.api import Redacted
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration import case_context, closing_plan
from untangle.orchestration.contracts import (
    VOICE_RULES_MAX_WORDS,
    FinalText,
    Handoff,
    InboundTurn,
    PartialText,
    TurnError,
    TurnEvent,
    Waiting,
)
from untangle.orchestration.nodes.intake import normalization
from untangle.orchestration.rhythm import launch_background
from untangle.orchestration.transcript_writer import (
    TranscriptScope,
    closing_text,
    record_agent_turn,
    record_person_turn,
)
from untangle.providers.ports import Transcript
from untangle.tenancy.models import TenantConfig
from untangle.voice import (
    barge_in,
    closing,
    early_understanding,
    filler,
    first_turn,
    hold_request,
    language_request,
    latency,
    offer_reply,
    opening,
    pending_question,
    readback,
    resume,
    retry,
    silence,
    speakable,
)
from untangle.voice.models import CallSession, EndReason
from untangle.voice.session import set_language
from untangle.voice.turn_detection import (
    DEFAULT_END_OF_SPEECH,
    INCOMPLETE_END_OF_SPEECH,
    SIGNAL_GRACE,
    SIGNAL_ONLY_EXTENSION,
    UNPUNCTUATED_END_OF_SPEECH,
    SpeechEnd,
    TurnDetector,
)

#: Cuantos turnos seguidos en el otro idioma hacen falta para cambiar sin que nadie lo
#: pida (BR3.2, AC1.32.1). "La respuesta al turno t+1 ya es en espanol": el t+1 es el
#: segundo, no el primero.
TURNOS_PARA_CAMBIAR_SOLO = 2

#: Lo que la agente dice cuando no esta respondiendo un turno (2026-10-11).
BACK_TO_REPORT = CopyKey("voice.answer.back_to_report")
ANSWER_DELAYED = CopyKey("voice.answer.delayed")
TIME_RUNNING_OUT = CopyKey("voice.time.running_out")
#: La voz no toma cotizaciones: se piden por chat.
QUOTE_BY_CHAT = CopyKey("voice.quote.by_chat")
#: La primera frase solo anuncia que quiere consultar algo, sin decir que (2026-10-13): se
#: le pregunta a que viene, con otras palabras que las de la apertura.
FIRST_TURN_CLARIFY = CopyKey("voice.first_turn.clarify")
#: Alguien pidio el otro idioma y la llamada ya esta en el: el acuse, dicho en ese idioma
#: (2026-10-13). Antes (desde el 2026-10-11) la llamada decia que seguia en el suyo.
LANGUAGE_SWITCHED = CopyKey("voice.languages.switched")
#: Alguien pide que se espere ("un momento"): la agente dice que espera.
HOLD_ACKNOWLEDGE = CopyKey("voice.hold.acknowledge")
#: Contestaron "si" o "no" a "¿lo dejamos guardado o se lo paso a un ajustador?" sin decir
#: cual: se pregunta otra vez, una sola vez (2026-10-11).
OFFER_CHOOSE = CopyKey("voice.offer.choose")
#: Eligieron el ajustador: lo que se dice antes del numero de caso y la despedida.
OFFER_HANDED_OFF = CopyKey("voice.offer.handed_off")

#: Con menos palabras que esto el primer turno todavia no dice a que llama: "hola",
#: "si, buenas".
_PALABRAS_PARA_DECIR_A_QUE_LLAMA = 3


class TurnHandler(Protocol):
    """Lo que la llamada necesita del grafo (C-14), y nada mas.

    Es la firma de `orchestration.turn.handle_turn`, escrita aqui para que esta
    unidad no tenga que importar el modulo que la implementa.
    """

    def __call__(self, turn: InboundTurn) -> AsyncIterator[TurnEvent]: ...


@contextlib.asynccontextmanager
async def _cerrando[T](iterador: AsyncIterator[T]) -> AsyncIterator[AsyncIterator[T]]:
    """Cierra el generador al salir, en la tarea que lo esta usando.

    `async for` no cierra el generador que recorre cuando se sale antes de agotarlo: lo
    deja al recolector, que lo cierra desde otra tarea. Para un generador que abre un
    rastro con variables de contexto (el turno del grafo) eso es un `ValueError` al
    reponerlas.
    """
    try:
        yield iterador
    finally:
        cerrar = getattr(iterador, "aclose", None)
        if cerrar is not None:
            await cerrar()


class SwitchReason(StrEnum):
    """Por que cambio el idioma. Dos, y no se mezclan (U18).

    Los que la persona pidio deben ser el 100 %; los que la deteccion decidio sola
    son una tasa de acierto. Un solo contador mezclaria una compuerta con una
    estimacion.
    """

    REQUESTED = "requested"
    DETECTED = "detected"


@dataclass(frozen=True)
class LanguageChange:
    """El idioma nuevo de la llamada y por que cambio."""

    to: Locale
    reason: SwitchReason


@dataclass(frozen=True)
class Utterance:
    """Algo que la agente dice, listo para sintetizar.

    `copy_key` es nula cuando el texto viene del grafo: lo que se registra de una
    frase del catalogo es su clave, y una respuesta compuesta no tiene ninguna.

    `end_reason` no es nula cuando decir esto **termina la llamada**: el tercer
    silencio se despide antes de colgar, y colgar sin despedirse es la peor
    pantalla posible.

    **`text` es lo que se dice y `shown` lo que se lee** (2026-10-13). El puerto de sintesis
    solo recibe `Redacted`, asi que `text` va tapado cuando el texto no es del catalogo;
    pero la consola es la pantalla de quien habla, y ahi la persona lo ve todo sin
    etiquetas (lo pidio cuatro veces). `shown` trae el mismo texto sin tapar, en lineas
    --la consola pinta cada una como un turno--, y es nulo cuando `text` ya es lo que se
    lee. **Solo viaja al socket de esa persona**: nunca a un evento, una traza ni la base,
    que siguen tapados.
    """

    text: Redacted
    copy_key: CopyKey | None = None
    end_reason: EndReason | None = None
    shown: tuple[str, ...] | None = None


@dataclass(frozen=True)
class _Resuelto:
    """Lo que sale de mirar un turno antes de entregarlo (BR3.5).

    `text` en nulo significa **no se entrega nada al grafo todavia**: o se esta
    leyendo un codigo de vuelta, o la persona no confirmo el que se le leyo.
    """

    text: str | None
    say: Utterance | None = None


@dataclass
class CallEngine:
    """El ritmo de una llamada. Una instancia por llamada."""

    call: CallSession
    config: TenantConfig
    handle_turn: TurnHandler
    end_of_speech: timedelta = DEFAULT_END_OF_SPEECH
    unpunctuated_end_of_speech: timedelta = UNPUNCTUATED_END_OF_SPEECH
    incomplete_end_of_speech: timedelta = INCOMPLETE_END_OF_SPEECH
    #: Cuanto una senal de voz sin palabras mantiene abierto el turno, y lo maximo que varias
    #: pueden alargarlo (`turn_detection.SIGNAL_GRACE`). Las pruebas con reloj real los acortan.
    signal_grace: timedelta = SIGNAL_GRACE
    signal_only_extension: timedelta = SIGNAL_ONLY_EXTENSION
    silence_tolerance: timedelta = silence.DEFAULT_TOLERANCE
    confidence_floor: float = retry.DEFAULT_CONFIDENCE_FLOOR
    #: Quien lee un mensaje con el contexto de su caso antes de que el turno corra. Con el, la
    #: llamada empieza a entender la frase en cuanto el reconocedor entrega su final y no cuando
    #: vence la tolerancia de fin de habla (`early_understanding`). Nulo --lo que trae por
    #: omision-- deja el turno como siempre: las evaluaciones y las pruebas no lo quieren.
    understand: early_understanding.TurnUnderstander | None = None
    #: Cuanto espera la despedida de un reporte completo el resultado de las reglas, y cada
    #: cuanto lo mira (US1.17). Las pruebas lo acortan: el valor de verdad es de `closing`.
    result_wait: timedelta = closing.RESULT_WAIT
    result_poll_seconds: float = closing.RESULT_POLL_SECONDS

    #: Cuando termino de sonar la apertura. Mientras sea `None`, **ningun turno
    #: se atiende** (BR2.1) y una apertura interrumpida se repite entera (BR4.5).
    disclosed_at: datetime | None = None
    #: Si el cierre ya se dijo. Un caso completo se cierra **una** vez.
    closed: bool = False
    _silencios: int = 0
    _sin_entender: int = 0
    #: El codigo dictado que espera confirmacion, y el turno que lo traia
    #: (BR3.5). Mientras haya uno, nada se entrega al grafo: anotar sin
    #: confirmar seria guardar una placa que nadie dijo.
    _por_confirmar: tuple[str, str] | None = field(default=None, init=False)
    #: El caso que este navegador puede retomar, mientras espera respuesta a la
    #: oferta. Nulo cuando no hay ninguno o cuando ya se resolvio (BR6.2).
    _retomable: resume.Resumable | None = field(default=None, init=False)
    _detector: TurnDetector | None = field(default=None, init=False)
    #: La persona pidio que se espere: el proximo silencio se tolera mas
    #: (`silence.HOLD_TOLERANCE`) y despues vuelve la tolerancia de siempre.
    _espera_larga: bool = field(default=False, init=False)
    #: El turno cerro con la frase de espera: el fondo va a traer una respuesta, y
    #: el ciclo la aguarda sin preguntar "¿sigues ahi?".
    _espera_respuesta: bool = field(default=False, init=False)
    #: La ultima pregunta que la agente dejo en el aire. Se repite despues de decir
    #: algo que no la contesta, para que la persona sepa donde iba el reporte.
    _pregunta_pendiente: str | None = field(default=None, init=False)
    #: Si ya se sabe a que llama la persona. Lo decide lo primero que dice con
    #: sustancia; despues la conversacion sigue por su caso.
    _proposito_decidido: bool = field(default=False, init=False)
    #: Este turno pide cotizar, que la voz no hace: se le dice y no va al grafo.
    _pide_cotizar: bool = field(default=False, init=False)
    #: Este turno solo anuncia que quiere consultar algo, sin decir que: se le pregunta a que
    #: viene y no va al grafo (2026-10-13).
    _pide_aclarar: bool = field(default=False, init=False)
    #: Ya se le pregunto una vez a que viene. La segunda frase vaga sigue por donde iba la
    #: llamada, en vez de repetirle la misma pregunta con las mismas palabras.
    _aclaracion_dicha: bool = field(default=False, init=False)
    #: "¿Lo dejamos guardado o se lo paso a un ajustador?" esta dicha y espera su
    #: respuesta (2026-10-11). La dicen dos caminos --el segundo silencio y la tercera
    #: vez que no se entiende-- y mientras este abierta, el turno siguiente es esa
    #: respuesta y no una frase para el grafo.
    _oferta_pendiente: bool = field(default=False, init=False)
    #: Ya se repregunto cual de las dos. Una vez: tras eso, un si a secas sigue su camino.
    _oferta_repreguntada: bool = field(default=False, init=False)
    #: Cual fue la ultima muletilla que se dijo, para que la siguiente sea otra.
    _ultima_muletilla: int | None = field(default=None, init=False)
    #: Cuantos turnos seguidos han llegado en el otro idioma sin que nadie pida el
    #: cambio. Hacen falta dos (BR3.2): uno solo no es un cambio de idioma, es una
    #: frase, y con uno una cita o un modismo moverian la conversacion entera.
    _turnos_en_el_otro: int = field(default=0, init=False)
    #: El idioma en que se dijo la apertura. Se registra contra cada caso que abre la
    #: llamada (BR6.4), y lo que se registra es lo que se **dijo**: si la llamada ya
    #: cambio de idioma, el caso nuevo no puede quedar con una divulgacion en el otro.
    _idioma_de_la_apertura: Locale | None = field(default=None, init=False)
    #: Se enciende cada vez que el idioma de la llamada cambia. Lo espera quien tiene un
    #: reconocedor de un solo idioma por conexion, que tiene que abrirse de nuevo en el
    #: idioma nuevo: el motor decide y escribe, y el ciclo reacciona.
    language_changed: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    #: La lectura adelantada de esta llamada. Nula sin `understand`.
    _early: early_understanding.EarlyUnderstanding | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.understand is not None:
            self._early = early_understanding.EarlyUnderstanding(
                self.understand, tenant_id=self.call.tenant_id, call_id=self.call.call_id
            )

    @property
    def language(self) -> Locale:
        return self.call.language

    @property
    def opening_language(self) -> Locale | None:
        """El idioma en que se dijo la apertura, o nulo mientras no se ha registrado."""
        return self._idioma_de_la_apertura

    def _del_catalogo(self, text: str) -> Redacted:
        """Una frase que escribimos nosotros: **no se le pasa el detector**.

        Todo lo que dice la agente sale del catalogo por idioma, y una frase del
        catalogo no tiene datos personales por construccion. Pasarle el detector de
        nombres solo podia danarla, y la danaba: en espanol etiquetaba como persona
        el verbo con que arranca la frase. Los huecos, que **si** llevan datos de
        personas, los tapa quien los rellena.
        """
        return redaccion.from_catalog(text, language=self.language)

    def _de_fuera(self, text: str) -> Redacted:
        """Texto que no escribimos nosotros: lo que dijo el modelo. Se tapa entero."""
        return redaccion.redact(text, language=self.language)

    def _frase_fija(self, frase: str, key: CopyKey) -> Utterance:
        """Una frase fija del catalogo dicha fuera del grafo, y anotada en la transcripcion.

        Quien llama resuelve la clave con `copy_api.t` y su constante a la vista: una clave
        que llega por parametro dejaria de verse para el chequeo de claves sin consumidor.
        """
        self._anotar(frase, speaker=Speaker.AGENT, at=datetime.now(UTC), from_catalog=True)
        return Utterance(text=self._del_catalogo(frase), copy_key=key)

    # --- La apertura (BR2.1 a BR2.4) ------------------------------------------

    def opening(self) -> Utterance:
        """Lo primero que se oye. Se compone cada vez porque una apertura
        interrumpida se repite entera (BR4.5)."""
        # Con un caso por retomar la pregunta es la oferta de seguir con el, y es la unica:
        # dos seguidas --"¿en que te puedo ayudar?" y "¿seguimos con ese?"-- dejaban a la
        # persona sin saber a cual contestar. La divulgacion va entera de todos modos.
        compuesta = opening.compose(
            self.config, language=self.language, ask_how_to_help=self._retomable is None
        )
        self._pregunta_pendiente = pending_question.last_question(compuesta.text)
        return Utterance(text=self._del_catalogo(compuesta.text), copy_key=compuesta.copy_key)

    async def opening_finished(self, *, at: datetime) -> bool:
        """La apertura termino de sonar: se registra con **esa** hora (BR2.3).

        Devuelve si esta fue la que quedo. `False` es la segunda llamada del
        mismo caso, y la primera sigue en su sitio (BR2.4).
        """
        if self.call.case_id is None:
            msg = "la apertura no se puede registrar sin caso"
            raise ValueError(msg)
        self.disclosed_at = at
        # En el idioma en que **se dijo**: la llamada puede haber cambiado desde entonces,
        # y el caso nuevo de la misma llamada hereda una divulgacion que ya sono.
        if self._idioma_de_la_apertura is None:
            self._idioma_de_la_apertura = self.language
        compuesta = opening.compose(self.config, language=self._idioma_de_la_apertura)
        return await opening.record(
            tenant_id=self.call.tenant_id,
            case_id=self.call.case_id,
            language=self._idioma_de_la_apertura,
            opening=compuesta,
            finished_at=at,
        )

    # --- El idioma de la llamada (U18, BR2.1 a BR2.6, BR3.1 a BR3.3) -----------------
    # Cambia a pedido de la persona o, con la deteccion encendida, cuando habla dos turnos
    # seguidos en el otro. Se quito el 2026-10-11 porque el reconocedor era de un idioma
    # por llamada y la agente hablaba en uno y oia en otro; vuelve el 2026-10-13 con el
    # reconocedor reabierto en el idioma nuevo (`CallRunner._escuchar`).

    def _otro_idioma_pedido(self, speech: SpeechEnd) -> Locale | None:
        """El idioma que el turno pide, si es distinto del de la llamada.

        Pedir el idioma en que ya se esta no es nada: es un turno como cualquier otro.
        """
        pedido = language_request.requested(speech.text)
        return pedido if pedido is not None and pedido != self.language else None

    async def _resolver_idioma(self, speech: SpeechEnd) -> LanguageChange | None:
        """Decide si el turno cambia el idioma, y si si, lo cambia. Devuelve el cambio.

        El orden es la regla (BR2.2): **primero la peticion explicita**. "In English,
        please" esta dicho en ingles y el detector lo leeria como ingles por accidente;
        "¿me lo dice in English?" esta dicho en espanol y diria espanol. Los dos son la
        misma peticion, y si mandara el detector funcionaria en un sentido y no en el otro.
        Se atiende **aunque la transcripcion llegue con baja confianza**: quien habla el
        otro idioma ante un reconocedor del primero suena a ruido, y es justo quien lo pide.
        """
        pedido = language_request.requested(speech.text)
        if pedido is not None:
            return await self._resolver_pedido(pedido)
        return await self._resolver_deteccion(speech)

    async def _resolver_pedido(self, pedido: Locale) -> LanguageChange | None:
        self._turnos_en_el_otro = 0
        if pedido == self.language:
            return None
        return await self._cambiar_idioma(pedido, SwitchReason.REQUESTED)

    async def _resolver_deteccion(self, speech: SpeechEnd) -> LanguageChange | None:
        """El cambio sin que nadie lo pida: solo con la deteccion encendida (AC1.31.5).

        Cuenta turnos que **se entendieron** y cambia al segundo seguido (AC1.32.1): un
        turno suelto en el otro idioma es una frase, no un cambio.
        """
        if not self.config.voice.auto_language_detection:
            return None
        if not retry.understood(speech.last, confidence_floor=self.confidence_floor):
            return None

        detectado = self._idioma_detectado_o_nada(speech)
        if detectado is None or detectado == self.language:
            self._turnos_en_el_otro = 0
            return None

        self._turnos_en_el_otro += 1
        if self._turnos_en_el_otro < TURNOS_PARA_CAMBIAR_SOLO:
            return None
        return await self._cambiar_idioma(detectado, SwitchReason.DETECTED)

    def _idioma_detectado_o_nada(self, speech: SpeechEnd) -> Locale | None:
        """Como `_idioma_detectado`, pero un fallo del detector no tumba la llamada.

        El detector es una extension en Rust cargada de un paquete de terceros: es una
        frontera, y en una frontera se atrapa (guardarrail de la fase). Lo que se conserva
        es el idioma que habia, que es el mismo desenlace que "no hay senal suficiente", y
        el fallo **deja rastro**: sin el evento, un detector roto se veria igual que una
        aseguradora con la deteccion apagada.
        """
        try:
            return self._idioma_detectado(speech)
        except Exception as error:  # noqa: BLE001 -- la frontera es de terceros: lo que pueda levantar no es un conjunto que este lado conozca
            latency.language_detection_failed(
                tenant_id=self.call.tenant_id,
                call_id=self.call.call_id,
                error_type=type(error).__name__,
            )
            return None

    def _idioma_detectado(self, speech: SpeechEnd) -> Locale | None:
        """En que idioma llego este turno, si se puede decir con confianza.

        **Dos fuentes y el piso de palabras manda sobre las dos.** Con el reconocedor en
        modo multiidioma, cada transcrito trae el idioma que detecto; cuando no lo dice
        --el modo de un solo idioma, que es el de hoy-- se mira el texto con el detector
        del proyecto. Pero "okay" y "el Toyota Highlander" no cambian nada venga de donde
        venga (BR3.3, AC1.32.2), y por eso el piso va primero.
        """
        if not deteccion.has_signal(speech.text):
            return None
        if speech.last is not None and speech.last.language is not None:
            return speech.last.language
        return deteccion.measured(speech.text)

    async def _cambiar_idioma(self, to: Locale, reason: SwitchReason) -> LanguageChange:
        """Escribe el idioma nuevo de la llamada, deja el rastro y avisa al ciclo.

        **Escribe la llamada y no el caso**: el idioma del caso es el que tenia al abrirse
        y decide en que cola lo ve la aseguradora (RT-10). Nada de lo confirmado se toca.
        """
        anterior = self.language
        self.call = await set_language(self.call, language=to)
        self._turnos_en_el_otro = 0
        self._sin_entender = 0
        latency.language_switched(
            tenant_id=self.call.tenant_id,
            call_id=self.call.call_id,
            frm=anterior,
            to=to,
            reason=reason.value,
        )
        self.language_changed.set()
        return LanguageChange(to=to, reason=reason)

    async def _acuse_del_cambio(self) -> Utterance:
        """Lo que se dice al pedir el otro idioma: el acuse **ya en el idioma nuevo** y la
        pregunta que habia quedado en el aire, tambien en el nuevo.

        La pregunta no se traduce: se vuelve a deducir del caso (`resume.next_question`),
        porque lo que la agente pregunto hace un momento estaba escrito en el otro idioma.
        Lo ya confirmado no se vuelve a preguntar, y una lectura de codigo que esperaba su
        "si" se descarta --esa placa no esta anotada--: se vuelve a pedir desde el caso.
        """
        self._por_confirmar = None
        acuse = copy_api.t(LANGUAGE_SWITCHED, locale=self.language)
        pregunta = await self._pregunta_para_retomar()
        self._pregunta_pendiente = pending_question.last_question(pregunta)
        return self._frase_fija(f"{acuse} {pregunta}", LANGUAGE_SWITCHED)

    async def _pregunta_para_retomar(self) -> str:
        """La pregunta que sigue en el aire, escrita en el idioma de la llamada ahora.

        En este orden, la primera que aplica: la oferta de guardar o pasar a un ajustador,
        la de seguir con el caso cortado, la de a que llama (nadie ha dicho todavia), la que
        la captura haria con este caso, y si no hay ninguna, que mas quiere agregar.
        """
        if self._oferta_pendiente:
            return retry.offer(language=self.language)
        if self._retomable is not None:
            return resume.offer(language=self.language)
        if not self._proposito_decidido:
            return opening.first_question(language=self.language)
        vista = (
            None
            if self.call.case_id is None
            else await casos.get_case(self.call.tenant_id, self.call.case_id)
        )
        pregunta = None if vista is None else resume.next_question(vista, language=self.language)
        return pregunta if pregunta is not None else resume.ask_what_else(language=self.language)

    def _contestar_pedido(self, speech: SpeechEnd) -> Utterance | None:
        """La respuesta a un pedido de espera, si el turno es uno."""
        if hold_request.requested(speech.text):
            self._espera_larga = True
            latency.hold_requested(tenant_id=self.call.tenant_id, call_id=self.call.call_id)
            frase = copy_api.t(HOLD_ACKNOWLEDGE, locale=self.language)
            return self._frase_fija(frase, HOLD_ACKNOWLEDGE)
        return None

    async def _contestar_aparte(self, speech: SpeechEnd) -> Utterance | None:
        """Lo que se contesta sin pasar por el grafo, si el turno es de esos.

        En este orden: el pedido de espera (no cierra la oferta abierta, que sigue esperando
        su respuesta), la respuesta a esa oferta, y el pedido de cotizar, que la voz no toma.
        """
        pedido = self._contestar_pedido(speech)
        if pedido is not None:
            return pedido
        if self._oferta_pendiente:
            respuesta = await self._contestar_la_oferta(speech)
            if respuesta is not None:
                return respuesta
        return self._contestar_cotizacion() or self._contestar_aclaracion()

    def _contestar_aclaracion(self) -> Utterance | None:
        """Pregunta a que viene a quien solo dijo que quiere consultar algo. Nulo si no toca.

        No toca el tipo del caso ni lo que lleva: la llamada nace con un reporte (BR2.3) y
        eso no es a lo que llama la persona; si despues dice que es una duda de su poliza, la
        llamada abre otra consulta, como siempre.
        """
        if not self._pide_aclarar:
            return None
        self._pide_aclarar = False
        self._aclaracion_dicha = True
        frase = copy_api.t(FIRST_TURN_CLARIFY, locale=self.language)
        self._pregunta_pendiente = pending_question.last_question(frase)
        return self._frase_fija(frase, FIRST_TURN_CLARIFY)

    def _contestar_cotizacion(self) -> Utterance | None:
        """La voz no toma cotizaciones: se piden por chat. Nulo si este turno no cotiza."""
        if not self._pide_cotizar:
            return None
        self._pide_cotizar = False
        por_chat = copy_api.t(QUOTE_BY_CHAT, locale=self.language)
        self._pregunta_pendiente = pending_question.last_question(por_chat)
        self._anotar(por_chat, speaker=Speaker.AGENT, at=datetime.now(UTC), from_catalog=True)
        return Utterance(text=self._del_catalogo(por_chat), copy_key=QUOTE_BY_CHAT)

    def is_side_request(self, speech: SpeechEnd) -> bool:
        """Si el turno se contesta aparte --pide el otro idioma o pide que se espere--
        y no es respuesta a lo que la agente habia preguntado.

        Lo usa el ciclo para no leer "un momento" como el "no" a la oferta de retomar
        un caso, ni como el primer turno que decide a que llama la persona.
        """
        return hold_request.requested(speech.text) or self._otro_idioma_pedido(speech) is not None

    def spoken(self, utterance: Utterance) -> Redacted:
        """Lo que se manda a sintetizar de esta frase: los codigos dichos como se dictan.

        **Es el unico sitio donde el texto que suena difiere del que se ve**: la
        pantalla y la transcripcion guardada llevan `utterance.text` tal cual, y esto
        solo reescribe lo que tiene forma de numero de poliza, de caso o de placa
        (`speakable.for_speech`). Si no hay nada que reescribir, devuelve el mismo
        `Redacted` que entro.

        Cuando si lo hay, el resultado pasa por `from_catalog` porque es el unico
        constructor sancionado del tipo: el texto de partida ya era `Redacted` y esto
        solo cambia como se escriben sus codigos --nunca agrega nada que venga de fuera:
        digitos y nombres de letra salen de las tablas de U11 y la unica palabra, del
        catalogo--, asi que no hay dato personal nuevo que tapar.

        **Y es tambien el unico sitio donde una etiqueta deja de poder sonar** (2026-10-13).
        Una frase puede llegar aqui con "[LUGAR 1]" dentro: la explicacion de la IA con un
        pais que el detector tapo, o el comentario que un ajustador escribio y se guardo
        tapado. El sintetizador la leeria como quisiera; `without_labels` la cambia por
        "ese lugar", que no dice cual.
        """
        sin_etiquetas = redaccion.without_labels(utterance.text, language=self.language)
        dicho = speakable.for_speech(str(sin_etiquetas), language=self.language)
        if dicho == sin_etiquetas:
            return sin_etiquetas
        return redaccion.from_catalog(dicho, language=self.language)

    def on_screen(self, utterance: Utterance) -> tuple[str, ...]:
        """Lo que la consola de quien habla pinta de esta frase: una linea por turno.

        **Sin tapar** cuando se tiene (`Utterance.shown`): es su propia pantalla, y la base
        guarda tapado aparte. Cuando no se tiene --el comentario de un ajustador que llego
        de la base ya con etiquetas--, lo mismo que se dice: la palabra neutra, nunca la
        etiqueta, porque lo tapado no se puede destapar.
        """
        if utterance.shown is not None:
            return utterance.shown
        return (str(redaccion.without_labels(utterance.text, language=self.language)),)

    # --- A que llama (2026-10-11) ---------------------------------------------

    def first_turn_purpose(self, speech: SpeechEnd) -> first_turn.CallPurpose | None:
        """A que llama la persona, la primera vez que lo dice. `None` despues, o
        mientras solo haya saludado.

        Una duda de su poliza hace que el ciclo abra una consulta en vez del
        reporte con que nacio la llamada; pedir cotizar se contesta aqui.
        """
        self._pide_cotizar = False
        self._pide_aclarar = False
        if self._proposito_decidido:
            return None
        if len(speech.text.split()) < _PALABRAS_PARA_DECIR_A_QUE_LLAMA:
            return None
        proposito = first_turn.purpose_of(
            speech.text, language=self.language, quote_enabled=self.config.quote_enabled
        )
        if proposito is first_turn.CallPurpose.QUOTE:
            # No decide la llamada: tras oir que es por chat, puede pedir otra cosa.
            self._pide_cotizar = True
            return proposito
        if proposito is first_turn.CallPurpose.NOT_STATED:
            if self._aclaracion_dicha:
                # Ya se le pregunto y volvio a decir algo vago: la llamada sigue por donde
                # iba (el modelo ve el caso y la conversacion), no se repite la pregunta.
                self._proposito_decidido = True
                return first_turn.CallPurpose.CLAIM
            # No decide la llamada: lo siguiente que diga si puede decir a que viene.
            self._pide_aclarar = True
            return proposito
        self._proposito_decidido = True
        return proposito

    # --- Escuchar (BR3.1) -----------------------------------------------------

    def listening(
        self, *, since: datetime, stream_started_at: datetime | None = None
    ) -> TurnDetector:
        """Abre el detector del turno que empieza.

        `stream_started_at` es cuando llego el primer trozo de audio de la llamada: el
        origen de los tiempos de palabra del reconocedor, que no es el del turno.
        """
        self._detector = TurnDetector(
            started_at=since,
            stream_started_at=stream_started_at,
            end_of_speech=self.end_of_speech,
            unpunctuated_end_of_speech=self.unpunctuated_end_of_speech,
            incomplete_end_of_speech=self.incomplete_end_of_speech,
            signal_grace=self.signal_grace,
            signal_only_extension=self.signal_only_extension,
        )
        return self._detector

    # --- Entender antes de que venza la tolerancia (2026-10-13) -----------------

    def advance_understanding(self, speech: SpeechEnd) -> None:
        """Empieza a leer lo que la persona lleva dicho, sin esperar a que el turno cierre.

        `speech` es el turno tal como se cerraria ahora (`TurnDetector.pending_end`). Se adelanta
        **solo cuando el turno va a llegar al modelo tal cual**: todo lo que `speak_turn` resuelve
        antes del grafo --pedir otro idioma o una espera, la lectura de un codigo, la respuesta a
        la oferta, el primer turno que dice a que llama la persona, lo que no se entendio, las
        respuestas de una o dos palabras-- es pagar una lectura para tirarla. Ante la duda no se
        adelanta: el turno sigue por el camino de siempre. Si el texto crecio y ya no cumple, la
        lectura del texto anterior se suelta.
        """
        if self._early is None:
            return
        if not self._lo_lee_el_modelo(speech) or self.call.case_id is None:
            self._early.retire(speech.text)
            return
        self._early.start(self._inbound(speech.text, received_at=speech.at))

    def _lo_lee_el_modelo(self, speech: SpeechEnd) -> bool:
        """Si este turno, cerrado tal cual, llegaria al modelo sin pasar por una regla de la llamada.

        Son las mismas guardas que `speak_turn` recorre antes del grafo, **sin sus efectos**: aqui
        no se cambia el idioma, no se anota nada ni se cuenta nada. Lo que no se puede saber de
        antemano --que el idioma cambie por deteccion al segundo turno seguido-- lo atrapa
        `take`, que compara el idioma, el caso y el texto del turno con los de la lectura.
        """
        return (
            self.disclosed_at is not None
            and not self.closed
            and self._llama_por_un_reporte(speech)
            and self._por_confirmar is None
            and not self._oferta_pendiente
            and len(speech.text.split()) > VOICE_RULES_MAX_WORDS
            and retry.understood(speech.last, confidence_floor=self.confidence_floor)
            and not self.is_side_request(speech)
            and self._codigo_por_leer(speech) is None
        )

    def _llama_por_un_reporte(self, speech: SpeechEnd) -> bool:
        """Si el turno sigue en el caso con que nacio la llamada, sin abrir otro ni pedir cotizar.

        Una vez decidido a que llama la persona, todo turno sigue en su caso. El primer turno con
        sustancia es la excepcion: una duda de su poliza abre una consulta (otro caso) y pedir
        cotizar se contesta aparte (`first_turn_purpose`). Se calcula con la misma funcion pura y
        las mismas entradas, sin tocar la bandera que `first_turn_purpose` si cambia.
        """
        if self._proposito_decidido:
            return True
        proposito = first_turn.purpose_of(
            speech.text, language=self.language, quote_enabled=self.config.quote_enabled
        )
        if proposito is first_turn.CallPurpose.NOT_STATED:
            # La primera vez se le pregunta a que viene; la segunda sigue por donde iba.
            return self._aclaracion_dicha
        return proposito is first_turn.CallPurpose.CLAIM

    def drop_advanced(
        self, cause: early_understanding.Discard, *, turn_id: str | None = None
    ) -> None:
        """Suelta la lectura adelantada, si la hay: la persona siguio hablando, llego algo del
        fondo, o el turno no la necesito. Sin `understand` no hace nada."""
        if self._early is not None:
            self._early.drop(cause, turn_id=turn_id)

    async def close_advanced(self) -> None:
        """La llamada termino: suelta la lectura en vuelo y espera a que se deshaga."""
        if self._early is not None:
            await self._early.aclose()

    def _inbound(self, text: str, *, received_at: datetime) -> InboundTurn:
        """El turno que se le entrega al grafo, con el caso y el idioma de ahora.

        Uno solo para las dos cosas que lo necesitan --la lectura adelantada y el turno de
        verdad--: que la lectura se haga sobre la misma forma que el turno entrega es lo que
        deja compararlas.
        """
        return InboundTurn(
            tenant_id=self.call.tenant_id,
            session_ref=self.call.call_id,
            case_id=self.call.case_id,
            text=text,
            language=self.language,
            channel="voice",
            received_at=received_at,
        )

    async def _con_lo_adelantado(self, turno: InboundTurn, *, turn_id: str) -> InboundTurn:
        """El turno con la lectura que se adelanto, si la hay y sigue valiendo.

        Entra igual que la del chat --`understood_by_channel`--: con ella el turno no vuelve a
        llamar al modelo, tambien cuando la lectura no pudo (entonces sigue por reglas).
        """
        if self._early is None:
            return turno
        tomada = await self._early.take(turno, turn_id=turn_id)
        if tomada is None:
            return turno
        return replace(turno, understood=tomada.response, understood_by_channel=True)

    # --- El turno hablado (BR3.2, BR3.4, BR3.6) -------------------------------

    async def speak_turn(self, speech: SpeechEnd, *, turn_id: str) -> AsyncGenerator[Utterance]:
        """Lo que la agente dice despues de que la persona termino de hablar.

        Tres caminos y ninguno silencioso: no se entendio, se entendio, o el
        grafo fallo --y ese ultimo ya llega como `TurnError` por C-14, que esta
        unidad habla igual que los demas eventos--. Un pedido de espera o del otro
        idioma se entiende y se contesta aparte, sin pasar por el grafo; el del idioma
        ademas cambia la llamada antes de contestar.
        """
        if self.disclosed_at is None:
            msg = "BR2.1: ningun turno se atiende antes de que la apertura este registrada"
            raise ValueError(msg)
        if self.call.case_id is None:
            msg = "el turno necesita un caso abierto"
            raise ValueError(msg)

        latency.speech_end(
            tenant_id=self.call.tenant_id,
            call_id=self.call.call_id,
            turn_id=turn_id,
            at=speech.at,
            last_audible_word_at=speech.last_audible_word_at,
        )
        self._silencios = 0
        # Un turno nuevo de la persona cancela la espera larga: si vuelve a pedirla,
        # se vuelve a armar mas abajo.
        self._espera_larga = False

        # **La llamada tambien escribe su transcripcion** (PENDIENTES 1.18). Hasta
        # hoy no escribia ninguna linea: el caso de una llamada quedaba sin una sola
        # palabra, la revision de cumplimiento no se podia acotar --no hay turno
        # hasta donde llegar-- y sin esa revision la bandeja no dejaba cerrarlo.
        #
        # **Va aqui arriba, antes de la comprobacion de confianza, y lo puso una
        # prueba.** Lo que la persona dijo se anota aunque el reconocedor no lo
        # entienda: es justo lo que el ajustador necesita leer para saber por que se
        # le repregunto. Detras de esa comprobacion se perdian los turnos que mas
        # hay que auditar.
        #
        # **Fuera del turno, sin esperarla.** Este es el camino con el presupuesto
        # de latencia mas estricto del proyecto, y una escritura a la base dentro de
        # el gastaria del tiempo que va del fin del habla al primer audio. El ritmo
        # de fondo es donde va por la misma razon que la verificacion y las reglas
        # (P4, R2).
        #
        # **El idioma se resuelve antes de anotar**: el turno que lo cambia ya esta dicho en
        # el idioma nuevo, y asi se guarda (con sus etiquetas de redaccion en ese idioma).
        cambio = await self._resolver_idioma(speech)
        self._anotar(speech.text, speaker=Speaker.INSURED, at=speech.at)

        # Quien pide el otro idioma recibe el acuse y la pregunta que seguia, ya en el idioma
        # nuevo, y el pedido no va al grafo (AC1.31.1). Aunque la transcripcion llegue con
        # baja confianza: pedir el cambio es justo lo que suena a ruido ante el reconocedor
        # del otro idioma. Un cambio por deteccion, en cambio, no dice nada aparte: el turno
        # sigue su camino y el grafo ya contesta en el idioma nuevo (AC1.32.1).
        if cambio is not None and cambio.reason is SwitchReason.REQUESTED:
            yield await self._acuse_del_cambio()
            return

        if not retry.understood(speech.last, confidence_floor=self.confidence_floor):
            repregunta = self._repreguntar(speech)
            if repregunta is not None:
                yield repregunta
            return

        self._sin_entender = 0

        # **Lo que se contesta aparte y no va al grafo**: pedir que se espere, la respuesta a
        # "¿lo dejamos guardado o se lo paso a un ajustador?" y pedir cotizar. Despues de la
        # comprobacion de confianza, como cualquier turno: un "un momento" que no se oyo
        # bien se repregunta.
        aparte = await self._contestar_aparte(speech)
        if aparte is not None:
            yield aparte
            return

        resuelto = self._resolver_codigo(speech)
        if resuelto.say is not None:
            yield resuelto.say
        if resuelto.text is None:
            return

        turno = await self._con_lo_adelantado(
            self._inbound(resuelto.text, received_at=speech.at), turn_id=turn_id
        )
        # Cada generador de la cadena se cierra aqui, en la tarea de la llamada, cuando el
        # turno se corta a medias: lo que se deja al recolector se cierra en otra tarea, y el
        # rastro del turno no se repone fuera de la tarea donde se abrio (2026-10-12).
        async with _cerrando(self._lo_que_dice_el_grafo(turno)) as dichos:
            async for dicho in dichos:
                yield dicho

    async def _lo_que_dice_el_grafo(self, turno: InboundTurn) -> AsyncGenerator[Utterance]:
        """El turno entregado al grafo: lo que contesta y, si toca, el cierre."""
        ultimo_dicho = ""
        derivado = False
        async with _cerrando(self.handle_turn(turno)) as eventos:
            async for evento in eventos:
                if isinstance(evento, Waiting) or (
                    isinstance(evento, FinalText) and evento.answer_pending
                ):
                    self._espera_respuesta = True
                if isinstance(evento, Handoff):
                    # La frase, el caso en la cola del ajustador y, abajo, el cierre.
                    derivado = True
                    self._derivar(evento.text, reason=evento.reason_code, at=turno.received_at)
                    yield self._hablar(evento)
                    continue
                dicho = closing_text(evento)
                if dicho is not None:
                    ultimo_dicho = dicho.text
                    self._pregunta_pendiente = (
                        pending_question.last_question(dicho.text) or self._pregunta_pendiente
                    )
                    # Solo lo que **cierra** el turno, y con su propio instante: la
                    # transcripcion se lee por ese campo, y dos turnos con el mismo
                    # quedan en orden arbitrario --que es justo el orden que la revision
                    # de cumplimiento comprueba--.
                    self._anotar(
                        dicho.text,
                        speaker=Speaker.AGENT,
                        at=datetime.now(UTC),
                        from_catalog=dicho.from_catalog,
                    )
                yield self._hablar(evento)

        # Si la agente acaba de preguntar --"¿quiere agregar algo, o lo dejamos para el
        # ajustador?"--, el cierre espera la respuesta: antes la llamada colgaba justo
        # despues de la pregunta (C6, visto el 2026-10-07).
        if derivado:
            yield await self._cierre_de_derivacion()
            return
        cierre = None if "?" in ultimo_dicho else await self._cierre_si_el_caso_quedo_completo()
        if cierre is not None:
            yield cierre

    def _repreguntar(self, speech: SpeechEnd) -> Utterance | None:
        """Lo que se dice cuando no se entendio el turno: el peldano que toca, o nada.

        Nada se anota en ninguno (BR3.4). El tercero es la oferta de dejar el caso guardado
        o pasarlo a un ajustador, y deja abierta su respuesta.
        """
        self._sin_entender += 1
        confianzas = (
            []
            if speech.last is None
            else [p.confidence for p in speech.last.words if p.confidence is not None]
        )
        latency.not_understood(
            tenant_id=self.call.tenant_id,
            call_id=self.call.call_id,
            words=0 if speech.last is None else len(speech.last.words),
            low_confidence_words=sum(1 for c in confianzas if c < self.confidence_floor),
            min_confidence=min(confianzas) if confianzas else None,
        )
        frase = retry.prompt_for(self._sin_entender, language=self.language)
        if frase is None:
            return None
        if frase.step is retry.RetryStep.OFFER:
            self._abrir_la_oferta()
        # La repregunta tambien es lo que la agente dijo, y cierra el turno.
        self._anotar(str(frase.text), speaker=Speaker.AGENT, at=datetime.now(UTC))
        return Utterance(text=self._del_catalogo(frase.text), copy_key=frase.copy_key)

    # --- "¿Lo dejamos guardado o se lo paso a un ajustador?" (2026-10-11) -----------

    def _abrir_la_oferta(self) -> None:
        self._oferta_pendiente = True
        self._oferta_repreguntada = False

    async def _contestar_la_oferta(self, speech: SpeechEnd) -> Utterance | None:
        """Lo que se dice ante la respuesta a la oferta, o `None` si el turno sigue su camino.

        Hasta hoy nadie leia esa respuesta: "guardalo" y "pasalo" entraban al grafo como un
        turno mas y la llamada seguia. Ahora cada eleccion hace lo que dijo: el ajustador
        deriva el caso por el mismo camino que cuando se pide uno (`_derivar` y el cierre
        de la derivacion), y guardarlo termina la llamada dejando el caso retomable.
        """
        eleccion = await offer_reply.classify(speech.text, language=self.language)
        if eleccion is offer_reply.OfferReply.CHOOSE and not self._oferta_repreguntada:
            # "Si" a una pregunta de dos opciones no elige ninguna, y entregarlo al grafo
            # lo anotaria como respuesta a otra cosa --un "si" a "¿hubo heridos?"--.
            self._oferta_repreguntada = True
            pregunta = copy_api.t(OFFER_CHOOSE, locale=self.language)
            return self._frase_fija(pregunta, OFFER_CHOOSE)
        self._oferta_pendiente = False
        if eleccion is offer_reply.OfferReply.ADJUSTER:
            texto = copy_api.t(OFFER_HANDED_OFF, locale=self.language)
            self._derivar(texto, reason=HandoffReason.HUMAN_REQUEST, at=speech.at)
            # Una sola frase y sin interrupcion: lleva el numero de caso, y cortarla a la
            # mitad deja a la persona sin lo unico que se lleva de la llamada.
            cierre = await self._cierre_de_derivacion()
            return Utterance(
                text=self._del_catalogo(f"{texto} {cierre.text}"),
                copy_key=OFFER_HANDED_OFF,
                end_reason=cierre.end_reason,
            )
        if eleccion is offer_reply.OfferReply.SAVE:
            return self._cierre_de_guardado()
        return None

    def _cierre_de_guardado(self) -> Utterance:
        """Se despide diciendo que el caso queda guardado y hasta cuando se puede retomar.

        La ventana es la que la llamada deja abierta al terminar con `SAVED`
        (`resume_window_seconds`), y la frase la dice tal cual: ni un plazo escrito aqui ni
        una promesa que la fila no sostenga.
        """
        self.closed = True
        self._pregunta_pendiente = None
        texto = closing.build_saved(
            window=timedelta(seconds=self.config.call.resume_window_seconds),
            language=self.language,
        )
        self._anotar(texto, speaker=Speaker.AGENT, at=datetime.now(UTC), from_catalog=True)
        return Utterance(
            text=self._del_catalogo(texto), copy_key=closing.SAVED, end_reason=EndReason.SAVED
        )

    def _derivar(self, text: str, *, reason: HandoffReason, at: datetime) -> None:
        """Escribe la frase de derivacion y **deriva el caso**, sin esperarlo.

        En el chat lo hace quien entrega el turno; en la llamada no lo hacia nadie:
        la agente decia "le paso su caso a un ajustador" y el caso se quedaba en
        captura, fuera de la cola de cualquier ajustador (visto el 2026-10-11).
        Primero el turno y despues la derivacion, que se acota a un turno que exista.
        """
        if self.call.case_id is None:  # pragma: no cover -- `speak_turn` ya lo exigio
            return
        tenant_id, case_id = self.call.tenant_id, self.call.case_id
        ambito = TranscriptScope(
            tenant_id=tenant_id, case_id=case_id, channel=Channel.VOICE, language=self.language
        )

        async def _escribir_y_derivar() -> None:
            turno = await record_agent_turn(
                ambito, text=text, now=datetime.now(UTC), from_catalog=True
            )
            await case_context.derive_case(
                tenant_id=tenant_id,
                case_id=case_id,
                reason=reason,
                turn_id=turno,
                now=at,
            )

        launch_background(_escribir_y_derivar())

    async def _numero_de_caso(self) -> str | None:
        if self.call.case_id is None:
            return None
        vista = await casos.get_case(self.call.tenant_id, self.call.case_id)
        return None if vista is None else str(vista.case_number)

    async def _cierre_de_derivacion(self) -> Utterance:
        """Lo que se dice despues de pasar el caso a un ajustador: el numero y adios.

        Antes la llamada seguia abierta, preguntaba "¿sigues ahi?" y terminaba por
        silencio sin haber dicho el numero de caso (2026-10-11).
        """
        self.closed = True
        self._pregunta_pendiente = None
        texto = closing.build_after_handoff(
            number=await self._numero_de_caso(),
            insurer=self.config.display_name,
            language=self.language,
        )
        return Utterance(text=self._del_catalogo(texto), end_reason=EndReason.HANDED_OFF)

    def postpone_closing(self) -> None:
        """El cierre del reporte quedo sin decir porque la persona seguia hablando:
        se vuelve a decidir despues de atender lo que dijo."""
        self.closed = False

    # --- Lo que se dice fuera de un turno (2026-10-11) ------------------------

    def take_awaited_answer(self) -> bool:
        """Si el turno que acaba de cerrar dejo una respuesta del fondo pendiente."""
        pendiente, self._espera_respuesta = self._espera_respuesta, False
        return pendiente

    def _lo_pendiente(self) -> str | None:
        """Volver al reporte y la pregunta que la persona todavia debe, o nada."""
        if self._pregunta_pendiente is None:
            return None
        retomar = copy_api.t(BACK_TO_REPORT, locale=self.language)
        return f"{retomar} {self._pregunta_pendiente}"

    def _con_lo_pendiente(self, text: str) -> str:
        """El texto, y despues la pregunta que la persona todavia debe."""
        pendiente = self._lo_pendiente()
        return text if pendiente is None else f"{text} {pendiente}"

    def background_answer(self, text: str) -> Utterance:
        """La respuesta que el fondo trajo --la de cobertura--, lista para decirla.

        Trae frases del catalogo y, a veces, la explicacion que dio la IA sobre la
        clausula: es texto compuesto, y se le tapa lo que tenga forma de dato. Eso es lo
        que va al sintetizador; la consola recibe el texto sin tapar (2026-10-13).

        **En dos lineas en la consola: la respuesta, y despues "volviendo al reporte" con
        su pregunta.** La base guarda la respuesta sola --la pregunta es de un turno
        anterior--, y la pantalla del caso destapa un turno solo si la copia que recuerda
        el navegador encaja con el entero (`shared/own-text`): una sola linea con la
        pregunta pegada no encajaria nunca.
        """
        pendiente = self._lo_pendiente()
        completo = text if pendiente is None else f"{text} {pendiente}"
        return Utterance(
            text=redaccion.redact_composed(completo, language=self.language),
            shown=(text,) if pendiente is None else (text, pendiente),
        )

    def answer_delayed(self) -> Utterance:
        """El fondo tarda mas de lo que se puede esperar callada: se dice, y se sigue."""
        frase = copy_api.t(ANSWER_DELAYED, locale=self.language)
        self._anotar(frase, speaker=Speaker.AGENT, at=datetime.now(UTC), from_catalog=True)
        return Utterance(
            text=self._del_catalogo(self._con_lo_pendiente(frase)), copy_key=ANSWER_DELAYED
        )

    def filler_phrase(self) -> Utterance:
        """La muletilla que toca: un acuse corto mientras se prepara la respuesta (2026-10-12).

        Rotan las tres del catalogo y nunca sale la misma dos veces seguidas en una llamada.
        **No se anota en la transcripcion del caso**: no es contenido, y una linea de
        "Listo…" en cada turno le haria ruido a la revision de cumplimiento y al ajustador.
        """
        indice = filler.next_index(self._ultima_muletilla)
        self._ultima_muletilla = indice
        clave, frase = filler.phrase(indice, language=self.language)
        return Utterance(text=self._del_catalogo(frase), copy_key=clave)

    def time_warning(self) -> Utterance:
        """El aviso de que queda poco, **dicho**: antes solo salia en la pantalla."""
        frase = copy_api.t(TIME_RUNNING_OUT, locale=self.language)
        return Utterance(text=self._del_catalogo(frase), copy_key=TIME_RUNNING_OUT)

    async def time_is_up(self) -> Utterance:
        """La despedida cuando se acaba el tiempo: que paso, el numero de caso y adios.

        Antes la llamada cortaba en seco a los tres minutos, sin numero de caso.

        **El caso pasa a la cola del ajustador**, con el motivo "limite de la demo":
        la frase dice que un ajustador lo revisa, y un caso que se quedara en captura
        no lo veria ninguno.
        """
        self.closed = True
        texto = closing.build_time_is_up(
            number=await self._numero_de_caso(),
            insurer=self.config.display_name,
            language=self.language,
        )
        self._derivar(texto, reason=HandoffReason.LIMIT, at=datetime.now(UTC))
        return Utterance(text=self._del_catalogo(texto), end_reason=EndReason.MAX_DURATION)

    def _anotar(
        self, text: str, *, speaker: Speaker, at: datetime, from_catalog: bool = False
    ) -> None:
        """Lanza la escritura de un turno en la transcripcion, sin esperarla.

        Sin ambito escrito no se anota nada: `transcript` nulo es un despliegue sin
        la transcripcion cableada, y se dice con su evento en vez de suponerlo --la
        alternativa es una llamada que termina y un caso que nadie puede cerrar, sin
        nada que lo explique--.
        """
        if self.call.case_id is None:  # pragma: no cover -- `speak_turn` ya lo exigio
            return
        if not text.strip():
            # Un turno sin nada audible no es un turno. Anotar una linea vacia
            # dejaria la transcripcion contando silencios como si fueran frases.
            return
        ambito = TranscriptScope(
            tenant_id=self.call.tenant_id,
            case_id=self.call.case_id,
            channel=Channel.VOICE,
            language=self.language,
        )
        # Lo que dijo la persona nunca es del catalogo: lo transcribio el
        # reconocedor y se tapa entero.
        escritura = (
            record_person_turn(ambito, text=text, now=at)
            if speaker is Speaker.INSURED
            else record_agent_turn(ambito, text=text, now=at, from_catalog=from_catalog)
        )
        launch_background(escritura)

    def _resolver_codigo(self, speech: SpeechEnd) -> _Resuelto:
        """Que se le entrega al grafo de este turno, y que se dice antes (BR3.5).

        Tres desenlaces: el turno va tal cual; el turno trae un codigo que hay
        que leer antes de anotar, y entonces no va nada al grafo todavia; o este
        turno era la respuesta a una lectura anterior.
        """
        pendiente = self._por_confirmar
        if pendiente is not None:
            _codigo, texto_original = pendiente
            self._por_confirmar = None
            if readback.accepted(speech.text, language=self.language):
                return _Resuelto(text=texto_original)
            # No confirmo: no se anota nada y se vuelve a pedir. El codigo se
            # descarta entero en vez de intentar corregirlo a medias.
            frase = retry.prompt_for(1, language=self.language)
            assert frase is not None  # noqa: S101 -- el primer peldano siempre existe
            return _Resuelto(
                text=None,
                say=Utterance(text=self._del_catalogo(frase.text), copy_key=frase.copy_key),
            )

        codigo = self._codigo_por_leer(speech)
        if codigo is None:
            return _Resuelto(text=speech.text)
        self._por_confirmar = (codigo, speech.text)
        leido = readback.build(codigo, language=self.language)
        return _Resuelto(
            text=None,
            say=Utterance(text=self._del_catalogo(leido.text), copy_key=leido.copy_key),
        )

    def _codigo_por_leer(self, speech: SpeechEnd) -> str | None:
        """El codigo dictado en este turno que hay que leer antes de anotar.

        Se miran los dos que se dictan caracter a caracter --la placa y el numero
        de poliza-- con los normalizadores de U11, no con un reconocedor propio:
        el que decodifica lo deletreado ya existe y es el mismo que usa el chat.
        """
        for normalizar in (normalization.normalize_plate, normalization.normalize_policy_number):
            codigo = normalizar(speech.text, language=self.language)
            if codigo and readback.needs_readback(
                codigo,
                language=self.language,
                transcript=speech.last,
                confidence_floor=self.confidence_floor,
            ):
                return codigo
        return None

    async def _cierre_si_el_caso_quedo_completo(self) -> Utterance | None:
        """El cierre por voz, cuando el caso acaba de quedar completo (BR3.7).

        Lo decide la completitud del caso, que U4 **deriva** de los campos: un
        numero guardado seria un numero que alguien puede escribir a mano.

        Lo que se dice aqui es la cola del cierre --como quedo el caso, el numero y la
        despedida--; el resumen de tres frases lo trajo el grafo en su turno, y
        armarlo aqui habria obligado a este canal a descifrar campos del caso.

        Termina la llamada con su propio motivo, porque un reporte terminado no
        es ni colgar ni un silencio.
        """
        if self.call.case_id is None or self.closed:
            return None
        resultado = await casos.summary_with_fields(self.call.tenant_id, self.call.case_id)
        if resultado is None:
            return None
        resumen, _ = resultado
        if resumen.completeness.complete < resumen.completeness.total:
            return None
        self.closed = True
        texto = await self._despedida_del_reporte(resumen.case_number)
        return Utterance(text=self._del_catalogo(texto), end_reason=EndReason.COMPLETED)

    async def _despedida_del_reporte(self, number: str) -> str:
        """Como quedo el reporte, dicho al despedirse (US1.17, 2026-10-13).

        Al terminar la captura el caso pasa a revision y las reglas deciden **en el fondo** si
        se cierra solo o lo mira un ajustador; esta despedida espera ese resultado un instante
        (`closing.RESULT_WAIT`) y dice lo que hay:

        - cerrado como `registered`: «quedo registrado y no necesita ajustador»;
        - todavia en revision tras la espera: la neutral, que no promete ninguna de las dos;
        - cualquier otra cosa --derivado, o un caso que nunca paso por revision--: la de
          siempre, «un ajustador revisa tu caso».

        **El resultado se dice una sola vez, y es por aqui.** El aviso de fondo que lleva el
        resultado del chat (`closing_outcome._anunciar`) en una llamada solo guarda la frase
        en la transcripcion: decirla tambien por el oyente de la llamada la repetiria.
        """
        vista = await self._esperar_el_resultado()
        insurer = self.config.display_name
        if vista is not None and vista.state is CaseState.CLOSED:
            if vista.resolution is Resolution.REGISTERED:
                return closing.build_registered(
                    number=number, insurer=insurer, language=self.language
                )
        elif vista is not None and vista.state in closing_plan.REVIEW_STATES:
            return closing.build_pending(number=number, insurer=insurer, language=self.language)
        return closing.build(number=number, insurer=insurer, language=self.language)

    async def _esperar_el_resultado(self) -> casos.CaseView | None:
        """El caso tal como esta, esperando hasta `result_wait` a que salga de la revision.

        Solo **lee** el estado: las reglas y la revision de cumplimiento corren en el fondo
        (P4, R2) y esto no las espera a ellas sino al cambio de estado que dejan.
        """
        if self.call.case_id is None:
            return None
        reloj = asyncio.get_running_loop()
        limite = reloj.time() + self.result_wait.total_seconds()
        while True:
            vista = await casos.get_case(self.call.tenant_id, self.call.case_id)
            if vista is None or vista.state not in closing_plan.REVIEW_STATES:
                return vista
            falta = limite - reloj.time()
            if falta <= 0:
                return vista
            await asyncio.sleep(min(self.result_poll_seconds, falta))

    def _hablar(self, event: TurnEvent) -> Utterance:
        """La forma hablada de cada uno de los cinco eventos de C-14 (BR3.6).

        `Waiting` lleva el texto ya resuelto --a diferencia del flujo del chat,
        que manda solo la clave-- precisamente para que la voz lo diga sin otra
        ida y vuelta. Los cinco tienen rama, y el `assert_never` del final es lo
        que lo obliga: un sexto evento en la union deja de compilar aqui, que es
        exactamente donde tiene que enterarse.
        """
        # **De donde viene el texto es un dato, no una adivinanza.** Los tres eventos
        # con clave traen una frase del catalogo ya resuelta; `FinalText` lo dice en
        # `from_catalog`, porque sus respuestas se componen de varias frases y una
        # clave sola no las describiria. Lo que escribio un modelo se tapa entero.
        # Lo que escribio un modelo se tapa para sintetizarlo, y la consola lo lee tal
        # cual: sin ese `shown`, "Gracias, Juan" se leia "Gracias, [NOMBRE 1]" en la
        # pantalla de quien acababa de decir su nombre.
        if isinstance(event, FinalText):
            if event.from_catalog:
                return Utterance(text=self._del_catalogo(event.text))
            return Utterance(text=self._de_fuera(event.text), shown=(event.text,))
        if isinstance(event, PartialText):
            return Utterance(text=self._de_fuera(event.text), shown=(event.text,))
        if isinstance(event, Waiting):
            return Utterance(text=self._del_catalogo(event.text), copy_key=event.copy_key)
        if isinstance(event, Handoff):
            return Utterance(text=self._del_catalogo(event.text), copy_key=event.copy_key)
        if isinstance(event, TurnError):
            return Utterance(text=self._del_catalogo(event.text), copy_key=event.copy_key)
        assert_never(event)

    # --- El corte y la retoma (BR6.1 a BR6.5, BR8.3) --------------------------

    async def look_for_resumable(self, dropped: CallSession) -> resume.Resumable | None:
        """El caso que este navegador dejo a medias, si lo hay.

        La llamada cortada se busca por el resumen de la clave del visitante y
        por nada mas (BR6.3): la poliza de ejemplo es publica, y buscar por ella
        ofreceria el caso de otra persona.
        """
        self._retomable = await resume.find(
            dropped, tenant_id=self.call.tenant_id, now=self.call.started_at, language=self.language
        )
        return self._retomable

    def offer_resume(self) -> Utterance | None:
        """Lo que se dice **despues de la apertura completa** (BR6.2, BR6.5).

        Si el caso ya se decidio, primero el resultado y despues la oferta: la
        persona llama para saber que paso, y preguntarle en que se le puede
        ayudar antes de contarselo es la forma mas segura de que lo pregunte
        ella.
        """
        retomable = self._retomable
        if retomable is None:
            return None
        if self.disclosed_at is None:
            msg = "BR6.2: la oferta de retomar va despues de la apertura completa"
            raise ValueError(msg)
        partes = []
        if retomable.spoken_decision is not None:
            partes.append(retomable.spoken_decision.text)
        partes.append(resume.offer(language=self.language))
        texto = " ".join(partes)
        self._pregunta_pendiente = pending_question.last_question(texto)
        return Utterance(text=self._del_catalogo(texto))

    def heard(self, speech: SpeechEnd) -> bool:
        """Si lo que llego se puede dar por entendido (la escalera de `retry`).

        La oferta de retomar no se contesta con algo que no se oyo: un turno vacio o de
        baja confianza no es un "no", y tomarlo por uno abria un caso nuevo.
        """
        return retry.understood(speech.last, confidence_floor=self.confidence_floor)

    def resume_reply(self, speech: SpeechEnd) -> resume.Reply:
        """Que contesto la persona a "¿seguimos con ese?": un si, un no o algo con contenido."""
        return resume.reply_to(speech.text, language=self.language)

    def resume_accepted(self, answer: str, *, at: datetime) -> bool:
        """Si la persona sigue con su caso, o llama por otro accidente (BR6.4).

        Seguir es todo lo que no es un "no" ni pedir uno nuevo: un "si" y tambien contar
        algo del accidente. Aceptar deja la marca de recuperacion **enlazada al caso
        original** (BR8.3): sin ese enlace, la marca no distingue una retoma de una
        llamada nueva y NFR3 se contaria sobre el denominador equivocado. Y deja como
        pregunta pendiente la que el caso tenia, para repetirla despues de decir algo que
        no la contesta.
        """
        retomable = self._retomable
        if retomable is None:
            return False
        self._retomable = None
        if resume.reply_to(answer, language=self.language) is resume.Reply.NEW_CASE:
            return False
        self._pregunta_pendiente = retomable.pending_question
        latency.resume_after_drop(
            tenant_id=self.call.tenant_id,
            call_id=self.call.call_id,
            case_id=retomable.case_id,
            dropped_call_id=retomable.dropped_call_id,
            previous_end_reason=retomable.ended_by,
            at=at,
        )
        return True

    def note_person_turn(self, speech: SpeechEnd) -> None:
        """Anota lo que la persona dijo cuando el turno se contesta sin pasar por `speak_turn`."""
        self._anotar(speech.text, speaker=Speaker.INSURED, at=speech.at)

    def resume_followup(self) -> Utterance:
        """Tras un "si" a seguir con el caso: la pregunta que habia quedado pendiente, una vez.

        Antes la llamada no decia nada y a los cinco segundos preguntaba "¿sigues ahi?".
        Sin pregunta pendiente --el caso ya se decidio, o solo falta su lectura final-- se
        le pregunta que quiere agregar.
        """
        acuse = resume.acknowledge_continue(language=self.language)
        pregunta = self._pregunta_pendiente
        if pregunta is None:
            pregunta = resume.ask_what_else(language=self.language)
            self._pregunta_pendiente = pending_question.last_question(pregunta)
        # El caso ya existe: lo que diga despues es de su reporte, no una llamada que
        # todavia tenga que decir a que viene.
        self._proposito_decidido = True
        return self._frase_fija(f"{acuse} {pregunta}", resume.ACCEPTED)

    def new_case_followup(self) -> Utterance:
        """Tras un "no": se abre uno nuevo y se pregunta en que se la puede ayudar."""
        acuse = resume.acknowledge_new_case(language=self.language)
        pregunta = opening.first_question(language=self.language)
        self._pregunta_pendiente = pending_question.last_question(pregunta)
        self._proposito_decidido = False
        return self._frase_fija(f"{acuse} {pregunta}", resume.NEW_CASE)

    # --- La interrupcion (BR4.1, BR4.3, BR4.5) --------------------------------

    @property
    def needs_opening_again(self) -> bool:
        """BR4.5: media divulgacion no es divulgacion.

        Se sabe por la hora de fin: si la apertura no llego a registrarse, no
        esta dicha, y se repite **entera** antes de la primera pregunta.
        """
        return self.disclosed_at is None

    def on_barge_in(
        self, transcript: Transcript, *, detected_at: datetime, stopped_at: datetime, turn_id: str
    ) -> Utterance | None:
        """La persona interrumpio: se deja de sintetizar y se marca la parada.

        Devuelve la frase de ceder el turno, o `None` cuando lo que dijo ya trae
        la correccion: responderle que siga a quien ya dijo lo que queria
        corregir es hacerle repetirlo.

        Quien vacia la cola de reproduccion es el navegador, con el cuadro
        `stop_audio` (BR4.3): el servidor no puede retirar lo que ya mando.
        """
        latency.barge_in_stop(
            tenant_id=self.call.tenant_id,
            call_id=self.call.call_id,
            turn_id=turn_id,
            detected_at=detected_at,
            at=stopped_at,
        )
        if transcript.text.split():
            return None
        return Utterance(
            text=self._del_catalogo(barge_in.acknowledgement(language=self.language)),
            copy_key=barge_in.ACKNOWLEDGE,
        )

    def interrupted_by(
        self, transcript: Transcript | None, *, min_words: int = barge_in.DEFAULT_MIN_WORDS
    ) -> bool:
        """Si esto cuenta como interrupcion y no como ruido (BR4.1)."""
        return barge_in.interrupts(transcript, min_words=min_words)

    def opening_is_sounding(self, *, now: datetime) -> bool:
        """Si la apertura todavia suena: no se ha registrado, o su hora de fin no llego.

        `disclosed_at` es la hora **estimada** en que termina de sonar en el navegador,
        no la del fin del envio: el servidor la manda en un segundo y ella dura diez.
        """
        return self.disclosed_at is None or now < self.disclosed_at

    def greeting_over_opening(self, transcript: Transcript | None, *, now: datetime) -> bool:
        """Si esto es un saludo dicho encima de la apertura, que no la interrumpe.

        "¿Alo?" y "hola" son la forma de comprobar que hay alguien, no una
        interrupcion; cortar la apertura por ellos la repetia entera (BR4.5) y la
        persona oia el saludo dos veces (2026-10-11). Algo con contenido ("tuve un
        choque") si la interrumpe, como siempre.
        """
        return (
            transcript is not None
            and self.opening_is_sounding(now=now)
            and barge_in.is_greeting(transcript.text, language=self.language)
        )

    # --- Los silencios (BR5.1, BR5.2) -----------------------------------------

    def silence_deadline(self, *, since: datetime) -> datetime:
        """Cuando vence la tolerancia, contada desde que la agente callo (BR5.1).

        Tras un "un momento" es la espera larga, por una sola vez (2026-10-11).
        """
        if self._espera_larga:
            return since + max(self.silence_tolerance, silence.HOLD_TOLERANCE)
        return since + self.silence_tolerance

    def on_silence(self) -> Utterance | None:
        """El peldano que toca. El tercero **termina la llamada** (BR5.2)."""
        # La espera larga se gasta con el primer silencio: lo que sigue ya no es
        # alguien buscando su poliza sino alguien que no esta.
        self._espera_larga = False
        self._silencios += 1
        frase = silence.prompt_for(self._silencios, language=self.language)
        if frase is None:
            return None
        if frase.step is silence.SilenceStep.OFFER:
            self._abrir_la_oferta()
        return Utterance(
            text=self._del_catalogo(frase.text),
            copy_key=frase.copy_key,
            end_reason=EndReason.SILENCE if frase.ends_call else None,
        )


__all__ = [
    "HOLD_ACKNOWLEDGE",
    "LANGUAGE_SWITCHED",
    "TURNOS_PARA_CAMBIAR_SOLO",
    "CallEngine",
    "LanguageChange",
    "SwitchReason",
    "TurnHandler",
    "Utterance",
]
