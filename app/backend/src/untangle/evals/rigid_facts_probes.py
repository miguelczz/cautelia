"""Las sondas de las preguntas rigidas por la poliza (plan 09, punto 6, 2026-11-02).

Decision de Miguel del 2026-11-02, a partir de la revision de una persona externa: lo que la
persona pregunta y es **un dato guardado en su poliza** --el deducible, los limites, la vigencia,
los vehiculos, los conductores, los endosos-- se contesta con codigo desde el registro, sin
recuperacion de clausulas, sin verificador de citas y sin que un modelo lo redacte. Una pregunta de
interpretacion --«¿me cubre un carro de alquiler?»-- sigue por la recuperacion con su cita. Cuatro
criterios, cada uno con su pareja por idioma:

- `rigid_facts_deductible`: un deducible preguntado con la poliza identificada sale del registro: el
  turno elige el camino de los datos, el texto trae **el monto exacto de cada deducible** (calculado
  aqui del registro, no de la plantilla) y el numero de poliza, y nada mas.
- `rigid_facts_vehicles`: lo mismo para los vehiculos, que es un tema sin montos; el texto trae el
  vehiculo y **no** la placa ni el VIN.
- `rigid_facts_coverage_stays_rag`: «¿me cubre un carro de alquiler?» **no** es un tema rigido: el
  turno sigue por la recuperacion y el puerto de datos rigidos ni se toca.
- `rigid_facts_needs_policy`: un tema rigido sin la poliza identificada no se contesta de memoria ni
  con la de otra persona: el turno sigue como siempre, que es pedir la poliza, y el puerto no se toca.

**Corren las funciones reales del turno** (`orchestration.rigid_route`: la eleccion del camino y la
llamada al puerto) y el armado real de la respuesta (`policy_rag.facts.rigid`), sin modelo y sin base:
la poliza es la del **corpus versionado** en `app/data/tenants/`, el mismo que cargaria la base, y el
puerto es un doble que lo lee de memoria y cuenta cuantas veces lo llamaron.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path

from untangle.base import Locale, RigidTopic
from untangle.case_record.models import RecordType
from untangle.evals import loading
from untangle.evals.models import Dataset, GoldenCase, RigidFactsExpectation
from untangle.evals.runner.api import (
    CheckOutcome,
    EvalTarget,
    register_async_check,
    register_targets,
)
from untangle.orchestration import rigid_route
from untangle.orchestration.nodes.intake.understanding import (
    UnderstandingResponse,
    Want,
)
from untangle.orchestration.rigid_route import RigidAnswerView
from untangle.policy_rag.corpus.loading import load_corpus
from untangle.policy_rag.corpus.models import IssuedPolicy
from untangle.policy_rag.facts import formatting, rigid

UNIT = "u8-rigid-facts"

_CASES_DIR = "app/evals/cases"

#: Un dia fijo: el turno entrega la fecha y la sonda tampoco lee el reloj.
_HOY = date(2026, 11, 2)


class _PuertoEnMemoria:
    """El puerto de datos rigidos sobre el corpus versionado, que cuenta las llamadas."""

    def __init__(self, polizas: dict[str, IssuedPolicy]) -> None:
        self._polizas = polizas
        self.calls = 0

    async def answer(  # noqa: PLR0913 -- la firma del puerto `RigidFactsPort`
        self,
        tenant_id: str,
        policy_number: str,
        topic: RigidTopic,
        *,
        language: Locale,
        on: date,
        spoken: bool,
    ) -> RigidAnswerView | None:
        self.calls += 1
        poliza = self._polizas.get(policy_number)
        if poliza is None or poliza.tenant_id != tenant_id:
            return None
        respuesta = rigid.render(topic, poliza, language=language, on=on, spoken=spoken)
        if respuesta is None:
            return None
        return RigidAnswerView(
            topic=respuesta.topic, copy_key=respuesta.copy_key, text=respuesta.text
        )


def _caso(nombre: str, language: Locale, root: Path) -> GoldenCase:
    return loading.load_case(root / _CASES_DIR / "ds2" / nombre / f"{language}.yaml")


def _cifra(units: int, language: Locale) -> str:
    """El monto en pesos con los separadores del idioma, calculado aqui y no por la plantilla."""
    pesos = units * formatting.PESOS_PER_UNIT
    return f"{pesos:,}".replace(",", ".") if language == "es" else f"{pesos:,}"


def _lectura(esperado: RigidFactsExpectation) -> UnderstandingResponse:
    """Lo que el modelo habria leido del mensaje, ya entregado."""
    return UnderstandingResponse(
        wants=Want(esperado.wants),
        person_question=esperado.message,
        asks_about_coverage=esperado.asks_about_coverage,
        rigid_topic=esperado.topic,
    )


def _veredicto(caso: GoldenCase, problemas: list[str]) -> CheckOutcome:
    if problemas:
        return CheckOutcome(passed=False, detail=f"'{caso.case_key}': " + "; ".join(problemas))
    return CheckOutcome(passed=True)


async def _comprobar(nombre: str, *, language: Locale, root: Path) -> CheckOutcome:
    caso = _caso(nombre, language, root)
    esperado = caso.rigid_facts
    assert esperado is not None  # noqa: S101 -- el archivo del caso lo declara; si no, es un caso mal escrito
    assert caso.tenant is not None  # noqa: S101 -- idem
    corpus = load_corpus(caso.tenant, corpus_tenants_dir=root / "app" / "data" / "tenants")
    polizas = {p.policy_number: p for p in corpus.policies}
    registro = polizas.get(esperado.policy_number)
    if registro is None:
        return CheckOutcome(
            passed=False,
            detail=f"'{caso.case_key}': la poliza '{esperado.policy_number}' no esta en el corpus",
        )
    puerto = _PuertoEnMemoria(polizas)
    problemas: list[str] = []

    # 1. El camino: el mismo que elige el turno con lo entendido y el estado del caso.
    tema = rigid_route.topic_for(
        _lectura(esperado),
        record_type=RecordType(esperado.record_type),
        policy_identified=esperado.policy_identified,
    )
    respuesta = (
        await rigid_route.answer(
            puerto,
            tenant_id=caso.tenant,
            policy_number=esperado.policy_number,
            topic=tema,
            language=caso.language,
            on=_HOY,
            spoken=False,
        )
        if tema is not None
        else None
    )
    camino = "facts" if respuesta is not None else "rag"
    if camino != esperado.route:
        problemas.append(f"el turno va por '{camino}', se esperaba '{esperado.route}'")

    # 2. Por la RAG el puerto de datos rigidos no se toca: contestar de memoria seria inventar.
    if esperado.route == "rag" and puerto.calls:
        problemas.append(f"el puerto de datos rigidos se llamo {puerto.calls} vez/veces")

    # 3. Por el registro: el texto trae el dato exacto de la poliza y nada de lo que no debe.
    if esperado.route == "facts" and respuesta is not None:
        problemas.extend(_texto_exacto(esperado, registro, respuesta.text, caso.language))
    return _veredicto(caso, problemas)


def _texto_exacto(
    esperado: RigidFactsExpectation, registro: IssuedPolicy, texto: str, language: Locale
) -> list[str]:
    problemas: list[str] = []
    for clave in esperado.amounts:
        unidades = registro.limits_and_deductibles.get(clave)
        if unidades is None:
            problemas.append(f"el registro no trae '{clave}'")
        elif _cifra(int(str(unidades)), language) not in texto:
            problemas.append(
                f"el texto no trae el monto de '{clave}' "
                f"({_cifra(int(str(unidades)), language)}): {texto!r}"
            )
    problemas.extend(
        f"el texto no menciona '{fragmento}': {texto!r}"
        for fragmento in esperado.mentions
        if fragmento not in texto
    )
    problemas.extend(
        f"el texto trae '{fragmento}', que no puede traer"
        for fragmento in esperado.forbids
        if fragmento in texto
    )
    return problemas


def _sonda(nombre: str) -> Callable[..., Awaitable[CheckOutcome]]:
    async def sonda(*, language: Locale, root: Path) -> CheckOutcome:
        return await _comprobar(nombre, language=language, root=root)

    return sonda


#: criterio -> nombre del caso. El criterio es lo que declara `expected_verdicts` del archivo.
CASOS: dict[str, str] = {
    "rigid_facts_deductible": "rigid-deductible-from-record",
    "rigid_facts_vehicles": "rigid-vehicles-from-record",
    "rigid_facts_coverage_stays_rag": "rigid-coverage-question-stays-rag",
    "rigid_facts_needs_policy": "rigid-needs-policy-first",
}

SONDAS_ASINCRONAS = {criterio: _sonda(nombre) for criterio, nombre in CASOS.items()}

TARGETS: tuple[EvalTarget, ...] = (
    EvalTarget(
        "rigid_facts_deductible",
        Dataset.DS_2,
        "Un deducible preguntado con la poliza identificada sale del registro: el monto exacto de "
        "cada deducible, sin recuperacion, sin citas y sin modelo (plan 09, punto 6)",
    ),
    EvalTarget(
        "rigid_facts_vehicles",
        Dataset.DS_2,
        "Los vehiculos asegurados salen del registro sin placa ni VIN (plan 09, punto 6)",
    ),
    EvalTarget(
        "rigid_facts_coverage_stays_rag",
        Dataset.DS_2,
        "Una pregunta de cobertura no es un tema rigido: sigue por la recuperacion con su cita y "
        "el puerto de datos rigidos no se toca (plan 09, punto 6)",
    ),
    EvalTarget(
        "rigid_facts_needs_policy",
        Dataset.DS_2,
        "Un tema rigido sin la poliza identificada no se contesta: el turno sigue pidiendo la "
        "poliza como siempre (plan 09, punto 6)",
    ),
)


def register_rigid_facts_probes() -> None:
    """Registra las cuatro sondas asincronas y sus objetivos."""
    for criterio, sonda in SONDAS_ASINCRONAS.items():
        register_async_check(criterio, sonda)
    register_targets(UNIT, TARGETS)


__all__ = ["CASOS", "SONDAS_ASINCRONAS", "TARGETS", "UNIT", "register_rigid_facts_probes"]
