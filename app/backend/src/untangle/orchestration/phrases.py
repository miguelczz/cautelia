"""Las frases fijas del runtime del grafo, no de un nodo (paso 5, BR2.4).

Una sola clave hoy: la frase de espera cuando el ritmo del turno necesita un
resultado del ritmo de fondo que todavia no volvio. Vive en `orchestration/` y
no en `orchestration/nodes/<nodo>/` porque no es de ningun nodo -- es del
runtime que decide que el turno no espera (BR2.2) y que, mientras tanto, dice
algo (BR2.4).

El texto es **literal**, copiado de AC1.25.3: una frase aprobada parafraseada
deja de ser la aprobada (regla del proyecto sobre textos fijos de maquetas y
criterios).
"""

from __future__ import annotations

from untangle.base import Locale
from untangle.copy_catalog import api as copy_api
from untangle.copy_catalog.api import CopyKey

#: AC1.25.3: "Let me check your policy, one moment." / "Déjeme revisar su
#: póliza, un momento." Antes de dos segundos de silencio (BR2.4, PERF-U12.5).
WAITING = CopyKey("orchestration.turn.waiting")


def waiting_text(*, locale: Locale) -> str:
    return copy_api.t(WAITING, locale=locale)


__all__ = ["WAITING", "waiting_text"]
