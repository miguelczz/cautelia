"""El repositorio de U10, contra PostgreSQL de verdad (paso 8 del plan).

Tres promesas, las tres de BR4.2 y BR6.3, y la de aislamiento de BR8.1:

1. **Doble registro**: la segunda divulgacion del mismo caso y canal no crea
   otra fila, y el reintento de una intervencion con su identificador tampoco.
2. **Reejecucion sin duplicar**: el nodo que se vuelve a ejecutar al reanudar
   recalcula la revision con otro identificador y otra hora, y aun asi queda
   una sola, la primera.
3. **Dos aseguradoras que no se ven**: lo que una registra no aparece en las
   lecturas de la otra, ni siquiera preguntando por el mismo caso.

La conexion es la del rol del aplicativo, que no puede saltarse las politicas.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from untangle.compliance.controls import repository
from untangle.compliance.controls.models import (
    ComplianceReview,
    DisclosureChannel,
    DisclosureRecord,
    FindingCode,
    GuardCategory,
    GuardIntervention,
    InterventionAction,
)

from .conftest import AHORA, CasoSembrado, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u10")


def _divulgacion(
    caso: CasoSembrado, *, canal: DisclosureChannel = DisclosureChannel.CHAT, sufijo: str = "1"
) -> DisclosureRecord:
    return DisclosureRecord(
        disclosure_id=f"{caso.case_id}-divulgacion-{sufijo}",
        tenant_id=caso.tenant_id,
        case_id=caso.case_id,
        channel=canal,
        language="es",
        catalog_key="compliance.disclosure.opening",
        disclosed_at=AHORA,
    )


def _intervencion(caso: CasoSembrado, **cambios: object) -> GuardIntervention:
    base = GuardIntervention(
        intervention_id=f"{caso.case_id}-intervencion-1",
        tenant_id=caso.tenant_id,
        case_id=caso.case_id,
        turn_id=caso.turn_ids[-1],
        category=GuardCategory.COVERAGE_PROMISE,
        pattern_id="guard.es.coverage_promise.001",
        action=InterventionAction.SUBSTITUTED,
        catalog_key="compliance.guard.coverage_promise",
        occurred_at=AHORA,
    )
    return base.evolve(**cambios) if cambios else base


def _revision(caso: CasoSembrado, *, sufijo: str, segundos: int = 0) -> ComplianceReview:
    """Una revision con un control en falso, para que la ida y vuelta lleve hallazgos."""
    return ComplianceReview(
        review_id=f"{caso.case_id}-revision-{sufijo}",
        tenant_id=caso.tenant_id,
        case_id=caso.case_id,
        disclosure_ok=False,
        human_route_ok=True,
        explainability_ok=True,
        findings=(FindingCode.DISCLOSURE_MISSING,),
        reviewed_through_turn=caso.turn_ids[-1],
        reviewed_at=AHORA + timedelta(seconds=segundos),
    )


# --- Doble registro (BR4.2) ---------------------------------------------------


async def test_la_segunda_divulgacion_del_mismo_canal_no_crea_otra_fila(
    dos_aseguradoras: tuple[str, str],
) -> None:
    primera, _ = dos_aseguradoras
    caso = await nuevo_caso(primera)

    quedo_la_primera = await repository.record_disclosure(_divulgacion(caso, sufijo="1"))
    quedo_la_segunda = await repository.record_disclosure(_divulgacion(caso, sufijo="2"))

    assert quedo_la_primera is True
    assert quedo_la_segunda is False
    assert await repository.disclosures(primera, caso.case_id) == (_divulgacion(caso, sufijo="1"),)


async def test_un_caso_retomado_por_otro_canal_lleva_dos_divulgaciones(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La unicidad es por canal: voz y despues chat son dos registros legitimos."""
    primera, _ = dos_aseguradoras
    caso = await nuevo_caso(primera)

    await repository.record_disclosure(_divulgacion(caso, canal=DisclosureChannel.VOICE))
    await repository.record_disclosure(_divulgacion(caso, canal=DisclosureChannel.CHAT, sufijo="2"))

    canales = [d.channel for d in await repository.disclosures(primera, caso.case_id)]
    assert sorted(canales) == [DisclosureChannel.CHAT, DisclosureChannel.VOICE]


async def test_reintentar_una_intervencion_con_su_identificador_no_la_duplica(
    dos_aseguradoras: tuple[str, str],
) -> None:
    primera, _ = dos_aseguradoras
    caso = await nuevo_caso(primera)
    intervencion = _intervencion(caso)

    assert await repository.record_intervention(intervencion) is True
    assert await repository.record_intervention(intervencion) is False
    assert await repository.interventions(primera, caso.case_id) == (intervencion,)


async def test_las_tres_acciones_de_la_guardia_vuelven_tal_como_se_guardaron(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Ida y vuelta de las tres formas, incluida la no evaluable sin categoria (BR1.5)."""
    primera, _ = dos_aseguradoras
    caso = await nuevo_caso(primera)
    sustituida = _intervencion(caso)
    descartada = _intervencion(
        caso,
        intervention_id=f"{caso.case_id}-intervencion-2",
        action=InterventionAction.DROPPED,
        catalog_key=None,
        occurred_at=AHORA + timedelta(seconds=1),
    )
    no_evaluable = _intervencion(
        caso,
        intervention_id=f"{caso.case_id}-intervencion-3",
        action=InterventionAction.NOT_EVALUABLE,
        category=None,
        pattern_id=None,
        catalog_key="compliance.guard.degraded",
        occurred_at=AHORA + timedelta(seconds=2),
    )
    for intervencion in (no_evaluable, sustituida, descartada):
        await repository.record_intervention(intervencion)

    assert await repository.interventions(primera, caso.case_id) == (
        sustituida,
        descartada,
        no_evaluable,
    )


# --- Reejecucion sin duplicar (BR6.3) -----------------------------------------


async def test_la_reejecucion_de_la_revision_deja_una_sola_y_devuelve_la_primera(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """El nodo se vuelve a ejecutar al reanudar y recalcula la revision.

    La recalculada trae otro identificador y otra hora, que es lo que pasa de
    verdad: si la prueba repitiera el mismo objeto, pasaria aunque el
    repositorio insertara sin mirar la clave.
    """
    primera, _ = dos_aseguradoras
    caso = await nuevo_caso(primera)
    original = _revision(caso, sufijo="original")
    recalculada = _revision(caso, sufijo="recalculada", segundos=30)

    guardada_primero = await repository.save_review(original)
    guardada_despues = await repository.save_review(recalculada)

    assert guardada_primero == original
    assert guardada_despues == original
    assert await repository.review_through(primera, caso.case_id, caso.turn_ids[-1]) == original


async def test_revisar_un_turno_posterior_si_es_otra_revision(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La clave es (caso, turno revisado): otro punto de la conversacion no choca."""
    primera, _ = dos_aseguradoras
    caso = await nuevo_caso(primera, turnos=3)
    temprana = _revision(caso, sufijo="temprana").evolve(reviewed_through_turn=caso.turn_ids[1])
    final = _revision(caso, sufijo="final")

    await repository.save_review(temprana)
    await repository.save_review(final)

    assert await repository.review_through(primera, caso.case_id, caso.turn_ids[1]) == temprana
    assert await repository.review_through(primera, caso.case_id, caso.turn_ids[2]) == final


# --- Dos aseguradoras que no se ven (BR8.1) -----------------------------------


async def test_lo_que_registra_una_aseguradora_no_aparece_en_las_lecturas_de_otra(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """La otra aseguradora pregunta por **el mismo caso** y no encuentra nada.

    Preguntar por el identificador ajeno es la forma de la prueba que falla si
    el aislamiento solo viviera en un filtro del codigo: aqui no hay filtro por
    aseguradora en ninguna consulta, lo filtra la politica.
    """
    primera, segunda = dos_aseguradoras
    caso = await nuevo_caso(primera)
    await repository.record_disclosure(_divulgacion(caso))
    await repository.record_intervention(_intervencion(caso))
    await repository.save_review(_revision(caso, sufijo="1"))

    assert await repository.disclosures(segunda, caso.case_id) == ()
    assert await repository.interventions(segunda, caso.case_id) == ()
    assert await repository.review_through(segunda, caso.case_id, caso.turn_ids[-1]) is None
    # Y la duena si lo ve: sin esta mitad, un repositorio que no leyera nada
    # pasaria la prueba.
    assert len(await repository.disclosures(primera, caso.case_id)) == 1
    assert len(await repository.interventions(primera, caso.case_id)) == 1
    assert await repository.review_through(primera, caso.case_id, caso.turn_ids[-1]) is not None


async def test_un_caso_sin_nada_registrado_responde_vacio_y_no_con_un_error(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Vacio es una respuesta: la revision lo leera como divulgacion ausente."""
    primera, _ = dos_aseguradoras
    caso = await nuevo_caso(primera)

    assert await repository.disclosures(primera, caso.case_id) == ()
    assert await repository.interventions(primera, caso.case_id) == ()
    assert await repository.review_through(primera, caso.case_id, caso.turn_ids[-1]) is None
