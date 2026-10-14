"""Lo que las pruebas de integracion de U10 necesitan en la base efimera.

La base la levanta `tests/conftest.py`, una sola para toda la corrida. Aqui solo
esta lo propio de esta unidad: crear los casos y sus turnos **con la API de U4**
(`unit-test-instructions.md`, Datos de prueba) y dejar la base vacia antes y
despues de cada prueba.

**Por que se vacia borrando el caso.** Las tres tablas de U10 cuelgan del caso
con borrado en cascada (CG-U10-3); borrar el caso es exactamente como el
reinicio nocturno las vacia, y asi la limpieza de la prueba no ejercita un
camino distinto del de produccion.

**Por que se vacia antes tambien.** Cada prueba tiene que poder correr sola y en
cualquier orden, y entrar limpia es la mitad de esa promesa que mas se olvida.

**Ninguna aseguradora escrita a mano.** Se toman de la configuracion cargada: si
una cuarta entra o una sale, las pruebas siguen midiendo lo mismo.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from untangle.base import Locale
from untangle.case_record import api as casos
from untangle.case_record.models import Channel, Origin, RecordType, Speaker
from untangle.case_record.transcript import TurnDraft
from untangle.compliance.redaction.api import redact
from untangle.tenancy import api as tenancy
from untangle.tenancy import ephemeral, session

#: Un instante fijo para toda la suite de U10. El reloj entra por argumento: una
#: conducta que leyera el reloj del proceso solo se podria probar esperando.
AHORA = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class CasoSembrado:
    """Un caso de una aseguradora con sus turnos, creado con la API de U4."""

    tenant_id: str
    case_id: str
    turn_ids: tuple[str, ...]


async def _vaciar() -> None:
    """Borra los casos de cada aseguradora; la cascada se lleva lo de U10.

    La sentencia va escrita entera, por aseguradora: sin aseguradora fijada, la
    politica no dejaria ver ninguna fila y el borrado borraria exactamente cero.
    """
    for tenant_id in tenancy.available_ids():
        async with session.session_for(tenant_id) as sesion:
            await session.execute_sql(sesion, "DELETE FROM case_record")


@pytest.fixture
async def base_de_u10(sesiones: ephemeral.EphemeralDatabase) -> AsyncIterator[None]:
    """La base efimera, sin casos antes ni despues de cada prueba."""
    await _vaciar()
    yield
    await _vaciar()


@pytest.fixture
def dos_aseguradoras() -> tuple[str, str]:
    """Dos aseguradoras reales de la configuracion, sin escribir su nombre."""
    disponibles = tenancy.available_ids()
    assert len(disponibles) >= 2, "la prueba de aislamiento necesita dos aseguradoras"
    return disponibles[0], disponibles[1]


async def nuevo_caso(tenant_id: str, *, turnos: int = 2, language: Locale = "es") -> CasoSembrado:
    """Un caso de chat publico con sus turnos, por la API de U4.

    El texto de cada turno pasa por la redaccion antes de guardarse, porque la
    API de U4 no acepta otro: es el mismo camino que usara el aplicativo.
    """
    case_id = f"u10-caso-{uuid.uuid4().hex[:12]}"
    await casos.create_case(
        tenant_id,
        casos.NewCase(
            case_id=case_id,
            record_type=RecordType.CLAIM,
            channel=Channel.CHAT,
            origin=Origin.PUBLIC_CHAT,
            language=language,
        ),
        now=AHORA,
    )
    turn_ids: list[str] = []
    for numero in range(turnos):
        turn_id = f"{case_id}-turno-{numero + 1}"
        await casos.append_turn(
            tenant_id,
            TurnDraft(
                turn_id=turn_id,
                case_id=case_id,
                speaker=Speaker.INSURED if numero % 2 == 0 else Speaker.AGENT,
                channel=Channel.CHAT,
                language=language,
                started_at=AHORA + timedelta(seconds=numero),
            ),
            redact("Turno sembrado para las pruebas de los controles.", language=language),
        )
        turn_ids.append(turn_id)
    return CasoSembrado(tenant_id=tenant_id, case_id=case_id, turn_ids=tuple(turn_ids))
