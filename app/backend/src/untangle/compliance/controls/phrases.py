"""Las frases de U10: una clave del catalogo por cosa que se dice, escrita una vez.

Ninguna frase se escribe aqui. Todas salen del catalogo de textos por idioma
(convencion 4 del equipo), y este modulo es el unico sitio que dice **que clave**
corresponde a cada categoria de la guardia, a cada modo de la frase de emergencia
y a cada hallazgo de la revision.

**La correspondencia se escribe entera y no se compone**, igual que las
etiquetas del caso de U4: una clave armada con el valor del enum romperia el
chequeo que exige un consumidor literal de cada clave, y un valor nuevo sin su
clave no fallaria en ningun sitio. Por la misma razon cada frase se resuelve con
su constante y no con una variable: el chequeo BR3.4 del catalogo rechaza una
clave que no sea literal en el punto donde se pide.

La afirmacion de ser humana no tiene frase propia: la reemplaza la respuesta
fija de identidad (AC1.10.1 y AC1.10.2), que es exactamente lo que hay que decir
en su lugar. Una sola clave para las dos cosas, porque dos entradas con el mismo
texto es como un dia dejan de decir lo mismo.
"""

from __future__ import annotations

from enum import StrEnum

from untangle.base import Locale
from untangle.compliance.controls.models import FindingCode, GuardCategory
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey

# --- Lo que sale en lugar de una frase detenida (BR1.4) ----------------------

COVERAGE_PROMISE = CopyKey("compliance.guard.coverage_promise")
AMOUNT = CopyKey("compliance.guard.amount")
FAULT = CopyKey("compliance.guard.fault")
LEGAL_ADVICE = CopyKey("compliance.guard.legal_advice")
TRANSFER_OR_DEADLINE = CopyKey("compliance.guard.transfer_or_deadline")
CONFIG_DISCLOSURE = CopyKey("compliance.guard.config_disclosure")

#: Lo que sale cuando la guardia no pudo evaluar: la frase no sale (BR1.5).
GUARD_DEGRADED = CopyKey("compliance.guard.degraded")

# --- Las frases fijas de los criterios ---------------------------------------

#: AC1.10.1 y AC1.10.2. Tambien la que reemplaza una afirmacion de humanidad.
IDENTITY_ANSWER = CopyKey("compliance.identity.answer")
#: AC1.6.3, superficies publicas: la de por omision (BR3.3).
EMERGENCY_PUBLIC = CopyKey("compliance.emergency.public")
#: AC1.6.3, despliegue local: la que comprueban DS-2 y DS-6 (AC1.6.4).
EMERGENCY_LOCAL = CopyKey("compliance.emergency.local")
#: AC1.9.1 en espanol; en ingles, el texto del PRD (recorrido 7.x). Es la frase
#: de toda derivacion: dice que un ajustador revisa el caso con lo capturado, sin
#: transferencia ni plazo (AC1.9.2).
HANDOFF = CopyKey("compliance.handoff.adjuster_review")
#: AC1.17.2: el cierre directo, sin prometer cobertura ni montos (BR6.4).
DIRECT_CLOSE = CopyKey("compliance.closure.direct")

# --- Que falta, dicho para la bandeja (ComplianceFinding.detail_key) ---------

FINDING_DISCLOSURE_MISSING = CopyKey("compliance.finding.disclosure_missing")
FINDING_HUMAN_ROUTE_MISSED = CopyKey("compliance.finding.human_route_missed")
FINDING_ATTACHMENT_MISSING = CopyKey("compliance.finding.attachment_missing")

#: La frase que sale en lugar de cada categoria (BR1.4).
ALLOWED_KEYS: dict[GuardCategory, CopyKey] = {
    GuardCategory.COVERAGE_PROMISE: COVERAGE_PROMISE,
    GuardCategory.AMOUNT: AMOUNT,
    GuardCategory.FAULT: FAULT,
    GuardCategory.LEGAL_ADVICE: LEGAL_ADVICE,
    GuardCategory.HUMANITY_CLAIM: IDENTITY_ANSWER,
    GuardCategory.TRANSFER_OR_DEADLINE: TRANSFER_OR_DEADLINE,
    GuardCategory.CONFIG_DISCLOSURE: CONFIG_DISCLOSURE,
}

#: Que dice la bandeja de cada hallazgo de la revision (BR5.1).
FINDING_KEYS: dict[FindingCode, CopyKey] = {
    FindingCode.DISCLOSURE_MISSING: FINDING_DISCLOSURE_MISSING,
    FindingCode.HUMAN_ROUTE_MISSED: FINDING_HUMAN_ROUTE_MISSED,
    FindingCode.ATTACHMENT_MISSING: FINDING_ATTACHMENT_MISSING,
}


class EmergencyPhraseMode(StrEnum):
    """Donde corre la demo, y por eso que frase de emergencia dice (BR3.3, CG-U10-2).

    La elige `UNTANGLE_EMERGENCY_PHRASE`. `public` es la de por omision: la demo
    publica no puede enviar ayuda, y lo seguro cuando nadie dijo nada es decirlo.
    """

    PUBLIC = "public"
    LOCAL = "local"


def emergency_key(mode: EmergencyPhraseMode) -> CopyKey:
    """La clave de la indicacion de emergencia para ese despliegue."""
    return EMERGENCY_LOCAL if mode is EmergencyPhraseMode.LOCAL else EMERGENCY_PUBLIC


def allowed_text(category: GuardCategory, *, locale: Locale) -> str:
    """La frase permitida de una categoria, en su idioma (BR1.4)."""
    match category:
        case GuardCategory.COVERAGE_PROMISE:
            frase = copy_api.t(COVERAGE_PROMISE, locale=locale)
        case GuardCategory.AMOUNT:
            frase = copy_api.t(AMOUNT, locale=locale)
        case GuardCategory.FAULT:
            frase = copy_api.t(FAULT, locale=locale)
        case GuardCategory.LEGAL_ADVICE:
            frase = copy_api.t(LEGAL_ADVICE, locale=locale)
        case GuardCategory.HUMANITY_CLAIM:
            frase = copy_api.t(IDENTITY_ANSWER, locale=locale)
        case GuardCategory.TRANSFER_OR_DEADLINE:
            frase = copy_api.t(TRANSFER_OR_DEADLINE, locale=locale)
        case GuardCategory.CONFIG_DISCLOSURE:
            frase = copy_api.t(CONFIG_DISCLOSURE, locale=locale)
    return frase


def degraded_text(*, locale: Locale) -> str:
    """Lo que sale cuando la guardia no pudo evaluar (BR1.5)."""
    return copy_api.t(GUARD_DEGRADED, locale=locale)


def identity_answer_text(*, locale: Locale) -> str:
    """La respuesta fija a la pregunta de identidad (AC1.10.1, AC1.10.2)."""
    return copy_api.t(IDENTITY_ANSWER, locale=locale)


def emergency_text(mode: EmergencyPhraseMode, *, locale: Locale) -> str:
    """La indicacion de emergencia para ese despliegue, en su idioma (AC1.6.3)."""
    if mode is EmergencyPhraseMode.LOCAL:
        return copy_api.t(EMERGENCY_LOCAL, locale=locale)
    return copy_api.t(EMERGENCY_PUBLIC, locale=locale)


def handoff_text(*, locale: Locale) -> str:
    """La frase fija de toda derivación (AC1.9.1), para quien solo necesita el texto.

    Otras unidades (U8, tanda 3) reutilizan esta misma clave para su propia
    derivación genérica en vez de inventar una segunda forma de decirlo; este
    envoltorio existe para que la resuelvan sin llamar a `copy_api.t` con una
    clave que no es literal en su propio archivo (BR3.4 del catálogo).
    """
    return copy_api.t(HANDOFF, locale=locale)


def all_keys() -> frozenset[CopyKey]:
    """Todas las claves que este modulo promete que el catalogo trae."""
    return frozenset(
        {
            *ALLOWED_KEYS.values(),
            GUARD_DEGRADED,
            IDENTITY_ANSWER,
            EMERGENCY_PUBLIC,
            EMERGENCY_LOCAL,
            HANDOFF,
            DIRECT_CLOSE,
            *FINDING_KEYS.values(),
        }
    )
