"""El comando `mise run evals:label:queue`: arma la cola de etiquetado de DS-7.

Lee las transcripciones de una corrida de evaluaciones con conversaciones (las deja
`mise run evals:conversaciones` o `evals:completa` en `tmp/evals/transcripts/`, ya
redactadas) y escribe `app/evals/labels/queue.yaml`, que es lo que lee `mise run
evals:label`. **No llama a ningun modelo y no gasta nada.**

Se puede correr las veces que haga falta: nunca toca lo ya etiquetado ni cambia las
entradas que la cola ya tiene; solo agrega las que faltan para llegar a 20 por idioma.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from untangle import paths
from untangle.evals.gates import judged_criteria, label_queue, loading
from untangle.evals.gates.calibration import CALIBRATION_THRESHOLD
from untangle.evals.loading import LoadError
from untangle.evals.transcripts import (
    TranscriptsFile,
    TranscriptsLoadError,
    latest_path,
    load_transcripts,
    path_for,
)

EXIT_OK = 0
#: La cola se escribio pero un idioma no alcanzo los 20.
EXIT_SHORT = 1
#: No se pudo hacer nada: falta una corrida, o un archivo esta roto.
EXIT_NOTHING = 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="untangle-evals-label-queue",
        description="Arma la cola de etiquetado de DS-7 con una corrida ya hecha.",
    )
    parser.add_argument(
        "--run",
        default=None,
        help="Identificador de la corrida (run-...) o ruta de su archivo. Por omision, la ultima.",
    )
    parser.add_argument(
        "--per-language",
        type=int,
        default=label_queue.DEFAULT_PER_LANGUAGE,
        help="Entradas por idioma en la cola (por omision 20, la cifra de DS-7).",
    )
    parser.add_argument(
        "--seed",
        default=label_queue.DEFAULT_SEED,
        help="Semilla de la eleccion. Misma corrida y misma semilla, misma cola.",
    )
    parser.add_argument(
        "--criteria",
        nargs="+",
        default=list(judged_criteria.DEFAULT_NAMES),
        help="Criterios del juez a etiquetar. Por omision: "
        + ", ".join(judged_criteria.DEFAULT_NAMES),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Cuenta lo que haria sin escribir la cola.",
    )
    return parser


def _find_run(run: str | None, write_error: Callable[[str], None]) -> Path | None:
    if run is None:
        encontrada = latest_path()
        if encontrada is None:
            write_error(
                f"no hay ninguna corrida con conversaciones guardada en '{paths.transcripts_dir()}'.\n"
                "Las transcripciones las deja una corrida con conversaciones: corre antes "
                "'mise run evals:conversaciones' (llama a Claude y cuesta centavos) o "
                "'mise run evals:completa', y despues vuelve a correr este comando. Las "
                "corridas hechas antes de que existiera este comando no guardaron lo que "
                "dijo la agente y no sirven."
            )
        return encontrada

    candidata = Path(run)
    if candidata.is_file():
        return candidata
    por_id = path_for(run.removesuffix(".json"))
    if por_id.is_file():
        return por_id
    write_error(
        f"no encuentro la corrida '{run}': ni como ruta ni como '{por_id}'. "
        "Sin --run, el comando toma la ultima."
    )
    return None


def _describe_run(file: TranscriptsFile, write_output: Callable[[str], None]) -> None:
    por_idioma = {
        idioma: sum(1 for c in file.conversations if c.language == idioma)
        for idioma in label_queue.LANGUAGES
    }
    write_output(
        f"corrida {file.run_id} (commit {file.commit_sha[:12]}): "
        f"{len(file.conversations)} conversaciones guardadas "
        f"(es {por_idioma['es']}, en {por_idioma['en']})"
    )
    if file.not_saved:
        casos = ", ".join(f"{n.case_key} ({n.reason})" for n in file.not_saved)
        write_output(f"  no se guardaron, por eso no entran: {casos}")


def _describe_plan(
    plan: label_queue.QueuePlan, per_language: int, write_output: Callable[[str], None]
) -> None:
    write_output(f"entradas nuevas: {len(plan.new_entries)}")
    for estadistica in plan.stats:
        agregadas = estadistica.added_flagged + estadistica.added_clean
        write_output(
            f"  [{estadistica.language}] {estadistica.criterion}: {estadistica.already} ya estaban, "
            f"{agregadas} nuevas ({estadistica.added_flagged} que el codigo marco como dudosas, "
            f"{estadistica.added_clean} limpias); {estadistica.test_total} quedan en la "
            "particion de prueba"
        )
        if estadistica.flagged_in_run == 0:
            write_output(
                f"      ojo: en esta corrida el codigo no marco ningun turno como dudoso para "
                f"'{estadistica.criterion}' en '{estadistica.language}'. Todas las entradas de ese "
                "criterio son limpias: un fallo, si lo hay, solo aparece al leerlas."
            )
    if plan.unsignaled_conversations:
        write_output(
            f"  {plan.unsignaled_conversations} conversaciones no entran porque la corrida no "
            "pudo leer las senales del codigo y no se pueden repartir entre dudosas y limpias."
        )
    for idioma, falta in plan.shortfall.items():
        if falta > 0:
            write_output(
                f"FALTAN {falta} en '{idioma}': la corrida solo trae {plan.eligible[idioma]} turnos "
                f"de la agente sin usar en ese idioma y se pidieron {per_language}. No se rellena "
                "con otro idioma ni con texto de ejemplo; hace falta otra corrida con mas "
                "conversaciones."
            )


def _describe_calibration_math(
    plan: label_queue.QueuePlan, write_output: Callable[[str], None]
) -> None:
    minimo = label_queue.min_labels_per_class()
    en_prueba = [s.test_total for s in plan.stats]
    peor, mejor = min(en_prueba, default=0), max(en_prueba, default=0)
    cuantas = f"{peor}" if peor == mejor else f"entre {peor} y {mejor}"
    if peor < 2 * minimo:
        conclusion = (
            "asi que sirve para ver como se comporta el juez, pero no alcanza para encenderlo"
        )
    else:
        conclusion = (
            f"que alcanza solo si en cada criterio e idioma al menos {minimo} salen 'pasa' y "
            f"{minimo} 'falla'"
        )
    write_output(
        f"\nAviso sobre la calibracion: para que un criterio cuente en un idioma, la particion "
        f"de prueba necesita al menos {minimo} etiquetas 'pasa' y {minimo} 'falla' de ese "
        f"criterio y ese idioma: con menos, el limite inferior de Wilson no llega al umbral "
        f"de {CALIBRATION_THRESHOLD:.2f} ni con un juez perfecto. Esta cola deja {cuantas} en "
        f"prueba por criterio e idioma, {conclusion}. El umbral no se toca; lo que se decide "
        "es cuantas etiquetas mas se ponen (--per-language)."
    )


def build_queue(
    argv: list[str] | None = None,
    *,
    write_output: Callable[[str], None] = print,
    write_error: Callable[[str], None] = lambda m: print(m, file=sys.stderr),
) -> int:
    args = _parser().parse_args(argv)

    desconocidos = [c for c in args.criteria if judged_criteria.by_name(c) is None]
    if desconocidos:
        write_error(
            f"criterio desconocido: {', '.join(desconocidos)}. Los declarados son: "
            f"{', '.join(judged_criteria.DEFAULT_NAMES)}."
        )
        return EXIT_NOTHING
    if args.per_language < 1:
        write_error("--per-language tiene que ser al menos 1.")
        return EXIT_NOTHING

    archivo = _find_run(args.run, write_error)
    if archivo is None:
        return EXIT_NOTHING

    try:
        corrida = load_transcripts(archivo)
        cola = loading.load_labeling_queue()
        etiquetas = loading.load_labels("es") + loading.load_labels("en")
    except (TranscriptsLoadError, LoadError) as error:
        # Un archivo roto se nombra y no se pisa: la cola y las etiquetas son trabajo de Miguel.
        write_error(str(error))
        return EXIT_NOTHING

    _describe_run(corrida, write_output)
    plan = label_queue.plan_queue(
        corrida,
        existing=label_queue.Existing(queue=cola, labels=etiquetas),
        per_language=args.per_language,
        criteria=tuple(args.criteria),
        seed=args.seed,
    )
    _describe_plan(plan, args.per_language, write_output)

    if plan.new_entries and not args.dry_run:
        escrito = loading.save_labeling_queue(label_queue.merge(cola, plan.new_entries))
        write_output(f"\ncola escrita: {escrito} ({len(cola) + len(plan.new_entries)} entradas)")
        write_output("siguiente paso: mise run evals:label")
    elif args.dry_run:
        write_output("\n--dry-run: no se escribio nada")
    else:
        write_output("\nla cola ya tiene lo pedido: no hay nada que agregar")

    _describe_calibration_math(plan, write_output)
    return EXIT_SHORT if any(falta > 0 for falta in plan.shortfall.values()) else EXIT_OK


def main(argv: list[str] | None = None) -> int:
    return build_queue(argv)


if __name__ == "__main__":
    sys.exit(main())
