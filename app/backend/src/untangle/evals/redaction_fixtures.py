"""Las fixtures sembradas de la redaccion: que hay en ellas y como se leen.

Viven versionadas en `app/evals/fixtures/redaction/`, **un archivo por idioma de
turno**, y no se generan en tiempo de corrida (practica del equipo sobre datos de
prueba). Dos consumidores las leen: las sondas de DS-6 de este mismo paquete y
las pruebas unitarias del detector. Una sola fuente de datos sembrados, para que
la compuerta y la prueba no midan cosas distintas.

El modulo vive aparte de las sondas para que las pruebas del detector puedan
leerlas **sin** arrastrar la superficie de la redaccion: una prueba de la capa de
deteccion no deberia caerse porque la capa de encima todavia no exista.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, ValidationError

from untangle.base import Frozen, Locale
from untangle.compliance.redaction.recognizers.models import EntityType


class FixtureLoadError(Exception):
    """Las fixtures sembradas no se pudieron cargar. El mensaje nombra el archivo."""


class Seed(Frozen):
    """Un turno sembrado: su dato, su forma de escritura y su texto.

    `value` es lo que **no** puede quedar en el texto que sale. Vive en un
    archivo versionado, no se genera en tiempo de corrida (practica del equipo:
    un archivo por caso, con identificador estable).
    """

    id: str = Field(min_length=1)
    entity_type: EntityType
    form: str = Field(min_length=1)
    value: str = Field(min_length=1)
    text: str = Field(min_length=1)
    #: Solo en los turnos de RT-15: en que idioma viene dictado el dato.
    dictated_in: Locale | None = None
    #: Solo en los turnos de RT-15: que juego de reconocedores debe encontrarlo.
    found_by_language: Locale | None = None


class SeededFixtures(Frozen):
    """Las fixtures de un idioma de turno: las de RT-14 y las de RT-15."""

    language: Locale
    seeds: tuple[Seed, ...]
    cross_language: tuple[Seed, ...]


def fixtures_dir(root: Path) -> Path:
    """Donde viven las fixtures sembradas de la redaccion."""
    return root / "app" / "evals" / "fixtures" / "redaction"


def load_fixtures(language: Locale, root: Path) -> SeededFixtures:
    """Las fixtures sembradas de un idioma, validadas y nombrando el archivo."""
    archivo = fixtures_dir(root) / f"{language}.yaml"
    if not archivo.is_file():
        msg = (
            f"faltan las fixtures sembradas del idioma '{language}': se esperaba "
            f"'{archivo}'. Sin ellas RT-14 y RT-15 no se pueden medir, y una "
            "compuerta que no se pudo ejecutar se declara no medida, jamas verde."
        )
        raise FixtureLoadError(msg)

    try:
        cargado: Any = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        msg = f"no se pudieron leer las fixtures '{archivo}': {error}"
        raise FixtureLoadError(msg) from error

    try:
        return SeededFixtures.model_validate(cargado)
    except ValidationError as error:
        msg = f"las fixtures '{archivo}' no validan su esquema: {error}"
        raise FixtureLoadError(msg) from error


def expected_recognizer_id(seed: Seed) -> str:
    """El identificador del reconocedor que **tiene** que encontrar la semilla.

    Los identificadores de los reconocedores propios son `<idioma>-<tipo>`, con
    el tipo en guiones. Que la sonda lo componga en vez de leerlo de la
    configuracion es deliberado: si alguien renombra un reconocedor, esta sonda
    falla y obliga a decidirlo a la vista, en lugar de seguir midiendo otra cosa.
    """
    idioma = seed.found_by_language or "es"
    return f"{idioma}-{seed.entity_type.value.replace('_', '-')}"
