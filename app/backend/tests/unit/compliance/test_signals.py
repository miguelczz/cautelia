"""Las tres senales del turno: peticion de persona, identidad y emergencia (BR2.1, BR2.4, BR3.1, BR3.2).

Cada prueba mira **las tres** senales a la vez y no solo la que le toca: una
pregunta de identidad que levantara tambien la peticion de persona derivaria un
caso que nadie pidio derivar, y eso tambien es un fallo.
"""

from __future__ import annotations

import pytest

from untangle.compliance.controls import patterns, signals
from untangle.compliance.controls.signals import TurnSignals

NINGUNA = TurnSignals(human_request=False, identity_question=False, emergency=False)
PERSONA = TurnSignals(human_request=True, identity_question=False, emergency=False)
IDENTIDAD = TurnSignals(human_request=False, identity_question=True, emergency=False)
EMERGENCIA = TurnSignals(human_request=False, identity_question=False, emergency=True)


@pytest.mark.parametrize(
    "turno",
    [
        "Quisiera comunicarme con un asesor, por favor.",
        "¿Me comunica con un agente?",
        "I'd prefer to talk with a real person.",
        "Connect me to an adjuster, please.",
    ],
)
def test_la_peticion_directa_levanta_solo_la_peticion(
    biblioteca: patterns.PatternLibrary, turno: str
) -> None:
    assert signals.read_signals(turno, library=biblioteca) == PERSONA


@pytest.mark.parametrize(
    "turno",
    [
        # BR2.1: en cualquier turno, incluida la mitad de una pregunta.
        "La placa es la que le dije... oiga, mejor que me llame alguien.",
        "Is there somebody else I could speak to?",
        # RT-15: la peticion a medias en el otro idioma.
        "Can I hablar con alguien de la aseguradora?",
    ],
)
def test_la_peticion_indirecta_o_mezclada_tambien_se_levanta(
    biblioteca: patterns.PatternLibrary, turno: str
) -> None:
    assert signals.read_signals(turno, library=biblioteca).human_request


@pytest.mark.parametrize(
    "turno",
    [
        "El testigo era una persona mayor.",
        "Hablé con alguien de la grúa y ya vienen.",
        "I spoke to someone from the police already.",
        "My husband wants to know if the claim is open.",
    ],
)
def test_nombrar_a_una_persona_sin_pedirla_no_levanta_nada(
    biblioteca: patterns.PatternLibrary, turno: str
) -> None:
    assert signals.read_signals(turno, library=biblioteca) == NINGUNA


@pytest.mark.parametrize(
    "turno",
    ["¿Es usted un robot?", "¿Estamos hablando con una máquina?", "Is this a real person?"],
)
def test_la_pregunta_de_identidad_levanta_solo_la_identidad(
    biblioteca: patterns.PatternLibrary, turno: str
) -> None:
    """BR2.4: responder con la frase fija y seguir, no derivar."""
    assert signals.read_signals(turno, library=biblioteca) == IDENTIDAD


@pytest.mark.parametrize(
    "turno",
    [
        "Mi esposa no respira bien, está pálida.",
        "The passenger is unconscious and not moving.",
        # Dicha de paso, a mitad de otra cosa.
        "El carro es gris y... ay, hay alguien herido de gravedad.",
    ],
)
def test_la_emergencia_se_levanta_aunque_llegue_de_paso(
    biblioteca: patterns.PatternLibrary, turno: str
) -> None:
    assert signals.read_signals(turno, library=biblioteca) == EMERGENCIA


@pytest.mark.parametrize(
    "turno",
    [
        "No, nadie está sangrando, fue un golpecito.",
        "No hay heridos graves, solo el susto.",
        "He's not bleeding, we're all fine.",
        "No serious injuries, just the bumper.",
    ],
)
def test_la_negacion_apaga_la_emergencia_que_toca(
    biblioteca: patterns.PatternLibrary, turno: str
) -> None:
    """BR3.2: "sangrando" dentro de "nadie esta sangrando" no cuenta."""
    assert signals.read_signals(turno, library=biblioteca) == NINGUNA


@pytest.mark.parametrize(
    "turno",
    [
        "Todos estamos bien menos mi hija, que no reacciona.",
        "We're all fine except my daughter, she's not responding.",
        "No hay heridos graves, pero el conductor de la moto no se mueve.",
        "Nobody got hurt in our car, but the cyclist is bleeding a lot.",
    ],
)
def test_una_negacion_no_apaga_a_un_herido_grave_nombrado_en_el_mismo_turno(
    biblioteca: patterns.PatternLibrary, turno: str
) -> None:
    """BR3.2 enmendada el 2026-09-21: la negacion apaga solo lo que toca."""
    assert signals.emergency_match(turno, library=biblioteca) is not None
    assert signals.read_signals(turno, library=biblioteca).emergency
