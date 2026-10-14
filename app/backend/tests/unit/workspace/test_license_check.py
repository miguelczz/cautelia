"""El chequeo de licencias del arbol resuelto (D-017).

Nace de un hallazgo real del 2026-09-27: la revision a mano del arbol de
dependencias no vio los dos modelos de spaCy --entran por un extra, con su
URL-- y uno de los dos, el de espanol, es GPL-3.0. Por eso estas pruebas
comprueban sobre todo que el chequeo **falla** en las tres formas en que ese
hallazgo pudo esconderse: una licencia que nadie admitio, un paquete del
lockfile sin instalar, y una familia de licencias adivinada.
"""

from __future__ import annotations

from email.message import Message
from importlib import metadata as md
from pathlib import Path

import pytest

from untangle import paths
from untangle.workspace import license_check as lc


def _metadato(**campos: str) -> Message:
    """Un metadato de distribucion como el que devuelve `importlib.metadata`."""
    mensaje = Message()
    for clave, valor in campos.items():
        mensaje[clave.replace("_", "-")] = valor
    return mensaje


def _paquete(nombre: str, licencias: tuple[str, ...], ecosystem: str = lc.PYTHON) -> lc.Paquete:
    return lc.Paquete(
        ecosystem=ecosystem, name=nombre, version="1.0", licenses=licencias, source="prueba"
    )


PERMISIVA = lc.Politica(allowed={"MIT": "permisiva", "Apache-2.0": "permisiva"})


# --- Lo que falla -------------------------------------------------------------


def test_falla_la_licencia_que_nadie_admitio() -> None:
    informe = lc.evaluate([_paquete("es-core-news-md", ("GPL-3.0-only",))], PERMISIVA)

    assert len(informe.problems) == 1
    # El fallo nombra el paquete y la licencia: sin las dos cosas no se puede
    # decidir nada al leerlo.
    assert "es-core-news-md" in informe.problems[0]
    assert "GPL-3.0-only" in informe.problems[0]


def test_falla_el_paquete_del_lockfile_que_no_esta_instalado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La grieta exacta por la que un modelo GPL puede pasar desapercibido.

    Sin los modelos instalados, un chequeo que solo mirara lo instalado daria
    verde sobre medio arbol.
    """
    monkeypatch.setattr(
        lc, "_requisitos_del_lockfile", lambda _r: ({"pydantic", "es-core-news-md"}, [])
    )
    monkeypatch.setattr(
        md,
        "distributions",
        lambda: [
            _Distribucion(_metadato(Name="pydantic", Version="2.12.4", License_Expression="MIT"))
        ],
    )

    paquetes, problemas = lc.python_packages(Path("/no-importa"))

    assert [p.name for p in paquetes] == ["pydantic"]
    assert len(problemas) == 1
    assert "es-core-news-md" in problemas[0]
    assert "models:install" in problemas[0]


def test_no_adivina_la_familia_de_una_licencia() -> None:
    """ "BSD" no dice si son dos clausulas o tres, y adivinar es inventar un hecho."""
    licencias, _origen = lc._licencias_de_metadato(
        _metadato(Name="blis", License="BSD", Classifier="License :: OSI Approved :: BSD License")
    )

    assert licencias == ()
    informe = lc.evaluate([_paquete("blis", licencias)], PERMISIVA)
    assert "declared" in informe.problems[0]


def test_falla_la_excepcion_sin_razon_o_sin_fecha(tmp_path: Path) -> None:
    _manifiesto(
        tmp_path,
        """
allowed = [{ id = "MIT", reason = "permisiva" }]
exceptions = [{ ecosystem = "python", package = "x", licenses = ["GPL-3.0-only"], reason = "" , date = "2026-09-27" }]
""",
    )

    _politica, problemas = lc.load_policy(tmp_path)

    assert any("razon y fecha" in p for p in problemas)


def test_una_expresion_compuesta_exige_todas_sus_licencias() -> None:
    """`Apache-2.0 AND CNRI-Python`: la segunda tambien tiene que estar decidida."""
    licencias, _origen = lc._licencias_de_metadato(
        _metadato(Name="regex", License_Expression="Apache-2.0 AND CNRI-Python")
    )

    assert licencias == ("Apache-2.0", "CNRI-Python")
    informe = lc.evaluate([_paquete("regex", licencias)], PERMISIVA)
    assert len(informe.problems) == 1
    assert "CNRI-Python" in informe.problems[0]


# --- Lo que pasa --------------------------------------------------------------


def test_la_excepcion_admite_y_queda_dicha() -> None:
    """Una excepcion que nadie vuelve a leer es una decision olvidada."""
    politica = lc.Politica(
        allowed={"MIT": "permisiva"},
        exceptions={
            (lc.PYTHON, "es-core-news-md"): (
                ("GPL-3.0-only",),
                "no esta en el repositorio",
                "2026-09-27",
            )
        },
    )

    informe = lc.evaluate([_paquete("es-core-news-md", ("GPL-3.0-only",))], politica)

    assert informe.problems == []
    assert len(informe.used_exceptions) == 1
    assert "2026-09-27" in informe.used_exceptions[0]
    assert "no esta en el repositorio" in informe.used_exceptions[0]


def test_la_licencia_declarada_a_mano_sustituye_al_metadato_callado() -> None:
    politica = lc.Politica(
        allowed={"BSD-3-Clause": "permisiva"},
        declared={(lc.PYTHON, "blis"): ("BSD-3-Clause",)},
    )

    assert lc.evaluate([_paquete("blis", ())], politica).problems == []


def test_el_metadato_de_pep_639_manda_sobre_el_clasificador() -> None:
    licencias, origen = lc._licencias_de_metadato(
        _metadato(
            Name="x",
            License_Expression="BSD-3-Clause",
            Classifier="License :: OSI Approved :: MIT License",
        )
    )

    assert licencias == ("BSD-3-Clause",)
    assert origen == "License-Expression"


def test_el_texto_libre_que_nombra_una_licencia_se_traduce() -> None:
    assert lc._licencias_de_metadato(_metadato(Name="x", License="GNU GPL 3.0")) == (
        ("GPL-3.0-only",),
        "License",
    )
    assert lc._licencias_de_metadato(
        _metadato(
            Name="x", Classifier="License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)"
        )
    ) == (("MPL-2.0",), "Classifier")


def test_el_texto_de_una_licencia_entera_no_es_un_identificador() -> None:
    """`pip-api` mete el texto completo de Apache en el campo `License`."""
    licencias, _origen = lc._licencias_de_metadato(
        _metadato(
            Name="pip-api",
            License="Apache License\n                    Version 2.0, January 2004",
            Classifier="License :: OSI Approved :: Apache Software License",
        )
    )

    assert licencias == ("Apache-2.0",)


# --- La politica de verdad ----------------------------------------------------


def test_la_politica_del_proyecto_tiene_su_razon_por_entrada() -> None:
    """Cada licencia admitida dice por que, cada declarada de donde se leyo."""
    politica, problemas = lc.load_policy(paths.repo_root())

    assert problemas == []
    assert politica.allowed
    assert all(razon for razon in politica.allowed.values())


# --- Andamiaje ----------------------------------------------------------------


class _Distribucion:
    """Lo unico que `python_packages` le pide a una distribucion instalada."""

    def __init__(self, metadata: Message) -> None:
        self.metadata = metadata


def _manifiesto(directorio: Path, seccion: str) -> None:
    backend = directorio / "app" / "backend"
    backend.mkdir(parents=True, exist_ok=True)
    (backend / "pyproject.toml").write_text(
        f"[tool.untangle.licenses]\n{seccion}", encoding="utf-8"
    )
