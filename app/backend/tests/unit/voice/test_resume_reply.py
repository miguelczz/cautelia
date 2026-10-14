"""Que contesta la persona a "¿seguimos con ese?" (BR6.4), leido sin base de datos."""

from __future__ import annotations

import pytest

from untangle.voice import resume
from untangle.voice.resume import Reply

pytestmark = pytest.mark.usefixtures("catalogo_cargado")


@pytest.mark.parametrize(
    "dicho",
    ["sí", "Sí, ese", "sí, ese mismo", "claro, sigamos", "ok", "yes", "yes, that one", "por favor"],
)
def test_un_si_a_secas_sigue_con_el_caso(dicho: str) -> None:
    assert resume.reply_to(dicho, language="es") is Reply.CONTINUE


@pytest.mark.parametrize(
    "dicho",
    [
        "no",
        "No, es otra cosa",
        "quiero empezar de nuevo",
        "tuve otro accidente",
        "no, I want to start over",
        "I want to start over",
        "it's a different accident",
    ],
)
def test_un_no_o_pedir_uno_nuevo_abre_un_caso_nuevo(dicho: str) -> None:
    assert resume.reply_to(dicho, language="es") is Reply.NEW_CASE


@pytest.mark.parametrize(
    "dicho",
    [
        "fue ayer en la calle diez",
        "sí, tuve un choque",
        "tengo otra cosa que agregar",
        "a mi me chocaron por detrás",
    ],
)
def test_contar_algo_del_caso_es_seguir_con_el_y_ya_es_su_turno(dicho: str) -> None:
    """Antes todo lo que no era un si abria un caso nuevo, y quien contestaba contando el
    accidente perdia el reporte que habia empezado."""
    assert resume.reply_to(dicho, language="es") is Reply.WITH_CONTENT


def test_un_si_con_pedir_uno_nuevo_gana_lo_segundo() -> None:
    assert resume.reply_to("sí, pero empezar de nuevo", language="es") is Reply.NEW_CASE
