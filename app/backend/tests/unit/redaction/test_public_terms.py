"""Los nombres publicos de la demo no se tapan; los de las personas, si (2026-10-08)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from untangle.compliance.redaction import api as redaccion


@pytest.fixture
def nombres_publicos() -> Iterator[None]:
    redaccion.allow_public_terms(["Autos Poblado", "Catalina"])
    yield
    redaccion.allow_public_terms([])


@pytest.mark.usefixtures("nombres_publicos")
def test_la_aseguradora_y_la_agente_no_se_tapan() -> None:
    texto = "Con gusto le ayudo a preparar su cotización en Autos Poblado. Soy Catalina."

    assert str(redaccion.redact(texto, language="es")) == texto


@pytest.mark.usefixtures("nombres_publicos")
def test_el_nombre_de_una_persona_se_sigue_tapando() -> None:
    tapado = str(redaccion.redact("Me llamo Laura Gómez y vivo en Itagüí", language="es"))

    assert "Laura" not in tapado
    assert "Itagüí" not in tapado


@pytest.mark.usefixtures("nombres_publicos")
def test_el_posesivo_del_ingles_no_esconde_a_la_aseguradora() -> None:
    """La apertura de la llamada en ingles se guardaba "[NAME 1] AI assistant"."""
    texto = "Hi, this is Catalina, Autos Poblado's AI assistant."

    assert str(redaccion.redact(texto, language="en")) == texto


@pytest.mark.usefixtures("nombres_publicos")
def test_el_posesivo_de_una_persona_se_sigue_tapando() -> None:
    tapado = str(redaccion.redact("This is Laura Gomez's car, she lives in Itagui", language="en"))

    assert "Laura" not in tapado
