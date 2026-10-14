"""Los dos ritmos (paso 5 de U12): BR2.1 a BR2.4, sobre `orchestration/rhythm.py`.

BR5.5 (el arrendamiento) y el hallazgo del plazo del ritmo del turno
(PERF-U12.4) viven en `test_executor.py`, junto al modulo que los implementa.
Lo cronometrado (PERF-U12.2 a PERF-U12.4) vive en `test_performance.py`.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import time
from collections.abc import Iterator

import pytest

from untangle.compliance.controls import patterns
from untangle.copy_catalog import api as copy_api
from untangle.orchestration import phrases, rhythm
from untangle.orchestration import rhythm as rhythm_module
from untangle.telemetry.traces.models import NodeName
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import TenantConfig


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


# --- BR2.3: dentro del turno, solo los tres controles baratos -------------------

#: La verificacion de poliza y el motor de reglas son paquetes propios: si
#: `rhythm.py` los importara, aparecerian aqui como segmento de un modulo.
_MODULOS_PROHIBIDOS = frozenset({"policy_rag", "rules"})

#: La revision completa de cumplimiento vive en el mismo paquete que la guardia
#: que si esta permitida (`compliance.controls.api`), asi que el contrato de
#: importacion no puede distinguirlas por modulo: hace falta mirar los simbolos.
_SIMBOLOS_PROHIBIDOS = frozenset(
    {
        "final_review",
        "ReviewRequest",
        "ReviewPorts",
        "ReviewEvidence",
        "EvidenceState",
        "TranscriptLine",
        "save_review",
        "record_intervention",
    }
)


def _segmentos(punteado: str) -> set[str]:
    return set(punteado.split("."))


def test_br2_3_el_manejador_del_turno_no_importa_verificacion_reglas_ni_revision_completa() -> None:
    """BR2.3, AC1.25.4: analiza el arbol de importaciones y de llamadas, no el texto.

    Dos comprobaciones independientes: que el modulo no importa `policy_rag` ni
    `rules` (la verificacion de poliza y el motor de reglas son paquetes propios,
    asi que aparecerian como modulo importado), y que ninguno de los simbolos de
    la revision completa de cumplimiento aparece referenciado -- ni importado ni
    usado como atributo (`compliance.controls.api.final_review(...)` tambien
    quedaria atrapado).
    """
    arbol = ast.parse(inspect.getsource(rhythm_module))

    modulos_importados: set[str] = set()
    simbolos_importados: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module:
            modulos_importados |= _segmentos(nodo.module)
            simbolos_importados |= {alias.name for alias in nodo.names}
        elif isinstance(nodo, ast.Import):
            for alias in nodo.names:
                modulos_importados |= _segmentos(alias.name)

    referencias = {p.attr for p in ast.walk(arbol) if isinstance(p, ast.Attribute)}
    referencias |= {p.id for p in ast.walk(arbol) if isinstance(p, ast.Name)}
    referencias |= simbolos_importados

    # `from untangle import policy_rag` importa el modulo como un simbolo, no
    # como un segmento de `nodo.module` (que ahi seria solo "untangle"): sin
    # sumar `simbolos_importados` aqui, esa forma de importar se coleaba.
    chocan_modulos = (modulos_importados | simbolos_importados) & _MODULOS_PROHIBIDOS
    assert not chocan_modulos, (
        f"'orchestration.rhythm' importa {sorted(chocan_modulos)}: son del ritmo "
        "de fondo (D22), no del turno"
    )

    chocan_simbolos = referencias & _SIMBOLOS_PROHIBIDOS
    assert not chocan_simbolos, (
        f"'orchestration.rhythm' referencia {sorted(chocan_simbolos)}: es la "
        "revision completa de cumplimiento, no uno de los tres controles baratos"
    )


async def test_control_positivo_los_dos_controles_baratos_corren_de_verdad(
    aseguradoras: tuple[TenantConfig, ...],
) -> None:
    """Control positivo del anterior: si `run_turn_controls` no llamara a nada,
    la prueba de arriba pasaria igual con una funcion vacia. Esta comprueba que
    los dos controles que si estan permitidos corren y devuelven lo que la
    logica de U10 ya prueba por su cuenta.
    """
    tenant_id = aseguradoras[0].tenant_id
    texto = "Sí, fue culpa suya y le van a pagar 900 dólares, y alguien está sangrando mucho"

    resultado = await rhythm.run_turn_controls(
        texto, tenant_id=tenant_id, language="es", case_id="caso-1"
    )

    assert resultado.signals.emergency is True
    assert resultado.guard.evaluated is True
    assert {i.category.value for i in resultado.guard.interventions if i.category is not None} == {
        "fault",
        "amount",
    }


# --- BR2.2: el turno nunca espera al trabajo de fondo ---------------------------


async def test_br2_2_lanzar_el_fondo_no_espera_aunque_se_demore() -> None:
    """AC1.25.2, con el retardo inyectado a proposito: `launch_background` no bloquea."""
    fondo_termino = asyncio.Event()

    async def _fondo_lento() -> None:
        await asyncio.sleep(0.2)
        fondo_termino.set()

    inicio = time.perf_counter()
    tarea = rhythm.launch_background(_fondo_lento())
    transcurrido_s = time.perf_counter() - inicio

    assert transcurrido_s < 0.05, (
        f"lanzar el fondo tardo {transcurrido_s * 1000:.1f} ms: no puede tardar "
        "lo que tarda el propio fondo (200 ms)"
    )
    # La senal fuerte: recien creada, la tarea todavia no corrio ni un paso --
    # no depende de cuanto tarde esta maquina en medir 50 ms.
    assert isinstance(tarea, asyncio.Task), "el factory por omision crea una Task de verdad"
    assert tarea.done() is False, "la tarea ya estaba resuelta nada mas lanzarla"
    assert not fondo_termino.is_set(), "el fondo ya corrio: se espero en vez de lanzarse"

    # Control positivo: el fondo si termina, cuando alguien lo espera de verdad.
    await tarea
    assert fondo_termino.is_set()


# --- BR2.4: la frase de espera --------------------------------------------------


def test_br2_4_frase_de_espera_cuando_algo_del_fondo_no_ha_vuelto() -> None:
    """AC1.25.3: la frase literal del catalogo, con su clave."""
    pendiente = frozenset({NodeName.POLICY_VERIFICATION})

    resultado = rhythm.waiting_response(pendiente, language="es")

    assert resultado is not None
    clave, texto = resultado
    assert clave == phrases.WAITING
    assert texto == "Déjame revisar tu póliza, un momento."


def test_br2_4_sin_nada_pendiente_no_hay_frase_de_espera() -> None:
    """Control positivo del anterior: sin nada pendiente, no hace falta decir nada."""
    assert rhythm.waiting_response(frozenset(), language="es") is None
