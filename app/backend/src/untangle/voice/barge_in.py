"""Interrumpir a la agente (BR4.1, BR4.2, BR4.3).

**Un parcial cualquiera no puede callar a la agente.** El ruido de un carro se
transcribe a veces como una silaba suelta, y una agente que se calla con cada
bache es peor que una que no se calla nunca. El piso es dos palabras, o una
palabra por encima del umbral de confianza.

Las otras dos capas no estan aqui. La primera es del navegador: el microfono se
pide con su cancelacion de eco activada (BR4.2), la misma que usan las
videollamadas. La segunda es del servidor, desde el 2026-10-13, y existe porque la
primera no siempre alcanza: lo que el reconocedor oye mientras la agente suena, y
es lo que la agente esta diciendo, se quita antes de llegar aqui
(`own_voice.OwnVoice`, por `CallRunner._sin_la_voz_de_la_agente`). Asi la propia
voz de la agente, saliendo por el altavoz de un portatil sin audifonos, no se lee
como interrupcion ni como turno de la persona.

**Quien corta el audio es el navegador, avisado por el servidor** (BR4.3). El
servidor no puede retirar lo que ya mando: cuando detecta la interrupcion, el
navegador tiene cientos de milisegundos encolados. Por eso deja de sintetizar
**y** manda `stop_audio`, y por eso NFR2 se mide en el cliente.
"""

from __future__ import annotations

from untangle.base import Locale
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration.nodes.intake import confirmation, social
from untangle.providers.ports import Transcript

ACKNOWLEDGE = CopyKey("voice.barge_in.acknowledge")

#: Cuantas palabras hacen falta para que algo cuente como interrupcion. Es dato
#: de la aseguradora y entra por argumento; dos es el arranque.
DEFAULT_MIN_WORDS = 2

#: Por encima de esto, una sola palabra basta. Una persona que dice "no" claro
#: esta interrumpiendo, y pedirle dos palabras la obligaria a repetirse.
DEFAULT_CONFIDENCE_FLOOR = 0.8

#: Hasta cuantas palabras un saludo sigue siendo un saludo ("hola, buenas tardes,
#: alo"). Es el mismo tope que usa el chat para decidir que un primer mensaje solo
#: saluda; por encima ya hay frase.
MAX_GREETING_WORDS = 6

#: Lo que se dice al telefono para saber si alguien contesta y que las listas de
#: saludos no traen: el "alo" de contestar y las muletillas de asentir. Plegadas. El
#: "si" y el "yes" no estan aqui porque ya los reconoce `confirmation.is_affirmative`.
CONTACT_WORDS: frozenset[str] = frozenset(
    {"alo", "allo", "ok", "okay", "aja", "mhm", "mm", "eh", "ah", "uh", "um"}
)


def interrupts(
    transcript: Transcript | None,
    *,
    min_words: int = DEFAULT_MIN_WORDS,
    confidence_floor: float = DEFAULT_CONFIDENCE_FLOOR,
) -> bool:
    """Si esto es una interrupcion de verdad y no ruido (BR4.1).

    Se mira **la mejor** palabra para el atajo de una sola --lo que se busca es
    una senal clara de que alguien hablo-- y esa es la diferencia con la escalera
    de "no le entendi", que mira la peor porque busca lo contrario: si se puede
    dar por bueno lo que se oyo entero.
    """
    if transcript is None:
        return False
    palabras = transcript.text.split()
    if not palabras:
        return False
    if len(palabras) >= min_words:
        return True
    confianzas = [p.confidence for p in transcript.words if p.confidence is not None]
    return bool(confianzas) and max(confianzas) >= confidence_floor


def is_greeting(text: str, *, language: Locale) -> bool:
    """Si el turno es solo un saludo o una muletilla de contacto: "alo", "hola", "si", "yes".

    Por reglas y con las listas que ya existen: los saludos son los de las senales
    sociales del chat (`social_signals.yaml`, con el nombre de la agente incluido) y el
    si es el de la lectura de confirmacion. Lo unico propio son las pocas palabras de
    `CONTACT_WORDS`, que no son saludos ni confirmaciones sino la forma de comprobar que
    hay alguien al otro lado.

    Un "gracias", un "adios" o un "cuanto falta" **no** son esto, aunque sean sociales:
    quien se despide o pregunta algo si esta interrumpiendo. Y en cuanto queda una
    palabra con contenido ("alo, tuve un choque") deja de serlo.
    """
    senal = social.detect(text, language=language)
    if senal not in (None, social.SocialIntent.GREETING):
        return False
    if len(text.split()) > MAX_GREETING_WORDS:
        return False
    restantes = social.leftover_words(text, language=language)
    if senal is None and not restantes:
        return False
    return all(
        palabra in CONTACT_WORDS or confirmation.is_affirmative(palabra, language=language)
        for palabra in restantes
    )


def acknowledgement(*, language: Locale) -> str:
    """Lo que la agente dice al ceder el turno (AC1.24.1).

    Se dice cuando la interrupcion no trae todavia una correccion que tomar. Si
    la trae, la conversacion sigue con ella y esta frase sobra: responder "si,
    digame" a alguien que ya dijo lo que queria corregir es hacerle repetirlo.
    """
    return copy_api.t(ACKNOWLEDGE, locale=language)


__all__ = [
    "ACKNOWLEDGE",
    "CONTACT_WORDS",
    "DEFAULT_CONFIDENCE_FLOOR",
    "DEFAULT_MIN_WORDS",
    "MAX_GREETING_WORDS",
    "acknowledgement",
    "interrupts",
    "is_greeting",
]
