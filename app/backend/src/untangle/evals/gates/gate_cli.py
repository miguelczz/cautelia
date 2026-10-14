"""El comando `mise run evals:gate`: corre, compara y decide (F1, F4, BR5.1).

Compone el mismo corredor que `untangle.evals.cli` (`register_all_probes`) y le
suma la memoria entre corridas: sin esta unidad, el comando de U1 corria las
evaluaciones pero nadie comparaba el resultado contra nada.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from untangle import paths
from untangle.evals.cli import register_all_probes, write_report
from untangle.evals.gates import loading as gates_loading
from untangle.evals.gates.gate import GateOutcome, run_gate
from untangle.evals.loading import LoadError
from untangle.evals.runner import runner
from untangle.settings import Settings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="untangle-evals-gate",
        description="Corre las evaluaciones y decide si la entrega pasa (BR5.1).",
    )
    parser.add_argument(
        "--subset",
        default=None,
        help="Nombre del subconjunto declarado (por ejemplo `smoke`).",
    )
    parser.add_argument(
        "--out",
        default=None,
        type=Path,
        help="Donde escribir el reporte. Por defecto, tmp/evals/reports/.",
    )
    parser.add_argument(
        "--audit-path",
        action="append",
        default=[],
        type=Path,
        dest="audit_paths",
        help=(
            "Traza exportada, log o exportacion que revisa el segundo detector "
            "(BR4.2). Repetible; ausente hoy mientras no exista una tuberia que "
            "las produzca."
        ),
    )
    parser.add_argument(
        "--judge-model",
        default=None,
        help="Identificador exacto del modelo del juez, para leer su calibracion (BR3.2).",
    )
    parser.add_argument(
        "--rubric-version",
        default=None,
        help="Version de la rubrica del juez, junto con --judge-model.",
    )
    return parser


def _resumen(outcome: GateOutcome) -> str:
    """Que paso a fallar, que paso a pasar, y por que bloquea o no (F1 paso 5)."""
    veredicto = outcome.verdict
    lineas: list[str] = []

    if not veredicto.compared:
        lineas.append("sin linea base vigente: esta corrida no compara (FD-U21-5)")
    if veredicto.unstable_excluded:
        lineas.append(
            f"inestables, fuera de la compuerta: {', '.join(veredicto.unstable_excluded)}"
        )
    # Un fallo bloqueante en un caso inestable no cuenta para la compuerta,
    # pero nunca queda en silencio: su propia linea, siempre (item 4 de la
    # correccion del 2026-09-25).
    if veredicto.unstable_blocking_failures:
        lineas.append(
            "ATENCION: inestables con un criterio bloqueante en rojo (no cuentan para la "
            f"compuerta, pero necesitan revision): {', '.join(veredicto.unstable_blocking_failures)}"
        )
    if veredicto.newly_passed:
        lineas.append(f"pasaron a pasar: {', '.join(veredicto.newly_passed)}")
    if veredicto.explained_regressions:
        lineas.append(f"regresiones explicadas: {', '.join(veredicto.explained_regressions)}")
    if veredicto.judge_not_calibrated:
        lineas.append(
            f"juez sin calibrar, no medida (BR3.2): {', '.join(veredicto.judge_not_calibrated)}"
        )
    if veredicto.pii_findings:
        # Por idioma y por tipo de entidad, nunca como promedio (BR4.2).
        for hallazgo in veredicto.pii_findings:
            lineas.append(
                f"segundo detector: '{hallazgo.source}' idioma={hallazgo.language} "
                f"tipo={hallazgo.entity_type.value}"
            )

    if veredicto.blocked:
        lineas.append("COMPUERTA EN ROJO:")
        lineas.extend(f"  - {razon}" for razon in veredicto.reasons)
    else:
        lineas.append("compuerta en verde")

    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    register_all_probes()

    try:
        resultado = asyncio.run(runner.run_evaluation(subset=args.subset, settings=Settings()))
    except runner.EnvironmentNotReadyError as error:
        print(str(error), file=sys.stderr)
        return 2
    except LoadError as error:
        print(str(error), file=sys.stderr)
        return 2

    calibracion = None
    if args.judge_model and args.rubric_version:
        calibracion = gates_loading.load_calibration(args.judge_model, args.rubric_version)

    outcome = run_gate(resultado.report, audit_paths=args.audit_paths, calibration=calibracion)

    destino = args.out or (paths.reports_dir() / f"{resultado.run.run_id}-gate.json")
    write_report(outcome.report, destino)

    print(_resumen(outcome))
    print(f"reporte: {destino}")
    return outcome.exit_code


if __name__ == "__main__":
    sys.exit(main())
