"""Cuando la persona termino de hablar (BR3.1, PA-6).

**La definicion es de esta unidad** y no del proveedor. El puerto `SpeechToText`
de C-16 entrega `Transcript` con `is_final` y nada mas: no publica el
`speech_final` de Deepgram. Ampliar el puerto para un dato de un solo proveedor
seria cambiar un contrato del que U15 es duena, asi que el fin del habla se
deriva aqui: **un transcrito final seguido de `end_of_speech` sin nada nuevo**.

**La marca de tiempo es la del ultimo final, no la del vencimiento.** El tiempo
de esperar el silencio es del detector y no de la respuesta; cargarselo a NFR1
mediria otra cosa --mediria cuanto se espera antes de decidir que alguien callo--
y haria que subir la tolerancia empeorara una meta que no empeoro.

**No hay reloj aqui dentro.** Este modulo dice *cuando* vence, y quien mira el
reloj es la llamada. Un temporizador propio obligaria a dormir para probarlo, y
ninguna prueba de esta unidad duerme.

`AC1.23.5` pide publicar tambien la variante "ultima palabra audible": sale de
`WordHypothesis.end_s` del ultimo final, y el detector la lleva al lado de la
suya para que el reporte del hito ponga las dos columnas con su nombre. No se
elige la mas favorable.

**Esos tiempos se cuentan desde el principio del flujo de audio de la LLAMADA, no
desde el principio del turno** (2026-10-12). Hay un solo `speech.listen` por llamada y
Deepgram numera cada palabra con los segundos de audio recibidos desde que abrio el
canal; el navegador manda audio sin parar, tambien mientras la agente habla, asi que
esos segundos son tiempo de pared desde que llego el primer trozo. Anclarlos al inicio
del turno --como se hacia-- los dejaba en el futuro en cuanto la llamada llevaba algo
mas que el instante de empezar. Si la conversion da un instante imposible, no se
publica: `None`, y no un numero inventado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from untangle.providers.ports import Transcript

#: Las tres esperas con que se cierra el turno, segun como termino lo ultimo que dijo la
#: persona (2026-10-12). Esperar no cuesta nada --mientras la persona calla no se gasta
#: modelo--, y cortar a quien hace una pausa a mitad de frase si cuesta: la agente
#: contesta a media frase y la persona tiene que repetirse. Por eso las dos de abajo son
#: largas a proposito.
#:
#: **Frase cerrada**: el reconocedor la termino con punto, interrogacion o exclamacion, o
#: es una respuesta corta ("no", "si claro", "ayer en la tarde"). Es la tolerancia de
#: partida, dato de la aseguradora que entra por argumento; 700 ms es lo bastante para no
#: cortar a quien piensa y lo bastante poco para no comerse el presupuesto de NFR1.
DEFAULT_END_OF_SPEECH = timedelta(milliseconds=700)

#: **Frase sin cierre**: mas de unas pocas palabras y el reconocedor no puso su punto. Lo
#: mas probable es que la persona todavia no termino ("el vehiculo que yo iba
#: conduciendo"), y se le da tiempo para seguir.
UNPUNCTUATED_END_OF_SPEECH = timedelta(milliseconds=1200)

#: **Frase a medias**: termina en una palabra que pide continuacion ("mi poliza es...",
#: "queria consultar sobre..."), con puntuacion o sin ella y tenga las palabras que tenga.
#: Con 700 ms el turno se cortaba ahi y el numero llegaba solo, como otro turno (2026-10-09),
#: y "Hola, queria consultar sobre" + una pausa de 1,3 s se contestaba a medias
#: (2026-10-12). La pausa de quien busca la palabra siguiente cabe en esto.
INCOMPLETE_END_OF_SPEECH = timedelta(milliseconds=2500)

#: **La senal de voz del reconocedor sin palabras es una pista, no una prueba** (2026-10-13).
#: `SpeechStarted` es deteccion de voz por energia: la dispara la persona retomando la frase,
#: pero tambien una tos, el teclado, un clic, la respiracion, musica o el eco de la sala. Con
#: el turno abierto, antes valia igual que un parcial con palabras y estiraba el plazo a la
#: espera mas larga contada desde la senal; en dos llamadas reales eso costo hasta 2,5 s por
#: ruido, y varios seguidos dejaron un turno sin cerrar (la persona espero y colgo).
#:
#: Ahora la senal sola mantiene el turno abierto **solo hasta `SIGNAL_GRACE` despues de ella**:
#: lo que tarda en llegar un parcial con palabras si de verdad se retomo. Si llega, cuenta
#: como retomar y vale la espera larga de siempre. Si no, la senal se olvida y el turno se
#: cierra con su plazo normal. El valor sale de lo que cuesta no esperarlo: un parcial tarda
#: hasta un segundo de audio en salir mas la latencia del reconocedor (0,9 s medido en la
#: llamada del 2026-10-12, «Hola, queria consultar sobre» + pausa + «si mi poliza me
#: cubre...»). Por debajo de 1 s la agente volveria a contestar encima de quien retoma, que
#: fue el defecto que la senal arreglo; 1,5 s deja medio segundo de margen sobre esa medida.
SIGNAL_GRACE = timedelta(milliseconds=1500)

#: Lo maximo que las senales sin palabras, **repetidas**, pueden alargar el turno por encima
#: de su plazo (el de su ultimo final, o el de su ultimo parcial con palabras). Sin tope, un
#: ruido cada segundo y medio lo dejaba abierto sin limite. Es `SIGNAL_GRACE` mas medio
#: segundo: si el ruido y la voz de verdad llegan separados --un suspiro, y la frase un
#: segundo despues--, la senal de la voz todavia alcanza a esperar su parcial. Un parcial con
#: palabras o un final **no tienen este tope**: ahi la persona de verdad sigue hablando.
#: Con las esperas de hoy el ruido deja el turno abierto, como mucho, 2,7 s tras un final
#: cerrado, 3,2 s tras uno sin punto y 4,5 s tras uno a medias.
SIGNAL_ONLY_EXTENSION = timedelta(milliseconds=2000)

#: Cuanto antes de la llegada del final puede caer su ultima palabra para que la hora
#: calculada se publique. Un final llega unas decimas despues de que la persona calla; si
#: la distancia es de segundos, el flujo de audio no iba en tiempo de pared (una pausa en
#: el envio, una cola atrasada) y el instante saldria falso. Por encima de esto, o con la
#: palabra despues de la llegada del final --imposible--, la variante se descarta.
MAX_WORD_TO_FINAL = timedelta(seconds=5)

#: Hasta cuantas palabras una respuesta sin punto final se toma por terminada:
#: "no", "si claro", "ayer en la tarde". Por encima, una frase que el reconocedor
#: no cerro con su punto es una frase que la persona todavia no termino. **No se aplica a
#: una frase que termina en una palabra de `_A_MEDIAS`**: esa nunca es una respuesta corta.
SHORT_ANSWER_WORDS = 4

#: Con que termina una frase acabada, segun la puntuacion que pone el reconocedor.
_FIN_DE_FRASE = ".?!…"

#: Lo que se quita de los bordes de la ultima palabra para compararla: puntuacion y comillas.
_BORDES = " .,;:!?…¿¡\"'“”«»()[]-—"

#: Las palabras con que no termina una frase acabada, en los dos idiomas: preposiciones,
#: articulos, conjunciones, posesivos y verbos que piden lo que sigue. Se comparan en
#: minuscula y **tal cual**, sin plegar tildes: "si" (condicional) pide continuacion y
#: "si" con tilde es una respuesta completa, igual que "no". "como" y "cuando" sin tilde
#: son conjunciones; con tilde son preguntas, que se contestan solas.
_A_MEDIAS: frozenset[str] = frozenset(
    {
        # espanol: preposiciones
        "a",
        "al",
        "ante",
        "con",
        "de",
        "del",
        "desde",
        "durante",
        "en",
        "entre",
        "hacia",
        "hasta",
        "para",
        "por",
        "segun",
        "según",
        "sin",
        "sobre",
        "tras",
        "acerca",
        "respecto",
        "referente",
        # espanol: articulos y determinantes
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        "este",
        # espanol: posesivos
        "mi",
        "mis",
        "tu",
        "tus",
        "su",
        "sus",
        "nuestro",
        "nuestra",
        "nuestros",
        "nuestras",
        # espanol: conjunciones
        "y",
        "e",
        "o",
        "u",
        "ni",
        "pero",
        "porque",
        "pues",
        "aunque",
        "si",
        "que",
        "cuando",
        "como",
        "donde",
        "mientras",
        "sino",
        # espanol: verbos que piden lo que sigue
        "es",
        "son",
        "era",
        "eran",
        "fue",
        "fueron",
        "quería",
        "queria",
        "quiero",
        "quisiera",
        "iba",
        "muy",
        "numero",
        "número",
        # ingles: preposiciones
        "about",
        "of",
        "with",
        "for",
        "to",
        "in",
        "on",
        "at",
        "by",
        "into",
        "under",
        "during",
        "than",
        # ingles: articulos, determinantes y posesivos
        "the",
        "an",
        "that",
        "my",
        "your",
        "our",
        "their",
        # ingles: conjunciones
        "and",
        "or",
        "but",
        "because",
        "if",
        "when",
        "while",
        "as",
        # ingles: verbos que piden lo que sigue
        "is",
        "are",
        "was",
        "were",
        "wanted",
        "i'm",
        "it's",
        "that's",
        "very",
        "number",
    }
)


class Ending(StrEnum):
    """Como termino lo ultimo que dijo la persona: de ahi sale cuanto se espera."""

    #: Cerrada por el reconocedor, o respuesta corta.
    CLOSED = "closed"
    #: Larga y sin su punto.
    UNPUNCTUATED = "unpunctuated"
    #: Termina en una palabra que pide continuacion.
    INCOMPLETE = "incomplete"


def ending_of(text: str) -> Ending:
    """Como termina esta frase (2026-10-12). Tres reglas, en este orden:

    1. **Termina en una palabra de `_A_MEDIAS`**: `INCOMPLETE`, tenga las palabras que
       tenga y la puntuacion que tenga. Nunca es una respuesta corta. Una sola palabra
       "si" es la excepcion: es una respuesta, y el reconocedor no siempre pone la tilde.
    2. **Sin cierre del reconocedor y con mas de `SHORT_ANSWER_WORDS` palabras**:
       `UNPUNCTUATED`. Una frase de esa longitud que llego sin su punto es una frase que la
       persona no termino ("El vehiculo que yo iba conduciendo" llego asi y la agente
       contesto encima, 2026-10-11).
    3. **Todo lo demas**: `CLOSED`. Incluye las respuestas cortas legitimas ("no",
       "si claro", "ayer en la tarde") aunque lleguen sin punto, y el texto vacio.
    """
    ultimo = text.strip().replace("\u2019", "'")
    palabras = ultimo.lower().rstrip(_BORDES).split()
    if not palabras:
        return Ending.CLOSED
    final = palabras[-1].strip(_BORDES)
    if final in _A_MEDIAS and palabras != ["si"]:
        return Ending.INCOMPLETE
    if ultimo[-1] not in _FIN_DE_FRASE and len(palabras) > SHORT_ANSWER_WORDS:
        return Ending.UNPUNCTUATED
    return Ending.CLOSED


@dataclass(frozen=True)
class SpeechEnd:
    """El turno de la persona, cerrado."""

    #: Todo lo final que dijo, en orden.
    text: str
    #: La marca de NFR1: cuando llego el ultimo transcrito final (BR3.1).
    at: datetime
    #: La otra variante de AC1.23.5, para el reporte del hito. Nula si el
    #: proveedor no mando tiempos de palabra.
    last_audible_word_at: datetime | None
    #: El ultimo final, para que el umbral de confianza lo pueda mirar (BR3.4).
    last: Transcript | None
    #: Cuantas senales de voz llegaron con el turno abierto y se quedaron sin palabras: ni un
    #: parcial ni un final las siguio. Es lo que se cuenta en llamadas reales para saber
    #: cuanto ruido hay (2026-10-13).
    unconfirmed_signals: int = 0
    #: Cuanto alargaron esas senales el plazo del turno sobre el que tenia sin ellas. Es el
    #: plazo de diseno, no un tiempo medido: el ciclo cierra el turno en cuanto vence.
    held_by_signals: timedelta = timedelta(0)


@dataclass
class TurnDetector:
    """Acumula transcritos y dice cuando el turno se cerro.

    `started_at` es cuando empezo a escucharse este turno. **No** convierte los tiempos
    de palabra: esos los manda el proveedor relativos al comienzo del flujo de audio de
    toda la llamada, y se pasan a instantes con `stream_started_at`.
    """

    started_at: datetime
    #: Cuando llego el primer trozo de audio de la llamada --el segundo cero de los
    #: tiempos de palabra--. Nulo mientras no se sepa: sin el, la ultima palabra audible
    #: no se calcula.
    stream_started_at: datetime | None = None
    end_of_speech: timedelta = DEFAULT_END_OF_SPEECH
    #: Lo que se espera cuando la frase es larga y no llego con su punto, y cuando quedo a
    #: medias. Datos, como la primera: quien prueba el ritmo sin reloj los pone los tres en
    #: cero.
    unpunctuated_end_of_speech: timedelta = UNPUNCTUATED_END_OF_SPEECH
    incomplete_end_of_speech: timedelta = INCOMPLETE_END_OF_SPEECH
    #: Lo que una senal de voz sin palabras mantiene abierto el turno, y lo maximo que varias
    #: pueden alargarlo. Datos, como las esperas: las pruebas con reloj real los acortan.
    signal_grace: timedelta = SIGNAL_GRACE
    signal_only_extension: timedelta = SIGNAL_ONLY_EXTENSION
    _finales: list[str] = field(default_factory=list)
    _ultimo: Transcript | None = None
    _ultimo_final_a: datetime | None = None
    _ultima_palabra_a: datetime | None = None
    #: Cuando llego lo ultimo que se oyo, parcial o final. No mueve el plazo del turno (eso
    #: solo lo hace un final), pero si dice que alguien esta hablando. **La senal de voz del
    #: reconocedor no lo mueve**: no trae palabras, y no dice que alguien hable.
    _ultimo_oido_a: datetime | None = None
    #: Cuando llego el ultimo parcial **con palabras** despues del ultimo final: la persona
    #: hizo una pausa y siguio hablando. Mientras su final no llegue, el turno no se cierra
    #: por el final anterior.
    _siguio_hablando_a: datetime | None = None
    #: Cuando llego la ultima senal de voz que ningun parcial con palabras ni final ha
    #: confirmado todavia. Es provisional: se olvida si no llegan palabras (`SIGNAL_GRACE`).
    _senal_a: datetime | None = None
    #: Cuantas senales llevan sin confirmarse en este turno; un parcial con palabras o un final
    #: las confirma a todas, y las que queden al cerrar se cuentan como ruido.
    _senales_sin_palabras: int = 0

    @property
    def speaking(self) -> bool:
        """Si hay un turno abierto esperando a cerrarse."""
        return self._ultimo_final_a is not None

    @property
    def last_heard_at(self) -> datetime | None:
        """Cuando llego el ultimo transcrito, parcial o final (2026-10-07).

        Es lo que la escalera de silencios mira: un parcial no cierra el turno,
        pero quien esta a mitad de frase no esta callado, y preguntarle «¿sigue
        ahi?» mientras habla es interrumpirlo. Se vio en produccion: ocho segundos
        de parciales sin un final y la agente preguntaba si seguia ahi.
        """
        return self._ultimo_oido_a

    @property
    def deadline(self) -> datetime | None:
        """Cuando se cerraria el turno si no llega nada mas. `None` si no hay turno."""
        plazo = self._plazo_sin_senal()
        if plazo is None or self._senal_a is None:
            return plazo
        # Una senal sin palabras: se espera `signal_grace` a que llegue un parcial que la
        # confirme, sin pasar de `signal_only_extension` sobre el plazo de antes. Si ese
        # plazo es mayor, la senal no cambia nada.
        return max(
            plazo, min(self._senal_a + self.signal_grace, plazo + self.signal_only_extension)
        )

    def _plazo_sin_senal(self) -> datetime | None:
        """El plazo del turno por lo que dijo la persona: sus finales y sus parciales con palabras."""
        if self._ultimo_final_a is None:
            return None
        plazo = self._ultimo_final_a + self.wait_for(self._ending())
        if self._siguio_hablando_a is not None:
            # Retomo la frase tras la pausa: se espera a que la termine. El tope es
            # por si su final no llega nunca, no un plazo para que hable; es el mas
            # largo, porque quien retoma tras una pausa puede volver a hacerla.
            plazo = max(plazo, self._siguio_hablando_a + self._la_mas_larga())
        return plazo

    def wait_for(self, ending: Ending) -> timedelta:
        """Cuanto se espera, desde el ultimo final, segun como termino."""
        if ending is Ending.INCOMPLETE:
            return max(self.end_of_speech, self.incomplete_end_of_speech)
        if ending is Ending.UNPUNCTUATED:
            return max(self.end_of_speech, self.unpunctuated_end_of_speech)
        return self.end_of_speech

    def _la_mas_larga(self) -> timedelta:
        return max(
            self.end_of_speech, self.unpunctuated_end_of_speech, self.incomplete_end_of_speech
        )

    def _ending(self) -> Ending:
        """Como termino el ultimo final: la puntuacion del reconocedor y su ultima palabra
        (ver `ending_of`). Sin finales --un final vacio--, nada que esperar de mas."""
        if not self._finales:
            return Ending.CLOSED
        return ending_of(self._finales[-1])

    @property
    def ending(self) -> Ending:
        """Como termino lo ultimo que dijo la persona: de ahi sale cuanto se espera."""
        return self._ending()

    @property
    def resumed(self) -> bool:
        """Si la persona siguio hablando despues del ultimo final, y su final aun no llego.

        Un parcial **con palabras** lo enciende; el final siguiente lo apaga. Mientras este
        encendido, lo que el turno lleva escrito no es todo lo que va a decir. **La senal de
        voz sola no lo enciende** (2026-10-13): puede ser un ruido, y quien la mira para soltar
        una lectura que cuesta dinero espera a que lleguen palabras.
        """
        return self._siguio_hablando_a is not None

    def observe(self, transcript: Transcript, *, at: datetime) -> None:
        """Un transcrito del reconocedor.

        Los parciales **no abren** un turno: lo unico que el proveedor afirma es un
        final. Pero un parcial con palabras **despues** de un final dice que la
        persona hizo una pausa y siguio (2026-10-11): el turno ya abierto no se
        cierra por aquel final mientras llega el siguiente. Antes el plazo corria
        igual, y la agente respondia a media frase: "quiero hablarte... referente a
        mi poliza" se atendia como dos turnos, y el primero se entendia mal.
        """
        self._ultimo_oido_a = at
        if not transcript.is_final:
            if self._ultimo_final_a is None:
                self._ultimo = transcript
            elif transcript.text.strip():
                self._siguio_hablando_a = at
                self._confirmar_senales()
            return
        self._ultimo = transcript
        self._siguio_hablando_a = None
        texto = transcript.text.strip()
        if texto:
            self._confirmar_senales()
            self._finales.append(texto)
        else:
            # Un final sin palabras es la respuesta del reconocedor a la senal: hubo ruido.
            # La espera provisional termina, y la senal sigue contando como ruido.
            self._senal_a = None
        self._ultimo_final_a = at
        if transcript.words:
            fin_s = max(p.end_s for p in transcript.words)
            self._ultima_palabra_a = self._hora_de_la_palabra(fin_s, llegada=at)

    def speech_started(self, at: datetime) -> None:
        """El reconocedor oyo que alguien empezo a hablar (2026-10-12, corregido 2026-10-13).

        **Es una pista y no una prueba.** Con un turno abierto, la persona pudo retomar la
        frase tras una pausa --y entonces llega en decimas de segundo, mucho antes que el
        parcial, que tarda hasta un segundo de audio--, o pudo ser un ruido: una tos, el
        teclado, el eco de la sala. Sin esta senal el plazo de un final vencia antes de que
        el parcial llegara, y la agente contestaba encima ("Hola, queria consultar sobre" +
        una pausa + «si mi poliza me cubre...»). Pero tratarla como palabras dejaba el turno
        abierto 2,5 s por cada ruido, y varios seguidos sin limite.

        Por eso la senal sola **solo mantiene abierto el turno `signal_grace`** a partir de
        ella, y nunca mas de `signal_only_extension` sobre el plazo que ya tenia. Si en ese
        tiempo llega un parcial con palabras, la persona retomo de verdad: ese parcial manda,
        con la espera larga de siempre y sin tope. Si no llega, la senal se olvida sola y el
        turno se cierra a su plazo, y queda contada en `SpeechEnd.unconfirmed_signals`.

        No cuenta en `last_heard_at` ni en `resumed`: ninguna de las dos dice que alguien
        hable, y la escalera de silencios y la lectura adelantada del modelo las leen para
        eso. **Sin turno abierto no hace nada**: solo un final abre un turno, y una senal sin
        el puede ser el eco de la propia agente.
        """
        if self._ultimo_final_a is None:
            return
        self._senal_a = at
        self._senales_sin_palabras += 1

    def _confirmar_senales(self) -> None:
        """Llegaron palabras: las senales que esperaban eran la voz de la persona."""
        self._senal_a = None
        self._senales_sin_palabras = 0

    def _hora_de_la_palabra(self, fin_s: float, *, llegada: datetime) -> datetime | None:
        """La hora de pared en que termino la ultima palabra, o `None` si no es creible.

        Una palabra no puede acabar despues de que llego el final que la trae, ni
        segundos antes: cualquiera de las dos cosas es que el flujo no iba en tiempo de
        pared, y publicar la cuenta seria publicar un numero imposible.
        """
        if self.stream_started_at is None:
            return None
        palabra = self.stream_started_at + timedelta(seconds=fin_s)
        if palabra > llegada or llegada - palabra > MAX_WORD_TO_FINAL:
            return None
        return palabra

    def expired(self, now: datetime) -> bool:
        """Si el silencio ya cerro el turno."""
        limite = self.deadline
        return limite is not None and now >= limite

    def pending_end(self) -> SpeechEnd | None:
        """El turno tal como se cerraria **ahora**, sin cerrarlo; nulo si no hay turno abierto.

        Lo usa quien empieza a entender la frase antes de que venza la tolerancia
        (`voice.early_understanding`): necesita el texto y la hora que `close` va a entregar si
        no llega nada mas, y cerrar el turno para saberlo lo acabaria.
        """
        if self._ultimo_final_a is None:
            return None
        base = self._plazo_sin_senal()
        plazo = self.deadline
        retenido = plazo - base if base is not None and plazo is not None else timedelta(0)
        return SpeechEnd(
            text=" ".join(self._finales),
            at=self._ultimo_final_a,
            last_audible_word_at=self._ultima_palabra_a,
            last=self._ultimo,
            unconfirmed_signals=self._senales_sin_palabras,
            held_by_signals=retenido,
        )

    def close(self) -> SpeechEnd:
        """El turno cerrado, y el detector listo para el siguiente.

        Falla si no hay turno abierto: cerrar lo que no se abrio produciria un
        turno vacio con la hora de ahora, que es un dato inventado.
        """
        cerrado = self.pending_end()
        if cerrado is None:
            msg = "no hay turno abierto que cerrar"
            raise ValueError(msg)
        self._finales = []
        self._ultimo = None
        self._ultimo_final_a = None
        self._ultima_palabra_a = None
        self._ultimo_oido_a = None
        self._siguio_hablando_a = None
        self._senal_a = None
        self._senales_sin_palabras = 0
        return cerrado


__all__ = [
    "DEFAULT_END_OF_SPEECH",
    "INCOMPLETE_END_OF_SPEECH",
    "MAX_WORD_TO_FINAL",
    "SHORT_ANSWER_WORDS",
    "SIGNAL_GRACE",
    "SIGNAL_ONLY_EXTENSION",
    "UNPUNCTUATED_END_OF_SPEECH",
    "Ending",
    "SpeechEnd",
    "TurnDetector",
    "ending_of",
]
