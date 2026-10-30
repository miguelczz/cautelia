"""Las frases de prueba de los controles de cumplimiento: que hay y como se leen (U10).

Viven versionadas en `app/evals/fixtures/compliance/`, **un archivo por idioma de
turno**, y no se generan en tiempo de corrida (practica del equipo sobre datos de
prueba). Las leen dos consumidores: las sondas de DS-2 y DS-6 de este mismo
paquete y las pruebas de la logica de la guardia y de las senales. Una sola
fuente de frases, para que la compuerta y la prueba no midan cosas distintas
(FD-U10-7).

El modulo vive aparte de las sondas por la misma razon que el de la redaccion:
las pruebas de la logica leen las frases sin arrastrar el registro del corredor.

**Los marcadores se llenan con la configuracion cargada** (BR1.7): donde una
frase necesita otra aseguradora u otro caso lleva `{other_tenant_name}` o
`{other_case_number}`, y nadie escribe aqui el nombre de ninguna. Si manana entra
una cuarta aseguradora, los casos siguen midiendo lo mismo sin tocar el archivo.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import Field, ValidationError, model_validator

from untangle.base import Frozen, Locale
from untangle.compliance.controls.delimitation import (
    CLOSE_DELIMITER,
    UntrustedSource,
    open_delimiter,
)
from untangle.compliance.controls.models import GuardCategory
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import TenantConfig

#: Los seriales de los dos numeros de caso que las frases nombran. Son de la
#: prueba y no de ninguna aseguradora: el prefijo lo pone la configuracion.
CURRENT_CASE_SERIAL = "73"
OTHER_CASE_SERIAL = "48"

#: La forma de un identificador de fila: `<escenario>/<nn>`, igual en los dos
#: idiomas, porque la paridad es fila por fila (P12, NFR20.2).
ROW_ID_PATTERN = r"^[a-z0-9-]+/\d{2}$"


class ComplianceFixtureError(Exception):
    """Las frases de prueba no se pudieron cargar. El mensaje nombra el archivo."""


class FixtureRow(Frozen):
    """Lo comun a toda fila: su identificador, su escenario y su texto."""

    id: str = Field(pattern=ROW_ID_PATTERN)
    scenario: str = Field(min_length=1)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def _el_identificador_nombra_su_escenario(self) -> Self:
        if not self.id.startswith(f"{self.scenario}/"):
            msg = f"la fila '{self.id}' dice pertenecer al escenario '{self.scenario}'"
            raise ValueError(msg)
        return self


class GuardRow(FixtureRow):
    """Una frase candidata a salir hacia el asegurado, y que tiene que pasarle."""

    #: Vacio: la frase sale igual. Con valor: no sale, y la intervencion lo nombra.
    expected_category: GuardCategory | None


class ExpectedSignals(Frozen):
    """Las **tres** senales esperadas de un turno, no solo la que el escenario mira."""

    human_request: bool
    identity_question: bool
    emergency: bool


class TurnRow(FixtureRow):
    """Lo que dijo la persona, ya redactado, con sus senales esperadas."""

    expected: ExpectedSignals


class UntrustedRow(FixtureRow):
    """Un texto de origen externo camino de un prompt (BR7.1)."""

    source: UntrustedSource


class FixedPhrases(Frozen):
    """Las frases que los criterios fijan palabra por palabra."""

    identity_answer: str = Field(min_length=1)
    emergency_local: str = Field(min_length=1)
    emergency_public: str = Field(min_length=1)


class ComplianceFixtures(Frozen):
    """Las frases de prueba de un idioma de turno."""

    language: Locale
    fixed_phrases: FixedPhrases
    guard: tuple[GuardRow, ...]
    turns: tuple[TurnRow, ...]
    untrusted: tuple[UntrustedRow, ...]

    @model_validator(mode="after")
    def _identificadores_unicos_por_seccion(self) -> Self:
        for seccion in ("guard", "turns", "untrusted"):
            ids = [fila.id for fila in getattr(self, seccion)]
            repetidos = sorted({i for i in ids if ids.count(i) > 1})
            if repetidos:
                msg = f"la seccion '{seccion}' repite las filas {repetidos}"
                raise ValueError(msg)
        return self


def fixtures_dir(root: Path) -> Path:
    """Donde viven las frases de prueba de los controles."""
    return root / "app" / "evals" / "fixtures" / "compliance"


def load_fixtures(language: Locale, root: Path) -> ComplianceFixtures:
    """Las frases de un idioma, validadas y nombrando el archivo en cada fallo."""
    archivo = fixtures_dir(root) / f"{language}.yaml"
    if not archivo.is_file():
        msg = (
            f"faltan las frases de prueba de los controles del idioma '{language}': "
            f"se esperaba '{archivo}'. Sin ellas los casos de U10 no se pueden medir"
        )
        raise ComplianceFixtureError(msg)
    try:
        cargado: Any = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        msg = f"no se pudieron leer las frases '{archivo}': {error}"
        raise ComplianceFixtureError(msg) from error
    try:
        fixtures = ComplianceFixtures.model_validate(cargado)
    except ValidationError as error:
        msg = f"las frases '{archivo}' no validan su esquema: {error}"
        raise ComplianceFixtureError(msg) from error
    if fixtures.language != language:
        msg = f"'{archivo}' declara el idioma '{fixtures.language}' y se cargo como '{language}'"
        raise ComplianceFixtureError(msg)
    return fixtures


@dataclass(frozen=True)
class Scene:
    """La aseguradora del turno, otra aseguradora, y lo que llena cada marcador."""

    current: TenantConfig
    other: TenantConfig
    tenants: tuple[TenantConfig, ...]

    @property
    def current_case_number(self) -> str:
        return f"{self.current.case_number_prefix}-{CURRENT_CASE_SERIAL}"

    def markers(self, source: UntrustedSource | None = None) -> dict[str, str]:
        """Lo que va en cada marcador. Los delimitadores, con la procedencia de la fila."""
        return {
            "other_tenant_id": self.other.tenant_id,
            "other_tenant_name": self.other.display_name,
            "other_case_number": f"{self.other.case_number_prefix}-{OTHER_CASE_SERIAL}",
            "current_case_number": self.current_case_number,
            "open_delimiter": open_delimiter(source or UntrustedSource.INSURED_TURN),
            "close_delimiter": CLOSE_DELIMITER,
        }


def load_scene(root: Path) -> Scene:
    """Dos aseguradoras de la configuracion cargada, sin escribir el nombre de ninguna.

    La del turno es la primera por orden de identificador y la otra, la segunda:
    un orden fijo para que dos corridas del mismo commit midan lo mismo.
    """
    disponibles = tuple(
        sorted(
            tenancy_config.load(root / "app" / "config" / "tenants").available,
            key=lambda t: t.tenant_id,
        )
    )
    if len(disponibles) < 2:
        msg = (
            "la revelacion de otra aseguradora (RT-5) necesita dos aseguradoras "
            f"cargadas y hay {len(disponibles)}"
        )
        raise ComplianceFixtureError(msg)
    return Scene(current=disponibles[0], other=disponibles[1], tenants=disponibles)


def fill(text: str, markers: dict[str, str]) -> str:
    """La frase con sus marcadores llenos. Un marcador desconocido levanta."""
    try:
        return text.format_map(markers)
    except (KeyError, ValueError) as error:
        msg = f"una frase de prueba lleva un marcador que no existe: {error}"
        raise ComplianceFixtureError(msg) from error
