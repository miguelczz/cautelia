"""Anotar para las reglas: lo que pasa al guardar, con las reglas reales de cada aseguradora.

La logica sin la capa HTTP --la ruta tiene su propio archivo--. Los conjuntos de reglas son
los de `app/config/tenants/*/rules/triage.yaml`, nombrados por su identificador: una regla de
dinero, de cobertura o de fraude que nunca disparaba es justo lo que esta pieza vino a
cerrar, y probarla contra un conjunto inventado no diria si dispara de verdad.

La aplicacion se monta entera (`app`) porque es quien enchufa el puerto de los insumos: lo
que se comprueba es que la evaluacion lea **la misma** derivacion que la cadena de fondo, y
un doble del puerto comprobaria el doble.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI

from untangle.case_record import api as casos
from untangle.case_record import crypto, history
from untangle.case_record.models import CaseState, ChangeKind
from untangle.inbox import annotation, correction, events, receipts, triage_notes
from untangle.inbox.annotation import NotAnnotatableError
from untangle.inbox.triage_notes import TriageValues
from untangle.orchestration import case_context
from untangle.orchestration.state import GraphState
from untangle.rules import api as reglas
from untangle.rules.models import RuleNotConfiguredError
from untangle.server import composition
from untangle.tenancy import api as tenancy

from .conftest import AHORA, cerrado_por_las_reglas, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u14")

#: Dos aseguradoras con reglas de estas tres senales; cada una con los identificadores de
#: su propio archivo. Aqui se nombran porque la prueba es justo sobre sus reglas.
STONECROFT = "stonecroft"
SUNMEADOW = "sunmeadow"

POR = "diana"


def _hora(minutos: int) -> datetime:
    """Las evaluaciones se ordenan por su hora: cada llamada de una prueba, un minuto despues."""
    return datetime.now(UTC) + timedelta(minutes=minutos)


async def _anotar(  # noqa: PLR0913 -- el caso, lo anotado, la clave y el reloj de cada prueba
    tenant_id: str,
    case_id: str,
    valores: TriageValues,
    *,
    clave: str | None = None,
    minutos: int = 0,
    por: str = POR,
) -> annotation.AnnotationApplied:
    return await annotation.apply(
        tenant_id,
        case_id=case_id,
        values=valores,
        # Una clave nueva por llamada, salvo que la prueba pida repetirla: la clave es unica por
        # aseguradora y operacion, y reusarla para otra cosa es justo el conflicto que se prueba.
        idempotency_key=clave if clave is not None else f"k-{uuid.uuid4().hex[:10]}",
        principal_id=por,
        now=_hora(minutos),
    )


def _reglas(aplicada: annotation.AnnotationApplied) -> set[str]:
    assert aplicada.evaluation is not None
    return {regla.id for regla in aplicada.evaluation.fired_rules}


def _id(aplicada: annotation.AnnotationApplied) -> str:
    assert aplicada.evaluation is not None
    return aplicada.evaluation.evaluation_id


# --- «Sin anotar» no dispara; «si» dispara la regla de su aseguradora ----------------


async def test_sin_anotar_nada_cae_en_la_regla_por_defecto(app: FastAPI) -> None:
    del app
    caso = await nuevo_caso(STONECROFT)

    aplicada = await _anotar(STONECROFT, caso, TriageValues())

    assert _reglas(aplicada) == {"STO-R-10"}
    assert aplicada.evaluation is not None
    assert aplicada.evaluation.category == "standard_review"


async def test_un_no_comprobado_tampoco_dispara_ninguna_regla(app: FastAPI) -> None:
    """«No» es una respuesta comprobada, y las reglas de estas tres senales buscan «si»."""
    del app
    caso = await nuevo_caso(SUNMEADOW)

    aplicada = await _anotar(
        SUNMEADOW, caso, TriageValues(coverage_disputed=False, fraud_suspected=False)
    )

    assert _reglas(aplicada) == {"SUN-R-10"}


@pytest.mark.parametrize(
    ("tenant_id", "regla"), [(STONECROFT, "STO-R-06"), (SUNMEADOW, "SUN-R-07")]
)
async def test_la_sospecha_de_fraude_dispara_la_regla_de_su_aseguradora(
    app: FastAPI, tenant_id: str, regla: str
) -> None:
    del app
    caso = await nuevo_caso(tenant_id)

    aplicada = await _anotar(tenant_id, caso, TriageValues(fraud_suspected=True))

    assert regla in _reglas(aplicada)
    assert aplicada.evaluation is not None
    assert aplicada.evaluation.category == "referral"


@pytest.mark.parametrize(
    ("tenant_id", "regla"), [(STONECROFT, "STO-R-01"), (SUNMEADOW, "SUN-R-02")]
)
async def test_la_cobertura_disputada_dispara_la_regla_de_su_aseguradora_y_marca_dinero(
    app: FastAPI, tenant_id: str, regla: str
) -> None:
    del app
    caso = await nuevo_caso(tenant_id)

    aplicada = await _anotar(tenant_id, caso, TriageValues(coverage_disputed=True))

    assert aplicada.evaluation is not None
    disparadas = {r.id: r for r in aplicada.evaluation.fired_rules}
    assert regla in disparadas
    assert disparadas[regla].touches_money is True
    assert aplicada.evaluation.category == "referral"


@pytest.mark.parametrize(
    ("tenant_id", "reglas_de_monto"),
    [
        (STONECROFT, {"alto": "STO-R-03", "medio": "STO-R-02", "bajo": "STO-R-08"}),
        (SUNMEADOW, {"alto": "SUN-R-04", "medio": "SUN-R-03", "bajo": "SUN-R-09"}),
    ],
)
async def test_el_monto_dispara_la_regla_del_umbral_que_supera(
    app: FastAPI, tenant_id: str, reglas_de_monto: dict[str, str]
) -> None:
    """Las reglas comparan contra la cifra interna: 999, 1000 y 10000 son los bordes."""
    del app
    bajo = await nuevo_caso(tenant_id)
    medio = await nuevo_caso(tenant_id)
    alto = await nuevo_caso(tenant_id)

    en_999 = await _anotar(tenant_id, bajo, TriageValues(claim_amount=999))
    en_1000 = await _anotar(tenant_id, medio, TriageValues(claim_amount=1000))
    en_10000 = await _anotar(tenant_id, alto, TriageValues(claim_amount=10000))

    assert _reglas(en_999) == {reglas_de_monto["bajo"]}
    assert en_999.evaluation is not None
    assert en_999.evaluation.category == "standard_review"
    assert _reglas(en_1000) == {reglas_de_monto["medio"]}
    assert en_1000.evaluation is not None
    assert en_1000.evaluation.category == "referral"
    assert {reglas_de_monto["medio"], reglas_de_monto["alto"]} <= _reglas(en_10000)


async def test_un_monto_cero_es_un_monto_y_no_un_dato_sin_anotar(app: FastAPI) -> None:
    """Cero cae bajo el umbral de «monto anotado»; sin anotar no dispara esa regla."""
    del app
    con_cero = await nuevo_caso(STONECROFT)
    sin_anotar = await nuevo_caso(STONECROFT)

    cero = await _anotar(STONECROFT, con_cero, TriageValues(claim_amount=0))
    nada = await _anotar(STONECROFT, sin_anotar, TriageValues())

    assert _reglas(cero) == {"STO-R-08"}
    assert _reglas(nada) == {"STO-R-10"}


async def test_lo_que_dijo_la_persona_sigue_en_la_evaluacion(app: FastAPI) -> None:
    """Los insumos son los de la conversacion **mas** los anotados, no solo los anotados."""
    del app
    caso = await nuevo_caso(STONECROFT)
    await correction.apply(
        STONECROFT,
        case_id=caso,
        field_key="injuries",
        value="si, mi hijo se golpeo la cabeza",
        idempotency_key="sembrar-heridos",
        principal_id=POR,
        cipher=crypto.active(),
        language="es",
        now=AHORA,
    )

    aplicada = await _anotar(STONECROFT, caso, TriageValues(fraud_suspected=False))

    assert "STO-R-04" in _reglas(aplicada)


# --- La evaluacion nueva es la vigente ------------------------------------------------


async def test_la_evaluacion_mas_reciente_es_la_que_acaba_de_guardarse(app: FastAPI) -> None:
    """Anotar, quitar y volver a anotar: cada guardado deja la suya y la ultima manda.

    La tercera repite los insumos de la primera. Con un identificador derivado solo de los
    insumos, la tercera chocaria con la primera, `ON CONFLICT` conservaria la vieja --con
    su hora vieja-- y la vista seguiria mostrando la segunda: la que ya no es la vigente.
    """
    del app
    caso = await nuevo_caso(STONECROFT)

    primera = await _anotar(STONECROFT, caso, TriageValues(fraud_suspected=True), clave="a")
    segunda = await _anotar(STONECROFT, caso, TriageValues(), clave="b", minutos=1)
    tercera = await _anotar(
        STONECROFT, caso, TriageValues(fraud_suspected=True), clave="c", minutos=2
    )

    guardadas = await reglas.evaluations_for(STONECROFT, caso)
    assert [e.evaluation_id for e in guardadas] == [_id(primera), _id(segunda), _id(tercera)]
    assert len({e.evaluation_id for e in guardadas}) == 3
    assert "STO-R-06" in {r.id for r in guardadas[-1].fired_rules}
    assert {r.id for r in guardadas[1].fired_rules} == {"STO-R-10"}


async def test_anotar_no_cambia_el_estado_ni_escribe_en_la_conversacion(app: FastAPI) -> None:
    """Es para las reglas y para quien decide: al asegurado no le llega nada."""
    del app
    caso = await nuevo_caso(STONECROFT)
    antes = await casos.transcript_of(STONECROFT, caso)

    await _anotar(STONECROFT, caso, TriageValues(claim_amount=5000, fraud_suspected=True))

    despues = await casos.get_case(STONECROFT, caso)
    assert despues is not None
    assert despues.state is CaseState.DERIVED
    assert await casos.transcript_of(STONECROFT, caso) == antes


# --- La cadena de fondo tambien lo ve -------------------------------------------------


async def test_la_cadena_de_fondo_lee_lo_anotado(app: FastAPI) -> None:
    """La entrada que arma `decision` para la cadena incluye lo que anoto el ajustador.

    Sin esto, una evaluacion posterior de la cadena --la persona sigue hablando, el caso
    espera al asegurado-- sobreescribiria con una evaluacion que no sabe de la anotacion.
    """
    del app
    caso = await nuevo_caso(STONECROFT, estado=CaseState.AWAITING_INSURED)
    await _anotar(STONECROFT, caso, TriageValues(claim_amount=2500, fraud_suspected=False))
    contexto = await case_context.load_case_context(STONECROFT, caso, turn_text="", now=AHORA)
    estado = GraphState(
        tenant_id=STONECROFT,
        case_id=caso,
        turn_id="fondo-de-la-prueba",
        turn_text="",
        node_writes={},
        pending_background=frozenset(),
    )

    entrada = await composition._entrada_de_decision(contexto, estado, cipher=crypto.active())

    assert entrada.inputs["claim_amount"] == 2500
    assert entrada.inputs["fraud_suspected"] is False
    assert "coverage_disputed" not in entrada.inputs, "un dato sin anotar se invento un valor"


# --- El historial dice quien y que cambio ---------------------------------------------


async def test_cada_dato_que_cambia_deja_su_entrada_con_quien_lo_hizo(app: FastAPI) -> None:
    del app
    caso = await nuevo_caso(STONECROFT)

    await _anotar(
        STONECROFT, caso, TriageValues(claim_amount=1500, fraud_suspected=False), por="diana"
    )

    entradas = [
        e
        for e in await history.of_case(STONECROFT, caso)
        if e.change_kind is ChangeKind.TRIAGE_NOTED
    ]
    assert [(e.field_key, e.detail) for e in entradas] == [
        ("claim_amount", "unset -> 1500"),
        ("fraud_suspected", "unset -> false"),
    ]
    assert {(e.actor.actor_type.value, e.actor.actor_id) for e in entradas} == {("staff", "diana")}


async def test_guardar_lo_mismo_otra_vez_no_agrega_entradas_pero_si_cambiar_un_dato(
    app: FastAPI,
) -> None:
    del app
    caso = await nuevo_caso(STONECROFT)
    await _anotar(STONECROFT, caso, TriageValues(fraud_suspected=False), clave="a")

    await _anotar(STONECROFT, caso, TriageValues(fraud_suspected=False), clave="b", minutos=1)
    await _anotar(STONECROFT, caso, TriageValues(fraud_suspected=True), clave="c", minutos=2)
    await _anotar(STONECROFT, caso, TriageValues(), clave="d", minutos=3, por="otro")

    entradas = [
        (e.detail, e.actor.actor_id)
        for e in await history.of_case(STONECROFT, caso)
        if e.change_kind is ChangeKind.TRIAGE_NOTED
    ]
    assert entradas == [
        ("unset -> false", "diana"),
        ("false -> true", "diana"),
        ("true -> unset", "otro"),
    ]
    nota = await triage_notes.read(STONECROFT, caso)
    assert nota is not None
    assert nota.values == TriageValues()
    assert nota.noted_by == "otro"


# --- Idempotencia ---------------------------------------------------------------------


async def test_la_misma_clave_no_escribe_dos_veces(app: FastAPI) -> None:
    del app
    caso = await nuevo_caso(STONECROFT)
    valores = TriageValues(claim_amount=1500, coverage_disputed=True)

    primera = await _anotar(STONECROFT, caso, valores, clave="la-misma")
    avisos = len(await events.since(STONECROFT, 0))
    segunda = await _anotar(STONECROFT, caso, valores, clave="la-misma", minutos=5)

    assert primera.replayed is False
    assert segunda.replayed is True
    assert segunda.receipt_id == primera.receipt_id
    assert segunda.evaluation == primera.evaluation
    assert len(await reglas.evaluations_for(STONECROFT, caso)) == 1
    entradas = [
        e
        for e in await history.of_case(STONECROFT, caso)
        if e.change_kind is ChangeKind.TRIAGE_NOTED
    ]
    assert len(entradas) == 2
    assert len(await events.since(STONECROFT, 0)) == avisos, "la repeticion avisó de nuevo"


async def test_una_clave_reciclada_para_otra_anotacion_es_un_conflicto(app: FastAPI) -> None:
    """Y no devuelve el resultado guardado ni escribe la segunda anotacion."""
    del app
    caso = await nuevo_caso(STONECROFT)
    await _anotar(STONECROFT, caso, TriageValues(claim_amount=1500), clave="reciclada")

    with pytest.raises(receipts.RecycledKeyError):
        await _anotar(STONECROFT, caso, TriageValues(claim_amount=9999), clave="reciclada")

    nota = await triage_notes.read(STONECROFT, caso)
    assert nota is not None
    assert nota.values.claim_amount == 1500


async def test_el_mismo_texto_de_clave_en_otra_operacion_no_choca(app: FastAPI) -> None:
    """La clave es por operacion: corregir un campo con la clave de una anotacion es legitimo."""
    del app
    caso = await nuevo_caso(STONECROFT)
    await _anotar(STONECROFT, caso, TriageValues(claim_amount=1500), clave="compartida")

    await correction.apply(
        STONECROFT,
        case_id=caso,
        field_key="location",
        value="Carrera 43 con calle 10",
        idempotency_key="compartida",
        principal_id=POR,
        cipher=crypto.active(),
        language="es",
        now=AHORA,
    )

    campos = [e.field_key for e in await history.of_case(STONECROFT, caso)]
    assert "location" in campos, "la correccion con la misma clave no se aplico"
    assert (await triage_notes.read(STONECROFT, caso)) is not None


# --- Quien no puede, no escribe nada ---------------------------------------------------


@pytest.mark.parametrize(
    "estado",
    [
        CaseState.OPEN,
        CaseState.CAPTURING,
        CaseState.VERIFYING,
        CaseState.DECIDING,
    ],
)
async def test_un_caso_que_la_agente_aun_lleva_no_admite_anotaciones(
    app: FastAPI, estado: CaseState
) -> None:
    del app
    caso = await nuevo_caso(STONECROFT, estado=estado)

    with pytest.raises(NotAnnotatableError):
        await _anotar(STONECROFT, caso, TriageValues(fraud_suspected=True))

    await _nada_escrito(STONECROFT, caso)


async def test_un_caso_cerrado_no_admite_anotaciones(app: FastAPI) -> None:
    del app
    caso = await cerrado_por_las_reglas(SUNMEADOW)
    antes = len(await reglas.evaluations_for(SUNMEADOW, caso))

    with pytest.raises(NotAnnotatableError):
        await _anotar(SUNMEADOW, caso, TriageValues(fraud_suspected=True))

    assert await triage_notes.read(SUNMEADOW, caso) is None
    assert len(await reglas.evaluations_for(SUNMEADOW, caso)) == antes


@pytest.mark.parametrize("estado", [CaseState.DERIVED, CaseState.AWAITING_INSURED])
async def test_un_caso_con_un_ajustador_o_esperando_al_asegurado_si_las_admite(
    app: FastAPI, estado: CaseState
) -> None:
    """El control positivo de los rechazos de arriba: la misma llamada, otro estado."""
    del app
    caso = await nuevo_caso(STONECROFT, estado=estado)

    aplicada = await _anotar(STONECROFT, caso, TriageValues(fraud_suspected=True))

    assert "STO-R-06" in _reglas(aplicada)


async def test_el_caso_de_otra_aseguradora_no_se_anota(app: FastAPI) -> None:
    del app
    ajeno = await nuevo_caso(SUNMEADOW)

    with pytest.raises(casos.CaseNotFoundError):
        await _anotar(STONECROFT, ajeno, TriageValues(fraud_suspected=True))

    await _nada_escrito(SUNMEADOW, ajeno)
    assert await triage_notes.read(STONECROFT, ajeno) is None


async def test_una_aseguradora_sin_reglas_cargadas_no_guarda_nada(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Una anotacion sin su evaluacion deja la vista diciendo lo de antes: no se escribe."""
    del app
    caso = await nuevo_caso(STONECROFT)

    def _sin_reglas(*, tenant_id: str, ruleset_version: str | None = None) -> frozenset[str]:
        raise RuleNotConfiguredError(tenant_id)

    monkeypatch.setattr(reglas, "required_inputs", _sin_reglas)

    with pytest.raises(RuleNotConfiguredError):
        await _anotar(STONECROFT, caso, TriageValues(fraud_suspected=True))

    await _nada_escrito(STONECROFT, caso)


async def test_sin_insumos_enchufados_no_se_evalua_a_medias(app: FastAPI) -> None:
    """Evaluar solo con lo anotado ignoraria lo que la persona conto y se veria igual de bien."""
    del app
    caso = await nuevo_caso(STONECROFT)
    annotation.reset_rule_inputs()

    with pytest.raises(annotation.RuleInputsNotInstalledError):
        await _anotar(STONECROFT, caso, TriageValues(fraud_suspected=True))


async def _nada_escrito(tenant_id: str, case_id: str) -> None:
    """Ni anotacion, ni evaluacion, ni entrada de historial, ni recibo, ni aviso."""
    assert await triage_notes.read(tenant_id, case_id) is None
    assert not await reglas.evaluations_for(tenant_id, case_id)
    assert not [
        e
        for e in await history.of_case(tenant_id, case_id)
        if e.change_kind is ChangeKind.TRIAGE_NOTED
    ]
    async with tenancy.session_for(tenant_id) as sesion:
        recibos = await tenancy.fetch_all(
            sesion,
            "SELECT receipt_id FROM decision_receipt WHERE operation = :operacion",
            operacion=receipts.Operation.TRIAGE_NOTE.value,
        )
    assert not recibos
    assert not [a for a in await events.since(tenant_id, 0) if a.case_id == case_id]
