"""La validacion de la carpeta de una aseguradora (US5.1, BR1.1).

Lee archivos y devuelve **todas** las faltas, cada una con su archivo y su campo.
No la primera: obligar a descubrir un campo por corrida convierte dar de alta una
aseguradora en cinco intentos.

No escribe nada y no abre ninguna sesion: es lo que corre **antes** de crear la
aseguradora, porque una aseguradora a medias no la borra nada y no la completa
nada --se queda existiendo mal--.

Que tiene que traer una carpeta sale de lo que el cargador ya exige y de lo que
las unidades consumidoras necesitan para que la aseguradora funcione de verdad:

- `tenant.yaml` valido contra el esquema del cargador (nombre, idioma, voz, etc.);
- una voz **completa**: transcripcion, voz principal y de respaldo en los dos
  idiomas. El esquema las deja opcionales a proposito --una voz incompleta apaga
  la voz de una aseguradora ya existente, no la aseguradora (BR2.2)--, pero dar de
  alta una nueva sin voz no es aprovisionarla;
- al menos una persona de bandeja;
- el conjunto de reglas, valido en su forma y en su significado (las politicas de
  triage y derivacion de esa aseguradora);
- el corpus: formularios, clausulas y polizas emitidas;
- la poliza de ejemplo, que tiene que existir en ese corpus.

Las politicas de cumplimiento (`config/compliance`) no son por aseguradora: son las
mismas para todas, asi que aqui no hay nada que validarles.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from untangle.demo_operations.models import TenantFault, TenantFolderReport
from untangle.rules.loading import RULESET_FILE, validate_ruleset
from untangle.rules.models import RuleValidationError
from untangle.tenancy.config import RULES_DIR, TENANT_FILE
from untangle.tenancy.models import RuleSet, TenantConfig

#: Las tres carpetas del corpus de una aseguradora, tal como las lee la ingesta.
CLAUSES_DIR = "clauses"
FORMS_DIR = "forms"
POLICIES_DIR = "issued_policies"

#: Los idiomas en los que una voz tiene que existir para considerarse completa.
VOICE_LANGUAGES = ("es", "en")

#: Una poliza de ejemplo nombra un archivo: nada que salga de su carpeta.
_NOMBRE_DE_POLIZA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _falta(archivo: Path, campo: str, detalle: str) -> TenantFault:
    return TenantFault(file=str(archivo), field=campo, detail=detalle)


def _leer_yaml(archivo: Path) -> tuple[dict[str, Any] | None, list[TenantFault]]:
    """El mapa de la raiz del archivo, o la falta que explica por que no hay."""
    if not archivo.is_file():
        return None, [_falta(archivo, "(archivo)", "no existe")]
    try:
        cargado = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        return None, [_falta(archivo, "(archivo)", f"no es YAML legible: {type(error).__name__}")]
    if not isinstance(cargado, dict):
        return None, [_falta(archivo, "(raiz)", "no contiene un mapa en su raiz")]
    return cargado, []


def _campo(loc: tuple[int | str, ...]) -> str:
    return ".".join(str(parte) for parte in loc) or "(raiz)"


def _faltas_del_esquema(archivo: Path, error: ValidationError) -> list[TenantFault]:
    return [
        _falta(archivo, _campo(problema["loc"]), problema["msg"]) for problema in error.errors()
    ]


def _mapa(valor: object) -> Mapping[str, Any] | None:
    return valor if isinstance(valor, dict) else None


def _faltas_de_la_voz(archivo: Path, datos: Mapping[str, Any]) -> list[TenantFault]:
    """Una voz que se pueda encender: transcripcion, principal y respaldo por idioma.

    Si `voice` falta o no es un mapa, el esquema ya lo reporto; aqui no se repite.
    """
    voz = _mapa(datos.get("voice"))
    if voz is None:
        return []

    faltas: list[TenantFault] = []
    if _mapa(voz.get("stt")) is None:
        faltas.append(_falta(archivo, "voice.stt", "falta el modelo de transcripcion"))
    for bloque in ("primary", "fallback"):
        por_idioma = _mapa(voz.get(bloque))
        if por_idioma is None:
            faltas.append(_falta(archivo, f"voice.{bloque}", "falta la voz en los dos idiomas"))
            continue
        faltas.extend(
            _falta(archivo, f"voice.{bloque}.{idioma}", f"falta la voz en '{idioma}'")
            for idioma in VOICE_LANGUAGES
            if _mapa(por_idioma.get(idioma)) is None
        )
    return faltas


def _faltas_de_la_carpeta(
    folder: Path, archivo: Path, datos: Mapping[str, Any]
) -> list[TenantFault]:
    """Lo que el esquema no dice: las personas y que el identificador nombre la carpeta."""
    faltas: list[TenantFault] = []

    declarado = datos.get("tenant_id")
    if isinstance(declarado, str) and declarado != folder.name:
        faltas.append(
            _falta(
                archivo,
                "tenant_id",
                f"declara '{declarado}' y vive en la carpeta '{folder.name}': "
                "el identificador nombra la carpeta",
            )
        )

    personas = datos.get("staff")
    if personas is None or personas == []:
        faltas.append(_falta(archivo, "staff", "falta al menos una persona de bandeja"))

    return faltas


def _faltas_de_las_reglas(folder: Path, tenant_id: str) -> list[TenantFault]:
    archivo = folder / RULES_DIR / RULESET_FILE
    datos, faltas = _leer_yaml(archivo)
    if datos is None:
        return faltas
    try:
        conjunto = RuleSet.model_validate(datos)
    except ValidationError as error:
        return _faltas_del_esquema(archivo, error)
    try:
        validate_ruleset(conjunto, tenant_id=tenant_id)
    except RuleValidationError as error:
        return [_falta(archivo, "rules", str(error))]
    return []


def _json_del_corpus(carpeta: Path) -> list[Path]:
    return sorted(carpeta.glob("*.json")) if carpeta.is_dir() else []


def _faltas_de_la_poliza(politicas: Path, ejemplo: object, tenant_yaml: Path) -> list[TenantFault]:
    """La poliza de ejemplo existe en el corpus y es la que dice ser."""
    if not isinstance(ejemplo, str) or not ejemplo:
        return []  # ausente o mal formada: el esquema ya lo reporto
    if not _NOMBRE_DE_POLIZA.match(ejemplo):
        return [_falta(tenant_yaml, "example_policy", "no es un nombre de poliza valido")]

    archivo = politicas / f"{ejemplo}.json"
    if not archivo.is_file():
        return [
            _falta(
                tenant_yaml,
                "example_policy",
                f"la poliza '{ejemplo}' no esta en el corpus: se esperaba '{archivo}'",
            )
        ]
    try:
        contenido = json.loads(archivo.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [_falta(archivo, "(archivo)", f"no es JSON legible: {type(error).__name__}")]
    numero = contenido.get("policy_number") if isinstance(contenido, dict) else None
    if numero != ejemplo:
        return [
            _falta(
                archivo,
                "policy_number",
                f"declara '{numero}' y el archivo es el de la poliza de ejemplo '{ejemplo}'",
            )
        ]
    return []


def _faltas_del_corpus(corpus: Path, ejemplo: object, tenant_yaml: Path) -> list[TenantFault]:
    faltas = [
        _falta(corpus / nombre, "(carpeta)", "no trae ningun archivo .json")
        for nombre in (FORMS_DIR, CLAUSES_DIR, POLICIES_DIR)
        if not _json_del_corpus(corpus / nombre)
    ]
    faltas.extend(_faltas_de_la_poliza(corpus / POLICIES_DIR, ejemplo, tenant_yaml))
    return faltas


def validate_tenant_folder(folder: Path, *, corpus_root: Path) -> TenantFolderReport:
    """Valida la carpeta entera y devuelve todas las faltas (BR1.1).

    `folder` es `.../tenants/<id>` y `corpus_root` es el directorio de corpus por
    aseguradora; el corpus de la carpeta esta en `corpus_root/<id>`. No escribe
    nada: lo que hace falta para crear la aseguradora empieza despues de esto.
    """
    tenant_id = folder.name
    archivo = folder / TENANT_FILE
    faltas: list[TenantFault] = []

    datos, leyendo = _leer_yaml(archivo)
    faltas.extend(leyendo)
    ejemplo: object = None
    if datos is not None:
        ejemplo = datos.get("example_policy")
        try:
            TenantConfig.model_validate(datos)
        except ValidationError as error:
            faltas.extend(_faltas_del_esquema(archivo, error))
        faltas.extend(_faltas_de_la_voz(archivo, datos))
        faltas.extend(_faltas_de_la_carpeta(folder, archivo, datos))

    faltas.extend(_faltas_de_las_reglas(folder, tenant_id))
    faltas.extend(_faltas_del_corpus(corpus_root / tenant_id, ejemplo, archivo))

    return TenantFolderReport(tenant_id=tenant_id, missing=tuple(faltas))
