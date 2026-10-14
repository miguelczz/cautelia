"""El detector: los dos juegos, el respaldo y la resolucion de solapes.

**Un motor con los dos modelos residentes**, no uno que se reconfigure por
llamada (NFRD-U3-1). Reconfigurarlo reintroduce la posibilidad de que corra un
solo juego, que es exactamente el agujero de RT-15: dictar el dato en el otro
idioma. Cuesta unos megabytes residentes y los ahorra en cada llamada.

**Los dos juegos corren en cada llamada**, sea cual sea el idioma del turno
(BR2.9). Es el control, no una optimizacion rechazada: cargar solo el juego del
turno es la forma natural de escribirlo, y queda escrito aqui porque es el atajo
que alguien tomara al optimizar. El idioma del turno decide en que idioma se
escribe la etiqueta, no que se busca.

Fallar cerrado atraviesa todo el modulo (BR1.7, SEC-U3.10): si los modelos o los
reconocedores no cargan, esto levanta; si una llamada falla, levanta. No existe
ninguna ruta en la que un fallo del detector produzca texto sin tapar.
"""

from __future__ import annotations

import functools
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import regex
import tldextract
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import EmailRecognizer, SpacyRecognizer

from untangle import observability
from untangle.base import Locale
from untangle.compliance.redaction.recognizers import loading
from untangle.compliance.redaction.recognizers.models import (
    FORMAT_TYPES,
    DetectedEntity,
    EntityType,
    FallbackRule,
    Mechanism,
    Recognizer,
    RecognizerSet,
    SelfIdentificationRule,
)

#: Los modelos de spaCy por idioma. Fijados por URL con su hash en el lockfile e
#: instalados por `mise run models:install`; nunca por `spacy download`, que es
#: una resolucion libre (INF-U3-1).
MODELOS: dict[Locale, str] = {"es": "es_core_news_md", "en": "en_core_web_md"}

#: El comando que los instala. Aparece en el mensaje de error a proposito: un
#: `ImportError` de spaCy a mitad de una prueba no le dice a nadie que hacer.
COMANDO_DE_MODELOS = "mise run models:install"

#: La lista publica de dominios, leida **solo** de la copia que trae `tldextract`.
#: Sin `suffix_list_urls`, la biblioteca nunca sale a internet a buscarla: la
#: primera vez que el reconocedor de correos validaba un dominio en una maquina
#: sin cache, intentaba descargarla de publicsuffix.org. La redaccion corre en
#: cada punto de salida y no puede depender de la red ni avisar a un tercero de
#: que se esta procesando un correo (C-13, enmienda del 2026-09-21).
_DOMINIOS_SIN_RED = tldextract.TLDExtract(suffix_list_urls=())


#: Nombres publicos que no son datos de nadie: las aseguradoras de la demo, la agente y
#: la marca. Los instala la raiz de composicion desde la configuracion de cada
#: aseguradora, para que este modulo no nombre ninguna. Sin esto, "Autos Poblado" en
#: una respuesta de la agente se guardaba como "[LUGAR 1]" (visto el 2026-10-08).
_TERMINOS_PUBLICOS: frozenset[str] = frozenset()

#: Las palabras con que alguien se presenta, que la regla de autoidentificacion incluye
#: en su tramo: "Soy Catalina" es un nombre publico aunque "soy" no lo sea.
_PRESENTACION: frozenset[str] = frozenset(
    {
        "soy",
        "me",
        "llamo",
        "mi",
        "nombre",
        "es",
        "habla",
        "le",
        "i'm",
        "i",
        "am",
        "my",
        "name",
        "is",
        "this",
    }
)


def _es_nombre_publico(text: str, hallazgo: DetectedEntity) -> bool:
    """Si el tramo es solo un nombre publico (o varios): "Autos Poblado", "Catalina"."""
    if not _TERMINOS_PUBLICOS:
        return False
    # El posesivo del ingles no cambia de quien se habla: "Autos Poblado's AI
    # assistant" se guardaba como "[NAME 1] AI assistant" (apertura de la llamada).
    palabras = [
        p.strip(_PUNTUACION_DE_SALUDO).removesuffix("'s").removesuffix("\u2019s")
        for p in text[hallazgo.start : hallazgo.end].casefold().split()
    ]
    nombre = [p for p in palabras if p not in _PRESENTACION]
    return bool(nombre) and all(p in _TERMINOS_PUBLICOS for p in nombre)


#: Las palabras de nuestras propias frases: todo lo que el catalogo de textos puede
#: decir, en los dos idiomas (2026-10-10). Las instala la raiz de composicion, igual
#: que los nombres publicos. Solo cuentan para el texto que **compone la agente**
#: (`detect(..., composed=True)`): el reconocedor de nombres en espanol etiqueta
#: como persona el verbo con que arranca una frase --"Encontre", "Confirmo"--, y sin
#: esto habia que elegir entre mutilar la frase o guardarla entera sin tapar los
#: datos que lleva dentro.
_VOCABULARIO_PROPIO: frozenset[str] = frozenset()

#: Los tipos que salen de un modelo de lenguaje y no de una forma escrita. Solo a
#: estos se les perdona un tramo hecho de palabras nuestras: una poliza, una placa,
#: una cedula, un telefono o un correo se tapan siempre.
_TIPOS_DE_MODELO: frozenset[EntityType] = frozenset({EntityType.PERSON, EntityType.LOCATION})

#: La forma de un numero de caso: el prefijo de la aseguradora y seis digitos. El
#: de poliza (`POL-`) no entra: ese si es un dato, y lo tapa su propio reconocedor.
_NUMERO_DE_CASO = regex.compile(r"(?!POL-)[A-Z]{3}-\d{6}")

_SEPARADORES_DE_PALABRA = regex.compile(r"[^\p{L}\p{M}\p{N}'\u2019\-]+")


def _palabras(texto: str) -> list[str]:
    return [p for p in _SEPARADORES_DE_PALABRA.split(texto.casefold()) if p]


def _es_solo_vocabulario_propio(text: str, hallazgo: DetectedEntity) -> bool:
    """Si un hallazgo de nombre o de lugar esta hecho solo de palabras nuestras."""
    if hallazgo.entity_type not in _TIPOS_DE_MODELO:
        return False
    if _NUMERO_DE_CASO.fullmatch(text[hallazgo.start : hallazgo.end].strip()):
        # El numero del propio caso, que la agente dice en sus avisos: el
        # reconocedor de nombres lo etiqueta como persona **segun que digitos
        # traiga**, y el aviso de la decision se guardaba "tu caso [NOMBRE 1]".
        # Salio en la revision de GitHub del 2026-10-11 y no en cuatro corridas
        # locales: los numeros de caso son al azar. No es un dato personal, y que
        # numero de caso puede salir lo decide la guardia de salida, no esto.
        return True
    palabras = _palabras(text[hallazgo.start : hallazgo.end])
    conocidas = _VOCABULARIO_PROPIO | _TERMINOS_PUBLICOS
    return bool(palabras) and all(p in conocidas for p in palabras)


def install_own_vocabulary(texts: Iterable[str]) -> None:
    """Las palabras de las frases del catalogo, sin sus huecos `{...}`."""
    global _VOCABULARIO_PROPIO
    sin_huecos = (regex.sub(r"\{[^{}]*\}", " ", texto) for texto in texts)
    _VOCABULARIO_PROPIO = frozenset(p for texto in sin_huecos for p in _palabras(texto))


def install_public_terms(terms: Iterable[str]) -> None:
    """Las palabras de los nombres publicos, que un hallazgo nunca tapa si es solo eso."""
    global _TERMINOS_PUBLICOS
    _TERMINOS_PUBLICOS = frozenset(
        palabra.casefold() for termino in terms for palabra in termino.split() if palabra
    )


class OfflineEmailRecognizer(EmailRecognizer):
    """El reconocedor de correos del motor, validando el dominio sin red.

    Hace lo mismo que el original --el dominio tiene que tener un sufijo publico
    conocido--, pero con la lista local de `_DOMINIOS_SIN_RED`. Conserva el
    nombre `EmailRecognizer`: el detector solo acepta hallazgos de reconocedores
    declarados, y los archivos declaran ese nombre.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "EmailRecognizer")
        super().__init__(**kwargs)

    def validate_result(self, pattern_text: str) -> bool:
        return _DOMINIOS_SIN_RED(pattern_text).fqdn != ""


#: Los reconocedores del motor que este detector admite, por su nombre declarado.
#: La lista es explicita: un nombre que no este aqui **no carga**, en vez de
#: quedarse sin reconocedor en silencio. `EmailRecognizer` apunta a la version
#: sin red: el nombre declarado en los archivos de reconocedores no cambia.
RECONOCEDORES_DEL_MOTOR: dict[str, Any] = {
    "SpacyRecognizer": SpacyRecognizer,
    "EmailRecognizer": OfflineEmailRecognizer,
}

# Las banderas con las que corren nuestros patrones. **Sin ignorar mayusculas**,
# que es lo que trae el motor por defecto: con ellas activadas, `[A-Z]{3}\d{3}`
# taparia cualquier palabra de tres letras seguida de tres digitos. Donde hace
# falta ignorar mayusculas se declara en el patron, con `(?i:...)`, que se ve al
# leerlo.
BANDERAS = regex.DOTALL | regex.MULTILINE

#: Digitos seguidos, para la regla de respaldo.
_TIRADA_DE_DIGITOS = regex.compile(r"\d+")

#: Una palabra de un nombre: empieza por mayuscula, admite tildes y un apostrofo o
#: un guion **dentro** ("O'Brien", "Ochoa-Henao"), y nunca digitos: asi
#: "POL-173620" no se convierte en un apellido.
_PALABRA_DE_NOMBRE = r"\p{Lu}[\p{L}\p{M}]*(?:['\u2019\-]\p{L}[\p{L}\p{M}]*)*"

#: Lo que separa las partes de una palabra de nombre: el apostrofo y el guion.
_PARTES_DE_PALABRA = regex.compile(r"['\u2019\-]")

#: Lo que rodea a un saludo transcrito («¡hola!», «hola,») y no es parte de el.
_PUNTUACION_DE_SALUDO = ",.;:!?¡¿"

#: Cuanto puntua un hallazgo de la regla de autoidentificacion. Por debajo del que
#: da el modelo a una persona: cuando los dos encuentran el mismo trozo, el
#: credito es del modelo, y la fila del modelo en el informe sigue diciendo si el
#: modelo funciona. La regla solo se lleva el credito de lo que el modelo no vio.
CONFIANZA_DE_AUTOIDENTIFICACION = 0.6

#: **Que corre del juego del otro idioma.** Los reconocedores **por formato** de
#: los dos idiomas corren siempre, sea cual sea el idioma del turno: es el
#: control de BR2.9 y lo que cierra el agujero de RT-15, porque una cedula
#: dictada en espanol tiene una forma escrita que solo el patron espanol conoce.
#: Los que vienen del **modelo de lenguaje** corren solo en el idioma del turno.
#:
#: La diferencia entre los dos casos es que un formato es del idioma y un nombre
#: no: "Carlos Mendoza" se escribe igual en un turno en ingles, y lo que cambia
#: no es la forma del dato sino que modelo lo lee bien. Correr el modelo ingles
#: sobre prosa espanola no anade ninguna forma que se nos escapara; anade ruido.
#:
#: **La regla de autoidentificacion tambien corre con los dos idiomas.** No es un
#: modelo de lenguaje: busca una frase declarada --"my name is", "me llamo"-- y la
#: secuencia con mayuscula que la sigue, asi que correrla sobre el otro idioma no
#: anade el ruido que esta acotacion evita. Y tiene que correr: "Me llamo Megan
#: Hughes" en un turno ingles es la misma evasion que RT-15 aplicada a un nombre.
#:
#: **Medido** al construir esta unidad, sobre tres turnos realistas en espanol:
#: sin acotar, ocho hallazgos falsos; con la acotacion, uno. Los siete que
#: desaparecen son todos del juego ingles --"Iba por la avenida", "dio su
#: telefono", "dijo que su aseguradora", "misma mia", "si el deducible", "lo
#: cobran", "si lo cubre la"--; el que queda, "Necesito", es una falsa deteccion
#: del propio modelo espanol y no del cruce. Los cinco hallazgos verdaderos son
#: **exactamente los mismos** en los dos casos: el juego ingles no aporto ni uno
#: que el espanol no tuviera ya.
#:
#: Esto **acota** la letra del Flujo 1 paso 4, que nombra tambien los del
#: detector de base entre los que corren de los dos idiomas. No toca ninguna
#: compuerta: los tipos de RT-14 y RT-15 --placa, cedula, telefono, poliza y
#: VIN-- son todos por formato, y sus casos sembrados pasan igual. Queda declarado en `code-summary.md` con su
#: medicion, para que sea una decision a la vista y no un atajo enterrado aqui.
PASADA_DEL_OTRO_IDIOMA = "solo por formato"


class ModelsMissingError(RuntimeError):
    """Falta un modelo de lenguaje. El mensaje nombra cual y como instalarlo."""


class DetectionError(RuntimeError):
    """El detector no pudo terminar su trabajo.

    Se levanta en vez de devolver texto: si la redaccion no se puede ejecutar, no
    sale texto (BR1.7). El punto de salida responde con la clave de degradacion
    del catalogo, y queda un valor distinguible en el caso y un evento en la
    traza con la causa.
    """


def _sin_tildes(texto: str) -> str:
    """El texto en minusculas y sin tildes, para buscar frases de contexto.

    Quien dicta escribe "numero" y quien teclea escribe "numero" o "numero" con
    tilde. Normalizar aqui --y solo para **buscar la frase**, nunca para lo que
    sale-- evita duplicar cada frase de contexto en dos grafias.
    """
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def _entidades_declaradas(juego: RecognizerSet, *, solo_por_formato: bool = False) -> list[str]:
    """Los nombres de entidad que este idioma declara, y solo esos.

    Se le pasan al motor para que no devuelva las de sus reconocedores por
    defecto --tarjetas, criptomonedas, fechas-- que no estan declaradas aqui y
    que nadie podria atribuir a un reconocedor de este archivo.

    Con `solo_por_formato`, deja fuera los que vienen del modelo de lenguaje.
    Es lo que se le pide al juego del **otro** idioma: ver `PASADA_DEL_OTRO_IDIOMA`.
    """
    nombres = set()
    for reconocedor in juego.recognizers:
        if reconocedor.provided_by is None:
            nombres.add(reconocedor.entity_type.engine_entity)
        elif not (solo_por_formato and reconocedor.mechanism is Mechanism.MODEL):
            nombres.add(reconocedor.provided_by.entity)
    return sorted(nombres)


def _patron_del_motor(reconocedor: Recognizer, language: Locale) -> PatternRecognizer:
    """Un reconocedor propio, tal como lo declara su archivo."""
    return PatternRecognizer(
        supported_entity=reconocedor.entity_type.engine_entity,
        name=reconocedor.id,
        supported_language=language,
        patterns=[
            Pattern(name=patron.form.value, regex=patron.regex, score=patron.score)
            for patron in reconocedor.patterns
        ],
        context=list(reconocedor.context),
        global_regex_flags=BANDERAS,
    )


def _construir_registro(juegos: dict[Locale, RecognizerSet]) -> RecognizerRegistry:
    """El registro con **exactamente** lo que declaran los dos archivos.

    Se construye a mano y no con los reconocedores por defecto del motor: los
    por defecto traen dos docenas de entidades que nadie declaro, y un hallazgo
    que no se puede atribuir a una fila del archivo no se puede medir ni
    auditar.
    """
    registro = RecognizerRegistry(supported_languages=sorted(juegos))

    for idioma, juego in juegos.items():
        del_motor: dict[str, list[str]] = {}
        for reconocedor in juego.recognizers:
            if reconocedor.patterns:
                registro.add_recognizer(_patron_del_motor(reconocedor, idioma))
                continue

            procedencia = reconocedor.provided_by
            assert procedencia is not None  # noqa: S101 -- el modelo lo garantiza
            if procedencia.recognizer not in RECONOCEDORES_DEL_MOTOR:
                msg = (
                    f"el reconocedor '{reconocedor.id}' dice venir de "
                    f"'{procedencia.recognizer}', que este detector no conoce. Los "
                    f"admitidos son {sorted(RECONOCEDORES_DEL_MOTOR)}"
                )
                raise loading.RecognizerLoadError(msg)
            del_motor.setdefault(procedencia.recognizer, []).append(procedencia.entity)

        for nombre, entidades in sorted(del_motor.items()):
            clase = RECONOCEDORES_DEL_MOTOR[nombre]
            if nombre == "SpacyRecognizer":
                registro.add_recognizer(
                    clase(supported_language=idioma, supported_entities=sorted(entidades))
                )
            else:
                registro.add_recognizer(clase(supported_language=idioma))

    return registro


def _tabla_de_atribucion(
    juegos: dict[Locale, RecognizerSet],
) -> dict[tuple[str, str, str], Recognizer]:
    """De lo que devuelve el motor a la fila del archivo que lo declara.

    La clave es `(idioma, nombre del reconocedor, entidad)`, y hacen falta las
    tres: un mismo reconocedor del motor aporta varias entidades --nombre y
    lugar salen del mismo--, y el mismo nombre existe en los dos idiomas. Es lo
    que permite decir **que reconocedor encontro cada hallazgo**, que es lo que
    hace visible un juego roto detras del otro (BR2.9, SEC-U3.9).
    """
    tabla: dict[tuple[str, str, str], Recognizer] = {}
    for idioma, juego in juegos.items():
        for reconocedor in juego.recognizers:
            if reconocedor.provided_by is not None:
                clave = (idioma, reconocedor.provided_by.recognizer, reconocedor.provided_by.entity)
            else:
                clave = (idioma, reconocedor.id, reconocedor.entity_type.engine_entity)
            tabla[clave] = reconocedor
    return tabla


def _especificidad(entity_type: EntityType) -> int:
    """Cuan especifico es un tipo. Menor es mas especifico.

    Tres escalones: los tipos que encuentran los reconocedores por formato (los
    cuatro propios del dominio y el VIN), los del detector de base y la regla de
    autoidentificacion, y lo que solo atrapo el respaldo. Decide un solape **entre hallazgos
    del mismo tamano**, no contra uno mas largo: lo que nunca se hace es dejar a
    la vista un caracter que alguien reclamo.
    """
    if entity_type in FORMAT_TYPES:
        return 0
    if entity_type is EntityType.UNCLASSIFIED:
        return 2
    return 1


def resolve_overlaps(
    text: str,
    hallazgos: Iterable[DetectedEntity],
    *,
    turno: Locale,
    context_words: frozenset[str] = frozenset(),
) -> tuple[DetectedEntity, ...]:
    """Deja un solo hallazgo por cada trozo de texto (decision FD-U3-5).

    **Gana el mas especifico**, y el que pierde se queda con lo que sobra. Los
    dos escalones importan y son distintos:

    - *Gana el mas especifico*: una poliza dentro de una tirada que el respaldo
      tambien reclamo se tapa como poliza y no como dato sin clasificar, y la
      medicion por tipo no pierde un acierto real. Lo mismo pasa cuando el
      modelo de lenguaje se traga el numero dentro de un nombre o un lugar: el
      tipo propio del dominio manda, porque es el que el reconocedor **sabe** lo
      que es.
    - *El que pierde se queda con lo que sobra*: si el perdedor se descartara
      entero, los caracteres que solo el reclamaba quedarian a la vista. Tapar
      de mas es el lado seguro del error; dejar a la vista media frase que el
      modelo habia marcado, no.

    Orden de preferencia: especificidad, luego el mas largo, luego el de mayor
    puntaje, **luego el reconocedor del idioma del turno**, y a igualdad el
    identificador y la posicion, para que dos corridas del mismo commit
    resuelvan igual.

    El escalon del idioma del turno no es cosmetico: cuando los dos juegos
    encuentran el mismo trozo, el credito tiene que ser del juego del turno. Sin
    el, un nombre espanol en un turno espanol se le atribuiria al juego ingles
    solo porque `en-` va antes que `es-` en el alfabeto, y el informe por idioma
    diria que el espanol no encuentra nada (P12). Cuando el trozo lo encuentra
    **solo** el otro juego --que es el caso de RT-15-- el credito sigue siendo
    suyo, que es justo lo que esa sonda exige.

    **El respaldo nunca gana un solape.** Es el escalon menos especifico de los
    tres, y ademas solo reclama lo que nadie reclamo. La garantia esta en dos
    sitios a proposito: una que depende de uno solo deja de serlo el dia que
    alguien mueve ese sitio.
    """
    candidatos = sorted(
        hallazgos,
        key=lambda h: (
            _especificidad(h.entity_type),
            -h.length,
            -h.confidence,
            0 if h.recognizer_id.startswith(f"{turno}-") else 1,
            h.recognizer_id,
            h.start,
        ),
    )

    elegidos: list[DetectedEntity] = []
    for candidato in candidatos:
        for inicio, fin in _trozos_libres(candidato.start, candidato.end, elegidos):
            recortado = _recortar(text, inicio, fin)
            if recortado is None:
                continue
            trozo = candidato.model_copy(update={"start": recortado[0], "end": recortado[1]})
            if _sobra_que_era_la_palabra_de_contexto(text, candidato, trozo, context_words):
                continue
            elegidos.append(trozo)

    return tuple(sorted(elegidos, key=lambda h: (h.start, h.end)))


def _sobra_que_era_la_palabra_de_contexto(
    text: str,
    candidato: DetectedEntity,
    trozo: DetectedEntity,
    context_words: frozenset[str],
) -> bool:
    """Si lo que le sobro al perdedor es la palabra que delataba el dato.

    Pasa de verdad y se midio al construir la unidad: el modelo de lenguaje
    espanol marca "placa ABC123" entero como un lugar, la placa --que es mas
    especifica-- se queda con `ABC123`, y al perdedor le sobra `placa`. Taparla
    daria `[LUGAR 1] [PLACA 1]`, que es ruido sobre el texto que lee una persona.

    Se descarta **solo** cuando se cumple todo esto, y cada condicion importa:

    - es un **sobrante**, no un hallazgo entero: ya sabemos que otro hallazgo mas
      especifico se quedo con el dato de al lado;
    - el perdedor venia del detector de base, no de un patron propio;
    - lo que sobra es, entero, una palabra de contexto **declarada** en el
      archivo de reconocedores.

    Esa tercera condicion es la que lo hace seguro: una palabra de contexto la
    declaramos nosotros como marca de formato --"placa", "cedula", "poliza"-- y
    por construccion no es el nombre de nadie ni una direccion. Lo que se
    arriesga es dejar sin tapar a una persona que se llame exactamente como una
    de esas palabras y sin nada mas alrededor; lo que se gana es que la
    transcripcion de cada turno del dominio se lea.
    """
    if not context_words or trozo.length == candidato.length:
        return False
    if _especificidad(candidato.entity_type) != 1:
        return False
    return _sin_tildes(text[trozo.start : trozo.end]).strip() in context_words


def _recortar(text: str, inicio: int, fin: int) -> tuple[int, int] | None:
    """Quita los espacios de los bordes de un trozo. `None` si no queda nada.

    Solo espacios: recortar puntuacion podria dejar a la vista el punto que
    separa dos grupos de una cedula, y entonces el recorte estaria ensenando
    parte del dato en vez de limpiar un borde.
    """
    while inicio < fin and text[inicio].isspace():
        inicio += 1
    while fin > inicio and text[fin - 1].isspace():
        fin -= 1
    return (inicio, fin) if fin > inicio else None


def fallback_findings(
    text: str, rule: FallbackRule, claimed: Sequence[DetectedEntity]
) -> tuple[DetectedEntity, ...]:
    """La regla de respaldo: digitos en contexto que nadie reclamo (BR2.5).

    Corre **despues** de los reconocedores y solo sobre lo que quedo libre. Si
    una tirada de digitos contiene un trozo ya reclamado, se parte y se queda
    solo con lo que sobra: asi el respaldo no puede ganarle a un reconocedor, y
    tampoco deja al aire la cola que el reconocedor no cubria.

    Cubre el formato que nadie previo, que es por donde se escapan las cosas. El
    costo aceptado es alguna redaccion de mas (decision FD-U3-9).
    """
    normalizado = _sin_tildes(text)
    frases = [_sin_tildes(frase) for frase in rule.context_phrases]

    hallazgos: list[DetectedEntity] = []
    for tirada in _TIRADA_DE_DIGITOS.finditer(text):
        if tirada.end() - tirada.start() < rule.min_digits:
            continue
        if not _hay_contexto(normalizado, frases, tirada.start(), tirada.end(), rule.window):
            continue
        for inicio, fin in _trozos_libres(tirada.start(), tirada.end(), claimed):
            if fin - inicio < rule.min_digits:
                continue
            hallazgos.append(
                DetectedEntity(
                    entity_type=rule.entity_type,
                    start=inicio,
                    end=fin,
                    recognizer_id=rule.id,
                    confidence=0.4,
                )
            )
    return tuple(hallazgos)


def _frase_como_patron(frase: str) -> str:
    """Una frase de autoidentificacion como patron: espacios flexibles y los dos apostrofos."""
    # Primero se lleva el apostrofo tipografico al recto, y despues el recto se
    # vuelve la clase de los dos: en el otro orden, el segundo reemplazo volveria
    # a tocar el apostrofo que el primero acaba de meter en la clase.
    rectas = frase.replace("\u2019", "'")
    palabras = [regex.escape(palabra, special_only=True) for palabra in rectas.split()]
    return r"\s+".join(palabras).replace("'", "['\u2019]")


@functools.lru_cache(maxsize=8)
def _patron_de_autoidentificacion(cues: tuple[str, ...]) -> regex.Pattern[str]:
    """El patron de una regla: una de sus frases y la secuencia con mayuscula que sigue.

    Las frases se prueban de la mas larga a la mas corta, para que "le habla" gane
    a "habla" en el mismo sitio. La frase no distingue mayusculas; el nombre si,
    y es lo que lo hace nombre: sin mayuscula no hay secuencia.
    """
    frases = sorted((_frase_como_patron(frase) for frase in cues), key=len, reverse=True)
    return regex.compile(
        rf"(?<![\p{{L}}\p{{N}}])(?i:{'|'.join(frases)})\s+"
        rf"(?P<name>{_PALABRA_DE_NOMBRE}(?:[ \t]+{_PALABRA_DE_NOMBRE})*)"
    )


def _es_de_organizacion(palabra: str, organizaciones: frozenset[str]) -> bool:
    """Si la palabra, o una de sus partes, es una palabra de organizacion declarada.

    Por partes: "Mutual's" es "Mutual" con un posesivo, y "Ridgeway-Mutual" lleva
    "Auto" dentro. Sin tildes ni mayusculas, como las frases de contexto.
    """
    return any(parte in organizaciones for parte in _PARTES_DE_PALABRA.split(_sin_tildes(palabra)))


def self_identification_findings(
    text: str,
    rule: SelfIdentificationRule,
    *,
    organization_words: Iterable[str] | None = None,
) -> tuple[DetectedEntity, ...]:
    """El nombre que sigue a una frase de autoidentificacion (U7, NFR11.10).

    No depende de como etiquete el modelo ese nombre --organizacion, otra cosa o
    nada--, que es justo por donde se escapaba: "My name is Megan Hughes." salia
    entero porque el modelo ingles lo llama organizacion.

    Dos condiciones, y cada una tiene su razon:

    - **De `min_tokens` a `max_tokens` palabras con mayuscula.** Una sola es
      demasiado a menudo otra cosa ("Soy Colombiano", "This is Monday"), y una
      tirada mas larga que un nombre completo es un titulo, no una persona.
    - **Ninguna palabra de organizacion declarada.** "This is Ridgeway Mutual
      calling" presenta una empresa; taparla dejaria la transcripcion sin decir
      quien llamaba, sin proteger a nadie.

    Tapar de mas en lo demas es el costo aceptado de la decision FD-U3-9.

    `organization_words` reemplaza las de la regla. El detector le pasa **las de
    los dos idiomas**: una empresa se llama igual en los dos, y "Le habla Knotwell
    Insurance Agency" es una frase espanola con un nombre de empresa en ingles.
    """
    patron = _patron_de_autoidentificacion(rule.cues)
    palabras_de_organizacion = (
        rule.organization_words if organization_words is None else organization_words
    )
    organizaciones = frozenset(_sin_tildes(palabra) for palabra in palabras_de_organizacion)

    hallazgos: list[DetectedEntity] = []
    for encontrado in patron.finditer(text):
        inicio, fin = encontrado.span("name")
        palabras = text[inicio:fin].split()
        if not rule.min_tokens <= len(palabras) <= rule.max_tokens:
            continue
        if any(_es_de_organizacion(palabra, organizaciones) for palabra in palabras):
            continue
        hallazgos.append(
            DetectedEntity(
                entity_type=rule.entity_type,
                start=inicio,
                end=fin,
                recognizer_id=rule.id,
                confidence=CONFIANZA_DE_AUTOIDENTIFICACION,
            )
        )
    return tuple(hallazgos)


def _hay_contexto(
    normalizado: str, frases: Sequence[str], inicio: int, fin: int, ventana: int
) -> bool:
    """Si alguna frase declarada aparece a menos de `ventana` de la tirada."""
    desde = max(0, inicio - ventana)
    hasta = min(len(normalizado), fin + ventana)
    alrededor = normalizado[desde:hasta]
    return any(frase in alrededor for frase in frases)


def _trozos_libres(
    inicio: int, fin: int, claimed: Sequence[DetectedEntity]
) -> list[tuple[int, int]]:
    """Lo que queda de `[inicio, fin)` tras quitar lo ya reclamado."""
    trozos = [(inicio, fin)]
    for hallazgo in claimed:
        siguiente: list[tuple[int, int]] = []
        for desde, hasta in trozos:
            if hallazgo.end <= desde or hallazgo.start >= hasta:
                siguiente.append((desde, hasta))
                continue
            if desde < hallazgo.start:
                siguiente.append((desde, hallazgo.start))
            if hallazgo.end < hasta:
                siguiente.append((hallazgo.end, hasta))
        trozos = siguiente
    return trozos


#: Una sola palabra hecha de letras: sin espacios, digitos ni guiones.
_UNA_PALABRA = regex.compile(r"\p{L}[\p{L}\p{M}]*")

#: Lo que puede haber entre el inicio de una frase y su primera palabra sin ser de la
#: frase: espacios y los signos que abren una pregunta, una exclamacion o una cita.
_ANTES_DE_LA_PRIMERA_PALABRA = " \t\u00a0\u00bf\u00a1\"'\u00ab("
#: Lo que cierra una frase. El salto de linea cuenta: cada linea de un mensaje abre una.
_CIERRE_DE_FRASE = ".!?\u2026:\n"


def _abre_una_frase(antes: str) -> bool:
    """Si lo que precede a una palabra es el inicio del texto o el cierre de una frase.

    Es la unica posicion en la que una mayuscula no dice nada: abre toda frase, sea
    de un nombre o de «Queria»."""
    previo = antes.rstrip(_ANTES_DE_LA_PRIMERA_PALABRA)
    return previo == "" or previo[-1] in _CIERRE_DE_FRASE


def _usada_como_verbo_que_pide(doc: Any, token: Any, idioma: Locale) -> bool:
    """Si la palabra (en minuscula) abre una peticion: la sigue un infinitivo, o «si» /
    «que» tras un verbo conjugado."""
    siguiente = doc[token.i + 1]
    if "Inf" in siguiente.morph.get("VerbForm"):
        return True
    if idioma == "en" and siguiente.lower_ == "to" and token.i + 2 < len(doc):
        return bool(doc[token.i + 2].pos_ == "VERB")
    return bool(
        token.pos_ in ("VERB", "AUX")
        and "Fin" in token.morph.get("VerbForm")
        and siguiente.pos_ == "SCONJ"
    )


@dataclass(frozen=True)
class Detector:
    """El detector del proceso: un motor, dos modelos y dos juegos.

    Se construye una vez al arrancar y se comparte. No guarda nada entre
    llamadas: lo unico que lleva dentro son los modelos y la configuracion.
    """

    engine: AnalyzerEngine
    sets: dict[Locale, RecognizerSet]
    attribution: dict[tuple[str, str, str], Recognizer]

    @property
    def context_words(self) -> frozenset[str]:
        """Las palabras de contexto declaradas, de los dos idiomas, normalizadas."""
        return frozenset(
            _sin_tildes(palabra)
            for juego in self.sets.values()
            for reconocedor in juego.recognizers
            for palabra in reconocedor.context
        )

    @property
    def organization_words(self) -> frozenset[str]:
        """Las palabras de organizacion de los dos idiomas, juntas.

        Juntas porque una empresa se llama igual en los dos: la negativa de la
        regla de autoidentificacion no puede depender del idioma de la frase que
        la presenta.
        """
        return frozenset(
            palabra
            for juego in self.sets.values()
            for palabra in juego.self_identification.organization_words
        )

    def detect(
        self, text: str, *, language: Locale, composed: bool = False
    ) -> tuple[DetectedEntity, ...]:
        """Los hallazgos de un texto, con los dos juegos y el respaldo.

        `language` es el idioma **de la conversacion**. No elige que se busca:
        elige, mas arriba, en que idioma se escribe la etiqueta.

        `composed` dice que el texto lo compuso la agente con frases del catalogo y
        datos dentro. Se busca igual; solo se descartan los hallazgos de nombre o de
        lugar hechos enteros de palabras nuestras (`_VOCABULARIO_PROPIO`).
        """
        if language not in self.sets:
            msg = f"el idioma '{language}' no tiene juego de reconocedores cargado"
            raise DetectionError(msg)

        hallazgos: list[DetectedEntity] = []
        for idioma in sorted(self.sets):
            hallazgos.extend(self._de_un_juego(text, idioma, turno=language))
        # La regla de autoidentificacion de **los dos** idiomas, sea cual sea el
        # del turno: decir el nombre con la frase del otro idioma no puede ser la
        # via para sacarlo (ver `PASADA_DEL_OTRO_IDIOMA`).
        organizaciones = self.organization_words
        for idioma in sorted(self.sets):
            hallazgos.extend(
                self_identification_findings(
                    text,
                    self.sets[idioma].self_identification,
                    organization_words=organizaciones,
                )
            )

        palabras = self.context_words
        reconocidos = resolve_overlaps(text, hallazgos, turno=language, context_words=palabras)
        del_respaldo = fallback_findings(text, self.sets[language].fallback, reconocidos)
        finales = resolve_overlaps(
            text, [*reconocidos, *del_respaldo], turno=language, context_words=palabras
        )
        publicos = tuple(h for h in finales if not _es_nombre_publico(text, h))
        if not composed:
            return publicos
        return tuple(h for h in publicos if not _es_solo_vocabulario_propio(text, h))

    def _es_verbo_con_mayuscula_de_inicio(
        self, text: str, start: int, end: int, idioma: Locale
    ) -> bool:
        """Si el «nombre» que encontro el modelo es la primera palabra de una frase que
        pide algo: «Queria saber si cubre...», «Pregunto si me cubre...».

        El modelo toma por persona la palabra con que abre una frase cuando esa palabra
        es una forma verbal, y la mayuscula inicial es el unico dato en que se apoya
        (visto el 2026-10-12: «Queria saber...» se guardaba como «[NOMBRE 1] saber...»).
        Se arregla la clase y no la palabra, y solo si se cumplen **las dos** cosas:

        - es **una** palabra, la primera de su frase: ahi la mayuscula no dice nada;
        - lo que le sigue, pegado, la usa como verbo que pide algo: un infinitivo
          («queria **saber**», «need **to** report») o «si» / «que» tras un verbo
          conjugado («pregunto **si**»).

        Un nombre no se sigue de un infinitivo, y uno seguido de verbo conjugado
        («Daniel quiere reportar») sigue tapado. Ante la duda se tapa, que es el lado
        seguro: un nombre solo, con una coma o seguido de «mi poliza» no cumple lo
        segundo. Se vuelve a leer la frase con la palabra en minuscula para que la
        mayuscula no decida lo que el modelo ve; lo caro corre solo para los hallazgos
        que cumplen lo primero, que son pocos.
        """
        palabra = text[start:end]
        minuscula = palabra.lower()
        if (
            not _UNA_PALABRA.fullmatch(palabra)
            or len(minuscula) != len(palabra)
            or not _abre_una_frase(text[:start])
        ):
            return False
        doc = self._modelo(idioma)(text[:start] + minuscula + text[end:])
        token = next((t for t in doc if t.idx == start), None)
        if token is None or token.i + 1 >= len(doc):
            return False
        siguiente = doc[token.i + 1]
        if not siguiente.is_alpha or text[end : siguiente.idx].strip() != "":
            return False
        return _usada_como_verbo_que_pide(doc, token, idioma)

    def _modelo(self, idioma: Locale) -> Any:
        """El modelo de lenguaje de ese idioma, el mismo que ya usa el motor."""
        return cast(Any, self.engine.nlp_engine).nlp[idioma]

    def _de_un_juego(self, text: str, idioma: Locale, *, turno: Locale) -> list[DetectedEntity]:
        """Lo que encuentra el juego de un idioma, atribuido a su fila."""
        juego = self.sets[idioma]
        try:
            resultados = self.engine.analyze(
                text=text,
                language=idioma,
                entities=_entidades_declaradas(juego, solo_por_formato=idioma != turno),
                score_threshold=juego.score_threshold,
            )
        except Exception as error:
            msg = (
                f"el detector fallo al analizar el texto con el juego '{idioma}': "
                f"{type(error).__name__}: {error}"
            )
            raise DetectionError(msg) from error

        hallazgos: list[DetectedEntity] = []
        nunca = {palabra.casefold() for palabra in juego.never_personal}
        for resultado in resultados:
            palabras = [
                p.strip(_PUNTUACION_DE_SALUDO)
                for p in text[resultado.start : resultado.end].casefold().split()
            ]
            if palabras and all(p in nunca for p in palabras):
                continue
            metadatos = resultado.recognition_metadata or {}
            nombre = str(metadatos.get("recognizer_name", ""))
            clave = (idioma, nombre, resultado.entity_type)
            reconocedor = self.attribution.get(clave)
            if (
                reconocedor is not None
                and reconocedor.entity_type is EntityType.PERSON
                and reconocedor.mechanism is Mechanism.MODEL
                and self._es_verbo_con_mayuscula_de_inicio(
                    text, resultado.start, resultado.end, idioma
                )
            ):
                continue
            if reconocedor is None:
                # Fallar cerrado: un hallazgo que no se puede atribuir a una fila
                # del archivo no se puede medir. Descartarlo en silencio dejaria
                # de taparlo sin que nada avise, que es el fallo de esta unidad.
                msg = (
                    f"el motor devolvio un hallazgo de '{nombre}' con la entidad "
                    f"'{resultado.entity_type}' en el idioma '{idioma}', que el "
                    "archivo de reconocedores no declara"
                )
                raise DetectionError(msg)
            hallazgos.append(
                DetectedEntity(
                    entity_type=reconocedor.entity_type,
                    start=resultado.start,
                    end=resultado.end,
                    recognizer_id=reconocedor.id,
                    confidence=min(1.0, max(0.0, resultado.score)),
                )
            )
        return hallazgos


def load(root: Path | None = None) -> Detector:
    """Construye el detector: comprueba los modelos, carga los dos juegos.

    Comprueba los modelos **antes** de construir nada, para poder fallar
    nombrandolos y nombrando el comando que los instala (INF-U3-3).
    """
    _comprobar_modelos()
    juegos = loading.load_all(root)

    proveedor = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [
                {"lang_code": idioma, "model_name": MODELOS[idioma]} for idioma in sorted(juegos)
            ],
        }
    )
    motor = proveedor.create_engine()

    detector = Detector(
        engine=AnalyzerEngine(
            nlp_engine=motor,
            registry=_construir_registro(juegos),
            supported_languages=sorted(juegos),
        ),
        sets=juegos,
        attribution=_tabla_de_atribucion(juegos),
    )
    observability.emit(
        "redaction.detector_loaded",
        languages=sorted(juegos),
        recognizers={idioma: len(juego.recognizers) for idioma, juego in juegos.items()},
    )
    return detector


def _comprobar_modelos() -> None:
    """Que los dos modelos esten instalados, y si no, decir cual y con que.

    Un `ImportError` de spaCy a mitad de una prueba no le dice a nadie que hacer.
    """
    import importlib.util

    faltan = [
        nombre for nombre in sorted(MODELOS.values()) if importlib.util.find_spec(nombre) is None
    ]
    if faltan:
        msg = (
            f"faltan los modelos de lenguaje {faltan}. Instalelos con "
            f"`{COMANDO_DE_MODELOS}`. Viven en un extra y no en las dependencias "
            "normales para que el camino del clon al reporte no se descargue 72 MB "
            "(INF-U3-2); sin ellos, la redaccion no puede correr y esta unidad "
            "falla cerrado en vez de dejar salir texto sin tapar."
        )
        raise ModelsMissingError(msg)


_detector: Detector | None = None


def install(detector: Detector) -> None:
    """Fija el detector del proceso. Lo llama la raiz de composicion (C-24)."""
    global _detector
    _detector = detector


def get_detector() -> Detector:
    """El detector del proceso, construyendolo la primera vez si hace falta."""
    global _detector
    if _detector is None:
        _detector = load()
    return _detector


def reset() -> None:
    """Olvida el detector cargado. Lo usan las pruebas para no compartir estado."""
    global _detector
    _detector = None
