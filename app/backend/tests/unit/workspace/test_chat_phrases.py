"""Toda clave que el servidor puede mandar al chat, la pantalla sabe decirla (2026-10-12).

El servidor estreno `compliance.handoff.adjuster_review_inquiry` y la tabla de la
pantalla no la tenia: quien pidio un ajustador en una consulta leyo «tuve un problema
para responder eso» con el caso ya derivado. El chequeo existia pero solo miraba las
frases de degradacion de los nodos; ahora mira tambien las que declara `turn.py` y la
del cierre por insultos.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from untangle.workspace import chat_phrases

#: Una tabla con la forma de la real, para romperla sin tocar la verdadera.
TABLA = """\
const FRASES: Partial<Record<CopyKey, Message>> = {{
{entradas}
}};
"""


def _arbol_con_tabla(raiz: Path, claves: list[str], *, comentario: str = "") -> Path:
    tabla = raiz / chat_phrases.TABLA_DEL_CHAT
    tabla.parent.mkdir(parents=True)
    entradas = "\n".join(f'  "{clave}": (t) => t("{clave}"),' for clave in claves)
    tabla.write_text(TABLA.format(entradas=entradas) + comentario, encoding="utf-8")
    return raiz


def test_la_pantalla_real_sabe_decir_todo_lo_que_el_servidor_manda() -> None:
    assert chat_phrases.faltantes() == []


def test_lo_que_se_comprueba_incluye_las_claves_que_fallaron_en_pantalla() -> None:
    """El control positivo: sin esto, una lista vacia haria pasar el chequeo sin mirar nada."""
    claves = chat_phrases.claves_que_el_servidor_manda()

    assert "compliance.handoff.adjuster_review_inquiry" in claves
    assert "compliance.handoff.adjuster_review" in claves
    assert "intake.tone.closing_abuse" in claves
    assert "chat.turn.waiting" in claves
    assert "chat.turn.error" in claves
    # Las dos frases propias de la llamada no pasan por esta pantalla.
    assert "orchestration.turn.waiting" not in claves
    assert "orchestration.turn.error" not in claves


def test_una_tabla_sin_la_derivacion_de_la_consulta_la_reporta(tmp_path: Path) -> None:
    """El defecto de este dia, reproducido: la tabla de antes no tenia la clave."""
    completa = chat_phrases.claves_que_el_servidor_manda()
    sin_ella = [c for c in completa if c != "compliance.handoff.adjuster_review_inquiry"]

    ausentes = chat_phrases.faltantes(_arbol_con_tabla(tmp_path, sin_ella))

    assert ausentes == ["compliance.handoff.adjuster_review_inquiry"]


def test_una_clave_nombrada_solo_en_un_comentario_no_cuenta(tmp_path: Path) -> None:
    completa = chat_phrases.claves_que_el_servidor_manda()
    sin_ella = [c for c in completa if c != "intake.tone.closing_abuse"]

    ausentes = chat_phrases.faltantes(
        _arbol_con_tabla(tmp_path, sin_ella, comentario='// "intake.tone.closing_abuse"\n')
    )

    assert ausentes == ["intake.tone.closing_abuse"]


def test_sin_la_tabla_el_chequeo_falla_en_vez_de_pasar_en_verde(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        chat_phrases.faltantes(tmp_path)
