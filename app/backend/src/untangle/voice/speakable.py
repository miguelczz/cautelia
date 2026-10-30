"""Lo que se manda a sintetizar: los codigos dichos como los diria una persona (2026-10-11).

El sintetizador lee "POL-23" como una palabra y un numero, "ABC123" como una palabra
inventada y "AP-29" como dos letras, un guion y un numero: nadie dicta asi. Una persona los
dice **digito a digito, de a tres, con una pausa**: "póliza dos tres". Es la forma de D2 para
el numero de caso (`case_number.spell`) y este modulo la extiende a lo que faltaba.

| Escrito | Español | Ingles |
| --- | --- | --- |
| `POL-23` | póliza dos tres | policy two three |
| `AP-29` | a pe, dos nueve | A P, two nine |
| `ABC123` | a be ce, uno dos tres | A B C, one two three |
| `2015` | 2015 | 2015 |

**Un ano se queda como numero**: el sintetizador lo lee bien como ano, y partirlo en
digitos lo dejaria irreconocible. Por eso nada de lo de aqui toca un numero suelto, y
una placa o un codigo solo se reconoce por **su forma** (tres letras mayusculas y
digitos), nunca por ser digitos.

**Un solo punto, justo antes de sintetizar**: `CallRunner._decir` pide a
`CallEngine.spoken` el texto que suena. Lo que se muestra en pantalla y lo que se guarda en la
transcripcion siguen con el formato escrito: la persona lee `POL-23`, no dos
palabras.

**Reusa lo que ya existe.** Los digitos y el agrupado de tres son los de
`case_number.spell`, y los nombres de las letras en español son los de la tabla de
deletreo de U11 (`spelling_alphabet.yaml`), la misma con la que se lee una placa de
vuelta. En ingles las letras van como mayusculas separadas, que es como los
sintetizadores ingleses dicen una sigla.

**La palabra "póliza" no se repite**: en "tu póliza POL-23" el prefijo se queda
mudo y suenan solo las cifras. La palabra sale del catalogo, como todo lo que se oye.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from untangle.base import Locale
from untangle.compliance.controls.normalization import fold
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration.nodes.intake import spelling
from untangle.voice import case_number

SPOKEN_POLICY = CopyKey("voice.spoken.policy")

#: El prefijo de un numero de poliza. Un numero de caso lleva el de su aseguradora (dos
#: letras), asi que "POL" es la unica que se dice como palabra.
POLICY_PREFIX = "POL"

#: Si las letras se dicen por su nombre de la tabla de deletreo ("ese te o") o como
#: mayusculas separadas ("S T O"). Es un dato por idioma y no una rama: lo que cambia es
#: como suena cada sintetizador, no la logica.
_LETRAS_POR_SU_NOMBRE: Mapping[Locale, bool] = {"es": True, "en": False}

#: Una pausa entre tramos, la misma coma que ya separa los grupos de cifras.
_PAUSA = ", "

#: `POL-23` o `AP-29`: el numero de poliza (tres letras, dos cifras) o el de caso (dos letras,
#: de una a seis cifras sin cero a la izquierda). Si no se limita a la forma de cada uno,
#: `ZNX-9706` (una placa) se leeria como un codigo.
_CODIGO = r"(?:(?P<prefijo>POL)-(?P<cifras>\d{2})|(?P<prefijo_de_caso>[A-Z]{2})-(?P<cifras_de_caso>[1-9]\d{0,5}))"
#: Las dos formas de placa que reconoce U11: colombiana o estadounidense.
_PLACA = r"(?P<placa>[A-Z]{3}(?:\d{3}|\d{2}[A-Z]|\d{4})|\d[A-Z]{3}\d{3})"
_PATRON = re.compile(rf"(?<![\w-])(?:{_CODIGO}|{_PLACA})(?![\w-])")

#: Cuantas palabras hacia atras se mira si la frase ya dijo "póliza": "tu póliza es
#: POL-23" lo dijo tres palabras antes.
_PALABRAS_HACIA_ATRAS = 5
_PALABRAS_DE_POLIZA = frozenset({"poliza", "polizas", "policy", "policies"})


def _letras(letras: str, *, language: Locale) -> str:
    """Las letras una a una, por su nombre o como mayusculas, segun el idioma."""
    if not _LETRAS_POR_SU_NOMBRE[language]:
        return " ".join(letras)
    tabla = spelling.load().letters
    return " ".join(tabla[letra].name[language] if letra in tabla else letra for letra in letras)


def _cifras(cifras: str, *, language: Locale) -> str:
    tabla = spelling.load().digit_names[language]
    return " ".join(tabla.get(d, d) for d in cifras)


def _placa(placa: str, *, language: Locale) -> str:
    """Una placa por tramos de letras y de digitos, con una pausa entre tramos."""
    tramos = re.findall(r"[A-Z]+|\d+", placa)
    return _PAUSA.join(
        _cifras(t, language=language) if t.isdigit() else _letras(t, language=language)
        for t in tramos
    )


def _codigo(prefijo: str, cifras: str, *, antes: str, language: Locale) -> str:
    agrupadas = case_number.spell(cifras, language=language)
    if prefijo != POLICY_PREFIX:
        return f"{_letras(prefijo, language=language)}{_PAUSA}{agrupadas}"
    cerca = re.findall(r"\w+", fold(antes))[-_PALABRAS_HACIA_ATRAS:]
    if _PALABRAS_DE_POLIZA.intersection(cerca):
        return agrupadas
    return f"{copy_api.t(SPOKEN_POLICY, locale=language)} {agrupadas}"


def for_speech(text: str, *, language: Locale) -> str:
    """El texto como suena. Lo que no es un codigo ni una placa pasa tal cual."""

    def reemplazo(coincidencia: re.Match[str]) -> str:
        if coincidencia["placa"] is not None:
            return _placa(coincidencia["placa"], language=language)
        if coincidencia["prefijo"] is not None:
            return _codigo(
                coincidencia["prefijo"],
                coincidencia["cifras"],
                antes=text[: coincidencia.start()],
                language=language,
            )
        return _codigo(
            coincidencia["prefijo_de_caso"],
            coincidencia["cifras_de_caso"],
            antes=text[: coincidencia.start()],
            language=language,
        )

    return _PATRON.sub(reemplazo, text)


__all__ = ["POLICY_PREFIX", "SPOKEN_POLICY", "for_speech"]
