"""Mientras suena la apertura no se escucha (decision de Miguel, 2026-10-14).

«Mientras ella hable no debe escuchar, obviamente tampoco se puede interrumpir, ella deja de
hablar y de alli comienza todo». Lo que se prueba aqui es la pieza que decide que entra
(`CallRunner._sin_la_voz_de_la_agente`), sin base de datos: el motor es un doble con solo la
hora en que la apertura termina de sonar. Que el ciclo entero no la corte ni la repita esta en
`tests/integration/u16/test_call_loop.py`.
"""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest

from untangle import observability
from untangle.providers.ports import ExternalText, SpeechStarted, Transcript, WordHypothesis
from untangle.voice.loop import CallRunner

if TYPE_CHECKING:
    from untangle.voice.call import CallEngine

#: Cuando llego el primer trozo de audio: el segundo cero del reconocedor.
INICIO = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
#: La apertura termina de sonar diez segundos despues.
FIN_DE_LA_APERTURA = INICIO + timedelta(seconds=10)
DESCARTE = "voice.heard_during_opening_discarded"


@dataclass
class _Motor:
    """Lo unico del motor que mira el filtro: cuando termina de sonar la apertura."""

    disclosed_at: datetime | None = None
    call: SimpleNamespace = field(
        default_factory=lambda: SimpleNamespace(tenant_id="tenant-x", call_id="call-1")
    )


def _ciclo(motor: _Motor) -> CallRunner:
    ciclo = CallRunner(
        engine=cast("CallEngine", motor),
        channel=cast("Any", None),
        speech=cast("Any", None),
        now=lambda: FIN_DE_LA_APERTURA + timedelta(seconds=30),
        max_call=timedelta(seconds=180),
        warn_at=timedelta(seconds=30),
    )
    ciclo._flujo_empezo_a = INICIO
    return ciclo


def _oido(texto: str, *, desde: float, final: bool = True) -> Transcript:
    """Un transcrito cuyas palabras empiezan en `desde` segundos de audio, una cada 0,35 s."""
    palabras = tuple(
        WordHypothesis(
            text=ExternalText(palabra),
            start_s=desde + i * 0.35,
            end_s=desde + i * 0.35 + 0.3,
            confidence=0.9,
        )
        for i, palabra in enumerate(texto.split())
    )
    return Transcript(text=ExternalText(texto), is_final=final, words=palabras)


@pytest.fixture
def eventos() -> Iterator[io.StringIO]:
    salida = io.StringIO()
    observability.set_stream(salida)
    yield salida
    observability.set_stream(sys.stdout)


def _descartes(salida: io.StringIO) -> list[dict[str, object]]:
    lineas = (json.loads(linea) for linea in salida.getvalue().splitlines() if linea.strip())
    return [e for e in lineas if e.get("event") == DESCARTE]


def test_mientras_la_apertura_se_envia_no_entra_nada(eventos: io.StringIO) -> None:
    """Todavia sin hora de fin: lo que se oiga, con o sin hora propia, es durante."""
    ciclo = _ciclo(_Motor(disclosed_at=None))

    lejos = _oido("wait I need to correct something", desde=40)
    assert ciclo._sin_la_voz_de_la_agente(lejos) is None
    assert ciclo._sin_la_voz_de_la_agente(SpeechStarted(at_s=40)) is None
    assert ciclo._sin_la_voz_de_la_agente(_oido("hello", desde=1, final=False)) is None
    # Un evento por cada final descartado, con cuantas palabras y nunca cuales.
    (descarte,) = _descartes(eventos)
    assert descarte["words"] == 6
    assert "wait" not in json.dumps(descarte)


def test_lo_que_termino_antes_del_fin_de_la_apertura_no_entra(eventos: io.StringIO) -> None:
    ciclo = _ciclo(_Motor(disclosed_at=FIN_DE_LA_APERTURA))
    # Palabras de 2,0 a 4,75 s: todo mientras sonaba.
    alo = _oido("hola me escucha tuve un choque y necesito", desde=2.0)

    assert ciclo._sin_la_voz_de_la_agente(alo) is None
    assert [e["words"] for e in _descartes(eventos)] == [8]


def test_lo_dicho_despues_del_fin_de_la_apertura_entra_entero(eventos: io.StringIO) -> None:
    ciclo = _ciclo(_Motor(disclosed_at=FIN_DE_LA_APERTURA))
    despues = _oido("I was rear-ended this morning", desde=10.5)

    assert ciclo._sin_la_voz_de_la_agente(despues) is despues
    assert _descartes(eventos) == []


def test_una_frase_que_empezo_encima_y_termino_despues_entra_entera(
    eventos: io.StringIO,
) -> None:
    """Cortarle el principio a quien siguio hablando le haria repetirse."""
    ciclo = _ciclo(_Motor(disclosed_at=FIN_DE_LA_APERTURA))
    # Palabras de 9,0 a 11,05 s: empieza encima de la apertura y termina despues.
    pegada = _oido("hello I had an accident today", desde=9.0)

    assert ciclo._sin_la_voz_de_la_agente(pegada) is pegada
    assert _descartes(eventos) == []


def test_la_senal_de_voz_cuenta_por_su_instante(eventos: io.StringIO) -> None:
    ciclo = _ciclo(_Motor(disclosed_at=FIN_DE_LA_APERTURA))
    antes = SpeechStarted(at_s=9.9)
    despues = SpeechStarted(at_s=10.1)

    assert ciclo._sin_la_voz_de_la_agente(antes) is None
    assert ciclo._sin_la_voz_de_la_agente(despues) is despues
    # Las senales no dejan evento: llegan por decenas y no dicen nada.
    assert _descartes(eventos) == []


def test_sin_hora_por_palabra_y_con_la_apertura_dicha_no_lo_descarta_esta_regla(
    eventos: io.StringIO,
) -> None:
    """Sin tiempos no se sabe cuando se dijo; de eso se encarga el filtro del eco."""
    ciclo = _ciclo(_Motor(disclosed_at=FIN_DE_LA_APERTURA))
    sin_tiempos = Transcript(text=ExternalText("I had an accident"), is_final=True, words=())

    assert ciclo._sin_la_voz_de_la_agente(sin_tiempos) is sin_tiempos
    assert _descartes(eventos) == []
