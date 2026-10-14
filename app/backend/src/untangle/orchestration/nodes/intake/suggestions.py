"""Los botones de respuesta rapida debajo de cada pregunta (fase 0, 2026-10-07).

Principio de la propuesta: que nadie se pierda. Escribir nunca es obligatorio, y
para las preguntas que tienen respuestas cortas y conocidas --si o no, hoy o ayer,
la poliza de ejemplo-- la agente las ofrece como botones. **Los decide el codigo**,
a partir de la pregunta que el codigo ya eligio, y salen del catalogo: el
navegador solo los dibuja y, al tocarlos, manda su texto como si se hubiera escrito.

Cada boton es una respuesta que la captura ya entiende por sus reglas, sin modelo:
asi funcionan tambien cuando la comprension no esta.
"""

from __future__ import annotations

from untangle.base import Locale
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey

CHIP_YES = CopyKey("chat.chip.answer_yes")
CHIP_NO = CopyKey("chat.chip.answer_no")
CHIP_ADD_MORE = CopyKey("chat.chip.add_more")
CHIP_LEAVE_IT = CopyKey("chat.chip.leave_it")
CHIP_NOBODY_HURT = CopyKey("chat.chip.nobody_hurt")
CHIP_SOMEONE_HURT = CopyKey("chat.chip.someone_hurt")
CHIP_EXAMPLE_POLICY = CopyKey("chat.chip.example_policy")
CHIP_EXAMPLE_HOLDER = CopyKey("chat.chip.example_holder")
CHIP_TODAY = CopyKey("chat.chip.today")
CHIP_YESTERDAY = CopyKey("chat.chip.yesterday")
CHIP_USE_PERSONAL = CopyKey("chat.chip.use_personal")
CHIP_USE_COMMUTING = CopyKey("chat.chip.use_commuting")
CHIP_USE_COMMERCIAL = CopyKey("chat.chip.use_commercial")
CHIP_MILEAGE_LOW = CopyKey("chat.chip.mileage_low")
CHIP_MILEAGE_MEDIUM = CopyKey("chat.chip.mileage_medium")
CHIP_MILEAGE_HIGH = CopyKey("chat.chip.mileage_high")
CHIP_ADJUSTER_REVIEW = CopyKey("chat.chip.adjuster_review")
CHIP_ANOTHER_QUESTION = CopyKey("chat.chip.another_question")
CHIP_REPORT = CopyKey("chat.chip.report")
CHIP_POLICY_QUESTION = CopyKey("chat.chip.policy_question")
CHIP_QUOTE = CopyKey("chat.chip.quote")

#: Las preguntas de si o no, por la clave con que se hicieron.
_DE_SI_O_NO: frozenset[str] = frozenset(
    {
        "intake.policy.found",
        "intake.policy.found_no_vehicle",
        "intake.question.quote_salvage_title",
        "intake.question.quote_prior_coverage_active",
    }
)
_DE_CUANDO: frozenset[str] = frozenset(
    {"intake.question.when_and_where", "intake.question.when_only"}
)


def for_question(  # noqa: PLR0911 -- una salida por tipo de pregunta, cada clave literal (BR3.4)
    question_key: str,
    *,
    language: Locale,
    example_policy: str,
    example_holder: str | None = None,
) -> tuple[str, ...]:
    """Los botones de la pregunta que el codigo eligio, o ninguno.

    Una lectura de confirmacion (`intake.readback.*`) y las preguntas de si o no
    llevan Si y No; las demas, las respuestas cortas que les corresponden.
    """
    if question_key.startswith("intake.readback.") or question_key in _DE_SI_O_NO:
        return (copy_api.t(CHIP_YES, locale=language), copy_api.t(CHIP_NO, locale=language))
    if question_key == "intake.closing.fast_claim_offer":
        # La oferta no es de si o no: o se agrega algo, o queda para el ajustador.
        return (
            copy_api.t(CHIP_ADD_MORE, locale=language),
            copy_api.t(CHIP_LEAVE_IT, locale=language),
        )
    if question_key == "intake.question.safety":
        return (
            copy_api.t(CHIP_NOBODY_HURT, locale=language),
            copy_api.t(CHIP_SOMEONE_HURT, locale=language),
        )
    if question_key == "intake.question.identity_and_policy":
        # La pregunta pide nombre y poliza: el boton contesta las dos con el titular
        # de la poliza de ejemplo, y dice exactamente lo que manda.
        if example_holder:
            return (
                copy_api.t(
                    CHIP_EXAMPLE_HOLDER,
                    locale=language,
                    holder=example_holder,
                    policy=example_policy,
                ),
            )
        return (copy_api.t(CHIP_EXAMPLE_POLICY, locale=language, policy=example_policy),)
    if question_key == "policy_rag.coverage.ask_question":
        # La poliza ya esta atada y falta la pregunta: las de ejemplo orientan a quien
        # entro por el boton sin saber que preguntar.
        return sample_questions(language=language)
    if question_key in _DE_CUANDO:
        return (
            copy_api.t(CHIP_TODAY, locale=language),
            copy_api.t(CHIP_YESTERDAY, locale=language),
        )
    if question_key == "intake.question.quote_use_type":
        return (
            copy_api.t(CHIP_USE_PERSONAL, locale=language),
            copy_api.t(CHIP_USE_COMMUTING, locale=language),
            copy_api.t(CHIP_USE_COMMERCIAL, locale=language),
        )
    if question_key == "intake.question.quote_annual_mileage_band":
        return (
            copy_api.t(CHIP_MILEAGE_LOW, locale=language),
            copy_api.t(CHIP_MILEAGE_MEDIUM, locale=language),
            copy_api.t(CHIP_MILEAGE_HIGH, locale=language),
        )
    return ()


def options(*, language: Locale, quote_enabled: bool) -> tuple[str, ...]:
    """Lo que la agente sabe hacer, como botones: los de la apertura y del saludo."""
    botones = [
        copy_api.t(CHIP_REPORT, locale=language),
        copy_api.t(CHIP_POLICY_QUESTION, locale=language),
    ]
    if quote_enabled:
        botones.append(copy_api.t(CHIP_QUOTE, locale=language))
    return tuple(botones)


#: Preguntas de ejemplo para quien pide preguntar por su poliza sin decir que
#: (2026-10-09): sirven en cualquier poliza y su respuesta sale de las clausulas.
SAMPLE_THEFT = CopyKey("policies.question.theft")
SAMPLE_UNINSURED = CopyKey("policies.question.uninsured_driver")
SAMPLE_RENTAL = CopyKey("policies.question.rental_car")
SAMPLE_LEND = CopyKey("policies.question.lend_car")


def sample_questions(*, language: Locale) -> tuple[str, ...]:
    """Cuatro preguntas de ejemplo, como botones: orientan una consulta sin pregunta."""
    return (
        copy_api.t(SAMPLE_THEFT, locale=language),
        copy_api.t(SAMPLE_UNINSURED, locale=language),
        copy_api.t(SAMPLE_RENTAL, locale=language),
        copy_api.t(SAMPLE_LEND, locale=language),
    )


def is_option(text: str) -> bool:
    """Si el texto es uno de los botones de opciones, en cualquier idioma: «Preguntar
    por mi poliza» dice que quiere preguntar, no cual es la pregunta."""
    plegado = text.strip().casefold()
    return any(
        plegado == opcion.casefold()
        for idioma in ("es", "en")
        for opcion in options(language=idioma, quote_enabled=True)
    )


def after_coverage(*, language: Locale) -> tuple[str, ...]:
    """Despues de una respuesta de cobertura: que lo revise un ajustador, o preguntar
    otra cosa (fase 1, 2026-10-08). El primero lo entiende la comprension como pedir
    una persona; el segundo hace que la agente pida la pregunta."""
    return (
        copy_api.t(CHIP_ADJUSTER_REVIEW, locale=language),
        copy_api.t(CHIP_ANOTHER_QUESTION, locale=language),
    )


__all__ = ["after_coverage", "for_question", "is_option", "options", "sample_questions"]
