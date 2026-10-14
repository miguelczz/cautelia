"""Un modulo de prueba que monta **otra vez** el chat (F8).

Dos modulos que montan la misma superficie dejarian al inicio y a la salud sin
saber de quien es cada boton y cada sonda; la raiz se niega a arrancar.
"""

from __future__ import annotations

from untangle.surface_spec import SurfaceId, SurfaceProbe, SurfaceSpec


async def _responde() -> None:
    return None


def surfaces() -> tuple[SurfaceSpec, ...]:
    return (
        SurfaceSpec(
            surface_id=SurfaceId.CHAT,
            owning_unit="U99 (modulo de prueba repetido)",
            public=True,
            per_tenant=True,
            probe=SurfaceProbe(check=_responde, timeout_ms=100),
        ),
    )
