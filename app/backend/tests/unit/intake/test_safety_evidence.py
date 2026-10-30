"""Que cuenta como hablar de heridos (2026-10-10).

El reconocedor es ancho a proposito: dejar pasar de mas devuelve la conducta de
antes, y cerrar de mas solo cuesta volver a preguntar.
"""

from __future__ import annotations

import pytest

from untangle.orchestration.nodes.intake.safety_evidence import mentions_injuries


@pytest.mark.parametrize(
    "texto",
    [
        "nadie salió herido",
        "Estamos todos bien, solo fue el susto",
        "mi esposa quedó con dolor en el cuello",
        "se llevaron al taxista en ambulancia",
        "No hubo lesionados",
        "ninguno",
        "nobody was hurt",
        "everyone is okay",
        "my son has whiplash",
        "we're all fine, no injuries",
    ],
)
def test_reconoce_a_quien_habla_de_heridos_o_de_como_quedaron(texto: str) -> None:
    assert mentions_injuries(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "hola, ayer un taxi me choco por detras en la avenida 80 con la 33",
        "Soy Natalia Henao Rendón, mi póliza es POL-11",
        "me rayaron el carro en el parqueadero",
        "fue como a las siete de la noche",
        "yesterday a taxi rear-ended me at the light",
        "my policy is POL-21",
    ],
)
def test_un_choque_contado_sin_hablar_de_las_personas_no_cuenta(texto: str) -> None:
    assert not mentions_injuries(texto)
