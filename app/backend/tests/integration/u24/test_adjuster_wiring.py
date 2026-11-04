"""El cableado del ajustador contra la base: quien firma, el aviso al chat, la lectura y el disparo.

El proceso en si (los seis pasos) se prueba con dobles en `tests/unit/adjuster`; aqui se prueba lo
que solo la base y las rutas de verdad dicen: que la decision del ajustador de IA cierra el caso
por la misma ruta que una persona y queda firmada como ajustador de IA, que repetirla no cierra ni
avisa dos veces, que la agencia sigue sin aprobar (A3), que la lectura del caso trae el bloque del
ajustador y que derivar un caso lo avisa.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI

from untangle.case_record import api as casos
from untangle.case_record import history as historial
from untangle.case_record.models import ActorType, CaseState, Resolution
from untangle.compliance.controls.api import HandoffReason
from untangle.inbox import actions, adjuster_view, decision
from untangle.inbox.actions import InboxAction
from untangle.orchestration import case_context, derivation_trigger
from untangle.tenancy import api as tenancy
from untangle.tenancy.models import TenantKind

from ..u14.conftest import cliente, credencial_de
from .conftest import AHORA, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u14")


@pytest.fixture
def emisora() -> str:
    return next(
        t.tenant_id
        for t in sorted(tenancy.loaded().available, key=lambda c: c.tenant_id)
        if t.kind is TenantKind.CARRIER
    )


@pytest.fixture
def agencia() -> str:
    return next(
        t.tenant_id
        for t in sorted(tenancy.loaded().available, key=lambda c: c.tenant_id)
        if t.kind is TenantKind.AGENCY
    )


@pytest.fixture(autouse=True)
def reanudaciones(app: FastAPI) -> Iterator[list[str]]:
    del app
    llamadas: list[str] = []

    async def reanudar(case_id: str, resolucion: object, tenant_id: str) -> None:
        del resolucion, tenant_id
        llamadas.append(case_id)

    decision.install_resume_handler(reanudar)
    yield llamadas
    decision.reset_resume_handler()
    decision.install_decision_listener(None)
    adjuster_view.install(None)
    derivation_trigger.install_derived_listener(None)


async def _decide_la_ia(
    tenant_id: str, case_id: str, accion: InboxAction, *, clave: str = "adjuster-1"
) -> decision.DecisionRecorded:
    return await decision.decide(
        tenancy.require(tenant_id),
        case_id=case_id,
        action=accion,
        comment="Aprobado: el choque esta cubierto.",
        idempotency_key=clave,
        principal_id=None,
        adjuster_ai=True,
        now=AHORA,
    )


async def test_la_decision_del_ajustador_de_ia_cierra_el_caso_y_queda_firmada_como_tal(
    emisora: str, reanudaciones: list[str]
) -> None:
    caso = await nuevo_caso(emisora)

    registrada = await _decide_la_ia(emisora, caso, InboxAction.APPROVE)

    assert registrada.case_state is CaseState.CLOSED
    assert registrada.resolution is Resolution.APPROVED
    entradas = await historial.of_case(emisora, caso)
    firmadas = [e for e in entradas if e.actor.actor_type is ActorType.ADJUSTER_AI]
    assert firmadas, "el historial no dice que lo cerro el ajustador de IA"
    assert all(e.actor.actor_id is None for e in firmadas)
    assert not [e for e in entradas if e.actor.actor_id == decision.VISITOR_ACTOR_ID]
    assert reanudaciones == [caso]


async def test_repetir_el_registro_con_la_misma_llave_no_cierra_ni_reanuda_ni_avisa_otra_vez(
    emisora: str, reanudaciones: list[str]
) -> None:
    avisos: list[decision.DecisionMade] = []

    async def avisar(decidida: decision.DecisionMade) -> None:
        avisos.append(decidida)

    decision.install_decision_listener(avisar)
    caso = await nuevo_caso(emisora)

    primera = await _decide_la_ia(emisora, caso, InboxAction.APPROVE)
    segunda = await _decide_la_ia(emisora, caso, InboxAction.APPROVE)

    assert not primera.replayed
    assert segunda.replayed
    assert segunda.receipt_id == primera.receipt_id
    assert reanudaciones == [caso]
    (aviso,) = avisos
    assert aviso.actor_type is ActorType.ADJUSTER_AI


async def test_la_agencia_solo_envia_a_la_aseguradora_tambien_con_el_ajustador_de_ia(
    agencia: str,
) -> None:
    """A3: la misma regla de siempre; el actor nuevo no abre una via nueva."""
    caso = await nuevo_caso(agencia)

    with pytest.raises(actions.ActionNotAllowedError):
        await _decide_la_ia(agencia, caso, InboxAction.APPROVE, clave="adjuster-agencia-1")
    pendiente = await casos.get_case(agencia, caso)
    assert pendiente is not None
    assert pendiente.state is CaseState.DERIVED

    enviada = await _decide_la_ia(agencia, caso, InboxAction.MARK_SENT, clave="adjuster-agencia-2")

    assert enviada.resolution is Resolution.SENT_TO_INSURER


async def test_el_ajustador_de_ia_no_toma_un_caso_que_la_agente_aun_evalua(emisora: str) -> None:
    caso = await nuevo_caso(emisora, estado=CaseState.DECIDING)

    with pytest.raises(actions.ActionNotAllowedError):
        await _decide_la_ia(emisora, caso, InboxAction.APPROVE)

    actual = await casos.get_case(emisora, caso)
    assert actual is not None
    assert actual.state is CaseState.DECIDING


class _Vigia:
    def __init__(self, *, falla: bool = False) -> None:
        self.falla = falla
        self.reintentos: list[tuple[str, str, CaseState]] = []

    async def read(self, tenant_id: str, case_id: str) -> adjuster_view.AdjusterRunOut | None:
        if self.falla:
            msg = "la base del ajustador no contesta"
            raise OSError(msg)
        return adjuster_view.AdjusterRunOut(
            status="decided",
            attempt=1,
            steps=(
                adjuster_view.AdjusterStepOut(
                    id="clauses",
                    text="Encontre la clausula del choque.",
                    sources=(
                        adjuster_view.AdjusterSourceOut(
                            kind="clause", ref="SM-PAP-2026-D.INS.COLLISION", label="Choque"
                        ),
                    ),
                ),
            ),
            decision=InboxAction.APPROVE,
            headline="Aprobado",
            explanation="Cubre el choque.",
            updated_at=AHORA.isoformat(),
        )

    async def retry_if_needed(self, tenant_id: str, case_id: str, state: CaseState) -> None:
        self.reintentos.append((tenant_id, case_id, state))


async def _ver(app: FastAPI, tenant_id: str, case_id: str) -> Any:
    async with cliente(app, credencial=credencial_de(tenant_id)) as http:
        return await http.get(f"/api/inbox/{tenant_id}/cases/{case_id}")


async def test_la_lectura_del_caso_trae_el_bloque_del_ajustador_y_despierta_el_reintento(
    app: FastAPI, emisora: str
) -> None:
    vigia = _Vigia()
    adjuster_view.install(vigia)
    caso = await nuevo_caso(emisora)

    respuesta = await _ver(app, emisora, caso)

    assert respuesta.status_code == 200, respuesta.text
    bloque = respuesta.json()["adjuster"]
    assert bloque["status"] == "decided"
    assert bloque["headline"] == "Aprobado"
    assert bloque["steps"][0]["sources"][0]["ref"] == "SM-PAP-2026-D.INS.COLLISION"
    assert vigia.reintentos == [(emisora, caso, CaseState.DERIVED)]


async def test_sin_ajustador_enchufado_o_con_el_fallando_el_caso_se_lee_igual(
    app: FastAPI, emisora: str
) -> None:
    caso = await nuevo_caso(emisora)

    sin_ajustador = await _ver(app, emisora, caso)
    adjuster_view.install(_Vigia(falla=True))
    con_fallo = await _ver(app, emisora, caso)

    for respuesta in (sin_ajustador, con_fallo):
        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["adjuster"] is None


async def test_derivar_un_caso_avisa_al_ajustador_y_un_fallo_suyo_no_deshace_la_derivacion(
    emisora: str,
) -> None:
    avisados: list[tuple[str, str]] = []

    async def oyente(tenant_id: str, case_id: str) -> None:
        avisados.append((tenant_id, case_id))
        msg = "el ajustador no esta"
        raise RuntimeError(msg)

    derivation_trigger.install_derived_listener(oyente)
    caso = await nuevo_caso(emisora, estado=CaseState.CAPTURING)

    derivado = await case_context.derive_case(
        tenant_id=emisora, case_id=caso, reason=HandoffReason.RULE, turn_id=None, now=AHORA
    )

    assert derivado is True
    assert avisados == [(emisora, caso)]
    actual = await casos.get_case(emisora, caso)
    assert actual is not None
    assert actual.state is CaseState.DERIVED
