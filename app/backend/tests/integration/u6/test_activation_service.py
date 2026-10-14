"""La superficie de la activacion contra PostgreSQL de verdad (BR8.1, BR8.3, BR8.4).

Las unitarias prueban que hace la superficie con cada fallo simulado; estas, que
las clasificaciones valen con los fallos **reales**: una base a la que no se
puede llegar y una fila que la base rechaza por su referencia.
"""

from __future__ import annotations

import time

import pytest

from untangle.server import health
from untangle.telemetry.activation import api as activation
from untangle.tenancy import ephemeral, session

from ...unit.web.eventos import capturar
from .conftest import AHORA, nueva_sesion

pytestmark = pytest.mark.usefixtures("activacion")

#: Una direccion a la que no responde nadie: el puerto 1 no escucha. Con el rol
#: del aplicativo y sin clave, porque la conexion no llega ni a pedirla.
BASE_INALCANZABLE = "postgresql+psycopg://untangle_app@127.0.0.1:1/untangle"


async def test_tres_informes_del_mismo_hito_cuentan_una_vez(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR8.1 de punta a punta: superficie, repositorio y base."""
    primera, _ = dos_aseguradoras
    visita = await nueva_sesion(primera)

    resultados = [
        await activation.record_milestone(
            tenant_id=primera,
            visitor_key_hash=visita.visitor_key_hash,
            milestone=activation.ActivationMilestone.THIRD_TURN,
            source=activation.ActivationSource.VISITOR,
            now=AHORA,
        )
        for _ in range(3)
    ]

    assert resultados == [
        activation.MilestoneOutcome.COUNTED,
        activation.MilestoneOutcome.ALREADY_REACHED,
        activation.MilestoneOutcome.ALREADY_REACHED,
    ]
    [fila] = await activation.daily_counts()
    assert (fila.tenant_id, fila.milestone, fila.count) == (
        primera,
        activation.ActivationMilestone.THIRD_TURN,
        1,
    )


async def test_la_sonda_de_salud_y_un_caso_del_corredor_dejan_los_conteos_en_cero(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR8.4: ni el chequeo periodico ni las evaluaciones son sesiones."""
    primera, _ = dos_aseguradoras
    visita = await nueva_sesion(primera)

    # La comprobacion de la base de la salud, la de verdad, contra la base de verdad.
    await health.database_check()
    # Un caso del corredor informando los tres hitos.
    for hito in activation.ActivationMilestone:
        resultado = await activation.record_milestone(
            tenant_id=primera,
            visitor_key_hash=visita.visitor_key_hash,
            milestone=hito,
            source=activation.ActivationSource.EVAL_RUNNER,
            now=AHORA,
        )
        assert resultado is activation.MilestoneOutcome.NOT_A_SESSION

    assert await activation.daily_counts() == ()


async def test_con_la_base_inalcanzable_el_turno_sigue_y_el_evento_dice_por_que(
    sesiones: ephemeral.EphemeralDatabase,
    dos_aseguradoras: tuple[str, str],
) -> None:
    """BR8.3 y REL-U6.3 con una base que de verdad no contesta."""
    primera, _ = dos_aseguradoras
    visita = await nueva_sesion(primera)
    await session.dispose()
    session.configure(BASE_INALCANZABLE)
    try:
        with capturar() as leer:
            inicio = time.perf_counter()
            resultado = await activation.record_milestone(
                tenant_id=primera,
                visitor_key_hash=visita.visitor_key_hash,
                milestone=activation.ActivationMilestone.FIRST_MESSAGE,
                source=activation.ActivationSource.VISITOR,
                now=AHORA,
            )
            transcurrido = time.perf_counter() - inicio
            eventos = leer()
    finally:
        await session.dispose()
        session.configure(sesiones.app_url)

    assert resultado is activation.MilestoneOutcome.FAILED
    assert transcurrido < activation.RECORD_TIMEOUT_S + 0.2
    [evento] = [e for e in eventos if e["event"] == "activation.milestone_failed"]
    assert evento["error_kind"] in {"unavailable", "timeout"}
    assert visita.visitor_key_hash not in str(eventos)


async def test_una_sesion_que_no_es_de_esa_aseguradora_se_rechaza_sin_romper_nada(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La referencia de la tabla rechaza la fila; la superficie lo clasifica y sigue."""
    primera, segunda = dos_aseguradoras
    ajena = await nueva_sesion(segunda)

    with capturar() as leer:
        resultado = await activation.record_milestone(
            tenant_id=primera,
            visitor_key_hash=ajena.visitor_key_hash,
            milestone=activation.ActivationMilestone.FIRST_MESSAGE,
            source=activation.ActivationSource.VISITOR,
            now=AHORA,
        )
        eventos = leer()

    assert resultado is activation.MilestoneOutcome.FAILED
    [evento] = [e for e in eventos if e["event"] == "activation.milestone_failed"]
    assert evento["error_kind"] == "rejected"
    assert await activation.daily_counts() == ()
