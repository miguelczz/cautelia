"""Genera los artefactos de `app/contracts/` desde los modelos.

Los JSON Schema se generan desde los modelos de Pydantic, nunca se escriben a
mano (C-28). El chequeo de deriva del guion de verificacion corre este comando y
despues compara: si un modelo cambio y el artefacto no se regenero en el mismo
commit, la compuerta falla con el nombre del archivo.

Un artefacto generado nunca se arregla editandolo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from untangle import paths
from untangle.compliance.controls.patterns import PatternSet
from untangle.compliance.redaction.recognizers.models import RecognizerSet
from untangle.copy_catalog.keys_module import (
    render_characters_module,
    render_keys_module,
    render_texts_module,
)
from untangle.copy_catalog.loading import load_catalog
from untangle.copy_catalog.models import CopyEntry
from untangle.evals.loading import DatasetManifest
from untangle.evals.models import EvalRun, GoldenCase, SubsetDefinition
from untangle.evals.report import EvalReport
from untangle.providers.config import PricesConfig, ProvidersConfig
from untangle.synthetic_data import models as sinteticos
from untangle.tenancy import config as tenancy_config
from untangle.tenancy.models import RuleSet, TenantConfig

# Que modelo produce que archivo. La lista es explicita a proposito: un
# descubrimiento automatico generaria esquemas de modelos internos que nadie
# consume y que despues nadie se atreve a borrar.
ESQUEMAS: tuple[tuple[str, type[BaseModel]], ...] = (
    ("golden-case.schema.json", GoldenCase),
    ("subset.schema.json", SubsetDefinition),
    # El manifiesto de los ocho conjuntos de datos (U1, BR1.9). Se llamo
    # `manifest.schema.json` hasta U7, que es cuando llego el manifiesto al que
    # C-28 da ese nombre: el del corpus (C-26). Este paso a un nombre que dice
    # de cual se trata; ningun otro archivo lo referenciaba por el nombre viejo.
    ("dataset-manifest.schema.json", DatasetManifest),
    ("copy-entry.schema.json", CopyEntry),
    ("eval-run.schema.json", EvalRun),
    ("eval-report.schema.json", EvalReport),
    # La configuracion por aseguradora (C-25). El esquema del archivo es de U2;
    # el **significado** del bloque de reglas es de U9 y el de voz de U15 y U16,
    # y por eso `when`, `then` y sus casos quedan abiertos en el modelo.
    ("tenant.schema.json", TenantConfig),
    ("ruleset.schema.json", RuleSet),
    # El juego de reconocedores de la redaccion (U3). Lo genera el modelo, como
    # todos: validar contra el modelo y validar contra el esquema son la misma
    # comprobacion. Importa que exista porque **U21 lee esos archivos** para
    # comprobar que su segundo detector no comparte mecanismo con este, y sin el
    # esquema publicado tendria que adivinar la forma (AC4.14.1, BR4.6).
    ("recognizer-set.schema.json", RecognizerSet),
    # Los patrones de los controles de cumplimiento (U10, CG-U10-1): un archivo
    # por idioma y familia bajo `app/config/compliance/`. Regenerarlo con los
    # contratos es lo que deja sin deriva al esquema publicado (TECH-U10.2).
    ("compliance-pattern-set.schema.json", PatternSet),
    # La carpeta de proveedores (U5). Dos esquemas y no uno porque son dos
    # archivos con cadencias distintas: los precios llevan su propia version y
    # cambian sin que se toque nada de lo demas.
    ("providers.schema.json", ProvidersConfig),
    ("prices.schema.json", PricesConfig),
    # El corpus y su manifiesto (U7, C-26). Un esquema por **archivo** que existe,
    # no por modelo: la persona ficticia, el vehiculo y la clausula aparecen dentro
    # del esquema del archivo que los contiene. `manifest.schema.json` es el
    # nombre que C-28 reserva para el manifiesto de C-26.
    ("manifest.schema.json", sinteticos.GenerationManifest),
    ("corpus-form.schema.json", sinteticos.FormRecord),
    ("corpus-clauses.schema.json", sinteticos.ClauseFile),
    ("corpus-clause-relations.schema.json", sinteticos.ClauseRelationFile),
    ("corpus-issued-policy.schema.json", sinteticos.IssuedPolicyRecord),
    ("corpus-seeded-case.schema.json", sinteticos.SeededCaseRecord),
    # La lista de valores personales ficticios (FD-U7-8): la leen la prueba de
    # redaccion y los canarios de U21 sin cargar el manifiesto.
    ("corpus-personal-values.schema.json", sinteticos.PersonalValueList),
    # Las entradas revisadas del generador y las huellas de terceros (U7): se
    # escriben a mano o con un comando a mano, y el esquema es lo que las valida
    # antes de que el generador las lea.
    ("synthetic-source.schema.json", sinteticos.SourceFile),
    ("synthetic-review-sample.schema.json", sinteticos.ReviewSample),
    ("synthetic-differences.schema.json", sinteticos.DifferenceFile),
    ("synthetic-seeded-criteria.schema.json", sinteticos.SeededCriteriaFile),
    ("third-party-shingles.schema.json", sinteticos.FingerprintSet),
)


def _schema_for(model: type[BaseModel], filename: str) -> dict[str, Any]:
    esquema = model.model_json_schema(mode="serialization")
    esquema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    esquema["$id"] = f"https://untangle.local/contracts/schemas/{filename}"
    return esquema


def _write_if_changed(path: Path, contenido: str) -> bool:
    """Escribe solo si cambio, y dice si cambio."""
    path.parent.mkdir(parents=True, exist_ok=True)
    anterior = path.read_text(encoding="utf-8") if path.is_file() else None
    if anterior == contenido:
        return False
    path.write_text(contenido, encoding="utf-8")
    return True


def generate(
    schemas_root: Path | None = None,
    frontend_root: Path | None = None,
    tenants_root: Path | None = None,
) -> list[Path]:
    """Genera todos los artefactos y devuelve los que cambiaron."""
    destino_esquemas = schemas_root if schemas_root is not None else paths.schemas_dir()
    destino_frontend = frontend_root if frontend_root is not None else paths.frontend_copy_dir()

    cambiados: list[Path] = []

    for filename, model in ESQUEMAS:
        archivo = destino_esquemas / filename
        contenido = json.dumps(_schema_for(model, filename), indent=2, ensure_ascii=False) + "\n"
        if _write_if_changed(archivo, contenido):
            cambiados.append(archivo)

    # El modulo tipado de claves que consume la interfaz: una clave inexistente
    # deja de ser un texto vacio en pantalla y pasa a ser un error de tipos antes
    # de compilar (C-28, frontend-components.md).
    catalogo = load_catalog()
    modulo = destino_frontend / "copy-keys.ts"
    if _write_if_changed(modulo, render_keys_module(catalogo)):
        cambiados.append(modulo)

    # Las frases, para que la interfaz resuelva cada clave sin preguntar al
    # servidor (U6, BR2.3).
    # Un modulo por idioma: la interfaz carga solo el del arranque antes de pintar.
    for idioma in ("es", "en"):
        frases = destino_frontend / f"copy-texts.{idioma}.ts"
        if _write_if_changed(frases, render_texts_module(catalogo, idioma)):
            cambiados.append(frases)

    # La tabla cerrada del caracter de cada aseguradora (U6, BR4.2). Sale de las
    # aseguradoras que cargan: una carpeta rota se apaga sola al arrancar y aqui
    # tampoco aporta su clave.
    caracteres = destino_frontend / "tenant-characters.ts"
    claves = [
        aseguradora.character_key
        for aseguradora in tenancy_config.load(tenants_root).available
        if aseguradora.character_key is not None
    ]
    if _write_if_changed(caracteres, render_characters_module(claves)):
        cambiados.append(caracteres)

    return cambiados


def main() -> int:
    cambiados = generate()
    for archivo in cambiados:
        print(f"regenerado: {archivo}")
    if not cambiados:
        print("sin cambios: los contratos generados ya estaban al dia")
    return 0


if __name__ == "__main__":
    sys.exit(main())
