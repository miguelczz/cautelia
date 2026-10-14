"""La lectura de confirmacion de un codigo dictado (BR3.5, AC1.23.2).

Cuando alguien dicta una placa o un numero de poliza por telefono, dos cosas
obligan a leerselo de vuelta antes de anotarlo: que lleve una letra que se
confunde al oido, o que el reconocedor no estuviera seguro de alguna palabra.
Anotar sin confirmar seria guardar una placa que nadie dijo.

**Se lee el codigo entero, no el caracter dudoso.** Leer solo la letra
sospechosa de una placa no ayuda a nadie a comprobarla: quien escucha necesita
oir la placa completa para reconocer la suya.

**La tabla es la de U11 y no una copia.** `spell_for_readback` existia
versionada y con sus pruebas desde entonces y **no la llamaba nadie en
produccion**: esta unidad es su primer consumidor. La lista de letras
confundibles se anadio a esa misma tabla, no a un archivo aparte, porque dos
tablas sobre como suenan las letras se separan.
"""

from __future__ import annotations

from dataclasses import dataclass

from untangle.base import Locale
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration.nodes.intake import confirmation, spelling
from untangle.providers.ports import Transcript

CONFIRM = CopyKey("voice.readback.confirm")

#: Por debajo de esto, una palabra del codigo no se da por oida. Es el mismo piso
#: que usa la escalera de "no le entendi", y a proposito: dos umbrales distintos
#: para la misma duda se separan.
DEFAULT_CONFIDENCE_FLOOR = 0.6


@dataclass(frozen=True)
class Readback:
    """El codigo deletreado y la frase que lo lee."""

    code: str
    spelled: str
    copy_key: CopyKey
    text: str


def needs_readback(
    code: str,
    *,
    language: Locale,
    transcript: Transcript | None = None,
    confidence_floor: float = DEFAULT_CONFIDENCE_FLOOR,
) -> bool:
    """Si este codigo hay que leerlo antes de anotarlo (AC1.23.2).

    Dos condiciones y basta una: una letra de la lista versionada, o una palabra
    por debajo del umbral. La segunda mira **la peor palabra** y no el promedio,
    igual que la escalera de "no le entendi"; una palabra sin confianza no cuenta
    en contra, porque nula significa "el proveedor no lo dijo".
    """
    if spelling.is_confusable(code, language=language):
        return True
    if transcript is None:
        return False
    confianzas = [p.confidence for p in transcript.words if p.confidence is not None]
    return bool(confianzas) and min(confianzas) < confidence_floor


def build(code: str, *, language: Locale) -> Readback:
    """El codigo entero, deletreado con la tabla de U11, dentro de su frase."""
    deletreado = spelling.spell_for_readback(code, language=language)
    return Readback(
        code=code,
        spelled=deletreado,
        copy_key=CONFIRM,
        text=copy_api.t(CONFIRM, locale=language, spelled=deletreado),
    )


def accepted(answer: str, *, language: Locale) -> bool:
    """Si la respuesta confirma el codigo leido.

    Es el reconocedor de U11 y no uno propio: BR3.1 de aquella unidad exige un si
    explicito, y una segunda lista de formas de decir que si empezaria a adivinar
    donde la regla pide certeza. Callar no confirma: lo que no es un si es un no.
    """
    return confirmation.is_affirmative(answer, language=language)


__all__ = [
    "CONFIRM",
    "DEFAULT_CONFIDENCE_FLOOR",
    "Readback",
    "accepted",
    "build",
    "needs_readback",
]
