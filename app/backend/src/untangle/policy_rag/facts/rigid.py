"""La respuesta de una pregunta rigida, armada con codigo desde el registro (plan 09, punto 6).

Decision de Miguel del 2026-11-02: lo que la persona pregunta y es un dato guardado en la poliza
emitida --el deducible, los limites, la vigencia, los vehiculos, los conductores, los endosos--
se contesta **sin recuperacion de clausulas, sin verificador de citas y sin un modelo que
redacte**. Es exacto (el valor sale del registro, no de lo que un modelo recuerde) y no gasta
tokens. Una pregunta de interpretacion --«¿me cubre un carro de alquiler?»-- no pasa por aqui y
sigue por la recuperacion con su cita verificada.

**El texto es del catalogo**, una plantilla por tema y por idioma (`chat.rigid.*`); lo que el
codigo pone son los valores del registro. Lo que dice la plantilla es lo que la poliza declara
--«segun tu poliza, el deducible es...»--, nunca que algo este o no cubierto: afirmar cobertura
sigue siendo cosa del ajustador y de la guardia de salida (P1).

`render` es pura: recibe la poliza ya leida y la fecha. La lectura de la base y el aislamiento
por aseguradora son de `api.py`. Devuelve `None` cuando el registro no trae el dato que el tema
pide --una poliza sin sus deducibles, por ejemplo--: quien llama sigue por el camino de siempre
en vez de contestar con un hueco.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from untangle.base import Locale, RigidTopic
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.policy_rag.corpus.models import IssuedPolicy
from untangle.policy_rag.facts import formatting, records
from untangle.policy_rag.facts.models import PolicyStatus

#: Las claves del corpus que cada plantilla nombra. Si el registro no trae alguna, no hay respuesta.
COLLISION_DEDUCTIBLE = "d.collision_deductible"
OTHER_DEDUCTIBLE = "d.other_than_collision_deductible"
BODILY_PER_PERSON = "a.bodily_injury_per_person"
BODILY_PER_ACCIDENT = "a.bodily_injury_per_accident"
PROPERTY_DAMAGE = "a.property_damage"
MEDICAL_PER_PERSON = "b.medical_payments_per_person"
UNINSURED_PER_PERSON = "c.uninsured_per_person"
UNINSURED_PER_ACCIDENT = "c.uninsured_per_accident"

#: Las plantillas del catalogo. Constantes de modulo con la clave literal: el chequeo de claves del
#: catalogo (BR3.4) las encuentra con un grep y una clave armada en ejecucion no.
DEDUCTIBLE_KEY = CopyKey("chat.rigid.deductible")
LIMITS_KEY = CopyKey("chat.rigid.limits")
VALIDITY_IN_FORCE_KEY = CopyKey("chat.rigid.validity.in_force")
VALIDITY_EXPIRED_KEY = CopyKey("chat.rigid.validity.expired")
VALIDITY_NOT_YET_KEY = CopyKey("chat.rigid.validity.not_yet")
VEHICLES_LISTED_KEY = CopyKey("chat.rigid.vehicles.listed")
VEHICLES_NONE_KEY = CopyKey("chat.rigid.vehicles.none")
DRIVERS_LISTED_KEY = CopyKey("chat.rigid.drivers.listed")
DRIVERS_NONE_KEY = CopyKey("chat.rigid.drivers.none")
ENDORSEMENTS_LISTED_KEY = CopyKey("chat.rigid.endorsements.listed")
ENDORSEMENTS_COUNT_ONLY_KEY = CopyKey("chat.rigid.endorsements.count_only")
ENDORSEMENTS_NONE_KEY = CopyKey("chat.rigid.endorsements.none")

#: Separador de una lista dentro de una frase: puntuacion, no palabra, para que sirva en los dos
#: idiomas sin escribir una conjuncion en linea.
_LIST_SEPARATOR = "; "


@dataclass(frozen=True)
class RigidAnswer:
    """La respuesta lista para pasar por la guardia: el tema, la clave de la plantilla y su texto."""

    topic: RigidTopic
    copy_key: CopyKey
    text: str


def render(  # noqa: PLR0913 -- el tema, la poliza y lo que cambia por turno: idioma, fecha, canal, endosos
    topic: RigidTopic,
    policy: IssuedPolicy,
    *,
    language: Locale,
    on: date,
    spoken: bool = False,
    clause_keys: Mapping[str, Sequence[str]] | None = None,
) -> RigidAnswer | None:
    """La respuesta del tema desde el registro, o `None` si el tema no es rigido o falta el dato."""
    respuesta: RigidAnswer | None = None
    match topic:
        case RigidTopic.DEDUCTIBLE:
            respuesta = _deductible(policy, language, spoken)
        case RigidTopic.LIMITS:
            respuesta = _limits(policy, language, spoken)
        case RigidTopic.VALIDITY:
            respuesta = _validity(policy, language, on)
        case RigidTopic.VEHICLES:
            respuesta = _vehicles(policy, language)
        case RigidTopic.DRIVERS:
            respuesta = _drivers(policy, language)
        case RigidTopic.ENDORSEMENTS:
            respuesta = _endorsements(policy, language, clause_keys or {})
        case RigidTopic.NONE:
            respuesta = None
    return respuesta


def _amounts(policy: IssuedPolicy, language: Locale, spoken: bool) -> dict[str, str]:
    """Cada limite y deducible del registro, escrito para el idioma y el canal."""
    return {
        clave: formatting.format_pesos(int(str(valor)), language, spoken=spoken)
        for clave, valor in policy.limits_and_deductibles.items()
    }


def _deductible(policy: IssuedPolicy, language: Locale, spoken: bool) -> RigidAnswer | None:
    montos = _amounts(policy, language, spoken)
    if COLLISION_DEDUCTIBLE not in montos or OTHER_DEDUCTIBLE not in montos:
        return None
    texto = copy_api.t(
        DEDUCTIBLE_KEY,
        locale=language,
        policy_number=policy.policy_number,
        collision=montos[COLLISION_DEDUCTIBLE],
        other=montos[OTHER_DEDUCTIBLE],
    )
    return RigidAnswer(RigidTopic.DEDUCTIBLE, DEDUCTIBLE_KEY, texto)


def _limits(policy: IssuedPolicy, language: Locale, spoken: bool) -> RigidAnswer | None:
    montos = _amounts(policy, language, spoken)
    necesarios = (
        BODILY_PER_PERSON,
        BODILY_PER_ACCIDENT,
        PROPERTY_DAMAGE,
        MEDICAL_PER_PERSON,
        UNINSURED_PER_PERSON,
        UNINSURED_PER_ACCIDENT,
    )
    if any(k not in montos for k in necesarios):
        return None
    texto = copy_api.t(
        LIMITS_KEY,
        locale=language,
        policy_number=policy.policy_number,
        bodily_person=montos[BODILY_PER_PERSON],
        bodily_accident=montos[BODILY_PER_ACCIDENT],
        property_damage=montos[PROPERTY_DAMAGE],
        medical_person=montos[MEDICAL_PER_PERSON],
        uninsured_person=montos[UNINSURED_PER_PERSON],
        uninsured_accident=montos[UNINSURED_PER_ACCIDENT],
    )
    return RigidAnswer(RigidTopic.LIMITS, LIMITS_KEY, texto)


def _validity(policy: IssuedPolicy, language: Locale, on: date) -> RigidAnswer:
    estado = records.status_on(policy, on)
    datos = {
        "policy_number": policy.policy_number,
        "start": formatting.format_date(policy.period_start, language),
        "end": formatting.format_date(policy.period_end, language),
    }
    if estado is PolicyStatus.IN_FORCE:
        clave = VALIDITY_IN_FORCE_KEY
        texto = copy_api.t(VALIDITY_IN_FORCE_KEY, locale=language, **datos)
    elif estado is PolicyStatus.EXPIRED:
        clave = VALIDITY_EXPIRED_KEY
        texto = copy_api.t(VALIDITY_EXPIRED_KEY, locale=language, **datos)
    else:
        clave = VALIDITY_NOT_YET_KEY
        texto = copy_api.t(VALIDITY_NOT_YET_KEY, locale=language, **datos)
    return RigidAnswer(RigidTopic.VALIDITY, clave, texto)


def _vehicles(policy: IssuedPolicy, language: Locale) -> RigidAnswer:
    vehiculos = records.vehicles_of(policy)
    if not vehiculos:
        clave = VEHICLES_NONE_KEY
        texto = copy_api.t(VEHICLES_NONE_KEY, locale=language, policy_number=policy.policy_number)
    else:
        clave = VEHICLES_LISTED_KEY
        texto = copy_api.t(
            VEHICLES_LISTED_KEY,
            locale=language,
            policy_number=policy.policy_number,
            vehicles=_LIST_SEPARATOR.join(v.description for v in vehiculos),
        )
    return RigidAnswer(RigidTopic.VEHICLES, clave, texto)


def _drivers(policy: IssuedPolicy, language: Locale) -> RigidAnswer:
    conductores = records.drivers_of(policy)
    if not conductores:
        clave = DRIVERS_NONE_KEY
        texto = copy_api.t(DRIVERS_NONE_KEY, locale=language, policy_number=policy.policy_number)
    else:
        clave = DRIVERS_LISTED_KEY
        texto = copy_api.t(
            DRIVERS_LISTED_KEY,
            locale=language,
            policy_number=policy.policy_number,
            drivers=_LIST_SEPARATOR.join(d.full_name for d in conductores),
        )
    return RigidAnswer(RigidTopic.DRIVERS, clave, texto)


def _endorsements(
    policy: IssuedPolicy, language: Locale, clause_keys: Mapping[str, Sequence[str]]
) -> RigidAnswer:
    endosos = records.endorsements_of(policy, clause_keys=clause_keys, language=language)
    frases = [frase for e in endosos for frase in e.summaries]
    if not endosos:
        clave = ENDORSEMENTS_NONE_KEY
        texto = copy_api.t(
            ENDORSEMENTS_NONE_KEY, locale=language, policy_number=policy.policy_number
        )
    elif not frases:
        # Trae endosos pero no se sabe que cambia cada uno: se dice cuantos, sin inventar su efecto.
        clave = ENDORSEMENTS_COUNT_ONLY_KEY
        texto = copy_api.t(
            ENDORSEMENTS_COUNT_ONLY_KEY,
            locale=language,
            policy_number=policy.policy_number,
            count=str(len(endosos)),
        )
    else:
        clave = ENDORSEMENTS_LISTED_KEY
        texto = copy_api.t(
            ENDORSEMENTS_LISTED_KEY,
            locale=language,
            policy_number=policy.policy_number,
            endorsements=_LIST_SEPARATOR.join(frases),
        )
    return RigidAnswer(RigidTopic.ENDORSEMENTS, clave, texto)


__all__ = ["RigidAnswer", "render"]
