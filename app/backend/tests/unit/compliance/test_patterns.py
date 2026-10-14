"""La normalizacion y la carga de los patrones versionados (BR1.3, TECH-U10.1).

Lo que se protege: un patron mal escrito **impide arrancar** nombrando el archivo
y el patron, en vez de convertirse en una regla que nunca coincide y deja pasar
las frases en silencio; y los patrones de los dos idiomas se aplican a cada
texto sea cual sea el idioma del turno.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from untangle.compliance.controls import patterns
from untangle.compliance.controls.models import GuardCategory
from untangle.compliance.controls.normalization import normalize
from untangle.compliance.controls.patterns import PatternFamily, PatternLoadError

# --- Normalizacion (BR1.3) ----------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        # Minusculas y sin tildes: las tres formas son el mismo texto.
        ("Está CUBIERTO", "esta cubierto"),
        ("está   cubierto", "esta cubierto"),
        # La ñ tambien pierde su marca: el patron se escribe sin ella.
        ("Mi acompañante", "mi acompanante"),
        # Espacios de cualquier clase, colapsados y recortados.
        ("  sí,\tsoy\nuna persona  ", "si, soy una persona"),
        # Los apostrofos tipograficos pasan a rectos.
        ("I\u2019m a person", "i'm a person"),
        ("you\u02bcre covered", "you're covered"),
    ],
)
def test_la_normalizacion_es_minusculas_sin_tildes_y_espacios_colapsados(
    texto: str, esperado: str
) -> None:
    assert normalize(texto) == esperado


# --- La biblioteca de verdad --------------------------------------------------


def test_los_ocho_archivos_cargan_y_cada_idioma_cubre_las_siete_categorias(
    biblioteca: patterns.PatternLibrary,
) -> None:
    assert len(biblioteca.sets) == 8
    for idioma in ("es", "en"):
        cubiertas = {p.category for p in biblioteca.guard if p.id.startswith(f"guard.{idioma}.")}
        assert cubiertas == set(GuardCategory), f"al juego {idioma} le faltan categorias"
    # Las negaciones son solo de la emergencia, y la emergencia las tiene.
    assert biblioteca.emergency_negations
    assert all(p.id.startswith("emergency.") for p in biblioteca.emergency_negations)


def test_la_biblioteca_junta_los_dos_idiomas_en_cada_familia(
    biblioteca: patterns.PatternLibrary,
) -> None:
    """BR1.3: una familia con un solo idioma es exactamente el hueco de RT-15."""
    for familia in (
        biblioteca.guard,
        biblioteca.human_request,
        biblioteca.identity_question,
        biblioteca.emergency,
    ):
        idiomas = {p.id.split(".")[1] for p in familia}
        assert idiomas == {"es", "en"}


# --- Un archivo invalido impide arrancar (TECH-U10.1) -------------------------


def _reescribir(carpeta: Path, idioma: str, familia: str, cambiar: object) -> Path:
    archivo = carpeta / idioma / f"{familia}.yaml"
    datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    assert callable(cambiar)
    cambiar(datos)
    archivo.write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")
    return archivo


@pytest.mark.parametrize(
    ("cambio", "fragmento"),
    [
        # Una expresion que no compila.
        (lambda d: d["patterns"][0].update(regex="(sin cerrar"), "no es una expresion valida"),
        # Una tilde o una mayuscula: nunca coincidiria con el texto normalizado.
        (lambda d: d["patterns"][0].update(regex="\\bestá cubierto\\b"), "nunca coincidiria"),
        (lambda d: d["patterns"][0].update(regex="\\bCubierto\\b"), "nunca coincidiria"),
        # Un identificador que no es el de su archivo.
        (
            lambda d: d["patterns"][0].update(id="guard.en.coverage_promise.001"),
            "no tiene la forma",
        ),
        # Un patron de la guardia sin su categoria.
        (lambda d: d["patterns"][0].pop("category"), "no declara su categoria"),
    ],
)
def test_un_patron_roto_impide_cargar_nombrando_el_archivo_y_el_patron(
    patrones_copiados: Path, cambio: object, fragmento: str
) -> None:
    archivo = _reescribir(patrones_copiados, "es", "guard", cambio)

    with pytest.raises(PatternLoadError) as error:
        patterns.load_library(patrones_copiados)

    mensaje = str(error.value)
    assert str(archivo) in mensaje
    assert fragmento in mensaje
    assert "guard.e" in mensaje, "el mensaje no nombra el patron culpable"


def test_un_archivo_que_falta_impide_cargar_nombrandolo(patrones_copiados: Path) -> None:
    faltante = patrones_copiados / "en" / "emergency.yaml"
    faltante.unlink()

    with pytest.raises(PatternLoadError, match="emergency"):
        patterns.load_library(patrones_copiados)


def test_negaciones_fuera_de_la_emergencia_no_cargan(patrones_copiados: Path) -> None:
    def con_negacion(datos: dict[str, list[dict[str, str]]]) -> None:
        datos["negations"] = [{"id": "human_request.es.negation.001", "regex": "\\bno\\b"}]

    _reescribir(patrones_copiados, "es", "human_request", con_negacion)

    with pytest.raises(PatternLoadError, match="solo la emergencia"):
        patterns.load_library(patrones_copiados)


def test_un_idioma_sin_una_categoria_no_carga(patrones_copiados: Path) -> None:
    """P12: una categoria vigilada solo por el otro idioma no es paridad."""

    def sin_montos(datos: dict[str, list[dict[str, str]]]) -> None:
        datos["patterns"] = [p for p in datos["patterns"] if p.get("category") != "amount"]

    _reescribir(patrones_copiados, "en", "guard", sin_montos)

    with pytest.raises(PatternLoadError, match="amount"):
        patterns.load_library(patrones_copiados)


def test_las_dos_guardias_tienen_que_eximir_las_mismas_claves(patrones_copiados: Path) -> None:
    """BR1.8: una exencion es de la plantilla, no del idioma."""

    def eximir(datos: dict[str, list[str]]) -> None:
        datos["exempt_catalog_keys"] = ["policy_rag.answer.verified_clause"]

    _reescribir(patrones_copiados, "es", "guard", eximir)

    with pytest.raises(PatternLoadError, match="eximen claves distintas"):
        patterns.load_library(patrones_copiados)


def test_la_biblioteca_del_proceso_se_carga_una_vez_y_se_puede_instalar(
    biblioteca: patterns.PatternLibrary,
) -> None:
    patterns.install(biblioteca)
    assert patterns.get_library() is biblioteca
    patterns.reset()
    cargada = patterns.get_library()
    assert cargada is not biblioteca
    assert cargada.versions() == biblioteca.versions()
    assert PatternFamily.GUARD.value in next(iter(cargada.versions()))
