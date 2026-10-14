"""El nucleo del generador: compone en memoria, valida todo y solo entonces escribe (F3).

## Las tres fases, y por que estan separadas

1. **Componer** (`render`): lee las fuentes revisadas y la configuracion de
   aseguradoras, pide a cada compositor sus salidas y las pasa a bytes
   canonicos. No escribe nada.
2. **Validar**: cada salida contra su modelo, las rutas contra el arbol, y lo que
   cada compositor declare como problema. Con **un solo** problema no se escribe
   ningun archivo (BR2.2): un corpus a medio regenerar es peor que el anterior
   entero, porque ya no corresponde a ningun manifiesto.
3. **Escribir** (`write`): cada archivo de forma atomica, las salidas que la
   generacion anterior escribio y esta ya no produce se borran, y el manifiesto
   va al final.

## Lo que el nucleo no hace

- **No llama a ningun modelo ni lee ninguna clave** (BR1.5): no importa
  `untangle.providers`, y un contrato de importacion lo comprueba.
- **No lee `tmp/`**: los borradores del modelo no tienen ninguna ruta hasta aqui
  (BR2.1). Las fuentes salen siempre de `app/data/sources/` del repositorio, aunque
  la salida se escriba en un directorio temporal.
- **No borra lo que no escribio.** Un archivo de `app/data/` que no esta en el
  manifiesto anterior ni en la salida nueva detiene la generacion: puede ser una
  entrada puesta en el sitio equivocado, y borrarla seria perder trabajo.
- **No sabe que se compone.** Eso lo aportan los compositores que recibe, en el
  orden de F3.2; el nucleo solo garantiza que lo compongan sin azar ajeno a la
  semilla, sin reloj y sin escribir a medias.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ValidationError

from untangle.synthetic_data.canonical import canonical_bytes, sha256_hex, write_atomic
from untangle.synthetic_data.chooser import ChooserFactory
from untangle.synthetic_data.manifest import (
    MANIFEST_FILE,
    SEED,
    SOURCES_DIRNAME,
    ManifestRecords,
    build_manifest,
    logical_output,
    verify_output,
)
from untangle.synthetic_data.models import (
    DeclaredDifference,
    GenerationManifest,
    ReviewSample,
    SeededCaseRef,
)
from untangle.synthetic_data.sources import (
    SourceBundle,
    SourceLoadError,
    load_sources,
    logical_path,
)
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.config import TENANT_FILE, LoadedTenants
from untangle.tenancy.models import TenantConfigError

__all__ = [
    "Composer",
    "Composition",
    "CompositionContext",
    "CorpusOutput",
    "GenerationError",
    "GenerationRequest",
    "RenderedGeneration",
    "WriteReport",
    "compare",
    "generate",
    "render",
    "write",
]


class GenerationError(RuntimeError):
    """La generacion no escribio nada. Lleva **todos** los problemas encontrados."""

    def __init__(self, problems: tuple[str, ...] | list[str]) -> None:
        self.problems = tuple(problems)
        super().__init__("\n".join(self.problems))


@dataclass(frozen=True)
class CorpusOutput:
    """Una salida: su ruta dentro de `app/data/` y lo que se escribe en ella."""

    relative: str
    document: BaseModel | Mapping[str, object]


@dataclass(frozen=True)
class Composition:
    """Lo que devuelve un compositor: sus salidas, lo que declara y lo que encontro mal."""

    outputs: tuple[CorpusOutput, ...] = ()
    records: ManifestRecords = field(default_factory=ManifestRecords)
    #: Lo que el compositor comprobo sobre el conjunto y no se cumple (un endoso
    #: que no existe, una combinacion de estado sin caso). Uno solo detiene todo.
    problems: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompositionContext:
    """Lo unico que un compositor puede leer: fuentes revisadas, aseguradoras, su carpeta y el azar."""

    sources: SourceBundle
    tenants: LoadedTenants
    chooser: ChooserFactory
    #: La carpeta de configuracion de las aseguradoras (`app/config/tenants`), la misma de la que
    #: salio `tenants`. Un compositor lee de ahi lo que `TenantConfig` no trae, como las reglas.
    tenants_dir: Path


#: Un compositor: una funcion pura de lo que hay en el contexto.
type Composer = Callable[[CompositionContext], Composition]


@dataclass(frozen=True)
class GenerationRequest:
    """Una generacion: de que repositorio lee y donde escribe."""

    repo_root: Path
    #: Donde se escriben las salidas: `app/data/` o un directorio temporal. Las
    #: fuentes se leen **siempre** de `app/data/sources/` del repositorio.
    data_dir: Path
    composers: tuple[Composer, ...]
    seed: int = SEED


@dataclass(frozen=True)
class RenderedGeneration:
    """La generacion entera en memoria: ruta dentro de `app/data/` y bytes."""

    files: dict[str, bytes]
    manifest: GenerationManifest


@dataclass(frozen=True)
class WriteReport:
    """Lo que cambio en disco."""

    written: tuple[str, ...]
    unchanged: tuple[str, ...]
    deleted: tuple[str, ...]


def _oculto(relativa: PurePosixPath) -> bool:
    """Los archivos ocultos (`.DS_Store`, los temporales de la escritura) no son del corpus."""
    return any(parte.startswith(".") for parte in relativa.parts)


def _ruta_de_salida(relativa: str) -> str | None:
    """Por que una ruta no puede ser una salida, o nada si puede."""
    ruta = PurePosixPath(relativa)
    if relativa != ruta.as_posix() or ruta.is_absolute() or ".." in ruta.parts or not relativa:
        return f"'{relativa}': una salida es una ruta relativa dentro de app/data/"
    if ruta.parts[0] == SOURCES_DIRNAME:
        return f"'{relativa}': las fuentes son entrada; el generador nunca escribe en sources/"
    if relativa == MANIFEST_FILE or _oculto(ruta):
        return f"'{relativa}': nombre reservado para el manifiesto o para un archivo oculto"
    return None


def _carpeta_de_aseguradoras(repo_root: Path) -> Path:
    return repo_root / "app" / "config" / "tenants"


def _aseguradoras(repo_root: Path) -> tuple[LoadedTenants, dict[str, str]]:
    """Las aseguradoras, todas validas, y el hash de cada `tenant.yaml` leido.

    Una carpeta rota apaga su aseguradora en el aplicativo, pero aqui **detiene la
    generacion**: un corpus sin una aseguradora no es un corpus mas pequeno, es uno
    que ya no corresponde a la configuracion versionada.
    """
    directorio = _carpeta_de_aseguradoras(repo_root)
    try:
        cargadas = tenancy_config.load(directorio)
    except TenantConfigError as error:
        raise GenerationError([str(error)]) from None
    if cargadas.unavailable:
        raise GenerationError([caida.detail for caida in cargadas.unavailable])
    hashes = {
        logical_path(directorio / t.tenant_id / TENANT_FILE, repo_root): sha256_hex(
            (directorio / t.tenant_id / TENANT_FILE).read_bytes()
        )
        for t in cargadas.available
    }
    return cargadas, hashes


def _componer(
    request: GenerationRequest, contexto: CompositionContext
) -> tuple[dict[str, bytes], ManifestRecords, list[str]]:
    archivos: dict[str, bytes] = {}
    diferencias: list[DeclaredDifference] = []
    casos: list[SeededCaseRef] = []
    muestras: list[ReviewSample] = []
    problemas: list[str] = []
    for compositor in request.composers:
        composicion = compositor(contexto)
        problemas.extend(composicion.problems)
        diferencias.extend(composicion.records.declared_differences)
        casos.extend(composicion.records.seeded_cases)
        muestras.extend(composicion.records.review_samples)
        for salida in composicion.outputs:
            motivo = _ruta_de_salida(salida.relative)
            if motivo is not None:
                problemas.append(motivo)
                continue
            if salida.relative in archivos:
                problemas.append(f"'{salida.relative}': dos piezas escriben la misma salida")
                continue
            contenido = canonical_bytes(salida.document)
            problemas.extend(verify_output(logical_output(salida.relative), contenido))
            archivos[salida.relative] = contenido
    # Las muestras de revision son entrada: se copian al manifiesto tal cual.
    muestras.extend(revision.sample for revision in contexto.sources.reviews)
    registros = ManifestRecords(
        declared_differences=tuple(diferencias),
        seeded_cases=tuple(casos),
        review_samples=tuple(muestras),
    )
    return archivos, registros, problemas


def render(request: GenerationRequest) -> RenderedGeneration:
    """Compone y valida todo en memoria. No escribe nada, ni siquiera si todo esta bien."""
    aseguradoras, hashes_de_configuracion = _aseguradoras(request.repo_root)
    try:
        fuentes = load_sources(
            request.repo_root / "app" / "data" / SOURCES_DIRNAME,
            repo_root=request.repo_root,
            tenants=aseguradoras,
        )
    except SourceLoadError as error:
        raise GenerationError(error.problems) from None

    contexto = CompositionContext(
        sources=fuentes,
        tenants=aseguradoras,
        chooser=ChooserFactory(request.seed),
        tenants_dir=_carpeta_de_aseguradoras(request.repo_root),
    )
    archivos, registros, problemas = _componer(request, contexto)
    if problemas:
        raise GenerationError(problemas)

    try:
        manifiesto = build_manifest(
            seed=request.seed,
            inputs={**fuentes.input_hashes(), **hashes_de_configuracion},
            outputs={logical_output(r): sha256_hex(b) for r, b in archivos.items()},
            records=registros,
        )
    except ValidationError as error:
        raise GenerationError([f"el manifiesto no valida: {error}"]) from None
    archivos[MANIFEST_FILE] = canonical_bytes(manifiesto)
    return RenderedGeneration(files=archivos, manifest=manifiesto)


def _en_disco(data_dir: Path) -> Iterator[str]:
    """Lo que hay en `data_dir` fuera de las fuentes y de lo oculto, en orden."""
    if not data_dir.is_dir():
        return
    for path in sorted(data_dir.rglob("*"), key=lambda p: p.as_posix()):
        relativa = PurePosixPath(path.relative_to(data_dir).as_posix())
        if path.is_file() and relativa.parts[0] != SOURCES_DIRNAME and not _oculto(relativa):
            yield relativa.as_posix()


def _salidas_anteriores(data_dir: Path) -> set[str]:
    """Lo que la generacion anterior escribio, segun su manifiesto."""
    ruta = data_dir / MANIFEST_FILE
    if not ruta.is_file():
        return set()
    try:
        anterior = GenerationManifest.model_validate_json(ruta.read_bytes())
    except (ValidationError, json.JSONDecodeError):
        return set()
    prefijo = logical_output("")
    return {salida.removeprefix(prefijo) for salida in anterior.outputs} | {MANIFEST_FILE}


def write(rendered: RenderedGeneration, data_dir: Path) -> WriteReport:
    """Escribe la generacion. Antes de tocar nada comprueba que no pisa nada ajeno."""
    existentes = set(_en_disco(data_dir))
    anteriores = _salidas_anteriores(data_dir)
    ajenos = sorted(existentes - rendered.files.keys() - anteriores)
    if ajenos:
        raise GenerationError(
            [
                f"'{logical_output(r)}': esta en app/data/ y el generador no lo escribio: "
                "no se borra algo ajeno. Si es una entrada, va en sources/; si sobra, "
                "borrelo a mano y vuelva a generar"
                for r in ajenos
            ]
        )

    escritos: list[str] = []
    iguales: list[str] = []
    # El manifiesto al final: mientras no se escribe, el manifiesto en disco sigue
    # siendo el de la generacion anterior, y un corte a mitad se detecta.
    orden = sorted(rendered.files, key=lambda r: (r == MANIFEST_FILE, r))
    for relativa in orden:
        destino = data_dir / relativa
        contenido = rendered.files[relativa]
        if destino.is_file() and destino.read_bytes() == contenido:
            iguales.append(relativa)
            continue
        write_atomic(destino, contenido)
        escritos.append(relativa)

    borrados = sorted((existentes & anteriores) - rendered.files.keys())
    for relativa in borrados:
        (data_dir / relativa).unlink()
        _quitar_vacios((data_dir / relativa).parent, data_dir)
    return WriteReport(written=tuple(escritos), unchanged=tuple(iguales), deleted=tuple(borrados))


def _quitar_vacios(directorio: Path, data_dir: Path) -> None:
    """Quita los directorios que quedaron vacios al borrar, sin salir de `data_dir`."""
    while directorio != data_dir and directorio.is_dir() and not any(directorio.iterdir()):
        directorio.rmdir()
        directorio = directorio.parent


def generate(request: GenerationRequest) -> WriteReport:
    """Compone, valida y escribe. Si algo falla antes de escribir, no escribe nada."""
    return write(render(request), request.data_dir)


def compare(generated_dir: Path, versioned_dir: Path) -> list[str]:
    """Lo que difiere entre una regeneracion limpia y lo versionado (TECH-U7.1).

    Una linea por archivo, con su ruta logica: quien la lee tiene que saber que
    archivo se edito a mano o que fuente cambio sin regenerar.
    """
    generados = set(_en_disco(generated_dir))
    versionados = set(_en_disco(versioned_dir))
    diferencias: list[str] = []
    for relativa in sorted(generados - versionados):
        diferencias.append(
            f"'{logical_output(relativa)}': el generador lo produce y no esta versionado"
        )
    for relativa in sorted(versionados - generados):
        diferencias.append(
            f"'{logical_output(relativa)}': esta versionado y el generador no lo produce"
        )
    for relativa in sorted(generados & versionados):
        if (generated_dir / relativa).read_bytes() != (versioned_dir / relativa).read_bytes():
            diferencias.append(
                f"'{logical_output(relativa)}': difiere de lo que produce el generador; se edito a "
                "mano o una fuente cambio sin regenerar"
            )
    return diferencias
