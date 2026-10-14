"""El camino de arranque, de punta a punta (NFR21.1, CG-2).

Corre el comando unico sobre el subconjunto declarado del repositorio real, con
sus casos, su catalogo y sus chequeos de verdad. Es la prueba del criterio de
terminado del Bolt: "clonar y llegar al reporte".

**Sin clave de ningun proveedor y sin base de datos.** Que esta prueba pase en
una maquina limpia es exactamente lo que la meta de los quince minutos promete.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from untangle.copy_catalog import api as copy_api
from untangle.evals import cli
from untangle.evals.runner import api as runner_api


@pytest.fixture(autouse=True)
def registros_limpios() -> Iterator[None]:
    runner_api.reset()
    copy_api.reset()
    yield
    runner_api.reset()
    copy_api.reset()


@pytest.fixture
def reporte(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[int, dict[str, object]]:
    """Corre el subconjunto de arranque sin clave y devuelve codigo y reporte."""
    monkeypatch.delenv("UNTANGLE_EVALS_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("UNTANGLE_TRACES_ENDPOINT", raising=False)

    destino = tmp_path / "reporte.json"
    codigo = cli.main(["--subset", "smoke", "--out", str(destino)])
    return codigo, json.loads(destino.read_text(encoding="utf-8"))


# --- Camino feliz -------------------------------------------------------------


def test_el_subconjunto_de_arranque_llega_al_reporte_sin_clave_ni_base_de_datos(
    reporte: tuple[int, dict[str, object]],
) -> None:
    codigo, contenido = reporte

    assert codigo == 0

    cabecera = contenido["header"]
    assert isinstance(cabecera, dict)
    assert cabecera["subset"] == "smoke"
    assert cabecera["subset_declared"] is True
    # La duracion se mide siempre, cumpla la meta o no (BR1.8).
    assert isinstance(cabecera["duration_seconds"], float)
    # Sin backend de trazas la corrida sigue siendo comparable: es informacion
    # perdida sobre por que paso algo, no sobre que paso (BR1.3, REL-U1.3).
    assert cabecera["traces_available"] is False
    assert cabecera["comparable"] is True


def test_el_reporte_muestra_los_dos_idiomas_lado_a_lado(
    reporte: tuple[int, dict[str, object]],
) -> None:
    _, contenido = reporte
    totales = contenido["totals"]
    assert isinstance(totales, dict)

    # Mismos casos y mismas metas en los dos idiomas, cada uno en su columna.
    assert set(totales) == {"es", "en"}
    assert totales["es"] == totales["en"]
    assert isinstance(totales["es"], dict)
    assert totales["es"]["failed"] == 0
    assert totales["es"]["not_measured"] == 0
    assert totales["es"]["passed"] > 0


def test_cada_caso_sale_con_su_identificador_estable_y_su_traza_marcada(
    reporte: tuple[int, dict[str, object]],
) -> None:
    _, contenido = reporte
    casos = contenido["cases"]
    assert isinstance(casos, list)

    claves = [caso["case_key"] for caso in casos]
    assert "DS-8/es/copy-catalog-parity" in claves
    assert "DS-8/en/content-clause-text" in claves
    # El identificador es la moneda: aparece sin traducir en el reporte, en el
    # diff contra la linea base y en cualquier conversacion sobre el caso.
    assert all(clave.startswith("DS-") for clave in claves)

    for caso in casos:
        # Marcado como no disponible, nunca vacio ni inventado.
        assert caso["trace_status"] == "unavailable"
        assert caso["trace_ref"] is None


# --- Casos de error y de borde ------------------------------------------------


def test_un_subconjunto_que_no_existe_termina_con_codigo_dos_nombrandolo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = cli.main(["--subset", "no-existe", "--out", str(tmp_path / "r.json")])

    assert codigo == 2
    assert "no-existe" in capsys.readouterr().err


def test_dos_corridas_del_mismo_commit_ejecutan_los_mismos_casos_en_el_mismo_orden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("UNTANGLE_EVALS_MODEL_API_KEY", raising=False)

    def claves(nombre: str) -> list[str]:
        destino = tmp_path / nombre
        assert cli.main(["--subset", "smoke", "--out", str(destino)]) == 0
        contenido = json.loads(destino.read_text(encoding="utf-8"))
        return [caso["case_key"] for caso in contenido["cases"]]

    assert claves("primera.json") == claves("segunda.json")
