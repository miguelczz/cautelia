"""El manifiesto de la generacion, y la comprobacion del arbol contra el (BR1.4).

El manifiesto es la prueba de que lo versionado en `app/data/` salio de unas
entradas y de una semilla: registra el hash de cada entrada leida y de cada
salida escrita. U8 lo compara antes de ingerir (C-26), y `schema:check` lo
compara en cada corrida del guion (TECH-U7.2).

## Lo que la comprobacion afirma

- Todo archivo de `app/data/` fuera de `sources/` esta en el manifiesto, con el
  mismo hash. Un JSON corregido a mano se nombra.
- Toda salida del manifiesto existe.
- Toda entrada del manifiesto existe y no cambio desde que se genero, y ningun
  archivo de `sources/` falta en el: una fuente nueva sin regenerar se nombra.
- **Toda copia de una agencia es identica a su original** (BR4.2): un formulario
  o un archivo de clausulas cuya emisora no es la aseguradora de la carpeta se
  compara byte a byte con el de la emisora. La comprobacion no necesita la
  configuracion: la emisora esta escrita en el propio formulario.

## Antes de la primera generacion

Si no hay manifiesto **ni** corpus, no hay nada que comprobar todavia y se dice
asi --"no medido"-- en vez de callarlo o de fallar: DS-8 vive en `app/data/`
desde U2, escrita a mano, y el manifiesto la cuenta desde que el generador la
regenera. Si hay corpus y no manifiesto, eso si es un problema.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ValidationError

from untangle.synthetic_data.canonical import sha256_hex
from untangle.synthetic_data.models import (
    DATA_PREFIX,
    MANIFEST_OUTPUT,
    MANIFEST_VERSION,
    PERSONAL_VALUES_OUTPUT,
    ClauseFile,
    ClauseRelationFile,
    DeclaredDifference,
    FormRecord,
    GenerationManifest,
    IssuedPolicyRecord,
    PersonalValueList,
    ReviewSample,
    SeededCaseRecord,
    SeededCaseRef,
)
from untangle.synthetic_data.sources import validation_problems

__all__ = [
    "GENERATOR_VERSION",
    "MANIFEST_FILE",
    "SEED",
    "ManifestRecords",
    "build_manifest",
    "corpus_notice",
    "logical_output",
    "output_model_for",
    "verify_copies",
    "verify_output",
    "verify_tree",
]

#: La semilla de todo el conjunto: la misma que DS-8 fijo en U2 (FD-U7-4).
SEED: Final = 20260916

#: La version del generador. Cambia cuando cambia **como** se compone, aunque las
#: fuentes no cambien: es lo que distingue en el manifiesto dos corpus que salieron
#: de las mismas entradas por caminos distintos.
GENERATOR_VERSION: Final = "1"

MANIFEST_FILE: Final = "manifest.json"

#: La carpeta de entradas dentro de `app/data/`: el generador nunca escribe ahi.
SOURCES_DIRNAME: Final = "sources"

#: Que modelo valida cada salida, por su ruta logica. Una salida que no esta aqui
#: --DS-8, que tiene el formato que fijo U2-- se comprueba solo por su hash.
_MODELOS_POR_RUTA: Final[tuple[tuple[re.Pattern[str], type[BaseModel]], ...]] = (
    (re.compile(r"^app/data/tenants/[^/]+/forms/[^/]+\.json$"), FormRecord),
    (re.compile(r"^app/data/tenants/[^/]+/clauses/[^/]+\.json$"), ClauseFile),
    (re.compile(r"^app/data/tenants/[^/]+/clause_relations\.json$"), ClauseRelationFile),
    (re.compile(r"^app/data/tenants/[^/]+/issued_policies/[^/]+\.json$"), IssuedPolicyRecord),
    (re.compile(r"^app/data/tenants/[^/]+/cases/(?:es|en)/[^/]+\.json$"), SeededCaseRecord),
    (re.compile(rf"^{re.escape(PERSONAL_VALUES_OUTPUT)}$"), PersonalValueList),
)


def logical_output(relative: str) -> str:
    """La ruta logica de una salida a partir de su ruta dentro de `app/data/`."""
    return f"{DATA_PREFIX}{relative}"


def output_model_for(logical: str) -> type[BaseModel] | None:
    """El modelo que valida esa salida, o nada si solo se comprueba su hash."""
    for patron, modelo in _MODELOS_POR_RUTA:
        if patron.fullmatch(logical):
            return modelo
    return None


def verify_output(logical: str, data: bytes) -> list[str]:
    """Una salida contra su modelo, nombrando el archivo y la clave si no valida."""
    modelo = output_model_for(logical)
    if modelo is None:
        return []
    try:
        modelo.model_validate_json(data)
    except ValidationError as error:
        return validation_problems(error, logical)
    return []


@dataclass(frozen=True)
class ManifestRecords:
    """Lo que el manifiesto registra ademas de los hashes: lo declara la composicion."""

    declared_differences: tuple[DeclaredDifference, ...] = ()
    seeded_cases: tuple[SeededCaseRef, ...] = ()
    review_samples: tuple[ReviewSample, ...] = ()


def build_manifest(
    *,
    seed: int,
    inputs: dict[str, str],
    outputs: dict[str, str],
    records: ManifestRecords,
) -> GenerationManifest:
    """El manifiesto de una generacion, con todo lo que es lista ya ordenado.

    Ordenar aqui y no en quien llama es lo que hace que el orden en que la
    composicion produjo las cosas no llegue a los bytes (BR1.1).
    """
    return GenerationManifest(
        manifest_version=MANIFEST_VERSION,
        seed=seed,
        generator_version=GENERATOR_VERSION,
        inputs=dict(sorted(inputs.items())),
        outputs=dict(sorted(outputs.items())),
        declared_differences=tuple(
            sorted(records.declared_differences, key=lambda d: d.difference_id)
        ),
        seeded_cases=tuple(sorted(records.seeded_cases, key=lambda c: c.case_key)),
        review_samples=tuple(
            sorted(records.review_samples, key=lambda r: (r.tenant_id, r.sample_seed, r.clause_ids))
        ),
    )


def _archivos_del_arbol(data_dir: Path) -> dict[str, Path]:
    """Las salidas que hay en disco: todo `app/data/` menos las fuentes y el manifiesto."""
    encontrados: dict[str, Path] = {}
    if not data_dir.is_dir():
        return encontrados
    for path in sorted(data_dir.rglob("*"), key=lambda p: p.as_posix()):
        if not path.is_file():
            continue
        relativa = path.relative_to(data_dir)
        if relativa.parts[0] == SOURCES_DIRNAME or relativa.as_posix() == MANIFEST_FILE:
            continue
        encontrados[logical_output(relativa.as_posix())] = path
    return encontrados


def _fuentes_del_arbol(data_dir: Path) -> set[str]:
    fuentes = data_dir / SOURCES_DIRNAME
    if not fuentes.is_dir():
        return set()
    return {
        logical_output(p.relative_to(data_dir).as_posix())
        for p in fuentes.rglob("*")
        if p.is_file()
    }


def corpus_notice(data_dir: Path) -> str | None:
    """Lo que se dice cuando todavia no hay nada que comprobar, o nada si si lo hay."""
    if (data_dir / MANIFEST_FILE).is_file() or (data_dir / "tenants").exists():
        return None
    return (
        "manifiesto del corpus: no medido, porque todavia no se ha generado el corpus en "
        "app/data/ (se genera con `mise run synthetic:generate`)"
    )


def _cargar(path: Path) -> tuple[GenerationManifest | None, list[str]]:
    try:
        crudo = path.read_bytes()
        return GenerationManifest.model_validate_json(crudo), []
    except ValidationError as error:
        return None, validation_problems(error, MANIFEST_OUTPUT)
    except (OSError, json.JSONDecodeError) as error:
        return None, [f"'{MANIFEST_OUTPUT}': no se pudo leer: {error}"]


def verify_tree(repo_root: Path, data_dir: Path | None = None) -> list[str]:
    """El arbol de `app/data/` contra su manifiesto (BR1.4, TECH-U7.2)."""
    datos = data_dir if data_dir is not None else repo_root / "app" / "data"
    ruta_manifiesto = datos / MANIFEST_FILE
    if not ruta_manifiesto.is_file():
        if (datos / "tenants").exists():
            return [
                f"falta '{MANIFEST_OUTPUT}': hay corpus y nada dice de que entradas salio "
                "(BR1.4). Regenerelo con `mise run synthetic:generate`"
            ]
        return []

    manifiesto, problemas = _cargar(ruta_manifiesto)
    if manifiesto is None:
        return problemas
    problemas.extend(_comparar_salidas(manifiesto, datos))
    problemas.extend(_comparar_entradas(manifiesto, repo_root, datos))
    problemas.extend(verify_copies(datos))
    return problemas


def _emisora_de(formulario: Path) -> str | None:
    """La emisora que declara un formulario, o nada si no se puede leer."""
    try:
        return FormRecord.model_validate_json(formulario.read_bytes()).issuer_tenant
    except (OSError, ValidationError):
        return None


def verify_copies(data_dir: Path) -> list[str]:
    """Cada copia de una agencia, contra su original de la emisora (BR4.1, BR4.2)."""
    problemas: list[str] = []
    for formulario in sorted(data_dir.glob("tenants/*/forms/*.json"), key=lambda p: p.as_posix()):
        duena = formulario.parent.parent.name
        emisora = _emisora_de(formulario)
        if emisora is None or emisora == duena:
            continue
        for tipo in ("forms", "clauses"):
            copia = data_dir / "tenants" / duena / tipo / formulario.name
            original = data_dir / "tenants" / emisora / tipo / formulario.name
            donde = logical_output(copia.relative_to(data_dir).as_posix())
            if not original.is_file():
                problemas.append(f"'{donde}': es copia de '{emisora}', que no tiene ese archivo")
            elif not copia.is_file() or copia.read_bytes() != original.read_bytes():
                problemas.append(
                    f"'{donde}': la copia no es identica a su original de '{emisora}'; las "
                    "copias salen del original en la misma generacion (BR4.2)"
                )
    return problemas


def _comparar_salidas(manifiesto: GenerationManifest, datos: Path) -> list[str]:
    """Cada salida en disco contra su hash y su modelo, y cada salida listada en disco."""
    problemas: list[str] = []
    reales = _archivos_del_arbol(datos)
    for ruta in sorted(reales.keys() - manifiesto.outputs.keys()):
        problemas.append(
            f"'{ruta}': esta en app/data/ y no en el manifiesto; el generador no lo produjo"
        )
    for ruta in sorted(manifiesto.outputs.keys() - reales.keys()):
        problemas.append(f"'{ruta}': el manifiesto la lista como salida y no existe")
    for ruta in sorted(reales.keys() & manifiesto.outputs.keys()):
        contenido = reales[ruta].read_bytes()
        if sha256_hex(contenido) != manifiesto.outputs[ruta]:
            problemas.append(
                f"'{ruta}': su hash no es el del manifiesto; se edito a mano o no se regenero"
            )
        problemas.extend(verify_output(ruta, contenido))
    return problemas


def _comparar_entradas(manifiesto: GenerationManifest, repo_root: Path, datos: Path) -> list[str]:
    """Cada entrada contada existe y no cambio, y ninguna fuente quedo sin contar."""
    problemas: list[str] = []
    for ruta in sorted(_fuentes_del_arbol(datos) - manifiesto.inputs.keys()):
        problemas.append(
            f"'{ruta}': fuente que el manifiesto no cuenta; regenere con "
            "`mise run synthetic:generate`"
        )
    for ruta, esperado in sorted(manifiesto.inputs.items()):
        entrada = repo_root / ruta
        if not entrada.is_file():
            problemas.append(f"'{ruta}': el manifiesto la cuenta como entrada y no existe")
        elif sha256_hex(entrada.read_bytes()) != esperado:
            problemas.append(
                f"'{ruta}': la entrada cambio despues de generar; regenere con "
                "`mise run synthetic:generate`"
            )
    return problemas
