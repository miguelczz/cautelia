"""El acceso a datos de lo que el ajustador anota: leer, escribir y no mezclar aseguradoras.

Contra PostgreSQL de verdad. La tabla ya tiene su prueba de politica y de llaves
(`test_triage_note_table.py`); aqui se comprueba lo que el codigo le pide: que "sin anotar"
y "no" sobrevivan a la ida y vuelta, que lo ultimo reemplace a lo anterior y que la lectura
de una aseguradora no vea lo de otra.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from untangle.inbox import triage_notes
from untangle.inbox.triage_notes import TriageValues
from untangle.tenancy import api as tenancy

from .conftest import AHORA, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u14")


async def _escribir(
    tenant_id: str,
    case_id: str,
    valores: TriageValues,
    *,
    por: str = "ajustador-de-prueba",
    cuando: datetime = AHORA,
) -> None:
    async with tenancy.session_for(tenant_id) as sesion:
        await triage_notes.write(sesion, tenant_id, case_id, valores, noted_by=por, now=cuando)


async def test_un_caso_sin_anotaciones_no_devuelve_nada(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    assert await triage_notes.read(propia, caso) is None
    assert await triage_notes.rule_inputs_of(propia, caso) == {}


async def test_lo_anotado_vuelve_igual_con_quien_y_cuando(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    valores = TriageValues(claim_amount=2500, coverage_disputed=True, fraud_suspected=False)

    await _escribir(propia, caso, valores, por="diana")

    nota = await triage_notes.read(propia, caso)
    assert nota is not None
    assert nota.values == valores
    assert nota.noted_by == "diana"
    assert nota.updated_at == AHORA


async def test_sin_anotar_y_no_sobreviven_a_la_ida_y_vuelta(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """El nulo no se vuelve falso al guardar ni al leer: es lo que impide que una regla
    que lee un campo ausente dispare, o que uno en falso afirme que se comprobo."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    await _escribir(propia, caso, TriageValues(coverage_disputed=False))

    nota = await triage_notes.read(propia, caso)
    assert nota is not None
    assert nota.values.claim_amount is None
    assert nota.values.coverage_disputed is False
    assert nota.values.fraud_suspected is None
    assert await triage_notes.rule_inputs_of(propia, caso) == {"coverage_disputed": False}


async def test_lo_ultimo_reemplaza_a_lo_anterior_y_se_puede_volver_a_dejar_sin_anotar(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    await _escribir(propia, caso, TriageValues(claim_amount=100, fraud_suspected=True), por="uno")

    despues = AHORA + timedelta(minutes=5)
    await _escribir(propia, caso, TriageValues(claim_amount=300), por="otro", cuando=despues)

    nota = await triage_notes.read(propia, caso)
    assert nota is not None
    assert nota.values == TriageValues(claim_amount=300)
    assert nota.noted_by == "otro"
    assert nota.updated_at == despues
    assert await triage_notes.rule_inputs_of(propia, caso) == {"claim_amount": 300}


async def test_leer_para_cambiar_devuelve_lo_de_antes_dentro_de_la_transaccion(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    async with tenancy.session_for(propia) as sesion:
        assert await triage_notes.read_for_update(sesion, propia, caso) is None
    await _escribir(propia, caso, TriageValues(claim_amount=7))

    async with tenancy.session_for(propia) as sesion:
        previa = await triage_notes.read_for_update(sesion, propia, caso)

    assert previa is not None
    assert previa.values == TriageValues(claim_amount=7)


async def test_una_aseguradora_no_lee_lo_que_anoto_otra(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Misma consulta, otra aseguradora: la politica de fila no le entrega la fila."""
    ajena, propia = dos_aseguradoras
    caso_ajeno = await nuevo_caso(ajena)
    await _escribir(ajena, caso_ajeno, TriageValues(claim_amount=9999, fraud_suspected=True))

    assert await triage_notes.read(propia, caso_ajeno) is None
    assert await triage_notes.rule_inputs_of(propia, caso_ajeno) == {}
    # Y el control positivo: la duena si lo lee, asi que la ausencia de arriba no es una
    # lectura que siempre devuelve vacio.
    duena = await triage_notes.read(ajena, caso_ajeno)
    assert duena is not None
    assert duena.values.claim_amount == 9999


async def test_no_se_anota_el_caso_de_otra_aseguradora(
    dos_aseguradoras: tuple[str, str],
) -> None:
    ajena, propia = dos_aseguradoras
    caso_ajeno = await nuevo_caso(ajena)

    with pytest.raises(IntegrityError):
        await _escribir(propia, caso_ajeno, TriageValues(claim_amount=1))

    assert await triage_notes.read(ajena, caso_ajeno) is None
