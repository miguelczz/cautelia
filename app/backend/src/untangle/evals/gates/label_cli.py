"""El comando `mise run evals:label`: etiquetado humano de DS-7 (F2, FD-U21-3).

Muestra un turno con su criterio, uno a la vez, y guarda el avance despues de
cada respuesta: se puede interrumpir y retomar donde quedo, porque nunca
depende de terminar la cola entera para escribir algo.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import UTC, datetime

from untangle.base import Locale
from untangle.evals.gates import judged_criteria, loading
from untangle.evals.gates.models import HumanLabel, LabelingQueueEntry, LabelVerdict


def _ya_etiquetado(existentes: list[HumanLabel], entrada: LabelingQueueEntry) -> bool:
    return any(
        e.transcript_id == entrada.transcript_id
        and e.turn_index == entrada.turn_index
        and e.criterion == entrada.criterion
        for e in existentes
    )


def label_queue(
    *,
    read_input: Callable[[str], str] = input,
    write_output: Callable[[str], None] = print,
) -> int:
    """Recorre la cola y guarda cada etiqueta apenas se confirma."""
    cola = loading.load_labeling_queue()
    if not cola:
        # No es "ya terminaste": es que todavia no hay nada que etiquetar, y la
        # diferencia cuesta una tarde. Cada entrada de la cola lleva el turno que la
        # agente dijo de verdad (`agent_text`), asi que la cola se arma a partir de una
        # corrida de evaluaciones con conversaciones (`mise run evals:label:queue`). El
        # juez se calibra contra lo que va a juzgar, no contra texto de ejemplo.
        write_output(
            "la cola de etiquetado esta vacia. No es que no haya trabajo: es que "
            "todavia no hay transcripciones que etiquetar.\n"
            "Cada entrada lleva un turno que la agente dijo de verdad. Para armar la "
            "cola: corre una vez 'mise run evals:conversaciones' (llama a Claude, "
            "cuesta centavos) y despues 'mise run evals:label:queue'.\n"
            "Hasta entonces, los criterios que dependen del juez se publican como "
            "'no medida' con esa causa, que es lo correcto."
        )
        return 0

    existentes_por_idioma: dict[Locale, list[HumanLabel]] = {
        idioma: list(loading.load_labels(idioma)) for idioma in ("es", "en")
    }

    for entrada in cola:
        existentes = existentes_por_idioma[entrada.language]
        if _ya_etiquetado(existentes, entrada):
            continue

        write_output(
            f"\n[{entrada.language}] {entrada.transcript_id}#{entrada.turn_index} "
            f"-- {entrada.criterion}"
        )
        pregunta = judged_criteria.question_for(entrada.criterion)
        if pregunta is not None:
            write_output(f"se pregunta: {pregunta}")
        if entrada.context is not None:
            write_output(f"la persona dijo antes: {entrada.context}")
        write_output(f"la agente dijo: {entrada.agent_text}")
        respuesta = read_input("pasa/falla/q para salir> ").strip().lower()

        if respuesta in ("q", "quit", "salir"):
            write_output("etiquetado interrumpido: el avance ya esta guardado")
            break
        if respuesta not in ("pasa", "falla"):
            write_output(f"respuesta '{respuesta}' no reconocida; se salta este turno")
            continue

        etiqueta = HumanLabel(
            transcript_id=entrada.transcript_id,
            turn_index=entrada.turn_index,
            criterion=entrada.criterion,
            language=entrada.language,
            split=entrada.split,
            verdict=LabelVerdict.PASS if respuesta == "pasa" else LabelVerdict.FAIL,
            labeled_at=datetime.now(UTC).date(),
        )
        existentes.append(etiqueta)
        loading.save_labels(entrada.language, tuple(existentes))
        write_output(f"guardado ({len(existentes)} etiquetas en '{entrada.language}')")

    return 0


def main(argv: list[str] | None = None) -> int:
    del argv
    return label_queue()


if __name__ == "__main__":
    sys.exit(main())
