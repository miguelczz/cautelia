"""El comando `mise run evals:baseline`: publica una linea base por hito (F5, BR2.1).

Siempre corre la corrida completa, nunca un subconjunto (F5, "no un
subconjunto"): no acepta `--subset` a proposito. Por eso es tambien quien escribe
el resumen de la ultima corrida completa (U22, BR4.3).

**Con `--report` no corre nada: publica el reporte de una corrida completa que ya se hizo.**
Es la forma de llevar a la linea base lo que solo mide la corrida que conversa con el modelo
--las conversaciones del chat y, con ellas, su latencia--: `mise run evals:completa` es la unica
que arma la aplicacion con el modelo y deja su reporte en `tmp/evals/reports/`, y este comando
sin `--report` no la arma. Publicar desde ese reporte no gasta: ya se gasto al correrla. Las
tres condiciones de BR2.1 se aplican igual (comparable, completa, en verde) y no se escribe un
resumen nuevo, porque `evals:completa` ya dejo el suyo.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from pydantic import ValidationError

from untangle import paths
from untangle.evals.cli import register_all_probes
from untangle.evals.gates.baseline import BaselinePublicationError, build_digest, publish
from untangle.evals.gates.gate import blocking_criteria_from_registry
from untangle.evals.gates.loading import save_last_run_digest
from untangle.evals.loading import LoadError
from untangle.evals.report import EvalReport
from untangle.evals.runner import runner
from untangle.settings import Settings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="untangle-evals-baseline",
        description="Corre la corrida completa y la publica como linea base vigente.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help=(
            "No corre nada: publica el reporte de una corrida completa ya hecha, por ejemplo "
            "el de `mise run evals:completa` (tmp/evals/reports/<corrida>.json)."
        ),
    )
    return parser


def _publicar_un_reporte(archivo: Path) -> int:
    """Publica el reporte de una corrida que ya se hizo, con las condiciones de siempre."""
    try:
        reporte = EvalReport.model_validate_json(archivo.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as error:
        print(f"no se pudo leer el reporte '{archivo}': {error}", file=sys.stderr)
        return 2

    try:
        baseline, propia, vigente = publish(reporte)
    except BaselinePublicationError as error:
        print(str(error), file=sys.stderr)
        return 1

    print(f"linea base publicada: {baseline.baseline_id} (del reporte {archivo})")
    print(f"  {propia}")
    print(f"  {vigente}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.report is not None:
        return _publicar_un_reporte(args.report)

    register_all_probes()

    try:
        resultado = asyncio.run(runner.run_evaluation(subset=None, settings=Settings()))
    except runner.EnvironmentNotReadyError as error:
        print(str(error), file=sys.stderr)
        return 2
    except LoadError as error:
        print(str(error), file=sys.stderr)
        return 2

    # Antes de decidir si se publica, y sea cual sea la decision: la corrida en rojo
    # es justo la que "Como falla" necesita contar (BR4.3).
    resumen = save_last_run_digest(
        build_digest(
            resultado.report,
            blocking_criteria=blocking_criteria_from_registry(),
            dirty_tree=runner.tree_is_dirty(paths.repo_root()),
        )
    )
    print(f"resumen de la ultima corrida completa: {resumen}")

    try:
        baseline, propia, vigente = publish(resultado.report)
    except BaselinePublicationError as error:
        print(str(error), file=sys.stderr)
        return 1

    print(f"linea base publicada: {baseline.baseline_id}")
    print(f"  {propia}")
    print(f"  {vigente}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
