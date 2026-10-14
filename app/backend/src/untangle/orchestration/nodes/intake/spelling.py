"""La tabla de deletreo: una sola para leer en voz y para reconocer lo dictado (BR2.5, TECH-U11.3).

Es del canal de voz -- deletrear con una palabra de desambiguacion es para que
se oiga bien, y un canal de texto no lo necesita para leerlo -- pero la tabla y
la composicion son de aqui, "para que el texto y la voz lean lo mismo" (BR2.5).
El canal de texto puede usar la misma composicion tal cual, y de hecho es lo
que le conviene: son las mismas letras y no hay ninguna razon para que su
version se escriba dos veces.

La misma tabla resuelve la mitad contraria -- reconocer lo que la persona
dicto -- para `normalization.py` (BR2.4): un nombre de letra hablado por
idioma y una palabra de desambiguacion por letra son exactamente lo que hace
falta para las dos direcciones, y una sola fuente evita que se desincronicen.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from untangle import paths
from untangle.base import Locale
from untangle.compliance.controls.normalization import fold

_ARCHIVO = "spelling_alphabet.yaml"


class SpellingConfigError(ValueError):
    """El archivo de la tabla de deletreo no tiene la forma que se espera."""


@dataclass(frozen=True)
class LetterEntry:
    """Una letra: su nombre hablado y su palabra de desambiguacion, por idioma."""

    letter: str
    name: dict[Locale, str]
    disambiguation: dict[Locale, str]


@dataclass(frozen=True)
class SpellingAlphabet:
    """La tabla entera, ya cargada e indexada en los dos sentidos."""

    letters: dict[str, LetterEntry]
    digit_names: dict[Locale, dict[str, str]]
    connector: dict[Locale, str]

    #: `nombre hablado -> letra`, por idioma. Construido una sola vez al cargar
    #: para que reconocer no recorra las veintiseis letras por cada palabra.
    letter_names: dict[Locale, dict[str, str]]
    #: `palabra de desambiguacion -> letra`, por idioma.
    disambiguations: dict[Locale, dict[str, str]]
    #: `nombre hablado -> digito`, por idioma (el inverso de `digit_names`).
    digit_words: dict[Locale, dict[str, str]]
    #: Las letras que se confunden al oido, por idioma (AC1.23.2, U16). Una letra
    #: de aqui obliga a leer el codigo entero y esperar confirmacion.
    confusable: dict[Locale, frozenset[str]]


def _archivo(root: Path | None) -> Path:
    base = root if root is not None else paths.intake_dir()
    return base / _ARCHIVO


@lru_cache(maxsize=1)
def _cargado(ruta: str) -> SpellingAlphabet:
    contenido = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    if not isinstance(contenido, dict):
        msg = f"'{ruta}' no es un mapeo YAML"
        raise SpellingConfigError(msg)

    letras_crudas = contenido.get("letters")
    digitos_crudos = contenido.get("digits")
    conector_crudo = contenido.get("connector")
    if not isinstance(letras_crudas, dict) or not isinstance(digitos_crudos, dict):
        msg = f"'{ruta}' tiene que declarar 'letters' y 'digits' como mapeos"
        raise SpellingConfigError(msg)

    letras: dict[str, LetterEntry] = {}
    nombres: dict[Locale, dict[str, str]] = {"es": {}, "en": {}}
    desambiguaciones: dict[Locale, dict[str, str]] = {"es": {}, "en": {}}
    for letra, por_idioma in letras_crudas.items():
        entrada = LetterEntry(
            letter=letra,
            name={idioma: valores["name"] for idioma, valores in por_idioma.items()},
            disambiguation={
                idioma: valores["disambiguation"] for idioma, valores in por_idioma.items()
            },
        )
        letras[letra] = entrada
        for idioma, nombre in entrada.name.items():
            # Las claves de reconocimiento se pliegan (minusculas, sin
            # tildes) con la misma funcion que `decode_spelled_code` aplica al
            # texto dictado: sin esto, "ábaco" en la tabla nunca encontraria
            # "abaco" en una transcripcion, que nunca lleva tilde.
            nombres[idioma][fold(nombre)] = letra
        for idioma, palabra in entrada.disambiguation.items():
            desambiguaciones[idioma][fold(palabra)] = letra

    digitos: dict[Locale, dict[str, str]] = {"es": {}, "en": {}}
    palabras_digito: dict[Locale, dict[str, str]] = {"es": {}, "en": {}}
    for digito, por_idioma in digitos_crudos.items():
        for idioma, palabra in por_idioma.items():
            digitos[idioma][digito] = palabra
            palabras_digito[idioma][fold(palabra)] = digito

    conector = dict(conector_crudo) if isinstance(conector_crudo, dict) else {}

    # La lista de letras confundibles la anadio U16 (AC1.23.2). Se exige entera:
    # una tabla a la que le faltara un idioma dejaria ese idioma sin lectura de
    # confirmacion y nadie lo notaria, porque no falla, solo deja de proteger.
    confundibles_crudas = contenido.get("confusable")
    if not isinstance(confundibles_crudas, dict) or set(confundibles_crudas) != {"es", "en"}:
        msg = f"'{ruta}' tiene que declarar 'confusable' con los dos idiomas"
        raise SpellingConfigError(msg)
    confundibles: dict[Locale, frozenset[str]] = {
        idioma: frozenset(str(c).upper() for c in letras_del_idioma)
        for idioma, letras_del_idioma in confundibles_crudas.items()
    }

    return SpellingAlphabet(
        letters=letras,
        digit_names=digitos,
        connector=conector,
        letter_names=nombres,
        disambiguations=desambiguaciones,
        digit_words=palabras_digito,
        confusable=confundibles,
    )


def load(root: Path | None = None) -> SpellingAlphabet:
    """La tabla, cargada una vez y compartida (`lru_cache`)."""
    return _cargado(str(_archivo(root)))


def is_confusable(code: str, *, language: Locale, root: Path | None = None) -> bool:
    """Si algun caracter del codigo esta en la lista de letras confundibles.

    Se mira el codigo entero y se devuelve un si o un no, no que caracter: leer
    en voz alta solo la letra dudosa de una placa no ayuda a nadie a comprobarla
    (AC1.23.2).
    """
    confundibles = load(root).confusable[language]
    return any(caracter.upper() in confundibles for caracter in code)


def spell_for_readback(code: str, *, language: Locale, root: Path | None = None) -> str:
    """BR2.5: el codigo, deletreado con la palabra de desambiguacion por caracter.

    Un digito se lee con su nombre, sin palabra de desambiguacion (los digitos
    no llevan una en la tabla): "B de burro, D de dado, seis" y no "B de
    burro, D de dado, seis de ¿que?".
    """
    tabla = load(root)
    conector = tabla.connector.get(language, "")
    partes: list[str] = []
    for caracter in code:
        letra = tabla.letters.get(caracter.upper())
        if letra is not None:
            nombre = letra.name[language]
            desambiguacion = letra.disambiguation[language]
            partes.append(f"{nombre} {conector} {desambiguacion}" if conector else nombre)
            continue
        nombre_digito = tabla.digit_names.get(language, {}).get(caracter)
        partes.append(nombre_digito if nombre_digito is not None else caracter)
    return ", ".join(partes)


__all__ = [
    "LetterEntry",
    "SpellingAlphabet",
    "SpellingConfigError",
    "is_confusable",
    "load",
    "spell_for_readback",
]
