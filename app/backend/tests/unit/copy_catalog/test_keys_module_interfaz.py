"""Los dos modulos del catalogo que genera U6 para la interfaz (C-28)."""

from __future__ import annotations

from untangle.copy_catalog import keys_module
from untangle.copy_catalog.keys_module import render_characters_module, render_texts_module
from untangle.copy_catalog.models import CopyEntry, Surface


def _entrada(clave: str, idioma: str, texto: str) -> CopyEntry:
    return CopyEntry(key=clave, locale=idioma, text=texto, surface=Surface.SYSTEM)  # type: ignore[arg-type]


def test_las_frases_salen_por_idioma_ordenadas_y_escapadas() -> None:
    entradas = {
        ("home.b", "es"): _entrada("home.b", "es", 'Dice "hola"'),
        ("home.a", "es"): _entrada("home.a", "es", "Ñandú"),
        ("home.a", "en"): _entrada("home.a", "en", "Rhea"),
    }

    espanol = render_texts_module(entradas, "es")
    ingles = render_texts_module(entradas, "en")

    assert espanol.startswith("// GENERADO. No editar a mano.")
    # Un modulo por idioma (2026-10-09), cada uno con solo sus frases, ordenadas.
    assert espanol.index('["home.a", "Ñandú"]') < espanol.index('["home.b", "Dice \\"hola\\""]')
    assert "Rhea" not in espanol
    assert '["home.a", "Rhea"]' in ingles
    assert "home.b" not in ingles
    assert render_texts_module(dict(reversed(list(entradas.items()))), "es") == espanol


def test_el_catalogo_puede_pasar_de_mil_frases_sin_un_literal_gigante() -> None:
    """TypeScript se rinde (TS2590) ante un literal de mas de mil tuplas con clave literal.

    El catalogo estaba en 994 claves y la 1.001 rompia `tsc` sin tocar el codigo que lo lee.
    El modulo sale en tramos con su tipo declarado, y ninguno pasa del tope: lo que
    TypeScript reduce es un tramo, no el catalogo entero.
    """
    total = keys_module.FRASES_POR_TRAMO * 5 + 7
    entradas = {
        (f"k.{n:05d}", "es"): _entrada(f"k.{n:05d}", "es", f"frase {n}") for n in range(total)
    }

    generado = render_texts_module(entradas, "es")

    assert generado.count("] = [\n") == 6, "debia salir en seis tramos"
    assert "new Map<CopyKey, string>([...TRAMO_0, ...TRAMO_1, ...TRAMO_2" in generado
    for n in (0, keys_module.FRASES_POR_TRAMO, total - 1):
        assert f'["k.{n:05d}", "frase {n}"]' in generado
    assert generado.count('", "frase ') == total, "alguna frase se perdio o se repitio"
    for tramo in generado.split("const TRAMO_")[1:]:
        assert tramo.count('", "frase ') <= keys_module.FRASES_POR_TRAMO


def test_un_idioma_sin_frases_sigue_siendo_un_modulo_valido() -> None:
    generado = render_texts_module({}, "en")

    assert "const TRAMO_0: readonly (readonly [CopyKey, string])[] = [\n];" in generado
    assert "new Map<CopyKey, string>([...TRAMO_0])" in generado


def test_la_tabla_de_caracteres_es_cerrada_literal_y_sin_repetidos() -> None:
    generado = render_characters_module(
        ["insurer.character.b", "insurer.character.a", "insurer.character.b"]
    )

    assert generado.startswith("// GENERADO. No editar a mano.")
    assert generado.count('(t) => t("insurer.character.a")') == 1
    assert generado.count('(t) => t("insurer.character.b")') == 1
    assert generado.index("insurer.character.a") < generado.index('"insurer.character.b"')


def test_sin_aseguradoras_con_caracter_la_tabla_queda_vacia() -> None:
    assert (
        "new Map<\n  string,\n  (t: ResolveCopy) => string\n>([\n]);"
        in render_characters_module([])
    )
