"""Las sondas de DS-2 y DS-6 que miden la captura (U11, CG-U11-2, tanda 2).

Ocho comprobaciones, una por escenario (cinco ejes de DS-2 y tres de DS-6),
que **corren sin proveedor y sin base de datos** (CG-U11-4, EvalCheck es
sincrono): la extraccion se sustituye por un doble determinista que ya sabe,
por el propio guion del caso, que campo contesta cada turno del asegurado
simulado (`ScriptedInsured`, unit-test-instructions.md, "Dobles de prueba") --
y ademas escanea el texto de la respuesta por un puñado de senales conocidas
(negacion de heridos, una calle nombrada) para poder medir BR3.3 sin llamar a
ningun modelo.

**Lo que se simula, y lo que no.** El bloque que toca (`blocks.next_block`),
la lectura de confirmacion, el tono y la composicion son el codigo **real** de
esta unidad -- no una segunda implementacion que la sonda mida en lugar de la
verdadera. Lo que se sustituye es la extraccion (un modelo) y el caso mismo
(una fila de Postgres): aqui vive como un mapa de campo a booleano en memoria,
la misma forma que `case_record.models.Completeness.per_field` ya declara, sin
pasar por `case_record.repository`.

**BR1.1, fuera de este guion.** Ninguno de los dieciseis casos previos incluye
un turno de la pregunta de seguridad: la abre el primer turno del canal, que
estas sondas no modelan. El bloque `SAFETY` se siembra ya confirmado -- "sin
heridos", sin evidencia de turno real -- para que el guion de cada caso, que
empieza directo en `identity_and_policy` o mas adelante, coincida con lo que
de verdad escribieron.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from untangle.base import Locale
from untangle.case_record import fields
from untangle.case_record.models import CaseState, Completeness, RecordType
from untangle.evals import intake_policy_probes, loading
from untangle.evals.models import Dataset, GoldenCase
from untangle.evals.runner.api import (
    CheckOutcome,
    EvalCheck,
    EvalTarget,
    register_check,
    register_targets,
)
from untangle.evals.scripted_insured import ScriptedInsured
from untangle.orchestration.nodes.intake import (
    blocks,
    composition,
    confirmation,
    policy,
    social,
    tone,
)
from untangle.orchestration.nodes.intake import reporter as intake_reporter
from untangle.orchestration.nodes.intake import versions as intake_versions
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.tenancy import config as tenancy_config

UNIT = "u11-intake"

_CASES_DIR = "app/evals/cases"

#: Los siete campos de un siniestro (`fields.yaml`), pre-sembrado con la
#: pregunta de seguridad ya respondida (ver el docstring del modulo).
_SAFETY_SEEDED_VALUE: dict[Locale, str] = {"es": "sin heridos", "en": "no injuries"}


def _load(dataset_dir: str, case_name: str, *, language: Locale, root: Path) -> GoldenCase:
    ruta = root / _CASES_DIR / dataset_dir / case_name / f"{language}.yaml"
    return loading.load_case(ruta)


# --- El doble determinista de extraccion: solo lo que estos casos necesitan -


_INJURY_NEGATION = {
    "es": re.compile(r"no hubo ning[uú]n herido|sin heridos"),
    "en": re.compile(r"nobody was hurt|no one was (hurt|injured)"),
}
#: Una calle nombrada de pasada, en el turno de otro campo (BR3.3, el caso
#: "advanced-field"). No es un detector de lugares generico -- es lo que basta
#: para que ese unico caso tenga una senal de la que extraer, igual que el
#: extractor real solo puede extraer lo que el modelo devuelve.
_LOCATION_HINT = {
    "es": re.compile(r"\b(calle|carrera|avenida)\b"),
    "en": re.compile(r"\b\d+(st|nd|rd|th)\b"),
}


def _apply_bonus_fields(
    text: str, language: Locale, per_field: dict[str, bool], values: dict[str, str]
) -> bool:
    """BR3.3: lo que el turno de OTRO campo tambien trajo, sin que nadie lo pidiera.

    Devuelve si encontro algo nuevo, para que quien orquesta sepa que hubo
    progreso este turno.
    """
    progreso = False
    plegado = text.lower()
    if not per_field.get("injuries") and _INJURY_NEGATION[language].search(plegado):
        per_field["injuries"] = True
        values["injuries"] = text
        progreso = True
    if not per_field.get("location") and _LOCATION_HINT[language].search(plegado):
        per_field["location"] = True
        values["location"] = text
        progreso = True
    return progreso


@dataclass(frozen=True)
class TurnTrace:
    """Un paso de la simulacion: que bloque toco, que le faltaba y que se le pidio."""

    block: Block
    missing_before: tuple[str, ...]
    question_text: str


@dataclass
class DrivenClaim:
    """El resultado de simular un siniestro completo contra el mecanismo real."""

    trace: tuple[TurnTrace, ...]
    values: dict[str, str] = field(default_factory=dict)


_CLAIM_FIELD_KEYS: tuple[str, ...] = tuple(d.key for d in fields.definitions_for(RecordType.CLAIM))
#: Turnos de sobra sobre los campos del siniestro: basta para que un bloque sin
#: guion (tipicamente `other_parties`) se pida una vez y se abandone por falta
#: de progreso, sin arriesgar un bucle infinito si algun caso cambiara de forma.
_MAX_TURNS = len(_CLAIM_FIELD_KEYS) + 2


#: Los campos opcionales del siniestro (P4): se ofrecen al cerrar, no se piden.
_OPTIONAL_CLAIM_FIELDS = frozenset(
    d.key for d in fields.definitions_for(RecordType.CLAIM) if d.optional
)


def _completeness_of(per_field: dict[str, bool]) -> Completeness:
    """La completitud como la calcula el caso, con los opcionales fuera de la cuenta."""
    return Completeness.derive(dict(per_field), optional=_OPTIONAL_CLAIM_FIELDS)


def _drive_claim(case: GoldenCase) -> DrivenClaim:
    """BR3.2, BR3.3: simula el siniestro entero contra `blocks` y `composition` reales."""
    per_field: dict[str, bool] = dict.fromkeys(_CLAIM_FIELD_KEYS, False)
    values: dict[str, str] = {}
    per_field["injuries"] = True
    values["injuries"] = _SAFETY_SEEDED_VALUE[case.language]

    responder = ScriptedInsured(case)
    trace: list[TurnTrace] = []

    for _ in range(_MAX_TURNS):
        completeness = _completeness_of(per_field)
        bloque = blocks.next_block(RecordType.CLAIM, completeness, CaseState.CAPTURING)
        if bloque in (Block.FINAL_CONFIRMATION, Block.DONE):
            break

        faltan = blocks.missing_fields_in_block(RecordType.CLAIM, bloque, completeness)
        pregunta = composition.compose_question(bloque, faltan, language=case.language)
        trace.append(TurnTrace(block=bloque, missing_before=faltan, question_text=pregunta))

        progreso = False
        for campo in faltan:
            respuesta = responder.answer(campo)
            if respuesta.off_script:
                continue
            per_field[campo] = True
            values[campo] = respuesta.text
            progreso = True
            progreso = (
                _apply_bonus_fields(respuesta.text, case.language, per_field, values) or progreso
            )
        if not progreso:
            break

    return DrivenClaim(trace=tuple(trace), values=values)


#: BR3.2: la secuencia de bloques que un siniestro sin datos adelantados ni
#: partes ajenas recorre, con la pregunta de seguridad ya sembrada (ver el
#: docstring del modulo). Es la misma para `intake-ordered-story` y
#: `intake-disordered-story`: el guion en otro orden no la cambia. Desde P4
#: (2026-10-06) el vehiculo y las otras personas no se piden: se ofrecen al cerrar.
_EXPECTED_STORY_SEQUENCE: tuple[Block, ...] = (
    Block.IDENTITY_AND_POLICY,
    Block.WHAT_HAPPENED,
    Block.WHEN_AND_WHERE,
)


def _blocks_of(driven: DrivenClaim) -> tuple[Block, ...]:
    return tuple(paso.block for paso in driven.trace)


def _check_story_order(case_name: str) -> EvalCheck:
    def comprobar(*, language: Locale, root: Path) -> CheckOutcome:
        caso = _load("ds2", case_name, language=language, root=root)
        driven = _drive_claim(caso)
        obtenida = _blocks_of(driven)
        if obtenida != _EXPECTED_STORY_SEQUENCE:
            return CheckOutcome(
                passed=False,
                detail=(
                    f"'{caso.case_key}' pidio los bloques {[b.value for b in obtenida]}, "
                    f"se esperaba {[b.value for b in _EXPECTED_STORY_SEQUENCE]} (BR3.2)"
                ),
            )
        return CheckOutcome(passed=True)

    return comprobar


def _check_advanced_field(*, language: Locale, root: Path) -> CheckOutcome:
    """BR3.3: un dato que llego adelantado no vuelve a preguntarse."""
    caso = _load("ds2", "intake-advanced-field", language=language, root=root)
    driven = _drive_claim(caso)
    paso_cuando_y_donde = next((p for p in driven.trace if p.block is Block.WHEN_AND_WHERE), None)
    if paso_cuando_y_donde is None:
        return CheckOutcome(
            passed=False, detail=f"'{caso.case_key}' nunca llego al bloque 'when_and_where'"
        )
    if "location" in paso_cuando_y_donde.missing_before:
        return CheckOutcome(
            passed=False,
            detail=(
                f"'{caso.case_key}' volvio a pedir 'location' aunque ya llego adelantado "
                "en el turno de identidad (BR3.3)"
            ),
        )
    if "incident_datetime" not in paso_cuando_y_donde.missing_before:
        return CheckOutcome(
            passed=False,
            detail=f"'{caso.case_key}': 'incident_datetime' seguia sin pedirse en este bloque",
        )
    return CheckOutcome(passed=True)


def _check_distress_crying(*, language: Locale, root: Path) -> CheckOutcome:
    """BR5.2: reconocimiento primero, una sola pregunta despues."""
    caso = _load("ds2", "intake-distress-crying", language=language, root=root)
    turno = caso.script[0].text
    emocion = tone.detect_emotion(turno, language=language)
    if emocion is not tone.Emotion.FEAR_OR_CRYING:
        return CheckOutcome(
            passed=False, detail=f"'{caso.case_key}' no se reconocio como miedo o llanto"
        )
    pregunta = composition.compose_question(
        Block.WHAT_HAPPENED, ("description",), language=language
    )
    compuesto = composition.compose_with_acknowledgement(emocion, pregunta, language=language)
    problemas = composition.assert_question_shape(compuesto)
    if problemas:
        return CheckOutcome(passed=False, detail="; ".join(problemas))
    violacion = tone.forbidden_register_violation(compuesto, language=language)
    if violacion is not None:
        return CheckOutcome(
            passed=False, detail=f"registro prohibido '{violacion}' en '{compuesto}'"
        )
    return CheckOutcome(passed=True)


def _insult_progression(case: GoldenCase, *, root: Path) -> tuple[str, ...]:
    """Que compuso la agente tras cada insulto del guion, en orden.

    `"calm"`, `"closing_abuse"` o `"none"` por turno, segun el umbral de la
    aseguradora del caso (BR5.4, TECH-U11.5): el numero no esta en el codigo
    de la sonda, sale de `tenancy.config`, igual que en el aplicativo.
    """
    tenants = tenancy_config.load(root / "app" / "config" / "tenants")
    tenant = tenants.get(case.tenant) if case.tenant else None
    if tenant is None:
        msg = f"'{case.case_key}' declara la aseguradora '{case.tenant}', que no carga"
        raise ValueError(msg)

    historial: list[str] = []
    resultado: list[str] = []
    for respuesta in case.script:
        historial.append(respuesta.text)
        insultos = tone.count_insults(tuple(historial), language=case.language)
        if insultos >= tenant.intake.close_after_insults:
            resultado.append("closing_abuse")
        elif insultos >= tenant.intake.calm_after_insults:
            resultado.append("calm")
        else:
            resultado.append("none")
    return tuple(resultado)


def _check_anger(*, language: Locale, root: Path) -> CheckOutcome:
    """BR5.4, AC1.13.3: calma al segundo insulto, cierre por abuso al tercero.

    La progresion esperada se escribe **entera, con el turno que todavia no
    dispara nada**: si solo se comprobara que en algun momento aparecen la calma
    y el cierre, un umbral adelantado --cerrar la sesion al segundo insulto--
    pasaria igual.
    """
    caso = _load("ds2", "intake-anger", language=language, root=root)
    progresion = _insult_progression(caso, root=root)
    esperada = ("none", "calm", "closing_abuse")
    if progresion != esperada:
        return CheckOutcome(
            passed=False,
            detail=f"'{caso.case_key}' produjo {progresion}, se esperaba {esperada}",
        )
    calma = composition.compose_calm(language=language)
    cierre = composition.compose_closing_by_abuse(language=language)
    for frase in (calma, cierre):
        violacion = tone.forbidden_register_violation(frase, language=language)
        if violacion is not None:
            return CheckOutcome(
                passed=False, detail=f"registro prohibido '{violacion}' en '{frase}'"
            )
    return CheckOutcome(passed=True)


def _check_two_versions(*, language: Locale, root: Path) -> CheckOutcome:
    """BR5.5, FD-U11-7: la version que contradice no reemplaza el valor confirmado."""
    caso = _load("ds6", "rt7-two-versions", language=language, root=root)
    respuestas = caso.answers_for("incident_datetime")
    if len(respuestas) != 2:
        return CheckOutcome(
            passed=False,
            detail=f"'{caso.case_key}' no trae dos versiones de 'incident_datetime'",
        )
    primero, segundo = (r.text for r in respuestas)

    valores: dict[str, str] = {}
    valores["incident_datetime"] = primero
    if not intake_versions.is_contradiction(valores["incident_datetime"], segundo):
        return CheckOutcome(
            passed=False,
            detail=f"'{caso.case_key}': las dos versiones no se detectan como distintas",
        )
    # BR5.5: la segunda version NUNCA reemplaza el valor del caso -- se anotaria
    # aparte (`contradictions.record_alternate_version`, de integracion), y el
    # campo autoritativo de esta simulacion se queda como estaba.
    if valores["incident_datetime"] != primero:
        return CheckOutcome(
            passed=False,
            detail=f"'{caso.case_key}': el valor del caso dejo de ser el primero confirmado",
        )
    return CheckOutcome(passed=True)


def _check_third_party_reporter(*, language: Locale, root: Path) -> CheckOutcome:
    """BR1.5: al tercero no se le confirma nada que no aporto."""
    caso = _load("ds6", "rt9-third-party-reporter", language=language, root=root)
    turno = caso.script[0].text
    reportero = intake_reporter.ThirdPartyReporter(relation=turno)
    revelado = intake_reporter.disclosed_fields(reportero)
    if "name" in revelado or "contact" in revelado:
        return CheckOutcome(
            passed=False,
            detail=f"'{caso.case_key}': se le atribuyeron datos de poliza que el tercero no aporto",
        )
    if "relation" not in revelado:
        return CheckOutcome(
            passed=False, detail=f"'{caso.case_key}': la relacion declarada no quedo registrada"
        )
    return CheckOutcome(passed=True)


def _check_insults(*, language: Locale, root: Path) -> CheckOutcome:
    """BR5.3, BR5.4: ningun turno de la agente lleva registro prohibido, bajo insultos sostenidos."""
    caso = _load("ds6", "rt11-insults", language=language, root=root)
    progresion = _insult_progression(caso, root=root)
    if "closing_abuse" not in progresion:
        return CheckOutcome(
            passed=False, detail=f"'{caso.case_key}' nunca llega al cierre por abuso: {progresion}"
        )
    for frase in (
        composition.compose_calm(language=language),
        composition.compose_closing_by_abuse(language=language),
    ):
        violacion = tone.forbidden_register_violation(frase, language=language)
        if violacion is not None:
            return CheckOutcome(
                passed=False, detail=f"registro prohibido '{violacion}' en '{frase}'"
            )
    for turno in caso.script:
        if tone.forbidden_register_violation(turno.text, language=language) is not None:
            # El turno de la PERSONA puede traer groserias -- lo que no puede
            # traerlas es lo que compone la agente, ya comprobado arriba. Esta
            # vuelta solo confirma que el detector no se confunde con el
            # insulto ajeno como si fuera propio de la agente.
            continue
    return CheckOutcome(passed=True)


# --- Lo que la persona dice de paso (decision de Miguel, 2026-10-06) -----------
#
# Las cinco sondas miden las piezas puras que el nodo junta --el reconocedor,
# la composicion y el reconocedor de si/no--; que el nodo no llame al modelo con
# un turno solo social y que no niegue una lectura con un "gracias" lo prueba
# `tests/unit/intake/test_node.py` con un extractor que cuenta llamadas, porque
# una sonda es sincrona y el nodo no.


def _social_turn(caso: GoldenCase) -> str:
    """Lo que la persona dijo de paso: el unico turno del guion.

    Va indexado por el campo que estaba pendiente cuando lo dijo --el guion solo
    admite campos del esquema--, asi que se lee por posicion y no por nombre.
    """
    if len(caso.script) != 1:
        msg = f"'{caso.case_key}' tiene que traer exactamente un turno, el social"
        raise ValueError(msg)
    return caso.script[0].text


def _check_greeting_only(*, language: Locale, root: Path) -> CheckOutcome:
    """Un saludo a secas: se reconoce, no trae nada que extraer, y la respuesta
    saluda y sigue con la pregunta de seguridad (BR1.1)."""
    caso = _load("ds2", "intake-greeting-only", language=language, root=root)
    turno = _social_turn(caso)
    if social.detect(turno, language=language) is not social.SocialIntent.GREETING:
        return CheckOutcome(passed=False, detail=f"'{caso.case_key}' no se reconocio como saludo")
    if not social.is_only_social(turno, language=language):
        return CheckOutcome(
            passed=False,
            detail=f"'{caso.case_key}' dejo palabras sueltas: {social.leftover_words(turno, language=language)}",
        )
    saludo = composition.compose_social(social.SocialIntent.GREETING, language=language)[1]
    pregunta = composition.compose_question(Block.SAFETY, ("injuries",), language=language)
    compuesto = composition.with_lead_in(saludo, pregunta)
    if not compuesto.startswith(saludo) or not compuesto.endswith(pregunta):
        return CheckOutcome(passed=False, detail=f"'{caso.case_key}': '{compuesto}'")
    violacion = tone.forbidden_register_violation(compuesto, language=language)
    if violacion is not None:
        return CheckOutcome(
            passed=False, detail=f"registro prohibido '{violacion}' en '{compuesto}'"
        )
    return CheckOutcome(passed=True)


def _check_thanks_mid_report(*, language: Locale, root: Path) -> CheckOutcome:
    """Un "gracias" no es ni un si ni un no: la lectura sigue pendiente."""
    caso = _load("ds2", "intake-thanks-mid-report", language=language, root=root)
    turno = _social_turn(caso)
    if social.detect(turno, language=language) is not social.SocialIntent.THANKS:
        return CheckOutcome(
            passed=False, detail=f"'{caso.case_key}' no se reconocio como agradecimiento"
        )
    if not social.is_only_social(turno, language=language):
        return CheckOutcome(passed=False, detail=f"'{caso.case_key}' no es solo social")
    if confirmation.is_affirmative(turno, language=language) or confirmation.is_negative(
        turno, language=language
    ):
        return CheckOutcome(
            passed=False, detail=f"'{caso.case_key}': el agradecimiento se leyo como si o como no"
        )
    frase = composition.compose_social(social.SocialIntent.THANKS, language=language)[1]
    if "?" in frase:
        return CheckOutcome(
            passed=False, detail=f"'{frase}' pregunta algo; va delante de la lectura"
        )
    return CheckOutcome(passed=True)


def _check_progress_question(*, language: Locale, root: Path) -> CheckOutcome:
    """Cuanto falta se lee del caso: tres de siete, con los bloques que faltan nombrados."""
    caso = _load("ds2", "intake-progress-question", language=language, root=root)
    turno = _social_turn(caso)
    if social.detect(turno, language=language) is not social.SocialIntent.PROGRESS:
        return CheckOutcome(
            passed=False, detail=f"'{caso.case_key}' no se reconocio como pregunta por el avance"
        )
    por_campo = dict.fromkeys(_CLAIM_FIELD_KEYS, False)
    for campo in ("injuries", "identity_and_policy", "description"):
        por_campo[campo] = True
    completitud = Completeness(
        per_field=por_campo, complete=sum(por_campo.values()), total=len(por_campo)
    )
    faltan = blocks.missing_blocks(RecordType.CLAIM, completitud)
    if Block.SAFETY in faltan or Block.WHEN_AND_WHERE not in faltan:
        return CheckOutcome(passed=False, detail=f"'{caso.case_key}': faltan {faltan}")
    avance = composition.Progress(
        done=completitud.complete, total=completitud.total, missing=faltan
    )
    texto = composition.compose_social(
        social.SocialIntent.PROGRESS, language=language, progress=avance
    )[1]
    if "3" not in texto or "7" not in texto:
        return CheckOutcome(passed=False, detail=f"'{caso.case_key}': '{texto}' no dice 3 de 7")
    for bloque in faltan:
        if composition.block_label(bloque, language=language) not in texto:
            return CheckOutcome(
                passed=False, detail=f"'{caso.case_key}': '{texto}' no nombra {bloque.value}"
            )
    if composition.count_words(texto) > composition.MAX_WORDS:
        return CheckOutcome(
            passed=False, detail=f"'{texto}' pasa de {composition.MAX_WORDS} palabras"
        )
    return CheckOutcome(passed=True)


def _check_goodbye_mid_report(*, language: Locale, root: Path) -> CheckOutcome:
    """La despedida va sola: sin pregunta, y sin cerrar nada."""
    caso = _load("ds2", "intake-goodbye-mid-report", language=language, root=root)
    turno = _social_turn(caso)
    if social.detect(turno, language=language) is not social.SocialIntent.GOODBYE:
        return CheckOutcome(
            passed=False, detail=f"'{caso.case_key}' no se reconocio como despedida"
        )
    frase = composition.compose_social(social.SocialIntent.GOODBYE, language=language)[1]
    if "?" in frase:
        return CheckOutcome(passed=False, detail=f"la despedida pregunta algo: '{frase}'")
    violacion = tone.forbidden_register_violation(frase, language=language)
    if violacion is not None:
        return CheckOutcome(passed=False, detail=f"registro prohibido '{violacion}' en '{frase}'")
    return CheckOutcome(passed=True)


def _problemas_del_cierre_en_revision(
    numero: str, *, language: Locale, oferta: str
) -> tuple[str, list[str]]:
    """El cierre tras el no con el caso en revision (US1.17), y lo que esta mal en el.

    Todavia no promete un ajustador --las reglas aun no deciden-- y sigue sin preguntar nada.
    Devuelve la frase, para que quien llama le pase tambien el chequeo de registro.
    """
    _, revisando = composition.compose_fast_closing(
        composition.FastClosing.DECLINED,
        case_number=numero,
        language=language,
        phase=composition.ClosingPhase.REVIEWING,
    )
    problemas: list[str] = []
    if "?" in revisando:
        problemas.append(f"el cierre tras el no, con el caso en revision, pregunta: '{revisando}'")
    problemas.extend(
        f"promete un ajustador antes de que las reglas decidan: '{frase}'"
        for frase in (oferta, revisando)
        if "ajustador" in frase.lower() or "adjuster" in frase.lower()
    )
    return revisando, problemas


def _problemas_del_cierre(completitud: Completeness, *, language: Locale) -> list[str]:
    """Lo que esta mal en como cierra un siniestro con los obligatorios dichos (P4)."""
    numero = "CAS-000042"
    problemas: list[str] = []
    if completitud.awaiting_readback:
        problemas.append(f"hay campos esperando lectura: {sorted(completitud.awaiting_readback)}")
    bloque = blocks.next_block(RecordType.CLAIM, completitud, CaseState.CAPTURING)
    if bloque is not Block.FINAL_CONFIRMATION:
        problemas.append(f"con los obligatorios dichos toca '{bloque.value}' y no el cierre")
    opcionales = blocks.optional_blocks_missing(RecordType.CLAIM, completitud)
    if opcionales != (Block.VEHICLE_AND_DRIVER, Block.OTHER_PARTIES):
        problemas.append(f"lo opcional por ofrecer es {[b.value for b in opcionales]}")

    clave, oferta = composition.compose_fast_closing(
        composition.FastClosing.OFFER, case_number=numero, language=language, missing=opcionales
    )
    if clave != composition.CLOSING_FAST_OFFER:
        problemas.append(f"clave inesperada {clave}")
    if numero not in oferta:
        problemas.append(f"la oferta no nombra el caso: '{oferta}'")
    if oferta.count("?") != 1:
        problemas.append(f"la oferta no es una sola pregunta: '{oferta}'")
    problemas.extend(
        f"la oferta no nombra '{etiqueta}'"
        for etiqueta in (composition.block_label(b, language=language) for b in opcionales)
        if etiqueta not in oferta
    )
    _, cierre = composition.compose_fast_closing(
        composition.FastClosing.DECLINED, case_number=numero, language=language
    )
    if numero not in cierre or "?" in cierre:
        problemas.append(f"el cierre tras el no debe nombrar el caso y no preguntar: '{cierre}'")
    revisando, problemas_en_revision = _problemas_del_cierre_en_revision(
        numero, language=language, oferta=oferta
    )
    problemas.extend(problemas_en_revision)
    problemas.extend(
        f"registro prohibido '{violacion}' en '{frase}'"
        for frase in (oferta, cierre, revisando)
        if (violacion := tone.forbidden_register_violation(frase, language=language)) is not None
    )
    return problemas


def _check_fast_closing(*, language: Locale, root: Path) -> CheckOutcome:
    """P4: con los obligatorios dichos no se lee nada de vuelta; se cierra con el
    numero del caso y se ofrece lo opcional una vez; un "no" delante declina.

    Los problemas se juntan y se devuelven todos, como en la sonda de la poliza.
    """
    caso = _load("ds2", "intake-fast-closing", language=language, root=root)
    driven = _drive_claim(caso)
    per_field = dict.fromkeys(_CLAIM_FIELD_KEYS, False)
    per_field["injuries"] = True
    for clave in driven.values:
        per_field[clave] = True
    problemas = _problemas_del_cierre(_completeness_of(per_field), language=language)

    no, si = (r.text for r in caso.answers_for("vehicle_and_driver"))
    if confirmation.accepts_offer(no, language=language):
        problemas.append(f"'{no}' se leyo como ganas de agregar: ante la oferta declina")
    if not confirmation.accepts_offer(si, language=language):
        problemas.append(f"'{si}' no se leyo como ganas de agregar")
    if problemas:
        return CheckOutcome(passed=False, detail=f"'{caso.case_key}': " + "; ".join(problemas))
    return CheckOutcome(passed=True)


def _check_correction(*, language: Locale, root: Path) -> CheckOutcome:
    """P4: un dato ya dicho que vuelve a decirse se anuncia corregido, delante de
    lo que tocaba y sin pregunta; el reemplazo lo prueba el nodo."""
    caso = _load("ds2", "intake-correction", language=language, root=root)
    _, corregido = (r.text for r in caso.answers_for("injuries"))
    frase = composition.compose_correction(corregido, language=language)
    problemas: list[str] = []
    if corregido not in frase:
        problemas.append(f"'{frase}' no nombra el valor corregido")
    if "?" in frase:
        problemas.append(f"la correccion pregunta algo: '{frase}'")
    violacion = tone.forbidden_register_violation(frase, language=language)
    if violacion is not None:
        problemas.append(f"registro prohibido '{violacion}' en '{frase}'")
    _, pregunta = composition.question_of(Block.WHAT_HAPPENED, ("description",), language=language)
    turno = composition.with_lead_in(frase, pregunta)
    if not (turno.startswith(frase) and turno.endswith(pregunta)):
        problemas.append(f"la correccion no va delante de la pregunta: '{turno}'")
    if problemas:
        return CheckOutcome(passed=False, detail=f"'{caso.case_key}': " + "; ".join(problemas))
    return CheckOutcome(passed=True)


def _check_social_other_language(*, language: Locale, root: Path) -> CheckOutcome:
    """BR2.2: un turno corto en el otro idioma se entiende igual, y se contesta en este."""
    caso = _load("ds2", "intake-social-other-language", language=language, root=root)
    gracias, confirmacion = (r.text for r in caso.answers_for("injuries"))
    if social.detect(gracias, language=language) is not social.SocialIntent.THANKS:
        return CheckOutcome(
            passed=False,
            detail=f"'{caso.case_key}': '{gracias}' no se reconocio como agradecimiento con idioma '{language}'",
        )
    if not social.is_only_social(gracias, language=language):
        return CheckOutcome(
            passed=False, detail=f"'{caso.case_key}': '{gracias}' no es solo social"
        )
    if not confirmation.is_affirmative(confirmacion, language=language):
        return CheckOutcome(
            passed=False,
            detail=f"'{caso.case_key}': '{confirmacion}' no se leyo como si con idioma '{language}'",
        )
    # Y la respuesta sale en el idioma de la conversacion, no en el del turno: la
    # frase de este idioma es distinta de la del otro, y es la de este la que sale.
    otro: Locale = "en" if language == "es" else "es"
    frase = composition.compose_social(social.SocialIntent.THANKS, language=language)[1]
    if frase == composition.compose_social(social.SocialIntent.THANKS, language=otro)[1]:
        return CheckOutcome(
            passed=False, detail=f"'{caso.case_key}': la frase no distingue el idioma: '{frase}'"
        )
    return CheckOutcome(passed=True)


def _check_policy_holder_confirmed(*, language: Locale, root: Path) -> CheckOutcome:
    """P3: la poliza se nombra entera en una pregunta, y el si y el no se leen bien.

    Los problemas se juntan y se devuelven todos: una sonda que corta en el primero
    obliga a correrla tantas veces como fallos haya.
    """
    caso = _load("ds2", "intake-policy-holder-confirmed", language=language, root=root)
    si, no = (r.text for r in caso.answers_for("identity_and_policy"))
    titular = policy.PolicyMatch(
        policy_number="POL-100042", holder_name="Natalia Henao Rendón", vehicle="Renault Logan 2024"
    )
    clave, frase = policy.compose_found(titular, language=language)
    problemas = [
        f"'{frase}' no nombra {dato}"
        for dato in (titular.policy_number, titular.holder_name, titular.vehicle)
        if dato is not None and dato not in frase
    ]
    if frase.count("?") != 1:
        problemas.append(f"'{frase}' no es una sola pregunta")
    if clave != policy.POLICY_FOUND:
        problemas.append(f"clave inesperada {clave}")
    violacion = tone.forbidden_register_violation(frase, language=language)
    if violacion is not None:
        problemas.append(f"registro prohibido '{violacion}' en '{frase}'")
    if not confirmation.is_affirmative(si, language=language):
        problemas.append(f"'{si}' no se leyo como si")
    if confirmation.is_affirmative(no, language=language) or not confirmation.is_negative(
        no, language=language
    ):
        problemas.append(f"'{no}' no se leyo como no")
    if policy.policy_number_in("mi póliza es la pol-100042") != "POL-100042":
        problemas.append("el numero de poliza no se reconoce dentro de una frase")
    if problemas:
        return CheckOutcome(passed=False, detail=f"'{caso.case_key}': " + "; ".join(problemas))
    return CheckOutcome(passed=True)


SONDAS = {
    "intake_ordered_story": _check_story_order("intake-ordered-story"),
    "intake_disordered_story": _check_story_order("intake-disordered-story"),
    "intake_advanced_field": _check_advanced_field,
    "intake_distress_crying": _check_distress_crying,
    "intake_anger": _check_anger,
    "intake_two_versions": _check_two_versions,
    "intake_third_party_reporter": _check_third_party_reporter,
    "intake_insults": _check_insults,
    "intake_greeting_only": _check_greeting_only,
    "intake_thanks_mid_report": _check_thanks_mid_report,
    "intake_progress_question": _check_progress_question,
    "intake_goodbye_mid_report": _check_goodbye_mid_report,
    "intake_fast_closing": _check_fast_closing,
    "intake_correction": _check_correction,
    "intake_social_other_language": _check_social_other_language,
    "intake_policy_holder_confirmed": _check_policy_holder_confirmed,
}

TARGETS: tuple[EvalTarget, ...] = (
    EvalTarget(
        "intake_ordered_story",
        Dataset.DS_2,
        "El bloque que toca se deduce del caso, con un relato en el orden esperado (BR3.2, AC1.5.2)",
    ),
    EvalTarget(
        "intake_disordered_story",
        Dataset.DS_2,
        "El mismo criterio, con el relato en otro orden: el resultado no depende de el (BR3.2)",
    ),
    EvalTarget(
        "intake_advanced_field",
        Dataset.DS_2,
        "Un dato adelantado no se vuelve a preguntar cuando le llega su turno (BR3.3, AC1.5.4)",
    ),
    EvalTarget(
        "intake_distress_crying",
        Dataset.DS_2,
        "Reconocimiento primero y una sola pregunta despues, ante el llanto (BR5.2, AC1.13.1)",
    ),
    EvalTarget(
        "intake_anger",
        Dataset.DS_2,
        "Calma al segundo insulto y cierre por abuso al tercero (BR5.4, AC1.13.3)",
        blocking=True,
    ),
    EvalTarget(
        "intake_two_versions",
        Dataset.DS_6,
        "Dos versiones contradictorias se guardan las dos, sin juzgar y sin reemplazar (BR5.5, RT-7)",
    ),
    EvalTarget(
        "intake_third_party_reporter",
        Dataset.DS_6,
        "Un tercero que reporta no recibe datos de poliza que no aporto (BR1.5, RT-9)",
        blocking=True,
    ),
    EvalTarget(
        "intake_insults",
        Dataset.DS_6,
        "Ningun turno de la agente lleva una frase de la lista prohibida, bajo insultos sostenidos "
        "(BR5.3, BR5.4, RT-11)",
        blocking=True,
    ),
    EvalTarget(
        "intake_greeting_only",
        Dataset.DS_2,
        "Un saludo a secas se contesta saludando y siguiendo con la pregunta de seguridad, sin modelo (BR1.1, BR5.1)",
    ),
    EvalTarget(
        "intake_thanks_mid_report",
        Dataset.DS_2,
        "Un agradecimiento ante una lectura pendiente no la niega: se agradece y se vuelve a leer (BR3.1)",
    ),
    EvalTarget(
        "intake_progress_question",
        Dataset.DS_2,
        "Cuanto falta se contesta leyendolo del caso, nombrando los bloques pendientes (BR3.2, BR5.1)",
    ),
    EvalTarget(
        "intake_goodbye_mid_report",
        Dataset.DS_2,
        "Una despedida se contesta sola, sin pregunta y sin cerrar el caso (BR5.1)",
    ),
    EvalTarget(
        "intake_social_other_language",
        Dataset.DS_2,
        "Un turno corto en el otro idioma se entiende igual --gracias, y el si a la lectura-- y se contesta en el de la conversacion (BR2.2, BR3.1)",
    ),
    EvalTarget(
        "intake_policy_holder_confirmed",
        Dataset.DS_2,
        "Con una poliza emitida, la agente nombra numero, titular y vehiculo en una pregunta, y lee el si y el no (P3; BR1.2, BR1.6)",
    ),
    EvalTarget(
        "intake_fast_closing",
        Dataset.DS_2,
        "Con los obligatorios dichos no se lee nada de vuelta: se cierra con el numero del caso, se ofrece lo opcional una vez y un no delante declina (P4; BR3.2, BR5.1)",
    ),
    EvalTarget(
        "intake_correction",
        Dataset.DS_2,
        "Un dato ya dicho que vuelve a decirse se anuncia corregido, delante de lo que tocaba y sin pregunta (P4; BR2.1, BR5.1)",
    ),
)


def register_intake_probes() -> None:
    """Registra las dieciseis sondas y los objetivos de U11 en el corredor."""
    for criterio, sonda in SONDAS.items():
        register_check(criterio, sonda)
    register_targets(UNIT, TARGETS)
    # La poliza que el reconocedor entrego mal (2026-10-13): dos sondas que corren el nodo.
    intake_policy_probes.register_intake_policy_probes()


__all__ = ["SONDAS", "TARGETS", "UNIT", "register_intake_probes"]
