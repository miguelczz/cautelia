"""Los escenarios de la cotizacion: que hay y como se leen (U19, DS-4).

Viven versionados en `app/evals/fixtures/quote/`, un archivo por idioma, igual que los del motor
de reglas (`rules_fixtures.py`). Las leen las sondas de DS-4 de este mismo paquete.

**Los insumos de elegibilidad son los mismos en los dos idiomas, valor por valor** (P12): el
motor no depende del idioma. Lo que cambia entre `es.yaml` y `en.yaml` es lo que una persona
*dice* --las frases con las que presiona por un precio y con las que pide cotizar--, que es
justo lo que un reconocedor bilingue puede dejar pasar en un idioma y no en el otro.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import Field, ValidationError, model_validator

from untangle.base import Frozen, Locale
from untangle.rules.fields import RuleValue

#: La forma de un identificador de fila: `<escenario>/<nn>`.
ROW_ID_PATTERN = r"^[a-z0-9-]+/\d{2}$"

Outcome = Literal["eligible", "not_eligible", "referred"]
Band = Literal["standard_risk", "elevated_risk", "pending_review", "outside_appetite"]


class QuoteFixtureError(Exception):
    """Los escenarios de la cotizacion no se pudieron cargar. Nombra el archivo."""


class _Row(Frozen):
    id: str = Field(pattern=ROW_ID_PATTERN)
    scenario: str = Field(min_length=1)

    @model_validator(mode="after")
    def _el_identificador_nombra_su_escenario(self) -> Self:
        if not self.id.startswith(f"{self.scenario}/"):
            msg = f"la fila '{self.id}' dice pertenecer al escenario '{self.scenario}'"
            raise ValueError(msg)
        return self


class EligibilityRow(_Row):
    """Una solicitud ya capturada y lo que el motor tiene que decidir de ella."""

    tenant_id: str = Field(min_length=1)
    inputs: dict[str, RuleValue]
    expected_outcome: Outcome
    expected_band: Band
    #: Las reglas que tienen que decidir, en el orden del archivo de reglas.
    expected_rules: tuple[str, ...] = Field(min_length=1)


class PressureRow(_Row):
    """Una frase con la que quien pregunta presiona por un precio dentro de una solicitud."""

    text: str = Field(min_length=1)


class AvailabilityRow(_Row):
    """Una peticion de cotizar a una aseguradora, y si debe recibir la respuesta de «no cotiza»."""

    tenant_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    #: Si ya se capturo algo del siniestro: a mitad de un relato, mencionar una cotizacion no
    #: es pedirla.
    anything_captured: bool = False
    expect_unavailable: bool


class QuoteFixtures(Frozen):
    """Los escenarios de un idioma."""

    language: Locale
    eligibility: tuple[EligibilityRow, ...]
    pressure: tuple[PressureRow, ...]
    availability: tuple[AvailabilityRow, ...]

    @model_validator(mode="after")
    def _identificadores_unicos(self) -> Self:
        ids = [fila.id for fila in (*self.eligibility, *self.pressure, *self.availability)]
        repetidos = sorted({i for i in ids if ids.count(i) > 1})
        if repetidos:
            msg = f"los escenarios repiten las filas {repetidos}"
            raise ValueError(msg)
        return self

    def eligibility_for(self, *scenarios: str) -> tuple[EligibilityRow, ...]:
        """Las filas de elegibilidad de esos escenarios, en el orden del archivo."""
        return tuple(fila for fila in self.eligibility if fila.scenario in scenarios)


def fixtures_dir(root: Path) -> Path:
    """Donde viven los escenarios de la cotizacion."""
    return root / "app" / "evals" / "fixtures" / "quote"


def load_quote_fixtures(language: Locale, root: Path) -> QuoteFixtures:
    """Los escenarios de un idioma, validados y nombrando el archivo en cada fallo."""
    archivo = fixtures_dir(root) / f"{language}.yaml"
    if not archivo.is_file():
        msg = (
            f"faltan los escenarios de la cotizacion del idioma '{language}': se esperaba "
            f"'{archivo}'. Sin ellos los casos de DS-4 no se pueden medir"
        )
        raise QuoteFixtureError(msg)
    try:
        cargado: Any = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        msg = f"no se pudieron leer los escenarios '{archivo}': {error}"
        raise QuoteFixtureError(msg) from error
    try:
        fixtures = QuoteFixtures.model_validate(cargado)
    except ValidationError as error:
        msg = f"los escenarios '{archivo}' no validan su esquema: {error}"
        raise QuoteFixtureError(msg) from error
    if fixtures.language != language:
        msg = f"'{archivo}' declara el idioma '{fixtures.language}' y se cargo como '{language}'"
        raise QuoteFixtureError(msg)
    return fixtures
