"""Los escenarios de prueba de la bandeja: que hay y como se leen (U14, tanda 4).

Viven versionados en `app/evals/fixtures/inbox/`, un archivo por idioma, igual que
los del motor de reglas (`rules_fixtures.py`) y los de cumplimiento. Los leen las
sondas de DS-2 de este mismo paquete.

**Recuentos y enums, nunca texto.** Lo que estas filas miden --si la explicacion
deja una pregunta sin responder, y que acciones ofrece una aseguradora-- no depende
de lo que diga nadie, asi que las mismas filas viven en los dos idiomas valor por
valor y la paridad EN<->ES es real y no una traduccion (P12).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import Field, ValidationError, model_validator

from untangle.base import Frozen, Locale
from untangle.case_record.models import CaseState

#: La forma de un identificador de fila: `<escenario>/<nn>`, igual que en U9 y U10.
ROW_ID_PATTERN = r"^[a-z0-9-]+/\d{2}$"


class InboxFixtureError(Exception):
    """Los escenarios de la bandeja no se pudieron cargar. Nombra el archivo."""


class InboxFixtureRow(Frozen):
    """Una fila: la aseguradora, el estado del caso y lo que se espera.

    Un solo modelo para los dos escenarios, con los campos de cada uno opcionales:
    dos modelos casi iguales se separarian el dia que uno cambie, y el validador de
    abajo exige que cada fila traiga lo que su escenario necesita.
    """

    id: str = Field(pattern=ROW_ID_PATTERN)
    scenario: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    state: CaseState
    #: Del escenario `explanation`.
    questions: int | None = Field(default=None, ge=0)
    cited_clauses: int | None = Field(default=None, ge=0)
    fired_rules: int | None = Field(default=None, ge=0)
    rule_category: str | None = None
    #: El tipo de actor de U4 (`staff`, `insured`), o nada si no se decidio.
    decided_by_kind: str | None = None
    expected: dict[str, str] | None = None
    #: Del escenario `agency-actions`. La tupla vacia es una expectativa legitima
    #: --un caso que no admite ninguna accion-- y por eso se distingue de ausente.
    expected_actions: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def _cada_fila_trae_lo_de_su_escenario(self) -> Self:
        if not self.id.startswith(f"{self.scenario}/"):
            msg = f"la fila '{self.id}' dice pertenecer al escenario '{self.scenario}'"
            raise ValueError(msg)
        if self.scenario == "explanation" and (
            self.expected is None
            or self.questions is None
            or self.cited_clauses is None
            or self.fired_rules is None
        ):
            msg = f"la fila '{self.id}' del escenario 'explanation' no trae sus recuentos y su `expected`"
            raise ValueError(msg)
        if self.scenario == "agency-actions" and self.expected_actions is None:
            msg = f"la fila '{self.id}' del escenario 'agency-actions' no trae `expected_actions`"
            raise ValueError(msg)
        if self.decided_by_kind is not None and self.state is not CaseState.CLOSED:
            # Un caso sin cerrar con decisor seria un caso decidido que sigue
            # abierto: no existe, y sembrarlo mediria algo que el sistema no hace.
            msg = f"la fila '{self.id}' declara quien decidio y su estado no es 'closed'"
            raise ValueError(msg)
        return self


class InboxFixtures(Frozen):
    """Los escenarios de la bandeja de un idioma."""

    language: Locale
    rows: tuple[InboxFixtureRow, ...]

    @model_validator(mode="after")
    def _identificadores_unicos(self) -> Self:
        ids = [fila.id for fila in self.rows]
        repetidos = sorted({i for i in ids if ids.count(i) > 1})
        if repetidos:
            msg = f"los escenarios repiten las filas {repetidos}"
            raise ValueError(msg)
        return self

    def rows_for(self, scenario: str) -> tuple[InboxFixtureRow, ...]:
        """Las filas de un escenario, en el orden del archivo."""
        return tuple(fila for fila in self.rows if fila.scenario == scenario)


def fixtures_dir(root: Path) -> Path:
    """Donde viven los escenarios de la bandeja."""
    return root / "app" / "evals" / "fixtures" / "inbox"


def load_inbox_fixtures(language: Locale, root: Path) -> InboxFixtures:
    """Los escenarios de un idioma, validados y nombrando el archivo en cada fallo."""
    archivo = fixtures_dir(root) / f"{language}.yaml"
    if not archivo.is_file():
        msg = (
            f"faltan los escenarios de la bandeja del idioma '{language}': se "
            f"esperaba '{archivo}'. Sin ellos los casos de U14 no se pueden medir"
        )
        raise InboxFixtureError(msg)
    try:
        cargado: Any = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        msg = f"no se pudieron leer los escenarios '{archivo}': {error}"
        raise InboxFixtureError(msg) from error
    try:
        fixtures = InboxFixtures.model_validate(cargado)
    except ValidationError as error:
        msg = f"los escenarios '{archivo}' no validan su esquema: {error}"
        raise InboxFixtureError(msg) from error
    if fixtures.language != language:
        msg = f"'{archivo}' declara el idioma '{fixtures.language}' y se cargo como '{language}'"
        raise InboxFixtureError(msg)
    return fixtures
