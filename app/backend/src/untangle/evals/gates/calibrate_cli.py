"""El comando `mise run evals:calibrate`: TPR y TNR contra DS-7 (F2, BR3.1 a BR3.4).

Lee las etiquetas humanas y los veredictos grabados del juez -- nunca llama al
juez de verdad -- y publica la calibracion de esa combinacion exacta de modelo
y version de rubrica. Sin veredictos grabados no hay nada que calcular: esa
corrida real necesita la clave del proveedor y vive en la sesion local
(CG-U21-4).
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

from pydantic import ValidationError

from untangle.evals.gates import loading
from untangle.evals.gates.calibration import CALIBRATION_THRESHOLD, build_calibration, is_calibrated


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="untangle-evals-calibrate",
        description="Calibra al juez contra las etiquetas humanas de DS-7 (BR3.1).",
    )
    parser.add_argument(
        "--judge-model", required=True, help="Identificador exacto del modelo del juez."
    )
    parser.add_argument("--rubric-version", required=True, help="Version de la rubrica.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    etiquetas = loading.load_labels("es") + loading.load_labels("en")
    if not etiquetas:
        print("no hay etiquetas humanas de DS-7 todavia: nada que calibrar", file=sys.stderr)
        return 2

    veredictos = loading.load_judge_verdicts(args.judge_model, args.rubric_version)
    if not veredictos:
        print(
            f"no hay veredictos grabados del juez para '{args.judge_model}' / "
            f"'{args.rubric_version}'",
            file=sys.stderr,
        )
        return 2

    try:
        calibracion = build_calibration(
            judge_model=args.judge_model,
            rubric_version=args.rubric_version,
            labels=etiquetas,
            verdicts=veredictos,
            measured_at=datetime.now(UTC),
        )
    except ValidationError:
        print(
            "ningun criterio tuvo etiquetas de las dos clases (pasa y falla) en la "
            "particion de prueba: no se publica una calibracion vacia",
            file=sys.stderr,
        )
        return 2

    archivo = loading.save_calibration(calibracion)
    print(f"calibracion publicada: {archivo}")
    for tasa in calibracion.rates:
        estado = "CUENTA" if is_calibrated(tasa) else "no medida"
        print(
            f"  {tasa.criterion} [{tasa.language}] n={tasa.n} "
            f"tpr={tasa.tpr:.2f} (limite {tasa.ci_low_tpr:.2f}) "
            f"tnr={tasa.tnr:.2f} (limite {tasa.ci_low_tnr:.2f}) "
            f"umbral={CALIBRATION_THRESHOLD:.2f} -> {estado}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
