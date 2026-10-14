"""El panel de cifras: `GET /api/metrics`, sin credencial (U22, BR2.1, SEC-U22.1).

Sirve la vista de lectura de la linea base vigente y **nada mas**. No consulta la
base de datos, no llama a ningun proveedor y no gasta: lee un archivo versionado.

La respuesta es el modelo `MetricsSnapshot` entero y ese modelo no tiene ningun
campo capaz de cargar un identificador de caso ni un dato de un visitante. Eso es
lo que hace verdadera la regla `[bloquea]` del panel publico: no se promete en
la ruta, se impide en el tipo de la respuesta.

**Por que vive en `untangle.server` y no junto a las cifras.** `untangle.evals` no
puede importar el framework web, y el codigo de produccion no puede importar
`untangle.evals` salvo la arista que el contrato de importacion nombra: esta. Es
el mismo arreglo que `voice_cli`, y por la misma razon: la ruta necesita leer la
linea base, que es del corredor de evaluaciones.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter

from untangle.evals.evidence import api as evidence
from untangle.server.problems import problem_responses
from untangle.surface_spec import SurfaceId, SurfaceProbe, SurfaceSpec

#: Leer y validar un archivo pequeno. Es el plazo de la sonda, no de la ruta.
PROBE_TIMEOUT_MS = 200


def router() -> APIRouter:
    enrutador = APIRouter(prefix="/api", tags=["metrics"])

    @enrutador.get(
        "/metrics",
        response_model=evidence.MetricsSnapshot,
        operation_id="getMetrics",
        responses=problem_responses(),
    )
    def metrics() -> evidence.MetricsSnapshot:
        return evidence.current_snapshot()

    @enrutador.get(
        "/quality",
        operation_id="getQualityBoard",
        responses=problem_responses(),
    )
    def quality() -> evidence.QualityBoard | None:
        """La ultima corrida completa de evaluacion, como salio (2026-10-11).

        `200` con `null` cuando todavia no se ha guardado ninguna: no es un error
        de quien pregunta. Publica, como el panel de cifras: son resultados del
        conjunto de prueba versionado, no casos de visitantes.
        """
        return evidence.current_board()

    return enrutador


def empty_example() -> evidence.MetricsSnapshot:
    """El panel sin linea base publicada: el ejemplo que escribe `contracts:gen`."""
    return evidence.build_snapshot(None)


async def _sonda() -> None:
    """Que el panel se puede armar: lee la linea base vigente. No toca proveedores."""
    await asyncio.to_thread(evidence.current_snapshot)


def surfaces() -> tuple[SurfaceSpec, ...]:
    """El panel de cifras: publico y unico (no hay uno por aseguradora)."""
    return (
        SurfaceSpec(
            surface_id=SurfaceId.METRICS_PANEL,
            owning_unit="u22-public-evidence",
            public=True,
            per_tenant=False,
            probe=SurfaceProbe(check=_sonda, timeout_ms=PROBE_TIMEOUT_MS),
        ),
    )
