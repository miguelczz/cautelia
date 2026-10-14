"""Un corpus minimo sembrado en un directorio temporal (unit-test-instructions.md).

Un formulario base, dos endosos, una version anterior con un distractor
declarado: lo mismo que pide "Datos de prueba" para las pruebas de ingesta,
nunca `app/data/` directamente -- salvo la prueba de CG-U8-2, que es
justamente la que lo comprueba contra el corpus real.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

TENANT_ID = "testco"

_FORM_BASE: dict[str, object] = {
    "form_id": "TCO-PAP-2026",
    "form_kind": "base",
    "form_version": "2026.1",
    "issuer_label": "Testco Mutual",
    "issuer_tenant": TENANT_ID,
    "jurisdiction_ref": None,
    "language": "es",
    "clause_ids": ["TCO-PAP-2026-AGREEMENT.1", "TCO-PAP-2026-A.LIMIT"],
}

_FORM_BASE_OLD: dict[str, object] = {
    "form_id": "TCO-PAP-2025",
    "form_kind": "base",
    "form_version": "2025.1",
    "issuer_label": "Testco Mutual",
    "issuer_tenant": TENANT_ID,
    "jurisdiction_ref": None,
    "language": "es",
    "clause_ids": ["TCO-PAP-2025-AGREEMENT.1.ALT"],
}

_FORM_END_1: dict[str, object] = {
    "form_id": "TCO-PAP-2026-END-1",
    "form_kind": "endorsement",
    "form_version": "2026.1",
    "issuer_label": "Testco Mutual",
    "issuer_tenant": TENANT_ID,
    "jurisdiction_ref": None,
    "language": "es",
    "clause_ids": ["TCO-PAP-2026-END-1-A.LIMIT"],
}

_FORM_END_2: dict[str, object] = {
    "form_id": "TCO-PAP-2026-END-2",
    "form_kind": "endorsement",
    "form_version": "2026.1",
    "issuer_label": "Testco Mutual",
    "issuer_tenant": TENANT_ID,
    "jurisdiction_ref": None,
    "language": "es",
    "clause_ids": [],
}

_CLAUSES_BASE: dict[str, object] = {
    "form_id": "TCO-PAP-2026",
    "clauses": [
        {
            "clause_id": "TCO-PAP-2026-AGREEMENT.1",
            "clause_key": "AGREEMENT.1",
            "form_id": "TCO-PAP-2026",
            "form_version": "2026.1",
            "part": "Acuerdo",
            "language": "es",
            "text": "Testco protege al asegurado en los terminos de este contrato.",
            "is_distractor": False,
            "issuer_label": "Testco Mutual",
        },
        {
            "clause_id": "TCO-PAP-2026-A.LIMIT",
            "clause_key": "A.LIMIT",
            "form_id": "TCO-PAP-2026",
            "form_version": "2026.1",
            "part": "Parte A",
            "language": "es",
            "text": "El limite por persona es el que muestra la caratula.",
            "is_distractor": False,
            "issuer_label": "Testco Mutual",
        },
    ],
}

_CLAUSES_BASE_OLD: dict[str, object] = {
    "form_id": "TCO-PAP-2025",
    "clauses": [
        {
            "clause_id": "TCO-PAP-2025-AGREEMENT.1.ALT",
            "clause_key": "AGREEMENT.1",
            "form_id": "TCO-PAP-2025",
            "form_version": "2025.1",
            "part": "Acuerdo",
            "language": "es",
            "text": "Version anterior del acuerdo, que ya no aplica (distractor).",
            "is_distractor": True,
            "issuer_label": "Testco Mutual",
        },
    ],
}

_CLAUSES_END_1: dict[str, object] = {
    "form_id": "TCO-PAP-2026-END-1",
    "clauses": [
        {
            "clause_id": "TCO-PAP-2026-END-1-A.LIMIT",
            "clause_key": "A.LIMIT",
            "form_id": "TCO-PAP-2026-END-1",
            "form_version": "2026.1",
            "part": "Endoso 1",
            "language": "es",
            "text": "El endoso 1 sube el limite de la parte A.",
            "is_distractor": False,
            "issuer_label": "Testco Mutual",
        },
    ],
}

_CLAUSES_END_2: dict[str, object] = {"form_id": "TCO-PAP-2026-END-2", "clauses": []}

_RELATIONS: dict[str, object] = {
    "relations": [
        {
            "from_clause": "TCO-PAP-2026-END-1-A.LIMIT",
            "relation": "endorsement_modifies",
            "to_clause": "TCO-PAP-2026-A.LIMIT",
        },
    ],
}

_POLICY: dict[str, object] = {
    "policy_number": "POL-TEST-001",
    "tenant_id": TENANT_ID,
    "issuer_tenant": TENANT_ID,
    "form_id": "TCO-PAP-2026",
    "form_version": "2026.1",
    "endorsement_ids": ["TCO-PAP-2026-END-1"],
    "named_insured": {"full_name": "Persona de Prueba"},
    "vehicles": [],
    "limits_and_deductibles": {},
    "period_start": "2026-01-01",
    "period_end": "2027-01-01",
}


@dataclass(frozen=True)
class SeededCorpus:
    """Donde quedo el corpus sembrado, listo para `verify_manifest`/`load_corpus`."""

    repo_root: Path
    manifest_path: Path
    corpus_tenants_dir: Path
    tenant_id: str

    def write_form_file(self, name: str, content: dict[str, object]) -> Path:
        """Sobrescribe un archivo del corpus y actualiza su hash en el manifiesto.

        Sirve para las pruebas que corrompen el corpus a proposito (BR1.2): la
        prueba pasa el archivo ya roto y este metodo deja el manifiesto
        consistente, para que el fallo que se busca sea el de la validacion
        estructural y no el del manifiesto.
        """
        relativo = name
        ruta = self.corpus_tenants_dir / self.tenant_id / relativo
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(content), encoding="utf-8")
        _actualizar_manifiesto(self.manifest_path, self.repo_root, ruta)
        return ruta

    def corrupt_manifest_hash(self, name: str) -> None:
        """Deja el manifiesto con un hash que ya no casa (BR1.1)."""
        manifiesto = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        clave = (
            (self.corpus_tenants_dir / self.tenant_id / name).relative_to(self.repo_root).as_posix()
        )
        manifiesto["outputs"][clave] = "0" * 64
        self.manifest_path.write_text(json.dumps(manifiesto), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _actualizar_manifiesto(manifest_path: Path, repo_root: Path, archivo: Path) -> None:
    manifiesto = json.loads(manifest_path.read_text(encoding="utf-8"))
    clave = archivo.relative_to(repo_root).as_posix()
    manifiesto["outputs"][clave] = _sha256(archivo)
    manifest_path.write_text(json.dumps(manifiesto), encoding="utf-8")


@pytest.fixture
def seeded_corpus(tmp_path: Path) -> SeededCorpus:
    """Un corpus minimo de `testco`, con manifiesto consistente desde el inicio."""
    repo_root = tmp_path
    tenants_dir = repo_root / "app" / "data" / "tenants"
    tenant_dir = tenants_dir / TENANT_ID

    archivos: dict[str, dict[str, object]] = {
        "forms/TCO-PAP-2026.json": _FORM_BASE,
        "forms/TCO-PAP-2025.json": _FORM_BASE_OLD,
        "forms/TCO-PAP-2026-END-1.json": _FORM_END_1,
        "forms/TCO-PAP-2026-END-2.json": _FORM_END_2,
        "clauses/TCO-PAP-2026.json": _CLAUSES_BASE,
        "clauses/TCO-PAP-2025.json": _CLAUSES_BASE_OLD,
        "clauses/TCO-PAP-2026-END-1.json": _CLAUSES_END_1,
        "clauses/TCO-PAP-2026-END-2.json": _CLAUSES_END_2,
        "clause_relations.json": _RELATIONS,
        "issued_policies/POL-TEST-001.json": _POLICY,
    }

    outputs: dict[str, str] = {}
    for nombre, contenido in archivos.items():
        ruta = tenant_dir / nombre
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(contenido), encoding="utf-8")
        outputs[ruta.relative_to(repo_root).as_posix()] = _sha256(ruta)

    manifest_path = repo_root / "app" / "data" / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "generator_version": "test",
                "seed": 1,
                "declared_differences": [],
                "review_samples": [],
                "seeded_cases": [],
                "inputs": {},
                "outputs": outputs,
            }
        ),
        encoding="utf-8",
    )

    return SeededCorpus(
        repo_root=repo_root,
        manifest_path=manifest_path,
        corpus_tenants_dir=tenants_dir,
        tenant_id=TENANT_ID,
    )


@pytest.fixture
def rewrite_json() -> Callable[[Path, dict[str, object]], None]:
    """Sobrescribe un archivo JSON con nuevo contenido, sin tocar el manifiesto.

    Sirve para simular una corrupcion que el manifiesto **no** vio -- el
    archivo cambio despues de que el manifiesto se calculo -- y que por lo
    tanto BR1.1 tiene que atajar antes de que BR1.2 llegue a mirarlo.
    """

    def _escribir(path: Path, content: dict[str, object]) -> None:
        path.write_text(json.dumps(content), encoding="utf-8")

    return _escribir
