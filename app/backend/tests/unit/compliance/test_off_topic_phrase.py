"""La frase fija de lo que no es de la aseguradora pasa por la guardia sin cambiar (plan 09, punto 5).

Como toda frase hacia la persona, se emite por la guardia de salida (BR1.1): una prueba comprueba
que, en los dos idiomas y para cada aseguradora, ninguna de las dos formas dispara una categoria.
"""

from __future__ import annotations

import pytest

from untangle.compliance.controls import guard, patterns
from untangle.compliance.controls.guard import GuardTurn
from untangle.copy_catalog import api as copy_api
from untangle.orchestration import off_topic
from untangle.tenancy.models import TenantConfig

from .conftest import contexto_de


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_la_frase_fija_no_dispara_la_guardia(
    biblioteca: patterns.PatternLibrary,
    aseguradoras: tuple[TenantConfig, ...],
    idioma: str,
) -> None:
    copy_api.install(copy_api.load())
    textos = (
        off_topic.lead_text(language=idioma),  # type: ignore[arg-type]
        off_topic.with_case_text(language=idioma),  # type: ignore[arg-type]
    )
    for texto in textos:
        for indice in range(len(aseguradoras)):
            orden = aseguradoras[indice:] + aseguradoras[:indice]
            resultado = guard.evaluate(
                texto, library=biblioteca, context=contexto_de(orden, idioma), turn=GuardTurn()
            )
            assert resultado.unchanged, f"'{texto}' ({idioma}) dispara la guardia"
