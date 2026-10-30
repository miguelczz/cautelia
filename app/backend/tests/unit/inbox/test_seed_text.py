"""La conversacion de un caso de ejemplo se ve como se escribio, sin etiquetas.

Miguel lo pidio el 2026-10-30 al ver «Soy [NOMBRE 1], póliza [PÓLIZA 1]» en un caso de
ejemplo: son datos sinteticos y ya publicados en el repositorio. La base sigue guardando
el turno redactado; lo que cambia es lo que la vista entrega, y solo para esos turnos.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from untangle import paths
from untangle.case_record.models import Channel, Speaker, TranscriptTurn
from untangle.inbox.case_view import con_texto_de_ejemplo
from untangle.synthetic_data.cases import (
    load_seeded_cases,
    seeded_case_id,
    seeded_turn_id,
    seeded_turn_texts,
)

AHORA = datetime(2026, 10, 30, 21, 0, tzinfo=UTC)

#: La forma de una etiqueta de la redaccion: `[NOMBRE 1]`, `[PLATE 2]`.
_ETIQUETA = re.compile(r"\[[A-ZÁÉÍÓÚÑ ]+ \d+\]")


def _turno(turn_id: str, texto: str) -> TranscriptTurn:
    return TranscriptTurn(
        turn_id=turn_id,
        case_id="caso",
        speaker=Speaker.INSURED,
        channel=Channel.CHAT,
        language="es",
        text_redacted=texto,
        started_at=AHORA,
    )


def test_el_turno_de_ejemplo_sale_con_su_texto_escrito() -> None:
    sembrado = _turno("seed-abc-t01", "Soy [NOMBRE 1], póliza [PÓLIZA 1].")

    (salida,) = con_texto_de_ejemplo((sembrado,), {"seed-abc-t01": "Soy Marco, póliza 23."})

    assert salida.text_redacted == "Soy Marco, póliza 23."
    assert salida.turn_id == "seed-abc-t01"


def test_el_turno_de_un_visitante_sigue_con_sus_etiquetas() -> None:
    """Es dato que pudo ser real: la vista no tiene de donde destaparlo, y no debe."""
    visitante = _turno("turn-9f2", "Soy [NOMBRE 1], póliza [PÓLIZA 1].")

    (salida,) = con_texto_de_ejemplo((visitante,), {"seed-abc-t01": "Soy Marco, póliza 23."})

    assert salida.text_redacted == "Soy [NOMBRE 1], póliza [PÓLIZA 1]."


def test_cada_turno_sembrado_del_repositorio_tiene_su_texto_y_ninguno_trae_etiquetas() -> None:
    """Los identificadores son los mismos que fija la siembra, turno por turno."""
    casos = load_seeded_cases(paths.data_dir())
    textos = seeded_turn_texts(paths.data_dir())

    assert casos
    for caso in casos:
        case_id = seeded_case_id(caso.case_key)
        for posicion, turno in enumerate(caso.transcript, start=1):
            assert textos[seeded_turn_id(case_id, posicion)] == turno.text
    assert not [texto for texto in textos.values() if _ETIQUETA.search(texto)]
