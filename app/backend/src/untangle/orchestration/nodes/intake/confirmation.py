"""Lectura de confirmacion por bloque, y como se interpreta la respuesta (BR3.1, FD-U11-8).

**FD-U11-8**: lesiones, conductor y lugar -- los tres campos de `fields.yaml`
con `requires_readback: true` -- se leen **nombrandolos**, nunca resumidos:
"Anotado: usted conducía, en la autopista salida 12, sin heridos" cumple,
"Anotado: los datos del accidente" no. Cada bloque tiene su propia clave del
catalogo (BR5.1) con el valor dicho como variable, para que la frase repita lo
que la persona dijo y no una parafrasis.

**BR3.4 no se aplica a estas lecturas.** La regla de veinticinco palabras
declara su propia excepcion: "salvo ... las lecturas de confirmacion [y] el
resumen de cierre". Este modulo no llama a `composition.assert_question_shape`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date

from untangle.base import Locale
from untangle.case_record.models import RecordType
from untangle.compliance.controls.normalization import fold
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration.nodes.intake.blocks import Block

#: Una clave por bloque de campos, escrita entera (la misma razon que
#: `composition.py` documenta): `FINAL_CONFIRMATION` y `DONE` no son bloques
#: de campos (`blocks.BLOCK_ORDER`) y quedan fuera: el resumen de cierre, que
#: lee el caso entero, tiene sus dos claves propias mas abajo
#: (`build_closing_summary`).
READBACK_SAFETY = CopyKey("intake.readback.safety")
READBACK_IDENTITY_AND_POLICY = CopyKey("intake.readback.identity_and_policy")
READBACK_WHAT_HAPPENED = CopyKey("intake.readback.what_happened")
READBACK_WHEN_AND_WHERE = CopyKey("intake.readback.when_and_where")
READBACK_VEHICLE_AND_DRIVER = CopyKey("intake.readback.vehicle_and_driver")
READBACK_OTHER_PARTIES = CopyKey("intake.readback.other_parties")
#: La lectura de cada bloque de una solicitud de cotizacion (U19, BR1.2). Es **por
#: bloque**: se leen todos sus campos nombrandolos y la persona confirma el bloque entero.
READBACK_QUOTE_DRIVER = CopyKey("intake.readback.quote_driver")
READBACK_QUOTE_VEHICLE = CopyKey("intake.readback.quote_vehicle")
READBACK_QUOTE_USAGE = CopyKey("intake.readback.quote_usage")
READBACK_QUOTE_HISTORY = CopyKey("intake.readback.quote_history")


#: Cada bloque con su clave de lectura, escrita entera. Se separa de
#: `build_readback` porque quien emite el turno necesita **la clave** para el
#: registro y **el texto** para decirlo, y componer la clave con una f-string la
#: dejaria fuera del chequeo de claves sin consumidor, que busca literales.
_READBACK_KEYS: Mapping[Block, CopyKey] = {
    Block.SAFETY: READBACK_SAFETY,
    Block.IDENTITY_AND_POLICY: READBACK_IDENTITY_AND_POLICY,
    Block.WHAT_HAPPENED: READBACK_WHAT_HAPPENED,
    Block.WHEN_AND_WHERE: READBACK_WHEN_AND_WHERE,
    Block.VEHICLE_AND_DRIVER: READBACK_VEHICLE_AND_DRIVER,
    Block.OTHER_PARTIES: READBACK_OTHER_PARTIES,
    Block.QUOTE_DRIVER: READBACK_QUOTE_DRIVER,
    Block.QUOTE_VEHICLE: READBACK_QUOTE_VEHICLE,
    Block.QUOTE_USAGE: READBACK_QUOTE_USAGE,
    Block.QUOTE_HISTORY: READBACK_QUOTE_HISTORY,
}

#: Las etiquetas de los valores cerrados de la solicitud. **La persona lee la etiqueta del
#: catalogo, nunca el valor del enum**: `commuting` no es texto para nadie. Cada clave se
#: pasa a `copy_api.t` como constante, nunca construida en ejecucion, o el chequeo de
#: claves sin consumidor dejaria de ser exacto (BR3.4 del catalogo). Un valor que no es de
#: los conocidos no se inventa: sale como se guardo, que deja seguir la lectura y que la
#: persona lo corrija si esta mal.
LABEL_USE_PERSONAL = CopyKey("quote.value.use_type.personal")
LABEL_USE_COMMUTING = CopyKey("quote.value.use_type.commuting")
LABEL_USE_COMMERCIAL = CopyKey("quote.value.use_type.commercial")
LABEL_MILEAGE_LOW = CopyKey("quote.value.mileage.low")
LABEL_MILEAGE_MEDIUM = CopyKey("quote.value.mileage.medium")
LABEL_MILEAGE_HIGH = CopyKey("quote.value.mileage.high")
LABEL_SALVAGE_TRUE = CopyKey("quote.value.salvage_title.true")
LABEL_SALVAGE_FALSE = CopyKey("quote.value.salvage_title.false")
LABEL_COVERAGE_TRUE = CopyKey("quote.value.prior_coverage.true")
LABEL_COVERAGE_FALSE = CopyKey("quote.value.prior_coverage.false")


def _use_type_label(raw: str, *, language: Locale) -> str:
    match raw:
        case "personal":
            return copy_api.t(LABEL_USE_PERSONAL, locale=language)
        case "commuting":
            return copy_api.t(LABEL_USE_COMMUTING, locale=language)
        case "commercial":
            return copy_api.t(LABEL_USE_COMMERCIAL, locale=language)
        case _:
            return raw


def _mileage_label(raw: str, *, language: Locale) -> str:
    match raw:
        case "low":
            return copy_api.t(LABEL_MILEAGE_LOW, locale=language)
        case "medium":
            return copy_api.t(LABEL_MILEAGE_MEDIUM, locale=language)
        case "high":
            return copy_api.t(LABEL_MILEAGE_HIGH, locale=language)
        case _:
            return raw


def _salvage_label(raw: str, *, language: Locale) -> str:
    match raw:
        case "true":
            return copy_api.t(LABEL_SALVAGE_TRUE, locale=language)
        case "false":
            return copy_api.t(LABEL_SALVAGE_FALSE, locale=language)
        case _:
            return raw


def _coverage_label(raw: str, *, language: Locale) -> str:
    match raw:
        case "true":
            return copy_api.t(LABEL_COVERAGE_TRUE, locale=language)
        case "false":
            return copy_api.t(LABEL_COVERAGE_FALSE, locale=language)
        case _:
            return raw


def readback_key(block: Block) -> CopyKey:
    """La clave del catalogo con la que ese bloque se lee de vuelta."""
    clave = _READBACK_KEYS.get(block)
    if clave is None:
        msg = f"el bloque '{block.value}' no tiene lectura de confirmacion propia"
        raise ValueError(msg)
    return clave


def _fecha_legible(valor: str, *, language: Locale) -> str:
    """Una fecha AAAA-MM-DD como la lee una persona: 15/03/2004 en espanol, como se
    escribe en Colombia, y 03/15/2004 en ingles. Lo que no es esa forma, tal cual."""
    try:
        fecha = date.fromisoformat(valor.strip())
    except ValueError:
        return valor
    return fecha.strftime("%d/%m/%Y" if language == "es" else "%m/%d/%Y")


def _build_quote_readback(block: Block, values: Mapping[str, str], *, language: Locale) -> str:
    """La lectura de un bloque de la solicitud (U19, BR1.2): todos sus campos, nombrados.

    Los valores cerrados salen por su etiqueta del catalogo y nunca por el valor del enum.
    """
    if block is Block.QUOTE_DRIVER:
        return copy_api.t(
            READBACK_QUOTE_DRIVER,
            locale=language,
            name=values.get("driver_name", ""),
            birth_date=_fecha_legible(values.get("driver_birth_date", ""), language=language),
            license_years=values.get("license_years", ""),
            license_jurisdiction=values.get("license_jurisdiction", ""),
        )
    if block is Block.QUOTE_VEHICLE:
        return copy_api.t(
            READBACK_QUOTE_VEHICLE,
            locale=language,
            vehicle_year=values.get("vehicle_year", ""),
            vehicle_make=values.get("vehicle_make", ""),
            vehicle_model=values.get("vehicle_model", ""),
            vin=values.get("vin", ""),
            salvage_title=_salvage_label(values.get("salvage_title", ""), language=language),
        )
    if block is Block.QUOTE_USAGE:
        return copy_api.t(
            READBACK_QUOTE_USAGE,
            locale=language,
            use_type=_use_type_label(values.get("use_type", ""), language=language),
            annual_mileage_band=_mileage_label(
                values.get("annual_mileage_band", ""), language=language
            ),
            garaging_jurisdiction=values.get("garaging_jurisdiction", ""),
        )
    return copy_api.t(
        READBACK_QUOTE_HISTORY,
        locale=language,
        at_fault_losses_3y=values.get("at_fault_losses_3y", ""),
        claims_3y=values.get("claims_3y", ""),
        prior_coverage_active=_coverage_label(
            values.get("prior_coverage_active", ""), language=language
        ),
        lapse_months=values.get("lapse_months", ""),
    )


READBACK_QUOTE_ALL = CopyKey("intake.readback.quote_all")


def build_quote_summary(
    blocks_to_read: Sequence[Block], values: Mapping[str, str], *, language: Locale
) -> str:
    """Toda la solicitud en una sola lectura, con una sola pregunta al final (2026-10-08).

    Antes se confirmaba bloque por bloque: cuatro "¿Es correcto?" para una cotizacion.
    Cada bloque se nombra con sus valores, como en su lectura propia (FD-U11-8).
    """
    partes: list[str] = []
    for bloque in blocks_to_read:
        if bloque is Block.QUOTE_DRIVER:
            partes.append(
                copy_api.t(
                    CopyKey("intake.readback.quote_driver_part"),
                    locale=language,
                    name=values.get("driver_name", ""),
                    birth_date=_fecha_legible(
                        values.get("driver_birth_date", ""), language=language
                    ),
                    license_years=values.get("license_years", ""),
                    license_jurisdiction=values.get("license_jurisdiction", ""),
                )
            )
        elif bloque is Block.QUOTE_VEHICLE:
            partes.append(
                copy_api.t(
                    CopyKey("intake.readback.quote_vehicle_part"),
                    locale=language,
                    vehicle_year=values.get("vehicle_year", ""),
                    vehicle_make=values.get("vehicle_make", ""),
                    vehicle_model=values.get("vehicle_model", ""),
                    vin=values.get("vin", ""),
                    salvage_title=_salvage_label(
                        values.get("salvage_title", ""), language=language
                    ),
                )
            )
        elif bloque is Block.QUOTE_USAGE:
            partes.append(
                copy_api.t(
                    CopyKey("intake.readback.quote_usage_part"),
                    locale=language,
                    use_type=_use_type_label(values.get("use_type", ""), language=language),
                    annual_mileage_band=_mileage_label(
                        values.get("annual_mileage_band", ""), language=language
                    ),
                    garaging_jurisdiction=values.get("garaging_jurisdiction", ""),
                )
            )
        elif bloque is Block.QUOTE_HISTORY:
            partes.append(
                copy_api.t(
                    CopyKey("intake.readback.quote_history_part"),
                    locale=language,
                    at_fault_losses_3y=values.get("at_fault_losses_3y", ""),
                    claims_3y=values.get("claims_3y", ""),
                    prior_coverage_active=_coverage_label(
                        values.get("prior_coverage_active", ""), language=language
                    ),
                    lapse_months=values.get("lapse_months", ""),
                )
            )
    return copy_api.t(READBACK_QUOTE_ALL, locale=language, summary=" ".join(partes))


def build_readback(  # noqa: PLR0911 -- un `return` por bloque: es la tabla de las lecturas, no logica
    block: Block, values: Mapping[str, str], *, language: Locale
) -> str:
    """FD-U11-8: la lectura de confirmacion de un bloque, con lo dicho nombrado.

    `values` es `field_key -> lo dicho` (ya normalizado cuando aplica). Un
    campo ausente resuelve a cadena vacia -- pasa solo cuando se llama con un
    bloque a medio completar, que no deberia ocurrir si quien orquesta espera
    a que el bloque este completo para leerlo.

    **Hay una segunda causa desde el 2026-09-29, y se dice en vez de heredarse**:
    un valor guardado que no se puede abrir --la fila la cerro otra clave tras una
    rotacion, o el dato esta corrupto-- tampoco llega aqui, y su hueco sale en la
    frase. Es el mismo escenario en que el caso entero ya esta degradado, y no se
    construyo maquinaria para el: quien orquesta lo omite y lo deja anotado.
    """
    match block:
        case Block.SAFETY:
            return copy_api.t(READBACK_SAFETY, locale=language, value=values.get("injuries", ""))
        case Block.IDENTITY_AND_POLICY:
            return copy_api.t(
                READBACK_IDENTITY_AND_POLICY,
                locale=language,
                value=values.get("identity_and_policy", ""),
            )
        case Block.WHAT_HAPPENED:
            return copy_api.t(READBACK_WHAT_HAPPENED, locale=language)
        case Block.WHEN_AND_WHERE:
            return copy_api.t(
                READBACK_WHEN_AND_WHERE,
                locale=language,
                when=values.get("incident_datetime", ""),
                where=values.get("location", ""),
            )
        case Block.VEHICLE_AND_DRIVER:
            return copy_api.t(
                READBACK_VEHICLE_AND_DRIVER,
                locale=language,
                value=values.get("vehicle_and_driver", ""),
            )
        case Block.OTHER_PARTIES:
            return copy_api.t(READBACK_OTHER_PARTIES, locale=language)
        case Block.QUOTE_DRIVER | Block.QUOTE_VEHICLE | Block.QUOTE_USAGE | Block.QUOTE_HISTORY:
            return _build_quote_readback(block, values, language=language)
        case _:
            msg = f"el bloque '{block.value}' no tiene lectura de confirmacion propia"
            raise ValueError(msg)


#: El siniestro ya no tiene resumen de cierre con "¿esta todo correcto?": desde el
#: 2026-10-06 (P4, decision de Miguel) cierra con la frase del recorrido rapido,
#: que compone el nodo (`composition.compose_fast_closing`). Quedan los dos tipos
#: que si lo tienen.
CLOSING_SUMMARY_COVERAGE = CopyKey("intake.closing.summary_coverage")
#: La solicitud no tiene un resumen que confirmar: cada bloque ya se confirmo. Este cierre es
#: ademas la frase de espera mientras el ritmo de fondo evalua la elegibilidad (BR2.5).
CLOSING_SUMMARY_QUOTE = CopyKey("intake.closing.summary_quote")


def closing_summary_key(record_type: RecordType) -> CopyKey:
    """Cual de las dos claves del resumen de cierre le toca a este tipo de caso."""
    if record_type is RecordType.COVERAGE_INQUIRY:
        return CLOSING_SUMMARY_COVERAGE
    if record_type is RecordType.QUOTE_REQUEST:
        return CLOSING_SUMMARY_QUOTE
    msg = "el siniestro cierra con la frase del recorrido rapido, no con un resumen (P4)"
    raise ValueError(msg)


def build_closing_summary(
    record_type: RecordType, values: Mapping[str, str], *, language: Locale
) -> str:
    """AC1.5.2, AC1.5.3: el resumen de cierre, ultimo bloque del orden fijo.

    Nombra lo dicho --lesiones, conductor y lugar entre ello (FD-U11-8)-- y no
    lo resume. Es una de las cuatro excepciones que AC1.5.3 declara al limite de
    veinticinco palabras, asi que no pasa por `assert_question_shape`.

    Se llega a este bloque solo cuando todos los campos del caso estan
    confirmados (`blocks.next_block`), asi que ninguna variable viene vacia.
    """
    if record_type is RecordType.QUOTE_REQUEST:
        return copy_api.t(CLOSING_SUMMARY_QUOTE, locale=language)
    if record_type is RecordType.COVERAGE_INQUIRY:
        return copy_api.t(
            CLOSING_SUMMARY_COVERAGE,
            locale=language,
            identity_and_policy=values.get("identity_and_policy", ""),
            question_asked=values.get("question_asked", ""),
        )
    msg = "el siniestro cierra con la frase del recorrido rapido, no con un resumen (P4)"
    raise ValueError(msg)


#: Formas de si/no, plegadas (sin tildes, minusculas). Una lista corta y
#: cerrada a proposito: BR3.1 exige un si explicito, y una lista larga de
#: sinonimos empezaria a adivinar donde la regla pide certeza.
_AFFIRMATIVE: dict[Locale, tuple[str, ...]] = {
    "es": ("si", "correcto", "exacto", "asi es", "claro"),
    "en": ("yes", "correct", "that.s right", "exactly", "right"),
}
#: Formas que niegan **dondequiera que aparezcan**: nombran la correccion.
_NEGATIVE: dict[Locale, tuple[str, ...]] = {
    "es": ("incorrecto", "no es correcto", "eso no es asi", "no es asi"),
    "en": ("incorrect", "not correct", "that.s wrong", "not right"),
}

#: El "no" a secas niega **solo cuando abre la respuesta**, y esto no es una
#: sutileza: la lectura del bloque de seguridad pregunta por las lesiones, asi
#: que "Si, no hubo heridos" es la forma normal de confirmarla. Buscando "no" en
#: cualquier posicion, esa respuesta se leia como una correccion, se volvia a
#: leer el bloque y la persona no tenia forma de salir del bucle.
_NEGATIVE_LEADING: dict[Locale, tuple[str, ...]] = {
    "es": ("no", "nada de eso"),
    "en": ("no", "nope"),
}

#: Las formas que confirman **aunque abran con un "no"**: "No, asi esta bien" es
#: un si en el que el "no" niega la duda, no el dato. Lo vio Miguel probando el
#: chat el 2026-10-06: la agente leia su "No, asi esta bien" como una correccion,
#: borraba el bloque y lo volvia a preguntar. Son frases enteras y no palabras
#: sueltas, para que "no esta bien" --que si corrige-- no entre: "esta bien" solo
#: cuenta precedido de "asi" o "todo", que es como se dice que algo quedo bien.
_AFFIRMATIVE_DESPITE_LEADING_NO: dict[Locale, tuple[str, ...]] = {
    "es": ("asi esta bien", "todo esta bien", "todo bien", "asi es correcto", "esta correcto"),
    "en": ("that.s fine", "that.s right", "all good", "looks good", "that works", "it.s correct"),
}


def _matches_any(text: str, phrases: tuple[str, ...]) -> bool:
    plegado = fold(text)
    return any(re.search(rf"\b{frase}\b", plegado) for frase in phrases)


def _opens_with_any(text: str, phrases: tuple[str, ...]) -> bool:
    plegado = fold(text).lstrip()
    return any(re.match(rf"{frase}\b", plegado) for frase in phrases)


def _en_los_dos_idiomas(tabla: dict[Locale, tuple[str, ...]]) -> tuple[str, ...]:
    """Las formas de los dos idiomas juntas.

    **Desde el 2026-10-06 el si y el no se reconocen en los dos idiomas a la vez.**
    Un "si", un "no" o un "asi esta bien" tienen menos de las cuatro palabras con
    las que el detector de idioma cambia de idioma (BR2.2), asi que llegan con el
    idioma que la conversacion tenia: en una aseguradora que habla ingles por
    omision, "No, asi esta bien" se leia como un no en ingles y la lectura se
    repetia (visto en produccion con Sunmeadow). Las formas son cortas y ninguna
    significa otra cosa en el otro idioma, asi que mirar las dos listas no abre
    ningun falso si. El idioma de la **respuesta** sigue siendo el de la
    conversacion; esto solo decide que dijo la persona.
    """
    return tuple(frase for lista in tabla.values() for frase in lista)


def is_negative(text: str, *, language: Locale) -> bool:
    """BR3.1: si la respuesta abre la correccion en vez de confirmar.

    Una correccion nombrada ("no es correcto") niega donde aparezca. Un "no" que
    abre la respuesta niega **salvo que lo que sigue sea una de las formas de
    "asi esta bien"**: ahi el "no" contesta a la duda y la frase confirma.
    `language` se conserva en la firma para quien llama; la busqueda mira los dos
    idiomas (ver `_en_los_dos_idiomas`).
    """
    del language
    if _matches_any(text, _en_los_dos_idiomas(_NEGATIVE)):
        return True
    if _matches_any(text, _en_los_dos_idiomas(_AFFIRMATIVE_DESPITE_LEADING_NO)):
        return False
    return _opens_with_any(text, _en_los_dos_idiomas(_NEGATIVE_LEADING))


def is_affirmative(text: str, *, language: Locale) -> bool:
    """BR3.1: si la respuesta a la lectura cuenta como el si que confirma.

    Lo negativo manda primero: "no es correcto" contiene la palabra
    "correcto", y sin esta comprobacion se leeria como un si. BR3.1 exige un
    si explicito, y una correccion nombrada no lo es aunque cite la palabra.
    """
    if is_negative(text, language=language):
        return False
    return _matches_any(text, _en_los_dos_idiomas(_AFFIRMATIVE)) or _matches_any(
        text, _en_los_dos_idiomas(_AFFIRMATIVE_DESPITE_LEADING_NO)
    )


def accepts_offer(text: str, *, language: Locale) -> bool:
    """P4: si la persona quiere agregar lo que la agente ofrecio al cerrar.

    La oferta no pregunta "¿es correcto?" sino "¿quiere agregar X, o lo dejamos
    para el ajustador?", y eso cambia lo que significa un "no" delante: "No, asi
    esta bien" aqui deja el caso como esta, mientras que ante una lectura
    confirmaba. Por eso la excepcion de `is_affirmative` no se aplica: un "no" que
    abre la respuesta declina, y hace falta un si explicito para preguntar mas.
    """
    if _opens_with_any(text, _en_los_dos_idiomas(_NEGATIVE_LEADING)) or _matches_any(
        text, _en_los_dos_idiomas(_NEGATIVE)
    ):
        return False
    return _matches_any(text, _en_los_dos_idiomas(_AFFIRMATIVE))


__all__ = [
    "READBACK_QUOTE_ALL",
    "accepts_offer",
    "build_closing_summary",
    "build_quote_summary",
    "build_readback",
    "closing_summary_key",
    "is_affirmative",
    "is_negative",
    "readback_key",
]
