"""Lo que la persona dice de paso --saluda, agradece, se despide, pregunta cuanto falta--
y como se reconoce sin ningun modelo (decision de Miguel, 2026-10-06).

**Por que existe.** La captura preguntaba el campo pendiente ante cualquier turno:
a "Hola" le contestaba "¿Cual es su nombre completo y el numero de su poliza?", y a
"gracias" tambien. Miguel lo describio como una contestadora de toda la vida, y
tenia razon: lo que distingue a alguien que escucha es que contesta lo que le
dijeron antes de seguir con lo suyo.

**Es un reconocedor determinista, como el de tono y el de cobertura.** Una lista
versionada de frases por idioma (`social_signals.yaml`, junto a `tone_signals.yaml`),
plegada y comparada con limite de palabra. No es comprension del lenguaje: es lo
bastante ancho para los casos de DS-2 que lo miden, y se amplia el dia que un caso
nuevo lo necesite, nunca adivinando (misma disciplina que el resto de los
reconocedores del proyecto). La decision de que decir sigue en codigo y el texto
sale del catalogo (BR5.1).

**Se reconoce en los dos idiomas a la vez, se contesta en el de la conversacion.**
Un "gracias" o un "hola" tienen menos de las cuatro palabras con las que el
detector de idioma cambia de idioma (BR2.2: un turno corto no mueve la
conversacion), asi que llegan con el idioma que la conversacion ya tenia. Si el
reconocedor mirara solo ese idioma, "gracias" en una aseguradora que habla ingles
por omision no seria un agradecimiento sino un no a la lectura pendiente --paso
en produccion el 2026-10-06, en la primera prueba con Sunmeadow--. Las frases son
cortas e inequivocas en cualquier idioma, asi que se buscan todas; la respuesta
sale en el idioma de la conversacion, que es lo que BR2.2 decide.

**Un turno que solo trae lo social no llama al modelo.** "Hola", "gracias" o
"¿cuanto falta?" no dicen nada que extraer, y llamar al extractor con eso gasta una
llamada del plan gratuito para que devuelva una lista vacia tras varios segundos
--el plan que esta saturado--. `is_only_social` lo decide: quitadas las frases
sociales y el nombre de la agente, si no queda mas que una palabra suelta, no hay
nada que extraer. "Hola, soy Marcus Reed y mi poliza es la POL-000001" si llama al
modelo, y ademas recibe su saludo.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

import yaml

from untangle import paths
from untangle.base import Locale
from untangle.compliance.controls.normalization import fold

_SOCIAL_FILE = "social_signals.yaml"

#: Hasta cuantas palabras puede quedar en el turno, quitado lo social, para
#: considerarlo solo social. Una: "ok gracias", "si gracias", "hola catalina". Con
#: dos ya puede haber un dato ("gracias, el jueves").
MAX_LEFTOVER_WORDS = 1


class SocialConfigError(ValueError):
    """El archivo de senales sociales no tiene la forma que se espera."""


class SocialIntent(StrEnum):
    """Las cuatro senales. Una conversacion de siniestros no necesita mas, y cada
    una nueva entra con su caso de golden set."""

    GREETING = "greeting"
    THANKS = "thanks"
    GOODBYE = "goodbye"
    PROGRESS = "progress"


#: Cuando un turno trae mas de una senal, manda la primera de esta tupla: quien se
#: despide agradeciendo se esta despidiendo; quien saluda y pregunta cuanto falta
#: quiere saber cuanto falta.
PRIORITY: tuple[SocialIntent, ...] = (
    SocialIntent.GOODBYE,
    SocialIntent.PROGRESS,
    SocialIntent.THANKS,
    SocialIntent.GREETING,
)


@dataclass(frozen=True)
class SocialSignals:
    """Las frases de cada senal, por idioma, ya plegadas."""

    phrases: dict[SocialIntent, dict[Locale, tuple[str, ...]]]


def _social_path(root: Path | None) -> Path:
    base = root if root is not None else paths.intake_dir()
    return base / _SOCIAL_FILE


@lru_cache(maxsize=1)
def _loaded(ruta: str) -> SocialSignals:
    contenido = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    if not isinstance(contenido, dict):
        msg = f"'{ruta}' no es un mapeo YAML"
        raise SocialConfigError(msg)
    frases: dict[SocialIntent, dict[Locale, tuple[str, ...]]] = {}
    for senal in SocialIntent:
        por_idioma = contenido.get(senal.value)
        if not isinstance(por_idioma, dict):
            msg = f"'{ruta}' tiene que declarar '{senal.value}' como mapeo por idioma"
            raise SocialConfigError(msg)
        frases[senal] = {
            idioma: tuple(fold(frase) for frase in lista) for idioma, lista in por_idioma.items()
        }
    return SocialSignals(phrases=frases)


def load_social_signals(root: Path | None = None) -> SocialSignals:
    return _loaded(str(_social_path(root)))


def _pattern(frases: tuple[str, ...]) -> re.Pattern[str] | None:
    if not frases:
        return None
    # Las mas largas primero, para que "muchas gracias" no se quede en "gracias" y
    # deje "muchas" como palabra suelta.
    ordenadas = sorted(frases, key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(re.escape(frase) for frase in ordenadas) + r")\b")


def _all_phrases(senales: SocialSignals, senal: SocialIntent) -> tuple[str, ...]:
    """Las frases de una senal en **todos** los idiomas (ver el docstring del modulo)."""
    return tuple(frase for lista in senales.phrases[senal].values() for frase in lista)


def detect(text: str, *, language: Locale, root: Path | None = None) -> SocialIntent | None:
    """La senal social del turno, o `None`. Con varias, la de mas prioridad.

    `language` es el idioma de la conversacion y se recibe para que quien llama
    diga en que idioma va a contestar; **no acota la busqueda**: un turno corto
    llega con el idioma anterior aunque venga en el otro (BR2.2).
    """
    del language
    senales = load_social_signals(root)
    plegado = fold(text)
    for senal in PRIORITY:
        patron = _pattern(_all_phrases(senales, senal))
        if patron is not None and patron.search(plegado):
            return senal
    return None


#: Lo que ademas se descuenta al medir si quedo algo: el nombre de la agente,
#: porque "hola catalina" es un saludo y no un dato. Plegado, como todo lo demas.
_AGENT_NAMES: tuple[str, ...] = ("catalina",)


def install_agent_names(names: Iterable[str]) -> None:
    """Los nombres de las agentes de las aseguradoras cargadas. Los instala la raiz de
    composicion: cada aseguradora tiene la suya y este modulo no nombra ninguna."""
    global _AGENT_NAMES
    _AGENT_NAMES = tuple(sorted({fold(nombre) for nombre in names if nombre.strip()}))


def leftover_words(text: str, *, language: Locale, root: Path | None = None) -> tuple[str, ...]:
    """Las palabras que quedan quitadas las frases sociales y el nombre de la agente.

    Publica porque es lo que la prueba y la sonda miran para explicar un fallo:
    "quedo 'reed'" dice mas que un booleano.
    """
    del language
    senales = load_social_signals(root)
    plegado = fold(text)
    for senal in SocialIntent:
        patron = _pattern(_all_phrases(senales, senal))
        if patron is not None:
            plegado = patron.sub(" ", plegado)
    for nombre in _AGENT_NAMES:
        plegado = re.sub(rf"\b{re.escape(nombre)}\b", " ", plegado)
    return tuple(palabra for palabra in re.findall(r"[^\W_]+", plegado) if palabra)


def is_only_social(text: str, *, language: Locale, root: Path | None = None) -> bool:
    """Si el turno no trae mas que lo social: nada que extraer, nada que preguntarle al modelo."""
    if detect(text, language=language, root=root) is None:
        return False
    return len(leftover_words(text, language=language, root=root)) <= MAX_LEFTOVER_WORDS


__all__ = [
    "MAX_LEFTOVER_WORDS",
    "PRIORITY",
    "SocialConfigError",
    "SocialIntent",
    "SocialSignals",
    "detect",
    "install_agent_names",
    "is_only_social",
    "leftover_words",
    "load_social_signals",
]
