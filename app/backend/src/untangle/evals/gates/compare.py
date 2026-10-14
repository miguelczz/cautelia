"""La comparacion contra la linea base y el veredicto de la compuerta (F1, BR2.x).

Cinco reglas, cada una con su prueba que la aisla (regla heredada de U9, ajuste
del 2026-09-16):

- **Compuertas duras** (PRD 11.2, `[bloquea]`): un caso que falla un criterio
  declarado `EvalTarget.blocking=True` bloquea siempre, sin excepcion. Ninguna
  explicacion lo levanta, porque una compuerta dura no se mide contra el
  pasado: es pasa o falla por caso (correccion del 2026-09-25, ver
  `code-generation-plan.md` paso 0).
- BR2.2: en los conjuntos pequenos (DS-2, DS-3, DS-6), un caso que pasaba en la
  linea base y ahora falla un criterio **no bloqueante** bloquea, salvo que una
  explicacion lo nombre.
- BR2.3: en las metricas de denominador grande, una caida de mas de 2 puntos
  porcentuales bloquea, con la misma salida de explicacion.
- BR2.4: un caso inestable no cuenta para la compuerta, en ningun sentido: ni
  como fallo propio ni como regresion ni como mejora. Si su fallo era de un
  criterio bloqueante, se reporta en su propia linea de todas formas: nunca en
  silencio.
- BR3.1 a BR3.3: un criterio juzgado por el juez solo cuenta donde esta
  calibrado; sin calibracion sale "no medida" y no bloquea, y las compuertas
  juzgadas por codigo siguen bloqueando igual (`judgment.criterion_counts`).
"""

from __future__ import annotations

from dataclasses import dataclass

from untangle.base import Locale
from untangle.evals.gates.audit import AuditFinding
from untangle.evals.gates.judgment import effective_failed_criteria
from untangle.evals.gates.metrics import criterion_pass_rates
from untangle.evals.gates.models import Baseline, RegressionExplanation, UnstableCase
from untangle.evals.models import CaseStatus, JudgmentKind
from untangle.evals.report import EvalReport

#: Los tres conjuntos pequenos donde manda BR2.2 y no el umbral porcentual de
#: BR2.3 ("El umbral porcentual no se aplica a los conjuntos pequenos").
SMALL_DENOMINATOR_DATASETS = frozenset({"DS-2", "DS-3", "DS-6"})

#: 2 puntos porcentuales (BR2.3).
METRIC_DROP_THRESHOLD = 0.02


def _dataset_of(case_key: str) -> str:
    return case_key.split("/", 1)[0]


def _judge_criteria_in_report(report: EvalReport) -> frozenset[tuple[str, Locale]]:
    """Los pares (criterio, idioma) que este reporte juzgo con el juez."""
    return frozenset(
        (criterio, fila.language)
        for fila in report.cases
        for criterio in fila.criteria_results
        if fila.criteria_judgment.get(criterio) is JudgmentKind.JUDGE
    )


@dataclass(frozen=True)
class GateRules:
    """Los dos conjuntos que deciden que cuenta para la compuerta.

    Agrupados en un solo parametro para no pasar de cinco argumentos en
    `evaluate` (PLR0913).
    """

    blocking_criteria: frozenset[str] = frozenset()
    calibrated_criteria: frozenset[tuple[str, Locale]] = frozenset()


@dataclass(frozen=True)
class MetricDrop:
    """Una metrica de denominador grande que cayo mas de lo permitido (BR2.3)."""

    criterion: str
    language: Locale
    baseline_rate: float
    current_rate: float

    @property
    def delta(self) -> float:
        return self.baseline_rate - self.current_rate


@dataclass(frozen=True)
class GateVerdict:
    """Lo que decide si la entrega pasa, con cada motivo nombrado (BR2.x)."""

    #: `False` cuando no habia linea base vigente: la compuerta corrio sin
    #: comparar (FD-U21-5), y solo sus propios fallos duros pueden bloquearla.
    compared: bool
    blocked: bool
    #: Casos que fallaron un criterio bloqueante (`[bloquea]`), sin marcar
    #: inestables: bloquean siempre, y ninguna explicacion los excusa.
    blocking_failures: tuple[str, ...] = ()
    #: Los mismos, pero marcados inestables (BR2.4): no cuentan para la
    #: compuerta, pero se listan aqui para que el fallo nunca quede en
    #: silencio.
    unstable_blocking_failures: tuple[str, ...] = ()
    #: Casos fallidos en un criterio **no** bloqueante, sin explicacion y sin
    #: marcar inestables.
    unexplained_failures: tuple[str, ...] = ()
    newly_failed: tuple[str, ...] = ()
    newly_passed: tuple[str, ...] = ()
    explained_regressions: tuple[str, ...] = ()
    unstable_excluded: tuple[str, ...] = ()
    metric_drops: tuple[MetricDrop, ...] = ()
    #: Hallazgos del segundo detector (BR4.1, BR4.2): siempre bloquean, y se
    #: adjuntan aqui desde `gate.run_gate`, que es quien conoce que archivos
    #: revisar.
    pii_findings: tuple[AuditFinding, ...] = ()
    #: `"criterio@idioma"` para cada criterio del juez que este reporte trajo
    #: y que no esta calibrado (BR3.2): se declara, nunca se omite (BR1.3).
    judge_not_calibrated: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()


def evaluate(
    report: EvalReport,
    *,
    baseline: Baseline | None,
    unstable: tuple[UnstableCase, ...],
    explanations: tuple[RegressionExplanation, ...],
    rules: GateRules | None = None,
) -> GateVerdict:
    """El veredicto de la compuerta (Flujo 1, pasos 3 a 6).

    Dos fuentes de bloqueo, y no una:

    1. **Compuertas duras.** Un caso que fallo un criterio de
       `rules.blocking_criteria` bloquea siempre: ninguna explicacion lo
       excusa, porque una compuerta dura no se mide contra el pasado, es
       absoluta por caso (PRD 11.2). Un caso inestable no cuenta para la
       compuerta (BR2.4), pero su fallo bloqueante se reporta en
       `unstable_blocking_failures` de todas formas, nunca en silencio.
    2. **Regresiones.** Un caso que fallo un criterio **no** bloqueante bloquea
       salvo que este inestable o que una explicacion lo nombre (BR2.2). Una
       linea base solo se publica con las compuertas duras en verde (BR2.1),
       asi que todo caso `case_verdicts` es `passed`: cualquier caso que falle
       ahora un criterio no bloqueante "pasaba" por definicion, aunque sea uno
       recien creado que la linea base nunca vio.

    Antes de las dos, un caso solo cuenta como fallido por lo que
    `judgment.effective_failed_criteria` deja despues de descontar los
    criterios del juez sin calibrar (BR3.1 a BR3.3): un caso cuyo unico fallo
    era un criterio del juez sin calibrar no bloquea nada, y tampoco aparece
    como regresion.

    `newly_failed` y `explained_regressions` siguen existiendo aparte, solo
    para el conjunto DS-2/DS-3/DS-6 (BR2.2 los nombra explicitamente): son la
    seccion informativa del diff, no una tercera fuente de bloqueo.
    """
    reglas = rules if rules is not None else GateRules()
    blocking_criteria = reglas.blocking_criteria
    calibrated_criteria = reglas.calibrated_criteria

    inestables = {caso.case_key for caso in unstable}
    explicados = {clave for explicacion in explanations for clave in explicacion.case_keys}

    fallos_efectivos = {
        fila.case_key: effective_failed_criteria(fila, calibrated=calibrated_criteria)
        for fila in report.cases
    }
    fallidos = tuple(fila for fila in report.cases if fallos_efectivos[fila.case_key])

    sin_calibrar = tuple(
        sorted(
            f"{criterio}@{idioma}"
            for criterio, idioma in _judge_criteria_in_report(report) - calibrated_criteria
        )
    )

    # Compuertas duras primero, y separadas del resto: ninguna explicacion las
    # toca, y un caso inestable con un fallo bloqueante se reporta aparte en
    # vez de desaparecer junto con los demas casos inestables.
    bloqueos_duros = tuple(
        sorted(
            fila.case_key
            for fila in fallidos
            if fila.case_key not in inestables
            and any(c in blocking_criteria for c in fallos_efectivos[fila.case_key])
        )
    )
    bloqueos_inestables = tuple(
        sorted(
            fila.case_key
            for fila in fallidos
            if fila.case_key in inestables
            and any(c in blocking_criteria for c in fallos_efectivos[fila.case_key])
        )
    )
    bloqueantes = set(bloqueos_duros) | set(bloqueos_inestables)

    # BR2.4: un caso inestable no cuenta para la compuerta, en ningun sentido.
    excluidos = tuple(sorted(fila.case_key for fila in fallidos if fila.case_key in inestables))

    fallos_sin_explicar = tuple(
        sorted(
            fila.case_key
            for fila in fallidos
            if fila.case_key not in inestables
            and fila.case_key not in explicados
            and fila.case_key not in bloqueantes
        )
    )

    razones = [f"el caso '{clave}' fallo un criterio bloqueante" for clave in bloqueos_duros]
    razones.extend(f"el caso '{clave}' fallo sin explicacion" for clave in fallos_sin_explicar)
    razones.extend(f"'{par}': juez sin calibrar, no medida (BR3.2)" for par in sin_calibrar)

    if baseline is None:
        # FD-U21-5: sin linea base vigente la compuerta corre, publica y no
        # compara; las compuertas duras y los fallos sin explicar bloquean
        # igual, porque ninguno de los dos depende de tener con que comparar.
        return GateVerdict(
            compared=False,
            blocked=bool(bloqueos_duros) or bool(fallos_sin_explicar),
            blocking_failures=bloqueos_duros,
            unstable_blocking_failures=bloqueos_inestables,
            unexplained_failures=fallos_sin_explicar,
            unstable_excluded=excluidos,
            judge_not_calibrated=sin_calibrar,
            reasons=tuple(razones),
        )

    nuevos_fallos: list[str] = []
    regresiones_explicadas: list[str] = []
    for fila in report.cases:
        if fila.case_key in inestables or fila.case_key in bloqueantes:
            continue
        anterior = baseline.case_verdicts.get(fila.case_key)
        if anterior is not CaseStatus.PASSED or not fallos_efectivos[fila.case_key]:
            continue
        if _dataset_of(fila.case_key) not in SMALL_DENOMINATOR_DATASETS:
            continue
        if fila.case_key in explicados:
            regresiones_explicadas.append(fila.case_key)
        else:
            nuevos_fallos.append(fila.case_key)

    nuevos_pasan = tuple(
        sorted(
            fila.case_key
            for fila in report.cases
            if fila.case_key not in inestables
            and baseline.case_verdicts.get(fila.case_key) is CaseStatus.FAILED
            and not fallos_efectivos[fila.case_key]
        )
    )

    caidas = _metric_drops(
        report,
        baseline,
        inestables=inestables,
        explicados=explicados,
        blocking_criteria=blocking_criteria,
    )

    razones.extend(
        f"'{caida.criterion}' en '{caida.language}' cayo {caida.delta * 100:.1f} pp "
        "sin explicacion (BR2.3)"
        for caida in caidas
    )

    return GateVerdict(
        compared=True,
        blocked=bool(bloqueos_duros) or bool(fallos_sin_explicar) or bool(caidas),
        blocking_failures=bloqueos_duros,
        unstable_blocking_failures=bloqueos_inestables,
        unexplained_failures=fallos_sin_explicar,
        newly_failed=tuple(sorted(nuevos_fallos)),
        newly_passed=nuevos_pasan,
        explained_regressions=tuple(sorted(set(regresiones_explicadas))),
        unstable_excluded=excluidos,
        metric_drops=caidas,
        judge_not_calibrated=sin_calibrar,
        reasons=tuple(razones),
    )


def _metric_drops(
    report: EvalReport,
    baseline: Baseline,
    *,
    inestables: set[str],
    explicados: set[str],
    blocking_criteria: frozenset[str],
) -> tuple[MetricDrop, ...]:
    """BR2.3: una caida de mas de 2 pp sin explicacion.

    Una caida cuenta como explicada solo cuando **todos** los casos de ese
    criterio e idioma que pasaron de aprobar a fallar estan nombrados en una
    explicacion; sin ningun caso al que atribuirsela tampoco cuenta como
    explicada, porque nadie la nombro (BR2.3, "no hay explicacion que nombre
    los casos afectados"). Un criterio bloqueante queda fuera: un solo fallo ya
    bloquea por su cuenta, sin esperar a que la tasa se mueva 2 pp.
    """
    actuales = criterion_pass_rates(report)
    caidas: list[MetricDrop] = []

    for criterio, por_idioma in sorted(actuales.items()):
        if criterio in blocking_criteria:
            continue
        anteriores = baseline.metrics.get(criterio, {})
        for idioma, tasa_actual in sorted(por_idioma.items()):
            tasa_anterior = anteriores.get(idioma)
            if tasa_anterior is None or tasa_anterior - tasa_actual <= METRIC_DROP_THRESHOLD:
                continue

            contribuyentes = {
                fila.case_key
                for fila in report.cases
                if fila.language == idioma
                and criterio in fila.criteria_results
                and fila.criteria_results[criterio] == "fail"
                and fila.case_key not in inestables
                and baseline.case_verdicts.get(fila.case_key) is CaseStatus.PASSED
            }
            if contribuyentes and contribuyentes <= explicados:
                continue

            caidas.append(
                MetricDrop(
                    criterion=criterio,
                    language=idioma,
                    baseline_rate=tasa_anterior,
                    current_rate=tasa_actual,
                )
            )

    return tuple(caidas)
