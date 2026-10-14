"""El registro de superficies montadas y sus sondas (U6, F7, F8, BR5.2, BR5.3).

La raiz de composicion junta aqui las superficies que declaran los modulos con
la capacidad `surfaces` (CG-U6-7). Desde ese momento:

- el inicio muestra solo las **publicas y montadas** (BR4.1), por el directorio
  del sitio;
- la salud de listo corre la sonda de **cada montada** y ninguna mas (BR5.3).

Montar una superficie no toca ningun archivo de U6 (SCALE-U6.1): basta con que
su modulo este en `MODULOS` y exponga `surfaces()`.

## Las sondas corren en paralelo, cada una con su tiempo maximo

La salud tarda lo que la sonda mas lenta y no la suma de todas (SCALE-U6.3). Una
sonda que levanta o que se pasa de su tiempo marca su superficie `down`; nunca
se escribe `ok` por no saber (convencion 8c del equipo), y una caida deja su
evento con la superficie y la duracion. Una sonda caida **no** vuelve no apto al
proceso: el chequeo periodico tiene que distinguir "no despierta" de "el chat
esta caido" (NFR16.2).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from untangle import observability
from untangle.surface_spec import SurfaceId, SurfaceProbe, SurfaceSpec

type ProbeStatus = Literal["ok", "down"]


class SurfaceDeclarationError(ValueError):
    """Un modulo declaro superficies que no cumplen el contrato (BR5.2).

    La raiz la envuelve en su propio error de contrato, que nombra el modulo.
    """


@dataclass(frozen=True)
class ProbeResult:
    """Lo que devolvio una sonda en un reporte de salud."""

    status: ProbeStatus
    duration_ms: int


def validate_declared(declared: object) -> tuple[SurfaceSpec, ...]:
    """Comprueba lo que devolvio `surfaces()` de un modulo, antes de arrancar.

    Cada elemento tiene que ser un `SurfaceSpec` **con su sonda**. Una superficie
    sin sonda impide arrancar: descubrirlo en el chequeo periodico seria
    descubrirlo en produccion, con la superficie ya publicada (BR5.2).
    """
    if isinstance(declared, (str, bytes)) or not isinstance(declared, Iterable):
        msg = "surfaces() tiene que devolver una secuencia de SurfaceSpec"
        raise SurfaceDeclarationError(msg)

    validas: list[SurfaceSpec] = []
    for elemento in declared:
        if not isinstance(elemento, SurfaceSpec):
            msg = f"surfaces() devolvio {type(elemento).__name__} y no un SurfaceSpec"
            raise SurfaceDeclarationError(msg)
        # El tipo ya exige la sonda; esto la exige tambien en ejecucion, porque
        # un `None` que llegue por un camino sin comprobar de tipos no puede
        # dejar arrancar una superficie publicada sin comprobacion.
        sonda: object = elemento.probe
        if not isinstance(sonda, SurfaceProbe):
            msg = (
                f"la superficie '{elemento.surface_id}' se monta sin sonda; toda "
                "superficie montada declara una sonda barata (BR5.2)"
            )
            raise SurfaceDeclarationError(msg)
        validas.append(elemento)
    return tuple(validas)


class SurfaceRegistry:
    """Las superficies montadas en este proceso, en el orden de la lista cerrada."""

    def __init__(self, specs: Sequence[SurfaceSpec] = ()) -> None:
        vistas: set[SurfaceId] = set()
        for spec in specs:
            if spec.surface_id in vistas:
                msg = f"la superficie '{spec.surface_id}' esta montada dos veces"
                raise SurfaceDeclarationError(msg)
            vistas.add(spec.surface_id)
        orden = list(SurfaceId)
        self._specs = tuple(sorted(specs, key=lambda s: orden.index(s.surface_id)))

    @property
    def specs(self) -> tuple[SurfaceSpec, ...]:
        return self._specs

    def mounted(self) -> tuple[SurfaceId, ...]:
        return tuple(spec.surface_id for spec in self._specs)

    def public_mounted(self) -> tuple[SurfaceId, ...]:
        """Las que un visitante puede ver: lo unico que el inicio muestra (BR4.1)."""
        return tuple(spec.surface_id for spec in self._specs if spec.public)

    async def probe_all(self) -> dict[SurfaceId, ProbeResult]:
        """Corre todas las sondas **en paralelo**, cada una con su tiempo maximo."""
        resultados = await asyncio.gather(*(_probe(spec) for spec in self._specs))
        return dict(zip(self.mounted(), resultados, strict=True))


async def _probe(spec: SurfaceSpec) -> ProbeResult:
    """Una sonda, acotada por su tiempo. Nunca levanta: el fallo es `down`."""
    inicio = time.perf_counter()
    motivo: str | None = None
    tipo: str | None = None
    try:
        async with asyncio.timeout(spec.probe.timeout_ms / 1000):
            await spec.probe.check()
    except TimeoutError:
        motivo = "timeout"
    except Exception as error:  # noqa: BLE001 -- una sonda rota es una superficie caida, no una salud rota
        motivo = "error"
        tipo = type(error).__name__

    duracion = round((time.perf_counter() - inicio) * 1000)
    if motivo is None:
        return ProbeResult(status="ok", duration_ms=duracion)

    # Deja rastro: una superficie caida es lo que el chequeo periodico tiene que
    # poder mirar, con la superficie, la duracion y el motivo (OBS-U6.1).
    observability.emit(
        "server.surface_down",
        surface=spec.surface_id.value,
        owning_unit=spec.owning_unit,
        duration_ms=duracion,
        reason=motivo,
        error_type=tipo,
    )
    return ProbeResult(status="down", duration_ms=duracion)
