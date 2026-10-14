"""Los escenarios de prueba del motor de reglas: que hay y como se leen (U9).

Viven versionados en `app/evals/fixtures/rules/`, un archivo por idioma, igual
que las de U10 (`compliance_fixtures.py`). Las leen las sondas de DS-2 de este
mismo paquete: cada fila nombra una aseguradora real de la configuracion
cargada y los insumos que un caso ya habria capturado, y la sonda evalua el
motor real de esa aseguradora contra ellos (Q3).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import Field, ValidationError, model_validator

from untangle.base import Frozen, Locale
from untangle.case_record.models import FieldStatus
from untangle.rules.fields import RuleValue
from untangle.rules.models import Category

#: La forma de un identificador de fila: `<escenario>/<nn>`, igual que en U10.
ROW_ID_PATTERN = r"^[a-z0-9-]+/\d{2}$"


class RulesFixtureError(Exception):
    """Los escenarios de prueba del motor no se pudieron cargar. Nombra el archivo."""


class CapturedInjuries(Frozen):
    """El campo `injuries` del caso, sin derivar: lo que anoto el modelo o, si fallo, las
    palabras de la persona."""

    value: str = Field(min_length=1)
    status: FieldStatus = FieldStatus.STATED


class CapturedOtherParties(Frozen):
    """El campo `other_parties` del caso, sin derivar: lo que anoto el modelo o las palabras
    de la persona. Sin filas de partes: es el caso del tercero que se nombra y nadie registra."""

    value: str = Field(min_length=1)
    status: FieldStatus = FieldStatus.STATED


class CapturedDriver(Frozen):
    """El campo `vehicle_and_driver` del caso y los conductores que declara su poliza, sin derivar.

    `declared_drivers` son los nombres que la poliza del caso declara, el titular primero: lo
    que la base le da a la derivacion cuando el caso tiene poliza identificada. Vacio es una
    poliza que no declara conductores, o un caso sin poliza."""

    value: str = Field(min_length=1)
    status: FieldStatus = FieldStatus.STATED
    declared_drivers: tuple[str, ...] = ()


#: Lo que la fila espera del insumo `unlisted_driver` ya derivado: el conductor figura en la
#: poliza (`false`), no figura (`true`) o no se sabe (ausente). Palabras y no booleanos: en YAML
#: `false` y `ausente` se confundirian a la vista, y el tercer valor es justo el que importa.
ExpectedDriver = Literal["listed", "unlisted", "unknown"]

#: Como termina el reporte cuando la cadena de fondo acaba (2026-10-13): cerrado por las reglas
#: con la resolucion `registered`, sin pasar por la bandeja, o con un ajustador.
ExpectedClosure = Literal["registered", "with_adjuster"]


class RulesFixtureRow(Frozen):
    """Un escenario: la aseguradora, los insumos y la categoria esperada.

    `inputs` son insumos ya derivados; `injuries` y `other_parties` son los campos del caso,
    para medir el recorrido desde lo que el caso guarda hasta la categoria. Las dos formas del
    mismo dato juntas no se admiten: una pisaria a la otra sin decirlo.

    `closure` es lo que la fila espera del **final** del recorrido: que el caso quede cerrado
    como `registered` o con un ajustador. Solo las filas de cierre directo lo declaran.

    `vehicle_and_driver` es el campo de quien conducia, para medir el recorrido desde lo que el
    caso guarda hasta la categoria, y `expected_driver` lo que la derivacion debe dar: la
    categoria sola no distingue "figura" de "no se sabe" (ninguna regla exige el insumo en falso),
    asi que la fila lo declara.
    """

    id: str = Field(pattern=ROW_ID_PATTERN)
    scenario: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    inputs: dict[str, RuleValue] = Field(default_factory=dict)
    injuries: CapturedInjuries | None = None
    other_parties: CapturedOtherParties | None = None
    vehicle_and_driver: CapturedDriver | None = None
    expected_category: Category
    expected_driver: ExpectedDriver | None = None
    closure: ExpectedClosure | None = None

    @model_validator(mode="after")
    def _el_identificador_nombra_su_escenario(self) -> Self:
        if not self.id.startswith(f"{self.scenario}/"):
            msg = f"la fila '{self.id}' dice pertenecer al escenario '{self.scenario}'"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _heridos_se_dan_de_una_sola_forma(self) -> Self:
        if self.injuries is not None and "injuries_present" in self.inputs:
            msg = f"la fila '{self.id}' da los heridos como insumo y como campo del caso a la vez"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _terceros_se_dan_de_una_sola_forma(self) -> Self:
        if self.other_parties is not None and "other_parties_data_pending" in self.inputs:
            msg = f"la fila '{self.id}' da los terceros como insumo y como campo del caso a la vez"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _conductor_se_da_de_una_sola_forma(self) -> Self:
        if self.vehicle_and_driver is not None and "unlisted_driver" in self.inputs:
            msg = f"la fila '{self.id}' da el conductor como insumo y como campo del caso a la vez"
            raise ValueError(msg)
        if self.expected_driver is not None and self.vehicle_and_driver is None:
            msg = f"la fila '{self.id}' espera un conductor derivado y no da el campo del caso"
            raise ValueError(msg)
        return self


class RulesFixtures(Frozen):
    """Los escenarios de prueba de un idioma."""

    language: Locale
    rows: tuple[RulesFixtureRow, ...]

    @model_validator(mode="after")
    def _identificadores_unicos(self) -> Self:
        ids = [fila.id for fila in self.rows]
        repetidos = sorted({i for i in ids if ids.count(i) > 1})
        if repetidos:
            msg = f"los escenarios repiten las filas {repetidos}"
            raise ValueError(msg)
        return self

    def rows_for(self, scenario: str) -> tuple[RulesFixtureRow, ...]:
        """Las filas de un escenario, en el orden del archivo."""
        return tuple(fila for fila in self.rows if fila.scenario == scenario)


def fixtures_dir(root: Path) -> Path:
    """Donde viven los escenarios de prueba del motor de reglas."""
    return root / "app" / "evals" / "fixtures" / "rules"


def load_rules_fixtures(language: Locale, root: Path) -> RulesFixtures:
    """Los escenarios de un idioma, validados y nombrando el archivo en cada fallo."""
    archivo = fixtures_dir(root) / f"{language}.yaml"
    if not archivo.is_file():
        msg = (
            f"faltan los escenarios de prueba del motor de reglas del idioma '{language}': "
            f"se esperaba '{archivo}'. Sin ellos los casos de U9 no se pueden medir"
        )
        raise RulesFixtureError(msg)
    try:
        cargado: Any = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        msg = f"no se pudieron leer los escenarios '{archivo}': {error}"
        raise RulesFixtureError(msg) from error
    try:
        fixtures = RulesFixtures.model_validate(cargado)
    except ValidationError as error:
        msg = f"los escenarios '{archivo}' no validan su esquema: {error}"
        raise RulesFixtureError(msg) from error
    if fixtures.language != language:
        msg = f"'{archivo}' declara el idioma '{fixtures.language}' y se cargo como '{language}'"
        raise RulesFixtureError(msg)
    return fixtures
