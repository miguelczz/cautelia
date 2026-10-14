"""Lo cronometrado del paso 5: PERF-U12.2, PERF-U12.3 y PERF-U12.4.

Los umbrales son los de `nfr-requirements/performance-requirements.md`: el trabajo
de estas pruebas no es certificar una milesima, es fallar el dia que uno de los
controles deje de ser barato (una consulta a la base, una lectura de archivo, una
llamada de red). Un umbral pegado a la medicion falla por el ruido de la maquina.

**El margen se cuenta contra la maquina mas lenta que corre la compuerta, que es
la de GitHub Actions y no esta.** Es la correccion del 2026-10-03, y la escribio un
`main` en rojo: PERF-U12.2 se habia fijado con diez veces de margen sobre los
0,098 ms medidos aqui el 2026-09-27, y en el flujo midio 1,0507 ms --que es la
misma naturaleza de control sobre un procesador compartido y entre seis y diez
veces mas lento--. Un umbral calibrado en una maquina y comprobado en otra no mide
el control: mide cual de las dos toco. El procedimiento estaba escrito en la
suposicion aprobada de `performance-requirements.md` --"lo que se ajusta es el
umbral con su medicion escrita al lado, nunca el control"-- y es lo que se hizo.

Se mide con `time.perf_counter()` sobre un **unico** bucle de eventos reutilizado
(`loop.run_until_complete`, nunca `asyncio.run` dentro del tramo medido: crear y
cerrar un bucle nuevo en cada muestra cuesta, en algunas plataformas, mas que el
propio control que se quiere medir, y contaminaria justo el umbral mas ajustado
de los tres). El reloj es tiempo real, no el reloj inyectado de `executor.py`,
que es para el registro de `NodeRun` y no para cronometrar nada. El p95 se
publica con `print` en la salida de la prueba (`mise run test:u12`).
"""

from __future__ import annotations

import asyncio
import statistics
import time
from collections.abc import Callable, Coroutine, Iterator
from datetime import date
from typing import Any

import pytest

from untangle.base import ProviderName, SpendSource, Use
from untangle.case_record.models import CaseState, Completeness, RecordType
from untangle.compliance.controls import api as controls
from untangle.compliance.controls import patterns
from untangle.copy_catalog import api as copy_api
from untangle.orchestration import graph
from untangle.orchestration.nodes.intake.extraction import ExtractedItem, ExtractionResponse
from untangle.orchestration.nodes.intake.node import IntakeNode, IntakeNodeInput
from untangle.providers.ports import (
    GenerationResult,
    InstructionText,
    PromptRef,
    SystemInstruction,
    UsageReport,
)
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import TenantConfig

_MUESTRAS = 200


@pytest.fixture(autouse=True)
def _estado_limpio() -> Iterator[None]:
    """Mismo patron que `tests/unit/compliance/conftest.py`: nada persiste entre pruebas."""
    copy_api.reset()
    patterns.reset()
    tenancy_config.reset()
    yield
    copy_api.reset()
    patterns.reset()
    tenancy_config.reset()


@pytest.fixture(name="aseguradoras")
def _aseguradoras() -> tuple[TenantConfig, ...]:
    """Las aseguradoras de la configuracion real, sin escribir ningun identificador."""
    return tuple(sorted(tenancy_config.load().available, key=lambda t: t.tenant_id))


def _p95(muestras: list[float]) -> float:
    ordenadas = sorted(muestras)
    indice = max(0, int(len(ordenadas) * 0.95) - 1)
    return ordenadas[indice]


def _cronometrar_async(
    factory: Callable[[], Coroutine[Any, Any, object]], *, veces: int = _MUESTRAS
) -> list[float]:
    """El p95 de `veces` corridas de la corrutina que `factory` produce cada vez.

    Un unico bucle de eventos para toda la medicion (ver el docstring del
    modulo). La primera corrida, fuera del cronometro, paga la carga perezosa
    del catalogo, los patrones y la configuracion de aseguradoras -- costos de
    arranque de proceso, no del control que se mide.
    """
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(factory())
        muestras: list[float] = []
        for _ in range(veces):
            inicio = time.perf_counter()
            loop.run_until_complete(factory())
            muestras.append(time.perf_counter() - inicio)
        return muestras
    finally:
        loop.close()


# --- PERF-U12.2: los tres controles del turno, sumados -------------------------


def test_perf_u12_2_los_tres_controles_del_turno(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    """`read_turn_signals` (dos de las tres) mas `guard_output` (la guardia), p95 <= 10 ms.

    **Diez milisegundos y no uno** (2026-10-03). Las dos mediciones que lo fijan:
    0,17 ms en la maquina de desarrollo y 1,05 ms en el flujo de GitHub Actions,
    que es donde corre la compuerta. Diez veces la segunda sigue siendo el 1,25 %
    del presupuesto de 800 ms del turno, y sigue cayendo el dia que uno de estos
    controles gane una consulta, un archivo o una llamada de red: las tres cuestan
    milisegundos o decenas, no decimas.
    """
    texto = "me chocaron por detrás en la autopista, ¿está cubierto mi carro?"
    tenant_id = aseguradoras[0].tenant_id

    async def _controles() -> None:
        await controls.read_turn_signals(texto)
        await controls.guard_output(texto, tenant_id=tenant_id, language="es")

    muestras_ms = [s * 1000 for s in _cronometrar_async(_controles)]
    p95 = _p95(muestras_ms)
    print(f"PERF-U12.2: p50={statistics.median(muestras_ms):.4f} ms p95={p95:.4f} ms")

    assert p95 <= 10.0, f"los tres controles del turno midieron p95={p95:.4f} ms (umbral 10 ms)"


# --- PERF-U12.3: el trabajo propio del nodo del turno, sin proveedor -----------

_CAMPOS = (
    "identity_and_policy",
    "incident_datetime",
    "location",
    "description",
    "vehicle_and_driver",
    "other_parties",
    "injuries",
)


def _completitud(*completos: str) -> Completeness:
    por_campo = {c: c in completos for c in _CAMPOS}
    return Completeness(per_field=por_campo, complete=sum(por_campo.values()), total=len(_CAMPOS))


class _ExtractorInstantaneo:
    """El unico proveedor que este nodo llamaria -- sustituido, para medir sin el (CG-U12-3)."""

    async def __call__(self, _prompt: object) -> GenerationResult:
        return GenerationResult(
            text=None,
            parsed=ExtractionResponse(
                items=(ExtractedItem(field_key="location", value="la autopista"),)
            ),
            usage=UsageReport(
                provider=ProviderName.GEMINI,
                model="gemini-2.5-flash",
                use=Use.CHAT,
                source=SpendSource.PROVIDER_REPORTED,
            ),
            prompt=PromptRef(prompt_id="intake", locale="es", sha256="a" * 64),
        )


def _instruccion(_language: str) -> SystemInstruction:
    return SystemInstruction(
        ref=PromptRef(prompt_id="intake", locale="es", sha256="a" * 64),
        text=InstructionText("Eres la agente de captura. Nunca afirmes cobertura."),
    )


def test_perf_u12_3_el_trabajo_propio_del_nodo_del_turno_sin_proveedor() -> None:
    """El nodo `intake` real, con el proveedor sustituido: p95 <= 50 ms."""
    nodo = IntakeNode(
        extract=_ExtractorInstantaneo(), instruction=_instruccion, clock=lambda: date(2026, 9, 27)
    )
    estado = IntakeNodeInput(
        tenant_id="knotwell",
        case_id="perf-u12-3",
        record_type=RecordType.CLAIM,
        case_state=CaseState.CAPTURING,
        completeness=_completitud(),
        language="es",
        turn_text="me chocaron por detrás en la autopista",
        turn_id="turno-1",
    )

    async def _turno() -> None:
        await nodo.run(estado)

    muestras_ms = [s * 1000 for s in _cronometrar_async(_turno)]
    p95 = _p95(muestras_ms)
    print(f"PERF-U12.3: p50={statistics.median(muestras_ms):.4f} ms p95={p95:.4f} ms")

    assert p95 <= 50.0, f"el nodo del turno sin proveedor midio p95={p95:.4f} ms (umbral 50 ms)"


# --- PERF-U12.4: el plazo declarado del ritmo del turno -------------------------


def test_perf_u12_4_el_plazo_declarado_del_ritmo_del_turno() -> None:
    """Sobre el `NodeSpec` declarado, no una corrida cronometrada de verdad.

    El mecanismo que hace cumplir este numero -- que el plazo es de la
    ejecucion completa y no de cada intento -- lo prueba, cronometrado de
    verdad,
    `test_executor.py::test_el_ritmo_del_turno_no_gasta_el_doble_del_plazo_declarado`.
    Esta prueba comprueba el numero que ese mecanismo aplica: el doble de la
    meta p95 del turno (800 ms), el margen que `performance-requirements.md`
    razona -- suficiente para una llamada simplemente lenta, poco para una
    colgada.
    """
    assert graph.TURN_NODE_SPECS, "no hay ningun nodo del ritmo del turno que medir"
    for spec in graph.TURN_NODE_SPECS:
        assert spec.timeout_ms <= 1_600, (
            f"'{spec.name.value}' declara {spec.timeout_ms} ms de plazo en el "
            "ritmo del turno: PERF-U12.4 fija 1.600 ms como techo"
        )
