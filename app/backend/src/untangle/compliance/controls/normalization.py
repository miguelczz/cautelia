"""La normalizacion del texto antes de aplicar los patrones (BR1.3).

Tres transformaciones y solo tres, las de la regla: **minusculas, sin tildes y
espacios colapsados**. Con ellas, «Está cubierto», «esta  CUBIERTO» y «está
cubierto» son el mismo texto para un patron, y un patron no tiene que escribirse
tres veces.

Una cuarta, dicha a la vista porque no esta en la regla: los apostrofos
tipograficos (U+2019, U+2018, U+02BC, U+00B4 y el acento grave) se escriben como
el recto. No es cosmetica. El modelo escribe `I'm` con el tipografico con la
misma naturalidad que con el recto, y un patron de la lista de afirmaciones de
humanidad escrito con uno no veria la frase escrita con el otro: la forma mas
barata de saltarse la guardia seria que el modelo eligiera la comilla.

La normalizacion es la **misma** para la frase y para el patron: los patrones
se escriben ya normalizados, y el cargador rechaza uno que lleve mayusculas o
tildes fuera de sus secuencias de escape, porque nunca podria coincidir.
"""

from __future__ import annotations

import re
import unicodedata

#: Los apostrofos que se escriben como el recto. La lista es cerrada: un
#: caracter nuevo entra aqui a proposito, con su prueba.
_APOSTROFOS = str.maketrans(
    {"\u2019": "'", "\u2018": "'", "\u02bc": "'", "\u00b4": "'", "\u0060": "'"}
)

_ESPACIOS = re.compile(r"\s+")


def strip_accents(text: str) -> str:
    """El texto sin marcas diacriticas: `á` pasa a `a` y `ñ` pasa a `n`.

    Se descompone y se descartan las marcas combinantes, que es lo que hace que
    la regla valga para cualquier letra acentuada y no solo para las cinco
    vocales del espanol.
    """
    descompuesto = unicodedata.normalize("NFD", text)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def fold(text: str) -> str:
    """Minusculas, sin tildes y con el apostrofo recto, sin tocar los espacios.

    Es la mitad de `normalize` que el cargador de patrones usa para comprobar
    que un patron ya esta escrito como el texto que va a mirar: los espacios de
    una expresion regular no se colapsan, porque dentro de una expresion no son
    texto.
    """
    # Primero minusculas y despues sin tildes: pasar a minusculas puede producir
    # una marca combinante (la `İ` turca da `i` mas un punto), y en este orden
    # tambien se va.
    return strip_accents(text.translate(_APOSTROFOS).casefold())


def normalize(text: str) -> str:
    """El texto como lo ven los patrones: minusculas, sin tildes, espacios colapsados."""
    return _ESPACIOS.sub(" ", fold(text)).strip()
