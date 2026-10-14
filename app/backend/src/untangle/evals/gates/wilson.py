"""El intervalo de Wilson, escrito a mano (TECH-U21.1, sin `scipy`).

Se comporta mejor que la aproximacion normal con `n` pequeno, que es el tamano
de DS-7 por idioma (unas diez etiquetas por criterio): la aproximacion normal
puede dar un limite por debajo de 0 o por encima de 1, y Wilson no.
"""

from __future__ import annotations

import math

#: El 97.5 percentil de la normal estandar, para un intervalo de dos colas al
#: 95 % (FD-U21-4).
Z_95 = 1.959963985


def wilson_lower_bound(successes: int, n: int, *, z: float = Z_95) -> float:
    """El limite inferior del intervalo de Wilson para `successes` de `n`.

    Exigir el limite inferior y no la proporcion observada es la decision
    FD-U21-4: una muestra pequena y afortunada (por ejemplo 4 de 4) no habilita
    al juez solo porque la media sale en 1.0.
    """
    if n <= 0:
        msg = f"el intervalo de Wilson necesita al menos una observacion, y n={n}"
        raise ValueError(msg)
    if not 0 <= successes <= n:
        msg = f"successes={successes} tiene que estar entre 0 y n={n}"
        raise ValueError(msg)

    p_hat = successes / n
    z2 = z * z
    denominador = 1 + z2 / n
    centro = (p_hat + z2 / (2 * n)) / denominador
    margen = (z * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n))) / denominador
    return max(0.0, centro - margen)
