"""Que contesta la persona a "dejamos tu caso guardado, o se lo paso a un ajustador"."""

from __future__ import annotations

import pytest

from untangle.voice.offer_reply import OfferReply, classify

pytestmark = pytest.mark.usefixtures("catalogo_cargado")


@pytest.mark.parametrize(
    "dicho",
    [
        "pásalo",
        "sí, pásalo",
        "al ajustador",
        "que lo revise un ajustador",
        "pásaselo a un ajustador",
        "quiero hablar con un ajustador",
        "pass it to the adjuster",
        "the adjuster, please",
    ],
)
async def test_pedir_el_ajustador(dicho: str) -> None:
    assert await classify(dicho, language="es") is OfferReply.ADJUSTER


@pytest.mark.parametrize(
    "dicho",
    [
        "guárdalo",
        "déjalo así",
        "déjalo guardado",
        "luego sigo",
        "sigo después",
        "sí, guárdalo",
        "keep it saved",
        "I'll finish later",
        "save it",
    ],
)
async def test_pedir_dejarlo_guardado(dicho: str) -> None:
    assert await classify(dicho, language="es") is OfferReply.SAVE


@pytest.mark.parametrize("dicho", ["sí", "no", "claro", "No, gracias", "yes"])
async def test_un_si_o_un_no_a_secas_no_elige_ninguna_de_las_dos(dicho: str) -> None:
    assert await classify(dicho, language="es") is OfferReply.CHOOSE


@pytest.mark.parametrize(
    "dicho",
    [
        "el golpe fue en la parte de atrás",
        "me chocaron esta mañana por la avenida",
        "dejé el carro estacionado frente a mi casa",
        "la guardia de tránsito llegó rápido",
        "tuve el choque dos horas después de salir del trabajo",
    ],
)
async def test_contar_algo_del_caso_es_otra_cosa_y_la_conversacion_sigue(dicho: str) -> None:
    assert await classify(dicho, language="es") is OfferReply.OTHER


@pytest.mark.parametrize(
    ("dicho", "esperado"),
    [
        ("guárdalo, no lo pases al ajustador", OfferReply.SAVE),
        ("pásalo, no lo guardes", OfferReply.ADJUSTER),
        ("no quiero al ajustador, guárdalo", OfferReply.SAVE),
        ("don't keep it, pass it to the adjuster", OfferReply.ADJUSTER),
    ],
)
async def test_la_negacion_decide_cuando_el_turno_nombra_las_dos(
    dicho: str, esperado: OfferReply
) -> None:
    assert await classify(dicho, language="es") is esperado


async def test_si_nombra_las_dos_sin_negar_ninguna_no_se_elige() -> None:
    """Adivinar entre derivar un caso y dejarlo guardado seria elegir por la persona."""
    assert await classify("guárdalo y pásalo al ajustador", language="es") is OfferReply.OTHER
