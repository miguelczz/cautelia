"""El respaldo de la afirmación: una segunda pasada del juez, nunca en el turno (paso 9, BR3.6, BR3.7).

`CitationVerifier.verify` (paso 5) ya decidió `verified` con las cuatro
comprobaciones exactas -- existencia, inquilino, póliza, vigencia -- sin
llamar a ningún modelo (BR3.1 a BR3.5). Lo que este módulo añade es una
pregunta distinta, que el código no puede responder: **¿el texto de la
cláusula sostiene lo que la respuesta afirmó?** (AC2.2.2). Es un juicio de
lenguaje, así que lo hace el juez, y por eso su veredicto no es una compuerta
dura como las de código: cuenta solo cuando el juez está calibrado (ADR-014),
y mientras no lo esté sale "no medida" sin bloquear ni desbloquear nada
(BR3.6). Las cuatro comprobaciones exactas de `verifier.py` siguen bloqueando
igual, calibrado el juez o no (BR3.3).

**Cómo se engancha con la calibración, sin reinventarla.** `CRITERION` es el
nombre con el que este respaldo entra en `CaseRow.criteria_results` /
`criteria_judgment` (`JudgmentKind.JUDGE`); `evals.gates.judgment.
criterion_counts` -- ya construido por U21 -- es quien decide, de forma
genérica, si un criterio juzgado por el juez cuenta para una corrida: solo
cuando `(criterion, idioma)` está en el conjunto que devuelve
`evals.gates.calibration.calibrated_criteria`. Este módulo no repite esa
lógica: la prueba de este paso conecta `CRITERION` con esa función ya
probada, en vez de escribir un "apagado" propio que podría decir algo
distinto.

**Por qué no corre en el turno.** BR3.7 y D22: dentro del turno solo corren
los tres controles baratos de cumplimiento (la guardia, la petición de
persona, la emergencia); ni la verificación exacta ni, menos aún, esta
segunda pasada con modelo -- que además le cuesta al proyecto y no tiene
presupuesto de latencia de turno -- corren ahí. El contrato de importación
`respaldo-nunca-en-el-turno` de `.importlinter` comprueba que ni
`orchestration.nodes.policy_verification` ni `compliance.controls` importan
este módulo.

**El puerto, y por qué no recibe un `Prompt` armado.** `JudgePort` abstrae la
llamada entera -- construir el prompt, llamarlo con `Use.EVALS` y leer la
respuesta estructurada -- porque ese cableado real es de quien construya el
respaldo de fondo (todavía no existe ninguna unidad que lo haga, igual que
U12 `graph-runtime`): aquí solo hay contrato y decisión, ninguna prueba llama
al juez de verdad, con veredictos grabados, como ya hizo U21 (CG-U8, "Como se
trabaja aquí").
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from pydantic import BaseModel, Field

#: El nombre con el que este respaldo entra en `CaseRow.criteria_results` y
#: `criteria_judgment` (AC2.2.2). Una sola grafía: el reporte, el diff contra
#: la línea base y la calibración lo agrupan por esta clave.
CRITERION = "citation_backing"


@dataclass(frozen=True)
class BackingCheck:
    """Lo que el juez necesita para responder, y nada más (BR2.7).

    El texto de la cláusula y la afirmación son datos, nunca instrucción: el
    puerto real los coloca en la posición de contenido del prompt, jamás en
    la de sistema.
    """

    clause_id: str
    clause_text: str
    claim: str


class BackingVerdict(BaseModel):
    """La respuesta estructurada del juez para una comprobación (AC2.2.2).

    `backed` es el veredicto; `rationale` existe para que un desacuerdo con la
    etiqueta humana de DS-7 se pueda leer, no solo contar (`compute_rates`
    ignora el texto y compara solo el veredicto).
    """

    model_config = {"extra": "forbid"}

    backed: bool
    rationale: str = Field(min_length=1)


@dataclass(frozen=True)
class BackingResult:
    """El veredicto de una comprobación, con la cita a la que pertenece."""

    clause_id: str
    verdict: BackingVerdict


#: Le pregunta al juez por **una** comprobación y espera su veredicto. Quien
#: cablea el puerto real arma el prompt con el texto de la cláusula y la
#: afirmación como contenido delimitado (BR2.7), llama con `Use.EVALS`
#: (ADR-014: el juez propio calibrado para la compuerta) y valida la
#: respuesta contra `BackingVerdict`.
JudgePort = Callable[[BackingCheck], Awaitable[BackingVerdict]]


async def check_citation_backing(
    checks: Sequence[BackingCheck], *, judge: JudgePort
) -> tuple[BackingResult, ...]:
    """El respaldo de cada comprobación, en el orden recibido.

    No decide si el criterio cuenta para una compuerta -- eso es
    `evals.gates.judgment.criterion_counts`, con `CRITERION` y la calibración
    del juez --: aquí solo se pregunta y se responde.
    """
    veredictos: list[BackingResult] = []
    for comprobacion in checks:
        veredicto = await judge(comprobacion)
        veredictos.append(BackingResult(clause_id=comprobacion.clause_id, verdict=veredicto))
    return tuple(veredictos)


__all__ = [
    "CRITERION",
    "BackingCheck",
    "BackingResult",
    "BackingVerdict",
    "JudgePort",
    "check_citation_backing",
]
