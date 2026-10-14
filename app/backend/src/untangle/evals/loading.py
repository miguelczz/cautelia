"""Carga de los casos, los subconjuntos y el manifiesto desde archivos.

Para U1 el "almacen" son archivos versionados, no una base de datos (decision
CG-1). Dos cosas que este modulo hace a proposito y que se notan solo cuando
faltan:

1. **Ordena el listado del sistema de archivos antes de usarlo.** El orden que
   devuelve el sistema de archivos no es una garantia, y una corrida que ejecuta
   los mismos casos en otro orden deja de ser comparable con la anterior
   (REL-U1.1).
2. **Nombra el archivo y la clave en cada fallo.** Una carga que solo dice
   "invalido" no ayuda a nadie a las seis semanas.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from untangle import paths
from untangle.evals.models import Dataset, GoldenCase, SubsetDefinition


class LoadError(Exception):
    """Un archivo versionado no se pudo cargar. El mensaje nombra el archivo."""


class DatasetDeclaration(BaseModel):
    """Lo que el manifiesto declara de un conjunto de datos (BR1.9)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset: Dataset
    count: int = Field(default=0, ge=0)
    built: bool = True
    reason: str | None = None
    runs_per_delivery: bool = False

    @model_validator(mode="after")
    def _un_conjunto_no_construido_declara_su_razon(self) -> Self:
        if not self.built and not self.reason:
            msg = (
                f"el conjunto '{self.dataset.value}' figura como no construido y "
                "no declara su razon (BR1.9)"
            )
            raise ValueError(msg)
        return self


class DatasetManifest(BaseModel):
    """El manifiesto de los ocho conjuntos de datos."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    datasets: tuple[DatasetDeclaration, ...]

    @model_validator(mode="after")
    def _los_ocho_conjuntos_figuran_una_sola_vez(self) -> Self:
        declarados = [d.dataset for d in self.datasets]
        repetidos = {d.value for d in declarados if declarados.count(d) > 1}
        if repetidos:
            msg = f"el manifiesto repite los conjuntos {sorted(repetidos)}"
            raise ValueError(msg)
        faltan = sorted({d.value for d in Dataset} - {d.value for d in declarados})
        if faltan:
            msg = f"el manifiesto no declara los conjuntos {faltan} (BR1.9)"
            raise ValueError(msg)
        return self

    def declaration_for(self, dataset: Dataset) -> DatasetDeclaration:
        for declaracion in self.datasets:
            if declaracion.dataset is dataset:
                return declaracion
        msg = f"el manifiesto no declara el conjunto '{dataset.value}'"
        raise LoadError(msg)


def _read_yaml(path: Path) -> dict[str, Any]:
    """Lee un YAML y devuelve su mapa, nombrando el archivo en cada fallo."""
    try:
        crudo = path.read_text(encoding="utf-8")
    except OSError as error:
        msg = f"no se pudo leer '{path}': {error}"
        raise LoadError(msg) from error

    try:
        cargado = yaml.safe_load(crudo)
    except yaml.YAMLError as error:
        msg = f"'{path}' no es YAML valido: {error}"
        raise LoadError(msg) from error

    if cargado is None:
        msg = f"'{path}' esta vacio"
        raise LoadError(msg)
    if not isinstance(cargado, dict):
        msg = f"'{path}' no contiene un mapa en su raiz, sino {type(cargado).__name__}"
        raise LoadError(msg)
    return cargado


def _sorted_yaml_files(root: Path) -> tuple[Path, ...]:
    """Los archivos YAML del arbol, ordenados explicitamente por su ruta."""
    if not root.is_dir():
        return ()
    return tuple(sorted(root.rglob("*.yaml"), key=lambda p: p.as_posix()))


def load_case(path: Path) -> GoldenCase:
    """Un caso de golden set, validado contra su modelo."""
    datos = _read_yaml(path)
    try:
        return GoldenCase.model_validate(datos)
    except ValidationError as error:
        claves = ", ".join(
            ".".join(str(parte) for parte in problema["loc"]) or "(raiz)"
            for problema in error.errors()
        )
        msg = f"el caso '{path}' no valida su esquema; claves: {claves}"
        raise LoadError(msg) from error


def load_cases(root: Path | None = None) -> tuple[GoldenCase, ...]:
    """Todos los casos del arbol, en orden estable por identificador.

    El orden sale del identificador y no del sistema de archivos: es lo que hace
    que dos corridas del mismo commit ejecuten los mismos casos en el mismo
    orden (BR1.7).
    """
    directorio = root if root is not None else paths.cases_dir()
    casos = [load_case(archivo) for archivo in _sorted_yaml_files(directorio)]

    vistos: dict[str, GoldenCase] = {}
    for caso in casos:
        if caso.case_key in vistos:
            msg = f"el identificador '{caso.case_key}' aparece en mas de un archivo"
            raise LoadError(msg)
        vistos[caso.case_key] = caso

    return tuple(sorted(casos, key=lambda c: c.case_key))


def load_subset(name: str, root: Path | None = None) -> SubsetDefinition:
    """La definicion de un subconjunto por su nombre."""
    directorio = root if root is not None else paths.subsets_dir()
    archivo = directorio / f"{name}.yaml"
    if not archivo.is_file():
        msg = f"no existe el subconjunto '{name}': se esperaba el archivo '{archivo}'"
        raise LoadError(msg)

    datos = _read_yaml(archivo)
    try:
        return SubsetDefinition.model_validate(datos)
    except ValidationError as error:
        msg = f"el subconjunto '{archivo}' no valida su esquema: {error}"
        raise LoadError(msg) from error


def load_manifest(path: Path | None = None) -> DatasetManifest:
    """El manifiesto de conjuntos de datos, validado."""
    archivo = path if path is not None else paths.manifest_path()
    if not archivo.is_file():
        msg = f"no existe el manifiesto de conjuntos: se esperaba '{archivo}'"
        raise LoadError(msg)

    datos = _read_yaml(archivo)
    try:
        return DatasetManifest.model_validate(datos)
    except ValidationError as error:
        msg = f"el manifiesto '{archivo}' no valida su esquema: {error}"
        raise LoadError(msg) from error


def check_manifest_counts(
    manifest: DatasetManifest, cases: tuple[GoldenCase, ...]
) -> tuple[str, ...]:
    """Diferencias entre lo que el manifiesto declara y los archivos que hay.

    Devuelve una lista de problemas en lugar de lanzar: el corredor decide que
    hacer con ellos, y asi el mismo chequeo sirve para el guion de verificacion.
    """
    problemas: list[str] = []
    for declaracion in manifest.datasets:
        reales = sum(1 for caso in cases if caso.dataset is declaracion.dataset)
        if not declaracion.built:
            if reales:
                problemas.append(
                    f"el conjunto '{declaracion.dataset.value}' figura como no "
                    f"construido y tiene {reales} casos en el arbol"
                )
            continue
        if reales != declaracion.count:
            problemas.append(
                f"el conjunto '{declaracion.dataset.value}' declara "
                f"{declaracion.count} casos y tiene {reales} en el arbol"
            )
    return tuple(problemas)


def check_language_parity(cases: tuple[GoldenCase, ...]) -> tuple[str, ...]:
    """Los casos que existen en un idioma y no en el otro (P12, NFR20.2).

    La pareja de `DS-6/es/rt-8-emergency` es `DS-6/en/rt-8-emergency`: mismo
    conjunto, mismo sufijo, el otro idioma. Un caso sin pareja es una metrica
    que se publicaria en un idioma y no en el otro, y el reporte por idioma lo
    esconderia en lugar de mostrarlo: cada lado se veria completo por separado.

    Devuelve problemas en lugar de lanzar, como `check_manifest_counts`, para
    que el guion de verificacion los junte con los demas.
    """
    claves = {caso.case_key for caso in cases}
    problemas: list[str] = []
    for caso in cases:
        otro = "en" if caso.language == "es" else "es"
        sufijo = caso.case_key.split("/", 2)[2]
        pareja = f"{caso.dataset.value}/{otro}/{sufijo}"
        if pareja not in claves:
            problemas.append(
                f"el caso '{caso.case_key}' no tiene pareja en '{otro}': se esperaba "
                f"'{pareja}' (P12, NFR20.2)"
            )
    return tuple(problemas)


def resolve_subset_cases(
    subset: SubsetDefinition, cases: tuple[GoldenCase, ...]
) -> tuple[GoldenCase, ...]:
    """Los casos del subconjunto, en el orden de su lista versionada.

    Un identificador de la lista que no exista como archivo detiene la carga
    nombrandolo: una corrida que se salta en silencio un caso declarado produce
    un reporte que miente sobre su cobertura (BR1.6).
    """
    por_clave = {caso.case_key: caso for caso in cases}
    faltantes = [clave for clave in subset.case_keys if clave not in por_clave]
    if faltantes:
        msg = (
            f"el subconjunto '{subset.name}' nombra casos que no existen como "
            f"archivo: {', '.join(faltantes)}"
        )
        raise LoadError(msg)
    return tuple(por_clave[clave] for clave in subset.case_keys)
