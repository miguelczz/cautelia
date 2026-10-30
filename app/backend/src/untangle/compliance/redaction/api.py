"""La superficie del modulo: `Redacted`, `redact()` y `redaction_report()` (C-13).

**Regla dura del proyecto:** una salida sin redaccion debe ser imposible por
construccion, no detectable por disciplina. Aqui vive la mitad declarativa de ese
mecanismo --el tipo que los cinco puntos de salida exigen-- y este es el **unico**
archivo que lo fabrica.

El tipo por si solo **no garantiza nada**, y decirlo es la mitad del control.
`Redacted` es un `NewType`, que se borra en tiempo de ejecucion: `Redacted(texto)`
es una llamada legal que el comprobador de tipos acepta sin queja, y
`cast(Redacted, texto)` ni siquiera la invoca. Quien impone la regla es el
chequeo `redaction:constructor`, que falla ante las tres formas de producir el
tipo fuera de este archivo. Dejar la garantia apoyada en el tipo seria escribir
un control que no existe.

**Fallar cerrado atraviesa todo** (BR1.7, SEC-U3.10): si los modelos no cargan,
esto levanta; si una llamada falla, esto levanta. `redact` no devuelve texto
nunca que no haya pasado por el detector, y el punto de salida responde con
`sinks.DEGRADED_COPY_KEY`. No existe ninguna ruta en la que un fallo produzca
texto sin tapar.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NewType

from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig, RecognizerResult

from untangle import observability
from untangle.base import Locale
from untangle.compliance.redaction import detector as deteccion
from untangle.compliance.redaction import labels
from untangle.compliance.redaction.recognizers.models import (
    DetectedEntity,
    EntityType,
    RedactionReport,
)

#: El texto ya tapado, y el tipo que los cinco puntos de salida exigen. Un punto
#: de salida que acepte `str` es un punto de salida sin redaccion, y por eso no
#: acepta `str`.
Redacted = NewType("Redacted", str)

#: El prefijo de los tipos sinteticos con que se le pide al sustituidor que
#: ponga **esta** etiqueta en **este** hallazgo. El sustituidor trabaja por tipo
#: de entidad, y sin un tipo por hallazgo no habria forma de darle a cada uno su
#: numero (BR3.3).
_MARCA = "U3RED"


class RedactionFailedError(RuntimeError):
    """La redaccion no se pudo ejecutar.

    Se levanta en vez de devolver texto. **Su mensaje nunca incluye el texto de
    entrada**: un error de la redaccion que imprimiera lo que iba a tapar
    convertiria el camino de fallo en el punto de fuga que la unidad evita.
    """


_sustituidor: AnonymizerEngine | None = None


def _anonymizer() -> AnonymizerEngine:
    """El sustituidor del proceso. Resuelve los desplazamientos por nosotros.

    Sustituir a mano sobre indices es donde se cuelan los errores de un
    caracter, y aqui un caracter de mas deja medio dato a la vista.
    """
    global _sustituidor
    if _sustituidor is None:
        # El constructor del sustituidor no viene anotado en la biblioteca. Se
        # silencia **ese** error en **esa** linea, con su razon al lado, en vez
        # de aflojar la regla para el modulo entero.
        _sustituidor = AnonymizerEngine()  # type: ignore[no-untyped-call]
    return _sustituidor


def _sustituir(text: str, findings: Sequence[DetectedEntity], etiquetas: Sequence[str]) -> str:
    """Pone cada etiqueta en su sitio, con los desplazamientos ya resueltos."""
    if not findings:
        return text

    resultados = [
        RecognizerResult(
            entity_type=f"{_MARCA}{indice}",
            start=hallazgo.start,
            end=hallazgo.end,
            score=hallazgo.confidence,
        )
        for indice, hallazgo in enumerate(findings)
    ]
    operadores = {
        f"{_MARCA}{indice}": OperatorConfig("replace", {"new_value": etiqueta})
        for indice, etiqueta in enumerate(etiquetas)
    }
    return str(
        _anonymizer().anonymize(text=text, analyzer_results=resultados, operators=operadores).text
    )


def redact(text: str, *, language: Locale) -> Redacted:
    """Reemplaza cada dato personal por la etiqueta de su tipo (C-13).

    Sin red y sin modelo de lenguaje (ADR-013): el texto no sale del proceso.

    `language` es el idioma **de la conversacion**. Decide en que idioma se
    escribe la etiqueta, y nada mas: los reconocedores de los dos idiomas corren
    igual (BR2.9).
    """
    try:
        hallazgos = deteccion.get_detector().detect(text, language=language)
        etiquetas = labels.labels_for(text, hallazgos, locale=language)
        return Redacted(_sustituir(text, hallazgos, etiquetas))
    except Exception as error:
        # Se traduce a un solo tipo para que los cinco puntos de salida tengan una
        # sola cosa que atrapar, y se levanta: si la redaccion no se puede
        # ejecutar, no sale texto (BR1.7).
        observability.emit(
            "redaction.failed",
            language=language,
            error=type(error).__name__,
        )
        msg = (
            f"la redaccion fallo en el idioma '{language}': {type(error).__name__}. "
            "No se emite texto: el punto de salida responde con la clave de "
            "degradacion del catalogo (BR1.7)"
        )
        raise RedactionFailedError(msg) from error


def redact_composed(text: str, *, language: Locale) -> Redacted:
    """Lo que dijo la agente, para guardarlo: frases del catalogo con datos dentro.

    La agente responde con frases nuestras a las que se les insertan valores --el
    numero de poliza, el nombre del titular, lo que la persona dijo y se le lee de
    vuelta--, a veces con un acuse o una reescritura del modelo delante. Ni `redact`
    ni `from_catalog` sirven para eso: el primero etiqueta como persona palabras
    nuestras ("Encontre la poliza" se guardaba "[NOMBRE 1] la poliza"), y el segundo,
    sin los valores por separado, no tapaba nada: el nombre y la poliza quedaban
    guardados en claro (visto el 2026-10-10).

    Esta busca en todo el texto, tapa todo lo que tiene forma de dato y los nombres,
    y solo perdona los hallazgos de nombre o de lugar hechos enteros de palabras del
    catalogo. Falla cerrado igual que `redact`.
    """
    try:
        hallazgos = deteccion.get_detector().detect(text, language=language, composed=True)
        etiquetas = labels.labels_for(text, hallazgos, locale=language)
        return Redacted(_sustituir(text, hallazgos, etiquetas))
    except Exception as error:
        observability.emit(
            "redaction.failed",
            language=language,
            error=type(error).__name__,
        )
        msg = (
            f"la redaccion fallo en el idioma '{language}': {type(error).__name__}. "
            "No se emite texto: el punto de salida responde con la clave de "
            "degradacion del catalogo (BR1.7)"
        )
        raise RedactionFailedError(msg) from error


def from_catalog(text: str, *, language: Locale, **values: str) -> Redacted:
    """Una frase del catalogo, con lo que se mete en ella ya tapado (U18).

    **El molde no se mira; lo que se mete en el, si.** Una frase del catalogo no
    tiene datos personales por construccion: la escribimos nosotros, se revisa en
    un diff y vive en un archivo versionado. Pasarle un detector de nombres solo
    puede danarla, y la dano: en espanol etiquetaba como persona el verbo con que
    arranca la frase, asi que la agente se presentaba diciendo "[NOMBRE 1]
    ayudarle a reportar un siniestro" en vez de "Puedo ayudarle...". Siete frases
    en espanol y ninguna en ingles, porque el reconocedor de nombres en espanol
    falla donde el ingles no.

    Lo que si lleva datos personales son los **huecos**: el nombre de quien llama,
    el comentario que escribio una ajustadora, la placa que se lee de vuelta. Cada
    valor pasa por `redact` antes de entrar en la frase, asi que la salida sigue
    sin llevar un dato personal que nadie tapo.

    **Por que el texto que llega aqui es de verdad del catalogo.** No lo garantiza
    este archivo ni el comprobador de tipos: lo garantiza otra compuerta que ya
    existe. El chequeo `copy:check` (BR3.3 del catalogo) falla ante cualquier frase
    visible escrita en linea en el codigo, asi que un modulo no tiene de donde
    sacar una frase que no sea del catalogo. Lo que **no** cierra ninguna maquina
    es que alguien pase por `text` una variable con texto de fuera; eso lo cierra
    la revision, y es la razon por la que los huecos existen: el texto externo
    entra por `values`, donde si se tapa.

    Falla cerrado igual que `redact`: si tapar un valor falla, esto levanta y no
    sale texto.

    **Lo que esto no atrapa:** una frase con huecos a la que nadie le paso ninguno
    sale con el `{hueco}` a la vista, igual que hoy la saca el catalogo. Es un
    defecto visible --se oye y se lee-- y no una fuga, y se deja asi porque la
    alternativa, llamar a `format` siempre, haria levantar la llamada ante una
    llave escrita dentro de un comentario de una ajustadora.
    """
    if not values:
        # **No se llama `format` cuando no hay huecos que llenar**, y no es un atajo:
        # el texto que llega aqui ya puede traer una llave dentro. La oferta de
        # retomar junta la frase del catalogo con el comentario que escribio una
        # ajustadora --ya redactado al guardarse-- y un comentario con un `{` haria
        # levantar a `format`. Una llave en un comentario no puede tumbar una
        # llamada.
        return Redacted(text)
    tapados = {clave: str(redact(valor, language=language)) for clave, valor in values.items()}
    return Redacted(text.format(**tapados))


def without_labels(text: Redacted, *, language: Locale) -> Redacted:
    """El mismo texto ya tapado, con cada etiqueta cambiada por una palabra neutra (2026-10-13).

    Para lo que se **dice** en voz alta o se pinta sin tener el dato: "[LUGAR 1]" se lee
    en una pantalla donde se sabe que es una etiqueta, y en un altavoz suena a lo que el
    sintetizador decida. No destapa nada --"esa persona" no dice quien--, y por eso el
    resultado sigue siendo `Redacted`: es el `Redacted -> Redacted` explicito que
    `CallEngine.spoken` echaba en falta.

    Reconoce las etiquetas de los dos idiomas y escribe las palabras en `language`.
    """
    return Redacted(labels.replace_labels_with_spoken(str(text), locale=language))


def redaction_report(text: str, *, language: Locale) -> RedactionReport:
    """Conteo por tipo de entidad, por reconocedor y del respaldo (C-13).

    Se produce **aparte** del texto redactado, para que medir nunca obligue a
    conservar lo medido. Las tres cifras salen de **la misma lista de
    hallazgos**, agrupada tres veces (SEC-U3.9): dos recuentos independientes
    podrian divergir, y el dia que divergieran nadie sabria cual creer.
    """
    try:
        detector = deteccion.get_detector()
        hallazgos = detector.detect(text, language=language)
    except Exception as error:
        observability.emit("redaction.report_failed", language=language, error=type(error).__name__)
        msg = f"el informe de redaccion fallo en el idioma '{language}': {type(error).__name__}"
        raise RedactionFailedError(msg) from error

    del_respaldo = {juego.fallback.id for juego in detector.sets.values()}

    # Todos los tipos, tambien con cero: un tipo **ausente** del informe y un
    # tipo con cero hallazgos son cosas distintas, y confundirlas esconde un
    # reconocedor que dejo de cargar (BR4.1).
    por_tipo: dict[EntityType, int] = dict.fromkeys(EntityType, 0)
    # Lo mismo con los reconocedores: la fila que desaparece es la senal.
    por_reconocedor: dict[str, int] = {
        reconocedor.id: 0 for juego in detector.sets.values() for reconocedor in juego.recognizers
    }
    por_reconocedor.update(dict.fromkeys(del_respaldo, 0))
    # Y la regla de autoidentificacion de cada idioma, con su propia fila: sin
    # ella, lo que la regla tapa se sumaria en silencio a la fila del modelo, y un
    # modelo que dejara de reconocer nombres se esconderia detras de la regla.
    por_reconocedor.update({juego.self_identification.id: 0 for juego in detector.sets.values()})

    for hallazgo in hallazgos:
        por_tipo[hallazgo.entity_type] += 1
        por_reconocedor[hallazgo.recognizer_id] = por_reconocedor.get(hallazgo.recognizer_id, 0) + 1

    return RedactionReport(
        language=language,
        counts_by_type=por_tipo,
        counts_by_recognizer=por_reconocedor,
        # La cifra del respaldo, aparte. Nunca sumada a la de un tipo del
        # dominio: un respaldo que dispara mucho es la senal de que un
        # reconocedor se rompio, y sumarlo la borraria (BR4.2).
        fallback_count=sum(1 for h in hallazgos if h.recognizer_id in del_respaldo),
    )


def allow_public_terms(terms: Sequence[str]) -> None:
    """Nombres publicos --aseguradoras, la agente, la marca-- que nunca se tapan solos."""
    deteccion.install_public_terms(terms)


def allow_own_vocabulary(texts: Sequence[str]) -> None:
    """Las frases del catalogo: sus palabras no se toman por nombres en `redact_composed`."""
    deteccion.install_own_vocabulary(texts)


def warm_up() -> None:
    """Carga el detector ya, para que el primer texto no pague la carga.

    La carga de los modelos dura segundos y bloquea a quien la dispare; en una
    llamada de voz eso era el primer transcrito (2026-10-07). El servidor la
    llama al arrancar.
    """
    deteccion.get_detector()


__all__ = [
    "Redacted",
    "RedactionFailedError",
    "RedactionReport",
    "allow_own_vocabulary",
    "allow_public_terms",
    "from_catalog",
    "redact",
    "redact_composed",
    "redaction_report",
    "warm_up",
    "without_labels",
]
