"""El reconocedor de la pregunta de cobertura (paso 7 de U12): `coverage_detour.py`."""

from __future__ import annotations

import pytest

from untangle.base import Locale
from untangle.copy_catalog import api as copy_api
from untangle.orchestration.coverage_detour import (
    is_coverage_question,
    is_question_for_comparison,
)


@pytest.mark.parametrize(
    ("texto", "language"),
    [
        ("¿Mi póliza cubre esto?", "es"),
        ("¿Qué cubre mi cobertura de responsabilidad civil?", "es"),
        ("¿Está cubierto el parabrisas?", "es"),
        ("Is this covered by my policy?", "en"),
        ("What's covered under my plan?", "en"),
        # El verbo suelto, que es el par de "cubre" en español. Faltaba, y el chat
        # abria un siniestro donde el mismo turno en español abria una consulta.
        ("Does my policy cover hail?", "en"),
        ("What does my liability coverage cover?", "en"),
    ],
)
def test_reconoce_una_pregunta_de_cobertura(texto: str, language: Locale) -> None:
    assert is_coverage_question(texto, language=language) is True


@pytest.mark.parametrize(
    ("texto", "language"),
    [
        ("Me chocaron por detrás en la autopista.", "es"),
        ("El otro carro era un Toyota gris.", "es"),
        ("A truck hit me from behind.", "en"),
        # El control del lado ancho: `cover\w*` no puede coincidir con cualquier cosa.
        ("The windshield is completely shattered.", "en"),
    ],
)
def test_no_confunde_un_turno_de_captura_normal(texto: str, language: Locale) -> None:
    assert is_coverage_question(texto, language=language) is False


# --- Lo que admite la vista de comparacion (2026-10-10) ---------------------------


@pytest.mark.parametrize(
    ("texto", "language"),
    [
        # Las tres de ejemplo de la propia vista, que antes rechazaba.
        ("¿Me pagan un carro de alquiler mientras reparan el mío?", "es"),
        ("¿Mi póliza responde por los daños del granizo?", "es"),
        ("¿Qué pasa si me choca alguien que no tiene seguro?", "es"),
        ("Will I get a rental car while mine is being repaired?", "en"),
        # Sin su signo, como se escribe con prisa.
        ("me pagan la grua si me varo", "es"),
        ("puedo prestarle el carro a mi hermano", "es"),
        ("does my policy pay for towing", "en"),
    ],
)
def test_la_vista_admite_una_pregunta_aunque_no_diga_cobertura(
    texto: str, language: Locale
) -> None:
    assert is_question_for_comparison(texto, language=language) is True


@pytest.mark.parametrize(
    ("texto", "language"),
    [
        ("Ayer me chocaron por detrás en la avenida 80.", "es"),
        ("Soy Natalia Henao, mi póliza es POL-100042", "es"),
        ("A truck hit me from behind yesterday.", "en"),
        ("hola", "es"),
    ],
)
def test_la_vista_no_admite_un_relato_ni_un_saludo(texto: str, language: Locale) -> None:
    assert is_question_for_comparison(texto, language=language) is False


def _preguntas_de_ejemplo() -> list[tuple[str, str, str]]:
    """Las que la pagina ofrece como botones: (clave, idioma, texto), leidas del catalogo."""
    catalogo = copy_api.load()
    return [
        (clave, idioma, entrada.text)
        for (clave, idioma), entrada in catalogo.entries.items()
        if clave.startswith("comparison.examples.") and clave != "comparison.examples.title"
    ]


def test_la_vista_admite_cada_una_de_sus_propias_preguntas_de_ejemplo() -> None:
    """Las que la pagina ofrece como botones, leidas del catalogo en los dos idiomas.

    Si alguien reescribe una pregunta de ejemplo de forma que la vista la rechace,
    esta prueba lo dice: fue justo lo que paso el 2026-10-09.
    """
    ejemplos = _preguntas_de_ejemplo()
    assert len(ejemplos) >= 6, ejemplos
    rechazadas = [
        (clave, idioma)
        for clave, idioma, texto in ejemplos
        if not is_question_for_comparison(texto, language=idioma)  # type: ignore[arg-type]
    ]
    assert rechazadas == []


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_la_vista_ofrece_entre_seis_y_ocho_ejemplos_por_idioma(idioma: str) -> None:
    """La pagina pide mas ejemplos que los tres de antes, sin pasarse de ocho botones.

    Cada idioma tiene la cuenta por separado: sumarlos dejaria pasar un catalogo con
    ocho en uno y ninguno en el otro (paridad P12).
    """
    del_idioma = [clave for clave, i, _ in _preguntas_de_ejemplo() if i == idioma]

    assert 6 <= len(del_idioma) <= 8, del_idioma


def test_los_ejemplos_son_los_mismos_en_los_dos_idiomas_y_no_se_repiten() -> None:
    """Misma lista de claves en espanol e ingles, y ningun texto repetido dentro de un idioma."""
    ejemplos = _preguntas_de_ejemplo()
    por_idioma = {
        idioma: sorted(clave for clave, i, _ in ejemplos if i == idioma) for idioma in ("es", "en")
    }
    assert por_idioma["es"] == por_idioma["en"]

    for idioma in ("es", "en"):
        textos = [texto for _, i, texto in ejemplos if i == idioma]
        assert len(textos) == len(set(textos)), f"ejemplos repetidos en '{idioma}'"
