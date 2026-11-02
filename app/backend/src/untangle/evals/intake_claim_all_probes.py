"""Las sondas de los datos del accidente en un solo mensaje (plan 09, punto 2, 2026-11-02).

Decision de Miguel del 2026-11-02, a partir de la revision de una persona externa: en el chat,
al empezar el reporte, la agente pide **en un solo mensaje** todo lo que falta, como una lista
corta, y acepta las respuestas en uno o en varios mensajes; en la llamada sigue una pregunta a la
vez, porque por voz una lista larga no se retiene de oido. Dos criterios, uno por canal:

- `intake_claim_all_at_once` (chat): el primer turno sin datos pide la lista entera; una respuesta
  parcial recibe una lista **solo con lo que falta**; y si ya se pidio la lista y la persona no
  anoto nada, sale una sola pregunta, no la lista otra vez.
- `intake_claim_voice_one_at_a_time` (llamada): el mismo primer turno es una sola pregunta del
  catalogo, nunca una lista.

**La lista sale del codigo.** Lo que cada sonda cuenta es cuantas lineas trae la lista contra los
bloques a los que todavia les falta algo segun `blocks.missing_blocks` --el mecanismo real que
decide que toca--, no contra el texto del catalogo: una lista que el modelo o una frase fija
inventaran no seguiria al caso.

**Corren el nodo `intake` de verdad**, sin modelo y sin base: lo entendido de cada mensaje se
entrega ya hecho (`understood`), como en las sondas de la poliza.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from untangle.base import Locale
from untangle.case_record import fields
from untangle.case_record.models import CaseState, Completeness, RecordType
from untangle.evals import loading
from untangle.evals.models import Dataset, GoldenCase
from untangle.evals.runner.api import (
    CheckOutcome,
    EvalTarget,
    register_async_check,
    register_targets,
)
from untangle.orchestration.nodes.intake import blocks, composition
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.orchestration.nodes.intake.node import (
    IntakeNode,
    IntakeNodeInput,
    IntakeNodeOutput,
)
from untangle.orchestration.nodes.intake.understanding import (
    Answer,
    UnderstandingResponse,
    UnderstoodItem,
    Want,
)
from untangle.providers.ports import GenerationResult, Prompt, SystemInstruction

UNIT = "u11-intake-claim-all"

_CASES_DIR = "app/evals/cases"

#: Un dia fijo: un nodo no lee el reloj, y la sonda tampoco.
_HOY = date(2026, 11, 2)

#: Lo que dice la persona en el primer turno y cuando no tiene mas que decir: no importa el
#: contenido, solo que no traiga datos.
_PRIMER_MENSAJE: dict[Locale, str] = {
    "es": "Quiero reportar un choque.",
    "en": "I want to report a crash.",
}
_SIN_DATOS: dict[Locale, str] = {"es": "No sé.", "en": "I don't know."}

#: Las lineas de una lista: cada una empieza con este marcador.
_VINETA = "- "


class _UnreachableError(RuntimeError):
    """Un puerto que este caso no debe tocar: el mensaje ya llega entendido."""


async def _sin_extractor(_prompt: Prompt) -> GenerationResult:
    msg = "la sonda entrega lo entendido; el extractor no se llama"
    raise _UnreachableError(msg)


def _sin_instruccion(_language: Locale) -> SystemInstruction:
    msg = "la sonda entrega lo entendido; la instruccion de extraccion no se pide"
    raise _UnreachableError(msg)


def _nodo() -> IntakeNode:
    return IntakeNode(extract=_sin_extractor, instruction=_sin_instruccion, clock=lambda: _HOY)


def _completitud(dichos: frozenset[str] = frozenset()) -> Completeness:
    """Un siniestro con solo `dichos` anotado, con los opcionales fuera de la cuenta."""
    claves = [d.key for d in fields.definitions_for(RecordType.CLAIM)]
    opcionales = frozenset(d.key for d in fields.definitions_for(RecordType.CLAIM) if d.optional)
    return Completeness.derive({c: c in dichos for c in claves}, optional=opcionales)


def _entrada(  # noqa: PLR0913 -- el caso, el texto, la completitud, el canal y los dos que cambian por turno
    caso: GoldenCase,
    texto: str,
    *,
    completitud: Completeness,
    spoken: bool,
    items: tuple[UnderstoodItem, ...] = (),
    previous_block: Block | None = None,
) -> IntakeNodeInput:
    return IntakeNodeInput.model_validate(
        {
            "tenant_id": caso.tenant,
            "case_id": "caso-sonda",
            "record_type": RecordType.CLAIM,
            "case_state": CaseState.CAPTURING,
            "completeness": completitud,
            "language": caso.language,
            "turn_text": texto,
            "turn_id": "turno-sonda",
            "spoken": spoken,
            "previous_block": previous_block,
            "understood": UnderstandingResponse(
                wants=Want.REPORT_ACCIDENT if not items else Want.CONTINUE,
                items=items,
                answer=Answer.NONE,
            ),
        }
    )


async def _responde(
    nodo: IntakeNode, entrada: IntakeNodeInput, problemas: list[str], donde: str
) -> IntakeNodeOutput | None:
    try:
        return await nodo.run(entrada)
    except Exception as error:  # noqa: BLE001 -- una sonda dice que fallo, no se cae con el
        problemas.append(f"{donde}: el nodo levanto {type(error).__name__}")
        return None


def _caso(nombre: str, language: Locale, root: Path) -> GoldenCase:
    return loading.load_case(root / _CASES_DIR / "ds2" / nombre / f"{language}.yaml")


def _veredicto(caso: GoldenCase, problemas: list[str]) -> CheckOutcome:
    if problemas:
        return CheckOutcome(passed=False, detail=f"'{caso.case_key}': " + "; ".join(problemas))
    return CheckOutcome(passed=True)


def _lineas(salida: IntakeNodeOutput) -> int:
    """Cuantas lineas de lista trae la respuesta."""
    return sum(1 for linea in salida.intake_response_text.splitlines() if linea.startswith(_VINETA))


def _es_pregunta_unica(salida: IntakeNodeOutput) -> bool:
    return _lineas(salida) == 0 and salida.intake_response_key.startswith("intake.question.")


async def _check_all_at_once(*, language: Locale, root: Path) -> CheckOutcome:
    """Chat: la lista entera al empezar, solo lo que falta despues, una pregunta si no hubo avance."""
    caso = _caso("intake-claim-all-at-once", language, root)
    # El guion trae claves de campo como texto; el nodo las valida contra el tipo del caso.
    parcial = tuple(
        UnderstoodItem(field_key=r.field_key, value=r.text)  # type: ignore[arg-type]
        for r in caso.script
    )
    nodo = _nodo()
    problemas: list[str] = []

    # 1. Un primer mensaje sin datos: la lista de lo que falta, con los opcionales al final.
    vacio = _completitud()
    obligatorios = len(blocks.missing_blocks(RecordType.CLAIM, vacio))
    opcionales = len(blocks.optional_blocks_missing(RecordType.CLAIM, vacio))
    primero = await _responde(
        nodo,
        _entrada(caso, _PRIMER_MENSAJE[language], completitud=vacio, spoken=False),
        problemas,
        "el primer mensaje",
    )
    if primero is not None:
        if _lineas(primero) != obligatorios + opcionales:
            problemas.append(
                f"el primer mensaje trae {_lineas(primero)} lineas, y al caso le faltan "
                f"{obligatorios} bloques obligatorios y {opcionales} opcionales"
            )
        if "?" in primero.intake_response_text.splitlines()[0]:
            problemas.append("la lista abre con una pregunta, no con la invitacion a contar")

    # 2. Una respuesta parcial: la lista solo con lo que falta, sin lo dicho ni los opcionales.
    dichos = frozenset(item.field_key for item in parcial)
    despues = _completitud(dichos)
    faltan = len(blocks.missing_blocks(RecordType.CLAIM, despues))
    parcial_salida = await _responde(
        nodo,
        _entrada(
            caso,
            " ".join(item.value for item in parcial),
            completitud=vacio,
            spoken=False,
            items=parcial,
            previous_block=Block.SAFETY,
        ),
        problemas,
        "la respuesta parcial",
    )
    if parcial_salida is not None:
        if _lineas(parcial_salida) != faltan:
            problemas.append(
                f"tras una respuesta parcial la lista trae {_lineas(parcial_salida)} lineas "
                f"y al caso le faltan {faltan} bloques"
            )
        if faltan < obligatorios and _lineas(parcial_salida) >= obligatorios:
            problemas.append("la lista vuelve a pedir lo que la persona ya dijo")

    # 3. Ya se pidio la lista y la persona no anoto nada: una sola pregunta.
    repetido = await _responde(
        nodo,
        _entrada(
            caso, _SIN_DATOS[language], completitud=vacio, spoken=False, previous_block=Block.SAFETY
        ),
        problemas,
        "el mensaje sin datos",
    )
    if repetido is not None and not _es_pregunta_unica(repetido):
        problemas.append("tras un mensaje sin datos repite la lista en vez de una sola pregunta")
    return _veredicto(caso, problemas)


async def _check_voice_one_at_a_time(*, language: Locale, root: Path) -> CheckOutcome:
    """Llamada: el primer turno es una sola pregunta del catalogo, nunca una lista."""
    caso = _caso("intake-claim-voice-one-at-a-time", language, root)
    problemas: list[str] = []
    salida = await _responde(
        _nodo(),
        _entrada(caso, caso.script[0].text, completitud=_completitud(), spoken=True),
        problemas,
        "el primer turno de la llamada",
    )
    if salida is not None:
        if not _es_pregunta_unica(salida):
            problemas.append("la llamada pide una lista en vez de una sola pregunta")
        primera = blocks.next_block(RecordType.CLAIM, _completitud(), CaseState.CAPTURING)
        esperada = composition.compose_question(
            primera,
            blocks.missing_fields_in_block(RecordType.CLAIM, primera, _completitud()),
            language=language,
        )
        if salida.intake_response_text != esperada:
            problemas.append("la pregunta de la llamada no es la del bloque que toca")
    return _veredicto(caso, problemas)


SONDAS_ASINCRONAS = {
    "intake_claim_all_at_once": _check_all_at_once,
    "intake_claim_voice_one_at_a_time": _check_voice_one_at_a_time,
}

TARGETS: tuple[EvalTarget, ...] = (
    EvalTarget(
        "intake_claim_all_at_once",
        Dataset.DS_2,
        "En el chat la agente pide en un solo mensaje todo lo que falta del accidente, como lista "
        "que sale del codigo; tras una respuesta parcial pide solo lo que falta, y sin avance "
        "hace una sola pregunta (plan 09, punto 2)",
    ),
    EvalTarget(
        "intake_claim_voice_one_at_a_time",
        Dataset.DS_2,
        "En la llamada la agente sigue preguntando de a una cosa: una lista larga no se retiene "
        "de oido (plan 09, punto 2)",
    ),
)


def register_intake_claim_all_probes() -> None:
    """Registra las dos sondas asincronas y sus objetivos."""
    for criterio, sonda in SONDAS_ASINCRONAS.items():
        register_async_check(criterio, sonda)
    register_targets(UNIT, TARGETS)


__all__ = ["SONDAS_ASINCRONAS", "TARGETS", "UNIT", "register_intake_claim_all_probes"]
