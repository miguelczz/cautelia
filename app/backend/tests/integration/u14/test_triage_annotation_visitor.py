"""Anotar para las reglas como visitante: quien queda como autor, que no pisa y que tiene techo.

La logica sin la capa HTTP (la ruta tiene su propio archivo). El visitante que "hace de
ajustador" sobre su propio caso anota igual que el personal, con tres diferencias que son lo
que se prueba aqui: queda como `insured` con el identificador de visitante, no toca lo que
anoto una persona de la aseguradora, y su escritura publica tiene techo y no repite trabajo.

Los controles positivos van delante de cada rechazo: el visitante anota, el personal pisa la
nota del visitante, el tope corta en el borde y no antes. Las reglas son las reales de cada
aseguradora, por su identificador.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI

from untangle.case_record import history
from untangle.case_record.models import Actor, ActorType, CaseChange, ChangeKind
from untangle.inbox import annotation, decision, events, receipts, triage_notes
from untangle.inbox.annotation import AnnotationLimitReachedError, StaffNoteLockedError
from untangle.inbox.triage_notes import TriageValues
from untangle.rules import api as reglas
from untangle.tenancy import api as tenancy

from .conftest import AHORA, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u14")

SUNMEADOW = "sunmeadow"
PERSONAL = "diana"
VISITANTE = Actor(actor_type=ActorType.INSURED, actor_id=decision.VISITOR_ACTOR_ID)


async def _anotar(
    case_id: str,
    valores: TriageValues,
    *,
    por: str | None,
    clave: str | None = None,
    minutos: int = 0,
) -> annotation.AnnotationApplied:
    return await annotation.apply(
        SUNMEADOW,
        case_id=case_id,
        values=valores,
        idempotency_key=clave if clave is not None else f"k-{uuid.uuid4().hex[:10]}",
        principal_id=por,
        now=datetime.now(UTC) + timedelta(minutes=minutos),
    )


async def _entradas(case_id: str) -> list[CaseChange]:
    return [
        e
        for e in await history.of_case(SUNMEADOW, case_id)
        if e.change_kind is ChangeKind.TRIAGE_NOTED
    ]


async def _sembrar_entradas_del_visitante(case_id: str, cuantas: int) -> None:
    """Entradas de historial del visitante, sin pasar por el guardado: lo que se prueba es el tope."""
    for _ in range(cuantas):
        await history.append(
            SUNMEADOW,
            CaseChange(
                change_id=history.new_change_id(),
                case_id=case_id,
                change_kind=ChangeKind.TRIAGE_NOTED,
                field_key="fraud_suspected",
                actor=VISITANTE,
                detail="unset -> true",
                changed_at=AHORA,
            ),
        )


async def _recibos() -> int:
    async with tenancy.session_for(SUNMEADOW) as sesion:
        filas = await tenancy.fetch_all(
            sesion,
            "SELECT receipt_id FROM decision_receipt WHERE operation = :operacion",
            operacion=receipts.Operation.TRIAGE_NOTE.value,
        )
    return len(filas)


# --- El visitante anota y queda como visitante ----------------------------------------


async def test_el_visitante_anota_y_las_reglas_se_vuelven_a_evaluar(app: FastAPI) -> None:
    del app
    caso = await nuevo_caso(SUNMEADOW)

    aplicada = await _anotar(caso, TriageValues(claim_amount=1500, fraud_suspected=True), por=None)

    assert aplicada.evaluation is not None
    assert {"SUN-R-03", "SUN-R-07"} <= {r.id for r in aplicada.evaluation.fired_rules}
    assert aplicada.evaluation.category == "referral"
    assert aplicada.receipt_id is not None
    nota = await triage_notes.read(SUNMEADOW, caso)
    assert nota is not None
    assert nota.values == TriageValues(claim_amount=1500, fraud_suspected=True)


async def test_el_visitante_queda_como_visitante_en_la_nota_y_en_el_historial(
    app: FastAPI,
) -> None:
    """Nunca como una persona de la aseguradora: es lo que responde "quien anoto esto"."""
    del app
    caso = await nuevo_caso(SUNMEADOW)

    await _anotar(caso, TriageValues(claim_amount=1500, coverage_disputed=False), por=None)

    nota = await triage_notes.read(SUNMEADOW, caso)
    assert nota is not None
    assert nota.noted_by == decision.VISITOR_ACTOR_ID
    entradas = await _entradas(caso)
    assert [(e.field_key, e.detail) for e in entradas] == [
        ("claim_amount", "unset -> 1500"),
        ("coverage_disputed", "unset -> false"),
    ]
    assert {(e.actor.actor_type, e.actor.actor_id) for e in entradas} == {
        (ActorType.INSURED, decision.VISITOR_ACTOR_ID)
    }


async def test_el_visitante_puede_seguir_cambiando_lo_que_anoto_el(app: FastAPI) -> None:
    del app
    caso = await nuevo_caso(SUNMEADOW)
    await _anotar(caso, TriageValues(fraud_suspected=True), por=None, clave="a")

    cambiada = await _anotar(caso, TriageValues(fraud_suspected=False), por=None, clave="b")

    assert cambiada.evaluation is not None
    assert "SUN-R-07" not in {r.id for r in cambiada.evaluation.fired_rules}
    assert [e.detail for e in await _entradas(caso)] == ["unset -> true", "true -> false"]


# --- Lo que anoto el personal ni se lee ni se pisa ------------------------------------


async def test_la_nota_del_personal_no_la_pisa_el_visitante(app: FastAPI) -> None:
    del app
    caso = await nuevo_caso(SUNMEADOW)
    await _anotar(caso, TriageValues(claim_amount=7318, fraud_suspected=True), por=PERSONAL)
    antes = await triage_notes.read(SUNMEADOW, caso)
    evaluaciones = len(await reglas.evaluations_for(SUNMEADOW, caso))
    entradas = len(await _entradas(caso))
    recibos = await _recibos()

    with pytest.raises(StaffNoteLockedError):
        await _anotar(caso, TriageValues(claim_amount=10, fraud_suspected=False), por=None)

    assert await triage_notes.read(SUNMEADOW, caso) == antes
    assert len(await reglas.evaluations_for(SUNMEADOW, caso)) == evaluaciones
    assert len(await _entradas(caso)) == entradas
    assert await _recibos() == recibos


async def test_el_visitante_tampoco_puede_guardar_lo_mismo_que_anoto_el_personal(
    app: FastAPI,
) -> None:
    """Guardar "lo mismo" le diria, por la respuesta, que ahi hay una nota igual a la suya."""
    del app
    caso = await nuevo_caso(SUNMEADOW)
    await _anotar(caso, TriageValues(fraud_suspected=True), por=PERSONAL)

    with pytest.raises(StaffNoteLockedError):
        await _anotar(caso, TriageValues(fraud_suspected=True), por=None)


async def test_el_personal_si_pisa_la_nota_del_visitante_y_desde_ahi_es_suya(
    app: FastAPI,
) -> None:
    del app
    caso = await nuevo_caso(SUNMEADOW)
    await _anotar(caso, TriageValues(fraud_suspected=True), por=None, clave="visitante")

    await _anotar(caso, TriageValues(fraud_suspected=False), por=PERSONAL, clave="personal")

    nota = await triage_notes.read(SUNMEADOW, caso)
    assert nota is not None
    assert nota.noted_by == PERSONAL
    assert nota.values.fraud_suspected is False
    # Y con ese cambio la nota dejo de ser del visitante: ya no la puede cambiar.
    with pytest.raises(StaffNoteLockedError):
        await _anotar(caso, TriageValues(fraud_suspected=True), por=None)


# --- Guardar lo mismo no escribe nada -------------------------------------------------


async def test_el_visitante_que_guarda_lo_mismo_no_escribe_nada_y_recibe_la_evaluacion_vigente(
    app: FastAPI,
) -> None:
    del app
    caso = await nuevo_caso(SUNMEADOW)
    valores = TriageValues(claim_amount=1500, fraud_suspected=True)
    primera = await _anotar(caso, valores, por=None, clave="a")
    evaluaciones = await reglas.evaluations_for(SUNMEADOW, caso)
    entradas = len(await _entradas(caso))
    recibos = await _recibos()
    avisos = len(await events.since(SUNMEADOW, 0))

    otra_vez = await _anotar(caso, valores, por=None, clave="b", minutos=5)

    assert otra_vez.receipt_id is None, "dio un recibo por una escritura que no ocurrio"
    assert otra_vez.replayed is False
    assert otra_vez.evaluation == primera.evaluation
    assert await reglas.evaluations_for(SUNMEADOW, caso) == evaluaciones
    assert len(await _entradas(caso)) == entradas
    assert await _recibos() == recibos
    assert len(await events.since(SUNMEADOW, 0)) == avisos, "avisó de un cambio que no hubo"


async def test_el_visitante_que_guarda_el_formulario_vacio_sin_nada_anotado_no_crea_nada(
    app: FastAPI,
) -> None:
    del app
    caso = await nuevo_caso(SUNMEADOW)

    aplicada = await _anotar(caso, TriageValues(), por=None)

    assert aplicada.evaluation is None
    assert aplicada.receipt_id is None
    assert await triage_notes.read(SUNMEADOW, caso) is None
    assert not await reglas.evaluations_for(SUNMEADOW, caso)
    assert not await _entradas(caso)
    assert await _recibos() == 0


async def test_el_personal_que_guarda_lo_mismo_sigue_evaluando_y_dando_recibo(
    app: FastAPI,
) -> None:
    """El control de las dos pruebas de arriba: para el personal nada de esto cambia."""
    del app
    caso = await nuevo_caso(SUNMEADOW)
    valores = TriageValues(fraud_suspected=True)
    await _anotar(caso, valores, por=PERSONAL, clave="a")

    otra_vez = await _anotar(caso, valores, por=PERSONAL, clave="b", minutos=5)

    assert otra_vez.receipt_id is not None
    assert len(await reglas.evaluations_for(SUNMEADOW, caso)) == 2


async def test_repetir_la_misma_clave_devuelve_la_primera_y_no_cuenta_dos_veces(
    app: FastAPI,
) -> None:
    del app
    caso = await nuevo_caso(SUNMEADOW)
    valores = TriageValues(claim_amount=1500, fraud_suspected=True)
    primera = await _anotar(caso, valores, por=None, clave="la-misma")

    segunda = await _anotar(caso, valores, por=None, clave="la-misma", minutos=5)

    assert segunda.replayed is True
    assert segunda.receipt_id == primera.receipt_id
    assert len(await _entradas(caso)) == 2


# --- El techo -------------------------------------------------------------------------


async def test_con_una_entrada_menos_que_el_tope_el_visitante_aun_puede(app: FastAPI) -> None:
    del app
    caso = await nuevo_caso(SUNMEADOW)
    await _sembrar_entradas_del_visitante(caso, annotation.VISITOR_ANNOTATION_LIMIT - 1)

    assert await annotation.visitor_has_budget(SUNMEADOW, caso) is True
    aplicada = await _anotar(caso, TriageValues(fraud_suspected=True), por=None)

    assert aplicada.receipt_id is not None
    assert await annotation.visitor_has_budget(SUNMEADOW, caso) is False


async def test_en_el_tope_el_siguiente_cambio_se_rechaza_sin_escribir(app: FastAPI) -> None:
    del app
    caso = await nuevo_caso(SUNMEADOW)
    await _sembrar_entradas_del_visitante(caso, annotation.VISITOR_ANNOTATION_LIMIT)
    entradas = len(await _entradas(caso))

    with pytest.raises(AnnotationLimitReachedError):
        await _anotar(caso, TriageValues(fraud_suspected=True), por=None)

    assert await annotation.visitor_has_budget(SUNMEADOW, caso) is False
    assert await triage_notes.read(SUNMEADOW, caso) is None
    assert not await reglas.evaluations_for(SUNMEADOW, caso)
    assert len(await _entradas(caso)) == entradas
    assert await _recibos() == 0


async def test_en_el_tope_guardar_lo_que_ya_estaba_no_es_un_cambio(app: FastAPI) -> None:
    """El tope es de cambios: quien ya llego sigue pudiendo guardar su pantalla tal cual."""
    del app
    caso = await nuevo_caso(SUNMEADOW)
    valores = TriageValues(fraud_suspected=True)
    primera = await _anotar(caso, valores, por=None, clave="a")
    await _sembrar_entradas_del_visitante(caso, annotation.VISITOR_ANNOTATION_LIMIT)

    igual = await _anotar(caso, valores, por=None, clave="b", minutos=5)

    assert igual.evaluation == primera.evaluation
    assert igual.receipt_id is None


async def test_un_guardado_de_tres_datos_que_empieza_bajo_el_tope_se_hace_entero(
    app: FastAPI,
) -> None:
    """El tope se mira antes de escribir y un guardado no se parte: puede pasarse en dos."""
    del app
    caso = await nuevo_caso(SUNMEADOW)
    await _sembrar_entradas_del_visitante(caso, annotation.VISITOR_ANNOTATION_LIMIT - 1)

    await _anotar(
        caso,
        TriageValues(claim_amount=2000, coverage_disputed=True, fraud_suspected=True),
        por=None,
    )

    assert len(await _entradas(caso)) == annotation.VISITOR_ANNOTATION_LIMIT + 2


async def test_el_tope_es_de_cada_caso(app: FastAPI) -> None:
    del app
    lleno = await nuevo_caso(SUNMEADOW)
    otro = await nuevo_caso(SUNMEADOW)
    await _sembrar_entradas_del_visitante(lleno, annotation.VISITOR_ANNOTATION_LIMIT)

    aplicada = await _anotar(otro, TriageValues(fraud_suspected=True), por=None)

    assert aplicada.receipt_id is not None
    assert await annotation.visitor_has_budget(SUNMEADOW, otro) is True


async def test_el_tope_no_alcanza_al_personal(app: FastAPI) -> None:
    """Las entradas del visitante llenan su cuenta, no la del ajustador que revisa el caso."""
    del app
    caso = await nuevo_caso(SUNMEADOW)
    await _sembrar_entradas_del_visitante(caso, annotation.VISITOR_ANNOTATION_LIMIT)

    aplicada = await _anotar(caso, TriageValues(claim_amount=5000), por=PERSONAL)

    assert aplicada.receipt_id is not None
    nota = await triage_notes.read(SUNMEADOW, caso)
    assert nota is not None
    assert nota.noted_by == PERSONAL


async def test_las_entradas_del_personal_no_gastan_el_tope_del_visitante(app: FastAPI) -> None:
    del app
    caso = await nuevo_caso(SUNMEADOW)
    await _sembrar_entradas_del_visitante(caso, annotation.VISITOR_ANNOTATION_LIMIT - 1)

    # Tres entradas del personal: si se contaran como del visitante, ya habria pasado el tope.
    await _anotar(
        caso,
        TriageValues(claim_amount=1500, coverage_disputed=True, fraud_suspected=True),
        por=PERSONAL,
    )

    assert len(await _entradas(caso)) == annotation.VISITOR_ANNOTATION_LIMIT + 2
    assert await annotation.visitor_has_budget(SUNMEADOW, caso) is True
