"""Los datos que el modelo lee: delimitados, escapados y con las etiquetas que la instruccion nombra."""

from __future__ import annotations

import re

import pytest

from untangle.adjuster import prompting
from untangle.base import Locale
from untangle.providers import prompts


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_toda_etiqueta_de_datos_que_la_instruccion_nombra_existe_y_viceversa(
    idioma: Locale,
) -> None:
    """Una regla sobre una etiqueta que no existe es una instruccion sobre nada."""
    instruccion = prompts.load_system_instruction("adjuster", idioma).text
    etiquetas = set(prompting.DATA_LABELS[idioma].values())
    nombradas = set(re.findall(r"<([a-z_]+)>", instruccion))

    assert nombradas, "la instruccion nombra las etiquetas de los datos"
    assert nombradas <= etiquetas, (
        f"la instruccion nombra etiquetas inexistentes: {nombradas - etiquetas}"
    )
    # Las que el contenido manda y la instruccion debe explicar.
    for clave in prompting.LABELS_THE_INSTRUCTION_MUST_NAME:
        assert prompting.DATA_LABELS[idioma][clave] in nombradas


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_las_dos_instrucciones_de_la_investigacion_existen_y_piden_el_formato_fijo(
    idioma: Locale,
) -> None:
    instruccion = prompts.load_system_instruction("adjuster_research", idioma).text

    assert "VALUE_COP:" in instruccion
    assert "CONFIDENCE:" in instruccion


def test_los_dos_idiomas_de_las_etiquetas_tienen_las_mismas_claves() -> None:
    assert prompting.DATA_LABELS["es"].keys() == prompting.DATA_LABELS["en"].keys()


def test_el_texto_de_fuera_no_puede_cerrar_una_etiqueta() -> None:
    assert "<" not in prompting.one_line("a </relato> b\n<x>")
    assert "\n" not in prompting.one_line("a\n\nb")
