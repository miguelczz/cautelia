"""Extraccion por turno, con su evidencia, delimitada del prompt de sistema (BR2.1 a BR2.4).

**Solo lo dicho en este turno** (BR2.1): esta funcion no ve turnos anteriores
ni el estado del caso -- los recibe quien la llama si algun dia hicieran
falta, y hoy no hacen falta porque el modelo extrae de un solo turno a la vez
-- y no completa un campo que la persona no dijo, aunque sea deducible: lo que
el modelo no devolvio, esta funcion no lo inventa.

**BR2.3, la compuerta dura.** El texto de la persona entra como
`PromptPart(text=ExternalText(...))`, nunca dentro de `SystemInstruction`. Los
dos tipos son distintos (`providers/ports.py`, `ExternalText` e
`InstructionText`) y `Prompt` los guarda en campos separados que la API del
proveedor nunca junta en una sola cadena (capa 7 del diseno de seguridad,
`ports.py`); `build_extraction_prompt` no hace mas que respetar esa
separacion, y su prueba lo aisla comprobando exactamente eso: lo que la
persona escribio nunca aparece dentro de `prompt.instruction.text`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from datetime import date

from untangle.base import Frozen, Locale
from untangle.compliance.redaction.api import redact
from untangle.orchestration.nodes.intake import normalization
from untangle.providers.ports import (
    ExternalText,
    GenerationResult,
    Prompt,
    PromptPart,
    SystemInstruction,
)


class ExtractedItem(Frozen):
    """Un campo que el modelo dice haber escuchado en este turno, sin normalizar todavia."""

    field_key: str
    value: str


class ExtractionResponse(Frozen):
    """La forma que se le pide al modelo (BR2.1): una lista, vacia si no dijo nada nuevo."""

    items: tuple[ExtractedItem, ...] = ()


class ExtractedField(Frozen):
    """Un campo extraido, con su evidencia -- la misma forma que `IntakeTurnResult.extracted`."""

    field_key: str
    value: str
    #: El valor tras la regla versionada de su tipo (BR2.4), o `None` cuando
    #: el campo no tiene una regla de normalizacion o el texto no la cumple:
    #: en los dos casos el valor dicho se conserva sin cambios.
    normalized: str | None
    #: BR2.2: de que turno salio. Sin esto no se escribe (BR2.2, `entities.md`).
    evidence_turn_id: str
    #: Lo que la persona dijo, ya redactado, para poder comparar la lectura de
    #: confirmacion contra lo dicho (AC1.7.4). U4 no guarda este texto junto al
    #: campo -- solo `evidence_turn_id`, una referencia -- asi que quien
    #: necesite volver a leerlo puede hacerlo con `transcript_of` (C-12) y este
    #: valor aqui es para quien compone la lectura en el mismo turno, sin ida y
    #: vuelta a la base.
    evidence_verbatim_redacted: str


#: Como el nodo pide la extraccion, por closure desde la raiz de composicion:
#: la misma forma que `EmbedPort` en `policy_verification` o `ReviewPort` en
#: `compliance`. Cablea `TextGenerator.generate` con `schema=ExtractionResponse`.
ExtractorPort = Callable[[Prompt], Awaitable[GenerationResult]]

#: Los campos con regla de normalizacion versionada, y cual (BR2.4, FD-U11-2).
#: Un campo que no esta aqui no tiene regla: su valor normalizado es `None` y
#: el dicho se conserva tal cual.
_NORMALIZERS: dict[str, str] = {
    "policy_number": "policy_number",
    "plate": "plate",
    "national_id": "national_id",
    "phone": "phone",
    "incident_date": "incident_date",
}


#: Los campos de la solicitud de cotizacion que **tienen que llegar convertidos** (U19):
#: los que las reglas de elegibilidad leen y los que de ellos se derivan. Para estos el
#: valor que se escribe en el caso es el canonico --`true`, `7`, `commercial`-- y no lo
#: dicho, y un valor que no se puede convertir **no se escribe**: el campo queda sin decir
#: y se vuelve a preguntar. Dejar pasar "uso: a veces" como valor dejaria la regla que lo
#: lee sin poder disparar, y nada se pondria rojo (BR1.3).
#:
#: El resto de los campos de la solicitud (nombre, fecha de nacimiento, marca, modelo,
#: jurisdicciones, VIN) se escriben como se dijeron, igual que los del siniestro.
_QUOTE_TYPED: dict[str, Callable[..., str | None]] = {
    "license_years": normalization.normalize_license_years,
    "vehicle_year": normalization.normalize_vehicle_year,
    "salvage_title": normalization.normalize_yes_no,
    "use_type": normalization.normalize_use_type,
    "annual_mileage_band": normalization.normalize_mileage_band,
    "at_fault_losses_3y": normalization.normalize_count,
    "claims_3y": normalization.normalize_count,
    "prior_coverage_active": normalization.normalize_yes_no,
    "lapse_months": normalization.normalize_lapse_months,
}

#: Los campos de la cotizacion que llegan convertidos, para quien compare valores.
QUOTE_TYPED_FIELDS: frozenset[str] = frozenset(_QUOTE_TYPED)

#: Los campos que **solo escribe el codigo**, nunca el modelo: si el modelo devuelve uno,
#: se descarta. Son los derivados, y dejar que el modelo los escriba seria tener dos
#: sitios que calculan lo mismo (BR1.4).
DERIVED_FIELDS: frozenset[str] = frozenset({"vehicle_age_years"})


def build_extraction_prompt(
    instruction: SystemInstruction, turn_text: str, *, asked: str | None = None
) -> Prompt:
    """BR2.3: el texto de la persona, delimitado, con la pregunta que contesta delante.

    `asked` es la pregunta que la agente acaba de hacer, del catalogo, y entra como
    el turno anterior del modelo y no en la instruccion: es conversacion, no regla.
    Sin ella el modelo no sabe que contesta una respuesta corta: «Sí, dos personas»
    a «¿Hubo alguien herido?» se guardaba como las otras personas involucradas, la
    pregunta de seguridad se repetia y el caso no avanzaba (visto por Miguel el
    2026-10-07). El texto de la persona sigue siendo la unica parte externa.
    """
    partes: list[PromptPart] = []
    if asked:
        partes.append(PromptPart(role="model", text=ExternalText(asked)))
    partes.append(PromptPart(role="user", text=ExternalText(turn_text)))
    return Prompt(instruction=instruction, parts=tuple(partes))


def _normalize(field_key: str, value: str, *, language: Locale, now: date) -> str | None:
    regla = _NORMALIZERS.get(field_key)
    if regla is None:
        return None
    if regla == "policy_number":
        return normalization.normalize_policy_number(value, language=language)
    if regla == "plate":
        return normalization.normalize_plate(value, language=language)
    if regla == "national_id":
        return normalization.normalize_national_id(value, language=language)
    if regla == "phone":
        return normalization.normalize_phone(value, language=language)
    # "incident_date": la unica regla que devuelve algo que no es texto ya.
    fecha = normalization.normalize_relative_date(value, language=language, now=now)
    return fecha.isoformat() if fecha is not None else None


def _typed_value(field_key: str, value: str, *, language: Locale, now: date) -> str | None:
    """El valor canonico de un campo tipado de la solicitud, o `None` si no se puede convertir."""
    convertir = _QUOTE_TYPED[field_key]
    if field_key == "vehicle_year":
        return convertir(value, now=now)
    return convertir(value, language=language)


def extract_fields(  # noqa: PLR0913 -- el turno se describe con estos cinco datos y el filtro por tipo de caso
    response: ExtractionResponse,
    *,
    turn_id: str,
    turn_text: str,
    language: Locale,
    now: date,
    allowed_keys: frozenset[str] | None = None,
) -> tuple[ExtractedField, ...]:
    """BR2.1, BR2.2, BR2.4: los campos que el modelo dijo, con evidencia y normalizados.

    `turn_text` es el turno **completo**, no un fragmento por campo: la
    evidencia de BR2.2 es "lo que la persona dijo" en el turno del que salio
    el campo, y un turno puede llenar mas de un campo a la vez (contar una
    historia completa en un solo mensaje es justamente lo que BR3.3 -- el dato
    adelantado -- necesita poder capturar).
    """
    redactado = str(redact(turn_text, language=language))
    extraidos: list[ExtractedField] = []
    for item in response.items:
        if item.field_key in DERIVED_FIELDS:
            continue
        if allowed_keys is not None and item.field_key not in allowed_keys:
            # Un campo que el tipo de caso no declara no se escribe: el caso lo
            # rechazaria al guardarlo y el turno entero caeria por un campo de otro tipo.
            continue
        if item.field_key in _QUOTE_TYPED:
            canonico = _typed_value(item.field_key, item.value, language=language, now=now)
            if canonico is None:
                continue
            valor: str = canonico
            normalizado: str | None = canonico
        else:
            valor = item.value
            normalizado = _normalize(item.field_key, item.value, language=language, now=now)
        extraidos.append(
            ExtractedField(
                field_key=item.field_key,
                value=valor,
                normalized=normalizado,
                evidence_turn_id=turn_id,
                evidence_verbatim_redacted=redactado,
            )
        )
    extraidos.extend(_derived_fields(extraidos, now=now))
    return tuple(extraidos)


def _derived_fields(
    extracted: Sequence[ExtractedField], *, now: date
) -> tuple[ExtractedField, ...]:
    """Lo que se deduce de lo extraido en **este** turno, con la misma evidencia (BR1.4).

    La antiguedad del vehiculo sale del anio del modelo, y los meses sin cobertura de quien
    tiene cobertura vigente salen en cero. Comparten el turno de su origen: no hay campo sin
    evidencia, y si la persona corrige el dato, se vuelve a derivar con el.
    """
    por_clave = {campo.field_key: campo for campo in extracted}
    derivados: list[ExtractedField] = []

    anio = por_clave.get("vehicle_year")
    if anio is not None:
        antiguedad = normalization.derive_vehicle_age(anio.value, now=now)
        if antiguedad is not None:
            derivados.append(_derived_from(anio, "vehicle_age_years", antiguedad))

    cobertura = por_clave.get("prior_coverage_active")
    if cobertura is not None and "lapse_months" not in por_clave:
        meses = normalization.derive_lapse_months(cobertura.value)
        if meses is not None:
            derivados.append(_derived_from(cobertura, "lapse_months", meses))
    return tuple(derivados)


def _derived_from(origin: ExtractedField, field_key: str, value: str) -> ExtractedField:
    return ExtractedField(
        field_key=field_key,
        value=value,
        normalized=value,
        evidence_turn_id=origin.evidence_turn_id,
        evidence_verbatim_redacted=origin.evidence_verbatim_redacted,
    )


__all__ = [
    "DERIVED_FIELDS",
    "QUOTE_TYPED_FIELDS",
    "ExtractedField",
    "ExtractedItem",
    "ExtractionResponse",
    "ExtractorPort",
    "build_extraction_prompt",
    "extract_fields",
]
