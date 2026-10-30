"""El numero de caso, dicho en voz alta (BR3.7, AC1.23.4).

Un numero dictado de corrido no se anota bien al otro lado del telefono. La
decision D2 fija la forma: **el nombre de la aseguradora y las cifras del contador uno a
uno**, con "zero" y nunca "oh". Desde el 2026-10-09 los digitos van en grupos de tres y el
nombre va en la frase, no delante de los digitos. Desde el 2026-10-30 el contador no tiene
ceros a la izquierda (`AP-29`) y suele ser corto: «dos nueve».

Que nunca se diga "oh" no es una comprobacion de este modulo: los nombres de los
digitos salen de la tabla de U11, donde el cero se llama `zero` y `cero` y no hay
ninguna otra forma. Un modulo que tradujera digitos por su cuenta seria la
segunda tabla que un dia dice "oh".
"""

from __future__ import annotations

from untangle.base import Locale
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration.nodes.intake import spelling

SPOKEN = CopyKey("voice.closing.case_number")


def spell(case_number: str, *, language: Locale) -> str:
    """Las cifras uno a una, en grupos de tres: "cuatro ocho dos, nueve uno tres" (o "dos nueve").

    Una coma entre cada digito hacia que la voz se detuviera seis veces, y el numero
    sonaba lento y con mucha paciencia (2026-10-09). Siguen siendo los digitos uno a
    uno de D2, con una sola pausa en medio, que es como se dicta un numero.
    """
    tabla = spelling.load()
    nombres = [tabla.digit_names[language].get(d, d) for d in case_number if d.isdigit()]
    return ", ".join(" ".join(nombres[i : i + 3]) for i in range(0, len(nombres), 3))


def say(case_number: str, *, insurer: str, language: Locale) -> str:
    """La frase entera del catalogo: la aseguradora por su nombre y los digitos."""
    return copy_api.t(
        SPOKEN, locale=language, insurer=insurer, spoken=spell(case_number, language=language)
    )


__all__ = ["SPOKEN", "say", "spell"]
