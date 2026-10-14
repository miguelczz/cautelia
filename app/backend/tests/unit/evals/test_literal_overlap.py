"""Pruebas del tramo literal compartido entre dos textos (`literal_overlap`).

Sin modelo y sin archivos: es comparacion de cadenas. Lo que importa es la frontera, porque
de ella depende que copiar un prompt falle y que hablar con palabras propias no.
"""

from __future__ import annotations

import pytest

from untangle.evals.literal_overlap import fold, longest_shared_run


def test_plegar_perdona_mayusculas_tildes_espacios_y_marcas_de_markdown() -> None:
    original = "- Nunca  afirmas **ni** niegas `cobertura`, más allá de la ÓRDEN."

    assert fold(original) == "nunca afirmas ni niegas cobertura, mas alla de la orden."


def test_plegar_quita_la_vineta_y_la_numeracion_del_principio_de_la_linea() -> None:
    assert fold("- uno\n* dos\n1. tres\n2) cuatro") == "uno dos tres cuatro"
    # Un guion a mitad de linea no es una vineta: es parte de la frase.
    assert fold("la poliza - la suya") == "la poliza - la suya"


def test_el_tramo_se_mide_en_caracteres_seguidos() -> None:
    texto = "abc 123456789 xyz"
    referencia = "otra cosa 123456789 distinta"

    assert longest_shared_run(texto, referencia, min_chars=5) == len(" 123456789 ")


def test_en_la_frontera_un_caracter_menos_no_cuenta_y_el_minimo_exacto_si() -> None:
    referencia = "x" + "a" * 60 + "y"

    assert longest_shared_run("a" * 59, referencia, min_chars=60) == 0
    assert longest_shared_run("a" * 60, referencia, min_chars=60) == 60


def test_una_palabra_cambiada_a_la_mitad_rompe_el_tramo() -> None:
    """Parafrasear no es filtrar: cambiar una palabra corta la copia en dos."""
    referencia = "a" * 40 + " b " + "c" * 40
    copia_exacta = referencia
    copia_con_un_cambio = "a" * 40 + " X " + "c" * 40

    assert longest_shared_run(copia_exacta, referencia, min_chars=50) == len(referencia)
    assert longest_shared_run(copia_con_un_cambio, referencia, min_chars=50) == 0


def test_el_tramo_mas_largo_gana_cuando_aparece_mas_de_una_vez() -> None:
    referencia = "kkkkkkkkkk-corto-kkkkkkkkkk-y-este-es-el-largo-de-verdad"
    texto = "este-es-el-largo-de-verdad"

    # La ventana inicial aparece una sola vez; lo que se mide es hasta donde llega.
    assert longest_shared_run(texto, referencia, min_chars=8) == len(texto)


def test_un_texto_mas_corto_que_el_minimo_no_comparte_nada() -> None:
    assert longest_shared_run("corto", "corto y largo", min_chars=10) == 0
    assert longest_shared_run("", "algo", min_chars=3) == 0


def test_un_minimo_menor_que_uno_no_tiene_sentido() -> None:
    with pytest.raises(ValueError, match="al menos un caracter"):
        longest_shared_run("a", "a", min_chars=0)
