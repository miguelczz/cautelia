"""Pruebas de los chequeos de contenido.

Las tres afirman lo mismo desde angulos distintos: que el chequeo detecte lo que
dice detectar, que **no** detecte lo que esta permitido, y que la lista de
exclusiones haga lo que promete. La segunda es la que importa de verdad: un
chequeo que marca la estructura de una poliza como si fuera texto de clausula se
desactiva a la semana, y entonces deja de proteger nada.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from untangle import paths
from untangle.evals import content_checks

RAIZ_REAL = paths.repo_root()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Un arbol minimo con las mismas listas versionadas del repositorio real."""
    (tmp_path / "app" / "config").mkdir(parents=True)
    shutil.copy(
        RAIZ_REAL / "app" / "config" / "content-checks.yaml",
        tmp_path / "app" / "config" / "content-checks.yaml",
    )
    (tmp_path / "app" / "backend" / "src").mkdir(parents=True)
    # El catalogo en espanol, tambien el de verdad: el chequeo del registro (U18)
    # lo mira, y sin el se declara "sin medir" --que es un hallazgo a proposito-- y
    # ensuciaria todas las demas pruebas.
    (tmp_path / "app" / "config" / "copy").mkdir(parents=True)
    shutil.copy(
        RAIZ_REAL / "app" / "config" / "copy" / "es.yaml",
        tmp_path / "app" / "config" / "copy" / "es.yaml",
    )
    return tmp_path


def escribir(repo: Path, relativo: str, texto: str) -> None:
    destino = repo / relativo
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")


# --- Camino feliz -------------------------------------------------------------


def test_la_estructura_de_una_poliza_no_se_confunde_con_texto_de_clausula(
    repo: Path,
) -> None:
    # Nombres de seccion y numeracion: estructura, permitida y documentada.
    escribir(
        repo,
        "app/backend/src/estructura.py",
        'SECCIONES = ["SECTION I - COVERAGES", "PP 00 01"]\n'
        'FORMULARIO = "inspirado en la estructura ISO PP 00 01"\n',
    )

    assert content_checks.run_all(repo) == []


# --- Casos de error y de borde ------------------------------------------------


def test_una_afirmacion_de_cumplimiento_falla_nombrando_el_archivo(repo: Path) -> None:
    escribir(repo, "README.md", "# Untangle\n\nEsta demostracion cumple con SOC 2.\n")

    hallazgos = [h for h in content_checks.run_all(repo) if h.rule == "CONTENT-CLAIMS"]

    assert len(hallazgos) == 1
    assert hallazgos[0].where == "README.md:3"
    assert "CLAIM-1" in hallazgos[0].detail


def test_un_arranque_de_clausula_copiado_falla_y_una_exclusion_lo_calla(
    repo: Path,
) -> None:
    escribir(
        repo,
        "app/backend/src/poliza.py",
        'TEXTO = "We will pay those sums the insured becomes obligated to pay."\n',
    )

    hallazgos = [h for h in content_checks.run_all(repo) if h.rule == "CONTENT-CLAUSE"]
    assert len(hallazgos) == 1
    assert hallazgos[0].where == "app/backend/src/poliza.py:1"

    # La misma frase bajo una ruta excluida deja de contar: es lo que permite que
    # las pruebas rompan el chequeo a proposito sin poner el arbol en rojo.
    escribir(
        repo,
        "app/backend/tests/rompe.py",
        'TEXTO = "We will pay those sums the insured becomes obligated to pay."\n',
    )
    reglas = content_checks.load_rules(repo)
    assert reglas.is_excluded("app/backend/tests/rompe.py")
    assert len(content_checks.check_clause_text(repo, reglas)) == 1


# --- El registro de la voz en espanol (U18, BR5.4) ----------------------------


def _con_frase_de_voz(repo: Path, texto: str) -> None:
    """Deja el catalogo con **una sola** frase de voz, la que la prueba escribe.

    Se reescribe entero en vez de parchear el real porque lo que se mide es el
    veredicto sobre una frase concreta, y con el catalogo completo detras un
    hallazgo podria venir de cualquier otra.
    """
    escribir(
        repo,
        "app/config/copy/es.yaml",
        "voice:\n  prueba:\n    frase:\n      text: " + texto + "\n      surface: voice\n",
    )


def _del_registro(repo: Path) -> list[content_checks.ContentFinding]:
    reglas = content_checks.load_rules(repo)
    return content_checks.check_spanish_register(repo, reglas)


def test_una_frase_de_tu_no_es_un_hallazgo(repo: Path) -> None:
    """El caso que importa de verdad: un chequeo que marca lo correcto se apaga."""
    _con_frase_de_voz(repo, "Con mucho gusto te ayudo. ¿Me confirmas la placa, por favor?")

    assert _del_registro(repo) == []


def test_las_formas_de_tercera_persona_correctas_no_son_un_hallazgo(repo: Path) -> None:
    """ "su cupo" y "que puede sonar" hablan de la demostracion y de la voz, no de usted."""
    _con_frase_de_voz(repo, "La demostración llegó a su cupo, y la voz puede sonar distinta.")

    assert _del_registro(repo) == []


@pytest.mark.parametrize(
    ("frase", "regla"),
    [
        ("¿Es usted quien conducía?", "REGISTER-1"),
        ("Con mucho gusto le ayudo.", "REGISTER-2"),
        ("Le ayudo con eso cuando quiera.", "REGISTER-5"),
        ("Que esté muy bien.", "REGISTER-5"),
        ("Déjeme revisar eso.", "REGISTER-3"),
        ("Pulse llamar y cuéntenos qué pasó.", "REGISTER-3"),
    ],
)
def test_cada_forma_de_usted_se_detecta(repo: Path, frase: str, regla: str) -> None:
    """Una fila por regla; la de los enclíticos ("déjeme") no lleva ningun pronombre
    suelto que un patron de palabras pueda ver."""
    _con_frase_de_voz(repo, frase)

    hallazgos = _del_registro(repo)

    assert [h.rule for h in hallazgos] == ["CONTENT-REGISTER"] * len(hallazgos)
    assert any(regla in h.detail for h in hallazgos), [h.detail for h in hallazgos]


def test_la_muletilla_una_vez_pasa_y_dos_no(repo: Path) -> None:
    """No esta prohibida: repetida en la misma frase suena a relleno (BR5.4)."""
    _con_frase_de_voz(repo, "Pues te cuento lo que encontre en tu poliza.")
    assert _del_registro(repo) == []

    _con_frase_de_voz(repo, "Pues te cuento pues lo que encontre en tu poliza.")
    hallazgos = _del_registro(repo)

    assert len(hallazgos) == 1
    assert "REGISTER-4" in hallazgos[0].detail


def test_el_registro_de_la_interfaz_no_es_un_hallazgo(repo: Path) -> None:
    """El chequeo mira la voz de la agente, no las pantallas.

    Sin esta prueba, alguien podria ampliar el alcance del chequeo a todo el catalogo
    sin decidirlo: eso es una decision aparte (content-checks.yaml).
    """
    escribir(
        repo,
        "app/config/copy/es.yaml",
        "chat:\n  page:\n    composer:\n      text: Su mensaje, usted\n      surface: chat\n",
    )

    hallazgos = _del_registro(repo)

    # El unico hallazgo posible es "nada que mirar", porque no hay frases de voz;
    # lo que no puede aparecer es el registro de la interfaz como infraccion.
    assert all("REGISTER-" not in h.detail for h in hallazgos)


def test_sin_catalogo_el_registro_se_declara_sin_medir_y_no_pasa(repo: Path) -> None:
    """Un chequeo que no encuentra nada que mirar y dice "sin hallazgos" es
    indistinguible de uno que miro. Es la misma regla que las huellas de terceros."""
    (repo / "app" / "config" / "copy" / "es.yaml").unlink()

    hallazgos = _del_registro(repo)

    assert len(hallazgos) == 1
    assert "sin medir" in hallazgos[0].detail


def test_el_criterio_no_se_repite_en_ingles(repo: Path) -> None:
    """El registro de tu/usted no existe en ingles, y copiar el veredicto daria a
    entender que se midio algo alli."""
    _con_frase_de_voz(repo, "¿Me confirma la placa, usted?")

    en = content_checks.content_spanish_register(language="en", root=repo)
    es = content_checks.content_spanish_register(language="es", root=repo)

    assert en.passed is True
    assert en.detail is not None
    assert "no aplica" in en.detail
    assert es.passed is False
