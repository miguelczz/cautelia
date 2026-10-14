"""Reconocer que alguien pide el otro idioma en voz alta (BR2.1, BR2.2, AC1.31.1, AC1.31.2).

**Reconoce, y lo que se hace con el reconocimiento lo decide `CallEngine`**: cambiar el
idioma de la llamada --el acuse y la pregunta pendiente, ya en el idioma nuevo-- y reabrir
el reconocedor en el idioma nuevo (`CallRunner._escuchar`). Entre el 2026-10-11 y el
2026-10-13 la llamada no cambiaba: el reconocedor era de un solo idioma por conexion y
cambiar la voz sin cambiar el oido dejaba a la persona hablando con quien no la entendia.

**Lo reconoce codigo y no un modelo**, y es la misma razon por la que la
transicion del grafo tampoco la decide uno (ADR-003): una peticion de cambio de
idioma cambia el estado de la conversacion, y eso se decide con una lista que se
puede leer en un diff.

**Por que no basta el detector.** "In English, please" esta dicho **en ingles**, y
el detector lo leeria como ingles por su cuenta --acertando por accidente--. Pero
"¿me lo puede decir in English?" esta dicho en espanol, y el detector diria
espanol. Los dos son la misma peticion. Si el cambio dependiera solo del detector,
funcionaria en un sentido y no en el otro, y nadie sabria por que.

**Lo que esta lista no hace.** No intenta entender: reconoce. Una peticion que no
este aqui no cambia nada, y lo que pasa entonces es lo de siempre --la
conversacion sigue en su idioma-- que es el lado seguro. Ampliarla es anadir una
linea que se ve en la revision, no afinar un umbral.

**El falso positivo que queda escrito, porque queda.** "in english" y "en espanol"
sueltos estan en la lista porque son como se pide, dicho a secas: "In English,
please". El precio es que "¿como se dice eso in English?" se lee como un pedido y la
llamada pasa al ingles; quien no lo queria lo arregla diciendo "en espanol", y cuesta una
frase de la agente. Por eso nunca se agregaron los espejos --"en ingles" y "in spanish"
sueltos--: con ellos, "mi carro es un Ford, no se si eso se dice igual en ingles" cambiaria
la llamada entera sin ningun criterio detras.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping

from untangle.base import Locale

#: Las formas de pedir cada idioma, ya normalizadas: sin tildes y en minusculas.
#:
#: **Se escriben en los dos idiomas a proposito.** Quien pide el cambio suele
#: decirlo en el idioma al que quiere ir --"in English"-- pero tambien en el que
#: esta hablando --"hablemos en ingles"--, y las dos son la misma peticion.
#:
#: Son frases y no palabras sueltas: "ingles" a secas aparece en "mi carro es un
#: Ford, no se si eso se dice igual en ingles", que no pide nada. Las dos unicas
#: entradas cortas son los literales que la agente promete en AC1.31.4, y su
#: falso positivo esta escrito arriba con su razon.
PETICIONES: Mapping[Locale, tuple[str, ...]] = {
    "en": (
        "in english",
        "switch to english",
        "speak english",
        "hablemos en ingles",
        "puede hablar en ingles",
        "podemos hablar en ingles",
        "prefiero ingles",
        "can you speak english",
        "let's speak english",
        "lets speak english",
    ),
    "es": (
        "en espanol",
        "switch to spanish",
        "speak spanish",
        "hablemos en espanol",
        "puede hablar en espanol",
        "podemos hablar en espanol",
        "prefiero espanol",
        "can you speak spanish",
        "let's speak spanish",
        "lets speak spanish",
    ),
}


#: Decir que **no** se habla un idioma tambien es pedir el otro, y es probablemente
#: la forma mas frecuente de pedirlo: quien no entiende nada rara vez conoce la
#: frase "in English, please". La clave es el idioma al que se va, no el que se
#: nombra.
#:
#: **Se miran antes que `PETICIONES` y cortan.** No es una preferencia de orden:
#: "i do not speak spanish" contiene "speak spanish", asi que sin esta precedencia
#: la frase casaria con los dos idiomas a la vez y la regla de las peticiones
#: contrarias la dejaria sin hacer nada. Lo encontro una frase de prueba.
NEGATIVAS: Mapping[Locale, tuple[str, ...]] = {
    "en": (
        "i do not speak spanish",
        "i dont speak spanish",
        "i don't speak spanish",
        "i cannot speak spanish",
        "i can not speak spanish",
        "i can't speak spanish",
        "i do not understand spanish",
        "i dont understand spanish",
        "i don't understand spanish",
        "no hablo espanol",
        "no entiendo espanol",
        "no entiendo el espanol",
    ),
    "es": (
        "i do not speak english",
        "i dont speak english",
        "i don't speak english",
        "i cannot speak english",
        "i can not speak english",
        "i can't speak english",
        "i do not understand english",
        "i dont understand english",
        "i don't understand english",
        "no hablo ingles",
        "no entiendo ingles",
        "no entiendo el ingles",
    ),
}


#: El nombre del idioma **dicho a secas**: todo el turno es eso, con o sin «por favor».
#:
#: Existe por lo que se oyo en una llamada simulada por el camino real (2026-10-13): con el
#: reconocedor en espanol, «In English, please» llego transcrito como «¿En ingles?» y despues
#: «Please.». El literal que la agente promete nunca llega escrito en ingles cuando quien
#: escucha es un reconocedor de un solo idioma, asi que su espejo tiene que valer.
#:
#: **Solo si es el turno entero**, y por eso no rompe lo que la nota de arriba protege: «no se
#: si eso se dice igual en ingles» sigue sin pedir nada, porque ahi «en ingles» es parte de
#: una frase y no la frase.
A_SECAS: Mapping[Locale, frozenset[str]] = {
    # «en english» y «in ingles» no son descuidos: el reconocedor mezcla los dos idiomas
    # cuando oye uno con el oido del otro (la segunda llamada simulada dio «En English,
    # please.»).
    "en": frozenset(
        {"en ingles", "ingles", "in english", "english", "el ingles", "en english", "in ingles"}
    ),
    "es": frozenset(
        {"in spanish", "spanish", "en espanol", "espanol", "el espanol", "en spanish", "in espanol"}
    ),
}

#: Lo que acompana a la peticion sin cambiarla.
_CORTESIAS = frozenset({"please", "por", "favor", "porfa", "porfavor", "si", "yes", "ok", "okay"})


def _a_secas(normalizado: str) -> str:
    """El turno sin puntuacion ni cortesias, para comparar la frase entera."""
    palabras = "".join(c if c.isalnum() or c.isspace() else " " for c in normalizado).split()
    return " ".join(p for p in palabras if p not in _CORTESIAS)


def _normalizar(texto: str) -> str:
    """Sin tildes, en minusculas y con los espacios colapsados.

    La transcripcion no siempre trae las tildes --depende del proveedor y del
    idioma del modelo-- asi que compararlas seria hacer depender una regla de la
    conducta de un tercero. Se quitan de los dos lados.
    """
    plano = unicodedata.normalize("NFD", texto.casefold())
    sin_tildes = "".join(c for c in plano if unicodedata.category(c) != "Mn")
    return " ".join(sin_tildes.replace("'", "'").split())


def requested(text: str) -> Locale | None:
    """El idioma que este turno pide, o nada si no pide ninguno.

    Se miran **primero las negativas** ("I do not speak Spanish"), porque una de
    ellas contiene dentro una peticion del idioma contrario y sin esa precedencia
    la frase quedaria sin hacer nada.

    Cuando el turno contiene peticiones de los dos --"in English, no, en
    espanol"-- **no se cambia nada**: dos peticiones contrarias en una frase no
    son una peticion, y adivinar cual gana es adivinar. La conversacion sigue en
    su idioma y la persona lo vuelve a decir, que es el lado seguro.
    """
    normalizado = _normalizar(text)
    if not normalizado:
        return None
    negados = _coincidencias(NEGATIVAS, normalizado)
    if negados:
        # Se corta aqui incluso cuando hay dos: quien dice que no habla ninguno de
        # los dos no esta pidiendo ninguno, y la escalera del idioma no atendido
        # es la que responde a eso, no esta lista.
        return negados[0] if len(negados) == 1 else None
    pedidos = _coincidencias(PETICIONES, normalizado)
    if pedidos:
        return pedidos[0] if len(pedidos) == 1 else None
    solo = _a_secas(normalizado)
    return next((idioma for idioma, formas in A_SECAS.items() if solo in formas), None)


def _coincidencias(lista: Mapping[Locale, tuple[str, ...]], normalizado: str) -> tuple[Locale, ...]:
    return tuple(
        idioma for idioma, frases in lista.items() if any(f in normalizado for f in frases)
    )


__all__ = ["A_SECAS", "NEGATIVAS", "PETICIONES", "requested"]
