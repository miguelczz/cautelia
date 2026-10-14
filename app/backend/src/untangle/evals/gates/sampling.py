"""La muestra para revision humana: reproducible, sin `random` (BR3.4).

Mismo mecanismo que el generador sintetico (U7): se elige con SHA-256 sobre la
semilla y el identificador, nunca con el modulo `random`, que la regla del
equipo prohibe fuera de la semilla.
"""

from __future__ import annotations

import hashlib


def _score(seed: str, case_key: str) -> int:
    digest = hashlib.sha256(f"{seed}:{case_key}".encode()).hexdigest()
    return int(digest, 16)


def review_sample(
    case_keys: tuple[str, ...],
    *,
    judge_failures: frozenset[str] = frozenset(),
    seed: str,
    fraction: float = 0.2,
) -> tuple[str, ...]:
    """El 20 % elegido con la semilla, mas todos los fallos del juez (BR3.4).

    Reproducible: la misma semilla y los mismos casos siempre eligen el mismo
    20 %, en cualquier maquina.
    """
    tamano = round(len(case_keys) * fraction)
    ordenados = sorted(case_keys, key=lambda clave: _score(seed, clave))
    elegidos = set(ordenados[:tamano]) | set(judge_failures)
    return tuple(sorted(elegidos))
