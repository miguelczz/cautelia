"""El idioma de un turno, para los dos canales (BR2.1 a BR2.3 de U13; BR3.4 de U18).

**Vive en la raiz del paquete y es una hoja**, como `base.py` y `surface_spec.py`.
Nacio dentro de `untangle.chat` --era el unico canal que lo necesitaba-- y subio
aqui el 2026-09-29 con U18, porque la llamada de voz tambien cambia de idioma y
`untangle.chat` y `untangle.voice` son hermanos en el contrato de capas: ninguno
puede importar al otro.

**Lo que no se hizo, y es la parte que importa: no se copio.** Un segundo detector
con los mismos umbrales son dos numeros que se separan el dia que alguien afina
uno, en un proyecto que publica adherencia de idioma **por idioma**. Los dos
umbrales de abajo no son elecciones: son medidas, y estan anotadas con la frase
que las produjo.

**Dos usos, dos umbrales, y no se confunden.**

Dentro del turno (`for_turn`) lo que importa es no equivocarse en contra: sin senal
suficiente, la conversacion **conserva** el idioma que ya tenia. Cambiar de idioma por
un "ok" rompe la conversacion a mitad por un turno que no dice nada, que es peor que
no cambiarla nunca (BR2.2).

En el corredor de evaluaciones (`measured`) lo que importa es no inventar: un turno
sin senal se cuenta como **no medido** antes que adivinarlo. Contar una adivinanza
como acierto contamina la metrica de adherencia de idioma que el PRD publica.

**Un tercer idioma se dice, no se finge** (BR2.3). Si el mensaje no esta en espanol ni
en ingles, la conversacion sigue en el suyo y quien llama emite la frase del catalogo
que dice que la demostracion atiende esos dos. Nunca se responde en un tercer idioma y
nunca se ignora el turno.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache

from lingua import Language, LanguageDetector, LanguageDetectorBuilder

from untangle.base import Locale

#: Los dos idiomas que la demostracion atiende. El detector se construye **solo
#: con ellos**: uno que considerara setenta y cinco repartiria su confianza entre
#: candidatos que este proyecto no va a responder nunca, y acertaria menos en los
#: dos que si importan.
_IDIOMAS = (Language.SPANISH, Language.ENGLISH)

#: Debajo de esta confianza no hay senal suficiente para cambiar de idioma. No es
#: un numero magico: es el punto por debajo del cual el propio detector considera
#: que los dos candidatos estan practicamente empatados, y un empate en un turno
#: de dos palabras es exactamente el caso de BR2.2.
_CONFIANZA_MINIMA = 0.75

#: El mismo juicio sobre el detector **amplio**, y el numero es otro a proposito:
#: los dos no comparten escala. El de dos idiomas reparte su confianza entre dos
#: candidatos y una frase clara llega a 0,99; el amplio la reparte entre setenta y
#: cinco y esa misma frase se queda en 0,73. Medido: "Bom dia, preciso reportar um
#: acidente..." da 0,726 en portugues, y el nombre propio "Marcela Rios" da 0,168.
#: Medio punto separa los dos casos con margen holgado por los dos lados, y usar
#: aqui el umbral del otro detector trataria una frase clara como si no tuviera
#: senal.
_CONFIANZA_AMPLIA = 0.5

#: Un turno con menos palabras que esto no se mira siquiera. Se cuentan
#: **palabras y no caracteres**, y esa es la leccion de esta funcion: "Marcela
#: Rios" tiene doce caracteres --pasaba cualquier filtro de longitud-- y el
#: detector le da 0,92 a espanol, asi que un nombre propio cambiaba el idioma de
#: la conversacion. AC1.2.3 lo nombra justo como el caso que **no** debe cambiar
#: nada, junto con "ok" y una placa. Cuatro palabras es donde un mensaje deja de
#: ser un identificador o un nombre y empieza a ser una frase.
_PALABRAS_MINIMAS = 4


class LanguageOutcome(StrEnum):
    """Que se pudo decir del idioma de un turno. Conjunto cerrado."""

    #: Se detecto uno de los dos que la demostracion atiende.
    DETECTED = "detected"
    #: No hay senal suficiente: texto corto, o dos candidatos empatados.
    NO_SIGNAL = "no_signal"
    #: Se detecto, pero no es ninguno de los dos (BR2.3).
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class TurnLanguage:
    """El idioma con el que se responde este turno, y por que.

    `language` **siempre** trae uno de los dos: es el idioma en el que la agente
    va a responder, y ninguna de las tres salidas deja a quien llama sin uno.
    `outcome` dice si se detecto, si se conservo el anterior o si el mensaje venia
    en un idioma que la demostracion no atiende, que es lo que decide si ademas
    hay que decir algo al respecto.
    """

    language: Locale
    outcome: LanguageOutcome

    @property
    def unsupported(self) -> bool:
        return self.outcome is LanguageOutcome.UNSUPPORTED


@lru_cache(maxsize=1)
def _detector() -> LanguageDetector:
    """El detector, construido una vez por proceso: construirlo carga sus modelos."""
    return LanguageDetectorBuilder.from_languages(*_IDIOMAS).build()


@lru_cache(maxsize=1)
def _detector_amplio() -> LanguageDetector:
    """El detector de todos los idiomas, para distinguir BR2.3 de BR2.2.

    Hace falta uno aparte: el de dos idiomas siempre responde espanol o ingles
    --no conoce otros-- asi que con el solo, un mensaje en portugues seria
    indistinguible de uno sin senal. Este responde cual es de verdad, y es lo que
    permite decir "la demostracion atiende estos dos" en vez de callar.
    """
    return LanguageDetectorBuilder.from_all_languages().build()


def _sin_senal(text: str) -> bool:
    return len(text.split()) < _PALABRAS_MINIMAS


def has_signal(text: str) -> bool:
    """Si el texto trae palabras suficientes para mirarle el idioma.

    **Publica desde U18**, y no por comodidad: en la voz hay una segunda fuente
    de idioma --el reconocedor en modo multiidioma lo devuelve en cada
    transcrito-- y el piso de palabras tiene que valer para las dos. Sin esto, un
    "okay" con el idioma que trae el proveedor cambiaria la llamada entera, que es
    justo lo que AC1.32.2 prohibe, y el piso quedaria aplicandose solo por un lado.
    """
    return not _sin_senal(text)


def for_turn(text: str, *, current: Locale) -> TurnLanguage:
    """El idioma en que se responde este turno (BR2.1, BR2.2, BR2.3).

    `current` es el de la conversacion: lo que se conserva cuando el turno no
    trae senal suficiente. La respuesta nunca deja de traer un idioma.
    """
    if _sin_senal(text):
        return TurnLanguage(language=current, outcome=LanguageOutcome.NO_SIGNAL)

    # Al detector amplio se le exige **la misma confianza** que al de dos idiomas,
    # y no solo que responda algo. Sin ese umbral, un nombre propio --"Marcela
    # Rios"-- cae en el idioma que mas se le parezca de los setenta y cinco y se
    # trataria como un tercer idioma, cuando AC1.2.3 lo nombra justo como el caso
    # que **no** debe cambiar nada. Lo encontro su propia prueba.
    amplios = _detector_amplio().compute_language_confidence_values(text)
    if amplios and amplios[0].value >= _CONFIANZA_AMPLIA and amplios[0].language not in _IDIOMAS:
        # BR2.3: se detecto de verdad, con confianza, y no es ninguno de los dos.
        return TurnLanguage(language=current, outcome=LanguageOutcome.UNSUPPORTED)

    valores = _detector().compute_language_confidence_values(text)
    if not valores or valores[0].value < _CONFIANZA_MINIMA:
        return TurnLanguage(language=current, outcome=LanguageOutcome.NO_SIGNAL)

    # `==` y no `is`: los valores de `Language` vienen de una extension en Rust y
    # no garantizan identidad entre llamadas. Con `is` la comparacion falla en
    # silencio y **todo turno en espanol se responderia en ingles**; se encontro
    # probando el detector contra frases reales antes de escribir su prueba.
    detectado: Locale = "es" if valores[0].language == Language.SPANISH else "en"
    return TurnLanguage(language=detectado, outcome=LanguageOutcome.DETECTED)


def measured(text: str) -> Locale | None:
    """El idioma de un texto para la metrica de adherencia (AC1.2.4).

    Devuelve `None` --no medido-- en vez de adivinar. Es el otro umbral: aqui no
    hay conversacion de la que heredar un idioma, y contar una adivinanza como
    acierto contaminaria la cifra que el PRD publica por idioma.
    """
    if _sin_senal(text):
        return None
    valores = _detector().compute_language_confidence_values(text)
    if not valores or valores[0].value < _CONFIANZA_MINIMA:
        return None
    return "es" if valores[0].language == Language.SPANISH else "en"


__all__ = ["LanguageOutcome", "TurnLanguage", "for_turn", "has_signal", "measured"]
