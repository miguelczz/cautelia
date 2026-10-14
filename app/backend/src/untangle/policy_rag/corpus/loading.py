"""Leer el corpus de `app/data/` y comprobarlo, antes de tocar la base (BR1.1 a BR1.3).

Dos pasos, en orden, y ninguno escribe:

1. **El manifiesto** (BR1.1): el hash de cada archivo del corpus contra
   `app/data/manifest.json`. Solo se comparan los archivos que esta unidad
   ingiere -- formularios, clausulas, relaciones, polizas -- nunca los casos
   sembrados ni las fuentes, que no son de U8.
2. **La validacion estructural** (BR1.2): dos clausulas con el mismo
   `clause_id`, una poliza que referencia un endoso que no existe, o una
   relacion hacia una clausula inexistente. Se recogen **todos** los problemas
   antes de fallar, no solo el primero: la ingesta no es parcial, asi que un
   fallo tiene que decir todo lo que esta mal de una vez, no descubrirse un
   problema por corrida.

Nada de esto llama al proveedor ni abre una sesion: es lectura de archivos y
comparacion de tipos, la capa mas baja de la unidad.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from untangle import paths
from untangle.policy_rag.corpus.models import (
    Clause,
    ClauseRelation,
    IssuedPolicy,
    PolicyForm,
)
from untangle.tenancy.models import TenantId


class ManifestMismatchError(ValueError):
    """Un archivo del corpus no casa con su manifiesto (BR1.1).

    El mensaje nombra **todos** los archivos que no casan, con el hash
    esperado y el que se encontro: no se ingiere nada mientras alguno falle.
    """


class CorpusValidationError(ValueError):
    """El corpus no pasa su validacion estructural (BR1.2).

    El mensaje nombra el archivo y el identificador de cada problema. No hay
    ingesta parcial: si algo de esto se levanta, no se escribio ninguna fila.
    """


@dataclass(frozen=True)
class LoadedCorpus:
    """El corpus de una aseguradora, ya leido y validado, listo para indexar."""

    tenant_id: TenantId
    forms: tuple[PolicyForm, ...]
    clauses: tuple[Clause, ...]
    relations: tuple[ClauseRelation, ...]
    policies: tuple[IssuedPolicy, ...]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _corpus_files(tenant_dir: Path) -> tuple[Path, ...]:
    """Los archivos de un corpus de aseguradora que U8 ingiere, y solo esos.

    `cases/` es de U4 (casos sembrados) y no de esta unidad; un archivo que no
    cambia no aparece aqui aunque el manifiesto lo liste.
    """
    archivos = [
        *sorted((tenant_dir / "forms").glob("*.json")),
        *sorted((tenant_dir / "clauses").glob("*.json")),
        *sorted((tenant_dir / "issued_policies").glob("*.json")),
    ]
    relaciones = tenant_dir / "clause_relations.json"
    if relaciones.is_file():
        archivos.append(relaciones)
    return tuple(archivos)


def verify_manifest(
    tenant_id: TenantId, *, repo_root: Path | None = None, manifest_path: Path | None = None
) -> None:
    """Compara el hash de cada archivo del corpus de esa aseguradora (BR1.1).

    Se llama **antes** de leer ningun archivo para el resto de la ingesta: un
    archivo que no casa con su manifiesto no se lee, se nombra y se detiene
    todo. `repo_root` y `manifest_path` existen para las pruebas, que siembran
    un corpus minimo en un directorio temporal en vez de `app/data/`.
    """
    base = repo_root if repo_root is not None else paths.repo_root()
    ruta_manifiesto = (
        manifest_path if manifest_path is not None else paths.synthetic_manifest_path()
    )
    manifiesto = json.loads(ruta_manifiesto.read_text(encoding="utf-8"))
    salidas: dict[str, str] = manifiesto["outputs"]

    tenant_dir = (
        paths.corpus_tenants_dir() if repo_root is None else base / "app" / "data" / "tenants"
    ) / tenant_id

    problemas: list[str] = []
    for archivo in _corpus_files(tenant_dir):
        clave = archivo.relative_to(base).as_posix()
        esperado = salidas.get(clave)
        if esperado is None:
            problemas.append(f"'{clave}' no aparece en el manifiesto ('{ruta_manifiesto}')")
            continue
        real = _sha256(archivo)
        if real != esperado:
            problemas.append(
                f"'{clave}': el manifiesto esperaba '{esperado}' y el archivo da '{real}'"
            )

    if problemas:
        msg = "el corpus no casa con su manifiesto (BR1.1):\n" + "\n".join(
            f"  - {problema}" for problema in problemas
        )
        raise ManifestMismatchError(msg)


def _read_json(path: Path) -> dict[str, Any]:
    resultado: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return resultado


def _load_forms(
    tenant_dir: Path, tenant_id: TenantId, *, problems: list[str]
) -> tuple[PolicyForm, ...]:
    forms: list[PolicyForm] = []
    for archivo in sorted((tenant_dir / "forms").glob("*.json")):
        datos = _read_json(archivo)
        try:
            forms.append(PolicyForm.model_validate({**datos, "tenant_id": tenant_id}))
        except ValidationError as error:
            problems.append(f"'{archivo}': {_claves(error)}")
    return tuple(forms)


def _load_clauses(
    tenant_dir: Path, tenant_id: TenantId, *, problems: list[str]
) -> tuple[Clause, ...]:
    clauses: list[Clause] = []
    vistas_clause_id: dict[str, Path] = {}
    for archivo in sorted((tenant_dir / "clauses").glob("*.json")):
        datos = _read_json(archivo)
        for cruda in datos.get("clauses", []):
            try:
                clausula = Clause.model_validate({**cruda, "tenant_id": tenant_id})
            except ValidationError as error:
                problems.append(f"'{archivo}': {_claves(error)}")
                continue
            # BR1.2: dos clausulas con el mismo clause_id detienen la ingesta,
            # nombrando los dos archivos.
            if clausula.clause_id in vistas_clause_id:
                problems.append(
                    f"'{archivo}': el identificador '{clausula.clause_id}' ya aparecio en "
                    f"'{vistas_clause_id[clausula.clause_id]}' (BR1.2)"
                )
                continue
            vistas_clause_id[clausula.clause_id] = archivo
            clauses.append(clausula)
    return tuple(clauses)


def _load_relations(
    tenant_dir: Path, tenant_id: TenantId, *, clause_ids: set[str], problems: list[str]
) -> tuple[ClauseRelation, ...]:
    relations: list[ClauseRelation] = []
    relaciones_path = tenant_dir / "clause_relations.json"
    if not relaciones_path.is_file():
        return ()

    datos = _read_json(relaciones_path)
    for cruda in datos.get("relations", []):
        try:
            relations.append(ClauseRelation.model_validate({**cruda, "tenant_id": tenant_id}))
        except ValidationError as error:
            problems.append(f"'{relaciones_path}': {_claves(error)}")

    # BR1.2: una relacion hacia una clausula inexistente.
    for relacion in relations:
        if relacion.from_clause not in clause_ids:
            problems.append(
                f"'{relaciones_path}': la relacion '{relacion.relation_id}' parte de "
                f"'{relacion.from_clause}', que no existe (BR1.2)"
            )
        if relacion.to_clause not in clause_ids:
            problems.append(
                f"'{relaciones_path}': la relacion '{relacion.relation_id}' apunta a "
                f"'{relacion.to_clause}', que no existe (BR1.2)"
            )
    return tuple(relations)


def _load_policies(
    tenant_dir: Path,
    tenant_id: TenantId,
    *,
    known_endorsement_ids: set[str],
    problems: list[str],
) -> tuple[IssuedPolicy, ...]:
    policies: list[IssuedPolicy] = []
    for archivo in sorted((tenant_dir / "issued_policies").glob("*.json")):
        datos = _read_json(archivo)
        try:
            policies.append(IssuedPolicy.model_validate({**datos, "tenant_id": tenant_id}))
        except ValidationError as error:
            problems.append(f"'{archivo}': {_claves(error)}")

    # BR1.2: una poliza que referencia un endoso sin version, es decir, un
    # `form_id` de endoso que ningun formulario de esta aseguradora declara.
    for policy in policies:
        for endoso in policy.endorsement_ids:
            if endoso not in known_endorsement_ids:
                problems.append(
                    f"la poliza '{policy.policy_number}' referencia el endoso "
                    f"'{endoso}', que ningun formulario de '{tenant_id}' declara (BR1.2)"
                )
    return tuple(policies)


def load_corpus(tenant_id: TenantId, *, corpus_tenants_dir: Path | None = None) -> LoadedCorpus:
    """Lee y valida el corpus de una aseguradora. No escribe nada (BR1.2, BR1.3).

    `corpus_tenants_dir` existe para las pruebas: un corpus minimo sembrado en
    un directorio temporal, nunca `app/data/` directamente (salvo la prueba de
    CG-U8-2, que es justamente la que lo comprueba).
    """
    base_tenants = (
        corpus_tenants_dir if corpus_tenants_dir is not None else paths.corpus_tenants_dir()
    )
    tenant_dir = base_tenants / tenant_id
    if not tenant_dir.is_dir():
        msg = f"no existe el corpus de '{tenant_id}': se esperaba '{tenant_dir}'"
        raise CorpusValidationError(msg)

    problemas: list[str] = []
    forms = _load_forms(tenant_dir, tenant_id, problems=problemas)
    clauses = _load_clauses(tenant_dir, tenant_id, problems=problemas)
    relations = _load_relations(
        tenant_dir, tenant_id, clause_ids={c.clause_id for c in clauses}, problems=problemas
    )
    endorsement_ids = {f.form_id for f in forms if f.form_kind.value == "endorsement"}
    policies = _load_policies(
        tenant_dir, tenant_id, known_endorsement_ids=endorsement_ids, problems=problemas
    )

    if problemas:
        msg = f"el corpus de '{tenant_id}' no pasa su validacion (BR1.2):\n" + "\n".join(
            f"  - {problema}" for problema in problemas
        )
        raise CorpusValidationError(msg)

    return LoadedCorpus(
        tenant_id=tenant_id, forms=forms, clauses=clauses, relations=relations, policies=policies
    )


def _claves(error: ValidationError) -> str:
    return ", ".join(
        ".".join(str(parte) for parte in problema["loc"]) or "(raiz)" for problema in error.errors()
    )
