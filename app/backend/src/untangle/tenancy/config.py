"""El cargador de las carpetas de aseguradora (C-25, BR4.1 a BR4.4).

Es la pieza mas baja del modulo: **no depende de ninguna otra**. Si dependiera de
la sesion, validar la configuracion exigiria una base de datos y arrancar sin
base dejaria de poder decir que carpeta esta rota.

Cada carpeta se valida **por separado**. Una rota apaga solo su aseguradora,
nombrando el archivo y la clave; las demas siguen vivas. Un error de una carpeta
que tumbara las tres convertiria un descuido de configuracion en una caida total
(BR4.1).

Anadir una cuarta aseguradora es anadir una carpeta: este modulo recorre el
directorio, no una lista escrita a mano (BR4.3).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from untangle import observability, paths
from untangle.tenancy.models import (
    RuleSet,
    TenantConfig,
    TenantConfigError,
    TenantId,
    UnavailableTenant,
    UnknownTenantError,
)

#: El archivo que declara una aseguradora dentro de su carpeta.
TENANT_FILE = "tenant.yaml"

#: Donde viven sus reglas. Su **forma** la fija U2; su significado es de U9, que
#: las ejecuta, y por eso aqui solo se valida la estructura del archivo.
RULES_DIR = "rules"


@dataclass(frozen=True)
class LoadedTenants:
    """Lo que quedo tras recorrer el directorio: lo que vale y lo que no."""

    available: tuple[TenantConfig, ...]
    unavailable: tuple[UnavailableTenant, ...]

    def get(self, tenant_id: TenantId) -> TenantConfig | None:
        for tenant in self.available:
            if tenant.tenant_id == tenant_id:
                return tenant
        return None

    @property
    def ids(self) -> tuple[TenantId, ...]:
        return tuple(tenant.tenant_id for tenant in self.available)


def _read_yaml(path: Path) -> dict[str, object]:
    try:
        crudo = path.read_text(encoding="utf-8")
    except OSError as error:
        msg = f"no se pudo leer '{path}': {error}"
        raise TenantConfigError(msg) from error

    try:
        cargado = yaml.safe_load(crudo)
    except yaml.YAMLError as error:
        msg = f"'{path}' no es YAML valido: {error}"
        raise TenantConfigError(msg) from error

    if not isinstance(cargado, dict):
        encontrado = type(cargado).__name__
        msg = f"'{path}' no contiene un mapa en su raiz, sino {encontrado}"
        raise TenantConfigError(msg)
    return cargado


def _claves_del_error(error: ValidationError) -> str:
    """La clave rota de cada problema **y su mensaje**.

    El mensaje hacia falta: los validadores de modelo --el que exige el emisor de
    una agencia, el que prohibe dos personas con el mismo identificador-- no tienen
    clave, asi que su problema salia como `(raiz)` y la razon, que esta escrita en
    el propio validador, no llegaba a ningun sitio. Quien lee esto es quien tiene
    que arreglar la carpeta, y "claves: (raiz)" le obliga a leer el codigo.
    """
    return "; ".join(
        f"{'.'.join(str(parte) for parte in problema['loc']) or '(raiz)'}: {problema['msg']}"
        for problema in error.errors()
    )


def load_tenant(folder: Path) -> TenantConfig:
    """Una carpeta, validada. El fallo nombra el archivo y la clave rota."""
    archivo = folder / TENANT_FILE
    if not archivo.is_file():
        msg = f"la carpeta '{folder}' no tiene '{TENANT_FILE}'"
        raise TenantConfigError(msg)

    datos = _read_yaml(archivo)
    try:
        tenant = TenantConfig.model_validate(datos)
    except ValidationError as error:
        msg = f"'{archivo}' no valida su esquema; claves: {_claves_del_error(error)}"
        raise TenantConfigError(msg) from error

    if tenant.tenant_id != folder.name:
        msg = (
            f"'{archivo}' declara tenant_id '{tenant.tenant_id}' y vive en la "
            f"carpeta '{folder.name}': el identificador nombra la carpeta"
        )
        raise TenantConfigError(msg)

    for archivo_de_reglas in sorted((folder / RULES_DIR).glob("*.yaml")):
        load_ruleset(archivo_de_reglas)

    return tenant


def load_ruleset(path: Path) -> RuleSet:
    """Un archivo de reglas, validado en su forma (C-25)."""
    datos = _read_yaml(path)
    try:
        return RuleSet.model_validate(datos)
    except ValidationError as error:
        msg = f"'{path}' no valida su esquema; claves: {_claves_del_error(error)}"
        raise TenantConfigError(msg) from error


def load(root: Path | None = None) -> LoadedTenants:
    """Recorre el directorio de aseguradoras y valida cada carpeta por separado."""
    directorio = root if root is not None else paths.tenants_dir()
    if not directorio.is_dir():
        msg = f"no existe el directorio de aseguradoras: se esperaba '{directorio}'"
        raise TenantConfigError(msg)

    disponibles: list[TenantConfig] = []
    caidas: list[UnavailableTenant] = []

    for carpeta in sorted(p for p in directorio.iterdir() if p.is_dir()):
        try:
            disponibles.append(load_tenant(carpeta))
        except TenantConfigError as error:
            # La carpeta rota apaga **solo la suya**, y su razon sale por el
            # punto unico de salida para que el fallo no sea silencioso.
            caidas.append(UnavailableTenant(tenant_id=carpeta.name, detail=str(error)))
            observability.emit(
                "tenancy.tenant_unavailable",
                tenant_id=carpeta.name,
                detail=str(error),
            )

    return LoadedTenants(available=tuple(disponibles), unavailable=tuple(caidas))


_loaded: LoadedTenants | None = None


def install(tenants: LoadedTenants) -> None:
    """Fija la configuracion del proceso. La llama la raiz de composicion."""
    global _loaded
    _loaded = tenants


def loaded() -> LoadedTenants:
    """La configuracion del proceso, cargandola la primera vez si hace falta."""
    global _loaded
    if _loaded is None:
        _loaded = load()
    return _loaded


def reset() -> None:
    """Olvida lo cargado. Lo usan las pruebas para no compartir estado."""
    global _loaded
    _loaded = None


def require(tenant_id: TenantId) -> TenantConfig:
    """La aseguradora, o un fallo que la nombra.

    No devuelve `None` ni una configuracion vacia: un modulo podria consultar la
    nada durante semanas creyendo que la aseguradora no tiene datos (BR1.5).
    """
    tenant = loaded().get(tenant_id)
    if tenant is None:
        disponibles = ", ".join(loaded().ids) or "(ninguna)"
        msg = (
            f"la aseguradora '{tenant_id}' no esta en la configuracion cargada; "
            f"disponibles: {disponibles}"
        )
        raise UnknownTenantError(msg)
    return tenant


def available_ids() -> tuple[TenantId, ...]:
    """Los identificadores de las aseguradoras disponibles."""
    return loaded().ids
