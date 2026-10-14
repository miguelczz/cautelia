"""El ritmo de una llamada sobre el transporte: quien habla, quien escucha, quien calla.

`untangle.voice` sabe **que** decir en cada momento; este modulo sabe **cuando**,
porque es el unico sitio que tiene a la vez el socket abierto, el reconocedor y
la sintesis. Es el llamador de produccion de `CallEngine`, que hasta esta tanda
no tenia ninguno.

**Vive en la unidad, y en la tanda 5 no.** Nacio en `untangle.server` porque
recibia la plataforma de voz entera, y eso son los adaptadores, que solo la raiz
importa. Al reducir esa dependencia al puerto `CallVoice` --cuatro lineas-- dejo
de haber ninguna razon para tenerlo arriba, y una: el conductor de evaluaciones
esta **debajo** de la raiz y no podia alcanzarlo. Un ritmo de llamada que el
corredor de evaluaciones no puede ejecutar es un ritmo que solo se mide en
produccion.

**Por que es un archivo aparte de las rutas.** Aquellas son una frontera HTTP
--tres verbos, sus cuerpos y sus codigos-- y esto es una conversacion en tiempo
real con tres relojes corriendo a la vez. Juntarlos daria un archivo donde el
apreton de manos y el turno hablado se leen como si fueran la misma clase de
cosa, y no lo son.

**El transporte entra por un `Protocol`.** Este ciclo no conoce WebSocket: recibe
audio y cuadros por `CallChannel` y responde por el mismo. Es lo que permite
probarlo entero sin levantar un servidor, y es tambien lo que deja la conversion
de formato en un solo sitio, la frontera del transporte, que es donde `ports.py`
dice que vive.

**Aqui no hay `sleep` de prueba.** Cada espera tiene su instante limite, calculado
con el reloj que entra por argumento; una prueba que alimente el guion de
transcritos de golpe resuelve todas las esperas en el acto.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol, runtime_checkable

from untangle import observability
from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.compliance.redaction.api import Redacted
from untangle.orchestration.nodes.intake.identity import ReportIntent

# `Transcript` a secas es el **del reconocedor** (C-16). El del protocolo se
# escribe siempre `WireTranscript`: son dos cosas distintas, y el nombre corto se
# lo queda la que mas se maneja aqui.
from untangle.providers.ports import SPEECH_AUDIO, ListenEvent, SpeechStarted, Transcript
from untangle.telemetry.spend import attribution as spend_attribution
from untangle.telemetry.spend.models import VoiceMode
from untangle.tenancy.models import TenantId, TranscriptionMode
from untangle.voice import answers, own_voice, resume
from untangle.voice.call import CallEngine, Utterance
from untangle.voice.case_opening import open_for_call
from untangle.voice.early_understanding import Discard
from untangle.voice.first_turn import CallPurpose
from untangle.voice.latency import (
    filler_said,
    first_audio,
    listening_reopened,
    speech_signal_discarded,
)
from untangle.voice.models import EndReason
from untangle.voice.session import switch_case
from untangle.voice.turn_detection import Ending, SpeechEnd, TurnDetector
from untangle.voice.wire import (
    TIME_RUNNING_OUT,
    Case,
    Hangup,
    Latency,
    Notice,
    ServerFrame,
    State,
    StopAudio,
)
from untangle.voice.wire import Transcript as WireTranscript

#: Cuantos trozos de 20 ms caben en la cola de entrada antes de que recibir se
#: detenga. Cinco segundos.
#:
#: **Acotada a proposito, y es la mitad de D1 que se paga aqui.** El transporte
#: es TCP: en una red mala no se pierden paquetes, se **acumula retraso**. Una
#: cola sin limite convertiria ese retraso en memoria --minutos de audio
#: esperando a un reconocedor que no da abasto-- y en una conversacion donde la
#: agente contesta a lo que se dijo hace medio minuto. Con el limite puesto, el
#: que se detiene es quien recibe, que es lo que de verdad hay que frenar.
COLA_DE_AUDIO = 250

#: Lo que dura cada trozo de audio que manda el navegador: 20 ms de PCM de 16 bits a 24 kHz.
TROZO_DE_AUDIO_S = 0.02

#: Lo que se espera de mas, al final, sobre la hora estimada en que termina de sonar
#: lo ultimo: el audio todavia cruza la red y la cola del navegador.
FINAL_PLAYBACK_GRACE_S = 0.4
#: El tope de esa espera. La despedida mas larga --paso siguiente, numero de caso y
#: adios-- suena en unos once segundos.
FINAL_PLAYBACK_MAX_S = 15.0

#: Cuanto se aguarda, callada, la respuesta que el fondo va a traer --la de
#: cobertura-- antes de decir que sigue revisando. Mientras tanto no se pregunta
#: "¿sigues ahi?": quien calla es la agente, no la persona.
ANSWER_WAIT = timedelta(seconds=12)

#: Cuanto se sigue aguardando la respuesta del fondo **despues** de decir "sigo
#: revisando". Antes la espera terminaba ahi y el reloj de silencio arrancaba contra la
#: persona: a los cinco segundos "¿sigues ahi?" y a los quince la despedida, con la
#: respuesta todavia en camino (2026-10-11). Pasado esto, la agente deja de esperar y
#: el silencio vuelve a contar; si la respuesta llega despues, se dice igual.
LATE_ANSWER_WAIT = timedelta(seconds=30)

#: Cuanto se espera, desde que se cerro el turno, a que la respuesta tenga su primera
#: frase antes de decir una muletilla (2026-10-12). Si llega antes --lo que resuelven las
#: reglas, los pedidos de espera o de idioma, las ofertas--, no hay muletilla. Es del
#: ritmo de la llamada y no de la aseguradora; `None` en `CallRunner.filler_after` la
#: apaga del todo.
FILLER_AFTER = timedelta(milliseconds=350)

#: Con que cierres de frase se adelanta la lectura del modelo, en cuanto llega el final del
#: reconocedor (2026-10-13). La que termina en una palabra que pide continuacion ("mi poliza
#: es...") casi nunca esta acabada: su tolerancia es la mas larga a proposito, y leerla antes es
#: pagar el modelo para tirar la lectura. Las otras dos si: la cerrada y la larga sin su punto.
ADVANCED_ENDINGS = (Ending.CLOSED, Ending.UNPUNCTUATED)

#: Cuanto antes del limite de la llamada empieza la despedida: lo que tarda en
#: sonar "se nos acabo el tiempo", el numero de caso y el adios. La llamada no
#: pasa de su duracion maxima por despedirse.
FAREWELL_BUDGET = timedelta(seconds=14)


class _Despierta:
    """Una senal en la cola de lo oido: el fondo dejo algo por decir.

    No es un transcrito y nadie lo trata como tal; solo saca al ciclo de su espera
    para que mire lo que tiene pendiente.
    """


_DESPIERTA = _Despierta()


@dataclass
class _Muletilla:
    """La muletilla de un turno: una tarea que espera y, si la respuesta tarda, la dice."""

    tarea: asyncio.Task[None]
    #: La tarea dejo de esperar y va a hablar. Desde ahi no se cancela: se deja terminar.
    empezo: asyncio.Event


class CallVoice(Protocol):
    """Lo que el ciclo necesita de la voz de U15, y nada mas (C-16).

    Es la parte de `SpeechPlatform` que se usa aqui, escrita como puerto en vez
    de tomar la plataforma entera. Dos razones y las dos pesan: el ciclo se puede
    probar con los dobles de esta unidad --que heredan de los `Protocol` de
    C-16-- sin construir clientes ni adaptadores, y lo que este archivo puede
    pedirle a la voz queda escrito en cuatro lineas en vez de ser "lo que la
    plataforma exponga".
    """

    def listen(
        self, tenant_id: TenantId, audio: AsyncIterator[bytes], *, language: Locale
    ) -> AsyncIterator[ListenEvent]: ...

    def speak(
        self, tenant_id: TenantId, text: Redacted, *, mode: VoiceMode, language: Locale
    ) -> AsyncIterator[bytes]: ...


class CallSpeech(Protocol):
    """La boca de una llamada ya abierta: una frase detras de otra (C-16).

    Es lo que el ciclo usa para decir cada frase. Detras puede haber una conexion con el
    proveedor que se mantiene abierta mientras dura la llamada, o nada mas que la voz suelta;
    al ciclo le da igual. **Una frase a la vez**, y quien deja de leer una a medias cierra su
    flujo antes de pedir la siguiente (`_cerrando`): con la conexion abierta, la frase siguiente
    espera a que la anterior se cierre.
    """

    def speak(
        self, tenant_id: TenantId, text: Redacted, *, mode: VoiceMode, language: Locale
    ) -> AsyncIterator[bytes]: ...


@runtime_checkable
class SessionVoice(CallVoice, Protocol):
    """Una voz que sabe mantener su conexion abierta durante toda la llamada.

    Conectar con el proveedor de la voz cuesta de 0,7 a 0,8 s, y una llamada dice una frase
    detras de otra: abrir una conexion por frase era pagar esa espera delante de cada una.
    `speech_session` abre una vez, antes de la apertura, y cierra al terminar la llamada.

    Es un puerto aparte y no parte de `CallVoice` para que quien solo habla frase por frase
    --los dobles de prueba, la persona simulada-- no tenga que fingir una sesion: el ciclo
    pregunta si la voz la ofrece y, si no, habla por la voz suelta.
    """

    def speech_session(
        self, tenant_id: TenantId, *, mode: VoiceMode, language: Locale
    ) -> contextlib.AbstractAsyncContextManager[CallSpeech]: ...


@contextlib.asynccontextmanager
async def _cerrando(flujo: AsyncIterator[bytes]) -> AsyncIterator[AsyncIterator[bytes]]:
    """El flujo de una frase, cerrado al dejar de leerlo aunque no se haya agotado.

    `async for` no cierra el flujo que recorre si se sale antes del final, y la boca de la
    llamada no empieza la frase siguiente mientras la anterior siga abierta. Cerrarlo aqui,
    en la tarea que lo leia, tambien evita que lo cierre el recolector desde otra.
    """
    try:
        yield flujo
    finally:
        cerrar = getattr(flujo, "aclose", None)
        if cerrar is not None:
            await cerrar()


class CallChannel(Protocol):
    """El transporte de una llamada, visto desde el ciclo (C-29).

    Tres operaciones y ninguna mas. Lo que llega es audio crudo o el cuadro de
    colgar; lo que sale son cuadros del vocabulario cerrado y audio.
    """

    def inbound(self) -> AsyncIterator[bytes | Hangup]:
        """El flujo del navegador. Se agota cuando el socket se cierra."""
        ...

    async def send(self, frame: ServerFrame) -> None: ...

    async def send_audio(self, chunk: bytes) -> None: ...


class _Toca(StrEnum):
    """Lo que toca cuando la espera vuelve sin nada nuevo."""

    TURNO = "turno"
    SILENCIO = "silencio"
    ESPERAR = "esperar"
    #: Se aguardaba una respuesta del fondo y no llego a tiempo.
    SIN_RESPUESTA = "sin_respuesta"


@dataclass
class CallRunner:
    """Una llamada en curso. Una instancia por llamada, como el motor."""

    engine: CallEngine
    channel: CallChannel
    speech: CallVoice
    now: Callable[[], datetime]
    max_call: timedelta
    warn_at: timedelta
    #: Cuanto se espera la primera frase de una respuesta antes de decir una muletilla.
    #: Nulo --lo que trae por omision-- la apaga: las evaluaciones y las pruebas no
    #: quieren una frase que depende de cuanto tarda el modelo. La llamada de verdad la
    #: enciende con `FILLER_AFTER` (`voice_routes._atender_socket`).
    filler_after: timedelta | None = None
    #: Quien quiere ver el error entero cuando la llamada falla: `run` atrapa cualquier
    #: excepcion para terminar con su motivo, y el registro solo dice tipo y sitio. Lo usa
    #: la llamada simulada (`voice:simular`) para imprimir la traza; el servidor no lo pone.
    on_failure: Callable[[Exception], None] | None = None
    _entrante: asyncio.Queue[bytes | None] = field(
        default_factory=lambda: asyncio.Queue(maxsize=COLA_DE_AUDIO), init=False
    )
    _oido: asyncio.Queue[ListenEvent | _Despierta | None] = field(
        default_factory=asyncio.Queue, init=False
    )
    #: La persona colgo con su cuadro. Distinto de que el socket muera solo.
    _colgo: bool = field(default=False, init=False)
    #: El flujo del navegador o el del reconocedor se acabaron. Es un corte
    #: (BR6.1), que no es un final sino una pausa.
    _cerrado: bool = field(default=False, init=False)
    _turnos: int = field(default=0, init=False)
    _aviso_dado: bool = field(default=False, init=False)
    #: Mientras la oferta de retomar espera respuesta, el siguiente turno de la
    #: persona es esa respuesta y no una frase para el grafo (BR6.2, BR6.4).
    _oferta_abierta: bool = field(default=False, init=False)
    #: Lo que interrumpio, guardado hasta que el turno siguiente lo escuche.
    #:
    #: **No vuelve a la cola**, y ese fue un defecto de verdad: devolviendolo, una
    #: apertura interrumpida se repetia, volvia a encontrar el mismo transcrito y
    #: se interrumpia otra vez, para siempre. Lo que BR4.5 pide es repetir la
    #: divulgacion, no volver a oir la misma frase.
    _interrumpio: Transcript | None = field(default=None, init=False)
    #: Hasta cuando **sigue sonando en el navegador** lo ultimo que dijo la agente.
    #:
    #: El servidor sintetiza y manda una frase en uno o dos segundos; el navegador
    #: la reproduce durante los que dure. Hasta el 2026-10-06 el reloj de silencio
    #: arrancaba al terminar el envio, asi que a los cinco segundos de empezar a
    #: sonar la apertura la agente ya creia que la persona habia callado: "¿sigue
    #: ahi?", la oferta, la despedida, y colgaba sola. Lo vio Miguel en la primera
    #: llamada real. El formato del audio es fijo (PCM de 16 bits, 24 kHz, mono) y
    #: el servidor sabe cuantos bytes mando, asi que sabe cuando termina de sonar.
    _sonando_hasta: datetime | None = field(default=None, init=False)
    #: "Escuchando" esta por anunciar: se anuncia cuando termina de sonar, no
    #: cuando termina de enviarse.
    _escucha_pendiente: bool = field(default=False, init=False)
    #: Lo que el fondo trajo y todavia no se ha dicho (2026-10-11).
    _por_decir: list[answers.BackgroundAnswer] = field(default_factory=list, init=False)
    #: Hasta cuando se aguarda, sin contar silencio, la respuesta del fondo.
    _respuesta_hasta: datetime | None = field(default=None, init=False)
    #: Ya se dijo "sigo revisando": la espera que sigue es la ultima (`LATE_ANSWER_WAIT`).
    _demora_dicha: bool = field(default=False, init=False)
    #: El aviso de tiempo esta dado en pantalla y falta decirlo: la persona hablaba.
    _aviso_por_decir: bool = field(default=False, init=False)
    #: El caso por el que esta llamada escucha al fondo.
    _caso_escuchado: str | None = field(default=None, init=False)
    #: Antes de la respuesta de este turno sono una muletilla. Lo lee el primer audio, que
    #: lo anota en su marca: la muletilla no es el primer audio, y asi se puede ver.
    _tras_muletilla: bool = field(default=False, init=False)
    #: Cuando llego el primer trozo de audio del navegador (2026-10-12): el segundo cero de
    #: los tiempos de palabra del reconocedor. Hay un solo flujo por llamada, y la cola de
    #: entrada es FIFO y no descarta, asi que ese primer trozo es el primero que ve el
    #: reconocedor --aunque su canal tarde en abrirse y lo reciba despues--. Nulo hasta que
    #: llega el primero.
    _flujo_empezo_a: datetime | None = field(default=None, init=False)
    #: Lo que la agente dijo hace poco y cuando suena: con eso se quita su propia voz de lo
    #: que el reconocedor oye, cuando el altavoz vuelve por el microfono (2026-10-13).
    _propia_voz: own_voice.OwnVoice = field(default_factory=own_voice.OwnVoice, init=False)
    #: Cuantas veces el reconocedor aviso de que alguien empezo a hablar. Lo cuenta quien
    #: recibe la escucha y no quien la consume, para que lo sepa tambien una muletilla que
    #: espera mientras el ciclo esta ocupado atendiendo el turno.
    _voces_oidas: int = field(default=0, init=False)
    #: Lo que valia `_voces_oidas` cuando se cerro el turno que se esta atendiendo: si
    #: crecio, la persona retomo la palabra despues de que se le cerro el turno.
    _voces_al_cerrar_el_turno: int = field(default=0, init=False)
    #: La boca abierta de esta llamada, mientras `run` la tiene abierta. Nula fuera de `run`, y
    #: siempre nula con una voz que no ofrece sesion: ahi las frases salen por la voz suelta.
    _habla: CallSpeech | None = field(default=None, init=False)

    # --- Lo que el fondo trae -------------------------------------------------

    def _escuchar_al_fondo(self) -> None:
        """Apunta esta llamada como oyente de su caso; si el caso cambio, lo cambia."""
        llamada = self.engine.call
        if self._caso_escuchado == llamada.case_id:
            return
        self._dejar_de_escuchar_al_fondo()
        if llamada.case_id is None:
            return
        self._caso_escuchado = llamada.case_id
        answers.listen(llamada.tenant_id, llamada.case_id, self._llego_del_fondo)

    def _dejar_de_escuchar_al_fondo(self) -> None:
        if self._caso_escuchado is not None:
            answers.stop(self.engine.call.tenant_id, self._caso_escuchado)
            self._caso_escuchado = None

    def _llego_del_fondo(self, respuesta: answers.BackgroundAnswer) -> None:
        self._por_decir.append(respuesta)
        # El estado del caso que la lectura adelantada vio ya no es el de ahora: la respuesta que
        # esperaba el fondo cambia lo que el modelo debe decir de ella.
        self.engine.drop_advanced(Discard.STATE_CHANGED)
        self._oido.put_nowait(_DESPIERTA)

    async def _decir_lo_del_fondo(self, detector: TurnDetector) -> bool:
        """Dice lo que el fondo trajo, si la persona no esta hablando. Devuelve si dijo.

        Nunca encima de la persona: si esta a mitad de una frase, espera a que su
        turno se atienda y se dice despues.
        """
        if not self._por_decir or detector.speaking:
            return False
        pendientes, self._por_decir = self._por_decir, []
        self._respuesta_hasta = None
        self._demora_dicha = False
        for respuesta in pendientes:
            await self._decir(self.engine.background_answer(respuesta.text))
        return True

    # --- Lo que corre en paralelo ---------------------------------------------

    async def _recibir(self) -> None:
        """Pasa el audio del navegador a la cola, y anota si colgo (BR1.6)."""
        try:
            async for pieza in self.channel.inbound():
                if isinstance(pieza, Hangup):
                    self._colgo = True
                    break
                if self._flujo_empezo_a is None:
                    self._flujo_empezo_a = self.now()
                await self._entrante.put(pieza)
        finally:
            self._cerrado = self._cerrado or not self._colgo
            await self._entrante.put(None)

    async def _audio(self) -> AsyncIterator[bytes]:
        while True:
            trozo = await self._entrante.get()
            if trozo is None:
                return
            yield trozo

    async def _escuchar(self) -> None:
        """Pone en la cola lo que el reconocedor va entendiendo (BR3.1).

        **Con un reconocedor de un solo idioma por conexion, cambiar el idioma de la
        llamada lo reabre** (2026-10-13). El idioma se le dice al abrir el canal, asi que
        cambiar la voz sin cambiar el oido era el defecto de la auditoria (V18): la agente
        hablaba en uno y oia en el otro. Cuando el motor cambia el idioma se cierra esta
        escucha y se abre otra con el nuevo, sobre **la misma cola de audio**: lo que el
        navegador mande mientras tanto espera ahi, hasta cinco segundos (`COLA_DE_AUDIO`).

        Con el reconocedor en modo multiidioma no hay nada que reabrir: el idioma lo
        detecta el modelo en cada palabra y la conexion sirve para los dos.
        """
        try:
            if not self._escucha_sigue_al_idioma():
                await self._pasar_lo_oido(self.engine.language)
                return
            while await self._escuchar_en_un_idioma():
                self._anotar_la_reapertura()
        finally:
            self._cerrado = True
            await self._oido.put(None)

    def _escucha_sigue_al_idioma(self) -> bool:
        """Si la conexion del reconocedor depende del idioma de la llamada.

        Sin la eleccion del reconocedor en la configuracion se supone que si: es el lado
        seguro, porque reabrir de mas cuesta una conexion y no reabrir deja a la persona
        sin que la oigan.
        """
        stt = self.engine.config.voice.stt
        return stt is None or stt.mode is TranscriptionMode.MONOLINGUAL

    async def _escuchar_en_un_idioma(self) -> bool:
        """Escucha en el idioma de ahora. Devuelve si hay que abrirla otra vez: cambio el idioma.

        Termina cuando el reconocedor acaba (el audio se agoto: devuelve falso) o cuando el
        motor cambia el idioma (devuelve cierto). Si el reconocedor falla, el fallo sale.
        Las dos tareas se cierran siempre, tambien si cancelan a quien las espera al colgar.
        """
        idioma = self.engine.language
        escucha = asyncio.create_task(self._pasar_lo_oido(idioma))
        cambio = asyncio.create_task(self._hasta_que_cambie_el_idioma(idioma))
        try:
            await asyncio.wait({escucha, cambio}, return_when=asyncio.FIRST_COMPLETED)
            if escucha.done():
                escucha.result()
                return False
            return True
        finally:
            for tarea in (escucha, cambio):
                if not tarea.done():
                    tarea.cancel()
            await asyncio.gather(escucha, cambio, return_exceptions=True)

    async def _hasta_que_cambie_el_idioma(self, idioma: Locale) -> None:
        """Espera a que el motor deje la llamada en otro idioma que `idioma`.

        Se vuelve a mirar el idioma antes de dormir, no solo la senal: un cambio que ocurre
        mientras no se esta esperando no puede perderse.
        """
        while self.engine.language == idioma:
            self.engine.language_changed.clear()
            await self.engine.language_changed.wait()

    def _anotar_la_reapertura(self) -> None:
        """Deja el rastro de la reapertura y corrige el origen de los tiempos de palabra.

        Los tiempos del reconocedor cuentan desde que abrio su canal, y el nuevo abre ahora:
        su segundo cero es el del primer trozo de audio que le toca, que es el mas viejo de
        los que esperaban en la cola. Es una estimacion --cada trozo es de 20 ms-- y alcanza
        para lo que se hace con ella: ubicar el eco de la agente y la ultima palabra.
        """
        listening_reopened(
            tenant_id=self.engine.call.tenant_id,
            call_id=self.engine.call.call_id,
            language=self.engine.language,
        )
        if self._flujo_empezo_a is not None:
            esperando = self._entrante.qsize() * TROZO_DE_AUDIO_S
            self._flujo_empezo_a = self.now() - timedelta(seconds=esperando)

    async def _pasar_lo_oido(self, idioma: Locale) -> None:
        """Una conexion del reconocedor: lo que entiende va a la cola, sin la voz de la agente."""
        async for transcrito in self.speech.listen(
            self.engine.call.tenant_id, self._audio(), language=idioma
        ):
            oido = self._sin_la_voz_de_la_agente(transcrito)
            if oido is None:
                continue
            if isinstance(oido, SpeechStarted):
                self._voces_oidas += 1
            await self._oido.put(oido)

    def _durante_la_apertura(self, momento: datetime | None) -> bool:
        """Si esto se dijo mientras sonaba la apertura: entonces no se escucha (2026-10-14).

        Mientras la apertura se envia --todavia no se registro (`disclosed_at`)-- todo es
        durante. Despues, lo que termino de decirse antes de su hora de fin estimada, que es
        cuando deja de sonar en el navegador. Lo que no trae hora (`None`) ya no se descarta
        aqui: lo filtra el eco. Una frase que empezo encima y sigue despues se oye entera.
        """
        fin = self.engine.disclosed_at
        if fin is None:
            return True
        return momento is not None and momento < fin

    def _cuando_termino(self, transcrito: Transcript) -> datetime | None:
        """Cuando termino de decirse esto, por su ultima palabra; `None` si no lo trae."""
        if not transcrito.words or self._flujo_empezo_a is None:
            return None
        return self._flujo_empezo_a + timedelta(seconds=max(p.end_s for p in transcrito.words))

    def _sin_la_voz_de_la_agente(self, oido: ListenEvent) -> ListenEvent | None:
        """Lo que el reconocedor oyo, sin lo que es la agente sonando por el altavoz.

        **Es el unico sitio por donde entra lo oido**, y por eso el eco se quita aqui y no
        en cada sitio que decide algo con un transcrito: ni interrumpe a la agente, ni abre
        un turno, ni se pinta como dicho por la persona. Lo dicho mientras suena la apertura
        tampoco entra (2026-10-14). Nulo si no queda nada.
        """
        ahora = self.now()
        if isinstance(oido, SpeechStarted):
            momento = (
                ahora
                if self._flujo_empezo_a is None
                else self._flujo_empezo_a + timedelta(seconds=oido.at_s)
            )
            if self._durante_la_apertura(None if self._flujo_empezo_a is None else momento):
                return None
            # Una senal de voz no dice de quien es: mientras la agente suena, es ella.
            return None if self._propia_voz.sounding(momento) else oido
        if self._durante_la_apertura(self._cuando_termino(oido)):
            if oido.is_final:
                observability.emit(
                    "voice.heard_during_opening_discarded",
                    tenant_id=self.engine.call.tenant_id,
                    call_id=self.engine.call.call_id,
                    words=len(str(oido.text).split()),
                )
            return None
        limpio = self._propia_voz.strip(
            oido, heard_at=ahora, stream_started_at=self._flujo_empezo_a
        )
        if limpio is not oido:
            observability.emit(
                "voice.own_voice_discarded",
                tenant_id=self.engine.call.tenant_id,
                call_id=self.engine.call.call_id,
                words=len(str(oido.text).split()),
                kept=0 if limpio is None else len(str(limpio.text).split()),
                final=oido.is_final,
            )
        return limpio

    # --- Hablar ---------------------------------------------------------------

    def _interrupcion(self) -> Transcript | None:
        """Lo que llego mientras la agente hablaba, si cuenta como interrupcion.

        Lo que no cuenta se **descarta**: es ruido de carro o el eco del propio
        altavoz, y eso es exactamente lo que el piso de palabras y de confianza
        existe para filtrar (BR4.2). Devolverlo a la cola lo convertiria en un
        turno de la persona que la persona nunca dijo.
        """
        while True:
            try:
                transcrito = self._oido.get_nowait()
            except asyncio.QueueEmpty:
                return None
            if transcrito is None:
                self._cerrado = True
                return None
            if isinstance(transcrito, _Despierta):
                # Lo que el fondo trajo sigue en `_por_decir`; se dice al terminar.
                continue
            if isinstance(transcrito, SpeechStarted):
                # **Nunca interrumpe.** El microfono recoge la voz de la agente por el
                # altavoz y el reconocedor la oye como cualquier otra: una senal de voz no
                # dice de quien es. La interrupcion se decide por palabras.
                continue
            if self._interrumpe(transcrito):
                return transcrito

    def _interrumpe(self, transcrito: Transcript) -> bool:
        """Si esto callaria a la agente: palabras de sobra, y no un saludo sobre la apertura."""
        if self.engine.greeting_over_opening(transcrito, now=self.now()):
            return False
        return self.engine.interrupted_by(transcrito)

    @property
    def _boca(self) -> CallSpeech:
        """Por donde sale cada frase: la sesion de la llamada, o la voz suelta si no hay."""
        return self._habla if self._habla is not None else self.speech

    async def _decir(
        self,
        frase: Utterance,
        *,
        speech_end_at: datetime | None = None,
        last_word_at: datetime | None = None,
        after_filler: bool = False,
        interrumpible: bool = True,
    ) -> bool:
        """Sintetiza y emite una frase. Devuelve si la interrumpieron (BR4.1).

        El texto ya viene `Redacted` del motor: el puerto de sintesis no acepta
        otra cosa, y esa es la mitad de BR3.8 que el comprobador de tipos sostiene.

        **A la consola va otra cosa: lo que la persona ve de su propia llamada va sin
        tapar** (2026-10-13, lo pidio cuatro veces), igual que `_mostrar` con lo que ella
        dijo. Lo decide `CallEngine.on_screen`: el texto sin tapar cuando se tiene y,
        cuando no --viene de la base ya con etiquetas--, el que suena, nunca una etiqueta.
        Lo que se **guarda** y lo que va a eventos y trazas sigue tapado.
        """
        await self.channel.send(State("speaking"))
        self._escucha_pendiente = False
        for linea in self.engine.on_screen(frase):
            await self.channel.send(WireTranscript(speaker="agent", text=linea, final=True))
        turno = f"{self.engine.call.call_id}-t{self._turnos}"
        # Lo que suena no es lo que se ve: los codigos se dicen como se dictan. La
        # pantalla y la transcripcion siguen con `frase.text`.
        sonara = self.engine.spoken(frase)
        # Empieza a sonar cuando termine lo anterior, si todavia suena: el
        # navegador encola, no mezcla.
        empieza = self.silent_since()
        # Lo que va a sonar queda anotado antes de mandar el primer trozo: el eco de la
        # primera palabra puede volver antes de que termine el envio.
        sonando = self._propia_voz.begin(str(sonara), starts_at=empieza)
        try:
            return await self._enviar(
                sonara,
                turno=turno,
                empieza=empieza,
                speech_end_at=speech_end_at,
                last_word_at=last_word_at,
                after_filler=after_filler,
                interrumpible=interrumpible,
            )
        finally:
            if sonando.ends_at is None:
                sonando.ends_at = self._sonando_hasta or self.now()

    async def _enviar(  # noqa: PLR0913 -- lo que `_decir` ya resolvio, por nombre
        self,
        sonara: Redacted,
        *,
        turno: str,
        empieza: datetime,
        speech_end_at: datetime | None,
        last_word_at: datetime | None,
        after_filler: bool,
        interrumpible: bool,
    ) -> bool:
        """Manda la frase trozo a trozo. Devuelve si la interrumpieron.

        El flujo de la frase se cierra aqui al dejar de leerla, y **la frase de cortesia de una
        interrupcion se dice despues de cerrarlo**: con la conexion de la llamada abierta, la
        frase nueva espera a que la anterior suelte el canal, y pedirla con la interrumpida
        todavia abierta la dejaria esperando para siempre.
        """
        primero = True
        enviados = 0
        cede: Utterance | None = None
        interrumpida = False
        async with _cerrando(
            self._boca.speak(
                self.engine.call.tenant_id,
                sonara,
                mode=self.engine.call.voice_mode,
                language=self.engine.language,
            )
        ) as audio:
            async for trozo in audio:
                if interrumpible:
                    interruptor = self._interrupcion()
                    if interruptor is not None:
                        # El servidor no puede retirar el audio que ya mando: quien
                        # vacia la cola de reproduccion es el navegador (BR4.3), y
                        # por eso NFR2 se mide alli y no aqui.
                        await self.channel.send(StopAudio())
                        ahora = self.now()
                        # El navegador vacia su cola: deja de sonar ya.
                        self._sonando_hasta = ahora
                        self._propia_voz.cut(ahora)
                        cede = self.engine.on_barge_in(
                            interruptor, detected_at=ahora, stopped_at=self.now(), turn_id=turno
                        )
                        self._interrumpio = interruptor
                        # **Lo que interrumpe tambien se pinta.** Sin esta linea, la
                        # frase con la que alguien corta a la agente se usa para
                        # callarla y despues no aparece en la consola: la persona ve
                        # su propia correccion desaparecer justo cuando la dijo. Lo
                        # que se descarta es el ruido que no interrumpe, no esto.
                        await self._mostrar(interruptor)
                        interrumpida = True
                        break
                if primero and speech_end_at is not None:
                    # El extremo derecho de NFR1: el primer byte sintetizado del
                    # turno (BR8.1). Solo el de un turno, porque la apertura no
                    # responde a nada que la persona haya dicho.
                    tardo = first_audio(
                        tenant_id=self.engine.call.tenant_id,
                        call_id=self.engine.call.call_id,
                        turn_id=turno,
                        speech_end_at=speech_end_at,
                        at=self.now(),
                        last_audible_word_at=last_word_at,
                        filler_said=after_filler,
                    )
                    # Y a la consola, **las mismas cifras** que acaban de quedar en la
                    # traza (BR3.3): no se vuelven a medir aqui.
                    await self.channel.send(
                        Latency(
                            turn_id=turno,
                            elapsed_ms=tardo.elapsed_ms,
                            from_last_word_ms=tardo.from_last_word_ms,
                        )
                    )
                primero = False
                await self.channel.send_audio(trozo)
                enviados += len(trozo)
                self._sonando_hasta = empieza + timedelta(
                    seconds=enviados / SPEECH_AUDIO.bytes_per_second
                )
        if interrumpida and cede is not None:
            await self._decir(cede, interrumpible=False)
        return interrumpida

    @property
    def playback_ends_at(self) -> datetime | None:
        """Cuando termina de sonar lo ultimo que dijo la agente, estimado por los bytes."""
        return self._sonando_hasta

    def silent_since(self) -> datetime:
        """Desde cuando la agente esta callada **para la persona**.

        Ahora mismo si ya no suena nada; si no, cuando termine de sonar. Es el
        instante desde el que cuentan la tolerancia de silencio (BR5.1) y el
        estado "escuchando": contarlos desde el fin del envio hacia que la agente
        se interrumpiera a si misma.
        """
        ahora = self.now()
        if self._sonando_hasta is None or self._sonando_hasta <= ahora:
            return ahora
        return self._sonando_hasta

    async def _anunciar_escucha(self) -> None:
        """ "Escuchando", en cuanto deje de sonar la agente; mientras tanto, pendiente."""
        if self._sonando_hasta is None or self._sonando_hasta <= self.now():
            self._escucha_pendiente = False
            await self.channel.send(State("listening"))
            return
        self._escucha_pendiente = True

    async def _mostrar(self, transcrito: Transcript) -> None:
        """Lo que la persona dijo, en su propia pantalla y **tal como lo dijo**.

        Decision de Miguel del 2026-10-09, que cambia BR7.2: antes salia redactado
        ("mi nombre completo es [NOMBRE 1]") y la persona veia tapadas sus propias
        palabras mientras hablaba. Va solo a la consola de quien habla, por su
        socket. Lo que se **guarda** sigue redactado antes de persistir: la
        transcripcion del caso la escribe `transcript_writer`, no esta funcion.
        """
        await self.channel.send(
            WireTranscript(speaker="insured", text=str(transcrito.text), final=transcrito.is_final)
        )

    # --- Los relojes ----------------------------------------------------------

    @property
    def _fin_de_llamada(self) -> datetime:
        return self.engine.call.started_at + self.max_call

    @property
    def _momento_del_aviso(self) -> datetime:
        return self._fin_de_llamada - self.warn_at

    @property
    def _hora_de_despedirse(self) -> datetime:
        """Cuando empieza el cierre por tiempo, para que quepa antes del limite."""
        return self._fin_de_llamada - min(FAREWELL_BUDGET, self.warn_at / 2)

    async def _esperar(self, limite: datetime) -> ListenEvent | _Despierta | None:
        """El siguiente transcrito, o nada si el plazo vencio antes.

        `None` significa las dos cosas --venció el plazo, o el flujo se acabo-- y
        quien llama las distingue mirando `_colgo` y `_cerrado`. Son desenlaces
        distintos y en ningun sitio se colapsan.
        """
        restante = (limite - self.now()).total_seconds()
        if restante <= 0:
            return None
        try:
            async with asyncio.timeout(restante):
                return await self._oido.get()
        except TimeoutError:
            return None

    # --- La conversacion ------------------------------------------------------

    async def run(self) -> EndReason:
        """La llamada entera. Devuelve con que motivo termino (BR1.6)."""
        recibir = asyncio.create_task(self._recibir())
        escuchar = asyncio.create_task(self._escuchar())
        self._escuchar_al_fondo()
        try:
            async with self._con_la_boca_abierta():
                motivo = await self._conversar()
            await self._dejar_sonar(motivo)
            return motivo
        except Exception as error:  # noqa: BLE001 -- cualquier fallo termina la llamada con su motivo; una lista de tipos dejaria escapar el siguiente y con el un socket colgado
            observability.emit(
                "voice.call_failed",
                tenant_id=self.engine.call.tenant_id,
                call_id=self.engine.call.call_id,
                error_type=type(error).__name__,
                # Donde fallo, nunca con que: el mensaje del error puede llevar lo que dijo la
                # persona. Sin esto una llamada caida solo decia su tipo (2026-10-12).
                where=observability.failure_location(error),
            )
            if self.on_failure is not None:
                self.on_failure(error)
            return EndReason.ERROR
        finally:
            self._dejar_de_escuchar_al_fondo()
            for tarea in (recibir, escuchar):
                tarea.cancel()
            await asyncio.gather(recibir, escuchar, return_exceptions=True)
            # Tambien si la llamada falla: una lectura adelantada no se queda colgando.
            await self.engine.close_advanced()

    @contextlib.asynccontextmanager
    async def _con_la_boca_abierta(self) -> AsyncIterator[None]:
        """Abre la boca de la llamada antes de la apertura y la cierra al terminar, como sea.

        Con una voz que ofrece sesion (`SessionVoice`) las frases salen por una sola conexion
        con el proveedor; con cualquier otra, por la voz suelta, frase por frase.

        **Se abre y se cierra en la tarea de la llamada**, la de `run`, y nunca en otra: una
        conexion abierta en una tarea y cerrada en otra, igual que una variable de contexto,
        es de las cosas que se rompen solo con el servidor de verdad. Lo que va a una tarea
        aparte, como la muletilla, habla por ella pero no la abre ni la cierra.
        """
        if not isinstance(self.speech, SessionVoice):
            yield
            return
        llamada = self.engine.call
        async with self.speech.speech_session(
            llamada.tenant_id, mode=llamada.voice_mode, language=self.engine.language
        ) as habla:
            self._habla = habla
            try:
                yield
            finally:
                self._habla = None

    async def _dejar_sonar(self, motivo: EndReason) -> None:
        """Espera a que termine de **sonar** lo ultimo que dijo la agente.

        Enviar el audio no es que se haya oido: la sintesis va mas rapido que la
        voz, y la despedida de un reporte completo --con el numero de caso, lo
        unico que la persona se lleva-- tarda unos once segundos en sonar. Sin esta
        espera el servidor daba la llamada por terminada 0,15 s despues de mandarla,
        la pagina cerraba el audio y el numero se cortaba (2026-10-09).

        No se espera si la persona colgo o la conexion se cayo: no hay a quien
        hacerle oir nada. Tiene tope, y se suelta en cuanto pasa cualquiera de las
        dos cosas.
        """
        if motivo in (EndReason.HANGUP, EndReason.DROPPED, EndReason.ERROR):
            return
        termina = self._sonando_hasta
        if termina is None:
            return
        falta = (termina - self.now()).total_seconds() + FINAL_PLAYBACK_GRACE_S
        espera = min(falta, FINAL_PLAYBACK_MAX_S)
        paso = 0.05
        while espera > 0 and not self._colgo and not self._cerrado:
            await asyncio.sleep(min(paso, espera))
            espera -= paso

    async def _conversar(self) -> EndReason:
        motivo = await self._abrir()
        if motivo is not None:
            return motivo
        return await self._turnos_hasta_el_final()

    async def _abrir(self) -> EndReason | None:
        """La apertura y, si la hay, la oferta de retomar (BR2.1 a BR2.4, BR6.2).

        **La apertura no se interrumpe y mientras suena no se escucha** (decision de Miguel,
        2026-10-14). Antes se podia cortar y se repetia entera hasta oirse completa (media
        divulgacion no es divulgacion, BR4.5): quien hablaba al conectar la oia tres veces. Ahora
        suena entera una sola vez, lo que la persona diga encima se descarta
        (`_sin_la_voz_de_la_agente`) y la conversacion empieza cuando la agente termina.
        """
        if self.engine.needs_opening_again:
            if self._colgo:
                return EndReason.HANGUP
            if self._cerrado:
                return EndReason.DROPPED
            if self.now() >= self._hora_de_despedirse:
                return await self._despedirse_por_tiempo()
            await self._decir(self.engine.opening(), interrumpible=False)
            # Con la hora en que **termina de sonar**, que es cuando esta dicha
            # (BR2.3), no la del fin del envio.
            await self.engine.opening_finished(at=self.silent_since())

        oferta = self.engine.offer_resume()
        if oferta is not None:
            await self._decir(oferta)
            self._oferta_abierta = True
        return None

    async def _turnos_hasta_el_final(self) -> EndReason:
        """El ciclo: escuchar, detectar el fin del habla, hablar, volver a escuchar.

        `callo_a` es desde cuando la agente esta callada **para la persona**: el
        fin estimado de la reproduccion, no el del envio (ver `_sonando_hasta`).
        Mientras la frase siga sonando no vence ningun silencio: la agente no
        puede callar antes de terminar de hablar.
        """
        callo_a = self.silent_since()
        detector = self._escuchando(callo_a)
        await self._anunciar_escucha()

        while True:
            if self._colgo:
                return EndReason.HANGUP
            if self._cerrado and self._oido.empty():
                return EndReason.DROPPED

            transcrito = await self._esperar(self._limite_de_espera(detector, callo_a))
            if isinstance(transcrito, Transcript):
                await self._oir(transcrito, detector)
                continue
            if isinstance(transcrito, SpeechStarted):
                # Con la agente callada y un turno abierto, quiza la persona retomo la frase:
                # el plazo se mueve ya y no cuando llegue el parcial, pero solo un rato corto
                # (puede ser un ruido). La lectura adelantada no se toca: se suelta cuando
                # llegan palabras, que es cuando se sabe que la persona sigue.
                detector.speech_started(self.now())
                continue

            ahora = self.now()
            if ahora >= self._hora_de_despedirse:
                return await self._despedirse_por_tiempo()
            if self._escucha_pendiente:
                await self._anunciar_escucha()
                continue

            hubo_intercambio, motivo = await self._al_vencer(detector, callo_a, ahora)
            if motivo is not None:
                return motivo
            if not hubo_intercambio:
                continue
            callo_a = self.silent_since()
            detector = self._escuchando(callo_a)
            await self._anunciar_escucha()

    async def _al_vencer(
        self, detector: TurnDetector, callo_a: datetime, ahora: datetime
    ) -> tuple[bool, EndReason | None]:
        """Lo que se hace al vencer la espera: atender, preguntar si sigue, o nada.

        Devuelve si hubo intercambio --un turno atendido, la respuesta que trajo el
        fondo o una frase de silencio dicha, tras lo cual se escucha de nuevo-- y el
        motivo de fin, si lo hay.
        """
        if await self._decir_lo_del_fondo(detector):
            return True, None
        toca = self._que_toca(detector, callo_a, ahora)
        if toca is _Toca.TURNO:
            try:
                return True, await self._atender(detector.close())
            finally:
                # Si el turno tomo un camino que no pasa por el modelo, la lectura que se
                # adelanto no se uso: se suelta y queda dicho. Si la recogio, ya no hay nada.
                self.engine.drop_advanced(Discard.NOT_NEEDED, turn_id=self._turno_actual())
        if await self._avisar(ahora, hablando=detector.speaking):
            # Dicho en voz alta, es un intercambio: se vuelve a escuchar desde ahi.
            return not detector.speaking, None
        if toca is _Toca.ESPERAR:
            return False, None
        if toca is _Toca.SIN_RESPUESTA:
            return True, await self._cuando_la_respuesta_tarda()
        return True, await self._callar(ahora)

    def _que_toca(self, detector: TurnDetector, callo_a: datetime, ahora: datetime) -> _Toca:
        """Que se hace cuando la espera vuelve sin transcrito (2026-10-07).

        **Un turno abierto nunca se lee como silencio.** La espera puede volver un
        instante antes del plazo que pidio --el reloj del bucle de eventos y el de
        la llamada no son el mismo-- y antes eso caia en la rama del silencio: la
        agente preguntaba «¿sigue ahi?» con la frase de la persona ya transcrita,
        y el detector nuevo la tiraba. Medido en una llamada real: finales a los
        17,3 y 17,8 s, plazo a los 18,5 s, «¿sigue ahi?» a los 18,4 s.
        """
        if detector.speaking:
            return _Toca.TURNO if detector.expired(ahora) else _Toca.ESPERAR
        if self._respuesta_hasta is not None:
            # La agente dijo "dejame revisar": quien calla es ella, y no se le
            # pregunta a la persona si sigue ahi.
            return _Toca.ESPERAR if ahora < self._respuesta_hasta else _Toca.SIN_RESPUESTA
        if ahora < self._vence_el_silencio(detector, callo_a):
            return _Toca.ESPERAR
        return _Toca.SILENCIO

    async def _cuando_la_respuesta_tarda(self) -> EndReason | None:
        """El plazo de la respuesta del fondo vencio: se dice que sigue revisando, una vez.

        Y se **sigue esperando** (`LATE_ANSWER_WAIT`): quien debe hablar sigue siendo la
        agente, asi que el silencio no cuenta contra la persona. Si ese segundo plazo
        tambien vence, deja de esperar y el silencio vuelve a contar desde ahora.
        """
        self._respuesta_hasta = None
        if self._demora_dicha:
            self._demora_dicha = False
            return None
        self._demora_dicha = True
        await self._decir(self.engine.answer_delayed())
        self._respuesta_hasta = self.silent_since() + LATE_ANSWER_WAIT
        return None

    def _vence_el_silencio(self, detector: TurnDetector, callo_a: datetime) -> datetime:
        """Cuando vence la tolerancia de silencio, contada desde lo ultimo oido."""
        # El silencio cuenta desde lo ultimo que se oyo, parcial incluido: quien
        # esta a mitad de frase sin un final todavia no esta callado (2026-10-07).
        oido = detector.last_heard_at
        callado_desde = max(callo_a, oido) if oido is not None else callo_a
        return self.engine.silence_deadline(since=callado_desde)

    async def _avisar(self, ahora: datetime, *, hablando: bool) -> bool:
        """El aviso de que queda poco, una sola vez: en pantalla y **dicho**.

        Devuelve si lo mando. Antes solo salia en la pantalla, y quien habla por
        telefono no la esta mirando (2026-10-11). Si la persona esta a mitad de una
        frase no se le habla encima: queda por decir, delante de la respuesta a su
        turno.
        """
        if self._aviso_dado or ahora < self._momento_del_aviso:
            return False
        self._aviso_dado = True
        await self.channel.send(Notice(TIME_RUNNING_OUT))
        if hablando:
            self._aviso_por_decir = True
        else:
            await self._decir(self.engine.time_warning())
        return True

    async def _despedirse_por_tiempo(self) -> EndReason:
        """Se acabo el tiempo: se dice, con el numero de caso, y la llamada termina."""
        await self._decir(await self.engine.time_is_up(), interrumpible=False)
        return EndReason.MAX_DURATION

    async def _callar(self, ahora: datetime) -> EndReason | None:
        """El peldano de silencio que toca. El tercero termina la llamada (BR5.2)."""
        del ahora  # quien lleva la cuenta es el motor, no el reloj de aqui
        frase = self.engine.on_silence()
        if frase is None:
            return EndReason.SILENCE
        await self._decir(frase)
        return frase.end_reason

    def _escuchando(self, desde: datetime) -> TurnDetector:
        """Abre el detector del turno, con lo que ya haya dicho quien interrumpio.

        Sin esta linea, la frase con la que alguien corta a la agente se pierde:
        se usa para decidir que hay interrupcion y despues no la oye nadie, que
        es la forma mas segura de que la persona tenga que repetirla.
        """
        detector = self.engine.listening(since=desde, stream_started_at=self._flujo_empezo_a)
        if self._interrumpio is not None:
            detector.observe(self._interrumpio, at=desde)
            self._interrumpio = None
        return detector

    def _limite_de_espera(self, detector: TurnDetector, callo_a: datetime) -> datetime:
        """El proximo reloj que vence, contando tambien el fin de la reproduccion
        cuando "escuchando" esta por anunciar. Con algo del fondo por decir y la
        persona callada, no se espera nada: se dice ya."""
        if self._por_decir and not detector.speaking:
            return self.now()
        limite = self._proximo_limite(detector, callo_a)
        if self._escucha_pendiente and self._sonando_hasta is not None:
            return min(limite, self._sonando_hasta)
        return limite

    async def _oir(self, transcrito: Transcript, detector: TurnDetector) -> None:
        """Un transcrito de la persona mientras la agente esta callada o terminando.

        Si llega mientras la cola de la frase **sigue sonando** --ya enviada
        entera, todavia en el altavoz-- y cuenta como interrupcion, se corta igual
        que una interrupcion (BR4.3), y desde ahi la agente esta callada.
        """
        ahora = self.now()
        if self.engine.greeting_over_opening(transcrito, now=ahora):
            # "¿Alo?" encima de la apertura (2026-10-11): ni la corta ni es un turno. Se
            # descarta como el ruido que no interrumpe; la apertura sigue sonando y
            # termina de registrarse con su hora.
            return
        # La apertura tampoco se corta por este camino, ya enviada y sonando (2026-10-14).
        if (
            self._escucha_pendiente
            and not self.engine.opening_is_sounding(now=ahora)
            and self.engine.interrupted_by(transcrito)
        ):
            await self.channel.send(StopAudio())
            self._sonando_hasta = ahora
            self._propia_voz.cut(ahora)
            await self._anunciar_escucha()
        detector.observe(transcrito, at=ahora)
        self._seguir_la_lectura_adelantada(detector)
        await self._mostrar(transcrito)

    def _seguir_la_lectura_adelantada(self, detector: TurnDetector) -> None:
        """Adelanta la lectura del modelo, o la suelta, segun lo ultimo que se oyo (2026-10-13).

        Con un final nuevo que cerraria bien el turno, la lectura sale **ya**, sin esperar la
        tolerancia: cuando venza, el turno recoge lo que haya avanzado. Si la persona retomo la
        palabra --un parcial con palabras-- lo que se leyo ya no es todo lo que va a decir y se
        suelta; cuando llegue su final, se lee de nuevo con el texto completo. **La senal de voz
        sola no la suelta** (por eso el ciclo no llama aqui al recibirla): puede ser un ruido, y
        cada lectura soltada es un llamado al modelo pagado para nada. Si de verdad era la
        persona, su parcial llega en menos de `SIGNAL_GRACE` y la suelta entonces.
        """
        if detector.resumed:
            self.engine.drop_advanced(Discard.KEPT_TALKING)
            return
        fin = detector.pending_end()
        if fin is None:
            return
        if self._oferta_abierta or detector.ending not in ADVANCED_ENDINGS:
            self.engine.drop_advanced(Discard.KEPT_TALKING)
            return
        self.engine.advance_understanding(fin)

    def _proximo_limite(self, detector: TurnDetector, callo_a: datetime) -> datetime:
        """El primero de los tres relojes que vence: turno, aviso y duracion.

        Se espera hasta el mas cercano y no hasta el que toca, porque los tres
        corren a la vez: dormir hasta el fin del habla se comeria el aviso de
        tiempo, y esperar el silencio se comeria el final de la llamada.
        """
        plazo = detector.deadline
        if plazo is None:
            plazo = self._respuesta_hasta or self._vence_el_silencio(detector, callo_a)
        candidatos = [plazo, self._hora_de_despedirse]
        if not self._aviso_dado:
            candidatos.append(self._momento_del_aviso)
        return min(candidatos)

    async def _atender(self, fin: SpeechEnd) -> EndReason | None:
        """Lo que se hace con un turno cerrado de la persona.

        Dos caminos: o es la respuesta a la oferta de retomar, o es una frase para
        el grafo. Una oferta contestada deja de estar abierta antes de que nada llegue
        a `handle_turn`; la unica respuesta que sigue al grafo es la que cuenta algo del
        caso, y entonces ya no hay oferta que contestar.
        """
        self._turnos += 1
        if fin.unconfirmed_signals:
            speech_signal_discarded(
                tenant_id=self.engine.call.tenant_id,
                call_id=self.engine.call.call_id,
                turn_id=self._turno_actual(),
                signals=fin.unconfirmed_signals,
                held_ms=int(fin.held_by_signals.total_seconds() * 1000),
            )
        cerrado_a = self.now()
        self._voces_al_cerrar_el_turno = self._voces_oidas
        self._tras_muletilla = False
        # "Un momento" y "in English, please" se contestan aparte: no son el "no" a la
        # oferta de retomar ni lo primero que dice a que llama la persona.
        aparte = self.engine.is_side_request(fin)
        if self._oferta_abierta and not aparte and await self._resolver_oferta(fin):
            return None

        if not aparte and self.engine.first_turn_purpose(fin) is CallPurpose.POLICY_QUESTION:
            # Llama por una duda de su poliza: la llamada nacio con un reporte y
            # ahora abre una consulta, que es lo que el grafo sabe responder.
            await self._abrir_otro_caso(intent=ReportIntent.COVERAGE_INQUIRY)

        avisado = await self._avisar_antes_de_responder()

        interrumpida = False
        primera = True
        # `aclosing`: si el turno termina antes de agotar las frases (la despedida es la
        # ultima que se dice), el generador se cierra aqui, en esta tarea. Dejarlo al
        # recolector lo cierra en otra, y el rastro del turno no se repone fuera de la
        # tarea donde se abrio.
        async with contextlib.aclosing(
            self._frases_del_turno(fin, cerrado_a=cerrado_a, avisado=avisado)
        ) as frases:
            async for frase in frases:
                if interrumpida:
                    # La persona corto a la agente: lo que quedaba por decir de este
                    # turno no se le dice encima (2026-10-11). Si lo que quedaba era el
                    # cierre de un reporte completo, se aplaza a despues de oirla; una
                    # derivacion ya ocurrio y su despedida si se dice.
                    if frase.end_reason is EndReason.COMPLETED:
                        self.engine.postpone_closing()
                        continue
                    if frase.end_reason is None:
                        continue
                # Una despedida se dice entera: lleva el numero de caso, y cortarla a la
                # mitad deja a la persona sin lo unico que se lleva de la llamada.
                # La marca de latencia es la del **primer** audio del turno (BR8.1): las
                # frases que siguen no son la espera de la persona.
                interrumpida = await self._decir(
                    frase,
                    speech_end_at=fin.at if primera else None,
                    last_word_at=fin.last_audible_word_at,
                    after_filler=self._tras_muletilla,
                    interrumpible=frase.end_reason is None,
                )
                primera = False
                if frase.end_reason is not None:
                    return frase.end_reason
        if self.engine.take_awaited_answer():
            self._respuesta_hasta = self.silent_since() + ANSWER_WAIT
            self._demora_dicha = False
        return None

    async def _avisar_antes_de_responder(self) -> bool:
        """El aviso de tiempo que quedo por decir, delante de la respuesta al turno.

        Devuelve si lo dijo: tras un aviso hablado no tiene sentido una muletilla.
        """
        if not self._aviso_por_decir and (self._aviso_dado or self.now() < self._momento_del_aviso):
            return False
        if not self._aviso_dado:
            self._aviso_dado = True
            await self.channel.send(Notice(TIME_RUNNING_OUT))
        self._aviso_por_decir = False
        await self._decir(self.engine.time_warning(), interrumpible=False)
        return True

    def _puede_la_muletilla(self, *, avisado: bool) -> bool:
        """Si todavia cabe una muletilla: con la llamada abierta, sin cerrar, con tiempo y
        con la persona callada.

        Si el reconocedor oyo empezar a hablar a alguien despues de cerrado el turno, la
        persona retomo la palabra y un "Listo..." encima la tapa. No deshace el turno que
        ya se cerro --la respuesta sigue su camino y la interrumpen las palabras, como
        siempre--; solo se ahorra la muletilla. No mira si esta encendida (`filler_after`):
        eso lo decide quien la pide.
        """
        return (
            not avisado
            and not self.engine.closed
            and not self._colgo
            and not self._cerrado
            and self._voces_oidas == self._voces_al_cerrar_el_turno
            and self.now() < self._hora_de_despedirse
        )

    async def _frases_del_turno(
        self, fin: SpeechEnd, *, cerrado_a: datetime, avisado: bool
    ) -> AsyncGenerator[Utterance]:
        """Lo que la agente dice de este turno, con una muletilla si la primera frase tarda.

        **El generador del motor se consume y se cierra aqui, en la tarea de la llamada, y
        nunca en otra.** El turno de verdad abre su rastro con variables de contexto al
        entrar y las repone al salir, y una variable de contexto solo se repone en la tarea
        donde se puso: pedir la primera frase desde una tarea aparte y seguir desde esta
        tiraba la llamada con `ValueError: ... was created in a different Context`
        (2026-10-12). Lo que va a una tarea aparte es la muletilla, que espera y habla.

        Si la primera frase llega antes de `filler_after`, la muletilla no empieza nunca. Si
        la muletilla ya esta sonando, se espera a que termine antes de decir la respuesta.
        Lo que sigue a la primera frase sale tal cual.
        """
        frases = self.engine.speak_turn(fin, turn_id=self._turno_actual())
        muletilla = self._armar_la_muletilla(fin, cerrado_a=cerrado_a, avisado=avisado)
        try:
            primera = await anext(frases, None)
            if muletilla is not None:
                pendiente, muletilla = muletilla, None
                await self._terminar_la_muletilla(pendiente)
            if primera is None:
                return
            yield primera
            async for resto in frases:
                yield resto
        finally:
            if muletilla is not None:
                # El turno fallo o la cancelaron antes de la primera frase.
                muletilla.tarea.cancel()
                await asyncio.wait({muletilla.tarea})
                if not muletilla.tarea.cancelled():
                    muletilla.tarea.exception()
            await frases.aclose()

    def _armar_la_muletilla(
        self, fin: SpeechEnd, *, cerrado_a: datetime, avisado: bool
    ) -> _Muletilla | None:
        """Echa a andar la muletilla del turno, si esta encendida y todavia cabe una."""
        if self.filler_after is None or not self._puede_la_muletilla(avisado=avisado):
            return None
        espera = max(0.0, (cerrado_a + self.filler_after - self.now()).total_seconds())
        empezo = asyncio.Event()
        tarea = asyncio.create_task(
            self._muletilla_si_tarda(fin, espera=espera, avisado=avisado, empezo=empezo)
        )
        return _Muletilla(tarea=tarea, empezo=empezo)

    async def _muletilla_si_tarda(
        self, fin: SpeechEnd, *, espera: float, avisado: bool, empezo: asyncio.Event
    ) -> None:
        """Espera `espera` segundos y, si la llamada sigue abierta, dice la muletilla.

        Se cancela mientras duerme y nunca mientras habla: entre despertar y marcar
        `empezo` no hay ninguna espera, asi que quien la mira desde fuera sabe si hay que
        cancelarla o dejarla terminar.
        """
        await asyncio.sleep(espera)
        if not self._puede_la_muletilla(avisado=avisado):
            return
        empezo.set()
        await self._decir_la_muletilla(fin)

    async def _terminar_la_muletilla(self, muletilla: _Muletilla) -> None:
        """La primera frase llego: la muletilla que no empezo no empieza, y la que suena
        termina antes de que se diga la respuesta. Un fallo suyo no se pierde."""
        if not muletilla.empezo.is_set():
            muletilla.tarea.cancel()
        await asyncio.wait({muletilla.tarea})
        if not muletilla.tarea.cancelled():
            muletilla.tarea.result()

    async def _decir_la_muletilla(self, fin: SpeechEnd) -> None:
        """Dice la muletilla del turno. No es interrumpible: dura medio segundo.

        No es un turno ni cuenta como interrupcion; lo que la persona diga mientras tanto
        lo recoge el detector como siempre. Deja su evento --turno y milisegundos, sin
        texto-- y marca que la respuesta que sigue viene detras de una.
        """
        filler_said(
            tenant_id=self.engine.call.tenant_id,
            call_id=self.engine.call.call_id,
            turn_id=self._turno_actual(),
            speech_end_at=fin.at,
            at=self.now(),
        )
        self._tras_muletilla = True
        await self._decir(self.engine.filler_phrase(), interrumpible=False)

    def _turno_actual(self) -> str:
        return f"{self.engine.call.call_id}-t{self._turnos}"

    async def _resolver_oferta(self, fin: SpeechEnd) -> bool:
        """La respuesta a "¿seguimos con su caso?" (BR6.4). Devuelve si quedo contestada aqui.

        Tres respuestas, y la llamada nunca se queda callada despues de ninguna:

        - **Un si a secas**: se sigue con el caso y la agente retoma la pregunta que habia
          quedado pendiente, una vez.
        - **Un no, o pedir uno nuevo**: no es rechazar la llamada sino que llama por otro
          accidente. Se abre un caso nuevo, **el anterior queda intacto**, y la
          divulgacion que ya se dijo en esta llamada se registra tambien contra el nuevo.
          Sin eso, el caso con el que la llamada termina no tendria divulgacion registrada
          y BR2.1 quedaria rota por la puerta de atras. Y se pregunta en que se la ayuda.
        - **Cualquier otra cosa con contenido** --cuenta algo del choque--: se sigue con el
          caso y eso es ya su turno, que sigue su camino como cualquier otro (devuelve
          `False`).

        Lo que no se entendio no es un "no": la oferta sigue abierta y el turno lo atiende
        la escalera de reintentos.
        """
        if not self.engine.heard(fin):
            return False
        self._oferta_abierta = False
        respuesta = self.engine.resume_reply(fin)
        if respuesta is not resume.Reply.WITH_CONTENT:
            # Antes de cambiar de caso: lo que dijo es del caso en el que lo dijo.
            self.engine.note_person_turn(fin)
        seguir = self.engine.resume_accepted(fin.text, at=fin.at)
        if not seguir:
            await self._abrir_otro_caso()
            await self._decir(self.engine.new_case_followup())
            return True
        if respuesta is resume.Reply.WITH_CONTENT:
            return False
        await self._decir(self.engine.resume_followup())
        return True

    async def _abrir_otro_caso(self, *, intent: ReportIntent = ReportIntent.CLAIM) -> None:
        """La llamada sigue con un caso nuevo, y el anterior queda intacto.

        Dos motivos: la persona llama por otro accidente (BR6.4), o lo primero que
        dijo es una duda de su poliza y el caso con que nacio la llamada era un
        reporte. La divulgacion ya dicha se registra tambien contra el nuevo.
        """
        llamada = self.engine.call
        nuevo = await open_for_call(
            llamada.tenant_id, language=self.engine.language, now=self.now(), intent=intent
        )
        self.engine.call = await switch_case(llamada, case_id=nuevo)
        spend_attribution.switch_case(nuevo)
        self._escuchar_al_fondo()
        dicho = self.engine.disclosed_at
        if dicho is not None:
            await self.engine.opening_finished(at=dicho)
        await self._anunciar_caso(nuevo)

    async def _anunciar_caso(self, case_id: str) -> None:
        """El cuadro `case`: la consola necesita el numero para mostrarlo."""
        vista = await casos.get_case(self.engine.call.tenant_id, case_id)
        if vista is None:
            return
        await self.channel.send(Case(case_id=case_id, case_number=str(vista.case_number)))


__all__ = ["CallChannel", "CallRunner", "CallSpeech", "CallVoice", "SessionVoice"]
