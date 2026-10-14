"""Contar las entradas del historial que dejo un actor: lo que fija el tope del visitante.

Contra PostgreSQL de verdad. Lo que importa es que la cuenta mire las cuatro cosas a la vez
--el caso, la clase de entrada, el tipo de actor y su identificador-- y que no cruce
aseguradoras: una cuenta que olvidara una de las cuatro le cortaria el paso a quien no lo
merece, o dejaria pasar a quien ya llego al tope.
"""

from __future__ import annotations

import pytest

from untangle.case_record import history
from untangle.case_record.models import Actor, ActorType, CaseChange, ChangeKind
from untangle.tenancy import api as tenancy

from .conftest import AHORA, nuevo_caso

pytestmark = pytest.mark.usefixtures("base_de_u14")

VISITANTE = Actor(actor_type=ActorType.INSURED, actor_id="demo-visitor")
OTRO_VISITANTE = Actor(actor_type=ActorType.INSURED, actor_id="otro-visitante")
AJUSTADOR = Actor(actor_type=ActorType.STAFF, actor_id="diana")


async def _entrada(
    tenant_id: str, case_id: str, actor: Actor, *, clase: ChangeKind = ChangeKind.TRIAGE_NOTED
) -> None:
    await history.append(
        tenant_id,
        CaseChange(
            change_id=history.new_change_id(),
            case_id=case_id,
            change_kind=clase,
            field_key="claim_amount" if clase is ChangeKind.TRIAGE_NOTED else None,
            actor=actor,
            detail="unset -> 100"
            if clase is ChangeKind.TRIAGE_NOTED
            else "se intento y no se pudo",
            changed_at=AHORA,
        ),
    )


async def _cuenta(tenant_id: str, case_id: str, actor: Actor) -> int:
    assert actor.actor_id is not None
    return await history.count_by_actor(
        tenant_id,
        case_id,
        kind=ChangeKind.TRIAGE_NOTED,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
    )


async def test_un_caso_sin_entradas_cuenta_cero(dos_aseguradoras: tuple[str, str]) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    assert await _cuenta(propia, caso, VISITANTE) == 0


async def test_cuenta_solo_las_de_esa_clase_y_ese_actor(
    dos_aseguradoras: tuple[str, str],
) -> None:
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)
    for _ in range(3):
        await _entrada(propia, caso, VISITANTE)
    # Lo que no es del visitante ni de esta clase: ninguna de estas suma.
    await _entrada(propia, caso, AJUSTADOR)
    await _entrada(propia, caso, OTRO_VISITANTE)
    await _entrada(propia, caso, VISITANTE, clase=ChangeKind.CLOSE_REJECTED)

    assert await _cuenta(propia, caso, VISITANTE) == 3
    assert await _cuenta(propia, caso, AJUSTADOR) == 1
    assert await _cuenta(propia, caso, OTRO_VISITANTE) == 1


async def test_no_cuenta_las_de_otro_caso(dos_aseguradoras: tuple[str, str]) -> None:
    _, propia = dos_aseguradoras
    este, otro = await nuevo_caso(propia), await nuevo_caso(propia)
    await _entrada(propia, este, VISITANTE)
    await _entrada(propia, otro, VISITANTE)
    await _entrada(propia, otro, VISITANTE)

    assert await _cuenta(propia, este, VISITANTE) == 1
    assert await _cuenta(propia, otro, VISITANTE) == 2


async def test_no_cuenta_las_de_otra_aseguradora(dos_aseguradoras: tuple[str, str]) -> None:
    ajena, propia = dos_aseguradoras
    caso_propio = await nuevo_caso(propia)
    caso_ajeno = await nuevo_caso(ajena)
    await _entrada(ajena, caso_ajeno, VISITANTE)

    assert await _cuenta(propia, caso_propio, VISITANTE) == 0
    # Y preguntando por el caso ajeno desde la sesion de la propia: la politica de fila lo
    # oculta, y la cuenta no lo ve.
    assert await _cuenta(propia, caso_ajeno, VISITANTE) == 0


async def test_cuenta_dentro_de_la_transaccion_de_quien_va_a_escribir(
    dos_aseguradoras: tuple[str, str],
) -> None:
    """Con la sesion de quien escribe ve lo que ella misma acaba de anexar, aun sin confirmar."""
    _, propia = dos_aseguradoras
    caso = await nuevo_caso(propia)

    async with tenancy.session_for(propia) as sesion:
        await history.append(
            propia,
            CaseChange(
                change_id=history.new_change_id(),
                case_id=caso,
                change_kind=ChangeKind.TRIAGE_NOTED,
                field_key="claim_amount",
                actor=VISITANTE,
                detail="unset -> 100",
                changed_at=AHORA,
            ),
            en=sesion,
        )
        dentro = await history.count_by_actor(
            propia,
            caso,
            kind=ChangeKind.TRIAGE_NOTED,
            actor_type=ActorType.INSURED,
            actor_id="demo-visitor",
            en=sesion,
        )

    assert dentro == 1
