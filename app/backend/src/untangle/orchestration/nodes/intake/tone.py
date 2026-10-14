"""Trato, calma y registro prohibido, comprobados por codigo (BR5.2 a BR5.4, TECH-U11.4, TECH-U11.5).

**FD-U11-4**: el registro prohibido y la forma del turno los juzga el codigo
sobre el texto ya compuesto, nunca el juez -- lo que aqui vive se publica
aunque el juez este descalibrado.

Dos listas versionadas y dos direcciones distintas:

- `tone_signals.yaml` (`paths.intake_dir()`) mide lo que **dice la persona**:
  angustia o llanto (BR5.2) e insultos (BR5.4). Vive junto a la tabla de
  deletreo porque las dos son datos del proyecto y no de una aseguradora
  (convencion 9): reconocer miedo o un insulto no cambia entre Stonecroft,
  Knotwell y Sunmeadow.
- `forbidden_register.yaml` mide lo que **compone la agente**: BR5.3, sobre
  el texto ya compuesto de cada turno.

**El contador de insultos no es un contador que U11 lleve** (FD-U11-1,
generalizado a BR5.4): se recalcula en cada turno contando los insultos de la
transcripcion completa, la misma idea que evita el contador propio de
`blocks.next_block`.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

import yaml

from untangle import paths
from untangle.base import Locale
from untangle.compliance.controls.normalization import fold

_TONE_FILE = "tone_signals.yaml"
_FORBIDDEN_REGISTER_FILE = "forbidden_register.yaml"


class ToneConfigError(ValueError):
    """Un archivo de tono versionado no tiene la forma que se espera."""


class Emotion(StrEnum):
    """Las dos senales de BR5.2. Ninguna otra dispara el reconocimiento."""

    FEAR_OR_CRYING = "fear_or_crying"
    ANGER = "anger"


@dataclass(frozen=True)
class ToneSignals:
    distress: dict[Locale, tuple[str, ...]]
    insults: dict[Locale, tuple[str, ...]]


def _tone_path(root: Path | None) -> Path:
    base = root if root is not None else paths.intake_dir()
    return base / _TONE_FILE


@lru_cache(maxsize=1)
def _tone_loaded(ruta: str) -> ToneSignals:
    contenido = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    if not isinstance(contenido, dict):
        msg = f"'{ruta}' no es un mapeo YAML"
        raise ToneConfigError(msg)
    distress = contenido.get("distress")
    insults = contenido.get("insults")
    if not isinstance(distress, dict) or not isinstance(insults, dict):
        msg = f"'{ruta}' tiene que declarar 'distress' e 'insults' como mapeos"
        raise ToneConfigError(msg)
    return ToneSignals(
        distress={
            idioma: tuple(fold(p) for p in patrones) for idioma, patrones in distress.items()
        },
        insults={idioma: tuple(fold(p) for p in patrones) for idioma, patrones in insults.items()},
    )


def load_tone_signals(root: Path | None = None) -> ToneSignals:
    return _tone_loaded(str(_tone_path(root)))


def _contains_any(folded_text: str, phrases: Sequence[str]) -> bool:
    return any(re.search(rf"\b{re.escape(frase)}\b", folded_text) for frase in phrases)


def detect_emotion(text: str, *, language: Locale, root: Path | None = None) -> Emotion | None:
    """BR5.2: la senal de emocion del turno, o `None`.

    `FEAR_OR_CRYING` manda sobre `ANGER` cuando las dos aparecen: reconocer el
    miedo es siempre seguro; reconocer enojo cuando en realidad hay miedo no
    lo es.
    """
    senales = load_tone_signals(root)
    plegado = fold(text)
    if _contains_any(plegado, senales.distress.get(language, ())):
        return Emotion.FEAR_OR_CRYING
    if _contains_any(plegado, senales.insults.get(language, ())):
        return Emotion.ANGER
    return None


def is_insult(text: str, *, language: Locale, root: Path | None = None) -> bool:
    """BR5.4: si este turno de la persona cuenta como un insulto."""
    senales = load_tone_signals(root)
    return _contains_any(fold(text), senales.insults.get(language, ()))


def count_insults(turns: Sequence[str], *, language: Locale, root: Path | None = None) -> int:
    """BR5.4: cuantos turnos de la persona, en toda la conversacion, insultaron.

    Recalculado sobre la transcripcion completa en cada turno -- no hay un
    contador que U11 lleve y que se pudiera desincronizar al reanudar tras
    `interrupt()` (FD-U11-1, generalizado a BR5.4).
    """
    return sum(1 for turno in turns if is_insult(turno, language=language, root=root))


# --- BR5.3: el registro prohibido de la agente, sobre el texto compuesto ---


@dataclass(frozen=True)
class ForbiddenForm:
    form_id: str
    reason: str
    patterns: dict[Locale, tuple[re.Pattern[str], ...]]


#: Al menos dos diminutivos en un mismo turno son registro prohibido
#: (TECH-U11.4). Uno solo no lo es -- "un ratico" es espanol corriente -- y
#: por eso esto no vive en `forbidden_register.yaml` junto a las frases fijas:
#: es un conteo, no una lista.
_DIMINUTIVE = re.compile(r"\b[a-z]{3,}(?:it|ic)[oa]s?\b")


def _forbidden_register_path(root: Path | None) -> Path:
    base = root if root is not None else paths.intake_dir()
    return base / _FORBIDDEN_REGISTER_FILE


@lru_cache(maxsize=1)
def _forbidden_register_loaded(ruta: str) -> tuple[ForbiddenForm, ...]:
    contenido = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    if not isinstance(contenido, dict) or not isinstance(contenido.get("forms"), list):
        msg = f"'{ruta}' tiene que declarar una lista 'forms'"
        raise ToneConfigError(msg)
    formas: list[ForbiddenForm] = []
    for entrada in contenido["forms"]:
        patrones_crudos = entrada["patterns"]
        # Los patrones no distinguen idioma en el archivo (a diferencia de
        # `tone_signals.yaml`): son expresiones regulares que ya declaran su
        # propio texto en espanol o en ingles, y las dos corren siempre, sobre
        # el turno del idioma que sea -- una frase de otro idioma nunca
        # coincide, asi que no hace falta filtrar por idioma antes.
        compilados = tuple(re.compile(p) for p in patrones_crudos)
        formas.append(
            ForbiddenForm(
                form_id=entrada["id"],
                reason=str(entrada["reason"]).strip(),
                patterns={"es": compilados, "en": compilados},
            )
        )
    return tuple(formas)


def load_forbidden_register(root: Path | None = None) -> tuple[ForbiddenForm, ...]:
    return _forbidden_register_loaded(str(_forbidden_register_path(root)))


def forbidden_register_violation(
    text: str, *, language: Locale, root: Path | None = None
) -> str | None:
    """BR5.3: el identificador de la forma prohibida que aparece, o `None`.

    Comprueba tambien los diminutivos sostenidos (dos o mas en el mismo
    turno), que no es una frase fija sino un conteo.
    """
    # Sobre el texto **plegado**, que es lo que el propio archivo declara en su
    # encabezado y como estan escritos sus patrones. Comparando contra el texto
    # crudo, "¿que mas?" coincidia y "¿qué más?" --la forma con tildes, que es
    # la que AC1.13.4 nombra y la que de verdad se escribe-- no.
    plegado = fold(text)
    for forma in load_forbidden_register(root):
        for patron in forma.patterns.get(language, ()):
            if patron.search(plegado):
                return forma.form_id
    if len(_DIMINUTIVE.findall(plegado)) >= 2:
        return "IR-DIMINUTIVES"
    return None


__all__ = [
    "Emotion",
    "ForbiddenForm",
    "ToneConfigError",
    "ToneSignals",
    "count_insults",
    "detect_emotion",
    "forbidden_register_violation",
    "is_insult",
    "load_forbidden_register",
    "load_tone_signals",
]
