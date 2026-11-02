"""Compone la salida del turno: una idea, veinticinco palabras, catalogo (BR3.4, BR3.6, BR5.2).

**BR3.4 no es un adorno de estilo: lo comprueba el codigo** (FD-U11-4) sobre
el texto ya compuesto, salvo cuatro excepciones que la propia regla nombra: el
primer mensaje, las lecturas de confirmacion (`confirmation.build_readback`),
el resumen de cierre y el texto de una clausula. `assert_question_shape` solo
se llama sobre lo que compone este modulo para preguntar un campo -- nunca
sobre una lectura.

**BR5.2**: reconocer primero, preguntar despues, en una sola idea. El
reconocimiento y la pregunta se unen en un solo turno que **si** cuenta para
BR3.4 -- no es ninguna de las cuatro excepciones -- asi que las frases del
catalogo de reconocimiento se escriben cortas a proposito.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from untangle.base import Frozen, Locale
from untangle.case_record.models import RecordType
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey
from untangle.orchestration.nodes.intake import confirmation
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.orchestration.nodes.intake.social import SocialIntent
from untangle.orchestration.nodes.intake.tone import Emotion

#: Encima de esto, una pregunta deja de ser "una idea" (BR3.4).
MAX_WORDS = 25


def count_words(text: str) -> int:
    """Palabras por espacio en blanco. Simple a proposito: es lo que un turno
    hablado o escrito cuenta, sin pesar signos de puntuacion."""
    return len(text.split())


def assert_question_shape(text: str) -> tuple[str, ...]:
    """BR3.4: los problemas de forma de una pregunta ya compuesta, o ninguno.

    No se llama sobre una lectura de confirmacion, el resumen de cierre, el
    primer mensaje ni el texto de una clausula: los cuatro son la excepcion
    que la propia regla declara.
    """
    problemas: list[str] = []
    palabras = count_words(text)
    if palabras > MAX_WORDS:
        problemas.append(f"tiene {palabras} palabras, mas de las {MAX_WORDS} que permite BR3.4")
    # Se cuenta **solo el signo de cierre**, que es el unico que los dos idiomas
    # comparten. Sumar tambien el `¿` obligaba a un umbral de dos signos, y con
    # ese umbral dos preguntas en ingles --"Are you hurt? Where did it
    # happen?"-- pasaban mientras las mismas dos en espanol fallaban: la regla
    # se volvia mas laxa en un idioma que en el otro, que es justo lo que P12
    # prohibe.
    preguntas = text.count("?")
    if preguntas > 1:
        problemas.append(f"trae {preguntas} preguntas: mas de una idea (BR3.4)")
    return tuple(problemas)


#: Una clave por bloque de un solo campo, mas las tres formas de "cuando y
#: donde" (BR3.3): las dos, solo "cuando", o solo "donde". Escritas enteras y
#: no compuestas desde el valor del enum -- la misma razon que
#: `compliance/controls/phrases.py` declara en su modulo: una clave armada con
#: el valor de `Block` rompería el chequeo BR3.4 del catalogo, que exige un
#: consumidor literal de cada clave.
QUESTION_SAFETY = CopyKey("intake.question.safety")
QUESTION_IDENTITY_AND_POLICY = CopyKey("intake.question.identity_and_policy")
QUESTION_WHAT_HAPPENED = CopyKey("intake.question.what_happened")
QUESTION_WHEN_AND_WHERE = CopyKey("intake.question.when_and_where")
QUESTION_WHEN_ONLY = CopyKey("intake.question.when_only")
QUESTION_WHERE_ONLY = CopyKey("intake.question.where_only")
QUESTION_VEHICLE_AND_DRIVER = CopyKey("intake.question.vehicle_and_driver")
QUESTION_OTHER_PARTIES = CopyKey("intake.question.other_parties")


#: Una pregunta por campo de la solicitud de cotizacion (U19, BR1.2), escritas enteras por
#: la misma razon que las de arriba. **Una idea a la vez**: `question_of` pregunta el
#: primer campo que falta del bloque que toca, nunca dos en un turno.
QUESTION_QUOTE_DRIVER_NAME = CopyKey("intake.question.quote_driver_name")
QUESTION_QUOTE_DRIVER_BIRTH_DATE = CopyKey("intake.question.quote_driver_birth_date")
QUESTION_QUOTE_LICENSE_YEARS = CopyKey("intake.question.quote_license_years")
QUESTION_QUOTE_LICENSE_JURISDICTION = CopyKey("intake.question.quote_license_jurisdiction")
QUESTION_QUOTE_VEHICLE_YEAR = CopyKey("intake.question.quote_vehicle_year")
QUESTION_QUOTE_VEHICLE_MAKE = CopyKey("intake.question.quote_vehicle_make")
QUESTION_QUOTE_VEHICLE_MODEL = CopyKey("intake.question.quote_vehicle_model")
QUESTION_QUOTE_VIN = CopyKey("intake.question.quote_vin")
QUESTION_QUOTE_SALVAGE_TITLE = CopyKey("intake.question.quote_salvage_title")
QUESTION_QUOTE_USE_TYPE = CopyKey("intake.question.quote_use_type")
QUESTION_QUOTE_ANNUAL_MILEAGE_BAND = CopyKey("intake.question.quote_annual_mileage_band")
QUESTION_QUOTE_GARAGING_JURISDICTION = CopyKey("intake.question.quote_garaging_jurisdiction")
QUESTION_QUOTE_AT_FAULT_LOSSES_3Y = CopyKey("intake.question.quote_at_fault_losses_3y")
QUESTION_QUOTE_CLAIMS_3Y = CopyKey("intake.question.quote_claims_3y")
QUESTION_QUOTE_PRIOR_COVERAGE_ACTIVE = CopyKey("intake.question.quote_prior_coverage_active")
QUESTION_QUOTE_LAPSE_MONTHS = CopyKey("intake.question.quote_lapse_months")

#: Que campo se vuelve a preguntar cuando el unico que falta es uno que solo escribe el
#: codigo: la antiguedad sale del anio del modelo, y sin el anio no hay de donde derivarla.
_ASKED_INSTEAD_OF_DERIVED: dict[str, str] = {"vehicle_age_years": "vehicle_year"}


def _quote_question(  # noqa: C901, PLR0912 -- un caso por campo: es la tabla de las preguntas, no logica
    missing_field_keys: tuple[str, ...], *, language: Locale
) -> tuple[CopyKey, str]:
    """La pregunta del primer campo que falta de un bloque de la solicitud (BR1.2, BR3.3).

    En el orden del esquema, y saltando lo que ya se dijo porque no esta entre los que
    faltan (BR3.3). Un campo derivado no se pregunta: si es lo unico que falta, se
    pregunta el dato del que sale. Un `match` en vez de una tabla, por lo mismo que el
    resto de este modulo: cada clave se resuelve con `copy_api.t` recibiendola literal.
    """
    if not missing_field_keys:
        msg = "un bloque de la solicitud sin campos pendientes no tiene pregunta que hacer"
        raise ValueError(msg)
    clave_de_campo = _ASKED_INSTEAD_OF_DERIVED.get(missing_field_keys[0], missing_field_keys[0])
    match clave_de_campo:
        case "driver_name":
            clave, frase = (
                QUESTION_QUOTE_DRIVER_NAME,
                copy_api.t(QUESTION_QUOTE_DRIVER_NAME, locale=language),
            )
        case "driver_birth_date":
            clave, frase = (
                QUESTION_QUOTE_DRIVER_BIRTH_DATE,
                copy_api.t(QUESTION_QUOTE_DRIVER_BIRTH_DATE, locale=language),
            )
        case "license_years":
            clave, frase = (
                QUESTION_QUOTE_LICENSE_YEARS,
                copy_api.t(QUESTION_QUOTE_LICENSE_YEARS, locale=language),
            )
        case "license_jurisdiction":
            clave, frase = (
                QUESTION_QUOTE_LICENSE_JURISDICTION,
                copy_api.t(QUESTION_QUOTE_LICENSE_JURISDICTION, locale=language),
            )
        case "vehicle_year":
            clave, frase = (
                QUESTION_QUOTE_VEHICLE_YEAR,
                copy_api.t(QUESTION_QUOTE_VEHICLE_YEAR, locale=language),
            )
        case "vehicle_make":
            clave, frase = (
                QUESTION_QUOTE_VEHICLE_MAKE,
                copy_api.t(QUESTION_QUOTE_VEHICLE_MAKE, locale=language),
            )
        case "vehicle_model":
            clave, frase = (
                QUESTION_QUOTE_VEHICLE_MODEL,
                copy_api.t(QUESTION_QUOTE_VEHICLE_MODEL, locale=language),
            )
        case "vin":
            clave, frase = QUESTION_QUOTE_VIN, copy_api.t(QUESTION_QUOTE_VIN, locale=language)
        case "salvage_title":
            clave, frase = (
                QUESTION_QUOTE_SALVAGE_TITLE,
                copy_api.t(QUESTION_QUOTE_SALVAGE_TITLE, locale=language),
            )
        case "use_type":
            clave, frase = (
                QUESTION_QUOTE_USE_TYPE,
                copy_api.t(QUESTION_QUOTE_USE_TYPE, locale=language),
            )
        case "annual_mileage_band":
            clave, frase = (
                QUESTION_QUOTE_ANNUAL_MILEAGE_BAND,
                copy_api.t(QUESTION_QUOTE_ANNUAL_MILEAGE_BAND, locale=language),
            )
        case "garaging_jurisdiction":
            clave, frase = (
                QUESTION_QUOTE_GARAGING_JURISDICTION,
                copy_api.t(QUESTION_QUOTE_GARAGING_JURISDICTION, locale=language),
            )
        case "at_fault_losses_3y":
            clave, frase = (
                QUESTION_QUOTE_AT_FAULT_LOSSES_3Y,
                copy_api.t(QUESTION_QUOTE_AT_FAULT_LOSSES_3Y, locale=language),
            )
        case "claims_3y":
            clave, frase = (
                QUESTION_QUOTE_CLAIMS_3Y,
                copy_api.t(QUESTION_QUOTE_CLAIMS_3Y, locale=language),
            )
        case "prior_coverage_active":
            clave, frase = (
                QUESTION_QUOTE_PRIOR_COVERAGE_ACTIVE,
                copy_api.t(QUESTION_QUOTE_PRIOR_COVERAGE_ACTIVE, locale=language),
            )
        case "lapse_months":
            clave, frase = (
                QUESTION_QUOTE_LAPSE_MONTHS,
                copy_api.t(QUESTION_QUOTE_LAPSE_MONTHS, locale=language),
            )
        case _:
            msg = f"el campo '{clave_de_campo}' de la solicitud no tiene pregunta propia"
            raise ValueError(msg)
    return clave, frase


#: Cuantos datos de la solicitud se preguntan en un mismo mensaje (2026-10-08). Antes
#: era uno por mensaje y la conversacion se hacia eterna; mas de tres se lee como un
#: formulario.
QUOTE_QUESTIONS_PER_TURN = 3

QUESTION_QUOTE_ALL = CopyKey("intake.question.quote_all")


def quote_opening_question(*, language: Locale) -> tuple[CopyKey, str]:
    """La primera pregunta de la solicitud: todo de una vez, y lo que falte despues."""
    return QUESTION_QUOTE_ALL, copy_api.t(QUESTION_QUOTE_ALL, locale=language)


def _quote_questions(
    missing_field_keys: tuple[str, ...], *, language: Locale
) -> tuple[CopyKey, str]:
    """Hasta tres preguntas del mismo bloque en un solo mensaje, en el orden del esquema.

    La clave es la del primer dato: es la que identifica el turno en la traza.
    """
    vistos: set[str] = set()
    pedidos: list[str] = []
    for campo in missing_field_keys:
        preguntado = _ASKED_INSTEAD_OF_DERIVED.get(campo, campo)
        if preguntado not in vistos:
            vistos.add(preguntado)
            pedidos.append(campo)
        if len(pedidos) == QUOTE_QUESTIONS_PER_TURN:
            break
    preguntas = [_quote_question((campo,), language=language) for campo in pedidos]
    return preguntas[0][0], " ".join(frase for _, frase in preguntas)


def question_of(
    block: Block, missing_field_keys: tuple[str, ...], *, language: Locale
) -> tuple[CopyKey, str]:
    """BR3.2, BR3.3: la clave y la frase del bloque que toca, solo por lo que falta.

    Devuelve las dos porque el canal necesita las dos (C-14): la clave identifica
    la frase en la traza y en el reporte por caso, y deducirla del texto seria
    adivinar cual del catalogo lo produjo.

    Un solo `return`, con la clave **y la frase** resueltas en cada rama -- la
    misma forma que `compliance/controls/phrases.py:allowed_text`. Que cada rama
    repita su clave dos veces no es descuido: `copy_api.t` tiene que recibirla
    como literal o el chequeo de claves sin consumidor del catalogo deja de ser
    exacto (BR3.4 del catalogo). Resolver el texto una sola vez al final, con la
    clave en una variable, es lo que ese chequeo detecta.
    """
    match block:
        case Block.SAFETY:
            clave, frase = QUESTION_SAFETY, copy_api.t(QUESTION_SAFETY, locale=language)
        case Block.IDENTITY_AND_POLICY:
            clave, frase = (
                QUESTION_IDENTITY_AND_POLICY,
                copy_api.t(QUESTION_IDENTITY_AND_POLICY, locale=language),
            )
        case Block.WHAT_HAPPENED:
            clave, frase = (
                QUESTION_WHAT_HAPPENED,
                copy_api.t(QUESTION_WHAT_HAPPENED, locale=language),
            )
        case Block.WHEN_AND_WHERE:
            falta_cuando = "incident_datetime" in missing_field_keys
            falta_donde = "location" in missing_field_keys
            if falta_cuando and falta_donde:
                clave, frase = (
                    QUESTION_WHEN_AND_WHERE,
                    copy_api.t(QUESTION_WHEN_AND_WHERE, locale=language),
                )
            elif falta_cuando:
                clave, frase = QUESTION_WHEN_ONLY, copy_api.t(QUESTION_WHEN_ONLY, locale=language)
            else:
                clave, frase = QUESTION_WHERE_ONLY, copy_api.t(QUESTION_WHERE_ONLY, locale=language)
        case Block.VEHICLE_AND_DRIVER:
            clave, frase = (
                QUESTION_VEHICLE_AND_DRIVER,
                copy_api.t(QUESTION_VEHICLE_AND_DRIVER, locale=language),
            )
        case Block.OTHER_PARTIES:
            clave, frase = (
                QUESTION_OTHER_PARTIES,
                copy_api.t(QUESTION_OTHER_PARTIES, locale=language),
            )
        case Block.QUOTE_DRIVER | Block.QUOTE_VEHICLE | Block.QUOTE_USAGE | Block.QUOTE_HISTORY:
            # U19: un bloque de la solicitud se pregunta campo a campo.
            clave, frase = _quote_questions(missing_field_keys, language=language)
        case _:
            msg = f"el bloque '{block.value}' no tiene pregunta propia"
            raise ValueError(msg)
    return clave, frase


def compose_question(block: Block, missing_field_keys: tuple[str, ...], *, language: Locale) -> str:
    """La frase sola, para quien no necesita la clave."""
    return question_of(block, missing_field_keys, language=language)[1]


ACK_FEAR_OR_CRYING = CopyKey("intake.ack.fear_or_crying")
ACK_ANGER = CopyKey("intake.ack.anger")


def compose_acknowledgement(emotion: Emotion, *, language: Locale) -> str:
    """BR5.2: la sola frase de reconocimiento del catalogo, antes de la pregunta."""
    if emotion is Emotion.FEAR_OR_CRYING:
        return copy_api.t(ACK_FEAR_OR_CRYING, locale=language)
    return copy_api.t(ACK_ANGER, locale=language)


def compose_with_acknowledgement(
    emotion: Emotion | None, question: str, *, language: Locale
) -> str:
    """BR5.2: reconocer primero, preguntar despues -- una sola idea junta.

    Sin emocion, la pregunta sale tal cual: reconocer sin que haya nada que
    reconocer seria la forma contraria del mismo error.
    """
    if emotion is None:
        return question
    return f"{compose_acknowledgement(emotion, language=language)} {question}"


INTAKE_DEGRADED = CopyKey("intake.degraded")
TONE_CALM = CopyKey("intake.tone.calm")
TONE_CLOSING_ABUSE = CopyKey("intake.tone.closing_abuse")
EMERGENCY_CONTINUATION = CopyKey("intake.emergency.continuation")
IDENTITY_NAME_PERMISSION = CopyKey("intake.identity.name_permission")


def compose_calm(*, language: Locale) -> str:
    """BR5.4, primer insulto: la frase de calma, sin reproches."""
    return copy_api.t(TONE_CALM, locale=language)


def compose_closing_by_abuse(*, language: Locale) -> str:
    """BR5.4, segundo insulto: la frase de cierre por abuso."""
    return copy_api.t(TONE_CLOSING_ABUSE, locale=language)


def compose_emergency_continuation(*, language: Locale) -> str:
    """BR4.1: se ofrece seguir despues de la indicacion de emergencia."""
    return copy_api.t(EMERGENCY_CONTINUATION, locale=language)


def should_ask_name_permission(
    *, language: Locale, first_name: str | None, permitted: bool | None
) -> bool:
    """BR3.6: en ingles, antes de usar el nombre de pila, se pide permiso."""
    return language == "en" and first_name is not None and permitted is None


def compose_name_permission_question(first_name: str, *, language: Locale) -> str:
    """BR3.6: la pregunta que pide usar el nombre de pila."""
    return copy_api.t(IDENTITY_NAME_PERMISSION, locale=language, name=first_name)


# --- Lo que la persona dijo de paso, y lo que se dice al cambiar de bloque ----
#
# Decision de Miguel del 2026-10-06: la agente contesta lo que le dijeron antes de
# seguir con lo pendiente, y al pasar de una lectura confirmada o corregida a lo
# siguiente lo dice, en vez de soltar la pregunta a secas. Cada frase sale del
# catalogo con su clave literal (BR3.4 del catalogo), y va **delante** del turno
# que tocaba; la despedida va sola.

SOCIAL_GREETING = CopyKey("intake.social.greeting")
SOCIAL_THANKS = CopyKey("intake.social.thanks")
SOCIAL_GOODBYE = CopyKey("intake.social.goodbye")
SOCIAL_PROGRESS = CopyKey("intake.social.progress")
#: Lo que se dice cuando la persona quiere terminar y el caso todavia no esta completo (2026-10-13).
UNFINISHED = CopyKey("intake.unfinished")
TRANSITION_CONFIRMED = CopyKey("intake.transition.confirmed")
TRANSITION_CORRECTED = CopyKey("intake.transition.corrected")

BLOCK_SAFETY = CopyKey("intake.block.safety")
BLOCK_IDENTITY_AND_POLICY = CopyKey("intake.block.identity_and_policy")
BLOCK_WHAT_HAPPENED = CopyKey("intake.block.what_happened")
BLOCK_WHEN_AND_WHERE = CopyKey("intake.block.when_and_where")
BLOCK_VEHICLE_AND_DRIVER = CopyKey("intake.block.vehicle_and_driver")
BLOCK_OTHER_PARTIES = CopyKey("intake.block.other_parties")
BLOCK_QUOTE_DRIVER = CopyKey("intake.block.quote_driver")
BLOCK_QUOTE_VEHICLE = CopyKey("intake.block.quote_vehicle")
BLOCK_QUOTE_USAGE = CopyKey("intake.block.quote_usage")
BLOCK_QUOTE_HISTORY = CopyKey("intake.block.quote_history")


def block_label(block: Block, *, language: Locale) -> str:  # noqa: C901, PLR0911 -- un `return` por bloque: es la tabla de los nombres, no logica
    """Como se nombra un bloque cuando la agente dice que falta.

    Un `match` con la clave literal en cada rama, por la misma razon que
    `question_of`: el chequeo de claves sin consumidor exige ver la clave en la
    llamada. `FINAL_CONFIRMATION` y `DONE` no se nombran porque no faltan nunca.
    """
    match block:
        case Block.SAFETY:
            return copy_api.t(BLOCK_SAFETY, locale=language)
        case Block.IDENTITY_AND_POLICY:
            return copy_api.t(BLOCK_IDENTITY_AND_POLICY, locale=language)
        case Block.WHAT_HAPPENED:
            return copy_api.t(BLOCK_WHAT_HAPPENED, locale=language)
        case Block.WHEN_AND_WHERE:
            return copy_api.t(BLOCK_WHEN_AND_WHERE, locale=language)
        case Block.VEHICLE_AND_DRIVER:
            return copy_api.t(BLOCK_VEHICLE_AND_DRIVER, locale=language)
        case Block.OTHER_PARTIES:
            return copy_api.t(BLOCK_OTHER_PARTIES, locale=language)
        case Block.QUOTE_DRIVER:
            return copy_api.t(BLOCK_QUOTE_DRIVER, locale=language)
        case Block.QUOTE_VEHICLE:
            return copy_api.t(BLOCK_QUOTE_VEHICLE, locale=language)
        case Block.QUOTE_USAGE:
            return copy_api.t(BLOCK_QUOTE_USAGE, locale=language)
        case Block.QUOTE_HISTORY:
            return copy_api.t(BLOCK_QUOTE_HISTORY, locale=language)
        case _:
            msg = f"el bloque '{block.value}' no se nombra como pendiente"
            raise ValueError(msg)


class Progress(Frozen):
    """Cuanto va y que falta, para contestarle a quien pregunta cuanto falta."""

    done: int
    total: int
    missing: tuple[Block, ...]


def compose_social(
    intent: SocialIntent, *, language: Locale, progress: Progress | None = None
) -> tuple[CopyKey, str]:
    """La frase con que se contesta lo que la persona dijo de paso, con su clave.

    La del avance necesita el caso (`progress`); sin el, falla: decir "llevamos
    tantos datos" sin saber cuantos seria inventar una cifra.
    """
    match intent:
        case SocialIntent.GREETING:
            return SOCIAL_GREETING, copy_api.t(SOCIAL_GREETING, locale=language)
        case SocialIntent.THANKS:
            return SOCIAL_THANKS, copy_api.t(SOCIAL_THANKS, locale=language)
        case SocialIntent.GOODBYE:
            return SOCIAL_GOODBYE, copy_api.t(SOCIAL_GOODBYE, locale=language)
        case SocialIntent.PROGRESS:
            if progress is None:
                msg = "contestar cuanto falta necesita el avance del caso"
                raise ValueError(msg)
            return SOCIAL_PROGRESS, copy_api.t(
                SOCIAL_PROGRESS,
                locale=language,
                done=str(progress.done),
                total=str(progress.total),
                missing=", ".join(
                    block_label(bloque, language=language) for bloque in progress.missing
                ),
            )


def compose_unfinished(block: Block, *, language: Locale) -> tuple[CopyKey, str]:
    """La verdad en una frase corta: el caso no esta completo, que falta, que lo que lleva queda
    guardado y se puede seguir despues, y una sola pregunta.

    Es la frase que sale cuando el modelo dio el reporte por hecho sin estarlo
    (`turn._frase_base`). `block` es el que toca preguntar y se nombra como en
    la respuesta a «¿cuanto falta?»; los que son cierre (`FINAL_CONFIRMATION`, `DONE`) no se
    nombran porque no faltan nunca, y `block_label` falla ante ellos.
    """
    return UNFINISHED, copy_api.t(
        UNFINISHED, locale=language, missing=block_label(block, language=language)
    )


def compose_transition(*, accepted: bool, language: Locale) -> str:
    """Lo que se dice al pasar de una lectura resuelta a lo siguiente."""
    if accepted:
        return copy_api.t(TRANSITION_CONFIRMED, locale=language)
    return copy_api.t(TRANSITION_CORRECTED, locale=language)


def with_lead_in(lead_in: str | None, text: str) -> str:
    """El turno con su frase previa delante, o tal cual si no la hay."""
    if lead_in is None or lead_in == "":
        return text
    return f"{lead_in} {text}"


# --- El cierre del recorrido rapido y la correccion (P4, 2026-10-06) -----------

CLOSING_FAST_OFFER = CopyKey("intake.closing.fast_claim_offer")
#: La espera de una consulta de cobertura con la poliza ya identificada (fase 1).
COVERAGE_CHECKING = CopyKey("policy_rag.coverage.checking")
#: La misma frase que dice el turno cuando la poliza ya esta atada y no hay pregunta
#: (`policy_rag.coverage.ask_question`): se repite el literal aqui porque los nodos no
#: se importan entre si, y el catalogo es de los dos.
COVERAGE_ASK_QUESTION = CopyKey("policy_rag.coverage.ask_question")
CLOSING_FAST_DONE = CopyKey("intake.closing.fast_claim_done")
CLOSING_FAST_AFTER_EXTRA = CopyKey("intake.closing.fast_claim_after_extra")
CLOSING_FAST_DECLINED = CopyKey("intake.closing.fast_claim_declined")
CLOSING_FAST_ALREADY = CopyKey("intake.closing.fast_claim_already")
#: Con el caso en revision (US1.17): las reglas todavia no dicen si lo cierran o lo mira un
#: ajustador, asi que ninguna de estas frases promete uno.
CLOSING_REVIEW_AFTER_EXTRA = CopyKey("intake.closing.fast_claim_review_after_extra")
CLOSING_REVIEW_DECLINED = CopyKey("intake.closing.fast_claim_review_declined")
CLOSING_REVIEW_ALREADY = CopyKey("intake.closing.fast_claim_review_already")
#: Con el caso ya cerrado por las reglas: quien sigue escribiendo oye que quedo registrado.
CLOSING_FAST_REGISTERED = CopyKey("intake.closing.fast_claim_registered")
CORRECTION_APPLIED = CopyKey("intake.correction.applied")


class FastClosing(StrEnum):
    """Las formas de cerrar un siniestro por el recorrido rapido."""

    #: Los obligatorios estan y falta algo opcional: se ofrece una vez.
    OFFER = "offer"
    #: No habia nada opcional que ofrecer.
    DONE = "done"
    #: La persona agrego lo opcional y no queda mas.
    AFTER_EXTRA = "after_extra"
    #: La persona no quiso agregar nada mas.
    DECLINED = "declined"
    #: La persona sigue escribiendo despues del cierre, sin dato nuevo: se le
    #: recuerda donde esta su caso.
    ALREADY = "already"


class ClosingPhase(StrEnum):
    """Donde esta el caso cuando se dice la frase de cierre (US1.17, 2026-10-13).

    Antes el caso se derivaba en el mismo turno en que la captura cerraba, y todo cierre decia
    «queda con un ajustador». Ahora el reporte pasa por una revision de las reglas, y lo que se
    puede decir depende de en cual de las tres situaciones esta.
    """

    #: La captura cierra en este turno: se acaba de pasar a revision.
    CAPTURING = "capturing"
    #: El caso esta en revision (`verifying`/`deciding`): todavia no se sabe si lo cierra la
    #: agente o lo mira un ajustador.
    REVIEWING = "reviewing"
    #: Un ajustador lo tiene (`derived`/`awaiting_insured`).
    WITH_ADJUSTER = "with_adjuster"
    #: Las reglas lo cerraron como `registered`.
    REGISTERED = "registered"


#: El cierre del siniestro por voz (2026-10-09): sin "el enlace de arriba", que en una llamada no
#: existe, y sin el numero de caso, que la despedida de la llamada ya dice --antes salia tres
#: veces--. Ninguna de estas frases menciona a un ajustador: la despedida es la que dice como
#: quedo el caso, cuando ya se sabe.
CLOSING_VOICE_OFFER = CopyKey("intake.closing.voice_fast_offer")
CLOSING_VOICE_DONE = CopyKey("intake.closing.voice_fast_done")
CLOSING_VOICE_AFTER_EXTRA = CopyKey("intake.closing.voice_fast_after_extra")
CLOSING_VOICE_DECLINED = CopyKey("intake.closing.voice_fast_declined")
CLOSING_VOICE_ALREADY = CopyKey("intake.closing.voice_fast_already")
CLOSING_VOICE_REGISTERED = CopyKey("intake.closing.voice_fast_registered")


def _cierre_hablado(
    kind: FastClosing, *, phase: ClosingPhase, language: Locale, missing: str
) -> tuple[CopyKey, str]:
    if phase is ClosingPhase.REGISTERED:
        return CLOSING_VOICE_REGISTERED, copy_api.t(CLOSING_VOICE_REGISTERED, locale=language)
    match kind:
        case FastClosing.OFFER:
            return CLOSING_VOICE_OFFER, copy_api.t(
                CLOSING_VOICE_OFFER, locale=language, missing=missing
            )
        case FastClosing.DONE:
            return CLOSING_VOICE_DONE, copy_api.t(CLOSING_VOICE_DONE, locale=language)
        case FastClosing.AFTER_EXTRA:
            return CLOSING_VOICE_AFTER_EXTRA, copy_api.t(CLOSING_VOICE_AFTER_EXTRA, locale=language)
        case FastClosing.DECLINED:
            return CLOSING_VOICE_DECLINED, copy_api.t(CLOSING_VOICE_DECLINED, locale=language)
        case FastClosing.ALREADY:
            return CLOSING_VOICE_ALREADY, copy_api.t(CLOSING_VOICE_ALREADY, locale=language)


def _cierre_escrito(  # noqa: PLR0911 -- una salida por frase, cada clave literal (BR3.4)
    kind: FastClosing, *, phase: ClosingPhase, case_number: str, language: Locale, missing: str
) -> tuple[CopyKey, str]:
    """La frase del chat: segun lo que se hizo y segun donde esta el caso."""
    if phase is ClosingPhase.REGISTERED:
        return CLOSING_FAST_REGISTERED, copy_api.t(
            CLOSING_FAST_REGISTERED, locale=language, case_number=case_number
        )
    # La oferta y el cierre sin oferta solo existen en el turno en que la captura cierra.
    if kind is FastClosing.OFFER:
        return CLOSING_FAST_OFFER, copy_api.t(
            CLOSING_FAST_OFFER, locale=language, case_number=case_number, missing=missing
        )
    if kind is FastClosing.DONE:
        return CLOSING_FAST_DONE, copy_api.t(
            CLOSING_FAST_DONE, locale=language, case_number=case_number
        )
    revisando = phase in (ClosingPhase.CAPTURING, ClosingPhase.REVIEWING)
    match kind:
        case FastClosing.AFTER_EXTRA if revisando:
            return CLOSING_REVIEW_AFTER_EXTRA, copy_api.t(
                CLOSING_REVIEW_AFTER_EXTRA, locale=language
            )
        case FastClosing.DECLINED if revisando:
            return CLOSING_REVIEW_DECLINED, copy_api.t(CLOSING_REVIEW_DECLINED, locale=language)
        case FastClosing.ALREADY if revisando:
            return CLOSING_REVIEW_ALREADY, copy_api.t(
                CLOSING_REVIEW_ALREADY, locale=language, case_number=case_number
            )
        case FastClosing.AFTER_EXTRA:
            return CLOSING_FAST_AFTER_EXTRA, copy_api.t(
                CLOSING_FAST_AFTER_EXTRA, locale=language, case_number=case_number
            )
        case FastClosing.DECLINED:
            return CLOSING_FAST_DECLINED, copy_api.t(
                CLOSING_FAST_DECLINED, locale=language, case_number=case_number
            )
        case _:
            return CLOSING_FAST_ALREADY, copy_api.t(
                CLOSING_FAST_ALREADY, locale=language, case_number=case_number
            )


def compose_fast_closing(  # noqa: PLR0913 -- la forma, el caso, el idioma, lo que falta, el canal y donde esta el caso
    kind: FastClosing,
    *,
    case_number: str,
    language: Locale,
    missing: tuple[Block, ...] = (),
    spoken: bool = False,
    phase: ClosingPhase = ClosingPhase.WITH_ADJUSTER,
) -> tuple[CopyKey, str]:
    """La frase de cierre del siniestro, con su clave (P4). Por voz, la de la llamada.

    `phase` es donde esta el caso (US1.17): lo que se puede decir cambia entre «ya tengo lo
    necesario y reviso tu reporte», «queda con un ajustador» y «quedo registrado». Por omision
    es la de un caso con un ajustador, que es lo que decian todas antes de la revision.
    """
    faltan = ", ".join(block_label(bloque, language=language) for bloque in missing)
    if spoken:
        return _cierre_hablado(kind, phase=phase, language=language, missing=faltan)
    return _cierre_escrito(
        kind, phase=phase, case_number=case_number, language=language, missing=faltan
    )


def compose_correction(value: str, *, language: Locale) -> str:
    """Lo que se dice al reemplazar un dato ya dicho: "Corregido: tres heridos."."""
    return copy_api.t(CORRECTION_APPLIED, locale=language, value=value)


class ComposedTurn(Frozen):
    """La clave del catalogo y el texto ya resuelto (`functional-spec.md`: "U11
    entrega la clave y el texto compuesto; quien lo muestra o lo sintetiza es
    del canal").

    Las dos cosas y no solo el texto: la clave es lo que identifica la frase en
    la traza y en el reporte por caso, y recomponerla mirando el texto seria
    adivinar cual de las claves del catalogo lo produjo.
    """

    key: str
    text: str


def compose_turn(  # noqa: PLR0913 -- el turno se compone de estas siete cosas y ninguna se deriva de otra
    *,
    emergency_raised: bool,
    emergency_instruction: str | None = None,
    block: Block,
    missing_field_keys: tuple[str, ...],
    emotion: Emotion | None,
    language: Locale,
    record_type: RecordType | None = None,
    confirmed_values: Mapping[str, str] | None = None,
    question_known: bool | None = None,
) -> ComposedTurn:
    """BR4.1: la emergencia rompe el orden en el mismo turno, antes de pedir nada.

    Es la unica rama de todo el modulo: si `emergency_raised` es verdadero, el
    turno entero son **las dos frases que AC1.6.1 pide juntas** --la indicacion
    de llamar a emergencias primero, y despues el ofrecimiento de seguir con el
    reporte-- y ni `block` ni `missing_field_keys` -- lo que fuera que tocaba
    preguntar -- se componen.

    `emergency_instruction` es el texto que produce el control barato de U10
    (`compliance.controls.api.emergency_instruction`, que elige la frase segun
    donde corre, AC1.6.3). **Entra como dato y no se busca aqui**: U11 no
    detecta la emergencia ni decide su frase (FD-U11-3), solo la pone delante de
    todo. Con la senal levantada y sin frase, esta funcion **falla**: un turno
    que solo dijera "podemos seguir despues" ante alguien que se esta
    desangrando es el fallo exacto que AC1.6.1 y AC1.6.2 bloquean, y fallar
    ruidosamente es la unica forma de que no salga.

    `emergency_raised` lo levanta el control barato de U10 dentro del turno,
    nunca este modulo (FD-U11-3): esta funcion solo lo respeta.

    Sin emergencia, BR4.2 ya esta resuelto por construccion: `block` y
    `missing_field_keys` los deduce `blocks.next_block` del caso, y una
    pregunta de cobertura a mitad no escribe ningun campo -- asi que la
    proxima vez que se llegue aqui con la misma completitud, se compone la
    misma pregunta, sin retroceder ni saltar el bloque en curso.
    """
    if emergency_raised:
        if emergency_instruction is None:
            msg = (
                "la senal de emergencia esta levantada y no llego la indicacion de "
                "U10: el turno tiene que decir que llame a emergencias antes de "
                "ofrecer seguir despues (AC1.6.1, AC1.6.2)"
            )
            raise ValueError(msg)
        return ComposedTurn(
            key=str(EMERGENCY_CONTINUATION),
            text=f"{emergency_instruction} {compose_emergency_continuation(language=language)}",
        )
    if block is Block.FINAL_CONFIRMATION and record_type is RecordType.COVERAGE_INQUIRY:
        # Fase 1 (2026-10-08): una consulta no se cierra con un resumen --salia
        # "Para cerrar: ; su pregunta es ."--, sino respondiendo. Con la poliza ya
        # identificada y la pregunta hecha, el turno lanza la revision y la respuesta
        # llega sola. **Sin pregunta no hay revision que lanzar**, asi que "te respondo
        # en un momento" seria una promesa que nadie cumple (visto el 2026-10-12, quien
        # entro por «Preguntar por mi poliza»): se pregunta que quiere saber.
        if question_known is None:
            msg = (
                "una consulta de cobertura con la poliza identificada necesita saber si "
                "la pregunta ya esta en el caso: sin eso no se sabe si se promete la "
                "revision o se pide la pregunta"
            )
            raise ValueError(msg)
        if not question_known:
            return ComposedTurn(
                key=str(COVERAGE_ASK_QUESTION),
                text=copy_api.t(COVERAGE_ASK_QUESTION, locale=language),
            )
        return ComposedTurn(
            key=str(COVERAGE_CHECKING), text=copy_api.t(COVERAGE_CHECKING, locale=language)
        )
    if block is Block.FINAL_CONFIRMATION:
        # El ultimo bloque del orden fijo de AC1.5.2. No es una pregunta de
        # campo: es el resumen de cierre, y por eso no pasa por
        # `assert_question_shape` (AC1.5.3 lo declara como excepcion).
        if record_type is None or confirmed_values is None:
            msg = (
                "el bloque de confirmacion final necesita el tipo de caso y sus "
                "valores confirmados para leer el resumen de cierre (AC1.5.2)"
            )
            raise ValueError(msg)
        return ComposedTurn(
            key=str(confirmation.closing_summary_key(record_type)),
            text=confirmation.build_closing_summary(
                record_type, confirmed_values, language=language
            ),
        )
    clave, pregunta = question_of(block, missing_field_keys, language=language)
    return ComposedTurn(
        key=str(clave),
        text=compose_with_acknowledgement(emotion, pregunta, language=language),
    )


__all__ = [
    "CLOSING_FAST_ALREADY",
    "COVERAGE_ASK_QUESTION",
    "COVERAGE_CHECKING",
    "INTAKE_DEGRADED",
    "MAX_WORDS",
    "SOCIAL_GOODBYE",
    "ClosingPhase",
    "ComposedTurn",
    "FastClosing",
    "Progress",
    "assert_question_shape",
    "block_label",
    "compose_acknowledgement",
    "compose_calm",
    "compose_closing_by_abuse",
    "compose_correction",
    "compose_emergency_continuation",
    "compose_fast_closing",
    "compose_name_permission_question",
    "compose_question",
    "compose_social",
    "compose_transition",
    "compose_turn",
    "compose_unfinished",
    "compose_with_acknowledgement",
    "count_words",
    "question_of",
    "should_ask_name_permission",
    "with_lead_in",
]
