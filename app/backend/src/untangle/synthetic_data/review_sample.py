"""La muestra de diez clausulas por emisora que revisa Miguel (U7, F2, BR5.4, AC5.4.5, AC5.5.6).

`mise run synthetic:sample -- --date AAAA-MM-DD` elige, con la semilla del
generador, diez clausulas **no distractoras** de cada emisora y escribe la muestra
en `app/data/sources/reviews/<aseguradora>-<fecha>.yaml`, **sin veredicto**:
Miguel lee esas diez clausulas y anota el suyo --`own_text_structure_ok` o
`changes_requested`--, la fecha y el commit. La siguiente generacion copia la
muestra al manifiesto tal cual.

**La fecha entra por argumento** y no se lee del reloj: ningun modulo del
generador lee el reloj de pared (BR1.1; lo comprueba `test_fronteras.py`), y la
fecha del nombre del archivo es la de cuando se saco la muestra, que quien la
saca sabe.

**Con la misma semilla y la misma fecha, la misma muestra.** El elegidor sale de
la semilla registrada en el archivo y de la ruta de ese archivo (BR1.2), asi que
cualquiera puede comprobar que las diez no se escogieron a mano. Los
distractores quedan fuera porque lo que se revisa es el texto propio de la
emisora: un distractor es, por diseno, un calco de otra clausula del mismo
corpus.

Las copias de Knotwell no entran: son las mismas clausulas de sus emisoras, y una
agencia no tiene texto propio que revisar (BR4.2).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from untangle.synthetic_data.chooser import ChooserFactory
from untangle.synthetic_data.models import REVIEW_SAMPLE_SIZE, SOURCES_PREFIX, ReviewSample

__all__ = [
    "PURPOSE",
    "ReviewSampleError",
    "SampleCandidate",
    "candidates",
    "draw",
    "render",
    "review_path",
]

#: El flujo del elegidor de la muestra, aparte del de la composicion de ese archivo.
PURPOSE = "review-sample"


class ReviewSampleError(ValueError):
    """La muestra no se pudo sacar. El mensaje nombra la aseguradora o el archivo."""


@dataclass(frozen=True)
class SampleCandidate:
    """Una clausula que puede entrar en la muestra, y donde leerla."""

    clause_id: str
    part: str
    path: str


def candidates(data_dir: Path, tenant_id: str) -> tuple[SampleCandidate, ...]:
    """Las clausulas no distractoras de una emisora, ordenadas por su identificador."""
    elegibles: list[SampleCandidate] = []
    for archivo in sorted((data_dir / "tenants" / tenant_id / "clauses").glob("*.json")):
        try:
            datos: Any = json.loads(archivo.read_text(encoding="utf-8"))
            clausulas = datos["clauses"]
        except (OSError, ValueError, KeyError, TypeError) as error:
            msg = f"no se pudo leer '{archivo}': {type(error).__name__}"
            raise ReviewSampleError(msg) from error
        relativo = f"app/data/tenants/{tenant_id}/clauses/{archivo.name}"
        elegibles.extend(
            SampleCandidate(clause_id=str(c["clause_id"]), part=str(c["part"]), path=relativo)
            for c in clausulas
            if not c.get("is_distractor", False)
        )
    return tuple(sorted(elegibles, key=lambda c: c.clause_id))


def review_path(tenant_id: str, drawn_on: date) -> str:
    """`reviews/<aseguradora>-<fecha>.yaml`, relativo a `app/data/sources/`."""
    return f"reviews/{tenant_id}-{drawn_on.isoformat()}.yaml"


def draw(
    tenant_id: str, drawn_on: date, elegibles: Sequence[SampleCandidate], *, seed: int
) -> ReviewSample:
    """Diez clausulas elegidas con la semilla y la ruta del archivo de la muestra."""
    if len(elegibles) < REVIEW_SAMPLE_SIZE:
        msg = (
            f"'{tenant_id}' tiene {len(elegibles)} clausulas no distractoras y la muestra es "
            f"de {REVIEW_SAMPLE_SIZE}: genere el corpus antes de sacarla"
        )
        raise ReviewSampleError(msg)
    elegidor = ChooserFactory(seed).for_output(
        f"{SOURCES_PREFIX}{review_path(tenant_id, drawn_on)}", purpose=PURPOSE
    )
    elegidas = elegidor.sample([c.clause_id for c in elegibles], REVIEW_SAMPLE_SIZE)
    return ReviewSample(tenant_id=tenant_id, sample_seed=seed, clause_ids=tuple(sorted(elegidas)))


def render(sample: ReviewSample, elegibles: Sequence[SampleCandidate], drawn_on: date) -> str:
    """El archivo de la muestra: los campos del modelo y, en comentarios, donde leer cada una.

    Los comentarios son para quien revisa y el cargador los ignora; el modelo no
    admite campos de mas, asi que la ayuda no puede ir en otro sitio.
    """
    donde = {c.clause_id: c for c in elegibles}
    lineas = [
        f"# Muestra de revision humana de '{sample.tenant_id}', sacada el {drawn_on.isoformat()}",
        "# con `mise run synthetic:sample` (U7, BR5.4, AC5.4.5, AC5.5.6).",
        "#",
        "# Diez clausulas no distractoras, elegidas con la semilla de abajo y la ruta de",
        "# este archivo: la misma semilla y la misma fecha dan las mismas diez.",
        "#",
        "# Para revisarla: lea cada clausula en su archivo (el comentario de cada una",
        "# dice cual) y compruebe que es texto propio con estructura inspirada, sin",
        "# giros reconocibles de un formulario de terceros (P8). Despues anote abajo:",
        "#   verdict: own_text_structure_ok    o    verdict: changes_requested",
        "#   reviewed_on: AAAA-MM-DD            el dia en que la reviso",
        "#   commit: <hash>                     el commit del corpus que leyo",
        "# y corra `mise run synthetic:generate`, que la copia al manifiesto.",
        f"tenant_id: {sample.tenant_id}",
        f"sample_seed: {sample.sample_seed}",
        "clause_ids:",
    ]
    for clave in sample.clause_ids:
        candidata = donde[clave]
        lineas.append(f"  - {clave}  # {candidata.part}, en {candidata.path}")
    lineas += ["reviewed_on: null", "commit: null", "verdict: null"]
    return "\n".join(lineas) + "\n"
