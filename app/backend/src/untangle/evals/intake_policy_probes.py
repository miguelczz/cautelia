"""Las sondas de la poliza que el reconocedor entrego mal (2026-10-13).

Nacen de una llamada real: «Soy Marco Parker, mi poliza es POL-200117» llego como «mi poliza
es Paul 201 17», y el caso quedo **sin poliza identificada** aunque la persona dijo su nombre
entero, mientras que en el chat la agente dice «Encontre la poliza ... ¿Eres tu?». Dos criterios,
cada uno con su pareja por idioma:

- `intake_policy_heard_incomplete`: con el nombre completo del titular, **una sola** poliza suya
  y cifras que se parecen, la agente **propone** esa poliza con la frase del chat, no ata nada, y
  solo el si de la persona la ata.
- `intake_policy_not_found_repeat`: si no hay a quien proponer, dice que no la encontro y pide que
  la repita cifra por cifra, **una sola vez**.

**Corren el nodo `intake` de verdad**, sin modelo y sin base: lo que se entiende del mensaje se
entrega ya hecho (`understood`), y el corpus es el **versionado en `app/data/`**, el mismo que
cargaria la base. Asi el caso del titular propuesto es el de la tarjeta de la demostracion y no
uno inventado para la sonda: si el corpus se regenera y esa poliza cambia, la sonda lo dice.
"""

from __future__ import annotations

from collections.abc import Sequence
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
from untangle.orchestration.nodes.intake import policy
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
from untangle.policy_rag.corpus.loading import load_corpus
from untangle.policy_rag.corpus.models import IssuedPolicy
from untangle.providers.ports import GenerationResult, Prompt, SystemInstruction

UNIT = "u11-intake-policy"

_CASES_DIR = "app/evals/cases"

#: Un dia fijo: un nodo no lee el reloj, y la sonda tampoco.
_HOY = date(2026, 10, 13)


class _UnreachableError(RuntimeError):
    """Un puerto que este caso no debe tocar: el mensaje ya llega entendido."""


async def _sin_extractor(_prompt: Prompt) -> GenerationResult:
    msg = "la sonda entrega lo entendido; el extractor no se llama"
    raise _UnreachableError(msg)


def _sin_instruccion(_language: Locale) -> SystemInstruction:
    msg = "la sonda entrega lo entendido; la instruccion de extraccion no se pide"
    raise _UnreachableError(msg)


def _reducida(poliza: IssuedPolicy) -> policy.PolicyMatch:
    """La poliza emitida como la reduce la raiz de composicion: numero, titular, 1.er vehiculo."""
    descripcion = poliza.vehicles[0].get("make_model_year") if poliza.vehicles else None
    return policy.PolicyMatch(
        policy_number=poliza.policy_number,
        holder_name=str(poliza.named_insured.get("full_name", "")),
        vehicle=str(descripcion) if descripcion else None,
    )


def _nodo(tenant: str, root: Path) -> tuple[IntakeNode, tuple[policy.PolicyMatch, ...]]:
    """El nodo con el corpus versionado de la aseguradora detras de sus dos puertos."""
    corpus = load_corpus(tenant, corpus_tenants_dir=root / "app" / "data" / "tenants")
    polizas = tuple(_reducida(p) for p in corpus.policies)
    por_numero = {p.policy_number: p for p in polizas}

    async def exacta(_tenant_id: str, numero: str) -> policy.PolicyMatch | None:
        return por_numero.get(numero)

    async def por_titular(_tenant_id: str, texto: str) -> Sequence[policy.PolicyMatch]:
        return tuple(p for p in polizas if policy.names_holder(texto, p.holder_name))

    nodo = IntakeNode(
        extract=_sin_extractor,
        instruction=_sin_instruccion,
        clock=lambda: _HOY,
        lookup=exacta,
        holder_lookup=por_titular,
    )
    return nodo, polizas


def _completitud() -> Completeness:
    """Un siniestro con la pregunta de seguridad ya contestada, como en las demas sondas."""
    claves = [d.key for d in fields.definitions_for(RecordType.CLAIM)]
    opcionales = frozenset(d.key for d in fields.definitions_for(RecordType.CLAIM) if d.optional)
    return Completeness.derive({c: c == "injuries" for c in claves}, optional=opcionales)


def _entrada(
    caso: GoldenCase, texto: str, *, entendido: bool = True, **cambios: object
) -> IntakeNodeInput:
    """Un turno de una llamada, con lo que la agente entendio de el ya entregado."""
    datos: dict[str, object] = {
        "tenant_id": caso.tenant,
        "case_id": "caso-sonda",
        "record_type": RecordType.CLAIM,
        "case_state": CaseState.CAPTURING,
        "completeness": _completitud(),
        "language": caso.language,
        "turn_text": texto,
        "turn_id": "turno-sonda",
        "spoken": True,
    }
    if entendido:
        datos["understood"] = UnderstandingResponse(
            wants=Want.CONTINUE,
            items=(UnderstoodItem(field_key="identity_and_policy", value=texto),),
            answer=Answer.NONE,
        )
    return IntakeNodeInput.model_validate({**datos, **cambios})


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


def _problemas_de_la_propuesta(
    propuesta: IntakeNodeOutput, esperada: policy.PolicyMatch, language: Locale
) -> list[str]:
    """La agente propone la poliza del titular con la frase del chat y no ata nada."""
    clave, frase = policy.compose_found(esperada, language=language)
    problemas: list[str] = []
    if propuesta.intake_policy_match != esperada:
        problemas.append(f"no propone {esperada.policy_number} a nombre de {esperada.holder_name}")
    if propuesta.intake_response_key != str(clave) or propuesta.intake_response_text != frase:
        problemas.append("la frase no es la del chat para esa poliza")
    if propuesta.intake_policy_confirmed is not None:
        problemas.append("ata la poliza sin que la persona la confirmara")
    return problemas


async def _problemas_de_la_respuesta(
    nodo: IntakeNode, caso: GoldenCase, pendiente: policy.PolicyMatch, *, si: str, no: str
) -> list[str]:
    """El si de la persona ata la poliza propuesta; el no no ata nada."""
    problemas: list[str] = []
    for texto, ata, donde in ((si, True, "el si"), (no, False, "el no")):
        salida = await _responde(
            nodo,
            _entrada(caso, texto, entendido=False, awaiting_policy_confirmation=pendiente),
            problemas,
            donde,
        )
        if salida is None:
            continue
        atada = salida.intake_policy_confirmed
        if ata and atada != pendiente.policy_number:
            problemas.append("el si de la persona no ata la poliza propuesta")
        if not ata and atada is not None:
            problemas.append("ata la poliza aunque la persona dijo que no era ella")
    return problemas


async def _check_heard_incomplete(*, language: Locale, root: Path) -> CheckOutcome:
    """Con el nombre entero, una sola poliza suya y cifras que se parecen: propone, no ata."""
    caso = _caso("intake-policy-heard-incomplete", language, root)
    dicho, si, no = (r.text for r in caso.answers_for("identity_and_policy"))
    nodo, polizas = _nodo(caso.tenant or "", root)

    del_titular = [p for p in polizas if policy.names_holder(dicho, p.holder_name)]
    if len(del_titular) != 1:
        return CheckOutcome(
            passed=False,
            detail=(
                f"'{caso.case_key}': el corpus de '{caso.tenant}' no trae exactamente una poliza "
                f"del titular que nombra el caso ({len(del_titular)})"
            ),
        )
    esperada = del_titular[0]
    problemas: list[str] = []
    oido = policy.heard_policy_number(dicho)
    if (
        oido is None
        or oido.complete
        or not policy.digits_resemble(oido.digits, esperada.policy_number)
    ):
        problemas.append(
            f"'{dicho}' ya no se oye como un numero incompleto que se parece a {esperada.policy_number}"
        )

    propuesta = await _responde(nodo, _entrada(caso, dicho), problemas, "el turno incompleto")
    if propuesta is not None:
        problemas += _problemas_de_la_propuesta(propuesta, esperada, language)
        if propuesta.intake_policy_match is not None:
            problemas += await _problemas_de_la_respuesta(
                nodo, caso, propuesta.intake_policy_match, si=si, no=no
            )
    return _veredicto(caso, problemas)


def _problemas_del_primer_intento(pide: IntakeNodeOutput, language: Locale) -> list[str]:
    """No la encontro: lo dice con la frase del catalogo, pide cifra por cifra y lo anota."""
    frase = policy.compose_not_found_repeat(language=language)
    uno_por_uno = "cifra por cifra" if language == "es" else "digit by digit"
    problemas: list[str] = []
    if pide.intake_response_key != str(policy.POLICY_NOT_FOUND_REPEAT):
        problemas.append("no pide repetir la poliza con la clave del catalogo")
    if pide.intake_response_text != frase:
        problemas.append("no pide repetir la poliza con la frase del catalogo")
    if uno_por_uno not in frase:
        problemas.append(f"la frase no pide '{uno_por_uno}'")
    if pide.intake_policy_repeat_asked is not True:
        problemas.append("no deja anotado que ya pidio repetirla")
    if pide.intake_policy_match is not None or pide.intake_policy_confirmed is not None:
        problemas.append("propone o ata una poliza que no encontro")
    return problemas


async def _check_not_found_repeat(*, language: Locale, root: Path) -> CheckOutcome:
    """Sin a quien proponer: dice que no la encontro y pide repetirla, una sola vez."""
    caso = _caso("intake-policy-not-found-repeat", language, root)
    primero, segundo = (r.text for r in caso.answers_for("identity_and_policy"))
    nodo, polizas = _nodo(caso.tenant or "", root)

    if any(policy.names_holder(f"{primero} {segundo}", p.holder_name) for p in polizas):
        return CheckOutcome(
            passed=False,
            detail=f"'{caso.case_key}': el titular que nombra el caso ya existe en el corpus de '{caso.tenant}'",
        )
    problemas: list[str] = []

    pide = await _responde(nodo, _entrada(caso, primero), problemas, "el primer intento")
    if pide is not None:
        problemas += _problemas_del_primer_intento(pide, language)

    # El segundo intento llega con lo ya pedido anotado, como lo guarda el punto de control.
    otra_vez = await _responde(
        nodo, _entrada(caso, segundo, policy_repeat_asked=True), problemas, "el segundo intento"
    )
    if otra_vez is not None:
        if otra_vez.intake_response_key == str(policy.POLICY_NOT_FOUND_REPEAT):
            problemas.append("pide repetirla una segunda vez")
        if otra_vez.intake_policy_match is not None or otra_vez.intake_policy_confirmed is not None:
            problemas.append("propone o ata una poliza que tampoco encontro")
    return _veredicto(caso, problemas)


SONDAS_ASINCRONAS = {
    "intake_policy_heard_incomplete": _check_heard_incomplete,
    "intake_policy_not_found_repeat": _check_not_found_repeat,
}

TARGETS: tuple[EvalTarget, ...] = (
    EvalTarget(
        "intake_policy_heard_incomplete",
        Dataset.DS_2,
        "Con el nombre completo, una sola poliza suya y cifras que se parecen al numero oido, la agente "
        "propone esa poliza con la frase del chat y solo el si de la persona la ata (P3; BR1.2, BR1.6)",
    ),
    EvalTarget(
        "intake_policy_not_found_repeat",
        Dataset.DS_2,
        "Sin a quien proponer, la agente dice que no encontro la poliza y pide repetirla cifra por "
        "cifra una sola vez (P3; BR1.6)",
    ),
)


def register_intake_policy_probes() -> None:
    """Registra las dos sondas asincronas y sus objetivos."""
    for criterio, sonda in SONDAS_ASINCRONAS.items():
        register_async_check(criterio, sonda)
    register_targets(UNIT, TARGETS)


__all__ = ["SONDAS_ASINCRONAS", "TARGETS", "UNIT", "register_intake_policy_probes"]
