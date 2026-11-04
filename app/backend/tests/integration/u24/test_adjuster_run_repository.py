"""El acceso a datos de la corrida: abrir sin duplicar, anexar pasos y cerrar una sola vez.

Contra PostgreSQL de verdad. Lo que importa es lo que el proceso de la tanda 2 va a necesitar:
que dos arranques del mismo caso dejen una corrida y un solo dueno, que los pasos lleguen en
orden con sus fuentes, que cerrar sea de una sola vez y que la lectura de una aseguradora no vea
la de otra.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytest

from untangle.adjuster import repository
from untangle.adjuster.models import OpenedRun, RunStatus, RunStep, SourceKind, StepId, StepSource
from untangle.inbox.actions import InboxAction

from .conftest import AHORA, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u14")

MODELO = "claude-haiku-5-5"
MAXIMO = 3
CADUCA = timedelta(minutes=5)


async def _abrir(tenant_id: str, case_id: str, *, cuando: datetime = AHORA) -> OpenedRun:
    return await repository.open_run(
        tenant_id, case_id, model=MODELO, max_attempts=MAXIMO, stale_after=CADUCA, now=cuando
    )


def _paso(paso_id: StepId = StepId.CASE_READ, **cambios: object) -> RunStep:
    base: dict[str, object] = {
        "id": paso_id,
        "text": "Leyo el reporte: choque en la via, sin heridos.",
        "sources": (StepSource(kind=SourceKind.CASE, ref="incident_description", label="Relato"),),
    }
    return RunStep.model_validate(base | cambios)


async def test_un_caso_sin_corrida_no_devuelve_nada(dos_aseguradoras: tuple[str, str]) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    assert await repository.read(propia, caso) is None


async def test_abrir_crea_la_corrida_corriendo_en_su_primer_intento(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    abierta = await _abrir(propia, caso)

    assert abierta.started
    assert abierta.run.status is RunStatus.RUNNING
    assert abierta.run.attempt == 1
    assert abierta.run.steps == ()
    assert abierta.run.model == MODELO
    assert await repository.read(propia, caso) == abierta.run


async def test_abrir_dos_veces_deja_una_corrida_y_un_solo_dueno(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    primera = await _abrir(propia, caso)
    segunda = await _abrir(propia, caso, cuando=AHORA + timedelta(seconds=5))

    assert primera.started
    assert not segunda.started, "una corrida que ya esta corriendo tiene dueno"
    assert segunda.run.attempt == 1


async def test_dos_arranques_a_la_vez_tienen_un_solo_dueno(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Dos procesos que leen el caso a la vez: la llave primaria decide la carrera."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    resultados = await asyncio.gather(*(_abrir(propia, caso) for _ in range(4)))

    assert sum(1 for r in resultados if r.started) == 1
    assert len({r.run.created_at for r in resultados}) == 1


async def test_los_pasos_se_guardan_en_orden_con_sus_fuentes(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _abrir(propia, caso)
    valor = _paso(
        StepId.VEHICLE_VALUE,
        text="Valor de referencia: 62.000.000 COP.",
        sources=(
            StepSource(
                kind=SourceKind.WEB,
                ref="fasecolda",
                label="Guia de valores",
                url="https://guiadevalores.fasecolda.com/x",
            ),
        ),
    )

    await repository.append_step(propia, caso, _paso(), now=AHORA)
    escrita = await repository.append_step(
        propia, caso, valor, now=AHORA + timedelta(seconds=2), searches_used=2
    )

    assert [p.id for p in escrita.steps] == [StepId.CASE_READ, StepId.VEHICLE_VALUE]
    assert escrita.steps[1] == valor, "el paso y su fuente web sobreviven a la ida y vuelta"
    assert escrita.searches_used == 2
    assert escrita.updated_at == AHORA + timedelta(seconds=2)
    leida = await repository.read(propia, caso)
    assert leida == escrita


async def test_anexar_el_mismo_paso_otra_vez_no_cambia_nada(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _abrir(propia, caso)

    primera = await repository.append_step(propia, caso, _paso(), now=AHORA)
    repetida = await repository.append_step(
        propia, caso, _paso(text="Otro texto."), now=AHORA + timedelta(seconds=9)
    )

    assert len(repetida.steps) == 1
    assert repetida.steps[0].text == primera.steps[0].text
    assert repetida.updated_at == primera.updated_at


async def test_no_se_anexa_a_una_corrida_que_no_existe_ni_a_una_que_no_corre(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    with pytest.raises(repository.RunNotFoundError):
        await repository.append_step(propia, caso, _paso(), now=AHORA)

    await _abrir(propia, caso)
    await repository.close_decided(
        propia, caso, decision=InboxAction.APPROVE, summary="Cubierto.", now=AHORA
    )

    with pytest.raises(repository.RunNotRunningError):
        await repository.append_step(propia, caso, _paso(), now=AHORA)


async def test_cerrar_como_decidida_guarda_la_decision_y_la_explicacion(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _abrir(propia, caso)
    await repository.append_step(propia, caso, _paso(), now=AHORA)

    cerrada = await repository.close_decided(
        propia,
        caso,
        decision=InboxAction.REJECT,
        summary="La poliza no cubre uso en plataforma de viajes.",
        now=AHORA + timedelta(seconds=30),
        searches_used=3,
    )

    assert cerrada.status is RunStatus.DECIDED
    assert cerrada.decision is InboxAction.REJECT
    assert cerrada.summary == "La poliza no cubre uso en plataforma de viajes."
    assert cerrada.searches_used == 3
    assert len(cerrada.steps) == 1, "cerrar no pierde los pasos"


async def test_cerrar_otra_vez_con_lo_mismo_devuelve_lo_que_ya_hay_y_con_otra_cosa_choca(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Dos procesos que creen haber decidido el mismo caso: la idempotencia del cierre."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _abrir(propia, caso)
    primera = await repository.close_decided(
        propia, caso, decision=InboxAction.APPROVE, summary="Cubierto.", now=AHORA
    )

    repetida = await repository.close_decided(
        propia, caso, decision=InboxAction.APPROVE, summary="Cubierto.", now=AHORA
    )
    assert repetida == primera

    with pytest.raises(repository.RunConflictError):
        await repository.close_decided(
            propia, caso, decision=InboxAction.REJECT, summary="No cubierto.", now=AHORA
        )
    with pytest.raises(repository.RunConflictError):
        await repository.close_failed(propia, caso, error_kind="timeout", now=AHORA)


async def test_una_corrida_decidida_nunca_se_reabre(dos_aseguradoras: tuple[str, str]) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _abrir(propia, caso)
    await repository.close_decided(
        propia, caso, decision=InboxAction.APPROVE, summary="Cubierto.", now=AHORA
    )

    de_nuevo = await _abrir(propia, caso, cuando=AHORA + timedelta(days=1))

    assert not de_nuevo.started
    assert de_nuevo.run.status is RunStatus.DECIDED


async def test_una_corrida_capada_se_reabre_sin_gastar_intento(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Nunca llego a intentar: el tope diario la detuvo antes de empezar."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _abrir(propia, caso)
    capada = await repository.close_capped(propia, caso, now=AHORA)
    assert capada.status is RunStatus.CAPPED

    reabierta = await _abrir(propia, caso, cuando=AHORA + timedelta(days=1))

    assert reabierta.started
    assert reabierta.run.status is RunStatus.RUNNING
    assert reabierta.run.attempt == 1


async def test_una_corrida_fallida_se_reabre_gastando_un_intento_hasta_el_maximo(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    for esperado in range(1, MAXIMO + 1):
        abierta = await _abrir(propia, caso, cuando=AHORA + timedelta(minutes=esperado))
        assert abierta.started
        assert abierta.run.attempt == esperado
        assert abierta.run.steps == (), "un intento nuevo parte sin los pasos del anterior"
        assert abierta.run.error_kind is None
        await repository.append_step(propia, caso, _paso(), now=AHORA)
        fallida = await repository.close_failed(
            propia, caso, error_kind="rate_limited", now=AHORA, searches_used=1
        )
        assert fallida.status is RunStatus.FAILED
        assert fallida.error_kind == "rate_limited"

    agotada = await _abrir(propia, caso, cuando=AHORA + timedelta(days=1))

    assert not agotada.started, "al agotar los intentos el caso queda en revision"
    assert agotada.run.status is RunStatus.FAILED
    assert agotada.run.attempt == MAXIMO


async def test_una_corrida_que_corre_y_no_avanza_se_reabre_gastando_un_intento(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """El proceso que la llevaba se cayo: su fila seguia en `running` y nadie la tomaba."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _abrir(propia, caso)
    await repository.append_step(propia, caso, _paso(), now=AHORA)

    antes = await _abrir(propia, caso, cuando=AHORA + CADUCA - timedelta(seconds=1))
    despues = await _abrir(propia, caso, cuando=AHORA + CADUCA)

    assert not antes.started, "mientras avanza o no ha caducado, otro proceso la lleva"
    assert despues.started
    assert despues.run.status is RunStatus.RUNNING
    assert despues.run.attempt == 2
    assert despues.run.steps == (), "el intento nuevo parte sin los pasos del perdido"


async def test_dos_arranques_sobre_una_corrida_perdida_tienen_un_solo_dueno(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _abrir(propia, caso)
    tarde = AHORA + CADUCA + timedelta(minutes=1)

    resultados = await asyncio.gather(*(_abrir(propia, caso, cuando=tarde) for _ in range(4)))

    assert sum(1 for r in resultados if r.started) == 1
    assert {r.run.attempt for r in resultados} == {2}


async def test_una_corrida_perdida_sin_intentos_que_gastar_queda_fallida(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    for esperado in range(1, MAXIMO + 1):
        abierta = await _abrir(propia, caso, cuando=AHORA + timedelta(hours=esperado))
        assert abierta.started
        assert abierta.run.attempt == esperado

    cerrada = await _abrir(propia, caso, cuando=AHORA + timedelta(days=1))

    assert not cerrada.started
    assert cerrada.run.status is RunStatus.FAILED
    assert cerrada.run.error_kind == "run_abandoned"
    assert cerrada.run.attempt == MAXIMO


async def test_cada_aseguradora_lee_solo_sus_corridas(dos_aseguradoras: tuple[str, str]) -> None:
    primera, segunda = dos_aseguradoras
    caso_primera = await nuevo_caso(primera)
    await _abrir(primera, caso_primera)
    await repository.append_step(primera, caso_primera, _paso(), now=AHORA)

    assert await repository.read(primera, caso_primera) is not None
    assert await repository.read(segunda, caso_primera) is None, (
        "la otra aseguradora no ve la corrida aunque conozca el identificador del caso"
    )
