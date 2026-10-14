"""Un modulo de prueba que monta una superficie **sin sonda** (BR5.2, REL-U6.4).

El tipo exige la sonda, asi que este modulo tiene que saltarse el comprobador de
tipos para existir: es exactamente el camino --un valor que llega sin pasar por
los tipos-- que la comprobacion en ejecucion de la raiz tiene que cerrar.
"""

from __future__ import annotations

from untangle.surface_spec import SurfaceId, SurfaceSpec


def surfaces() -> tuple[SurfaceSpec, ...]:
    return (
        SurfaceSpec(
            surface_id=SurfaceId.COMPARISON,
            owning_unit="U17 comparison (modulo de prueba)",
            public=True,
            per_tenant=False,
            # A proposito: una superficie montada sin sonda es lo que se prueba.
            probe=None,  # type: ignore[arg-type]
        ),
    )
