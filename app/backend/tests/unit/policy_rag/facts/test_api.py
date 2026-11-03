"""La superficie asincrona: lee la poliza por el punto unico y devuelve `None` si no es de esa aseguradora.

La base se sustituye en el limite del repositorio (`find_policy`, `clause_keys_of_forms`,
`clauses_by_ids`): lo que se prueba aqui es lo que `api.py` hace con lo leido. Que la base filtre por
aseguradora es la politica de fila, que prueban las pruebas de aislamiento con la base de verdad.
"""

from __future__ import annotations

from datetime import date

import pytest

from untangle.base import RigidTopic
from untangle.copy_catalog import api as copy_api
from untangle.policy_rag.facts import api as facts
from untangle.policy_rag.facts.models import PolicyStatus

from .conftest import CorpusEnMemoria, corpus_de_ejemplo, instalar_corpus

HOY = date(2026, 9, 1)


@pytest.fixture
def corpus(monkeypatch: pytest.MonkeyPatch) -> CorpusEnMemoria:
    copy_api.reset()
    return instalar_corpus(monkeypatch, corpus_de_ejemplo())


async def test_el_resumen_se_lee_con_el_tenant_pedido(corpus: CorpusEnMemoria) -> None:
    resumen = await facts.policy_summary("stonecroft", "POL-99", on=HOY)

    assert resumen is not None
    assert resumen.status is PolicyStatus.IN_FORCE
    assert corpus.read_for == ["stonecroft"]


async def test_una_poliza_de_otra_aseguradora_o_inexistente_devuelve_lo_mismo(
    corpus: CorpusEnMemoria,
) -> None:
    de_otra = await facts.policy_summary("sunmeadow", "POL-99", on=HOY)
    inexistente = await facts.policy_summary("stonecroft", "POL-00", on=HOY)

    assert de_otra is None
    assert inexistente is None


async def test_cada_funcion_devuelve_none_si_la_poliza_no_existe(corpus: CorpusEnMemoria) -> None:
    assert await facts.limits("stonecroft", "POL-00", language="es") is None
    assert await facts.deductibles("stonecroft", "POL-00", language="es") is None
    assert await facts.vehicles("stonecroft", "POL-00") is None
    assert await facts.drivers("stonecroft", "POL-00") is None
    assert await facts.endorsements("stonecroft", "POL-00", language="es") is None
    assert await facts.clause("stonecroft", "POL-00", "C-BASE") is None
    assert (
        await facts.rigid_answer(
            "stonecroft", "POL-00", RigidTopic.DEDUCTIBLE, language="es", on=HOY
        )
        is None
    )


async def test_las_funciones_devuelven_los_datos_del_registro(corpus: CorpusEnMemoria) -> None:
    limites = await facts.limits("stonecroft", "POL-99", language="es")
    deducibles = await facts.deductibles("stonecroft", "POL-99", language="en")
    vehiculos = await facts.vehicles("stonecroft", "POL-99")
    conductores = await facts.drivers("stonecroft", "POL-99")

    assert limites is not None
    assert len(limites) == 5
    assert deducibles is not None
    assert {d.amount.units for d in deducibles} == {1500, 250}
    assert vehiculos is not None
    assert len(vehiculos) == 2
    assert conductores is not None
    assert conductores[0].is_holder


async def test_los_endosos_traen_las_clausulas_que_cambian(corpus: CorpusEnMemoria) -> None:
    endosos = await facts.endorsements("stonecroft", "POL-99", language="es")

    assert endosos is not None
    assert [e.form_id for e in endosos] == ["SA-PAP-2026-END-1", "SA-PAP-2026-END-2"]
    assert endosos[0].clause_keys == ("B.INS",)
    assert endosos[1].clause_keys == ()


async def test_una_clausula_solo_se_devuelve_si_es_de_la_poliza(corpus: CorpusEnMemoria) -> None:
    base = await facts.clause("stonecroft", "POL-99", "C-BASE")
    endoso = await facts.clause("stonecroft", "POL-99", "C-ENDOSO")

    assert base is not None
    assert base.form_id == "SA-PAP-2026"
    assert endoso is not None
    # De otro formulario, senuelo o inexistente: lo mismo, nada.
    assert await facts.clause("stonecroft", "POL-99", "C-AJENA") is None
    assert await facts.clause("stonecroft", "POL-99", "C-SENUELO") is None
    assert await facts.clause("stonecroft", "POL-99", "C-NO-EXISTE") is None


async def test_la_respuesta_rigida_se_arma_desde_el_registro(corpus: CorpusEnMemoria) -> None:
    respuesta = await facts.rigid_answer(
        "stonecroft", "POL-99", RigidTopic.ENDORSEMENTS, language="es", on=HOY
    )
    ninguna = await facts.rigid_answer(
        "stonecroft", "POL-99", RigidTopic.NONE, language="es", on=HOY
    )

    assert respuesta is not None
    assert "Los gastos médicos cubren también a peatones atropellados" in respuesta.text
    assert ninguna is None
