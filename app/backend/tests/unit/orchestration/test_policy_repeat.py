"""Que ya se pidio repetir la poliza sobrevive entre turnos del punto de control (2026-10-13).

La repeticion cifra por cifra se pide **una sola vez** por conversacion. El nodo de cada turno
escribe `intake_policy_repeat_asked` y casi todo lo que escribe reemplaza lo del turno anterior:
si este valor tambien se reemplazara, el turno siguiente al que lo pidio lo escribiria `False`
por omision y la agente volveria a pedirlo.

Funcion pura, sin base y sin modelo.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from untangle.orchestration import turn
from untangle.orchestration.nodes.intake.blocks import Block
from untangle.orchestration.nodes.intake.node import IntakeNodeOutput


def _previo(**writes: object) -> Any:
    return cast(Any, SimpleNamespace(node_writes=writes))


def _salida(**cambios: Any) -> IntakeNodeOutput:
    base: dict[str, Any] = {
        "intake_next_block": Block.WHAT_HAPPENED,
        "intake_extracted": (),
        "intake_awaiting_confirmation": None,
        "intake_readback_resolved": None,
        "intake_response_key": "intake.question.what_happened",
        "intake_response_text": "¿Qué pasó?",
        "intake_session_ended": None,
    }
    return IntakeNodeOutput(**{**base, **cambios})


@pytest.mark.parametrize(
    ("guardado", "pedida"),
    [
        ({"intake_policy_repeat_asked": True}, True),
        ({"intake_policy_repeat_asked": False}, False),
        ({"intake_policy_repeat_asked": None}, False),
        ({"intake_policy_repeat_asked": "True"}, False),
        ({}, False),
    ],
)
def test_solo_un_true_guardado_cuenta_como_ya_pedida(
    guardado: dict[str, object], pedida: bool
) -> None:
    assert turn._poliza_repetida(_previo(**guardado)) is pedida


def test_lo_que_se_pidio_en_este_turno_se_guarda() -> None:
    nuevos = turn._writes_del_turno(_previo(), _salida(intake_policy_repeat_asked=True))

    assert nuevos["intake_policy_repeat_asked"] is True


def test_un_turno_que_no_la_pide_no_borra_que_ya_se_pidio() -> None:
    previo = _previo(intake_policy_repeat_asked=True, intake_next_block=Block.SAFETY)

    nuevos = turn._writes_del_turno(previo, _salida())

    assert nuevos["intake_policy_repeat_asked"] is True
    # Lo demas si se reemplaza por lo que escribio el nodo.
    assert nuevos["intake_next_block"] is Block.WHAT_HAPPENED


def test_si_nunca_se_pidio_queda_sin_pedir() -> None:
    nuevos = turn._writes_del_turno(_previo(otra_cosa="se conserva"), _salida())

    assert nuevos["intake_policy_repeat_asked"] is False
    assert nuevos["otra_cosa"] == "se conserva"
