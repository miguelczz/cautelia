"""La transcripcion en vivo: acumular, cortar seguro y avisar (BR3.5, Flujo 2).

La consola muestra transcripcion parcial mientras el asegurado habla. Un telefono
llega digito a digito, asi que un fragmento puede contener media cedula que
todavia no tiene forma de cedula.

**Los digitos nunca se muestran y luego se tapan.** Un numero mostrado y cubierto
medio segundo despues ya se leyo: cualquiera que estuviera mirando lo leyo, y la
captura de pantalla lo conserva. Por eso esta pieza retrasa en vez de corregir.

**El corte va por frases, y no por palabras.** BR3.5 dice que lo acumulado se
vuelve a redactar "con lo anterior de la misma frase", y ahi esta la razon: un
reconocedor necesita el dato **y su contexto** para reconocerlo. "79123456" a
secas no llega al umbral; "mi cedula es 79123456" si. Si se mostrara hasta la
ultima palabra segura, una cedula cuyo "es mi cedula" viene **despues** se
mostraria en claro antes de que la frase que la delata llegara. Mostrar solo
frases cerradas hace que lo que se muestra se redacte exactamente igual que se
redactara al final.

El costo aceptado es que la transcripcion en vivo va por detras de la voz
mientras se dicta un dato. Ese retraso **no se acota**, porque su duracion
pertenece a quien habla (NFR11.4): lo que se acota es que nadie se quede mirando
una pantalla quieta sin saber por que, y de eso se ocupa el aviso.

**Donde corre la redaccion**, que no es donde parecia: la llamada a `redact()`
no va al bucle de eventos, va a un hilo del pool, con semaforo por uso --voz,
chat y fondo-- (ADR-004, NFRD-U3-6). El Flujo 2 es exactamente su caso: redactar
un fragmento parcial ocurre mientras la persona esta hablando, dentro del turno
de voz. Lo que el turno no puede permitirse es quedarse bloqueado.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from weakref import WeakKeyDictionary

from untangle.base import Locale
from untangle.compliance.redaction import api

#: Lo que cierra una frase.
TERMINADORES = frozenset({".", "!", "?", "…", "\n"})

#: Cuanto puede estar oculto un fragmento **sin avisar** (NFR11.4).
#:
#: Un segundo, que es el limite del hilo de pensamiento en los tres limites de
#: respuesta de Nielsen: por debajo no hace falta indicador; por encima, una
#: pantalla congelada hace pensar que el sistema se cayo. No acota cuanto puede
#: estar oculto --eso lo decide quien habla-- sino cuando hay que decirlo.
AVISO_TRAS_SEGUNDOS = 1.0


class Use(StrEnum):
    """Para que se pide la redaccion. Cada uso tiene su propio semaforo.

    Que sean tres y no uno es lo que impide que una corrida de evaluaciones en
    segundo plano se quede con los hilos que necesita una llamada en curso
    (ADR-004).
    """

    VOICE = "voice"
    CHAT = "chat"
    BACKGROUND = "background"


#: Cuantas redacciones a la vez admite cada uso.
#:
#: La voz lleva dos porque en un turno pueden convivir la pasada del parcial y la
#: del texto final; el chat lleva cuatro porque son varias conversaciones a la
#: vez y ninguna esta dictando; y el fondo lleva **una**, que es el numero que
#: hace que una corrida larga no pueda comerse el pool.
LIMITES: dict[Use, int] = {Use.VOICE: 2, Use.CHAT: 4, Use.BACKGROUND: 1}

_semaforos: WeakKeyDictionary[asyncio.AbstractEventLoop, dict[Use, asyncio.Semaphore]] = (
    WeakKeyDictionary()
)


def _semaforo(use: Use) -> asyncio.Semaphore:
    """El semaforo de un uso, uno por bucle de eventos.

    Uno por bucle y no uno global: un semaforo compartido entre bucles distintos
    --que es lo que hay en una suite de pruebas-- acaba esperando en un bucle que
    ya no corre.
    """
    bucle = asyncio.get_running_loop()
    del_bucle = _semaforos.setdefault(bucle, {})
    if use not in del_bucle:
        del_bucle[use] = asyncio.Semaphore(LIMITES[use])
    return del_bucle[use]


async def redact_off_loop(text: str, *, language: Locale, use: Use) -> api.Redacted:
    """Redacta **fuera del bucle de eventos**, en un hilo del pool (ADR-004).

    El camino del turno la espera de forma asincrona. La redaccion es trabajo de
    CPU --dos pasadas de modelo y unas cuantas expresiones-- y hacerla en el
    bucle bloquearia todo lo demas del turno mientras dura.
    """
    async with _semaforo(use):
        return await asyncio.to_thread(api.redact, text, language=language)


def safe_prefix_end(text: str) -> int:
    """Hasta donde se puede mostrar: el final de la ultima frase cerrada.

    Una frase esta cerrada cuando su terminador cumple **las tres** condiciones,
    y cada una cierra un camino por el que se veria un digito:

    1. Le sigue un espacio. Sin el, el punto es un separador de miles y no un
       final: `79.123.456` tiene dos puntos y ninguna frase.
    2. Despues de ese espacio hay algo. Un terminador al final de lo acumulado no
       cierra nada, porque el fragmento siguiente puede continuarlo: `79.123.`
       todavia puede convertirse en `79.123.456`.
    3. Lo que sigue **no es un digito**. `79.123. 456` dictado con pausas es el
       mismo numero partido, no dos frases.
    """
    corte = 0
    for indice, caracter in enumerate(text):
        if caracter not in TERMINADORES:
            continue
        resto = text[indice + 1 :]
        if caracter != "\n" and not resto[:1].isspace():
            continue
        siguiente = resto.lstrip()
        if not siguiente or siguiente[0].isdigit():
            continue
        corte = indice + 1
    return corte


@dataclass(frozen=True)
class LiveFrame:
    """Lo que la consola puede pintar ahora mismo.

    No lleva el texto oculto ni nada de el: lleva **cuantos caracteres** se estan
    reteniendo, que es lo que la consola necesita para decidir si dibuja el
    indicador y no revela nada de lo que retiene.
    """

    #: Lo que se muestra, ya redactado. Fabricado por `api.redact`, que es el
    #: unico sitio que fabrica este tipo.
    shown: api.Redacted
    #: Cuantos caracteres quedan retenidos esperando a cerrar su frase.
    withheld_chars: int
    #: Si la consola debe dibujar su indicador de que viene texto (NFR11.4).
    notice: bool


@dataclass
class LiveTranscript:
    """Acumula fragmentos parciales de una frase y decide que se puede mostrar.

    Una instancia por llamada. Lleva estado --lo acumulado y desde cuando hay
    algo retenido-- y por eso no se comparte: dos llamadas con la misma
    instancia mezclarian sus frases.
    """

    language: Locale
    use: Use = Use.VOICE
    #: El reloj. Se inyecta para poder **probar cuando aparece el aviso** sin
    #: esperar un segundo de verdad en cada corrida. Lo que no se prueba con un
    #: reloj controlado es el coste de la pasada: eso se cronometra con el reloj
    #: del sistema alrededor de la llamada real, porque un reloj simulado no
    #: cronometra trabajo real (SEC-U3.11).
    clock: Callable[[], float] = time.monotonic
    _acumulado: str = field(default="", init=False)
    _oculto_desde: float | None = field(default=None, init=False)
    _corte_anterior: int = field(default=0, init=False)

    @property
    def accumulated_length(self) -> int:
        """Cuanto lleva acumulado. Nunca el texto: solo su longitud."""
        return len(self._acumulado)

    async def push(self, fragment: str) -> LiveFrame:
        """Acumula un fragmento y devuelve lo que ya se puede mostrar."""
        self._acumulado += fragment
        corte = safe_prefix_end(self._acumulado)
        retenidos = len(self._acumulado) - corte

        # El cronometro del aviso mide **cuanto lleva la consola sin ensenar
        # nada nuevo**, no cuanto lleva habiendo algo retenido. Mientras alguien
        # habla siempre hay una frase a medias esperando a cerrar, asi que un
        # cronometro sobre "hay algo retenido" avisaria en cada pausa. Lo que
        # hace pensar que el sistema se cayo es que la pantalla no se mueva.
        if retenidos == 0:
            self._oculto_desde = None
        elif corte > self._corte_anterior or self._oculto_desde is None:
            self._oculto_desde = self.clock()
        self._corte_anterior = corte

        mostrado = await redact_off_loop(
            self._acumulado[:corte], language=self.language, use=self.use
        )
        return LiveFrame(
            shown=mostrado,
            withheld_chars=retenidos,
            notice=self._hay_que_avisar(),
        )

    def _hay_que_avisar(self) -> bool:
        """Si lo retenido lleva mas de un segundo sin poder mostrarse."""
        if self._oculto_desde is None:
            return False
        return (self.clock() - self._oculto_desde) > AVISO_TRAS_SEGUNDOS

    async def finish(self) -> api.Redacted:
        """Cierra la frase: el texto final vuelve a pasar por el Flujo 1.

        Deja la instancia lista para la siguiente frase. La numeracion de las
        etiquetas empieza de nuevo, que es lo que BR3.3 fija: mantenerla exigiria
        guardar la correspondencia entre el valor real y su numero.
        """
        completo = self._acumulado
        self.reset()
        return await redact_off_loop(completo, language=self.language, use=self.use)

    def reset(self) -> None:
        """Olvida lo acumulado. Nada de una frase sobrevive a la siguiente."""
        self._acumulado = ""
        self._oculto_desde = None
        self._corte_anterior = 0
