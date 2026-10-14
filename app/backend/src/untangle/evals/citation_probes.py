"""Las sondas de citacion de DS-3 (fase 1, 2026-10-08).

Cada caso `DS-3/<idioma>/<slug>` trae una pregunta sobre una poliza y dice que tiene
que salir: el resultado (verificado o "no hay clausula"), la clausula citada, el
endoso que la modifica, las clausulas que nunca deben citarse y, cuando es distinto,
el idioma de la clausula. La sonda corre **la misma logica que responde en el chat**
--recuperar, proponer con el modelo y verificar con el verificador exacto
(`PolicyVerificationNode.answer`)-- sin registrar la respuesta.

Hasta esta fase los cuarenta casos existian y nada los corria: el conductor de chat
los recibia y no sabia medirlos.

**El que responde lo instala quien corre la sonda**: necesita la base con el corpus,
el modelo de embeddings y el de las citas, y eso lo construye la raiz de
composicion (`untangle.server.understanding_cli`). Sin el, el caso queda no medido.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from untangle.base import Locale
from untangle.evals import loading
from untangle.evals.models import CitationExpectation, Dataset
from untangle.evals.runner.api import (
    CheckOutcome,
    EvalTarget,
    register_async_check,
    register_targets,
)
from untangle.evals.runner.failures import TargetUnavailableError

UNIT = "fase-1-citas"

_CASES_DIR = Path("app/evals/cases/ds3")

#: La forma minima de lo que devuelve el nodo. El corredor no importa el nodo: su
#: cadena llega a la sesion de base de datos, que el corredor tiene prohibida.


class _Valor(Protocol):
    @property
    def value(self) -> str: ...


class _Veredicto(Protocol):
    @property
    def clause_id(self) -> str: ...
    @property
    def outcome(self) -> _Valor: ...


class _Verificacion(Protocol):
    @property
    def outcome(self) -> _Valor: ...
    @property
    def citations(self) -> Sequence[_Veredicto]: ...
    @property
    def clause_language(self) -> str | None: ...


class _Clausula(Protocol):
    @property
    def clause_id(self) -> str: ...
    @property
    def form_id(self) -> str: ...


class _Recuperacion(Protocol):
    @property
    def clauses(self) -> Sequence[_Clausula]: ...


@dataclass(frozen=True)
class CitationQuestion:
    """La pregunta de un caso, como la recibe quien responde."""

    tenant_id: str
    case_ref: str
    policy_number: str
    question: str
    language: Locale


#: Recupera, propone y verifica, sin registrar: `PolicyVerificationNode.answer`.
Answerer = Callable[[CitationQuestion], Awaitable[tuple[_Recuperacion | None, _Verificacion]]]

_respondedor: Answerer | None = None

#: Lo que se respondio en esta corrida, por caso e idioma: los dos criterios de un
#: caso miran **la misma** respuesta. Responder dos veces gastaria el doble y
#: mediria dos respuestas distintas como si fueran una.
_respondido: dict[tuple[str, Locale], tuple[_Recuperacion | None, _Verificacion]] = {}

_VERIFICADA = "verified"


def install(answerer: Answerer | None) -> None:
    """Instala (o quita, con `None`) quien responde de verdad."""
    global _respondedor
    _respondedor = answerer
    _respondido.clear()


def evaluate(
    esperado: CitationExpectation,
    retrieval: _Recuperacion | None,
    verification: _Verificacion,
) -> list[str]:
    """Las diferencias entre la respuesta y lo esperado; vacia si coincide."""
    fallos: list[str] = []
    citadas = {veredicto.clause_id for veredicto in verification.citations}
    if verification.outcome.value != esperado.expected_outcome:
        fallos.append(
            f"resultado '{verification.outcome.value}', se esperaba "
            f"'{esperado.expected_outcome}' (citadas: {sorted(citadas)})"
        )
    if esperado.clause_id is not None and esperado.clause_id not in citadas:
        fallos.append(f"no cito '{esperado.clause_id}' (citadas: {sorted(citadas)})")
    if esperado.amended_by is not None:
        recuperadas = {c.clause_id: c for c in (retrieval.clauses if retrieval else ())}
        del_endoso = {
            clave
            for clave in citadas
            if clave in recuperadas and recuperadas[clave].form_id == esperado.amended_by
        }
        if not del_endoso:
            fallos.append(f"no cito ninguna clausula del endoso '{esperado.amended_by}'")
    recuperadas_ids = {c.clause_id for c in (retrieval.clauses if retrieval else ())}
    for prohibida in esperado.forbidden_clause_ids:
        if prohibida in citadas or prohibida in recuperadas_ids:
            fallos.append(f"recupero o cito la clausula prohibida '{prohibida}'")
    if (
        esperado.clause_language is not None
        and verification.clause_language != esperado.clause_language
    ):
        fallos.append(
            f"idioma de la clausula '{verification.clause_language}', se esperaba "
            f"'{esperado.clause_language}'"
        )
    return fallos


def invented(retrieval: _Recuperacion | None, verification: _Verificacion) -> list[str]:
    """Las citas que salieron sin respaldo; vacia si no hay ninguna.

    **Es la compuerta dura "cero citas inexistentes"** (PRD 11.2, `[bloquea]`): una
    respuesta que se entrega como verificada solo puede citar clausulas que se
    recuperaron de esa poliza, y cada una con su propio veredicto en verde. No mira
    si es la clausula *esperada* --eso lo mide el otro criterio del caso--: una
    respuesta que no encuentra nada no inventa nada.
    """
    if verification.outcome.value != _VERIFICADA:
        return []
    recuperadas = {c.clause_id for c in (retrieval.clauses if retrieval else ())}
    fallos: list[str] = []
    for cita in verification.citations:
        if cita.clause_id not in recuperadas:
            fallos.append(f"cito '{cita.clause_id}', que no se recupero de esa poliza")
        elif cita.outcome.value != _VERIFICADA:
            fallos.append(f"cito '{cita.clause_id}' sin verificarla ({cita.outcome.value})")
    return fallos


async def _responder(
    nombre: str, language: Locale, root: Path
) -> tuple[CitationExpectation, _Recuperacion | None, _Verificacion] | None:
    """La respuesta de este caso, pedida una sola vez por corrida. `None` si el caso
    no trae su citacion."""
    caso = loading.load_case(root / _CASES_DIR / nombre / f"{language}.yaml")
    esperado = caso.citation
    if esperado is None or caso.tenant is None:
        return None
    respondedor = _respondedor
    if respondedor is None:
        msg = (
            "no hay quien responda instalado: las citas se miden con "
            "`mise run evals:citas`, que construye el nodo con el corpus y los modelos"
        )
        raise TargetUnavailableError(msg)
    clave = (nombre, language)
    if clave not in _respondido:
        _respondido[clave] = await respondedor(
            CitationQuestion(
                tenant_id=caso.tenant,
                case_ref=f"eval-{nombre}-{language}",
                policy_number=esperado.policy_number,
                question=esperado.question,
                language=language,
            )
        )
    retrieval, verification = _respondido[clave]
    return esperado, retrieval, verification


def _sonda(nombre: str) -> Callable[..., Awaitable[CheckOutcome]]:
    async def sonda(*, language: Locale, root: Path) -> CheckOutcome:
        respuesta = await _responder(nombre, language, root)
        if respuesta is None:
            return CheckOutcome(passed=False, detail=f"el caso '{nombre}' no trae su citacion")
        fallos = evaluate(*respuesta)
        return CheckOutcome(passed=not fallos, detail="; ".join(fallos))

    return sonda


def _sonda_de_la_compuerta(nombre: str) -> Callable[..., Awaitable[CheckOutcome]]:
    async def sonda(*, language: Locale, root: Path) -> CheckOutcome:
        respuesta = await _responder(nombre, language, root)
        if respuesta is None:
            return CheckOutcome(passed=False, detail=f"el caso '{nombre}' no trae su citacion")
        _, retrieval, verification = respuesta
        fallos = invented(retrieval, verification)
        return CheckOutcome(passed=not fallos, detail="; ".join(fallos))

    return sonda


def criterion_of(case_name: str) -> str:
    return "citation_" + case_name.replace("-", "_")


def gate_criterion_of(case_name: str) -> str:
    """El criterio de la compuerta dura de ese caso: ninguna cita inventada."""
    return "citation_exists_" + case_name.replace("-", "_")


def register_citation_probes(root: Path | None = None) -> None:
    """Registra una sonda por caso de DS-3 y sus objetivos."""
    base = (root or Path.cwd()) / _CASES_DIR
    nombres = tuple(sorted(d.name for d in base.iterdir() if d.is_dir())) if base.is_dir() else ()
    for nombre in nombres:
        register_async_check(criterion_of(nombre), _sonda(nombre))
        register_async_check(gate_criterion_of(nombre), _sonda_de_la_compuerta(nombre))
    register_targets(
        UNIT,
        tuple(
            EvalTarget(criterion_of(nombre), Dataset.DS_3, f"Cita lo que responde: {nombre}")
            for nombre in nombres
        )
        # La compuerta dura, registrada como bloqueante el 2026-10-11 (decision de
        # Miguel): un solo caso con una cita sin respaldo detiene la entrega, y
        # ninguna explicacion de regresion lo levanta.
        + tuple(
            EvalTarget(
                gate_criterion_of(nombre),
                Dataset.DS_3,
                f"Cero citas inexistentes (PRD 11.2 [bloquea]): {nombre}",
                blocking=True,
            )
            for nombre in nombres
        ),
    )


__all__ = [
    "UNIT",
    "Answerer",
    "CitationQuestion",
    "criterion_of",
    "evaluate",
    "gate_criterion_of",
    "install",
    "invented",
    "register_citation_probes",
]
