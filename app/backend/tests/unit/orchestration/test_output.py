"""El punto único de salida (paso 7 de U12, BR2.5): `orchestration/output.py`.

Mismo patrón de estado limpio que `test_rhythm.py`: la guardia y el catálogo se
cargan de verdad desde `app/config/`, sin dobles -- lo que se prueba es que
`ExitGate.send` de verdad pasa por `guard_output` (C-20), no una segunda
implementación de la guardia.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from untangle.compliance.controls import patterns
from untangle.copy_catalog import api as copy_api
from untangle.orchestration.output import ExitGate
from untangle.tenancy import config as tenancy_config

_TENANT = "knotwell"


@pytest.fixture(autouse=True)
def _estado_limpio() -> Iterator[None]:
    copy_api.reset()
    patterns.reset()
    tenancy_config.reset()
    yield
    copy_api.reset()
    patterns.reset()
    tenancy_config.reset()


async def test_send_sustituye_un_monto_por_la_guardia_real() -> None:
    """BR2.5: `send` pasa el texto por `guard_output` de verdad, no lo repite en línea."""
    gate = ExitGate(tenant_id=_TENANT, language="es", case_id="caso-1")

    texto, claves = await gate.send("Le pagan 1.200.000 pesos por el parachoques.")

    assert claves, "la guardia no sustituyó nada: la prueba no comprobó lo que dice"
    assert "1.200.000" not in texto


async def test_send_deja_pasar_una_frase_sin_hallazgos() -> None:
    """Una frase limpia sale igual, y sin claves de sustitución."""
    gate = ExitGate(tenant_id=_TENANT, language="es", case_id="caso-1")

    texto, claves = await gate.send("Gracias, ya anoté el lugar del choque.")

    assert texto == "Gracias, ya anoté el lugar del choque."
    assert claves == ()


async def test_send_no_repite_la_sustitucion_dos_veces_en_el_mismo_turno() -> None:
    """BR1.4 de la guardia: una instancia de `ExitGate` es un turno.

    La segunda frase de la misma categoría en el mismo turno se descarta -- el
    texto sale vacío -- en vez de repetir la sustitución permitida. Es
    `GuardTurn` haciendo su trabajo, y `ExitGate` reutilizándolo entre
    llamadas es lo que lo hace posible.
    """
    gate = ExitGate(tenant_id=_TENANT, language="es", case_id="caso-1")

    _, primeras_claves = await gate.send("Le pagan 1.200.000 pesos por el parachoques.")
    segundo_texto, segundas_claves = await gate.send("Le dan 900.000 pesos más por la puerta.")

    assert primeras_claves == (copy_api.CopyKey("compliance.guard.amount"),)
    assert segundo_texto == ""  # BR1.4: la segunda de la categoría se descarta
    assert segundas_claves == ()  # descartada, no vuelve a sustituir


async def test_una_instancia_nueva_por_turno_no_recuerda_la_anterior() -> None:
    """Dos turnos (dos instancias) no comparten la memoria de `GuardTurn`."""
    primero = ExitGate(tenant_id=_TENANT, language="es", case_id="caso-1")
    segundo = ExitGate(tenant_id=_TENANT, language="es", case_id="caso-1")

    await primero.send("Le pagan 1.200.000 pesos por el parachoques.")
    texto, claves = await segundo.send("Le dan 900.000 pesos más por la puerta.")

    assert claves, "un turno nuevo vuelve a evaluar la categoría, no la hereda del anterior"
    assert texto != ""
