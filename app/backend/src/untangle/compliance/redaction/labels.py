"""Las etiquetas: que lee una persona en lugar del dato (BR3.1 a BR3.4).

Tres cosas que esta pieza hace y una que no puede hacer.

Hace: escribe la etiqueta **desde el catalogo de textos**, en el idioma de la
conversacion, y la numera por tipo dentro del texto de la llamada. La deja ya
escrita, para que un renglon de log o una traza exportada se entiendan fuera del
aplicativo, sin catalogo que resolver.

No puede: **importar el detector**. Estan en el mismo renglon del contrato de
capas, y el contrato lo comprueba. Escribir la etiqueta no puede depender de por
que se detecto algo, que es lo que impide que un dia la etiqueta lleve "una
pista" del valor original para ayudar a depurar.

Y lo que no existe aqui: **ninguna estructura que relacione un valor con su
numero**. La numeracion reusa el numero del hallazgo anterior comparando los dos
trozos del texto de entrada en el momento, sin guardar ninguno. Por eso la
numeracion no sobrevive a la llamada: mantenerla entre turnos exigiria
exactamente esa correspondencia, que es la boveda que BR1.6 prohibe.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from untangle.base import Locale
from untangle.compliance.redaction.recognizers.models import DetectedEntity, EntityType
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import LOCALES

# Una clave por tipo de entidad, literal, para que el chequeo de claves sin
# consumidor las encuentre y el de paridad EN-ES las compare (BR3.2, BR3.4).
CLAVE_PLACA = copy_api.CopyKey("redaction.label.license_plate")
CLAVE_CEDULA = copy_api.CopyKey("redaction.label.national_id")
CLAVE_TELEFONO = copy_api.CopyKey("redaction.label.phone")
CLAVE_POLIZA = copy_api.CopyKey("redaction.label.policy_number")
CLAVE_NOMBRE = copy_api.CopyKey("redaction.label.person")
CLAVE_CORREO = copy_api.CopyKey("redaction.label.email")
CLAVE_LUGAR = copy_api.CopyKey("redaction.label.location")
CLAVE_SIN_CLASIFICAR = copy_api.CopyKey("redaction.label.unclassified")
CLAVE_VIN = copy_api.CopyKey("redaction.label.vin")


def label_for(entity_type: EntityType, *, locale: Locale, ordinal: int) -> str:
    """La etiqueta de un tipo, en un idioma y con su numero.

    Los casos estan escritos uno a uno, y no resueltos por un diccionario,
    a proposito: el chequeo de claves literales del catalogo exige ver la clave
    en la llamada, porque una clave armada en ejecucion hace inexacto el chequeo
    de claves sin consumidor. Escribirlos deja ademas el mapa completo a la
    vista de quien lo lea.
    """
    numero = str(ordinal)
    match entity_type:
        case EntityType.LICENSE_PLATE:
            etiqueta = copy_api.t(CLAVE_PLACA, locale=locale, n=numero)
        case EntityType.NATIONAL_ID:
            etiqueta = copy_api.t(CLAVE_CEDULA, locale=locale, n=numero)
        case EntityType.PHONE:
            etiqueta = copy_api.t(CLAVE_TELEFONO, locale=locale, n=numero)
        case EntityType.POLICY_NUMBER:
            etiqueta = copy_api.t(CLAVE_POLIZA, locale=locale, n=numero)
        case EntityType.PERSON:
            etiqueta = copy_api.t(CLAVE_NOMBRE, locale=locale, n=numero)
        case EntityType.EMAIL:
            etiqueta = copy_api.t(CLAVE_CORREO, locale=locale, n=numero)
        case EntityType.LOCATION:
            etiqueta = copy_api.t(CLAVE_LUGAR, locale=locale, n=numero)
        case EntityType.UNCLASSIFIED:
            etiqueta = copy_api.t(CLAVE_SIN_CLASIFICAR, locale=locale, n=numero)
        case EntityType.VIN:
            etiqueta = copy_api.t(CLAVE_VIN, locale=locale, n=numero)
    return etiqueta


def ordinals(text: str, findings: Sequence[DetectedEntity]) -> tuple[int, ...]:
    """El numero de cada hallazgo, por tipo y dentro de este texto (BR3.3).

    Dos datos distintos del mismo tipo se distinguen --el telefono del asegurado
    es `1` y el del testigo `2`-- y **el mismo valor repetido conserva su
    numero**, porque si no, un turno que repite el mismo telefono pareceria
    traer dos telefonos distintos.

    Para saber que un valor se repite se comparan dos trozos del texto de
    entrada en el momento, y no se guarda ninguno: la lista que este metodo
    lleva es de **numeros**, no de valores. Es lo que permite que la propiedad de
    BR1.6 --que no exista ninguna correspondencia guardada-- sea comprobable por
    una herramienta y no una promesa.
    """
    asignados: list[int] = []
    contador: dict[EntityType, int] = {}

    for indice, hallazgo in enumerate(findings):
        repetido = next(
            (
                asignados[anterior]
                for anterior in range(indice)
                if findings[anterior].entity_type is hallazgo.entity_type
                and text[findings[anterior].start : findings[anterior].end]
                == text[hallazgo.start : hallazgo.end]
            ),
            None,
        )
        if repetido is None:
            contador[hallazgo.entity_type] = contador.get(hallazgo.entity_type, 0) + 1
            repetido = contador[hallazgo.entity_type]
        asignados.append(repetido)

    return tuple(asignados)


def labels_for(text: str, findings: Sequence[DetectedEntity], *, locale: Locale) -> tuple[str, ...]:
    """Una etiqueta por hallazgo, en el mismo orden, ya escrita y numerada."""
    numeros = ordinals(text, findings)
    return tuple(
        label_for(hallazgo.entity_type, locale=locale, ordinal=numero)
        for hallazgo, numero in zip(findings, numeros, strict=True)
    )


# --- Lo que se dice en voz alta en lugar de una etiqueta (2026-10-13) -----------------
# Una etiqueta se lee en pantalla, no se dice: "[PLACA 1]" en un altavoz suena a lo que
# el sintetizador decida. Cuando una frase que se va a decir todavia trae etiquetas --un
# comentario que un ajustador escribio y se guardo tapado, una explicacion con un lugar
# que el detector confundio con un dato-- se cambia cada una por una palabra neutra.

CLAVE_PLACA_DICHA = copy_api.CopyKey("redaction.spoken.license_plate")
CLAVE_CEDULA_DICHA = copy_api.CopyKey("redaction.spoken.national_id")
CLAVE_TELEFONO_DICHO = copy_api.CopyKey("redaction.spoken.phone")
CLAVE_POLIZA_DICHA = copy_api.CopyKey("redaction.spoken.policy_number")
CLAVE_NOMBRE_DICHO = copy_api.CopyKey("redaction.spoken.person")
CLAVE_CORREO_DICHO = copy_api.CopyKey("redaction.spoken.email")
CLAVE_LUGAR_DICHO = copy_api.CopyKey("redaction.spoken.location")
CLAVE_SIN_CLASIFICAR_DICHA = copy_api.CopyKey("redaction.spoken.unclassified")
CLAVE_VIN_DICHO = copy_api.CopyKey("redaction.spoken.vin")

#: Un numero que ninguna etiqueta real lleva, para sacar de cada plantilla del catalogo
#: el molde con que se reconoce: lo que rodea al numero es lo que se busca.
_NUMERO_DE_MUESTRA = 987654321


def spoken_label_for(entity_type: EntityType, *, locale: Locale) -> str:
    """La palabra neutra que se dice en lugar de la etiqueta de ese tipo.

    Escritos uno a uno por la misma razon que `label_for`: el chequeo de claves sin
    consumidor necesita ver cada clave literal.
    """
    match entity_type:
        case EntityType.LICENSE_PLATE:
            dicha = copy_api.t(CLAVE_PLACA_DICHA, locale=locale)
        case EntityType.NATIONAL_ID:
            dicha = copy_api.t(CLAVE_CEDULA_DICHA, locale=locale)
        case EntityType.PHONE:
            dicha = copy_api.t(CLAVE_TELEFONO_DICHO, locale=locale)
        case EntityType.POLICY_NUMBER:
            dicha = copy_api.t(CLAVE_POLIZA_DICHA, locale=locale)
        case EntityType.PERSON:
            dicha = copy_api.t(CLAVE_NOMBRE_DICHO, locale=locale)
        case EntityType.EMAIL:
            dicha = copy_api.t(CLAVE_CORREO_DICHO, locale=locale)
        case EntityType.LOCATION:
            dicha = copy_api.t(CLAVE_LUGAR_DICHO, locale=locale)
        case EntityType.UNCLASSIFIED:
            dicha = copy_api.t(CLAVE_SIN_CLASIFICAR_DICHA, locale=locale)
        case EntityType.VIN:
            dicha = copy_api.t(CLAVE_VIN_DICHO, locale=locale)
    return dicha


def _molde_de_etiqueta(entity_type: EntityType, locale: Locale) -> str:
    """La expresion que reconoce las etiquetas de ese tipo en ese idioma, con cualquier numero."""
    muestra = label_for(entity_type, locale=locale, ordinal=_NUMERO_DE_MUESTRA)
    trozos = muestra.split(str(_NUMERO_DE_MUESTRA))
    return r"\d+".join(re.escape(trozo) for trozo in trozos)


def replace_labels_with_spoken(text: str, *, locale: Locale) -> str:
    """El texto con cada etiqueta cambiada por su palabra neutra, en el idioma de `locale`.

    Reconoce las etiquetas de **los dos idiomas** y no solo las del `locale`: el idioma de
    una llamada puede cambiar a media conversacion, y lo que ya estaba escrito (el
    comentario de un ajustador) conserva las etiquetas con que se guardo. El numero se
    descarta: "esa persona" no necesita saber que era la primera.
    """
    tipos = tuple(EntityType)
    patron = re.compile(
        "|".join(
            f"(?P<t{indice}>{'|'.join(_molde_de_etiqueta(tipo, idioma) for idioma in LOCALES)})"
            for indice, tipo in enumerate(tipos)
        )
    )

    def _cambio(encontrada: re.Match[str]) -> str:
        grupo = encontrada.lastgroup
        assert grupo is not None  # noqa: S101 -- cada rama de la alternancia es un grupo con nombre
        return spoken_label_for(tipos[int(grupo[1:])], locale=locale)

    return patron.sub(_cambio, text)
