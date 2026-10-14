"""Carga los textos fuente revisados, y rechaza el que no lo esta (BR2.2).

La carpeta tiene una forma fija, y cualquier cosa fuera de ella es un problema
que se nombra, no algo que se ignora:

    app/data/sources/<aseguradora>/<idioma>/<parte>.yaml   un SourceFile por parte
    app/data/sources/reviews/<aseguradora>-<fecha>.yaml    una ReviewSample
    app/data/sources/differences.yaml                      las diferencias declaradas (BR3.7)
    app/data/sources/seeded_criteria.yaml                  los criterios con caso sembrado (BR6.2)

Todo se valida **antes** de devolver nada, y los problemas se juntan en vez de
parar en el primero: quien revisa veinte archivos quiere la lista entera en una
corrida, no veinte corridas.

## Lo que se comprueba contra la configuracion

El modelo solo sabe la forma de un identificador de aseguradora; aqui se
comprueba contra `app/config/tenants/` que la aseguradora exista y **sea una
emisora**: una agencia no tiene textos propios, sus copias salen de los de sus
emisoras (BR4.2). La unica fuente que una agencia si tiene son los turnos de
**sus** casos sembrados (`case_turns.yaml`, FD-U7-7): el caso es suyo, no una
copia. Y que cada identificador empiece por el prefijo de sus numeros de caso
(FD-U7-1). Ninguna aseguradora se nombra en este archivo.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import ValidationError

from untangle.synthetic_data.canonical import sha256_hex
from untangle.synthetic_data.models import (
    CASE_TURNS_FILE_KEY,
    DIFFERENCES_FILE,
    POOLS_FILE_KEY,
    SEEDED_CRITERIA_FILE,
    DifferenceFile,
    PolicyPart,
    ReviewSample,
    SeededCriteriaFile,
    SourceFile,
    SourceText,
)
from untangle.tenancy.config import LoadedTenants
from untangle.tenancy.models import TenantConfig, TenantKind

__all__ = [
    "REVIEWS_DIR",
    "LoadedReview",
    "LoadedRootFile",
    "LoadedSourceFile",
    "SourceBundle",
    "SourceLoadError",
    "load_sources",
    "logical_path",
    "validation_problems",
]

#: La subcarpeta de las muestras que revisa Miguel (BR5.4).
REVIEWS_DIR = "reviews"

#: Los nombres de archivo validos de una parte: las diez partes, los repertorios
#: y los turnos de los casos sembrados.
_PARTES_VALIDAS = frozenset({p.value for p in PolicyPart} | {POOLS_FILE_KEY, CASE_TURNS_FILE_KEY})

#: Los archivos de la raiz, que no son de ninguna aseguradora, y su modelo.
_ARCHIVOS_DE_RAIZ: dict[str, type[DifferenceFile] | type[SeededCriteriaFile]] = {
    DIFFERENCES_FILE: DifferenceFile,
    SEEDED_CRITERIA_FILE: SeededCriteriaFile,
}


class SourceLoadError(ValueError):
    """Uno o mas textos fuente no se pueden usar. Lleva **todos** los problemas."""

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems = tuple(problems)
        super().__init__("\n".join(self.problems))


@dataclass(frozen=True)
class LoadedSourceFile:
    """Un archivo de parte, validado, con su ruta logica y su hash."""

    logical: str
    sha256: str
    header: SourceFile
    texts: tuple[SourceText, ...]


@dataclass(frozen=True)
class LoadedReview:
    """Una muestra de revision, validada, con su ruta logica y su hash."""

    logical: str
    sha256: str
    sample: ReviewSample


@dataclass(frozen=True)
class LoadedRootFile[T: (DifferenceFile, SeededCriteriaFile)]:
    """Un archivo de la raiz de las fuentes, validado, con su ruta logica y su hash."""

    logical: str
    sha256: str
    content: T


@dataclass(frozen=True)
class SourceBundle:
    """Todo lo que la composicion puede leer de `app/data/sources/`, y nada mas."""

    files: tuple[LoadedSourceFile, ...]
    reviews: tuple[LoadedReview, ...]
    differences: LoadedRootFile[DifferenceFile] | None = None
    criteria: LoadedRootFile[SeededCriteriaFile] | None = None

    @property
    def texts(self) -> tuple[SourceText, ...]:
        return tuple(texto for archivo in self.files for texto in archivo.texts)

    def input_hashes(self) -> dict[str, str]:
        """El hash de cada archivo leido, por su ruta logica (BR1.4)."""
        hashes = {archivo.logical: archivo.sha256 for archivo in self.files}
        hashes.update({revision.logical: revision.sha256 for revision in self.reviews})
        for raiz in (self.differences, self.criteria):
            if raiz is not None:
                hashes[raiz.logical] = raiz.sha256
        return hashes


def logical_path(path: Path, repo_root: Path) -> str:
    """La ruta desde la raiz del repositorio, en forma POSIX: como la nombra el manifiesto."""
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def validation_problems(
    error: ValidationError, where: str, raw: Mapping[str, Any] | None = None
) -> list[str]:
    """Un problema por error de validacion, nombrando el archivo y la clave.

    Si el error cae dentro de una entrada de `texts`, se nombra tambien su
    `source_id`: "texts[7]" solo no le dice nada a quien abre el archivo.
    """
    problemas: list[str] = []
    for problema in error.errors():
        ruta = problema["loc"]
        clave = _clave_legible(ruta, raw)
        if problema["type"] == "missing":
            detalle = f"falta '{ruta[-1]}'"
            if ruta[-1] in {"reviewed_at", "reviewed_by", "drafted_with"}:
                detalle += ": un texto sin marca de revision no entra al corpus (BR2.2)"
        else:
            detalle = str(problema["msg"]).removeprefix("Value error, ")
        problemas.append(f"'{where}': {clave}: {detalle}")
    return problemas


def _clave_legible(ruta: tuple[int | str, ...], raw: Mapping[str, Any] | None) -> str:
    partes: list[str] = []
    for parte in ruta:
        if isinstance(parte, int) and partes:
            partes[-1] = f"{partes[-1]}[{parte}]"
        else:
            partes.append(str(parte))
    legible = ".".join(partes) or "(raiz)"
    if raw is not None and len(ruta) >= 2 and ruta[0] == "texts" and isinstance(ruta[1], int):
        entradas = raw.get("texts")
        if isinstance(entradas, list) and ruta[1] < len(entradas):
            entrada = entradas[ruta[1]]
            if isinstance(entrada, Mapping) and isinstance(entrada.get("source_id"), str):
                legible += f" ({entrada['source_id']})"
    return legible


def _leer_yaml(path: Path, where: str) -> tuple[bytes, Mapping[str, Any]]:
    crudo = path.read_bytes()
    try:
        datos = yaml.safe_load(crudo.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        msg = f"'{where}': no es YAML valido en UTF-8: {error}"
        raise SourceLoadError([msg]) from None
    if not isinstance(datos, Mapping):
        msg = f"'{where}': no contiene un mapa en su raiz"
        raise SourceLoadError([msg])
    return crudo, cast("Mapping[str, Any]", datos)


def _emisora(
    tenants: LoadedTenants, tenant_id: str, where: str, *, case_turns: bool = False
) -> TenantConfig:
    """La aseguradora de un archivo, que tiene que existir y ser una emisora.

    Con una excepcion: los turnos de los casos sembrados de una agencia son suyos.
    """
    tenant = tenants.get(tenant_id)
    if tenant is None:
        disponibles = ", ".join(tenants.ids) or "(ninguna)"
        msg = f"'{where}': la aseguradora '{tenant_id}' no existe; disponibles: {disponibles}"
        raise SourceLoadError([msg])
    if tenant.kind is not TenantKind.CARRIER and not case_turns:
        msg = (
            f"'{where}': '{tenant_id}' es una agencia y no tiene textos propios: sus copias "
            "salen de los textos de sus emisoras (BR4.2)"
        )
        raise SourceLoadError([msg])
    return tenant


def _cargar_parte(
    path: Path, *, repo_root: Path, sources_dir: Path, tenants: LoadedTenants
) -> LoadedSourceFile:
    where = logical_path(path, repo_root)
    tenant_carpeta, idioma_carpeta = path.relative_to(sources_dir).parts[:2]
    crudo, datos = _leer_yaml(path, where)
    try:
        cabecera = SourceFile.model_validate(datos)
    except ValidationError as error:
        raise SourceLoadError(validation_problems(error, where, datos)) from None

    problemas: list[str] = []
    for campo, dicho, esperado in (
        ("tenant_id", cabecera.tenant_id, tenant_carpeta),
        ("language", cabecera.language, idioma_carpeta),
        ("part_key", str(cabecera.part_key), path.stem),
    ):
        if dicho != esperado:
            problemas.append(
                f"'{where}': {campo}: la cabecera dice '{dicho}' y la ruta '{esperado}'"
            )
    if problemas:
        raise SourceLoadError(problemas)

    tenant = _emisora(
        tenants,
        cabecera.tenant_id,
        where,
        case_turns=str(cabecera.part_key) == CASE_TURNS_FILE_KEY,
    )
    for indice, entrada in enumerate(cabecera.texts):
        if not entrada.source_id.startswith(f"{tenant.case_number_prefix}-"):
            problemas.append(
                f"'{where}': texts[{indice}] ({entrada.source_id}): no empieza por el prefijo "
                f"'{tenant.case_number_prefix}' de su aseguradora (FD-U7-1)"
            )
    if problemas:
        raise SourceLoadError(problemas)

    textos = tuple(
        SourceText.model_validate(
            {
                **entrada.model_dump(),
                "tenant_id": cabecera.tenant_id,
                "language": cabecera.language,
            }
        )
        for entrada in cabecera.texts
    )
    return LoadedSourceFile(logical=where, sha256=sha256_hex(crudo), header=cabecera, texts=textos)


def _cargar_revision(path: Path, *, repo_root: Path, tenants: LoadedTenants) -> LoadedReview:
    where = logical_path(path, repo_root)
    crudo, datos = _leer_yaml(path, where)
    try:
        muestra = ReviewSample.model_validate(datos)
    except ValidationError as error:
        raise SourceLoadError(validation_problems(error, where, datos)) from None
    _emisora(tenants, muestra.tenant_id, where)
    if not path.stem.startswith(f"{muestra.tenant_id}-"):
        msg = f"'{where}': el archivo se llama <aseguradora>-<fecha>.yaml y es de '{muestra.tenant_id}'"
        raise SourceLoadError([msg])
    return LoadedReview(logical=where, sha256=sha256_hex(crudo), sample=muestra)


@dataclass
class _Clasificados:
    partes: list[Path]
    revisiones: list[Path]
    raiz: list[Path]
    inesperados: list[str]


def _clasificar(sources_dir: Path, repo_root: Path) -> _Clasificados:
    """Separa los archivos de parte, las revisiones, los de la raiz y lo que sobra."""
    hallados = _Clasificados(partes=[], revisiones=[], raiz=[], inesperados=[])
    for path in sorted(sources_dir.rglob("*"), key=lambda p: p.as_posix()):
        if not path.is_file():
            continue
        relativa = path.relative_to(sources_dir).parts
        if len(relativa) == 1 and relativa[0] in _ARCHIVOS_DE_RAIZ:
            hallados.raiz.append(path)
        elif relativa[0] == REVIEWS_DIR and len(relativa) == 2 and path.suffix == ".yaml":
            hallados.revisiones.append(path)
        elif len(relativa) == 3 and path.suffix == ".yaml" and path.stem in _PARTES_VALIDAS:
            hallados.partes.append(path)
        else:
            hallados.inesperados.append(
                f"'{logical_path(path, repo_root)}': archivo inesperado; las fuentes son "
                "<aseguradora>/<idioma>/<parte>.yaml, reviews/<aseguradora>-<fecha>.yaml, "
                f"{DIFFERENCES_FILE} y {SEEDED_CRITERIA_FILE}"
            )
    return hallados


def _cargar_raiz(
    path: Path, *, repo_root: Path
) -> tuple[str, str, DifferenceFile | SeededCriteriaFile]:
    """Un archivo de la raiz: su ruta logica, su hash y su contenido validado."""
    where = logical_path(path, repo_root)
    crudo, datos = _leer_yaml(path, where)
    try:
        contenido = _ARCHIVOS_DE_RAIZ[path.name].model_validate(datos)
    except ValidationError as error:
        raise SourceLoadError(validation_problems(error, where, datos)) from None
    return where, sha256_hex(crudo), contenido


def _cargar_raices(
    paths: Iterable[Path], repo_root: Path, problemas: list[str]
) -> tuple[LoadedRootFile[DifferenceFile] | None, LoadedRootFile[SeededCriteriaFile] | None]:
    """Los dos archivos de la raiz, si estan; sus problemas se anaden a la lista."""
    diferencias: LoadedRootFile[DifferenceFile] | None = None
    criterios: LoadedRootFile[SeededCriteriaFile] | None = None
    for path in paths:
        try:
            where, huella, contenido = _cargar_raiz(path, repo_root=repo_root)
        except SourceLoadError as error:
            problemas.extend(error.problems)
            continue
        if isinstance(contenido, DifferenceFile):
            diferencias = LoadedRootFile(logical=where, sha256=huella, content=contenido)
        else:
            criterios = LoadedRootFile(logical=where, sha256=huella, content=contenido)
    return diferencias, criterios


def _repetidos_entre_archivos(files: Iterable[LoadedSourceFile]) -> list[str]:
    """Un identificador repetido entre dos archivos de la misma aseguradora (BR3.2)."""
    vistos: dict[tuple[str, str], str] = {}
    problemas: list[str] = []
    for archivo in files:
        for texto in archivo.texts:
            clave = (texto.tenant_id, texto.source_id)
            if clave in vistos and vistos[clave] != archivo.logical:
                problemas.append(
                    f"'{archivo.logical}': '{texto.source_id}' ya esta en '{vistos[clave]}': "
                    "un identificador es unico dentro de la aseguradora (BR3.2)"
                )
            vistos.setdefault(clave, archivo.logical)
    return problemas


def load_sources(sources_dir: Path, *, repo_root: Path, tenants: LoadedTenants) -> SourceBundle:
    """Todas las fuentes, validadas, o un `SourceLoadError` con todos los problemas."""
    if not sources_dir.is_dir():
        msg = (
            f"no hay textos fuente: no existe '{logical_path(sources_dir.parent, repo_root)}/"
            f"{sources_dir.name}'. Se escriben revisando los borradores de "
            "`mise run synthetic:draft` (F2)"
        )
        raise SourceLoadError([msg])

    hallados = _clasificar(sources_dir, repo_root)
    partes, revisiones, problemas = hallados.partes, hallados.revisiones, hallados.inesperados
    if not partes:
        problemas.append(
            f"no hay textos fuente en '{logical_path(sources_dir, repo_root)}': sin ellos no "
            "hay nada que componer"
        )

    archivos: list[LoadedSourceFile] = []
    for path in partes:
        try:
            archivos.append(
                _cargar_parte(path, repo_root=repo_root, sources_dir=sources_dir, tenants=tenants)
            )
        except SourceLoadError as error:
            problemas.extend(error.problems)

    muestras: list[LoadedReview] = []
    for path in revisiones:
        try:
            muestras.append(_cargar_revision(path, repo_root=repo_root, tenants=tenants))
        except SourceLoadError as error:
            problemas.extend(error.problems)

    diferencias, criterios = _cargar_raices(hallados.raiz, repo_root, problemas)
    problemas.extend(_repetidos_entre_archivos(archivos))
    if problemas:
        raise SourceLoadError(problemas)
    return SourceBundle(
        files=tuple(archivos),
        reviews=tuple(muestras),
        differences=diferencias,
        criteria=criterios,
    )
