"""Un modulo de prueba que monta dos superficies con su sonda (F8, SCALE-U6.1).

Hace lo mismo que hara cada unidad con pantallas: exponer `surfaces()` y nada
mas. Que su chat aparezca en el inicio y en la salud **sin tocar ningun archivo
de U6** es lo que prueba montarlo.

Sus sondas no llaman a nada: una sonda de verdad es asi de barata (BR5.2).
"""

from __future__ import annotations

from untangle.surface_spec import SurfaceId, SurfaceProbe, SurfaceSpec


async def _responde() -> None:
    return None


def surfaces() -> tuple[SurfaceSpec, ...]:
    return (
        SurfaceSpec(
            surface_id=SurfaceId.CHAT,
            owning_unit="U13 chat (modulo de prueba)",
            public=True,
            per_tenant=True,
            probe=SurfaceProbe(check=_responde, timeout_ms=100),
        ),
        # La bandeja con credencial no es publica: la salud la sondea, el inicio
        # no la muestra (BR4.1).
        SurfaceSpec(
            surface_id=SurfaceId.INBOX,
            owning_unit="U14 inbox (modulo de prueba)",
            public=False,
            per_tenant=True,
            probe=SurfaceProbe(check=_responde, timeout_ms=100),
        ),
    )
