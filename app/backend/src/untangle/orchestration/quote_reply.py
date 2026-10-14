"""Lo que la agente dice de una cotizacion fuera de la captura (U19, BR1.5, BR2.3, BR3.1, BR3.2).

Tres cosas, todas frases fijas del catalogo --ninguna la improvisa un modelo--:

1. **Donde la cotizacion esta apagada**, la peticion de cotizar recibe una respuesta util
   (AC6.1.3): esta demostracion no cotiza, y lo que si puede hacer. No se ofrece lo que esta
   aseguradora no tiene activo.
2. **Ante la insistencia en un precio**, una frase que no da ninguna cifra y ofrece la banda
   (AC6.2.4, BR3.2). Dejar que el modelo improvise la negativa es dejarle la oportunidad de
   ceder, que es justo lo que los casos adversariales buscan.
3. **La respuesta a la solicitud**: la salida, la razon en lenguaje llano y la banda (BR2.3).

**No importa `untangle.rules`**, a proposito. La elegibilidad se evalua en el ritmo de fondo
(BR2.5) y este modulo lo importa el camino del turno: si llegara al motor de reglas, el turno
lo arrastraria con el. Recibe la salida y la banda como **texto** --los valores de los enums de
`rules.eligibility`-- y una prueba compara los dos conjuntos en los dos sentidos, asi que un
valor nuevo sin su frase falla alli y no en una conversacion.

**Ninguna de estas frases lleva un importe, un simbolo o codigo de moneda, ni un porcentaje**
(BR3.1, compuerta dura). No se construye un detector aqui: la guardia de salida ya los caza en
los dos idiomas (FD-U19-1), y lo que esta unidad anade son los casos de DS-4 que la ejercitan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from untangle.base import Locale
from untangle.case_record.models import RecordType
from untangle.compliance.controls.normalization import normalize
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey

REPLY_ELIGIBLE = CopyKey("quote.reply.eligible")
REPLY_NOT_ELIGIBLE = CopyKey("quote.reply.not_eligible")
REPLY_REFERRED = CopyKey("quote.reply.referred")
PRICE_REFUSAL = CopyKey("quote.reply.price_refusal")
PRICE_REFUSAL_WITH_BAND = CopyKey("quote.reply.price_refusal_with_band")
UNAVAILABLE = CopyKey("quote.reply.unavailable")

BAND_STANDARD_RISK = CopyKey("quote.band.standard_risk")
BAND_ELEVATED_RISK = CopyKey("quote.band.elevated_risk")
BAND_PENDING_REVIEW = CopyKey("quote.band.pending_review")
BAND_OUTSIDE_APPETITE = CopyKey("quote.band.outside_appetite")

#: Las razones de la elegibilidad, una por clave `then.explanation_key` de
#: `rules/eligibility.yaml`. Escritas enteras y no compuestas, por la razon de todo el
#: proyecto: una clave armada en ejecucion deja fuera del chequeo de claves sin consumidor a
#: la que no se vea. Una clave que el YAML nombre y esta tabla no conozca falla en una
#: prueba, y aqui levanta: una razon que sale vacia diria "no" sin decir por que.
EXPLAIN_COMMERCIAL_USE = CopyKey("rules.explain.quote_commercial_use")
EXPLAIN_SALVAGE_TITLE = CopyKey("rules.explain.quote_salvage_title")
EXPLAIN_AT_FAULT_LOSSES = CopyKey("rules.explain.quote_at_fault_losses")
EXPLAIN_NEW_LICENSE = CopyKey("rules.explain.quote_new_license")
EXPLAIN_OLD_VEHICLE = CopyKey("rules.explain.quote_old_vehicle")
EXPLAIN_STANDARD_RISK = CopyKey("rules.explain.quote_standard_risk")
EXPLAIN_ELEVATED_RISK = CopyKey("rules.explain.quote_elevated_risk")

#: Las claves de razon que esta tabla sabe decir. La prueba las compara con las de cada
#: `eligibility.yaml`.
KNOWN_EXPLANATION_KEYS: frozenset[str] = frozenset(
    {
        EXPLAIN_COMMERCIAL_USE,
        EXPLAIN_SALVAGE_TITLE,
        EXPLAIN_AT_FAULT_LOSSES,
        EXPLAIN_NEW_LICENSE,
        EXPLAIN_OLD_VEHICLE,
        EXPLAIN_STANDARD_RISK,
        EXPLAIN_ELEVATED_RISK,
    }
)

#: Los valores de las salidas y de las bandas que este modulo sabe decir, como texto.
KNOWN_OUTCOMES: frozenset[str] = frozenset({"eligible", "not_eligible", "referred"})
KNOWN_BANDS: frozenset[str] = frozenset(
    {"standard_risk", "elevated_risk", "pending_review", "outside_appetite"}
)


@dataclass(frozen=True)
class QuoteReply:
    """La clave del catalogo y el texto ya resuelto, igual que `ComposedTurn`."""

    key: str
    text: str


# --- Reconocer la peticion -----------------------------------------------------
#
# Reconocedores deterministas y bilingues, como el del desvio de cobertura: la categoria de un
# turno la deciden reglas y no el modelo. No son NLU; son lo bastante anchos para los casos de
# DS-4 y se amplian el dia que un caso nuevo los pida mas anchos, con ese caso delante.

_QUOTE_REQUEST: dict[Locale, re.Pattern[str]] = {
    "es": re.compile(
        r"\b(cotiz\w*|presupuesto|sacar (un )?seguro|quiero (un )?seguro"
        r"|asegurar (mi|el) (carro|auto|vehiculo|coche))\b"
    ),
    "en": re.compile(
        r"\b(quotes?|quoting|get (a |an )?(insurance|policy)|insure my (car|vehicle)"
        r"|new (insurance )?policy)\b"
    ),
}

_PRICE_REQUEST: dict[Locale, re.Pattern[str]] = {
    "es": re.compile(
        r"\b(cuanto\b[^.?!]{0,25}\b(cuesta|cuestan|vale|valdria|saldria|sale|costaria|costar"
        r"|pagar|pagaria|cobran|cobra)|precio|precios|prima|tarifa|cuota|mensualidad|costo"
        # "aproximadamente", "estimado", "al mes" o "monto" solos no piden un precio:
        # "llevo aproximadamente 4 anos con licencia" disparaba la frase de que la
        # demo no calcula precios (C7, visto el 2026-10-07). Cuentan junto a un valor.
        r"|(valor|cifra|monto|costo|numero) (aproximad\w*|estimad\w*)"
        r"|(pagaria|pago|pagar|cuesta|costaria) (al mes|por mes|mensual\w*)"
        r"|(dame|dime|deme|digame) (una|un|algun\w*) (cifra|numero|valor|estimado)"
        r"|un estimado(?! de)|cualquier numero"
        r"|(dame|dime|deme|digame) (un|algun|el) (numero|valor))\b"
    ),
    "en": re.compile(
        r"\b(how much|price|prices|pricing|premium|rates?|what (would|do) i pay"
        # "a month", "monthly", "figure" or "estimate" alone do not ask for a price: "I was
        # uninsured for a month" did (C7). They count next to a payment word.
        r"|(pay|cost|costs) (per month|a month|monthly)|ballpark|price estimate"
        r"|(monthly|yearly|annual) (cost|premium|payment|price)"
        r"|(give|tell) me (a|an|any|the) (figure|estimate)"
        r"|rough (number|figure|idea|estimate)|any number"
        r"|(give|tell) me (a|an|any|the) (number|value))\b"
    ),
}


def is_quote_request(text: str, *, language: Locale) -> bool:
    """El turno pide una cotizacion."""
    return _QUOTE_REQUEST[language].search(normalize(text)) is not None


def is_price_request(text: str, *, language: Locale) -> bool:
    """El turno pregunta cuanto cuesta o insiste en un precio."""
    return _PRICE_REQUEST[language].search(normalize(text)) is not None


# --- Las frases ------------------------------------------------------------------


def band_sentence(band: str, *, language: Locale) -> str:
    """Donde queda el riesgo, en lenguaje llano. Habla de riesgo y nunca de precio (Q1)."""
    match band:
        case "standard_risk":
            return copy_api.t(BAND_STANDARD_RISK, locale=language)
        case "elevated_risk":
            return copy_api.t(BAND_ELEVATED_RISK, locale=language)
        case "pending_review":
            return copy_api.t(BAND_PENDING_REVIEW, locale=language)
        case "outside_appetite":
            return copy_api.t(BAND_OUTSIDE_APPETITE, locale=language)
        case _:
            msg = f"la banda '{band}' no tiene frase propia (BR2.2)"
            raise ValueError(msg)


def outcome_sentence(outcome: str, *, language: Locale) -> str:
    """Lo que pasa con la solicitud: sigue, no puede seguir o la revisa una persona."""
    match outcome:
        case "eligible":
            return copy_api.t(REPLY_ELIGIBLE, locale=language)
        case "not_eligible":
            return copy_api.t(REPLY_NOT_ELIGIBLE, locale=language)
        case "referred":
            return copy_api.t(REPLY_REFERRED, locale=language)
        case _:
            msg = f"la salida '{outcome}' no tiene frase propia (BR2.1)"
            raise ValueError(msg)


def explanation_sentence(explanation_key: str, *, language: Locale) -> str:  # noqa: PLR0911 -- una clave por razon: es la tabla de las razones, no logica
    """La razon en lenguaje llano de la regla que decidio (BR2.3). Nunca un identificador de regla."""
    match explanation_key:
        case "rules.explain.quote_commercial_use":
            return copy_api.t(EXPLAIN_COMMERCIAL_USE, locale=language)
        case "rules.explain.quote_salvage_title":
            return copy_api.t(EXPLAIN_SALVAGE_TITLE, locale=language)
        case "rules.explain.quote_at_fault_losses":
            return copy_api.t(EXPLAIN_AT_FAULT_LOSSES, locale=language)
        case "rules.explain.quote_new_license":
            return copy_api.t(EXPLAIN_NEW_LICENSE, locale=language)
        case "rules.explain.quote_old_vehicle":
            return copy_api.t(EXPLAIN_OLD_VEHICLE, locale=language)
        case "rules.explain.quote_standard_risk":
            return copy_api.t(EXPLAIN_STANDARD_RISK, locale=language)
        case "rules.explain.quote_elevated_risk":
            return copy_api.t(EXPLAIN_ELEVATED_RISK, locale=language)
        case _:
            msg = f"la razon '{explanation_key}' no tiene frase propia (BR2.3)"
            raise ValueError(msg)


def compose_eligibility_reply(
    outcome: str, band: str, explanation_key: str, *, language: Locale
) -> str:
    """La respuesta a la solicitud: la salida, la razon en lenguaje llano y la banda (AC6.2.1, AC6.2.3).

    Sin identificadores de regla, sin nombre de aseguradora y sin una sola cifra (BR2.3,
    BR3.1). Lo que la decidio --`deciding_rules`-- va a la traza y a la bandeja, no aqui.
    """
    return " ".join(
        (
            outcome_sentence(outcome, language=language),
            explanation_sentence(explanation_key, language=language),
            band_sentence(band, language=language),
        )
    )


def compose_price_refusal(band: str | None, *, language: Locale) -> QuoteReply:
    """La negativa a dar un precio, que ofrece la banda (AC6.2.4, BR3.2).

    Con la banda cuando el ritmo de fondo ya la dejo; sin ella cuando todavia no, que dice
    que se la dira al terminar y no inventa una.
    """
    if band is None:
        return QuoteReply(key=str(PRICE_REFUSAL), text=copy_api.t(PRICE_REFUSAL, locale=language))
    return QuoteReply(
        key=str(PRICE_REFUSAL_WITH_BAND),
        text=copy_api.t(
            PRICE_REFUSAL_WITH_BAND,
            locale=language,
            band=band_sentence(band, language=language),
        ),
    )


def compose_unavailable(*, language: Locale) -> QuoteReply:
    """Donde la cotizacion esta apagada: no cotiza, y lo que si puede hacer (AC6.1.3, BR1.5)."""
    return QuoteReply(key=str(UNAVAILABLE), text=copy_api.t(UNAVAILABLE, locale=language))


def reply_before_capture(  # noqa: PLR0913 -- las cinco cosas que decide la respuesta, ninguna derivable de otra
    *,
    record_type: RecordType,
    anything_captured: bool,
    quote_enabled: bool,
    text: str,
    language: Locale,
    band: str | None = None,
) -> QuoteReply | None:
    """La respuesta fija a una peticion de cotizacion o de precio, o `None` si no toca.

    - Un turno que pide cotizar **antes de haber capturado nada** de un siniestro, en una
      aseguradora con la cotizacion apagada, recibe la respuesta de AC6.1.3. **Solo antes de
      capturar nada**: a mitad de un reporte, "el taller me dio una cotizacion" es parte del
      relato y no una peticion.
    - Un turno que pregunta por el precio dentro de una solicitud recibe la negativa de
      AC6.2.4, con la banda si ya se conoce.

    Pura y sin reloj: es lo que el manejador del turno llama, y no toca el motor de reglas.
    """
    if (
        record_type is RecordType.CLAIM
        and not anything_captured
        and not quote_enabled
        and is_quote_request(text, language=language)
    ):
        return compose_unavailable(language=language)
    if record_type is RecordType.QUOTE_REQUEST and is_price_request(text, language=language):
        return compose_price_refusal(band, language=language)
    return None


__all__ = [
    "KNOWN_BANDS",
    "KNOWN_EXPLANATION_KEYS",
    "KNOWN_OUTCOMES",
    "QuoteReply",
    "band_sentence",
    "compose_eligibility_reply",
    "compose_price_refusal",
    "compose_unavailable",
    "explanation_sentence",
    "is_price_request",
    "is_quote_request",
    "outcome_sentence",
    "reply_before_capture",
]
