"""Pruebas del catalogo de textos (C-21, US5.8).

Cada prueba afirma una conducta del contrato, no una forma de codificarlo.
Ninguna necesita red, base de datos ni credenciales: el catalogo se monta sobre
un directorio temporal.
"""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from untangle import observability
from untangle.copy_catalog import api
from untangle.copy_catalog.loading import CatalogLoadError, load_catalog

CATALOGO_ES = """
inbox:
  card:
    title:
      text: "Caso {case_number}"
      surface: inbox
system:
  degraded:
    text: Algo falló de nuestro lado.
    surface: system
"""

CATALOGO_EN = """
inbox:
  card:
    title:
      text: "Case {case_number}"
      surface: inbox
system:
  degraded:
    text: Something went wrong on our side.
    surface: system
"""


@pytest.fixture
def catalogo(tmp_path: Path) -> api.Catalog:
    (tmp_path / "es.yaml").write_text(CATALOGO_ES, encoding="utf-8")
    (tmp_path / "en.yaml").write_text(CATALOGO_EN, encoding="utf-8")
    return api.load(tmp_path)


@pytest.fixture
def eventos() -> Iterator[io.StringIO]:
    """Captura los eventos estructurados sin tocar `sys.stdout` global."""
    buffer = io.StringIO()
    observability.set_stream(buffer)
    yield buffer
    observability.set_stream(sys.stdout)


# --- Camino feliz -------------------------------------------------------------


def test_resuelve_la_misma_clave_en_los_dos_idiomas(catalogo: api.Catalog) -> None:
    assert catalogo.t(api.CopyKey("system.degraded"), locale="es") == "Algo falló de nuestro lado."
    assert (
        catalogo.t(api.CopyKey("system.degraded"), locale="en")
        == "Something went wrong on our side."
    )


def test_sustituye_las_variables_de_la_frase(catalogo: api.Catalog) -> None:
    assert (
        catalogo.t(api.CopyKey("inbox.card.title"), locale="es", case_number="C-042")
        == "Caso C-042"
    )


def test_keys_for_devuelve_solo_las_claves_de_esa_superficie(catalogo: api.Catalog) -> None:
    assert catalogo.keys_for("inbox") == frozenset({"inbox.card.title"})
    assert catalogo.keys_for("system") == frozenset({"system.degraded"})


# --- Casos de error y de borde ------------------------------------------------


def test_una_clave_ausente_devuelve_la_clave_y_registra_el_evento(
    catalogo: api.Catalog, eventos: io.StringIO
) -> None:
    devuelto = catalogo.t(api.CopyKey("inbox.card.subtitle"), locale="es")

    # Nunca una cadena vacia: una cadena vacia en pantalla parece un problema de
    # maquetacion y se busca donde no es.
    assert devuelto == "inbox.card.subtitle"
    registrado = [json.loads(linea) for linea in eventos.getvalue().splitlines()]
    assert {"event": "copy.missing_entry", "key": "inbox.card.subtitle", "locale": "es"} in (
        registrado
    )


def test_una_variable_que_no_se_paso_falla_nombrando_la_clave(catalogo: api.Catalog) -> None:
    with pytest.raises(api.MissingVariableError) as excinfo:
        catalogo.t(api.CopyKey("inbox.card.title"), locale="es", otra="x")

    assert "inbox.card.title" in str(excinfo.value)


def test_una_carga_fallida_nombra_el_archivo_que_falta(tmp_path: Path) -> None:
    (tmp_path / "es.yaml").write_text(CATALOGO_ES, encoding="utf-8")

    with pytest.raises(CatalogLoadError) as excinfo:
        api.load(tmp_path)

    assert "en.yaml" in str(excinfo.value)


def test_la_estructura_cargada_es_inmutable(tmp_path: Path) -> None:
    (tmp_path / "es.yaml").write_text(CATALOGO_ES, encoding="utf-8")
    (tmp_path / "en.yaml").write_text(CATALOGO_EN, encoding="utf-8")

    # Un mapa mutable compartido entre el proceso servido, el corredor y las
    # pruebas es una diferencia entre dos corridas esperando a ocurrir. Lo que
    # se comprueba es que el catalogo copie su fuente en vez de aliasarla: si la
    # aliasara, vaciar el mapa de origen lo vaciaria a el.
    fuente = dict(load_catalog(tmp_path))
    catalogo = api.Catalog(fuente)
    antes = catalogo.t(api.CopyKey("system.degraded"), locale="es")

    fuente.clear()

    assert catalogo.t(api.CopyKey("system.degraded"), locale="es") == antes

    # Y lo que devuelve el cargador no se deja escribir.
    with pytest.raises(TypeError):
        load_catalog(tmp_path)[("system.degraded", "es")] = None  # type: ignore[index]
