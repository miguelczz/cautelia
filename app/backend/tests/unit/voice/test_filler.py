"""La muletilla: tres por idioma, que rotan sin repetirse (2026-10-12)."""

from __future__ import annotations

from itertools import pairwise

import pytest

from untangle.base import Locale
from untangle.voice import filler

pytestmark = pytest.mark.usefixtures("catalogo_cargado")

IDIOMAS: tuple[Locale, ...] = ("en", "es")


def test_la_rotacion_da_la_vuelta_y_nunca_repite_la_misma_dos_veces_seguidas() -> None:
    indices: list[int] = []
    ultimo: int | None = None
    for _ in range(3 * filler.COUNT + 1):
        ultimo = filler.next_index(ultimo)
        indices.append(ultimo)

    assert indices[: filler.COUNT] == list(range(filler.COUNT))
    assert indices[filler.COUNT] == 0
    assert all(a != b for a, b in pairwise(indices))


@pytest.mark.parametrize("language", IDIOMAS)
def test_son_tres_frases_distintas_y_vienen_del_catalogo(language: Locale) -> None:
    frases = [filler.phrase(i, language=language) for i in range(filler.COUNT)]

    assert [clave for clave, _ in frases] == [filler.ONE, filler.TWO, filler.THREE]
    textos = [texto for _, texto in frases]
    assert len(set(textos)) == filler.COUNT
    assert all(texto.endswith("…") for texto in textos)


def test_los_textos_aprobados() -> None:
    assert [filler.phrase(i, language="es")[1] for i in range(3)] == ["Listo…", "Ajá…", "Okey…"]
    assert [filler.phrase(i, language="en")[1] for i in range(3)] == ["Okay…", "Got it…", "Right…"]


def test_una_muletilla_que_no_existe_levanta() -> None:
    with pytest.raises(ValueError, match="no hay muletilla"):
        filler.phrase(filler.COUNT, language="es")
