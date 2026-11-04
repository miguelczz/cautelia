"""El ajustador de IA enchufado a la raiz: cuando se enchufa, cuando no, y como registra su decision."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from typing import Any, get_args

import pytest

from untangle.adjuster.models import RunStatus, SourceKind, StepId
from untangle.adjuster.ports import DecisionToRecord
from untangle.case_record.crypto import Cipher
from untangle.case_record.models import ActorType
from untangle.inbox import adjuster_view
from untangle.inbox import decision as inbox_decision
from untangle.inbox.actions import InboxAction
from untangle.orchestration import derivation_trigger, transcript_writer
from untangle.providers import config as provider_config
from untangle.providers.ports import Vector
from untangle.server import adjuster_wiring
from untangle.settings import Settings
from untangle.tenancy import api as tenancy

BASE = "postgresql+asyncpg://prueba:prueba@localhost:5432/prueba"
CLAVE = "sk-ant-api03-clave-de-prueba"


@pytest.fixture(autouse=True)
def _sin_enchufes() -> Iterator[None]:
    adjuster_wiring.uninstall()
    yield
    adjuster_wiring.uninstall()


async def _embed(textos: Sequence[str]) -> list[Vector]:
    return [(0.0,) for _ in textos]


def _enchufar(settings: Settings, *, cifrador: bool = True) -> Any:
    return adjuster_wiring.install(
        settings,
        provider_config.load(),
        cipher=Cipher.__new__(Cipher) if cifrador else None,
        embed=_embed,
    )


def _enchufado() -> bool:
    return derivation_trigger._OYENTE is not None and adjuster_view._VIGIA is not None


def test_con_base_clave_y_cifrador_se_enchufan_el_oyente_y_el_vigia() -> None:
    servicio = _enchufar(Settings(env="ci", database_url=BASE, anthropic_api_key_adjuster=CLAVE))

    assert servicio is not None
    assert _enchufado()


@pytest.mark.parametrize(
    ("ajustes", "cifrador"),
    [
        (Settings(env="ci", anthropic_api_key_adjuster=CLAVE), True),
        (Settings(env="ci", database_url=BASE), True),
        (Settings(env="ci", database_url=BASE, anthropic_api_key_adjuster=CLAVE), False),
    ],
    ids=["sin base", "sin clave del uso", "sin cifrador"],
)
def test_sin_algo_de_lo_que_necesita_no_se_enchufa_nada_y_el_producto_sigue_como_antes(
    ajustes: Settings, cifrador: bool
) -> None:
    assert _enchufar(ajustes, cifrador=cifrador) is None
    assert not _enchufado()


def test_una_aplicacion_nueva_sin_clave_desenchufa_lo_que_dejo_la_anterior() -> None:
    _enchufar(Settings(env="ci", database_url=BASE, anthropic_api_key_adjuster=CLAVE))
    assert _enchufado()

    _enchufar(Settings(env="ci", database_url=BASE))

    assert not _enchufado()


async def test_la_decision_se_registra_firmada_por_el_ajustador_de_ia_y_no_por_una_persona(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llamadas: list[dict[str, Any]] = []
    aseguradora = tenancy.load().available[0]

    async def decide(tenant: Any, **kwargs: Any) -> None:
        llamadas.append({"tenant": tenant, **kwargs})

    monkeypatch.setattr(inbox_decision, "decide", decide)
    monkeypatch.setattr(tenancy, "require", lambda tenant_id: aseguradora)

    await adjuster_wiring._registrar(
        DecisionToRecord(
            tenant_id=aseguradora.tenant_id,
            case_id="caso-1",
            action=InboxAction.APPROVE,
            comment="Aprobado: el choque esta cubierto.",
            idempotency_key="adjuster-caso-1",
        )
    )

    (llamada,) = llamadas
    assert llamada["adjuster_ai"] is True
    assert llamada["principal_id"] is None
    assert llamada["idempotency_key"] == "adjuster-caso-1"
    assert llamada["action"] is InboxAction.APPROVE
    assert llamada["now"] <= datetime.now(UTC)


def test_los_vocabularios_de_la_bandeja_son_los_del_ajustador() -> None:
    """La bandeja no puede importar los enums del ajustador: sus `Literal` se repiten aqui."""
    campos = adjuster_view.AdjusterRunOut.model_fields
    paso = adjuster_view.AdjusterStepOut.model_fields
    fuente = adjuster_view.AdjusterSourceOut.model_fields

    assert set(get_args(campos["status"].annotation)) == {e.value for e in RunStatus}
    assert set(get_args(paso["id"].annotation)) == {e.value for e in StepId}
    assert set(get_args(fuente["kind"].annotation)) == {e.value for e in SourceKind}


def test_el_actor_del_ajustador_de_ia_no_lleva_identificador_de_persona() -> None:
    actor = inbox_decision.actor_of(principal_id=None, adjuster_ai=True)

    assert actor.actor_type is ActorType.ADJUSTER_AI
    assert actor.actor_id is None


@pytest.mark.parametrize(
    ("actor", "esperado"), [(ActorType.ADJUSTER_AI, True), (ActorType.STAFF, False)]
)
async def test_el_aviso_al_chat_solo_omite_la_explicacion_cuando_firmo_el_ajustador_de_ia(
    monkeypatch: pytest.MonkeyPatch, actor: ActorType, esperado: bool
) -> None:
    from untangle.chat import notice as chat_notice
    from untangle.server import composition

    avisos: list[chat_notice.Decision] = []

    async def aviso(decision: chat_notice.Decision, **_kw: Any) -> chat_notice.Notice:
        avisos.append(decision)
        return chat_notice.Notice(
            copy_key=chat_notice.ADJUSTER_AI,
            text="Tu caso ya tiene una decision.",
            decision_ref="r-1",
        )

    async def decir(*_a: Any, **_k: Any) -> None:
        return None

    monkeypatch.setattr(chat_notice, "for_decision", aviso)
    monkeypatch.setattr(transcript_writer, "say_without_turn", decir)

    await composition._avisar_la_decision_al_chat(
        inbox_decision.DecisionMade(
            tenant_id="sunmeadow",
            case_id="caso-1",
            case_number="AP-1",
            resolution="approved",
            comment="Aprobado.",
            ref="r-1",
            language="es",
            actor_type=actor,
        )
    )

    (enviado,) = avisos
    assert enviado.by_adjuster_ai is esperado
